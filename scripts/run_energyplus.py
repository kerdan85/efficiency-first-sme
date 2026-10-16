"""Cross-validation of the net-zero designs with EnergyPlus 25.1.

For each design the script writes an EPW weather file (NASA POWER 2023 hourly,
rescaled to the 2001-2025 climatology and shifted from local solar to local
standard time), an hourly load schedule identical to the Python model, and an
IDF with Generator:PVWatts, ElectricLoadCenter:Inverter:PVWatts and
ElectricLoadCenter:Storage:Simple (AC-coupled, TrackFacilityElectricDemandStoreExcessOnSite).
EnergyPlus hourly purchased/surplus electricity is then passed through the same
net-metering bank and GDMTO tariff as the Python model.

Requires EnergyPlus 25.1 (https://github.com/NREL/EnergyPlus/releases/tag/v25.1.0);
set EPLUS_DIR to its installation folder.
"""
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from efirst.hourly import hourly_load, hourly_pv_per_kWp, monthly_net_metering, nz_central  # noqa: E402
from efirst.model import RAW, load_all, measure_savings, monthly_bill  # noqa: E402
from efirst.params import HOURS_OPERATING_PER_MONTH, central  # noqa: E402

EPLUS = Path(os.environ.get("EPLUS_DIR", "/home/claude/eplus/EnergyPlus-25.1.0-68a4a7c774-Linux-Ubuntu22.04-x86_64"))
WORK = ROOT / "energyplus"; WORK.mkdir(exist_ok=True)
LAT, LON, TZ, ELEV = 20.0965, -98.7624, -6.0, 2338.0

P = central(); NZ = nz_central(); D = load_all(P); W = hourly_pv_per_kWp(P)
nzres = json.load(open(ROOT / "results/netzero.json"))
EE = ["E4", "E1", "E2", "E3", "E5"]
DESIGNS = {
    "NZ-S": (["E5"], nzres["scenarios"]["NZ-S annual, supply only"]),
    "NZ-E": (EE, nzres["scenarios"]["NZ-E annual, efficiency first"]),
    "SS80-S": (["E5"], nzres["scenarios"]["SS80-supply"]),
    "SS80-E": (EE, nzres["scenarios"]["SS80-eefirst"]),
    "SS90-E": (EE, nzres["scenarios"]["SS90-eefirst"]),
}


# ----------------------------------------------------------------------------- weather
def write_epw(path: Path):
    w = pd.read_csv(RAW / "nasa_power_hourly_2023_pachuca.csv", parse_dates=["timestamp_LST"])
    clim = pd.read_csv(RAW / "nasa_power_climatology_pachuca.csv").set_index("month")
    t = w.timestamp_LST
    doy = t.dt.dayofyear.to_numpy(); hr = t.dt.hour.to_numpy() + 0.5 + (7 + LON / 15)  # UTC-7 labels -> solar time
    dec = np.radians(23.45 * np.sin(np.radians(360 * (284 + doy) / 365)))
    om = np.radians(15 * (hr - 12)); phi = math.radians(LAT)
    cosz = np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(om)
    ghi = w.GHI_Wm2.to_numpy(float); dhi = np.minimum(w.DHI_Wm2.to_numpy(float), ghi)
    month = t.dt.month
    g23 = w.groupby(month).GHI_Wm2.sum() / w.groupby(month).size() * 24 / 1000
    fac = month.map(clim.GHI_kWh_m2_d / g23).to_numpy()
    ghi = ghi * fac; dhi = dhi * fac
    dni = np.where(cosz > 0.087, (ghi - dhi) / np.maximum(cosz, 0.087), 0.0)
    dni = np.clip(dni, 0, 1100)
    dhi = np.where(cosz > 0.087, dhi, ghi)
    # NASA POWER "LST" labels are UTC-7 here (UTC + round(lon/15)); local standard time is UTC-6
    shift_h = np.ones(len(ghi), dtype=int)
    n = len(ghi)
    idx_std = (np.arange(n) + shift_h) % n
    arr = np.zeros((n, 4)); tdb = w.T2M_C.to_numpy(float)
    for i in range(n):
        j = idx_std[i]
        arr[j] = (ghi[i], dni[i], dhi[i], tdb[i])
    rh = 60.0
    a, b_ = 17.27, 237.7
    lines = [
        f"LOCATION,Pachuca de Soto (NASA POWER 2023 rescaled),HID,MEX,NASA-POWER,000000,{LAT:.3f},{LON:.3f},{TZ:.1f},{ELEV:.0f}",
        "DESIGN CONDITIONS,0", "TYPICAL/EXTREME PERIODS,0", "GROUND TEMPERATURES,0",
        "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
        "COMMENTS 1,Synthesised from NASA POWER hourly 2023 (GHI DHI T2M; UTC-7 labels shifted to UTC-6) rescaled monthly to 2001-2025 climatology",
        "COMMENTS 2,RH 60% and wind 2 m/s constant; pressure from elevation; DNI from GHI-DHI and solar geometry",
        "DATA PERIODS,1,1,Data,Sunday, 1/ 1,12/31",
    ]
    p_atm = 101325 * (1 - 2.25577e-5 * ELEV) ** 5.25588
    for i in range(n):
        ts = pd.Timestamp("2023-01-01") + pd.Timedelta(hours=i)
        g, dn, df, tt = arr[i]
        gam = a * tt / (b_ + tt) + math.log(rh / 100)
        tdp = b_ * gam / (a - gam)
        lines.append(f"2023,{ts.month},{ts.day},{ts.hour + 1},0,?9?9?9?9E0?9?9?9?9?9?9?9?9?9?9?9?9*9*9?9?9?9,"
                     f"{tt:.1f},{tdp:.1f},{rh:.0f},{p_atm:.0f},9999,9999,9999,{g:.0f},{dn:.0f},{df:.0f},"
                     f"999999,999999,999999,9999,180,2.0,5,5,9999,99999,9,999999999,999,0.999,999,99,999,999,99")
    path.write_text("\n".join(lines) + "\n")


