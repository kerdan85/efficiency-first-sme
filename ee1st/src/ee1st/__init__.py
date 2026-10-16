"""ee1st: Energy Efficiency First appraisal of demand- and supply-side options for SMEs."""
__version__ = "1.0.0"

from .case import load_case  # noqa: F401
from .core import context, evaluate, cce, pv_lcoe, pathways  # noqa: F401
