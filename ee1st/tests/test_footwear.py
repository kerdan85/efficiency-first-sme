"""The footwear example must reproduce the published case-study results (García Kerdan et al., 2026)."""
from pathlib import Path

import pytest

from ee1st.appraisal import monte_carlo, portfolio_table, regulatory_stress, standard_portfolios
from ee1st.case import load_case
from ee1st.core import cce, context, pv_lcoe

CASE = Path(__file__).parents[1] / "examples" / "footwear_mx" / "case.yaml"
_DATA = CASE.parent / "data"
pytestmark = pytest.mark.skipif(not ((_DATA / "billing_monthly.csv").exists() and (_DATA / "enduse_shares.csv").exists()),
                                reason="confidential footwear-plant records not present (see examples/footwear_mx/README.md)")


@pytest.fixture(scope="module")
def setup():
    c = load_case(CASE); P = c.P.central(); ctx = context(c, P)
    ports = standard_portfolios(c, P, ctx)
    return c, P, ctx, ports, portfolio_table(c, P, ctx, ports)


def test_baseline_and_tariff(setup):
    c, P, ctx, *_ = setup
    s = ctx["baseline"]["selected"]
    assert s["intercept"] == pytest.approx(25341, abs=1)
    assert s["slope"] == pytest.approx(0.54, abs=0.01)
    assert s["r2"] == pytest.approx(0.38, abs=0.01)
    assert c.ref.energy_kWh.sum() == pytest.approx(460800, abs=1)
    assert c.tariff.marginal_value() == pytest.approx(2.644, abs=0.001)
    v = c.tariff.validate(c.billing, "reported_price")
    assert v.error.abs().mean() == pytest.approx(0.022, abs=0.001)


def test_cce_and_lcoe(setup):
    c, P, ctx, *_ = setup
    exp = {"E4": 0.214, "E3": 0.815, "E2": 0.944, "E1": 1.042}
    for m, v in exp.items():
        assert cce(c, m, P, ctx)[0] == pytest.approx(v, abs=0.001)
    assert pv_lcoe(c, P, ctx)[0] == pytest.approx(0.925, abs=0.001)
    assert ctx["pv_yield"].sum() * P["pv.PR"] == pytest.approx(1526.5, abs=0.1)


def test_portfolios(setup):
    c, P, ctx, ports, T = setup
    assert ports["P4"]["pv_kWp"] == pytest.approx(94.9, abs=0.05)
    assert T.loc["P2", "npv"] == pytest.approx(3.566e6, rel=1e-3)
    assert T.loc["P4", "npv"] == pytest.approx(3.805e6, rel=1e-3)
    assert T.loc["P2", "grid_saved_frac"] == pytest.approx(0.54, abs=0.005)
    assert T.loc["P3", "grid_saved_frac"] == pytest.approx(0.76, abs=0.005)
    assert T.loc["P4", "capex"] / T.loc["P2", "capex"] - 1 == pytest.approx(-0.13, abs=0.005)
    s = regulatory_stress(c, P, ctx, ports)
    assert s["P2"] / T.loc["P2", "npv"] - 1 == pytest.approx(-0.69, abs=0.01)


@pytest.mark.slow
def test_montecarlo_close_to_paper(setup):
    c, P, ctx, ports, _ = setup
    _, s = monte_carlo(c, ports, n=1000, seed=20261014)
    assert s["prob_P4_beats_P2"] == pytest.approx(0.86, abs=0.04)


@pytest.mark.slow
def test_netzero_headline(setup):
    from ee1st.netzero import evaluate_nz, hourly_pv_per_kWp, size_pv_for_annual_nz
    c, P, ctx, ports, _ = setup
    w = hourly_pv_per_kWp(c, P)
    ee = ports["P1"]["measures"]
    k = size_pv_for_annual_nz(c, ee, P, ctx, w)
    assert k == pytest.approx(233.6, abs=0.1)
    r = evaluate_nz(c, ee, k, 0, P, ctx, w)
    assert r["npv"] == pytest.approx(6.648e6, rel=1e-3)
    assert r["self_sufficiency"] == pytest.approx(0.573, abs=0.001)
    r = evaluate_nz(c, ee, 350.4, 300, P, ctx, w)
    assert r["self_sufficiency"] >= 0.80


EXP = Path(__file__).parent / "expected"   # results files of the published case repository


def test_full_tables_match_case_repository(setup):
    """Every portfolio, measure and pathway value equals the paper's case-repository output."""
    import pandas as pd
    from ee1st.appraisal import measure_table
    from ee1st.core import pathways
    c, P, ctx, ports, T = setup
    e = pd.read_csv(EXP / "portfolios.csv")
    e.index = [s.split()[0] for s in e.portfolio]
    cols = {"bill1": "bill1", "capex": "capex", "npv": "npv", "payback_yr": "payback_yr", "grid1_MWh": "grid1_MWh",
            "co2_saved_t": "co2_saved_t", "imported_gas_avoided_GJ": "imported_gas_avoided_GJ",
            "shock_exposure1": "shock_exposure1", "billed_peak1_kW": "peak1_kW", "roof_m2": "roof_m2",
            "cost_per_t": "net_abatement_cost", "months_over_100kW": "months_over_threshold"}
    for k in e.index:
        for a, b in cols.items():
            assert T.loc[k, b] == pytest.approx(e.loc[k, a], rel=1e-9, abs=1e-6, nan_ok=True), (k, a)
    M = measure_table(c, P, ctx); em = pd.read_csv(EXP / "measures.csv").set_index("id")
    for k in em.index:
        for a in ("capex", "cce", "npv", "savings_y1", "co2_t", "payback"):
            assert M.loc[k, a] == pytest.approx(em.loc[k, a], rel=1e-9, abs=1e-6, nan_ok=True), (k, a)
    PA, _ = pathways(c, P, ctx); ep = pd.read_csv(EXP / "pathways.csv")
    for a in ("supply_kWp", "supply_npv", "ee_capex", "ee_npv", "ee_measures"):
        if a == "ee_measures":
            assert list(PA[a]) == list(ep[a])
        else:
            assert PA[a].to_numpy() == pytest.approx(ep[a].to_numpy(), rel=1e-6)
