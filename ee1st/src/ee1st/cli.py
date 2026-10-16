"""Command line: ``ee1st run case.yaml [--out DIR] [--mc N] [--no-netzero]``  and  ``ee1st init DIR``."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import __version__
from .appraisal import measure_table, parameter_table, monte_carlo, oneway, portfolio_table, regulatory_stress, standard_portfolios, thermal
from .case import load_case
from .core import context, pathways
from .report import dump_json, fig_merit_order, fig_netzero, fig_pathways, markdown_summary


def run(case_path, out=None, mc=None, netzero=True, figures=True, quiet=False):
    say = (lambda *a: None) if quiet else (lambda *a: print(*a, file=sys.stderr))
    case = load_case(case_path)
    out = Path(out or Path(case_path).parent / "results"); out.mkdir(parents=True, exist_ok=True)
    P = case.P.central(); ctx = context(case, P); cur = case.currency
    say(f"[ee1st] {case.cfg['case']['name']}: deterministic appraisal")
    R = dict(case=case.cfg["case"]["name"], version=__version__, ref_MWh=float(case.ref.energy_kWh.sum() / 1000))
    R["baseline"] = ctx["baseline"]
    R["base_share"] = ctx["base_kWh"] / case.ref.energy_kWh.mean()
    R["tariff"] = dict(marginal=case.tariff.marginal_value())
    pc = case.cfg["tariff"].get("validation_price_column")
    if pc and pc in case.billing.columns and case.billing[pc].notna().any():
        v = case.tariff.validate(case.billing.dropna(subset=[pc]), pc); v.to_csv(out / "tariff_validation.csv", index=False)
        R["tariff"].update(validation_mean_error=float(v.error.mean()), validation_mae=float(v.error.abs().mean()))
    M = measure_table(case, P, ctx); M.to_csv(out / "measures.csv")
    ports = standard_portfolios(case, P, ctx)
    T = portfolio_table(case, P, ctx, ports); T.to_csv(out / "portfolios.csv")
    R["bill0"] = float(T.loc["P0", "bill0"])
    R["portfolio_definitions"] = ports
    R["measures"] = M.to_dict(orient="index"); R["portfolios"] = T.to_dict(orient="index")
    R["stress"] = regulatory_stress(case, P, ctx, ports)
    PA, order = pathways(case, P, ctx); PA.to_csv(out / "pathways.csv", index=False); R["merit_order"] = order
    oneway(case, ports).to_csv(out / "sensitivity_oneway.csv", index=False)
    th = thermal(case, P)
    if th is not None:
        th.to_csv(out / "thermal.csv"); R["thermal"] = th.to_dict(orient="index")
    n = mc if mc is not None else case.cfg.get("montecarlo", {}).get("n", 1000)
    if n:
        say(f"[ee1st] Monte Carlo, {n} draws")
        MC, s = monte_carlo(case, ports, n=n); MC.to_csv(out / "montecarlo.csv.gz", index=False); R["montecarlo"] = s
    if netzero and case.weather_hourly is not None and "netzero" in case.cfg:
        from .netzero import run_netzero
        say("[ee1st] net-zero sweep (hourly)")
        pfc = [m.id for m in case.measures if m.type == "pf_correction"]
        sets = {"supply": pfc, "eefirst": [m.id for m in case.measures]}
        NZ = run_netzero(case, P, ctx, sets, progress=lambda s: say(f"        {s} done"))
        NZ["sweep"].to_csv(out / "netzero_sweep.csv", index=False); NZ["frontier"].to_csv(out / "netzero_frontier.csv", index=False)
        R["netzero_summary"] = NZ["summary"]; R["netzero"] = NZ["designs"]
        NZ["nightload"].to_csv(out / "netzero_nightload_sensitivity.csv", index=False)
        R["netzero_nightload"] = NZ["nightload"].to_dict(orient="records")
        if figures and len(NZ["frontier"]):
            fig_netzero(NZ["frontier"], cur, out / "fig_netzero.pdf")
    if figures:
        fig_merit_order(M, case.tariff.marginal_value(), cur, out / "fig_merit_order.pdf")
        fig_pathways(PA, cur, out / "fig_pathways.pdf")
    PT = parameter_table(case, R.get("montecarlo")); PT.to_csv(out / "parameters.csv")
    R["parameters"] = PT.reset_index().to_dict(orient="records")
    dump_json(R, out / "results.json")
    (out / "summary.md").write_text(markdown_summary(case.cfg["case"]["name"], cur, R))
    say(f"[ee1st] results in {out}")
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ee1st", description="Energy Efficiency First appraisal for SMEs")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a case file")
    r.add_argument("case"); r.add_argument("--out"); r.add_argument("--mc", type=int, help="Monte Carlo draws (0 = skip)")
    r.add_argument("--no-netzero", action="store_true"); r.add_argument("--no-figures", action="store_true")
    i = sub.add_parser("init", help="copy the blank case template to a new folder")
    i.add_argument("dir")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        run(a.case, a.out, a.mc, not a.no_netzero, not a.no_figures)
    else:
        src = Path(__file__).parent / "template"
        if Path(a.dir).exists():
            sys.exit(f"ee1st init: {a.dir} already exists; choose a new folder")
        shutil.copytree(src, a.dir)
        print(f"template copied to {a.dir}; fill in the CSV files and case.yaml, then: ee1st run {a.dir}/case.yaml")


if __name__ == "__main__":
    main()
