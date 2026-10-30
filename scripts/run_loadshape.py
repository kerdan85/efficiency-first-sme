"""Sensitivity of the hourly results to the synthetic load profile (reviewer request).

Variants of the hourly load: how the base-load-control saving (E4) is allocated, the always-on load, and the
operating schedule. For each variant and measure set: hourly self-sufficiency of the annual net-zero design
without storage, and the least-capital design reaching 80% self-sufficiency (PV x battery grid as in
run_netzero.py).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from efirst.hourly import evaluate_nz, hourly_pv_per_kWp, load_profile, nz_central, size_pv_for_annual_nz  # noqa: E402
from efirst.model import load_all  # noqa: E402
from efirst.params import central  # noqa: E402

P = central(); NZ0 = nz_central(); D = load_all(P); W = hourly_pv_per_kWp(P)
EE = ["E4", "E1", "E2", "E3", "E5"]
SETS = {"supply": ["E5"], "eefirst": EE}
MULTS = [round(x, 2) for x in np.arange(0.6, 2.41, 0.1)]
BATS = list(range(0, 2401, 100))
BASE24 = float(D["intercept"] / 730)        # regression base load spread over all hours (upper bound)

VARIANTS = {
    "central": dict(night=15.0, e4_mode="offhours", profile="standard"),
    "E4 proportional": dict(night=15.0, e4_mode="proportional", profile="standard"),
    "always-on 8 kW": dict(night=8.0, e4_mode="offhours", profile="standard"),
    "always-on 25 kW": dict(night=25.0, e4_mode="offhours", profile="standard"),
    f"always-on {BASE24:.0f} kW (all base load 24 h)": dict(night=BASE24, e4_mode="proportional", profile="standard"),
    "two-shift schedule": dict(night=15.0, e4_mode="offhours", profile="extended"),
}
rows = []
for name, v in VARIANTS.items():
    NZ = dict(NZ0); NZ["night_load_kW"] = v["night"]
    kw = dict(e4_mode=v["e4_mode"], profile=v["profile"])
    for lab, meas in SETS.items():
        k_nz = size_pv_for_annual_nz(meas, P, NZ, D, W)
        nz = evaluate_nz(meas, k_nz, 0, P, NZ, D, W, **kw)
        best = None
        for mult in MULTS:
            kwp = min(k_nz * mult, 700.0)
            for bat in BATS:
                r = evaluate_nz(meas, kwp, bat, P, NZ, D, W, **kw)
                if r["self_sufficiency"] >= 0.80 and (best is None or r["capex"] < best[0]):
                    best = (r["capex"], kwp, bat, r["npv"])
        L, _, night = load_profile(meas, P, NZ, D, W, **kw)
        rows.append(dict(variant=name, set=lab, always_on_kW=float(night.mean()), peak_kW=float(L.max()),
                         kWp_nz=k_nz, ss_nz=nz["self_sufficiency"], npv_nz=nz["npv"],
                         capex_ss80=best[0] if best else np.nan, kWp_ss80=best[1] if best else np.nan,
                         bat_ss80=best[2] if best else np.nan, npv_ss80=best[3] if best else np.nan))
        print(rows[-1], flush=True)
R = pd.DataFrame(rows)
R.to_csv(ROOT / "results/loadshape_sensitivity.csv", index=False)
piv = R.pivot(index="variant", columns="set", values="capex_ss80")
summary = dict(base24_kW=BASE24,
               ss80_capex_saving_range=[float((piv.supply - piv.eefirst).min()), float((piv.supply - piv.eefirst).max())],
               ss_nz_range={lab: [float(R[R.set == lab].ss_nz.min()), float(R[R.set == lab].ss_nz.max())] for lab in SETS},
               eefirst_cheaper_all=bool((piv.eefirst < piv.supply).all()))
json.dump(summary, open(ROOT / "results/loadshape_summary.json", "w"), indent=1)
print(R.round(2).to_string()); print(summary)
