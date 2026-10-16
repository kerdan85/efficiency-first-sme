"""Hourly net-zero module: synthetic hourly load from monthly bills, hourly PV, greedy battery
dispatch and three compensation regimes (net metering with a credit bank, net metering with demand
billed on imports, and net billing).

Without interval data the hourly load is synthetic: an always-on load N (kW) plus a flat load during
operating hours. N is the most influential assumption of this module and is swept in the sensitivity.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .case import Case
from .core import apply_measures, cashflow, measure_cost, peak_after


# ----------------------------------------------------------------------------- weather / PV
def hourly_pv_per_kWp(case: Case, P: dict) -> pd.DataFrame:
    if case.weather_hourly is None:
        raise ValueError("net-zero module needs data.weather_hourly")
    cc = case.cfg["case"]["location"]; wc = case.cfg["data"].get("weather_hourly_options", {})
    lat, lon, utc = cc["lat"], cc["lon"], cc.get("utc_offset", round(cc["lon"] / 15))
    label_utc = wc.get("label_utc_offset", utc)
    w = case.weather_hourly.copy()
    t = w.timestamp
    solar_offset = lon / 15 - label_utc            # hours: solar time minus label time
    doy = t.dt.dayofyear.to_numpy(); hr = t.dt.hour.to_numpy() + 0.5 + solar_offset
    phi = math.radians(lat); beta = math.radians(P["pv.tilt_deg"]); albedo = P["pv.albedo"]
    dec = np.radians(23.45 * np.sin(np.radians(360 * (284 + doy) / 365)))
    omega = np.radians(15 * (hr - 12))
    sgn = 1 if lat >= 0 else -1
    cosz = np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(omega)
    # array faces the equator: tilt toward the equator
    cost = np.sin(phi - sgn * beta) * np.sin(dec) + np.cos(phi - sgn * beta) * np.cos(dec) * np.cos(omega)
    ghi = w.GHI.to_numpy(float); dhi = np.minimum(w.DHI.to_numpy(float), ghi)
    rb = np.where(cosz > 0.087, np.maximum(cost, 0) / np.maximum(cosz, 0.087), 0.0)
    rb = np.minimum(rb, 5.0)
    poa = (ghi - dhi) * rb + dhi * (1 + math.cos(beta)) / 2 + ghi * albedo * (1 - math.cos(beta)) / 2
    w["POA"] = np.maximum(poa, 0); w["month"] = t.dt.month
    if wc.get("rescale_to_climatology", True):
        g = w.groupby("month").GHI.sum() / w.groupby("month").size() * 24 / 1000
        fac = case.climate.set_index("month").GHI / g
        w["POA"] = w.POA * w.month.map(fac)
    # after rolling by the label-to-clock offset, row i carries the irradiance of clock hour i,
    # so the timestamps can be read as local clock time (the year wraps at the ends)
    shift = int(round(utc - label_utc))
    if shift:
        w["POA"] = np.roll(w.POA.to_numpy(), shift)
    w["pv_kWh_per_kWp"] = w.POA / 1000 * P["pv.PR"]
    w["weekday"] = t.dt.weekday; w["hour"] = t.dt.hour
    return w


# ----------------------------------------------------------------------------- load
def operating_mask(case: Case, w: pd.DataFrame, month: int):
    s = case.cfg.get("schedule", {})
    wd0, wd1 = s.get("weekday_hours", [8, 18]); sa = s.get("saturday_hours"); su = s.get("sunday_hours")
    cont = set(s.get("continuous_months", []))
    hr, wd, mo = w.hour.to_numpy(), w.weekday.to_numpy(), w.month.to_numpy()
    idx = mo == month
    if month in cont:
        return idx & (wd <= (6 if s.get("continuous_includes_sunday") else 5))
    op = (wd <= 4) & (hr >= wd0) & (hr < wd1)
    if sa:
        op |= (wd == 5) & (hr >= sa[0]) & (hr < sa[1])
    if su:
        op |= (wd == 6) & (hr >= su[0]) & (hr < su[1])
    return idx & op


def operating_hours_per_month(case: Case) -> float:
    s = case.cfg.get("schedule", {})
    wd = s.get("weekday_hours", [8, 18]); sa = s.get("saturday_hours"); su = s.get("sunday_hours")
    h = (wd[1] - wd[0]) * 22 + ((sa[1] - sa[0]) * 4 if sa else 0) + ((su[1] - su[0]) * 4 if su else 0)
    return float(s.get("operating_hours_per_month", h))


def hourly_load(case: Case, q_month, w, night_kW):
    load = np.zeros(len(w)); mo = w.month.to_numpy()
    for q, m, n in zip(q_month, case.ref.mon.to_numpy(), night_kW):
        idx = mo == m; op = operating_mask(case, w, m)
        h_tot, h_op = idx.sum(), op.sum()
        n_eff = min(n, 0.9 * q / h_tot)
        load[idx] = n_eff
        load[op] += (q - n_eff * h_tot) / h_op
    return load


# ----------------------------------------------------------------------------- dispatch / billing
def dispatch(load, pv, cap_kWh, P):
    usable = cap_kWh * P["netzero.bat_dod"]; pmax = cap_kWh * P["netzero.bat_c_rate"]
    eta = math.sqrt(P["netzero.bat_rte"]); soc = 0.5 * usable
    imp = np.zeros_like(load); exp = np.zeros_like(load)
    for i in range(len(load)):
        net = pv[i] - load[i]
        if net >= 0:
            ch = min(net, pmax, (usable - soc) / eta) if usable > 0 else 0.0
            soc += ch * eta; exp[i] = net - ch
        else:
            dis = min(-net, pmax, soc * eta) if usable > 0 else 0.0
            soc -= dis / eta; imp[i] = -net - dis
    return imp, exp


def net_metering_bank(imp, exp, months_h, ref_months, expiry_months=12):
    bank = []; q_net = []; expired = 0.0
    for m in ref_months:
        net = imp[months_h == m].sum() - exp[months_h == m].sum()
        for c in bank:
            c[1] += 1
        expired += sum(c[0] for c in bank if c[1] > expiry_months)
        bank = [c for c in bank if c[1] <= expiry_months]
        if net >= 0:
            while net > 0 and bank:
                use = min(net, bank[0][0]); bank[0][0] -= use; net -= use
                if bank[0][0] <= 1e-9:
                    bank.pop(0)
            q_net.append(net)
        else:
            bank.append([-net, 0]); q_net.append(0.0)
    return np.array(q_net), expired


def evaluate_nz(case: Case, ids, kWp, bat_kWh, P, ctx, w, regime="net_metering", years_to_steady=5):
    """regime: net_metering | import_demand | net_billing"""
    ref = case.ref; days = ref.days.to_numpy(); months = ref.mon.to_numpy()
    q0 = ref.energy_kWh.to_numpy(float)
    q_ee, det = apply_measures(case, P, ctx["base_kWh"], ids)
    h_month = np.array([(w.month == m).sum() for m in months])
    nonop = h_month - operating_hours_per_month(case) * h_month / 730
    N = P["netzero.night_load_kW"]; night = np.full(12, N)
    for m in case.measures:
        if m.id in ids and m.type == "base_load":
            night = np.maximum(night - det[m.id] / nonop, 0.3 * N)
    load = hourly_load(case, q_ee, w, night)
    pv = w.pv_kWh_per_kWp.to_numpy() * kWp
    imp, exp = dispatch(load, pv, bat_kWh, P)
    mh = w.month.to_numpy()
    pfm = [m for m in case.measures if m.id in ids and m.type == "pf_correction"]
    pf0 = ref.power_factor.to_numpy(float)
    pf1 = np.full(12, P[f"measures.{pfm[0].id}.pf_after"]) if pfm else pf0
    T = case.tariff
    q_imp = np.array([imp[mh == m].sum() for m in months])
    dmax = ref.max_demand_kW.to_numpy(float)
    dmax1 = peak_after(case, dmax, q0, q_ee)   # efficiency lowers a measured peak; PV and storage are not credited
    expiry = int(case.cfg.get("netzero", {}).get("credit_expiry_months", 12))
    if regime in ("net_metering", "import_demand"):
        q_net, expired = net_metering_bank(imp, exp, mh, list(months) * years_to_steady, expiry)
        q_net = q_net[-12:]
        if regime == "net_metering":
            bill1 = float(np.sum(T.bill(q_net, days, pf1, dmax=dmax1)))
        else:
            bill1 = float(np.sum(T.bill(q_net, days, pf1, q_for_demand=q_imp, demand_credit=0.0, dmax=dmax1)))
        bill1 -= expired / max(years_to_steady - 1, 1) * P["netzero.expired_credit_value"]
    else:
        bill1 = float(np.sum(T.bill(q_imp, days, pf1, dmax=dmax1))) - exp.sum() * P["netzero.net_billing_export_value"]
    bill0 = float(np.sum(T.bill(q0, days, pf0, dmax=dmax)))
    items = [(m.id,) + measure_cost(case, P, m) for m in case.measures if m.id in ids]
    if kWp > 0:
        cap = kWp * 1000 * P["pv.cost_per_W"]; items.append(("PV", cap, P["pv.om_frac"] * cap, P["pv.life"]))
    if bat_kWh > 0:
        cap = bat_kWh * P["netzero.bat_cost_per_kWh"]
        items.append(("BAT", cap, P["netzero.bat_om_frac"] * cap, P["netzero.bat_life"]))
    sav = bill0 - bill1
    if kWp > 0:
        sav_pv = float(np.sum(T.bill(q_ee, days, pf1, dmax=dmax1))) - bill1
    else:
        sav_pv = 0.0
    npv, capex, _ = cashflow(items, sav - sav_pv, sav_pv, P)
    ef = P["grid.emission_factor"]
    return dict(kWp=kWp, bat_kWh=bat_kWh, roof_m2=kWp * P["pv.m2_per_kWp"], load_MWh=load.sum() / 1000,
                pv_MWh=pv.sum() / 1000, import_MWh=imp.sum() / 1000, export_MWh=exp.sum() / 1000,
                self_sufficiency=1 - imp.sum() / load.sum(), net_annual_MWh=(imp.sum() - exp.sum()) / 1000,
                co2_gross_t=imp.sum() / 1000 * ef, co2_net_t=max(imp.sum() - exp.sum(), 0) / 1000 * ef,
                bill0=bill0, bill1=bill1, savings=sav, capex=capex, npv=npv, night_kW=float(night.mean()),
                peak_load_kW=float(load.max()))


def size_pv_for_annual_nz(case: Case, ids, P, ctx, w):
    q_ee, _ = apply_measures(case, P, ctx["base_kWh"], ids)
    return q_ee.sum() / w.pv_kWh_per_kWp.sum()


def run_netzero(case: Case, P: dict, ctx: dict, sets: dict, progress=None) -> dict:
    """Sweep PV multiple x battery size for each measure set; return sweep, frontier and headline designs."""
    nz = case.cfg.get("netzero", {})
    mults = np.round(np.arange(*nz.get("pv_multipliers", [0.6, 2.41, 0.1])), 2)
    bats = list(range(*nz.get("battery_kWh", [0, 2401, 100])))
    limit = float(nz.get("pv_limit_kWp", 1e9))
    w = hourly_pv_per_kWp(case, P)
    out = dict(specific_yield_hourly=float(w.pv_kWh_per_kWp.sum()))
    rows = []
    for lab, ids in sets.items():
        k = size_pv_for_annual_nz(case, ids, P, ctx, w); out[f"kWp_nz_{lab}"] = float(k)
        for mult in mults:
            kwp = min(k * mult, limit)
            for bat in bats:
                e = evaluate_nz(case, ids, kwp, bat, P, ctx, w)
                e2 = evaluate_nz(case, ids, kwp, bat, P, ctx, w, "import_demand")
                e3 = evaluate_nz(case, ids, kwp, bat, P, ctx, w, "net_billing")
                e.update(set=lab, pv_mult=float(mult), npv_import_demand=e2["npv"], npv_net_billing=e3["npv"])
                rows.append(e)
        if progress:
            progress(lab)
    S = pd.DataFrame(rows)
    front = []
    for lab in sets:
        for tgt in np.arange(0.50, 0.951, 0.025):
            sub = S[(S.set == lab) & (S.self_sufficiency >= tgt - 1e-9)]
            if len(sub):
                b = sub.sort_values("capex").iloc[0]
                front.append(dict(set=lab, target=round(float(tgt), 3), capex=b.capex, kWp=b.kWp, bat_kWh=b.bat_kWh,
                                  npv=b.npv, npv_net_billing=b.npv_net_billing, roof_m2=b.roof_m2))
    F = pd.DataFrame(front)
    heads = {}
    for lab, ids in sets.items():
        heads[f"NZ-{lab}"] = evaluate_nz(case, ids, out[f"kWp_nz_{lab}"], 0, P, ctx, w)
        for tgt in nz.get("self_sufficiency_targets", [0.7, 0.8, 0.9]):
            sub = S[(S.set == lab) & (S.self_sufficiency >= tgt)]
            if len(sub):
                b = sub.sort_values("capex").iloc[0]
                heads[f"SS{int(round(tgt * 100))}-{lab}"] = b.to_dict()
            else:
                heads[f"SS{int(round(tgt * 100))}-{lab}"] = None
    out["max_self_sufficiency"] = {lab: float(S[S.set == lab].self_sufficiency.max()) for lab in sets}
    # sensitivity to the always-on load N (the synthetic-profile assumption), net metering only
    sens = []
    pN = case.P.params["netzero.night_load_kW"]
    tgt = float(nz.get("night_load_sensitivity_target", 0.8))
    for lab_n, N in (("low", pN.low), ("central", pN.central), ("high", pN.high)):
        if lab_n != "central" and pN.low == pN.high:
            continue
        Q = dict(P); Q["netzero.night_load_kW"] = N
        for lab, ids in sets.items():
            k = out[f"kWp_nz_{lab}"]; best = None
            for mult in mults:
                for bat in bats:
                    e = evaluate_nz(case, ids, min(k * mult, limit), bat, Q, ctx, w)
                    if e["self_sufficiency"] >= tgt and (best is None or e["capex"] < best["capex"]):
                        best = e
            nz0 = evaluate_nz(case, ids, k, 0, Q, ctx, w)
            sens.append(dict(night_load_kW=N, set=lab, ss_annual_nz=nz0["self_sufficiency"], target=tgt,
                             capex_at_target=best["capex"] if best else np.nan, kWp=best["kWp"] if best else np.nan,
                             bat_kWh=best["bat_kWh"] if best else np.nan))
    return dict(summary=out, sweep=S, frontier=F, designs=heads, weather=w, nightload=pd.DataFrame(sens))
