"""Patch notebooks/02_single_target_search.ipynb for multi-mission support.

Updates cells 3 (config), 5 (download), 13 (crossmatch), and 20 (report)
so the notebook can use TESS, K2, or Kepler data.
"""

import json
import pathlib

NB_PATH = pathlib.Path(__file__).parent.parent / "notebooks" / "02_single_target_search.ipynb"

# ---------------------------------------------------------------------------
# New cell sources
# ---------------------------------------------------------------------------

CONFIG_SRC = """\
# ── Mission & target ──────────────────────────────────────────────────────────
# TESS example : TARGET = 278892590    MISSION = "TESS"   SECTOR = None
# K2 example   : TARGET = "EPIC 200164267"  MISSION = "K2"  CAMPAIGN = 12
# Kepler example: TARGET = "KIC 9414417"    MISSION = "Kepler"  QUARTER = 5
TARGET   = "EPIC 200164267"     # int TIC, "EPIC NNN", "KIC NNN", or a name
MISSION  = "K2"                 # "TESS", "K2", or "Kepler"
SECTOR   = None                 # TESS: specific sector(s), or None = all
CAMPAIGN = 12                   # K2:   specific campaign(s), or None = all
QUARTER  = None                 # Kepler: specific quarter(s), or None = all
AUTHOR   = "K2SFF"              # pipeline author: "K2SFF", "EVEREST", "SPOC", None

# Human-readable label used in plot titles and the report filename
TARGET_LABEL = "TRAPPIST-1 / K2 C12"

# TIC ID for TESS catalog cross-match.
# Set to None when using K2/Kepler — cell 13 will try to resolve it automatically.
TIC_ID   = None

# ── BLS search parameters ────────────────────────────────────────────────────
PERIOD_MIN = 1.0
PERIOD_MAX = 20.5

DURATION_MIN = 0.01
DURATION_MAX = 0.15

TOP_N = 20

DO_FLATTEN = True
FLATTEN_WINDOW = 0.5
SIGMA = 4.0
BIN_MINUTES = 10.0
"""

DOWNLOAD_SRC = """\
import warnings
warnings.filterwarnings("ignore", message=".*zero-centered.*")

lcc = download.search_and_download_lc(
    target   = TARGET,
    mission  = MISSION,
    sector   = SECTOR,
    campaign = CAMPAIGN,
    quarter  = QUARTER,
    author   = AUTHOR,
)
if lcc is None:
    raise RuntimeError(f"No data found for {TARGET!r} ({MISSION})")

lc_raw  = download.stitch_collection(lcc)
sectors = download.observing_units_available(lcc, MISSION)

_ulabels = {"TESS": "Sector", "K2": "Campaign", "KEPLER": "Quarter"}
_ulabel  = _ulabels.get(MISSION.upper(), "Unit")
print(f"Mission: {MISSION}  |  {_ulabel}(s): {sectors}  |  Cadences: {len(lc_raw)}")
"""

CROSSMATCH_SRC = """\
import re

# ── Resolve TIC ID for catalog cross-match ─────────────────────────────────
# For TESS:     set TIC_ID = <int> in the config cell above.
# For K2/Kepler: leave TIC_ID = None; this cell resolves it from the target name.
if TIC_ID is not None:
    _resolved_tic = TIC_ID
else:
    _m = re.match(r"TIC\\s*(\\d+)", str(TARGET), re.IGNORECASE)
    if _m:
        _resolved_tic = int(_m.group(1))
    else:
        print(f"Resolving TIC ID for {TARGET!r} via MAST (may take a few seconds)...")
        _resolved_tic = download.get_tic_id_from_name(str(TARGET))
        if _resolved_tic:
            print(f"  Resolved TIC ID: {_resolved_tic}")
        else:
            print("  Could not resolve TIC ID — cross-match will be skipped.")

# Update TIC_ID so downstream cells can reference it consistently
TIC_ID = _resolved_tic  # may be None if resolution failed

if TIC_ID is not None:
    xmatch = catalog_crossmatch.crossmatch(TIC_ID)
else:
    xmatch = {
        "tic_metadata":      None,
        "toi_entries":       None,
        "confirmed_planets": None,
        "is_known_toi":      False,
        "is_confirmed_planet": False,
        "summary_str": (
            f"No TIC ID could be resolved for {TARGET!r} — "
            "catalog cross-match skipped."
        ),
    }

print("Cross-match summary:")
print(xmatch["summary_str"])
print(f"Is known TOI       : {xmatch['is_known_toi']}")
print(f"Is confirmed planet: {xmatch['is_confirmed_planet']}")

tic_meta = xmatch.get("tic_metadata") or {}
stellar_radius = tic_meta.get("stellar_radius_rsun")
if stellar_radius:
    print(f"Stellar radius from TIC: {stellar_radius:.3f} R_Sun")
else:
    print("Stellar radius not available -- planet radius estimate will be skipped.")
"""

