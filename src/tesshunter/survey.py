"""Survey-scale search: configuration presets, the stitched-curve disk cache,
transit injection, and the one-job worker used by ``scripts/run_survey.py``.

The survey never calls ``search_target``. It downloads every survey-author
product for a TIC once, prepares and stitches them (:mod:`tesshunter.ffi`),
stores the stitched curve under ``data/cache/stitched``, and searches the
cached curve through :func:`tesshunter.pipeline.search_light_curve`. The
injection harness multiplies a batman model into the cached curve before the
same search, so completeness is measured on the real sampling, real noise and
real detrending of every star.

Nothing here talks to ExoFOP or submits anything anywhere. The pipeline
finds candidates.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import lightkurve as lk
import numpy as np

from . import ffi, pipeline
from .config import CACHE_DIR
from .stellar import StellarParams
from .download import observing_units_available, search_and_download_lc

logger = logging.getLogger(__name__)

STITCHED_DIR = CACHE_DIR / "stitched"


class NoDataError(RuntimeError):
    """No usable survey-author light curve exists for the target."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SurveyConfig:
    """Every knob of a survey search, in one frozen record.

    Ingestion fields (``authors`` .. ``quality_bitmask``) decide what a
    stitched curve contains and are hashed into the cache file name; search
    fields are passed to :func:`tesshunter.pipeline.search_light_curve`.
    """

    name: str = "survey_v1"
    # ── ingestion ──
    authors: tuple[str, ...] = ffi.SURVEY_AUTHORS
    qlp_flux: str = "kspsap"
    qlp_low_precision_mask: bool = True
    edge_trim_minutes: float = 120.0
    target_cadence_minutes: float = 30.0
    quality_bitmask: str = "default"
    max_units: Optional[int] = None
    # ── search ──
    period_min: float = 1.0
    period_max: float = 100.0
    duration_min: float = 0.045
    duration_max: float = 0.5
    bin_minutes: Optional[float] = 30.0
    max_planets: int = 3
    top_n: int = 8
    snr_min: float = 5.0
    snr_min_resolved: float = 5.0
    min_event_completeness: float = 0.5
    min_composite_score: float = 3.0
    min_transits: int = 2
    sigma_clip: float = 4.0
    mask_width_factor: float = 7.0
    window_days: Optional[float] = None
    grid_cap: Optional[int] = 40000
    local_grid_cap: Optional[int] = 1500
    time_budget_s: float = 600.0
    # -- search plan --
    #: "chunked": short periods per contiguous chunk of sectors at full
    #: frequency resolution, long periods on the whole stitch; "stitched":
    #: one search of the whole stitch (the grid cap then smears short periods
    #: on multi-year baselines, measured in P2).
    search_mode: str = "chunked"
    chunk_gap_days: float = 60.0
    chunk_min_baseline_days: float = 20.0
    long_period_min: float = 10.0
    max_planets_total: int = 12
    # -- prompt 8: the native-cadence path --
    #: "mast_stitched": products fetched from MAST, ingested by ``tesshunter.ffi``
    #: and stitched (prompts 2-4).  "audit_lc": the raw per-product arrays of the
    #: shared audit store (``data/survey/audit_lc``), prepared by
    #: ``tesshunter.audit_prep`` (prompt 8), so the search and the event rules
    #: read identical inputs.
    source: str = "mast_stitched"
    #: Drop products from sectors below this (None: keep all).  Prompt 8 searches
    #: sectors >= 56 (200-second FFIs) only.
    sector_min: Optional[int] = None
    #: "survey": the pipeline's own sigma clip + two-pass flatten (prompts 2-4).
    #: "audit_prep": the prompt-6 recipe (quality + low-precision mask, per-product
    #: biweight, upward clip, isolated-dip clip, deep clip) applied BEFORE the
    #: search, which then runs with its own flatten off.
    preprocess: str = "survey"
    #: The biweight window for ``preprocess="audit_prep"`` (days).  3 x T14 for
    #: every M-dwarf transit in the 0.5-30 d band is below the 0.75-d floor of
    #: ``audit_rules.WOTAN_WINDOW_MIN_DAYS``, so the floor is the window.
    audit_window_days: float = 0.75
    #: Measure a rotation proxy (Lomb-Scargle peak on the normalised corrected
    #: flux before the detrend) and store it in the record.
    rotation_proxy: bool = False
    #: The dip threshold of the alias resolver's event-completeness test:
    #: "cadence" (one per-cadence noise unit, prompts 0-7) or "mean" (one sigma
    #: of the in-transit mean, prompt 8).  See ``bls_search.EVENT_COMPLETENESS_NOISE``.
    event_completeness_noise: str = "cadence"

    INGEST_FIELDS = (
        "authors", "qlp_flux", "qlp_low_precision_mask", "edge_trim_minutes",
        "target_cadence_minutes", "quality_bitmask", "max_units",
    )
    #: Prompt-8 ingestion fields.  They enter the ingest key ONLY when they
    #: differ from their defaults, so every ``survey_v1`` cache file keeps the
    #: key it was written under.
    INGEST_FIELDS_P8 = ("source", "sector_min", "preprocess", "audit_window_days")
    # -- prompt 10 Part 2b: search capacity and ranking (HANDOFF_P10.md 0.3) --
    #: Which score picks the accepted survivor of a detection pass: "composite"
    #: (prompts 0-8) or the resolved "snr" (the survey_p10_rank variant); the
    #: composite floor (gate 4) stays either way.
    rank_by: str = "composite"
    #: Record every broad-BLS candidate list and alias resolution per partition
    #: and a per-partition ``budget_exhausted`` flag (the P9 replay
    #: instrumentation).  Off by default so ``survey_p8`` output is unchanged.
    record_traces: bool = False
    #: The prompt-10 fields are reported only when they differ from their
    #: defaults, so every earlier record (``config`` and ``params``) is byte-identical.
    P10_SEARCH_FIELDS = ("rank_by", "record_traces")
    # -- prompt K1 (k1/protocol/RULES_K1.md): the K-dwarf survey --
    #: [K1] "harmonise" (prompts 8-12): bin finer products to ``target_cadence_minutes`` and
    #: drop coarser ones.  "native_mixed" (K1 change 10): products finer than the target by the
    #: 1.5 ratio are binned to it (2-minute SPOC to 200 s); every other product is KEPT at its
    #: native cadence (1800 s in sectors 1-26, 600 s in 27-55, 200 s from 56).
    cadence_policy: str = "harmonise"
    #: [K1] Drop products from sectors above this (None: keep all).
    sector_max: Optional[int] = None
    #: [K1] The global pre-search deep clip of ``survey_p8.prepare_search_input`` (prompts 8-12:
    #: on; K1 change 3: off, the isolated single-cadence dip removal stays).
    deep_clip: bool = True
    #: [K1] Set every cadence's flux_err to its product's empirical noise (1.4826 MAD of the
    #: detrended, masked flux of that product) so the BLS inverse-variance weights are right
    #: across 1800-, 600- and 200-s products (QLP >= s56 ships all-NaN errors).
    empirical_flux_err: bool = False
    #: [K1] BLS duration-grid size (None: ``bls_search.DEFAULT_N_DURATIONS`` = 10).
    n_durations: Optional[int] = None
    #: [K1] Gate 7 judges a candidate at the cadence of its own in-transit cadences
    #: (``pipeline.GATE7_CADENCE = "in_transit"``) instead of the median binned cadence.
    exposure_aware: bool = False
    #: K1 ingestion fields enter the ingest key ONLY when they differ from their defaults, and
    #: K1 fields appear in ``to_dict`` only when non-default, so every earlier key and record is
    #: unchanged.
    INGEST_FIELDS_K1 = ("cadence_policy", "sector_max", "deep_clip", "empirical_flux_err")
    K1_SEARCH_FIELDS = ("n_durations", "exposure_aware")

    def ingest_key(self) -> str:
        """Short hash of the ingestion fields plus ``ffi.INGEST_VERSION``
        (names the cache file, so a code change invalidates old curves)."""
        payload = {}
        for k in self.INGEST_FIELDS:
            v = getattr(self, k)
            # Numbers are normalised to float so an override given as an int
            # (120) and the preset's float (120.0) name the same cache file.
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                v = float(v)
            payload[k] = v
        payload["authors"] = list(payload["authors"])
        payload["ingest_version"] = ffi.INGEST_VERSION
        defaults = {f.name: f.default for f in dataclasses.fields(SurveyConfig)}
        for k in self.INGEST_FIELDS_P8:
            v = getattr(self, k)
            if v != defaults[k]:
                payload[k] = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v
        for k in self.INGEST_FIELDS_K1:
            v = getattr(self, k)
            if v != defaults[k]:
                payload[k] = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]

    def search_kwargs(self) -> dict:
        kw = {
            "period_min": self.period_min, "period_max": self.period_max,
            "duration_min": self.duration_min, "duration_max": self.duration_max,
            "bin_minutes": self.bin_minutes, "max_planets": self.max_planets,
            "top_n": self.top_n, "snr_min": self.snr_min,
            "snr_min_resolved": self.snr_min_resolved,
            "min_event_completeness": self.min_event_completeness,
            "min_composite_score": self.min_composite_score,
            "min_transits": self.min_transits, "sigma_clip": self.sigma_clip,
            "mask_width_factor": self.mask_width_factor,
            "window_days": self.window_days, "grid_cap": self.grid_cap,
            "local_grid_cap": self.local_grid_cap,
            "time_budget_s": self.time_budget_s,
        }
        if self.rank_by != "composite":
            kw["rank_by"] = self.rank_by
        return kw

    def to_dict(self) -> dict:
        d = asdict(self)
        d["authors"] = list(self.authors)
        d["ingest_key"] = self.ingest_key()
        defaults = {f.name: f.default for f in dataclasses.fields(SurveyConfig)}
        for k in self.P10_SEARCH_FIELDS:
            if d.get(k) == defaults[k]:
                d.pop(k, None)
        for k in self.INGEST_FIELDS_K1 + self.K1_SEARCH_FIELDS:
            if d.get(k) == defaults[k]:
                d.pop(k, None)
        return d

    def k1_ingest_config(self) -> dict:
        """[K1] The non-default K1 ingestion fields (empty for every earlier preset)."""
        defaults = {f.name: f.default for f in dataclasses.fields(SurveyConfig)}
        return {k: getattr(self, k) for k in self.INGEST_FIELDS_K1 if getattr(self, k) != defaults[k]}


