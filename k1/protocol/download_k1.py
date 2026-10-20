"""K1 acquisition worker: one star's usable FFI products into the K1 store (Part C2).

Adapted (by copy) from ``scripts/audit_p5.download`` and ``p12/protocol/download_star_p12.py``:
* exactly one ``lightkurve.search_lightcurve`` per star (never per-sector searches);
* only usable products (``sector_policy_k1``): TESS-SPOC or QLP, sectors 1-98, QLP 80/83/85 and
  99+ excluded, one product per sector (TESS-SPOC preferred), FFI only (no SPOC 2-min);
* amendment 1: QLP 74-79 only in the corrected v02 delivery;
* every product's FITS header must say BJD_TDB / SOLARSYSTEM / BJDREFI 2457000 and its stored
  arrays must equal the FITS columns (P12 identity check); a failure is an unusable product,
  recorded, never silently replaced;
* a fresh per-attempt FITS cache (truncated FITS from an outage are never reused);
* refuses any star of the frozen survey list (STOP-E) and records every star in the exposure ledger.

Store layout = the audit store (``tic<id>/index.json`` + ``sNNN_<AUTHOR>.npz``) under
``D:/tesshunter_k1/audit_lc``.  CLI: ``download_k1.py <tic> <attempt> <use> [--receipt path]``.
"""
from __future__ import annotations

import argparse
import re
import socket
import sys
import time
from pathlib import Path

import numpy as np

from k1_common import ROOT, DATA, STORE, environment, read, write, sha, utc, ledger

environment()
import sector_policy_k1 as SP  # noqa: E402

BTJD_OFFSET = 2457000.0
SURVEY_LIST = ROOT / "survey" / "targets_k1.csv"


def survey_tics() -> set[int]:
    if not SURVEY_LIST.exists():
        return set()
    import pandas as pd
    return set(pd.read_csv(SURVEY_LIST, usecols=["tic_id"]).tic_id.astype("int64"))


def bounded(fn, limit: float):
    """Run one MAST call in a daemon thread and abandon it after ``limit`` s (the pilot of 2026-10-08
    lost 4 of 30 stars to search_lightcurve calls that sat with flat CPU for 8-11 minutes)."""
    import threading
    box = {}

    def run():
        try:
            box["v"] = fn()
        except Exception as exc:  # noqa: BLE001
            box["e"] = exc
    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(limit)
    if th.is_alive():
        raise TimeoutError(f"MAST call exceeded {limit:.0f} s")
    if "e" in box:
        raise box["e"]
    return box["v"]


def _col(lc, name):
    try:
        v = lc[name]
    except Exception:
        return None
    try:
        return np.asarray(v.value if hasattr(v, "value") else v, dtype=float)
    except Exception:
        return None


def _rows(sr) -> list[dict]:
    rows = []
    for i in range(len(sr)):
        author = str(sr.author[i])
        mission = str(sr.mission[i])
        # HLSP rows such as DIAMANTE carry "TESS Sector " with no number: they get -1 (never usable)
        nums = re.findall(r"Sector\s*(\d+)", mission)
        sector = int(nums[0]) if len(nums) == 1 else -1
        exptime = float(sr.exptime[i].value) if hasattr(sr.exptime[i], "value") else float(sr.exptime[i])
        rows.append({"index": i, "author": author, "sector": sector, "exptime_s": exptime})
    return rows


def _fits_for(download_dir: Path, tic: int, sector: int, author: str) -> Path | None:
    tag = "hlsp_qlp" if author == "QLP" else "hlsp_tess-spoc"
    hits = [p for p in download_dir.rglob("*.fits") if tag in p.name and f"s{sector:04d}" in p.name
            and (f"{tic:016d}" in p.name or f"{tic:010d}" in p.name or str(tic) in p.name)]
    return sorted(hits)[-1] if hits else None


