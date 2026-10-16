"""Linear-programming benchmark with urbs (TUM, open-source energy-system optimisation model).

Minimises the annualised cost of meeting the plant's hourly electricity demand over one year (8,760 h) by choosing
the capacities of four efficiency measures (negawatt processes), rooftop PV (<= 700 kWp), Li-ion storage and the
hourly grid purchases, under three compensation regimes and a sweep of caps on gross grid CO2.
Run in the urbs environment:  URBS_DIR=/path/to/urbs  <urbs-venv>/bin/python scripts/run_urbs.py
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.environ.get("URBS_DIR", str(ROOT.parent / "urbs_src" / "urbs")))
import urbs  # noqa: E402
import pyomo.environ as pyo  # noqa: E402
from pyomo.opt.base import SolverFactory  # noqa: E402

# urbs flags 'availability' mode whenever the column exists, even if it is empty, and then skips creating
# some empty sets; treat an all-NaN availability column as absent (no change to the model equations).
import urbs.input as _ui  # noqa: E402
_identify = _ui.identify_mode


def _identify_mode(data):
    mode = _identify(data)
    if data["process"]["availability"].isna().all():
        mode["avail"] = False
    return mode


_ui.identify_mode = _identify_mode

YEAR = 2026
INPUT = ROOT / "urbs" / "plant_urbs.xlsx"
meta = json.load(open(ROOT / "urbs" / "plant_urbs_meta.json"))
EE = {m: v["process"] for m, v in meta["measures"].items()}
SITE = "Plant"
TIMESTEPS = range(0, 8761)


def build(regime, co2_cap=np.inf, allow_ee=True, pv_max_kWp=None, bat_cost_factor=1.0):
    data = urbs.read_input(str(INPUT), YEAR)
    mv = meta["marginal_value"]
    sell = {"net_metering": mv, "net_billing": meta["net_billing_export"], "self_consumption": 0.0}[regime]
    bsp = data["buy_sell_price"]
    bsp.loc[bsp.index.get_level_values("t") > 0, "Elec sell"] = sell
    data["global_prop"].loc[(YEAR, "CO2 limit"), "value"] = co2_cap
    if pv_max_kWp is not None:
        data["process"].loc[(YEAR, SITE, "Photovoltaics"), "cap-up"] = pv_max_kWp * meta["pv_unit_per_kWp"]
    if not allow_ee:
        for p in EE.values():
            data["process"].loc[(YEAR, SITE, p), "cap-up"] = 0.0
    if bat_cost_factor != 1.0:
        data["storage"]["inv-cost-c"] *= bat_cost_factor
    urbs.validate_input(data)
    m = urbs.create_model(data, 1, TIMESTEPS, "cost")
    tm = list(m.tm)
    if regime == "net_metering":
        # annual net metering: kWh credited at the tariff, but annual exports cannot exceed annual imports
        m.nm_limit = pyo.Constraint(expr=sum(m.e_pro_out[t, YEAR, SITE, "Feed-in", "Elec sell"] for t in tm)
                                    <= sum(m.e_pro_out[t, YEAR, SITE, "Purchase", "Elec"] for t in tm))
    return m


def _annual_cost_process(m, pro):
    v = lambda x: float(pyo.value(x))
    k = (YEAR, SITE, pro)
    return (v(m.cap_pro_new[k]) * m.process_dict["inv-cost"][k] * m.process_dict["invcost-factor"][k]
            + v(m.cap_pro[k]) * m.process_dict["fix-cost"][k] * m.process_dict["cost_factor"][k])


def _annual_cost_storage(m):
    v = lambda x: float(pyo.value(x))
    s = (YEAR, SITE, "Li-ion battery", "Elec")
    if not hasattr(m, "cap_sto_c"):
        return 0.0
    d = m.storage_dict
    return ((v(m.cap_sto_p_new[s]) * d["inv-cost-p"][s] + v(m.cap_sto_c_new[s]) * d["inv-cost-c"][s]) * d["invcost-factor"][s]
            + (v(m.cap_sto_p[s]) * d["fix-cost-p"][s] + v(m.cap_sto_c[s]) * d["fix-cost-c"][s]) * d["cost_factor"][s])


def results(m):
    tm = list(m.tm)
    v = lambda x: float(pyo.value(x))
    cap = {p: v(m.cap_pro[YEAR, SITE, p]) for p in ["Photovoltaics"] + list(EE.values())}
    sto = ("Li-ion battery", "Elec")
    bat_c = v(m.cap_sto_c[YEAR, SITE, sto[0], sto[1]]) if hasattr(m, "cap_sto_c") else 0.0
    bat_p = v(m.cap_sto_p[YEAR, SITE, sto[0], sto[1]]) if hasattr(m, "cap_sto_p") else 0.0
    imp = sum(v(m.e_pro_out[t, YEAR, SITE, "Purchase", "Elec"]) for t in tm)
    exp = sum(v(m.e_pro_in[t, YEAR, SITE, "Feed-in", "Elec"]) for t in tm)
    pv = sum(v(m.e_pro_out[t, YEAR, SITE, "Photovoltaics", "Elec"]) for t in tm)
    curt = sum(v(m.e_pro_in[t, YEAR, SITE, "Curtailment", "Elec"]) for t in tm)
    ee = {k: sum(v(m.e_pro_out[t, YEAR, SITE, p, "Elec"]) for t in tm) for k, p in EE.items()}
    costs = {c: v(m.costs[c]) for c in m.cost_type}
    load = meta["load_MWh"] * 1000
    out = dict(pv_kWp=cap["Photovoltaics"] / meta["pv_unit_per_kWp"], bat_kWh_usable=bat_c, bat_kW=bat_p, import_MWh=imp / 1000,
               export_MWh=exp / 1000, pv_MWh=pv / 1000, curtailed_MWh=curt / 1000, ee_MWh=sum(ee.values()) / 1000,
               co2_t=imp / 1000 * meta["ef"], total_cost=sum(costs.values()),
               self_sufficiency=1 - imp / (load - sum(ee.values())), grid_cut=1 - imp / load)
    for k, p in EE.items():
        out[f"adopt_{k}"] = cap[p] / meta["measures"][k]["peak_kW"]
    out.update({f"cost_{c}": x for c, x in costs.items()})
    # annualised cost by technology (investment annuity + fixed O&M) and net grid cost
    out["acost_pv"] = _annual_cost_process(m, "Photovoltaics")
    out["acost_ee"] = sum(_annual_cost_process(m, p) for p in EE.values())
    out["acost_bat"] = _annual_cost_storage(m)
    out["acost_grid"] = costs["Purchase"] + costs["Revenue"]
    return out


def dispatch(m):
    """Hourly balance of the solved model (kW): demand, efficiency, PV, grid, battery, export."""
    tm = list(m.tm)
    v = lambda x: float(pyo.value(x))
    s = (YEAR, SITE, "Li-ion battery", "Elec")
    has = hasattr(m, "e_sto_in")
    return pd.DataFrame({
        "t": tm,
        "demand": [float(m.demand_dict[(SITE, "Elec")][(YEAR, t)]) for t in tm],
        "efficiency": [sum(v(m.e_pro_out[t, YEAR, SITE, p, "Elec"]) for p in EE.values()) for t in tm],
        "pv": [v(m.e_pro_out[t, YEAR, SITE, "Photovoltaics", "Elec"]) for t in tm],
        "grid": [v(m.e_pro_out[t, YEAR, SITE, "Purchase", "Elec"]) for t in tm],
        "export": [v(m.e_pro_in[t, YEAR, SITE, "Feed-in", "Elec"]) for t in tm],
        "curtailed": [v(m.e_pro_in[t, YEAR, SITE, "Curtailment", "Elec"]) for t in tm],
        "bat_in": [v(m.e_sto_in[(t,) + s]) if has else 0.0 for t in tm],
        "bat_out": [v(m.e_sto_out[(t,) + s]) if has else 0.0 for t in tm],
        "soc": [v(m.e_sto_con[(t,) + s]) if has else 0.0 for t in tm],
    })


def solve(m):
    opt = SolverFactory("appsi_highs")
    t0 = time.time()
    res = opt.solve(m, load_solutions=True)
    assert str(res.solver.termination_condition) == "optimal", res.solver.termination_condition
    return time.time() - t0


CO2_FRACS = (0.35, 0.30, 0.25, 0.20, 0.15, 0.10)
CASES = []
for regime in ("net_metering", "net_billing", "self_consumption"):
    for allow in (True, False):
        CASES.append(("cost-optimal", regime, allow, {}))
for allow in (True, False):
    CASES.append(("roof-limited", "net_metering", allow, dict(pv_max_kWp=163.8)))
for frac in CO2_FRACS:
    for allow in (True, False):
        CASES.append(("co2-cap", "net_metering", allow, dict(co2_cap=frac)))
# battery-cost sensitivity: unconstrained and at a 20% emission cap
for f in (0.75, 0.50, 0.25):
    for cap in (None, 0.20):
        for allow in (True, False):
            kw = dict(bat_cost_factor=f)
            if cap is not None:
                kw["co2_cap"] = cap
            CASES.append(("battery-cost", "net_metering", allow, kw))
DISPATCH = {("co2-cap", True, 0.20), ("co2-cap", False, 0.20)}


def run(case_spec):
    case, regime, allow, kw = case_spec
    kw = dict(kw)
    frac = kw.pop("co2_cap", None)
    if frac is not None:
        kw["co2_cap"] = frac * meta["co2_baseline_t"]
    m = build(regime, allow_ee=allow, **kw)
    disp = None
    try:
        s = solve(m); r = results(m)
        if (case, allow, frac) in DISPATCH:
            disp = dispatch(m); disp["efficiency_allowed"] = allow
    except AssertionError as e:
        r = dict(infeasible=str(e)); s = np.nan
    r.update(case=case, regime=regime, efficiency=allow, co2_cap_frac=frac if frac is not None else np.nan,
             pv_max_kWp=kw.get("pv_max_kWp", 700.0), bat_cost_factor=kw.get("bat_cost_factor", 1.0), solve_s=s)
    print(case, regime, allow, frac, kw.get("bat_cost_factor", 1.0), round(r.get("total_cost", np.nan)), flush=True)
    return r, disp


if __name__ == "__main__":
    from multiprocessing import Pool
    workers = int(os.environ.get("URBS_WORKERS", "2"))
    with Pool(workers) as pool:
        out = pool.map(run, CASES, chunksize=1)
    R = pd.DataFrame([r for r, _ in out])
    R["base_cost"] = meta["load_MWh"] * 1000 * meta["marginal_value"]
    (ROOT / "results").mkdir(exist_ok=True)
    R.to_csv(ROOT / "results" / "urbs_results.csv", index=False)
    D = [d for _, d in out if d is not None]
    if D:
        # hourly dispatch is derived from the confidential load profile: kept out of the public repository
        pd.concat(D).to_csv(ROOT / "urbs" / "urbs_dispatch.csv.gz", index=False)
    print(R[["case", "regime", "efficiency", "co2_cap_frac", "bat_cost_factor", "pv_kWp", "bat_kWh_usable", "ee_MWh",
             "import_MWh", "total_cost", "solve_s"]].round(2).to_string())