#: Native 200-second cadence in minutes (no binning anywhere in the search).
NATIVE_200S_MINUTES = 200.0 / 60.0

PRESETS: dict[str, SurveyConfig] = {
    "survey_v1": SurveyConfig(),
    # Prompt 8: mid-to-late M dwarfs at native 200-s cadence.  Products come from
    # the audit store (sectors >= 56 only, so no 600-s product can enter the
    # stitch), the prompt-6 preprocessing runs before the search, nothing is
    # binned, and the period band is the one the yield model counts.  Durations:
    # a central transit at 0.5 d on a 0.3 Rsun / 0.3 Msun star lasts 0.65 h and
    # one at 30 d on a 0.45 Rsun star 3.3 h; the grid runs 0.02-0.20 d
    # (0.48-4.8 h), which is 8.6 to 86 cadences at 200 s, so gate 7 never arms.
    "survey_p8": SurveyConfig(
        name="survey_p8", source="audit_lc", sector_min=56, preprocess="audit_prep",
        audit_window_days=0.75, rotation_proxy=True, event_completeness_noise="mean",
        target_cadence_minutes=NATIVE_200S_MINUTES, bin_minutes=None,
        period_min=0.5, period_max=30.0, duration_min=0.02, duration_max=0.20,
        long_period_min=10.0, time_budget_s=900.0,
    ),
    # The 600-second comparison of Part 1e: sectors >= 27 admitted, everything
    # binned to the common 10-minute cadence before the detrend, otherwise the
    # same search.  Duration floor 0.02 d is 2.9 bins of 600 s, so gate 7 does
    # not arm here either.
    "survey_p8_600s": SurveyConfig(
        name="survey_p8_600s", source="audit_lc", sector_min=27, preprocess="audit_prep",
        audit_window_days=0.75, rotation_proxy=True, event_completeness_noise="mean",
        target_cadence_minutes=10.0, bin_minutes=None,
        period_min=0.5, period_max=30.0, duration_min=0.02, duration_max=0.20,
        long_period_min=10.0, time_budget_s=900.0,
    ),
}