def _identity(path: Path, arrays: dict, flux_col: str) -> dict:
    from astropy.io import fits
    with fits.open(path, memmap=False) as hd:
        h0, h1 = hd[0].header, hd[1].header
        data = hd[1].data
        get = lambda k: h1.get(k, h0.get(k))  # noqa: E731
        t = np.asarray(data["TIME"], float)
        ref = float(get("BJDREFI") or 0) + float(get("BJDREFF") or 0)
        btjd = t + (ref - BTJD_OFFSET) if ref else t
        keep = np.isfinite(btjd) if len(btjd) != len(arrays["time"]) else np.ones(len(btjd), bool)
        checks = {
            "TIME": bool(np.array_equal(arrays["time"], btjd[keep], equal_nan=True)),
            "flux": flux_col.upper() in data.names and bool(np.array_equal(
                arrays["flux"], np.asarray(data[flux_col.upper()], float)[keep], equal_nan=True)),
            "SAP": "SAP_FLUX" in data.names and bool(np.array_equal(
                arrays["sap_flux"], np.asarray(data["SAP_FLUX"], float)[keep], equal_nan=True)),
            "BJD_TDB_SOLARSYSTEM": get("TIMESYS") == "TDB" and get("TIMEREF") == "SOLARSYSTEM"
                                   and int(get("BJDREFI") or 0) == 2457000,
        }
    m = re.search(r"_v([0-9.]+)_", path.name)
    return {"checks": checks, "all_required_exact": all(checks.values()), "version": m.group(1) if m else None,
            "fits": path.name, "fits_sha256": sha(path), "fits_bytes": path.stat().st_size}


