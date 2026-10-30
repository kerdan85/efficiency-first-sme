"""Stress test of the efficiency-first result against base-load control (E4), the least evidenced measure.

P4 is re-sized (bisection) to match P2's grid purchases in every case. Deterministic cases plus a Monte Carlo
in which E4 is excluded and P4 is re-sized in every draw (same seed and distributions as run_montecarlo.py).
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from efirst.model import evaluate, load_all  # noqa: E402
from efirst.params import PARAMS, central  # noqa: E402

P0 = central(); D = load_all(P0)
EE = ["E4", "E1", "E2", "E3", "E5"]
NOE4 = ["E1", "E2", "E3", "E5"]


def resize(meas, P, it=30):
    target = evaluate({"pv_kWp": 163.8}, P, D)["grid1_MWh"]
    lo, hi = 0.0, 163.8
    for _ in range(it):
        mid = (lo + hi) / 2
        g = evaluate({"measures": meas, "pv_kWp": mid}, P, D)["grid1_MWh"]
        lo, hi = (mid, hi) if g > target else (lo, mid)
    return hi


def case(meas, mod):
    P = dict(P0); P.update(mod)
    k = resize(meas, P)
    r = evaluate({"measures": meas, "pv_kWp": k}, P, D); r2 = evaluate({"pv_kWp": 163.8}, P, D)
    return dict(kWp=k, capex=r["capex"], npv=r["npv"], capex_P2=r2["capex"], npv_P2=r2["npv"],
                capex_save=1 - r["capex"] / r2["capex"], npv_gain=r["npv"] - r2["npv"])


lowE = {k: PARAMS[k][1] for k in ["ca_saving_frac", "sew_saving_frac", "heat_saving_frac"]}
out = {"deterministic": {
    "central": case(EE, {}),
    "no_E4": case(NOE4, {}),
    "E4_low_saving": case(EE, {"base_saving_frac": PARAMS["base_saving_frac"][1]}),
    "E4_low_saving_high_cost": case(EE, {"base_saving_frac": PARAMS["base_saving_frac"][1], "base_capex": PARAMS["base_capex"][2]}),
    "no_E4_low_E1_E3": case(NOE4, lowE),
}}
# break-even E4 saving fraction at which the NPV advantage of P4 over P2 would vanish (none if positive at 0)
out["no_E4_positive"] = out["deterministic"]["no_E4"]["npv_gain"] > 0

# Monte Carlo without E4 (same seed and distributions as run_montecarlo.py)
N, SEED = 5000, 20261014
rng = np.random.default_rng(SEED)
EXCLUDE = {"pv_demand_credit"}
gain, csave = [], []
for i in range(N):
    P = dict(P0)
    for k, (c, lo, hi, st, src) in PARAMS.items():
        if lo < hi and k not in EXCLUDE:
            P[k] = float(rng.triangular(lo, c, hi))
    k = resize(NOE4, P, it=22)
    r = evaluate({"measures": NOE4, "pv_kWp": k}, P, D); r2 = evaluate({"pv_kWp": 163.8}, P, D)
    gain.append(r["npv"] - r2["npv"]); csave.append(r2["capex"] - r["capex"])
gain, csave = np.array(gain), np.array(csave)
out["mc_no_E4"] = dict(N=N, prob_npv_gt_P2=float((gain > 0).mean()), prob_capex_lt_P2=float((csave > 0).mean()),
                       npv_gain_p5=float(np.quantile(gain, 0.05)), npv_gain_p50=float(np.median(gain)),
                       npv_gain_p95=float(np.quantile(gain, 0.95)))

# Monte Carlo with E4 kept but fixed at its lowest saving and highest cost
rng = np.random.default_rng(SEED)
gain, csave = [], []
for i in range(N):
    P = dict(P0)
    for k, (c, lo, hi, st, src) in PARAMS.items():
        if lo < hi and k not in EXCLUDE:
            P[k] = float(rng.triangular(lo, c, hi))
    P["base_saving_frac"] = PARAMS["base_saving_frac"][1]; P["base_capex"] = PARAMS["base_capex"][2]
    k = resize(EE, P, it=22)
    r = evaluate({"measures": EE, "pv_kWp": k}, P, D); r2 = evaluate({"pv_kWp": 163.8}, P, D)
    gain.append(r["npv"] - r2["npv"]); csave.append(r2["capex"] - r["capex"])
gain, csave = np.array(gain), np.array(csave)
out["mc_E4_low"] = dict(N=N, prob_npv_gt_P2=float((gain > 0).mean()), prob_capex_lt_P2=float((csave > 0).mean()),
                        npv_gain_p50=float(np.median(gain)))
# E4 saving expressed as kW of the always-on load (central allocation: outside operating hours)
out["E4_kWh_per_frac"] = float(D["intercept"] * 12)
json.dump(out, open(ROOT / "results/e4_stress.json", "w"), indent=1)
print(json.dumps(out, indent=1))
