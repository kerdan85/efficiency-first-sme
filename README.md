# efficiency-first-sme

Sizing rooftop PV and batteries after energy efficiency in manufacturing SMEs. One repository with two parts:

* **the paper** (root folders): code, public input data and results for the Mexican footwear-plant case study;
* **`ee1st/`**: the generalised Python toolkit to apply the same method to any other SME.

Article:

> Alberú Argüeso Y., Aguado Guerra I., Acosta Sosa F., Rosas-Meléndez S.A., García Kerdan I. (2026).
> *Sizing Rooftop Photovoltaics and Batteries After Energy Efficiency: An Optimisation Framework for Manufacturing SMEs.*
> Submitted to *Processes* (MDPI), Special Issue "Advanced Modelling, Optimisation and AI for
> Sustainable Energy Systems".

Archived version: https://doi.org/10.5281/zenodo.XXXXXXX


> **Confidential data.** The plant's billing, production and audit records are confidential and are not part of the
> public repository (see `data/raw/CONFIDENTIAL.md` for their format). All derived results in `results/` and all
> figures are included, so every number in the paper can be checked against them; re-running the scripts requires the
> confidential files.

## What the model does

1. Reads 28 months of transcribed utility bills and 25 months of production records for a
   medium-voltage (CFE GDMTO) footwear plant in Pachuca, Mexico.
2. Rebuilds every monthly bill from official GDMTO charges (Centro Oriente division) and the
   billed-demand rule `min(Dmax, Q / (24·d·0.55))`; the validation against the reported prices is in
   `results/tariff_validation.csv`.
3. Estimates the production-normalised energy baseline (ISO 50006).
4. Appraises demand-side measures (base-load control, insulation of heated platens/barrels, servo
   motors, compressed air, power-factor correction) and supply-side options (rooftop PV; heat
   electrification per GJ) with common indicators: energy, CO2, cost of conserved energy / LCOE,
   NPV, payback, imported-gas exposure, tariff-shock exposure, peak demand and roof area.
5. Compares supply-only and efficiency-first pathways and portfolios.
6. Propagates uncertainty with a 5,000-draw Monte Carlo (seed 20261014) and one-way sensitivities.
7. Tests net-zero electricity with rooftop PV and lithium-ion storage on an hourly basis (synthetic load
   profile, NASA POWER 2023 hourly irradiance rescaled to climatology, 12-month net-metering credit bank),
   and cross-validates the key designs in EnergyPlus 25.1 (Generator:PVWatts + ElectricLoadCenter:Storage:Simple).

## Reproduce

```bash
python3 -m pip install -r requirements.txt
export EPLUS_DIR=/path/to/EnergyPlus-25.1.0   # optional, for the EnergyPlus cross-validation
./run_all.sh            # ~5 min; also compiles the manuscript if latexmk is available
```

Each script can also be run alone, in this order:

| Script | Output |
|---|---|
| `scripts/run_analysis.py` | `results/results.json`, `measures.csv`, `portfolios.csv`, `pathways.csv`, `tariff_validation.csv`, `pv_monthly_yield.csv`, `thermal_unit_economics.csv`, `sensitivity_oneway.csv` |
| `scripts/run_montecarlo.py` | `results/montecarlo.csv.gz`, `results/montecarlo_summary.json` |
| `scripts/run_netzero.py` | `results/netzero.json`, `netzero_sweep.csv`, `netzero_frontier.csv` |
| `scripts/run_energyplus.py` (optional; needs `EPLUS_DIR` pointing to EnergyPlus 25.1) | `energyplus/*/in.idf`, `energyplus/pachuca_nasa2023.epw`, `results/energyplus_validation.csv` |
| `scripts/make_figures.py` | `figures/*.pdf|png` (Nature-style, Okabe–Ito palette, 7 pt Arial/Helvetica) |
| `scripts/make_diagrams.py` | `figures/fig_site_diagram.*` (plant layout and energy flows), `figures/fig_urbs_structure.*` (urbs model structure); needs no confidential data |
| `scripts/export_numbers.py` | `manuscript/numbers.tex` – every number quoted in the paper as a LaTeX macro |
| `scripts/export_tables.py` | `manuscript/tables/*.tex` |
| `scripts/urbs_prepare.py` | `urbs/plant_urbs.xlsx` (urbs input: hourly load, PV, efficiency measures as negawatt processes, battery) |
| `scripts/run_urbs.py` (urbs environment: `requirements-urbs.txt` + urbs from github.com/tum-ens/urbs, commit 37487e6; set `URBS_PYTHON` for `run_all.sh`) | `results/urbs_results.csv` (32 linear programmes: 3 compensation regimes, roof limit, CO2 caps, battery-cost sensitivity; HiGHS), `urbs/urbs_dispatch.csv.gz` (hourly dispatch, confidential) |
| `scripts/export_urbs.py` | `figures/fig9_urbs.*`, `figures/fig10_urbs_dispatch.*`, `manuscript/tables/urbs.tex`, `urbs_battery.tex`, `manuscript/numbers_urbs.tex`, `results/urbs_dispatch_summary.json` |
| `scripts/build_processes_manuscript.py` | `manuscript_processes/main.tex`, `tables/`, `numbers.tex`, `references.bib` (MDPI Processes version) |

## Repository layout

```
data/raw/        input data (see data/SOURCES.md for provenance and access dates)
src/efirst/      model: params.py (all parameters, ranges, status, source), model.py
scripts/         analysis, Monte Carlo, figures, manuscript numbers and tables
results/         generated results
figures/         generated figures
manuscript_processes/  submitted version: MDPI Processes LaTeX (Definitions/ = MDPI class), built by
                 scripts/build_processes_manuscript.py from the shared body text
manuscript/      earlier elsarticle draft; source of the shared body text, numbers and tables
energyplus/      EnergyPlus cross-validation (weather file; generated IDFs are not tracked)
urbs/            urbs benchmark metadata (the hourly input workbook is confidential, not tracked)
ee1st/           generalised toolkit (own pyproject.toml, tests, docs and examples)
.github/         CI: runs the ee1st test suite on every push
```

## Key conventions

* Money: 2026 MXN, excluding VAT; constant real prices; 1 USD = 17.10 MXN (CNE, Aug 2026).
* Emission factor: 0.444 tCO2e/MWh (SEMARNAT, 2024 factor, still mandated for 2026 reporting).
* Reference year: May 2025 – April 2026 (latest 12 billed months).
* Parameter status codes in `src/efirst/params.py`: measured, official, literature, quote, design,
  assumption, regulatory. Assumptions are varied in the Monte Carlo.

## Applying the method to another plant
This repository reproduces the paper. To appraise another SME, use the generalised toolkit **ee1st** in the [`ee1st/`](ee1st/) folder of this repository (`cd ee1st && pip install -e .`), which takes a single YAML case file, supports other tariff structures and includes this plant as a validated example.

## Licence

Code: MIT. Data, results, figures and manuscript: CC BY 4.0. See `LICENSE`.
Please cite the archived version (`CITATION.cff`).
