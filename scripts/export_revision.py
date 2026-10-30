"""LaTeX macros for the analyses added in the first revision (E4 stress test, load-profile sensitivity,
GDMTH scenario, urbs robustness). Writes manuscript/numbers_rev.tex."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
N = {}
f = lambda x, d=0: f"{x:,.{d}f}".replace(",", "{,}")
mm = lambda x, d=2: f"{x / 1e6:.{d}f}"
pct = lambda x: f"{x * 100:.0f}"

# ---------------------------------------------------------------- E4 stress test
e = json.load(open(RES / "e4_stress.json"))
d = e["deterministic"]
N.update(KWpNoE=f(d["no_E4"]["kWp"], 1), CapexSaveNoE=pct(d["no_E4"]["capex_save"]), NPVGainNoE=mm(d["no_E4"]["npv_gain"]),
         NPVGainLowE=mm(d["E4_low_saving_high_cost"]["npv_gain"]), CapexSaveLowE=pct(d["E4_low_saving_high_cost"]["capex_save"]),
         NPVGainNoELowAll=mm(d["no_E4_low_E1_E3"]["npv_gain"]),
         ProbNoE=pct(e["mc_no_E4"]["prob_npv_gt_P2"]), ProbCapexNoE=pct(e["mc_no_E4"]["prob_capex_lt_P2"]))

if "mc_E4_low" in e:
    N.update(ProbLowE=pct(e["mc_E4_low"]["prob_npv_gt_P2"]), ProbCapexLowE=pct(e["mc_E4_low"]["prob_capex_lt_P2"]))
# E4 saving as kW of the always-on load (central allocation: hours outside the standard schedule, 8760*(1-260/730))
_hoff = 8760 * (1 - 260 / 730)
_kwh = e.get("E4_kWh_per_frac", 0)
N.update(EFourKWLo=f"{0.05 * _kwh / _hoff:.1f}", EFourKW=f"{0.10 * _kwh / _hoff:.1f}", EFourKWHi=f"{0.20 * _kwh / _hoff:.0f}")

# ---------------------------------------------------------------- load-profile sensitivity
L = pd.read_csv(RES / "loadshape_sensitivity.csv")
piv = L.pivot(index="variant", columns="set", values="capex_ss80")
save = piv.supply - piv.eefirst
N.update(LSSSLo=pct(L.ss_nz.min()), LSSSHi=pct(L.ss_nz.max()),
         LSBatLo=f(L.bat_ss80.min()), LSBatHi=f(L.bat_ss80.max()),
         LSSaveLo=mm(save.min()), LSSaveHi=mm(save.max()), LSBaseKW=f(L.always_on_kW.max()),
         LSAllCheaper="every" if bool((save > 0).all()) else "most")
ee = L[L.set == "eefirst"]
N.update(LSNPVLo=mm(ee.npv_ss80.min()), LSNPVHi=mm(ee.npv_ss80.max()))
# table
lab = {"central": "Central (always-on 15 kW, E4 outside operating hours)",
       "E4 proportional": "E4 split in proportion to base-load energy",
       "always-on 8 kW": "Always-on load 8 kW", "always-on 25 kW": "Always-on load 25 kW",
       "two-shift schedule": "Two-shift schedule (06:00--22:00)"}
rows = []
for v in L.variant.unique():
    s = L[(L.variant == v) & (L.set == "supply")].iloc[0]; t = L[(L.variant == v) & (L.set == "eefirst")].iloc[0]
    name = lab.get(v, f"All base load around the clock ({s.always_on_kW:.0f} kW)")
    rows.append(f"{name} & {s.ss_nz*100:.0f} & {t.ss_nz*100:.0f} & {s.kWp_ss80:.0f} / {s.bat_ss80:.0f} & {t.kWp_ss80:.0f} / {t.bat_ss80:.0f} & "
                f"{s.capex_ss80/1e6:.2f} & {t.capex_ss80/1e6:.2f} \\\\")
(ROOT / "manuscript/tables/loadshape.tex").write_text(r"""\begin{table}[H]
\caption{Sensitivity of the hourly results to the synthetic load profile.}
\label{tab:loadshape}
\footnotesize
\resizebox{\linewidth}{!}{%
\begin{tabular}{lrrrrrr}
\toprule
 & \multicolumn{2}{c}{Self-sufficiency, annual net zero (\%)} & \multicolumn{2}{c}{80\% design: kWp / kWh} & \multicolumn{2}{c}{80\% design: capital (MMXN)} \\
\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}
Load profile & Supply only & Eff. first & Supply only & Eff. first & Supply only & Eff. first \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}}
\end{table}
""")

# ---------------------------------------------------------------- GDMTH
g = json.load(open(RES / "gdmth.json"))
s, x = g["standard"], g["extended"]
b = s["portfolios"]
N.update(GHValEE=f"{s['value_per_kWh_EE']['gdmth']:.2f}", GOValEE=f"{s['value_per_kWh_EE']['gdmto']:.2f}",
         GHValPV=f"{s['value_per_kWh_PV']['gdmth']:.2f}", GOValPV=f"{s['value_per_kWh_PV']['gdmto']:.2f}",
         GHValEEExt=f"{x['value_per_kWh_EE']['gdmth']:.2f}", GHValPVExt=f"{x['value_per_kWh_PV']['gdmth']:.2f}",
         GOPfourGain=mm(s["p4_minus_p2_npv"]["gdmto"]), GHPfourGain=mm(s["p4_minus_p2_npv"]["gdmth"]),
         GHPfourGainExt=mm(x["p4_minus_p2_npv"]["gdmth"]),
         GHPfourGainLo=mm(min(v["p4_minus_p2_npv"]["gdmth"] for k_, v in g.items() if isinstance(v, dict) and "p4_minus_p2_npv" in v)),
         GHPfourGainHi=mm(max(v["p4_minus_p2_npv"]["gdmth"] for k_, v in g.items() if isinstance(v, dict) and "p4_minus_p2_npv" in v)),
         GHBillZero=f(b["P0 baseline"]["bill_gdmth"] / 1e3), GOBillZero=f(b["P0 baseline"]["bill_gdmto"] / 1e3),
         GHBillChange=pct(1 - b["P0 baseline"]["bill_gdmth"] / b["P0 baseline"]["bill_gdmto"]),
         GHNPVTwo=mm(b["P2 PV only"]["npv_gdmth"]), GONPVTwo=mm(b["P2 PV only"]["npv_gdmto"]),
         GHNPVOne=mm(b["P1 efficiency"]["npv_gdmth"]), GONPVOne=mm(b["P1 efficiency"]["npv_gdmto"]))

# ---------------------------------------------------------------- bill-based check of the hourly load
bc = json.load(open(RES / "bill_loadcheck.json")); cr = bc["calendar_regression"]
c0 = cr["central (24 h Mon-Sat shifts, with production)"]
N.update(BCAon=f(c0["always_on_kW"]), BCAonLo=f(c0["ci"][0]), BCAonHi=f(c0["ci"][1]), BCOp=f(c0["operating_kW"]),
         BCAonShort=f(min(cr["shifts 24 h Mon-Fri only"]["always_on_kW"], cr["shifts 20 h Mon-Sat"]["always_on_kW"])),
         BCAonNoP=f(cr["without production"]["always_on_kW"]),
         BCLowMonth=f(bc["lowest_month_mean_load_kW"]),
         BCPeakLo=f(bc["peaks"]["measured_min"]), BCPeakHi=f(bc["peaks"]["measured_max"]),
         BCRatioLo=f"{bc['peaks']['ratio_min']:.1f}", BCRatioHi=f"{bc['peaks']['ratio_max']:.1f}")
N.update(GHPfourGainPk=mm(g["peak calibrated"]["p4_minus_p2_npv"]["gdmth"]))

# ---------------------------------------------------------------- alternative baseline specifications
ba = pd.read_csv(RES / "baseline_alt.csv")
rows = []
for _, r in ba.iterrows():
    r2s = "--" if pd.isna(r.r2) else f"{r.r2:.2f}"; cvs = "--" if pd.isna(r.cv_rmse) else f"{r.cv_rmse*100:.1f}"
    rows.append(f"{r.spec.replace('%', chr(92) + '%')} & {int(r.n)} & {r2s} & {cvs} & {f(r.base_kWh_month)} ({r.base_share*100:.0f}) & {r.npv_gain_central/1e6:.2f} & {r.capex_save_central*100:.0f} & {r.npv_gain_lowE4/1e6:.2f} \\\\")
(ROOT / "manuscript/tables/baseline_alt.tex").write_text(r"""\begin{table}[H]
\caption{Alternative baseline specifications. The base load is the production-independent consumption (intercept, or the regression evaluated at zero production for multivariate and calendar models); only base-load control (E4) depends on it. For each base load, efficiency first (P4) is re-sized to match the grid purchases of PV only (P2).}
\label{tab:baselinealt}
\footnotesize
\resizebox{\linewidth}{!}{%
\begin{tabular}{lrrrrrrr}
\toprule
 & & & & Base load & \multicolumn{2}{c}{P4 vs.\ P2, E4 central} & E4 lowest \\
\cmidrule(lr){6-7}\cmidrule(lr){8-8}
Specification & $n$ & $R^2$ & CV-RMSE (\%) & kWh/month (\% of mean) & $\Delta$NPV (MMXN) & Capital saving (\%) & $\Delta$NPV (MMXN) \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}}
\end{table}
""")
N.update(BABaseLo=f(ba.base_share.min() * 100), BABaseHi=f(ba.base_share.max() * 100),
         BABaseLoSpec=f(ba[ba.spec.str.startswith("Lower") == False].base_share.min() * 100),
         BAGainLo=mm(ba.npv_gain_central.min()), BAGainHi=mm(ba.npv_gain_central.max()),
         BALowELo=mm(ba.npv_gain_lowE4.min()), BALowEHi=mm(ba.npv_gain_lowE4.max()),
         BANSpec=str(len(ba)),
         BACalCV=f"{ba[ba.spec.str.startswith('Calendar')].cv_rmse.iloc[0]*100:.1f}",
         BACalR=f"{ba[ba.spec.str.startswith('Calendar')].r2.iloc[0]:.2f}",
         BADumCV=f"{ba[ba.spec.str.contains('dummy')].cv_rmse.iloc[0]*100:.1f}")

# ---------------------------------------------------------------- urbs robustness
rp = RES / "urbs_robustness.csv"
if rp.exists():
    R = pd.read_csv(rp)
    base = pd.read_csv(RES / "urbs_results.csv")
    rows = []
    names = {"monthly-netting": "Monthly netting (no carry-over of credits)",
             "degradation": "PV degradation and battery fade",
             "binary-adoption": "All-or-nothing adoption of measures (MILP)",
             "all-three": "All three combined"}
    saves = []
    for case, nm in names.items():
        cells = []
        for cap in (np.nan, 0.30, 0.20, 0.10):
            sel = lambda df, ee: df[(df.case == case) & (df.efficiency == ee) &
                                    (df.co2_cap_frac.isna() if np.isnan(cap) else np.isclose(df.co2_cap_frac, cap))]
            E_ = sel(R, True)
            if case == "binary-adoption":
                S_ = base[(base.case == ("cost-optimal" if np.isnan(cap) else "co2-cap")) & (~base.efficiency) &
                          np.isclose(base.bat_cost_factor, 1.0) &
                          (base.co2_cap_frac.isna() if np.isnan(cap) else np.isclose(base.co2_cap_frac, cap))]
            else:
                S_ = sel(R, False)
            if len(E_) and len(S_):
                e_, s_ = E_.iloc[0], S_.iloc[0]
                sv = 1 - e_.total_cost / s_.total_cost; saves.append(sv)
                ad = "".join("1" if e_[f"adopt_{m}"] > 0.99 else ("p" if e_[f"adopt_{m}"] > 0.01 else "0") for m in ("E4", "E3", "E2", "E1"))
                cells.append(f"{sv*100:.0f} ({abs(round(e_.bat_kWh_usable)):.0f}/{abs(round(s_.bat_kWh_usable)):.0f})")
            else:
                cells.append("--")
        rows.append(f"{nm} & " + " & ".join(cells) + r" \\")
    (ROOT / "manuscript/tables/urbs_robust.tex").write_text(r"""\begin{table}[H]
