#!/usr/bin/env python
"""Build the prompt-8 population: mid-to-late M dwarfs with 200-second FFI light curves.

Reproducible from one seeded command::

    python scripts/build_p8_population.py all --seed 20260904

Stages (each caches under ``data/survey/cache/p8`` and is skipped when cached):

``tic``       Query the TIC over the whole sky in 5-degree declination strips on
              the cuts (Tmag 12.5-14.5, Teff 2000-3600 K, radius <= 0.50 Rsun,
              objType STAR); the |b| >= 20 cut is applied locally.  The query is
              wider than the definition (Tmag to 14.5, radius to 0.50) so the two
              relaxations the prompt allows need no second query.
``sectors``   Observed sectors per star from the vendored tess-point, capped at the
              latest sector with a public QLP target list on the build date
              (measured by probing MAST, recorded in the JSON).
``products``  QLP and TESS-SPOC per-sector target lists streamed from MAST once and
              cached as FULL sorted TIC-id arrays (``data/survey/cache/target_lists``),
              so any pool can be checked against them without re-downloading.
``twomin``    SPOC 2-minute presence per sector from the MIT per-sector target lists
              (bulk, one file per sector; source recorded per row).  No per-star
              MAST search is issued anywhere in this script.
``dwarf``     The Gaia-based main-sequence check from the TIC's own Gaia columns
              (rule below).
``xmatch``    The prompt-1 hard stop with freshly downloaded catalogs.
``select``    The population cuts in order, the pre-registered relaxation and size
              rules, the ranking (only if more than ``size_max`` qualify), and the
              per-star prompt-1 expected-new-signal score.
``targets``   ``data/survey/targets_p8.csv``, ``targets_p8.meta.json`` and
              ``data/survey/population_p8.json`` (every count the memo quotes).

Gaia dwarf check (fixed before the pool was examined):
  requires TIC ``plx`` > 0 with ``plx / e_plx`` >= 5 and finite ``GAIAmag``,
  ``gaiabp``, ``gaiarp``; M_G = GAIAmag + 5 log10(plx / 1000) + 5 (no extinction:
  |b| >= 20); BP-RP = gaiabp - gaiarp.  A star PASSES when BP-RP >= 1.6 and
  |M_G - (2.5 + 3.0 (BP-RP))| <= 1.25.  The locus 2.5 + 3.0 (BP-RP) is a
  straight line through the Pecaut & Mamajek main-sequence table in Gaia DR2
  bands (M0V 1.84/8.1, M3V 2.5/10.0, M5V 3.3/12.5); 1.25 mag keeps an
  unresolved equal-brightness binary (0.75 mag over the locus) and drops
  giants, subgiants, pre-main-sequence stars and stars whose TIC Teff is wrong
  for their colour.  Reasons are counted separately.

Everything the memo quotes comes from the JSON this script writes; the memo
(``docs/POPULATION_P8.md``) is prose around those numbers.  Nothing here is a
detection; the agent never submits anything anywhere.
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
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

warnings.simplefilter("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("p8pop")

SURVEY_DIR = REPO / "data" / "survey"
CACHE = SURVEY_DIR / "cache" / "p8"
STRIPS_DIR = CACHE / "tic_strips"
LISTS_DIR = SURVEY_DIR / "cache" / "target_lists"      # shared, pool-independent
TWOMIN_DIR = SURVEY_DIR / "cache" / "twomin_lists"     # shared, pool-independent

QLP_LIST_URL = "https://archive.stsci.edu/hlsps/qlp/target_lists/s{sector:04d}.csv"
SPOC_LIST_URL = "https://archive.stsci.edu/hlsps/tess-spoc/target_lists/s{sector:04d}.csv"
TWOMIN_URLS = (
    "https://tess.mit.edu/public/target_lists/2m/all_targets_S{sector:03d}_v{v}.csv",
    "https://tess.mit.edu/public/target_lists/all_targets_S{sector:03d}_v{v}.csv",
    "https://tess.mit.edu/wp-content/uploads/all_targets_S{sector:03d}_v{v}.csv",
)
UA = {"User-Agent": "tesshunter/0.1 (prompt 8 population build)"}

# ── Design constants (all recorded in the JSON output) ───────────────────────
DESIGN = {
    "seed": 20260904,
    "prompt": 8,
    # definition
    "teff_max_k": 3600.0,
    "radius_max_rsun": 0.45,
    "tmag_range": [12.5, 14.0],
    "min_abs_galactic_latitude_deg": 20.0,
    "lumclass_required": "DWARF where the TIC gives one; missing is allowed",
    "first_200s_sector": 56,
    "first_600s_sector": 27,
    "min_sectors_200s_with_lc": 3,
    "ffi_only_rule": "n_2min_sectors_in_search < n_search_sectors / 2 (strict minority); "
                     "search sectors = sectors >= 56 with a QLP or TESS-SPOC light curve",
    "size_min": 1000,
    "size_max": 2000,
    # relaxations, in order, only if fewer than size_min qualify
    "relax_1_tmag_ceiling": 14.5,
    "relax_1_condition": "coverage(14.0-14.5) >= 0.8 x coverage(13.5-14.0), where coverage is the fraction "
                         "of TIC-cut stars whose predicted sectors >= 56 have a QLP or TESS-SPOC light "
                         "curve in at least 3 of them",
    "relax_2_radius_rsun": 0.50,
    "never_relaxed": ["min_sectors_200s_with_lc", "teff_max_k"],
    # query envelope (wider than the definition on purpose)
    "tic_query_tmag_range": [12.5, 14.5],
    "tic_query_teff_range": [2000.0, 3600.0],
    "tic_query_radius_range": [0.01, 0.50],
    "tic_query_objtype": "STAR",
    "dec_strip_deg": 5.0,
    "match_radius_arcsec": 21.0,
    "gaia_dwarf_check": {
        "plx_snr_min": 5.0, "bp_rp_min": 1.6, "locus": "M_G = 2.5 + 3.0 * (BP-RP)",
        "locus_tolerance_mag": 1.25,
        "source": "TIC v8 Gaia DR2 columns GAIAmag, gaiabp, gaiarp, plx, e_plx; no extinction correction",
    },
    # ranking, only if more than size_max qualify
    "ranking": "per-star expected new signals under the prompt-1 model (survey_yield: DC15 grid, "
               "0.5-30 d, faint_m priors mid, photon-noise model), sectors = 200-s sectors with a light curve",
    "yield_period_range_days": [0.5, 30.0],
    "yield_prior_key": "faint_m",
}

TIC_COLUMNS = ["ID", "ra", "dec", "pmRA", "pmDEC", "Tmag", "e_Tmag", "Teff", "e_Teff", "logg", "rad", "e_rad",
               "mass", "e_mass", "lum", "lumclass", "contratio", "objType", "GAIA", "GAIAmag", "gaiabp",
               "gaiarp", "plx", "e_plx", "d", "e_d", "gallat", "gallong", "eclat", "eclong", "disposition",
               "Vmag", "Jmag", "Hmag", "Kmag", "numcont"]


# ── helpers ───────────────────────────────────────────────────────────────────
def _sha_ids(ids) -> str:
    arr = np.sort(np.asarray(list(ids), dtype=np.int64))
    return hashlib.sha256(arr.tobytes()).hexdigest()[:16]


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _head_ok(url: str, timeout: int = 60) -> tuple[bool, int | None]:
    req = urllib.request.Request(url, method="HEAD", headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            n = r.headers.get("Content-Length")
            return True, (int(n) if n else None)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False, None
        raise


def _sectors_str(s) -> str:
    return ",".join(str(int(x)) for x in sorted(s))


def _parse_sectors(s) -> list[int]:
    if s is None or (isinstance(s, float) and np.isnan(s)) or str(s).strip() == "":
        return []
    return [int(x) for x in str(s).split(",") if x.strip()]


# ── stage: tic ────────────────────────────────────────────────────────────────
def query_strip(dec_lo: float, dec_hi: float, design: dict) -> pd.DataFrame:
    from astroquery.mast import Catalogs

    last = None
    for attempt in range(4):
        try:
            tab = Catalogs.query_criteria(
                catalog="Tic",
                Tmag=list(design["tic_query_tmag_range"]),
                Teff=list(design["tic_query_teff_range"]),
                rad=list(design["tic_query_radius_range"]),
                dec=[dec_lo, dec_hi],
                objType=design["tic_query_objtype"],
            )
            df = tab.to_pandas()
            keep = [c for c in TIC_COLUMNS if c in df.columns]
            df = df[keep].rename(columns={"ID": "tic_id"})
            df["tic_id"] = pd.to_numeric(df["tic_id"]).astype("int64")
            return df
        except Exception as exc:
            last = exc
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"TIC strip query failed for dec [{dec_lo}, {dec_hi}]: {last}")


def stage_tic(design: dict) -> pd.DataFrame:
    """All TIC stars inside the query envelope, whole sky, then the |b| cut."""
    STRIPS_DIR.mkdir(parents=True, exist_ok=True)
    step = float(design["dec_strip_deg"])
    edges = np.arange(-90.0, 90.0 + 1e-9, step)
    frames = []
    for i, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
        p = STRIPS_DIR / f"strip_{i:02d}.csv"
        if p.exists():
            df = pd.read_csv(p)
        else:
            t0 = time.time()
            try:
                df = query_strip(float(lo), float(hi), design)
            except RuntimeError:
                # split the strip once and retry (a very dense strip)
                mid = 0.5 * (lo + hi)
                df = pd.concat([query_strip(float(lo), float(mid), design),
                                query_strip(float(mid), float(hi), design)], ignore_index=True)
            df["strip"] = i
            df.to_csv(p, index=False)
            log.info("tic strip %2d dec [%+5.1f, %+5.1f]: %5d rows in %.0fs", i, lo, hi, len(df), time.time() - t0)
        frames.append(df)
    allrows = pd.concat(frames, ignore_index=True)
    n_raw = len(allrows)
    allrows = allrows.drop_duplicates("tic_id", keep="first").reset_index(drop=True)
    n_dup = n_raw - len(allrows)
    allrows.to_csv(CACHE / "tic_all_strips.csv", index=False)
    bcut = allrows["gallat"].abs() >= design["min_abs_galactic_latitude_deg"]
    pool = allrows[bcut].reset_index(drop=True)
    pool.to_csv(CACHE / "pool_tic.csv", index=False)
    log.info("tic: %d rows in %d strips (%d duplicates dropped), %d with |b| >= %g", n_raw, len(frames), n_dup,
             len(pool), design["min_abs_galactic_latitude_deg"])
    (CACHE / "tic_counts.json").write_text(json.dumps(
        {"n_rows_all_strips": int(n_raw), "n_duplicates_dropped": int(n_dup), "n_unique": int(len(allrows)),
         "n_after_abs_b_cut": int(len(pool)), "n_strips": len(frames), "queried_utc": _utc()}, indent=1))
    return pool


# ── stage: sectors ────────────────────────────────────────────────────────────
def latest_public_sector(start: int = 100, stop: int = 130) -> dict:
    """Highest sector with a public QLP target list, by HEAD probes upward until a 404."""
    latest, probed = None, {}
    for s in range(start, stop + 1):
        ok, n = _head_ok(QLP_LIST_URL.format(sector=s))
        probed[s] = {"qlp_list": ok, "bytes": n}
        if ok:
            latest = s
        elif latest is not None and s > latest + 1:
            break
    for s in range(max(start, (latest or start) - 25), (latest or start) + 1):
        ok, n = _head_ok(SPOC_LIST_URL.format(sector=s))
        probed.setdefault(s, {})["tess_spoc_list"] = ok
    return {"latest_public_sector": latest, "probed_utc": _utc(), "probes": probed}


def stage_sectors(pool: pd.DataFrame, latest_sector: int) -> pd.DataFrame:
    from tesshunter._vendor import tess_stars2px as tp

    p = CACHE / "pool_sectors.csv"
    keyf = CACHE / "pool_sectors.key"
    key = _sha_ids(pool["tic_id"]) + f"-s{latest_sector}"
    if p.exists() and keyf.exists() and keyf.read_text().strip() == key:
        return pd.read_csv(p)
    t0 = time.time()
    ids = pool["tic_id"].to_numpy()
    ra, dec = pool["ra"].to_numpy(), pool["dec"].to_numpy()
    per: dict[int, set] = {}
    # tess-point grows its output arrays with np.append inside its star loop, which is
    # quadratic in the number of output rows: on 117k stars it never finishes.  Chunks of
    # 2,000 stars keep every call small; the result is identical.
    chunk = 2000
    for a in range(0, len(ids), chunk):
        res = tp.tess_stars2px_function_entry(ids[a:a + chunk], ra[a:a + chunk], dec[a:a + chunk])
        out_id, out_sec = np.asarray(res[0]), np.asarray(res[3]).astype(int)
        for i, sct in zip(out_id, out_sec):
            if int(sct) <= latest_sector:
                per.setdefault(int(i), set()).add(int(sct))
        if (a // chunk) % 10 == 0:
            log.info("sectors: %d / %d stars in %.0fs", min(a + chunk, len(ids)), len(ids), time.time() - t0)
    rows = [{"tic_id": int(t), "n_sectors_predicted": len(per.get(int(t), ())),
             "sectors_predicted": _sectors_str(per.get(int(t), ()))} for t in ids]
    df = pd.DataFrame(rows)
    df.to_csv(p, index=False)
    keyf.write_text(key)
    log.info("sectors: tess-point over %d stars in %.0fs (cap s%d)", len(ids), time.time() - t0, latest_sector)
    return df


# ── stage: products (full target lists, cached once) ─────────────────────────
def _fetch_full_list(url: str, timeout: int = 900) -> np.ndarray:
    req = urllib.request.Request(url, headers=UA)
    parts = []
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        reader = pd.read_csv(io.TextIOWrapper(resp, encoding="utf-8"), usecols=[0], chunksize=500_000,
                             comment=None)
        for chunk in reader:
            ids = pd.to_numeric(chunk.iloc[:, 0], errors="coerce").dropna().to_numpy(dtype=np.int64)
            parts.append(ids)
    return np.unique(np.concatenate(parts)) if parts else np.zeros(0, dtype=np.int64)


def ensure_list(name: str, sector: int, url: str) -> tuple[str, int]:
    """Cache one full target list as a sorted int64 array; returns (status, n)."""
    LISTS_DIR.mkdir(parents=True, exist_ok=True)
    npy = LISTS_DIR / f"{name}_s{sector:04d}.npy"
    st = LISTS_DIR / f"{name}_s{sector:04d}.status"
    if npy.exists() and st.exists() and st.read_text().strip() == "ok":
        return "ok", int(np.load(npy, mmap_mode="r").shape[0])
    t0 = time.time()
    try:
        ids = _fetch_full_list(url)
        status = "ok"
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            ids, status = np.zeros(0, dtype=np.int64), "missing"
        else:
            raise
    np.save(npy, ids)
    st.write_text(status)
    (LISTS_DIR / f"{name}_s{sector:04d}.meta.json").write_text(json.dumps(
        {"url": url, "status": status, "n_ids": int(len(ids)), "fetched_utc": _utc(),
         "seconds": round(time.time() - t0, 1)}, indent=1))
    log.info("list %-9s s%04d: %8d ids (%s, %.0fs)", name, sector, len(ids), status, time.time() - t0)
    return status, int(len(ids))


def stage_products(pool: pd.DataFrame, latest_sector: int, workers: int = 4) -> pd.DataFrame:
    jobs = [(name, s, tmpl.format(sector=s)) for s in range(1, latest_sector + 1)
            for name, tmpl in (("qlp", QLP_LIST_URL), ("tess-spoc", SPOC_LIST_URL))]
    status: dict[str, dict[int, str]] = {"qlp": {}, "tess-spoc": {}}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(ensure_list, n, s, u): (n, s) for n, s, u in jobs}
        for f in as_completed(futs):
            n, s = futs[f]
            status[n][s] = f.result()[0]
    ids = pool["tic_id"].to_numpy(dtype=np.int64)
    have: dict[str, dict[int, list[int]]] = {"qlp": {}, "tess-spoc": {}}
    for name in have:
        for s in range(1, latest_sector + 1):
            if status[name].get(s) != "ok":
                continue
            lst = np.load(LISTS_DIR / f"{name}_s{s:04d}.npy")
            hit = np.isin(ids, lst)
            for t in ids[hit]:
                have[name].setdefault(int(t), []).append(s)
    rows = []
    for t in ids:
        q = sorted(have["qlp"].get(int(t), []))
        sp = sorted(have["tess-spoc"].get(int(t), []))
        anyl = sorted(set(q) | set(sp))
        rows.append({"tic_id": int(t),
                     "n_sectors_qlp": len(q), "sectors_qlp": _sectors_str(q),
                     "n_sectors_tess_spoc": len(sp), "sectors_tess_spoc": _sectors_str(sp),
                     "n_sectors_any_lc": len(anyl), "sectors_any_lc": _sectors_str(anyl)})
    df = pd.DataFrame(rows)
    df.to_csv(CACHE / "pool_products.csv", index=False)
    missing = {n: sorted(s for s, st in d.items() if st != "ok") for n, d in status.items()}
    json.dump({"latest_sector": latest_sector, "lists_missing": missing, "generated_utc": _utc()},
              open(CACHE / "products_summary.json", "w"), indent=1)
    log.info("products: missing lists %s", missing)
    return df


# ── stage: twomin (MIT per-sector 2-minute target lists) ─────────────────────
def ensure_twomin(sector: int) -> tuple[str, int, str | None]:
    TWOMIN_DIR.mkdir(parents=True, exist_ok=True)
    npy = TWOMIN_DIR / f"s{sector:03d}.npy"
    st = TWOMIN_DIR / f"s{sector:03d}.status"
    meta = TWOMIN_DIR / f"s{sector:03d}.meta.json"
    if npy.exists() and st.exists() and st.read_text().strip() == "ok":
        return "ok", int(np.load(npy, mmap_mode="r").shape[0]), json.loads(meta.read_text())["url"]
    t0 = time.time()
    for v in (1, 2, 3, 4):
        for tmpl in TWOMIN_URLS:
            url = tmpl.format(sector=sector, v=v)
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=300) as r:
                    raw = r.read()
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    continue
                raise
            lines = [ln for ln in raw.decode("utf-8", "replace").splitlines() if ln and not ln.startswith("#")]
            df = pd.read_csv(io.StringIO("\n".join(lines)))
            col = next((c for c in df.columns if c.strip().upper() in ("TICID", "TIC_ID", "TIC")), df.columns[0])
            ids = np.unique(pd.to_numeric(df[col], errors="coerce").dropna().to_numpy(dtype=np.int64))
            np.save(npy, ids)
            st.write_text("ok")
            meta.write_text(json.dumps({"url": url, "n_ids": int(len(ids)), "fetched_utc": _utc(),
                                        "seconds": round(time.time() - t0, 1)}, indent=1))
            log.info("twomin s%03d: %6d ids from %s", sector, len(ids), url.split("/")[-1])
            return "ok", int(len(ids)), url
    np.save(npy, np.zeros(0, dtype=np.int64))
    st.write_text("missing")
    meta.write_text(json.dumps({"url": None, "n_ids": 0, "fetched_utc": _utc()}, indent=1))
    log.info("twomin s%03d: no list found", sector)
    return "missing", 0, None


def stage_twomin(pool: pd.DataFrame, latest_sector: int, first_sector: int = 1, workers: int = 4) -> pd.DataFrame:
    status = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(ensure_twomin, s): s for s in range(first_sector, latest_sector + 1)}
        for f in as_completed(futs):
            s = futs[f]
            status[s] = f.result()
    ids = pool["tic_id"].to_numpy(dtype=np.int64)
    have: dict[int, list[int]] = {}
    for s in range(first_sector, latest_sector + 1):
        if status[s][0] != "ok":
            continue
        lst = np.load(TWOMIN_DIR / f"s{s:03d}.npy")
        for t in ids[np.isin(ids, lst)]:
            have.setdefault(int(t), []).append(s)
    df = pd.DataFrame({"tic_id": ids,
                       "n_sectors_2min_list": [len(have.get(int(t), [])) for t in ids],
                       "sectors_2min_list": [_sectors_str(have.get(int(t), [])) for t in ids]})
    df.to_csv(CACHE / "pool_twomin.csv", index=False)
    missing = sorted(s for s, v in status.items() if v[0] != "ok")
    json.dump({"source": "MIT per-sector 2-minute target lists (tess.mit.edu/public/target_lists)",
               "sectors": {str(s): {"status": v[0], "n_ids": v[1], "url": v[2]} for s, v in sorted(status.items())},
               "sectors_missing": missing, "generated_utc": _utc()},
              open(CACHE / "twomin_summary.json", "w"), indent=1)
    log.info("twomin: %d sectors, missing %s", len(status), missing)
    return df


# ── stage: dwarf (Gaia-based main-sequence check from the TIC columns) ───────
def gaia_dwarf_check(pool: pd.DataFrame, design: dict) -> pd.DataFrame:
    g = design["gaia_dwarf_check"]
    G = pd.to_numeric(pool["GAIAmag"], errors="coerce").to_numpy(dtype=float)
    bp = pd.to_numeric(pool["gaiabp"], errors="coerce").to_numpy(dtype=float)
    rp = pd.to_numeric(pool["gaiarp"], errors="coerce").to_numpy(dtype=float)
    plx = pd.to_numeric(pool["plx"], errors="coerce").to_numpy(dtype=float)
    eplx = pd.to_numeric(pool["e_plx"], errors="coerce").to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        snr = plx / eplx
        mg = G + 5.0 * np.log10(plx / 1000.0) + 5.0
    bprp = bp - rp
    locus = 2.5 + 3.0 * bprp
    reason = np.full(len(pool), "pass", dtype=object)
    reason[~(np.isfinite(G) & np.isfinite(bp) & np.isfinite(rp))] = "no_gaia_photometry"
    m = reason == "pass"
    reason[m & ~(np.isfinite(plx) & (plx > 0))] = "no_parallax"
    m = reason == "pass"
    reason[m & ~(np.isfinite(snr) & (snr >= g["plx_snr_min"]))] = "parallax_snr_below_5"
    m = reason == "pass"
    reason[m & (bprp < g["bp_rp_min"])] = "too_blue_for_teff"
    m = reason == "pass"
    reason[m & (mg < locus - g["locus_tolerance_mag"])] = "overluminous_for_colour"
    m = reason == "pass"
    reason[m & (mg > locus + g["locus_tolerance_mag"])] = "underluminous_for_colour"
    return pd.DataFrame({"tic_id": pool["tic_id"].to_numpy(),
                         "gaia_abs_g": np.round(mg, 3), "gaia_bp_rp": np.round(bprp, 3),
                         "gaia_plx_snr": np.round(snr, 1), "gaia_dwarf_check": reason})


# ── stage: xmatch ─────────────────────────────────────────────────────────────
def stage_xmatch(pool: pd.DataFrame, design: dict, refresh: bool = True):
    from tesshunter import catalog_crossmatch as cx

    t0 = time.time()
    cat = cx.KnownObjectCatalog.load(refresh=refresh, match_radius_arcsec=design["match_radius_arcsec"])
    if cat.any_stale():
        raise RuntimeError("a catalog is stale; refusing to build the population on it")
    res = cat.check_many(pool[["tic_id", "ra", "dec"]])
    cat.write_manifest(SURVEY_DIR / "catalog_versions_p8.json")
    log.info("xmatch: %d stars against %s in %.0fs -> %s", len(pool), cat.stamp(), time.time() - t0,
             res["xmatch_status"].value_counts().to_dict())
    return res, cat


# ── stage: select ─────────────────────────────────────────────────────────────
def era_columns(pool: pd.DataFrame, design: dict) -> pd.DataFrame:
    f200, f600 = design["first_200s_sector"], design["first_600s_sector"]
    out = {"sectors_200s": [], "n_sectors_200s": [], "sectors_600s": [], "n_sectors_600s": [],
           "sectors_1800s": [], "n_sectors_1800s": [], "n_sectors_2min_in_search": [], "sectors_2min_in_search": [],
           "n_sectors_predicted_200s": []}
    for anyl, twom, pred in zip(pool["sectors_any_lc"], pool["sectors_2min_list"], pool["sectors_predicted"]):
        a = _parse_sectors(anyl)
        t = set(_parse_sectors(twom))
        p = _parse_sectors(pred)
        s200 = [s for s in a if s >= f200]
        s600 = [s for s in a if f600 <= s < f200]
        s1800 = [s for s in a if s < f600]
        two = sorted(t & set(s200))
        out["sectors_200s"].append(_sectors_str(s200)); out["n_sectors_200s"].append(len(s200))
        out["sectors_600s"].append(_sectors_str(s600)); out["n_sectors_600s"].append(len(s600))
        out["sectors_1800s"].append(_sectors_str(s1800)); out["n_sectors_1800s"].append(len(s1800))
        out["sectors_2min_in_search"].append(_sectors_str(two)); out["n_sectors_2min_in_search"].append(len(two))
        out["n_sectors_predicted_200s"].append(sum(1 for s in p if s >= f200))
    return pd.DataFrame(out, index=pool.index)


def p1_model_scores(stars: pd.DataFrame, design: dict, contam_fill: float) -> dict:
    """Per-star expected NEW signals under the prompt-1 model (ranking only)."""
    from tesshunter import survey_yield as sy
    lo, hi = design["yield_period_range_days"]
    cells = sy.occurrence_cells("m", sy.CENTRAL_MODEL["m"], hi, p_min=lo)
    st = pd.DataFrame({"Tmag": stars["Tmag"], "rad": stars["rad"], "mass": stars["mass"],
                       "contratio": stars["contratio"], "n_sectors_use": stars["n_sectors_200s"]}, index=stars.index)
    cls = sy.class_yields(st, cells, cells, contam_fill=contam_fill)
    new = {lvl: sy.new_signals_per_star(cls, design["yield_prior_key"], lvl) for lvl in ("low", "mid", "high")}
    return {"classes": cls, "new": new, "n_cells": len(cells)}


def coverage_by_tmag(pool: pd.DataFrame, design: dict) -> dict:
    """Fraction of TIC-cut stars (Tmag bins) with >= 3 predicted-and-delivered 200-s sectors."""
    base = pool[(pool["Teff"] < design["teff_max_k"]) & (pool["rad"] < design["radius_max_rsun"])
                & (pool["gallat"].abs() >= design["min_abs_galactic_latitude_deg"])]
    out = {}
    for lo, hi in ((12.5, 13.0), (13.0, 13.5), (13.5, 14.0), (14.0, 14.5)):
        sub = base[(base["Tmag"] >= lo) & (base["Tmag"] < hi)]
        pred3 = sub[sub["n_sectors_predicted_200s"] >= 3]
        out[f"{lo}-{hi}"] = {
            "n_stars": int(len(sub)), "n_with_3_predicted_200s": int(len(pred3)),
            "n_with_3_lc_200s": int((sub["n_sectors_200s"] >= 3).sum()),
            "frac_with_3_lc_200s": float((sub["n_sectors_200s"] >= 3).mean()) if len(sub) else None,
            "frac_with_3_lc_200s_given_3_predicted": float((pred3["n_sectors_200s"] >= 3).mean()) if len(pred3) else None,
            "mean_lc_over_predicted_200s": float((sub["n_sectors_200s"] / sub["n_sectors_predicted_200s"].clip(lower=1)).mean()) if len(sub) else None,
        }
    a, b = out["14.0-14.5"]["frac_with_3_lc_200s"], out["13.5-14.0"]["frac_with_3_lc_200s"]
    out["ratio_14.0-14.5_over_13.5-14.0"] = (a / b) if (a is not None and b) else None
    out["ceiling_extension_allowed"] = bool(a is not None and b and a >= 0.8 * b)
    return out


def apply_cuts(pool: pd.DataFrame, design: dict, tmag_hi: float, rad_max: float) -> tuple[pd.DataFrame, dict]:
    counts = {}
    s = pool
    counts["query_pool_abs_b"] = int(len(s))
    s = s[s["Teff"] < design["teff_max_k"]]; counts["teff_lt_3600"] = int(len(s))
    s = s[s["rad"] < rad_max]; counts[f"radius_lt_{rad_max:g}"] = int(len(s))
    lc = s["lumclass"].fillna("").astype(str).str.upper()
    s = s[(lc == "DWARF") | (lc == "")]; counts["lumclass_dwarf_or_missing"] = int(len(s))
    counts["lumclass_missing_kept"] = int((lc.loc[s.index] == "").sum())
    s = s[(s["Tmag"] >= design["tmag_range"][0]) & (s["Tmag"] < tmag_hi)]; counts[f"tmag_12.5_to_{tmag_hi:g}"] = int(len(s))
    counts["gaia_dwarf_check_reasons"] = s["gaia_dwarf_check"].value_counts().to_dict()
    s = s[s["gaia_dwarf_check"] == "pass"]; counts["gaia_dwarf_pass"] = int(len(s))
    s = s[s["n_sectors_200s"] >= design["min_sectors_200s_with_lc"]]; counts["ge_3_sectors_200s_with_lc"] = int(len(s))
    counts["zero_2min_sectors_in_search"] = int((s["n_sectors_2min_in_search"] == 0).sum())
    minority = s["n_sectors_2min_in_search"] < s["n_sectors_200s"] / 2.0
    counts["minority_2min_sectors_in_search"] = int(minority.sum())
    s = s[minority]; counts["ffi_only_minority"] = int(len(s))
    counts["xmatch_status"] = s["xmatch_status"].value_counts().to_dict()
    s = s[s["xmatch_status"] == "CLEAN"]; counts["hard_stop_clean"] = int(len(s))
    return s, counts


def stage_select(pool: pd.DataFrame, design: dict) -> tuple[pd.DataFrame, dict]:
    cov = coverage_by_tmag(pool, design)
    tmag_hi, rad_max = design["tmag_range"][1], design["radius_max_rsun"]
    sel, counts = apply_cuts(pool, design, tmag_hi, rad_max)
    relaxed = []
    if len(sel) < design["size_min"] and cov["ceiling_extension_allowed"]:
        tmag_hi = design["relax_1_tmag_ceiling"]
        sel, counts2 = apply_cuts(pool, design, tmag_hi, rad_max)
        relaxed.append({"relaxation": "tmag_ceiling", "to": tmag_hi, "counts": counts2})
        counts = counts2
    if len(sel) < design["size_min"]:
        rad_max = design["relax_2_radius_rsun"]
        sel, counts3 = apply_cuts(pool, design, tmag_hi, rad_max)
        relaxed.append({"relaxation": "radius", "to": rad_max, "counts": counts3})
        counts = counts3
    # contamination policy: the measured median of the CLEAN qualifying stars
    from tesshunter import survey_yield as sy
    fills = sy.contamination_fills(sel["contratio"])
    fill = fills[sy.CONTAMINATION_POLICY["central"]]
    sc = p1_model_scores(sel, design, fill)
    sel = sel.assign(expected_new_signals_mid=sc["new"]["mid"], expected_new_signals_low=sc["new"]["low"],
                     expected_new_signals_high=sc["new"]["high"],
                     class_A=sc["classes"]["A"], class_B=sc["classes"]["B"], class_C=sc["classes"]["C"])
    n_qualified = int(len(sel))
    ranked = False
    if n_qualified > design["size_max"]:
        sel = sel.sort_values("expected_new_signals_mid", ascending=False, kind="stable").head(design["size_max"])
        ranked = True
    sel = sel.sort_values("tic_id").reset_index(drop=True)
    info = {"coverage_by_tmag": cov, "counts": counts, "relaxations": relaxed,
            "tmag_ceiling_used": tmag_hi, "radius_max_used": rad_max,
            "n_qualified": n_qualified, "ranked_and_cut": ranked, "n_targets": int(len(sel)),
            "contamination": {"policy": sy.CONTAMINATION_POLICY["central"], "fills": fills,
                              "n_missing": int(sel["contratio"].isna().sum()),
                              "fraction_missing": float(sel["contratio"].isna().mean()) if len(sel) else None},
            "p1_model": {"n_cells": sc["n_cells"], "period_range": design["yield_period_range_days"],
                         "sum_expected_new_mid": float(sel["expected_new_signals_mid"].sum()),
                         "sum_expected_new_low": float(sel["expected_new_signals_low"].sum()),
                         "sum_expected_new_high": float(sel["expected_new_signals_high"].sum()),
                         "note": "prompt-1 photon-noise model with adopted efficiencies; ranking only. "
                                 "The expectation that decides Part 1f uses the measured curve."}}
    return sel, info


# ── stage: targets ────────────────────────────────────────────────────────────
def write_targets(sel: pd.DataFrame, info: dict, design: dict, cat_stamp: str, extra: dict) -> None:
    from tesshunter import survey_yield as sy
    fill = info["contamination"]["fills"][sy.CONTAMINATION_POLICY["central"]]
    missing = sel["contratio"].isna()
    products = [";".join(p for p in (("qlp" if q > 0 else ""), ("tess-spoc" if s > 0 else "")) if p)
                for q, s in zip(sel["n_sectors_qlp"], sel["n_sectors_tess_spoc"])]
    out = pd.DataFrame({
        "tic_id": sel["tic_id"].astype("int64"),
        "ra_deg": sel["ra"].round(6), "dec_deg": sel["dec"].round(6),
        "tmag": sel["Tmag"].round(3), "teff_k": sel["Teff"].round(0),
        "radius_rsun": sel["rad"].round(3), "mass_msun": sel["mass"].round(3),
        "logg": sel["logg"].round(3) if "logg" in sel else np.nan,
        "contamination_ratio": sel["contratio"].round(4),
        "contamination_ratio_missing": missing.astype(bool),
        "contamination_ratio_used": np.where(missing, fill, sel["contratio"]).round(4),
        "contamination_policy": np.where(missing, sy.CONTAMINATION_POLICY["central"], "measured"),
        "galactic_lat_deg": sel["gallat"].round(2),
        "n_sectors_predicted": sel["n_sectors_predicted"].astype(int), "sectors_predicted": sel["sectors_predicted"],
        "n_sectors_with_lc": sel["n_sectors_any_lc"].astype(int),
        "sectors_qlp": sel["sectors_qlp"], "sectors_tess_spoc": sel["sectors_tess_spoc"],
        "lc_products_available": products,
        "n_sectors_200s": sel["n_sectors_200s"].astype(int), "sectors_200s": sel["sectors_200s"],
        "n_sectors_600s": sel["n_sectors_600s"].astype(int), "sectors_600s": sel["sectors_600s"],
        "n_sectors_1800s": sel["n_sectors_1800s"].astype(int), "sectors_1800s": sel["sectors_1800s"],
        "n_sectors_2min": sel["n_sectors_2min_list"].astype(int), "sectors_2min": sel["sectors_2min_list"],
        "n_sectors_2min_in_search": sel["n_sectors_2min_in_search"].astype(int),
        "twomin_source": "mit_target_lists",
        "gaia_dwarf_check": sel["gaia_dwarf_check"], "gaia_abs_g": sel["gaia_abs_g"],
        "gaia_bp_rp": sel["gaia_bp_rp"], "gaia_plx_snr": sel["gaia_plx_snr"],
        "tic_gaia_id": sel["GAIA"],
        "pmra_mas_yr": sel["pmRA"].round(2) if "pmRA" in sel else np.nan,
        "pmdec_mas_yr": sel["pmDEC"].round(2) if "pmDEC" in sel else np.nan,
        "crossmatch_status": sel["xmatch_status"],
        "nearest_known_object_sep_arcsec": sel["xmatch_nearest_known_sep_arcsec"].round(1),
        "expected_new_signals_mid": sel["expected_new_signals_mid"].map(lambda v: f"{v:.2e}"),
        "class_A_detectable": sel["class_A"].map(lambda v: f"{v:.2e}"),
        "class_B_detectable": sel["class_B"].map(lambda v: f"{v:.2e}"),
        "class_C_detectable": sel["class_C"].map(lambda v: f"{v:.2e}"),
        "tile": sel["strip"].astype(int), "stratum": "p8_mdwarf_200s",
        "occurrence_model": f"m={sy.CENTRAL_MODEL['m']}",
        "catalog_versions": cat_stamp,
    })
    SURVEY_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(SURVEY_DIR / "targets_p8.csv", index=False)
    meta = {"generated_utc": _utc(), "n_targets": int(len(out)), "design": design, "catalog_stamp": cat_stamp,
            "selection": {k: v for k, v in info.items() if k != "coverage_by_tmag"},
            "coverage_by_tmag": info["coverage_by_tmag"], **extra}
    (SURVEY_DIR / "targets_p8.meta.json").write_text(json.dumps(meta, indent=1, default=float))
    log.info("targets_p8.csv: %d rows", len(out))


def population_json(pool: pd.DataFrame, sel: pd.DataFrame, info: dict, design: dict, cat, extra: dict) -> dict:
    def q(sr):
        sr = pd.to_numeric(sr, errors="coerce").dropna()
        return [float(x) for x in sr.quantile([.1, .25, .5, .75, .9])] if len(sr) else None
    base = pool[(pool["Teff"] < design["teff_max_k"]) & (pool["rad"] < design["radius_max_rsun"])
                & (pool["Tmag"] >= design["tmag_range"][0]) & (pool["Tmag"] < design["tmag_range"][1])]
    model = {
        "design": design, "generated_utc": _utc(), "seed": design["seed"],
        "tic_query": json.loads((CACHE / "tic_counts.json").read_text()),
        "sectors": extra.get("latest_sector_probe"),
        "products": json.loads((CACHE / "products_summary.json").read_text()),
        "twomin": {k: v for k, v in json.loads((CACHE / "twomin_summary.json").read_text()).items() if k != "sectors"},
        "twomin_sectors_missing": json.loads((CACHE / "twomin_summary.json").read_text())["sectors_missing"],
        "catalog_manifest": {k: v for k, v in cat.manifest().items() if k in ("stamp", "n_rows", "n_unique_tic", "generated_utc")},
        "pool_xmatch": pool["xmatch_status"].value_counts().to_dict(),
        "pool_xmatch_reject_by_source": pool.loc[pool["xmatch_status"] == "REJECT", "xmatch_tic_sources"].value_counts().head(20).to_dict(),
        "gaia_dwarf_check_pool_definition_band": base["gaia_dwarf_check"].value_counts().to_dict(),
        "selection": {k: v for k, v in info.items()},
        "targets": {
            "n": int(len(sel)),
            "tmag_quantiles": q(sel["Tmag"]), "teff_quantiles": q(sel["Teff"]), "radius_quantiles": q(sel["rad"]),
            "mass_quantiles": q(sel["mass"]), "n_sectors_200s_quantiles": q(sel["n_sectors_200s"]),
            "n_sectors_600s_quantiles": q(sel["n_sectors_600s"]), "n_sectors_2min_in_search_quantiles": q(sel["n_sectors_2min_in_search"]),
            "n_with_zero_2min_in_search": int((sel["n_sectors_2min_in_search"] == 0).sum()) if len(sel) else 0,
            "n_with_any_600s": int((sel["n_sectors_600s"] > 0).sum()) if len(sel) else 0,
            "n_with_tess_spoc": int((sel["n_sectors_tess_spoc"] > 0).sum()) if len(sel) else 0,
            "n_with_qlp": int((sel["n_sectors_qlp"] > 0).sum()) if len(sel) else 0,
            "n_qlp_only_in_200s": int(sum(1 for a, b in zip(sel["sectors_200s"], sel["sectors_tess_spoc"])
                                          if not (set(_parse_sectors(a)) & set(_parse_sectors(b))))) if len(sel) else 0,
            "gallat_abs_quantiles": q(sel["gallat"].abs()), "dec_quantiles": q(sel["dec"]),
            "n_north": int((sel["dec"] > 0).sum()) if len(sel) else 0,
            "contamination_missing_fraction": float(sel["contratio"].isna().mean()) if len(sel) else None,
            "contamination_median_measured": float(sel["contratio"].median()) if len(sel) else None,
            "depth_2re_ppt_median": float(np.median((2.0 * 0.009168 / sel["rad"]) ** 2 * 1000)) if len(sel) else None,
            "depth_1re_ppt_median": float(np.median((1.0 * 0.009168 / sel["rad"]) ** 2 * 1000)) if len(sel) else None,
        },
    }
    (SURVEY_DIR / "population_p8.json").write_text(json.dumps(model, indent=1, default=float))
    return model


# ── orchestration ─────────────────────────────────────────────────────────────
def build(stages: list[str], design: dict, workers: int, refresh_catalogs: bool) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "design.json").write_text(json.dumps(design, indent=1))
    do = set(stages)
    pool = stage_tic(design) if ("tic" in do or not (CACHE / "pool_tic.csv").exists()) else pd.read_csv(CACHE / "pool_tic.csv")
    if do <= {"tic"}:
        return
    probe_path = CACHE / "latest_sector.json"
    if probe_path.exists() and "sectors" not in do:
        probe = json.loads(probe_path.read_text())
    else:
        probe = latest_public_sector()
        probe_path.write_text(json.dumps(probe, indent=1))
    latest = int(probe["latest_public_sector"])
    log.info("latest public sector (QLP target list present): %d", latest)
    sectors = stage_sectors(pool, latest)
    pool = pool.merge(sectors, on="tic_id", how="left")
    if do <= {"tic", "sectors"}:
        return
    if "products" in do or not (CACHE / "pool_products.csv").exists():
        products = stage_products(pool, latest, workers=workers)
    else:
        products = pd.read_csv(CACHE / "pool_products.csv")
    pool = pool.merge(products, on="tic_id", how="left")
    if "twomin" in do or not (CACHE / "pool_twomin.csv").exists():
        twomin = stage_twomin(pool, latest, workers=workers)
    else:
        twomin = pd.read_csv(CACHE / "pool_twomin.csv")
    pool = pool.merge(twomin, on="tic_id", how="left")
    if do <= {"tic", "sectors", "products", "twomin"}:
        pool.to_csv(CACHE / "pool_after_products.csv", index=False)
        return
    pool = pd.concat([pool, era_columns(pool, design)], axis=1)
    pool = pool.merge(gaia_dwarf_check(pool, design), on="tic_id", how="left")
    xm, cat = stage_xmatch(pool, design, refresh=refresh_catalogs)
    pool = pd.concat([pool, xm], axis=1)
    pool.to_csv(CACHE / "pool_after_xmatch.csv", index=False)
    sel, info = stage_select(pool, design)
    log.info("select: %s", json.dumps(info["counts"]))
    log.info("select: qualified %d, ranked %s, targets %d, relaxations %s", info["n_qualified"],
             info["ranked_and_cut"], info["n_targets"], [r["relaxation"] for r in info["relaxations"]])
    extra = {"latest_sector_probe": probe}
    write_targets(sel, info, design, cat.stamp(), extra)
    population_json(pool, sel, info, design, cat, extra)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stages", nargs="*", default=["all"], help="tic sectors products twomin xmatch select targets | all")
    ap.add_argument("--seed", type=int, default=DESIGN["seed"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-refresh-catalogs", action="store_true", help="use the 7-day catalog cache instead of re-downloading")
    a = ap.parse_args(argv)
    design = dict(DESIGN, seed=a.seed)
    stages = ["tic", "sectors", "products", "twomin", "xmatch", "select", "targets"] if "all" in a.stages else a.stages
    build(stages, design, a.workers, not a.no_refresh_catalogs)


if __name__ == "__main__":
    main()
