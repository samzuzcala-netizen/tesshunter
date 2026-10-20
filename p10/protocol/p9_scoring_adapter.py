"""P10 TLS-duration boundary around the unchanged read-only P9 event matcher."""
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "p9"))
from p9 import scoring
from tesshunter.stage_c import duration_summary


def match_tls_signal(times, truth, blind, ratio=1, cadence_s=None):
    """Keep P9 matching and truth unchanged; floor the reported TLS candidate duration."""
    if cadence_s is None:
        cadence_s = float(np.median(np.diff(np.sort(times)))) * 86400 if len(times) > 1 else 200.0
    summary = duration_summary(blind, cadence_s)
    candidate = {"period": summary["period"], "t0": summary["T0_btjd"], "duration": summary["duration_days"]}
    result = scoring.match_signal(times, truth, candidate, ratio=ratio)
    return {"match": result, "candidate": candidate, "tls_duration_floor": summary["duration_floor"]}
