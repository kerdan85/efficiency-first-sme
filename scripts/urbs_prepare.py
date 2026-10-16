"""Build the urbs input workbook for the plant (single site, one year, hourly).

Efficiency measures enter urbs as 'negawatt' processes: each delivers its hourly savings profile (from the same
hourly model used in the net-zero analysis) to the electricity balance, with its own investment cost, O&M and
lifetime, so the linear programme decides how much of each measure to adopt alongside PV, batteries and grid
purchases. Run with the main environment; the LP is solved by scripts/run_urbs.py in the urbs environment.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from efirst.hourly import hourly_load, hourly_pv_per_kWp, nz_central  # noqa: E402
from efirst.model import load_all, marginal_value_per_kWh, measure_capex, measure_savings  # noqa: E402
from efirst.params import HOURS_OPERATING_PER_MONTH, central  # noqa: E402

OUT = ROOT / "urbs"; OUT.mkdir(exist_ok=True)
P = central(); NZ = nz_central(); D = load_all(P); W = hourly_pv_per_kWp(P)
ref = D["ref"]; months = ref.mon.to_numpy()
h_month = np.array([(W.month == m).sum() for m in months])
nonop = h_month - HOURS_OPERATING_PER_MONTH * h_month / 730
N = NZ["night_load_kW"]


def load_for(meas):
    q, det = measure_savings(ref, P, D["intercept"], meas)
    night = np.full(12, N)
    if "E4" in det:
        night = np.maximum(night - det["E4"] / nonop, 0.3 * N)
    return hourly_load(q, months, W, night)


L0 = load_for([])
L4 = load_for(["E4"])
# Base-load control removes idle load outside production. In the synthetic profile its effect appears as a lower
# always-on load plus a small rise in operating hours (the monthly balance is closed there); for the LP the
# saving is assigned to the hours where it is positive and rescaled to the same monthly energy.
d4 = L0 - L4
s4 = np.clip(d4, 0, None)
for m in months:
    idx = (W.month == m).to_numpy()
    s4[idx] *= d4[idx].sum() / s4[idx].sum()
sav = {"E4": s4}
for m in ("E1", "E2", "E3"):
    sav[m] = L4 - load_for(["E4", m])        # savings of each component measure after base-load control
Lall = load_for(["E4", "E1", "E2", "E3"])
assert abs((L0 - Lall).sum() - sum(v.sum() for v in sav.values())) < 1e-3, "savings are not additive"
for m, s in sav.items():
    assert (s > -1e-9).all(), m

tab, _ = measure_capex(P, ref, D["intercept"])
mv = float(marginal_value_per_kWh(D["tariff"]))
pv_cap = P["pv_cost_per_W"] * 1000                       # MXN per kWp
pv_inv = pv_cap * (1 + P["pv_inverter_repl_frac"] * (1 + P["discount_rate"]) ** -12)
pv_h = W.pv_kWh_per_kWp.to_numpy()
fpk = float(pv_h.max())          # urbs needs SupIm <= 1: one urbs PV unit = 1/fpk kWp
bat_usable = NZ["bat_cost_per_kWh"] / NZ["bat_dod"]      # MXN per usable kWh
eta = math.sqrt(NZ["bat_rte"])
names = {"E1": "EE compressed air", "E2": "EE servo motors", "E3": "EE insulation", "E4": "EE base-load control"}

T = len(L0)
t_index = list(range(0, T + 1))
pad = lambda a: np.concatenate([[0.0], np.asarray(a, float)])

site = "Plant"
glob = pd.DataFrame({"Property": ["CO2 limit", "Cost limit", "mode"], "value": [np.inf, np.inf, np.nan]})
sites = pd.DataFrame({"Name": [site], "area": [np.nan]})
com_rows = [(site, "Solar", "SupIm", np.nan), (site, "Elec", "Demand", np.nan), (site, "CO2", "Env", 0.0),
            (site, "Elec buy", "Buy", 1.0), (site, "Elec sell", "Sell", 1.0), (site, "Elec curtailed", "Sell", 1.0)]
for m in sav:
    com_rows.append((site, f"Saving {m}", "SupIm", np.nan))
com = pd.DataFrame(com_rows, columns=["Site", "Commodity", "Type", "price"]); com["max"] = np.inf; com["maxperhour"] = np.inf

pro_cols = ["Site", "Process", "inst-cap", "cap-lo", "cap-up", "ramp-up-grad", "ramp-down-grad", "start-time",
            "min-fraction", "inv-cost", "fix-cost", "var-cost", "wacc", "depreciation", "area-per-cap", "cap-block",
            "start-price", "on-off", "decommissionable", "availability"]
r = P["discount_rate"]
pro = [[site, "Purchase", 0, 0, 1e6, np.inf, np.inf, np.nan, 0, 0, 0, 0, r, 20, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan],
       [site, "Feed-in", 0, 0, 1e6, np.inf, np.inf, np.nan, 0, 0, 0, 1e-3, r, 20, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan],
       # PV output can be curtailed (inverter limitation) at a negligible cost; it earns nothing
       [site, "Curtailment", 0, 0, 1e6, np.inf, np.inf, np.nan, 0, 0, 0, 1e-4, r, 20, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan],
       [site, "Photovoltaics", 0, 0, 700.0 * fpk, np.inf, np.inf, np.nan, 0, pv_inv / fpk, P["pv_om_frac"] * pv_cap / fpk, 0, r,
        P["pv_life"], np.nan, np.nan, np.nan, np.nan, np.nan, np.nan]]
meas_meta = {}
for m, s in sav.items():
    peak = float(s.max()); cap, om, life = tab[m]
    pro.append([site, names[m], 0, 0, peak, np.inf, np.inf, np.nan, 0, cap / peak, om / peak, 0, r, life,
                np.nan, np.nan, np.nan, np.nan, np.nan, np.nan])
    meas_meta[m] = dict(process=names[m], peak_kW=peak, annual_kWh=float(s.sum()), capex=cap, om=om, life=life)
pro = pd.DataFrame(pro, columns=pro_cols)
pc = [("Purchase", "Elec buy", "In", 1.0), ("Purchase", "Elec", "Out", 1.0),
      ("Purchase", "CO2", "Out", P["ef_grid_t_per_MWh"] / 1000), ("Feed-in", "Elec", "In", 1.0),
      ("Feed-in", "Elec sell", "Out", 1.0), ("Curtailment", "Elec", "In", 1.0),
      ("Curtailment", "Elec curtailed", "Out", 1.0), ("Photovoltaics", "Solar", "In", 1.0), ("Photovoltaics", "Elec", "Out", 1.0)]
for m in sav:
    pc += [(names[m], f"Saving {m}", "In", 1.0), (names[m], "Elec", "Out", 1.0)]
pc = pd.DataFrame(pc, columns=["Process", "Commodity", "Direction", "ratio"]); pc["ratio-min"] = np.nan

sto = pd.DataFrame([[site, "Li-ion battery", "Elec", 0, 0, np.inf, 0, 0, np.inf, eta, eta, 0.0, bat_usable, 0.0,
                     NZ["bat_om_frac"] * bat_usable, 1e-3, 0.0, r, NZ["bat_life"], 0.5, 0.0,
                     1.0 / (NZ["bat_c_rate"] / NZ["bat_dod"]), np.nan, np.nan]],
                   columns=["Site", "Storage", "Commodity", "inst-cap-c", "cap-lo-c", "cap-up-c", "inst-cap-p", "cap-lo-p",
                            "cap-up-p", "eff-in", "eff-out", "inv-cost-p", "inv-cost-c", "fix-cost-p", "fix-cost-c",
                            "var-cost-p", "var-cost-c", "wacc", "depreciation", "init", "discharge", "ep-ratio",
                            "c-block", "p-block"])
dem = pd.DataFrame({"t": t_index, f"{site}.Elec": pad(L0)})
sup = {"t": t_index, f"{site}.Solar": pad(pv_h / fpk)}
for m, s in sav.items():
    sup[f"{site}.Saving {m}"] = pad(s / s.max())
sup = pd.DataFrame(sup)
bsp = pd.DataFrame({"t": t_index, "Elec buy": pad(np.full(T, mv)), "Elec sell": pad(np.full(T, mv)),
                    "Elec curtailed": pad(np.zeros(T))})
tve = pd.DataFrame({"t": t_index})
trans = pd.DataFrame(columns=["Site In", "Site Out", "Transmission", "Commodity", "eff", "inv-cost", "fix-cost", "var-cost",
                              "inst-cap", "cap-lo", "cap-up", "wacc", "depreciation", "reactance", "difflimit",
                              "base_voltage", "tra-block"])
dsm = pd.DataFrame(columns=["Site", "Commodity", "delay", "eff", "recov", "cap-max-do", "cap-max-up"])

with pd.ExcelWriter(OUT / "plant_urbs.xlsx") as xw:
    for name, df in (("Global", glob), ("Site", sites), ("Commodity", com), ("Process", pro), ("Process-Commodity", pc),
                     ("Transmission", trans), ("Storage", sto), ("DSM", dsm), ("Demand", dem), ("SupIm", sup),
                     ("Buy-Sell-Price", bsp), ("TimeVarEff", tve)):
        df.to_excel(xw, sheet_name=name, index=False)
meta = dict(marginal_value=mv, pv_unit_per_kWp=fpk, load_MWh=float(L0.sum() / 1000), load_after_all_EE_MWh=float(Lall.sum() / 1000),
            pv_specific_yield=float(W.pv_kWh_per_kWp.sum()), pv_inv_cost_per_kWp=pv_inv, bat_cost_per_usable_kWh=bat_usable,
            co2_baseline_t=float(L0.sum() / 1000 * P["ef_grid_t_per_MWh"]), ef=P["ef_grid_t_per_MWh"],
            net_billing_export=NZ["net_billing_export_value"], measures=meas_meta, discount_rate=r)
json.dump(meta, open(OUT / "plant_urbs_meta.json", "w"), indent=1)
print(json.dumps({k: v for k, v in meta.items() if k != "measures"}, indent=1))
for m, v in meas_meta.items():
    print(m, {k: round(x, 2) if isinstance(x, float) else x for k, x in v.items()})
