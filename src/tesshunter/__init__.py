"""tesshunter — TESS transit candidate search pipeline."""

__version__ = "0.1.0"

from . import pipeline  # noqa: E402,F401  (canonical entry-point module)
from .pipeline import (  # noqa: E402,F401
    SearchTargetResult,
    load_search_config,
    search_target,
    search_targets_from_config,
)

__all__ = [
    "pipeline",
    "SearchTargetResult",
    "search_target",
    "load_search_config",
    "search_targets_from_config",
]
