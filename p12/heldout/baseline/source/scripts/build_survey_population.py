#!/usr/bin/env python
"""Build the survey population: tiles -> TIC -> sectors -> products -> hard stop -> yield.

Reproducible from a single invocation::

    python scripts/build_survey_population.py all --seed 20260901

Stages (each caches under ``data/survey/cache`` and is skipped when cached):

``tiles``     Draw seeded sky tiles, query the TIC in each (all stars Tmag <= 17).
``sectors``   Predict observed sectors per star with the vendored tess-point.
``products``  Stream the QLP and TESS-SPOC per-sector target lists from MAST and
              record which pool stars have a light curve in each sector.
``xmatch``    Run the known-object hard stop (TIC ID + 21 arcsec neighbours).
``yield``     Run the yield model (tesshunter.survey_yield: Kunimoto & Matthews 2020 FGK grid,
              Dressing & Charbonneau 2015 M-dwarf grid, explicit contamination policy) with the
              legacy model and contamination variants as sensitivity, the tile-prefix scan, the
              tile bootstrap and selection rule v4; writes ``data/survey/yield_model_v1.json``.
``targets``   Write ``data/survey/targets_v1.csv`` for the chosen stratum.

Every number the memo quotes comes from the JSON this script writes; the memo
is prose around those numbers.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data" / "cache" / "lightkurve"))

warnings.simplefilter("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("survey")

SURVEY_DIR = REPO / "data" / "survey"
CACHE = SURVEY_DIR / "cache"
TILES_DIR = CACHE / "tiles"
PRODUCTS_DIR = CACHE / "products"

# ── Survey design constants (all recorded in the JSON output) ────────────────
DESIGN = {
    "seed": 20260901,
    "n_tiles": 240,
    "tile_radius_deg": 0.75,
    "min_abs_galactic_latitude_deg": 20.0,
    "tic_query_tmag_max": 17.0,           # every TIC star in a tile, for neighbour checks
    "stratum1_tmag": [10.5, 13.5],
    "stratum2_tmag": [13.5, 15.0],
    "dwarf_max_radius_rsun": 1.5,
    "dwarf_teff_range_k": [2700.0, 7200.0],
    "mdwarf_teff_max_k": 4000.0,
    "mdwarf_max_radius_rsun": 0.6,
    "min_sectors": 4,
    "match_radius_arcsec": 21.0,
    "max_sector_in_target_lists": 105,
    # tess-point's pointing table runs into planned sectors; only sectors with
    # public data (SPOC TCE lists and QLP target lists both end at 105 on 2026-09-01) count
    "latest_observed_sector": 105,
}

QLP_LIST_URL = "https://archive.stsci.edu/hlsps/qlp/target_lists/s{sector:04d}.csv"
SPOC_LIST_URL = "https://archive.stsci.edu/hlsps/tess-spoc/target_lists/s{sector:04d}.csv"


# ── helpers ───────────────────────────────────────────────────────────────────
def _sha_ids(ids) -> str:
    arr = np.sort(np.asarray(list(ids), dtype=np.int64))
    return hashlib.sha256(arr.tobytes()).hexdigest()[:16]


def _sky_uniform(rng: np.random.Generator, n: int) -> tuple[np.ndarray, np.ndarray]:
    ra = 360.0 * rng.random(n)
    dec = np.rad2deg(np.arcsin(2.0 * rng.random(n) - 1.0))
    return ra, dec


def union_area_sqdeg(tiles: pd.DataFrame, radius_deg: float, n_mc: int = 2_000_000, seed: int = 1) -> float:
    """Sky area covered by the union of the tiles, Monte Carlo over the |b|-cut sky."""
    from scipy.spatial import cKDTree
    from astropy.coordinates import SkyCoord

    rng = np.random.default_rng(seed)
    ra = 360.0 * rng.random(n_mc)
    dec = np.rad2deg(np.arcsin(2.0 * rng.random(n_mc) - 1.0))
    b = SkyCoord(ra=ra, dec=dec, unit="deg").galactic.b.deg
    keep = np.abs(b) >= DESIGN["min_abs_galactic_latitude_deg"]
    pts = _unit(ra[keep], dec[keep])
    tree = cKDTree(_unit(tiles["ra"].to_numpy(), tiles["dec"].to_numpy()))
    d, _ = tree.query(pts, k=1)
    chord = 2.0 * np.sin(np.deg2rad(radius_deg) / 2.0)
    frac_of_cut_sky = float(np.mean(d <= chord))
    sky_cut = 4 * np.pi * (180 / np.pi) ** 2 * (1 - np.sin(np.deg2rad(DESIGN["min_abs_galactic_latitude_deg"])))
    return frac_of_cut_sky * sky_cut


def _unit(ra_deg, dec_deg):
    ra = np.deg2rad(np.asarray(ra_deg, float))
    dec = np.deg2rad(np.asarray(dec_deg, float))
    return np.column_stack([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)])


def draw_tiles(design: dict) -> pd.DataFrame:
    """Seeded uniform sky tiles with |b| >= cut.  Rejection sampling keeps it reproducible."""
    from astropy.coordinates import SkyCoord

    rng = np.random.default_rng(design["seed"])
    out = []
    while len(out) < design["n_tiles"]:
        ra, dec = _sky_uniform(rng, 64)
        c = SkyCoord(ra=ra, dec=dec, unit="deg")
        b = c.galactic.b.deg
        beta = c.barycentricmeanecliptic.lat.deg
        for i in range(len(ra)):
            if abs(b[i]) >= design["min_abs_galactic_latitude_deg"]:
                out.append({"tile": len(out), "ra": float(ra[i]), "dec": float(dec[i]),
                            "glat": float(b[i]), "elat": float(beta[i])})
                if len(out) == design["n_tiles"]:
                    break
    return pd.DataFrame(out)


TIC_COLUMNS = ["ID", "ra", "dec", "Tmag", "Teff", "logg", "rad", "mass", "lumclass",
               "contratio", "objType", "GAIA", "gallat", "eclat", "d", "plx"]


def query_tile(tile: dict, radius_deg: float, tmag_max: float) -> pd.DataFrame:
    from astroquery.mast import Catalogs
    from astropy.coordinates import SkyCoord

    c = SkyCoord(ra=tile["ra"], dec=tile["dec"], unit="deg")
    last = None
    for attempt in range(4):
        try:
            tab = Catalogs.query_criteria(
                catalog="Tic", coordinates=c, radius=radius_deg,
                Tmag=[-5.0, tmag_max], objType="STAR",
            )
            df = tab.to_pandas()
            keep = [c_ for c_ in TIC_COLUMNS if c_ in df.columns]
            df = df[keep].rename(columns={"ID": "tic_id"})
            df["tic_id"] = pd.to_numeric(df["tic_id"]).astype("int64")
            df["tile"] = tile["tile"]
            return df
        except Exception as exc:  # MAST hiccups; retry with backoff
            last = exc
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"TIC query failed for tile {tile['tile']}: {last}")


def stage_tiles(design: dict) -> pd.DataFrame:
    TILES_DIR.mkdir(parents=True, exist_ok=True)
    tiles = draw_tiles(design)
    tiles.to_csv(CACHE / "tiles.csv", index=False)
    frames = []
    for _, t in tiles.iterrows():
        p = TILES_DIR / f"tile_{int(t['tile']):03d}.csv"
        if p.exists():
            df = pd.read_csv(p)
        else:
            t0 = time.time()
            df = query_tile(t.to_dict(), design["tile_radius_deg"], design["tic_query_tmag_max"])
            df.to_csv(p, index=False)
            log.info("tile %3d  (%.2f, %.2f) b=%.1f: %d TIC stars in %.0fs",
                     t["tile"], t["ra"], t["dec"], t["glat"], len(df), time.time() - t0)
        frames.append(df)
    allstars = pd.concat(frames, ignore_index=True)
    allstars.to_csv(CACHE / "tile_stars_all.csv", index=False)
    log.info("tiles: %d tiles, %d TIC stars (Tmag<=%.1f)", len(tiles), len(allstars),
             design["tic_query_tmag_max"])
    return allstars


def select_pool(allstars: pd.DataFrame, design: dict) -> pd.DataFrame:
    """Stars that could belong to any stratum (bright dwarfs and faint M dwarfs)."""
    s = allstars.copy()
    s["dwarf"] = (
        (s["rad"] <= design["dwarf_max_radius_rsun"])
        & (s["Teff"] >= design["dwarf_teff_range_k"][0])
        & (s["Teff"] <= design["dwarf_teff_range_k"][1])
    )
    s["mdwarf"] = (
        (s["Teff"] <= design["mdwarf_teff_max_k"]) & (s["rad"] <= design["mdwarf_max_radius_rsun"])
    )
    lo1, hi1 = design["stratum1_tmag"]
    lo2, hi2 = design["stratum2_tmag"]
    s["in_s1_mag"] = (s["Tmag"] >= lo1) & (s["Tmag"] < hi1)
    s["in_s2_mag"] = (s["Tmag"] >= lo2) & (s["Tmag"] <= hi2)
    s["contamination_ratio_missing"] = s["contratio"].isna()      # NaN is preserved; never filled here
    pool = s[(s["in_s1_mag"] & s["dwarf"]) | (s["in_s2_mag"] & s["mdwarf"])].copy()
    n_before = len(pool)
    pool = pool.drop_duplicates("tic_id", keep="first")
    pool.attrs["n_duplicate_rows_dropped"] = int(n_before - len(pool))
    return pool.reset_index(drop=True)


def stage_sectors(pool: pd.DataFrame, latest_sector: int = DESIGN["latest_observed_sector"]) -> pd.DataFrame:
    from tesshunter._vendor import tess_stars2px as tp

    p = CACHE / "pool_sectors.csv"
    keyf = CACHE / "pool_sectors.key"
    key = _sha_ids(pool["tic_id"]) + f"-s{latest_sector}"
    if p.exists() and keyf.exists() and keyf.read_text().strip() == key:
        return pd.read_csv(p)
    ids = pool["tic_id"].to_numpy()
    res = tp.tess_stars2px_function_entry(ids, pool["ra"].to_numpy(), pool["dec"].to_numpy())
    out_id, out_sec = np.asarray(res[0]), np.asarray(res[3]).astype(int)
    per = {}
    for i, sct in zip(out_id, out_sec):
        if int(sct) <= latest_sector:
            per.setdefault(int(i), set()).add(int(sct))
    rows = [{"tic_id": int(t), "n_sectors_predicted": len(per.get(int(t), ())),
             "sectors_predicted": ",".join(str(x) for x in sorted(per.get(int(t), ())))}
            for t in ids]
    df = pd.DataFrame(rows)
    df.to_csv(p, index=False)
    (CACHE / "pool_sectors.key").write_text(key)
    return df


def _stream_list(url: str, pool_sorted: np.ndarray, timeout: int = 600) -> np.ndarray:
    """Stream a MAST target list and return the pool TIC IDs present in it."""
    req = urllib.request.Request(url, headers={"User-Agent": "tesshunter/0.1"})
    found = []
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        reader = pd.read_csv(io.TextIOWrapper(resp, encoding="utf-8"), usecols=[0],
                             chunksize=500_000, comment=None)
        for chunk in reader:
            ids = pd.to_numeric(chunk.iloc[:, 0], errors="coerce").dropna().to_numpy(dtype=np.int64)
            hit = ids[np.isin(ids, pool_sorted, assume_unique=False)]
            if len(hit):
                found.append(hit)
    return np.unique(np.concatenate(found)) if found else np.zeros(0, dtype=np.int64)


def stage_products(pool: pd.DataFrame, sectors: pd.DataFrame, design: dict,
                   workers: int = 4) -> pd.DataFrame:
    """Per-sector QLP / TESS-SPOC membership for the pool, streamed from MAST."""
    PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)
    key = _sha_ids(pool["tic_id"])
    pool_sorted = np.sort(pool["tic_id"].to_numpy(dtype=np.int64))
    needed = set()
    for s in sectors["sectors_predicted"].fillna("").astype(str):
        needed.update(int(x) for x in s.split(",") if x)
    needed = sorted(x for x in needed if x <= design["max_sector_in_target_lists"])
    jobs = []
    for sec in needed:
        for name, tmpl in (("qlp", QLP_LIST_URL), ("tess-spoc", SPOC_LIST_URL)):
            jobs.append((name, sec, tmpl.format(sector=sec)))

    def run(job):
        name, sec, url = job
        out = PRODUCTS_DIR / f"{name}_s{sec:04d}.csv"
        keyf = PRODUCTS_DIR / f"{name}_s{sec:04d}.key"
        if out.exists() and keyf.exists() and keyf.read_text().strip() == key:
            return name, sec, "cached", len(pd.read_csv(out))
        t0 = time.time()
        try:
            ids = _stream_list(url, pool_sorted)
            status = "ok"
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                ids, status = np.zeros(0, dtype=np.int64), "missing"
            else:
                raise
        pd.DataFrame({"tic_id": ids}).to_csv(out, index=False)
        keyf.write_text(key)
        (PRODUCTS_DIR / f"{name}_s{sec:04d}.status").write_text(status)
        log.info("products %-9s s%04d: %5d pool stars (%s, %.0fs)", name, sec, len(ids), status,
                 time.time() - t0)
        return name, sec, status, len(ids)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(run, j) for j in jobs]
        for f in as_completed(futs):
            f.result()

    # assemble per-star product summary
    have = {"qlp": {}, "tess-spoc": {}}
    missing = {"qlp": [], "tess-spoc": []}
    for name in have:
        for sec in needed:
            out = PRODUCTS_DIR / f"{name}_s{sec:04d}.csv"
            st = PRODUCTS_DIR / f"{name}_s{sec:04d}.status"
            if st.exists() and st.read_text().strip() == "missing":
                missing[name].append(sec)
                continue
            for t in pd.read_csv(out)["tic_id"].to_numpy(dtype=np.int64):
                have[name].setdefault(int(t), []).append(sec)
    rows = []
    for t in pool["tic_id"]:
        q = sorted(have["qlp"].get(int(t), []))
        s = sorted(have["tess-spoc"].get(int(t), []))
        rows.append({
            "tic_id": int(t),
            "n_sectors_qlp": len(q), "sectors_qlp": ",".join(map(str, q)),
            "n_sectors_tess_spoc": len(s), "sectors_tess_spoc": ",".join(map(str, s)),
            "n_sectors_any_lc": len(set(q) | set(s)),
        })
    df = pd.DataFrame(rows)
    json.dump({"sectors_checked": needed, "lists_missing": missing, "pool_key": key},
              open(PRODUCTS_DIR / "summary.json", "w"), indent=1)
    return df


def stage_xmatch(pool: pd.DataFrame, allstars: pd.DataFrame, design: dict):
    from tesshunter import catalog_crossmatch as cx

    cat = cx.KnownObjectCatalog.load(match_radius_arcsec=design["match_radius_arcsec"])
    if cat.any_stale():
        raise RuntimeError("a catalog is stale; refusing to build the population on it")
    res = cat.check_many(pool[["tic_id", "ra", "dec"]], neighbours=allstars[["tic_id", "ra", "dec"]])
    cat.write_manifest(SURVEY_DIR / "catalog_versions_v1.json")
    return res, cat


# ── Yield model (implementation in tesshunter.survey_yield) ───────────────────
from tesshunter import occurrence_grids as og  # noqa: E402
from tesshunter import survey_yield as sy  # noqa: E402

STRATA = {
    "1_ffi_bright_dwarfs_p_le_50d": {"pool": "s1", "p_max": 50.0, "prior": "bright"},
    "2_ffi_faint_mdwarfs": {"pool": "s2", "p_max": 50.0, "prior": "faint_m"},
    "3_multisector_stitch_bright_dwarfs_p_le_100d": {"pool": "s1", "p_max": 100.0, "prior": "bright"},
}
CANDIDATES = ["2_ffi_faint_mdwarfs", "3_multisector_stitch_bright_dwarfs_p_le_100d"]
S2, S3 = CANDIDATES

# Selection rule, version 4.  Written down before the expanded (>120-tile)
# sample was examined; the history of versions 1-3 is kept verbatim below.
SELECTION_RULE = {
    "version": 4,
    "candidates": CANDIDATES,
    "metric": "expected NEW detected signals per 1000 eligible stars, mid prior completeness, central model "
              "(FGK: Kunimoto & Matthews 2020 grid; M: Dressing & Charbonneau 2015 grid; contamination: measured median)",
    "sample_requirement": "the prefix-stable tile sequence is extended until BOTH candidates deliver >= "
                          "min_expected_new_from_sample under the central model; the smallest such prefix "
                          "(n_tiles_floor) is recorded and the metric is reported both there and on the full prefix",
    "min_expected_new_from_sample": 2.0,
    "min_allsky_population_for_primary": 20000 * 5,
    "tie_margin": 1.5,
    "primary": "the candidate with the higher metric; if the ratio of metrics is below tie_margin the model cannot "
               "separate them and the documented secondary criteria decide, in order",
    "secondary_criteria_in_order": ["fraction_of_eligible_pool_with_min_sectors_of_light_curves (higher)",
                                    "median_tmag (brighter)"],
    "deliverability_is_a_criterion": False,
    "history": [
        "v1 (first 60-tile run): rank by expected new signals per 1000 stars at mid priors among strata with all-sky "
        "population >= 100,000; margin recorded but not used. Picked stratum 2 (1.39 vs 1.12); its 594 eligible stars "
        "gave 0.83 expected signals, below the 2-to-5 target size.",
        "v2 (120-tile run): added 'sampled stars must deliver >= 2.0 expected new signals'. Picked stratum 3 "
        "(2 gave 1.63 from 1116 stars; ratio of metrics 1.21).",
        "v3 (P1 final): a metric ratio below the tie margin is a tie, resolved by ordered tie-breakers "
        "(deliverability, light-curve coverage, brightness). Picked stratum 3.",
        "v4 (remediation, fixed before the extended sample was examined): the sample is extended until both "
        "candidates satisfy the deliverability floor, so deliverability can no longer decide; the metric is the "
        "central-model yield density; ties inside the 1.5 margin go to the operational secondary criteria "
        "(coverage, then brightness).",
    ],
    "note": "stratum 1 is a subset of stratum 3 and is never chosen over 3; stratum 4 is excluded by the hard stop.",
}


def eligible_sets(pool: pd.DataFrame, design: dict):
    clean = pool[pool["xmatch_status"] == "CLEAN"].copy()
    clean["n_sectors_use"] = clean["n_sectors_any_lc"].where(clean["n_sectors_any_lc"] > 0,
                                                             clean["n_sectors_predicted"])
    s1_all = clean[clean["in_s1_mag"] & clean["dwarf"]]
    s2_all = clean[clean["in_s2_mag"] & clean["mdwarf"]]
    s1 = s1_all[s1_all["n_sectors_use"] >= design["min_sectors"]]
    s2 = s2_all[s2_all["n_sectors_use"] >= design["min_sectors"]]
    return clean, s1_all, s2_all, s1, s2


def contamination_fill_table(s1_all: pd.DataFrame, s2_all: pd.DataFrame) -> dict:
    return {"s1": sy.contamination_fills(s1_all["contratio"]), "s2": sy.contamination_fills(s2_all["contratio"])}


def stratum_scores(stars: pd.DataFrame, key: str, design: dict, fgk_model: str, m_model: str,
                   contam_fill: float, faint_penalty: float = 1.0, m_giant_rate: float | None = None) -> dict:
    """Per-star class yields and expected new signals for one stratum."""
    spec = STRATA[key]
    p_max = spec["p_max"]
    fgk = stars[stars["Teff"] > design["mdwarf_teff_max_k"]]
    mm = stars[stars["Teff"] <= design["mdwarf_teff_max_k"]]
    out = {k: np.zeros(len(stars)) for k in ("A", "B", "C", "stitched_snr9", "stitched_snr7")}
    per_bin = {}
    idx = {i: n for n, i in enumerate(stars.index)}
    for sub, group, model in ((fgk, "fgk", fgk_model), (mm, "m", m_model)):
        if len(sub) == 0:
            continue
        cells_le50 = sy.occurrence_cells(group, model, min(p_max, 50.0), m_giant_rate=m_giant_rate)
        cells_full = sy.occurrence_cells(group, model, p_max, m_giant_rate=m_giant_rate)
        cls = sy.class_yields(sub, cells_le50, cells_full, contam_fill=contam_fill, faint_penalty=faint_penalty)
        pos = np.array([idx[i] for i in sub.index])
        for k in out:
            out[k][pos] = cls[k]
        _, pc = sy.per_star_yield(sub, cells_full, "stitch", contam_fill=contam_fill,
                                  faint_penalty=faint_penalty, return_per_cell=True)
        for k, v in pc.items():
            per_bin[("M:" if group == "m" else "") + k] = v
    new = {lvl: sy.new_signals_per_star(out, spec["prior"], lvl) for lvl in ("low", "mid", "high")}
    return {"classes": out, "new": new, "per_bin": per_bin, "prior_key": spec["prior"]}


def summarize_stratum(scores: dict, n_allsky_scale: float) -> dict:
    n = len(scores["new"]["mid"])
    cls = scores["classes"]
    out = {"n_stars_sampled": int(n), "n_stars_allsky_est": int(round(n * n_allsky_scale)),
           "detectable_per_sample": {"A_single_sector_snr9": float(cls["A"].sum()),
                                     "B_stitched_snr9_not_A": float(cls["B"].sum()),
                                     "C_stitched_snr7_to_9": float(cls["C"].sum()),
                                     "total_stitched_snr7": float(cls["stitched_snr7"].sum())},
           "detectable_per_1000_stars": {k: 1000.0 * float(cls[k].sum()) / max(n, 1) for k in ("A", "B", "C")},
           "per_bin_stitched_snr7": scores["per_bin"], "prior_completeness_key": scores["prior_key"],
           "pipeline_efficiency": sy.PIPELINE_EFFICIENCY}
    for lvl in ("low", "mid", "high"):
        tot = float(scores["new"][lvl].sum())
        out[f"new_detected_per_sample_prior_{lvl}"] = tot
        out[f"new_detected_per_1000_stars_prior_{lvl}"] = 1000.0 * tot / max(n, 1)
        for target in (2, 3, 5):
            out[f"stars_for_{target}_new_prior_{lvl}"] = int(round(target / max(tot, 1e-12) * n))
        out[f"new_detected_by_class_prior_{lvl}"] = {
            k: float((cls[k] * (1 - sy.PRIOR_COMPLETENESS[scores["prior_key"]][k][lvl]) * sy.PIPELINE_EFFICIENCY[k]).sum())
            for k in ("A", "B", "C")}
    return out


def ranked_target_ids(stars: pd.DataFrame, per_star_new: np.ndarray, expected_new: float, cap: int) -> list[int]:
    order = np.argsort(-per_star_new, kind="stable")
    cum = np.cumsum(per_star_new[order])
    n_for = int(np.searchsorted(cum, expected_new) + 1) if len(cum) and cum[-1] >= expected_new else len(order)
    keep = order[: min(cap, n_for, len(order))]
    return [int(t) for t in stars["tic_id"].to_numpy()[keep]]


def run_configuration(pool: pd.DataFrame, design: dict, fgk_model: str, m_model: str, contam_policy: str,
                      faint_penalty: float = 1.0, drop_class_c: bool = False,
                      m_giant_rate: float | None = None) -> dict:
    """Everything the decision needs under one (occurrence model, contamination policy) configuration."""
    clean, s1_all, s2_all, s1, s2 = eligible_sets(pool, design)
    fills = contamination_fill_table(s1_all, s2_all)
    res = {}
    for key, spec in STRATA.items():
        stars = s1 if spec["pool"] == "s1" else s2
        fill = fills[spec["pool"]][contam_policy]
        sc = stratum_scores(stars, key, design, fgk_model, m_model, fill, faint_penalty, m_giant_rate)
        if drop_class_c:
            sc["classes"]["C"] = np.zeros_like(sc["classes"]["C"])
            sc["new"] = {lvl: sy.new_signals_per_star(sc["classes"], sc["prior_key"], lvl) for lvl in sc["new"]}
        res[key] = {"stars": stars, "scores": sc, "contam_fill": fill}
    return {"fgk_model": fgk_model, "m_model": m_model, "contam_policy": contam_policy,
            "faint_penalty": faint_penalty, "drop_class_c": drop_class_c, "m_giant_rate": m_giant_rate,
            "fills": fills, "strata": res}


def decide(summary: dict, coverage: dict, median_tmag: dict) -> dict:
    """Apply SELECTION_RULE v4 to stratum summaries (metric at mid priors)."""
    rule = SELECTION_RULE
    metric = {k: summary[k]["new_detected_per_1000_stars_prior_mid"] for k in CANDIDATES}
    deliver = {k: summary[k]["new_detected_per_sample_prior_mid"] for k in CANDIDATES}
    big = {k: summary[k]["n_stars_allsky_est"] >= rule["min_allsky_population_for_primary"] for k in CANDIDATES}
    floor_ok = {k: deliver[k] >= rule["min_expected_new_from_sample"] for k in CANDIDATES}
    ranked = sorted(CANDIDATES, key=lambda k: -metric[k])
    ratio = metric[ranked[0]] / max(metric[ranked[-1]], 1e-12)
    eligible = [k for k in CANDIDATES if big[k]] or CANDIDATES
    if ratio >= rule["tie_margin"]:
        primary = sorted(eligible, key=lambda k: -metric[k])[0]
        how = "metric ratio at or above tie_margin: higher yield density wins"
    else:
        primary = sorted(eligible, key=lambda k: (-coverage[k], median_tmag[k]))[0]
        how = "metric ratio inside tie_margin: secondary criteria (coverage, then brightness) decide"
    fallback = [k for k in CANDIDATES if k != primary][0]
    return {"metric_per_1000_mid": metric, "deliverable_from_sample_mid": deliver, "floor_satisfied": floor_ok,
            "both_satisfy_floor": all(floor_ok.values()), "allsky_ok": big, "yield_only_ranking": ranked,
            "margin_ratio": ratio, "within_model_uncertainty": ratio < rule["tie_margin"],
            "coverage": coverage, "median_tmag": median_tmag, "primary": primary, "fallback": fallback,
            "decided_by": how}


def prefix_scan(pool: pd.DataFrame, cfg: dict, tiles: pd.DataFrame, design: dict) -> dict:
    """Deliverable expected new signals for every tile prefix n = 1..N under one configuration.

    Per-star scores do not depend on n, so the scan is exact: cumulative sums
    of per-star scores by tile index.  Returns the smallest prefix at which
    each candidate reaches the floor, and both at once.
    """
    n_tiles = int(tiles["tile"].max()) + 1
    out = {"n_tiles": n_tiles}
    floor = SELECTION_RULE["min_expected_new_from_sample"]
    curves = {}
    for k in CANDIDATES:
        stars = cfg["strata"][k]["stars"]
        new = cfg["strata"][k]["scores"]["new"]["mid"]
        per_tile = np.zeros(n_tiles)
        np.add.at(per_tile, stars["tile"].to_numpy(dtype=int), new)
        cum = np.cumsum(per_tile)
        curves[k] = cum
        reach = int(np.argmax(cum >= floor)) + 1 if (cum >= floor).any() else None
        out[k] = {"n_tiles_to_floor": reach, "deliverable_at_full_prefix": float(cum[-1]),
                  "deliverable_at_120": float(cum[min(119, n_tiles - 1)]),
                  "deliverable_at_60": float(cum[min(59, n_tiles - 1)])}
    both = [n for n in range(1, n_tiles + 1) if all(curves[k][n - 1] >= floor for k in CANDIDATES)]
    out["n_tiles_floor_both"] = both[0] if both else None
    out["curve_every_20_tiles"] = {str(n): {k: float(curves[k][n - 1]) for k in CANDIDATES}
                                   for n in range(20, n_tiles + 1, 20)}
    return out


def tile_bootstrap(cfg: dict, tiles: pd.DataFrame, n_boot: int = 1000, seed: int = 7) -> dict:
    """Bootstrap over tiles of the per-1000 metric and of the S2/S3 ratio."""
    rng = np.random.default_rng(seed)
    n_tiles = int(tiles["tile"].max()) + 1
    sums, counts = {}, {}
    for k in CANDIDATES:
        stars = cfg["strata"][k]["stars"]
        new = cfg["strata"][k]["scores"]["new"]["mid"]
        s = np.zeros(n_tiles); c = np.zeros(n_tiles)
        np.add.at(s, stars["tile"].to_numpy(dtype=int), new)
        np.add.at(c, stars["tile"].to_numpy(dtype=int), 1.0)
        sums[k], counts[k] = s, c
    draws = rng.integers(0, n_tiles, size=(n_boot, n_tiles))
    metric = {k: 1000.0 * sums[k][draws].sum(axis=1) / np.maximum(counts[k][draws].sum(axis=1), 1) for k in CANDIDATES}
    ratio = metric[S2] / np.maximum(metric[S3], 1e-12)
    q = lambda a: [float(np.percentile(a, p)) for p in (16, 50, 84)]  # noqa: E731
    return {"n_boot": n_boot, "metric_p16_p50_p84": {k: q(metric[k]) for k in CANDIDATES},
            "ratio_s2_over_s3_p16_p50_p84": q(ratio), "prob_s2_metric_exceeds_s3": float(np.mean(ratio > 1.0)),
            "prob_ratio_exceeds_tie_margin_either_way": float(np.mean((ratio >= SELECTION_RULE["tie_margin"]) | (ratio <= 1 / SELECTION_RULE["tie_margin"])))}


def stage_yield(pool: pd.DataFrame, design: dict, n_tiles_done: int, tiles: pd.DataFrame,
                n_duplicates_dropped: int = 0, expected_new: float = 5.0, cap: int = 20000) -> dict:
    """Central model, sensitivity variants, prefix scan, bootstrap and the decision; writes the JSON."""
    tile_area = 2 * np.pi * (1 - np.cos(np.deg2rad(design["tile_radius_deg"]))) * (180 / np.pi) ** 2
    sky_area = 4 * np.pi * (180 / np.pi) ** 2 * (1 - np.sin(np.deg2rad(design["min_abs_galactic_latitude_deg"])))
    covered = union_area_sqdeg(tiles, design["tile_radius_deg"])
    scale = sky_area / covered

    clean, s1_all, s2_all, s1, s2 = eligible_sets(pool, design)
    fills = contamination_fill_table(s1_all, s2_all)
    coverage = {S3: float((s1_all["n_sectors_use"] >= design["min_sectors"]).mean()) if len(s1_all) else 0.0,
                S2: float((s2_all["n_sectors_use"] >= design["min_sectors"]).mean()) if len(s2_all) else 0.0}
    median_tmag = {S3: float(s1["Tmag"].median()) if len(s1) else 99.0, S2: float(s2["Tmag"].median()) if len(s2) else 99.0}

    central_cfg = run_configuration(pool, design, sy.CENTRAL_MODEL["fgk"], sy.CENTRAL_MODEL["m"],
                                    sy.CONTAMINATION_POLICY["central"])
    strata = {k: summarize_stratum(v["scores"], scale) for k, v in central_cfg["strata"].items()}
    decision = decide(strata, coverage, median_tmag)
    scan = prefix_scan(pool, central_cfg, tiles, design)
    boot = tile_bootstrap(central_cfg, tiles)

    # central target membership (for change accounting under the variants)
    def membership(cfg, key):
        st = cfg["strata"][key]
        return set(ranked_target_ids(st["stars"], st["scores"]["new"]["mid"], expected_new, cap))
    central_ids = {k: membership(central_cfg, k) for k in CANDIDATES}

    variants = {}
    for fgk_model in sy.FGK_MODELS:
        for m_model in sy.M_MODELS:
            for policy in sy.CONTAMINATION_POLICY["variants"]:
                cfg = run_configuration(pool, design, fgk_model, m_model, policy)
                summ = {k: summarize_stratum(v["scores"], scale) for k, v in cfg["strata"].items()}
                dec = decide(summ, coverage, median_tmag)
                ids = {k: membership(cfg, k) for k in CANDIDATES}
                variants[f"fgk={fgk_model}|m={m_model}|contam={policy}"] = {
                    "fgk_model": fgk_model, "m_model": m_model, "contamination_policy": policy,
                    "contam_fill_s1": cfg["fills"]["s1"][policy], "contam_fill_s2": cfg["fills"]["s2"][policy],
                    "metric_per_1000_mid": dec["metric_per_1000_mid"],
                    "deliverable_from_sample_mid": dec["deliverable_from_sample_mid"],
                    "stars_for_2_3_5_new_mid": {k: [summ[k][f"stars_for_{t}_new_prior_mid"] for t in (2, 3, 5)] for k in CANDIDATES},
                    "margin_ratio": dec["margin_ratio"], "primary": dec["primary"], "decided_by": dec["decided_by"],
                    "target_list_size": {k: len(ids[k]) for k in CANDIDATES},
                    "target_ids_vs_central": {k: {"n_added": len(ids[k] - central_ids[k]), "n_removed": len(central_ids[k] - ids[k]),
                                                  "n_common": len(ids[k] & central_ids[k])} for k in CANDIDATES},
                }
    # extra sensitivity on the central model: class C dropped; faint-end noise x1.4
    extra = {}
    giant_variants = [("m_giants_%g" % g, {"m_giant_rate": g}) for g in og.DC15_M_GIANTS_ADOPTED["sensitivity_values"]]
    giant_variants += [("m_giants_%g_faint_noise_x1.4" % g, {"m_giant_rate": g, "faint_penalty": 1.4})
                       for g in og.DC15_M_GIANTS_ADOPTED["sensitivity_values"]]
    for name, kw in [("no_class_C", {"drop_class_c": True}), ("faint_noise_x1.4", {"faint_penalty": 1.4})] + giant_variants:
        cfg = run_configuration(pool, design, sy.CENTRAL_MODEL["fgk"], sy.CENTRAL_MODEL["m"],
                                sy.CONTAMINATION_POLICY["central"], **kw)
        summ = {k: summarize_stratum(v["scores"], scale) for k, v in cfg["strata"].items()}
        dec = decide(summ, coverage, median_tmag)
        extra[name] = {"metric_per_1000_mid": dec["metric_per_1000_mid"], "margin_ratio": dec["margin_ratio"],
                       "primary": dec["primary"], "deliverable_from_sample_mid": dec["deliverable_from_sample_mid"]}

    toi_hosts = pool[pool["xmatch_tic_sources"].astype(str).str.contains("toi")]
    model = {
        "design": design,
        "central_model": {"fgk": sy.CENTRAL_MODEL["fgk"], "m": sy.CENTRAL_MODEL["m"],
                          "fgk_models": sy.FGK_MODELS, "m_models": sy.M_MODELS,
                          "occurrence_provenance": {"km2020": og.KM2020_PROVENANCE, "dc15": og.DC15_PROVENANCE,
                                                    "dc15_adopted_giants": og.DC15_M_GIANTS_ADOPTED,
                                                    "legacy": {"occurrence": sy.LEGACY_OCCURRENCE,
                                                               "period_shape": sy.LEGACY_PERIOD_SHAPE,
                                                               "period_edges": sy.LEGACY_PERIOD_EDGES}}},
        "noise_model": sy.NOISE_MODEL, "detection": sy.DETECTION,
        "prior_completeness": sy.PRIOR_COMPLETENESS, "pipeline_efficiency": sy.PIPELINE_EFFICIENCY,
        "contamination": {"policy": sy.CONTAMINATION_POLICY, "fills": fills,
                          "s1_missing_fraction": float(s1_all["contratio"].isna().mean()) if len(s1_all) else None,
                          "s2_missing_fraction": float(s2_all["contratio"].isna().mean()) if len(s2_all) else None,
                          "s1_missing_tmag_median": float(s1_all.loc[s1_all["contratio"].isna(), "Tmag"].median()) if s1_all["contratio"].isna().any() else None,
                          "s1_measured_tmag_median": float(s1_all.loc[s1_all["contratio"].notna(), "Tmag"].median()) if len(s1_all) else None},
        "sky": {"tile_area_sqdeg": tile_area, "sky_area_sqdeg_abs_b_ge_cut": sky_area, "n_tiles": n_tiles_done,
                "union_area_sqdeg": covered, "overlap_fraction": 1.0 - covered / (tile_area * n_tiles_done),
                "scale_to_allsky": scale, "n_duplicate_pool_rows_dropped": int(n_duplicates_dropped)},
        "noise_ppm_per_hour_at_Tmag": {str(t): float(sy.noise_ppm_per_hour(np.array([t]))[0]) for t in (9, 10, 10.5, 11, 12, 13, 13.5, 14, 15)},
        "pool_counts": {
            "pool_total": int(len(pool)),
            "pool_reject": int((pool["xmatch_status"] == "REJECT").sum()),
            "pool_flag": int((pool["xmatch_status"] == "FLAG").sum()),
            "pool_clean": int((pool["xmatch_status"] == "CLEAN").sum()),
            "reject_by_source": {k: int(v) for k, v in pool.loc[pool["xmatch_status"] == "REJECT", "xmatch_tic_sources"].value_counts().items()},
            "flag_by_source": {k: int(v) for k, v in pool.loc[pool["xmatch_status"] == "FLAG", "xmatch_neighbour_sources"].value_counts().items()},
        },
        "strata": strata,
        "stratum_4_toi_hosts": {"n_toi_hosts_in_pool_sample": int(len(toi_hosts)),
                                "n_toi_hosts_allsky_est": int(round(len(toi_hosts) * scale)),
                                "note": "computed in the memo from the TOI list size; excluded by the hard stop"},
        "pool_stats": {
            "s1_contratio_nan_frac": float(s1["contratio"].isna().mean()) if len(s1) else None,
            "s1_contratio_median": float(s1["contratio"].median()) if len(s1) else None,
            "s1_tmag_quartiles": [float(x) for x in s1["Tmag"].quantile([.25, .5, .75])] if len(s1) else None,
            "s1_teff_quartiles": [float(x) for x in s1["Teff"].quantile([.25, .5, .75])] if len(s1) else None,
            "s2_tmag_quartiles": [float(x) for x in s2["Tmag"].quantile([.25, .5, .75])] if len(s2) else None,
            "s1_frac_min_sectors": coverage[S3], "s2_frac_min_sectors": coverage[S2],
        },
        "sector_stats": {
            "s1_median_n_sectors_lc": float(s1["n_sectors_use"].median()) if len(s1) else None,
            "s1_frac_with_qlp": float((s1["n_sectors_qlp"] > 0).mean()) if len(s1) else None,
            "s1_frac_with_tess_spoc": float((s1["n_sectors_tess_spoc"] > 0).mean()) if len(s1) else None,
            "s2_median_n_sectors_lc": float(s2["n_sectors_use"].median()) if len(s2) else None,
            "s2_frac_with_qlp": float((s2["n_sectors_qlp"] > 0).mean()) if len(s2) else None,
        },
        "prefix_scan": scan,
        "tile_bootstrap": boot,
        "sensitivity": {"model_x_contamination": variants, "central_extras": extra,
                        "note": "each variant re-ranks per-star scores and re-cuts the target list; "
                                "target_ids_vs_central counts membership changes against the central list"},
        "selection": dict(decision, rule=SELECTION_RULE),
    }
    SURVEY_DIR.mkdir(parents=True, exist_ok=True)
    with open(SURVEY_DIR / "yield_model_v1.json", "w") as fh:
        json.dump(model, fh, indent=1, default=float)
    return model


# ── Orchestration ─────────────────────────────────────────────────────────────
def build(stages: list[str], design: dict, product_workers: int, target_cap: int,
          target_stratum: str, expected_new: float = 5.0) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "design.json").write_text(json.dumps(design, indent=1))
    do = set(stages)
    allstars = stage_tiles(design) if ("tiles" in do or not (CACHE / "tile_stars_all.csv").exists()) \
        else pd.read_csv(CACHE / "tile_stars_all.csv")
    n_tiles_done = int(allstars["tile"].nunique())
    pool = select_pool(allstars, design)
    n_dups = int(pool.attrs.get("n_duplicate_rows_dropped", 0))
    log.info("pool: %d unique stars (bright dwarfs %d, faint M dwarfs %d); %d duplicate rows from overlapping tiles dropped",
             len(pool), int((pool["in_s1_mag"] & pool["dwarf"]).sum()), int((pool["in_s2_mag"] & pool["mdwarf"]).sum()), n_dups)
    if "tiles" in do and len(do) == 1:
        return

    sectors = stage_sectors(pool, design["latest_observed_sector"])
    pool = pool.merge(sectors, on="tic_id", how="left")
    if "sectors" in do and do <= {"tiles", "sectors"}:
        pool.to_csv(CACHE / "pool_after_sectors.csv", index=False)
        return

    products = stage_products(pool, sectors, design, workers=product_workers)
    pool = pool.merge(products, on="tic_id", how="left")
    if do <= {"tiles", "sectors", "products"}:
        pool.to_csv(CACHE / "pool_after_products.csv", index=False)
        return

    xm, cat = stage_xmatch(pool, allstars, design)
    pool = pd.concat([pool, xm], axis=1)
    pool.to_csv(CACHE / "pool_after_xmatch.csv", index=False)
    log.info("xmatch: %s", pool["xmatch_status"].value_counts().to_dict())

    tiles = pd.read_csv(CACHE / "tiles.csv").head(n_tiles_done)
    model = stage_yield(pool, design, n_tiles_done, tiles, n_dups, expected_new, target_cap)
    for k, v in model["strata"].items():
        log.info("stratum %s: sampled=%d allsky~%d new/1000 (mid)=%.3f deliverable=%.2f stars for 3 new (mid)=%d",
                 k, v["n_stars_sampled"], v["n_stars_allsky_est"], v["new_detected_per_1000_stars_prior_mid"],
                 v["new_detected_per_sample_prior_mid"], v["stars_for_3_new_prior_mid"])
    sel = model["selection"]
    log.info("selection v4: primary=%s fallback=%s ratio=%.3f both_floor=%s n_tiles_floor_both=%s decided_by=%s",
             sel["primary"], sel["fallback"], sel["margin_ratio"], sel["both_satisfy_floor"],
             model["prefix_scan"]["n_tiles_floor_both"], sel["decided_by"])

    if "targets" in do:
        if target_stratum == "auto":
            target_stratum = sel["primary"]
        write_targets(pool, model, design, cat, target_cap, target_stratum, expected_new)
        fb = sel["fallback"]
        if fb != target_stratum:
            write_targets(pool, model, design, cat, target_cap, fb, expected_new, out_name="targets_v1_fallback")


def write_targets(pool: pd.DataFrame, model: dict, design: dict, cat, cap: int, stratum: str,
                  expected_new: float = 5.0, out_name: str = "targets_v1") -> None:
    cfg = run_configuration(pool, design, sy.CENTRAL_MODEL["fgk"], sy.CENTRAL_MODEL["m"],
                            sy.CONTAMINATION_POLICY["central"])
    key = stratum if stratum in STRATA else S3
    st = cfg["strata"][key]
    sel = st["stars"].copy()
    new_mid = st["scores"]["new"]["mid"]
    sel = sel.assign(expected_new_signals=new_mid,
                     class_A=st["scores"]["classes"]["A"], class_B=st["scores"]["classes"]["B"],
                     class_C=st["scores"]["classes"]["C"])
    keep_ids = ranked_target_ids(st["stars"], new_mid, expected_new, cap)
    sel = sel.set_index("tic_id").loc[keep_ids].reset_index()
    fill = st["contam_fill"]
    missing = sel["contratio"].isna()
    products = [";".join(p for p in (("qlp" if q > 0 else ""), ("tess-spoc" if s > 0 else "")) if p)
                for q, s in zip(sel["n_sectors_qlp"], sel["n_sectors_tess_spoc"])]
    out = pd.DataFrame({
        "tic_id": sel["tic_id"].astype("int64"),
        "ra_deg": sel["ra"].round(6), "dec_deg": sel["dec"].round(6),
        "tmag": sel["Tmag"].round(3), "teff_k": sel["Teff"].round(0),
        "radius_rsun": sel["rad"].round(3), "mass_msun": sel["mass"].round(3),
        "contamination_ratio": sel["contratio"].round(4),                 # NaN preserved
        "contamination_ratio_missing": missing.astype(bool),
        "contamination_ratio_used": np.where(missing, fill, sel["contratio"]).round(4),
        "contamination_policy": np.where(missing, sy.CONTAMINATION_POLICY["central"], "measured"),
        "galactic_lat_deg": sel["gallat"].round(2) if "gallat" in sel else np.nan,
        "n_sectors_predicted": sel["n_sectors_predicted"].astype(int), "sectors_predicted": sel["sectors_predicted"],
        "n_sectors_with_lc": sel["n_sectors_use"].astype(int),
        "sectors_qlp": sel["sectors_qlp"], "sectors_tess_spoc": sel["sectors_tess_spoc"],
        "lc_products_available": products,
        "crossmatch_status": sel["xmatch_status"],
        "nearest_known_object_sep_arcsec": sel["xmatch_nearest_known_sep_arcsec"].round(1),
        "expected_new_signals_mid": sel["expected_new_signals"].map(lambda v: f"{v:.2e}"),
        "class_A_detectable": sel["class_A"].map(lambda v: f"{v:.2e}"),
        "class_B_detectable": sel["class_B"].map(lambda v: f"{v:.2e}"),
        "class_C_detectable": sel["class_C"].map(lambda v: f"{v:.2e}"),
        "tile": sel["tile"].astype(int), "stratum": stratum,
        "occurrence_model": f"fgk={sy.CENTRAL_MODEL['fgk']};m={sy.CENTRAL_MODEL['m']}",
        "catalog_versions": cat.stamp(),
    })
    SURVEY_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(SURVEY_DIR / f"{out_name}.csv", index=False)
    meta = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stratum": stratum, "yield_key": key, "n_targets": int(len(out)), "cap": cap,
        "expected_new_target": expected_new, "n_available_clean": int(len(st["stars"])),
        "sum_expected_new_signals_mid": float(sel["expected_new_signals"].sum()),
        "occurrence_model": {"fgk": sy.CENTRAL_MODEL["fgk"], "m": sy.CENTRAL_MODEL["m"]},
        "contamination": {"policy": sy.CONTAMINATION_POLICY["central"], "fill_value": fill,
                          "n_missing": int(missing.sum()), "fraction_missing": float(missing.mean()) if len(missing) else 0.0,
                          "fills_available": cfg["fills"]["s1" if STRATA[key]["pool"] == "s1" else "s2"]},
        "design": design, "catalog_stamp": cat.stamp(),
    }
    (SURVEY_DIR / f"{out_name}.meta.json").write_text(json.dumps(meta, indent=1))
    log.info("%s.csv: %d rows, sum of expected NEW detected signals (mid priors) = %.2f (contamination policy %s, fill %.4f, %d missing)",
             out_name, len(out), meta["sum_expected_new_signals_mid"], sy.CONTAMINATION_POLICY["central"], fill, int(missing.sum()))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stages", nargs="*", default=["all"], help="tiles sectors products xmatch yield targets | all")
    ap.add_argument("--seed", type=int, default=DESIGN["seed"])
    ap.add_argument("--n-tiles", type=int, default=DESIGN["n_tiles"])
    ap.add_argument("--tile-radius", type=float, default=DESIGN["tile_radius_deg"])
    ap.add_argument("--product-workers", type=int, default=4)
    ap.add_argument("--cap", type=int, default=20000)
    ap.add_argument("--stratum", default="auto", help="stratum for targets_v1.csv; 'auto' applies SELECTION_RULE")
    ap.add_argument("--expected-new", type=float, default=5.0,
                    help="cut the ranked target list where the summed expected new signals (mid priors) reach this")
    a = ap.parse_args(argv)
    design = dict(DESIGN, seed=a.seed, n_tiles=a.n_tiles, tile_radius_deg=a.tile_radius)
    stages = ["tiles", "sectors", "products", "xmatch", "yield", "targets"] if "all" in a.stages else a.stages
    build(stages, design, a.product_workers, a.cap, a.stratum, a.expected_new)


if __name__ == "__main__":
    main()
