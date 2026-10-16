"""Parameter handling.

Any numeric input in a case file can be written as
  * a number                -> fixed value
  * [central, low, high]    -> triangular distribution (mode = central) for Monte Carlo
  * {value: <number|list>, status: ..., source: ..., mc: false}
Parameters are collected into a flat ParamSet keyed by dotted names, e.g.
``measures.E1.saving_frac`` or ``pv.cost_per_W``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

STATUSES = {"measured", "official", "literature", "quote", "design", "assumption", "regulatory", "derived"}


@dataclass
class Param:
    name: str
    central: float
    low: float
    high: float
    status: str = "assumption"
    source: str = ""
    mc: bool = True

    @property
    def uncertain(self) -> bool:
        return self.mc and self.low < self.high


def parse(name: str, spec, default_status="assumption") -> Param:
    status, source, mc = default_status, "", True
    if isinstance(spec, dict):
        status = spec.get("status", status)
        source = spec.get("source", "")
        mc = spec.get("mc", True)
        spec = spec["value"]
    if isinstance(spec, (list, tuple)):
        if len(spec) != 3:
            raise ValueError(f"{name}: expected [central, low, high], got {spec}")
        c, lo, hi = (float(x) for x in spec)
        if not lo <= c <= hi:
            raise ValueError(f"{name}: central value must lie within [low, high]")
    else:
        c = lo = hi = float(spec)
    return Param(name, c, lo, hi, status, source, mc)


@dataclass
class ParamSet:
    params: dict = field(default_factory=dict)

    def add(self, name, spec, default_status="assumption"):
        self.params[name] = parse(name, spec, default_status)
        return self.params[name]

    def central(self) -> dict:
        return {k: p.central for k, p in self.params.items()}

    def sample(self, rng: np.random.Generator) -> dict:
        out = {}
        for k, p in self.params.items():
            out[k] = float(rng.triangular(p.low, p.central, p.high)) if p.uncertain else p.central
        return out

    def table(self):
        return [dict(name=p.name, central=p.central, low=p.low, high=p.high, status=p.status, source=p.source,
                     monte_carlo=p.uncertain) for p in self.params.values()]
