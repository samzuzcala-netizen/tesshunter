"""P10 TLS-duration boundary around the unchanged read-only P9 event matcher.

P12 held-out copy of ``p10/protocol/p9_scoring_adapter.py`` (4c edit 7): the matcher is the held-out
``scoring.py`` copy and ``tesshunter.stage_c`` comes from the frozen snapshot; ``tls_candidate`` exposes
the floored candidate the matcher is given.
"""
from pathlib import Path
import sys

import numpy as np

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from common import frozen_imports
frozen_imports()
import scoring
from tesshunter.stage_c import duration_summary


def tls_candidate(times, blind, cadence_s=None):
    """The Stage C blind ephemeris with the TLS duration floored at the cadence (as P10 scored it)."""
    if cadence_s is None:
        cadence_s = float(np.median(np.diff(np.sort(times)))) * 86400 if len(times) > 1 else 200.0
    summary = duration_summary(blind, cadence_s)
    return {"period": summary["period"], "t0": summary["T0_btjd"], "duration": summary["duration_days"]}


def match_tls_signal(times, truth, blind, ratio=1, cadence_s=None):
    """Keep P9 matching and truth unchanged; floor the reported TLS candidate duration."""
    if cadence_s is None:
        cadence_s = float(np.median(np.diff(np.sort(times)))) * 86400 if len(times) > 1 else 200.0
    summary = duration_summary(blind, cadence_s)
    candidate = {"period": summary["period"], "t0": summary["T0_btjd"], "duration": summary["duration_days"]}
    result = scoring.match_signal(times, truth, candidate, ratio=ratio)
    return {"match": result, "candidate": candidate, "tls_duration_floor": summary["duration_floor"]}
