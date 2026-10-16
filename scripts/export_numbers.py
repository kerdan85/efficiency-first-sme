"""Export every number quoted in the manuscript as LaTeX macros (manuscript/numbers.tex)."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
r = json.load(open(ROOT / "results/results.json"))
mc = json.load(open(ROOT / "results/montecarlo_summary.json"))
PT = pd.read_csv(ROOT / "results/portfolios.csv").set_index("portfolio")
M = pd.read_csv(ROOT / "results/measures.csv").set_index("id")
PA = pd.read_csv(ROOT / "results/pathways.csv")

K = {"P1": "P1 Efficiency bundle", "P2": "P2 PV only (163.8 kWp)", "P3": "P3 Efficiency + PV (163.8 kWp)",
     "P4": "P4 Efficiency first + right-sized PV", "P0": "P0 Baseline"}
roman = {"P0": "Zero", "P1": "One", "P2": "Two", "P3": "Three", "P4": "Four"}
mname = {"E1": "CA", "E2": "Servo", "E3": "Insul", "E4": "Base", "E5": "PFC", "PV": "PV"}
out = {}


def f(x, d=0, comma=True):
    s = f"{x:,.{d}f}" if comma else f"{x:.{d}f}"
    return s.replace(",", "{,}")


def mm(x, d=2):  # million MXN
    return f"{x/1e6:.{d}f}"


def pct(x, d=0):
    return f"{100*x:.{d}f}"


b = r["billing"]
out.update(NMonths=b["n_months"], KWhMean=f(b["kWh_mean"]), KWhMin=f(b["kWh_min"]), KWhMax=f(b["kWh_max"]),
           KWMax=f(b["kW_max"]), PFMin=f(100 * b["pf_min"], 1), PFMax=f(100 * b["pf_max"], 1),
           PFMean=f(100 * b["pf_mean"], 1), MonthsPFLow=b["months_pf_below_90"], RefMWh=f(b["ref_kWh"] / 1000, 1),
           RefKWhMonth=f(b["ref_kWh_month_mean"]), MonthsKWHundred=b["months_kW_ge_100"],
           LFCalcMin=f(b["lf_calc_min"], 2), LFCalcMax=f(b["lf_calc_max"], 2), ProdMonths=b["production_months"])
bl = r["baseline"]
for key, tag in (("all_25", "All"), ("excl_24h_shift", "Excl"), ("student_subset_as_reported", "Orig"),
                 ("student_subset_corrected", "OrigCorr")):
    out[f"Slope{tag}"] = f(bl[key]["slope"], 2); out[f"Int{tag}"] = f(bl[key]["intercept"])
    out[f"RSq{tag}"] = f(bl[key]["r2"], 2); out[f"CV{tag}"] = pct(bl[key]["cv_rmse"], 1); out[f"N{tag}"] = int(bl[key]["n"])
out["IntExclSE"] = f(bl["excl_24h_shift"]["se_intercept"])
out["BaseShare"] = pct(bl["base_load_share_ref"])
out["IntensityPooled"] = f(bl["intensity_kWh_per_pair_pooled"], 2)
tv = r["tariff_validation"]
out.update(TVBias=f(100 * tv["mean_error"], 1), TVMape=f(100 * tv["mape"], 1), TVMax=f(100 * tv["max_abs"], 1),
           KWRatio=f(tv["kW_vs_Qbased_mean_ratio"], 3))
t = r["tariff"]
out.update(TFixed=f(t["fixed"], 2), TEnergy=f(t["energy"], 3), TDist=f(t["distribution"], 2), TCap=f(t["capacity"], 2),
           TMarg=f(t["marginal_MXN_per_kWh"], 2), TEnergyShare=pct(t["energy_share_of_marginal"]),
           BillZero=mm(t["bill0"]), AvgPrice=f(t["avg_price"], 2), PFSurcharge=f(t["pf_surcharge_MXN_ref"] / 1000, 1))
pv = r["pv"]
out.update(GHI=f(pv["GHI_annual_mean"], 2), POA=f(pv["POA_annual_mean"], 2), SpecYield=f(pv["specific_yield"]),
           PVGen=f(pv["gen_163_MWh"]), PVLCOE=f(pv["lcoe"], 2), PVCapex=mm(pv["capex_163"]))
for mid, row in M.iterrows():
    n = mname[mid]
    out[f"Capex{n}"] = f(row.capex / 1000); out[f"Saved{n}"] = f(row.saved_MWh, 1)
    out[f"CCE{n}"] = "--" if pd.isna(row.cce) else f(row.cce, 2)
    out[f"NPV{n}"] = mm(row.npv); out[f"Sav{n}"] = f(row.savings_y1 / 1000, 1)
    out[f"CO{n}"] = f(row.co2_t, 1); out[f"PB{n}"] = f(row.payback, 1)
    out[f"NPVCap{n}"] = f(row.npv_per_capex, 1)
out["NSewing"] = f(r["measures_meta"]["n_sewing_machines"])
for k, name in K.items():
    row = PT.loc[name]; n = roman[k]
    out[f"Capex{n}"] = mm(row.capex); out[f"NPV{n}"] = mm(row.npv); out[f"Grid{n}"] = pct(row.grid_saved_frac)
    out[f"GridMWh{n}"] = f(row.grid1_MWh); out[f"SavedMWh{n}"] = f(row.grid_saved_MWh)
    out[f"CO{n}"] = f(row.co2_saved_t); out[f"Peak{n}"] = f(row.billed_peak1_kW); out[f"Shock{n}"] = f(row.shock_exposure1 / 1000)
    out[f"Gas{n}"] = f(row.imported_gas_avoided_GJ); out[f"Roof{n}"] = f(row.roof_m2); out[f"KWp{n}"] = f(row.pv_kWp, 1)
    out[f"PB{n}"] = f(row.payback_yr, 1) if row.payback_yr == row.payback_yr else "--"
    out[f"SavY{n}"] = f(row.savings_y1 / 1000); out[f"BillOne{n}"] = mm(row.bill1)
    out[f"COPct{n}"] = pct(row.co2_saved_t / row.co2_0_t)
    out[f"CostT{n}"] = f(row.cost_per_t) if row.cost_per_t == row.cost_per_t else "--"
out["COBase"] = f(PT.loc[K["P0"]].co2_0_t)
p1, p2, p4 = PT.loc[K["P1"]], PT.loc[K["P2"]], PT.loc[K["P4"]]
out["CapexSaveFour"] = pct(1 - p4.capex / p2.capex); out["RoofSaveFour"] = pct(1 - p4.roof_m2 / p2.roof_m2)
out["NPVGainFour"] = mm(p4.npv - p2.npv); out["PVSaveFour"] = pct(1 - p4.pv_kWp / p2.pv_kWp)
out["PeakCutOne"] = f(p2.billed_peak1_kW - p1.billed_peak1_kW)
out["ShockCutOne"] = pct(1 - p1.shock_exposure1 / PT.loc[K["P0"]].shock_exposure1)
out["ShockCutFour"] = pct(1 - p4.shock_exposure1 / PT.loc[K["P0"]].shock_exposure1)
out["EESavedMWh"] = f(p1.ee_saved_MWh, 1)
out["EESavedPct"] = pct(p1.ee_saved_MWh / p1.grid0_MWh)
p50 = r["pathway_50"]
out.update(PathSKWp=f(p50["supply_kWp"]), PathEKWp=f(p50["ee_kWp"]), PathSCapex=mm(p50["supply_capex"]),
           PathECapex=mm(p50["ee_capex"]), PathSRoof=f(p50["supply_roof"]), PathERoof=f(p50["ee_roof"]),
           PathNPVGain=mm(p50["ee_npv"] - p50["supply_npv"]), PathCapexSave=pct(1 - p50["ee_capex"] / p50["supply_capex"]))
out["PathEEOnlyMax"] = pct(PA[PA.ee_kWp == 0].target.max())
s = r["pv_stress"]
out.update(NPVPVStress=mm(s["npv_pv_no_demand_credit"]), NPVEEStress=mm(s["npv_ee_no_demand_credit"]),
           PVStressDrop=pct(1 - s["npv_pv_no_demand_credit"] / p2.npv))
th = r["thermal"]
out.update(LPGFuel=f(th["lpg_MXN_per_GJ_fuel"]), IPGN=f(th["ipgn_12m"], 1), NGFuel=f(th["ng_MXN_per_GJ_fuel"]),
           ElGJ=f(th["el_MXN_per_GJ"]), EFElGJ=f(th["ef_el_kg_per_GJ"]),
           HeatLPG=f(th["table"]["LPG boiler"]["cost_MXN_per_GJ"]), HeatNG=f(th["table"]["Natural-gas boiler"]["cost_MXN_per_GJ"]),
           HeatHPThree=f(th["table"]["Heat pump COP 3.0"]["cost_MXN_per_GJ"]),
           HeatRes=f(th["table"]["Electric resistance"]["cost_MXN_per_GJ"]),
           COLPG=f(th["table"]["LPG boiler"]["kgCO2_per_GJ"]), CONG=f(th["table"]["Natural-gas boiler"]["kgCO2_per_GJ"]),
           COHPThree=f(th["table"]["Heat pump COP 3.0"]["kgCO2_per_GJ"]), CORes=f(th["table"]["Electric resistance"]["kgCO2_per_GJ"]),
           COPBELPG=f(th["hp_cop_breakeven_vs_lpg"], 1), COPBENG=f(th["hp_cop_breakeven_vs_ng"], 1),
           COPCOLPG=f(th["hp_cop_co2_breakeven_vs_lpg"], 1), COPCONG=f(th["hp_cop_co2_breakeven_vs_ng"], 1),
           CAHeatBefore=f(th["ca_heat_GJ_before"]), CAHeatAfter=f(th["ca_heat_GJ_after"]),
           HeadroomGJ=f(th["ee_headroom_GJ_heat_at_cop3"]))
out.update(MCN=f(mc["N"]), ProbFourTwo=pct(mc["prob_P4_gt_P2"]), ProbBaseCheapest=pct(mc["prob_E4_cheapest_overall"]),
           ProbAllBelow=f(100 * mc["prob_all_cce_below_marginal"], 2), ProbNPVCapex=pct(mc["prob_P1_npv_per_capex_gt_P2"]))
for k in ["P1", "P2", "P4"]:
    n = roman[k]
    out[f"MCLo{n}"] = mm(mc[f"npv_{k}"]["p5"]); out[f"MCHi{n}"] = mm(mc[f"npv_{k}"]["p95"]); out[f"MCMed{n}"] = mm(mc[f"npv_{k}"]["p50"])
    out[f"ProbPos{n}"] = pct(mc["prob_npv_pos"][k])
for m in ["E1", "E2", "E3", "E4"]:
    out[f"CCELo{mname[m]}"] = f(mc[f"cce_{m}"]["p5"], 2); out[f"CCEHi{mname[m]}"] = f(mc[f"cce_{m}"]["p95"], 2)
out["LCOELo"] = f(mc["lcoe_PV"]["p5"], 2); out["LCOEHi"] = f(mc["lcoe_PV"]["p95"], 2)
sp = mc["spearman_diff_P4_P2"]
out["RhoBase"] = f(sp["base_saving_frac"], 2); out["RhoInsul"] = f(sp["heat_saving_frac"], 2); out["RhoServo"] = f(sp["sew_saving_frac"], 2); out["RhoPVCost"] = f(sp["pv_cost_per_W"], 2); out["RhoPR"] = f(sp["pv_PR"], 2)
st = r["student"]
out.update(StuKWp=f(st["kWp_calc"], 1), StuKWpMod=f(st["kWp_modules"], 1), StuExport=f(st["retscreen_export_kWh"]),
           StuQ=f(st["Q_kvar"], 1), StuPF=f(100 * st["pf_with_50kvar"], 1))

lines = ["% Auto-generated by scripts/export_numbers.py -- do not edit by hand"]
for k, v in out.items():
    lines.append(f"\\newcommand{{\\n{k}}}{{{v}}}")
(ROOT / "manuscript").mkdir(exist_ok=True)
(ROOT / "manuscript/numbers.tex").write_text("\n".join(lines) + "\n")
json.dump(out, open(ROOT / "results/manuscript_numbers.json", "w"), indent=1, default=str)
print(len(out), "macros")

# USD equivalents (exchange rate used by CNE for the August 2026 IPGN)
fx = 17.0963
extra = dict(USDRate=f"{fx:.2f}", CapexTwoUSD=f"{p2.capex/fx/1000:,.0f}".replace(",", "{,}"),
             CapexFourUSD=f"{p4.capex/fx/1000:,.0f}".replace(",", "{,}"),
             NPVTwoUSD=f"{p2.npv/fx/1e6:.2f}", NPVFourUSD=f"{p4.npv/fx/1e6:.2f}", NPVOneUSD=f"{p1.npv/fx/1e6:.2f}",
             CapexOneUSD=f"{p1.capex/fx/1000:,.0f}".replace(",", "{,}"),
             TMargUSD=f"{r['tariff']['marginal_MXN_per_kWh']/fx:.3f}")
out.update(extra)
with open(ROOT / "manuscript/numbers.tex", "a") as fh:
    for k, v in extra.items():
        fh.write(f"\\newcommand{{\\n{k}}}{{{v}}}\n")
json.dump(out, open(ROOT / "results/manuscript_numbers.json", "w"), indent=1, default=str)

# Probabilities from Monte Carlo draws (comparison with PV LCOE and with the energy charge)
MCd = pd.read_csv(ROOT / "results/montecarlo.csv.gz")
extra2 = {}
for m in ["E1", "E2", "E3", "E4"]:
    extra2[f"ProbBelowPV{mname[m]}"] = pct((MCd[f"cce_{m}"] < MCd.lcoe_PV).mean())
    extra2[f"ProbBelowEnergy{mname[m]}"] = pct((MCd[f"cce_{m}"] < r["tariff"]["energy"]).mean())
extra2["DmaxImpMin"] = f(r["billing"]["dmax_implied_min"]); extra2["DmaxImpMax"] = f(r["billing"]["dmax_implied_max"])
extra2["MonthsDmaxImp"] = str(r["billing"]["months_dmax_implied_ge_100"])
extra2["EFTrendDrop"] = pct(1 - r["ef_trend"]["mean_multiplier_minus3"])
extra2["GasOneLo"] = f(r["gas_range"]["P1"]["lo"]); extra2["GasOneHi"] = f(r["gas_range"]["P1"]["hi"])
extra2["GasTwoLo"] = f(r["gas_range"]["P2"]["lo"]); extra2["GasTwoHi"] = f(r["gas_range"]["P2"]["hi"])
extra2["NPVCapMinEE"] = f(min(M.loc[i, "npv_per_capex"] for i in ["E1", "E2", "E3"]), 1)
extra2["NPVCapMaxEE"] = f(max(M.loc[i, "npv_per_capex"] for i in ["E1", "E2", "E3"]), 1)
extra2["PBMaxEE"] = f(max(M.loc[i, "payback"] for i in ["E1", "E2", "E3", "E4"]), 1)
extra2["GridDiffFour"] = f(abs(p4.grid1_MWh - p2.grid1_MWh), 2)
extra2["PVDiffFour"] = f"{p2.pv_kWp - p4.pv_kWp:.0f}"
out.update(extra2)
with open(ROOT / "manuscript/numbers.tex", "a") as fh:
    for k, v in extra2.items():
        fh.write(f"\\newcommand{{\\n{k}}}{{{v}}}\n")
json.dump(out, open(ROOT / "results/manuscript_numbers.json", "w"), indent=1, default=str)

# Net-zero scenarios
nz = json.load(open(ROOT / "results/netzero.json"))
S_ = nz["scenarios"]; nzs, nze = S_["NZ-S annual, supply only"], S_["NZ-E annual, efficiency first"]
s80, s90 = S_["SS80-eefirst"], S_["SS90-eefirst"]; s80s, s90s = S_["SS80-supply"], S_["SS90-supply"]
s70 = S_["SS70-eefirst"]
x = {}
for tag, s in (("NZS", nzs), ("NZE", nze), ("SSE", s80), ("SSNE", s90), ("SSS", s80s), ("SSNS", s90s), ("SSSE", s70)):
    x[f"KWp{tag}"] = f(s["kWp"]); x[f"Bat{tag}"] = f(s["bat_kWh"]); x[f"Roof{tag}"] = f(s["roof_m2"])
    x[f"SS{tag}"] = pct(s["self_sufficiency"]); x[f"Capex{tag}"] = mm(s["capex"]); x[f"NPV{tag}"] = mm(s["npv"])
    x[f"NPVImp{tag}"] = mm(s["npv_importdemand"]); x[f"NPVNB{tag}"] = mm(s["npv_netbilling"])
    x[f"Imp{tag}"] = f(s["import_MWh"]); x[f"COGross{tag}"] = f(s["co2_gross_t"]); x[f"Auto{tag}"] = f(s["autonomy_h"])
x["NZResidualBill"] = f(nze["bill1"] / 1000, 1)
x["NZKWpSave"] = f(nzs["kWp"] - nze["kWp"]); x["NZRoofSave"] = f(nzs["roof_m2"] - nze["roof_m2"])
x["NZCapexSave"] = mm(nzs["capex"] - nze["capex"]); x["NZImpSave"] = f(nzs["import_MWh"] - nze["import_MWh"])
x["SSEightyCapexSave"] = mm(s80s["capex"] - s80["capex"]); x["SSNinetyCapexSave"] = mm(s90s["capex"] - s90["capex"])
x["MaxSSE"] = pct(nz["max_ss"]["eefirst"]); x["MaxSSKWp"] = f(nz["max_ss_design"]["eefirst"]["kWp"])
x["MaxSSBat"] = f(nz["max_ss_design"]["eefirst"]["bat_kWh"])
b2 = nz["battery_marginal_200"]
x["BatMargNM"] = mm(b2["npv_nm"]); x["BatMargImp"] = mm(b2["npv_importdemand"]); x["BatMargNB"] = mm(b2["npv_netbilling"])
x["BatMargSS"] = pct(b2["ss_gain"])
x["SpecYieldHourly"] = f(nz["specific_yield_hourly"])
ns = pd.DataFrame(nz["nightload_sensitivity"])
x["NightSSLo"] = pct(ns.ss_annual_nz.min()); x["NightSSHi"] = pct(ns.ss_annual_nz.max())
out.update(x)
with open(ROOT / "manuscript/numbers.tex", "a") as fh:
    for k, v in x.items():
        fh.write(f"\\newcommand{{\\n{k}}}{{{v}}}\n")
json.dump(out, open(ROOT / "results/manuscript_numbers.json", "w"), indent=1, default=str)

# Net-zero follow-up numbers and EnergyPlus cross-validation
y = {}
be = nz["battery_breakeven_fraction"]
y["BatBENB"] = pct(1 - be["net_billing"]) if be["net_billing"] is not None else "--"
y["BatBEImp"] = pct(1 - be["import_demand"]) if be["import_demand"] is not None else "--"
y["FirstBattery"] = pct(min(nz["frontier_first_battery"].values()))
y["FirstOversizeE"] = f(100 * nz["frontier_first_oversize"]["eefirst"]); y["FirstOversizeS"] = f"{100 * nz['frontier_first_oversize']['supply']:g}"
y["SupplyLowNightCapex"] = mm(nz["ss80_supply_with_low_night_capex"])
EPV = pd.read_csv(ROOT / "results/energyplus_validation.csv").set_index("design")
main = EPV.loc[["NZ-S", "NZ-E", "SS80-S", "SS80-E", "SS90-E"]]
y["EPYield"] = f(EPV.specific_yield_ac.iloc[0]); y["PyYield"] = f(nz["specific_yield_hourly"])
y["EPYieldDiff"] = f(100 * (EPV.specific_yield_ac.iloc[0] / nz["specific_yield_hourly"] - 1), 1)
y["EPSSDiff"] = f(100 * (main.self_sufficiency - main.py_self_sufficiency).abs().max(), 1)
y["EPSSDiffBat"] = f(100 * (main[main.bat_kWh > 0].self_sufficiency - main[main.bat_kWh > 0].py_self_sufficiency).abs().max(), 1)
y["EPSSDiffNZ"] = f(100 * (main[main.bat_kWh == 0].self_sufficiency - main[main.bat_kWh == 0].py_self_sufficiency).abs().max(), 1)
y["EPNPVNZE"] = mm(EPV.loc["NZ-E-EP"].npv_resized); y["EPNPVNZS"] = mm(EPV.loc["NZ-S-EP"].npv_resized)
y["EPDCvsPy"] = f(100 * abs(EPV.loc["NZ-E"].pv_dc_MWh / EPV.loc["NZ-E"].py_pv_MWh - 1), 1)
bat = main[main.bat_kWh > 0]
y["EPImpDiffBat"] = f(100 * ((bat.import_MWh / bat.py_import_MWh - 1).abs().max()), 1)
y["EPKWpNZS"] = f(EPV.loc["NZ-S-EP"].kWp); y["EPKWpNZE"] = f(EPV.loc["NZ-E-EP"].kWp)
y["EPSSNZE"] = pct(EPV.loc["NZ-E-EP"].self_sufficiency); y["EPImpNZE"] = f(EPV.loc["NZ-E-EP"].import_MWh)
y["EPKWpSave"] = f(EPV.loc["NZ-S-EP"].kWp - EPV.loc["NZ-E-EP"].kWp)
out.update(y)
with open(ROOT / "manuscript/numbers.tex", "a") as fh:
    for k, v in y.items():
        fh.write(f"\\newcommand{{\\n{k}}}{{{v}}}\n")
json.dump(out, open(ROOT / "results/manuscript_numbers.json", "w"), indent=1, default=str)

# ---------------------------------------------------------------- additions for peer review
z = {}
_bl = r["baseline"]["excl_24h_shift"]
_t = 2.086  # Student t, 95%, n - 2 = 20 degrees of freedom
_mean = _bl["intercept"] / r["baseline"]["base_load_share_ref"]
z["IntCILo"] = f(_bl["intercept"] - _t * _bl["se_intercept"]); z["IntCIHi"] = f(_bl["intercept"] + _t * _bl["se_intercept"])
z["BaseShareLo"] = pct((_bl["intercept"] - _t * _bl["se_intercept"]) / _mean)
z["BaseShareHi"] = pct((_bl["intercept"] + _t * _bl["se_intercept"]) / _mean)
_PT = r["portfolios"]
_p4 = _PT["P4 Efficiency first + right-sized PV"]; _p3 = _PT["P3 Efficiency + PV (163.8 kWp)"]
_p2 = _PT["P2 PV only (163.8 kWp)"]; _p1 = _PT["P1 Efficiency bundle"]
z["NPVCapexOne"] = f(_p1["npv"] / _p1["capex"], 2); z["NPVCapexTwo"] = f(_p2["npv"] / _p2["capex"], 2)
z["NPVCapexThree"] = f(_p3["npv"] / _p3["capex"], 2); z["NPVCapexFour"] = f(_p4["npv"] / _p4["capex"], 2)
z["NPVCapexNZE"] = f(nze["npv"] / nze["capex"], 2)
if "prob_P4r_gt_P2" in mc:
    z["ProbFourRTwo"] = pct(mc["prob_P4r_gt_P2"]); z["ProbFourGridGE"] = pct(mc["prob_P4_grid_ge_P2"])
    z["ProbFourRCapex"] = pct(mc["prob_P4r_capex_lt_P2"])
    z["KWpFourRLo"] = f(mc["kwp_P4r"]["p5"]); z["KWpFourRHi"] = f(mc["kwp_P4r"]["p95"])
out.update(z)
with open(ROOT / "manuscript/numbers.tex", "a") as fh:
    for k, v in z.items():
        fh.write(f"\\newcommand{{\\n{k}}}{{{v}}}\n")
json.dump(out, open(ROOT / "results/manuscript_numbers.json", "w"), indent=1, default=str)

# typeset negative numbers with a true minus sign (works in text and math mode)
import re as _re  # noqa: E402
_p = ROOT / "manuscript/numbers.tex"
_p.write_text(_re.sub(r"(\\newcommand\{\\n\w+\}\{)-(?=\d)", r"\1\\ensuremath{-}", _p.read_text()))
