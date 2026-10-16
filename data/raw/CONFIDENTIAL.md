# Confidential plant data (not distributed)

The company has not authorised the release of its records, so two input files are withheld from the public
repository. The scripts expect them in `data/raw/` with exactly these columns:

`billing_monthly.csv` — one row per billed month (Jan 2024–Apr 2026 in the paper)

| column | unit | description |
|---|---|---|
| month | YYYY-MM | billing month |
| energy_kWh | kWh | billed energy |
| max_demand_kW | kW | billed demand printed on the bill |
| power_factor | 0–1 | power factor printed on the bill |
| load_factor_reported | 0–1 | load factor printed on the bill |
| avg_price_MXN_per_kWh_reported | MXN/kWh | average pre-VAT price printed on the bill |
| retscreen_cost_MXN | MXN | cost field of the audit RETScreen file (not used by the model) |
| production_pairs | pairs | monthly production (blank if not recorded) |

`area_disaggregation_reference_month.csv` — audit estimate for the reference month

| column | description |
|---|---|
| area_es, area_en | production area (Spanish, English); the model uses `area_en` names *compressed air room*, *stitching (sewing)*, *vulcanising*, *sole injection moulding* |
| energy_kWh_per_month | estimated kWh of the area in the reference month |
| share | share of the month's electricity (sums to 1) |

Summary statistics of the records are given in Table A.1 of the paper, and every derived result is in `results/`.
The files can be made available to editors and reviewers on request to the corresponding author, subject to the
company's permission. To apply the code to another plant, supply that plant's files in the same format, or use the
generalised toolkit `ee1st`.
