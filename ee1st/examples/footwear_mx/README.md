# Footwear SME, Pachuca area (Mexico) — case of the paper

This folder holds the case file and the **public** inputs of the plant studied in García Kerdan et al. (2026):
official CFE GDMTO tariffs (`tariff_monthly.csv`) and NASA POWER climate data (`climate_monthly.csv`,
`weather_hourly.csv`).

The plant's records are **confidential** (the company has not authorised their release), so two files are not
distributed:

* `data/billing_monthly.csv` — `month, energy_kWh, max_demand_kW, power_factor, load_factor_reported, reported_price, production`
* `data/enduse_shares.csv` — `end_use, share` with the end uses named in `case.yaml`
  (*compressed air room, stitching (sewing), vulcanising, sole injection moulding*, …)

Without them `ee1st run case.yaml` stops with a missing-file error and `tests/test_footwear.py` is skipped. With
them, the tests confirm that the toolkit reproduces the paper's results. Summary statistics of the records and all
derived results are in the paper and in its case repository. To try the toolkit without confidential data, run
`examples/synthetic_demand_tariff`.
