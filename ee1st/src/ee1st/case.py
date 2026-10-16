"""Load a case file (YAML) and its data into a Case object."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .params import ParamSet
from .tariff import Tariff


@dataclass
class Measure:
    id: str
    name: str
    type: str                  # base_load | enduse | pf_correction
    end_uses: list = field(default_factory=list)
    capex_mode: str = "fixed"  # fixed | units_from_energy


@dataclass
class Case:
    cfg: dict
    root: Path
    billing: pd.DataFrame
    ref: pd.DataFrame
    tariff: Tariff
    shares: dict
    climate: pd.DataFrame
    measures: list
    P: ParamSet
    weather_hourly: pd.DataFrame | None = None

    @property
    def currency(self):
        return self.cfg["case"].get("currency", "")


def _days(month_series):
    return pd.to_datetime(month_series).dt.days_in_month


def load_case(path: str | Path) -> Case:
    path = Path(path)
    cfg = yaml.safe_load(path.read_text())
    root = path.parent
    d = cfg["data"]
    b = pd.read_csv(root / d["billing"], dtype={"month": str})
    for col in ("month", "energy_kWh"):
        if col not in b.columns:
            raise ValueError(f"{d['billing']}: missing required column '{col}'")
    for col in ("power_factor", "max_demand_kW"):
        if col not in b.columns:
            b[col] = np.nan
    b["days"] = _days(b.month); b["mon"] = pd.to_datetime(b.month).dt.month
    ry = d["reference_year"]
    ref = b[(b.month >= str(ry["start"])) & (b.month <= str(ry["end"]))].reset_index(drop=True)
    if len(ref) != 12:
        raise ValueError(f"reference year must contain 12 months, found {len(ref)}")
    sched = pd.read_csv(root / cfg["tariff"]["schedule"], dtype={"month": str}) if "schedule" in cfg["tariff"] \
        else pd.DataFrame([dict(month=ref.month.iloc[-1], **cfg["tariff"]["charges"])])
    cur = str(cfg["tariff"].get("current_month", sched.month.iloc[-1]))
    if cur not in set(sched.month):
        raise ValueError(f"tariff.current_month {cur} not found in the tariff schedule")
    tariff = Tariff(cfg["tariff"], sched)
    if tariff.type == "energy_demand" and ref.max_demand_kW.isna().any():
        raise ValueError("energy_demand tariff needs max_demand_kW for every reference-year month")
    if tariff.type not in ("q_based_demand", "energy_demand", "flat"):
        raise ValueError(f"unknown tariff type {tariff.type}")
    sh = pd.read_csv(root / d["enduse_shares"])
    shares = dict(zip(sh.end_use, sh.share))
    if abs(sum(shares.values()) - 1) > 0.01:
        raise ValueError("end-use shares must sum to 1")
    clim = pd.read_csv(root / d["climate_monthly"])
    wh = None
    if d.get("weather_hourly"):
        wh = pd.read_csv(root / d["weather_hourly"], parse_dates=["timestamp"])

    P = ParamSet()
    fin = cfg.get("finance", {})
    P.add("finance.discount_rate", fin.get("discount_rate", 0.08))
    P.add("finance.horizon_yr", fin.get("horizon_yr", 20))
    P.add("finance.tariff_real_escalation", fin.get("tariff_real_escalation", 0.0))
    g = cfg.get("grid", {})
    P.add("grid.emission_factor", g.get("emission_factor_t_per_MWh", 0.0), "official")
    P.add("grid.gas_share", g.get("gas_share_generation", 0.0), "official")
    P.add("grid.heat_rate", g.get("heat_rate_GJ_per_MWh", 7.2))
    P.add("grid.import_share", g.get("gas_import_share", 0.0))
    measures = []
    for m in cfg.get("measures", []):
        mid = m["id"]
        if m.get("type") not in ("base_load", "enduse", "pf_correction"):
            raise ValueError(f"measure {mid}: type must be base_load, enduse or pf_correction")
        need = ["life", "pf_after"] if m["type"] == "pf_correction" else ["life", "saving_frac"]
        need.append("capex_per_unit" if "capex_per_unit" in m else "capex")
        if "capex_per_unit" in m:
            need += ["unit_kW", "hours_per_month"]
        miss = [k for k in need if k not in m]
        if miss:
            raise ValueError(f"measure {mid}: missing {miss}")
        if m["type"] == "pf_correction" and ref.power_factor.isna().any() and cfg["tariff"].get("pf_rule", "none") != "none":
            raise ValueError(f"measure {mid}: power-factor correction needs a power_factor column in the bills")
        lv = m["life"]["value"] if isinstance(m["life"], dict) else m["life"]
        if min(lv if isinstance(lv, list) else [lv]) < 1 or any(float(x) != int(x) for x in (lv if isinstance(lv, list) else [lv])):
            raise ValueError(f"measure {mid}: life must be a whole number of years >= 1")
        mm = Measure(mid, m.get("name", mid), m["type"], m.get("end_uses", []))
        for k in ("saving_frac", "share_of_enduse", "capex", "om", "life", "pf_after", "capex_per_unit", "unit_kW",
                  "hours_per_month"):
            if k in m:
                P.add(f"measures.{mid}.{k}", m[k])
        if "capex_per_unit" in m:
            mm.capex_mode = "units_from_energy"
        if mm.type == "enduse":
            missing = [e for e in mm.end_uses if e not in shares]
            if missing:
                raise ValueError(f"measure {mid}: unknown end uses {missing}")
            if f"measures.{mid}.share_of_enduse" not in P.params:
                P.add(f"measures.{mid}.share_of_enduse", 1.0)
        if f"measures.{mid}.om" not in P.params:
            P.add(f"measures.{mid}.om", 0.0)
        measures.append(mm)
    pv = cfg.get("pv", {})
    for k, default in (("cost_per_W", 1.0), ("PR", 0.8), ("tilt_deg", 20), ("albedo", 0.2), ("degradation", 0.005),
                       ("om_frac", 0.01), ("inverter_repl_frac", 0.1), ("inverter_repl_year", 12), ("life", 25),
                       ("m2_per_kWp", 5.5), ("demand_credit", {"value": 1.0, "mc": False})):
        P.add(f"pv.{k}", pv.get(k, default))
    nz = cfg.get("netzero", {})
    for k, default in (("night_load_kW", 10.0), ("bat_cost_per_kWh", 8500.0), ("bat_rte", 0.85), ("bat_dod", 0.9),
                       ("bat_c_rate", 0.5), ("bat_om_frac", 0.025), ("bat_life", 15), ("expired_credit_value", 0.0),
                       ("net_billing_export_value", 1.0)):
        P.add(f"netzero.{k}", nz.get(k, default))
    return Case(cfg, root, b, ref, tariff, shares, clim, measures, P, wh)
