"""Schematic diagrams that need no confidential data: plant layout/energy-flow diagram and urbs model structure.

Area shares are the aggregated values reported in the paper (audit reference month); PV sizes and roof areas come
from results/results.json.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
OI = dict(black="#000000", orange="#E69F00", sky="#56B4E9", green="#009E73", yellow="#F0E442",
          blue="#0072B2", verm="#D55E00", purple="#CC79A7", grey="#999999")
MM = 1 / 25.4
W2 = 183 * MM
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
                     "font.size": 7, "pdf.fonttype": 42, "savefig.dpi": 600})
res = json.load(open(ROOT / "results" / "results.json"))
um = json.load(open(ROOT / "urbs" / "plant_urbs_meta.json"))


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight")
    plt.close(fig)


def box(ax, x, y, w, h, text, fc="white", ec="#444444", fs=6.2, lw=0.6, ls="-", bold=False, color="#111111", r=0.6,
        alpha=1.0, ha="center"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw, ls=ls,
                                alpha=alpha))
    tx = x + w / 2 if ha == "center" else x + 0.8
    ax.text(tx, y + h / 2, text, ha=ha, va="center", fontsize=fs, color=color, linespacing=1.15,
            fontweight="bold" if bold else "normal")


def arrow(ax, a, b, color="#444444", lw=0.7, style="-|>", ls="-", ms=6, cs="arc3"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=ms, lw=lw, color=color, ls=ls,
                                 connectionstyle=cs, shrinkA=0, shrinkB=0))


# =================================================================== plant site diagram
# aggregated electricity shares of the audited reference month (April 2026), as reported in the paper
SH = dict(cut=5.7, stitch=19.8, last=15.3, vulc=29.2, inj=9.1, fin=4.1, air=16.8)
fig = plt.figure(figsize=(W2, 88 * MM))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(0, 48); ax.axis("off")

# building envelope (audit scope) and shared-meter areas
ax.add_patch(Rectangle((22.5, 5.0), 64.5, 33.5, fc="#FAFAFA", ec=OI["black"], lw=0.9))
ax.text(23.3, 37.6, "Production hall (audit scope) — base-load control E4 acts on all areas", fontsize=6.2, va="top",
        fontweight="bold")
box(ax, 88.5, 21.0, 10.5, 13.0, "Offices and\nwarehouse\n(shared meter,\nnot audited)", fc="white", ec="#888888",
    ls="--", fs=5.6, color="#555555")
# roof PV band
r2 = res["portfolios"]["P2 PV only (163.8 kWp)"]["roof_m2"]; r4 = res["portfolios"]["P4 Efficiency first + right-sized PV"]["roof_m2"]
RX, RW = 22.5, 64.5
ax.add_patch(Rectangle((RX, 40.0), RW, 4.2, fc="none", ec=OI["orange"], lw=0.7, hatch="////"))
ax.add_patch(Rectangle((RX, 40.0), RW * r4 / r2, 4.2, fc=OI["orange"], alpha=0.5, ec=OI["orange"], lw=0.7))
ax.text(RX + RW * r4 / r2 / 2, 42.1, f"PV after efficiency (P4): {res['p4_kWp']:.0f} kWp, {r4:.0f} m$^2$",
        ha="center", va="center", fontsize=5.8)
ax.text(RX + RW * (1 + r4 / r2) / 2, 42.1, f"PV only (P2): 163.8 kWp, {r2:.0f} m$^2$", ha="center", va="center",
        fontsize=5.8, bbox=dict(fc="white", ec="none", pad=0.5))
ax.text(RX, 45.0, "Proposed rooftop PV (roof area to scale between options)", fontsize=6.0, color="#8A5A00", va="bottom")

# process chain
C3, C2, C1 = "#F6D3BF", "#CDE8F6", "#C9DDEE"     # tints of the measure colours
y0, h = 21.0, 11.5
steps = [("Cutting", "cutting presses", SH["cut"], None, "white"),
         ("Stitching", "sewing machines\n(clutch motors)", SH["stitch"], "E2 servo motors", C2),
         ("Lasting and\nassembly", "lasting machines,\nheat setting", SH["last"], None, "white")]
x = 24.0; w = 10.5; xs = []
for name, sub, sh, meas, fc in steps:
    box(ax, x, y0, w, h, "", fc=fc, ec="#444444")
    ax.text(x + w / 2, y0 + h - 1.3, name, ha="center", va="top", fontsize=6.4, fontweight="bold", linespacing=1.05)
    ax.text(x + w / 2, y0 + 4.6, sub, ha="center", va="center", fontsize=5.4, color="#333333", linespacing=1.05)
    ax.text(x + w / 2, y0 + 1.4, f"{sh:.1f}%", ha="center", va="center", fontsize=6.4, fontweight="bold", color="#222222")
    if meas:
        ax.text(x + w / 2, y0 - 1.3, meas, ha="center", va="top", fontsize=5.5, color=OI["blue"], fontweight="bold")
    xs.append(x); x += w + 2.2
# sole attachment: two parallel routes
sx = x
for (name, sub, sh), yy in zip([("Vulcanising", "heated presses\nand platens", SH["vulc"]),
                                ("Sole injection", "heated barrels,\nhydraulics", SH["inj"])], (y0 + 6.2, y0 - 3.2)):
    box(ax, sx, yy, 12.0, 8.4 if name == "Vulcanising" else 7.6, "", fc=C3, ec="#444444")
    ax.text(sx + 6.0, yy + (8.4 if name == "Vulcanising" else 7.6) - 1.0, f"{name}  {sh:.1f}%", ha="center", va="top",
            fontsize=6.1, fontweight="bold")
    ax.text(sx + 6.0, yy + 2.6, sub, ha="center", va="center", fontsize=5.4, color="#333333", linespacing=1.05)
ax.text(sx + 4.6, y0 - 4.3, "E3 insulation and\ntemperature control", ha="center", va="top", fontsize=5.5, color=OI["verm"],
        fontweight="bold")
fx = sx + 12.0 + 2.2
box(ax, fx, y0, 8.5, h, "", fc="white", ec="#444444")
ax.text(fx + 4.25, y0 + h - 1.3, "Finishing\nand stores", ha="center", va="top", fontsize=6.2, fontweight="bold", linespacing=1.05)
ax.text(fx + 4.25, y0 + 4.6, "trims, racks,\noven", ha="center", va="center", fontsize=5.4, color="#333333", linespacing=1.05)
ax.text(fx + 4.25, y0 + 1.4, f"{SH['fin']:.1f}%", ha="center", va="center", fontsize=6.4, fontweight="bold")
# material flow arrows
for a in xs:
    if a != xs[-1]:
        arrow(ax, (a + w, y0 + h / 2), (a + w + 2.2, y0 + h / 2), color=OI["black"], lw=0.9)
arrow(ax, (xs[-1] + w, y0 + h / 2), (sx, y0 + 10.0), color=OI["black"], lw=0.9)
arrow(ax, (xs[-1] + w, y0 + h / 2), (sx, y0 + 0.6), color=OI["black"], lw=0.9)
arrow(ax, (sx + 12.0, y0 + 10.0), (fx, y0 + h / 2 + 1.0), color=OI["black"], lw=0.9)
arrow(ax, (sx + 12.0, y0 + 0.6), (fx, y0 + h / 2 - 1.0), color=OI["black"], lw=0.9)
arrow(ax, (fx + 8.5, y0 + h / 2), (88.5, y0 + h / 2), color=OI["black"], lw=0.9)

# compressed-air room and network
box(ax, 24.0, 6.3, 18.0, 8.2, "", fc=C1, ec="#444444")
ax.text(33.0, 13.4, f"Compressed-air room  {SH['air']:.1f}%", ha="center", va="top", fontsize=6.1, fontweight="bold")
ax.text(33.0, 9.6, "two compressors\nE1 leaks, pressure, no-load control", ha="center", va="center", fontsize=5.4,
        color="#333333", linespacing=1.1)
ax.plot([42.0, fx + 4.25], [10.4, 10.4], color=OI["blue"], lw=1.1, ls=(0, (3, 1.5)))
for xx in (xs[2] + w / 2, sx + 10.0, fx + 4.25):
    ax.plot([xx, xx], [10.4, y0 - 3.2 if xx == sx + 10.0 else y0], color=OI["blue"], lw=0.8, ls=(0, (3, 1.5)))
ax.text(58.0, 10.9, "compressed-air network", fontsize=5.2, color=OI["blue"], va="bottom", ha="center", style="italic")

# electricity supply
box(ax, 1.0, 26.0, 10.5, 7.0, "CFE grid\nmedium voltage", fc="white", fs=6.0)
box(ax, 1.0, 15.5, 10.5, 7.5, "Meter and\ntransformer\nGDMTO tariff", fc="white", fs=5.8)
box(ax, 13.0, 15.5, 7.5, 7.5, "Main\nswitch-\nboard", fc="white", fs=5.8)
box(ax, 1.0, 5.6, 10.5, 6.6, "Capacitor bank\nE5 (PF)", fc="#CFE9DF", fs=5.8)
arrow(ax, (6.25, 26.0), (6.25, 23.0), lw=0.9)
arrow(ax, (11.5, 19.25), (13.0, 19.25), lw=0.9)
ax.plot([6.25, 6.25], [12.2, 15.5], color="#444444", lw=0.6)
arrow(ax, (20.5, 19.25), (24.0, 19.25), lw=0.9, color=OI["verm"])
arrow(ax, (16.75, 15.5), (16.75, 10.4), lw=0.9, color=OI["verm"], cs="arc3")
arrow(ax, (16.75, 10.4), (24.0, 10.4), lw=0.9, color=OI["verm"])
arrow(ax, (RX + 2, 40.0), (17.8, 23.0), lw=0.7, color=OI["orange"], ls=(0, (3, 1.5)), cs="arc3,rad=0.25")
# legend
ax.text(1.0, 1.0, "Schematic, not to scale. Percentages: share of plant electricity in the audited reference month. "
        "Material flow (black), electricity (red), compressed air (blue).", fontsize=5.4, color="#555555")
save(fig, "fig_site_diagram")


# =================================================================== urbs model structure
fig = plt.figure(figsize=(W2, 92 * MM))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(-1.5, 50); ax.axis("off")
for x, t in ((10, "Input commodities\n(prices, hourly profiles)"), (34, "Processes and storage\n(capacity = decision variable)"),
             (55.5, "Electricity bus"), (70.5, "Sinks"), (90, "Objective and constraints")):
    ax.text(x, 48.6, t, ha="center", va="top", fontsize=6.6, fontweight="bold", color="#222222", linespacing=1.1)
BUS = 55.5
ax.plot([BUS, BUS], [2.8, 44.0], color=OI["black"], lw=2.2, solid_capstyle="butt")
ax.text(BUS + 1.0, 3.0, "8,760 hourly balances", fontsize=5.4, va="bottom", ha="left", rotation=90)

# inputs
G = "#EDEDED"
box(ax, 1.0, 37.5, 18.0, 6.0, f"Grid electricity (Elec buy)\nprice $v$ = {um['marginal_value']:.2f} MXN kWh$^{{-1}}$", fc=G, fs=5.8)
box(ax, 1.0, 28.5, 18.0, 6.0, "Solar resource (SupIm)\nhourly PV output per kWp", fc="#FCEBC7", fs=5.8)
box(ax, 1.0, 8.0, 18.0, 16.5, "Saving profiles (SupIm)\nhourly savings of each\nmeasure from the\nhourly plant model\n\nnegawatts: avoided kWh\nenter the balance as\nsupply", fc="#D5EEE5", fs=5.6)
# processes
P_X, P_W = 24.5, 19.0
box(ax, P_X, 37.5, P_W, 6.0, "Purchase\nemits 0.444 tCO$_2$ MWh$^{-1}$", fc=G, fs=5.8)
box(ax, P_X, 28.5, P_W, 6.0, "Rooftop PV  $\\kappa^{PV}\\leq$ 700 kWp\n(163.8 kWp roof case)", fc="#FCEBC7", ec=OI["orange"], lw=1.0, fs=5.8)
ee = [("E4 base-load control", um["measures"]["E4"]), ("E3 insulation", um["measures"]["E3"]),
      ("E2 servo motors", um["measures"]["E2"]), ("E1 compressed air", um["measures"]["E1"])]
for i, (n, mm) in enumerate(ee):
    y = 21.3 - i * 3.95
    box(ax, P_X, y, P_W, 3.3, f"{n}  (0–100%)", fc="#D5EEE5", ec=OI["green"], lw=1.0, fs=5.6)
    arrow(ax, (19.0, 16.25), (P_X, y + 1.65), color=OI["green"], lw=0.5, ms=4)
    arrow(ax, (P_X + P_W, y + 1.65), (BUS, y + 1.65), color=OI["green"], lw=0.7)
arrow(ax, (19.0, 40.5), (P_X, 40.5), color="#666666")
arrow(ax, (19.0, 31.5), (P_X, 31.5), color=OI["orange"])
arrow(ax, (P_X + P_W, 40.5), (BUS, 40.5), color="#666666", lw=0.9)
arrow(ax, (P_X + P_W, 31.5), (BUS, 31.5), color=OI["orange"], lw=0.9)
box(ax, P_X, 2.8, P_W, 5.0, "Li-ion battery  $\\kappa^{B}$ (kWh)\n85% round trip, 0.5 kW kWh$^{-1}$", fc="#D6E6F3", ec=OI["blue"], lw=1.0, fs=5.6)
arrow(ax, (P_X + P_W, 5.3), (BUS, 5.3), color=OI["blue"], style="<|-|>", lw=0.8)
ax.text((P_X + P_W + BUS) / 2, 5.7, "charge / discharge", fontsize=5.0, color=OI["blue"], ha="center", va="bottom")
# sinks
S_X, S_W = 60.0, 21.0
box(ax, S_X, 35.0, S_W, 7.0, f"Plant demand\nhourly load, {um['load_MWh']:.0f} MWh yr$^{{-1}}$", fc="white", fs=5.8)
box(ax, S_X, 22.0, S_W, 9.5, "Feed-in (Elec sell)\nNM: $v$, with Σ export ≤ Σ import\nNB: 1.0 MXN kWh$^{-1}$\nSC: 0", fc=G, fs=5.6)
box(ax, S_X, 13.5, S_W, 5.5, "Curtailment\n(no value)", fc="white", ec="#888888", ls="--", fs=5.6)
for y in (38.5, 26.75, 16.25):
    arrow(ax, (BUS, y), (S_X, y), color="#444444", lw=0.9)
# objective and constraints
box(ax, 82.5, 31.0, 17.0, 12.5, "", fc="#FFF7E0", ec="#C99A2E", lw=0.8)
ax.text(91.0, 42.3, "minimise annualised cost", ha="center", va="top", fontsize=6.0, fontweight="bold")
ax.text(91.0, 36.6, "capital recovery (10%)\n+ fixed O&M\n+ purchases $-$ export revenue", ha="center", va="center",
        fontsize=5.6, linespacing=1.2)
box(ax, 82.5, 2.8, 17.0, 25.0, "", fc="white", ec="#888888", lw=0.6)
ax.text(91.0, 26.6, "subject to", ha="center", va="top", fontsize=6.0, fontweight="bold")
ax.text(83.4, 15.4, "• hourly energy balance\n• PV and savings $\\leq$\n  capacity × profile\n• adoption $\\leq$ 100%\n"
        "• battery state of charge\n  and power limits\n• NM: annual exports\n  $\\leq$ annual imports\n"
        "• CO$_2$ cap: 0.444 Σ import\n  ≤ 35–10% of baseline", ha="left", va="center", fontsize=5.5, linespacing=1.25)
ax.text(1.0, -1.2, "Solved for 3 compensation regimes (NM net metering, NB net billing, SC self-consumption), with and without "
        "efficiency, a roof limit and a CO$_2$-cap sweep; Pyomo + HiGHS.", fontsize=5.3, color="#555555")
save(fig, "fig_urbs_structure")
print("diagrams written")
