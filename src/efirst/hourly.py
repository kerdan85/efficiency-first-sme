"""Hourly net-zero module: synthetic load profile, hourly PV, battery dispatch,
monthly net metering with a 12-month credit bank (CRE RES/142/2017).

Hourly PV uses NASA POWER 2023 hourly irradiance at the site, transposed to the
array plane (isotropic sky) and rescaled month by month to the 2001-2025
climatology so that annual yield is consistent with the monthly model.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .model import RAW, annual_bill, billed_demand_kW, load_all, measure_capex, measure_savings, monthly_bill
from .params import HOURS_OPERATING_PER_MONTH, central

SHIFT_MONTHS = {11, 12, 1}
LON_SITE = -98.7624  # 24-h shifts in the reference year (Nov 2025 - Jan 2026)

NZ_PARAMS = {
    # name: (central, low, high, status, source)
    "night_load_kW": (15.0, 8.0, 25.0, "assumption", "always-on load outside shifts; needs interval data"),
    "bat_cost_per_kWh": (8500.0, 6000.0, 12000.0, "assumption", "installed C&I LFP; NREL ATB 2024 pack 199 USD/kWh + inverter/BOS"),
    "bat_rte": (0.85, 0.85, 0.85, "literature", "NREL ATB 2024 commercial battery"),
    "bat_dod": (0.90, 0.90, 0.90, "assumption", "usable fraction of nameplate"),
    "bat_c_rate": (0.5, 0.5, 0.5, "assumption", "kW per kWh"),
    "bat_om_frac": (0.025, 0.025, 0.025, "literature", "NREL ATB 2024: 2.5% of capex per year"),
    "bat_life": (15, 15, 15, "literature", "NREL ATB 2024"),
    "expired_credit_value": (0.0, 0.0, 1.0, "assumption", "MXN/kWh paid for credits older than 12 months (PML); 0 = conservative"),
    "net_billing_export_value": (1.0, 0.6, 1.5, "assumption", "MXN/kWh export value in a net-billing stress case"),
}


def nz_central():
    return {k: v[0] for k, v in NZ_PARAMS.items()}


# ----------------------------------------------------------------------------- PV
def hourly_pv_per_kWp(P: dict, lat=20.0965, tilt=20.0, albedo=0.2) -> pd.DataFrame:
    w = pd.read_csv(RAW / "nasa_power_hourly_2023_pachuca.csv", parse_dates=["timestamp_LST"])
    clim = pd.read_csv(RAW / "nasa_power_climatology_pachuca.csv").set_index("month")
    t = w.timestamp_LST
    # NASA POWER "LST" timestamps are UTC + round(lon/15) = UTC-7 at this site; label t covers
    # UTC-7 t..t+1, i.e. solar time t+0.42..t+1.42 and clock time (UTC-6) t+1..t+2.
    solar_offset = 7 + LON_SITE / 15  # hours, solar time minus UTC-7 label
    doy = t.dt.dayofyear.to_numpy(); hr = t.dt.hour.to_numpy() + 0.5 + solar_offset
    phi = math.radians(lat); beta = math.radians(tilt)
    dec = np.radians(23.45 * np.sin(np.radians(360 * (284 + doy) / 365)))
    omega = np.radians(15 * (hr - 12))
    cosz = np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(omega)
    cost = (np.sin(phi - beta) * np.sin(dec) + np.cos(phi - beta) * np.cos(dec) * np.cos(omega))
    ghi = w.GHI_Wm2.to_numpy(float); dhi = np.minimum(w.DHI_Wm2.to_numpy(float), ghi)
    bh = ghi - dhi
    rb = np.where(cosz > 0.087, np.maximum(cost, 0) / np.maximum(cosz, 0.087), 0.0)
    rb = np.minimum(rb, 5.0)
    poa = bh * rb + dhi * (1 + math.cos(beta)) / 2 + ghi * albedo * (1 - math.cos(beta)) / 2
    w["POA"] = np.maximum(poa, 0)
    w["month"] = t.dt.month
    # rescale to climatology month by month
    g23 = w.groupby("month").GHI_Wm2.sum() / w.groupby("month").size() * 24 / 1000
    fac = clim.GHI_kWh_m2_d / g23
    w["POA"] = w.POA * w.month.map(fac)
    # re-index from UTC-7 labels to local clock time (UTC-6): shift one hour later
    w["POA"] = np.roll(w.POA.to_numpy(), 1)
    w["pv_kWh_per_kWp"] = w.POA / 1000 * P["pv_PR"]
    w["weekday"] = t.dt.weekday
    return w


# ----------------------------------------------------------------------------- load
def hourly_load(q_month: np.ndarray, months: np.ndarray, w: pd.DataFrame, night_kW: np.ndarray) -> np.ndarray:
    """Distribute monthly energy into hours: an always-on load N plus a flat
    operating-hours load (Mon-Fri 08-18, Sat 08-13; Mon-Sat 24 h in shift months)."""
    load = np.zeros(len(w))
    hr = w.timestamp_LST.dt.hour.to_numpy(); wd = w.weekday.to_numpy(); mo = w.month.to_numpy()
    for q, m, n in zip(q_month, months, night_kW):
        idx = mo == m
        if m in SHIFT_MONTHS:
            op = idx & (wd <= 5)
        else:
            op = idx & (((wd <= 4) & (hr >= 8) & (hr < 18)) | ((wd == 5) & (hr >= 8) & (hr < 13)))
        h_tot = idx.sum(); h_op = op.sum()
        n_eff = min(n, 0.9 * q / h_tot)
        p_op = (q - n_eff * h_tot) / h_op
        load[idx] = n_eff
        load[op] += p_op
    return load


# ----------------------------------------------------------------------------- dispatch
def dispatch(load, pv, cap_kWh, NZ):
    """Greedy self-consumption battery. Returns imports, exports, battery throughput (kWh, hourly arrays)."""
    usable = cap_kWh * NZ["bat_dod"]; pmax = cap_kWh * NZ["bat_c_rate"]
    eta = math.sqrt(NZ["bat_rte"])
    soc = 0.5 * usable
    imp = np.zeros_like(load); exp = np.zeros_like(load)
    for i in range(len(load)):
        net = pv[i] - load[i]
        if net >= 0:
            ch = min(net, pmax, (usable - soc) / eta) if usable > 0 else 0.0
            soc += ch * eta
            exp[i] = net - ch
        else:
            dis = min(-net, pmax, soc * eta) if usable > 0 else 0.0
            soc -= dis / eta
            imp[i] = -net - dis
    return imp, exp


def monthly_net_metering(imp, exp, months_h, ref_months, NZ):
    """Monthly net metering with a 12-month rolling credit bank (FIFO)."""
    bank = []  # list of [kWh, age]
    q_net = []; expired = 0.0
    for m in ref_months:
        i = imp[months_h == m].sum(); e = exp[months_h == m].sum()
        net = i - e
        # age credits and expire >12 months
        for c in bank:
            c[1] += 1
        expired += sum(c[0] for c in bank if c[1] > 12)
        bank = [c for c in bank if c[1] <= 12]
        if net >= 0:
            while net > 0 and bank:
                use = min(net, bank[0][0]); bank[0][0] -= use; net -= use
                if bank[0][0] <= 1e-9:
                    bank.pop(0)
            q_net.append(net)
        else:
            bank.append([-net, 0]); q_net.append(0.0)
    return np.array(q_net), expired, sum(c[0] for c in bank)


# ----------------------------------------------------------------------------- scenario
def evaluate_nz(measures, kWp, bat_kWh, P=None, NZ=None, data=None, w=None, tariff_mode="net_metering",
                years_to_steady=5, demand_basis="net"):
    P = P or central(); NZ = NZ or nz_central(); data = data or load_all(P)
    w = w if w is not None else hourly_pv_per_kWp(P)
    ref = data["ref"]; tr = data["tariff"]
    q0 = ref.energy_kWh.to_numpy(float)
    meas = [m for m in measures if m != "E5"]
    q_ee, det = measure_savings(ref, P, data["intercept"], meas)
    months = ref.mon.to_numpy()
    h_month = np.array([(w.month == m).sum() for m in months])
    nonop = h_month - HOURS_OPERATING_PER_MONTH * h_month / 730
    night = np.full(12, NZ["night_load_kW"])
    if "E4" in det:
        night = np.maximum(night - det["E4"] / nonop, 0.3 * NZ["night_load_kW"])
    load = hourly_load(q_ee, months, w, night)
    pv = w.pv_kWh_per_kWp.to_numpy() * kWp
    imp, exp = dispatch(load, pv, bat_kWh, NZ)
    mh = w.month.to_numpy()
    pf1 = np.full(12, P["pfc_pf_after"]) if ("E5" in measures) else ref.power_factor.to_numpy()
    if tariff_mode == "net_metering":
        # run the bank to steady state (credits carried from previous year)
        q_net, expired, carry = monthly_net_metering(imp, exp, mh, list(months) * years_to_steady, NZ)
        q_net = q_net[-12:]
        q_imp = np.array([imp[mh == m].sum() for m in months])
        qd = None if demand_basis == "net" else q_imp
        bill1 = float(np.sum(monthly_bill(q_net, ref.days.to_numpy(), pf1, tr, demand_credit=0.0 if qd is not None else 1.0,
                                          q_for_demand=qd)))
        expired_y = expired / max(years_to_steady - 1, 1)
        bill1 -= expired_y * NZ["expired_credit_value"]
        export_credit = 0.0
    else:  # net billing: imports billed, exports paid at a fixed value
        q_imp = np.array([imp[mh == m].sum() for m in months])
        bill1 = float(np.sum(monthly_bill(q_imp, ref.days.to_numpy(), pf1, tr)))
        export_credit = exp.sum() * NZ["net_billing_export_value"]
        bill1 -= export_credit
        q_net = q_imp; expired_y = 0.0
    bill0 = annual_bill(q0, ref, P, tr)
    # capex
    tab, _ = measure_capex(P, ref, data["intercept"])
    items = [(m,) + tab[m] for m in measures]
    if kWp > 0:
        cap = kWp * 1000 * P["pv_cost_per_W"]; items.append(("PV", cap, P["pv_om_frac"] * cap, P["pv_life"]))
    if bat_kWh > 0:
        cap = bat_kWh * NZ["bat_cost_per_kWh"]; items.append(("BAT", cap, NZ["bat_om_frac"] * cap, NZ["bat_life"]))
    H = int(P["horizon_yr"]); r = P["discount_rate"]
    cf = np.zeros(H + 1); capex = 0.0
    for name, cap, om, life in items:
        capex += cap; cf[0] -= cap
        cf[1:] -= om
        if life < H:
            for y in range(int(life), H, int(life)):
                cf[y] -= cap
            last = (H // int(life)) * int(life)
            last = last if last < H else H - int(life)
            rem = last + life - H
            if rem > 0:
                cf[H] += cap * rem / life
        elif name == "PV":
            cf[12] -= P["pv_inverter_repl_frac"] * cap
            cf[H] += cap * (life - H) / life
    sav = bill0 - bill1
    # split savings into an efficiency part and a PV/storage part; the latter degrades with PV output
    if kWp > 0:
        bill_ee = float(np.sum(monthly_bill(q_ee, ref.days.to_numpy(), pf1, tr)))
        sav_pv = bill_ee - bill1; sav_ee = sav - sav_pv
    else:
        sav_pv, sav_ee = 0.0, sav
    yrs = np.arange(1, H + 1)
    cf[1:] += sav_ee + sav_pv * (1 - P["pv_degradation"]) ** (yrs - 1)
    npv = float(np.sum(cf * (1 + r) ** -np.arange(H + 1)))
    ef = P["ef_grid_t_per_MWh"]
    gross_imp = imp.sum(); gross_exp = exp.sum()
    ss = 1 - gross_imp / load.sum()
    return dict(load_MWh=load.sum() / 1000, pv_MWh=pv.sum() / 1000, import_MWh=gross_imp / 1000,
                export_MWh=gross_exp / 1000, self_sufficiency=ss,
                net_annual_MWh=(gross_imp - gross_exp) / 1000,
                co2_gross_t=gross_imp / 1000 * ef, co2_net_t=max(gross_imp - gross_exp, 0) / 1000 * ef,
                bill0=bill0, bill1=bill1, savings=sav, capex=capex, npv=npv,
                expired_credit_MWh=expired_y / 1000, night_kW=float(night.mean()),
                peak_load_kW=float(load.max()), autonomy_h=(bat_kWh * NZ["bat_dod"] / night.mean()) if bat_kWh else 0.0,
                billed_q_MWh=float(np.sum(q_net)) / 1000)


def size_pv_for_annual_nz(measures, P=None, NZ=None, data=None, w=None):
    """PV kWp such that annual PV generation equals annual consumption after measures."""
    P = P or central(); data = data or load_all(P)
    w = w if w is not None else hourly_pv_per_kWp(P)
    ref = data["ref"]
    meas = [m for m in measures if m != "E5"]
    q_ee, _ = measure_savings(ref, P, data["intercept"], meas)
    return q_ee.sum() / w.pv_kWh_per_kWp.sum()
