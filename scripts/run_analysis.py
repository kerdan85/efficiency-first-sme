"""Deterministic analysis: baseline, tariff validation, measures, portfolios,
EE-first pathways, thermal substitution unit economics, sensitivities.

Writes results/*.csv and results/results.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from efirst.model import (annual_bill, annuity, baseline_models, billed_demand_kW, cce, evaluate,  # noqa: E402
                          load_all, marginal_value_per_kWh, measure_savings, pv_lcoe,
                          validate_tariff_model, GDMTO_FC)
from efirst.params import PARAMS, VAT, central  # noqa: E402

RES = ROOT / "results"; RES.mkdir(exist_ok=True)
P = central(); D = load_all(P)
ref, tr = D["ref"], D["tariff"]
out = {}

# ---------------------------------------------------------------- data/baseline
b = D["billing"]
out["billing"] = dict(
    n_months=int(len(b)), first=b.month.iloc[0], last=b.month.iloc[-1],
    kWh_mean=float(b.energy_kWh.mean()), kWh_min=float(b.energy_kWh.min()), kWh_max=float(b.energy_kWh.max()),
    kW_max=float(b.max_demand_kW.max()), pf_min=float(b.power_factor.min()), pf_max=float(b.power_factor.max()),
    pf_mean=float(b.power_factor.mean()),
    months_pf_below_90=int((b.power_factor < 0.90).sum()),
    ref_kWh=float(ref.energy_kWh.sum()), ref_first=ref.month.iloc[0], ref_last=ref.month.iloc[-1],
    ref_kWh_month_mean=float(ref.energy_kWh.mean()),
    months_kW_ge_100=int((b.max_demand_kW >= 100).sum()),
    lf_calc_min=float((b.energy_kWh / (b.max_demand_kW * 24 * b.days)).min()),
    lf_calc_max=float((b.energy_kWh / (b.max_demand_kW * 24 * b.days)).max()),
    production_months=int(b.production_pairs.notna().sum()),
    production_total=float(b.production_pairs.sum()),
    dmax_implied_min=float((b.energy_kWh / (b.load_factor_reported * 24 * b.days)).min()),
    dmax_implied_max=float((b.energy_kWh / (b.load_factor_reported * 24 * b.days)).max()),
    months_dmax_implied_ge_100=int(((b.energy_kWh / (b.load_factor_reported * 24 * b.days)) >= 100).sum()),
)
out["baseline"] = {k: {kk: float(vv) for kk, vv in v.items()} for k, v in D["baseline"].items()}
p = b.dropna(subset=["production_pairs"])
out["baseline"]["intensity_kWh_per_pair_mean"] = float((p.energy_kWh / p.production_pairs).mean())
out["baseline"]["intensity_kWh_per_pair_pooled"] = float(p.energy_kWh.sum() / p.production_pairs.sum())
bl = D["baseline"]["excl_24h_shift"]
out["baseline"]["base_load_share_ref"] = float(bl["intercept"] / ref.energy_kWh.mean())

# ---------------------------------------------------------------- tariff validation
v = validate_tariff_model(b, D["tariffs"])
v.to_csv(RES / "tariff_validation.csv", index=False)
out["tariff_validation"] = dict(mean_error=float(v.error.mean()), mape=float(v.error.abs().mean()),
                                sd=float(v.error.std()), max_abs=float(v.error.abs().max()),
                                kW_vs_Qbased_mean_ratio=float((v.recorded_kW / v.dq_kW).mean()))
out["tariff"] = dict(month="2026-10", fixed=float(tr.fixed_MXN_per_month), energy=float(tr.energy_MXN_per_kWh),
                     distribution=float(tr.distribution_MXN_per_kW), capacity=float(tr.capacity_MXN_per_kW),
                     FC=GDMTO_FC, marginal_MXN_per_kWh=float(marginal_value_per_kWh(tr)),
                     energy_share_of_marginal=float(tr.energy_MXN_per_kWh / marginal_value_per_kWh(tr)))
bill0 = annual_bill(ref.energy_kWh.to_numpy(float), ref, P, tr)
out["tariff"]["bill0"] = bill0
out["tariff"]["avg_price"] = bill0 / ref.energy_kWh.sum()
pfadj = [__import__("efirst.model", fromlist=["pf_adjustment"]).pf_adjustment(x) for x in ref.power_factor]
out["tariff"]["pf_surcharge_MXN_ref"] = float(sum(
    a / (1 + a) * x for a, x in zip(pfadj, __import__("efirst.model", fromlist=["monthly_bill"]).monthly_bill(
        ref.energy_kWh.to_numpy(float), ref.days.to_numpy(), ref.power_factor.to_numpy(), tr))))

# ---------------------------------------------------------------- PV resource
y = D["pv_yield"]
y.to_csv(RES / "pv_monthly_yield.csv", index=False)
lc, gen = pv_lcoe(P, D)
out["pv"] = dict(GHI_annual_mean=float(y.H.mean()), POA_annual_mean=float((y.Ht * y.days).sum() / 365),
                 specific_yield=float(y.yield_kWh_per_kWp.sum()), gen_163_MWh=float(gen / 1000),
                 lcoe=float(lc), capex_163=163.8 * 1000 * P["pv_cost_per_W"],
                 student_psh=4.8, student_kWp_calc=157.78)

# ---------------------------------------------------------------- measures (stand-alone)
rows = []
mv = marginal_value_per_kWh(tr)
from efirst.model import measure_capex  # noqa: E402
cap_tab, nmach = measure_capex(P, ref, D["intercept"])
names = {"E1": "Compressed-air package", "E2": "Servo motors (sewing)", "E3": "Insulation of heated platens/barrels",
         "E4": "Base-load (idle) control", "E5": "Power-factor correction", "PV": "Rooftop PV 163.8 kWp"}
for m in ["E4", "E3", "E2", "E1"]:
    c, kwh = cce(m, P, D)
    r = evaluate({"measures": [m]}, P, D)
    rows.append(dict(id=m, name=names[m], capex=cap_tab[m][0], om=cap_tab[m][1], life=cap_tab[m][2],
                     saved_MWh=kwh / 1000, cce=c, npv=r["npv"], savings_y1=r["savings_y1"],
                     co2_t=r["co2_saved_t"], payback=r["payback_yr"], cost_per_t=r["cost_per_t"]))
r = evaluate({"measures": ["E5"]}, P, D)
rows.append(dict(id="E5", name=names["E5"], capex=cap_tab["E5"][0], om=0, life=cap_tab["E5"][2], saved_MWh=0.0,
                 cce=float("nan"), npv=r["npv"], savings_y1=r["savings_y1"], co2_t=0.0, payback=r["payback_yr"],
                 cost_per_t=float("nan")))
r = evaluate({"pv_kWp": 163.8}, P, D)
rows.append(dict(id="PV", name=names["PV"], capex=r["capex"], om=P["pv_om_frac"] * r["capex"], life=P["pv_life"],
                 saved_MWh=r["grid_saved_MWh"], cce=lc, npv=r["npv"], savings_y1=r["savings_y1"],
                 co2_t=r["co2_saved_t"], payback=r["payback_yr"], cost_per_t=r["cost_per_t"]))
M = pd.DataFrame(rows)
M["npv_per_capex"] = M.npv / M.capex
M.to_csv(RES / "measures.csv", index=False)
out["measures"] = M.set_index("id").to_dict(orient="index")
out["measures_meta"] = dict(n_sewing_machines=float(nmach), marginal_value=float(mv))

# ---------------------------------------------------------------- portfolios
EE = ["E4", "E1", "E2", "E3", "E5"]
ports = {
    "P0 Baseline": {},
    "P1 Efficiency bundle": {"measures": EE},
    "P2 PV only (163.8 kWp)": {"pv_kWp": 163.8},
    "P3 Efficiency + PV (163.8 kWp)": {"measures": EE, "pv_kWp": 163.8},
}
# P4: EE first, PV re-sized to reach the same grid purchases as P2
r2 = evaluate(ports["P2 PV only (163.8 kWp)"], P, D)
target_grid = r2["grid1_MWh"]
lo, hi = 0.0, 163.8
for _ in range(60):
    mid = (lo + hi) / 2
    g = evaluate({"measures": EE, "pv_kWp": mid}, P, D)["grid1_MWh"]
    lo, hi = (mid, hi) if g > target_grid else (lo, mid)
kwp4 = round(hi, 1)
ports["P4 Efficiency first + right-sized PV"] = {"measures": EE, "pv_kWp": kwp4}
prow = []
for k, pf in ports.items():
    r = evaluate(pf, P, D)
    r.pop("cashflow")
    r["portfolio"] = k; r["pv_kWp"] = pf.get("pv_kWp", 0.0)
    r["roof_m2"] = r["pv_kWp"] * P["pv_m2_per_kWp"]
    prow.append(r)
PT = pd.DataFrame(prow)
PT.to_csv(RES / "portfolios.csv", index=False)
out["portfolios"] = PT.set_index("portfolio").to_dict(orient="index")
out["p4_kWp"] = kwp4

# ---------------------------------------------------------------- EE-first pathways
path = []
grid0 = ref.energy_kWh.sum() / 1000
yr_kWp = y.yield_kWh_per_kWp.sum() / 1000  # MWh per kWp
order = ["E4", "E3", "E2", "E1"]  # merit order by CCE (ascending), checked below
cce_sorted = sorted(order, key=lambda m: cce(m, P, D)[0])
assert cce_sorted == order, cce_sorted
for tgt in np.arange(0.05, 0.751, 0.025):
    # supply-only
    kwp_s = tgt * grid0 / yr_kWp
    rs = evaluate({"pv_kWp": kwp_s, "pfc": True}, P, D)
    # EE-first: add measures in merit order until target met, then PV for remainder
    chosen = []
    re_ = None
    for m in order:
        chosen.append(m)
        re_ = evaluate({"measures": chosen + ["E5"]}, P, D)
        if re_["grid_saved_frac"] >= tgt:
            break
    gap = max(tgt - re_["grid_saved_frac"], 0.0)
    lo, hi = 0.0, 400.0
    if gap > 0:
        for _ in range(50):
            mid = (lo + hi) / 2
            g = evaluate({"measures": chosen + ["E5"], "pv_kWp": mid}, P, D)["grid_saved_frac"]
            lo, hi = (mid, hi) if g < tgt else (lo, mid)
        kwp_e = hi
    else:
        kwp_e = 0.0
    re_ = evaluate({"measures": chosen + ["E5"], "pv_kWp": kwp_e}, P, D)
    path.append(dict(target=tgt, supply_kWp=kwp_s, supply_capex=rs["capex"], supply_npv=rs["npv"],
                     supply_roof=kwp_s * P["pv_m2_per_kWp"], supply_peak=rs["billed_peak1_kW"],
                     supply_shock=rs["shock_exposure1"], supply_surplus=rs["pv_surplus_MWh"],
                     ee_kWp=kwp_e, ee_capex=re_["capex"], ee_npv=re_["npv"], ee_roof=kwp_e * P["pv_m2_per_kWp"],
                     ee_peak=re_["billed_peak1_kW"], ee_shock=re_["shock_exposure1"], ee_measures="+".join(chosen),
                     ee_surplus=re_["pv_surplus_MWh"]))
PA = pd.DataFrame(path)
PA.to_csv(RES / "pathways.csv", index=False)
row50 = PA.iloc[(PA.target - 0.50).abs().argmin()]
out["pathway_50"] = {k: (float(v) if not isinstance(v, str) else v) for k, v in row50.items()}

# ---------------------------------------------------------------- PV regulatory stress
P_nb = dict(P); P_nb["pv_demand_credit"] = 0.0
out["pv_stress"] = dict(
    npv_pv_no_demand_credit=evaluate({"pv_kWp": 163.8}, P_nb, D)["npv"],
    npv_ee_no_demand_credit=evaluate({"measures": EE}, P_nb, D)["npv"],
    savings_pv_no_demand_credit=evaluate({"pv_kWp": 163.8}, P_nb, D)["savings_y1"],
)

# ---------------------------------------------------------------- thermal substitution (per GJ useful heat)
lpg_price_GJ = P["lpg_price_MXN_per_kg_incl_vat"] / (1 + VAT) / (P["lpg_LHV_MJ_per_kg"] / 1000)
ipgn = pd.read_csv(ROOT / "data/raw/fuel_prices_mexico.csv")
ipgn = ipgn[ipgn.series.str.startswith("IPGN")]
ipgn_12 = float(ipgn.value.tail(12).mean())
ng_price_GJ = ipgn_12 * P["ng_enduser_markup"]
el_price_GJ = mv / 0.0036  # MXN per GJ_e
ef_el_GJ = P["ef_grid_t_per_MWh"] * 1000 / 3.6  # kg/GJ_e
th = []
for name, cost, ef in [
    ("LPG boiler", lpg_price_GJ / P["boiler_eff"], P["lpg_EF_kg_per_GJ"] / P["boiler_eff"]),
    ("Natural-gas boiler", ng_price_GJ / P["boiler_eff"], P["ng_EF_kg_per_GJ"] / P["boiler_eff"]),
    ("Electric resistance", el_price_GJ, ef_el_GJ),
    ("Heat pump COP 2.5", el_price_GJ / 2.5, ef_el_GJ / 2.5),
    ("Heat pump COP 3.0", el_price_GJ / 3.0, ef_el_GJ / 3.0),
    ("Heat pump COP 4.0", el_price_GJ / 4.0, ef_el_GJ / 4.0),
    ("Compressor heat recovery", 0.0, 0.0),
]:
    th.append(dict(option=name, cost_MXN_per_GJ=cost, kgCO2_per_GJ=ef))
TH = pd.DataFrame(th)
TH.to_csv(RES / "thermal_unit_economics.csv", index=False)
ca_kWh0 = 0.16798 * ref.energy_kWh.sum()
_, det = measure_savings(ref, P, D["intercept"], ["E4", "E1"])
ca_kWh1 = ca_kWh0 * (1 - P["base_saving_frac"] * min(1, D["intercept"] / ref.energy_kWh.mean())) - det["E1"].sum()
out["thermal"] = dict(lpg_MXN_per_GJ_fuel=lpg_price_GJ, ipgn_12m=ipgn_12, ng_MXN_per_GJ_fuel=ng_price_GJ,
                      el_MXN_per_GJ=el_price_GJ, ef_el_kg_per_GJ=ef_el_GJ,
                      table=TH.set_index("option").to_dict(orient="index"),
                      hp_cop_breakeven_vs_lpg=el_price_GJ / (lpg_price_GJ / P["boiler_eff"]),
                      hp_cop_breakeven_vs_ng=el_price_GJ / (ng_price_GJ / P["boiler_eff"]),
                      hp_cop_co2_breakeven_vs_lpg=ef_el_GJ / (P["lpg_EF_kg_per_GJ"] / P["boiler_eff"]),
                      hp_cop_co2_breakeven_vs_ng=ef_el_GJ / (P["ng_EF_kg_per_GJ"] / P["boiler_eff"]),
                      ca_heat_GJ_before=ca_kWh0 * 0.0036 * P["ca_heat_recovery_frac"],
                      ca_heat_GJ_after=ca_kWh1 * 0.0036 * P["ca_heat_recovery_frac"],
                      ee_headroom_GJ_heat_at_cop3=out["portfolios"]["P1 Efficiency bundle"]["ee_saved_MWh"] * 3.6 * 3.0)

# ---------------------------------------------------------------- emission-factor trend and gas-indicator ranges
H = int(P["horizon_yr"])
ef_mult = {tr_: float(sum((1 + tr_) ** t for t in range(H)) / H) for tr_ in (0.0, -0.03)}
out["ef_trend"] = dict(mean_multiplier_minus3=ef_mult[-0.03],
                       lifetime_co2_P1_const=out["portfolios"]["P1 Efficiency bundle"]["co2_saved_t"] * H,
                       lifetime_co2_P1_minus3=out["portfolios"]["P1 Efficiency bundle"]["co2_saved_t"] * H * ef_mult[-0.03])
gl = PARAMS["gas_share_generation"]; hl = PARAMS["ccgt_heat_rate_GJ_per_MWh"]; il = PARAMS["gas_import_share"]
for lab_, k_ in (("P1", "P1 Efficiency bundle"), ("P2", "P2 PV only (163.8 kWp)")):
    mwh = out["portfolios"][k_]["grid_saved_MWh"]
    out.setdefault("gas_range", {})[lab_] = dict(lo=mwh * gl[1] * hl[1] * il[1], hi=mwh * gl[2] * hl[2] * il[2])

# ---------------------------------------------------------------- one-way sensitivity (NPV)
sens = []
for key, (c, lo_, hi_, st, src) in PARAMS.items():
    if lo_ == hi_ or key in ("pv_demand_credit", "ef_trend_per_yr"):
        continue
    for lab, val in (("low", lo_), ("high", hi_)):
        Pq = dict(P); Pq[key] = val
        Dq = D if key not in ("pv_tilt_deg", "pv_albedo") else load_all(Pq)
        sens.append(dict(param=key, case=lab, value=val,
                         npv_P1=evaluate({"measures": EE}, Pq, Dq)["npv"],
                         npv_P2=evaluate({"pv_kWp": 163.8}, Pq, Dq)["npv"],
                         npv_P4=evaluate({"measures": EE, "pv_kWp": kwp4}, Pq, Dq)["npv"]))
pd.DataFrame(sens).to_csv(RES / "sensitivity_oneway.csv", index=False)

# ---------------------------------------------------------------- student-report reproduction
stu = {}
stu["kWp_calc"] = 28400 * 0.8 / (30 * 4.8)
stu["kWp_modules"] = 252 * 0.65
stu["ca_5pct_total"] = 0.05 * 28400
stu["ca_energy_month"] = 0.16798 * 28400
stu["ca_5pct_as_frac_of_ca"] = stu["ca_5pct_total"] / stu["ca_energy_month"]
stu["retscreen_export_kWh"] = 200.2 * 0.17641027922 * 8760 - 28400
stu["npv_student"] = -1935000 + (90880 - 17254.4) * 12 * (1 - 1.1 ** -20) / 0.1
stu["Q_kvar"] = 100 * np.tan(np.arccos(0.8715))
stu["pf_with_50kvar"] = float(np.cos(np.arctan((stu["Q_kvar"] - 50) / 100)))
out["student"] = stu

with open(RES / "results.json", "w") as f:
    json.dump(out, f, indent=1, default=float)
print(json.dumps({k: out[k] for k in ["tariff_validation", "tariff", "pv", "pathway_50", "pv_stress", "p4_kWp"]},
                 indent=1, default=float))
print(M.round(3).to_string())
print(PT[["portfolio", "pv_kWp", "capex", "npv", "grid_saved_frac", "co2_saved_t", "billed_peak1_kW",
          "shock_exposure1", "imported_gas_avoided_GJ", "roof_m2"]].round(2).to_string())
