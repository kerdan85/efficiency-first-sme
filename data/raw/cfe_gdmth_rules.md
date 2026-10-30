# GDMTH (Gran Demanda en Media Tensión Horaria), CFE División Centro Oriente: billing rules and sources

Compiled 2026-10-29. All charges are in MXN and exclude VAT (IVA 16%) and DAP.

## 1. Data file: gdmth_tariff.csv

- Every value comes from the official monthly "Anexo II" tables (CRE Acuerdos up to Mar-2025, then CFE/CNE "Tarifas finales del Suministro Básico" notices), read through SIDOF (sidof.segob.gob.mx) or the DOF PDFs that CENACE mirrors. The one exception is Oct-2026 (see below).
- The Anexo II column order is: Transmisión ($/kWh), Distribución ($/kW), Operación del CENACE ($/kWh), Operación del Suministrador ($/mes, the fixed charge), Servicios conexos no MEM ($/kWh), Energía ($/kWh by period), Capacidad ($/kW).
- `energy_base`, `energy_intermedia` and `energy_punta` are the **generation-only** energy charges ("Energía" column).
- `*_allin` = generation + transmisión + CENACE + SCnMEM. This matches the "Base/Intermedia/Punta $/kWh" figures CFE shows on app.cfe.mx and on secondary sites. Use **either** the components **or** the all-in figures, never both, or the adders will be counted twice.
  - Cross-check: the all-in values for Sep-2025 to Sep-2026 match ideatuinmueble.com/tarifas-cfe/centro-oriente exactly. For example, Sep-2026 is 1.0181 / 1.8141 / 2.0466.
- Your GDMTO energy figures (~1.47–1.68) are also all-in values. For example, GDMTO Sep-2026 is 1.274 + 0.1946 = 1.4686.
- In every month the fixed charge and the distribution charge are **identical for GDMTO and GDMTH**. The capacity charge is about 16% higher in GDMTH. For example, Sep-2026 is 373.67 against 321.98 for GDMTO.
- The regulated components change only once a year:

| Year | Fixed ($/mes) | Distribution ($/kW) | Transmission ($/kWh) | CENACE ($/kWh) | SCnMEM ($/kWh) |
|---|---|---|---|---|---|
| 2024 | 360.01 | 155.26 | 0.1769 | 0.0065 | 0.0062 |
| 2025 | 308.10 | 155.81 | 0.1809 | 0.0065 (Jan–Aug), 0.0106 (Sep–Dec) | 0.0062 |
| 2026 | 335.36 | 149.44 | 0.1801 | 0.0076 | 0.0069 |

- The generation charges (energy and capacity) are adjusted every month. In 2026 the monthly factors were negative or 0%; July 2026 was −2.00%.

**Gaps and caveats**

