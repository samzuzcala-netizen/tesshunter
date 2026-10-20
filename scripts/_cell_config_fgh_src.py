# ── Mission & target ──────────────────────────────────────────────────────────
TARGET   = "EPIC 200164267"
MISSION  = "K2"
SECTOR   = None
CAMPAIGN = 12
QUARTER  = None
AUTHOR   = "K2SFF"

TARGET_LABEL = "TRAPPIST-1 / K2 C12 — f/g/h search"
TIC_ID   = None

# ── Search window — only f, g, h ──────────────────────────────────────────────
# Planets b (1.51 d), c (2.42 d), d (4.05 d), e (6.10 d) are pre-masked by
# the detection cell below before the BLS runs, so they don't interfere.
PERIOD_MIN = 8.0
PERIOD_MAX = 21.0

DURATION_MIN = 0.01
DURATION_MAX = 0.15   # g's transit duration is ~0.095 d

TOP_N     = 30        # enough candidates per pass to reach real planets past artifacts
N_PERIODS = 5000      # fine grid for K2's ~80-day baseline

# ── Preprocessing ─────────────────────────────────────────────────────────────
DO_FLATTEN     = True
FLATTEN_WINDOW = 0.5
SIGMA          = 4.0
BIN_MINUTES    = 10.0

# ── Detection thresholds — relaxed for sparse outer planets ───────────────────
# f has ~8 transits, g ~6, h ~4 in Campaign 12.  Completeness and composite
# scores are naturally lower than for the inner planets.
MAX_PLANETS            = 3     # we are only looking for f, g, h
SNR_MIN                = 1.5   # gate 1: minimum rank-1 BLS SNR to keep searching
SNR_MIN_RESOLVED       = 1.5   # gate 2: minimum resolved SNR to accept
MIN_EVENT_COMPLETENESS = 0.15  # gate 3: h has only ~4 transit windows
MIN_COMPOSITE_SCORE    = 0.5   # gate 4: SNR × ev_comp × (1 − overlap)

ARTIFACT_PERIODS = [1.0]       # 1-day K2 roll period

# ── Already-found planets — pre-masked before the f/g/h search ───────────────
# The detection cell uses planets_df from your previous run (accurate epochs)
# when it is available in the kernel namespace.  If the kernel was restarted,
# it falls back to these entries and resolves each epoch via a quick BLS.
#
# Optional: paste the exact epoch_btjd values from your previous planets_df
# here for faster / more accurate masking.  Leave as None to auto-resolve.
FOUND_PLANETS = [
    {"name": "b", "period_days": 1.5109, "epoch_btjd": None, "duration_days": 0.036},
    {"name": "c", "period_days": 2.4218, "epoch_btjd": None, "duration_days": 0.042},
    {"name": "d", "period_days": 4.0496, "epoch_btjd": None, "duration_days": 0.054},
    {"name": "e", "period_days": 6.0996, "epoch_btjd": None, "duration_days": 0.068},
]

# ── Known-period diagnostic ───────────────────────────────────────────────────
# After each accepted planet is masked the loop reports the SNR at each of
# these periods so you can track which of f/g/h remain in the residual.
KNOWN_PERIODS = {
    "TRAPPIST-1 f": 9.2067,
    "TRAPPIST-1 g": 12.3529,
    "TRAPPIST-1 h": 18.767,
}
