"""Bounded fetch of the small external inputs this follow-up needs.

1. Official TESS PRF model images (MAST, start_s0004 set: valid for sector 4+)
   for the 4 CCD grid points bracketing the target on each camera/CCD used.
2. One Gaia DR3 cone (600 arcsec, all magnitudes) around the target.
3. One TIC v8.2 cone (400 arcsec) for catalogue TESS magnitudes.

Every call: timeout 60-120 s, at most one transport retry. Outputs go only to
the follow-up locations; provenance (URL/query, UTC, bytes, sha256) is saved.

usage: python fetch_inputs.py prf|gaia|tic|all
"""
from __future__ import annotations

import hashlib
import json
import socket
import sys
import time
import urllib.request
from datetime import datetime, timezone

import common as C

PRF_BASE = "https://archive.stsci.edu/missions/tess/models/prf_fitsfiles/start_s0004/"
ROWS = [1, 513, 1025, 1536, 2048]
COLS = [45, 557, 1069, 1580, 2092]
# camera/ccd -> filename stamp (from the MAST directory listing, 2026-10-01)
STAMP = {(4, 4): "tess2019107181902", (2, 2): "tess2019107181901", (3, 4): "tess2019107181902",
         (2, 1): "tess2019107181901"}
# approximate target CCD (col, row) per sector from the TESScut 1CRV4P/2CRV4P + 10
TARGET_CCD = {57: (4, 4, 1840, 36), 79: (2, 2, 568, 1836), 80: (3, 4, 1688, 589), 84: (4, 4, 1859, 53)}


def bracket(v, grid):
    for a, b in zip(grid[:-1], grid[1:]):
        if a <= v <= b:
            return a, b
    return (grid[0], grid[1]) if v < grid[0] else (grid[-2], grid[-1])


def fetch(url, timeout=60):
    last = None
    for attempt in range(2):  # at most one retry
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "tic332366289-localisation-followup"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), attempt
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3)
    raise RuntimeError(f"fetch failed twice: {url}: {last}")


def do_prf():
    rows = []
    need = set()
    for s, (cam, ccd, col, row) in TARGET_CCD.items():
        c0, c1 = bracket(col, COLS)
        r0, r1 = bracket(row, ROWS)
        for rr in (r0, r1):
            for cc in (c0, c1):
                need.add((cam, ccd, rr, cc))
    for cam, ccd, rr, cc in sorted(need):
        name = f"{STAMP[(cam, ccd)]}-prf-{cam}-{ccd}-row{rr:04d}-col{cc:04d}.fits"
        url = f"{PRF_BASE}cam{cam}_ccd{ccd}/{name}"
        out = C.PRF_DIR / "start_s0004" / f"cam{cam}_ccd{ccd}" / name
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and out.stat().st_size > 0:
            b = out.read_bytes(); attempt = None
        else:
            b, attempt = fetch(url)
            out.write_bytes(b)
        rows.append({"url": url, "path": str(out), "bytes": len(b),
                     "sha256": hashlib.sha256(b).hexdigest(), "retry_used": attempt == 1})
        print(name, len(b))
    C.write_json(C.INPUTS / "prf_provenance.json",
                 {"utc": datetime.now(timezone.utc).isoformat(), "set": "start_s0004 (VERSION UPDATED_2.0, valid sector 4+)",
                  "readme": PRF_BASE + "00README.txt", "files": rows})


def tap_sync(query, timeout=120):
    import urllib.parse
    url = "https://gea.esac.esa.int/tap-server/tap/sync"
    data = urllib.parse.urlencode({"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv",
                                   "QUERY": query}).encode()
    last = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, data=data,
                                         headers={"User-Agent": "tic332366289-localisation-followup"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), attempt
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3)
    raise RuntimeError(f"Gaia TAP failed twice: {last}")


def do_gaia():
    ra, dec = 257.222579442748, 50.4877846010817  # TIC (J2000) position of the target
    q = ("SELECT source_id, ra, dec, ra_error, dec_error, ref_epoch, parallax, parallax_error, pmra, pmdec, "
         "pmra_error, pmdec_error, phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag, "
         "phot_bp_rp_excess_factor, ruwe, ipd_frac_multi_peak, ipd_gof_harmonic_amplitude, "
         "astrometric_excess_noise, astrometric_excess_noise_sig, astrometric_params_solved, "
         "duplicated_source, non_single_star, phot_variable_flag "
         "FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT('ICRS', ra, dec), "
         f"CIRCLE('ICRS', {ra}, {dec}, {600.0/3600.0}))")
    t0 = time.time()
    b, attempt = tap_sync(q)
    out = C.INPUTS / "gaia_dr3_cone600.csv"
    out.write_bytes(b)
    C.write_json(C.INPUTS / "gaia_dr3_cone600_provenance.json",
                 {"utc": datetime.now(timezone.utc).isoformat(), "service": "https://gea.esac.esa.int/tap-server/tap/sync",
                  "query": q, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(), "wall_s": time.time() - t0,
                  "retry_used": attempt == 1,
                  "note": "source_id kept as exact integer text in the CSV; parse as int/str, never float"})
    print("gaia bytes", len(b), "lines", b.count(b"\n"))


def do_tic():
    socket.setdefaulttimeout(120)
    ra, dec = 257.222579442748, 50.4877846010817
    import os
    os.environ.setdefault("ASTROPY_CACHE_DIR", str(C.BIG / "astropy_cache"))
    from astroquery.mast import Catalogs
    t0 = time.time()
    last = None
    for attempt in range(2):
        try:
            tab = Catalogs.query_region(f"{ra} {dec}", radius=400.0 / 3600.0, catalog="TIC")
            break
        except Exception as e:  # noqa: BLE001
            last = e; tab = None; time.sleep(3)
    if tab is None:
        raise RuntimeError(f"TIC query failed twice: {last}")
    keep = [c for c in ["ID", "GAIA", "ra", "dec", "Tmag", "e_Tmag", "Gmag", "BPmag", "RPmag", "Teff", "rad",
                        "mass", "objType", "typeSrc", "disposition", "duplicate_id", "dstArcSec", "TESSflag",
                        "pmRA", "pmDEC", "plx", "contratio"] if c in tab.colnames]
    sub = tab[keep]
    out = C.INPUTS / "tic_cone400.csv"
    sub.write(str(out), format="csv", overwrite=True)
    b = out.read_bytes()
    C.write_json(C.INPUTS / "tic_cone400_provenance.json",
                 {"utc": datetime.now(timezone.utc).isoformat(), "service": "astroquery.mast.Catalogs TIC",
                  "radius_arcsec": 400.0, "center": [ra, dec], "rows": len(sub), "bytes": len(b),
                  "sha256": hashlib.sha256(b).hexdigest(), "wall_s": time.time() - t0, "retry_used": attempt == 1,
                  "note": "ID and GAIA columns are exact integer strings in the CSV"})
    print("tic rows", len(sub))


if __name__ == "__main__":
    what = sys.argv[1]
    if what in ("prf", "all"):
        do_prf()
    if what in ("gaia", "all"):
        do_gaia()
    if what in ("tic", "all"):
        do_tic()
