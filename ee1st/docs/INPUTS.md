# Inputs

Start a new case with `ee1st init my_plant`, fill in the CSV files and `case.yaml`, then run `ee1st run my_plant/case.yaml`.

## Minimum data (what most SMEs already have)
| file | columns | source |
|---|---|---|
| `billing_monthly.csv` | `month` (YYYY-MM), `energy_kWh`, `max_demand_kW`, `power_factor` (0-1, optional), `reported_price` (optional), `production` (optional) | utility bills; production records |
| `enduse_shares.csv` | `end_use`, `share` (sum = 1) | walk-through audit, nameplate × hours, or one month of clamp-meter readings |
| `climate_monthly.csv` | `month` (1-12), `GHI`, `DHI` (kWh/m²/day) | NASA POWER climatology or PVGIS |
| tariff | `tariff_monthly.csv` (`month`, `fixed`, `energy`, `distribution`, `capacity`, `demand`) or `charges:` in the YAML | utility / regulator |

## Optional data
| file | columns | enables |
|---|---|---|
| `weather_hourly.csv` | `timestamp`, `GHI`, `DHI` (W/m²), `T` | net-zero module (PV + storage) |
| interval meter data | — | not yet read directly; use it to set `netzero.night_load_kW` and `baseline.base_load_kWh_month` |

## Writing parameters
```yaml
discount_rate: 0.08                    # fixed
saving_frac: [0.20, 0.10, 0.30]        # triangular (central, low, high) for Monte Carlo
capex: {value: [50000, 35000, 80000], status: quote, source: "supplier, 2026-09"}
demand_credit: {value: 1.0, mc: false} # excluded from Monte Carlo
```
`status` is one of `measured`, `official`, `literature`, `quote`, `design`, `assumption`, `regulatory`. It is written to
`results/parameters.csv` and the summary, so a reader can see which numbers are measured and which are assumed.

## Measure types
| type | required keys | optional |
|---|---|---|
| `base_load` | `saving_frac`, `capex`, `life` | `om` |
| `enduse` | `end_uses` (names in `enduse_shares.csv`), `saving_frac`, `capex` **or** (`capex_per_unit`, `unit_kW`, `hours_per_month`), `life` | `share_of_enduse`, `om` |
| `pf_correction` | `pf_after`, `capex`, `life` | |

Do not let two `enduse` measures target the same end use unless their savings are additive; otherwise combine them into
one measure.

## Grid and security
`grid.emission_factor_t_per_MWh` (official national or utility factor), `gas_share_generation`, `heat_rate_GJ_per_MWh`,
`gas_import_share`. Set the last two to 0 if the security indicator is not relevant.

## Where to find public data
* Climate: NASA POWER (https://power.larc.nasa.gov), PVGIS (https://re.jrc.ec.europa.eu/pvg_tools/).
* Mexico: CFE tariffs (https://app.cfe.mx/Aplicaciones/CCFE/Tarifas/TarifasCRENegocio/Negocio.aspx), SEMARNAT grid
  emission factor, CNE/PROFECO LPG prices, CNE IPGN natural-gas index.
* EU: national regulator tariff decisions; EEA or AIB emission factors.
