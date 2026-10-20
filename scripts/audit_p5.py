"""Prompt 5: independent audit of the top survey candidates.

Prompt 7 moved the rules this script established into the package: the
preprocessing is ``tesshunter.audit_prep``, the per-event examination and the
removal rules are ``tesshunter.event_vet``, the star-level tests are
``tesshunter.star_vet``, the full-phase secondary scan is
``tesshunter.secondary``, and every threshold is named once in
``tesshunter.audit_rules``.  What remains here is the driver: the MAST
downloads, the private lightkurve cache, the TLS calls, the file layout and the
CLI.  The rules are unchanged and still share no code with the survey
pipeline's own light-curve path; ``scripts/p7_reproduce.py`` re-derives every
P5 and P6 record through this file to prove it.

The rule set defaults to ``audit_rules.LEGACY_RULES`` (``p6.2``) - exactly what
prompts 5 and 6 applied - so these records reproduce.  ``--rules p7.0`` selects
the prompt-7 default set, with the four measured options on.

Sub-commands (each writes JSON under the output root, ``--out-root``, default
``data/survey/p5``; the raw per-product arrays live in the shared ``--lc-root``,
default ``data/survey/audit_lc``, because they are downloaded data, not results):

    download   --tic ID [...]        fresh-cache download of SPOC / TESS-SPOC / QLP products
    prepare    --tic ID --period P   wotan detrend + 30-min bins + the documented clips -> <key>_lc.npz
    tls        --tic ID --period P   blind TLS (0.5-110 d) and a forced narrow TLS at P
    forced     --tic ID --period P   the forced narrow TLS alone (a whole-baseline ephemeris, not a detection)
    events     --tic ID --period P   per-event SAP examination, depth consistency, SNR without bad events
    neighbours --tic ID              Gaia DR3 (1 arcmin, RUWE, variability), SIMBAD, VSX, dilution
    crossmatch --tic ID [...]        hard stop with freshly downloaded catalogs
    report                           assemble <out-root>/audit_summary.json

Nothing here submits anything anywhere.  The pipeline finds candidates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import socket
import sys
import time
import warnings
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from tesshunter import audit_rules as R          # noqa: E402
from tesshunter.audit_prep import (              # noqa: E402
    bin_lc,
    detrend_window_days,
    expected_t14_hours,
    prepare_series,
    product_bitmask,
    transit_mask,
)
from tesshunter.event_vet import (               # noqa: E402
    event_table,
    sector_beta,
    summarise_events,
    weighted_mean,
)

AUDIT_CACHE = REPO / "data" / "cache" / "audit_lightkurve"
DEFAULT_LC_ROOT = REPO / "data" / "survey" / "audit_lc"
OUT = REPO / "data" / "survey" / "p5"
LC_DIR = DEFAULT_LC_ROOT
INPUT_CONFIG = None  # P5-P7 retain their original product selection and 30-minute TLS bins.
AUDIT_CACHE.mkdir(parents=True, exist_ok=True)


def set_input_config(config=None) -> None:
    """Use a survey's sector/cadence selection throughout the audit; None restores P5-P7."""
    global INPUT_CONFIG
    INPUT_CONFIG = config


def input_config() -> dict | None:
    return input_config_for(INPUT_CONFIG)


def input_config_for(config) -> dict | None:
    if config is None:
        return None
    return {"ingest_key": config.ingest_key(), "sector_min": config.sector_min,
            "target_cadence_minutes": config.target_cadence_minutes,
            "bin_minutes": config.bin_minutes, "audit_input_version": 1}


def cache_matches(record: dict) -> bool:
    return record.get("rules_version") == RULES_VERSION and record.get("input_config") == input_config()


def _abs(root) -> Path:
    root = Path(root)
    return root if root.is_absolute() else REPO / root


def set_roots(out_root=None, lc_root=None) -> None:
    """Set the output root (per prompt: ``data/survey/p5``, ``data/survey/p6``, ...) and the
    raw light-curve store, which is SHARED between prompts because it is downloaded data,
    not a result (default ``data/survey/audit_lc``)."""
    global OUT, LC_DIR
    if out_root is not None:
        OUT = _abs(out_root)
    LC_DIR = _abs(lc_root) if lc_root is not None else DEFAULT_LC_ROOT
    LC_DIR.mkdir(parents=True, exist_ok=True)
    for _sub in ("tls", "events", "neighbours", "crossmatch", "prep", "fit"):
        (OUT / _sub).mkdir(parents=True, exist_ok=True)


set_roots()
# A cache of our own, so nothing the survey downloaded is reused.
os.environ["LIGHTKURVE_CACHE"] = str(AUDIT_CACHE)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
warnings.filterwarnings("ignore")
socket.setdefaulttimeout(300.0)

BTJD_OFFSET = 2457000.0
AUTHORS = ("SPOC", "TESS-SPOC", "QLP")
# TESS quality bits and the pixel scale now live in tesshunter.audit_rules; these names are kept
# so that anything importing this module (and the notebooks) still resolves them.
PIXEL_ARCSEC = R.PIXEL_ARCSEC
Q_DESAT = R.Q_DESAT
Q_MANUAL = R.Q_MANUAL
Q_STRAYLIGHT = R.Q_STRAYLIGHT
Q_DEFAULT = R.Q_DEFAULT
Q_HARD = R.Q_HARD
QLP_LOW_PRECISION_S1_55 = R.QLP_LOW_PRECISION_S1_55
QLP_LOW_PRECISION_S56 = R.QLP_LOW_PRECISION_S56

# Which optional rules are on.  LEGACY_RULES ("p6.2") is exactly what prompts 5 and 6 applied and
# is the default, so every record this script wrote then still reproduces; `set_rules` switches it.
RULES = R.LEGACY_RULES
# Stamped into every JSON this script writes, so that a mixed-vintage directory is detectable.
# "p5" is the code as it audited the frozen top ten in prompt 5; "p6.1" adds the `prepare` and
# `forced` split and the Stage A-D drivers of prompt 6, and "p6.2" makes a degenerate TLS result
# (NaN transit counts, which one narrow search returned) serialise as null instead of raising.
# None of those changed a rule or a threshold; every prompt-6 record is stamped "p6.2".  "p7.0" is
# the prompt-7 set with the four measured options on.
RULES_VERSION = RULES.version


def set_rules(rules) -> None:
    """Select the rule set (a ``tesshunter.audit_rules.RuleSet`` or its version string)."""
    global RULES, RULES_VERSION
    if isinstance(rules, str):
        rules = R.NAMED_RULES[rules]
        if rules is None:
            raise SystemExit("p8.0 is not decided yet (audit_rules.P8_RULES is None)")
    RULES = rules
    RULES_VERSION = rules.version


def jdump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def conv(o):
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)

    if INPUT_CONFIG is not None and isinstance(obj, dict):
        obj = dict(obj, input_config=input_config())
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(obj, indent=1, default=conv), encoding="utf-8")
    temporary.replace(path)


