"""Prompt 8: the native-cadence search input, built from the raw audit store.

The prompt-8 survey does not stitch MAST products through :mod:`tesshunter.ffi`.
It reads the raw per-product arrays that ``scripts/audit_p5.py download`` keeps
under ``data/survey/audit_lc/tic<id>/`` (corrected flux, SAP flux, background,
quality, one file per product per sector), and prepares them with the prompt-6
recipe in :mod:`tesshunter.audit_prep` (quality and low-precision masks,
per-product biweight, upward clip, isolated-dip clip, deep clip).  The search
then runs on that series with its own flatten switched off, so the search and
the event rules of the funnel read identical arrays.

Injection (Part 1e) happens here too, BEFORE any preprocessing and into every
flux column of every product, SAP and corrected alike: the "dip absent in SAP"
rule removed 164 events in prompt 6 and would kill any injection made only in
the corrected flux.

Everything here is pure except :func:`get_prepared`, which reads the store and
writes the stitched-cache file.  Nothing talks to MAST.  The pipeline finds
candidates; nothing here is a detection.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import lightkurve as lk
import numpy as np

from . import audit_prep
from .audit_rules import DEEP_CLIP_MAD_MULTIPLE, Q_DEFAULT
from .config import DATA_DIR

#: The shared raw light-curve store (downloaded data, not a result).
AUDIT_LC_ROOT = DATA_DIR / "survey" / "audit_lc"

#: One product per sector, in this order of preference (the audit's rule).
AUTHOR_PREFERENCE = {"SPOC": 0, "TESS-SPOC": 1, "QLP": 2}

#: Products finer than the target cadence by this ratio or more are binned to
#: it; products coarser than the target by more than it are dropped (the
#: ``ffi.bin_to_cadence`` / ``stitch_prepared`` rule, so no mixed cadence
#: ever enters one search).
CADENCE_RATIO = 1.5

PRODUCT_ARRAYS = ("time", "flux", "flux_err", "sap_flux", "sap_flux_err", "sap_bkg", "quality")


class NoStoreDataError(RuntimeError):
    """The star is not in the audit store, or nothing usable is left after the cuts."""


# ---------------------------------------------------------------------------
# Reading the store
# ---------------------------------------------------------------------------

def load_audit_products(tic: int, root: Optional[Path] = None, sector_min: Optional[int] = None,
                        sector_max: Optional[int] = None) -> list[dict]:
    """The store's products for ``tic``, one per sector (SPOC > TESS-SPOC > QLP),
    restricted to ``[sector_min, sector_max]``.

    Each product is a dict with the arrays of :data:`PRODUCT_ARRAYS` and the
    index metadata (``sector``, ``author``, ``cadence_s``, ``camera``, ``ccd``,
    ``file`` ...).  Raises :class:`NoStoreDataError` when the star has no
    ``index.json`` or no product survives the sector cut.
    """
    root = Path(root) if root is not None else AUDIT_LC_ROOT
    tdir = root / f"tic{int(tic)}"
    idx_path = tdir / "index.json"
    if not idx_path.exists():
        raise NoStoreDataError(f"TIC {tic}: not in the audit store ({tdir})")
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    best: dict[int, dict] = {}
    for p in idx.get("products", []):
        if "file" not in p:
            continue
        s = int(p["sector"])
        if sector_min is not None and s < sector_min:
            continue
        if sector_max is not None and s > sector_max:
            continue
        if p.get("author") not in AUTHOR_PREFERENCE:
            continue
        if s not in best or AUTHOR_PREFERENCE[p["author"]] < AUTHOR_PREFERENCE[best[s]["author"]]:
            best[s] = p
    out = []
    for s in sorted(best):
        p = dict(best[s])
        with np.load(tdir / p["file"]) as z:
            for k in PRODUCT_ARRAYS:
                p[k] = np.asarray(z[k], dtype=float) if k != "quality" else np.asarray(z[k]).astype(np.int64)
        out.append(p)
    if not out:
        raise NoStoreDataError(f"TIC {tic}: no product in sectors "
                               f"[{sector_min}, {sector_max}] in the audit store")
    return out


# ---------------------------------------------------------------------------
# Cadence harmonisation (bin finer products, drop coarser ones)
# ---------------------------------------------------------------------------

def bin_product(p: dict, minutes: float) -> dict:
    """Bin one product's arrays to ``minutes``; quality bits are OR-ed per bin,
    the flux error is the propagated per-cadence error (the in-bin scatter at
    >= 3 points, as ``audit_prep.bin_lc`` does for the corrected flux)."""
    t = p["time"]
    ok = np.isfinite(t)
    w = minutes / 1440.0
    idx = np.floor((t[ok] - np.nanmin(t[ok])) / w).astype(int)
    uniq, inv = np.unique(idx, return_inverse=True)
    n = np.bincount(inv)
    out = dict(p)

    def mean(a):
        a = a[ok]
        good = np.isfinite(a)
        s = np.bincount(inv[good], weights=a[good], minlength=len(uniq))
        c = np.bincount(inv[good], minlength=len(uniq))
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(c > 0, s / np.maximum(c, 1), np.nan)

    out["time"] = np.bincount(inv, weights=t[ok]) / n
    for k in ("flux", "sap_flux", "sap_bkg"):
        out[k] = mean(p[k])
    for k, fk in (("flux_err", "flux"), ("sap_flux_err", "sap_flux")):
        e = p[k][ok]
        good = np.isfinite(e)
        prop = np.sqrt(np.bincount(inv[good], weights=e[good] ** 2, minlength=len(uniq))) / np.maximum(
            np.bincount(inv[good], minlength=len(uniq)), 1)
        f = p[fk][ok]
        fg = np.isfinite(f)
        s1 = np.bincount(inv[fg], weights=f[fg], minlength=len(uniq))
        s2 = np.bincount(inv[fg], weights=f[fg] ** 2, minlength=len(uniq))
        c = np.bincount(inv[fg], minlength=len(uniq))
        with np.errstate(invalid="ignore", divide="ignore"):
            var = np.maximum(s2 / np.maximum(c, 1) - (s1 / np.maximum(c, 1)) ** 2, 0.0)
            scat = np.sqrt(var / np.maximum(c - 1, 1))
        eb = np.where(c >= audit_prep.BIN_MIN_POINTS_FOR_SCATTER, scat, prop)
        eb = np.where(eb > 0, eb, prop)
        out[k] = np.where(c > 0, eb, np.nan)
    q = np.zeros(len(uniq), dtype=np.int64)
    np.bitwise_or.at(q, inv, p["quality"][ok])
    out["quality"] = q
    out["cadence_s"] = float(minutes * 60.0)
    out["n"] = int(len(uniq))
    out["binned_from_s"] = float(p.get("cadence_s", np.nan))
    return out


def harmonise_cadence(products: list[dict], target_minutes: Optional[float]) -> tuple[list[dict], list[str]]:
    """Bin products finer than ``target_minutes`` (ratio >= 1.5) and drop products
    coarser than it (ratio > 1.5), so one search never mixes cadences."""
    if not target_minutes:
        return products, []
    kept, notes = [], []
    tgt_s = float(target_minutes) * 60.0
    for p in products:
        cad = float(p.get("cadence_s") or np.nanmedian(np.diff(p["time"])) * 86400.0)
        if tgt_s / cad >= CADENCE_RATIO:
            kept.append(bin_product(p, float(target_minutes)))
            notes.append(f"s{int(p['sector'])} {p['author']}: {cad:.0f} s binned to {tgt_s:.0f} s")
        elif cad / tgt_s > CADENCE_RATIO:
            notes.append(f"s{int(p['sector'])} {p['author']}: {cad:.0f} s coarser than {tgt_s:.0f} s; dropped")
        else:
            kept.append(p)
    return kept, notes


# ---------------------------------------------------------------------------
# Injection into every flux column, before any preprocessing
# ---------------------------------------------------------------------------

def inject_products(products: list[dict], *, period: float, t0: float, rp_rs: float, b: float,
                    a_rs: float, u: tuple[float, float], supersample: int = 7) -> tuple[list[dict], dict]:
    """Multiply a batman model into ``flux`` AND ``sap_flux`` of every product.

    The model is integrated over each product's own exposure (its cadence), so a
    2-minute SPOC product and a 200-second FFI product each see the transit
    the way the detector did.  Returns the new products and the model record
    (depth, T14, cadences touched, transits with data).
    """
    from .survey import transit_model, transit_duration_days

    out, n_in, epochs = [], 0, set()
    depth_max = 0.0
    for p in products:
        q = dict(p)
        t = p["time"]
        cad_days = float(p.get("cadence_s") or 200.0) / 86400.0
        m = np.ones_like(t)
        ok = np.isfinite(t)
        m[ok] = transit_model(t[ok], period=period, t0=t0, rp_rs=rp_rs, b=b, a_rs=a_rs, u=u,
                              exp_time_days=cad_days, supersample=supersample)
        q["flux"] = p["flux"] * m
        q["sap_flux"] = p["sap_flux"] * m
        in_tr = m < 1.0
        n_in += int(in_tr.sum())
        if in_tr.any():
            epochs.update(np.unique(np.round((t[in_tr] - t0) / period)).astype(int).tolist())
            depth_max = max(depth_max, float(1.0 - m.min()))
        out.append(q)
    info = {"period": float(period), "t0": float(t0), "rp_rs": float(rp_rs), "b": float(b),
            "a_rs": float(a_rs), "u1": float(u[0]), "u2": float(u[1]),
            "exp_time_minutes": "per product (its own cadence)",
            "depth_max_ppm": depth_max * 1e6,
            "t14_days": transit_duration_days(period, a_rs, b, rp_rs),
            "n_cadences_in_transit": n_in, "n_transits_with_data": len(epochs),
            "injected_into": ["flux", "sap_flux"]}
    return out, info


# ---------------------------------------------------------------------------
# Rotation proxy
# ---------------------------------------------------------------------------

def rotation_proxy(products: list[dict], period_min_days: float = 0.1, period_max_days: float = 30.0,
                   n_freq: int = 20000) -> dict:
    """Lomb-Scargle peak on the per-product-normalised corrected flux (quality
    masked, no detrend): peak period, its power, and the semi-amplitude of the
    best sinusoid in ppt.  A proxy, not a rotation-period measurement."""
    from astropy.timeseries import LombScargle

    T, F = [], []
    for p in products:
        t, f, q = p["time"], p["flux"], p["quality"]
        ok = np.isfinite(t) & np.isfinite(f) & ((q & audit_prep.product_bitmask(p, Q_DEFAULT)) == 0) & (f > 0)
        if ok.sum() < 50:
            continue
        T.append(t[ok]); F.append(f[ok] / np.nanmedian(f[ok]) - 1.0)
    if not T:
        return {"available": False}
    t = np.concatenate(T); f = np.concatenate(F)
    o = np.argsort(t); t, f = t[o], f[o]
    freq = np.linspace(1.0 / period_max_days, 1.0 / period_min_days, n_freq)
    ls = LombScargle(t, f)
    power = ls.power(freq)
    k = int(np.nanargmax(power))
    best_f = float(freq[k])
    params = ls.model_parameters(best_f)
    amp = float(np.hypot(params[1], params[2])) if len(params) >= 3 else float("nan")
    return {"available": True, "peak_period_days": 1.0 / best_f, "peak_power": float(power[k]),
            "semi_amplitude_ppt": 1000.0 * amp, "n_cadences": int(len(t)),
            "baseline_days": float(t[-1] - t[0]), "period_grid_days": [period_min_days, period_max_days],
            "scatter_ppt": float(1000.0 * 1.4826 * np.nanmedian(np.abs(f - np.nanmedian(f))))}


# ---------------------------------------------------------------------------
# The prepared search series
# ---------------------------------------------------------------------------

def prepare_search_input(products: list[dict], window_days: float,
                         deep_clip_mad: float = DEEP_CLIP_MAD_MULTIPLE) -> dict:
    """The prompt-6 recipe on the corrected flux, unbinned: quality and
    low-precision masks, per-product biweight, upward clip, isolated
    single-cadence dips, then the deep clip at ``deep_clip_mad`` MAD (there is
    no candidate depth before a search, so the depth term of
    ``audit_prep.clip_binned`` is zero and the MAD term is the clip)."""
    det = audit_prep.clean_and_detrend(products, window_days)
    f = det["flux"]
    r = f - 1.0
    mad = float(1.4826 * np.nanmedian(np.abs(r - np.nanmedian(r))))
    deep = r < -deep_clip_mad * mad
    keep = ~deep
    out = {k: det[k][keep] for k in ("time", "flux", "flux_err", "sector", "trend")}
    out["per_product"] = det["per_product"]
    out["counters"] = {
        "n_unbinned": int(len(det["time"])), "n_after_deep_clip": int(keep.sum()),
        "n_deep_clipped": int(deep.sum()), "deep_clip_threshold_ppt": round(1000 * deep_clip_mad * mad, 3),
        "mad_ppt": round(1000 * mad, 3), "window_days": float(window_days),
        "n_isolated_clipped": int(sum(pp.get("n_isolated_clipped", 0) for pp in det["per_product"])),
        "n_clipped_up": int(sum(pp.get("n_clipped_up", 0) for pp in det["per_product"])),
        "n_masked_quality": int(sum(pp.get("n_masked_quality", 0) for pp in det["per_product"])),
        "n_products_dropped": int(sum(1 for pp in det["per_product"] if pp.get("dropped"))),
    }
    return out


def to_lightcurve(prep: dict, products: list[dict], provenance: dict) -> lk.LightCurve:
    """An ``lk.LightCurve`` (BTJD) carrying the survey's provenance meta keys."""
    from astropy import units as u
    from astropy.time import Time

    lc = lk.LightCurve(
        time=Time(np.asarray(prep["time"], dtype=float), format="btjd", scale="tdb"),
        flux=np.asarray(prep["flux"], dtype=float) * u.dimensionless_unscaled,
        flux_err=np.asarray(prep["flux_err"], dtype=float) * u.dimensionless_unscaled,
    )
    lc.meta["SECTOR"] = "multi"
    lc.meta["TESSHUNTER_PROVENANCE"] = provenance.get("products", [])
    lc.meta["TESSHUNTER_UNITS"] = provenance.get("units_used", [])
    lc.meta["TESSHUNTER_INGEST"] = provenance.get("ingest", [])
    lc.meta["TESSHUNTER_SECTOR"] = np.asarray(prep["sector"])
    return lc


