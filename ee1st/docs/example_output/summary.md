# EE1st appraisal: Footwear SME, Pachuca (MX)

## Inputs check
- Reference-year consumption: 460.80 MWh; annual bill 1,234,426 MXN
- Marginal value of a saved kWh: 2.644 MXN/kWh
- Tariff model vs reported prices: bias +2.1%, mean absolute error 2.2%
- Baseline: kWh = 25341 + 0.540 x production (R2 0.38, n 22); base load 66% of consumption

## Measures (merit order; PF correction last, no kWh saved)

| id | name | capex (MXN) | MWh/yr | CCE/LCOE (MXN/kWh) | NPV (MXN) |
|---|---|---:|---:|---:|---:|
| E4 | Base-load (idle) control | 40,000 | 30.4 | 0.21 | 638,453 |
| E3 | Insulation of heated platens/barrels | 100,000 | 23.0 | 0.82 | 361,599 |
| PV | Rooftop PV 163.8 kWp | 1,801,800 | 250.0 | 0.92 | 3,565,999 |
| E2 | Servo motors (sewing) | 240,683 | 41.5 | 0.94 | 609,850 |
| E1 | Compressed-air package | 50,000 | 15.5 | 1.04 | 214,520 |
| E5 | Power-factor correction | 85,000 | 0.0 | - | 206,364 |

## Portfolios

| | PV kWp | capex | NPV | grid cut | tCO2/yr | roof m2 | bill shock exposure |
|---|---:|---:|---:|---:|---:|---:|---:|
| P0 | 0.0 | 0.00 | 0.00 | 0% | 0 | 0 | 342,240 |
| P1 | 0.0 | 515,683 | 1,840,016 | 23% | 47 | 0 | 256,559 |
| P2 | 163.8 | 1,801,800 | 3,565,999 | 54% | 111 | 901 | 155,999 |
| P3 | 163.8 | 2,317,483 | 5,111,852 | 76% | 155 | 901 | 80,249 |
| P4 | 94.9 | 1,559,583 | 3,804,754 | 54% | 111 | 522 | 152,072 |

Regulatory stress (no demand credit for PV): P2 NPV 1,111,404, P3 NPV 2,787,673, P4 NPV 2,427,612

## Monte Carlo (n = 5000, seed 20261014)
- P(NPV > 0): P1 100%, P2 100%, P3 100%, P4 100%
- P(efficiency first + right-sized PV beats PV only): 86%
- P(all CCE below marginal tariff): 100.00%

## Inputs: data status and influence on the efficiency-first advantage

Spearman rank correlation with NPV(P4) − NPV(P2) across the Monte Carlo draws; inputs marked `assumption` with large |rho| are where a site measurement is worth most.

| input | central | range | status | rho |
|---|---:|---|---|---:|
| measures.E4.saving_frac | 0.10 | 0.05–0.20 | literature | +0.67 |
| measures.E3.saving_frac | 0.20 | 0.10–0.30 | literature | +0.34 |
| pv.cost_per_W | 11.00 | 9.00–14.00 | quote | +0.28 |
| measures.E1.saving_frac | 0.20 | 0.10–0.30 | literature | +0.24 |
| pv.PR | 0.80 | 0.75–0.85 | literature | -0.23 |
| measures.E2.saving_frac | 0.65 | 0.50–0.75 | literature | +0.23 |
| measures.E3.share_of_enduse | 0.65 | 0.50–0.80 | assumption | +0.17 |
| measures.E2.share_of_enduse | 0.70 | 0.50–0.85 | assumption | +0.16 |
| measures.E2.capex_per_unit | 3,800 | 2,800–5,500 | assumption | -0.16 |
| measures.E2.unit_kW | 0.35 | 0.25–0.45 | literature | +0.16 |
| measures.E3.capex | 100,000 | 60,000–150,000 | assumption | -0.08 |
| pv.om_frac | 0.01 | 0.005–0.015 | assumption | +0.06 |
| pv.degradation | 0.005 | 0.003–0.008 | literature | +0.06 |
| measures.E1.om | 8,000 | 5,000–12,000 | assumption | -0.05 |
| measures.E4.capex | 40,000 | 20,000–70,000 | assumption | -0.05 |
| measures.E5.capex | 85,000 | 70,000–110,000 | quote | -0.04 |
| pv.m2_per_kWp | 5.50 | 5.00–6.50 | assumption | +0.04 |
| finance.tariff_real_escalation | 0.00 | -0.01–0.02 | assumption | +0.04 |
| measures.E5.pf_after | 0.97 | 0.95–0.99 | assumption | +0.03 |
| measures.E1.capex | 50,000 | 35,000–80,000 | quote | -0.03 |
| netzero.net_billing_export_value | 1.00 | 0.60–1.50 | assumption | -0.01 |
| pv.inverter_repl_frac | 0.10 | 0.08–0.15 | assumption | +0.01 |
| grid.import_share | 0.74 | 0.70–0.78 | official | -0.01 |
| finance.discount_rate | 0.10 | 0.06–0.14 | assumption | -0.01 |
| netzero.night_load_kW | 15.00 | 8.00–25.00 | assumption | -0.01 |
| grid.heat_rate | 7.20 | 6.50–8.50 | assumption | -0.01 |
| netzero.bat_cost_per_kWh | 8,500 | 6,000–12,000 | assumption | -0.01 |
| grid.gas_share | 0.64 | 0.60–0.68 | official | +0.00 |