# Prompt 10 Part 2b (HANDOFF_P10.md 0.3): the search-capacity and ranking
# variants.  Ingestion is identical to survey_p8 (same stitched cache); only
# the search fields differ.  survey_p8 itself is not edited.
PRESETS["survey_p10_budget"] = dataclasses.replace(PRESETS["survey_p8"], name="survey_p10_budget", time_budget_s=2700.0)
PRESETS["survey_p10_slots"] = dataclasses.replace(PRESETS["survey_p8"], name="survey_p10_slots",
                                                  max_planets=6, max_planets_total=24, top_n=16)
PRESETS["survey_p10_rank"] = dataclasses.replace(PRESETS["survey_p10_slots"], name="survey_p10_rank", rank_by="snr")
PRESETS["survey_p10_both"] = dataclasses.replace(PRESETS["survey_p10_rank"], name="survey_p10_both", time_budget_s=2700.0)
# Part 2d freeze: variant e won the complete paired Part 2b comparison.
# The named frozen preset preserves e's search and the original ingestion.
PRESETS["survey_p10"] = dataclasses.replace(PRESETS["survey_p10_both"], name="survey_p10")

# Prompt K1 (k1/protocol/RULES_K1.md): K dwarfs and early M dwarfs on every usable archival
# FFI sector.  Search machinery of survey_p10 (chunked plan, stitch re-measurement,
# long_period_min 10 d, slots and ranking of variant e); changed inputs and grids only:
#   change 3  no global deep clip (isolated single-cadence dips are still removed)
#   change 4  durations 0.02-0.35 d in 14 log steps (central K-dwarf transits last 4-6 h)
#   change 5  per-product biweight window 1.1 d (>= 3 x the 0.35-d maximum duration)
#   change 10 every usable product at its native cadence (sectors <= 98; the K1 store holds
#             only usable products), per-product empirical errors, exposure-aware gate 7 and
#             event completeness
#   periods 0.5-50 d (>= 3 transits unchanged); time_budget_s is set by rule E4.
PRESETS["survey_k1"] = dataclasses.replace(
    PRESETS["survey_p10"], name="survey_k1", sector_min=None, sector_max=98,
    cadence_policy="native_mixed", deep_clip=False, empirical_flux_err=True, audit_window_days=1.1,
    period_max=50.0, duration_min=0.02, duration_max=0.35, n_durations=14, exposure_aware=True,
    event_completeness_noise="mean_err", time_budget_s=2700.0,
)
#: [K1] identical except usable sectors limited to 56-98 (the comparison arm of rule E1).
PRESETS["survey_k1_s56"] = dataclasses.replace(PRESETS["survey_k1"], name="survey_k1_s56", sector_min=56)


def budget_exhausted(notes: list[str] | None) -> bool:
    """[P10] Did a sub-search stop because another detection pass would not fit its
    wall budget?  Read from the search notes (``_detect_planets`` writes the message);
    an exhausted budget still returns status ``ok`` (gotcha 11), so read this, not the status."""
    return any("would not fit the" in str(n) and "budget" in str(n) for n in (notes or []))


