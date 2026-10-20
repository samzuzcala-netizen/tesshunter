"""K1 Part 0.3-0.4: fresh catalogue snapshots and the target-list refresh.

``catalogs``: TOI, CTOI, NASA ps, pscomppars, TESS EB and SPOC TCE through the unchanged
``tesshunter.catalog_crossmatch`` loader, written to ``D:/tesshunter_k1/catalogs/snap_<label>``
(the repo's own catalogue cache and every P12 snapshot are untouched).  SPOC TCE raw files and
TIC coordinates already in ``data/cache/catalogs/spoc_tce`` are COPIED in first (published TCE
files are immutable; only new runs are fetched).  The TESS Ten Thousand journal tables (Kostov et
al. 2025, ApJS 279, 50, tables 3 and 4) are downloaded again and compared with the P12 copies.
Every source records its hash and row count in ``k1/manifests/catalog_snapshot_<label>.json``.

``lists``: QLP / TESS-SPOC / 2-min target lists in ``data/survey/cache`` for sectors whose list is
absent or recorded missing, up to the latest public sector.  Existing "ok" lists are never touched;
a "missing" list is re-written only when a HEAD probe finds it now exists.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from k1_common import REPO, ROOT, DATA, environment, read, write, sha, utc

environment()

TTT_TABLES = {
    3: dict(url="https://content.cld.iop.org/journals/0067-0049/279/2/50/revision1/apjsade2d8t3_mrt.txt",
            rows=7936, p12_copy="data/survey/p12/negatives/ttt_downloads/apjsade2d8t3_mrt.txt"),
    4: dict(url="https://content.cld.iop.org/journals/0067-0049/279/2/50/revision1/apjsade2d8t4_mrt.txt",
            rows=2065, p12_copy="data/survey/p12/negatives/ttt_downloads/apjsade2d8t4_mrt.txt"),
}
SOURCES = ("toi", "ctoi", "nasa_ps", "nasa_pscomppars", "tess_eb", "spoc_tce")


def _get(url: str, timeout: int = 600) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "tesshunter/0.1 (K1 catalogue snapshot)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_mrt(body: bytes):
    """TIC and period columns of a TTT journal MRT (astropy mrt reader)."""
    from astropy.io import ascii
    lines = body.decode("utf-8-sig").splitlines()
    t = ascii.read(lines, format="mrt", guess=False)
    pcol = next(c for c in ("Per", "Per-TESS") if c in t.colnames)
    df = t.to_pandas()
    df = df.rename(columns={"TIC": "tic_id", pcol: "period_days"})
    df["tic_id"] = df["tic_id"].astype("int64")
    return df


def snapshot_catalogs(label: str) -> dict:
    from tesshunter import catalog_crossmatch as cx
    dest = DATA / "catalogs" / f"snap_{label}"
    if dest.exists() and (dest / "DONE").exists():
        return read(ROOT / "manifests" / f"catalog_snapshot_{label}.json")
    dest.mkdir(parents=True, exist_ok=True)
    seed = REPO / "data" / "cache" / "catalogs" / "spoc_tce"
    copied = 0
    (dest / "spoc_tce" / "raw").mkdir(parents=True, exist_ok=True)
    for f in (seed / "raw").glob("*"):
        target = dest / "spoc_tce" / "raw" / f.name
        if not target.exists():
            shutil.copy2(f, target)
            copied += 1
    for name in ("tic_coords.csv", "tic_coords.meta.json"):
        if (seed / name).exists() and not (dest / "spoc_tce" / name).exists():
            shutil.copy2(seed / name, dest / "spoc_tce" / name)
    cx.CATALOG_CACHE_DIR = dest
    out = {"label": label, "started_utc": utc(), "destination": str(dest), "spoc_tce_raw_files_seeded": copied,
           "sources": {}}
    t0 = time.time()
    cat = cx.KnownObjectCatalog.load(sources=list(SOURCES), refresh=True, allow_stale=False, offline=False,
                                     allow_partial_coords=True)
    cat.write_manifest(dest / "manifest.json")
    m = cat.manifest()
    for n in SOURCES:
        v = m["sources"][n]
        out["sources"][n] = {"fetched_utc": v["fetched_utc"], "n_rows": m["n_rows"][n],
                             "n_unique_tic": m["n_unique_tic"][n], "raw_sha256": v["sha256"],
                             "normalized_sha256": v["normalized_sha256"], "n_files": v["n_files"],
                             "coords": v.get("coords") and {k: v["coords"].get(k) for k in
                                                            ("n_requested", "n_resolved", "n_unresolved", "partial")}}
    out["stamp"] = cat.stamp()
    out["any_partial_coords"] = cat.any_partial_coords()
    out["catalog_seconds"] = round(time.time() - t0, 1)
    # RAVEN check: the CTOI list must contain the 2026-08-27 RAVEN uploads [R]
    out["ctoi_raven_check"] = raven_check(dest / "ctoi" / "raw" / "exofop_ctoi.csv")
    # TESS Ten Thousand journal tables
    ttt = {}
    (dest / "ttt").mkdir(exist_ok=True)
    for num, spec in TTT_TABLES.items():
        rec = {"url": spec["url"], "expected_rows": spec["rows"]}
        try:
            body = _get(spec["url"])
            rec["source"] = "fresh download"
        except Exception as exc:
            rec["download_error"] = f"{type(exc).__name__}: {exc}"[:300]
            body = (REPO / spec["p12_copy"]).read_bytes()
            rec["source"] = "fallback: P12 copy " + spec["p12_copy"]
        path = dest / "ttt" / f"ttt_table{num}_mrt.txt"
        path.write_bytes(body)
        rec["sha256"] = sha(path)
        p12 = REPO / spec["p12_copy"]
        rec["identical_to_p12_copy"] = p12.exists() and sha(p12) == rec["sha256"]
        df = parse_mrt(body)
        rec["rows"] = int(len(df))
        df.to_csv(dest / "ttt" / f"ttt_table{num}.csv", index=False)
        rec["csv_sha256"] = sha(dest / "ttt" / f"ttt_table{num}.csv")
        rec["columns"] = list(df.columns)
        ttt[num] = rec
    out["ttt"] = ttt
    out["completed_utc"] = utc()
    write(ROOT / "manifests" / f"catalog_snapshot_{label}.json", out)
    (dest / "DONE").write_text(utc())
    return out


def raven_check(raw_csv) -> dict:
    """The 1,173 RAVEN CTOIs (Lafarga et al. 2026) last-modified 2026-08-27 [R]."""
    import pandas as pd
    c = pd.read_csv(raw_csv, low_memory=False)
    on_day = c["CTOI lastmod"].astype(str).str[:10] == "2026-08-27"
    paper = (c["Paper"].astype(str).str.contains("Lafarga|RAVEN", case=False)
             | c["Notes"].astype(str).str.contains("RAVEN", case=False))
    return {"n_ctoi_total": int(len(c)), "n_lastmod_2026_08_27": int(on_day.sum()),
            "users_on_2026_08_27": c.loc[on_day, "User"].astype(str).value_counts().head(5).to_dict(),
            "n_rows_citing_lafarga_or_raven": int(paper.sum()), "expected": 1173,
            "present": bool(on_day.sum() >= 1173 and paper.sum() >= 1173)}


# ── target lists ──────────────────────────────────────────────────────────────
QLP_LIST_URL = "https://archive.stsci.edu/hlsps/qlp/target_lists/s{sector:04d}.csv"
SPOC_LIST_URL = "https://archive.stsci.edu/hlsps/tess-spoc/target_lists/s{sector:04d}.csv"


def _head(url: str) -> bool:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "tesshunter/0.1 (K1 lists)"})
    try:
        with urllib.request.urlopen(req, timeout=60):
            return True
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise


def refresh_lists(max_probe: int = 112) -> dict:
    import build_p8_population as B
    lists, twomin = B.LISTS_DIR, B.TWOMIN_DIR
    out = {"utc": utc(), "added": [], "still_missing": [], "untouched_ok": 0, "probes": {}}
    for name, tmpl in (("qlp", QLP_LIST_URL), ("tess-spoc", SPOC_LIST_URL)):
        for s in range(1, max_probe + 1):
            st = lists / f"{name}_s{s:04d}.status"
            status = st.read_text().strip() if st.exists() else "absent"
            if status == "ok":
                out["untouched_ok"] += 1
                continue
            url = tmpl.format(sector=s)
            present = _head(url)
            out["probes"][f"{name}_{s}"] = {"prior": status, "present_now": present}
            if present:
                B.ensure_list(name, s, url) if status == "absent" else _replace_missing(B, name, s, url)
                out["added"].append(f"{name}_s{s:04d}")
            elif status == "absent":
                out["still_missing"].append(f"{name}_s{s:04d} (not recorded; not written)")
            else:
                out["still_missing"].append(f"{name}_s{s:04d}")
    for s in range(1, max_probe + 1):
        st = twomin / f"s{s:03d}.status"
        status = st.read_text().strip() if st.exists() else "absent"
        if status == "ok":
            out["untouched_ok"] += 1
            continue
        res = B.ensure_twomin(s) if status == "absent" else ("skipped-missing", 0, None)
        out["probes"][f"twomin_{s}"] = {"prior": status, "result": res[0]}
        if res[0] == "ok":
            out["added"].append(f"twomin_s{s:03d}")
        else:
            out["still_missing"].append(f"twomin_s{s:03d}")
            # ensure_twomin writes a 'missing' status for a sector with no list; remove what K1 created
            if status == "absent":
                for ext in (".npy", ".status", ".meta.json"):
                    p = twomin / f"s{s:03d}{ext}"
                    if p.exists():
                        p.unlink()
    write(ROOT / "manifests" / f"target_list_refresh_{utc()[:10]}.json", out, replace=True)
    return out


def _replace_missing(B, name, s, url):
    """A list recorded 'missing' now exists: move the old empty records aside, then fetch."""
    for ext in (".npy", ".status", ".meta.json"):
        p = B.LISTS_DIR / f"{name}_s{s:04d}{ext}"
        if p.exists():
            p.rename(p.with_name(p.name + ".missing_before_k1"))
    return B.ensure_list(name, s, url)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["catalogs", "lists"])
    ap.add_argument("--label", default=time.strftime("%Y%m%d"))
    a = ap.parse_args()
    import json
    if a.what == "catalogs":
        r = snapshot_catalogs(a.label)
        print(json.dumps({k: v for k, v in r.items() if k != "sources"}, indent=1, default=str))
        print(json.dumps(r["sources"], indent=1, default=str))
    else:
        r = refresh_lists()
        print(json.dumps({k: v for k, v in r.items() if k != "probes"}, indent=1))
