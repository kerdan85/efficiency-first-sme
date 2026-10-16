# Data sources

| File | Content | Source | Status | Accessed |
|---|---|---|---|---|
| `raw/billing_monthly.csv` | Monthly kWh, billed kW, power factor, reported load factor, average pre-VAT price, production (pairs), Jan 2024–Apr 2026 | **Confidential, not distributed.** Plant utility bills and production records, transcribed during the 2026 energy audit; `retscreen_cost_MXN` is the cost field of the audit's RETScreen file (approx. VAT-inclusive, not used in the model) | Measured (transcribed) | 2026 |
| `raw/area_disaggregation_reference_month.csv` | Electricity by production area for the reference month (April 2026, 28,400 kWh) | **Confidential, not distributed.** Audit walk-through estimate entered in RETScreen Expert | Estimate | 2026 |
| `raw/cfe_gdmto_centro_oriente.csv` | GDMTO fixed, energy, distribution and capacity charges, División Centro Oriente (Pachuca de Soto), Jan 2024–Oct 2026 | CFE, https://app.cfe.mx/Aplicaciones/CCFE/Tarifas/TarifasCREIndustria/Tarifas/GranDemandaMTO.aspx | Official | 2026-10-14 |
| `raw/emission_factors_mexico.csv` | National grid emission factor 2022–2024 | CRE / SEMARNAT notices (URLs in file); SEMARNAT notice of 29 May 2026 keeps the 2024 value for COA 2026 | Official | 2026-10-14 |
| `raw/fuel_prices_mexico.csv` | IPGN natural-gas wholesale index (Sep 2025–Aug 2026); LP-gas maximum price Pachuca (11–17 Oct 2026) | CNE https://www.cne.gob.mx/IPGN/ ; PROFECO https://combustibles.profeco.gob.mx/maximoGas/2026/MAXIMOGAS_101126.pdf | Official | 2026-10-14 |
| `raw/grid_context_mexico.csv` | 2024 generation by technology; US gas exports and Mexican consumption; DG threshold; GDMTO load factor and PF rules | SENER Plan de Desarrollo del Sector Eléctrico (DOF 17-10-2025); EIA Today in Energy (20-10-2025); LSE art. 25; DOF 24-01-2025 | Official | 2026-10-14 |
| `raw/nasa_power_hourly_2023_pachuca.csv` | Hourly GHI and DHI (5 W/m2 resolution) and T2M (1 °C), 2023, NASA POWER "LST" labels (UTC−7 at this longitude; shifted +1 h to local clock time UTC−6 in the model), same point | NASA POWER Hourly API v2.10.1 | Institutional | 2026-10-14 |
| `raw/nasa_power_climatology_pachuca.csv` | Monthly GHI, DHI, clearness index, T2M, 2001–2025 climatology at 20.0965 N, −98.7624 E | NASA POWER Climatology API v2.10.1 | Institutional | 2026-10-14 |

The company is not named. The original RETScreen file is not redistributed because it was built on a vendor training template that contains third-party example data; only the plant-specific values were extracted.

## Map boundaries
`naturalearth_admin1_mexico_region.geojson`: Natural Earth 1:10m Admin 1 states and provinces (public domain, https://www.naturalearthdata.com), subset to Mexico and neighbouring areas and simplified (every third vertex, 3 decimals). Accessed 2026-10-14 from https://github.com/nvkelso/natural-earth-vector. Used only for Fig. 1a.
