"""Core appraisal: baseline, PV yield, measures, cash flows, indicators, pathways."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .case import Case


# ----------------------------------------------------------------------------- baseline
def ols(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    b, a = np.polyfit(x, y, 1)
    yhat = a + b * x
    r2 = 1 - np.sum((y - yhat) ** 2) / np.sum((y - y.mean()) ** 2)
    n = len(x)
    se = math.sqrt(np.sum((y - yhat) ** 2) / (n - 2))
    return dict(slope=b, intercept=a, r2=r2, n=n, cv_rmse=se / y.mean())


def baseline(case: Case) -> dict:
    bc = case.cfg.get("baseline", {})
    col = bc.get("production_column", "production")
    b = case.billing
    out = {}
    if col in b.columns and b[col].notna().sum() >= 6:
        p = b.dropna(subset=[col])
        out["all"] = ols(p[col], p.energy_kWh)
        excl = [str(m) for m in bc.get("exclude_months", [])]
        q = p[~p.month.isin(excl)]
        out["selected"] = ols(q[col], q.energy_kWh)
        out["base_load_kWh_month"] = out["selected"]["intercept"]
    else:
        # no production data: base load = user value or the minimum month
        if "base_load_kWh_month" in bc:
            out["base_load_kWh_month"] = float(bc["base_load_kWh_month"])
        else:
            import warnings
            warnings.warn("no production series and no baseline.base_load_kWh_month: base load set to the lowest "
                          "billed month, which overstates it; supply a measured value", stacklevel=2)
            out["base_load_kWh_month"] = float(b.energy_kWh.min())
        out["base_load_source"] = "user" if "base_load_kWh_month" in bc else "minimum month (fallback)"
    return out


# ----------------------------------------------------------------------------- PV
def pv_monthly_yield(case: Case, P: dict) -> np.ndarray:
    """kWh/kWp per calendar month (index 0 = January) at PR = 1, isotropic sky (Klein 1977)."""
    lat = case.cfg["case"]["location"]["lat"]
    tilt = P["pv.tilt_deg"]; albedo = P["pv.albedo"]
    rec_days = [17, 47, 75, 105, 135, 162, 198, 228, 258, 288, 318, 344]
    days_in = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    hemi = 1 if lat >= 0 else -1
    phi = math.radians(abs(lat)); beta = math.radians(tilt)
    out = []
    for i, r in case.climate.sort_values("month").reset_index(drop=True).iterrows():
        n = rec_days[i]
        dec = hemi * math.radians(23.45 * math.sin(math.radians(360 * (284 + n) / 365)))
        ws = math.acos(max(-1, min(1, -math.tan(phi) * math.tan(dec))))
        wsp = min(ws, math.acos(max(-1, min(1, -math.tan(phi - beta) * math.tan(dec)))))
        num = math.cos(phi - beta) * math.cos(dec) * math.sin(wsp) + wsp * math.sin(phi - beta) * math.sin(dec)
        den = math.cos(phi) * math.cos(dec) * math.sin(ws) + ws * math.sin(phi) * math.sin(dec)
        Rb = num / den
        H, Hd = r.GHI, r.DHI
        Ht = H * ((1 - Hd / H) * Rb + Hd / H * (1 + math.cos(beta)) / 2 + albedo * (1 - math.cos(beta)) / 2)
        out.append(Ht * days_in[i])
    return np.array(out)


# ----------------------------------------------------------------------------- measures
def apply_measures(case: Case, P: dict, base_kWh: float, ids: list[str]):
    """Monthly kWh after measures. Base-load measures act first on all end uses; end-use measures then act
    on their target end uses (computed on the post-base-load consumption, no double counting)."""
    q = case.ref.energy_kWh.to_numpy(float).copy()
    det = {}
    sel = [m for m in case.measures if m.id in ids]
    for m in sel:
        if m.type == "base_load":
            frac = np.minimum(base_kWh / q, 1.0)
            s = P[f"measures.{m.id}.saving_frac"] * frac * q
            det[m.id] = s; q = q - s
    q_after_base = q.copy()
    for m in sel:
        if m.type == "enduse":
            share = sum(case.shares[e] for e in m.end_uses)
            det[m.id] = P[f"measures.{m.id}.saving_frac"] * P[f"measures.{m.id}.share_of_enduse"] * share * q_after_base
    for m in sel:
        if m.type == "enduse":
            q = q - det[m.id]
    return q, det


def measure_cost(case: Case, P: dict, m) -> tuple[float, float, float]:
    """(capex, annual O&M, life) of a measure."""
    pre = f"measures.{m.id}."
    if m.capex_mode == "units_from_energy":
        share = sum(case.shares[e] for e in m.end_uses)
        e_month = share * case.ref.energy_kWh.mean() * P[pre + "share_of_enduse"]
        units = e_month / (P[pre + "unit_kW"] * P[pre + "hours_per_month"])
        capex = units * P[pre + "capex_per_unit"]
    else:
        capex = P[pre + "capex"]
    return capex, P[pre + "om"], P[pre + "life"]


def cashflow(items, sav_other, sav_pv, P):
    """NPV of a set of investments. items = [(name, capex, annual O&M, life)]; name 'PV' gets an inverter
    replacement and degradation of its savings. Like-for-like reinvestment within the horizon and straight-line
    residual value of the last (re)investment at the horizon. Savings escalate with the real tariff escalation."""
    H = int(P["finance.horizon_yr"]); r = P["finance.discount_rate"]
    cf = np.zeros(H + 1); capex = 0.0
    for name, cap, om, life in items:
        life = float(life); L = int(life)
        capex += cap; cf[0] -= cap; cf[1:] -= om
        if L < H:
            for y in range(L, H, L):
                cf[y] -= cap
        last = (H // L) * L if L < H else 0
        if last == H:
            last = H - L
        rem = (last + life) - H
        if rem > 0:
            cf[H] += cap * rem / life
        if name == "PV":
            yr = int(P["pv.inverter_repl_year"])
            if 0 < yr < H:
                cf[yr] -= P["pv.inverter_repl_frac"] * cap
    y = np.arange(1, H + 1)
    esc = (1 + P["finance.tariff_real_escalation"]) ** (y - 1)
    cf[1:] += esc * (sav_other + sav_pv * (1 - P["pv.degradation"]) ** (y - 1))
    return float(np.sum(cf * (1 + r) ** -np.arange(H + 1))), capex, cf


def annuity(r, n):
    return r / (1 - (1 + r) ** -n) if r > 0 else 1 / n


# ----------------------------------------------------------------------------- evaluation
def annual_bill(case: Case, q, P, pf=None, q_for_demand=None, dmax=None, row=None):
    ref = case.ref
    pf = ref.power_factor.to_numpy() if pf is None else pf
    dmax = ref.max_demand_kW.to_numpy(float) if dmax is None else dmax
    return float(np.sum(case.tariff.bill(q, ref.days.to_numpy(), pf, row=row, q_for_demand=q_for_demand,
                                         demand_credit=P["pv.demand_credit"], dmax=dmax)))


def peak_after(case: Case, dmax0, q0, q_ee):
    """Measured peak after efficiency (energy_demand tariffs): it falls by peak_coincidence x the cut in average
    power, (q0 - q_ee) / (24 d). PV is assumed not to reduce it."""
    days = case.ref.days.to_numpy()
    return np.maximum(dmax0 - case.tariff.peak_coincidence * (q0 - q_ee) / (24 * days), 0.0)


def evaluate(case: Case, portfolio: dict, P: dict, ctx: dict) -> dict:
    """portfolio = {'measures': [...ids], 'pv_kWp': float}. ctx carries base load and PV yield."""
    ref = case.ref
    ids = portfolio.get("measures", [])
    q0 = ref.energy_kWh.to_numpy(float)
    days = ref.days.to_numpy()
    pf0 = ref.power_factor.to_numpy(float)
    dmax0 = ref.max_demand_kW.to_numpy(float)
    bill0 = annual_bill(case, q0, P, pf0)
    q_ee, det = apply_measures(case, P, ctx["base_kWh"], ids)
    pfm = [m for m in case.measures if m.id in ids and m.type == "pf_correction"]
    pf1 = np.full(12, P[f"measures.{pfm[0].id}.pf_after"]) if pfm else pf0
    dmax1 = peak_after(case, dmax0, q0, q_ee)
    kWp = portfolio.get("pv_kWp", 0.0)
    gen = ctx["pv_yield"][ref.mon.to_numpy() - 1] * P["pv.PR"] * kWp
    q_net = np.maximum(q_ee - gen, 0.0); surplus = np.maximum(gen - q_ee, 0.0)
    bill1 = annual_bill(case, q_net, P, pf1, q_for_demand=q_ee, dmax=dmax1)
    items = []
    for m in case.measures:
        if m.id in ids:
            items.append((m.id,) + measure_cost(case, P, m))
    if kWp > 0:
        cap = kWp * 1000 * P["pv.cost_per_W"]
        items.append(("PV", cap, P["pv.om_frac"] * cap, P["pv.life"]))
    sav = bill0 - bill1
    pv_part = annual_bill(case, q_ee, P, pf1, dmax=dmax1) - bill1 if kWp > 0 else 0.0
    npv, capex0, _ = cashflow(items, sav - pv_part, pv_part, P)
    H = int(P["finance.horizon_yr"]); r = P["finance.discount_rate"]
    om_total = sum(it[2] for it in items)
    payback = capex0 / (sav - om_total) if sav - om_total > 0 else float("nan")
    ef = P["grid.emission_factor"]
    g0, g1 = q0.sum(), q_net.sum()
    gas = lambda kwh: kwh / 1000 * P["grid.gas_share"] * P["grid.heat_rate"] * P["grid.import_share"]
    sec = case.cfg.get("security", {})
    shock = float(sec.get("energy_charge_shock", 0.5))
    row_s = case.tariff.row.copy(); row_s["energy"] *= (1 + shock)
    sh0 = annual_bill(case, q0, P, pf0, row=row_s) - bill0
    sh1 = annual_bill(case, q_net, P, pf1, q_for_demand=q_ee, dmax=dmax1, row=row_s) - bill1
    thr = sec.get("demand_threshold_kW")
    if case.tariff.type == "q_based_demand":
        peak0 = float(case.tariff.billed_demand(q0, days).max()); peak1 = float(case.tariff.billed_demand(q_ee, days).max())
    else:
        peak0, peak1 = float(dmax0.max()), float(dmax1.max())
    co2s = (g0 - g1) / 1000 * ef
    return dict(bill0=bill0, bill1=bill1, savings_y1=sav, capex=capex0, npv=npv, payback_yr=payback,
                grid0_MWh=g0 / 1000, grid1_MWh=g1 / 1000, grid_saved_frac=(g0 - g1) / g0,
                ee_saved_MWh=(q0.sum() - q_ee.sum()) / 1000, pv_gen_MWh=gen.sum() / 1000,
                pv_surplus_MWh=surplus.sum() / 1000, co2_0_t=g0 / 1000 * ef, co2_saved_t=co2s,
                imported_gas_avoided_GJ=gas(g0 - g1), shock_exposure0=sh0, shock_exposure1=sh1,
                peak0_kW=peak0, peak1_kW=peak1,
                months_over_threshold=int(np.sum((case.tariff.billed_demand(q_ee, days) if case.tariff.type == "q_based_demand"
                                                 else dmax1) >= thr)) if thr else None,
                roof_m2=kWp * P["pv.m2_per_kWp"], pv_kWp=kWp,
                net_abatement_cost=(-npv * annuity(r, H)) / co2s if co2s > 0 else float("nan"))


def context(case: Case, P: dict) -> dict:
    bl = baseline(case)
    return dict(base_kWh=bl["base_load_kWh_month"], pv_yield=pv_monthly_yield(case, P), baseline=bl)


def cce(case: Case, mid: str, P: dict, ctx: dict):
    _, det = apply_measures(case, P, ctx["base_kWh"], [mid])
    kwh = det[mid].sum()
    m = next(x for x in case.measures if x.id == mid)
    cap, om, life = measure_cost(case, P, m)
    return (cap * annuity(P["finance.discount_rate"], life) + om) / kwh, kwh


def pv_lcoe(case: Case, P: dict, ctx: dict, kWp=100.0):
    y = ctx["pv_yield"].sum() * P["pv.PR"] * kWp
    cap = kWp * 1000 * P["pv.cost_per_W"]
    r = P["finance.discount_rate"]; n = int(P["pv.life"])
    disc = (1 + r) ** -np.arange(1, n + 1)
    energy = np.sum(y * (1 - P["pv.degradation"]) ** np.arange(n) * disc)
    costs = cap + np.sum(P["pv.om_frac"] * cap * disc) + P["pv.inverter_repl_frac"] * cap * (1 + r) ** -int(P["pv.inverter_repl_year"])
    return costs / energy, y


def efficiency_ids(case: Case):
    return [m.id for m in case.measures]


def size_pv_to_match(case: Case, target_grid_MWh: float, ids, P, ctx, hi=1000.0):
    lo = 0.0
    for _ in range(60):
        mid = (lo + hi) / 2
        g = evaluate(case, {"measures": ids, "pv_kWp": mid}, P, ctx)["grid1_MWh"]
        lo, hi = (mid, hi) if g > target_grid_MWh else (lo, mid)
    return round(hi, 1)


def pathways(case: Case, P: dict, ctx: dict, targets=None):
    """Supply-only vs efficiency-first pathways to given reductions of grid purchases."""
    targets = np.arange(0.05, 0.751, 0.025) if targets is None else targets
    grid0 = case.ref.energy_kWh.sum() / 1000
    yr = ctx["pv_yield"].sum() * P["pv.PR"] / 1000
    pfc = [m.id for m in case.measures if m.type == "pf_correction"]
    energy_ids = [m.id for m in case.measures if m.type != "pf_correction"]
    order = sorted(energy_ids, key=lambda mid: cce(case, mid, P, ctx)[0])
    rows = []
    for tgt in targets:
        k_s = tgt * grid0 / yr
        rs = evaluate(case, {"measures": pfc, "pv_kWp": k_s}, P, ctx)
        chosen = []; re_ = evaluate(case, {"measures": pfc}, P, ctx)
        for mid in order:
            chosen.append(mid)
            re_ = evaluate(case, {"measures": chosen + pfc}, P, ctx)
            if re_["grid_saved_frac"] >= tgt:
                break
        gap = max(tgt - re_["grid_saved_frac"], 0.0)
        k_e = 0.0
        if gap > 0 and yr > 0:
            lo, hi = 0.0, 4 * k_s + 1
            for _ in range(50):
                mid = (lo + hi) / 2
                g = evaluate(case, {"measures": chosen + pfc, "pv_kWp": mid}, P, ctx)["grid_saved_frac"]
                lo, hi = (mid, hi) if g < tgt else (lo, mid)
            k_e = hi
        re_ = evaluate(case, {"measures": chosen + pfc, "pv_kWp": k_e}, P, ctx)
        rows.append(dict(target=tgt, supply_kWp=k_s, supply_capex=rs["capex"], supply_npv=rs["npv"],
                         supply_roof=k_s * P["pv.m2_per_kWp"], ee_kWp=k_e, ee_capex=re_["capex"], ee_npv=re_["npv"],
                         ee_roof=k_e * P["pv.m2_per_kWp"], ee_measures="+".join(chosen),
                         supply_peak=rs["peak1_kW"], ee_peak=re_["peak1_kW"]))
    return pd.DataFrame(rows), order
