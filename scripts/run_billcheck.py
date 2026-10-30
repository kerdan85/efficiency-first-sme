"""Evidence from the bills on the always-on load and the shape of the hourly load (reviewer request).

1. Calendar regression: monthly energy = a * off-hours + b * operating hours (+ c * production), no intercept.
   a is the mean load outside operating hours (always-on load), b the mean load during operating hours.
   Operating hours from the calendar (Mon-Fri 08-18, Sat 08-13, Mexican statutory holidays and Holy Thursday/
   Friday excluded; Mon-Sat 24 h in the three shift months). The shift months provide most of the
   identification, so the estimate is repeated for shorter assumed shifts.
2. Upper bound on the always-on load: mean load over all hours of the lowest-consumption month.
3. Measured monthly peaks implied by the load factor printed on each bill, against the modelled peaks.
Only aggregate results are written (results/bill_loadcheck.json); the bills stay confidential.
"""
import calendar
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from efirst.hourly import hourly_pv_per_kWp, load_profile, nz_central  # noqa: E402
from efirst.model import load_all  # noqa: E402
from efirst.params import central  # noqa: E402

b = pd.read_csv(ROOT / "data/raw/billing_monthly.csv")
SHIFT = {"2025-11", "2025-12", "2026-01"}
EASTER = {2024: dt.date(2024, 3, 31), 2025: dt.date(2025, 4, 20), 2026: dt.date(2026, 4, 5)}


def nth(y, m, wd, n):
    d = [x for x in range(1, calendar.monthrange(y, m)[1] + 1) if dt.date(y, m, x).weekday() == wd]
    return dt.date(y, m, d[n - 1])


def holidays(y):
    return {dt.date(y, 1, 1), nth(y, 2, 0, 1), nth(y, 3, 0, 3), dt.date(y, 5, 1), dt.date(y, 9, 16),
            nth(y, 11, 0, 3), dt.date(y, 12, 25), EASTER[y] - dt.timedelta(3), EASTER[y] - dt.timedelta(2)}


rows = []
for _, r in b.iterrows():
    y, m = map(int, r.month.split("-")); nd = calendar.monthrange(y, m)[1]; H = holidays(y)
    days = [dt.date(y, m, d) for d in range(1, nd + 1)]
    wk = sum(1 for d in days if d.weekday() < 5 and d not in H)
    sa = sum(1 for d in days if d.weekday() == 5 and d not in H)
    rows.append(dict(month=r.month, E=r.energy_kWh, htot=24 * nd, wk=wk, sa=sa, P=r.production_pairs,
                     shift=r.month in SHIFT, peak_meas=r.energy_kWh / (r.load_factor_reported * 24 * nd)))
B = pd.DataFrame(rows)


def ols(y, X):
    X = np.asarray(X, float); y = np.asarray(y, float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ beta; n, k = X.shape
    s2 = res @ res / (n - k); cov = s2 * np.linalg.inv(X.T @ X)
    from scipy import stats
    t = stats.t.ppf(0.975, n - k)
    se = np.sqrt(np.diag(cov))
    return beta, beta - t * se, beta + t * se


def estimate(shift_hours=24, shift_days="monsat", with_P=True):
    d = B.copy()
    hop = d.wk * 10 + d.sa * 5
    if shift_days == "monsat":
        hs = (d.wk + d.sa) * shift_hours
    else:   # Mon-Fri shifts, Saturday normal
        hs = d.wk * shift_hours + d.sa * 5
    d["hop"] = np.where(d["shift"], hs, hop); d["hoff"] = d.htot - d.hop
    if with_P:
        d = d.dropna(subset=["P"])
        X = d[["hoff", "hop", "P"]]
    else:
        X = d[["hoff", "hop"]]
    beta, lo, hi = ols(d.E, X)
    return dict(always_on_kW=float(beta[0]), ci=[float(lo[0]), float(hi[0])], operating_kW=float(beta[1]), n=int(len(d)))


out = {"calendar_regression": {
    "central (24 h Mon-Sat shifts, with production)": estimate(),
    "without production": estimate(with_P=False),
    "shifts 24 h Mon-Fri only": estimate(shift_days="monfri"),
    "shifts 20 h Mon-Sat": estimate(shift_hours=20),
}}
low = B.loc[B.E.idxmin()]
out["lowest_month_mean_load_kW"] = float(low.E / low.htot)

# measured vs modelled monthly peaks, reference year
P = central(); NZ = nz_central(); D = load_all(P); W = hourly_pv_per_kWp(P)
L, _, _ = load_profile([], P, NZ, D, W)
mh = W.month.to_numpy(); ref = D["ref"]
pk = []
for _, r in ref.iterrows():
    meas = r.energy_kWh / (r.load_factor_reported * 24 * r.days)
    pk.append(dict(model=float(L[mh == r.mon].max()), measured=float(meas), q_cap=float(r.energy_kWh / (24 * r.days * 0.57))))
pk = pd.DataFrame(pk)
out["peaks"] = dict(measured_min=float(pk.measured.min()), measured_max=float(pk.measured.max()),
                    model_min=float(pk.model.min()), model_max=float(pk.model.max()),
                    ratio_min=float((pk.measured / pk.model).min()), ratio_max=float((pk.measured / pk.model).max()),
                    months_model_below_cap=int((pk.model < pk.q_cap).sum()),
                    months_measured_below_cap=int((pk.measured < pk.q_cap).sum()))
json.dump(out, open(ROOT / "results/bill_loadcheck.json", "w"), indent=1)
print(json.dumps(out, indent=1))
