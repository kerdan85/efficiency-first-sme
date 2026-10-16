"""Net-zero scenarios: annual net zero under net metering and hourly self-sufficiency with storage."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from efirst.hourly import NZ_PARAMS, evaluate_nz, hourly_pv_per_kWp, nz_central, size_pv_for_annual_nz  # noqa: E402
from efirst.model import load_all  # noqa: E402
from efirst.params import central  # noqa: E402

P = central(); NZ = nz_central(); D = load_all(P); W = hourly_pv_per_kWp(P)
EE = ["E4", "E1", "E2", "E3", "E5"]
SETS = {"supply": ["E5"], "eefirst": EE}
DG_LIMIT_KWP = 700.0
MULTS = [round(x, 2) for x in np.arange(0.6, 2.41, 0.1)]
BATS = list(range(0, 2401, 100))
out = {"dg_limit_kWp": DG_LIMIT_KWP, "specific_yield_hourly": float(W.pv_kWh_per_kWp.sum())}

# --- sweep PV size x battery size
rows = []
for lab, meas in SETS.items():
    k_nz = size_pv_for_annual_nz(meas, P, NZ, D, W)
    out[f"kWp_nz_{lab}"] = float(k_nz)
    for mult in MULTS:
        kwp = min(k_nz * mult, DG_LIMIT_KWP)
        for bat in BATS:
            r = evaluate_nz(meas, kwp, bat, P, NZ, D, W)
            r_imp = evaluate_nz(meas, kwp, bat, P, NZ, D, W, demand_basis="imports")
            r_nb = evaluate_nz(meas, kwp, bat, P, NZ, D, W, tariff_mode="net_billing")
            rows.append(dict(set=lab, pv_mult=mult, kWp=kwp, bat_kWh=bat, roof_m2=kwp * P["pv_m2_per_kWp"],
                             self_sufficiency=r["self_sufficiency"], net_annual_MWh=r["net_annual_MWh"],
                             import_MWh=r["import_MWh"], export_MWh=r["export_MWh"], load_MWh=r["load_MWh"],
                             co2_gross_t=r["co2_gross_t"], co2_net_t=r["co2_net_t"], capex=r["capex"],
                             npv_nm=r["npv"], npv_nm_importdemand=r_imp["npv"], npv_netbilling=r_nb["npv"],
                             bill_nm=r["bill1"], night_kW=r["night_kW"], autonomy_h=r["autonomy_h"],
                             peak_load_kW=r["peak_load_kW"]))
S = pd.DataFrame(rows)
S.to_csv(ROOT / "results/netzero_sweep.csv", index=False)
front = []
for lab in SETS:
    for tgt in np.arange(0.50, 0.951, 0.025):
        sub = S[(S.set == lab) & (S.self_sufficiency >= tgt - 1e-9)]
        if len(sub):
            b = sub.sort_values("capex").iloc[0]
            front.append(dict(set=lab, target=round(float(tgt), 3), capex=b.capex, kWp=b.kWp, bat_kWh=b.bat_kWh,
                              npv_nm=b.npv_nm, npv_netbilling=b.npv_netbilling, roof_m2=b.roof_m2))
pd.DataFrame(front).to_csv(ROOT / "results/netzero_frontier.csv", index=False)

# --- headline scenarios
def pick(lab, kwp, bat):
    r = evaluate_nz(SETS[lab], kwp, bat, P, NZ, D, W)
    r2 = evaluate_nz(SETS[lab], kwp, bat, P, NZ, D, W, demand_basis="imports")
    r3 = evaluate_nz(SETS[lab], kwp, bat, P, NZ, D, W, tariff_mode="net_billing")
    r.update(kWp=kwp, bat_kWh=bat, roof_m2=kwp * P["pv_m2_per_kWp"], npv_importdemand=r2["npv"],
             npv_netbilling=r3["npv"], bill_importdemand=r2["bill1"], bill_netbilling=r3["bill1"])
    return r

sc = {}
sc["NZ-S annual, supply only"] = pick("supply", out["kWp_nz_supply"], 0)
sc["NZ-E annual, efficiency first"] = pick("eefirst", out["kWp_nz_eefirst"], 0)
# least-capex designs reaching self-sufficiency targets
for tgt in (0.70, 0.80, 0.90):
    for lab in SETS:
        sub = S[(S.set == lab) & (S.self_sufficiency >= tgt)]
        if len(sub):
            best = sub.sort_values("capex").iloc[0]
            sc[f"SS{int(tgt*100)}-{lab}"] = pick(lab, float(best.kWp), float(best.bat_kWh))
        else:
            sc[f"SS{int(tgt*100)}-{lab}"] = None
out["scenarios"] = {k: v for k, v in sc.items()}
out["max_ss"] = {lab: float(S[S.set == lab].self_sufficiency.max()) for lab in SETS}
out["max_ss_design"] = {lab: S[S.set == lab].sort_values("self_sufficiency").iloc[-1][["kWp", "bat_kWh"]].to_dict() for lab in SETS}
# battery value per kWh under each regime for the EE-first NZ design (marginal 200 kWh)
base = sc["NZ-E annual, efficiency first"]
b200 = pick("eefirst", out["kWp_nz_eefirst"], 200)
out["battery_marginal_200"] = dict(npv_nm=b200["npv"] - base["npv"],
                                   npv_importdemand=b200["npv_importdemand"] - base["npv_importdemand"],
                                   npv_netbilling=b200["npv_netbilling"] - base["npv_netbilling"],
                                   ss_gain=b200["self_sufficiency"] - base["self_sufficiency"])
# battery break-even cost (fraction of central cost) for +200 kWh on the efficiency-first NZ design
be = {}
for regime, kw in (("net_metering", {}), ("import_demand", {"demand_basis": "imports"}), ("net_billing", {"tariff_mode": "net_billing"})):
    found = None
    for frac in np.arange(1.0, -0.001, -0.05):
        NZf = dict(NZ); NZf["bat_cost_per_kWh"] = NZ["bat_cost_per_kWh"] * frac
        r0 = evaluate_nz(EE, out["kWp_nz_eefirst"], 0, P, NZf, D, W, **kw)
        r1 = evaluate_nz(EE, out["kWp_nz_eefirst"], 200, P, NZf, D, W, **kw)
        if r1["npv"] - r0["npv"] >= 0:
            found = float(frac); break
    be[regime] = found
out["battery_breakeven_fraction"] = be
# smallest self-sufficiency at which the frontier needs storage, and first PV oversizing
F = pd.read_csv(ROOT / "results/netzero_frontier.csv")
out["frontier_first_battery"] = {lab: float(F[(F.set == lab) & (F.bat_kWh > 0)].target.min()) for lab in SETS}
out["frontier_first_oversize"] = {lab: float(F[(F.set == lab) & (F.kWp > out[f"kWp_nz_{lab}"] * 1.05)].target.min()) for lab in SETS}
# decomposition of the efficiency-first capex advantage at 80 %: supply-only with the lower night load
NZl = dict(NZ); NZl["night_load_kW"] = float(sc["NZ-E annual, efficiency first"]["night_kW"])
best = None
for mult in MULTS:
    for bat in BATS:
        kwp = min(out["kWp_nz_supply"] * mult, DG_LIMIT_KWP)
        r = evaluate_nz(SETS["supply"], kwp, bat, P, NZl, D, W)
        if r["self_sufficiency"] >= 0.80 and (best is None or r["capex"] < best):
            best = r["capex"]
out["ss80_supply_with_low_night_capex"] = best

# sensitivity to the always-on night load
sens = []
for n in (8.0, 15.0, 25.0):
    NZn = dict(NZ); NZn["night_load_kW"] = n
    for lab in SETS:
        sub = []
        for bat in BATS:
            for mult in MULTS:
                kwp = min(out[f"kWp_nz_{lab}"] * mult, DG_LIMIT_KWP)
                r = evaluate_nz(SETS[lab], kwp, bat, P, NZn, D, W)
                sub.append((r["capex"], r["self_sufficiency"], kwp, bat))
        ok = [s for s in sub if s[1] >= 0.80]
        best = min(ok) if ok else (np.nan, max(s[1] for s in sub), np.nan, np.nan)
        sens.append(dict(night_kW=n, set=lab, capex_ss80=best[0], kWp=best[2], bat_kWh=best[3],
                         ss_annual_nz=evaluate_nz(SETS[lab], out[f"kWp_nz_{lab}"], 0, P, NZn, D, W)["self_sufficiency"]))
pd.DataFrame(sens).to_csv(ROOT / "results/netzero_nightload_sensitivity.csv", index=False)
out["nightload_sensitivity"] = sens
json.dump(out, open(ROOT / "results/netzero.json", "w"), indent=1, default=float)
for k, v in sc.items():
    if v is None:
        print(k, "not reachable"); continue
    print(k, {x: round(float(v[x]), 2) for x in ["kWp", "bat_kWh", "roof_m2", "self_sufficiency", "net_annual_MWh",
                                                  "import_MWh", "co2_gross_t", "co2_net_t", "capex", "npv",
                                                  "npv_importdemand", "npv_netbilling", "bill1", "autonomy_h"]})
print("max_ss", out["max_ss"], out["max_ss_design"])
print("battery marginal", out["battery_marginal_200"])
print(pd.DataFrame(sens))
