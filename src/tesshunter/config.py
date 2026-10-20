"""Central configuration constants and defaults."""

from pathlib import Path

# Project root is three levels up from this file: src/tesshunter/config.py
PROJECT_ROOT = Path(__file__).parent.parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
PLOTS_DIR = OUTPUTS_DIR / "plots"
REPORTS_DIR = OUTPUTS_DIR / "reports"
CANDIDATES_DIR = OUTPUTS_DIR / "candidates"

CONFIGS_DIR = PROJECT_ROOT / "configs"

# Lightkurve cache location (override with env var LIGHTKURVE_CACHE)
import os
LIGHTKURVE_CACHE = Path(os.environ.get("LIGHTKURVE_CACHE", str(CACHE_DIR / "lightkurve")))

# BLS search defaults
BLS_PERIOD_MIN = 0.5        # days
BLS_PERIOD_MAX = 20.0       # days
BLS_DURATION_MIN = 0.02     # days (~30 min)
BLS_DURATION_MAX = 0.5      # days (~12 hours)
BLS_FREQUENCY_FACTOR = 10   # oversampling factor for frequency grid
BLS_TOP_N = 5               # how many period peaks to return

# Preprocessing defaults
SIGMA_CLIP_SIGMA = 4.0

# DEPRECATED (kept for backward compatibility only): FLATTEN_WINDOW_LENGTH was
# documented as a "fraction of baseline" but the shipped code multiplied it by
# a hardcoded 27-day constant. The detrending window is now expressed directly
# in DAYS (see FLATTEN_WINDOW_DAYS below); preprocessing.flatten() ignores this
# value and logs a deprecation warning if the old flatten_window kwarg is used.
FLATTEN_WINDOW_LENGTH = 0.75

# Savitzky-Golay detrending window in days (preprocessing.DEFAULT_WINDOW_DAYS).
# Converted to cadences via the actual median cadence, then clamped per segment
# to at most half the shortest contiguous segment.
FLATTEN_WINDOW_DAYS = 1.0

# BLS auto frequency-grid parameters (bls_search._build_period_grid):
# n from delta_f = duration_min / (A * baseline), floored and capped below.
BLS_OVERSAMPLE_A = 4          # oversampling factor A in the resolution criterion
BLS_MIN_FREQUENCIES = 500     # floor on auto grid size
BLS_MAX_FREQUENCIES = 20000   # cap on auto grid size (a warning is logged when hit)

# Advisory detection thresholds. SDE_MIN is documented guidance only: no code
# currently consumes it (bls_search emits an `sde` column; gating is left to
# the caller/pipeline). MIN_TRANSITS_DEFAULT is the recommended minimum number
# of observed transit epochs for acceptance (single-event candidates are
# flagged via the `single_event` column).
SDE_MIN = 7.0
MIN_TRANSITS_DEFAULT = 2

# NOTE: preprocessing.py and bls_search.py currently define these defaults
# locally (DEFAULT_WINDOW_DAYS, oversample=4, floor 500, cap 20000); config.py
# is the documented source of truth but is intentionally not imported by those
# modules to avoid circular imports.

# Vetting thresholds
MAX_DEPTH_PPT = 50.0        # transits deeper than this are probably EBs
MAX_DURATION_FRACTION = 0.1 # duration/period ratio; above this is suspect
ODD_EVEN_SIGMA_THRESHOLD = 2.5  # sigma difference to flag odd/even mismatch