class TraceRecorder:
    """[P10] Record every broad-BLS candidate list and every alias resolution of a
    search, per partition and detection pass, to a JSONL file (or in memory when no
    path is given).  Wraps ``bls_search.run_bls`` and
    ``bls_search.resolve_aliases_for_candidate`` for the duration of a ``with`` block
    and restores them afterwards; the search itself is unchanged.  Ported from the P9
    replay instrumentation (``p9/runner.py``)."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else None
        self.partition: Optional[str] = None
        self.passes: dict = {}
        self.n_events = 0
        self.events: list[dict] = []
        self._orig = None

    def __enter__(self):
        from . import bls_search
        self._orig = (bls_search.run_bls, bls_search.resolve_aliases_for_candidate)
        original_bls, original_alias = self._orig

        def recorded_bls(*args, **kwargs):
            result = original_bls(*args, **kwargs)
            self.passes[self.partition] = self.passes.get(self.partition, 0) + 1
            cands = result[2] if isinstance(result, tuple) and len(result) > 2 else None
            self.record("broad_bls", {
                "candidates": cands.to_dict(orient="records") if hasattr(cands, "to_dict") else [],
                "settings": {k: v for k, v in kwargs.items() if k in ("period_min", "period_max", "top_n", "n_max", "n_periods")}})
            return result

        def recorded_alias(*args, **kwargs):
            result = original_alias(*args, **kwargs)
            raw = args[1] if len(args) > 1 else kwargs.get("raw_candidate")
            resolved = result[0] if isinstance(result, tuple) else result
            self.record("alias", {"raw": raw.to_dict() if hasattr(raw, "to_dict") else raw,
                                  "resolved": resolved.to_dict() if hasattr(resolved, "to_dict") else resolved})
            return result

        bls_search.run_bls = recorded_bls
        bls_search.resolve_aliases_for_candidate = recorded_alias
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")
        return self

    def __exit__(self, *exc):
        from . import bls_search
        bls_search.run_bls, bls_search.resolve_aliases_for_candidate = self._orig
        return False

    def record(self, event: str, data: dict) -> None:
        entry = {"event": event, "partition": self.partition, "pass": self.passes.get(self.partition, 0), **data}
        self.n_events += 1
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(pipeline._to_native(entry), default=str) + "\n")
        else:
            self.events.append(entry)


def get_config(name: str = "survey_v1", **overrides: Any) -> SurveyConfig:
    """A preset with optional field overrides (unknown fields raise)."""
    base = PRESETS[name]
    valid = {f.name for f in dataclasses.fields(SurveyConfig)}
    bad = set(overrides) - valid
    if bad:
        raise ValueError(f"unknown SurveyConfig field(s): {sorted(bad)}")
    if "authors" in overrides:
        overrides["authors"] = tuple(overrides["authors"])
    return dataclasses.replace(base, **overrides)


# ---------------------------------------------------------------------------
# Stitched-curve cache
# ---------------------------------------------------------------------------

def stitched_path(tic: int, cfg: SurveyConfig, cache_dir: Optional[Path] = None) -> Path:
    root = Path(cache_dir) if cache_dir is not None else STITCHED_DIR
    return root / f"tic{int(tic)}_{cfg.ingest_key()}.npz"


def _atomic_write_bytes(path: Path, write_fn) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.part")
    try:
        write_fn(tmp)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def save_stitched(path: Path, lc: lk.LightCurve, provenance: dict) -> None:
    """Write ``time/flux/flux_err`` and a JSON sidecar atomically."""
    t = np.asarray(lc.time.value, dtype=float)
    f = np.asarray(lc.flux.value, dtype=float)
    e = np.asarray(lc.flux_err.value, dtype=float) if lc.flux_err is not None else np.full_like(f, np.nan)

    def _npz(tmp: Path) -> None:
        with open(tmp, "wb") as fh:
            np.savez_compressed(fh, time=t, flux=f, flux_err=e)

    _atomic_write_bytes(path, _npz)
    side = path.with_suffix(".json")

    def _json(tmp: Path) -> None:
        tmp.write_text(json.dumps(pipeline._to_native(provenance), indent=1), encoding="utf-8")

    _atomic_write_bytes(side, _json)


def load_stitched(path: Path) -> tuple[lk.LightCurve, dict]:
    """Read a cached stitched curve and its provenance sidecar."""
    from astropy import units as u
    from astropy.time import Time

    with np.load(path) as z:
        t, f, e = z["time"], z["flux"], z["flux_err"]
    prov = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    lc = lk.LightCurve(
        time=Time(t, format="btjd", scale="tdb"),
        flux=f * u.dimensionless_unscaled,
        flux_err=e * u.dimensionless_unscaled,
    )
    lc.meta["SECTOR"] = "multi"
    lc.meta["TESSHUNTER_PROVENANCE"] = prov.get("products", [])
    lc.meta["TESSHUNTER_UNITS"] = prov.get("units_used", [])
    lc.meta["TESSHUNTER_INGEST"] = prov.get("ingest", [])
    return lc, prov


def fetch_products(tic: int, cfg: SurveyConfig, offline: bool = False) -> lk.LightCurveCollection:
    """Every survey-author product for ``tic`` (all sectors).

    ``offline=True`` skips the MAST query and reads whatever the lightkurve
    FITS cache already holds for the TIC (used to re-stitch a star under a
    different ingestion config without touching the network).
    """
    if offline:
        from .download import _get_author, _load_cached_lightcurves
        lcc = _load_cached_lightcurves(f"TIC {int(tic)}", "TESS")
        if lcc is None or len(lcc) == 0:
            raise NoDataError(f"TIC {tic}: nothing in the local FITS cache")
        keep = []
        for lc in lcc:
            ticid = lc.meta.get("TICID")
            try:
                if ticid is not None and int(ticid) != int(tic):
                    continue
            except (TypeError, ValueError):
                pass
            if (_get_author(lc) or "").upper() in {a.upper() for a in cfg.authors}:
                keep.append(lc)
        if not keep:
            raise NoDataError(f"TIC {tic}: no {'/'.join(cfg.authors)} product in the local FITS cache")
        out = lk.LightCurveCollection(keep)
        out.tesshunter_events = [{"event": "offline_cache_mode",
                                  "detail": f"{len(keep)} cached file(s) read without a MAST query"}]
        return out
    lcc = search_and_download_lc(
        int(tic), mission="TESS", author=list(cfg.authors), exptime=None,
        quality_bitmask=cfg.quality_bitmask, max_results=None,
    )
    if lcc is None or len(lcc) == 0:
        raise NoDataError(f"TIC {tic}: no {'/'.join(cfg.authors)} light curves on MAST")
    return lcc


def build_stitched(tic: int, cfg: SurveyConfig, lcc: lk.LightCurveCollection) -> tuple[lk.LightCurve, dict]:
    """Prepare + stitch a downloaded collection; return (lc, provenance)."""
    prepared, preps = ffi.prepare_products(
        lcc, qlp_flux=cfg.qlp_flux, qlp_low_precision_mask=cfg.qlp_low_precision_mask,
        edge_trim_minutes=cfg.edge_trim_minutes,
        target_cadence_minutes=cfg.target_cadence_minutes, max_units=cfg.max_units,
    )
    if not prepared:
        raise NoDataError(f"TIC {tic}: no usable product after ingestion "
                          f"({[p.notes for p in preps]})")
    lc = ffi.stitch_prepared(prepared, preps)
    units_used = list(lc.meta.get("TESSHUNTER_UNITS", []))
    provenance = {
        "tic_id": int(tic),
        "products": list(lc.meta.get("TESSHUNTER_PROVENANCE", [])),
        "units_used": units_used,
        "units_all": observing_units_available(lcc, "TESS"),
        "fallback_events": list(getattr(lcc, "tesshunter_events", []) or []),
        "n_products_downloaded": len(lcc),
        "ingest": lc.meta.get("TESSHUNTER_INGEST", []),
        "ingest_key": cfg.ingest_key(),
        "ingest_config": {k: (list(v) if isinstance(v, tuple) else v)
                          for k, v in asdict(cfg).items() if k in cfg.INGEST_FIELDS},
        "n_cadences": int(len(lc)),
        "baseline_days": float(lc.time.value.max() - lc.time.value.min()) if len(lc) else 0.0,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "lightkurve_version": lk.__version__,
    }
    return lc, provenance


def get_stitched(
    tic: int,
    cfg: SurveyConfig,
    *,
    cache_dir: Optional[Path] = None,
    refresh: bool = False,
    allow_download: bool = True,
    offline: bool = False,
) -> tuple[lk.LightCurve, dict, dict]:
    """Stitched curve for ``tic`` from the cache, else built and cached.

    Returns ``(lc, provenance, info)`` with ``info`` holding ``cache_hit`` and
    the download / stitch wall-clock seconds. ``offline`` rebuilds from the
    local FITS cache without a MAST query.
    """
    path = stitched_path(tic, cfg, cache_dir)
    if path.exists() and path.with_suffix(".json").exists() and not refresh:
        t0 = time.perf_counter()
        lc, prov = load_stitched(path)
        return lc, prov, {"cache_hit": True, "path": str(path),
                          "load_s": time.perf_counter() - t0, "download_s": 0.0, "stitch_s": 0.0}
    if not allow_download and not offline:
        raise NoDataError(f"TIC {tic}: not in the stitched cache and downloads are disabled")
    t0 = time.perf_counter()
    lcc = fetch_products(tic, cfg, offline=offline)
    t1 = time.perf_counter()
    lc, prov = build_stitched(tic, cfg, lcc)
    t2 = time.perf_counter()
    save_stitched(path, lc, prov)
    return lc, prov, {"cache_hit": False, "path": str(path), "load_s": 0.0,
                      "download_s": t1 - t0, "stitch_s": t2 - t1}


# ---------------------------------------------------------------------------
# Transit injection (batman, quadratic limb darkening)
# ---------------------------------------------------------------------------

#: Adopted quadratic limb-darkening anchors for the TESS band at log g 4.5,
#: (Teff K -> (u1, u2)), interpolated linearly in Teff. Approximate values
#: in the range tabulated by Claret 2017 (A&A 600, A30); they set the
#: transit shape of INJECTED signals only.
LD_ANCHORS_TESS: tuple[tuple[float, float, float], ...] = (
    (3000.0, 0.18, 0.44),
    (3500.0, 0.22, 0.40),
    (4000.0, 0.44, 0.24),
    (4500.0, 0.50, 0.18),
    (5000.0, 0.45, 0.20),
    (5500.0, 0.40, 0.21),
    (6000.0, 0.36, 0.22),
    (6500.0, 0.31, 0.24),
    (7000.0, 0.28, 0.26),
)


def limb_darkening_for_teff(teff_k: Optional[float]) -> tuple[float, float]:
    """Quadratic (u1, u2) for the TESS band by linear interpolation in Teff."""
    t = np.array([a[0] for a in LD_ANCHORS_TESS])
    u1 = np.array([a[1] for a in LD_ANCHORS_TESS])
    u2 = np.array([a[2] for a in LD_ANCHORS_TESS])
    if teff_k is None or not np.isfinite(teff_k):
        teff_k = 5500.0
    teff_k = float(np.clip(teff_k, t.min(), t.max()))
    return float(np.interp(teff_k, t, u1)), float(np.interp(teff_k, t, u2))


def a_over_rs(period_days: float, mass_msun: float, radius_rsun: float) -> float:
    """Semi-major axis in stellar radii from Kepler's third law."""
    G = 6.674e-11
    M = mass_msun * 1.98847e30
    R = radius_rsun * 6.957e8
    P = period_days * 86400.0
    a = (G * M * P ** 2 / (4.0 * np.pi ** 2)) ** (1.0 / 3.0)
    return float(a / R)


