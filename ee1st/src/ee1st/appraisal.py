"""Portfolios, Monte Carlo, one-way sensitivity, regulatory stress and thermal unit economics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .case import Case
from .core import cce, context, evaluate, pv_lcoe, size_pv_to_match


def standard_portfolios(case: Case, P: dict, ctx: dict) -> dict:
    """P0 baseline, P1 efficiency bundle, P2 PV only, P3 bundle + same PV, P4 bundle + PV re-sized to P2's grid use."""
    ids = [m.id for m in case.measures]
    kwp = float(case.cfg.get("pv", {}).get("reference_kWp", 100.0))
    ports = {"P0": {}, "P1": {"measures": ids}, "P2": {"pv_kWp": kwp}, "P3": {"measures": ids, "pv_kWp": kwp}}
    if kwp > 0:
        tgt = evaluate(case, ports["P2"], P, ctx)["grid1_MWh"]
        ports["P4"] = {"measures": ids, "pv_kWp": size_pv_to_match(case, tgt, ids, P, ctx, hi=kwp)}
    return ports


def portfolio_table(case: Case, P: dict, ctx: dict, ports: dict) -> pd.DataFrame:
    rows = []
    for k, pf in ports.items():
        r = evaluate(case, pf, P, ctx); r["portfolio"] = k; rows.append(r)
    return pd.DataFrame(rows).set_index("portfolio")


def measure_table(case: Case, P: dict, ctx: dict) -> pd.DataFrame:
    rows = []
    for m in case.measures:
        r = evaluate(case, {"measures": [m.id]}, P, ctx)
        c, kwh = (cce(case, m.id, P, ctx) if m.type != "pf_correction" else (float("nan"), 0.0))
        rows.append(dict(id=m.id, name=m.name, type=m.type, capex=r["capex"], saved_MWh=kwh / 1000, cce=c,
                         npv=r["npv"], savings_y1=r["savings_y1"], co2_t=r["co2_saved_t"], payback=r["payback_yr"]))
    lc, _ = pv_lcoe(case, P, ctx)
    kwp = float(case.cfg.get("pv", {}).get("reference_kWp", 100.0))
    r = evaluate(case, {"pv_kWp": kwp}, P, ctx)
    rows.append(dict(id="PV", name=f"Rooftop PV {kwp:g} kWp", type="supply", capex=r["capex"],
                     saved_MWh=r["grid0_MWh"] - r["grid1_MWh"], cce=lc, npv=r["npv"], savings_y1=r["savings_y1"],
                     co2_t=r["co2_saved_t"], payback=r["payback_yr"]))
    M = pd.DataFrame(rows).set_index("id")
    M["below_marginal_tariff"] = M.cce < case.tariff.marginal_value()
    return M


def regulatory_stress(case: Case, P: dict, ctx: dict, ports: dict) -> dict:
    if case.tariff.type != "q_based_demand":
        return {}   # PV never reduces billed demand under the other tariff types
    Q = dict(P); Q["pv.demand_credit"] = 0.0
    return {k: evaluate(case, ports[k], Q, ctx)["npv"] for k in ports if ports[k].get("pv_kWp")}


