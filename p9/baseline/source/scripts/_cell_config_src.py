# ── Mission & target ──────────────────────────────────────────────────────────
# TESS example:    TARGET = 278892590          MISSION = "TESS"    SECTOR = None
# K2 example:      TARGET = "EPIC 200164267"   MISSION = "K2"      CAMPAIGN = 12
# Kepler example:  TARGET = "KIC 9414417"      MISSION = "Kepler"  QUARTER = 5
TARGET   = 278892590            # int TIC, "EPIC NNN", "KIC NNN", or a name
MISSION  = "TESS"               # "TESS", "K2", or "Kepler"
SECTOR   = None                 # TESS: specific sector(s), or None = all
CAMPAIGN = None                 # K2:   specific campaign(s), or None = all
QUARTER  = None                 # Kepler: specific quarter(s), or None = all
AUTHOR   = "SPOC"               # pipeline author: "SPOC", "K2SFF", "EVEREST", None

# Human-readable label used in plot titles and the report filename
TARGET_LABEL = "TIC 278892590"

# TIC ID for TESS catalog cross-match.
# Set to None when using K2/Kepler — cell 13 tries to resolve it automatically.
TIC_ID   = 278892590

# ── BLS search ────────────────────────────────────────────────────────────────
PERIOD_MIN = 1.0
PERIOD_MAX = 13.0   # 2+ transits in a typical 27-day TESS sector

DURATION_MIN = 0.01
DURATION_MAX = 0.12

# Number of BLS peaks returned per pass.
TOP_N = 20

# Broad BLS frequency-grid resolution.  None = auto (baseline × frequency_factor).
# 5000 gives finer period resolution and better separation of closely-spaced signals.
N_PERIODS = 5000

# ── Preprocessing ─────────────────────────────────────────────────────────────
DO_FLATTEN     = True
FLATTEN_WINDOW = 0.5
SIGMA          = 4.0
BIN_MINUTES    = 10.0

# ── Detection thresholds ──────────────────────────────────────────────────────
MAX_PLANETS            = 5
SNR_MIN                = 5.0   # gate 1: minimum raw BLS rank-1 SNR to keep searching
SNR_MIN_RESOLVED       = 5.0   # gate 2: minimum resolved SNR to accept a candidate
MIN_EVENT_COMPLETENESS = 0.5   # gate 3: fraction of transit windows with a real dip
MIN_COMPOSITE_SCORE    = 3.0   # gate 4: SNR × ev_comp × (1 − overlap)

# Periods (days) to suppress before peak extraction.
# Leave empty [] for TESS.  Add 1.0 for K2 (spacecraft roll systematic).
ARTIFACT_PERIODS = []

# ── Known-period diagnostic ───────────────────────────────────────────────────
# After each accepted planet is masked, the loop checks whether these periods
# remain visible in the residual.  Set to {} to disable (default for blind search).
KNOWN_PERIODS = {}
