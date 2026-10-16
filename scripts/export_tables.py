"""Generate LaTeX tables for the manuscript from results and raw data."""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from efirst.params import PARAMS  # noqa: E402
from efirst.hourly import NZ_PARAMS  # noqa: E402

T = ROOT / "manuscript" / "tables"; T.mkdir(parents=True, exist_ok=True)
mc = json.load(open(ROOT / "results/montecarlo_summary.json"))
M = pd.read_csv(ROOT / "results/measures.csv").set_index("id")
PT = pd.read_csv(ROOT / "results/portfolios.csv").set_index("portfolio")


def n(x, d=0):
    return f"{x:,.{d}f}".replace(",", "{,}")


# ---------------- Table: stand-alone measures
rows = []
lab = {"E4": "E4 Base-load (idle) control", "E3": "E3 Insulation of heated platens/barrels",
       "E2": "E2 Servo motors on sewing machines", "E1": "E1 Compressed-air package",
       "E5": "E5 Power-factor correction (50 kVAr)", "PV": "S1 Rooftop PV (163.8 kWp)"}
for i in ["E4", "E3", "E2", "E1", "E5", "PV"]:
    r = M.loc[i]
    if i == "PV":
        cce = f"{r.cce:.2f} [{mc['lcoe_PV']['p5']:.2f}--{mc['lcoe_PV']['p95']:.2f}]"
    elif i == "E5":
        cce = "--"
    else:
        cce = f"{r.cce:.2f} [{mc['cce_'+i]['p5']:.2f}--{mc['cce_'+i]['p95']:.2f}]"
    rows.append(f"{lab[i]} & {n(r.capex/1000)} & {n(r.saved_MWh,1)} & {cce} & {n(r.savings_y1/1000)} & "
                f"{n(r.npv/1e6,2)} & {n(r.payback,1)} & {n(r.co2_t,1)} \\\\")
(T / "measures.tex").write_text(r"""\begin{table}[!htbp]
\centering
\caption{Stand-alone appraisal of each option (CCE: for PV, LCOE; 5th--95th percentiles in brackets).}
\label{tab:measures}
\resizebox{\textwidth}{!}{%
\begin{tabular}{lrrlrrrr}
\toprule
Option & Capex & Electricity saved & CCE / LCOE & Bill saving, yr 1 & NPV & Payback & CO$_2$ avoided \\
 & (kMXN) & (MWh yr$^{-1}$) & (MXN kWh$^{-1}$) & (kMXN yr$^{-1}$) & (MMXN) & (yr) & (t yr$^{-1}$) \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}}
\end{table}
""")

# ---------------- Table: portfolios
K = [("P0 Baseline", "P0 Baseline"), ("P1 Efficiency bundle", "P1 Efficiency bundle (E1--E5)"),
     ("P2 PV only (163.8 kWp)", "P2 Supply only: PV 163.8 kWp"),
     ("P3 Efficiency + PV (163.8 kWp)", "P3 Efficiency bundle + PV 163.8 kWp"),
     ("P4 Efficiency first + right-sized PV", f"P4 Efficiency first + PV {PT.loc['P4 Efficiency first + right-sized PV','pv_kWp']:.1f} kWp")]
rows = []
for k, l in K:
    r = PT.loc[k]
    rows.append(f"{l} & {n(r.capex/1e6,2)} & {n(r.npv/1e6,2)} & {n(r.grid1_MWh)} & {n(100*r.grid_saved_frac)} & "
                f"{n(r.co2_1_t)} & {n(r.billed_peak1_kW)} & {n(r.shock_exposure1/1000)} & {n(r.imported_gas_avoided_GJ)} & {n(r.roof_m2)} \\\\")