# ----------------------------------------------------------------------------- IDF
def idf_text(name, kWp, bat_kWh):
    usable_J = bat_kWh * NZ["bat_dod"] * 3.6e6
    pmax_W = bat_kWh * NZ["bat_c_rate"] * 1000
    eta = math.sqrt(NZ["bat_rte"])
    s = f"""
Version,25.1;
SimulationControl,No,No,No,No,Yes,No,1;
Building,{name},0,Suburbs,0.04,0.4,FullExterior,25,6;
Timestep,4;
RunPeriod,Year,1,1,2023,12,31,2023,Sunday,No,No,No,Yes,Yes;
GlobalGeometryRules,UpperLeftCorner,Counterclockwise,World;
ScheduleTypeLimits,Any,,,Continuous;
Schedule:Constant,AlwaysOn,Any,1;
Material,Panel,MediumRough,0.10,0.5,800,900;
Construction,Wall,Panel;
Zone,Plant;
BuildingSurface:Detailed,Floor,Floor,Wall,Plant,,Adiabatic,,NoSun,NoWind,,4,0,0,0,0,10,0,10,10,0,10,0,0;
BuildingSurface:Detailed,Roof,Roof,Wall,Plant,,Adiabatic,,NoSun,NoWind,,4,0,0,4,10,0,4,10,10,4,0,10,4;
BuildingSurface:Detailed,S,Wall,Wall,Plant,,Adiabatic,,NoSun,NoWind,,4,0,0,4,0,0,0,10,0,0,10,0,4;
BuildingSurface:Detailed,E,Wall,Wall,Plant,,Adiabatic,,NoSun,NoWind,,4,10,0,4,10,0,0,10,10,0,10,10,4;
BuildingSurface:Detailed,N,Wall,Wall,Plant,,Adiabatic,,NoSun,NoWind,,4,10,10,4,10,10,0,0,10,0,0,10,4;
BuildingSurface:Detailed,W,Wall,Wall,Plant,,Adiabatic,,NoSun,NoWind,,4,0,10,4,0,10,0,0,0,0,0,0,4;
Schedule:File,PlantLoad,Any,load_{name}.csv,1,1,8760,Comma,No,60,No;
Exterior:FuelEquipment,ProcessLoad,Electricity,PlantLoad,1,Process;
"""
    if kWp > 0:
        s += f"""
Generator:PVWatts,PV,5,{kWp * 1000:.0f},Standard,FixedRoofMounted,0.14,TiltAzimuth,20,180,,0.4;
ElectricLoadCenter:Generators,PVList,PV,Generator:PVWatts,{kWp * 1000:.0f},AlwaysOn,;
ElectricLoadCenter:Inverter:PVWatts,Inverter,1.10,0.96;
"""
        if bat_kWh > 0:
            s += f"""
ElectricLoadCenter:Storage:Simple,Battery,AlwaysOn,,0,{eta:.4f},{eta:.4f},{usable_J:.0f},{pmax_W:.0f},{pmax_W:.0f},{0.5 * usable_J:.0f};
ElectricLoadCenter:Distribution,LC,PVList,Baseload,,,,DirectCurrentWithInverterACStorage,Inverter,Battery,,TrackFacilityElectricDemandStoreExcessOnSite,,,1.0,0.0,,,,,,;
"""
        else:
            s += "ElectricLoadCenter:Distribution,LC,PVList,Baseload,,,,DirectCurrentWithInverter,Inverter,,,,,,,,,,,,,;\n"
    s += """
Output:Meter,ElectricityPurchased:Facility,Hourly;
Output:Meter,ElectricitySurplusSold:Facility,Hourly;
Output:Meter,Electricity:Facility,Hourly;
Output:Variable,*,Inverter AC Output Electricity Energy,Hourly;
Output:Variable,*,Generator Produced DC Electricity Energy,Hourly;
OutputControl:Table:Style,Comma;
Output:Diagnostics,DisplayExtraWarnings;
"""
    return s


