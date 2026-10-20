#!/usr/bin/env python
"""Build the prompt-K1 population: K dwarfs plus early M dwarfs with archival FFI light curves.

Modeled on ``scripts/build_p8_population.py`` (which is not edited).  Stages, each cached under
``D:/tesshunter_k1/pop`` and skipped when cached:

``tic``       All-sky TIC query in declination strips on the query envelope (Teff 3500-5400 K,
              Tmag 9.5-13.6, radius 0.35-1.15 Rsun, objType STAR).  A strip that returns 50,000 or
              more rows is split in half and both halves are queried again, recursively, so no
              query can be silently truncated.  Cuts are applied locally (``select``).
``sectors``   Observed sectors per star from the vendored tess-point (chunks of 2,000 stars).
``products``  QLP and TESS-SPOC per-sector target lists (shared cache ``data/survey/cache/target_lists``).
``twomin``    SPOC 2-minute presence per sector (shared cache ``data/survey/cache/twomin_lists``).
``usable``    n_usable / n_usable_s56 / n_2min_in_search under the K1 usable-sector rule
              (``k1/protocol/sector_policy_k1.py``).
``gaia``      Main-sequence check against the tabulated dwarf sequence (``k1/protocol/gaia_ms_k1.py``)
              from the TIC's Gaia columns.
``xmatch``    The K1 hard stop (``k1/protocol/catalog_adapter_k1.py``) on the K1 catalogue snapshot.
``select``    The A3 cuts in order, counts after each.
``rank``      E_new per star (``k1/protocol/rank_k1.py``), separately for class K and class eM;
              writes ``k1/survey/targets_k1.csv`` and ``k1/survey/reserve_k1.csv``.

Nothing here is a detection.  Nothing is submitted anywhere.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "k1" / "protocol"))
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data" / "cache" / "lightkurve"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

warnings.simplefilter("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("k1pop")

POP = Path(os.environ.get("K1_POP_DIR", r"D:\tesshunter_k1\pop"))
STRIPS_DIR = POP / "tic_strips"
SURVEY_CACHE = REPO / "data" / "survey" / "cache"
LISTS_DIR = SURVEY_CACHE / "target_lists"
TWOMIN_DIR = SURVEY_CACHE / "twomin_lists"
K1 = REPO / "k1"

DESIGN = {
    "prompt": "K1",
    "seed": 20261007,
    "tic_query_teff_range": [3500.0, 5400.0],
    "tic_query_tmag_range": [9.5, 13.6],
    "tic_query_radius_range": [0.35, 1.15],
    "tic_query_objtype": "STAR",
    "dec_strip_deg": 5.0,
    "max_rows_per_query": 50000,
    "min_strip_deg": 0.05,
    "query_workers": 3,
    # A3 cuts, in order
    "class_K": {"teff": [3900.0, 5300.0], "radius": [0.55, 1.0]},
    "class_eM": {"teff": [3600.0, 3899.0], "radius": [0.40, 0.70]},
    "logg_min_where_present": 4.3,
    "tmag_range": [10.0, 13.5],
    "min_abs_b_deg": 20.0,
    "lmc": {"ra": 80.894, "dec": -69.756, "min_sep_deg": 10.0},
    "smc": {"ra": 13.187, "dec": -72.829, "min_sep_deg": 4.0},
    "contratio_max": 0.10,
    "gaia": {"plx_snr_min": 5.0, "reject_brighter_mag": 1.0, "reject_fainter_mag": 1.0,
             "flag_binary_brighter_mag": [0.5, 1.0], "ruwe_flag": 1.4},
    "ffi_rule": "n_2min_in_search < n_usable / 2 (strict minority)",
    "min_n_usable": 5,
    "survey_n": {"K": 7000, "eM": 3000},
    "reserve_ranks": {"K": [7001, 17000], "eM": [3001, 8000]},
}

TIC_COLUMNS = ["ID", "ra", "dec", "pmRA", "pmDEC", "Tmag", "e_Tmag", "Teff", "e_Teff", "logg", "rad", "e_rad",
               "mass", "e_mass", "lum", "lumclass", "contratio", "objType", "GAIA", "GAIAmag", "gaiabp",
               "gaiarp", "plx", "e_plx", "d", "e_d", "gallat", "gallong", "eclat", "eclong", "disposition",
               "Vmag", "Jmag", "Hmag", "Kmag", "numcont", "priority"]


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha_ids(ids) -> str:
    arr = np.sort(np.asarray(list(ids), dtype=np.int64))
    return hashlib.sha256(arr.tobytes()).hexdigest()[:16]


def _sectors_str(s) -> str:
    return ",".join(str(int(x)) for x in sorted(s))


def _parse_sectors(s) -> list[int]:
    if s is None or (isinstance(s, float) and np.isnan(s)) or str(s).strip() == "":
        return []
    return [int(x) for x in str(s).split(",") if x.strip()]


def _progress(stage: str, **kw) -> None:
    POP.mkdir(parents=True, exist_ok=True)
    body = {"stage": stage, "utc": _utc(), "pid": os.getpid(), **kw}
    tmp = POP / f"progress.json.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(body, indent=1), encoding="utf-8")
    for attempt in range(10):
        try:
            os.replace(tmp, POP / "progress.json")
            return
        except PermissionError:
            time.sleep(0.2 * (attempt + 1))


# ── stage: tic ────────────────────────────────────────────────────────────────
def query_strip(dec_lo: float, dec_hi: float, design: dict) -> pd.DataFrame:
    from astroquery.mast import Catalogs

    import threading

    def bounded(timeout_s: float = 420.0):
        """One MAST query in a daemon thread; a query still running after ``timeout_s`` is abandoned
        (the MAST-hang signature: a strip query sat 24 min without returning on 2026-10-08)."""
        box = {}

        def run():
            try:
                box["tab"] = Catalogs.query_criteria(
                    catalog="Tic",
                    Tmag=list(design["tic_query_tmag_range"]),
                    Teff=list(design["tic_query_teff_range"]),
                    rad=list(design["tic_query_radius_range"]),
                    dec=[dec_lo, dec_hi],
                    objType=design["tic_query_objtype"],
                )
            except Exception as exc:  # noqa: BLE001
                box["error"] = exc
        th = threading.Thread(target=run, daemon=True)
        th.start()
        th.join(timeout_s)
        if th.is_alive():
            raise TimeoutError(f"MAST TIC query exceeded {timeout_s:.0f} s")
        if "error" in box:
            raise box["error"]
        return box["tab"]

    last = None
    for attempt in range(5):
        try:
            tab = bounded()
            df = tab.to_pandas()
            keep = [c for c in TIC_COLUMNS if c in df.columns]
            df = df[keep].rename(columns={"ID": "tic_id"})
            df["tic_id"] = pd.to_numeric(df["tic_id"]).astype("int64")
            return df
        except Exception as exc:  # network / service errors: bounded retry
            last = exc
            log.warning("strip [%.3f, %.3f] attempt %d failed: %s", dec_lo, dec_hi, attempt + 1, str(exc)[:200])
            time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"TIC strip query failed for dec [{dec_lo}, {dec_hi}]: {last}")


def _strip_file(lo: float, hi: float) -> Path:
    return STRIPS_DIR / f"strip_{lo:+08.3f}_{hi:+08.3f}.csv"


def fetch_strip_recursive(lo: float, hi: float, design: dict, ledger: list) -> list[Path]:
    """Query [lo, hi); if the result has >= max_rows rows, split in half and recurse.
    Accepted strips (< max_rows) are cached as CSV; oversize results are recorded and discarded."""
    path = _strip_file(lo, hi)
    if path.exists():
        return [path]
    t0 = time.time()
    df = query_strip(lo, hi, design)
    n = len(df)
    if n >= design["max_rows_per_query"] and (hi - lo) > design["min_strip_deg"]:
        ledger.append({"dec_lo": lo, "dec_hi": hi, "rows": n, "action": "split", "seconds": round(time.time() - t0, 1)})
        log.info("strip [%+.3f, %+.3f]: %d rows >= cap; splitting", lo, hi, n)
        mid = round(0.5 * (lo + hi), 4)
        return fetch_strip_recursive(lo, mid, design, ledger) + fetch_strip_recursive(mid, hi, design, ledger)
    if n >= design["max_rows_per_query"]:
        raise RuntimeError(f"strip [{lo}, {hi}] still has {n} rows at the minimum width")
    df["strip_lo"] = lo
    df["strip_hi"] = hi
    tmp = path.with_name(path.name + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)
    ledger.append({"dec_lo": lo, "dec_hi": hi, "rows": n, "action": "accepted", "seconds": round(time.time() - t0, 1)})
    log.info("strip [%+.3f, %+.3f]: %d rows in %.0fs", lo, hi, n, time.time() - t0)
    return [path]


def stage_tic(design: dict) -> pd.DataFrame:
    STRIPS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = POP / "tic_all.pkl"
    if out_path.exists():
        return pd.read_pickle(out_path)
    step = float(design["dec_strip_deg"])
    edges = np.arange(-90.0, 90.0 + 1e-9, step)
    pairs = [(float(a), float(b)) for a, b in zip(edges[:-1], edges[1:])]
    ledger: list = []
    done = []
    t0 = time.time()

    def one(pair):
        return fetch_strip_recursive(pair[0], pair[1], design, ledger)

    with ThreadPoolExecutor(max_workers=int(design["query_workers"])) as ex:
        for i, paths in enumerate(ex.map(one, pairs)):
            done.extend(paths)
            _progress("tic", strips_done=i + 1, strips_total=len(pairs), files=len(done),
                      elapsed_s=round(time.time() - t0, 1))
    # Gaia DR2 source ids are 19-digit integers: read them as strings (float64 loses the last digits;
    # found 2026-10-08 when DR3 RUWE matched only ~35% of ids)
    frames = [pd.read_csv(p, dtype={"GAIA": "string"}) for p in sorted(set(done))]
    allrows = pd.concat(frames, ignore_index=True)
    n_raw = len(allrows)
    allrows = allrows.drop_duplicates("tic_id", keep="first").reset_index(drop=True)
    for c in ("lumclass", "objType", "disposition", "GAIA"):
        if c in allrows:
            allrows[c] = allrows[c].astype("string")
    allrows.to_pickle(out_path)
    counts = {"n_rows_all_strips": int(n_raw), "n_unique": int(len(allrows)),
              "n_duplicates_dropped": int(n_raw - len(allrows)), "n_files": len(set(done)),
              "ledger": ledger, "queried_utc": _utc(), "wall_s": round(time.time() - t0, 1),
              "max_rows_in_accepted_strip": int(max(r["rows"] for r in ledger if r["action"] == "accepted")) if ledger else None}
    (POP / "tic_counts.json").write_text(json.dumps(counts, indent=1))
    log.info("tic: %d rows (%d unique) in %.0fs", n_raw, len(allrows), time.time() - t0)
    return allrows


# ── stage: sectors (tess-point) ───────────────────────────────────────────────
def stage_sectors(pool: pd.DataFrame, max_sector: int = 134) -> pd.DataFrame:
    from tesshunter._vendor import tess_stars2px as tp

    p = POP / "pool_sectors.pkl"
    key = _sha_ids(pool["tic_id"]) + f"-s{max_sector}"
    keyf = POP / "pool_sectors.key"
    if p.exists() and keyf.exists() and keyf.read_text().strip() == key:
        return pd.read_pickle(p)
    t0 = time.time()
    ids = pool["tic_id"].to_numpy()
    ra, dec = pool["ra"].to_numpy(), pool["dec"].to_numpy()
    per: dict[int, set] = {}
    chunk = 2000
    for a in range(0, len(ids), chunk):
        res = tp.tess_stars2px_function_entry(ids[a:a + chunk], ra[a:a + chunk], dec[a:a + chunk])
        out_id, out_sec = np.asarray(res[0]), np.asarray(res[3]).astype(int)
        for i, sct in zip(out_id, out_sec):
            if int(sct) <= max_sector:
                per.setdefault(int(i), set()).add(int(sct))
        if (a // chunk) % 25 == 0:
            _progress("sectors", stars_done=int(min(a + chunk, len(ids))), stars_total=int(len(ids)),
                      elapsed_s=round(time.time() - t0, 1))
            log.info("sectors: %d / %d stars in %.0fs", min(a + chunk, len(ids)), len(ids), time.time() - t0)
    df = pd.DataFrame({"tic_id": ids,
                       "sectors_predicted": [_sectors_str(per.get(int(t), ())) for t in ids],
                       "n_sectors_predicted_le105": [sum(1 for s in per.get(int(t), ()) if s <= 105) for t in ids]})
    df.to_pickle(p)
    keyf.write_text(key)
    log.info("sectors: tess-point over %d stars in %.0fs", len(ids), time.time() - t0)
    return df


# ── stage: products / twomin (cached shared lists, never overwritten) ─────────
def _list_status(path_status: Path) -> str:
    return path_status.read_text().strip() if path_status.exists() else "absent"


def stage_products(pool: pd.DataFrame, max_sector: int = 105) -> pd.DataFrame:
    p = POP / "pool_products.pkl"
    if p.exists():
        return pd.read_pickle(p)
    ids = pool["tic_id"].to_numpy(dtype=np.int64)
    have: dict[str, dict[int, list[int]]] = {"qlp": {}, "tess-spoc": {}}
    status = {}
    for name in have:
        for s in range(1, max_sector + 1):
            st = _list_status(LISTS_DIR / f"{name}_s{s:04d}.status")
            status[f"{name}_{s}"] = st
            if st != "ok":
                continue
            lst = np.load(LISTS_DIR / f"{name}_s{s:04d}.npy")
            for t in ids[np.isin(ids, lst)]:
                have[name].setdefault(int(t), []).append(s)
    df = pd.DataFrame({"tic_id": ids,
                       "sectors_qlp": [_sectors_str(have["qlp"].get(int(t), [])) for t in ids],
                       "sectors_tess_spoc": [_sectors_str(have["tess-spoc"].get(int(t), [])) for t in ids]})
    df.to_pickle(p)
    (POP / "products_status.json").write_text(json.dumps(status, indent=1))
    return df


def stage_twomin(pool: pd.DataFrame, max_sector: int = 105) -> pd.DataFrame:
    p = POP / "pool_twomin.pkl"
    if p.exists():
        return pd.read_pickle(p)
    ids = pool["tic_id"].to_numpy(dtype=np.int64)
    have: dict[int, list[int]] = {}
    status = {}
    for s in range(1, max_sector + 1):
        st = _list_status(TWOMIN_DIR / f"s{s:03d}.status")
        status[s] = st
        if st != "ok":
            continue
        lst = np.load(TWOMIN_DIR / f"s{s:03d}.npy")
        for t in ids[np.isin(ids, lst)]:
            have.setdefault(int(t), []).append(s)
    df = pd.DataFrame({"tic_id": ids, "sectors_2min": [_sectors_str(have.get(int(t), [])) for t in ids]})
    df.to_pickle(p)
    (POP / "twomin_status.json").write_text(json.dumps(status, indent=1))
    return df


# ── stage: usable sectors ─────────────────────────────────────────────────────
def stage_usable(pool: pd.DataFrame) -> pd.DataFrame:
    import sector_policy_k1 as SP
    rows = {"n_usable": [], "n_usable_s56": [], "sectors_usable": [], "n_2min_in_search": [],
            "n_usable_1800": [], "n_usable_600": [], "n_usable_200": []}
    for q, sp, two in zip(pool["sectors_qlp"], pool["sectors_tess_spoc"], pool["sectors_2min"]):
        use = SP.usable_sectors(_parse_sectors(q), _parse_sectors(sp))
        u = sorted(use)
        tw = set(_parse_sectors(two))
        rows["sectors_usable"].append(_sectors_str(u))
        rows["n_usable"].append(len(u))
        rows["n_usable_s56"].append(sum(1 for s in u if s >= 56))
        rows["n_2min_in_search"].append(len(tw & set(u)))
        rows["n_usable_1800"].append(sum(1 for s in u if s <= 26))
        rows["n_usable_600"].append(sum(1 for s in u if 27 <= s <= 55))
        rows["n_usable_200"].append(sum(1 for s in u if s >= 56))
    return pd.DataFrame(rows, index=pool.index)


# ── stage: gaia (main-sequence check from the TIC Gaia columns) ──────────────
def stage_gaia(pool: pd.DataFrame, design: dict) -> pd.DataFrame:
    import gaia_ms_k1 as GM
    return GM.check_frame(pool, design["gaia"])


# ── stage: select (the A3 cuts, counts after each) ────────────────────────────
def angsep_deg(ra1, dec1, ra2, dec2):
    r1, d1, r2, d2 = map(np.radians, (ra1, dec1, ra2, dec2))
    c = np.sin(d1) * np.sin(d2) + np.cos(d1) * np.cos(d2) * np.cos(r1 - r2)
    return np.degrees(np.arccos(np.clip(c, -1, 1)))


def star_class(pool: pd.DataFrame, design: dict) -> np.ndarray:
    teff = pd.to_numeric(pool["Teff"], errors="coerce").to_numpy(float)
    rad = pd.to_numeric(pool["rad"], errors="coerce").to_numpy(float)
    k, e = design["class_K"], design["class_eM"]
    cls = np.full(len(pool), "", dtype=object)
    isk = (teff >= k["teff"][0]) & (teff <= k["teff"][1]) & (rad >= k["radius"][0]) & (rad <= k["radius"][1])
    ise = (teff >= e["teff"][0]) & (teff <= e["teff"][1]) & (rad >= e["radius"][0]) & (rad <= e["radius"][1])
    cls[isk] = "K"
    cls[ise & ~isk] = "eM"
    return cls


def cuts_1_to_4(pool: pd.DataFrame, design: dict) -> tuple[pd.DataFrame, list]:
    """A3 cuts 1-4 on the whole query pool (no list data needed), counts after each."""
    counts = []
    s = pool.copy()
    s["k1_class"] = star_class(s, design)

    def rec(name):
        counts.append({"cut": name, "n_total": int(len(s)), "n_K": int((s.k1_class == "K").sum()),
                       "n_eM": int((s.k1_class == "eM").sum())})

    rec("0_query_envelope_all_sky")
    s = s[s.k1_class != ""]
    logg = pd.to_numeric(s["logg"], errors="coerce")
    lc = s["lumclass"].astype("string").fillna("").str.upper()
    s = s[(~(logg < design["logg_min_where_present"])) & (lc != "GIANT")]
    rec("1_class_teff_radius_logg_lumclass")
    tm = pd.to_numeric(s["Tmag"], errors="coerce")
    s = s[(tm >= design["tmag_range"][0]) & (tm <= design["tmag_range"][1])]
    rec("2_tmag_10_13.5")
    b = pd.to_numeric(s["gallat"], errors="coerce").abs()
    sep_l = angsep_deg(s["ra"].to_numpy(float), s["dec"].to_numpy(float), design["lmc"]["ra"], design["lmc"]["dec"])
    sep_s = angsep_deg(s["ra"].to_numpy(float), s["dec"].to_numpy(float), design["smc"]["ra"], design["smc"]["dec"])
    s = s.assign(sep_lmc_deg=sep_l, sep_smc_deg=sep_s)
    s = s[(b >= design["min_abs_b_deg"]) & (s.sep_lmc_deg > design["lmc"]["min_sep_deg"])
          & (s.sep_smc_deg > design["smc"]["min_sep_deg"])]
    rec("3_abs_b_20_lmc_smc")
    cr = pd.to_numeric(s["contratio"], errors="coerce")
    s = s[np.isfinite(cr) & (cr <= design["contratio_max"])]
    rec("4_contratio_measured_le_0.10")
    return s, counts


def cuts_5_to_8(s: pd.DataFrame, counts: list, design: dict) -> pd.DataFrame:
    def rec(name):
        counts.append({"cut": name, "n_total": int(len(s)), "n_K": int((s.k1_class == "K").sum()),
                       "n_eM": int((s.k1_class == "eM").sum())})
    s = s[s["gaia_ms_status"] != "REJECT"]
    rec("5_gaia_main_sequence")
    s = s[s["xmatch_status"] != "REJECT"]
    rec("6_hard_stop_not_reject")
    s = s[s["n_2min_in_search"] < s["n_usable"] / 2.0]
    rec("7_ffi_strict_minority")
    s = s[s["n_usable"] >= design["min_n_usable"]]
    rec("8_n_usable_ge_5")
    return s


def stage_xmatch(pool: pd.DataFrame, label: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    import catalog_adapter_k1 as CA
    cat = CA.load(label)
    xm = cat.check_many(pool)
    side = cat.tce_sidecar(pool.loc[xm["spoc_tce"].to_numpy(), "tic_id"])
    return xm, side


def stage_rank(sel: pd.DataFrame, design: dict) -> pd.DataFrame:
    import rank_k1 as RK
    sel = sel.copy()
    sel["k1_type"] = RK.star_type(pd.to_numeric(sel["Teff"], errors="coerce"))
    sel.loc[(sel.k1_class == "eM"), "k1_type"] = "M_early"
    for col in ("sectors_2min",):
        sel["n_2min_all"] = [len(_parse_sectors(v)) for v in sel[col]]
    sel["n_obs_le105"] = sel["n_sectors_predicted_le105"]
    e, parts = RK.e_new(sel, sel["k1_type"], n_user_col="n_usable", p_max=50.0, by_radius=True)
    sel["E_new"] = e
    for c in parts.columns:
        sel[f"E_new_rp_{c}"] = parts[c]
    sel["E_new_p30"] = RK.e_new(sel, sel["k1_type"], n_user_col="n_usable", p_max=30.0)
    sel["E_new_s56_p30"] = RK.e_new(sel, sel["k1_type"], n_user_col="n_usable_s56", p_max=30.0)
    sel["E_new_s56"] = RK.e_new(sel, sel["k1_type"], n_user_col="n_usable_s56", p_max=50.0)
    em = sel.k1_class == "eM"
    if em.any():
        sel.loc[em, "E_new_published"] = RK.e_new(sel[em], sel.loc[em, "k1_type"], n_user_col="n_usable",
                                                   p_max=50.0, k_variant="published")
    out = []
    for cls in ("K", "eM"):
        sub = sel[sel.k1_class == cls].sort_values(["E_new", "tic_id"], ascending=[False, True], kind="stable")
        sub = sub.assign(rank=np.arange(1, len(sub) + 1))
        out.append(sub)
    return pd.concat(out, ignore_index=True)


def write_lists(ranked: pd.DataFrame, design: dict) -> dict:
    from k1_common import sha
    (K1 / "survey").mkdir(parents=True, exist_ok=True)
    nK, nE = design["survey_n"]["K"], design["survey_n"]["eM"]
    rK, rE = design["reserve_ranks"]["K"], design["reserve_ranks"]["eM"]
    isK, isE = ranked.k1_class == "K", ranked.k1_class == "eM"
    survey = ranked[(isK & (ranked["rank"] <= nK)) | (isE & (ranked["rank"] <= nE))].copy()
    reserve = ranked[(isK & ranked["rank"].between(rK[0], rK[1])) | (isE & ranked["rank"].between(rE[0], rE[1]))].copy()
    survey["slice"] = np.where(survey.k1_class == "eM", "eM_slice", "K")
    cols = [c for c in ranked.columns if c not in ("strip_lo", "strip_hi")]
    survey[cols + ["slice"]].to_csv(K1 / "survey" / "targets_k1.csv", index=False)
    reserve[cols].to_csv(K1 / "survey" / "reserve_k1.csv", index=False)
    ranked[cols].to_pickle(POP / "ranked_all.pkl")
    return {"targets_k1.csv": {"rows": int(len(survey)), "sha256": sha(K1 / "survey" / "targets_k1.csv")},
            "reserve_k1.csv": {"rows": int(len(reserve)), "sha256": sha(K1 / "survey" / "reserve_k1.csv")}}


def run_all(design: dict, label: str) -> dict:
    import k1_common  # noqa: F401  (paths)
    pool = stage_tic(design)
    _progress("cuts_1_4")
    s, counts = cuts_1_to_4(pool, design)
    s.to_pickle(POP / "after_cuts_1_4.pkl")
    _progress("products")
    s = s.merge(stage_products(s), on="tic_id", how="left")
    s = s.merge(stage_twomin(s), on="tic_id", how="left")
    s = pd.concat([s, stage_usable(s)], axis=1)
    _progress("gaia")
    s = pd.concat([s, stage_gaia(s, design)], axis=1)
    _progress("xmatch")
    xm, side = stage_xmatch(s, label)
    s = pd.concat([s, xm], axis=1)
    side.to_csv(POP / "tce_sidecar_pool.csv", index=False)
    s.to_pickle(POP / "pool_after_xmatch.pkl")
    sel = cuts_5_to_8(s, counts, design)
    _progress("sectors")
    sec = stage_sectors(sel)
    sel = sel.merge(sec, on="tic_id", how="left")
    _progress("rank")
    ranked = stage_rank(sel, design)
    files = write_lists(ranked, design)
    summary = {"generated_utc": _utc(), "design": design, "catalog_label": label, "cut_counts": counts,
               "files": files, "tce_sidecar_rows": int(len(side))}
    (K1 / "results").mkdir(parents=True, exist_ok=True)
    (K1 / "results" / "population_k1.json").write_text(json.dumps(summary, indent=1, default=float))
    _progress("done")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stages", nargs="*", default=["all"], help="tic | all")
    ap.add_argument("--catalog-label", default="20261008")
    a = ap.parse_args(argv)
    POP.mkdir(parents=True, exist_ok=True)
    (POP / "design.json").write_text(json.dumps(DESIGN, indent=1))
    if a.stages == ["tic"]:
        stage_tic(DESIGN)
        _progress("tic_done")
        return
    r = run_all(DESIGN, a.catalog_label)
    print(json.dumps(r["cut_counts"], indent=1))


if __name__ == "__main__":
    main()