(T / "portfolios.tex").write_text(r"""\begin{table}[!htbp]
\centering
\caption{Portfolio comparison on common indicators.}
\label{tab:portfolios}
\resizebox{\textwidth}{!}{%
\begin{tabular}{lrrrrrrrrr}
\toprule
Portfolio & Capex & NPV & Grid purchases & Reduction & Residual CO$_2$ & Peak demand & Shock exposure & Imported gas & PV roof \\
 & (MMXN) & (MMXN) & (MWh yr$^{-1}$) & (\%) & (t yr$^{-1}$) & (kW) & (kMXN yr$^{-1}$) & (GJ yr$^{-1}$) & (m$^2$) \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}}
\end{table}
""")

# ---------------- Appendix: billing data (summary only; monthly records are confidential)
b = pd.read_csv(ROOT / "data/raw/billing_monthly.csv")
spec = [("Electricity (kWh per month)", b.energy_kWh, lambda v: n(v)),
        ("Billed demand (kW)", b.max_demand_kW, lambda v: f"{v:.0f}"),
        ("Power factor (\\%)", 100 * b.power_factor, lambda v: f"{v:.1f}"),
        ("Average price (MXN kWh$^{-1}$, pre-VAT)", b.avg_price_MXN_per_kWh_reported, lambda v: f"{v:.3f}"),
        ("Production (pairs per month)", b.production_pairs.dropna(), lambda v: n(v))]
