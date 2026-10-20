"""Create notebooks/03_batch_search.ipynb — two-stage batch pipeline.

Stage 1: fast triage (coarse grid, few sectors, no reports).
Stage 2: targeted period refinement + vetting on Stage 1 flagged targets.
         Does NOT re-run a broad search — refines only around the known period.
"""

import json
import pathlib

NB_PATH_CANONICAL = pathlib.Path(__file__).parent.parent / "notebooks" / "03_batch_search.ipynb"
NB_PATH_COPY      = pathlib.Path(__file__).parent.parent / "notebooks" / "03_batch_candidate_search.ipynb"


def to_source_lines(src: str) -> list[str]:
    lines = src.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return [line + "\n" for line in lines[:-1]] + ([lines[-1]] if lines else [])


def md(src: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": to_source_lines(src)}


def code(src: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": to_source_lines(src),
    }


# ---------------------------------------------------------------------------
# Cell 0 — header
# ---------------------------------------------------------------------------

HEADER_SRC = """\
# Notebook 03: Batch Candidate Search

**Purpose:** Run the exoplanet-candidate pipeline across a list of targets
using a two-stage strategy that keeps runtimes sane.

## Two-stage workflow

| | Stage 1 — fast triage | Stage 2 — targeted follow-up |
|---|---|---|
| **Sectors** | ≤ 4 per target | ≤ 8 per target (hard cap) |
| **Bin size** | 20 min | 20 min |
| **Period grid** | 500 pts, full 1–13 d | 1 000 pts, ±3 % window |
| **Search type** | Broad iterative discovery | Narrow refinement around Stage 1 period |
| **Output** | Promising-target list | Reports, plots, CSV |

**Stage 2 is NOT a second broad search.** It refines the period already found
in Stage 1, then runs vetting and generates reports.  This keeps Stage 2 fast
even for targets with 70+ TESS sectors.

**How to use:**
1. Fill in `TARGET_LIST` and run **Stage 1** (`STAGE = 1`).
2. Review the promising-target list printed at the end.
3. Change `STAGE = 2` in the config cell and re-run it and the batch cell.
   `FOLLOWUP_TARGETS` (with Stage 1 period info) is preserved automatically.

**Sector pinning:** Add `"sector": [2, 5, 8]` to a target dict to force
exactly those sectors in both stages.  Without it, Stage 1 caps at 4 and
Stage 2 caps at 8.\
"""

# ---------------------------------------------------------------------------
# Cell 1 — imports
# ---------------------------------------------------------------------------

IMPORTS_SRC = """\
import sys, logging
sys.path.insert(0, '../src')
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

import matplotlib
matplotlib.use('inline')
%matplotlib inline

import numpy as np

from tesshunter import download, preprocessing, bls_search, plotting, vetting, catalog_crossmatch, reporting
from tesshunter import centroid, contamination
from tesshunter.config import PLOTS_DIR, CANDIDATES_DIR\
"""

# ---------------------------------------------------------------------------
# Cell 2 — config
# ---------------------------------------------------------------------------

CONFIG_SRC = """\
# ── Stage selector ────────────────────────────────────────────────────────────
# STAGE = 1  →  broad triage across TARGET_LIST
# STAGE = 2  →  narrow refinement on FOLLOWUP_TARGETS (auto-populated by Stage 1)
#
# After Stage 1 finishes, re-run ONLY this config cell (change 1→2) and then
# re-run the batch cell.  FOLLOWUP_TARGETS is preserved in the kernel — do NOT
# restart the kernel between stages or you will lose the candidate periods.
# If you did restart, paste the target dicts (with "_stage1_planets") back into
# FOLLOWUP_TARGETS before running Stage 2.
STAGE = 1

# ── Stage 1: fast triage ──────────────────────────────────────────────────────
TRIAGE_CONFIG = {
    "period_min":             1.0,
    "period_max":             13.0,
    "duration_min":           0.02,
    "duration_max":           0.15,
    "n_periods":              500,    # coarse — fast but adequate for triage
    "top_n":                  10,
    "bin_minutes":            20,     # 20-min bins → 3× faster than 10-min
    "max_sectors":            4,      # NEVER auto-grab 71 sectors
    "max_planets":            3,
    "snr_min":                7.0,    # gate 1
    "snr_min_resolved":       7.0,    # gate 2
    "min_event_completeness": 0.5,    # gate 3
    "min_composite_score":    4.0,    # gate 4
    "triage_snr":             6.0,    # minimum best-planet SNR to flag for Stage 2
}

# ── Stage 2: targeted period refinement ──────────────────────────────────────
# Stage 2 does NOT re-run a broad 1-13 d search.
# It refines ± period_window_frac around the period Stage 1 already found.
FOLLOWUP_CONFIG = {
    "period_window_frac":     0.03,   # ±3 % around the Stage 1 period
    "duration_min":           0.02,
    "duration_max":           0.15,
    "n_periods":              1000,   # fine grid — precise period recovery
    "top_n":                  10,
    "bin_minutes":            20,     # keep 20-min bins — still fast
    "max_sectors":            8,      # hard cap — never 71 sectors
    "max_cadences":           80000,  # bail if stitched LC is still too large
    "snr_min_resolved":       5.0,    # minimum SNR to keep a refined candidate
    "min_event_completeness": 0.4,    # relaxed — more sectors = more coverage
}

# ── Preprocessing (shared between stages) ─────────────────────────────────────
DO_FLATTEN     = True
FLATTEN_WINDOW = 0.5
SIGMA          = 4.0

# ── Artifact / known-period globals (override per target if needed) ────────────
ARTIFACT_PERIODS = []   # add 1.0 for K2 targets (spacecraft roll)
KNOWN_PERIODS    = {}   # {} = disabled; set per target or globally for diagnostics

# ── Stage 2 follow-up target list ─────────────────────────────────────────────
# Auto-populated by Stage 1 (with Stage 1 candidate periods embedded).
# Re-running this config cell does NOT reset the list — that only happens when
# Stage 1 itself runs.  To clear manually, run:  FOLLOWUP_TARGETS = []
#
# To bypass Stage 1 and run Stage 2 directly, add '_stage1_planets' yourself:
# FOLLOWUP_TARGETS = [
#     {"target": 261136679, "mission": "TESS", "author": "SPOC",
#      "label": "Pi Mensae / TOI-144",
#      "_stage1_planets": [{"period_days": 6.27, "epoch_btjd": 1328.0,
#                           "duration_days": 0.09, "depth_ppt": 5.2,
#                           "snr": 18.3, "planet_num": 1}]},
# ]
if "FOLLOWUP_TARGETS" not in vars():
    FOLLOWUP_TARGETS = []

# ── Target list (Stage 1) ─────────────────────────────────────────────────────
# Required keys: target, mission, label
# Optional keys: sector, campaign, quarter, author, tic_id
#                artifact_periods, known_periods            ← per-target overrides
#                stellar_rotation_period_days               ← enables rotation-harmonic vetting
#
# Tip — pin specific sectors to avoid auto-downloading dozens:
#   "sector": [2, 5, 8, 9]
# Without "sector", Stage 1 caps at max_sectors=4 and Stage 2 caps at 8.
#
# Tip — add stellar rotation period for active/young stars:
#   "stellar_rotation_period_days": 4.86   # AU Mic rotates every 4.86 d
TARGET_LIST = [
    {"target": 278892590, "mission": "TESS", "author": "SPOC",
     "label": "TIC 278892590"},
    {"target": 441420236, "mission": "TESS", "author": "SPOC",
     "label": "TIC 441420236"},
    {"target": 261136679, "mission": "TESS", "author": "SPOC",
     "label": "TIC 261136679"},
    # Pinned sectors example:
    # {"target": 261136679, "mission": "TESS", "author": "SPOC",
    #  "sector": [2, 5, 8, 9], "label": "Pi Mensae / TOI-144"},
    # K2 example (always add artifact_periods for K2):
    # {"target": "EPIC 211945201", "mission": "K2", "campaign": 5,
    #  "author": "K2SFF", "label": "55 Cnc / K2 C5",
    #  "artifact_periods": [1.0]},
]\
"""

# ---------------------------------------------------------------------------
# Cell 3 — batch runner
# ---------------------------------------------------------------------------

BATCH_SRC = """\
import re, traceback, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", message=".*zero-centered.*")

# ── Sanity check — catch a skipped imports cell early ─────────────────────────
if "download" not in vars():
    raise RuntimeError(
        "tesshunter modules not loaded — run the imports cell (In[1]) first, "
        "then re-run this cell."
    )

# ── Stage setup ───────────────────────────────────────────────────────────────
_cfg = TRIAGE_CONFIG if STAGE == 1 else FOLLOWUP_CONFIG

if STAGE == 1:
    _targets_to_run  = TARGET_LIST
    FOLLOWUP_TARGETS = []    # reset any previous Stage 1 results
    print(f"STAGE 1  —  fast triage  ({len(_targets_to_run)} target(s))")
else:
    _targets_to_run = FOLLOWUP_TARGETS if FOLLOWUP_TARGETS else TARGET_LIST
    if not FOLLOWUP_TARGETS:
        print("WARNING: FOLLOWUP_TARGETS is empty — running on TARGET_LIST instead.")
        print("  Run Stage 1 first without restarting the kernel.")
        print("  Or populate FOLLOWUP_TARGETS manually with '_stage1_planets' keys.")
    print(f"STAGE 2  —  targeted follow-up  ({len(_targets_to_run)} target(s))")

print(f"  sectors cap  : {_cfg['max_sectors']}  "
      f"bin_minutes : {_cfg['bin_minutes']}  "
      f"n_periods : {_cfg['n_periods']}  "
      f"top_n : {_cfg['top_n']}")
if STAGE == 2:
    print(f"  period window: ±{_cfg.get('period_window_frac', 0.03)*100:.0f}%  "
          f"max_cadences : {_cfg.get('max_cadences', 'unlimited')}")

# ── Unpack config into readable names ─────────────────────────────────────────
_DURATION_MIN           = _cfg["duration_min"]
_DURATION_MAX           = _cfg["duration_max"]
_N_PERIODS              = _cfg["n_periods"]
_TOP_N                  = _cfg["top_n"]
_BIN_MINUTES            = _cfg["bin_minutes"]
_MAX_SECTORS            = _cfg["max_sectors"]
_SNR_MIN_RESOLVED       = _cfg.get("snr_min_resolved",       5.0)
_MIN_EVENT_COMPLETENESS = _cfg.get("min_event_completeness", 0.4)
_MAX_CADENCES           = _cfg.get("max_cadences")          # Stage 2 only
_PERIOD_WINDOW_FRAC     = _cfg.get("period_window_frac",    0.03)  # Stage 2 only

# Stage 1 only
_PERIOD_MIN          = _cfg.get("period_min",          1.0)
_PERIOD_MAX          = _cfg.get("period_max",          13.0)
_MAX_PLANETS         = _cfg.get("max_planets",         3)
_SNR_MIN             = _cfg.get("snr_min",             7.0)
_MIN_COMPOSITE_SCORE = _cfg.get("min_composite_score", 4.0)
_TRIAGE_SNR          = _cfg.get("triage_snr")

_disp = ["harmonic_label", "trial_period", "period_days",
         "depth_ppt", "snr", "event_completeness",
         "alternating_flag", "overlap", "composite_score"]

_batch_summary = []
_failed        = []
_n_total       = len(_targets_to_run)

for _tidx, _tcfg in enumerate(_targets_to_run):

    # ── Unpack target config ──────────────────────────────────────────────────
    _TARGET      = _tcfg["target"]
    _MISSION     = _tcfg.get("mission",  "TESS")
    _SECTOR      = _tcfg.get("sector",   None)
    _CAMPAIGN    = _tcfg.get("campaign", None)
    _QUARTER     = _tcfg.get("quarter",  None)
    _AUTHOR      = _tcfg.get("author",   None)
    _LABEL       = _tcfg.get("label",    str(_TARGET))
    _TIC_ID      = _tcfg.get("tic_id",   None)
    _art_periods = _tcfg.get("artifact_periods", ARTIFACT_PERIODS)
    _known_p     = _tcfg.get("known_periods",    KNOWN_PERIODS)
    # Normalize: if a bare list was given, convert to {"P1": val, "P2": val, ...}
    if isinstance(_known_p, list):
        _known_p = {f"P{_i+1}": _kp for _i, _kp in enumerate(_known_p)}

    print(f"\\n{'#'*66}")
    print(f"  {_tidx + 1}/{_n_total}  {_LABEL}  [Stage {STAGE}]")
    print(f"{'#'*66}")

    try:

        # ── Download ──────────────────────────────────────────────────────────
        _lcc = download.search_and_download_lc(
            target   = _TARGET,
            mission  = _MISSION,
            sector   = _SECTOR,
            campaign = _CAMPAIGN,
            quarter  = _QUARTER,
            author   = _AUTHOR,
        )
        if _lcc is None:
            print(f"  [SKIP] No data found.")
            _failed.append({"label": _LABEL, "reason": "no data"})
            _batch_summary.append({"label": _LABEL, "mission": _MISSION,
                                   "n_planets": 0, "verdict": "no_data",
                                   "status": "no_data"})
            continue

        # Sector cap
        if _SECTOR is None and _MAX_SECTORS is not None and len(_lcc) > _MAX_SECTORS:
            _lcc = _lcc[:_MAX_SECTORS]
            print(f"  Trimmed to {_MAX_SECTORS} sector(s) "
                  f"(set 'sector': [...] in target dict to pin specific ones)")

        _lc_raw  = download.stitch_collection(_lcc)
        _sectors = download.observing_units_available(_lcc, _MISSION)
        _ulabel  = {"TESS": "Sector", "K2": "Campaign", "KEPLER": "Quarter"}.get(
                       _MISSION.upper(), "Unit")
        print(f"  {_ulabel}(s) used: {_sectors}")

        # Time-span diagnostic — catches mixed time-system stitching errors
        _t = _lc_raw.time.value
        _t_min, _t_max = float(np.nanmin(_t)), float(np.nanmax(_t))
        _t_span = _t_max - _t_min
        if _t_max > 2_400_000:
            print(f"  *** TIME ERROR: values look like full BJD (max={_t_max:.1f}),"
                  f" not BTJD — mixed time systems in stitch ***")
        elif _t_span > 10_000:
            print(f"  *** TIME WARNING: span={_t_span:.1f} d is implausibly large."
                  f"  Mixed time systems? (BTJD {_t_min:.1f} – {_t_max:.1f}) ***")
        print(f"  Time span : {_t_min:.2f} – {_t_max:.2f} BTJD"
              f"  ({_t_span:.1f} d)  |  Raw cadences: {len(_t)}")

        # Resolve TIC ID
        if _TIC_ID is not None:
            _resolved_tic = _TIC_ID
        else:
            _m = re.match(r"TIC\\s*(\\d+)", str(_TARGET), re.IGNORECASE)
            if _m:
                _resolved_tic = int(_m.group(1))
            elif isinstance(_TARGET, int):
                _resolved_tic = _TARGET
            else:
                _resolved_tic = download.get_tic_id_from_name(str(_TARGET))

        # Preprocess
        _lc_clean, _prep = preprocessing.preprocess(
            _lc_raw, sigma=SIGMA, do_flatten=DO_FLATTEN,
            flatten_window=FLATTEN_WINDOW,
        )
        _n_clean = len(_lc_clean)
        print(f"  Preprocessed: {_n_clean} cadences  "
              f"(will bin to {_BIN_MINUTES}-min bins)")

        # Cadence guard (Stage 2 only — Stage 1 is already capped at 4 sectors)
        if STAGE == 2 and _MAX_CADENCES is not None and _n_clean > _MAX_CADENCES:
            _msg = (f"cadence limit exceeded: {_n_clean} > {_MAX_CADENCES}. "
                    f"Reduce max_sectors in FOLLOWUP_CONFIG or add "
                    f"'sector': [...] to this target dict.")
            print(f"\\n  [SKIP] {_msg}")
            _failed.append({"label": _LABEL, "reason": _msg})
            _batch_summary.append({"label": _LABEL, "mission": _MISSION,
                                   "n_planets": 0, "verdict": "cadence_limit",
                                   "status": _msg[:120]})
            continue

        # =====================================================================
        # STAGE 1 — broad iterative discovery
        # =====================================================================
        if STAGE == 1:
            _found       = []
            _work_lc     = _lc_clean

            for _pass in range(_MAX_PLANETS):
                _pnum = _pass + 1
                print(f"\\n  {'='*58}")
                print(f"    Detection pass {_pnum}")
                print(f"  {'='*58}")

                _binned = preprocessing.bin_lightcurve(_work_lc, bin_minutes=_BIN_MINUTES)

                _, _bls_r, _raw = bls_search.run_bls(
                    _binned,
                    period_min       = _PERIOD_MIN,
                    period_max       = _PERIOD_MAX,
                    duration_min     = _DURATION_MIN,
                    duration_max     = _DURATION_MAX,
                    top_n            = _TOP_N,
                    suppress_periods = _art_periods,
                    n_periods        = _N_PERIODS,
                )

                if _raw.empty:
                    print("    No BLS candidates returned — stopping.")
                    break

                _top = _raw.iloc[0]
                print(f"    BLS top:  {_top['period_days']:.4f} d  "
                      f"depth {_top['depth_ppt']:.3f} ppt  SNR {_top['snr']:.1f}  "
                      f"({len(_raw)} candidates)")

                if _top["snr"] < _SNR_MIN:
                    print(f"    STOP (gate 1): SNR {_top['snr']:.1f} < {_SNR_MIN}")
                    break

                _existing = pd.DataFrame(_found) if _found else None
                _pool     = []

                print(f"\\n    Resolving {len(_raw)} candidate(s)...")
                for _, _rc in _raw.iterrows():
                    _p = _rc["period_days"]
                    if any(abs(_p / _b - 1.0) < 0.02 for _b in _art_periods):
                        print(f"    [{_p:.4f} d]  artifact — skip")
                        continue

                    _res, _ttbl = bls_search.resolve_aliases_for_candidate(
                        _binned, _rc,
                        existing_candidates = _existing,
                        period_min   = _PERIOD_MIN,
                        period_max   = _PERIOD_MAX,
                        duration_min = _DURATION_MIN,
                        duration_max = _DURATION_MAX,
                    )
                    _ev = _res.get("event_completeness", float("nan"))
                    _cs = _res.get("composite_score",    _res["snr"])
                    _rp = _res["period_days"]

                    if any(abs(_rp / _b - 1.0) < 0.02 for _b in _art_periods):
                        print(f"    [{_p:.4f}d→{_rp:.4f}d]  resolved to artifact — skip")
                        continue
                    if _res["snr"] < _SNR_MIN_RESOLVED:
                        print(f"    [{_p:.4f}d→{_rp:.4f}d]  "
                              f"SNR {_res['snr']:.1f} < {_SNR_MIN_RESOLVED}  (gate 2)")
                        continue
                    if not (_ev >= _MIN_EVENT_COMPLETENESS):
                        print(f"    [{_p:.4f}d→{_rp:.4f}d]  "
                              f"ev_comp {_ev:.2f} < {_MIN_EVENT_COMPLETENESS}  (gate 3)")
                        continue
                    if _cs < _MIN_COMPOSITE_SCORE:
                        print(f"    [{_p:.4f}d→{_rp:.4f}d]  "
                              f"composite {_cs:.2f} < {_MIN_COMPOSITE_SCORE}  (gate 4)")
                        continue
                    # Gate 5: reject if period duplicates an already-accepted planet.
                    # This catches signal leakage where BLS re-detects the same deep
                    # transit at a marginally different period in a later pass.
                    if any(abs(_res["period_days"] / _pf["period_days"] - 1.0) < 0.01
                           for _pf in _found):
                        print(f"    [{_p:.4f}d→{_rp:.4f}d]  "
                              f"within 1% of already-found period — likely leakage (gate 5)")
                        continue

                    print(f"    [{_p:.4f}d→{_rp:.4f}d]  "
                          f"SNR {_res['snr']:.1f}  ev_comp {_ev:.2f}  "
                          f"composite {_cs:.2f}  PASS")
                    _pool.append((_res, _ttbl))

                if not _pool:
                    print("\\n    No candidate survived quality gates — stopping.")
                    break

                _res, _ = max(_pool,
                              key=lambda rt: rt[0].get("composite_score", rt[0]["snr"]))
                _ev = _res.get("event_completeness", float("nan"))
                _cs = _res.get("composite_score", _res["snr"])

                print(f"\\n    Accepted planet {_pnum}: [{_res['harmonic_label']}]  "
                      f"P = {_res['period_days']:.6f} d  "
                      f"depth {_res['depth_ppt']:.3f} ppt  "
                      f"SNR {_res['snr']:.1f}  ev_comp {_ev:.2f}  composite {_cs:.2f}")

                _found.append({
                    "planet_num":         _pnum,
                    "period_days":        _res["period_days"],
                    "epoch_btjd":         _res["epoch_btjd"],
                    "duration_days":      _res["duration_days"],
                    "depth_ppt":          _res["depth_ppt"],
                    "power":              _res.get("power", 0.0),
                    "snr":                _res["snr"],
                    "event_completeness": _ev,
                    "harmonic_label":     _res.get("harmonic_label", "P"),
                })

                _work_lc = preprocessing.mask_transits(
                    _work_lc,
                    period       = _res["period_days"],
                    epoch        = _res["epoch_btjd"],
                    duration     = _res["duration_days"],
                    width_factor = 7.0,
                )

                # Guard: masking wiped (nearly) all data — stop iteration.
                # This prevents bin_lightcurve from receiving an empty array and
                # crashing with "zero-size array" ValueError.
                if len(_work_lc) < 50:
                    print(f"    WARNING: only {len(_work_lc)} cadences remain after "
                          f"masking — stopping pass.")
                    break

                # Post-mask check: narrow BLS window around the accepted period.
                # If residual SNR > 20 the transit was not fully removed — this
                # usually means the BLS-fit ephemeris is imprecise relative to the
                # observation baseline (epoch drift) or the transit wings dominate
                # (very deep / EB-like signal).  Stop here rather than letting the
                # next pass pick up the same signal at a marginally different period.
                _chk_bin = preprocessing.bin_lightcurve(_work_lc, bin_minutes=_BIN_MINUTES)
                if len(_chk_bin) < 10:
                    print(f"    Post-mask check skipped (too few binned points).")
                else:
                    _, _, _chk = bls_search.run_bls(
                        _chk_bin,
                        period_min   = _res["period_days"] * 0.98,
                        period_max   = _res["period_days"] * 1.02,
                        duration_min = _DURATION_MIN,
                        duration_max = _DURATION_MAX,
                        top_n        = 3,
                    )
                    if _chk.empty:
                        print(f"    Post-mask check: signal gone.  OK")
                    else:
                        _psnr = _chk.iloc[0]["snr"]
                        if _psnr > 20:
                            print(f"    Post-mask check: residual SNR = {_psnr:.1f}"
                                  f" — masking insufficient (deep transit / possible EB)."
                                  f"  Stopping pass; next pass would just re-detect same signal.")
                            break
                        elif _psnr > 5:
                            print(f"    Post-mask check: residual SNR = {_psnr:.1f}"
                                  f"  WARNING: still elevated")
                        else:
                            print(f"    Post-mask check: residual SNR = {_psnr:.1f}  OK")

            # Stage 1 detection summary
            _planets_df = pd.DataFrame(_found)
            _best       = _planets_df.iloc[0] if not _planets_df.empty else None
            print(f"\\n  Detection: {len(_found)} candidate(s) accepted.")
            if not _planets_df.empty:
                _sc = [c for c in ["planet_num", "period_days", "depth_ppt",
                                    "snr", "event_completeness", "harmonic_label"]
                       if c in _planets_df.columns]
                print(_planets_df[_sc].to_string(index=False))

            # Triage decision
            _is_promising = (
                _best is not None
                and _TRIAGE_SNR is not None
                and float(_best["snr"]) >= _TRIAGE_SNR
            )
            if _is_promising:
                print(f"\\n  [PROMISING]    SNR {_best['snr']:.1f} >= {_TRIAGE_SNR}"
                      f"  P = {_best['period_days']:.4f} d"
                      f"  →  added to FOLLOWUP_TARGETS")
                # Embed the candidate periods so Stage 2 knows what to refine
                _followup_entry = dict(_tcfg)
                _followup_entry["_stage1_planets"] = _found
                FOLLOWUP_TARGETS.append(_followup_entry)
            elif _best is not None:
                print(f"\\n  [BELOW TRIAGE] SNR {_best['snr']:.1f} < {_TRIAGE_SNR}"
                      f"  —  not flagging for Stage 2")
            else:
                print(f"\\n  [NO SIGNAL]    nothing accepted by detection gates")

            _batch_summary.append({
                "label":          _LABEL,
                "mission":        _MISSION,
                "sectors":        str(_sectors),
                "n_planets":      len(_found),
                "best_period_d":  round(_best["period_days"], 5) if _best is not None else None,
                "best_snr":       round(float(_best["snr"]),  2)  if _best is not None else None,
                "best_depth_ppt": round(float(_best["depth_ppt"]), 3) if _best is not None else None,
                "promising":      _is_promising,
                "status":         "ok",
            })
            continue   # ← skip Stage 2 block

        # =====================================================================
        # STAGE 2 — targeted period refinement + vetting
        # =====================================================================

        # Stage 2 refines the periods Stage 1 already found.
        # It does NOT re-run a broad 1–13 d search.
        _stage1_planets = _tcfg.get("_stage1_planets", [])
        if not _stage1_planets:
            _msg = ("No Stage 1 candidate info in target dict.  "
                    "Run Stage 1 without restarting the kernel so that "
                    "FOLLOWUP_TARGETS carries the candidate periods.")
            print(f"\\n  [SKIP] {_msg}")
            _failed.append({"label": _LABEL, "reason": _msg})
            _batch_summary.append({"label": _LABEL, "mission": _MISSION,
                                   "n_planets": 0, "verdict": "no_stage1_info",
                                   "status": _msg[:120]})
            continue

        _binned = preprocessing.bin_lightcurve(_lc_clean, bin_minutes=_BIN_MINUTES)

        # Refine each Stage 1 candidate in a narrow period window
        _refined     = []
        _bls_result  = None
        _first_cands = None

        for _sp in _stage1_planets:
            _p0   = float(_sp["period_days"])
            _pmin = _p0 * (1.0 - _PERIOD_WINDOW_FRAC)
            _pmax = _p0 * (1.0 + _PERIOD_WINDOW_FRAC)
            print(f"\\n  Refining: P = {_p0:.5f} d  "
                  f"window [{_pmin:.5f}, {_pmax:.5f}]  "
                  f"(+/-{_PERIOD_WINDOW_FRAC*100:.0f}%)")

            _, _bls_r, _raw = bls_search.run_bls(
                _binned,
                period_min   = _pmin,
                period_max   = _pmax,
                duration_min = _DURATION_MIN,
                duration_max = _DURATION_MAX,
                top_n        = _TOP_N,
                n_periods    = _N_PERIODS,
            )
            if _bls_result is None:
                _bls_result  = _bls_r
                _first_cands = _raw

            if _raw.empty:
                print(f"    No BLS signal in refinement window — candidate dropped.")
                continue

            _top = _raw.iloc[0]
            print(f"    BLS peak : P = {_top['period_days']:.6f} d  "
                  f"depth {_top['depth_ppt']:.3f} ppt  SNR {_top['snr']:.1f}")

            # Alias resolution within the narrow window
            _res, _ = bls_search.resolve_aliases_for_candidate(
                _binned, _top,
                period_min   = _pmin,
                period_max   = _pmax,
                duration_min = _DURATION_MIN,
                duration_max = _DURATION_MAX,
            )
            _ev = _res.get("event_completeness", float("nan"))
            _cs = _res.get("composite_score", _res["snr"])

            print(f"    Refined  : P = {_res['period_days']:.6f} d  "
                  f"depth {_res['depth_ppt']:.3f} ppt  SNR {_res['snr']:.1f}  "
                  f"ev_comp {_ev:.2f}")

            if _res["snr"] < _SNR_MIN_RESOLVED:
                print(f"    Below SNR threshold {_SNR_MIN_RESOLVED} — not keeping.")
                continue

            _refined.append({
                "planet_num":         _sp.get("planet_num", len(_refined) + 1),
                "stage1_period_d":    _p0,
                "period_days":        _res["period_days"],
                "epoch_btjd":         _res["epoch_btjd"],
                "duration_days":      _res["duration_days"],
                "depth_ppt":          _res["depth_ppt"],
                "power":              _res.get("power", 0.0),
                "snr":                _res["snr"],
                "event_completeness": _ev,
                "harmonic_label":     _res.get("harmonic_label", "P"),
            })

        _planets_df = pd.DataFrame(_refined)
        _best       = _planets_df.iloc[0] if not _planets_df.empty else None
        print(f"\\n  Stage 2 refinement: {len(_refined)} candidate(s) retained.")
        if not _planets_df.empty:
            _sc = [c for c in ["planet_num", "stage1_period_d", "period_days",
                                "depth_ppt", "snr", "event_completeness"]
                   if c in _planets_df.columns]
            print(_planets_df[_sc].to_string(index=False))

        # Known-period diagnostic
        if _known_p:
            print(f"\\n  Known-period diagnostic:")
            for _kname, _kp in _known_p.items():
                _, _, _kl = bls_search.run_bls(
                    _binned,
                    period_min   = _kp * 0.98,
                    period_max   = _kp * 1.02,
                    duration_min = _DURATION_MIN,
                    duration_max = _DURATION_MAX,
                    top_n        = 3,
                )
                if _kl.empty:
                    print(f"    {_kname} ({_kp:.4f} d): no signal")
                else:
                    _kb = _kl.iloc[0]
                    print(f"    {_kname} ({_kp:.4f} d): "
                          f"P={_kb['period_days']:.4f} d  SNR={_kb['snr']:.1f}")

        # Cross-match
        if _resolved_tic is not None:
            _xmatch = catalog_crossmatch.crossmatch(_resolved_tic)
        else:
            _xmatch = {
                "tic_metadata": None, "toi_entries": None,
                "confirmed_planets": None, "is_known_toi": False,
                "is_confirmed_planet": False,
                "summary_str": f"No TIC ID for {_LABEL!r} — cross-match skipped.",
            }
        _tic_meta   = _xmatch.get("tic_metadata") or {}
        _stellar_r  = _tic_meta.get("stellar_radius_rsun")
        # Rotation period: per-target dict wins; fall back to TIC catalog value
        _rot_period = (_tcfg.get("stellar_rotation_period_days")
                       or _tic_meta.get("stellar_rotation_period_days"))
        _catalog_ok = not _xmatch.get("any_query_failed", False)
        print(f"\\n  Cross-match: {_xmatch['summary_str'][:120]}")
        print(f"  Known TOI: {_xmatch['is_known_toi']}"
              f"  Confirmed: {_xmatch['is_confirmed_planet']}"
              f"  Catalog OK: {_catalog_ok}"
              + (f"  Rot period: {_rot_period:.2f} d" if _rot_period else ""))

        # Vetting
        if _best is not None:
            _vet = vetting.run_vetting(
                _lc_clean,
                period_days                  = _best["period_days"],
                epoch_btjd                   = _best["epoch_btjd"],
                duration_days                = _best["duration_days"],
                depth_ppt                    = _best["depth_ppt"],
                snr                          = float(_best["snr"]),
                n_sectors                    = len(_sectors),
                stellar_radius_rsun          = _stellar_r,
                stellar_rotation_period_days = _rot_period,
                is_known_toi                 = _xmatch["is_known_toi"],
                catalog_ok                   = _catalog_ok,
            )
            print(f"\\n  Vetting verdict: {_vet.verdict}")
            if _vet.hard_veto_flags:
                print(f"  HARD VETOES ({len(_vet.hard_veto_flags)}):")
                for _f in _vet.hard_veto_flags:
                    print(f"    ✗ {_f}")
            if _vet.high_risk_flags:
                print(f"  High-risk flags ({len(_vet.high_risk_flags)}):")
                for _f in _vet.high_risk_flags:
                    print(f"    ! {_f}")
            if _vet.medium_flags:
                print(f"  Medium flags ({len(_vet.medium_flags)}):")
                for _f in _vet.medium_flags:
                    print(f"    ~ {_f}")
            print()
            for _vn in _vet.notes:
                print(f"    {_vn}")
        else:
            _vet = None
            print("  No refined candidates — vetting skipped.")

        # ── Centroid analysis ─────────────────────────────────────────────────
        if _best is not None and _vet is not None:
            print("\\n  Centroid analysis (TPF):")
            try:
                _cent = centroid.run_centroid_check(
                    _TARGET, _MISSION, _sectors,
                    _best["period_days"], _best["epoch_btjd"], _best["duration_days"],
                )
                print(f"    {_cent.note}")
                if _cent.available and _cent.flagged:
                    _vet.high_risk_flags.append(
                        f"centroid shift {_cent.shift_arcsec:.1f} arcsec "
                        f"({_cent.sigma:.1f}σ) during transit"
                    )
                    _vet.centroid_shift = _cent.shift_arcsec
                    _vet.verdict = vetting.recompute_verdict(_vet, _xmatch["is_known_toi"])
                    print(f"    → Verdict updated: {_vet.verdict}")
            except Exception as _ce:
                print(f"    Centroid check error: {_ce}")

        # ── Contamination check ───────────────────────────────────────────────
        if _best is not None and _vet is not None:
            _ra  = _tic_meta.get("ra")
            _dec = _tic_meta.get("dec")
            _tmag = _tic_meta.get("tmag")
            if _ra is not None and _dec is not None and _tmag is not None:
                print("\\n  Nearby-star contamination check:")
                try:
                    _contam = contamination.run_contamination_check(
                        _ra, _dec, _tmag, float(_best["depth_ppt"]),
                    )
                    for _line in _contam.note.splitlines():
                        print(f"    {_line}")
                    if _contam.available and _contam.flagged:
                        if _contam.high_risk_neighbours:
                            _n_hr = len(_contam.high_risk_neighbours)
                            _worst_hr = max(
                                s.leakage_corrected_depth_ppt
                                for s in _contam.high_risk_neighbours
                            )
                            _vet.high_risk_flags.append(
                                f"{_n_hr} HIGH-risk nearby star(s) within aperture "
                                f"can mimic signal (corrected depth up to {_worst_hr:.0f} ppt)"
                            )
                        if _contam.medium_risk_neighbours:
                            _n_mr = len(_contam.medium_risk_neighbours)
                            _worst_mr = max(
                                s.leakage_corrected_depth_ppt
                                for s in _contam.medium_risk_neighbours
                            )
                            _vet.medium_flags.append(
                                f"{_n_mr} MEDIUM-risk nearby star(s) in PRF wings "
                                f"(corrected depth up to {_worst_mr:.0f} ppt)"
                            )
                        _vet.verdict = vetting.recompute_verdict(_vet, _xmatch["is_known_toi"])
                        print(f"    → Verdict updated: {_vet.verdict}")
                except Exception as _contame:
                    print(f"    Contamination check error: {_contame}")
            else:
                print("\\n  Contamination check skipped (no RA/Dec/Tmag in TIC metadata).")

        # Diagnostic plots
        _plot_paths = {}
        if _bls_result is not None:
            _plot_paths = plotting.all_diagnostic_plots(
                _lc_raw, _lc_clean, _bls_result, _first_cands, _LABEL,
            )
        if _best is not None:
            _plot_paths["folded"] = plotting.plot_folded_lightcurve(
                _lc_clean,
                _best["period_days"], _best["epoch_btjd"], _best["duration_days"],
                _LABEL,
            )
            _plot_paths["zoom"] = plotting.plot_transit_zoom(
                _lc_clean,
                _best["epoch_btjd"], _best["duration_days"], _best["period_days"],
                _LABEL,
            )
        print(f"  Plots saved: {list(_plot_paths.keys())}")

        # Report + CSV
        _report_tic = _resolved_tic or 0
        if _best is not None and _vet is not None:
            _report_path = reporting.generate_report(
                target_id          = _LABEL,
                tic_id             = _report_tic,
                sectors            = _sectors,
                prep_record        = _prep,
                candidates_df      = _first_cands if _first_cands is not None
                                     else pd.DataFrame(),
                vetting            = _vet,
                crossmatch_summary = _xmatch["summary_str"],
                plot_paths         = _plot_paths,
                planets_df         = _planets_df,
                mission            = _MISSION,
            )
            print(f"  Report: {_report_path}")
            for _, _pr in _planets_df.iterrows():
                _prnum = int(_pr.get("planet_num", 1))
                reporting.append_to_candidate_summary(
                    tic_id             = _report_tic,
                    target_id          = f"{_LABEL} P{_prnum}",
                    sectors            = _sectors,
                    period_days        = _pr["period_days"],
                    depth_ppt          = _pr["depth_ppt"],
                    duration_hours     = _pr["duration_days"] * 24,
                    bls_power          = float(_pr.get("power", 0.0)),
                    snr                = _pr["snr"],
                    verdict            = _vet.verdict if _prnum == 1 else "candidate",
                    crossmatch_summary = _xmatch["summary_str"],
                    summary_csv        = CANDIDATES_DIR / "candidate_summary.csv",
                )
        else:
            print("  No accepted candidates — report and CSV entry skipped.")

        _batch_summary.append({
            "label":          _LABEL,
            "tic_id":         _report_tic,
            "mission":        _MISSION,
            "sectors":        str(_sectors),
            "n_planets":      len(_refined),
            "best_period_d":  round(_best["period_days"], 5) if _best is not None else None,
            "best_snr":       round(float(_best["snr"]),  2)  if _best is not None else None,
            "best_depth_ppt": round(float(_best["depth_ppt"]), 3) if _best is not None else None,
            "is_known_toi":   _xmatch.get("is_known_toi",       False),
            "is_confirmed":   _xmatch.get("is_confirmed_planet", False),
            "verdict":        _vet.verdict if _vet else "no_candidate",
            "status":         "ok",
        })

    except Exception as _exc:
        print(f"\\n  [ERROR] {_LABEL}: {_exc}")
        traceback.print_exc()
        _failed.append({"label": _LABEL, "reason": str(_exc)})
        _batch_summary.append({
            "label": _LABEL, "mission": _MISSION,
            "n_planets": 0, "verdict": "error",
            "status": str(_exc)[:120],
        })

# ── Run complete ───────────────────────────────────────────────────────────────
_ok  = sum(1 for r in _batch_summary if r.get("status") == "ok")
_nd  = sum(1 for r in _batch_summary if r.get("status") == "no_data")
_err = _n_total - _ok - _nd

print(f"\\n{'='*66}")
print(f"  Stage {STAGE} complete.  {_n_total} target(s) processed.")
print(f"  OK: {_ok}  |  No data: {_nd}  |  Errors: {_err}")

if STAGE == 1:
    _np = len(FOLLOWUP_TARGETS)
    if _np:
        print(f"\\n  {_np} promising target(s) flagged for Stage 2:")
        for _ft in FOLLOWUP_TARGETS:
            _ns = len(_ft.get("_stage1_planets", []))
            print(f"    {_ft.get('label', str(_ft['target']))}  "
                  f"({_ns} candidate(s))")
        print("\\n  Next: change STAGE = 2 in the config cell and re-run this cell.")
        print("  Do NOT restart the kernel — FOLLOWUP_TARGETS lives in kernel memory.")
    else:
        print("\\n  No targets reached the triage SNR threshold.")
        print(f"  Consider lowering TRIAGE_CONFIG['triage_snr'] (currently {_TRIAGE_SNR}).")
elif STAGE == 2:
    print(f"\\n  Full reports in: {CANDIDATES_DIR / 'reports'}")
    print(f"  Summary CSV    : {CANDIDATES_DIR / 'candidate_summary.csv'}")

if _failed:
    print(f"\\n  Failed / skipped:")
    for _f in _failed:
        print(f"    {_f['label']:40s}  {_f['reason']}")
print(f"{'='*66}")\
"""

# ---------------------------------------------------------------------------
# Cell 4 — summary table
# ---------------------------------------------------------------------------

SUMMARY_SRC = """\
import pandas as pd

_summary_df = pd.DataFrame(_batch_summary)

if _summary_df.empty:
    print("No results yet — run the batch cell first.")
else:
    if STAGE == 1:
        _show = [c for c in ["label", "mission", "sectors", "n_planets",
                              "best_period_d", "best_snr", "best_depth_ppt",
                              "promising", "status"]
                 if c in _summary_df.columns]
        print(f"Stage 1 triage summary ({len(_summary_df)} targets):")
    else:
        _show = [c for c in ["label", "mission", "sectors", "n_planets",
                              "best_period_d", "best_snr", "best_depth_ppt",
                              "is_known_toi", "is_confirmed", "verdict", "status"]
                 if c in _summary_df.columns]
        print(f"Stage 2 follow-up summary ({len(_summary_df)} targets):")

    print(_summary_df[_show].to_string(index=False))

    _promising = _summary_df[
        _summary_df.get("promising", pd.Series(False, index=_summary_df.index)) == True
    ]
    if not _promising.empty:
        print(f"\\n{len(_promising)} target(s) flagged for Stage 2 follow-up:")
        print(_promising[["label", "best_period_d", "best_snr"]].to_string(index=False))\
"""

# ---------------------------------------------------------------------------
# Build and write notebook
# ---------------------------------------------------------------------------

cells = [
    md(HEADER_SRC),
    code(IMPORTS_SRC),
    code(CONFIG_SRC),
    code(BATCH_SRC),
    code(SUMMARY_SRC),
]

nb = {
    "nbformat":       4,
    "nbformat_minor": 4,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3 (ipykernel)",
            "language":     "python",
            "name":         "python3",
        },
        "language_info": {
            "name":    "python",
            "version": "3.14.0",
        },
    },
    "cells": cells,
}

for out in (NB_PATH_CANONICAL, NB_PATH_COPY):
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(nb, f, ensure_ascii=False, indent=1)
        print(f"Written: {out}")
    except PermissionError:
        print(f"Skipped (locked by Jupyter): {out}")