def download_star(tic: int, attempt: int, use: str, store: Path = STORE) -> dict:
    import lightkurve as lk
    socket.setdefaulttimeout(300.0)
    if int(tic) in survey_tics():
        raise RuntimeError(f"STOP-E: TIC {tic} is on the frozen survey list; K1 never downloads it")
    ledger(tic, use, "download", f"attempt {attempt}")
    t0 = time.perf_counter()
    cache = DATA / "lightkurve" / f"tic{int(tic)}" / f"attempt{int(attempt)}"
    cache.mkdir(parents=True, exist_ok=True)
    tdir = store / f"tic{int(tic)}"
    tdir.mkdir(parents=True, exist_ok=True)
    sr = bounded(lambda: lk.search_lightcurve(f"TIC {int(tic)}", mission="TESS"), 240.0)
    all_rows = _rows(sr)
    chosen = SP.choose_products(all_rows)
    products, dropped, failed = [], [], []
    for r in chosen:
        sector, author = int(r["sector"]), r["author"]
        try:
            lc = bounded(lambda: sr[r["index"]].download(quality_bitmask="none", download_dir=str(cache)), 300.0)
        except Exception as exc:
            failed.append({"sector": sector, "author": author, "error": f"{type(exc).__name__}: {exc}"[:300]})
            continue
        if lc is None:
            failed.append({"sector": sector, "author": author, "error": "download returned None"})
            continue
        sector = int(lc.meta.get("SECTOR", sector))
        t = np.asarray(lc.time.value, dtype=float)
        if np.nanmedian(t) > 2_400_000:
            t = t - BTJD_OFFSET
        flux_col = "pdcsap_flux"
        if author == "QLP":
            flux_col = "det_flux" if sector >= 56 else "kspsap_flux"
        flux = _col(lc, flux_col)
        if flux is None:
            failed.append({"sector": sector, "author": author, "error": f"no {flux_col} column"})
            continue
        ferr = _col(lc, flux_col + "_err")
        sap, sap_err, bkg, q = (_col(lc, "sap_flux"), _col(lc, "sap_flux_err"), _col(lc, "sap_bkg"), _col(lc, "quality"))
        q = np.zeros_like(t, dtype=np.int64) if q is None else np.nan_to_num(q).astype(np.int64)
        nan = np.full_like(t, np.nan)
        arrays = {"time": t, "flux": flux, "flux_err": nan if ferr is None else ferr,
                  "sap_flux": nan if sap is None else sap, "sap_flux_err": nan if sap_err is None else sap_err,
                  "sap_bkg": nan if bkg is None else bkg, "quality": q}
        fpath = _fits_for(cache, int(tic), sector, author)
        ident = _identity(fpath, arrays, flux_col) if fpath is not None else {"all_required_exact": False,
                                                                              "error": "source FITS not found"}
        if not ident.get("all_required_exact"):
            failed.append({"sector": sector, "author": author, "error": "identity check failed", "identity": ident})
            continue
        if not SP.product_version_usable(author, sector, ident.get("version")):
            dropped.append({"sector": sector, "author": author, "version": ident.get("version"),
                            "reason": "amendment 1: QLP 74-79 require v02"})
            continue
        name = f"s{sector:03d}_{author.replace('-', '')}.npz"
        with open(tdir / name, "wb") as fh:
            np.savez_compressed(fh, **arrays)
        cad = float(np.nanmedian(np.diff(t))) * 86400.0
        products.append({"file": name, "author": author, "exptime_s": r["exptime_s"], "cadence_s": round(cad, 1),
                         "native_cadence_s": SP.native_cadence_s(sector), "sector": sector, "n": int(len(t)),
                         "flux_column": flux_col, "t_start": float(np.nanmin(t)), "t_end": float(np.nanmax(t)),
                         "camera": int(lc.meta.get("CAMERA", -1) or -1), "ccd": int(lc.meta.get("CCD", -1) or -1),
                         "n_quality_nonzero": int(np.count_nonzero(q)), "version": ident.get("version"),
                         "fits": ident.get("fits"), "fits_sha256": ident.get("fits_sha256"),
                         "fits_bytes": ident.get("fits_bytes"), "npz_bytes": (tdir / name).stat().st_size})
    index = {"tic_id": int(tic), "downloaded_utc": utc(), "attempt": int(attempt), "use": use,
             "search_rows": len(all_rows), "rows": all_rows, "chosen": [{k: r[k] for k in ("author", "sector")} for r in chosen],
             "n_products": len(products), "n_failed": len(failed), "n_dropped_v01": len(dropped),
             "products": products, "failed": failed, "dropped": dropped, "policy": "k1 usable-sector rule + amendment 1",
             "sectors_usable_realised": sorted(p["sector"] for p in products),
             "seconds": round(time.perf_counter() - t0, 1)}
    write(tdir / "index.json", index, replace=True)
    return index


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("tic", type=int)
    ap.add_argument("attempt", type=int)
    ap.add_argument("use")
    ap.add_argument("--receipt", required=True)
    a = ap.parse_args(argv)
    started = utc(); t0 = time.perf_counter()
    try:
        idx = download_star(a.tic, a.attempt, a.use)
        status = "COMPLETE" if idx["n_failed"] == 0 else "OPERATIONAL_UNKNOWN"
        rec = {"tic_id": a.tic, "attempt": a.attempt, "use": a.use, "status": status,
               "n_products": idx["n_products"], "n_failed": idx["n_failed"], "n_dropped_v01": idx["n_dropped_v01"],
               "sectors": idx["sectors_usable_realised"],
               "bytes_npz": sum(p["npz_bytes"] for p in idx["products"]),
               "bytes_fits": sum(p["fits_bytes"] or 0 for p in idx["products"]), "failed": idx["failed"]}
    except Exception as exc:
        status = "OPERATIONAL_UNKNOWN"
        rec = {"tic_id": a.tic, "attempt": a.attempt, "use": a.use, "status": status,
               "error": f"{type(exc).__name__}: {exc}"[:500]}
        if "STOP-E" in str(exc):
            rec["stop"] = "STOP-E"
    rec.update(started_utc=started, completed_utc=utc(), wall_seconds=round(time.perf_counter() - t0, 1))
    write(Path(a.receipt), rec, replace=True)
    print("download", a.tic, status, rec.get("n_products"), flush=True)
    return 0 if status == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