def transit_model(
    time: np.ndarray,
    *,
    period: float,
    t0: float,
    rp_rs: float,
    b: float,
    a_rs: float,
    u: tuple[float, float],
    exp_time_days: Optional[float] = None,
    supersample: int = 7,
) -> np.ndarray:
    """batman quadratic-limb-darkened transit model evaluated at ``time``."""
    import batman

    params = batman.TransitParams()
    params.t0 = float(t0)
    params.per = float(period)
    params.rp = float(rp_rs)
    params.a = float(a_rs)
    inc = np.degrees(np.arccos(np.clip(b / a_rs, -1.0, 1.0)))
    params.inc = float(inc)
    params.ecc = 0.0
    params.w = 90.0
    params.u = [float(u[0]), float(u[1])]
    params.limb_dark = "quadratic"
    kwargs = {}
    if exp_time_days and exp_time_days > 0:
        kwargs = {"supersample_factor": int(supersample), "exp_time": float(exp_time_days)}
    m = batman.TransitModel(params, np.asarray(time, dtype=float), **kwargs)
    return m.light_curve(params)


def transit_duration_days(period: float, a_rs: float, b: float, rp_rs: float) -> float:
    """T14 for a circular orbit (Winn 2010, eq. 14)."""
    inc = np.arccos(np.clip(b / a_rs, -1.0, 1.0))
    arg = np.sqrt(max((1.0 + rp_rs) ** 2 - b ** 2, 0.0)) / (a_rs * np.sin(inc))
    return float(period / np.pi * np.arcsin(np.clip(arg, 0.0, 1.0)))


