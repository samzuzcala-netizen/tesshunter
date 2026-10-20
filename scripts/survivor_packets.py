"""Prompt 4, steps 3 and 4: the deferred expensive steps for the ranked survivors.

Three modes, run in this order (each writes one JSON per candidate under
``--out`` so ``scripts/rank_survivors.py --expensive`` can merge them):

1. ``--refresh-catalogs``: re-download all six hard-stop catalogs now
   (ignores the 7-day cache) and record the stamp.
2. ``--crossmatch``: fresh hard-stop check on EVERY survivor star (one TIC
   cone query per star for the 21-arcsec neighbour test); writes / updates
   the ``crossmatch`` key of each candidate's JSON.
3. ``--expensive --top N``: for the top N ranked survivors, in one
   subprocess per candidate with a wall-clock kill: a targeted re-search of
   the whole stitched curve in a +/-2% period window (so the limb-darkened
   fit, odd/even, secondary and per-unit folds use every transit), the
   centroid test on target pixel files from EVERY sector with one (SPOC,
   then TESS-SPOC, then a TESScut cutout), the TIC contamination check,
   TRICERATOPS with the real TIC / Gaia neighbours, the final verdict, and
   the full packet (:func:`tesshunter.packet.build_packet`).

Nothing here submits anything anywhere. The pipeline finds candidates.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tempfile import TemporaryDirectory

for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
             "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_var, "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

REPO = Path(__file__).resolve().parent.parent
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data" / "cache" / "lightkurve"))
sys.path.insert(0, str(REPO / "src"))

DEFAULT_OUT = REPO / "data" / "survey" / "p4" / "expensive"
DEFAULT_PACKETS = REPO / "docs" / "packets" / "survey_v1"
CUTOUT_PX = 21            # same size TRICERATOPS asks for, so the cutouts share one cache
CUTOUT_TIMEOUT_S = 240.0  # hard limit per TESScut download (a stalled transfer is skipped)
PERIOD_WINDOW = 0.05      # +/-5% re-search window on the whole stitch
MATCH_TOL = 0.02


def _key(tic: int, period: float) -> str:
    return f"tic{int(tic)}_P{float(period):.4f}"


def _write_json(path: Path, payload: dict) -> None:
    from tesshunter.survey import write_json_atomic
    write_json_atomic(path, payload)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ── catalogs ──────────────────────────────────────────────────────────────────

def refresh_catalogs(out_dir: Path) -> str:
    import socket
    socket.setdefaulttimeout(300.0)
    from tesshunter.catalog_crossmatch import KnownObjectCatalog
    t0 = time.perf_counter()
    cat = KnownObjectCatalog.load(refresh=True)
    stamp = cat.stamp()
    man = cat.manifest()
    man["refresh_seconds"] = round(time.perf_counter() - t0, 1)
    man["rows_per_source"] = {n: int(len(df)) for n, df in cat.tables.items()}
    man["unique_tic_per_source"] = {n: int(df["tic_id"].nunique()) for n, df in cat.tables.items()}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir.parent / "catalog_versions_p4.json").write_text(json.dumps(man, indent=1, default=str), encoding="utf-8")
    print(f"catalogs refreshed in {man['refresh_seconds']} s: {stamp}")
    print(json.dumps(man["rows_per_source"]))
    return stamp


def crossmatch_all(survivors: Path, out_dir: Path, targets: dict, retries: int = 1) -> None:
    """Fresh hard stop on every survivor star; one JSON (crossmatch key) per candidate."""
    import socket
    socket.setdefaulttimeout(300.0)
    from tesshunter.catalog_crossmatch import CatalogFetchError, KnownObjectCatalog
    cat = KnownObjectCatalog.load()          # served from the cache refresh_catalogs just made
    stamp = cat.stamp()
    rows = list(csv.DictReader(open(survivors, newline="", encoding="utf-8")))
    out_dir.mkdir(parents=True, exist_ok=True)
    per_star: dict[int, dict] = {}
    n_rej = n_flag = n_err = 0
    t0 = time.perf_counter()
    for r in rows:
        tic = int(r["tic_id"])
        if tic not in per_star:
            tr = targets.get(tic) or {}
            ra = float(tr["ra_deg"]) if tr.get("ra_deg") else None
            dec = float(tr["dec_deg"]) if tr.get("dec_deg") else None
            rec = None
            for attempt in range(retries + 1):
                try:
                    hs = cat.check(tic, ra, dec, resolve_neighbours=True)
                    rec = hs.to_dict()
                    rec["catalog_stamp"] = stamp
                    rec["checked_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    break
                except CatalogFetchError as exc:
                    rec = {"status": "ERROR", "summary": f"neighbour lookup failed: {exc}"[:300],
                           "catalog_stamp": stamp, "tic_id": tic}
            per_star[tic] = rec
            if rec["status"] == "REJECT":
                n_rej += 1
            elif rec["status"] == "FLAG":
                n_flag += 1
            elif rec["status"] == "ERROR":
                n_err += 1
        path = out_dir / f"{_key(tic, float(r['period_days']))}.json"
        d = _read_json(path)
        d.update({"tic_id": tic, "period_days": float(r["period_days"]), "planet_num": int(r["planet_num"]),
                  "crossmatch": per_star[tic]})
        _write_json(path, d)
    print(f"cross-matched {len(per_star)} star(s) / {len(rows)} candidate(s) in {time.perf_counter() - t0:.0f} s: "
          f"REJECT {n_rej}, FLAG {n_flag}, ERROR {n_err}; stamp {stamp}")


# ── one candidate (child process) ─────────────────────────────────────────────

def _pixel_plan(lk, tic: int, coord, log: list) -> tuple[dict, set]:
    """TWO MAST calls per star, not two per sector: one product search for
    every pipeline TPF (SPOC 2-min, TESS-SPOC FFI) and one TESScut sector
    list. The first design searched per sector and per author (90 MAST
    queries for a 45-sector star); eight workers doing that in parallel
    stalled the TESScut service for everyone (P4, section 5 of the handoff).
    Returns ({sector: (author, search_row)}, {sectors with a cutout})."""
    import warnings
    by_sector: dict = {}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sr = lk.search_targetpixelfile(f"TIC {tic}", mission="TESS")
        tab = sr.table if len(sr) else None
        if tab is not None:
            authors = tab["author"] if "author" in tab.colnames else tab["provenance_name"]
            for i in range(len(tab)):
                a = str(authors[i]).upper()
                if a not in ("SPOC", "TESS-SPOC"):
                    continue
                try:
                    s = int(tab["sequence_number"][i])
                except Exception:
                    continue
                rank = 0 if a == "SPOC" else 1
                if s not in by_sector or rank < by_sector[s][0]:
                    by_sector[s] = (rank, a, i)
    except Exception as exc:
        log.append(f"TPF search: {str(exc)[:160]}")
        sr = None
    plan = {s: (a, sr[i]) for s, (rank, a, i) in by_sector.items()}
    cut_sectors: set = set()
    try:
        from astroquery.mast import Tesscut
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            secs = Tesscut.get_sectors(coordinates=coord)
        cut_sectors = {int(s) for s in secs["sector"]} if secs is not None and len(secs) else set()
    except Exception as exc:
        log.append(f"TESScut sector list: {str(exc)[:160]}")
    return plan, cut_sectors


def _tesscut_tpf(lk, coord, sector: int, log: list):
    """A TESScut cutout for one sector, cached under the lightkurve cache's
    ``tesscut`` folder with lightkurve's own file name so TRICERATOPS's later
    request for the same sector is served from disk."""
    import warnings
    from pathlib import Path as _P
    from astroquery.mast import Tesscut
    cache = (_P(os.environ["LIGHTKURVE_CACHE"]) / "tesscut").resolve()
    cache.mkdir(parents=True, exist_ok=True)
    ra, dec = float(coord.ra.deg), float(coord.dec.deg)
    pattern = f"tess-s{int(sector):04d}-*_{ra:.6f}_{dec:.6f}_{CUTOUT_PX}x{CUTOUT_PX}_astrocut.fits"
    existing = sorted(cache.glob(pattern))
    path = existing[0] if existing else None
    if path is None:
        # A transfer that trickles never trips the idle-socket timeout (one
        # sector-104 cutout sat for over an hour in the P4 run), so the
        # download runs in a thread with a hard time limit and the sector is
        # skipped when it expires.
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as _Timeout

        def _dl():
            # Astroquery names its ZIP to one-second precision. Each request
            # needs a private directory even when different stars are fetched.
            # The worker owns cleanup so a timeout cannot remove a live transfer.
            with TemporaryDirectory(prefix=".tesscut-download-", dir=cache) as directory:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    res = Tesscut.download_cutouts(coordinates=coord, size=CUTOUT_PX,
                                                  sector=int(sector), path=directory)
                if res is None or len(res) == 0:
                    return None
                downloaded = _P(str(res["Local Path"][0])).resolve()
                if downloaded.parent != _P(directory).resolve() or not downloaded.match(pattern):
                    raise ValueError("TESScut returned a file outside this request or for a different target/sector")
                destination = cache / downloaded.name
                if not destination.exists():
                    try:
                        downloaded.replace(destination)
                    except OSError:
                        # Another request for this same cutout may have just
                        # published it. Never replace an already-open FITS file.
                        if not destination.exists():
                            raise
                return destination
        ex = ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(_dl)
        try:
            path = fut.result(timeout=CUTOUT_TIMEOUT_S)
        except _Timeout:
            log.append(f"s{sector} TESScut: download exceeded {CUTOUT_TIMEOUT_S:.0f} s; sector skipped")
            return None
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
        if path is None:
            return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tpf = lk.TessTargetPixelFile(str(path))
    # a cutout has no pipeline aperture: use a threshold mask around the
    # target pixel so the centroid follows the target, not the field
    try:
        mask = tpf.create_threshold_mask(threshold=3.0, reference_pixel="center")
        if mask.sum() < 2:
            mask = tpf.create_threshold_mask(threshold=1.5, reference_pixel="center")
        _orig = type(tpf).estimate_centroids
        tpf.estimate_centroids = (lambda _m=mask, _t=tpf, _f=_orig, **kw: _f(_t, aperture_mask=_m))
    except Exception as exc:
        log.append(f"s{sector} tesscut mask: {str(exc)[:120]}")
    return tpf


def _tpf_for_sector(lk, tic: int, sector: int, coord, log: list, plan: dict, cut_sectors: set) -> tuple[object | None, str]:
    """SPOC 2-min TPF, else TESS-SPOC FFI TPF, else a TESScut cutout, from the per-star plan."""
    import warnings
    if int(sector) in plan:
        author, row = plan[int(sector)]
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tpf = row.download()
            if tpf is not None:
                return tpf, author
        except Exception as exc:
            log.append(f"s{sector} {author}: {str(exc)[:120]}")
    if int(sector) in cut_sectors:
        try:
            tpf = _tesscut_tpf(lk, coord, int(sector), log)
            if tpf is not None:
                return tpf, "TESScut"
        except Exception as exc:
            log.append(f"s{sector} TESScut: {str(exc)[:120]}")
    return None, "none"


def centroid_all_sectors(tic: int, ra: float, dec: float, sectors: list[int], period: float, t0: float,
                         duration: float, max_sectors: int, tesscut_only: bool = False) -> dict:
    """The P0 per-TPF centroid measurement on every sector with pixel data,
    combined with inverse-variance weights (the same combination rule as
    ``run_centroid_check``, without its two-sector cap)."""
    import warnings
    import numpy as np
    import lightkurve as lk
    from astropy.coordinates import SkyCoord
    from tesshunter.centroid import _measure_tpf, _pixel_scale, _SHIFT_FLAG_PX, _SIGMA_THRESHOLD

    px = _pixel_scale("TESS")
    coord = SkyCoord(float(ra), float(dec), unit="deg")
    log: list[str] = []
    per_sector = []
    use = [int(s) for s in sectors][:max_sectors]
    t_start = time.perf_counter()
    plan, cut_sectors = _pixel_plan(lk, tic, coord, log)
    if tesscut_only:
        # the TESS-SPOC TPF download hung twice for TIC 201232256 (P4); the
        # cutouts come from a different service and carry the same pixels
        log.append(f"tesscut_only: {len(plan)} pipeline TPF sector(s) ignored")
        plan = {}
    log.append(f"pixel plan: {len(plan)} pipeline TPF sector(s) ({sorted(plan)[:12]}), "
               f"{len(cut_sectors)} TESScut sector(s); plan took {time.perf_counter() - t_start:.0f} s")
    for s in use:
        tpf, source = _tpf_for_sector(lk, tic, s, coord, log, plan, cut_sectors)
        if tpf is None:
            per_sector.append({"sector": s, "source": source, "available": False, "note": "no pixel data"})
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                m = _measure_tpf(tpf, period, t0, duration, px)
            per_sector.append({"sector": s, "source": source, "available": bool(m.available),
                               "col_shift_px": m.col_shift_px, "row_shift_px": m.row_shift_px,
                               "total_shift_px": m.total_shift_px, "shift_err_px": m.shift_err_px,
                               "sigma": m.sigma, "n_in": m.n_in_transit, "n_out": m.n_out_transit,
                               "flagged": bool(m.flagged), "note": m.note[:200]})
        except Exception as exc:
            per_sector.append({"sector": s, "source": source, "available": False, "note": str(exc)[:200]})
        finally:
            del tpf
    valid = [m for m in per_sector if m.get("available") and (m.get("n_in") or 0) >= 3
             and (m.get("n_out") or 0) >= 10 and (m.get("shift_err_px") or 0) > 0]
    out = {"available": False, "n_sectors_requested": len(use), "n_sectors_with_pixels": sum(1 for m in per_sector if m.get("source") != "none"),
           "n_sectors_used": len(valid), "sectors_used": [m["sector"] for m in valid],
           "sources": {k: sum(1 for m in valid if m["source"] == k) for k in ("SPOC", "TESS-SPOC", "TESScut")},
           "per_sector": per_sector, "log": log[:40], "seconds": round(time.perf_counter() - t_start, 1),
           "pixel_scale_arcsec": px, "method": "P0 in/out-of-transit median centroid per TPF, inverse-variance combined over sectors"}
    if not valid:
        out["note"] = "no sector gave a usable centroid measurement"
        return out
    w = np.array([1.0 / m["shift_err_px"] ** 2 for m in valid])
    col = float(np.sum(w * np.array([m["col_shift_px"] for m in valid])) / w.sum())
    row = float(np.sum(w * np.array([m["row_shift_px"] for m in valid])) / w.sum())
    tot = float(np.hypot(col, row))
    err = float(np.sqrt(1.0 / w.sum()))
    sig = tot / max(err, 1e-9)
    n_flag_sectors = sum(1 for m in valid if m["flagged"])
    out.update({"available": True, "col_shift_px": col, "row_shift_px": row, "total_shift_px": tot,
                "shift_arcsec": tot * px, "shift_err_px": err, "sigma": sig,
                "n_in_transit": int(sum(m["n_in"] for m in valid)), "n_out_transit": int(sum(m["n_out"] for m in valid)),
                "flagged": bool(tot > _SHIFT_FLAG_PX or sig > _SIGMA_THRESHOLD),
                "n_sectors_flagged_individually": n_flag_sectors,
                "note": (f"Centroid shift (weighted over {len(valid)} sectors): dcol = {col:+.3f} px, drow = {row:+.3f} px, "
                         f"total = {tot:.3f} px ({tot * px:.1f} arcsec), significance = {sig:.1f} sigma; "
                         f"{n_flag_sectors} of {len(valid)} sectors flagged on their own.")})
    return out


def run_one(job: dict) -> dict:
    import socket
    socket.setdefaulttimeout(300.0)
    import logging
    logging.basicConfig(level=logging.WARNING)
    import numpy as np
    from tesshunter import fpp as fppmod, packet, stellar as stmod, survey
    from tesshunter.catalog_crossmatch import CatalogFetchError, KnownObjectCatalog
    from tesshunter.contamination import run_contamination_check
    from tesshunter.pipeline import search_light_curve
    from tesshunter.vetting import apply_pixel_checks, vetting_result_from_dict

    tic = int(job["tic_id"])
    P_in = float(job["period_days"])

    def _num(v):
        try:
            x = float(v)
            return x if x == x else None
        except (TypeError, ValueError):
            return None           # CSV blanks ('') for a missing TIC mass
    target = {k: (_num(v) if k in ("radius_rsun", "mass_msun", "teff_k", "tmag", "contamination_ratio_used",
                                   "contamination_ratio", "ra_deg", "dec_deg") else v)
              for k, v in (job.get("target") or {}).items()}
    out = {"tic_id": tic, "period_days": P_in, "planet_num": int(job.get("planet_num", 0)), "rank": job.get("rank"),
           "status": "ok", "error": None, "timings": {}, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    t_all = time.perf_counter()
    try:
        cfg = survey.get_config("survey_v1")
        lc_raw, prov, _info = survey.get_stitched(tic, cfg, allow_download=False)
        units = [int(u) for u in prov.get("units_used", [])]
        authors = [str(p.get("author") or "") for p in prov.get("products", [])]
        main_author = max(set(authors), key=authors.count) if authors else "QLP"

        # stellar parameters: the TIC (cached JSON), else the survey row
        t1 = time.perf_counter()
        st = stmod.fetch_tic_params(tic)
        st_source = "tic"
        if st is None or st.radius is None:
            st = stmod.StellarParams.from_survey_row(target, tic)
            st_source = "survey_row"
        if st.ra is None and target.get("ra_deg"):
            st.ra, st.dec = float(target["ra_deg"]), float(target["dec_deg"])
        out["stellar_source"] = st_source
        out["timings"]["stellar"] = time.perf_counter() - t1

        # fresh cross-match (repeated here so the packet carries it)
        t1 = time.perf_counter()
        try:
            cat = KnownObjectCatalog.load()
            hs = cat.check(tic, st.ra, st.dec, resolve_neighbours=True)
            xm = hs.to_dict()
            xm["catalog_stamp"] = cat.stamp()
        except CatalogFetchError as exc:
            xm = {"status": "ERROR", "summary": f"neighbour lookup failed: {exc}"[:300], "tic_id": tic}
        xm["checked_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        out["crossmatch"] = xm
        out["timings"]["crossmatch"] = time.perf_counter() - t1

        # Targeted re-search of the WHOLE stitch in a +/-5% window so the fit,
        # odd/even, secondary and per-unit folds use every transit. A narrow
        # periodogram has no baseline for the SDE term of the composite score
        # (the survey's gate 4 rejected an SNR-57 stitch candidate this way),
        # so that gate is disabled here: the candidate already passed the full
        # search's gates. If the narrow search still does not return it, the
        # ORIGINAL sub-search (same mask, period range and settings) is
        # reproduced exactly, which is deterministic.
        t1 = time.perf_counter()
        kw = cfg.search_kwargs()
        kw.update({"period_min": P_in * (1 - PERIOD_WINDOW), "period_max": P_in * (1 + PERIOD_WINDOW),
                   "max_planets": 1, "time_budget_s": 900.0, "min_composite_score": 0.0})
        prov_small = {k: prov.get(k) for k in ("products", "units_used", "units_all", "fallback_events",
                                                 "n_products_downloaded")}

        def _closest(planets):
            return min(planets, key=lambda p: abs(float(p["period_days"]) / P_in - 1.0)) if planets else None

        scope = "stitch_narrow"
        res = search_light_curve(lc_raw, target=tic, mission="TESS", n_sectors=len(units) or None,
                                 provenance=prov_small, stellar_params=st, target_label=f"TIC {tic} stitch refit",
                                 stellar_radius_rsun=st.radius, **kw)
        d = res.to_dict()
        cand = _closest(d["planets"])
        out["refit_attempts"] = [{"scope": scope, "n_planets": len(d["planets"]),
                                  "periods": [round(float(p["period_days"]), 5) for p in d["planets"]]}]
        if cand is None or abs(float(cand["period_days"]) / P_in - 1.0) > MATCH_TOL:
            scope = "original_search"
            plan = {p["label"]: p for p in survey.plan_searches(lc_raw, cfg)}
            item = plan.get(str(job.get("search") or ""))
            if item is not None:
                sub = lc_raw[item["mask"]] if not item["mask"].all() else lc_raw
                kw2 = cfg.search_kwargs()
                kw2.update({"period_min": item["period_min"], "period_max": item["period_max"],
                            "time_budget_s": max(900.0, float(item["budget_s"]))})
                res = search_light_curve(sub, target=tic, mission="TESS", n_sectors=len(units) or None,
                                         provenance=prov_small, stellar_params=st,
                                         target_label=f"TIC {tic} {item['label']} reproduction",
                                         stellar_radius_rsun=st.radius, **kw2)
                d = res.to_dict()
                cand = _closest(d["planets"])
                out["refit_attempts"].append({"scope": scope, "label": item["label"], "n_planets": len(d["planets"]),
                                              "periods": [round(float(p["period_days"]), 5) for p in d["planets"]]})
        out["timings"]["refit_search"] = time.perf_counter() - t1
        out["refit_scope"] = scope
        if cand is None or abs(float(cand["period_days"]) / P_in - 1.0) > MATCH_TOL:
            out["status"] = "not_recovered"
            out["error"] = (f"targeted re-search found {len(d['planets'])} candidate(s), none within "
                            f"{100 * MATCH_TOL:.0f}% of P = {P_in:.5f} d "
                            f"({[round(float(p['period_days']), 4) for p in d['planets']]})")
            out["timings"]["total"] = time.perf_counter() - t_all
            return out
        num = int(cand["planet_num"])
        fit = cand.get("fit") or {}
        vet = next((v for v in d["vetting"] if int(v.get("planet_num", 0)) == num), None)
        out["verdict_lc_only"] = cand.get("verdict")
        out["refit"] = {k: cand.get(k) for k in ("period_days", "epoch_btjd", "duration_days", "depth_ppt", "depth_source",
                                                  "snr", "n_transits_observed", "rp_rs", "a_rs", "impact_b", "rp_rearth",
                                                  "a_rs_inconsistent", "verdict", "harmonic_label")}
        out["refit"]["fit"] = {k: fit.get(k) for k in (
            "success", "period", "period_err", "t0", "t0_err", "rp_rs", "rp_rs_err", "a_rs", "a_rs_err", "b", "b_err",
            "duration_days", "duration_err", "depth_ppt", "depth_err", "depth_err_white", "depth_mean_ppt",
            "rp_rearth", "rp_rearth_err", "rp_rjup", "rp_rjup_err", "rho_star_fit_cgs", "rho_star_cat_cgs",
            "a_rs_star", "density_ratio", "density_dchi2", "density_dchi2_eff", "beta_red_noise",
            "a_rs_inconsistent", "density_prior_adopted", "grazing", "rp_rs_constrained", "n_transits",
            "n_in_transit", "delta_bic", "ld_source", "odd_even")}
        out["refit"]["flags_high"] = list((vet or {}).get("flags_high") or [])
        out["refit"]["flags_medium"] = list((vet or {}).get("flags_medium") or [])
        P = float(cand["period_days"])
        T0 = float(fit.get("t0") if fit.get("success") and fit.get("t0") is not None else cand["epoch_btjd"])
        dur = float(fit.get("duration_days") or cand["duration_days"]) if fit.get("success") else float(cand["duration_days"])
        depth_ppt = float(cand["depth_ppt"])

        # centroid: every sector with pixel data
        t1 = time.perf_counter()
        cen = None
        if not job.get("no_centroid") and st.ra is not None:
            try:
                cen = centroid_all_sectors(tic, st.ra, st.dec, units, P, T0, dur, int(job.get("max_centroid_sectors", 40)),
                                           tesscut_only=bool(job.get("tesscut_only")))
            except Exception as exc:
                cen = {"available": False, "note": f"centroid stage failed: {exc}"[:300]}
        out["centroid"] = cen
        out["timings"]["centroid"] = time.perf_counter() - t1

        # contamination
        t1 = time.perf_counter()
        con = None
        if st.ra is not None:
            try:
                con = run_contamination_check(st.ra, st.dec, st.tmag or 12.0, depth_ppt)
            except Exception as exc:
                con = None
                out["contamination_error"] = str(exc)[:200]
        out["contamination"] = ({k: v for k, v in con.__dict__.items() if not k.endswith("neighbours")} if con else None)
        out["timings"]["contamination"] = time.perf_counter() - t1

        # TRICERATOPS
        t1 = time.perf_counter()
        fpp_res = None
        if not job.get("no_fpp"):
            lc = res.lc_clean
            fpp_res = fppmod.run_fpp(
                tic, units[:3], np.asarray(lc.time.value, float), np.asarray(lc.flux.value, float), None,
                period=P, t0=T0, duration=dur, depth_frac=depth_ppt / 1000.0,
                exp_time_days=cfg.bin_minutes / 1440.0, tmag=st.tmag, aperture="auto", author=main_author,
                n_draws=int(job.get("n_draws", 100_000)), red_noise_beta=fit.get("beta_red_noise"),
                ra=st.ra, dec=st.dec,
            )
        out["fpp"] = fpp_res.to_dict() if fpp_res is not None else None
        out["timings"]["fpp"] = time.perf_counter() - t1

        # final verdict
        verdict_final = cand.get("verdict")
        if vet is not None and vet.get("result"):
            vr = vetting_result_from_dict(vet["result"])
            verdict_final = apply_pixel_checks(vr, cen, con, fpp=fpp_res)
            vet["verdict_lc_only"] = vet.get("verdict")
            vet["verdict"] = verdict_final
            vet["flags_high"] = list(vr.high_risk_flags)
            vet["flags_medium"] = list(vr.medium_flags)
            vet["notes"] = list(vr.notes)
            cand["verdict"] = verdict_final
        out["verdict_final"] = verdict_final
        out["flags_high_final"] = list((vet or {}).get("flags_high") or [])
        out["fpp_blocks_packet"] = bool(fpp_res is not None and fpp_res.blocks_packet)

        # packet
        t1 = time.perf_counter()
        d["stellar"] = st.to_dict()
        d["crossmatch"] = {"status": xm.get("status"), "summary": xm.get("summary"),
                           "catalog_versions": xm.get("catalog_stamp"), "hard_stop": xm}
        d["survey_candidate"] = {k: job.get(k) for k in ("rank", "score", "stitch_snr", "stitch_n_transits", "search",
                                                          "snr", "verdict", "s_snr", "s_ntr", "s_fpp", "s_rho")}
        pk_dir = Path(job["packet_dir"])
        summary = packet.build_packet(result=d, planet_num=num, lc_clean=res.lc_clean, stellar=st, fpp=fpp_res,
                                      centroid=cen, contamination=con, out_dir=pk_dir, label=f"TIC {tic}",
                                      notes=(f"Survey rank {job.get('rank')} (frozen score {job.get('score')}); "
                                             f"survey stitch SNR {job.get('stitch_snr')}, {job.get('stitch_n_transits')} transits."))
        payload = {"search": d, "planet_num": num, "centroid": cen, "contamination": out["contamination"],
                   "fpp": out["fpp"], "crossmatch": xm, "packet": summary, "job": job}
        (pk_dir / "result.json").write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
        out["packet_dir"] = str(pk_dir)
        out["packet"] = {k: summary.get(k) for k in ("verdict", "fpp", "nfpp", "fpp_blocks_packet", "completeness")}
        out["timings"]["packet"] = time.perf_counter() - t1
    except Exception as exc:
        out["status"] = "error"
        out["error"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-2000:]}"
    out["timings"]["total"] = time.perf_counter() - t_all
    return out


# ── orchestration (parent) ────────────────────────────────────────────────────

def run_expensive(survivors: Path, out_dir: Path, packets_dir: Path, targets: dict, top: int, workers: int,
                  timeout_s: float, retries: int, force: bool, n_draws: int, max_centroid_sectors: int,
                  no_fpp: bool, no_centroid: bool, tesscut_only: bool = False) -> None:
    rows = list(csv.DictReader(open(survivors, newline="", encoding="utf-8")))
    rows = [r for r in rows if r.get("rank") and int(float(r["rank"])) <= top]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "jobs").mkdir(exist_ok=True)
    (out_dir / "logs").mkdir(exist_ok=True)
    jobs = []
    for r in rows:
        key = _key(int(r["tic_id"]), float(r["period_days"]))
        res_path = out_dir / f"{key}.json"
        existing = _read_json(res_path)
        if existing.get("status") == "ok" and existing.get("packet_dir") and not force:
            continue
        job = {k: r.get(k) for k in ("tic_id", "period_days", "planet_num", "rank", "score", "stitch_snr",
                                     "stitch_n_transits", "search", "snr", "verdict", "s_snr", "s_ntr", "s_fpp", "s_rho")}
        job.update({"tic_id": int(r["tic_id"]), "period_days": float(r["period_days"]),
                    "target": targets.get(int(r["tic_id"])) or {}, "packet_dir": str(packets_dir / key),
                    "n_draws": n_draws, "max_centroid_sectors": max_centroid_sectors,
                    "no_fpp": no_fpp, "no_centroid": no_centroid, "tesscut_only": tesscut_only, "key": key,
                    "crossmatch_prev": existing.get("crossmatch")})
        jobs.append(job)
    print(f"{len(jobs)} candidate(s) to run of {len(rows)} in the top {top}, {workers} worker(s), timeout {timeout_s:.0f} s",
          flush=True)

    def _one(job: dict, attempt: int) -> tuple[str, str, float]:
        key = job["key"]
        jp = out_dir / "jobs" / f"{key}.json"
        rp = out_dir / f"{key}.json"
        lp = out_dir / "logs" / f"{key}.log"
        jp.write_text(json.dumps(job, indent=1, default=str), encoding="utf-8")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        t0 = time.perf_counter()
        with open(lp, "a", encoding="utf-8") as fh:
            fh.write(f"\n=== attempt {attempt} {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} ===\n")
            fh.flush()
            proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--one", str(jp), "--result", str(rp)],
                                    stdout=fh, stderr=subprocess.STDOUT, env=env)
            try:
                rc = proc.wait(timeout=timeout_s)
                status = "ok" if rc == 0 else "error"
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                status = "timeout"
        wall = time.perf_counter() - t0
        rec = _read_json(rp)
        if not rec or rec.get("started_utc") is None or status == "timeout":
            rec = rec or {}
            rec.update({"tic_id": job["tic_id"], "period_days": job["period_days"], "planet_num": job["planet_num"],
                        "status": status if status != "ok" else "error",
                        "error": f"child exited rc={rc}" if status != "timeout" else f"timeout after {timeout_s:.0f} s",
                        "crossmatch": job.get("crossmatch_prev")})
        rec["attempts"] = attempt
        rec["orchestrator_wall_s"] = wall
        if not rec.get("crossmatch") and job.get("crossmatch_prev"):
            rec["crossmatch"] = job["crossmatch_prev"]
        _write_json(rp, rec)
        return key, rec.get("status", status), wall

    pending = [(j, 1) for j in jobs]
    t_start = time.perf_counter()
    while pending:
        batch, pending = pending, []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_one, j, a): (j, a) for j, a in batch}
            for fut in as_completed(futs):
                j, a = futs[fut]
                key, status, wall = fut.result()
                print(f"  [{key}] attempt {a}: {status} wall={wall:.0f}s (elapsed {time.perf_counter() - t_start:.0f}s)",
                      flush=True)
                if status in ("error", "timeout") and a <= retries:
                    pending.append((j, a + 1))
        if pending:
            print(f"retrying {len(pending)} candidate(s)", flush=True)
    print("done", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--survivors", default=str(REPO / "data" / "survey" / "p4" / "survivors.csv"))
    ap.add_argument("--targets", default=str(REPO / "data" / "survey" / "targets_v1.csv"))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--packets", default=str(DEFAULT_PACKETS))
    ap.add_argument("--refresh-catalogs", action="store_true")
    ap.add_argument("--crossmatch", action="store_true", help="fresh hard stop on every survivor star")
    ap.add_argument("--expensive", action="store_true", help="centroid + TRICERATOPS + packet for the top N")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--timeout", type=float, default=5400.0)
    ap.add_argument("--retries", type=int, default=1)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--n-draws", type=int, default=100_000)
    ap.add_argument("--max-centroid-sectors", type=int, default=40)
    ap.add_argument("--no-fpp", action="store_true")
    ap.add_argument("--no-centroid", action="store_true")
    ap.add_argument("--tesscut-only", action="store_true",
                    help="centroid from TESScut cutouts only (skip pipeline TPF downloads)")
    ap.add_argument("--one", default=None, help="(child) job JSON to run")
    ap.add_argument("--result", default=None, help="(child) where to write the result")
    args = ap.parse_args()

    if args.one:
        job = json.loads(Path(args.one).read_text(encoding="utf-8"))
        rec = run_one(job)
        _write_json(Path(args.result), rec)
        print(f"[{job.get('key')}] {rec['status']} total={rec['timings'].get('total', 0):.0f}s "
              f"verdict={rec.get('verdict_final')} fpp={(rec.get('fpp') or {}).get('fpp')}", flush=True)
        return 0 if rec["status"] in ("ok", "not_recovered") else 1

    out_dir = Path(args.out)
    targets = {int(r["tic_id"]): r for r in csv.DictReader(open(args.targets, newline="", encoding="utf-8"))}
    if args.refresh_catalogs:
        refresh_catalogs(out_dir)
    if args.crossmatch:
        crossmatch_all(Path(args.survivors), out_dir, targets, retries=args.retries)
    if args.expensive:
        run_expensive(Path(args.survivors), out_dir, Path(args.packets), targets, args.top, args.workers,
                      args.timeout, args.retries, args.force, args.n_draws, args.max_centroid_sectors,
                      args.no_fpp, args.no_centroid, tesscut_only=args.tesscut_only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
