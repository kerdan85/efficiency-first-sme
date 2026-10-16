"""Figure, table and LaTeX number macros for the urbs linear-programming benchmark (results/urbs_results.csv)."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
R = pd.read_csv(ROOT / "results/urbs_results.csv")
meta = json.load(open(ROOT / "urbs/plant_urbs_meta.json"))
MM = 1 / 25.4
OI = dict(black="#000000", orange="#E69F00", green="#009E73", blue="#0072B2", verm="#D55E00", grey="#999999",
          purple="#CC79A7", sky="#56B4E9")
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
                     "font.size": 7, "axes.linewidth": 0.5, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
                     "xtick.major.size": 2.5, "ytick.major.size": 2.5, "axes.spines.top": False,
                     "axes.spines.right": False, "legend.frameon": False, "pdf.fonttype": 42, "savefig.dpi": 600})


def row(case, regime, ee, cap=None, bcf=1.0):
    s = R[(R.case == case) & (R.regime == regime) & (R.efficiency == ee) & np.isclose(R.bat_cost_factor, bcf)]
    s = s[np.isclose(s.co2_cap_frac, cap)] if cap is not None else s[s.co2_cap_frac.isna()]
    assert len(s) == 1, (case, regime, ee, cap, bcf, len(s))
    return s.iloc[0]


base = meta["load_MWh"] * 1000 * meta["marginal_value"]
co2_0 = meta["co2_baseline_t"]
nmE, nmS = row("cost-optimal", "net_metering", True), row("cost-optimal", "net_metering", False)
scE, scS = row("cost-optimal", "self_consumption", True), row("cost-optimal", "self_consumption", False)
nbE, nbS = row("cost-optimal", "net_billing", True), row("cost-optimal", "net_billing", False)
rlE, rlS = row("roof-limited", "net_metering", True), row("roof-limited", "net_metering", False)
caps = sorted(R[R.case == "co2-cap"].co2_cap_frac.unique(), reverse=True)

# ---------------------------------------------------------------- figure: cost-optimal decarbonisation frontier
from matplotlib.lines import Line2D  # noqa: E402
CE, CS = OI["green"], OI["orange"]
fig, axs = plt.subplots(2, 2, figsize=(183 * MM, 112 * MM), gridspec_kw=dict(wspace=0.30, hspace=0.50))
front = {}
for ee in (True, False):
    pts = [(row("cost-optimal", "net_metering", ee).co2_t / co2_0, row("cost-optimal", "net_metering", ee))]
    pts += [(c, row("co2-cap", "net_metering", ee, c)) for c in caps]
    front[ee] = pts
for ee, col, lab in ((True, CE, "Efficiency available"), (False, CS, "Supply only")):
    pts = front[ee]; x = np.array([p[0] for p in pts]) * 100
    axs[0, 0].plot(x, [p[1].total_cost / 1e6 for p in pts], "o-", color=col, ms=2.5, lw=1, label=lab)
    axs[0, 1].plot(x, [p[1].pv_kWp for p in pts], "o-", color=col, ms=2.5, lw=1)
    axs[0, 1].plot(x, [p[1].bat_kWh_usable for p in pts], "s--", color=col, ms=2.5, lw=1)
axs[0, 0].axhline(base / 1e6, color=OI["grey"], lw=0.6, ls=":")
axs[0, 0].text(44, base / 1e6 + 0.02, "all electricity from grid", ha="left", va="bottom", fontsize=6, color="#555555")
axs[0, 0].set_ylabel("Annualised cost (M MXN yr$^{-1}$)")
axs[0, 1].set_ylabel("Capacity (kWp PV; kWh battery)")
axs[0, 0].legend(loc="upper left", bbox_to_anchor=(0, 0.86))
axs[0, 1].legend([Line2D([], [], color="k", marker="o", ms=2.5, lw=1), Line2D([], [], color="k", marker="s", ms=2.5, lw=1, ls="--")],
                 ["PV", "Battery (usable)"], loc="upper left")
# (c) adoption of each measure along the frontier
x = np.array([p[0] for p in front[True]]) * 100
mcol = {"E4": OI["green"], "E3": OI["verm"], "E2": OI["blue"], "E1": OI["black"]}
mlab = {"E4": "E4 base-load control", "E3": "E3 insulation", "E2": "E2 servo motors", "E1": "E1 compressed air"}
for k, (m, c) in enumerate(mcol.items()):
    axs[1, 0].plot(x, [p[1][f"adopt_{m}"] * 100 + (k - 1.5) * 1.6 for p in front[True]], "o-", color=c, ms=2.2, lw=0.9, label=mlab[m])
axs[1, 0].set_ylabel("Adoption (% of full measure)"); axs[1, 0].set_ylim(-8, 112)
axs[1, 0].legend(loc="center right", fontsize=6)
for ax in (axs[0, 0], axs[0, 1], axs[1, 0]):
    ax.set_xlabel("Gross grid CO$_2$ (% of baseline)"); ax.set_xlim(45, 5)
# (d) annualised cost by component
sel = [("No cap", None), ("30%", 0.30), ("20%", 0.20), ("10%", 0.10)]
comp = [("acost_grid", "Net grid purchases", OI["grey"]), ("acost_ee", "Efficiency", CE), ("acost_pv", "PV", CS),
        ("acost_bat", "Battery", OI["blue"])]
ax = axs[1, 1]; xt, xl = [], []
for i, (name, cap) in enumerate(sel):
    for j, ee in enumerate((False, True)):
        r = row("cost-optimal", "net_metering", ee) if cap is None else row("co2-cap", "net_metering", ee, cap)
        xx = i * 2.6 + j * 1.0; bottom = 0.0
        for key, lab, c in comp:
            v = max(r[key], 0.0) / 1e6
            ax.bar(xx, v, bottom=bottom, width=0.85, color=c, label=lab if (i == 0 and j == 0) else None,
                   hatch="" if ee else "////", edgecolor="white", lw=0.3)
            bottom += v
        xt.append(xx); xl.append("E" if ee else "S")
    ax.annotate(name, xy=(i * 2.6 + 0.5, -0.11), xycoords=("data", "axes fraction"), ha="center", va="top", fontsize=6.5)
ax.set_xticks(xt); ax.set_xticklabels(xl, fontsize=6)
ax.set_ylabel("Annualised cost (M MXN yr$^{-1}$)"); ax.set_ylim(0, None)
ax.legend(loc="upper left", fontsize=6, ncol=1)
ax.text(0.5, -0.24, "CO$_2$ cap (S supply only, E efficiency available)", transform=ax.transAxes, ha="center", va="top", fontsize=7)
for ax, l in zip(axs.flat, "abcd"):
    ax.text(-0.16, 1.04, l, transform=ax.transAxes, fontsize=8, fontweight="bold")
fig.savefig(ROOT / "figures/fig9_urbs.pdf", bbox_inches="tight"); fig.savefig(ROOT / "figures/fig9_urbs.png", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- figure: hourly operation at a 20% emission cap
DISP = ROOT / "urbs" / "urbs_dispatch.csv.gz"
disp_stats = {}
if DISP.exists():
    Dd = pd.read_csv(DISP)
    weeks = [("Dry season (3--9 April)", 2209), ("Shift month (4--10 December)", 8089)]
    fig, axs = plt.subplots(2, 2, figsize=(183 * MM, 92 * MM), sharey=True,
                            gridspec_kw=dict(wspace=0.08, hspace=0.42))
    for col, ee in enumerate((False, True)):
        d = Dd[Dd.efficiency_allowed == ee].set_index("t")
        for rr, (wname, t0) in enumerate(weeks):
            ax = axs[rr, col]
            w = d.loc[t0:t0 + 167]
            h = np.arange(len(w))
            pv_used = w.pv
            pos = [("efficiency", "Efficiency (negawatts)", CE), ("pv", "PV", CS), ("bat_out", "Battery discharge", OI["blue"]),
                   ("grid", "Grid import", OI["grey"])]
            neg = [("export", "Export", OI["purple"]), ("bat_in", "Battery charge", OI["sky"]), ("curtailed", "Curtailed", "#DDDDDD")]
            ax.stackplot(h, *[w[k] for k, _, _ in pos], colors=[c for _, _, c in pos], labels=[lab for _, lab, _ in pos], lw=0)
            ax.stackplot(h, *[-w[k] for k, _, _ in neg], colors=[c for _, _, c in neg], labels=[lab for _, lab, _ in neg], lw=0)
            ax.plot(h, w.demand, color="k", lw=0.7, label="Plant demand before efficiency")
            ax.axhline(0, color="k", lw=0.4)
            ax.set_xticks(range(0, 169, 24)); ax.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun", ""], fontsize=6)
            ax.set_xlim(0, 168)
            ax.set_title(f"{'Efficiency available' if ee else 'Supply only'}: {wname.replace('--', '–')}", fontsize=6.8, loc="left")
            if col == 0:
                ax.set_ylabel("Power (kW)")
    axs[0, 0].legend(loc="upper center", bbox_to_anchor=(1.04, 1.42), ncol=4, fontsize=6)
    for ax, l in zip(axs.flat, "abcd"):
        ax.text(-0.10 if l in "ac" else -0.04, 1.06, l, transform=ax.transAxes, fontsize=8, fontweight="bold")
    fig.savefig(ROOT / "figures/fig10_urbs_dispatch.pdf", bbox_inches="tight")
    fig.savefig(ROOT / "figures/fig10_urbs_dispatch.png", bbox_inches="tight")
    plt.close(fig)
    for ee in (True, False):
        d = Dd[Dd.efficiency_allowed == ee]
        r = row("co2-cap", "net_metering", ee, 0.20)
        disp_stats[ee] = dict(cycles=d.bat_out.sum() / max(r.bat_kWh_usable, 1e-9), curt_share=d.curtailed.sum() / d.pv.sum(),
                              night_share=d.bat_out[(d.pv < 1e-6)].sum() / max(d.bat_out.sum(), 1e-9))
    json.dump({str(k): v for k, v in disp_stats.items()}, open(ROOT / "results/urbs_dispatch_summary.json", "w"), indent=1)
else:
    disp_stats = {str(k): v for k, v in json.load(open(ROOT / "results/urbs_dispatch_summary.json")).items()}
    disp_stats = {k == "True": v for k, v in disp_stats.items()}

# ---------------------------------------------------------------- table: cost-optimal designs
lab = {"net_metering": "Net metering", "net_billing": "Net billing (1.0 MXN kWh$^{-1}$)", "self_consumption": "Self-consumption only"}
lines = []
blocks = (("cost-optimal", "net_metering", lab["net_metering"]), ("cost-optimal", "net_billing", lab["net_billing"]),
          ("cost-optimal", "self_consumption", lab["self_consumption"]),
          ("roof-limited", "net_metering", "Net metering, PV $\\le$ 163.8 kWp"))
for i, (case, regime, name) in enumerate(blocks):
    for ee in (True, False):
        r = row(case, regime, ee)
        full = [m for m in ("E1", "E2", "E3", "E4") if r[f"adopt_{m}"] > 0.99]
        part = [m for m in ("E1", "E2", "E3", "E4") if 0.01 < r[f"adopt_{m}"] <= 0.99]
        if not ee:
            ad = "--"
        else:
            ad = "E1--E4" if len(full) == 4 else ", ".join(full)
            if part:
                ad += ", " + ", ".join(f"{m} ({r[f'adopt_{m}']*100:.0f}\\%)" for m in part)
        bat = abs(round(max(r.bat_kWh_usable, 0.0)))
        cost = f"{r.total_cost/1e3:,.0f}".replace(",", "{,}")
        lines.append(f"{name if ee else ''} & {'with' if ee else 'without'} & {ad} & {r.pv_kWp:.0f} & {bat:.0f} & "
                     f"{r.import_MWh:.0f} & {r.co2_t:.0f} & {cost} \\\\")
    if i < len(blocks) - 1:
        lines.append("\\midrule")
tab = r"""\begin{table}[H]
\caption{Cost-optimal designs from urbs without an emission cap (grid only: %s~kMXN~yr$^{-1}$).}
\label{tab:urbs}
\footnotesize
\resizebox{\linewidth}{!}{%%
\begin{tabular}{llrrrrrr}
\toprule
Compensation regime & Efficiency & Measures adopted & PV (kWp) & Battery (usable kWh) & Grid imports (MWh) & CO$_2$ (t) & Cost (kMXN yr$^{-1}$) \\
\midrule
%s
\bottomrule
\end{tabular}}
\end{table}
""" % (f"{base/1e3:,.0f}".replace(",", "{,}"), "\n".join(lines))
(ROOT / "manuscript_processes" / "tables").mkdir(parents=True, exist_ok=True)
(ROOT / "manuscript/tables/urbs.tex").write_text(tab)

# ---------------------------------------------------------------- table: battery-cost sensitivity
bl = []
for f in (1.0, 0.75, 0.50, 0.25):
    cells = []
    for cap in (None, 0.20):
        for ee in (False, True):
            case = ("cost-optimal" if cap is None else "co2-cap") if f == 1.0 else "battery-cost"
            rr = row(case, "net_metering", ee, cap, f)
            cells += [f"{abs(round(max(rr.bat_kWh_usable, 0))):.0f}", f"{rr.pv_kWp:.0f}", f"{rr.total_cost/1e3:,.0f}".replace(",", "{,}")]
    bl.append(f"{f*100:.0f}\\% & " + " & ".join(cells) + " \\\\")
tabb = r"""\begin{table}[H]
\caption{Effect of battery cost on the urbs optimum under net metering (battery in usable kWh).}
\label{tab:urbsbat}
\footnotesize
\resizebox{\linewidth}{!}{%%
\begin{tabular}{lrrrrrrrrrrrr}
\toprule
 & \multicolumn{6}{c}{No emission cap} & \multicolumn{6}{c}{CO$_2$ cap 20\%% of baseline} \\
\cmidrule(lr){2-7}\cmidrule(lr){8-13}
 & \multicolumn{3}{c}{Supply only} & \multicolumn{3}{c}{Efficiency available} & \multicolumn{3}{c}{Supply only} & \multicolumn{3}{c}{Efficiency available} \\
Battery cost & kWh & kWp & kMXN & kWh & kWp & kMXN & kWh & kWp & kMXN & kWh & kWp & kMXN \\
\midrule
%s
\bottomrule
\end{tabular}}
\end{table}
""" % "\n".join(bl)
(ROOT / "manuscript/tables/urbs_battery.tex").write_text(tabb)

# ---------------------------------------------------------------- number macros
pct = lambda x: f"{x*100:.0f}"
c35E, c35S = row("co2-cap", "net_metering", True, 0.35), row("co2-cap", "net_metering", False, 0.35)
c20E, c20S = row("co2-cap", "net_metering", True, 0.20), row("co2-cap", "net_metering", False, 0.20)
c10E, c10S = row("co2-cap", "net_metering", True, 0.10), row("co2-cap", "net_metering", False, 0.10)
cap_saves = [1 - row("co2-cap", "net_metering", True, c).total_cost / row("co2-cap", "net_metering", False, c).total_cost for c in caps]
first_bat_E = max(c for c in caps if row("co2-cap", "net_metering", True, c).bat_kWh_usable > 1)
first_bat_S = max(c for c in caps if row("co2-cap", "net_metering", False, c).bat_kWh_usable > 1)
N = dict(
    UPVNME=f"{nmE.pv_kWp:.0f}", UPVNMS=f"{nmS.pv_kWp:.0f}", UCostNMSave=pct(1 - nmE.total_cost / nmS.total_cost),
    UEENMMWh=f"{nmE.ee_MWh:.0f}", UCOONME=pct(nmE.co2_t / co2_0), UCOONMS=pct(nmS.co2_t / co2_0),
    USSNMS=pct(nmS.self_sufficiency),
    UPVSCE=f"{scE.pv_kWp:.0f}", UPVSCS=f"{scS.pv_kWp:.0f}", UCostSCSave=pct(1 - scE.total_cost / scS.total_cost),
    UCostNBSave=pct(1 - nbE.total_cost / nbS.total_cost), UCostRLSave=pct(1 - rlE.total_cost / rlS.total_cost),
    UCapSaveMin=pct(min(cap_saves)), UCapSaveMax=pct(max(cap_saves)),
    UFirstBatE=pct(first_bat_E), UFirstBatS=pct(first_bat_S),
    UBatTwentyE=f"{c20E.bat_kWh_usable:.0f}", UBatTwentyS=f"{c20S.bat_kWh_usable:.0f}",
    UPVTwentyE=f"{c20E.pv_kWp:.0f}", UPVTwentyS=f"{c20S.pv_kWp:.0f}",
    UBatTenE=f"{c10E.bat_kWh_usable:.0f}", UBatTenS=f"{c10S.bat_kWh_usable:.0f}",
    UPVTenE=f"{c10E.pv_kWp:.0f}", UPVTenS=f"{c10S.pv_kWp:.0f}",
    UCostTenE=f"{c10E.total_cost/1e6:.2f}", UCostTenS=f"{c10S.total_cost/1e6:.2f}",
    UEtwoAdoptThirtyFive=pct(c35E.adopt_E2), USolveMean=f"{R.solve_s.mean():.0f}", UNRuns=f"{len(R)}",
    UGridCost=f"{base/1e3:,.0f}".replace(",", "{,}"),
)
c30E, c30S = row("co2-cap", "net_metering", True, 0.30), row("co2-cap", "net_metering", False, 0.30)
share = lambda r_, k: r_[k] / r_.total_cost
bat_unc = [f for f in (0.75, 0.50, 0.25) if row("battery-cost", "net_metering", True, None, f).bat_kWh_usable > 1]
b25E, b25S = row("battery-cost", "net_metering", True, 0.20, 0.25), row("battery-cost", "net_metering", False, 0.20, 0.25)
b50E, b50S = row("battery-cost", "net_metering", True, 0.20, 0.50), row("battery-cost", "net_metering", False, 0.20, 0.50)
N.update(
    UBatShareTenE=pct(share(c10E, "acost_bat")), UBatShareTenS=pct(share(c10S, "acost_bat")),
    UEEShareTenE=pct(share(c10E, "acost_ee")), UPVShareTenE=pct(share(c10E, "acost_pv")),
    UCostTwentyE=f"{c20E.total_cost/1e3:,.0f}".replace(",", "{,}"), UCostTwentyS=f"{c20S.total_cost/1e3:,.0f}".replace(",", "{,}"),
    UCostThirtyE=f"{c30E.total_cost/1e3:,.0f}".replace(",", "{,}"), UCostThirtyS=f"{c30S.total_cost/1e3:,.0f}".replace(",", "{,}"),
    UCostNME=f"{nmE.total_cost/1e3:,.0f}".replace(",", "{,}"), UCostNMS=f"{nmS.total_cost/1e3:,.0f}".replace(",", "{,}"),
    UCurtTwentyE=pct(c20E.curtailed_MWh / c20E.pv_MWh), UCurtTwentyS=pct(c20S.curtailed_MWh / c20S.pv_MWh),
    UCurtTenE=pct(c10E.curtailed_MWh / c10E.pv_MWh), UCurtTenS=pct(c10S.curtailed_MWh / c10S.pv_MWh),
    UCyclesTwentyE=f"{disp_stats[True]['cycles']:.0f}", UCyclesTwentyS=f"{disp_stats[False]['cycles']:.0f}",
    UBatNightTwentyE=pct(disp_stats[True]["night_share"]),
    UBatUncon="none" if not bat_unc else f"{(1-max(bat_unc))*100:.0f}",
    UBatTwentyQuarterE=f"{b25E.bat_kWh_usable:.0f}", UBatTwentyQuarterS=f"{b25S.bat_kWh_usable:.0f}",
    UCostTwentyQuarterSave=pct(1 - b25E.total_cost / b25S.total_cost),
    UBatTwentyHalfE=f"{b50E.bat_kWh_usable:.0f}", UBatTwentyHalfS=f"{b50S.bat_kWh_usable:.0f}",
    UImpTwentyE=f"{c20E.import_MWh:.0f}", USSTwentyE=pct(c20E.self_sufficiency), USSTwentyS=pct(c20S.self_sufficiency),
    USSTenE=pct(c10E.self_sufficiency),
    UNRunsMain=f"{(R.bat_cost_factor == 1.0).sum()}", UNRunsBat=f"{(R.bat_cost_factor != 1.0).sum()}",
)
(ROOT / "manuscript/numbers_urbs.tex").write_text("".join(f"\\newcommand{{\\n{k}}}{{{v}}}\n" for k, v in N.items()))
json.dump(N, open(ROOT / "results/urbs_numbers.json", "w"), indent=1)
print(json.dumps(N, indent=1))
print(tab)
