"""Figures (Nature-style: 7 pt sans, thin axes, Okabe-Ito palette) and a Markdown summary."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

OI = ["#000000", "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7"]


def _style():
    import matplotlib as mpl
    mpl.use("Agg")
    mpl.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
                         "font.size": 7, "axes.linewidth": 0.5, "xtick.major.width": 0.5,
                         "ytick.major.width": 0.5, "xtick.major.size": 2.5, "ytick.major.size": 2.5,
                         "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
                         "savefig.dpi": 600, "pdf.fonttype": 42})
    import matplotlib.pyplot as plt
    return plt


def _letter(ax, s):
    ax.text(-0.18, 1.05, s, transform=ax.transAxes, fontweight="bold", fontsize=8, va="bottom")


def fig_merit_order(M: pd.DataFrame, marginal: float, cur: str, path: Path):
    plt = _style()
    d = M[M.saved_MWh > 0].sort_values("cce")
    fig, ax = plt.subplots(figsize=(3.5, 2.4))
    x = 0.0
    for i, (k, r) in enumerate(d.iterrows()):
        col = OI[6] if k == "PV" else OI[3]
        ax.bar(x, r.cce, width=r.saved_MWh, align="edge", color=col, edgecolor="white", linewidth=0.4)
        ax.text(x + r.saved_MWh / 2, r.cce + 0.04, k, ha="center", fontsize=6)
        x += r.saved_MWh
    ax.axhline(marginal, color=OI[0], lw=0.6, ls="--")
    ax.text(x, marginal, f" marginal tariff {marginal:.2f}", va="bottom", ha="right", fontsize=6)
    ax.set_xlabel("Annual grid electricity avoided (MWh)")
    ax.set_ylabel(f"CCE or LCOE ({cur}/kWh)")
    ax.set_xlim(0, x * 1.02); ax.set_ylim(0, max(marginal, d.cce.max()) * 1.2)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def fig_pathways(PA: pd.DataFrame, cur: str, path: Path):
    plt = _style()
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.4))
    t = PA.target * 100
    axs[0].plot(t, PA.supply_capex / 1e6, color=OI[6], lw=1, label="Supply only (PV)")
    axs[0].plot(t, PA.ee_capex / 1e6, color=OI[3], lw=1, label="Efficiency first")
    axs[0].set_xlabel("Reduction in grid purchases (%)"); axs[0].set_ylabel(f"Up-front capex (M {cur})")
    axs[0].legend(); _letter(axs[0], "a")
    axs[1].plot(t, PA.supply_npv / 1e6, color=OI[6], lw=1)
    axs[1].plot(t, PA.ee_npv / 1e6, color=OI[3], lw=1)
    axs[1].set_xlabel("Reduction in grid purchases (%)"); axs[1].set_ylabel(f"NPV (M {cur})")
    _letter(axs[1], "b")
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def fig_netzero(F: pd.DataFrame, cur: str, path: Path):
    plt = _style()
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.4))
    for lab, col, name in (("supply", OI[6], "Supply only"), ("eefirst", OI[3], "Efficiency first")):
        f = F[F.set == lab]
        axs[0].plot(f.target * 100, f.capex / 1e6, color=col, lw=1, marker="o", ms=2, label=name)
        axs[1].plot(f.target * 100, f.npv / 1e6, color=col, lw=1, marker="o", ms=2)
    axs[0].set_xlabel("Hourly self-sufficiency (%)"); axs[0].set_ylabel(f"Least capex (M {cur})"); axs[0].legend()
    axs[1].axhline(0, color=OI[0], lw=0.5)
    axs[1].set_xlabel("Hourly self-sufficiency (%)"); axs[1].set_ylabel(f"NPV, net metering (M {cur})")
    _letter(axs[0], "a"); _letter(axs[1], "b")
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def _fmt(x, nd=2):
    if isinstance(x, (float, np.floating)):
        if x != x:
            return "-"
        if abs(x) >= 1e3:
            return f"{x:,.0f}"
        if x != 0 and abs(x) < 0.1:
            return f"{x:.3g}"
        return f"{x:.{nd}f}"
    return str(x)


def markdown_summary(name, cur, R: dict) -> str:
    L = [f"# EE1st appraisal: {name}", ""]
    b = R["baseline"]; t = R["tariff"]
    L += ["## Inputs check", f"- Reference-year consumption: {_fmt(R['ref_MWh'])} MWh; annual bill {_fmt(R['bill0'])} {cur}",
          f"- Marginal value of a saved kWh: {t['marginal']:.3f} {cur}/kWh"]
    if "validation_mean_error" in t:
        L.append(f"- Tariff model vs reported prices: bias {t['validation_mean_error']*100:+.1f}%, "
                 f"mean absolute error {t['validation_mae']*100:.1f}%")
    if "selected" in b:
        s = b["selected"]
        L.append(f"- Baseline: kWh = {s['intercept']:.0f} + {s['slope']:.3f} x production (R2 {s['r2']:.2f}, n {s['n']}); "
                 f"base load {R['base_share']*100:.0f}% of consumption")
    L += ["", "## Measures (merit order; PF correction last, no kWh saved)", "", f"| id | name | capex ({cur}) | MWh/yr | CCE/LCOE ({cur}/kWh) | NPV ({cur}) |",
          "|---|---|---:|---:|---:|---:|"]
    for k, r in sorted(R["measures"].items(), key=lambda kv: (kv[1]["cce"] != kv[1]["cce"], kv[1]["cce"])):
        L.append(f"| {k} | {r['name']} | {_fmt(r['capex'])} | {_fmt(r['saved_MWh'],1)} | {_fmt(r['cce'])} | {_fmt(r['npv'])} |")
    L += ["", "## Portfolios", "", f"| | PV kWp | capex | NPV | grid cut | tCO2/yr | roof m2 | bill shock exposure |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k, r in R["portfolios"].items():
        L.append(f"| {k} | {r['pv_kWp']:.1f} | {_fmt(r['capex'])} | {_fmt(r['npv'])} | {r['grid_saved_frac']*100:.0f}% | "
                 f"{r['co2_saved_t']:.0f} | {r['roof_m2']:.0f} | {_fmt(r['shock_exposure1'])} |")
    if R.get("stress"):
        L += ["", "Regulatory stress (no demand credit for PV): " +
              ", ".join(f"{k} NPV {_fmt(v)}" for k, v in R["stress"].items())]
    if R.get("montecarlo"):
        m = R["montecarlo"]
        L += ["", f"## Monte Carlo (n = {m['n']}, seed {m['seed']})",
              "- P(NPV > 0): " + ", ".join(f"{k} {v*100:.0f}%" for k, v in m["prob_npv_positive"].items())]
        if "prob_P4_beats_P2" in m:
            L.append(f"- P(efficiency first + right-sized PV beats PV only): {m['prob_P4_beats_P2']*100:.0f}%")
        L.append(f"- P(all CCE below marginal tariff): {m['prob_all_cce_below_marginal']*100:.2f}%")
    if R.get("parameters"):
        ps = R["parameters"]; has = any("spearman_P4_minus_P2" in p for p in ps)
        L += ["", "## Inputs: data status" + (" and influence on the efficiency-first advantage" if has else ""), "",
              "Spearman rank correlation with NPV(P4) − NPV(P2) across the Monte Carlo draws; "
              "inputs marked `assumption` with large |rho| are where a site measurement is worth most." if has else
              "Inputs with their data status.", "",
              "| input | central | range | status | rho |", "|---|---:|---|---|---:|"]
        for p in ps:
            if not p["monte_carlo"]:
                continue
            rho = p.get("spearman_P4_minus_P2")
            L.append(f"| {p['name']} | {_fmt(p['central'])} | {_fmt(p['low'])}–{_fmt(p['high'])} | {p['status']} | "
                     f"{'' if rho is None or rho != rho else f'{rho:+.2f}'} |")
        fixed = [p for p in ps if not p["monte_carlo"] and p["status"] == "assumption"]
        if fixed:
            L.append("")
            L.append("Fixed inputs marked `assumption`: " + ", ".join(p["name"] for p in fixed) + ".")
    if R.get("netzero"):
        L += ["", "## Net-zero electricity designs (net metering)", "", "| design | kWp | battery kWh | self-sufficiency | capex | NPV |",
              "|---|---:|---:|---:|---:|---:|"]
        for k, r in R["netzero"].items():
            if r is None:
                L.append(f"| {k} | not reachable in the explored range | | | | |"); continue
            L.append(f"| {k} | {r['kWp']:.0f} | {r['bat_kWh']:.0f} | {r['self_sufficiency']*100:.0f}% | {_fmt(r['capex'])} | {_fmt(r['npv'])} |")
    if R.get("netzero_nightload"):
        L += ["", "Sensitivity to the always-on load N of the synthetic hourly profile (net metering):", "",
              "| N (kW) | set | self-sufficiency at annual net zero | least capex at target |", "|---:|---|---:|---:|"]
        for r in R["netzero_nightload"]:
            L.append(f"| {r['night_load_kW']:g} | {r['set']} | {r['ss_annual_nz']*100:.0f}% | "
                     f"{_fmt(r['capex_at_target']) if r['capex_at_target'] == r['capex_at_target'] else 'not reached'} "
                     f"({r['target']*100:.0f}%) |")
    if R.get("thermal"):
        L += ["", "## Heat options (per GJ useful heat)", ""]
        for k, r in R["thermal"].items():
            v = [f"{a} {_fmt(b)}" for a, b in r.items() if b == b]
            L.append(f"- {k}: " + ", ".join(v))
    L += ["", "All values are model outputs from the inputs in the case file; parameters marked `assumption` "
          "should be replaced by site measurements where available."]
    return "\n".join(L) + "\n"


def dump_json(obj, path):
    def conv(o):
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)
    Path(path).write_text(json.dumps(obj, indent=1, default=conv))