def inject_transit(
    lc: lk.LightCurve,
    *,
    period: float,
    t0: float,
    rp_rs: float,
    b: float,
    a_rs: float,
    u: tuple[float, float],
    exp_time_minutes: Optional[float] = None,
) -> tuple[lk.LightCurve, dict]:
    """Multiply a transit model into a normalised light curve.

    Returns the injected curve (meta preserved) and a record of the model:
    maximum depth, mean in-transit depth, T14, and the number of cadences the
    model touched.
    """
    t = np.asarray(lc.time.value, dtype=float)
    exp_days = (exp_time_minutes / 1440.0) if exp_time_minutes else None
    model = transit_model(t, period=period, t0=t0, rp_rs=rp_rs, b=b, a_rs=a_rs,
                          u=u, exp_time_days=exp_days)
    out = lc.copy()
    out.flux = out.flux * model
    in_tr = model < 1.0
    info = {
        "period": float(period), "t0": float(t0), "rp_rs": float(rp_rs), "b": float(b),
        "a_rs": float(a_rs), "u1": float(u[0]), "u2": float(u[1]),
        "exp_time_minutes": exp_time_minutes,
        "depth_max_ppm": float((1.0 - model.min()) * 1e6),
        "depth_mean_in_transit_ppm": float((1.0 - model[in_tr]).mean() * 1e6) if in_tr.any() else 0.0,
        "t14_days": transit_duration_days(period, a_rs, b, rp_rs),
        "n_cadences_in_transit": int(in_tr.sum()),
        "n_transits_with_data": int(np.unique(np.round((t[in_tr] - t0) / period)).size) if in_tr.any() else 0,
    }
    return out, info


# ---------------------------------------------------------------------------
# Search plan: chunks for short periods, the stitch for long ones
# ---------------------------------------------------------------------------

def split_chunks(time: np.ndarray, gap_days: float) -> list[np.ndarray]:
    """Boolean masks of contiguous runs separated by gaps longer than ``gap_days``."""
    t = np.asarray(time, dtype=float)
    if t.size == 0:
        return []
    cut = np.flatnonzero(np.diff(t) > gap_days) + 1
    starts = np.concatenate(([0], cut))
    stops = np.concatenate((cut, [t.size]))
    masks = []
    for a, b in zip(starts, stops):
        m = np.zeros(t.size, dtype=bool)
        m[a:b] = True
        masks.append(m)
    return masks


def plan_searches(lc: lk.LightCurve, cfg: SurveyConfig) -> list[dict]:
    """The sub-searches for one star: ``[{label, mask, period_min, period_max, budget_s}]``.

    Why: the BLS frequency step must be about duration_min / (4 x baseline)
    for a transit to stay phase-coherent over the whole baseline. That step
    is the same for every period, so the number of grid points a period
    range needs is proportional to its width in FREQUENCY: [1, 10] d spans
    0.9 per day, [10, 100] d only 0.09 per day. On a 2,700-day stitch the
    short range wants about 240,000 points; a 20,000-point cap smears every
    short-period peak (injections at SNR of hundreds were missed, P2).
    Searching each contiguous chunk of sectors separately keeps the short
    range affordable at full resolution, and the long range is searched on
    the whole stitch where it is cheap. Candidates are merged afterwards.
    """
    t = np.asarray(lc.time.value, dtype=float)
    n = t.size
    if n == 0:
        return []
    full = np.ones(n, dtype=bool)
    baseline = float(t.max() - t.min()) if n > 1 else 0.0
    if cfg.search_mode != "chunked":
        return [{"label": "stitch", "mask": full, "period_min": cfg.period_min,
                 "period_max": cfg.period_max, "budget_s": cfg.time_budget_s}]
    chunks = [m for m in split_chunks(t, cfg.chunk_gap_days)
              if m.sum() >= 50 and (t[m].max() - t[m].min()) >= cfg.chunk_min_baseline_days]
    plan: list[dict] = []
    if len(chunks) <= 1:
        pmax = min(cfg.period_max, max(baseline / 2.0, cfg.period_min * 1.5))
        plan.append({"label": "chunk0", "mask": full, "period_min": cfg.period_min,
                     "period_max": pmax, "budget_s": cfg.time_budget_s})
        return plan
    for i, m in enumerate(chunks):
        span = float(t[m].max() - t[m].min())
        pmax = min(cfg.period_max, max(span / 2.0, cfg.period_min * 1.5))
        plan.append({"label": f"chunk{i}", "mask": m, "period_min": cfg.period_min,
                     "period_max": pmax, "budget_s": 0.0})
    plan.append({"label": "stitch", "mask": full,
                 "period_min": max(cfg.long_period_min, cfg.period_min),
                 "period_max": cfg.period_max, "budget_s": 0.0})
    weights = np.array([float(p["mask"].sum()) for p in plan])
    weights /= weights.sum()
    for p, w in zip(plan, weights):
        p["budget_s"] = max(60.0, cfg.time_budget_s * float(w))
    return plan


def merge_candidates(searches: list[dict], max_total: int, period_tol: float = 0.01) -> list[dict]:
    """Union of sub-search candidates; equal periods (within ``period_tol``)
    keep the higher-SNR entry. Sorted by SNR, capped, renumbered."""
    pool = []
    for s in searches:
        for p in s.get("planets") or []:
            q = dict(p)
            q["search"] = s["label"]
            pool.append(q)
    pool.sort(key=lambda q: -float(q.get("snr", 0.0)))
    kept: list[dict] = []
    for q in pool:
        dup = any(abs(float(q["period_days"]) / float(k["period_days"]) - 1.0) < period_tol for k in kept)
        if dup:
            continue
        kept.append(q)
        if len(kept) >= max_total:
            break
    for i, q in enumerate(kept, 1):
        q["planet_num_search"] = q.get("planet_num")
        q["planet_num"] = i
    return kept