def build_prepared(tic: int, cfg, products: list[dict], injection_info: Optional[dict] = None,
                   cadence_notes: Optional[list[str]] = None) -> tuple[lk.LightCurve, dict]:
    """Prepare (already harmonised, possibly injected) products into the search
    series and its provenance record."""
    t0 = time.perf_counter()
    prep = prepare_search_input(products, cfg.audit_window_days)
    rot = rotation_proxy(products) if cfg.rotation_proxy else {"available": False, "reason": "off"}
    units = sorted({int(p["sector"]) for p in products})
    prov = {
        "tic_id": int(tic), "source": "audit_lc", "preprocess": "audit_prep",
        "products": [{"unit": int(p["sector"]), "author": p["author"], "cadence_s": float(p["cadence_s"]),
                      "camera": p.get("camera"), "ccd": p.get("ccd"), "file": p.get("file"),
                      "binned_from_s": p.get("binned_from_s")} for p in products],
        "units_used": units, "units_all": units, "fallback_events": [],
        "n_products_downloaded": len(products), "cadence_notes": cadence_notes or [],
        "ingest": prep["per_product"], "counters": prep["counters"],
        "ingest_key": cfg.ingest_key(),
        "ingest_config": {k: getattr(cfg, k) for k in cfg.INGEST_FIELDS + cfg.INGEST_FIELDS_P8},
        "rotation_proxy": rot,
        "n_cadences": int(len(prep["time"])),
        "baseline_days": float(prep["time"].max() - prep["time"].min()) if len(prep["time"]) else 0.0,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "prepare_s": time.perf_counter() - t0,
        "injected": injection_info is not None,
    }
    prov["ingest_config"]["authors"] = list(prov["ingest_config"]["authors"])
    lc = to_lightcurve(prep, products, prov)
    return lc, prov


