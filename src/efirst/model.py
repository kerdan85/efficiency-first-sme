"""Core model: tariff, baseline, measures, PV, cash flows, indicators."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .params import HOURS_OPERATING_PER_MONTH, central

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"

GDMTO_FC = 0.55          # load factor for Q-based billed demand (DOF 24-01-2025, Tabla 2)
CURRENT_TARIFF_MONTH = "2026-10"


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
def load_billing() -> pd.DataFrame:
    d = pd.read_csv(RAW / "billing_monthly.csv")
    d["days"] = pd.to_datetime(d["month"]).dt.days_in_month
    d["mon"] = pd.to_datetime(d["month"]).dt.month
    return d


def load_tariffs() -> pd.DataFrame:
    return pd.read_csv(RAW / "cfe_gdmto_centro_oriente.csv")


def load_areas() -> pd.DataFrame:
    return pd.read_csv(RAW / "area_disaggregation_reference_month.csv")


def load_climate() -> pd.DataFrame:
    return pd.read_csv(RAW / "nasa_power_climatology_pachuca.csv")


def reference_year(b: pd.DataFrame) -> pd.DataFrame:
    """Latest 12 measured months (May 2025 - April 2026)."""
    r = b[(b.month >= "2025-05") & (b.month <= "2026-04")].copy()
    assert len(r) == 12
    return r.reset_index(drop=True)


# ----------------------------------------------------------------------------
# Tariff (CFE GDMTO, Centro Oriente)
# ----------------------------------------------------------------------------
def pf_adjustment(pf: float) -> float:
    """Fractional surcharge (+) or bonus (-) on the bill (DOF 24-01-2025, 5.5)."""
    p = 100.0 * pf
    if p < 90.0:
        pct = round(3.0 / 5.0 * (90.0 / p - 1.0) * 100.0, 1)
        return min(pct, 120.0) / 100.0
    pct = round(1.0 / 4.0 * (1.0 - 90.0 / p) * 100.0, 1)
    return -min(pct, 2.5) / 100.0


def billed_demand_kW(q_kwh, days, dmax=None):
    dq = np.asarray(q_kwh, float) / (24.0 * np.asarray(days, float) * GDMTO_FC)
    if dmax is None:
        return dq
    return np.minimum(np.asarray(dmax, float), dq)


def monthly_bill(q_kwh, days, pf, tariff_row, demand_credit=1.0, q_for_demand=None):
    """Pre-VAT bill in MXN for one or several months.

    q_for_demand allows a case where on-site generation reduces energy but not
    billed demand (demand_credit < 1 interpolates between the two cases).
    """
    q = np.asarray(q_kwh, float)
    qd = q if q_for_demand is None else (
        demand_credit * q + (1 - demand_credit) * np.asarray(q_for_demand, float))
    db = billed_demand_kW(qd, days)
    pre = (tariff_row["fixed_MXN_per_month"] + q * tariff_row["energy_MXN_per_kWh"]
           + db * (tariff_row["distribution_MXN_per_kW"] + tariff_row["capacity_MXN_per_kW"]))
    adj = np.array([pf_adjustment(x) for x in np.atleast_1d(pf)])
    return pre * (1 + adj)


def validate_tariff_model(b: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    """Reproduce reported average price with month-specific official charges."""
    d = b.merge(t, on="month")
    out = []
    for _, r in d.iterrows():
        pre = (r.fixed_MXN_per_month + r.energy_kWh * r.energy_MXN_per_kWh
               + r.max_demand_kW * (r.distribution_MXN_per_kW + r.capacity_MXN_per_kW))
        bill = pre * (1 + pf_adjustment(r.power_factor))
        out.append(dict(month=r.month, model_price=bill / r.energy_kWh,
                        reported_price=r.avg_price_MXN_per_kWh_reported,
                        dq_kW=r.energy_kWh / (24 * r.days * GDMTO_FC),
                        recorded_kW=r.max_demand_kW))
    o = pd.DataFrame(out)
    o["error"] = o.reported_price / o.model_price - 1
    return o


def marginal_value_per_kWh(t_row, days=30.4):
    """Avoided pre-VAT cost of one kWh under Q-based billed demand."""
    return t_row["energy_MXN_per_kWh"] + (
        t_row["distribution_MXN_per_kW"] + t_row["capacity_MXN_per_kW"]) / (24 * days * GDMTO_FC)


# ----------------------------------------------------------------------------
# Baseline regression (production-normalised EnB)
# ----------------------------------------------------------------------------
def ols(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    b, a = np.polyfit(x, y, 1)
    yhat = a + b * x
    r2 = 1 - np.sum((y - yhat) ** 2) / np.sum((y - y.mean()) ** 2)
    n = len(x)
    se = math.sqrt(np.sum((y - yhat) ** 2) / (n - 2))
    cv = se / y.mean()
    sxx = np.sum((x - x.mean()) ** 2)
    se_a = se * math.sqrt(1 / n + x.mean() ** 2 / sxx)
    se_b = se / math.sqrt(sxx)
    return dict(slope=b, intercept=a, r2=r2, n=n, cv_rmse=cv, se_intercept=se_a, se_slope=se_b)


def baseline_models(b: pd.DataFrame) -> dict:
    p = b.dropna(subset=["production_pairs"]).copy()
    res = {}
    res["all_25"] = ols(p.production_pairs, p.energy_kWh)
    # Months documented by the audit team as extraordinary (24-h shifts, Nov 2025-Jan 2026)
    m = ~p.month.isin(["2025-11", "2025-12", "2026-01"])
    res["excl_24h_shift"] = ols(p[m].production_pairs, p[m].energy_kWh)
    # Original student subset (16 months, corrected Oct-2024 value)
    s = p[(p.month <= "2025-06") | (p.month == "2025-09")]
    res["student_subset_corrected"] = ols(s.production_pairs, s.energy_kWh)
    s2 = s.copy(); s2.loc[s2.month == "2024-10", "energy_kWh"] = 34200
    res["student_subset_as_reported"] = ols(s2.production_pairs, s2.energy_kWh)
    return res


# ----------------------------------------------------------------------------
# PV (monthly, isotropic sky, Klein 1977 / Liu-Jordan)
# ----------------------------------------------------------------------------
def pv_monthly_yield_kWh_per_kWp(clim: pd.DataFrame, lat=20.0965, tilt=20.0, albedo=0.2, PR=0.8):
    rec_days = [17, 47, 75, 105, 135, 162, 198, 228, 258, 288, 318, 344]
    days_in = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    phi = math.radians(lat); beta = math.radians(tilt)
    out = []
    for i, r in clim.iterrows():
        n = rec_days[i]
        dec = math.radians(23.45 * math.sin(math.radians(360 * (284 + n) / 365)))
        ws = math.acos(-math.tan(phi) * math.tan(dec))
        wsp = min(ws, math.acos(-math.tan(phi - beta) * math.tan(dec)))
        num = (math.cos(phi - beta) * math.cos(dec) * math.sin(wsp) + wsp * math.sin(phi - beta) * math.sin(dec))
        den = (math.cos(phi) * math.cos(dec) * math.sin(ws) + ws * math.sin(phi) * math.sin(dec))
        Rb = num / den
        H = r.GHI_kWh_m2_d; Hd = r.DHI_kWh_m2_d
        Ht = H * ((1 - Hd / H) * Rb + Hd / H * (1 + math.cos(beta)) / 2 + albedo * (1 - math.cos(beta)) / 2)
        out.append(dict(month=i + 1, H=H, Ht=Ht, yield_kWh_per_kWp=Ht * PR * days_in[i], days=days_in[i]))
    return pd.DataFrame(out)


# ----------------------------------------------------------------------------
# Measures
# ----------------------------------------------------------------------------
def annuity(rate, n):
    return rate / (1 - (1 + rate) ** -n) if rate > 0 else 1 / n


def area_shares():
    a = load_areas()
    return dict(zip(a.area_en, a.share))


def measure_savings(ref: pd.DataFrame, P: dict, intercept_kWh: float, measures: list[str]):
    """Monthly kWh after applying measures sequentially (no double counting).

    Order: E4 base-load control (scales all end uses), then component measures.
    Returns (q_after, details) with per-measure monthly savings.
    """
    sh = area_shares()
    q = ref.energy_kWh.to_numpy(float).copy()
    det = {}
    if "E4" in measures:
        frac_base = np.minimum(intercept_kWh / q, 1.0)
        s = P["base_saving_frac"] * frac_base * q
        det["E4"] = s; q = q - s
    # end-use energy after E4 (shares constant)
    ca = sh["compressed air room"] * q
    sew = sh["stitching (sewing)"] * q
    heat_areas = (sh["vulcanising"] + sh["sole injection moulding"]) * q
    if "E1" in measures:
        det["E1"] = P["ca_saving_frac"] * ca
    if "E2" in measures:
        det["E2"] = P["sew_saving_frac"] * P["sew_motor_share"] * sew
    if "E3" in measures:
        det["E3"] = P["heat_saving_frac"] * P["heat_share"] * heat_areas
    for k in ("E1", "E2", "E3"):
        if k in det:
            q = q - det[k]
    return q, det


def measure_capex(P: dict, ref: pd.DataFrame, intercept_kWh: float):
    sh = area_shares()
    sew_motor_kWh_month = sh["stitching (sewing)"] * ref.energy_kWh.mean() * P["sew_motor_share"]
    n_machines = sew_motor_kWh_month / (P["sew_motor_kW"] * HOURS_OPERATING_PER_MONTH)
    return {
        "E1": (P["ca_capex"], P["ca_om"], P["ca_life"]),
        "E2": (n_machines * P["sew_cost_per_unit"], 0.0, P["sew_life"]),
        "E3": (P["heat_capex"], 0.0, P["heat_life"]),
        "E4": (P["base_capex"], 0.0, P["base_life"]),
        "E5": (P["pfc_capex"], 0.0, P["pfc_life"]),
    }, n_machines


# ----------------------------------------------------------------------------
# Scenario evaluation
# ----------------------------------------------------------------------------
def tariff_row(t: pd.DataFrame, month=CURRENT_TARIFF_MONTH):
    return t[t.month == month].iloc[0]


def annual_bill(q, ref, P, tr, pf=None, q_for_demand=None):
    pf = ref.power_factor.to_numpy() if pf is None else pf
    return float(np.sum(monthly_bill(q, ref.days.to_numpy(), pf, tr,
                                     demand_credit=P["pv_demand_credit"], q_for_demand=q_for_demand)))


def evaluate(portfolio: dict, P: dict | None = None, data: dict | None = None):
    """Evaluate a portfolio: {'measures': [...], 'pv_kWp': float, 'pfc': bool}.

    Returns a dict of annual indicators (year 1) and 20-yr NPV.
    """
    P = P or central()
    data = data or load_all()
    ref, tr, intercept, yld = data["ref"], data["tariff"], data["intercept"], data["pv_yield"]
    days = ref.days.to_numpy()
    q0 = ref.energy_kWh.to_numpy(float)
    pf0 = ref.power_factor.to_numpy()
    bill0 = annual_bill(q0, ref, P, tr, pf0)

    meas = [m for m in portfolio.get("measures", []) if m != "E5"]
    q_ee, det = measure_savings(ref, P, intercept, meas)
    pfc = portfolio.get("pfc", False) or "E5" in portfolio.get("measures", [])
    pf1 = np.full(12, P["pfc_pf_after"]) if pfc else pf0

    kWp = portfolio.get("pv_kWp", 0.0)
    # monthly PV generation aligned with reference months (calendar month)
    gen = np.array([yld.loc[yld.month == m, "yield_kWh_per_kWp"].iloc[0] for m in ref.mon]) * kWp
    gen = gen * (P["pv_PR"] / 0.80)  # yield table computed at PR=0.80
    q_net = np.maximum(q_ee - gen, 0.0)
    surplus = np.maximum(gen - q_ee, 0.0)
    bill1 = annual_bill(q_net, ref, P, tr, pf1, q_for_demand=q_ee)

    capex_tab, n_mach = measure_capex(P, ref, intercept)
    items = []
    for m in portfolio.get("measures", []):
        items.append((m,) + capex_tab[m])
    if pfc and "E5" not in portfolio.get("measures", []):
        items.append(("E5",) + capex_tab["E5"])
    if kWp > 0:
        cap = kWp * 1000 * P["pv_cost_per_W"]
        items.append(("PV", cap, P["pv_om_frac"] * cap, P["pv_life"]))

    H = int(P["horizon_yr"]); r = P["discount_rate"]
    savings_y1 = bill0 - bill1
    cf = np.zeros(H + 1)
    capex0 = 0.0
    for name, cap, om, life in items:
        capex0 += cap
        cf[0] -= cap
        for y in range(1, H + 1):
            cf[y] -= om
            if life < H and y % int(life) == 0 and y < H:
                cf[y] -= cap  # like-for-like reinvestment
        if name != "PV":
            # straight-line residual value of the last (re)investment at the horizon
            last = (H // int(life)) * int(life) if life < H else 0
            if last == H:
                last = H - int(life)
            remaining = (last + life) - H
            if remaining > 0:
                cf[H] += cap * remaining / life
        if name == "PV":
            cf[12] -= P["pv_inverter_repl_frac"] * cap
    # PV degradation affects only the PV share of savings: recompute bill per year approx.
    pv_part = 0.0
    if kWp > 0:
        bill_ee_only = annual_bill(q_ee, ref, P, tr, pf1)
        pv_part = bill_ee_only - bill1
    other_part = savings_y1 - pv_part
    for y in range(1, H + 1):
        esc = (1 + P["tariff_real_escalation"]) ** (y - 1)
        deg = (1 - P["pv_degradation"]) ** (y - 1)
        cf[y] += esc * (other_part + pv_part * deg)
    # residual value of PV beyond horizon (straight-line)
    if kWp > 0 and P["pv_life"] > H:
        cf[H] += kWp * 1000 * P["pv_cost_per_W"] * (P["pv_life"] - H) / P["pv_life"]
    disc = (1 + r) ** -np.arange(H + 1)
    npv = float(np.sum(cf * disc))
    grid0 = q0.sum(); grid1 = q_net.sum()
    ef = P["ef_grid_t_per_MWh"]
    co2_0 = grid0 / 1000 * ef; co2_1 = grid1 / 1000 * ef
    gas_GJ = lambda kwh: kwh / 1000 * P["gas_share_generation"] * P["ccgt_heat_rate_GJ_per_MWh"]
    dq_peak0 = billed_demand_kW(q0, days).max()
    dq_peak1 = billed_demand_kW(q_ee, days).max()  # PV cannot be relied on for the measured peak
    months_over_100 = int(np.sum(billed_demand_kW(q_ee, days) >= 100))
    # bill exposure to a +50 % shock in the energy charge (gas-price pass-through proxy)
    tr_shock = tr.copy(); tr_shock["energy_MXN_per_kWh"] *= 1.5
    shock0 = annual_bill(q0, ref, P, tr_shock, pf0) - bill0
    shock1 = annual_bill(q_net, ref, P, tr_shock, pf1, q_for_demand=q_ee) - bill1
    saved_kWh = grid0 - grid1
    ann = annuity(r, H)
    om_total = sum(om for _, _, om, _ in items)
    net_y1 = savings_y1 - om_total
    payback = capex0 / net_y1 if net_y1 > 0 else float("nan")  # simple payback, years
    return dict(
        bill0=bill0, bill1=bill1, savings_y1=savings_y1, capex=capex0, npv=npv,
        payback_yr=payback,
        grid0_MWh=grid0 / 1000, grid1_MWh=grid1 / 1000, ee_saved_MWh=(q0.sum() - q_ee.sum()) / 1000,
        pv_gen_MWh=gen.sum() / 1000, pv_surplus_MWh=surplus.sum() / 1000,
        grid_saved_MWh=saved_kWh / 1000, grid_saved_frac=saved_kWh / grid0,
        co2_0_t=co2_0, co2_1_t=co2_1, co2_saved_t=co2_0 - co2_1,
        gas_avoided_GJ=gas_GJ(saved_kWh), imported_gas_avoided_GJ=gas_GJ(saved_kWh) * P["gas_import_share"],
        billed_peak0_kW=dq_peak0, billed_peak1_kW=dq_peak1, months_over_100kW=months_over_100,
        shock_exposure0=shock0, shock_exposure1=shock1,
        cost_per_t=(-npv * ann) / ((co2_0 - co2_1)) if co2_0 > co2_1 else float("nan"),
        n_sewing_machines=n_mach, pf_after=float(np.mean(pf1)),
        cashflow=cf,
    )


def load_all(P=None):
    P = P or central()
    b = load_billing(); t = load_tariffs(); ref = reference_year(b)
    bm = baseline_models(b)
    clim = load_climate()
    yld = pv_monthly_yield_kWh_per_kWp(clim, tilt=P["pv_tilt_deg"], albedo=P["pv_albedo"], PR=0.80)
    return dict(billing=b, tariffs=t, ref=ref, tariff=tariff_row(t), baseline=bm,
                intercept=bm["excl_24h_shift"]["intercept"], pv_yield=yld)


def cce(measure: str, P=None, data=None):
    """Cost of conserved energy (MXN/kWh) and annual savings (kWh) of one measure alone."""
    P = P or central(); data = data or load_all(P)
    ref = data["ref"]
    _, det = measure_savings(ref, P, data["intercept"], [measure])
    kwh = det[measure].sum()
    tab, _ = measure_capex(P, ref, data["intercept"])
    cap, om, life = tab[measure]
    return (cap * annuity(P["discount_rate"], life) + om) / kwh, kwh


def pv_lcoe(P=None, data=None, kWp=163.8):
    P = P or central(); data = data or load_all(P)
    y = data["pv_yield"].yield_kWh_per_kWp.sum() * P["pv_PR"] / 0.80 * kWp
    cap = kWp * 1000 * P["pv_cost_per_W"]
    r = P["discount_rate"]; n = P["pv_life"]
    disc = (1 + r) ** -np.arange(1, n + 1)
    energy = np.sum(y * (1 - P["pv_degradation"]) ** np.arange(n) * disc)
    costs = cap + np.sum(P["pv_om_frac"] * cap * disc) + P["pv_inverter_repl_frac"] * cap * (1 + r) ** -12
    return costs / energy, y