def monte_carlo(case: Case, ports: dict, n=None, seed=None) -> tuple[pd.DataFrame, dict]:
    mc = case.cfg.get("montecarlo", {})
    n = int(n or mc.get("n", 1000)); seed = int(seed if seed is not None else mc.get("seed", 1))
    rng = np.random.default_rng(seed)
    P0 = case.P.central()
    ctx0 = context(case, P0)
    geo = {"pv.tilt_deg", "pv.albedo"}
    unc = [k for k, p in case.P.params.items() if p.uncertain]
    energy = [m.id for m in case.measures if m.type != "pf_correction"]
    rows = []
    for _ in range(n):
        P = case.P.sample(rng)
        ctx = context(case, P) if any(P[g] != P0[g] for g in geo) else ctx0
        r = {}
        for lab, pf in ports.items():
            if lab == "P0":
                continue
            e = evaluate(case, pf, P, ctx)
            r[f"npv_{lab}"] = e["npv"]; r[f"co2_{lab}"] = e["co2_saved_t"]; r[f"capex_{lab}"] = e["capex"]
        for mid in energy:
            r[f"cce_{mid}"] = cce(case, mid, P, ctx)[0]
        r["lcoe_PV"] = pv_lcoe(case, P, ctx)[0]
        r.update({f"par:{k}": P[k] for k in unc})
        rows.append(r)
    MC = pd.DataFrame(rows)
    s = {"n": n, "seed": seed}
    for c in [c for c in MC.columns if not c.startswith("par:")]:
        s[c] = dict(p5=float(MC[c].quantile(.05)), p50=float(MC[c].median()), p95=float(MC[c].quantile(.95)))
    s["prob_npv_positive"] = {lab: float((MC[f"npv_{lab}"] > 0).mean()) for lab in ports if lab != "P0"}
    if "P4" in ports:
        s["prob_P4_beats_P2"] = float((MC.npv_P4 > MC.npv_P2).mean())
        diff = (MC.npv_P4 - MC.npv_P2).rank()
        par = MC[[c for c in MC.columns if c.startswith("par:")]]
        sp = {c[4:]: float(par[c].rank().corr(diff)) for c in par.columns}
        s["spearman_P4_minus_P2"] = sp
        s["drivers_P4_minus_P2"] = dict(sorted(sp.items(), key=lambda x: -abs(np.nan_to_num(x[1])))[:8])
    cc = MC[[f"cce_{m}" for m in energy] + ["lcoe_PV"]]
    s["prob_cheapest"] = {c: float((cc.idxmin(axis=1) == c).mean()) for c in cc.columns}
    s["prob_all_cce_below_marginal"] = float((MC[[f"cce_{m}" for m in energy]].max(axis=1)
                                              < case.tariff.marginal_value()).mean())
    return MC, s


def oneway(case: Case, ports: dict, keys=("P1", "P2", "P4")) -> pd.DataFrame:
    P0 = case.P.central(); ctx0 = context(case, P0); rows = []
    for k, p in case.P.params.items():
        if not p.uncertain:
            continue
        for lab, val in (("low", p.low), ("high", p.high)):
            P = dict(P0); P[k] = val
            ctx = context(case, P) if k in ("pv.tilt_deg", "pv.albedo") else ctx0
            row = dict(param=k, case=lab, value=val)
            for q in keys:
                if q in ports:
                    row[f"npv_{q}"] = evaluate(case, ports[q], P, ctx)["npv"]
            rows.append(row)
    return pd.DataFrame(rows)


def thermal(case: Case, P: dict) -> pd.DataFrame | None:
    """Cost and CO2 per GJ of useful heat for fuel, resistance and heat-pump options."""
    th = case.cfg.get("thermal")
    if not th:
        return None
    mv = case.tariff.marginal_value()
    el = mv / 0.0036; ef_el = P["grid.emission_factor"] * 1000 / 3.6
    rows = []
    for f in th.get("fuels", []):
        price = f["price_per_GJ"] if "price_per_GJ" in f else f["price_per_unit"] / f["GJ_per_unit"]
        eff = f.get("efficiency", 0.85)
        rows.append(dict(option=f["name"], cost_per_GJ_heat=price / eff, kgCO2_per_GJ_heat=f["kgCO2_per_GJ"] / eff))
    rows.append(dict(option="Electric resistance", cost_per_GJ_heat=el, kgCO2_per_GJ_heat=ef_el))
    for cop in th.get("heat_pump_cop", [2.5, 3.0, 4.0]):
        rows.append(dict(option=f"Heat pump COP {cop:g}", cost_per_GJ_heat=el / cop, kgCO2_per_GJ_heat=ef_el / cop))
    T = pd.DataFrame(rows).set_index("option")
    T["breakeven_COP_cost"] = np.nan; T["breakeven_COP_co2"] = np.nan
    for f in th.get("fuels", []):
        c = T.loc[f["name"]]
        T.loc[f["name"], "breakeven_COP_cost"] = el / c.cost_per_GJ_heat   # heat-pump COP that matches this fuel
        T.loc[f["name"], "breakeven_COP_co2"] = ef_el / c.kgCO2_per_GJ_heat
    return T


def parameter_table(case: Case, mc_summary: dict | None = None) -> pd.DataFrame:
    """All inputs with range, data status, source and (if available) Spearman correlation with NPV(P4) - NPV(P2)."""
    T = pd.DataFrame(case.P.table()).set_index("name")
    if mc_summary and "spearman_P4_minus_P2" in mc_summary:
        T["spearman_P4_minus_P2"] = pd.Series(mc_summary["spearman_P4_minus_P2"])
        T = T.sort_values("spearman_P4_minus_P2", key=lambda x: -x.abs().fillna(0))
    return T