def jload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def finite_fields(value):
    """Use JSON null for unavailable fit/packet numbers, rather than non-standard NaN tokens."""
    if isinstance(value, dict):
        return {k: finite_fields(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_fields(v) for v in value]
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return None
    return value


def key(tic: int, period: float) -> str:
    return f"tic{int(tic)}_P{float(period):.4f}"


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# The candidate table and the packet directory this driver reads.  The defaults are the
# prompt-4 files, so prompts 5-7 reproduce; prompt 8 points them at its own tables through
# ``set_population``.
SURVIVORS_CSV = REPO / "data" / "survey" / "p4" / "survivors.csv"
PACKETS_DIR = REPO / "docs" / "packets" / "survey_v1"


def set_population(survivors_csv=None, packets_dir=None) -> None:
    """Point the driver at another candidate table / packet directory (prompt 8)."""
    global SURVIVORS_CSV, PACKETS_DIR
    if survivors_csv is not None:
        SURVIVORS_CSV = _abs(survivors_csv)
    if packets_dir is not None:
        PACKETS_DIR = _abs(packets_dir)


def survivor_row(tic: int, period: float) -> dict:
    """The survivor row (frozen P4 ranking, or the prompt-8 table) for this candidate, or {}."""
    import csv
    rows = list(csv.DictReader(open(SURVIVORS_CSV, newline="", encoding="utf-8")))
    best, bestd = {}, 1e9
    for r in rows:
        if int(r["tic_id"]) != int(tic):
            continue
        d = abs(float(r["period_days"]) - period)
        if d < bestd:
            best, bestd = r, d
    return best if bestd < 0.05 * period else {}


def stellar_from_cache(tic: int) -> dict:
    p = REPO / "data" / "cache" / "tic" / f"tic{int(tic)}.json"
    return jload(p) if p.exists() else {}


# ─────────────────────────────────────────────────────────────────────────────
# download: every SPOC / TESS-SPOC / QLP light curve, all cadences kept
# ─────────────────────────────────────────────────────────────────────────────
def _col(lc, name):
    try:
        v = lc[name]
    except Exception:
        return None
    try:
        v = np.asarray(v.value if hasattr(v, "value") else v, dtype=float)
    except Exception:
        return None
    return v


def download(tic: int, force: bool = False, sector_min: int | None = None) -> dict:
    """One ``search_lightcurve`` per star, then every SPOC 2-min / TESS-SPOC / QLP product.

    ``sector_min`` (prompt 8) skips products from earlier sectors; the index records it so
    a store entry built with a cut is never mistaken for a complete one.  ``None`` is the
    prompt-5/6 behaviour (every sector)."""
    import lightkurve as lk
    tdir = LC_DIR / f"tic{tic}"
    tdir.mkdir(parents=True, exist_ok=True)
    index_path = tdir / "index.json"
    if index_path.exists() and not force:
        return jload(index_path)
    t0 = time.perf_counter()
    sr = lk.search_lightcurve(f"TIC {tic}", mission="TESS")
    rows = []
    n_skipped_sector = 0
    for i in range(len(sr)):
        author = str(sr.author[i])
        if author not in AUTHORS:
            continue
        exptime = float(sr.exptime[i].value) if hasattr(sr.exptime[i], "value") else float(sr.exptime[i])
        if author == "SPOC" and abs(exptime - 120.0) > 5:
            continue                      # 20-s products duplicate the 2-min ones
        sec_i = int(sr.mission[i].split()[-1]) if "Sector" in str(sr.mission[i]) else -1
        if sector_min is not None and 0 <= sec_i < sector_min:
            n_skipped_sector += 1
            continue
        rows.append((i, author, exptime, sec_i))
    products = []
    n_fail = 0
    for i, author, exptime, sector in rows:
        try:
            lc = sr[i].download(quality_bitmask="none", download_dir=str(AUDIT_CACHE))
        except Exception as exc:
            n_fail += 1
            products.append({"author": author, "exptime_s": exptime, "sector": sector, "error": str(exc)[:200]})
            continue
        if lc is None:
            n_fail += 1
            continue
        sector = int(lc.meta.get("SECTOR", sector))
        t = np.asarray(lc.time.value, dtype=float)       # BTJD
        if np.nanmedian(t) > 2_400_000:
            t = t - BTJD_OFFSET
        flux_col = "pdcsap_flux"
        if author == "QLP":
            flux_col = "det_flux" if sector >= 56 else "kspsap_flux"
        flux = _col(lc, flux_col)
        if flux is None:
            flux = np.asarray(lc.flux.value, dtype=float)
            flux_col = "flux"
        ferr = _col(lc, flux_col + "_err")
        if ferr is None:
            ferr = _col(lc, "flux_err")
        sap = _col(lc, "sap_flux")
        sap_err = _col(lc, "sap_flux_err")
        bkg = _col(lc, "sap_bkg")
        q = _col(lc, "quality")
        q = np.zeros_like(t, dtype=int) if q is None else np.nan_to_num(q).astype(int)
        cad = float(np.nanmedian(np.diff(t))) * 86400.0
        name = f"s{sector:03d}_{author.replace('-', '')}.npz"
        np.savez_compressed(
            tdir / name, time=t, flux=flux, flux_err=np.full_like(t, np.nan) if ferr is None else ferr,
            sap_flux=np.full_like(t, np.nan) if sap is None else sap,
            sap_flux_err=np.full_like(t, np.nan) if sap_err is None else sap_err,
            sap_bkg=np.full_like(t, np.nan) if bkg is None else bkg, quality=q,
        )
        products.append({
            "file": name, "author": author, "exptime_s": exptime, "cadence_s": round(cad, 1), "sector": sector,
            "n": int(len(t)), "flux_column": flux_col, "t_start": float(np.nanmin(t)), "t_end": float(np.nanmax(t)),
            "camera": int(lc.meta.get("CAMERA", -1) or -1), "ccd": int(lc.meta.get("CCD", -1) or -1),
            "n_quality_nonzero": int(np.count_nonzero(q)), "n_desat": int(np.count_nonzero(q & Q_DESAT)),
        })
    index = {"tic_id": tic, "downloaded_utc": utc(), "cache": str(AUDIT_CACHE), "search_rows": int(len(sr)),
             "n_products": len([p for p in products if "file" in p]), "n_failed": n_fail,
             "seconds": round(time.perf_counter() - t0, 1), "products": products}
    if sector_min is not None:
        index["sector_min"] = int(sector_min)
        index["n_products_skipped_below_sector_min"] = int(n_skipped_sector)
    jdump(index_path, index)
    return index


def load_products(tic: int) -> list[dict]:
    idx = jload(LC_DIR / f"tic{tic}" / "index.json")
    out = []
    for p in idx["products"]:
        if "file" not in p:
            continue
        if INPUT_CONFIG is not None and INPUT_CONFIG.sector_min is not None and int(p["sector"]) < INPUT_CONFIG.sector_min:
            continue
        d = dict(np.load(LC_DIR / f"tic{tic}" / p["file"]))
        d.update(p)
        out.append(d)
    return out


def choose_per_sector(products: list[dict]) -> list[dict]:
    """One product per sector: SPOC 2-min, else TESS-SPOC, else QLP."""
    pref = {"SPOC": 0, "TESS-SPOC": 1, "QLP": 2}
    best: dict[int, dict] = {}
    for p in products:
        s = p["sector"]
        if INPUT_CONFIG is not None and INPUT_CONFIG.sector_min is not None and int(s) < INPUT_CONFIG.sector_min:
            continue
        if s not in best or pref[p["author"]] < pref[best[s]["author"]]:
            best[s] = p
    selected = [best[s] for s in sorted(best)]
    if INPUT_CONFIG is not None:
        from tesshunter.survey_p8 import harmonise_cadence
        selected, _ = harmonise_cadence(selected, INPUT_CONFIG.target_cadence_minutes)
    return selected


# ─────────────────────────────────────────────────────────────────────────────
# detrend + TLS
# ─────────────────────────────────────────────────────────────────────────────
# expected_t14_hours, product_bitmask, clean_and_detrend and bin_lc are now
# tesshunter.audit_prep (imported above): the same code, with every threshold named once in
# tesshunter.audit_rules.  They are re-exported here because the notebooks and the P5/P6
# drivers import them from this module.


def run_tls(t, f, e, pmin, pmax, rstar, mstar, oversampling, threads, duration_grid_step=1.1):
    from transitleastsquares import transitleastsquares
    model = transitleastsquares(t, f, e)
    kw = dict(period_min=pmin, period_max=pmax, oversampling_factor=oversampling, duration_grid_step=duration_grid_step,
              use_threads=threads, show_progress_bar=False, R_star=rstar, M_star=mstar,
              R_star_min=max(0.1, 0.5 * rstar), R_star_max=2.0 * rstar, M_star_min=max(0.08, 0.5 * mstar),
              M_star_max=2.0 * mstar, T0_fit_margin=0.01)
    if INPUT_CONFIG is None:
        return model.power(**kw)
    # Native arrays make repeated phase sorting expensive. The equivalent TLS 1.32
    # epoch scan preserves its trial grid, arithmetic and tie rule; legacy calls
    # keep the upstream function, including the P5-P7 reproduction experiment.
    from tesshunter.tls_epoch import equivalent_epoch_scan
    with equivalent_epoch_scan():
        return model.power(**kw)


def _tls_summary(r) -> dict:
    def i_(x):
        """int(), except that TLS's NaN counts (a degenerate search that fits no transit) become None."""
        try:
            v = float(x)
        except (TypeError, ValueError):
            return None
        return None if not np.isfinite(v) else int(v)

    def f_(x):
        try:
            v = float(x)
        except (TypeError, ValueError):
            return None
        return None if not np.isfinite(v) else v

    def arr(x):
        try:
            return [None if (v is None or (isinstance(v, float) and not np.isfinite(v))) else float(v) for v in np.atleast_1d(x)]
        except Exception:
            return None
    return {
        "period": f_(r.period), "period_uncertainty": f_(r.period_uncertainty), "T0_btjd": f_(r.T0),
        "duration_days": f_(r.duration), "depth": f_(r.depth), "SDE": f_(r.SDE), "snr": f_(r.snr),
        "FAP": None if r.FAP is None or not np.isfinite(r.FAP) else float(r.FAP), "rp_rs": f_(r.rp_rs),
        "transit_count": i_(r.transit_count), "distinct_transit_count": i_(r.distinct_transit_count),
        "empty_transit_count": i_(r.empty_transit_count), "odd_even_mismatch": f_(r.odd_even_mismatch),
        "depth_mean_even": arr(r.depth_mean_even), "depth_mean_odd": arr(r.depth_mean_odd),
        "transit_times": arr(r.transit_times), "transit_depths": arr(r.transit_depths),
        "transit_depths_uncertainties": arr(r.transit_depths_uncertainties),
        "per_transit_count": arr(r.per_transit_count), "snr_per_transit": arr(r.snr_per_transit),
        "n_periods": int(len(r.periods)),
    }


def _peak_table(periods, power, n=10, exclude_frac=0.02, min_power=0.0):
    """Top-n distinct peaks of the TLS spectrum (each peak masks +/- exclude_frac around it)."""
    p = np.asarray(periods); w = np.asarray(power).copy()
    out = []
    for _ in range(n):
        i = int(np.nanargmax(w))
        if not np.isfinite(w[i]) or w[i] <= min_power:
            break
        out.append({"period": float(p[i]), "SDE": float(w[i])})
        m = np.abs(p / p[i] - 1) < exclude_frac
        w[m] = -np.inf
    return out


def _floor_tls_summary(summary: dict, times) -> dict:
    """Apply the P10 duration option at the report/consumer boundary; legacy is unchanged."""
    if not RULES.duration_floor_cadence:
        return summary
    from tesshunter.stage_c import duration_summary
    cadence_s = float(np.median(np.diff(np.sort(times)))) * 86400.0 if len(times) > 1 else 200.0
    return duration_summary(summary, cadence_s)


def _match(period_found: float, period_survey: float) -> dict:
    """Within 1%? Also report aliases (2:1, 1:2, 3:1, 1:3)."""
    ratios = {"1:1": 1.0, "2:1": 2.0, "1:2": 0.5, "3:1": 3.0, "1:3": 1 / 3, "3:2": 1.5, "2:3": 2 / 3}
    best = None
    for name, rr in ratios.items():
        frac = abs(period_found / (period_survey * rr) - 1.0)
        if best is None or frac < best["frac"]:
            best = {"alias": name, "frac": frac}
    return {"same_period_1pct": bool(abs(period_found / period_survey - 1.0) < 0.01),
            "closest_alias": best["alias"], "closest_alias_frac": best["frac"],
            "alias_1pct": bool(best["frac"] < 0.01)}


def stellar_for(tic: int, period: float) -> dict:
    """Radius, mass and the central-transit duration at this period (the detrending scale)."""
    st = stellar_from_cache(tic)
    row = survivor_row(tic, period)
    rstar = float(st.get("radius") or row.get("radius_rsun") or 1.0)
    mstar = st.get("mass") or row.get("mass_msun")
    mstar = float(mstar) if mstar not in (None, "", "nan") and np.isfinite(float(mstar)) else rstar
    return {"R_star": rstar, "M_star": mstar, "expected_t14_hours_b0": expected_t14_hours(period, rstar, mstar)}


def prepare_step(tic: int, period: float, bin_minutes: float | None = 30.0, window_days: float | None = None,
                 force: bool = False, mask: list[tuple[float, float]] | None = None, suffix: str = "",
                 detrend_mask_ephemeris: dict | None = None) -> dict:
    """Detrend, bin and clip one candidate's whole baseline; write ``<key><suffix>_lc.npz``.

    This is the input every later step uses: the ``tls`` and ``forced`` searches read the binned
    series from it and ``events`` reads the unbinned detrended series from it, so all of them see
    exactly the same preprocessing.  ``mask``: BTJD ranges removed (documented systematics).
    ``detrend_mask_ephemeris``: the ephemeris whose transits are masked out of the biweight when
    the rule set has ``transit_masked_detrend`` on (prompt-7 option 3); the survey ephemeris is
    used when none is given.  The numerics are ``tesshunter.audit_prep.prepare_series``.
    """
    if INPUT_CONFIG is not None:
        bin_minutes = INPUT_CONFIG.bin_minutes
    lc_path = OUT / "tls" / f"{key(tic, period)}{suffix}_lc.npz"
    meta_path = OUT / "prep" / f"{key(tic, period)}{suffix}.json"
    if lc_path.exists() and meta_path.exists() and not force:
        m = jload(meta_path)
        if cache_matches(m):
            return m
    row = survivor_row(tic, period)
    sp = stellar_for(tic, period)
    rstar, mstar, t14 = sp["R_star"], sp["M_star"], sp["expected_t14_hours_b0"]
    if window_days is None:
        window_days = detrend_window_days(t14)
    products = choose_per_sector(load_products(tic))
    ref_depth = (float(row.get("depth_ppt")) / 1000.0) if row.get("depth_ppt") else 0.0
    # Prompt-7 option 3: fit the biweight with the in-transit cadences masked out of the trend, so
    # the detrend cannot absorb part of the transit.  OFF under LEGACY_RULES, which is the default.
    mask_fn, mask_eph = None, None
    if RULES.transit_masked_detrend:
        mask_eph = detrend_mask_ephemeris if detrend_mask_ephemeris else _ephemeris(tic, period, "survey")
        mask_fn = (lambda tt, _e=mask_eph: transit_mask(tt, _e["period"], _e["t0"], _e["duration"]))
    t0 = time.perf_counter()
    prep = prepare_series(products, window_days, bin_minutes, ref_depth,
                          mask_ranges=mask, mask_fn=mask_fn)
    det, cnt = prep["unbinned"], prep["counters"]
    tb, fb, eb = prep["binned"]["time"], prep["binned"]["flux"], prep["binned"]["flux_err"]
    temporary = lc_path.with_name(f"{lc_path.name}.{os.getpid()}.tmp")
    with open(temporary, "wb") as handle:
        np.savez_compressed(handle, time=tb, flux=fb, flux_err=eb,
                            time_unbinned=det["time"], flux_unbinned=det["flux"], sector_unbinned=det["sector"],
                            trend_unbinned=det["trend"])
    temporary.replace(lc_path)
    meta = {
        "tic_id": tic, "survey_period": period, "generated_utc": utc(), "rules_version": RULES_VERSION,
        "lc_npz": (str(lc_path.relative_to(REPO)) if lc_path.is_relative_to(REPO) else str(lc_path)),
        "products": [{"sector": p_["sector"], "author": p_["author"], "cadence_s": p_["cadence_s"]} for p_ in products],
        "n_unbinned": cnt["n_unbinned"], "n_binned": cnt["n_binned"], "bin_minutes": bin_minutes,
        "wotan": {"method": "biweight", "window_days": window_days, "break_tolerance": 0.5, "edge_cutoff": 0.0},
        "quality_bitmask": "default(17087)", "upward_clip_sigma": 4.0,
        "R_star": rstar, "M_star": mstar, "expected_t14_hours_b0": round(t14, 2),
        "baseline_days": float(tb.max() - tb.min()) if len(tb) else 0.0,
        "mask_btjd_ranges": mask or [], "n_unbinned_masked": cnt["n_unbinned_masked"],
        "n_isolated_clipped": cnt["n_isolated_clipped"],
        "n_isolated_bins_clipped": cnt["n_isolated_bins_clipped"],
        "deep_clip_threshold_ppt": cnt["deep_clip_threshold_ppt"], "n_deep_clipped": cnt["n_deep_clipped"],
        "reference_depth_ppt": round(1000 * ref_depth, 3),
        "per_product": det["per_product"], "seconds": round(time.perf_counter() - t0, 1),
    }
    if mask_fn is not None:
        meta["transit_masked_detrend"] = {"ephemeris": mask_eph, "n_cadences_masked_from_trend":
                                          cnt["n_masked_from_trend"],
                                          "durations_either_side": R.MASK_DURATIONS_EITHER_SIDE}
    jdump(meta_path, meta)
    return meta


def load_prepared(tic: int, period: float, suffix: str = ""):
    """The binned series ``prepare_step`` wrote (time, flux, flux_err)."""
    z = np.load(OUT / "tls" / f"{key(tic, period)}{suffix}_lc.npz")
    return z["time"], z["flux"], z["flux_err"]


def _tls_inputs(prep: dict, pmin: float, pmax: float, oversampling: int) -> dict:
    """The ``inputs`` block of a search record: everything ``prepare`` recorded plus the grid."""
    d = {k: prep[k] for k in ("products", "n_unbinned", "n_binned", "bin_minutes", "wotan", "quality_bitmask",
                              "upward_clip_sigma", "R_star", "M_star", "expected_t14_hours_b0", "baseline_days",
                              "mask_btjd_ranges", "n_unbinned_masked", "n_isolated_clipped",
                              "n_isolated_bins_clipped", "deep_clip_threshold_ppt", "n_deep_clipped")}
    d.update({"period_min": pmin, "period_max": pmax, "oversampling_factor": oversampling,
              "prepare_generated_utc": prep["generated_utc"]})
    return d


def forced_step(tic: int, period: float, threads: int = 20, oversampling: int = 5, half_width: float = 0.015,
                bin_minutes: float = 30.0, window_days: float | None = None, force: bool = False,
                suffix: str = "") -> dict:
    """The narrow TLS around the survey period, on its own: a whole-baseline EPHEMERIS, not a detection.

    Written to ``<key>_forced.json`` with the same ``forced`` block a full ``tls`` record carries, so
    ``_ephemeris(source="tls")`` can read either.
    """
    out_path = OUT / "tls" / f"{key(tic, period)}{suffix}_forced.json"
    if out_path.exists() and not force:
        r = jload(out_path)
        if cache_matches(r):
            if RULES.duration_floor_cadence:
                r["forced"] = _floor_tls_summary(r["forced"], load_prepared(tic, period, suffix)[0])
            return r
    prep = prepare_step(tic, period, bin_minutes, window_days, force=False, suffix=suffix)
    tb, fb, eb = load_prepared(tic, period, suffix)
    t0 = time.perf_counter()
    rf = run_tls(tb, fb, eb, period * (1 - half_width), period * (1 + half_width),
                 prep["R_star"], prep["M_star"], oversampling, threads)
    res = {"tic_id": tic, "survey_period": period, "generated_utc": utc(), "rules_version": RULES_VERSION,
           "half_width": half_width,
           "inputs": _tls_inputs(prep, period * (1 - half_width), period * (1 + half_width), oversampling),
           "per_product": prep["per_product"], "forced": _floor_tls_summary(_tls_summary(rf), tb),
           "timing_s": {"tls_forced": round(time.perf_counter() - t0, 1)}}
    jdump(out_path, res)
    return res


def tls_step(tic: int, period: float, threads: int, oversampling: int, pmin: float, pmax: float,
             bin_minutes: float, window_days: float | None, force: bool = False,
             mask: list[tuple[float, float]] | None = None, suffix: str = "",
             residual_mask: dict | None = None) -> dict:
    """Blind TLS over ``pmin``-``pmax`` plus the narrow forced run, on the ``prepare`` output.

    [P10] ``residual_mask`` (an ephemeris ``period`` / ``t0`` / ``duration``): the stronger
    signal's transits are masked out of the prepared series (``C_RESIDUAL_MASK_DURATIONS``
    either side) before the blind run, the base ``prepare`` output is reused, and the record
    and spectrum are written under ``suffix``.  The saved spectrum carries the raw per-trial
    ``chi2``, ``SR`` and ``power_raw`` beside the installed ``power`` (gotcha 13).
    """
    out_path = OUT / "tls" / f"{key(tic, period)}{suffix}.json"
    if out_path.exists() and not force:
        cached = jload(out_path)
        if cache_matches(cached):
            if RULES.duration_floor_cadence:
                times = load_prepared(tic, period, "" if residual_mask else suffix)[0]
                cached["blind"] = _floor_tls_summary(cached["blind"], times)
                cached["forced"] = _floor_tls_summary(cached["forced"], times)
            return cached
    base_suffix = "" if residual_mask else suffix
    prep = prepare_step(tic, period, bin_minutes, window_days, force=force, mask=mask, suffix=base_suffix)
    tb, fb, eb = load_prepared(tic, period, base_suffix)
    n_residual_masked = 0
    if residual_mask:
        keep = ~transit_mask(tb, float(residual_mask["period"]), float(residual_mask["t0"]),
                             float(residual_mask["duration"]), n_durations=R.C_RESIDUAL_MASK_DURATIONS)
        n_residual_masked = int((~keep).sum())
        tb, fb, eb = tb[keep], fb[keep], eb[keep]
    rstar, mstar = prep["R_star"], prep["M_star"]
    t_det = prep["seconds"]
    # blind search
    t1 = time.perf_counter()
    r = run_tls(tb, fb, eb, pmin, pmax, rstar, mstar, oversampling, threads)
    t_blind = time.perf_counter() - t1
    blind = _floor_tls_summary(_tls_summary(r), tb)
    blind["peaks"] = _peak_table(r.periods, r.power)
    # SDE at the survey period (nearest grid point, and max within +/-1%)
    p = np.asarray(r.periods); w = np.asarray(r.power)
    m = np.abs(p / period - 1) < 0.01
    blind["SDE_at_survey_period_max_1pct"] = float(np.nanmax(w[m])) if m.any() else None
    blind["SDE_rank_of_survey_period"] = None
    if m.any():
        pk = blind["peaks"]
        for i, pkk in enumerate(pk):
            if abs(pkk["period"] / period - 1) < 0.01 or _match(pkk["period"], period)["alias_1pct"]:
                blind["SDE_rank_of_survey_period"] = i + 1
                break
    raw = {}
    for name in ("chi2", "SR", "power_raw"):
        arr = getattr(r, name, None)
        if arr is not None and np.ndim(arr) == 1 and len(arr) == len(p):
            raw[name] = np.asarray(arr, dtype=float)
    np.savez_compressed(OUT / "tls" / f"{key(tic, period)}{suffix}_spectrum.npz", periods=p, power=w, **raw)
    blind["match"] = _match(blind["period"], period)
    if residual_mask:
        blind["residual_mask"] = {"period": float(residual_mask["period"]), "t0": float(residual_mask["t0"]),
                                  "duration": float(residual_mask["duration"]), "n_cadences_masked": n_residual_masked,
                                  "durations_either_side": R.C_RESIDUAL_MASK_DURATIONS}
    # forced narrow search at the survey period (ephemeris + per-transit diagnostics, NOT a detection)
    t2 = time.perf_counter()
    rf = run_tls(tb, fb, eb, period * 0.985, period * 1.015, rstar, mstar, max(oversampling, 5), threads)
    forced = _floor_tls_summary(_tls_summary(rf), tb)
    t_forced = time.perf_counter() - t2
    res = {
        "tic_id": tic, "survey_period": period, "generated_utc": utc(), "rules_version": RULES_VERSION,
        "inputs": _tls_inputs(prep, pmin, pmax, oversampling),
        "per_product": prep["per_product"],
        "blind": blind, "forced": forced,
        "timing_s": {"detrend": round(t_det, 1), "tls_blind": round(t_blind, 1), "tls_forced": round(t_forced, 1)},
    }
    # PASS: strongest peak within 1% of the survey period AND SDE >= 9 (TLS's own FAP ~ 1e-4 level);
    # ALIAS: an exact low-order alias within 1% at SDE >= 9; WEAK: a match or alias below SDE 9 (noise-level);
    # FAIL: strongest peak elsewhere.
    strong = blind["SDE"] >= 9.0
    if blind["match"]["same_period_1pct"]:
        res["verdict_tls"] = "PASS" if strong else "WEAK"
    elif blind["match"]["alias_1pct"]:
        res["verdict_tls"] = "ALIAS" if strong else "WEAK"
    else:
        res["verdict_tls"] = "FAIL"
    jdump(out_path, res)
    return res


# ─────────────────────────────────────────────────────────────────────────────
# events: every predicted transit in the raw SAP flux of the product that saw it
# ─────────────────────────────────────────────────────────────────────────────
def _packet_fit(tic: int, period: float) -> dict:
    for d in PACKETS_DIR.glob(f"tic{tic}_P*"):
        try:
            if abs(float(d.name.split("_P")[1]) / period - 1) < 0.02 and (d / "fit.json").exists():
                return jload(d / "fit.json")
        except Exception:
            continue
    return {}


def _ephemeris(tic: int, period: float, source: str = "survey") -> dict:
    """Ephemeris to examine the events at.

    ``survey``: the candidate as ranked (period and epoch of the search that found it);
    ``packet``: the P4 packet refit (fit.json);
    ``tls``: the forced narrow TLS of this audit (whole baseline).
    The survey duration is used everywhere so that the same window is examined.
    """
    row = survivor_row(tic, period)
    ref_depth_ppt = float(row.get("depth_ppt") or 0.0) if row else None
    dur = float(row["duration_days"]) if row else 0.1
    if source == "tls":
        tls_path = OUT / "tls" / f"{key(tic, period)}.json"
        if not tls_path.exists():                     # the forced narrow run on its own (prompt 6 Stage A)
            tls_path = OUT / "tls" / f"{key(tic, period)}_forced.json"
        f = jload(tls_path)["forced"]
        if RULES.duration_floor_cadence:
            f = _floor_tls_summary(f, load_prepared(tic, period)[0])
        d_tls = float(f["duration_days"])
        return {"period": float(f["period"]), "t0": float(f["T0_btjd"]), "duration": max(dur, d_tls) if 0.02 <= d_tls <= 0.7 else dur,
                "source": "tls_forced", "ref_depth_ppt": ref_depth_ppt}
    if source == "packet":
        f = _packet_fit(tic, period)
        if f.get("period") and f.get("t0"):
            fd = float(f.get("duration_days") or dur)
            return {"period": float(f["period"]), "t0": float(f["t0"]), "duration": max(dur, fd) if 0.02 <= fd <= 0.7 else dur,
                    "source": "packet_fit", "ref_depth_ppt": ref_depth_ppt}
        source = "survey"
    return {"period": float(row["period_days"]), "t0": float(row["epoch_btjd"]), "duration": dur, "source": "survey",
            "ref_depth_ppt": ref_depth_ppt}


# _weighted, the per-event measurement, the removal rules and the kept-event statistics are now
# tesshunter.event_vet (imported above).  This wrapper supplies the ephemeris, the products and
# the file layout; nothing about the rules changed.
_weighted = weighted_mean


def _sector_cadences(products: list[dict]) -> dict:
    return {int(p["sector"]): float(p["cadence_s"]) for p in products}


def events_step(tic: int, period: float, force: bool = False, source: str = "survey") -> dict:
    out_path = OUT / "events" / f"{key(tic, period)}_{source}.json"
    if out_path.exists() and not force:
        cached = jload(out_path)
        if cache_matches(cached):
            return cached
    eph = _ephemeris(tic, period, source)
    P, T0, dur = eph["period"], eph["t0"], eph["duration"]
    ref_depth = (eph["ref_depth_ppt"] or 1.0) / 1000.0
    products = choose_per_sector(load_products(tic))
    lcz = np.load(OUT / "tls" / f"{key(tic, period)}_lc.npz")
    tdet, fdet = lcz["time_unbinned"], lcz["flux_unbinned"]
    events = event_table(products, tdet, fdet, P, T0, dur, ref_depth)
    # Prompt-7 option 2: inflate every event's error by its sector's red-noise beta before the
    # depth-consistency chi-square.  OFF under LEGACY_RULES, which is the default.
    beta = None
    if RULES.inflated_depth_consistency:
        sdet = lcz["sector_unbinned"]
        in_tr = transit_mask(tdet, P, T0, dur, n_durations=0.5)
        beta = sector_beta(tdet, fdet, sdet, in_tr, dur, _sector_cadences(products),
                           beta_max=RULES.beta_max)
    summary = summarise_events(events, eph, beta_by_sector=beta, gate_errors=RULES.depth_consistency_errors)
    if beta is not None:
        summary["red_noise_beta_by_sector"] = {str(k): round(v, 3) for k, v in sorted(beta.items())}
    res = {"tic_id": tic, "survey_period": period, "generated_utc": utc(), "rules_version": RULES_VERSION,
           "summary": summary, "events": events}
    jdump(out_path, res)
    return res


# ─────────────────────────────────────────────────────────────────────────────
# neighbours: Gaia DR3 within 1 arcmin, SIMBAD, VSX, dilution
# ─────────────────────────────────────────────────────────────────────────────
def _target_coords(tic: int) -> tuple[float, float, dict]:
    st = stellar_from_cache(tic)
    if st.get("ra") is not None:
        return float(st["ra"]), float(st["dec"]), st
    import csv
    for r in csv.DictReader(open(SURVIVORS_CSV, newline="", encoding="utf-8")):
        if int(r["tic_id"]) == tic:
            st = {"tmag": float(r["tmag"]) if r.get("tmag") not in (None, "") else None}
            # the prompt-8 target list carries the TIC's Gaia id and Teff; the P4 survivor table does not
            for src, dst in (("tic_gaia_id", "gaia_id"), ("teff_k", "teff"), ("radius_rsun", "radius"),
                             ("mass_msun", "mass"), ("pmra_mas_yr", "pmra"), ("pmdec_mas_yr", "pmdec")):
                v = r.get(src)
                if v not in (None, "", "nan"):
                    try:
                        st[dst] = int(float(v)) if dst == "gaia_id" else float(v)
                    except ValueError:
                        pass
            return float(r["ra_deg"]), float(r["dec_deg"]), st
    raise SystemExit(f"no coordinates for TIC {tic}")


def _gaia_cone(ra: float, dec: float, radius_arcmin: float = 1.0):
    from astroquery.gaia import Gaia
    Gaia.ROW_LIMIT = -1
    adql = f"""SELECT g.source_id, g.ra, g.dec, g.phot_g_mean_mag, g.phot_bp_mean_mag, g.phot_rp_mean_mag, g.parallax,
g.parallax_error, g.pmra, g.pmdec, g.ruwe, g.phot_variable_flag, g.non_single_star, g.duplicated_source, g.ipd_frac_multi_peak,
g.ipd_gof_harmonic_amplitude, g.astrometric_excess_noise, g.astrometric_excess_noise_sig, g.radial_velocity, g.radial_velocity_error,
g.rv_amplitude_robust, g.rv_nb_transits, g.phot_g_n_obs, g.teff_gspphot, g.logg_gspphot, g.distance_gspphot,
v.best_class_name, v.best_class_score,
DISTANCE(POINT('ICRS', g.ra, g.dec), POINT('ICRS', {ra}, {dec}))*3600.0 AS sep_arcsec
FROM gaiadr3.gaia_source AS g LEFT JOIN gaiadr3.vari_classifier_result AS v ON g.source_id = v.source_id
WHERE 1=CONTAINS(POINT('ICRS', g.ra, g.dec), CIRCLE('ICRS', {ra}, {dec}, {radius_arcmin / 60.0}))
ORDER BY sep_arcsec"""
    job = Gaia.launch_job(adql)
    return job.get_results()


def _nss(source_id: int) -> list[dict]:
    from astroquery.gaia import Gaia
    out = []
    for table in ("gaiadr3.nss_two_body_orbit", "gaiadr3.nss_acceleration_astro", "gaiadr3.nss_non_linear_spectro"):
        try:
            t = Gaia.launch_job(f"SELECT * FROM {table} WHERE source_id = {source_id}").get_results()
            for r in t:
                d = {"table": table}
                for c in ("nss_solution_type", "period", "period_error", "eccentricity", "semi_amplitude_primary", "inclination"):
                    if c in t.colnames:
                        v = r[c]
                        d[c] = None if (hasattr(v, "mask") and v.mask) else (str(v) if c == "nss_solution_type" else float(v))
                out.append(d)
        except Exception as exc:
            out.append({"table": table, "error": str(exc)[:120]})
    return out


def _fval(v):
    try:
        if v is None or (hasattr(v, "mask") and bool(np.all(v.mask))):
            return None
        f = float(v)
        return None if not np.isfinite(f) else f
    except Exception:
        return None


# Prompt 8: SIMBAD and VSX results fetched in bulk (one query per few hundred stars) and handed
# to ``neighbours_step`` per star, so the per-star record keeps its layout without a per-star
# SIMBAD query (measured at 32 s each).  Keyed by TIC id; absent keys fall back to the query.
PREFETCHED_SIMBAD: dict[int, list[dict]] = {}
PREFETCHED_VSX: dict[int, list[dict]] = {}


def neighbours_step(tic: int, force: bool = False) -> dict:
    out_path = OUT / "neighbours" / f"tic{tic}.json"
    if out_path.exists() and not force:
        return jload(out_path)
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    ra, dec, st = _target_coords(tic)
    # candidate depths on this star (all survivors), for the dilution test
    import csv
    depths = sorted({round(float(r["depth_ppt"]), 3) for r in csv.DictReader(open(SURVIVORS_CSV, newline="", encoding="utf-8"))
                     if int(r["tic_id"]) == tic and r.get("depth_ppt") not in (None, "", "nan")})
    res = {"tic_id": tic, "ra": ra, "dec": dec, "tic_gaia_id": st.get("gaia_id"), "tic_gaia_mag": st.get("gaia_mag"), "tmag": st.get("tmag"),
           "generated_utc": utc(), "candidate_depths_ppt": depths}
    # Gaia
    try:
        tab = _gaia_cone(ra, dec, 1.0)
        rows = []
        for r in tab:
            rows.append({c: (_fval(r[c]) if c not in ("phot_variable_flag", "best_class_name", "source_id") else
                             (int(r[c]) if c == "source_id" else (str(r[c]) if r[c] is not None else ""))) for c in tab.colnames})
        # identify the target: TIC's Gaia id, else nearest within 5 arcsec
        tgt = next((r for r in rows if st.get("gaia_id") and r["source_id"] == int(st["gaia_id"])), None)
        match_how = "tic_gaia_id" if tgt else None
        if tgt is None:
            near = [r for r in rows if (r["sep_arcsec"] or 99) < 5]
            tgt = near[0] if near else None
            match_how = "nearest_5arcsec" if tgt else None
        if tgt is None and st.get("pmra") is not None and st.get("pmdec") is not None:
            # prompt 8: a nearby M dwarf moves arcseconds between the TIC's J2000 position and
            # Gaia's 2016.0 epoch; propagate the TIC proper motion and match within 5 arcsec of that
            import math as _m
            dt_yr = 16.0
            ra_e = ra + (float(st["pmra"]) * dt_yr / 3.6e6) / _m.cos(_m.radians(dec))
            dec_e = dec + float(st["pmdec"]) * dt_yr / 3.6e6
            best, bestd = None, 5.0
            for r in rows:
                if r.get("ra") is None or r.get("dec") is None:
                    continue
                d = 3600.0 * _m.hypot((r["ra"] - ra_e) * _m.cos(_m.radians(dec)), r["dec"] - dec_e)
                if d < bestd:
                    best, bestd = r, d
            if best is not None:
                tgt, match_how = best, "nearest_5arcsec_after_proper_motion"
        res["gaia"] = {"n_within_1arcmin": len(rows), "target": tgt, "target_match": (match_how or "none")}
        if tgt and (tgt.get("non_single_star") or 0) > 0:
            res["gaia"]["nss"] = _nss(tgt["source_id"])
        # dilution: flux ratio in Rp where possible (closest to the TESS band), else G
        nb = []
        for r in rows:
            if tgt and r["source_id"] == tgt["source_id"]:
                continue
            band = "rp" if (r.get("phot_rp_mean_mag") is not None and tgt and tgt.get("phot_rp_mean_mag") is not None) else "g"
            m_n = r.get(f"phot_{band}_mean_mag"); m_t = tgt.get(f"phot_{band}_mean_mag") if tgt else None
            if m_n is None or m_t is None:
                fr = None
            else:
                fr = 10 ** (-0.4 * (m_n - m_t))
            dmax = fr / (1 + fr) if fr is not None else None
            nb.append({"source_id": r["source_id"], "sep_arcsec": round(r["sep_arcsec"], 1), "sep_px": round(r["sep_arcsec"] / PIXEL_ARCSEC, 2),
                       "G": r.get("phot_g_mean_mag"), "Rp": r.get("phot_rp_mean_mag"), "band_used": band,
                       "delta_mag": None if fr is None else round(m_n - m_t, 2), "flux_ratio_to_target": None if fr is None else round(fr, 5),
                       "max_observed_depth_ppt_total_eclipse": None if dmax is None else round(1000 * dmax, 2),
                       "can_produce_candidate_depths_total_eclipse": None if dmax is None else [bool(1000 * dmax >= d) for d in depths],
                       "can_produce_candidate_depths_50pct_eclipse": None if dmax is None else [bool(500 * dmax >= d) for d in depths],
                       "ruwe": r.get("ruwe"), "variable_flag": r.get("phot_variable_flag"), "vari_class": r.get("best_class_name"), "parallax": r.get("parallax")})
        res["gaia"]["neighbours"] = nb
        res["gaia"]["n_neighbours_that_could_produce_depth_total_eclipse_within_63arcsec"] = int(sum(
            1 for x in nb if x["sep_arcsec"] <= 63 and x["can_produce_candidate_depths_total_eclipse"] and any(x["can_produce_candidate_depths_total_eclipse"])))
        # prompt 8: the star-level count that needs no candidate depth (a 1-ppt dip, totally eclipsed)
        res["gaia"]["n_neighbours_within_3px_could_make_1ppt"] = int(sum(
            1 for x in nb if x["sep_px"] <= 3.0 and (x["max_observed_depth_ppt_total_eclipse"] or 0) >= 1.0))
    except Exception as exc:
        res["gaia"] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    # SIMBAD
    try:
        if tic in PREFETCHED_SIMBAD:
            simb = sorted(PREFETCHED_SIMBAD[tic], key=lambda x: x["sep_arcsec"])
            res["simbad"] = {"n_within_1arcmin": len(simb), "objects": simb, "source": "bulk prefetch (prompt 8)"}
            raise StopIteration
        from astroquery.simbad import Simbad
        s = Simbad()
        for f in ("otype", "otypes", "sp_type", "V", "G"):
            try:
                s.add_votable_fields(f)
            except Exception:
                pass
        c = SkyCoord(ra, dec, unit="deg")
        t = s.query_region(c, radius=1 * u.arcmin)
        simb = []
        if t is not None:
            for r in t:
                sep = SkyCoord(float(r["ra"]), float(r["dec"]), unit="deg").separation(c).arcsec
                simb.append({"main_id": str(r["main_id"]), "otype": str(r["otype"]) if "otype" in t.colnames else None,
                             "otypes": str(r["otypes.otype_txt"]) if "otypes.otype_txt" in t.colnames else (str(r["otypes"]) if "otypes" in t.colnames else None),
                             "sp_type": str(r["sp_type"]) if "sp_type" in t.colnames else None, "sep_arcsec": round(float(sep), 1),
                             "V": _fval(r["V"]) if "V" in t.colnames else None, "G": _fval(r["G"]) if "G" in t.colnames else None})
        simb.sort(key=lambda x: x["sep_arcsec"])
        res["simbad"] = {"n_within_1arcmin": len(simb), "objects": simb}
    except StopIteration:
        pass
    except Exception as exc:
        res["simbad"] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    # VSX
    try:
        if tic in PREFETCHED_VSX:
            vsx = sorted(PREFETCHED_VSX[tic], key=lambda x: x.get("sep_arcsec", 99))
            res["vsx"] = {"n_within_1arcmin": len(vsx), "objects": vsx, "source": "bulk prefetch (prompt 8)"}
            raise StopIteration
        from astroquery.vizier import Vizier
        v = Vizier(catalog="B/vsx/vsx", columns=["**"], row_limit=-1)
        c = SkyCoord(ra, dec, unit="deg")
        tl = v.query_region(c, radius=1 * u.arcmin)
        vsx = []
        for t in tl:
            for r in t:
                rr = {}
                for col in t.colnames:
                    val = r[col]
                    rr[col] = None if (hasattr(val, "mask") and bool(np.all(val.mask))) else (float(val) if isinstance(val, (np.floating, float, np.integer, int)) else str(val))
                try:
                    rr["sep_arcsec"] = round(float(SkyCoord(float(r["RAJ2000"]), float(r["DEJ2000"]), unit="deg").separation(c).arcsec), 1)
                except Exception:
                    pass
                vsx.append(rr)
        res["vsx"] = {"n_within_1arcmin": len(vsx), "objects": vsx}
    except StopIteration:
        pass
    except Exception as exc:
        res["vsx"] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    g = res.get("gaia", {}); tg = g.get("target") or {}
    res["summary"] = (f"Gaia: {g.get('n_within_1arcmin', '?')} sources within 1 arcmin; target RUWE {tg.get('ruwe')}, var flag {tg.get('phot_variable_flag')}, "
                      f"NSS {tg.get('non_single_star')}, dup {tg.get('duplicated_source')}, ipd_multi_peak {tg.get('ipd_frac_multi_peak')}, class {tg.get('best_class_name') or '-'}; "
                      f"{g.get('n_neighbours_that_could_produce_depth_total_eclipse_within_63arcsec', '?')} neighbour(s) within 3 px bright enough to make the depth; "
                      f"SIMBAD {res.get('simbad', {}).get('n_within_1arcmin', '?')} ({', '.join(o['otype'] or '' for o in res.get('simbad', {}).get('objects', [])[:3])}); "
                      f"VSX {res.get('vsx', {}).get('n_within_1arcmin', '?')}")
    jdump(out_path, res)
    return res


# ─────────────────────────────────────────────────────────────────────────────
# crossmatch: the hard stop again, catalogs re-downloaded now
# ─────────────────────────────────────────────────────────────────────────────
def crossmatch_step(tics: list[int], refresh: bool = True) -> dict:
    sys.path.insert(0, str(REPO / "src"))
    os.environ.pop("TESSHUNTER_OFFLINE", None)
    from tesshunter.catalog_crossmatch import CatalogFetchError, KnownObjectCatalog
    t0 = time.perf_counter()
    cat = KnownObjectCatalog.load(refresh=refresh)
    man = cat.manifest()
    man["refresh_seconds"] = round(time.perf_counter() - t0, 1)
    man["refreshed"] = refresh
    res = {"generated_utc": utc(), "rules_version": RULES_VERSION, "catalog_stamp": cat.stamp(),
           "manifest": man, "per_star": {}}
    for tic in tics:
        ra, dec, _ = _target_coords(tic)
        try:
            hs = cat.check(tic, ra, dec, resolve_neighbours=True)
            rec = hs.to_dict(); rec["catalog_stamp"] = cat.stamp(); rec["checked_utc"] = utc()
        except CatalogFetchError as exc:
            rec = {"status": "ERROR", "summary": str(exc)[:300]}
        res["per_star"][str(tic)] = rec
    jdump(OUT / f"crossmatch_{OUT.name}.json", res)
    return res


# ─────────────────────────────────────────────────────────────────────────────
# fit: every transit on the wotan-detrended data, batman, density prior handled
# ─────────────────────────────────────────────────────────────────────────────
def _ld_from_packet(tic: int, period: float) -> tuple[float, float, str]:
    for d in PACKETS_DIR.glob(f"tic{tic}_P*"):
        try:
            if abs(float(d.name.split("_P")[1]) / period - 1) < 0.02:
                f = jload(d / "fit.json")
                return float(f["u1"]), float(f["u2"]), str(f.get("ld_source", "packet fit.json"))
        except Exception:
            continue
    if INPUT_CONFIG is not None:
        from tesshunter.survey import limb_darkening_for_teff
        star = stellar_from_cache(tic)
        row = survivor_row(tic, period)
        for value in (star.get("teff"), row.get("teff_k")):
            try:
                teff = float(value)
            except (TypeError, ValueError):
                continue
            if np.isfinite(teff) and teff > 0:
                u1, u2 = limb_darkening_for_teff(teff)
                return float(u1), float(u2), f"survey Claret interpolation at TIC Teff {teff:g} K"
    return 0.45, 0.20, "default quadratic (no packet)"


def _p8_fit_input(tic: int, period: float) -> dict:
    """Seed the physical fit with the signal actually accepted by Stage C.

    Stage C allows a 1% period difference and validated factor-two aliases;
    the physical fit's local 0.1% bounds cannot reach those from the survey
    seed. Keep the wider of the survey and TLS durations for the fit window.
    Hash the accepted record so an old survey-seeded fit cannot be reused.
    """
    path = OUT / "stageC" / f"{key(tic, period)}.json"
    raw = path.read_bytes()
    rec = json.loads(raw)
    if not cache_matches(rec) or rec.get("decision") != "PASS":
        raise ValueError(f"{key(tic, period)}: physical fit requires a current Stage C PASS")
    blind = rec["blind"]
    p, t0, duration, depth = (float(blind[name]) for name in
                             ("period", "T0_btjd", "duration_days", "depth"))
    if not np.all(np.isfinite([p, t0, duration, depth])) or not (0 < duration < p and 0 < depth < 1):
        raise ValueError(f"{key(tic, period)}: invalid accepted Stage C fit ephemeris")
    survey_eph = _ephemeris(tic, period)
    return {"version": 1, "stage_c_sha256": hashlib.sha256(raw).hexdigest(),
            "ephemeris": {"period": p, "t0": t0, "duration": max(survey_eph["duration"], duration),
                          "source": "stageC.blind", "ref_depth_ppt": survey_eph["ref_depth_ppt"]},
            "depth_flux": depth}


def fit_step(tic: int, period: float, force: bool = False, max_iter: int = 2000) -> dict:
    import batman
    from scipy.optimize import least_squares
    out_path = OUT / "fit" / f"{key(tic, period)}.json"
    fit_input = _p8_fit_input(tic, period) if RULES_VERSION == "p8.0" else None
    if out_path.exists() and not force:
        cached = jload(out_path)
        if (INPUT_CONFIG is None or cache_matches(cached)) and (fit_input is None or cached.get("fit_input") == fit_input):
            return cached
    eph = fit_input["ephemeris"] if fit_input is not None else _ephemeris(tic, period)
    P0, T00, dur0 = eph["period"], eph["t0"], eph["duration"]
    st = stellar_from_cache(tic); row = survivor_row(tic, period)
    rstar = float(st.get("radius") or row.get("radius_rsun") or 1.0)
    rstar_err = float(st.get("radius_err") or 0.1 * rstar)
    mstar = st.get("mass") or row.get("mass_msun")
    mstar = float(mstar) if mstar not in (None, "", "nan") and np.isfinite(float(mstar)) else rstar
    rho_cat = float(st["rho"]) if st.get("rho") else 1.408 * mstar / rstar ** 3
    rho_cat_err = float(st["rho_err"]) if st.get("rho_err") else 0.3 * rho_cat
    G = 6.674e-8
    a_rs_cat = ((G * rho_cat * (P0 * 86400.0) ** 2) / (3 * math.pi)) ** (1 / 3)
    u1, u2, ld_src = _ld_from_packet(tic, period)
    lcz = np.load(OUT / "tls" / f"{key(tic, period)}_lc.npz")
    t, f, sec = lcz["time_unbinned"], lcz["flux_unbinned"], lcz["sector_unbinned"]
    tls = jload(OUT / "tls" / f"{key(tic, period)}.json")
    cad_by_sector = {p["sector"]: p["cadence_s"] for p in tls["inputs"]["products"]}
    # window around every transit
    phase_dt = ((t - T00 + 0.5 * P0) % P0) - 0.5 * P0
    win = max(3.0 * dur0, 0.4)
    m = np.abs(phase_dt) < win
    t, f, sec, phase_dt = t[m], f[m], sec[m], phase_dt[m]
    oot = np.abs(phase_dt) > 0.75 * dur0
    # per-sector white sigma from out-of-transit scatter, and a red-noise beta
    sig = np.ones_like(f)
    betas = []
    for s in np.unique(sec):
        ms = sec == s
        r = f[ms & oot] - 1.0
        if r.size < 20:
            r = f[ms] - 1.0
        w = 1.4826 * np.nanmedian(np.abs(r - np.nanmedian(r))) if r.size else 1e-3
        sig[ms] = max(w, 1e-6)
        # beta: binned residual scatter vs white expectation (bins of dur0/3)
        tt = t[ms & oot]
        if tt.size > 60:
            nb = max(3, int(round(dur0 / 3 / (cad_by_sector.get(int(s), 1800.0) / 86400.0))))
            k = (tt.size // nb) * nb
            if k >= 3 * nb:
                rb = r[:k].reshape(-1, nb).mean(axis=1)
                exp = w / math.sqrt(nb)
                betas.append(float(np.std(rb) / exp) if exp > 0 else 1.0)
    beta = float(np.clip(np.median(betas), 1.0, 5.0)) if betas else 1.0
    sig_eff = sig * beta
    # batman models per cadence group
    groups = {}
    for s in np.unique(sec):
        c = cad_by_sector.get(int(s), 1800.0)
        groups.setdefault(c, []).append(s)
    idx_by_cad = {c: np.isin(sec, ss) for c, ss in groups.items()}

    def make_params(t0, per, rp, a, b):
        p = batman.TransitParams()
        p.t0, p.per, p.rp, p.a = t0, per, rp, a
        p.inc = math.degrees(math.acos(min(1.0, b / a))); p.ecc = 0.0; p.w = 90.0
        p.u = [u1, u2]; p.limb_dark = "quadratic"
        return p

    p_init = make_params(T00, P0, 0.05, a_rs_cat, 0.3)
    models = {c: batman.TransitModel(p_init, t[idx], supersample_factor=max(1, int(round(c / 120.0))), exp_time=c / 86400.0)
              for c, idx in idx_by_cad.items()}

    def model_flux(t0, per, rp, a, b):
        out = np.empty_like(f)
        p = make_params(t0, per, rp, a, b)
        for c, idx in idx_by_cad.items():
            out[idx] = models[c].light_curve(p)
        return out

    def resid_free(x):
        t0, per, rp, a, b = x
        return (f - model_flux(t0, per, rp, a, b)) / sig_eff

    def resid_prior(x):
        t0, per, rp, b = x
        return (f - model_flux(t0, per, rp, a_rs_cat, b)) / sig_eff

    depth_guess = max(1e-4, 1.0 - float(fit_input["depth_flux"] if fit_input is not None else tls["forced"]["depth"]))
    rp0 = math.sqrt(depth_guess)
    lb = [T00 - 0.2 * dur0, P0 * 0.999, 0.005, 1.5, 0.0]; ub = [T00 + 0.2 * dur0, P0 * 1.001, 0.6, 1000.0, 1.1]
    x0 = [T00, P0, min(max(rp0, 0.006), 0.5), a_rs_cat, 0.3]
    t_start = time.perf_counter()
    r_free = least_squares(resid_free, x0, bounds=(lb, ub), max_nfev=max_iter, x_scale="jac")
    r_prior = least_squares(resid_prior, [x0[0], x0[1], x0[2], x0[4]], bounds=([lb[0], lb[1], lb[2], lb[4]], [ub[0], ub[1], ub[2], ub[4]]),
                            max_nfev=max_iter, x_scale="jac")
    chi2_free = float(np.sum(r_free.fun ** 2)); chi2_prior = float(np.sum(r_prior.fun ** 2))
    chi2_flat = float(np.sum(((f - 1.0) / sig_eff) ** 2))
    dchi2_prior = chi2_prior - chi2_free               # what the data lose when the catalog density is imposed
    adopt_prior = dchi2_prior < 9.0                    # the data cannot reject the catalog density at 3 sigma
    r = r_prior if adopt_prior else r_free
    if adopt_prior:
        t0, per, rp, b = r.x; a = a_rs_cat
    else:
        t0, per, rp, a, b = r.x

    def cov_errors(res):
        try:
            J = res.jac
            cov = np.linalg.inv(J.T @ J)
            dof = max(1, len(res.fun) - len(res.x))
            cov *= max(1.0, np.sum(res.fun ** 2) / dof)
            return np.sqrt(np.diag(cov))
        except Exception:
            return np.full(len(res.x), np.nan)
    errs = cov_errors(r)
    if adopt_prior:
        t0_err, per_err, rp_err, b_err = errs
        a_err = a_rs_cat * rho_cat_err / (3 * rho_cat)
    else:
        t0_err, per_err, rp_err, a_err, b_err = errs
    uncertainty_issues = []
    if not np.all(np.isfinite(errs)):
        uncertainty_issues.append("singular fit covariance: parameter uncertainties are unavailable")
    mod = model_flux(t0, per, rp, a, b)
    depth_max = float(1.0 - mod.min())
    # duration (T14) and duration-averaged depth from the model on a fine grid
    tg = np.linspace(t0 - 0.5 * P0 / 2, t0 + 0.5 * P0 / 2, 20001) if P0 < 2 else np.linspace(t0 - 1.0, t0 + 1.0, 20001)
    pg = make_params(t0, per, rp, a, b)
    mg = batman.TransitModel(pg, tg).light_curve(pg)
    intr = mg < 1.0 - 1e-7
    t14_h = float((tg[intr].max() - tg[intr].min()) * 24.0) if intr.any() else 0.0
    depth_avg = float(np.mean(1.0 - mg[intr])) if intr.any() else 0.0
    # T14 uncertainty by propagating rp, a, b errors numerically
    def t14_of(rp_, a_, b_):
        pp = make_params(t0, per, rp_, a_, b_); mm = batman.TransitModel(pp, tg).light_curve(pp); ii = mm < 1 - 1e-7
        return float((tg[ii].max() - tg[ii].min()) * 24.0) if ii.any() else 0.0
    parts = []
    perturbations = ((rp_err, 0, 0), (0, a_err, 0), (0, 0, b_err)) if np.all(np.isfinite([rp_err, a_err, b_err])) else ()
    for (dr, da, db) in perturbations:
        try:
            parts.append(abs(t14_of(min(0.6, rp + dr), max(1.5, a + da), min(1.1, max(0.0, b + db))) - t14_h))
        except Exception:
            pass
    t14_err_h = float(math.sqrt(sum(p_ ** 2 for p_ in parts))) if parts else float("nan")
    # odd / even: refit rp only on odd and on even transits
    n_tr = np.round((t - t0) / per).astype(int)
    oe = {}
    for name, sel in (("odd", n_tr % 2 == 1), ("even", n_tr % 2 == 0)):
        if sel.sum() < 10:
            continue
        def rr(x):
            return ((f - model_flux(t0, per, x[0], a, b)) / sig_eff)[sel]
        rs = least_squares(rr, [rp], bounds=([0.001], [0.7]), max_nfev=300)
        e = cov_errors(rs)
        oe[name] = {"rp_rs": float(rs.x[0]), "rp_rs_err": float(e[0]), "depth_ppt": round(1000 * float(rs.x[0] ** 2), 3),
                    "n_transits": int(len(np.unique(n_tr[sel])))}
    if "odd" in oe and "even" in oe:
        d_o, d_e = oe["odd"]["rp_rs"] ** 2, oe["even"]["rp_rs"] ** 2
        e_o, e_e = 2 * oe["odd"]["rp_rs"] * oe["odd"]["rp_rs_err"], 2 * oe["even"]["rp_rs"] * oe["even"]["rp_rs_err"]
        oe["sigma"] = round(abs(d_o - d_e) / math.sqrt(e_o ** 2 + e_e ** 2), 2)
    n_transits = int(len(np.unique(n_tr[np.abs(phase_dt) < 0.5 * dur0])))
    rho_fit = 3 * math.pi * a ** 3 / (G * (per * 86400.0) ** 2)
    rp_re = rp * rstar * 109.076
    rp_re_err = rp_re * math.sqrt((rp_err / rp) ** 2 + (rstar_err / rstar) ** 2) if np.isfinite(rp_err) else float("nan")
    res = {
        "tic_id": tic, "survey_period": period, "generated_utc": utc(), "ephemeris_start": eph,
        "rules_version": RULES_VERSION,
        "data": {"n_points_in_windows": int(len(t)), "n_transits_with_data": n_transits, "sectors": [int(s) for s in np.unique(sec)],
                 "window_half_days": win, "beta_red_noise": round(beta, 2), "sigma_white_median_ppt": round(1000 * float(np.median(sig)), 3)},
        "limb_darkening": {"u1": u1, "u2": u2, "source": ld_src},
        "stellar": {"radius": rstar, "radius_err": rstar_err, "mass": mstar, "rho_cgs": rho_cat, "rho_err": rho_cat_err, "a_rs_catalog": a_rs_cat},
        "free_fit": {"t0": float(r_free.x[0]), "period": float(r_free.x[1]), "rp_rs": float(r_free.x[2]), "a_rs": float(r_free.x[3]), "b": float(r_free.x[4]),
                     "chi2": chi2_free, "rho_fit_cgs": 3 * math.pi * float(r_free.x[3]) ** 3 / (G * (float(r_free.x[1]) * 86400.0) ** 2)},
        "prior_fit": {"t0": float(r_prior.x[0]), "period": float(r_prior.x[1]), "rp_rs": float(r_prior.x[2]), "a_rs": a_rs_cat, "b": float(r_prior.x[3]), "chi2": chi2_prior},
        "chi2_flat": chi2_flat, "delta_chi2_prior_minus_free": dchi2_prior, "density_prior_adopted": adopt_prior,
        "uncertainty_issues": uncertainty_issues,
        "impact_parameter_near_zero": bool(b <= 1e-3),  # geometry diagnostic, not a verdict rule
        "adopted": {"t0_btjd": float(t0), "t0_err": float(t0_err), "epoch_bjd": float(t0 + BTJD_OFFSET), "period": float(per), "period_err": float(per_err),
                    "rp_rs": float(rp), "rp_rs_err": float(rp_err), "a_rs": float(a), "a_rs_err": float(a_err), "b": float(b), "b_err": float(b_err),
                    "inc_deg": math.degrees(math.acos(min(1.0, b / a))), "depth_max_ppt": round(1000 * depth_max, 3),
                    "depth_avg_ppt": round(1000 * depth_avg, 3), "depth_err_ppt": round(1000 * 2 * rp * rp_err, 3) if np.isfinite(rp_err) else None,
                    "t14_hours": round(t14_h, 3), "t14_err_hours": round(t14_err_h, 3), "rp_rearth": round(rp_re, 3), "rp_rearth_err": round(rp_re_err, 3),
                    "rho_fit_cgs": rho_fit, "density_ratio_fit_over_cat": rho_fit / rho_cat, "grazing": bool(b + rp > 1.0),
                    "delta_chi2_vs_flat": chi2_flat - (chi2_prior if adopt_prior else chi2_free), "n_transits": n_transits},
        "odd_even": oe, "timing_s": round(time.perf_counter() - t_start, 1),
    }
    if fit_input is not None:
        res["fit_input"] = fit_input
    res = finite_fields(res)
    jdump(out_path, res)
    return res


def write_ctoi_fields(tic: int, period: float, note: str) -> Path:
    """ExoFOP candidate fields from the audit fit; the human fills the tag and submits by hand."""
    fit = fit_step(tic, period)
    a = fit["adopted"]; tls = jload(OUT / "tls" / f"{key(tic, period)}.json")
    ev_path = next((OUT / "events" / f"{key(tic, period)}_{s}.json" for s in ("tls", "packet", "survey")
                    if (OUT / "events" / f"{key(tic, period)}_{s}.json").exists()), None)
    if ev_path is None:
        raise ValueError(f"{key(tic, period)}: an event record is required before writing CTOI fields")
    ev = jload(ev_path)["summary"]
    xm_path = OUT / f"crossmatch_{OUT.name}.json"
    xm = jload(xm_path) if xm_path.exists() else {}
    d = {
        "form_fields": {
            "target": f"TIC {tic}", "tic_id": tic, "discovery_source": "TESS",
            "period_days": a["period"], "period_err_days": a["period_err"],
            "epoch_bjd": a["epoch_bjd"], "epoch_err_days": a["t0_err"],
            "depth_ppm": round(1000 * a["depth_max_ppt"], 1), "depth_err_ppm": None if a["depth_err_ppt"] is None else round(1000 * a["depth_err_ppt"], 1),
            "duration_hours": a["t14_hours"], "duration_err_hours": a["t14_err_hours"],
            "disposition": "PC", "tag": "FILL_ME: YYYYMMDD_username_tesshunter_NNN", "candidate_name": None, "paper_url": None,
            "notes": note,
        },
        "supplementary": {
            "rp_rs": a["rp_rs"], "rp_rs_err": a["rp_rs_err"], "rp_rearth": a["rp_rearth"], "rp_rearth_err": a["rp_rearth_err"],
            "a_rs": a["a_rs"], "a_rs_err": a["a_rs_err"], "impact_parameter": a["b"], "impact_parameter_err": a["b_err"], "inclination_deg": a["inc_deg"],
            "depth_duration_averaged_ppm": round(1000 * a["depth_avg_ppt"], 1), "density_prior_adopted": fit["density_prior_adopted"],
            "delta_chi2_prior_minus_free": fit["delta_chi2_prior_minus_free"], "beta_red_noise": fit["data"]["beta_red_noise"],
            "n_transits_in_fit": a["n_transits"], "odd_even": fit["odd_even"],
            "tls_blind": {k: tls["blind"][k] for k in ("period", "SDE", "snr", "distinct_transit_count")}, "tls_verdict": tls["verdict_tls"],
            "events": {k: ev[k] for k in ("n_observed", "n_excluded", "n_kept")}, "det_kept": ev["det_kept"], "sap_kept": ev["sap_kept"],
            "stellar": fit["stellar"], "limb_darkening": fit["limb_darkening"],
        },
        "provenance": {
            "generated_utc": utc(), "fit_method": "audit_p5: batman quadratic-LD least squares on wotan-biweight-detrended SPOC/TESS-SPOC/QLP flux, all transits, per-cadence supersampling, errors x beta",
            "rules_version": RULES_VERSION,
            "catalog_versions": xm.get("catalog_stamp"), "crossmatch_status": (xm.get("per_star", {}).get(str(tic)) or {}).get("status"),
            "audit_files": [str(OUT / "tls" / f"{key(tic, period)}.json"), str(ev_path),
                            str(OUT / "neighbours" / f"tic{tic}.json"), str(OUT / "fit" / f"{key(tic, period)}.json")],
        },
        "field_source": "ExoFOP-TESS candidate guidelines (candidate_help.php): TID, discovery source, period, transit midpoint (BJD), depth (ppm), duration, tag, paper URL, initial note; optional candidate name and disposition. The human fills the tag and submits.",
    }
    # inside the repo the packet lands under docs/packets/audit_<root>; a root outside the repo
    # (a test's temporary directory) keeps its packet next to its own records
    base = (REPO / "docs" / "packets" / f"audit_{OUT.name}") if OUT.is_relative_to(REPO) else (OUT / "packets")
    out = base / key(tic, period) / "ctoi_fields.json"
    jdump(out, finite_fields(d))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# report: one JSON with everything per candidate + a markdown table on stdout
# ─────────────────────────────────────────────────────────────────────────────
def _neighbour_digest(n: dict) -> dict:
    g = n.get("gaia") or {}
    t = g.get("target") or {}
    rv = None
    if t.get("rv_amplitude_robust") is not None and t.get("radial_velocity_error") and t.get("rv_nb_transits"):
        # per-epoch error ~ quoted error x sqrt(N); noise-only peak-to-peak of N draws ~ 4 sigma
        per_epoch = t["radial_velocity_error"] * math.sqrt(t["rv_nb_transits"])
        rv = {"amplitude_robust_kms": round(t["rv_amplitude_robust"], 2), "per_epoch_error_kms": round(per_epoch, 2),
              "expected_noise_p2p_kms": round(4 * per_epoch, 2), "ratio": round(t["rv_amplitude_robust"] / (4 * per_epoch), 2),
              "n_transits": int(t["rv_nb_transits"])}
    simb = {}
    for o in (n.get("simbad") or {}).get("objects", []):
        simb.setdefault(o["main_id"], {"otype": o.get("otype"), "sp_type": o.get("sp_type"), "sep_arcsec": o.get("sep_arcsec"), "otypes": set()})
        if o.get("otypes"):
            simb[o["main_id"]]["otypes"].add(o["otypes"])
    for v in simb.values():
        v["otypes"] = sorted(v["otypes"])
    could = [x for x in g.get("neighbours", []) if x["sep_arcsec"] <= 63 and x.get("can_produce_candidate_depths_total_eclipse") and any(x["can_produce_candidate_depths_total_eclipse"])]
    return {"summary": n.get("summary"), "n_gaia": g.get("n_within_1arcmin"), "target_match": g.get("target_match"),
            "target": {k: t.get(k) for k in ("source_id", "phot_g_mean_mag", "ruwe", "phot_variable_flag", "non_single_star", "duplicated_source",
                                             "ipd_frac_multi_peak", "astrometric_excess_noise", "astrometric_excess_noise_sig", "best_class_name",
                                             "best_class_score", "sep_arcsec", "parallax", "teff_gspphot")},
            "rv": rv, "n_could_produce": len(could),
            "could_produce": [{k: x[k] for k in ("sep_arcsec", "sep_px", "G", "delta_mag", "max_observed_depth_ppt_total_eclipse",
                                                  "can_produce_candidate_depths_50pct_eclipse", "variable_flag", "vari_class")} for x in could],
            "simbad": simb, "vsx": [{k: o.get(k) for k in ("Name", "Type", "Period", "max", "min", "n_max", "sep_arcsec")} for o in (n.get("vsx") or {}).get("objects", [])],
            "nss": g.get("nss"), "candidate_depths_ppt": n.get("candidate_depths_ppt")}


def report_step() -> dict:
    cands = []
    for p in sorted((OUT / "tls").glob("tic*_P*.json")):
        t = jload(p)
        tic, per = t["tic_id"], t["survey_period"]
        ev_all = {s: jload(OUT / "events" / f"{key(tic, per)}_{s}.json")["summary"] for s in ("survey", "packet", "tls")
                  if (OUT / "events" / f"{key(tic, per)}_{s}.json").exists()}
        # the ephemeris that gives the candidate the most credit (highest kept SNR) is the one reported
        best_src = max(ev_all, key=lambda s: (ev_all[s]["det_kept"].get("snr") or -99)) if ev_all else None
        nb_p = OUT / "neighbours" / f"tic{tic}.json"
        xm = jload(OUT / "crossmatch_p5.json")["per_star"].get(str(tic)) if (OUT / "crossmatch_p5.json").exists() else None
        row = survivor_row(tic, per)
        c = {"tic_id": tic, "survey_period": per, "survey_rank": int(row.get("rank", -1)) if row else None,
             "tls": {k: t["blind"].get(k) for k in ("period", "SDE", "depth", "distinct_transit_count", "snr", "SDE_at_survey_period_max_1pct", "SDE_rank_of_survey_period", "match")},
             "tls_forced": {k: t["forced"].get(k) for k in ("period", "T0_btjd", "duration_days", "depth", "SDE", "snr", "distinct_transit_count", "odd_even_mismatch")},
             "tls_peaks": t["blind"]["peaks"][:5], "verdict_tls": t["verdict_tls"], "tls_inputs": t["inputs"],
             "events": ev_all.get(best_src) if best_src else None, "events_ephemeris_used": best_src,
             "events_by_ephemeris": {s: {k: v[k] for k in ("n_observed", "n_excluded", "n_kept")} | {"det_kept_snr": v["det_kept"].get("snr"), "det_all_snr": v["det_all"].get("snr"), "flags": v["flags"]}
                                     for s, v in ev_all.items()},
             "neighbours": _neighbour_digest(jload(nb_p)) if nb_p.exists() else None,
             "crossmatch": xm}
        cands.append(c)
    cands.sort(key=lambda c: (c["survey_rank"] if c["survey_rank"] is not None else 999))
    out = {"generated_utc": utc(), "candidates": cands}
    jdump(OUT / "audit_summary.json", out)
    print("| rank | TIC | P survey | TLS blind P | SDE | match | SDE@P | events obs/kept | SNR kept (det) | top share | p_const | neighbours could produce | xmatch |")
    print("|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---:|---|")
    for c in cands:
        e = c["events"] or {}
        dk = (e.get("det_kept") or {})
        print(f"| {c['survey_rank']} | {c['tic_id']} | {c['survey_period']:.4f} | {c['tls']['period']:.4f} | {c['tls']['SDE']:.1f} | {c['verdict_tls']} | "
              f"{c['tls']['SDE_at_survey_period_max_1pct'] if c['tls']['SDE_at_survey_period_max_1pct'] is None else round(c['tls']['SDE_at_survey_period_max_1pct'], 1)} | "
              f"{e.get('n_observed')}/{e.get('n_kept')} | {dk.get('snr')} | {dk.get('top_event_share_of_snr2')} | "
              f"{None if dk.get('p_const') is None else f'{dk['p_const']:.2g}'} | {(c['neighbours'] or {}).get('n_could_produce')} | {(c['crossmatch'] or {}).get('status')} |")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-root", type=str, default=None, help="output root, e.g. data/survey/p6 (default data/survey/p5)")
    ap.add_argument("--lc-root", type=str, default=None, help="raw light-curve store (default data/survey/audit_lc)")
    ap.add_argument("--rules", choices=["p6.2", "p7.0"], default="p6.2",
                    help="rule set: p6.2 (the frozen prompt-5/6 rules, the default, so every "
                         "P5 and P6 record reproduces) or p7.0 (the same rules with the four "
                         "prompt-7 options on)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download"); d.add_argument("--tic", type=int, nargs="+", required=True); d.add_argument("--force", action="store_true")
    pr = sub.add_parser("prepare"); pr.add_argument("--tic", type=int, required=True); pr.add_argument("--period", type=float, required=True)
    pr.add_argument("--bin-minutes", type=float, default=30.0); pr.add_argument("--window-days", type=float, default=None)
    pr.add_argument("--force", action="store_true"); pr.add_argument("--suffix", type=str, default="")
    pr.add_argument("--mask", type=str, default=None)
    fo = sub.add_parser("forced"); fo.add_argument("--tic", type=int, required=True); fo.add_argument("--period", type=float, required=True)
    fo.add_argument("--threads", type=int, default=20); fo.add_argument("--oversampling", type=int, default=5)
    fo.add_argument("--half-width", type=float, default=0.015); fo.add_argument("--bin-minutes", type=float, default=30.0)
    fo.add_argument("--window-days", type=float, default=None); fo.add_argument("--force", action="store_true")
    fo.add_argument("--suffix", type=str, default="")
    tl = sub.add_parser("tls"); tl.add_argument("--tic", type=int, required=True); tl.add_argument("--period", type=float, required=True)
    tl.add_argument("--threads", type=int, default=20); tl.add_argument("--oversampling", type=int, default=3)
    tl.add_argument("--pmin", type=float, default=0.5); tl.add_argument("--pmax", type=float, default=110.0)
    tl.add_argument("--bin-minutes", type=float, default=30.0); tl.add_argument("--window-days", type=float, default=None)
    tl.add_argument("--force", action="store_true")
    tl.add_argument("--mask", type=str, default=None, help="BTJD ranges to drop, e.g. 2680-2687,2900-2901 (documented systematics)")
    tl.add_argument("--suffix", type=str, default="", help="output suffix for a masked re-run, e.g. _masked")
    ev = sub.add_parser("events"); ev.add_argument("--tic", type=int, required=True); ev.add_argument("--period", type=float, required=True)
    ev.add_argument("--force", action="store_true"); ev.add_argument("--ephemeris", choices=["survey", "packet", "tls", "all"], default="all")
    nb = sub.add_parser("neighbours"); nb.add_argument("--tic", type=int, nargs="+", required=True); nb.add_argument("--force", action="store_true")
    xm = sub.add_parser("crossmatch"); xm.add_argument("--tic", type=int, nargs="+", required=True); xm.add_argument("--no-refresh", action="store_true")
    ft = sub.add_parser("fit"); ft.add_argument("--tic", type=int, required=True); ft.add_argument("--period", type=float, required=True)
    ft.add_argument("--force", action="store_true"); ft.add_argument("--ctoi-note", type=str, default=None)
    sub.add_parser("report")
    args = ap.parse_args(argv)
    set_roots(args.out_root, args.lc_root)
    set_rules(args.rules)

    if args.cmd == "fit":
        res = fit_step(args.tic, args.period, force=args.force)
        a = res["adopted"]
        print(f"TIC {args.tic}: P={a['period']:.5f}+/-{a['period_err']:.5f} T0={a['epoch_bjd']:.4f}+/-{a['t0_err']:.4f} "
              f"depth={a['depth_max_ppt']:.2f}+/-{a['depth_err_ppt']} ppt T14={a['t14_hours']:.2f}+/-{a['t14_err_hours']:.2f} h "
              f"Rp/Rs={a['rp_rs']:.4f}+/-{a['rp_rs_err']:.4f} b={a['b']:.2f} a/Rs={a['a_rs']:.1f} (cat {res['stellar']['a_rs_catalog']:.1f}) "
              f"prior_adopted={res['density_prior_adopted']} dchi2={res['delta_chi2_prior_minus_free']:.1f} beta={res['data']['beta_red_noise']} "
              f"n_tr={a['n_transits']} odd/even={res['odd_even'].get('sigma')} sigma; {res['timing_s']} s")
        if args.ctoi_note:
            print("ctoi fields ->", write_ctoi_fields(args.tic, args.period, args.ctoi_note))
        return

    if args.cmd == "download":
        for tic in args.tic:
            idx = download(tic, force=args.force)
            print(f"TIC {tic}: {idx['n_products']} products ({idx['n_failed']} failed) in {idx['seconds']} s")
    elif args.cmd == "prepare":
        mask = [tuple(float(x) for x in r.split("-")) for r in args.mask.split(",")] if args.mask else None
        m = prepare_step(args.tic, args.period, args.bin_minutes, args.window_days, force=args.force,
                         mask=mask, suffix=args.suffix)
        print(f"TIC {args.tic} P={args.period:.4f}: {m['n_unbinned']} unbinned -> {m['n_binned']} bins over "
              f"{m['baseline_days']:.1f} d; window {m['wotan']['window_days']:.2f} d (T14 {m['expected_t14_hours_b0']} h); "
              f"clipped: isolated {m['n_isolated_clipped']}/bins {m['n_isolated_bins_clipped']}/deep {m['n_deep_clipped']} "
              f"(> {m['deep_clip_threshold_ppt']} ppt); {m['seconds']} s -> {m['lc_npz']}")
    elif args.cmd == "forced":
        r = forced_step(args.tic, args.period, args.threads, args.oversampling, args.half_width,
                        args.bin_minutes, args.window_days, force=args.force, suffix=args.suffix)
        f = r["forced"]
        print(f"TIC {args.tic} P_survey={args.period:.4f}: forced TLS P={f['period']:.5f} T0={f['T0_btjd']:.4f} "
              f"dur={f['duration_days']:.4f} d depth={1000 * (1 - f['depth']):.2f} ppt SDE={f['SDE']:.1f} "
              f"n_tr={f['distinct_transit_count']}; {r['timing_s']['tls_forced']} s")
    elif args.cmd == "tls":
        mask = [tuple(float(x) for x in r.split("-")) for r in args.mask.split(",")] if args.mask else None
        res = tls_step(args.tic, args.period, args.threads, args.oversampling, args.pmin, args.pmax,
                       args.bin_minutes, args.window_days, force=args.force, mask=mask, suffix=args.suffix)
        b = res["blind"]
        print(f"TIC {args.tic} P_survey={args.period:.4f}: blind TLS P={b['period']:.4f} SDE={b['SDE']:.1f} "
              f"depth={1000 * (1 - b['depth']):.2f} ppt n_tr={b['distinct_transit_count']} -> {res['verdict_tls']}; "
              f"SDE@survey={b['SDE_at_survey_period_max_1pct']}; timing {res['timing_s']}")
    elif args.cmd == "events":
        sources = ["survey", "packet", "tls"] if args.ephemeris == "all" else [args.ephemeris]
        for src in sources:
            res = events_step(args.tic, args.period, force=args.force, source=src)
            s = res["summary"]; dk = s["det_kept"]; da = s["det_all"]
            print(f"[{src}] P={s['ephemeris']['period']:.5f} T0={s['ephemeris']['t0']:.4f} dur={s['ephemeris']['duration']:.3f} ({s['ephemeris']['source']}): "
                  f"predicted {s['n_predicted_in_span']}, observed {s['n_observed']}, excluded {s['n_excluded']}, kept {s['n_kept']}; "
                  f"det all: n={da.get('n')} depth={da.get('weighted_mean_depth_ppt')}+/-{da.get('err_ppt')} snr={da.get('snr')} p_const={da.get('p_const')} top_share={da.get('top_event_share_of_snr2')}; "
                  f"det kept: n={dk.get('n')} depth={dk.get('weighted_mean_depth_ppt')}+/-{dk.get('err_ppt')} snr={dk.get('snr')} snr_wo_top={dk.get('snr_without_top_event')} "
                  f"top_share={dk.get('top_event_share_of_snr2')} p_const={dk.get('p_const')}; sap kept snr={s['sap_kept'].get('snr')}; flags={s['flags']}")
            for e in res["events"]:
                if e.get("observed"):
                    print(f"   n={e['n']:>4} tc={e['tc_btjd']:.3f} s{e['sector']:>3} {e['author']:<9} cov={e['coverage_in_transit']:.2f} "
                          f"det={e['det_depth_ppt']}+/-{e['det_depth_err_ppt']} sap={e['sap_depth_ppt']}+/-{e['sap_depth_err_ppt']} "
                          f"edge={e['edge_distance_days']:.2f} desat={int(e['desat_within_one_duration'])} qfrac={e['frac_in_transit_quality_flagged']} "
                          f"ramp/depth={e['baseline_change_across_event_over_depth']} bkg={e['bkg_in_over_sector_median']} {'EXCL: ' + '; '.join(e['exclusion_reasons']) if e['excluded'] else ''}")
    elif args.cmd == "neighbours":
        for tic in args.tic:
            res = neighbours_step(tic, force=args.force)
            print(f"TIC {tic}: {res['summary']}")
    elif args.cmd == "crossmatch":
        res = crossmatch_step(args.tic, refresh=not args.no_refresh)
        for tic, r in res["per_star"].items():
            print(tic, r.get("status"), r.get("summary"))
    elif args.cmd == "report":
        report_step()


if __name__ == "__main__":
    main()
