"""Monte Carlo propagation of parameter uncertainty (triangular distributions)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from efirst.model import cce, evaluate, load_all, pv_lcoe  # noqa: E402
from efirst.params import PARAMS, central  # noqa: E402

N = 5000
SEED = 20261014
rng = np.random.default_rng(SEED)
P0 = central(); D = load_all(P0)
res = json.load(open(ROOT / "results/results.json"))
kwp4 = res["p4_kWp"]
EE = ["E4", "E1", "E2", "E3", "E5"]
EXCLUDE = {"pv_demand_credit"}  # regulatory scenario, analysed separately

rows = []
for i in range(N):
    P = dict(P0)
    for k, (c, lo, hi, st, src) in PARAMS.items():
        if lo < hi and k not in EXCLUDE:
            P[k] = float(rng.triangular(lo, c, hi))
    r = {}
    for lab, pf in (("P1", {"measures": EE}), ("P2", {"pv_kWp": 163.8}),
                    ("P3", {"measures": EE, "pv_kWp": 163.8}), ("P4", {"measures": EE, "pv_kWp": kwp4})):
        e = evaluate(pf, P, D)
        r[f"npv_{lab}"] = e["npv"]; r[f"co2_{lab}"] = e["co2_saved_t"]; r[f"grid_{lab}"] = e["grid_saved_frac"]
        r[f"capex_{lab}"] = e["capex"]
    for m in ["E1", "E2", "E3", "E4"]:
        r[f"cce_{m}"] = cce(m, P, D)[0]
    r["lcoe_PV"] = pv_lcoe(P, D)[0]
    r.update({f"par_{k}": P[k] for k in PARAMS if PARAMS[k][1] < PARAMS[k][2] and k not in EXCLUDE})
    rows.append(r)

MC = pd.DataFrame(rows)
MC.to_csv(ROOT / "results/montecarlo.csv.gz", index=False, compression="gzip")
summ = {}
for col in [c for c in MC.columns if not c.startswith("par_")]:
    s = MC[col]
    summ[col] = dict(mean=float(s.mean()), p5=float(s.quantile(0.05)), p50=float(s.median()),
                     p95=float(s.quantile(0.95)))
summ["prob_npv_pos"] = {lab: float((MC[f"npv_{lab}"] > 0).mean()) for lab in ["P1", "P2", "P3", "P4"]}
summ["prob_P4_gt_P2"] = float((MC.npv_P4 > MC.npv_P2).mean())
summ["prob_P1_npv_per_capex_gt_P2"] = float(((MC.npv_P1 / MC.capex_P1) > (MC.npv_P2 / MC.capex_P2)).mean())
cc = MC[[f"cce_{m}" for m in ["E1", "E2", "E3", "E4"]] + ["lcoe_PV"]]
summ["prob_cheapest"] = {c: float((cc.idxmin(axis=1) == c).mean()) for c in cc.columns}
summ["prob_E4_cheapest_overall"] = summ["prob_cheapest"]["cce_E4"]
summ["prob_all_cce_below_marginal"] = float((cc.max(axis=1) < res["tariff"]["marginal_MXN_per_kWh"]).mean())
# Spearman rank correlation of inputs with NPV of P4 vs P2 difference
diff = MC.npv_P4 - MC.npv_P2
par = MC[[c for c in MC.columns if c.startswith("par_")]]
summ["spearman_diff_P4_P2"] = {c[4:]: float(par[c].rank().corr(diff.rank())) for c in par.columns}
summ["spearman_npv_P1"] = {c[4:]: float(par[c].rank().corr(MC.npv_P1.rank())) for c in par.columns}
summ["N"] = N; summ["seed"] = SEED
json.dump(summ, open(ROOT / "results/montecarlo_summary.json", "w"), indent=1)
print(json.dumps({k: summ[k] for k in ["prob_npv_pos", "prob_P4_gt_P2", "prob_cheapest",
                                       "prob_all_cce_below_marginal", "prob_P1_npv_per_capex_gt_P2"]}, indent=1))
for k in ["npv_P1", "npv_P2", "npv_P4", "cce_E1", "cce_E2", "cce_E3", "cce_E4", "lcoe_PV"]:
    print(k, {a: round(b, 3) for a, b in summ[k].items()})
top = sorted(summ["spearman_diff_P4_P2"].items(), key=lambda x: -abs(x[1]))[:6]
print("drivers P4-P2:", top)