def confirm_on_stitch(
    lc_raw: lk.LightCurve,
    cands: list[dict],
    cfg: SurveyConfig,
    n_max: int = 8000,
    do_flatten: bool = True,
) -> dict:
    """Re-measure every merged candidate on the WHOLE stitched curve.

    A chunk search sees one contiguous run of sectors. A real periodic signal
    folds coherently across every chunk, so a local BLS on the full stitch
    at the candidate's period (a +/-1% window, which is cheap at full
    frequency resolution because the window is narrow) returns an SNR at
    least as large as the chunk's and a consistent epoch; a chunk-local
    artifact is diluted by the other chunks. Nothing is removed here: the
    stitch SNR, depth, transit count and epoch consistency are recorded on
    each candidate (``stitch_*`` keys) so the false-alarm and completeness
    runs can measure what any threshold on them costs and buys.
    """
    from . import bls_search, preprocessing

    t0 = time.perf_counter()
    info = {"n_confirmed": 0, "n_candidates": len(cands), "error": None}
    if not cands:
        return info
    try:
        clean, _rec = preprocessing.preprocess(
            lc_raw, sigma=cfg.sigma_clip, do_flatten=do_flatten, window_days=cfg.window_days,
            max_transit_duration_days=cfg.duration_max,
        )
        binned = preprocessing.bin_lightcurve(clean, bin_minutes=cfg.bin_minutes)
        bt = np.asarray(binned.time.value, dtype=float)
        n_chunks = len([m for m in split_chunks(bt, cfg.chunk_gap_days)])
    except Exception as exc:                                  # pragma: no cover
        info["error"] = f"{type(exc).__name__}: {exc}"
        for q in cands:
            q["stitch_snr"] = None
        return info
    for q in cands:
        P = float(q["period_days"])
        q["stitch_n_chunks"] = int(n_chunks)
        if q.get("search") == "stitch":
            q["stitch_period_days"] = P
            q["stitch_snr"] = float(q.get("snr", 0.0))
            q["stitch_depth_ppt"] = float(q.get("depth_ppt", 0.0))
            q["stitch_n_transits"] = int(q.get("n_transits_observed", 0) or 0)
            q["stitch_epoch_consistent"] = True
            q["stitch_snr_ratio"] = 1.0
            info["n_confirmed"] += 1
            continue
        try:
            _, _, loc = bls_search.run_bls(
                binned, period_min=P * 0.99, period_max=P * 1.01,
                duration_min=cfg.duration_min, duration_max=cfg.duration_max,
                top_n=1, n_max=n_max,
            )
        except Exception:
            loc = None
        if loc is None or loc.empty:
            q["stitch_period_days"] = None
            q["stitch_snr"] = 0.0
            q["stitch_depth_ppt"] = 0.0
            q["stitch_n_transits"] = 0
            q["stitch_epoch_consistent"] = False
            q["stitch_snr_ratio"] = 0.0
            continue
        row = loc.iloc[0]
        ps = float(row["period_days"])
        dur = max(float(q.get("duration_days", 0.0)), float(row["duration_days"]), 0.02)
        d_epoch = (float(row["epoch_btjd"]) - float(q["epoch_btjd"]) + 0.5 * ps) % ps - 0.5 * ps
        q["stitch_period_days"] = ps
        q["stitch_snr"] = float(row["snr"])
        q["stitch_depth_ppt"] = float(row["depth_ppt"])
        q["stitch_n_transits"] = int(row.get("n_transits_observed", 0) or 0)
        q["stitch_epoch_btjd"] = float(row["epoch_btjd"])
        q["stitch_epoch_consistent"] = bool(abs(d_epoch) <= dur)
        q["stitch_snr_ratio"] = float(row["snr"]) / max(float(q.get("snr", 0.0)), 1e-9)
        info["n_confirmed"] += 1
    info["seconds"] = time.perf_counter() - t0
    return info


# ---------------------------------------------------------------------------
# One job
# ---------------------------------------------------------------------------

