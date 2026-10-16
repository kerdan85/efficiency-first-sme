"""Tariff models.

``q_based_demand``  Demand charges billed on min(measured kW, Q/(24 d F_C)), as in Mexican CFE
                    GDMTO; any kWh avoided reduces energy *and* demand charges.
``energy_demand``   Energy charge plus a demand charge on measured peak; measures reduce the peak by
                    ``peak_coincidence`` times their average-power reduction; PV does not reduce it.
``flat``            Single energy price (plus optional fixed charge).
Power-factor rules: ``mx_cfe`` (surcharge 3/5(90/PF-1), bonus 1/4(1-90/PF), caps 120 %/2.5 %) or ``none``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def pf_adjustment(pf: float, rule: str) -> float:
    if rule == "none" or pf is None or np.isnan(pf):
        return 0.0
    if rule == "mx_cfe":
        p = 100.0 * pf
        if p < 90.0:
            return min(round(3.0 / 5.0 * (90.0 / p - 1.0) * 100.0, 1), 120.0) / 100.0
        return -min(round(1.0 / 4.0 * (1.0 - 90.0 / p) * 100.0, 1), 2.5) / 100.0
    raise ValueError(f"unknown power-factor rule {rule}")


class Tariff:
    def __init__(self, cfg: dict, schedule: pd.DataFrame):
        self.type = cfg.get("type", "q_based_demand")
        self.pf_rule = cfg.get("pf_rule", "none")
        self.load_factor = float(cfg.get("load_factor", 0.55))
        self.peak_coincidence = float(cfg.get("peak_coincidence", 1.0))
        self.schedule = schedule.copy()
        cur = str(cfg.get("current_month", schedule.month.iloc[-1]))
        self.row = schedule[schedule.month == cur].iloc[0]
        for col in ("fixed", "energy", "distribution", "capacity", "demand"):
            if col not in self.schedule.columns:
                self.schedule[col] = 0.0
        self.row = self.schedule[self.schedule.month == cur].iloc[0]

    # ------------------------------------------------------------------
    def billed_demand(self, q, days, dmax=None):
        if self.type == "q_based_demand":
            dq = np.asarray(q, float) / (24.0 * np.asarray(days, float) * self.load_factor)
            return dq if dmax is None else np.minimum(np.asarray(dmax, float), dq)
        if self.type == "energy_demand":
            return np.asarray(dmax, float)
        return np.zeros_like(np.asarray(q, float))

    def bill(self, q, days, pf, row=None, q_for_demand=None, demand_credit=1.0, dmax=None):
        """Pre-tax bill per month. ``q_for_demand`` lets on-site generation reduce energy but not demand."""
        r = self.row if row is None else row
        q = np.asarray(q, float)
        if self.type == "q_based_demand":
            qd = q if q_for_demand is None else demand_credit * q + (1 - demand_credit) * np.asarray(q_for_demand, float)
            db = self.billed_demand(qd, days)
            dem = db * (r["distribution"] + r["capacity"])
        elif self.type == "energy_demand":
            dem = np.asarray(dmax, float) * (r["demand"] + r["distribution"] + r["capacity"])
        else:
            dem = 0.0
        pre = r["fixed"] + q * r["energy"] + dem
        adj = np.array([pf_adjustment(x, self.pf_rule) for x in np.atleast_1d(pf)])
        return pre * (1 + adj)

    def marginal_value(self, days=30.4) -> float:
        r = self.row
        if self.type == "q_based_demand":
            return float(r["energy"] + (r["distribution"] + r["capacity"]) / (24 * days * self.load_factor))
        if self.type == "energy_demand":
            # a kWh saved uniformly over the month cuts the average power by 1/(24 d) kW; a fraction
            # ``peak_coincidence`` of that reaches the billed peak
            return float(r["energy"] + self.peak_coincidence * (r["demand"] + r["distribution"] + r["capacity"]) / (24 * days))
        return float(r["energy"])

    def validate(self, billing: pd.DataFrame, price_col: str) -> pd.DataFrame:
        """Rebuild each historical bill with month-specific charges and compare with the reported price."""
        d = billing.merge(self.schedule, on="month")
        out = []
        for _, r in d.iterrows():
            if self.type == "q_based_demand":
                dem = r.max_demand_kW * (r.distribution + r.capacity)
            elif self.type == "energy_demand":
                dem = r.max_demand_kW * (r.demand + r.distribution + r.capacity)
            else:
                dem = 0.0
            pre = r.fixed + r.energy_kWh * r.energy + dem
            bill = pre * (1 + pf_adjustment(r.get("power_factor", np.nan), self.pf_rule))
            out.append(dict(month=r.month, model_price=bill / r.energy_kWh, reported_price=r[price_col],
                            dq_kW=r.energy_kWh / (24 * r.days * self.load_factor), recorded_kW=r.max_demand_kW))
        o = pd.DataFrame(out)
        o["error"] = o.reported_price / o.model_price - 1
        return o
