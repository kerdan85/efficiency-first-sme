"""Alternative baseline specifications (reviewer request): is the efficiency-first advantage an artefact of the
selected regression intercept?

Each specification gives a production-independent base load B (kWh/month). Only base-load control (E4) depends
on B (its saving is a fraction of B). For each B the efficiency-first portfolio (P4) is re-sized to match the grid
purchases of PV only (P2) and compared with it, at the central E4 saving (10%) and at its lowest (5%).
Only aggregate results are written (results/baseline_alt.csv); the bills stay confidential.
"""
import calendar
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from efirst.model import evaluate, load_all  # noqa: E402
from efirst.params import PARAMS, central  # noqa: E402

P0 = central(); D0 = load_all(P0)
EE = ["E4", "E1", "E2", "E3", "E5"]
SHIFT = {"2025-11", "2025-12", "2026-01"}
EASTER = {2024: dt.date(2024, 3, 31), 2025: dt.date(2025, 4, 20), 2026: dt.date(2026, 4, 5)}


def nth(y, m, wd, n):
    d = [x for x in range(1, calendar.monthrange(y, m)[1] + 1) if dt.date(y, m, x).weekday() == wd]
    return dt.date(y, m, d[n - 1])


def holidays(y):
    return {dt.date(y, 1, 1), nth(y, 2, 0, 1), nth(y, 3, 0, 3), dt.date(y, 5, 1), dt.date(y, 9, 16),
            nth(y, 11, 0, 3), dt.date(y, 12, 25), EASTER[y] - dt.timedelta(3), EASTER[y] - dt.timedelta(2)}


b = pd.read_csv(ROOT / "data/raw/billing_monthly.csv")
clim = pd.read_csv(ROOT / "data/raw/nasa_power_climatology_pachuca.csv").set_index("month")
rows = []
for _, r in b.iterrows():
    y, m = map(int, r.month.split("-")); nd = calendar.monthrange(y, m)[1]; H = holidays(y)
    days = [dt.date(y, m, d) for d in range(1, nd + 1)]
    wk = sum(1 for d in days if d.weekday() < 5 and d not in H); sa = sum(1 for d in days if d.weekday() == 5 and d not in H)
    shift = r.month in SHIFT
    hop = (wk + sa) * 24 if shift else wk * 10 + sa * 5
    rows.append(dict(month=r.month, E=r.energy_kWh, P=r.production_pairs, shift=float(shift), T=clim.loc[m, "T2M_C"],
                     wd=wk + 0.5 * sa, hop=hop, hoff=24 * nd - hop, nd=nd))
B = pd.DataFrame(rows).dropna(subset=["P"])
X_ = B[~B["shift"].astype(bool)]


def fit(df, cols, const=True, huber=False):
    X = df[cols].to_numpy(float)
    if const:
        X = np.column_stack([np.ones(len(df)), X])
    y = df.E.to_numpy(float); w = np.ones(len(y))
    for _ in range(50 if huber else 1):
        W = np.sqrt(w)
        beta, *_ = np.linalg.lstsq(X * W[:, None], y * W, rcond=None)
        res = y - X @ beta
        if huber:
            s = np.median(np.abs(res - np.median(res))) / 0.6745; k = 1.345 * s
            w = np.where(np.abs(res) <= k, 1.0, k / np.abs(res))
    n, p = X.shape
    ss = ((y - y.mean()) ** 2).sum(); r2 = 1 - (res ** 2).sum() / ss
    cv = np.sqrt((res ** 2).sum() / (n - p)) / y.mean()
    return beta, r2, cv, n


specs = []
# central: production only, shift months excluded
beta, r2, cv, n = fit(X_, ["P"]); specs.append(("Production, shift months excluded (central)", beta[0], r2, cv, n))
beta, r2, cv, n = fit(B, ["P"]); specs.append(("Production, all months", beta[0], r2, cv, n))
beta, r2, cv, n = fit(B, ["P", "shift"]); specs.append(("Production and shift dummy, all months", beta[0], r2, cv, n))
beta, r2, cv, n = fit(X_, ["P", "T"]); specs.append(("Production and mean temperature", beta[0] + beta[2] * X_["T"].mean(), r2, cv, n))
beta, r2, cv, n = fit(X_, ["P", "wd"]); specs.append(("Production and working days", beta[0] + beta[2] * X_["wd"].mean(), r2, cv, n))
beta, r2, cv, n = fit(B, ["hoff", "hop", "P"], const=False)
specs.append(("Calendar hours and production, all months", float((beta[0] * X_["hoff"] + beta[1] * X_["hop"]).mean()), r2, cv, n))
beta, r2, cv, n = fit(X_, ["P"], huber=True); specs.append(("Production, robust (Huber) fit", beta[0], r2, cv, n))
c = D0["baseline"]["excl_24h_shift"]
specs.append(("Lower 95% bound of the central intercept", c["intercept"] - 2.08 * c["se_intercept"], np.nan, np.nan, c["n"]))


def resize(meas, P, D, it=30):
    target = evaluate({"pv_kWp": 163.8}, P, D)["grid1_MWh"]
    lo, hi = 0.0, 163.8
    for _ in range(it):
        mid = (lo + hi) / 2
        g = evaluate({"measures": meas, "pv_kWp": mid}, P, D)["grid1_MWh"]
        lo, hi = (mid, hi) if g > target else (lo, mid)
    return hi


out = []
mean_E = D0["ref"].energy_kWh.mean()
for name, Bk, r2, cv, n in specs:
    D = dict(D0); D["intercept"] = float(Bk)
    row = dict(spec=name, n=n, r2=r2, cv_rmse=cv, base_kWh_month=float(Bk), base_share=float(Bk / mean_E))
    for lab, mod in [("central", {}), ("lowE4", {"base_saving_frac": PARAMS["base_saving_frac"][1], "base_capex": PARAMS["base_capex"][2]})]:
        P = dict(P0); P.update(mod)
        k = resize(EE, P, D)
        r = evaluate({"measures": EE, "pv_kWp": k}, P, D); r2_ = evaluate({"pv_kWp": 163.8}, P, D)
        row[f"kWp_{lab}"] = k; row[f"npv_gain_{lab}"] = r["npv"] - r2_["npv"]; row[f"capex_save_{lab}"] = 1 - r["capex"] / r2_["capex"]
    row["E4_MWh"] = 0.10 * Bk * 12 / 1000
    out.append(row); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}, flush=True)
pd.DataFrame(out).to_csv(ROOT / "results/baseline_alt.csv", index=False)