def run_job(job: dict, *, cache_dir: Optional[Path] = None, allow_download: bool = True) -> dict:
    """Execute one survey job and return a JSON-able record.

    ``job`` keys: ``job_id``, ``tic_id``, optional ``config`` (preset name),
    ``overrides`` (SurveyConfig fields), ``star`` (radius_rsun, mass_msun,
    teff_k), ``injection`` (period, t0_frac, rp_rs, b; a_rs/u derived if
    absent), ``prefetch_only`` (build the cache and stop).
    """
    t_job = time.perf_counter()
    tic = int(job["tic_id"])
    cfg = get_config(job.get("config", "survey_v1"), **(job.get("overrides") or {}))
    star = job.get("star") or {}
    rec: dict[str, Any] = {
        "job_id": job.get("job_id", f"tic{tic}"),
        "tic_id": tic,
        "config": cfg.to_dict(),
        "star": star,
        "status": "ok",
        "error": None,
        "cache": None,
        "injection": None,
        "injection_model": None,
        "result": None,
        "timings": {},
    }
    try:
        inj = job.get("injection")
        if cfg.source == "audit_lc":
            # Prompt 8: raw per-product arrays from the audit store, injected
            # (if asked) into SAP and corrected flux BEFORE the prompt-6
            # preprocessing, which replaces the survey's own flatten below.
            from . import survey_p8
            try:
                lc_raw, prov, info = survey_p8.get_prepared(
                    tic, cfg, cache_dir=cache_dir, refresh=bool(job.get("refresh")),
                    lc_root=(Path(job["lc_root"]) if job.get("lc_root") else None),
                    injection=inj, star=star,
                )
            except survey_p8.NoStoreDataError as exc:
                raise NoDataError(str(exc)) from exc
            rec["cache"] = {k: v for k, v in info.items() if k != "injection_model"}
            rec["rotation_proxy"] = prov.get("rotation_proxy")
            rec["prepare_counters"] = prov.get("counters")
            if inj:
                rec["injection"] = dict(inj)
                rec["injection_model"] = info.get("injection_model")
            inj = None                     # already applied at product level
        else:
            lc_raw, prov, info = get_stitched(
                tic, cfg, cache_dir=cache_dir, allow_download=allow_download,
                offline=bool(job.get("offline")), refresh=bool(job.get("refresh")),
            )
            rec["cache"] = info
        rec["n_cadences_raw"] = int(len(lc_raw))
        rec["baseline_days"] = float(prov.get("baseline_days", 0.0))
        rec["n_units"] = len(prov.get("units_used", []))
        if job.get("prefetch_only"):
            rec["timings"]["total"] = time.perf_counter() - t_job
            return rec

        if inj:
            t = np.asarray(lc_raw.time.value, dtype=float)
            period = float(inj["period"])
            t0 = float(inj.get("t0") if inj.get("t0") is not None
                       else t.min() + float(inj.get("t0_frac", 0.5)) * period)
            radius = float(star.get("radius_rsun") or 1.0)
            mass = float(star.get("mass_msun") or radius)      # M ~ R for dwarfs
            a_rs = float(inj.get("a_rs") or a_over_rs(period, mass, radius))
            u = (inj["u1"], inj["u2"]) if "u1" in inj else limb_darkening_for_teff(star.get("teff_k"))
            lc_raw, model_info = inject_transit(
                lc_raw, period=period, t0=t0, rp_rs=float(inj["rp_rs"]), b=float(inj["b"]),
                a_rs=a_rs, u=u, exp_time_minutes=cfg.target_cadence_minutes,
            )
            rec["injection"] = dict(inj)
            rec["injection_model"] = model_info

        t_s = time.perf_counter()
        from . import bls_search
        bls_search.EVENT_COMPLETENESS_NOISE = cfg.event_completeness_noise
        # [K1] module switches set from the preset on every job (defaults reproduce prompt 12)
        bls_search.DEFAULT_N_DURATIONS = int(cfg.n_durations) if cfg.n_durations else 10
        plan = plan_searches(lc_raw, cfg)
        prov_small = {k: prov.get(k) for k in
                      ("products", "units_used", "units_all", "fallback_events", "n_products_downloaded")}
        n_units_all = len(prov.get("units_used", [])) or None
        searches: list[dict] = []
        kw = cfg.search_kwargs()
        own_flatten = cfg.preprocess != "audit_prep"
        if not own_flatten:
            # The series is already detrended by the prompt-6 recipe: the
            # pipeline's flatten (and its two-pass variant) stay off, so the
            # search runs on exactly the arrays the event rules will read.
            kw.update({"do_flatten": False, "two_pass_flatten": False})
        # [P10] the trace instrumentation is a no-op context unless cfg.record_traces
        tracer = TraceRecorder(job.get("trace_path")) if cfg.record_traces else None
        # [K1] gate 7 at the candidate's own cadence (entered before the tracer, left after it)
        gate7 = pipeline.ExposureAwareGate7() if cfg.exposure_aware else _NullContext()
        with gate7, (tracer if tracer is not None else _NullContext()):
            for item in plan:
                if tracer is not None:
                    tracer.partition = item["label"]
                sub = lc_raw[item["mask"]] if not item["mask"].all() else lc_raw
                kw_i = dict(kw)
                kw_i.update({"period_min": item["period_min"], "period_max": item["period_max"],
                             "time_budget_s": item["budget_s"]})
                res = pipeline.search_light_curve(
                    sub, target=tic, mission="TESS", n_sectors=n_units_all, provenance=prov_small,
                    stellar_radius_rsun=star.get("radius_rsun"), target_label=f"TIC {tic} {item['label']}",
                    stellar_params=(StellarParams.from_survey_row(star, tic) if star else None),
                    **kw_i,
                )
                d = res.to_dict()
                tt = np.asarray(sub.time.value, dtype=float)
                entry = {
                    "label": item["label"], "n_cadences": int(len(sub)),
                    "baseline_days": float(tt.max() - tt.min()) if tt.size > 1 else 0.0,
                    "period_min": item["period_min"], "period_max": item["period_max"],
                    "budget_s": item["budget_s"], "timings": d["timings"], "planets": d["planets"],
                    "vetting": d["vetting"], "notes": d["notes"], "prep": d["prep"],
                    "n_cadences_clean": d["n_cadences_clean"],
                }
                if tracer is not None:
                    entry["budget_exhausted"] = budget_exhausted(d["notes"])
                    entry["n_passes_traced"] = int(tracer.passes.get(item["label"], 0))
                searches.append(entry)
        if tracer is not None:
            rec["trace"] = {"path": None if tracer.path is None else str(tracer.path), "n_events": tracer.n_events,
                            "passes": dict(tracer.passes)}
            if tracer.path is None:
                rec["trace"]["events"] = tracer.events
        merged = merge_candidates(searches, cfg.max_planets_total)
        confirm_info = None
        if cfg.search_mode == "chunked" and merged:
            confirm_info = confirm_on_stitch(lc_raw, merged, cfg, do_flatten=own_flatten)
            rec["timings"]["confirm"] = float(confirm_info.get("seconds", 0.0) or 0.0)
        rec["stitch_confirmation"] = confirm_info
        vet_by = {(s_["label"], v["planet_num"]): v for s_ in searches for v in (s_.get("vetting") or [])}
        vetting = []
        for q in merged:
            v = dict(vet_by.get((q["search"], q.get("planet_num_search")), {}))
            v["planet_num"] = q["planet_num"]
            vetting.append(v)
        timings: dict[str, float] = {}
        for s_ in searches:
            for k, v in (s_["timings"] or {}).items():
                timings[k] = timings.get(k, 0.0) + float(v)
        rec["timings"]["search"] = time.perf_counter() - t_s
        rec["searches"] = searches
        rec["result"] = {
            "target": tic, "mission": "TESS", "planets": merged, "vetting": vetting,
            "provenance": prov_small, "timings": timings,
            "n_cadences_raw": int(len(lc_raw)), "n_sectors": n_units_all or 0,
            "n_searches": len(searches), "search_mode": cfg.search_mode,
            "notes": [f"[{s_['label']}] {n}" for s_ in searches for n in (s_.get("notes") or [])],
            "params": kw,
        }
    except NoDataError as exc:
        rec["status"] = "no_data"
        rec["error"] = str(exc)
    except Exception as exc:                                   # pragma: no cover
        import traceback
        rec["status"] = "error"
        rec["error"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    rec["timings"]["total"] = time.perf_counter() - t_job
    return rec


class _NullContext:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


def write_json_atomic(path: Path, payload: dict) -> None:
    """Write JSON via a temp file and ``os.replace`` (a kill never leaves a
    half-written result that a resume would trust)."""
    def _w(tmp: Path) -> None:
        tmp.write_text(json.dumps(pipeline._to_native(payload), indent=1), encoding="utf-8")
    _atomic_write_bytes(path, _w)