def run_design(name, measures, kWp, bat):
    d = WORK / name; d.mkdir(exist_ok=True)
    ref = D["ref"]
    meas = [m for m in measures if m != "E5"]
    q_ee, det = measure_savings(ref, P, D["intercept"], meas)
    months = ref.mon.to_numpy()
    h_month = np.array([(W.month == m).sum() for m in months])
    nonop = h_month - HOURS_OPERATING_PER_MONTH * h_month / 730
    night = np.full(12, NZ["night_load_kW"])
    if "E4" in det:
        night = np.maximum(night - det["E4"] / nonop, 0.3 * NZ["night_load_kW"])
    load = hourly_load(q_ee, months, W, night)  # kW, calendar hours of 2023 (local time)
    pd.DataFrame({"W": load * 1000}).to_csv(d / f"load_{name}.csv", index=False)
    (d / "in.idf").write_text(idf_text(name, kWp, bat))
    epw = WORK / "pachuca_nasa2023.epw"
    res = subprocess.run([str(EPLUS / "energyplus"), "-w", str(epw), "-d", str(d), "-r", str(d / "in.idf")],
                         capture_output=True, text=True, cwd=d)
    if res.returncode != 0:
        raise RuntimeError(res.stdout[-2000:] + res.stderr[-2000:])
    m = pd.read_csv(d / "eplusmtr.csv")
    imp = m.filter(like="ElectricityPurchased").iloc[:, 0].to_numpy() / 3.6e6
    exp = m.filter(like="ElectricitySurplusSold").iloc[:, 0].to_numpy() / 3.6e6
    v = pd.read_csv(d / "eplusout.csv")
    ac = v.filter(like="Inverter AC Output").sum(axis=1).to_numpy() / 3.6e6 if kWp > 0 else np.zeros(len(imp))
    dc = v.filter(like="Produced DC").sum(axis=1).to_numpy() / 3.6e6 if kWp > 0 else np.zeros(len(imp))
    mh = W.month.to_numpy()
    q_net, expired, _ = monthly_net_metering(imp, exp, mh, list(months) * 5, NZ)
    q_net = q_net[-12:]
    pf1 = np.full(12, P["pfc_pf_after"])
    bill = float(np.sum(monthly_bill(q_net, ref.days.to_numpy(), pf1, D["tariff"])))
    warn = (d / "eplusout.err").read_text().count("** Warning **")
    return dict(design=name, kWp=kWp, bat_kWh=bat, load_MWh=load.sum() / 1000, pv_dc_MWh=dc.sum() / 1000,
                pv_ac_MWh=ac.sum() / 1000, specific_yield_ac=ac.sum() / kWp if kWp else 0.0,
                import_MWh=imp.sum() / 1000, export_MWh=exp.sum() / 1000,
                self_sufficiency=1 - imp.sum() / load.sum(), bill=bill, eplus_warnings=warn)


if __name__ == "__main__":
    write_epw(WORK / "pachuca_nasa2023.epw")
    rows = []
    for name, (meas, sc) in DESIGNS.items():
        r = run_design(name, meas, float(sc["kWp"]), float(sc["bat_kWh"]))
        r.update(py_pv_MWh=sc["pv_MWh"], py_import_MWh=sc["import_MWh"], py_export_MWh=sc["export_MWh"],
                 py_self_sufficiency=sc["self_sufficiency"], py_bill=sc["bill1"])
        rows.append(r)
        print(name, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
    # re-size the annual net-zero arrays with the EnergyPlus (PVWatts) yield
    for name in ("NZ-S", "NZ-E"):
        r0 = next(r for r in rows if r["design"] == name)
        meas, sc = DESIGNS[name]
        k2 = r0["kWp"] * r0["load_MWh"] / r0["pv_ac_MWh"]
        r = run_design(name + "-EP", meas, float(k2), 0.0)
        r.update(py_pv_MWh=np.nan, py_import_MWh=np.nan, py_export_MWh=np.nan, py_self_sufficiency=np.nan, py_bill=np.nan)
        # NPV with the EnergyPlus-sized array: both models give a bill equal to the fixed charge at annual net zero
        from efirst.hourly import evaluate_nz
        r["npv_resized"] = evaluate_nz(meas, float(k2), 0.0, P, NZ, D, W)["npv"]
        r["bill_python_at_resized"] = evaluate_nz(meas, float(k2), 0.0, P, NZ, D, W)["bill1"]
        rows.append(r)
        print(r["design"], {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "results/energyplus_validation.csv", index=False)