Fixed inputs marked `assumption`: finance.horizon_yr, measures.E4.life, measures.E1.life, measures.E5.om, measures.E5.life, measures.E3.life, measures.E3.om, measures.E2.hours_per_month, measures.E2.life, measures.E2.om, measures.E1.share_of_enduse, measures.E4.om, pv.inverter_repl_year, pv.albedo, netzero.bat_dod, netzero.bat_c_rate, netzero.expired_credit_value.

## Net-zero electricity designs (net metering)

| design | kWp | battery kWh | self-sufficiency | capex | NPV |
|---|---:|---:|---:|---:|---:|
| NZ-supply | 303 | 0 | 57% | 3,414,178 | 6,436,028 |
| SS70-supply | 333 | 200 | 71% | 5,447,096 | 3,773,726 |
| SS80-supply | 424 | 400 | 80% | 8,145,849 | 387,482 |
| SS90-supply | 575 | 1000 | 90% | 14,910,438 | -8,323,366 |
| NZ-eefirst | 234 | 0 | 57% | 3,085,532 | 6,648,064 |
| SS70-eefirst | 234 | 200 | 71% | 4,785,532 | 4,160,246 |
| SS80-eefirst | 350 | 300 | 80% | 6,920,457 | 1,800,509 |
| SS90-eefirst | 467 | 800 | 90% | 12,455,382 | -5,347,377 |

Sensitivity to the always-on load N of the synthetic hourly profile (net metering):

| N (kW) | set | self-sufficiency at annual net zero | least capex at target |
|---:|---|---:|---:|
| 8 | supply | 59% | 8,145,849 (80%) |
| 8 | eefirst | 60% | 7,177,442 (80%) |
| 15 | supply | 57% | 8,145,849 (80%) |
| 15 | eefirst | 57% | 6,920,457 (80%) |
| 25 | supply | 52% | 8,478,767 (80%) |
| 25 | eefirst | 51% | 7,256,487 (80%) |

## Heat options (per GJ useful heat)

- LPG boiler: cost_per_GJ_heat 423.69, kgCO2_per_GJ_heat 74.24, breakeven_COP_cost 1.73, breakeven_COP_co2 1.66
- Natural-gas boiler: cost_per_GJ_heat 125.98, kgCO2_per_GJ_heat 66.00, breakeven_COP_cost 5.83, breakeven_COP_co2 1.87
- Electric resistance: cost_per_GJ_heat 734.39, kgCO2_per_GJ_heat 123.33
- Heat pump COP 2.5: cost_per_GJ_heat 293.75, kgCO2_per_GJ_heat 49.33
- Heat pump COP 3: cost_per_GJ_heat 244.80, kgCO2_per_GJ_heat 41.11
- Heat pump COP 4: cost_per_GJ_heat 183.60, kgCO2_per_GJ_heat 30.83

All values are model outputs from the inputs in the case file; parameters marked `assumption` should be replaced by site measurements where available.
