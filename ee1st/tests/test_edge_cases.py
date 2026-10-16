"""Inputs a new user is likely to give (found in the independent audit)."""
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from ee1st.case import load_case
from ee1st.core import context, evaluate, pathways

ROOT = Path(__file__).parents[1]


def _copy(tmp_path, example, edit):
    d = tmp_path / example
    shutil.copytree(ROOT / "examples" / example, d, ignore=shutil.ignore_patterns("results"))
    cfg = yaml.safe_load((d / "case.yaml").read_text()); edit(cfg, d)
    (d / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    return d / "case.yaml"


def test_short_horizon(tmp_path):
    p = _copy(tmp_path, "synthetic_demand_tariff", lambda c, d: c["finance"].update(horizon_yr=10))
    c = load_case(p); P = c.P.central(); r = evaluate(c, {"pv_kWp": 100}, P, context(c, P))
    assert np.isfinite(r["npv"])


def test_no_energy_measures(tmp_path):
    p = _copy(tmp_path, "synthetic_demand_tariff", lambda c, d: c.update(measures=[]))
    c = load_case(p); P = c.P.central(); PA, order = pathways(c, P, context(c, P))
    assert order == [] and (PA.ee_kWp > 0).all()


def test_energy_demand_peak_consistent_with_marginal_value(tmp_path):
    p = _copy(tmp_path, "synthetic_demand_tariff", lambda c, d: None)
    c = load_case(p); P = c.P.central(); ctx = context(c, P)
    r0 = evaluate(c, {}, P, ctx); r1 = evaluate(c, {"measures": ["L1"]}, P, ctx)
    value_per_kWh = (r0["bill1"] - r1["bill1"]) / ((r0["grid1_MWh"] - r1["grid1_MWh"]) * 1000)
    assert value_per_kWh == pytest.approx(c.tariff.marginal_value(), rel=0.02)
    assert r1["months_over_threshold"] is None or r1["months_over_threshold"] >= 0


def test_threshold_counts_measured_peak(tmp_path):
    p = _copy(tmp_path, "synthetic_demand_tariff", lambda c, d: c["security"].update(demand_threshold_kW=100))
    c = load_case(p); P = c.P.central(); r = evaluate(c, {}, P, context(c, P))
    assert r["months_over_threshold"] == 12


def test_flat_tariff_without_demand_or_pf(tmp_path):
    def edit(c, d):
        c["tariff"] = {"type": "flat", "charges": {"fixed": 0, "energy": 0.2}, "pf_rule": "none"}
        b = pd.read_csv(d / "data/billing_monthly.csv").drop(columns=["max_demand_kW", "power_factor"])
        b.to_csv(d / "data/billing_monthly.csv", index=False)
    c = load_case(_copy(tmp_path, "synthetic_demand_tariff", edit)); P = c.P.central()
    r = evaluate(c, {"measures": ["A1"]}, P, context(c, P))
    assert r["savings_y1"] == pytest.approx(r["ee_saved_MWh"] * 1000 * 0.2)


def test_clear_errors(tmp_path):
    p = _copy(tmp_path, "synthetic_demand_tariff", lambda c, d: c["measures"][0].pop("life"))
    with pytest.raises(ValueError, match="missing"):
        load_case(p)
    p = _copy(tmp_path / "b", "synthetic_demand_tariff", lambda c, d: c["tariff"].update(current_month="1999-01"))
    with pytest.raises(ValueError, match="current_month"):
        load_case(p)


def test_base_load_fallback_warns(tmp_path):
    p = _copy(tmp_path, "synthetic_demand_tariff", lambda c, d: c.update(baseline={}))
    c = load_case(p); P = c.P.central()
    with pytest.warns(UserWarning, match="base load"):
        context(c, P)