\caption{Robustness of the urbs results: cost saving from efficiency (\%) and usable battery capacity with/without efficiency (kWh).}
\label{tab:urbsrobust}
\footnotesize
\resizebox{\linewidth}{!}{%
\begin{tabular}{lrrrr}
\toprule
Variant & No cap & CO$_2$ cap 30\% & CO$_2$ cap 20\% & CO$_2$ cap 10\% \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}}
\end{table}
""")
    capped = R[(R.efficiency) & R.co2_cap_frac.notna()]
    first_ee = []  # is the efficiency bundle complete whenever a battery is installed?
    for _, r_ in capped.iterrows():
        if r_.bat_kWh_usable > 1:
            first_ee.append(all(r_[f"adopt_{m}"] > 0.99 for m in ("E4", "E3", "E2", "E1")))
    N.update(URSaveMin=pct(min(saves)), URSaveMax=pct(max(saves)),
             URBundleFirst="in every" if all(first_ee) else "in most",
             URMIPTime=f(R[R.binary_ee].solve_s.mean() / 60, 0) if "binary_ee" in R else "--")
# urbs re-solved with alternative load profiles
lsv = [RES / f"urbs_loadshape_{t}.csv" for t in ("base24", "twoshift")]
if all(x.exists() for x in lsv):
    sv, batless = [], []
    for x in lsv:
        U = pd.read_csv(x)
        for cap in (np.nan, 0.30, 0.20, 0.10):
            sel = lambda ee: U[(U.efficiency == ee) & (U.co2_cap_frac.isna() if np.isnan(cap) else np.isclose(U.co2_cap_frac, cap))]
            e_, s_ = sel(True).iloc[0], sel(False).iloc[0]
            sv.append(1 - e_.total_cost / s_.total_cost)
            if not np.isnan(cap):
                batless.append(e_.bat_kWh_usable <= s_.bat_kWh_usable + 1)
    N.update(ULSSaveMin=pct(min(sv)), ULSSaveMax=pct(max(sv)), ULSBatLess="always" if all(batless) else "mostly")
else:
    N.update(ULSSaveMin="??", ULSSaveMax="??", ULSBatLess="??")
(ROOT / "manuscript/numbers_rev.tex").write_text("".join(f"\\newcommand{{\\n{k}}}{{{v}}}\n" for k, v in N.items()))
json.dump(N, open(RES / "revision_numbers.json", "w"), indent=1)
print(json.dumps(N, indent=1))
