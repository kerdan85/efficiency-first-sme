# ee1st — Energy Efficiency First appraisal for SMEs

Part of the repository [`efficiency-first-sme`](../README.md) (DOI: 10.5281/zenodo.23419738); tests run from the root workflow `.github/workflows/tests.yml`.

`ee1st` tests the Energy Efficiency First principle in a small or medium plant. It puts demand-side measures and
supply-side options (rooftop PV, batteries, heat electrification) on the **same indicators** — cost of conserved energy,
NPV, CO2, imported-gas exposure, bill-shock exposure, peak demand and roof area — and sizes supply only after
cost-effective efficiency has been taken.

It is built for the data an SME actually has: **12 monthly bills, a one-month end-use split and public climate data**.
Production records, hourly weather and a tariff history improve the analysis but are optional.

The method generalises the case study in

> Alberú Argüeso, Y.; Aguado Guerra, I.; Acosta Sosa, F.; Rosas-Meléndez, S.A.; García Kerdan, I. (2026). *Sizing Rooftop Photovoltaics and Batteries After Energy Efficiency: An Optimisation Framework for Manufacturing SMEs.*
> Submitted to *Processes* (MDPI).
> Paper code, public data and results: the root of this repository

and, when the confidential plant records are supplied, reproduces its deterministic results exactly: `tests/test_footwear.py` compares all headline portfolio, measure and pathway columns with the case repository, and checks the net-zero designs and Monte Carlo statistics.

## Install and run
```bash
pip install -e .            # Python >= 3.10; numpy, pandas, matplotlib, pyyaml
ee1st run examples/synthetic_demand_tariff/case.yaml   # runs out of the box (synthetic data)
ee1st run examples/footwear_mx/case.yaml   # needs the confidential plant files; several minutes
ee1st init my_plant         # blank case to fill in
```
Results go to `results/` next to the case file: `summary.md`, `results.json`, CSV tables and three figures
(merit order, efficiency-first vs supply-only pathways, net-zero frontier).

## What it computes
| step | output |
|---|---|
| data checks | tariff model reproduces each bill (bias, mean absolute error); ISO 50006 baseline and base-load share |
| measures | kWh, CCE, NPV, payback, CO2 of each measure alone; merit order against the marginal tariff |
| portfolios | P1 all measures; P2 PV only; P3 both; **P4 efficiency first + PV re-sized to P2's grid use** |
| pathways | capex and NPV of the supply-only and efficiency-first routes to 5–75% grid reduction |
| security | imported gas avoided, bill exposure to an energy-price shock, peak demand vs a tariff threshold, roof area |
| stress | PV without demand credit (Mexican Q-based demand tariffs) |
| uncertainty | Monte Carlo on every `[central, low, high]` input; P(P4 > P2); Spearman drivers; one-way sensitivity |
| net zero (optional) | hourly PV + synthetic load + battery dispatch under net metering, demand-on-imports and net billing; least-capex frontier per self-sufficiency target |
| heat (optional) | cost and CO2 per GJ useful heat for fuels, resistance and heat pumps; break-even COP |

Example output for the footwear plant: [`docs/example_output/summary.md`](docs/example_output/summary.md). See [`docs/METHOD.md`](docs/METHOD.md) for equations and [`docs/INPUTS.md`](docs/INPUTS.md) for the input format.

## Tariffs supported
* `q_based_demand` — billed demand tied to energy (CFE GDMTO, Mexico); every kWh avoided also cuts demand charges.
* `energy_demand` — energy plus a demand charge on the measured peak (common in the EU and US).
* `flat` — single energy price.

## Examples
* `examples/footwear_mx` — the paper's case (Pachuca area, Mexico): case file, official CFE tariffs and NASA POWER
  weather. The plant's bills, production and end-use records are confidential and not distributed, so this example
  runs only when they are supplied (see its README). The paper's own scripts are in `../scripts/`.
* `examples/synthetic_demand_tariff` — **invented data**, to show the inputs for a non-Mexican plant with an
  energy + demand tariff and no production records.

## Limits
Monthly resolution; the hourly net-zero module uses a synthetic load (always-on load plus flat operating-hours load)
because SMEs rarely have interval data — its results depend on the always-on load, whose low, central and high values are compared in the
sensitivity. Saving fractions default to literature ranges; replace them with measured values when available.

## Licence and citation
Code: MIT. Documentation and example data: CC BY 4.0 (third-party data keep their source terms). Cite with the
`CITATION.cff` at the repository root.
