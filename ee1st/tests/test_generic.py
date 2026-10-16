"""Generic behaviour: tariffs, parameter parsing, no double counting, synthetic example runs end to end."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ee1st.case import load_case
from ee1st.core import apply_measures, context, evaluate
from ee1st.params import parse
from ee1st.tariff import Tariff, pf_adjustment

ROOT = Path(__file__).parents[1]


def test_param_parsing():
    p = parse("x", [1, 0.5, 2]); assert (p.central, p.low, p.high, p.uncertain) == (1, 0.5, 2, True)
    p = parse("x", 3); assert not p.uncertain
    p = parse("x", {"value": [1, 0, 2], "mc": False}); assert not p.uncertain
    with pytest.raises(ValueError):
        parse("x", [3, 0, 2])


def test_pf_rule_mx():
    assert pf_adjustment(0.85, "mx_cfe") == pytest.approx(0.035)
    assert pf_adjustment(0.97, "mx_cfe") == pytest.approx(-0.018)
    assert pf_adjustment(1.0, "mx_cfe") == pytest.approx(-0.025)
    assert pf_adjustment(0.5, "none") == 0


def test_q_based_demand_tracks_energy():
    s = pd.DataFrame([dict(month="2026-01", fixed=0, energy=1.0, distribution=100, capacity=0)])
    t = Tariff({"type": "q_based_demand", "load_factor": 0.5}, s)
    b = t.bill(np.array([24 * 30 * 0.5 * 10.0]), np.array([30]), np.array([np.nan]))
    assert b[0] == pytest.approx(3600 + 10 * 100)


def test_no_double_counting():
    c = load_case(ROOT / "examples/synthetic_demand_tariff/case.yaml"); P = c.P.central(); ctx = context(c, P)
    ids = [m.id for m in c.measures]
    q, det = apply_measures(c, P, ctx["base_kWh"], ids)
    q0 = c.ref.energy_kWh.to_numpy(float)
    assert np.allclose(q0 - q, sum(det.values()))
    assert (q > 0).all()
    # bundle saves less than the sum of stand-alone savings (interaction)
    alone = sum(apply_measures(c, P, ctx["base_kWh"], [i])[1].get(i, np.zeros(12)).sum() for i in ids)
    assert (q0 - q).sum() < alone


def test_synthetic_runs(tmp_path):
    from ee1st.cli import run
    R = run(ROOT / "examples/synthetic_demand_tariff/case.yaml", out=tmp_path, mc=50, figures=False, quiet=True)
    assert set(R["portfolios"]) == {"P0", "P1", "P2", "P3", "P4"}
    assert (tmp_path / "summary.md").exists()
    # PV does not cut the measured peak under an energy+demand tariff
    assert R["portfolios"]["P2"]["peak1_kW"] == pytest.approx(R["portfolios"]["P0"]["peak1_kW"])
    assert R["stress"] == {}


def test_template_loads_shape():
    import yaml
    cfg = yaml.safe_load((ROOT / "src/ee1st/template/case.yaml").read_text())
    for k in ("case", "data", "tariff", "measures", "pv"):
        assert k in cfg