- **Mar-2024, Apr-2025 and May-2025 were not found** and are left blank. If you interpolate them, flag them as interpolated.
- **Oct-2026 is secondary.** batuenergy.com shows values identical to Sep-2026, and the press reported that the Oct-2026 DOF notice set a 0.00% adjustment versus September (elimparcial.com, 27-Oct-2026). I did not read the official Oct-2026 table.
- The values were extracted by a text tool from flattened PDF/HTML tables. Column assignment was inferred from the fixed column order. The arithmetic cross-check against independent all-in series supports it.
- Jan-2024: the "Intermedio" label was missing in the extracted text. The 1.7220 value sits in the intermediate slot.
- Jul-2026 punta is 1.8519; Aug and Sep-2026 are 1.8520. These are rounding differences in the source.
- app.cfe.mx (CFE's own tariff pages), dof.gob.mx and the original PDFs could not be opened directly (robots/proxy block). The rules below therefore come from the CRE/CNE methodology acuerdos on SIDOF plus secondary sources quoting the CFE page.

## 2. Billing rules (monthly bill)

Bill = Fixed + Energy + Distribution + Capacity, then the power-factor adjustment, then IVA.

1. **Fixed (Operación del Suministrador):** $/month per service.

2. **Energy:** sum of kWh_base·Pb + kWh_int·Pi + kWh_punta·Pp, using either the all-in prices or the generation prices plus (transmission + CENACE + SCnMEM) × total kWh.

3. **Capacity ($/kW):** billed on the demand coinciding with punta:
   `D_cap = min( DP , Q / (24 · d · FC) )`
   - DP = maximum demand measured in the punta period (15-min integration).
   - Q = total kWh of the month (all periods).
   - d = days in the billing period.
   - **FC = 0.57 for GDMTH** (0.55 for GDMTO).
   - In months with no punta period (BC/BCS seasons only), DP is replaced by the monthly maximum. Centro Oriente always has a punta on weekdays.

4. **Distribution ($/kW):** billed on the monthly maximum demand, with the same cap:
   `D_dist = min( DM , Q / (24 · d · FC) )`
   - DM = maximum demand of the month in any period.
   - FC = 0.57.
   - A fraction of a kW is rounded up to a whole kW (secondary source).

5. **Power factor (FP)**, from kWh and kVArh, applied to the sum of the charges above:
   - FP < 90%: surcharge % = 3/5 × (90/FP − 1) × 100, capped at 120%.
   - FP ≥ 90%: bonus % = 1/4 × (1 − 90/FP) × 100, capped at 2.5%.
   - FP is rounded to one decimal.
   - The Código de Red (RES/550/2021) separately requires FP ≥ 0.95 for load centres. That is a compliance requirement, not part of the bill formula.

6. **Low-voltage metering:** +2% on the charges if the service is metered on the low-voltage side. This does not apply to MV metering.

**How reliable these rules are**

- **Official:** FC 0.57 (GDMTH) and 0.55 (GDMTO), from Tabla 2 of Acuerdo A/158/2024 and of CNE Acuerdo CT/11.SE/8-2025. The SIDOF texts of both say that capacity and distribution are charged on demand (kW) under numerals 5.1 and 5.2. **However, the formula images and the text of 5.1, 5.2 and 5.5 could not be read.**
- **Secondary but consistent:** the min(DP or DM, Q/(24·d·FC)) structure and the power-factor formulas come from several secondary sources that cite the CFE GDMTH page, numeral 7 (psenergia.com.mx, danersolar.com, batuenergy.com, climatta.com, cceea.mx).
- **Historical note:** a 2018 CFE presentation described distribution for GDMTO as "the maximum demand of the last 12 months". The current rule (min with the Q/(24·d·FC) cap) replaced that; verify on a real bill if possible.

## 3. Time-of-use periods: Sistema Interconectado Nacional (applies to Centro Oriente / Pachuca)

Source: Tabla 4 and Tabla 5 of A/158/2024 (2025) and of CNE CT/11.SE/8-2025 (2026). The schedules are identical in both years.

**Seasons**

- **Verano:** from the first Sunday of April to the Saturday before the last Sunday of October.
- **Invierno:** from the last Sunday of October to the Saturday before the first Sunday of April.
- Examples:
  - 2026: verano 5-Apr to 24-Oct; invierno from 25-Oct-2026 to 3-Apr-2027.
  - 2025: verano 6-Apr to 25-Oct.
  - 2024: verano 7-Apr to 26-Oct.

| Season | Day | Base | Intermedio | Punta |
|---|---|---|---|---|
| Verano | Mon–Fri | 0:00–6:00 | 6:00–20:00, 22:00–24:00 | 20:00–22:00 |
| Verano | Saturday | 0:00–7:00 | 7:00–24:00 | — |
| Verano | Sunday/holiday | 0:00–19:00 | 19:00–24:00 | — |
| Invierno | Mon–Fri | 0:00–6:00 | 6:00–18:00, 22:00–24:00 | 18:00–22:00 |
| Invierno | Saturday | 0:00–8:00 | 8:00–19:00, 21:00–24:00 | 19:00–21:00 |
| Invierno | Sunday/holiday | 0:00–18:00 | 18:00–24:00 | — |

Holidays are the mandatory rest days of the Ley Federal del Trabajo, Art. 74, billed as Sunday (secondary source). Hours of punta per year: summer weekdays 2 h/day; winter weekdays 4 h/day plus 2 h on Saturdays.

## 4. GDMTO versus GDMTH threshold and reclassification

- **Official** (Tabla 1 of A/158/2024 and of CT/11.SE/8-2025):
  - GDMTO = "Gran Demanda (menor a 100 kW-mes) en Media Tensión Ordinaria", formerly OM.
  - GDMTH = "Gran Demanda (igual o mayor a 100 kW-mes) en Media Tensión Horaria", formerly HM/HMC.
- **CFE text** (2018 CFE presentation on the final tariffs; danersolar.com quoting the CFE page):
  - GDMTH applies to MV services "con una demanda de 100 kilowatts o más".
  - A GDMTH user who records "durante 12 meses consecutivos valores de demanda inferiores a 100 kilowatts" **may request** a move to GDMTO. The move is at the user's request, not automatic.
  - Contracted demand may not be below 60% of connected load nor below 100 kW (secondary).
- **Not verified:** the exact trigger for a forced GDMTO → GDMTH move, meaning whether a single month at or above 100 kW suffices or a run of months is needed. Secondary sources only say a user "passes to GDMTH on reaching 100 kW" (climatta.com). In practice CFE assigns the tariff by contracted or measured demand at contract stage, so confirm with the CFE division.

## 5. Sources

**Methodology / rules**

- CRE Acuerdo A/158/2024 (adopted 13-Dec-2024; 2025 tariff methodology, Tablas 1–5): https://sidof.segob.gob.mx/notas/docFuente/5747760. The DOF date appears to be 24-Jan-2025, inferred from SIDOF image paths.
- CNE Acuerdo CT/11.SE/8-2025 (adopted 29-Dec-2025; 2026 methodology, the 2026 equivalent of A/158/2024; publication ordered by oficio of 23-Jan-2026): https://sidof.segob.gob.mx/notas/docFuente/5783862
- CFE GDMTH page (blocked for direct reading; cited by secondary sources): https://app.cfe.mx/Aplicaciones/CCFE/Tarifas/TarifasCREIndustria/Tarifas/GranDemandaMTH.aspx
- 2018 CFE presentation on the final tariffs (100 kW and 12-month rule): https://sdc67fa33af33e8e9.jimcontent.com/download/version/1522677268/module/14828705922/name/Tarifas%20Finales%20del%20Suministro%20Basico.pdf
- Secondary sources:
  - https://psenergia.com.mx/servicios/almacenamiento/cargo-por-capacidad
  - https://danersolar.com/blog/tarifa-gdmth
  - https://batuenergy.com/blog/gdmto-vs-gdmth
  - https://www.climatta.com/es/blog/recibo-cfe/tarifa-gdmth
  - https://ideatuinmueble.com/tarifas-cfe/centro-oriente
  - https://batuenergy.com/tarifas/gdmth
  - https://tarifacfe.com/tarifa-gdmth/division-cte

**Monthly tariff tables** (Anexo II, División Centro Oriente). The URL for each month is in the CSV.

- 2024 (CRE acuerdos):
  - Jan: A/076/2023
  - Feb: A/009/2024
  - Apr: A/053/2024
  - May: A/058/2024
  - Jun: A/064/2024
  - Jul: A/074/2024 (DOF 19-Jul-2024)
  - Aug: A/088/2024
  - Sep: A/106/2024 (DOF 25-Sep-2024)
  - Oct: A/112/2024
  - Nov: A/132/2024
  - Dec: A/149/2024 (the Aug, Oct, Nov and Dec acuerdos were published in the DOF on 6–9 Jan 2025)
- 2025:
  - Jan and Feb are CRE acuerdos (Feb = A/013/2025); Mar = A/021/2025 (DOF 27-Mar-2025).
  - From June onward they are CFE notices: Jun (DOF 27-Jun-2025), Jul (DOF 29-Jul-2025), Aug (DOF 21-Aug-2025), Sep (DOF 22-Sep-2025), Oct (DOF 23-Oct-2025), Nov (DOF 28-Nov-2025), Dec (DOF 24-Dec-2025).
- 2026 (CFE notices under the CNE):
  - Jan: SIDOF 5779203
  - Feb: SIDOF 5781736
  - Mar: DOF 5784039, read through the sdv.com.mx mirror
  - Apr: SIDOF 5786266
  - May: SIDOF 5788863
  - Jun: SIDOF 5791865 (DOF 26-Jun-2026)
  - Jul: SIDOF 5795184 (DOF 31-Jul-2026)
  - Aug: SIDOF 5797487
  - Sep: SIDOF 5800039
  - Oct: secondary only