def get_prepared(tic: int, cfg, *, cache_dir: Optional[Path] = None, refresh: bool = False,
                 lc_root: Optional[Path] = None, injection: Optional[dict] = None,
                 star: Optional[dict] = None) -> tuple[lk.LightCurve, dict, dict]:
    """The prompt-8 counterpart of :func:`tesshunter.survey.get_stitched`.

    Without an injection the prepared series is cached under the config's
    ingest key like a stitched curve (so ``--prefetch`` and ``--resume`` work
    unchanged).  With an injection the products are read, injected and
    prepared afresh and nothing is cached.
    """
    from .survey import (a_over_rs, limb_darkening_for_teff, load_stitched, save_stitched,
                         stitched_path)

    star = star or {}
    path = stitched_path(tic, cfg, cache_dir)
    if injection is None and path.exists() and path.with_suffix(".json").exists() and not refresh:
        t0 = time.perf_counter()
        lc, prov = load_stitched(path)
        return lc, prov, {"cache_hit": True, "path": str(path), "load_s": time.perf_counter() - t0,
                          "download_s": 0.0, "stitch_s": 0.0}
    t0 = time.perf_counter()
    products = load_audit_products(tic, lc_root, sector_min=cfg.sector_min)
    products, notes = harmonise_cadence(products, cfg.target_cadence_minutes)
    if not products:
        raise NoStoreDataError(f"TIC {tic}: no product left after the cadence rule ({notes})")
    inj_info = None
    if injection is not None:
        t_all = np.concatenate([p["time"][np.isfinite(p["time"])] for p in products])
        period = float(injection["period"])
        t_inj = float(injection["t0"]) if injection.get("t0") is not None \
            else float(t_all.min()) + float(injection.get("t0_frac", 0.5)) * period
        radius = float(star.get("radius_rsun") or 1.0)
        mass = float(star.get("mass_msun") or radius)
        a_rs = float(injection.get("a_rs") or a_over_rs(period, mass, radius))
        u = (float(injection["u1"]), float(injection["u2"])) if "u1" in injection \
            else limb_darkening_for_teff(star.get("teff_k"))
        products, inj_info = inject_products(products, period=period, t0=t_inj, rp_rs=float(injection["rp_rs"]),
                                             b=float(injection["b"]), a_rs=a_rs, u=u)
    t1 = time.perf_counter()
    lc, prov = build_prepared(tic, cfg, products, inj_info, notes)
    t2 = time.perf_counter()
    if injection is None:
        save_stitched(path, lc, prov)
    info = {"cache_hit": False, "path": str(path) if injection is None else None, "load_s": 0.0,
            "download_s": t1 - t0, "stitch_s": t2 - t1, "injection_model": inj_info}
    return lc, prov, info
