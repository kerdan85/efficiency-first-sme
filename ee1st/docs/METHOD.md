# Method

`ee1st` applies the Energy Efficiency First (EE1st) principle at plant level: demand-side measures and supply-side
options are appraised on the **same indicators**, and supply is sized only after cost-effective efficiency has been taken.
The method was developed for, and is validated against, the footwear case study in García Kerdan et al. (2026).
Everything runs from monthly utility bills, a one-month end-use split and public climate data, which is what most SMEs have.

## 1. Data checks and baseline
* **Reference year**: 12 consecutive billed months (`data.reference_year`).
* **Tariff reconstruction**: every historical bill is rebuilt from the official monthly charges and compared with the
  reported average price (bias and mean absolute error are reported). A tariff model that cannot reproduce the bills
  should not be used to value savings.
* **Energy baseline (ISO 50006)**: ordinary least squares of monthly kWh on production, with documented atypical months
  excluded. The intercept is the base load: energy used regardless of output. Without a production series, the base load is
  supplied directly (`baseline.base_load_kWh_month`, e.g. from weekend or night meter readings). If neither is given, the
lowest billed month is used and a warning is issued, because this overstates the base load.

## 2. Value of a saved kWh
Three tariff types are supported.

| type | billed demand | marginal value of a kWh saved |
|---|---|---|
| `q_based_demand` (CFE GDMTO) | Q / (24 d F_C) (the energy term of min(D_max, Q/(24 d F_C)) is assumed binding, as on the case-study bills) | energy + (distribution + capacity) / (24 d F_C) |
| `energy_demand` | measured monthly peak | energy + c (demand charges) / (24 d), with c = `peak_coincidence` |
| `flat` | none | energy |

Under `q_based_demand`, any kWh avoided (including by PV under net metering) also reduces billed demand. Under
`energy_demand`, efficiency lowers the measured peak by c × ΔQ / (24 d), i.e. c times its cut in average power, and PV
and batteries are assumed not to lower it (a conservative assumption for PV; replace it with interval data if available).
The bill model and the marginal value use the same rule.
Power-factor surcharges and bonuses follow `pf_rule` (`mx_cfe` or `none`).

## 3. Measures (no double counting)
* `base_load`: saves `saving_frac` × min(base load / Q, 1) × Q in every month. Applied first.
* `enduse`: saves `saving_frac` × `share_of_enduse` × (sum of target end-use shares) × Q', where Q' is consumption after
  the base-load measures. End-use measures act on disjoint end uses and are computed in parallel.
* `pf_correction`: sets the power factor to `pf_after`; it saves money but no kWh.
* Capex is either fixed (`capex`) or derived from energy (`capex_per_unit` × number of units, with
  units = end-use energy / (`unit_kW` × `hours_per_month`)).

## 4. Supply option: rooftop PV
Monthly plane-of-array irradiation follows the isotropic-sky transposition of Klein (1977), with
`PR`, tilt and albedo as inputs. Generation is netted monthly against consumption (net metering); surplus is reported but
given no value. The PV LCOE includes O&M, an inverter replacement and degradation.

## 5. Indicators (common to all options)
| indicator | definition |
|---|---|
| CCE / LCOE | (capex × CRF(r, life) + O&M) / kWh saved; PV LCOE is discounted cost / discounted generation |
| NPV | horizon H with like-for-like reinvestment, straight-line residual value, PV degradation on the PV share of savings |
| simple payback | capex / (year-1 savings − O&M) |
| CO2 | grid kWh avoided × grid emission factor |
| imported gas avoided | ΔMWh × gas share of generation × heat rate × import share of gas |
| bill exposure | increase in annual bill if the energy charge rises by `security.energy_charge_shock` |
| peak | billed (or measured) peak demand after measures; months above `security.demand_threshold_kW` |
| roof | kWp × `m2_per_kWp` |
| net abatement cost | −NPV × CRF(r, H) / t CO2 per year |

## 6. Portfolios and pathways
* **P0** baseline; **P1** all measures; **P2** PV only at `pv.reference_kWp`; **P3** P1 + the same PV;
  **P4** P1 + PV re-sized by bisection to reach P2's grid purchases. P4 against P2 is the core EE1st test.
* **Pathways**: for grid-reduction targets from 5% to 75%, the supply-only route sizes PV alone; the efficiency-first
  route adds measures in merit order (ascending CCE) until the target is met, then sizes PV for the remainder.
* **Regulatory stress** (`q_based_demand` only): PV gets no demand credit.

## 7. Uncertainty
Every input given as `[central, low, high]` is sampled from a triangular distribution (Monte Carlo, `montecarlo.n`, fixed
seed). Outputs: percentiles, P(NPV > 0), P(P4 > P2), probability each option is the cheapest kWh, and Spearman rank
correlations of the inputs with NPV(P4) − NPV(P2). These correlations are written to `parameters.csv` and to the
summary next to each input's data status, so that the assumptions that matter most for the efficiency-first decision are
visible. One-way low/high sensitivity is also written.

## 8. Net-zero electricity (optional, needs hourly weather)
* Hourly PV from hourly GHI/DHI (transposed as above, rescaled month by month to the climatology). Timestamp labels are
  converted to clock time with `weather_hourly_options.label_utc_offset` (NASA POWER "LST" = UTC + round(lon/15)).
* **Synthetic hourly load**: an always-on load N (`netzero.night_load_kW`) plus a flat load during the operating hours in
  `schedule`, matching each month's billed kWh. Base-load measures lower N. *This is the weakest assumption of the module;
  replace it with interval data whenever possible.* The least-capex design at a self-sufficiency target
  (`night_load_sensitivity_target`, default 80%) is recomputed for the low, central and high N.
* Greedy battery dispatch (charge from surplus PV, discharge to load), round-trip efficiency, depth of discharge, C-rate.
* Three regimes: net metering with a FIFO credit bank (`credit_expiry_months`, expired credits valued at
  `expired_credit_value`), net metering with demand billed on imports, and net billing (exports paid at
  `net_billing_export_value`).
* Efficiency also lowers a measured peak under `energy_demand` (Section 2); PV and storage do not.
* Cash flows (reinvestment, residual value, inverter replacement, degradation, real tariff escalation) use the same
  function as the monthly appraisal. Asset lives are whole years.
* Sweep of PV size (multiples of the annual-net-zero size, capped at `pv_limit_kWp`) × battery size, for a supply-only set
  and the efficiency-first set; the least-capex design for each self-sufficiency target forms the frontier.

## 9. Heat (optional)
Cost and CO2 per GJ of useful heat for fuel boilers, resistance heating and heat pumps at several COPs, plus the
break-even COP against each fuel. This is reported per GJ so that it can be scaled when fuel use is not metered.

## Limits
Monthly resolution for the main appraisal; synthetic hourly load in the net-zero module; end-use split from a single
month; literature saving fractions unless the user supplies measured ones. The output states which inputs are
assumptions so that the next measurement can be targeted where it matters (see the Spearman ranking).
