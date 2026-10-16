"""All figures generated from results/*.csv|json (Nature-style, Okabe-Ito)."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from efirst.model import load_all  # noqa: E402

FIG = ROOT / "figures"; FIG.mkdir(exist_ok=True)
RES = ROOT / "results"
OI = dict(black="#000000", orange="#E69F00", sky="#56B4E9", green="#009E73", yellow="#F0E442",
          blue="#0072B2", verm="#D55E00", purple="#CC79A7", grey="#999999")
C_EE, C_PV, C_MIX, C_BASE = OI["green"], OI["orange"], OI["blue"], OI["grey"]
MM = 1 / 25.4
W1, W2 = 89 * MM, 183 * MM

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
    "font.size": 7, "axes.titlesize": 7, "axes.labelsize": 7, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
    "legend.fontsize": 6.5, "axes.linewidth": 0.5, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": False, "lines.linewidth": 1.0, "legend.frameon": False, "pdf.fonttype": 42, "ps.fonttype": 42,
    "savefig.dpi": 600, "figure.dpi": 150,
})

res = json.load(open(RES / "results.json"))
mc = json.load(open(RES / "montecarlo_summary.json"))
D = load_all()


def panel(ax, letter, x=-0.18, y=1.04):
    ax.text(x, y, letter, transform=ax.transAxes, fontsize=8, fontweight="bold", va="bottom", ha="left")


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------ Fig 1 data/baseline/tariff
b = D["billing"]
fig, axs = plt.subplots(1, 3, figsize=(W2, 52 * MM), gridspec_kw=dict(width_ratios=[1.5, 1, 1], wspace=0.42))
ax = axs[0]
x = np.arange(len(b))
# monthly records are confidential: both series are shown as an index (period mean = 100)
EM, PM = b.energy_kWh.mean(), b.production_pairs.mean()
ax.bar(x, b.energy_kWh / EM * 100, color=C_BASE, width=0.75, label="Electricity")
p = b.production_pairs / PM * 100
ax.plot(x, p, "o-", color=OI["black"], ms=2.2, lw=0.8, label="Production")
import calendar
ax.set_xticks(x[::6]); ax.set_xticklabels([calendar.month_abbr[int(m[5:])] + " " + m[2:4] for m in b.month[::6]])
ax.set_ylabel("Index (period mean = 100)")
ax.set_xlim(-0.8, len(b) - 0.2)
ax.legend(loc="upper left", ncol=1, handlelength=1.2)
ax.axvspan(21.5, 24.5, color=OI["yellow"], alpha=0.35, lw=0)
ax.set_ylim(0, 235)
ax.text(23, 222, "24-h shifts", ha="center", fontsize=6)
panel(ax, "a", x=-0.12)
ax = axs[1]
pp = b.dropna(subset=["production_pairs"])
shift = pp.month.isin(["2025-11", "2025-12", "2026-01"])
ax.scatter(pp[~shift].production_pairs / PM * 100, pp[~shift].energy_kWh / EM * 100, s=9, color=OI["blue"], lw=0, label="Regular months")
ax.scatter(pp[shift].production_pairs / PM * 100, pp[shift].energy_kWh / EM * 100, s=11, marker="^", color=OI["verm"], lw=0, label="24-h-shift months")
xx = np.linspace(0, 260, 50)
for key, ls, lab in (("excl_24h_shift", "-", "Fit excl. 24-h shifts"), ("student_subset_as_reported", "--", "Original fit (16 mo)")):
    m = res["baseline"][key]
    ax.plot(xx, (m["intercept"] + m["slope"] * xx / 100 * PM) / EM * 100, ls, color=OI["black"], lw=0.8,
            label=f"{lab}, $R^2$={m['r2']:.2f}")
ax.set_xlabel("Production (index)"); ax.set_ylabel("Electricity (index)")
ax.set_ylim(0, 200); ax.set_xlim(0, 260)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.32), handlelength=1.4, fontsize=5.8, ncol=1)
panel(ax, "b")
ax = axs[2]
v = pd.read_csv(RES / "tariff_validation.csv")
ax.plot([2.6, 3.2], [2.6, 3.2], color=OI["grey"], lw=0.6)
ax.scatter(v.model_price, v.reported_price, s=9, color=OI["blue"], lw=0)
ax.set_xlabel("Modelled price (MXN kWh$^{-1}$)"); ax.set_ylabel("Reported price (MXN kWh$^{-1}$)")
ax.set_xlim(2.6, 3.2); ax.set_ylim(2.6, 3.2)
tv = res["tariff_validation"]
ax.text(2.62, 3.17, f"Bias {tv['mean_error']*100:+.1f}%\nMAPE {tv['mape']*100:.1f}%", va="top", fontsize=6)
panel(ax, "c")
save(fig, "fig1_data_baseline")

# ------------------------------------------------------------------ Fig 2 end uses + conservation supply curve
areas = pd.read_csv(ROOT / "data/raw/area_disaggregation_reference_month.csv").sort_values("share")
areas = areas[areas.share > 0.005]
M = pd.read_csv(RES / "measures.csv").set_index("id")
fig, axs = plt.subplots(1, 2, figsize=(W2, 58 * MM), gridspec_kw=dict(width_ratios=[1, 1.5], wspace=0.55))
ax = axs[0]
target = {"compressed air room": C_EE, "stitching (sewing)": C_EE, "vulcanising": C_EE, "sole injection moulding": C_EE}  # E1-E3 target areas
cols = [target.get(a, C_BASE) for a in areas.area_en]
ax.barh(areas.area_en.str.capitalize(), areas.share * 100, color=cols, height=0.7)
ax.set_xlabel("Share of reference-month electricity (%)")
for i, s in enumerate(areas.share):
    ax.text(s * 100 + 0.5, i, f"{s*100:.1f}", va="center", fontsize=6)
ax.set_xlim(0, 35)
panel(ax, "a", x=-0.62)
ax = axs[1]
order = ["E4", "E3", "E2", "E1"]
labels2 = {"E4": "Base-load\ncontrol", "E3": "Platen/barrel\ninsulation", "E2": "Servo\nmotors", "E1": "Compressed\nair"}
labels = {"E4": "Base-load control", "E3": "Platen/barrel insulation", "E2": "Servo motors", "E1": "Compressed air"}
x0 = 0
for m in order:
    w = M.loc[m, "saved_MWh"]; h = M.loc[m, "cce"]
    lo, hi = mc[f"cce_{m}"]["p5"], mc[f"cce_{m}"]["p95"]
    ax.bar(x0, h, width=w, align="edge", color=C_EE, edgecolor="white", lw=0.8)
    ax.errorbar(x0 + w / 2, h, yerr=[[h - lo], [hi - h]], color=OI["black"], lw=0.6, capsize=1.5)
    ax.text(x0 + w / 2, hi + 0.05, labels2[m], ha="center", va="bottom", fontsize=5.8, linespacing=0.95)
    x0 += w
mv = res["tariff"]["marginal_MXN_per_kWh"]; ec = res["tariff"]["energy"]
ax.axhline(mv, color=OI["verm"], lw=0.9); ax.text(1, mv + 0.05, "Avoided tariff (energy + energy-based demand charges)", fontsize=6, color=OI["verm"])
ax.axhline(ec, color=OI["verm"], lw=0.8, ls=":"); ax.text(x0 + 2.5, ec + 0.05, "Energy charge only", fontsize=6, color=OI["verm"], ha="right")
lc = M.loc["PV", "cce"]
ax.axhline(lc, color=C_PV, lw=0.9, ls="--"); ax.text(1, lc + 0.05, f"PV LCOE {lc:.2f}", fontsize=6, color="#8a5d00")
ax.set_xlim(0, x0 + 3); ax.set_ylim(0, 3.2)
ax.set_xlabel("Cumulative stand-alone savings (MWh yr$^{-1}$)"); ax.set_ylabel("Cost of conserved energy (MXN kWh$^{-1}$)")
panel(ax, "b", x=-0.12)
save(fig, "fig2_enduses_cce")

# ------------------------------------------------------------------ Fig 3 portfolios
PT = pd.read_csv(RES / "portfolios.csv").set_index("portfolio")
keys = ["P1 Efficiency bundle", "P2 PV only (163.8 kWp)", "P3 Efficiency + PV (163.8 kWp)", "P4 Efficiency first + right-sized PV"]
short = ["P1", "P2", "P3", "P4"]
cols = [C_EE, C_PV, OI["purple"], C_MIX]
lab = ["P1", "P2", "P3", "P4"]
fig, axs = plt.subplots(1, 4, figsize=(W2, 48 * MM), gridspec_kw=dict(wspace=0.55))
xs = np.arange(4)
ax = axs[0]
npv = [PT.loc[k, "npv"] / 1e6 for k in keys]
lo = [mc[f"npv_{l}"]["p5"] / 1e6 for l in lab]; hi = [mc[f"npv_{l}"]["p95"] / 1e6 for l in lab]
ax.bar(xs, npv, color=cols, width=0.65)
ax.errorbar(xs, npv, yerr=[np.array(npv) - lo, np.array(hi) - npv], fmt="none", color="k", lw=0.6, capsize=1.5)
cap = [PT.loc[k, "capex"] / 1e6 for k in keys]
ax.scatter(xs, cap, marker="_", s=60, color="k", lw=1.0, zorder=3, label="Capex")
ax.set_ylabel("NPV, 20 yr (MMXN)"); ax.legend(loc="upper left", handlelength=0.8)
ax.set_xticks(xs); ax.set_xticklabels(short); panel(ax, "a", x=-0.35)
ax = axs[1]
ax.bar(xs, [PT.loc[k, "grid_saved_frac"] * 100 for k in keys], color=cols, width=0.65)
ax.set_ylabel("Grid purchases avoided (%)"); ax.set_xticks(xs); ax.set_xticklabels(short); panel(ax, "b", x=-0.35)
ax = axs[2]
ax.bar(xs, [PT.loc[k, "billed_peak1_kW"] for k in keys], color=cols, width=0.65)
ax.axhline(100, color=OI["verm"], lw=0.8, ls="--"); ax.text(3.45, 171, "dashed: GDMTO limit, 100 kW", ha="right", va="top", fontsize=5.8, color=OI["verm"])
ax.axhline(PT.loc["P0 Baseline", "billed_peak1_kW"], color=OI["grey"], lw=0.8); ax.text(-0.4, PT.loc["P0 Baseline", "billed_peak1_kW"] + 3, "P0", fontsize=6, color="#666666")
ax.set_ylabel("Peak energy-implied demand (kW)"); ax.set_ylim(0, 175)
ax.set_xticks(xs); ax.set_xticklabels(short); panel(ax, "c", x=-0.35)
ax = axs[3]
ax.bar(xs, [PT.loc[k, "roof_m2"] for k in keys], color=cols, width=0.65)
ax.set_ylabel("Roof area for PV (m$^2$)"); ax.set_xticks(xs); ax.set_xticklabels(short); panel(ax, "d", x=-0.35)
save(fig, "fig3_portfolios")

# ------------------------------------------------------------------ Fig 4 pathways
PA = pd.read_csv(RES / "pathways.csv")
fig, axs = plt.subplots(1, 3, figsize=(W2, 50 * MM), gridspec_kw=dict(wspace=0.45))
t = PA.target * 100
ax = axs[0]
ax.plot(t, PA.supply_capex / 1e6, color=C_PV, label="Supply-only (PV)")
ax.plot(t, PA.ee_capex / 1e6, color=C_MIX, label="Efficiency first")
ax.set_xlabel("Target reduction of grid purchases (%)"); ax.set_ylabel("Investment (MMXN)")
ax.legend(loc="upper left"); panel(ax, "a", x=-0.25)
ax = axs[1]
ax.plot(t, PA.supply_kWp, color=C_PV); ax.plot(t, PA.ee_kWp, color=C_MIX)
ax.set_xlabel("Target reduction of grid purchases (%)"); ax.set_ylabel("PV capacity required (kWp)")
ax2y = PA.supply_kWp.max()
panel(ax, "b", x=-0.25)
ax = axs[2]
ax.plot(t, (PA.ee_npv - PA.supply_npv) / 1e6, "o-", ms=2, color=OI["black"])
ax.axhline(0, color=OI["grey"], lw=0.6)
ax.set_xlabel("Target reduction of grid purchases (%)"); ax.set_ylabel("NPV gain of efficiency first (MMXN)")
panel(ax, "c", x=-0.25)
save(fig, "fig4_pathways")

# ------------------------------------------------------------------ Fig 5 resilience & regulation
fig, axs = plt.subplots(1, 3, figsize=(W2, 50 * MM), gridspec_kw=dict(wspace=0.5))
ax = axs[0]
st = res["pv_stress"]
vals = [[PT.loc[keys[0], "npv"], st["npv_ee_no_demand_credit"]], [PT.loc[keys[1], "npv"], st["npv_pv_no_demand_credit"]]]
w = 0.35
ax.bar(np.arange(2) - w / 2, [v[0] / 1e6 for v in vals], width=w, color=[C_EE, C_PV], label="Net metering, Q-based demand")
ax.bar(np.arange(2) + w / 2, [v[1] / 1e6 for v in vals], width=w, color=[C_EE, C_PV], hatch="////", edgecolor="white",
       lw=0, label="No demand credit for PV")
ax.set_xticks([0, 1]); ax.set_xticklabels(["P1 EE", "P2 PV"]); ax.set_ylabel("NPV, 20 yr (MMXN)")
ax.legend(loc="lower left", bbox_to_anchor=(0, 1.02), fontsize=5.8); panel(ax, "a", x=-0.3, y=1.2)
ax = axs[1]
ex = [PT.loc["P0 Baseline", "shock_exposure1"]] + [PT.loc[k, "shock_exposure1"] for k in keys]
ax.bar(np.arange(5), np.array(ex) / 1e3, color=[C_BASE] + cols, width=0.65)
ax.set_xticks(np.arange(5)); ax.set_xticklabels(["P0"] + lab)
ax.set_ylabel("Bill increase if energy charge\nrises 50% (kMXN yr$^{-1}$)"); panel(ax, "b", x=-0.3, y=1.2)
ax = axs[2]
ax.bar(np.arange(4), [PT.loc[k, "imported_gas_avoided_GJ"] for k in keys], color=cols, width=0.65)
ax.set_xticks(np.arange(4)); ax.set_xticklabels(lab)
ax.set_ylabel("Imported gas avoided\nupstream (GJ yr$^{-1}$)"); panel(ax, "c", x=-0.3, y=1.2)
save(fig, "fig5_resilience")

# ------------------------------------------------------------------ Fig 6 thermal substitution
TH = pd.read_csv(RES / "thermal_unit_economics.csv")
fig, axs = plt.subplots(1, 2, figsize=(W2 * 0.75, 52 * MM), gridspec_kw=dict(wspace=0.9))
colmap = {"LPG boiler": OI["verm"], "Natural-gas boiler": OI["purple"], "Electric resistance": C_BASE,
          "Heat pump COP 2.5": OI["sky"], "Heat pump COP 3.0": OI["sky"], "Heat pump COP 4.0": OI["sky"],
          "Compressor heat recovery": C_EE}
for ax, col, xl, let in ((axs[0], "cost_MXN_per_GJ", "Cost of useful heat (MXN GJ$^{-1}$)", "a"),
                         (axs[1], "kgCO2_per_GJ", "Emissions (kgCO$_2$ GJ$^{-1}$ useful heat)", "b")):
    yy = np.arange(len(TH))[::-1]
    ax.barh(yy, TH[col], color=[colmap[o] for o in TH.option], height=0.65)
    ax.set_yticks(yy); ax.set_yticklabels(TH.option if let == "a" else [""] * len(TH))
    ax.set_xlabel(xl)
    for yi, v in zip(yy, TH[col]):
        ax.text(v + TH[col].max() * 0.02, yi, f"{v:.0f}", va="center", fontsize=6)
    ax.set_xlim(0, TH[col].max() * 1.2)
    panel(ax, let, x=-0.15 if let == "b" else -0.75)
save(fig, "fig6_thermal")

# ------------------------------------------------------------------ Fig 7 uncertainty
MCd = pd.read_csv(RES / "montecarlo.csv.gz")
fig, axs = plt.subplots(1, 2, figsize=(W2, 55 * MM), gridspec_kw=dict(width_ratios=[1, 1.1], wspace=0.75))
ax = axs[0]
bins = np.linspace(0, 6.5, 60)
for l, c, n in (("P1", C_EE, "P1 EE"), ("P2", C_PV, "P2 PV"), ("P4", C_MIX, "P4 EE-first")):
    ax.hist(MCd[f"npv_{l}"] / 1e6, bins=bins, histtype="step", color=c, lw=1.0, label=n)
ax.set_xlabel("NPV, 20 yr (MMXN)"); ax.set_ylabel(f"Count (n = {len(MCd):,})")
ax.legend(loc="upper right"); panel(ax, "a", x=-0.2)
ax = axs[1]
sp = pd.Series(mc["spearman_diff_P4_P2"]).sort_values(key=abs, ascending=True).tail(8)
NICE = {"base_saving_frac": "Base-load saving", "heat_saving_frac": "Insulation saving", "pv_cost_per_W": "PV cost per W", "pv_PR": "PV performance ratio", "ca_saving_frac": "Compressed-air saving", "sew_saving_frac": "Servo saving", "sew_cost_per_unit": "Servo unit cost", "sew_motor_share": "Motor share (stitching)", "heat_share": "Heater share", "discount_rate": "Discount rate", "sew_motor_kW": "Clutch-motor power", "tariff_real_escalation": "Tariff escalation", "pv_degradation": "PV degradation"}
nice = {k: NICE.get(k, k.replace("_", " ")) for k in sp.index}
ax.barh(np.arange(len(sp)), sp.values, color=[C_MIX if v > 0 else C_PV for v in sp.values], height=0.65)
ax.set_yticks(np.arange(len(sp))); ax.set_yticklabels([nice[k] for k in sp.index])
ax.axvline(0, color="k", lw=0.5)
ax.set_xlabel("Spearman correlation with NPV(P4) − NPV(P2)"); panel(ax, "b", x=-0.6)
save(fig, "fig7_uncertainty")

# ------------------------------------------------------------------ Graphical abstract (storyline, ~13:5)
from matplotlib.patches import FancyArrowPatch as _FA, FancyBboxPatch as _FB  # noqa: E402
nzj = json.load(open(RES / "netzero.json")); FR = pd.read_csv(RES / "netzero_frontier.csv")
p1, p2, p4 = (PT.loc[k] for k in (keys[0], keys[1], keys[3]))
INK, SUB = "#222222", "#555555"
fig = plt.figure(figsize=(W2, 88 * MM))
fig.text(0.5, 0.975, "Sizing rooftop PV and batteries after energy efficiency: an optimisation framework for manufacturing SMEs",
         ha="center", va="top", fontsize=9.5, fontweight="bold", color=INK)


def head(x, n, title, sub):
    fig.text(x, 0.885, f"{n}", fontsize=11, fontweight="bold", color=OI["green"], va="top")
    fig.text(x + 0.022, 0.885, title, fontsize=8.2, fontweight="bold", color=INK, va="top")
    fig.text(x + 0.022, 0.835, sub, fontsize=6.4, color=SUB, va="top")


def arrow(x0, x1, y=0.60):
    fig.add_artist(_FA((x0, y), (x1, y), transform=fig.transFigure, arrowstyle="-|>", mutation_scale=9,
                       lw=1.0, color="#9A9A9A"))


# 0 inputs
box = _FB((0.012, 0.36), 0.135, 0.45, boxstyle="round,pad=0.006,rounding_size=0.012", transform=fig.transFigure,
          fc="#F3F3F3", ec="none"); fig.add_artist(box)
fig.text(0.0795, 0.765, "Data a typical\nSME already has", ha="center", va="top", fontsize=7.2, fontweight="bold", color=INK)
for i, t in enumerate(["28 monthly bills", "Production records", "Walk-through audit", "Official tariffs,\nemission factor, fuels",
                       "NASA POWER weather"]):
    fig.text(0.026, 0.675 - i * 0.06, "\u2022 " + t, fontsize=6.2, color=INK, va="top", linespacing=1.0)
fig.text(0.0795, 0.375, f"Bills reproduced within {res['tariff_validation']['mape']*100:.1f}%", ha="center", fontsize=5.8, color=SUB)
arrow(0.152, 0.172)

# 1 cut waste: conservation supply curve
head(0.185, 1, "Cut waste", "Cost of saved electricity")
ax = fig.add_axes([0.228, 0.40, 0.185, 0.38])
x0 = 0
for m in order:
    w = M.loc[m, "saved_MWh"]; h = M.loc[m, "cce"]
    ax.bar(x0, h, width=w, align="edge", color=C_EE, edgecolor="white", lw=0.8)
    if h > 0.5:
        ax.text(x0 + w / 2, h - 0.08, m, ha="center", va="top", fontsize=6, color="white", fontweight="bold")
    else:
        ax.text(x0 + w / 2, h + 0.06, m, ha="center", fontsize=6, color=INK)
    x0 += w
ax.axhline(mv, color=OI["verm"], lw=1.0)
ax.text(x0, mv + 0.07, f"Avoided tariff {mv:.2f}", ha="right", color=OI["verm"], fontsize=6.2)
ax.axhline(lc, color=C_PV, lw=1.0, ls="--")
ax.text(1.5, lc + 0.07, f"Solar PV {lc:.2f}", ha="left", color="#8a5d00", fontsize=6.2)
ax.set_ylim(0, 3.0); ax.set_xlim(0, x0 * 1.02)
ax.set_xlabel("MWh saved per year", fontsize=6.5); ax.set_ylabel("MXN per kWh", fontsize=6.5)
ax.tick_params(labelsize=6)
fig.text(0.31, 0.27, f"\u2212{p1.grid_saved_frac*100:.0f}% grid electricity\nfor {p1.capex/1e6:.2f} M MXN",
         ha="center", va="top", fontsize=6.8, fontweight="bold", color=OI["green"], linespacing=1.1)
arrow(0.425, 0.447)

# 2 then size solar: capex split and roof
head(0.462, 2, "Then size solar", f"Same {p2.grid_saved_frac*100:.0f}% cut in grid purchases")
ax = fig.add_axes([0.527, 0.40, 0.165, 0.38])
pvc4 = p4.capex - p1.capex
ax.barh([1], [p2.capex / 1e6], color=C_PV, height=0.55)
ax.barh([0], [p1.capex / 1e6], color=C_EE, height=0.55)
ax.barh([0], [pvc4 / 1e6], left=[p1.capex / 1e6], color=C_PV, height=0.55)
ax.set_yticks([1, 0]); ax.set_yticklabels(["Solar\nonly", "Efficiency\nfirst"], fontsize=6.5)
ax.set_xlim(0, 2.6); ax.set_xlabel("Investment (M MXN)", fontsize=6.5); ax.tick_params(axis="x", labelsize=6)
ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
ax.text(p2.capex / 1e6 + 0.05, 1, f"{p2.pv_kWp:.0f} kWp\n{p2.roof_m2:.0f} m$^2$ roof", va="center", fontsize=6, color=INK)
ax.text(p4.capex / 1e6 + 0.05, 0, f"{p4.pv_kWp:.0f} kWp\n{p4.roof_m2:.0f} m$^2$ roof", va="center", fontsize=6, color=INK)
ax.text(p1.capex / 2e6, -0.45, "EE", ha="center", fontsize=5.5, color=OI["green"])
ax.text(p1.capex / 1e6 + pvc4 / 2e6, -0.45, "PV", ha="center", fontsize=5.5, color="#8a5d00")
ax.set_ylim(-0.7, 1.5)
fig.text(0.595, 0.27, f"\u2212{(1 - p4.capex / p2.capex)*100:.0f}% capital, \u2212{(1 - p4.roof_m2 / p2.roof_m2)*100:.0f}% roof,\n"
         f"higher NPV in {mc.get('prob_P4r_gt_P2', mc['prob_P4_gt_P2'])*100:.0f}% of runs", ha="center", va="top", fontsize=6.8, fontweight="bold", color=OI["blue"], linespacing=1.1)
arrow(0.712, 0.734)

# 3 deep decarbonisation: urbs cost-optimal frontier
head(0.747, 3, "Optimise deep cuts (urbs)", "Least-cost system under CO$_2$ caps")
ax = fig.add_axes([0.795, 0.40, 0.19, 0.38])
UR = pd.read_csv(RES / "urbs_results.csv"); UR = UR[np.isclose(UR.bat_cost_factor, 1.0)]
for ee, col, name in ((False, C_PV, "Supply only"), (True, C_EE, "Efficiency available")):
    u = UR[(UR.case == "co2-cap") & (UR.efficiency == ee)].sort_values("co2_cap_frac", ascending=False)
    ax.plot(u.co2_cap_frac * 100, u.total_cost / 1e6, "o-", color=col, ms=2.2, lw=1.3, label=name)
    b20 = u[np.isclose(u.co2_cap_frac, 0.20)].iloc[0]
    ax.annotate(f"{b20.bat_kWh_usable:.0f} kWh", xy=(20, b20.total_cost / 1e6), xytext=(23.5, b20.total_cost / 1e6 + (0.25 if not ee else -0.35)),
                fontsize=5.6, color=col, arrowprops=dict(arrowstyle="-", lw=0.4, color=col))
ax.axhline(UR.base_cost.iloc[0] / 1e6, color=SUB, lw=0.6, ls=":")
ax.text(36, UR.base_cost.iloc[0] / 1e6 + 0.04, "grid only", fontsize=5.6, color=SUB)
ax.set_xlim(37, 8); ax.set_xlabel("Grid CO$_2$ cap (% of baseline)", fontsize=6.5)
ax.set_ylabel("Annualised cost (M MXN)", fontsize=6.5); ax.tick_params(labelsize=6)
ax.legend(fontsize=5.6, loc="upper left", handlelength=1.2)
_c = UR[UR.case == "co2-cap"]
_sv = [1 - _c[(_c.efficiency) & np.isclose(_c.co2_cap_frac, k)].total_cost.iloc[0] / _c[(~_c.efficiency) & np.isclose(_c.co2_cap_frac, k)].total_cost.iloc[0]
       for k in sorted(_c.co2_cap_frac.unique())]
fig.text(0.885, 0.27, f"Efficiency enters first: \u2212{min(_sv)*100:.0f}\u2013{max(_sv)*100:.0f}% cost,\nabout half the storage",
         ha="center", va="top", fontsize=6.8, fontweight="bold", color=INK, linespacing=1.1)

# security strip
fig.add_artist(plt.Line2D([0.012, 0.988], [0.185, 0.185], transform=fig.transFigure, color="#DDDDDD", lw=0.6))
drop = (1 - res["pv_stress"]["npv_pv_no_demand_credit"] / p2.npv) * 100
chips = [f"Annual net-zero electricity pays: {nzj['scenarios']['NZ-E annual, efficiency first']['kWp']:.0f} kWp\nafter efficiency vs {nzj['scenarios']['NZ-S annual, supply only']['kWp']:.0f} kWp without",
         f"If PV loses demand credit: solar NPV \u2212{drop:.0f}%,\nefficiency unaffected",
         f"{p4.co2_saved_t:.0f} tCO$_2$ and {p4.imported_gas_avoided_GJ:.0f} GJ of imported\ngas avoided per year"]
fig.text(0.012, 0.095, "Net zero, security\nand resilience", fontsize=6.6, fontweight="bold", color=INK, va="center")
for i, t in enumerate(chips):
    fig.add_artist(_FB((0.135 + i * 0.29, 0.04), 0.275, 0.11, boxstyle="round,pad=0.004,rounding_size=0.015",
                       transform=fig.transFigure, fc="#EAF5F0", ec="none"))
    fig.text(0.135 + i * 0.29 + 0.1375, 0.095, t, ha="center", va="center", fontsize=6.3, color=INK, linespacing=1.15)
save(fig, "graphical_abstract")
print("figures written:", sorted(p.name for p in FIG.glob("*.pdf")))

# ------------------------------------------------------------------ Fig 8 net zero and storage
from efirst.hourly import evaluate_nz, hourly_pv_per_kWp, hourly_load, nz_central  # noqa: E402
from efirst.model import measure_savings  # noqa: E402
from efirst.params import central as _central  # noqa: E402
NZJ = json.load(open(RES / "netzero.json"))
FR = pd.read_csv(RES / "netzero_frontier.csv")
fig, axs = plt.subplots(1, 3, figsize=(W2, 55 * MM), gridspec_kw=dict(wspace=0.5, width_ratios=[1.15, 1, 1.1]))
ax = axs[0]
for lab, c, n in (("supply", C_PV, "Supply only"), ("eefirst", C_MIX, "Efficiency first")):
    f_ = FR[FR.set == lab]
    ax.step(f_.target * 100, f_.capex / 1e6, where="post", color=c, label=n)
for key, c in (("NZ-S annual, supply only", C_PV), ("NZ-E annual, efficiency first", C_MIX)):
    s_ = NZJ["scenarios"][key]
    ax.scatter([s_["self_sufficiency"] * 100], [s_["capex"] / 1e6], color=c, s=14, zorder=3, edgecolor="white", lw=0.5)
ax.annotate("Annual net zero\n(no storage)", xy=(55, 3.2), xytext=(60, 8.5), fontsize=6, arrowprops=dict(arrowstyle="-", lw=0.5))
ax.set_xlabel("Hourly self-sufficiency (%)"); ax.set_ylabel("Minimum investment (MMXN)")
ax.set_xlim(50, 97); ax.legend(loc="upper left"); panel(ax, "a", x=-0.22)
ax = axs[1]
keys_nz = ["NZ-S annual, supply only", "NZ-E annual, efficiency first", "SS80-eefirst", "SS90-eefirst"]
labs_nz = ["NZ-S", "NZ-E", "SS80", "SS90"]
xs_ = np.arange(4); w_ = 0.26
for j, (fld, hatch, nm) in enumerate((("npv", None, "Net metering"), ("npv_importdemand", "////", "No PV demand credit"),
                                      ("npv_netbilling", "....", "Net billing"))):
    vals = [NZJ["scenarios"][k][fld] / 1e6 for k in keys_nz]
    ax.bar(xs_ + (j - 1) * w_, vals, width=w_, color=[C_PV, C_MIX, C_MIX, C_MIX], hatch=hatch, edgecolor="white", lw=0,
           label=nm)
ax.axhline(0, color="k", lw=0.5)
ax.set_xticks(xs_); ax.set_xticklabels(labs_nz); ax.set_ylabel("NPV, 20 yr (MMXN)")
ax.legend(loc="lower left", bbox_to_anchor=(0, 1.02), fontsize=5.8, handlelength=1.2, ncol=1); panel(ax, "b", x=-0.25, y=1.25)
ax = axs[2]
P_ = _central(); NZc = nz_central(); W_ = hourly_pv_per_kWp(P_)
ref_ = D["ref"]
q_ee_, det_ = measure_savings(ref_, P_, D["intercept"], ["E4", "E1", "E2", "E3"])
s_ = NZJ["scenarios"]["NZ-E annual, efficiency first"]
pv_m = np.array([W_[W_.month == m].pv_kWh_per_kWp.sum() for m in ref_.mon]) * s_["kWp"] / 1000
xm = np.arange(12)
ax.bar(xm, q_ee_ / 1000, color=C_BASE, width=0.7, label="Consumption after efficiency")
ax.plot(xm, pv_m, "o-", color=C_PV, ms=2.2, label=f"PV {s_['kWp']:.0f} kWp")
ax.set_xticks(xm[::2]); ax.set_xticklabels([calendar.month_abbr[int(m)] for m in ref_.mon[::2]])
ax.set_ylabel("MWh per month"); ax.legend(loc="upper left", fontsize=5.8); ax.set_ylim(0, 75)
panel(ax, "c", x=-0.22)
save(fig, "fig8_netzero")
print("fig8 written")


# ------------------------------------------------------------------ Fig 0 study site and plant schematic
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle  # noqa: E402


def squarify(vals, x, y, w, h):
    """Squarified treemap (Bruls et al. 2000); vals sorted descending, sum normalised to the box area."""
    vals = list(np.asarray(vals, float) * w * h / np.sum(vals)); out = []
    while vals:
        short = min(w, h); row = [vals.pop(0)]
        def worst(r):
            s = sum(r); return max(max(short ** 2 * v / s ** 2, s ** 2 / (short ** 2 * v)) for v in r)
        while vals and worst(row + [vals[0]]) <= worst(row):
            row.append(vals.pop(0))
        s = sum(row)
        if w >= h:
            cw = s / h; yy = y
            for v in row:
                out.append((x, yy, cw, v / cw)); yy += v / cw
            x += cw; w -= cw
        else:
            rh = s / w; xx = x
            for v in row:
                out.append((xx, y, v / rh, rh)); xx += v / rh
            y += rh; h -= rh
    return out


geo = json.load(open(ROOT / "data/raw/naturalearth_admin1_mexico_region.geojson"))
fig = plt.figure(figsize=(0.62 * W2, 74 * MM))
ax = fig.add_axes([0.0, 0.02, 1.0, 0.96])
for f in geo["features"]:
    mex = f["properties"]["adm0"] == "MEX"; hid = f["properties"]["name"] == "Hidalgo"
    fc = OI["orange"] if hid else ("#ECECEC" if mex else "#F7F7F7")
    for poly in f["geometry"]["coordinates"]:
        ax.add_patch(Polygon(poly[0], closed=True, fc=fc, ec="#9A9A9A" if mex else "#D0D0D0", lw=0.25))
ax.plot(-98.76, 20.10, "o", ms=3.5, mfc=OI["black"], mec="white", mew=0.5, zorder=5)
ax.annotate("Pachuca de Soto, Hidalgo\n20.10°N, 98.76°W, 2,340 m", xy=(-98.76, 20.10), xytext=(-110.5, 17.0),
            fontsize=6, arrowprops=dict(arrowstyle="-", lw=0.4, color=OI["black"]))
ax.plot(-99.13, 19.43, "s", ms=2.2, color=OI["grey"], zorder=5)
ax.set_xlim(-118, -86); ax.set_ylim(14, 33); ax.set_aspect(1 / np.cos(np.radians(23)))
ax.set_xticks([]); ax.set_yticks([])
for s in ax.spines.values():
    s.set_visible(False)
ax.text(-117.5, 14.4, "Boundaries: Natural Earth", fontsize=5, color="#777777")
# regional inset: central Mexico
E0, E1, N0, N1 = -100.5, -97.4, 18.85, 21.55
ax.add_patch(Rectangle((E0, N0), E1 - E0, N1 - N0, fc="none", ec=OI["black"], lw=0.5, zorder=6))
axi = ax.inset_axes([0.60, 0.50, 0.42, 0.52])
for f in geo["features"]:
    if f["properties"]["adm0"] != "MEX":
        continue
    hid = f["properties"]["name"] == "Hidalgo"
    for poly in f["geometry"]["coordinates"]:
        axi.add_patch(Polygon(poly[0], closed=True, fc=OI["orange"] if hid else "#ECECEC", ec="#8A8A8A", lw=0.35))
for name, (lo, la) in {"Hidalgo": (-98.95, 20.75), "Querétaro": (-99.95, 21.2), "Estado de\nMéxico": (-99.95, 19.95),
                       "Veracruz": (-97.85, 21.38), "Tlaxcala": (-98.05, 19.62)}.items():
    axi.text(lo, la, name, fontsize=4.3, color="#555555", ha="center", va="center", style="italic")
axi.plot(-98.76, 20.10, "o", ms=3.2, mfc=OI["black"], mec="white", mew=0.5, zorder=5)
axi.text(-98.70, 20.13, "Pachuca", fontsize=5.2, fontweight="bold", va="bottom")
axi.plot(-99.13, 19.43, "s", ms=2.2, color="#555555", zorder=5)
axi.text(-99.13, 19.32, "Mexico City", fontsize=4.8, color="#333333", va="top", ha="center")
km = 50 / (111.32 * np.cos(np.radians(20)))       # 50 km in degrees of longitude
axi.plot([E0 + 0.15, E0 + 0.15 + km], [N0 + 0.15] * 2, color=OI["black"], lw=1.0)
axi.text(E0 + 0.15 + km / 2, N0 + 0.2, "50 km", fontsize=4.6, ha="center", va="bottom")
axi.set_xlim(E0, E1); axi.set_ylim(N0, N1); axi.set_aspect(1 / np.cos(np.radians(20)))
axi.set_xticks([]); axi.set_yticks([])
for sp in axi.spines.values():
    sp.set_visible(True); sp.set_linewidth(0.5)
ax.indicate_inset_zoom(axi, edgecolor="#777777", lw=0.4) if False else None

# the plant layout and energy-flow diagram is drawn in scripts/make_diagrams.py (fig_site_diagram)
save(fig, "fig0_site")


# ------------------------------------------------------------------ Framework figure (Processes version)
from matplotlib.patches import FancyBboxPatch as _Box  # noqa: E402
fig = plt.figure(figsize=(W2, 92 * MM)); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(0, 50); ax.axis("off")
cols = [("Inputs", 1.5, "#F0F0F0", ["Monthly bills (28)", "Production records (25)", "Audit end-use split", "Official tariffs, emission\nfactor, fuel prices", "NASA POWER climate\nand hourly weather"]),
        ("Simulation models", 26.5, "#E3F1EC", ["Tariff model, validated\nagainst 28 bills", "ISO 50006 baseline\n(base load)", "Measure models: savings\nwithout double counting", "Monthly PV (Klein)", "Hourly PV, synthetic load,\nbattery, credit bank"]),
        ("Optimisation and uncertainty", 51.5, "#E2EDF7", ["A: PV right-sizing by bisection\nB: merit-order pathways", "C: least-capital PV–battery\nsearch, 950 designs\n× 3 compensation regimes", "D: urbs energy-system LP,\njoint cost-optimal EE,\nPV and storage", "Monte Carlo (5,000 draws)\nand Spearman ranking", "One-way and regulatory\nstress tests"]),
        ("Common indicators", 76.5, "#FBEFD9", ["Energy and CO$_2$", "CCE, LCOE, NPV, payback", "Imported gas avoided", "Bill-shock exposure,\nbilled demand", "Roof area,\nself-sufficiency"])]
W, H = 22, 7.0
for title, x, fc, items in cols:
    ax.text(x + W / 2, 48.3, title, ha="center", va="center", fontsize=9, fontweight="bold", color="#222222")
    for i, t in enumerate(items):
        y = 41.5 - i * 8.6
        key = "urbs" in t
        ax.add_patch(_Box((x, y - H / 2), W, H, boxstyle="round,pad=0.2,rounding_size=0.8", fc="#BFD7EE" if key else fc,
                          ec=OI["blue"] if key else "none", lw=1.3))
        ax.text(x + W / 2, y, t, ha="center", va="center", fontsize=8, color="#222222", linespacing=1.1,
                fontweight="bold" if key else "normal")
for x in (24.0, 49.0, 74.0):
    ax.annotate("", xy=(x + 2.2, 24.3), xytext=(x, 24.3), arrowprops=dict(arrowstyle="-|>", lw=1.0, color="#888888"))
ax.text(64.0, 1.2, "EnergyPlus 25.1 verifies hourly PV yield and battery dispatch", ha="center", fontsize=7, color="#555555", style="italic")
save(fig, "fig_framework")
