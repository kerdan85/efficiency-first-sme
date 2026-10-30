"""GDMTH (time-of-use) scenario: what if the plant were reclassified from GDMTO (reviewer request).

Hourly load and PV from the net-zero module; official GDMTH charges, Centro Oriente division (data/raw/
cfe_gdmth_centro_oriente.csv, all-in energy prices by period) and the national time-of-use periods.
Capacity is billed on min(DP, Q/(24 d FC)) with DP the maximum demand in the punta period and distribution on
min(DM, Q/(24 d FC)), FC = 0.57. PV energy is netted within each month and period; demand is measured on
imports. Holidays are treated as weekdays. NPVs add the discounted change in annual savings to the GDMTO NPV.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from efirst.hourly import dispatch, evaluate_nz, hourly_pv_per_kWp, load_profile, nz_central  # noqa: E402
from efirst.model import load_all, monthly_bill, pf_adjustment, tariff_row  # noqa: E402
from efirst.params import central  # noqa: E402

P = central(); NZ = nz_central(); D = load_all(P); W = hourly_pv_per_kWp(P)
ref = D["ref"]; months = ref.mon.to_numpy(); days = ref.days.to_numpy()

G = pd.read_csv(ROOT / "data/raw/cfe_gdmth_centro_oriente.csv")
TH = G[G.month == "2026-10"].iloc[0]          # same tariff month as the GDMTO central case
FC = 0.57
EE = ["E4", "E1", "E2", "E3", "E5"]
res = json.load(open(ROOT / "results/results.json")); K4 = res["p4_kWp"]


def periods(w):
    """0 base, 1 intermedia, 2 punta for each hour (SIN schedule; summer 5 Apr - 24 Oct)."""
    t = w.timestamp_LST; h = t.dt.hour.to_numpy(); wd = t.dt.weekday.to_numpy()
    md = t.dt.month.to_numpy() * 100 + t.dt.day.to_numpy()
    summer = (md >= 405) & (md <= 1024)
    p = np.ones(len(w), int)
    wk, sat, sun = wd <= 4, wd == 5, wd == 6
    # summer
    p[summer & wk & (h < 6)] = 0; p[summer & wk & (h >= 20) & (h < 22)] = 2
    p[summer & sat & (h < 7)] = 0
    p[summer & sun & (h < 19)] = 0
    # winter
    win = ~summer
    p[win & wk & (h < 6)] = 0; p[win & wk & (h >= 18) & (h < 22)] = 2
    p[win & sat & (h < 8)] = 0; p[win & sat & (h >= 19) & (h < 21)] = 2
    p[win & sun & (h < 18)] = 0
    return p


PER = periods(W)
PRICE = np.array([TH.energy_base_allin, TH.energy_intermedia_allin, TH.energy_punta_allin])


# measured monthly peaks implied by the load factor printed on each bill (kW = kWh / (LF * 24 d))
MEAS_PEAK = (ref.energy_kWh / (ref.load_factor_reported * 24 * ref.days)).to_numpy()


def bill_gdmth(load, pv, pf, peak_scale=None):
    """peak_scale: optional per-month factor applied to the modelled maximum demand (peak-calibrated variant)."""
    imp, exp = dispatch(load, pv, 0.0, NZ)
    mh = W.month.to_numpy(); total = 0.0
    for i, m in enumerate(months):
        idx = mh == m
        e = 0.0; q_net = 0.0
        for k in range(3):
            sel = idx & (PER == k)
            net = max(imp[sel].sum() - exp[sel].sum(), 0.0)   # netting within month and period
            e += net * PRICE[k]; q_net += net
        cap = q_net / (24 * days[i] * FC)
        dp = imp[idx & (PER == 2)].max() if (idx & (PER == 2)).any() else imp[idx].max()
        dm = imp[idx].max() * (peak_scale[i] if peak_scale is not None else 1.0)
        pre = TH.fixed_MXN + e + min(dp, cap) * TH.capacity_MXN_per_kW + min(dm, cap) * TH.distribution_MXN_per_kW
        total += pre * (1 + pf_adjustment(pf[i]))
    return total


def portfolio(meas, kwp, profile="standard", NZv=None, e4_mode="offhours", peakcal=False):
    NZv = NZv or NZ
    scale = None
    if peakcal:   # scale the modelled maximum demand so that the baseline matches the measured peak of each month
        L0, _, _ = load_profile([], P, NZv, D, W, e4_mode=e4_mode, profile=profile)
        mh = W.month.to_numpy()
        scale = np.array([max(MEAS_PEAK[i] / L0[mh == m].max(), 1.0) for i, m in enumerate(months)])
    L, q_ee, _ = load_profile(meas, P, NZv, D, W, e4_mode=e4_mode, profile=profile)
    pv = W.pv_kWh_per_kWp.to_numpy() * kwp
    pf = np.full(12, P["pfc_pf_after"]) if "E5" in meas else ref.power_factor.to_numpy()
    r = evaluate_nz(meas, kwp, 0, P, NZv, D, W, profile=profile, e4_mode=e4_mode)     # GDMTO, hourly-consistent, with NPV
    return dict(bill_gdmth=bill_gdmth(L, pv, pf, scale), bill_gdmto=r["bill1"], npv_gdmto=r["npv"], capex=r["capex"],
                load_MWh=L.sum() / 1000, pv_MWh=pv.sum() / 1000)


ann = sum((1 + P["discount_rate"]) ** -t for t in range(1, int(P["horizon_yr"]) + 1))
out = {"tariff_month": "2026-10", "FC": FC}
VARIANTS = {"standard": ("standard", 15.0, "offhours"), "extended": ("extended", 15.0, "offhours"),
            "always-on 25 kW": ("standard", 25.0, "offhours"),
            "all base load 24 h": ("standard", float(D["intercept"] / 730), "proportional"),
            "peak calibrated": ("standard", 15.0, "offhours", True)}
for vname, (profile, night, e4m, *pc) in VARIANTS.items():
    pc = bool(pc and pc[0])
    NZv = dict(NZ); NZv["night_load_kW"] = night
    PF = {"P0 baseline": ([], 0.0), "P1 efficiency": (EE, 0.0), "P1 energy measures": (["E4", "E1", "E2", "E3"], 0.0), "P2 PV only": ([], 163.8),
          "P3 efficiency + PV": (EE, 163.8), "P4 efficiency first": (EE, K4)}
    rows = {}
    for name, (meas, kwp) in PF.items():
        rows[name] = portfolio(meas, kwp, profile, NZv, e4m, pc)
    b0h, b0o = rows["P0 baseline"]["bill_gdmth"], rows["P0 baseline"]["bill_gdmto"]
    for name, r in rows.items():
        r["sav_gdmth"] = b0h - r["bill_gdmth"]; r["sav_gdmto"] = b0o - r["bill_gdmto"]
        r["npv_gdmth"] = r["npv_gdmto"] + (r["sav_gdmth"] - r["sav_gdmto"]) * ann
    # value per kWh avoided by efficiency and per kWh of PV
    kwh_ee = (rows["P0 baseline"]["load_MWh"] - rows["P1 energy measures"]["load_MWh"]) * 1000
    kwh_pv = rows["P2 PV only"]["pv_MWh"] * 1000
    out[vname] = dict(portfolios=rows,
                        value_per_kWh_EE=dict(gdmth=rows["P1 energy measures"]["sav_gdmth"] / kwh_ee, gdmto=rows["P1 energy measures"]["sav_gdmto"] / kwh_ee),
                        value_per_kWh_PV=dict(gdmth=rows["P2 PV only"]["sav_gdmth"] / kwh_pv, gdmto=rows["P2 PV only"]["sav_gdmto"] / kwh_pv),
                        p4_minus_p2_npv=dict(gdmth=rows["P4 efficiency first"]["npv_gdmth"] - rows["P2 PV only"]["npv_gdmth"],
                                             gdmto=rows["P4 efficiency first"]["npv_gdmto"] - rows["P2 PV only"]["npv_gdmto"]))
json.dump(out, open(ROOT / "results/gdmth.json", "w"), indent=1, default=float)
for prof in VARIANTS:
    print(prof, {k: {x: round(y / 1e3, 1) for x, y in v.items() if x.startswith(("bill", "sav", "npv"))} for k, v in out[prof]["portfolios"].items()})
    print(prof, "EE value", out[prof]["value_per_kWh_EE"], "PV value", out[prof]["value_per_kWh_PV"], "P4-P2", out[prof]["p4_minus_p2_npv"])
