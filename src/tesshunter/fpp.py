"""False-positive probability with TRICERATOPS (prompt 3, part B).

Wraps ``triceratops.target`` so one call gives the FPP and the nearby
false-positive probability (NFPP) of a candidate against the real TIC / Gaia
neighbours, keeps every raw output on disk, and never raises into the
pipeline.

What TRICERATOPS needs and where it comes from here:

* the target's TIC neighbours within ``search_radius`` pixels (TRICERATOPS
  queries the TIC itself) and a TESScut cutout per sector (network);
* the photometric aperture per sector, so the flux of every neighbour inside
  it can be computed: the SPOC optimal aperture when the light curve came
  from SPOC (``aperture="spoc"`` / ``"auto"``), otherwise a circular aperture
  of the radius :func:`tesshunter.contamination.estimate_aperture_radius_px`
  gives for the target's Tmag, centred on the target's pixel position in the
  cutout (``"circular"``); ``"default"`` is TRICERATOPS's own 5x5 box;
* the phase-folded, detrended light curve around the transit, the period
  and the on-target transit depth (``dilution_corrected=True`` because
  PDCSAP / QLP fluxes are already corrected for known neighbours).

Outputs are cached under ``data/cache/fpp/tic<id>/P<period>/`` as
``probs.csv`` (every scenario row TRICERATOPS evaluated), ``stars.csv`` (the
neighbour table with the flux ratios and required depths) and
``result.json``. The cache key includes the period, depth, sector list and
the sampling settings, so a changed input reruns.

FPP above :data:`FPP_MAX_FOR_PACKET` (0.5) means the candidate does not
proceed to a packet; that rule is applied by the caller.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from .config import CACHE_DIR

logger = logging.getLogger(__name__)

FPP_CACHE_DIR = CACHE_DIR / "fpp"

#: A candidate with FPP above this does not get a packet (prompt 3, part B).
FPP_MAX_FOR_PACKET = 0.5

#: NFPP above this is the TRICERATOPS "likely nearby false positive" regime
#: (Giacalone et al. 2021 use NFPP < 1e-3 together with FPP < 0.015 for a
#: statistical validation; here it only annotates).
NFPP_LIKELY_NFP = 0.1

DEFAULT_N_DRAWS = 200_000
DEFAULT_NSAMPLES = 20
DEFAULT_SEARCH_RADIUS_PX = 10
MAX_SECTORS = 3


@dataclass
class FPPResult:
    available: bool = False
    fpp: Optional[float] = None
    nfpp: Optional[float] = None
    tic_id: Optional[int] = None
    sectors: list = field(default_factory=list)
    n_stars: int = 0
    n_scenarios: int = 0
    aperture_source: str = ""
    aperture_radius_px: Optional[float] = None
    depth_frac_used: float = 0.0
    period_used: float = 0.0
    n_points_used: int = 0
    window_days: float = 0.0
    top_scenarios: list = field(default_factory=list)
    scenario_totals: dict = field(default_factory=dict)
    probs_path: str = ""
    stars_path: str = ""
    result_path: str = ""
    settings: dict = field(default_factory=dict)
    versions: dict = field(default_factory=dict)
    seconds: float = 0.0
    cached: bool = False
    note: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def blocks_packet(self) -> bool:
        return bool(self.available and self.fpp is not None and self.fpp > FPP_MAX_FOR_PACKET)


#: Wall-clock limit for TRICERATOPS's Gaia DR3 field-star query, which has no
#: timeout of its own: eight adversarial workers sat on open connections to
#: the ESA archive for six hours after the disk filled up. The query runs in
#: a child process that is killed at the limit; the blended-star scenarios
#: are then skipped (TRICERATOPS's own behaviour when the query returns
#: nothing) and the result says so.
GAIA_BACKGROUND_TIMEOUT_S = 240.0

_GAIA_BG_SCRIPT = r"""
import os, sys, json
ra, dec, tic, out_dir = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
os.chdir(out_dir)
import socket
socket.setdefaulttimeout(120.0)
from triceratops.funcs import query_gaia_background
fname = query_gaia_background(ra, dec, tic, verbose=0)
print(json.dumps({"fname": fname}))
"""


def _gaia_background_with_timeout(ra: float, dec: float, tic_id: int, bg_dir: Path,
                                  timeout_s: float = GAIA_BACKGROUND_TIMEOUT_S) -> tuple[Optional[Path], str]:
    """Run TRICERATOPS's Gaia query in a child process under a hard timeout.

    Returns (path to the background CSV or None, note)."""
    import subprocess
    import sys

    target = bg_dir / f"{int(tic_id)}_gaia_background.csv"
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _GAIA_BG_SCRIPT, str(ra), str(dec), str(int(tic_id)), str(bg_dir)],
            capture_output=True, text=True, timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return None, f"Gaia background query exceeded {timeout_s:.0f} s and was killed"
    except Exception as exc:                                      # pragma: no cover
        return None, f"Gaia background query could not be started ({exc})"
    if target.exists() and target.stat().st_size > 0:
        return target, "Gaia background queried"
    tail = (proc.stdout or "")[-200:] + (proc.stderr or "")[-300:]
    return None, f"Gaia background query returned nothing ({tail.strip()[:200]})"


def _sectors_with_cutouts(tic_id: int, sectors: list, ra: Optional[float], dec: Optional[float],
                          n_pix: int) -> tuple[list, list]:
    """Download (or find cached) the TESScut cutouts TRICERATOPS will ask for
    and return (usable sectors, dropped sectors)."""
    import warnings
    try:
        import lightkurve
        from astropy.coordinates import SkyCoord
    except Exception:                                             # pragma: no cover
        return list(sectors), []
    if ra is None or dec is None:
        from .stellar import fetch_tic_params
        sp = fetch_tic_params(int(tic_id))
        if sp is None or sp.ra is None:
            return list(sectors), []
        ra, dec = sp.ra, sp.dec
    coord = SkyCoord(float(ra), float(dec), unit="deg")
    ok, dropped = [], []
    for s in sectors:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = lightkurve.search_tesscut(target=coord, sector=int(s))
                if len(res) == 0:
                    dropped.append(int(s))
                    continue
                got = res.download_all(cutout_size=(n_pix, n_pix))
            if got is None or len(got) == 0:
                dropped.append(int(s))
            else:
                ok.append(int(s))
        except Exception as exc:
            logger.info("TESScut unavailable for TIC %s sector %s: %s", tic_id, s, exc)
            dropped.append(int(s))
    return ok, dropped


class _working_directory:
    """Temporarily change the working directory (TRICERATOPS writes to cwd)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.prev: Optional[str] = None

    def __enter__(self):
        import os
        self.prev = os.getcwd()
        os.chdir(self.path)
        return self

    def __exit__(self, *exc):
        import os
        if self.prev is not None:
            os.chdir(self.prev)
        return False