REPORT_SRC = """\
import pandas as pd

try:
    import tabulate as _tab
except ImportError:
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pip", "install", "tabulate", "-q"], check=True)

try:
    _planets = planets_df
except NameError:
    _planets = pd.DataFrame()

# ── Guard: nothing to report when no candidates were accepted ─────────────────
if best is None or vet is None:
    print("No accepted candidates — skipping report and CSV entry.")

else:
    # TIC_ID may be None (K2/Kepler without resolved TIC); fall back to 0
    _report_tic = TIC_ID or 0

    # Generate the markdown report.
    # candidates = raw first-pass BLS peaks (for the periodogram-peaks reference).
    # _planets   = alias-resolved multi-planet list (drives Section 2 table).
    report_path = reporting.generate_report(
        target_id          = TARGET_LABEL,
        tic_id             = _report_tic,
        sectors            = sectors,
        prep_record        = prep_record,
        candidates_df      = candidates,
        vetting            = vet,
        crossmatch_summary = xmatch["summary_str"],
        plot_paths         = plot_paths,
        planets_df         = _planets,
        mission            = MISSION,
    )
    print(f"Report written: {report_path}")

    # Append one CSV row per accepted planet.
    for _, p in _planets.iterrows():
        pnum = int(p.get("planet_num", 1))
        reporting.append_to_candidate_summary(
            tic_id             = _report_tic,
            target_id          = f"{TARGET_LABEL} P{pnum}",
            sectors            = sectors,
            period_days        = p["period_days"],
            depth_ppt          = p["depth_ppt"],
            duration_hours     = p["duration_days"] * 24,
            bls_power          = float(p.get("power", 0.0)),
            snr                = p["snr"],
            verdict            = vet.verdict if pnum == 1 else "candidate",
            crossmatch_summary = xmatch["summary_str"],
            summary_csv        = CANDIDATES_DIR / "candidate_summary.csv",
        )
"""

# ---------------------------------------------------------------------------
# Helper: convert a multiline string to the JSON source-list format
# ---------------------------------------------------------------------------

def to_source_lines(src: str) -> list[str]:
    """Split source string into per-line list, each ending with \\n except the last."""
    lines = src.split("\n")
    # Remove a trailing empty element from the final newline
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return [line + "\n" for line in lines[:-1]] + ([lines[-1]] if lines else [])


# ---------------------------------------------------------------------------
# Patch the notebook
# ---------------------------------------------------------------------------

with open(NB_PATH, encoding="utf-8") as f:
    nb = json.load(f)

cells = nb["cells"]
n = len(cells)
print(f"Notebook has {n} cells.")

PATCHES = {
    3:  CONFIG_SRC,
    5:  DOWNLOAD_SRC,
    13: CROSSMATCH_SRC,
    20: REPORT_SRC,
}

for idx, src in PATCHES.items():
    if idx >= n:
        print(f"  WARNING: cell {idx} does not exist (notebook has {n} cells) — skipping")
        continue
    cell = cells[idx]
    if cell["cell_type"] != "code":
        print(f"  WARNING: cell {idx} is type '{cell['cell_type']}', expected 'code' — skipping")
        continue
    cell["source"]  = to_source_lines(src)
    cell["outputs"] = []
    cell["execution_count"] = None
    print(f"  Patched cell {idx}")

with open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"\nWrote updated notebook to {NB_PATH}")
