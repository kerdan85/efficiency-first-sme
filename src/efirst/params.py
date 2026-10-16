"""Model parameters.

Each entry: (central, low, high, status, source_key).
status: 'measured' | 'official' | 'literature' | 'quote' | 'assumption'.
Triangular distributions (low, mode=central, high) are used in the Monte Carlo.
Monetary values are 2026 MXN excluding VAT (VAT is recoverable for firms).
"""

PARAMS = {
    # --- Finance -------------------------------------------------------
    "discount_rate": (0.10, 0.06, 0.14, "assumption", "student report; sensitivity"),
    "horizon_yr": (20, 20, 20, "assumption", "student report"),
    "tariff_real_escalation": (0.0, -0.01, 0.02, "assumption", "constant real tariffs"),
    # --- Grid ------------------------------------------------------------
    "ef_grid_t_per_MWh": (0.444, 0.444, 0.444, "official", "semarnat2025fesen"),
    "gas_share_generation": (0.638, 0.60, 0.68, "official", "sener2025plan Tabla 2.2"),
    "ccgt_heat_rate_GJ_per_MWh": (7.2, 6.5, 8.5, "assumption", "typical CCGT 42-55% LHV"),
    "gas_import_share": (0.74, 0.70, 0.78, "official-derived", "eia2025mexico 6.4/8.6 Bcf/d"),
    # --- Measure E1: compressed air package -------------------------------
    "ca_saving_frac": (0.20, 0.10, 0.30, "literature", "doe2016compressed leaks 20-30% -> <10%; 1%/2 psi"),
    "ca_capex": (50_000, 35_000, 80_000, "quote", "student estimate"),
    "ca_om": (8_000, 5_000, 12_000, "assumption", "annual ultrasonic leak survey"),
    "ca_life": (10, 10, 10, "assumption", ""),
    # --- Measure E2: servo motors on sewing machines ----------------------
    "sew_motor_share": (0.70, 0.50, 0.85, "assumption", "share of stitching-area energy in clutch motors"),
    "sew_saving_frac": (0.65, 0.50, 0.75, "literature", "nemesa2023"),
    "sew_motor_kW": (0.35, 0.25, 0.45, "literature", "clutch motor running power"),
    "sew_cost_per_unit": (3_800, 2_800, 5_500, "assumption", "installed servo motor, market"),
    "sew_life": (10, 10, 10, "assumption", ""),
    # --- Measure E3: insulation of heated platens / barrels ---------------
    "heat_share": (0.65, 0.50, 0.80, "assumption", "heater share of vulcanising+injection energy"),
    "heat_saving_frac": (0.20, 0.10, 0.30, "literature", "kent2018; grey literature 15-30%"),
    "heat_capex": (100_000, 60_000, 150_000, "assumption", "jackets + controls"),
    "heat_life": (8, 8, 8, "assumption", ""),
    # --- Measure E4: base-load (idle) control -----------------------------
    "base_saving_frac": (0.10, 0.05, 0.20, "literature", "mouzon2007; kara2011"),
    "base_capex": (40_000, 20_000, 70_000, "assumption", "timers, contactors, sub-meters"),
    "base_life": (10, 10, 10, "assumption", ""),
    # --- Measure E5: power-factor correction ------------------------------
    "pfc_kvar": (50, 50, 50, "quote", "student design"),
    "pfc_pf_after": (0.97, 0.95, 0.99, "assumption", "automatic bank"),
    "pfc_capex": (85_000, 70_000, 110_000, "quote", "student estimate"),
    "pfc_life": (15, 15, 15, "assumption", ""),
    # --- Supply S1: rooftop PV ---------------------------------------------
    "pv_kWp": (163.8, 163.8, 163.8, "design", "252 x 650 W modules (student design)"),
    "pv_cost_per_W": (11.0, 9.0, 14.0, "quote", "student quote 1.8 MMXN / 163.8 kWp"),
    "pv_PR": (0.80, 0.75, 0.85, "literature", "reich2012"),
    "pv_tilt_deg": (20, 20, 20, "design", "latitude tilt"),
    "pv_albedo": (0.20, 0.20, 0.20, "assumption", ""),
    "pv_degradation": (0.005, 0.003, 0.008, "literature", "typical crystalline Si"),
    "pv_om_frac": (0.01, 0.005, 0.015, "assumption", "of capex per year"),
    "pv_inverter_repl_frac": (0.10, 0.08, 0.15, "assumption", "of capex at year 12"),
    "pv_life": (25, 25, 25, "literature", ""),
    "pv_m2_per_kWp": (5.5, 5.0, 6.5, "assumption", "650 W module 3.1 m2 incl. spacing"),
    "pv_demand_credit": (1.0, 0.0, 1.0, "regulatory", "net metering reduces Q-based billed demand"),
    # --- Thermal / fuel substitution (parametric, per GJ useful heat) ------
    "lpg_price_MXN_per_kg_incl_vat": (19.76, 19.76, 19.76, "official", "CNE max price, PROFECO 11-17 Oct 2026"),
    "lpg_LHV_MJ_per_kg": (47.3, 47.3, 47.3, "literature", "IPCC 2006 Vol.2 Table 1.2 NCV"),
    "lpg_EF_kg_per_GJ": (63.1, 63.1, 63.1, "literature", "IPCC 2006 Vol.2 Table 2.2"),
    "ng_EF_kg_per_GJ": (56.1, 56.1, 56.1, "literature", "IPCC 2006 Vol.2 Table 2.2"),
    "ng_enduser_markup": (2.0, 1.5, 3.0, "assumption", "transport+distribution over IPGN"),
    "boiler_eff": (0.85, 0.80, 0.90, "assumption", ""),
    "hp_cop": (3.0, 2.5, 4.0, "literature", "arpagaus2018; schlosser2020 (<100 C)"),
    "ca_heat_recovery_frac": (0.70, 0.50, 0.80, "literature", "doe2016compressed >80% available"),
}

VAT = 0.16
HOURS_OPERATING_PER_MONTH = 10 * 22 + 5 * 4  # Mon-Fri 8-18 h, Sat 8-13 h (site description)


def central():
    return {k: v[0] for k, v in PARAMS.items()}