def _versions() -> dict:
    out = {}
    for name in ("triceratops", "pytransit", "lightkurve", "astroquery"):
        try:
            from importlib.metadata import version
            out[name] = str(version(name))
        except Exception:
            try:
                mod = __import__(name)
                out[name] = str(getattr(mod, "__version__", "unknown"))
            except Exception:
                out[name] = "unavailable"
    return out


def circular_aperture(center_col: float, center_row: float, radius_px: float) -> np.ndarray:
    """[[col, row], ...] of every pixel whose centre lies within ``radius_px``."""
    c0, r0 = float(center_col), float(center_row)
    r = max(float(radius_px), 1.0)
    cols = np.arange(math.floor(c0 - r) - 1, math.ceil(c0 + r) + 2)
    rows = np.arange(math.floor(r0 - r) - 1, math.ceil(r0 + r) + 2)
    cc, rr = np.meshgrid(cols, rows)
    keep = (cc - c0) ** 2 + (rr - r0) ** 2 <= r ** 2
    return np.column_stack([cc[keep], rr[keep]]).astype(float)


def fold_for_triceratops(
    time: np.ndarray,
    flux: np.ndarray,
    period: float,
    t0: float,
    duration: float,
    window_durations: float = 3.0,
    max_points: int = 6000,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Phase-fold to days from mid-transit and keep a window around it.

    At most ``max_points`` cadences are kept (random sub-sample): TRICERATOPS
    evaluates every scenario model on every point, and 6000 points across
    +/- 3 durations sample the transit far better than it needs (measured:
    calc_probs with 100 000 draws takes 50 s on 3000 points, 290 s on
    20 000).
    """
    t = np.asarray(time, dtype=float)
    f = np.asarray(flux, dtype=float)
    ok = np.isfinite(t) & np.isfinite(f)
    t, f = t[ok], f[ok]
    ph = ((t - t0 + 0.5 * period) % period) - 0.5 * period
    half = min(window_durations * max(duration, 1e-3), 0.45 * period)
    sel = np.abs(ph) <= half
    ph, f = ph[sel], f[sel]
    if ph.size > max_points:
        rng = np.random.default_rng(seed)
        keep = rng.choice(ph.size, size=max_points, replace=False)
        ph, f = ph[keep], f[keep]
    order = np.argsort(ph)
    return ph[order], f[order]


def bin_fold(
    phase_days: np.ndarray,
    flux: np.ndarray,
    duration: float,
    exp_time_days: float,
    bins_per_duration: int = 25,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Bin a folded curve in phase and measure its error empirically.

    Bin width is the larger of the cadence and ``duration / bins_per_duration``.
    Returns (bin centres, bin means, per-bin error, bin width). The error is
    the robust scatter of the binned points outside +/- 0.75 durations,
    which is the noise at the bin timescale including whatever red noise is
    there; this is the input TRICERATOPS was designed for (a binned folded
    curve with an error estimated from its own out-of-transit scatter).
    """
    w = max(float(exp_time_days), float(duration) / float(bins_per_duration))
    ph = np.asarray(phase_days, dtype=float)
    fl = np.asarray(flux, dtype=float)
    if ph.size == 0:
        return ph, fl, float("nan"), w
    edges = np.arange(ph.min(), ph.max() + w, w)
    idx = np.clip(np.digitize(ph, edges) - 1, 0, edges.size - 2)
    n = np.bincount(idx, minlength=edges.size - 1)
    s = np.bincount(idx, weights=fl, minlength=edges.size - 1)
    st = np.bincount(idx, weights=ph, minlength=edges.size - 1)
    keep = n >= 2
    bx = st[keep] / n[keep]
    by = s[keep] / n[keep]
    oot = np.abs(bx) > 0.75 * duration
    ref = by[oot] if oot.sum() >= 8 else by
    err = 1.4826 * float(np.median(np.abs(ref - np.median(ref))))
    if not np.isfinite(err) or err <= 0:
        err = float(np.std(ref)) if ref.size > 1 else 1e-4
    return bx, by, err, w


def _cache_key(tic_id: int, period: float, depth_frac: float, sectors: list, settings: dict) -> str:
    payload = json.dumps({"tic": int(tic_id), "P": round(float(period), 5),
                          "depth": round(float(depth_frac), 7), "sectors": [int(s) for s in sectors],
                          "settings": settings}, sort_keys=True)
    return hashlib.sha1(payload.encode()).hexdigest()[:10]


def run_fpp(
    tic_id: int,
    sectors: list,
    time_days: np.ndarray,
    flux: np.ndarray,
    flux_err: Optional[np.ndarray],
    *,
    period: float,
    t0: float,
    duration: float,
    depth_frac: float,
    exp_time_days: float,
    tmag: Optional[float] = None,
    aperture: str = "auto",
    author: Optional[str] = None,
    n_draws: int = DEFAULT_N_DRAWS,
    nsamples: int = DEFAULT_NSAMPLES,
    search_radius_px: int = DEFAULT_SEARCH_RADIUS_PX,
    flatpriors: bool = False,
    drop_scenario: Optional[list] = None,
    seed: int = 20260902,
    cache_dir: Optional[Path] = None,
    force: bool = False,
    lightkurve_cache_dir: Optional[str] = None,
    mission: str = "TESS",
    red_noise_beta: Optional[float] = None,
    ra: Optional[float] = None,
    dec: Optional[float] = None,
    fold_mode: str = "binned",
    bins_per_duration: int = 25,
    input_fingerprint: Optional[str] = None,
) -> FPPResult:
    """Compute FPP and NFPP for one candidate. Never raises.

    ``aperture``: ``"auto"`` uses the SPOC optimal aperture when ``author``
    is SPOC (and falls back to circular where a sector has none),
    ``"spoc"`` requires it, ``"circular"`` uses a Tmag-sized circle,
    ``"default"`` uses TRICERATOPS's 5x5 box.

    ``red_noise_beta`` (the transit fit's Winn beta) multiplies the per-point
    error handed to TRICERATOPS, which assumes white noise: with white-noise
    errors on a red-noise-dominated bright star every scenario's chi-square
    is inflated by beta^2 and the likelihood ratios explode, so one scenario
    takes probability 1.0 (WASP-76 b came out PEB = 1.0, TOI-836 c
    BEBx2P = 1.0 with beta 4.4 and 4.9).

    ``input_fingerprint`` optionally identifies the caller's complete measurement
    inputs in the result cache key. Omission preserves the legacy cache key.
    """
    res = FPPResult(tic_id=int(tic_id), period_used=float(period), depth_frac_used=float(depth_frac))
    if fold_mode not in ("binned", "subsample"):
        res.error = f"unknown fold_mode {fold_mode!r}"
        return res
    # beta only applies to the sub-sampled mode; the binned mode measures its
    # error from the binned out-of-transit scatter, which already holds the
    # red noise at the bin timescale.
    beta = float(np.clip(red_noise_beta if (red_noise_beta and fold_mode == "subsample") else 1.0, 1.0, 10.0))
    settings = {"n_draws": int(n_draws), "nsamples": int(nsamples), "search_radius_px": int(search_radius_px),
                "flatpriors": bool(flatpriors), "drop_scenario": list(drop_scenario or []),
                "seed": int(seed), "aperture": aperture, "exp_time_days": float(exp_time_days),
                "window_durations": 3.0, "mission": mission, "red_noise_beta": round(beta, 3),
                "fold_mode": fold_mode, "bins_per_duration": int(bins_per_duration)}
    if input_fingerprint is not None:
        settings["input_fingerprint"] = str(input_fingerprint)
    res.settings = settings
    res.versions = _versions()
    sectors = [int(s) for s in list(sectors)[:MAX_SECTORS]]
    res.sectors = sectors
    if not sectors:
        res.error = "no sectors supplied"
        return res
    if not (period > 0 and 0 < depth_frac < 1):
        res.error = "invalid period or depth"
        return res

    key = _cache_key(tic_id, period, depth_frac, sectors, settings)
    out_dir = (Path(cache_dir) if cache_dir else FPP_CACHE_DIR) / f"tic{int(tic_id)}" / f"P{period:.4f}_{key}"
    result_path = out_dir / "result.json"
    if result_path.exists() and not force:
        try:
            cached = json.loads(result_path.read_text(encoding="utf-8"))
            if cached.get("available"):
                r = FPPResult(**{k: v for k, v in cached.items() if k in FPPResult.__dataclass_fields__})
                r.cached = True
                return r
            # A cached FAILURE (network timeout, missing cutout) is never
            # served; the call is repeated.
        except Exception as exc:                                  # pragma: no cover
            logger.warning("FPP cache unreadable (%s); recomputing", exc)

    t_start = time.perf_counter()
    try:
        import socket
        import warnings
        from triceratops import triceratops as tr

        # Second layer against network hangs (TESScut, TIC): every new socket
        # in this process gets a read timeout unless the caller set one.
        if socket.getdefaulttimeout() is None:
            socket.setdefaulttimeout(300.0)

        if fold_mode == "binned":
            ph_all, fl_all = fold_for_triceratops(time_days, flux, period, t0, duration,
                                                  settings["window_durations"], max_points=10 ** 9)
            if ph_all.size < 30:
                res.error = f"only {ph_all.size} cadences in the transit window"
                return res
            ph, fl, sig, bin_w = bin_fold(ph_all, fl_all, duration, exp_time_days, bins_per_duration)
            if ph.size < 20:
                # Coarse cadence (30-minute FFI products on a short transit):
                # binning leaves too few points, so hand over the raw fold.
                ph, fl = fold_for_triceratops(time_days, flux, period, t0, duration,
                                              settings["window_durations"])
                if ph.size < 20:
                    res.error = f"only {ph.size} cadences in the transit window"
                    return res
                oot = np.abs(ph) > 0.75 * duration
                ref = fl[oot] if oot.sum() >= 10 else fl
                sig = 1.4826 * float(np.median(np.abs(ref - np.median(ref)))) or float(np.std(ref))
                exptime_for_tr = float(exp_time_days)
                res.settings["fold_mode_used"] = "subsample (binned fold had too few bins)"
            else:
                exptime_for_tr = float(bin_w)
                res.settings["bin_width_days"] = float(bin_w)
                res.settings["fold_mode_used"] = "binned"
            res.settings["n_cadences_folded"] = int(ph_all.size)
        else:
            ph, fl = fold_for_triceratops(time_days, flux, period, t0, duration, settings["window_durations"])
            if ph.size < 30:
                res.error = f"only {ph.size} cadences in the transit window"
                return res
            if flux_err is not None:
                e = np.asarray(flux_err, dtype=float)
                e = e[np.isfinite(e) & (e > 0)]
                sig = float(np.median(e)) if e.size else float("nan")
            else:
                sig = float("nan")
            oot = np.abs(ph) > 0.75 * duration
            ref = fl[oot] if oot.sum() >= 10 else fl
            sig_robust = 1.4826 * float(np.median(np.abs(ref - np.median(ref))))
            if not np.isfinite(sig) or sig <= 0 or sig < 0.3 * sig_robust:
                sig = sig_robust if sig_robust > 0 else float(np.std(ref))
            sig = float(sig * beta)
            exptime_for_tr = float(exp_time_days)
        res.settings["flux_err_used"] = float(sig)
        res.n_points_used = int(ph.size)
        res.window_days = float(ph.max() - ph.min())

        # TRICERATOPS writes the Gaia field-star population it queries to
        # "<ID>_gaia_background.csv" in the CURRENT DIRECTORY and re-reads it in
        # calc_probs. Keep those files under the FPP cache (one per star) and
        # hand a cached one back so the Gaia TAP is queried once per star.
        bg_dir = (Path(cache_dir) if cache_dir else FPP_CACHE_DIR) / "gaia_background"
        bg_dir.mkdir(parents=True, exist_ok=True)
        bg_file = bg_dir / f"{int(tic_id)}_gaia_background.csv"

        # TRICERATOPS drops a sector whose TESScut download fails WITHOUT
        # recording which one, so its per-sector pixel coordinates no longer
        # line up with the aperture list (KELT-11: IndexError in calc_depths
        # after one of three cutouts failed). Fetch the cutouts first (same
        # lightkurve cache, same size, so TRICERATOPS then reads them from
        # disk) and keep only the sectors that are actually available.
        if mission == "TESS":
            sectors, dropped = _sectors_with_cutouts(int(tic_id), sectors, ra, dec, 2 * search_radius_px + 2)
            res.sectors = sectors
            if dropped:
                res.note = f"sectors without a usable TESScut cutout dropped: {dropped}. "
            if not sectors:
                res.error = f"no TESScut cutout could be obtained (tried {dropped})"
                return res

        # Gaia field-star population: cached file, else a child process under a
        # hard timeout; when that fails TRICERATOPS's own query is replaced by
        # one returning None so the blended scenarios are skipped, not hung.
        bg_note = "Gaia background cached"
        if not bg_file.exists() and mission == "TESS":
            ra_q, dec_q = ra, dec
            if ra_q is None or dec_q is None:
                from .stellar import fetch_tic_params
                sp_q = fetch_tic_params(int(tic_id))
                if sp_q is not None:
                    ra_q, dec_q = sp_q.ra, sp_q.dec
            if ra_q is not None and dec_q is not None:
                _p, bg_note = _gaia_background_with_timeout(ra_q, dec_q, int(tic_id), bg_dir)
        res.settings["gaia_background"] = bg_note
        patched = None
        if not bg_file.exists() and hasattr(tr, "query_gaia_background"):
            patched = tr.query_gaia_background
            tr.query_gaia_background = lambda *a, **k: None
        try:
            with warnings.catch_warnings(), _working_directory(bg_dir):
                warnings.simplefilter("ignore")
                target = tr.target(ID=int(tic_id), sectors=np.asarray(sectors), search_radius=search_radius_px,
                                   mission=mission, lightkurve_cache_dir=lightkurve_cache_dir,
                                   trilegal_fname=(str(bg_file) if bg_file.exists() else None))
        finally:
            if patched is not None:
                tr.query_gaia_background = patched
        if not bg_file.exists():
            res.note = (res.note or "") + f"No Gaia field-star population ({bg_note}); blended scenarios skipped. "
        res.n_stars = int(len(target.stars))
        if len(target.pix_coords) != len(sectors):
            res.error = (
                f"TRICERATOPS kept {len(target.pix_coords)} of {len(sectors)} sectors after the "
                f"cutout pre-check; aperture mapping would be ambiguous"
            )
            return res
        res.settings["gaia_background_file"] = (
            str(bg_file) if bg_file.exists() else str(getattr(target, "trilegal_fname", None))
        )

        # Apertures
        aps: list = [None] * len(sectors)
        source = ""
        want_spoc = aperture in ("spoc", "auto") and (aperture == "spoc" or (author or "").upper() == "SPOC")
        if want_spoc:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    aps = list(target.get_spoc_apertures())
                source = "spoc"
            except Exception as exc:
                logger.info("SPOC apertures unavailable for TIC %s: %s", tic_id, exc)
                aps = [None] * len(sectors)
        if aperture == "spoc" and any(a is None for a in aps):
            res.error = "SPOC aperture missing for at least one sector"
            return res
        if aperture != "default":
            from .contamination import estimate_aperture_radius_px
            tm = tmag if tmag is not None else float(target.stars["Tmag"].values[0])
            r_px = float(estimate_aperture_radius_px(tm))
            res.aperture_radius_px = r_px
            filled = 0
            for k in range(len(sectors)):
                if aps[k] is None and k < len(target.pix_coords):
                    col, row = target.pix_coords[k][0]
                    aps[k] = circular_aperture(col, row, r_px)
                    filled += 1
            if filled:
                source = "circular_from_tmag" if source == "" or filled == len(sectors) else "spoc+circular"
        if aperture == "default" or any(a is None for a in aps):
            aps_arg = None
            source = "triceratops_default_5x5"
        else:
            aps_arg = [np.asarray(a) for a in aps]
        res.aperture_source = source

        with warnings.catch_warnings(), _working_directory(bg_dir):
            warnings.simplefilter("ignore")
            target.calc_depths(tdepth=float(depth_frac), all_ap_pixels=aps_arg, dilution_corrected=True)
            np.random.seed(int(seed))
            target.calc_probs(time=ph, flux_0=fl, flux_err_0=float(sig), P_orb=float(period),
                              N=int(n_draws), parallel=False, drop_scenario=list(drop_scenario or []),
                              verbose=0, flatpriors=bool(flatpriors), exptime=float(exptime_for_tr),
                              nsamples=int(nsamples), dilution_corrected=True)

        probs = target.probs.copy()
        stars = target.stars.copy()
        out_dir.mkdir(parents=True, exist_ok=True)
        probs.to_csv(out_dir / "probs.csv", index=False)
        stars.to_csv(out_dir / "stars.csv", index=False)
        res.probs_path = str(out_dir / "probs.csv")
        res.stars_path = str(out_dir / "stars.csv")
        res.fpp = float(target.FPP)
        res.nfpp = float(target.NFPP)
        res.n_scenarios = int(len(probs))
        if "prob" in probs.columns:
            totals = probs.groupby("scenario")["prob"].sum().sort_values(ascending=False)
            res.scenario_totals = {str(k): float(v) for k, v in totals.items()}
            top = probs.sort_values("prob", ascending=False).head(8)
            res.top_scenarios = [
                {"scenario": str(r["scenario"]), "ID": int(r["ID"]), "prob": float(r["prob"])}
                for _, r in top.iterrows()
            ]
        res.available = True
        res.note = (res.note or "") + (
            f"TRICERATOPS {res.versions.get('triceratops')}: FPP {res.fpp:.4f}, NFPP {res.nfpp:.4f} "
            f"over {res.n_scenarios} scenarios and {res.n_stars} TIC stars within {search_radius_px} px; "
            f"aperture {source}; {n_draws} draws; fold {fold_mode} ({res.n_points_used} points, "
            f"error {sig * 1e6:.0f} ppm{', x beta ' + format(beta, '.2f') if beta > 1 else ''}); sectors {sectors}."
        )
    except Exception as exc:
        import traceback
        res.error = f"{type(exc).__name__}: {exc}"
        logger.warning("TRICERATOPS failed for TIC %s: %s\n%s", tic_id, exc, traceback.format_exc())
    res.seconds = time.perf_counter() - t_start
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        res.result_path = str(result_path)
        result_path.write_text(json.dumps(res.to_dict(), indent=1), encoding="utf-8")
    except Exception as exc:                                      # pragma: no cover
        logger.warning("could not write FPP result: %s", exc)
    return res