rows = [f"{lab} & {len(x)} & {f(x.min())} & {f(x.mean())} & {f(x.max())} \\\\" for lab, x, f in spec]
(T / "billing.tex").write_text(r"""\begin{table}[H]
\centering
\caption{Billing and production records, January 2024--April 2026 (summary only; monthly data confidential).}
\label{tab:billing}
\footnotesize
\begin{tabular}{lrrrr}
\toprule
Variable & Months & Minimum & Mean & Maximum \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")

# ---------------- Appendix: tariffs
t = pd.read_csv(ROOT / "data/raw/cfe_gdmto_centro_oriente.csv")
rows = [f"{r.month} & {r.fixed_MXN_per_month:.2f} & {r.energy_MXN_per_kWh:.3f} & {r.distribution_MXN_per_kW:.2f} & {r.capacity_MXN_per_kW:.2f} \\\\"
        for _, r in t.iterrows()]
(T / "tariffs.tex").write_text(r"""\begin{table}[H]
\centering
\caption{Official GDMTO charges, Centro Oriente division, pre-VAT \citep{cfe2026gdmto}.}
\label{tab:tariffs}
\footnotesize
\resizebox{\linewidth}{!}{%
\begin{tabular}{lrrrr}
\toprule
Month & Fixed (MXN month$^{-1}$) & Energy (MXN kWh$^{-1}$) & Distribution (MXN kW$^{-1}$) & Capacity (MXN kW$^{-1}$) \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}}
\end{table}
""")

# ---------------- Appendix: parameters
nice = {"measured": "M", "official": "O", "official-derived": "O*", "literature": "L", "quote": "Q",
        "assumption": "A", "design": "D", "regulatory": "R"}
rows = []
for k, (c, lo, hi, st, src) in {**PARAMS, **NZ_PARAMS}.items():
    if k == "bat_cost_per_kWh":
        lo, hi = c, c
    rng = "fixed" if lo == hi else f"{lo:g}--{hi:g}"
    src_tex = src.replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")
    for key in ["doe2016compressed", "nemesa2023", "reich2012", "kent2018", "mouzon2007", "kara2011",
                "arpagaus2018", "schlosser2020", "semarnat2025fesen", "eia2025mexico", "sener2025plan"]:
        pass
    src_tex = src_tex.replace("NREL ATB 2024", "NREL ATB 2024 (\\citealp{nrel2024atb})")
    for key in ["doe2016compressed", "nemesa2023", "reich2012", "kent2018", "mouzon2007", "kara2011",
                "arpagaus2018", "schlosser2020", "semarnat2025fesen", "eia2025mexico", "sener2025plan"]:
        src_tex = src_tex.replace(key, r"\citet{" + key + "}")
    rows.append(f"\\texttt{{{k.replace('_', chr(92)+'_')}}} & {c:g} & {rng} & {nice[st]} & {src_tex} \\\\")
(T / "parameters.tex").write_text(r"""{\footnotesize
\begin{longtable}{p{3.4cm}rlcp{4.0cm}}
\caption{Model parameters, ranges and status.}\label{tab:parameters}\\
\toprule
Parameter & Central & Range & Status & Source / note \\
\midrule
\endfirsthead
\toprule
Parameter & Central & Range & Status & Source / note \\
\midrule
\endhead
""" + "\n".join(rows) + r"""
\bottomrule
\end{longtable}}
""")

# ---------------- Appendix: one-way sensitivity (top 10 by P4 swing)
s = pd.read_csv(ROOT / "results/sensitivity_oneway.csv")
piv = s.pivot(index="param", columns="case", values=["npv_P1", "npv_P2", "npv_P4"])
piv["swing"] = (piv[("npv_P4", "high")] - piv[("npv_P4", "low")]).abs()
piv = piv.sort_values("swing", ascending=False).head(12)
rows = []
for p_, r in piv.iterrows():
    rows.append(f"\\texttt{{{p_.replace('_', chr(92)+'_')}}} & " + " & ".join(
        f"{r[(c, lab_)]/1e6:.2f}" for c in ["npv_P1", "npv_P2", "npv_P4"] for lab_ in ["low", "high"]) + " \\\\")
(T / "sensitivity.tex").write_text(r"""\begin{table}[H]
\centering
\caption{One-way sensitivity of 20-year NPV (MMXN).}
\label{tab:sensitivity}
\footnotesize
\resizebox{\linewidth}{!}{%
\begin{tabular}{lrrrrrr}
\toprule
 & \multicolumn{2}{c}{P1 Efficiency} & \multicolumn{2}{c}{P2 PV only} & \multicolumn{2}{c}{P4 Efficiency first} \\
Parameter & low & high & low & high & low & high \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}}
\end{table}
""")
print("tables written")

# ---------------- EnergyPlus cross-validation
ep = pd.read_csv(ROOT / "results/energyplus_validation.csv")
lab = {"NZ-S": "NZ-S annual net zero, supply only", "NZ-E": "NZ-E annual net zero, efficiency first",
       "SS80-S": "80\\% self-sufficiency, supply only", "SS80-E": "80\\% self-sufficiency, efficiency first",
       "SS90-E": "90\\% self-sufficiency, efficiency first",
       "NZ-S-EP": "NZ-S re-sized with EnergyPlus yield", "NZ-E-EP": "NZ-E re-sized with EnergyPlus yield"}
rows = []
for _, r in ep.iterrows():
    py = lambda v, d=0: "--" if pd.isna(v) else n(v, d)
    rows.append(f"{lab[r.design]} & {n(r.kWp,1)} & {n(r.bat_kWh)} & {py(r.py_pv_MWh)} / {n(r.pv_ac_MWh)} & "
                f"{py(r.py_import_MWh)} / {n(r.import_MWh)} & {py(r.py_export_MWh)} / {n(r.export_MWh)} & "
                f"{py(100*r.py_self_sufficiency if not pd.isna(r.py_self_sufficiency) else float('nan'),1)} / {n(100*r.self_sufficiency,1)} \\\\")
(T / "energyplus.tex").write_text(r"""\begin{table}[!htbp]
\centering
\caption{Net-zero designs: Python model versus EnergyPlus 25.1 (annual values).}
\label{tab:energyplus}
\resizebox{\textwidth}{!}{%
\begin{tabular}{lrrrrrr}
\toprule
Design & PV (kWp) & Battery (kWh) & PV output (MWh) & Grid imports (MWh) & Exports (MWh) & Self-sufficiency (\%) \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}}
\end{table}
""")
print("energyplus table written")
