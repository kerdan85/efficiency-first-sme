#!/usr/bin/env bash
# Reproduce all results, figures, tables and manuscript numbers (about 3 minutes).
set -euo pipefail
cd "$(dirname "$0")"
python3 scripts/run_analysis.py
python3 scripts/run_montecarlo.py
python3 scripts/run_netzero.py
if [ -n "${EPLUS_DIR:-}" ] && [ -x "$EPLUS_DIR/energyplus" ]; then
  python3 scripts/run_energyplus.py   # optional cross-validation (EnergyPlus 25.1)
fi
python3 scripts/make_figures.py
python3 scripts/make_diagrams.py
if [ -n "${URBS_PYTHON:-}" ]; then   # optional: urbs environment (requirements-urbs.txt), ~30 min on 2 cores
  python3 scripts/urbs_prepare.py
  "$URBS_PYTHON" -W ignore scripts/run_urbs.py
fi
python3 scripts/export_urbs.py
python3 scripts/export_numbers.py
python3 scripts/export_tables.py
python3 scripts/build_processes_manuscript.py
if command -v latexmk >/dev/null; then
  (cd manuscript_processes && latexmk -pdf -interaction=nonstopmode main.tex)
fi
