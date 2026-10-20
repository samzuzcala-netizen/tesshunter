"""Census task 1/2 context: which TESS sectors exist at MAST at all (so that 'no sector > 98' can be read
correctly), and which sectors > 98 put each target on silicon according to the HEASARC Web TESS Viewing
Tool (WTV, tess-point based pointing predictions).  Metadata only.
"""
from __future__ import annotations

import re

import census_common as C
from census_common import TARGETS, fetch, log, save_json, tag

import numpy as np
from astroquery import cache_conf

cache_conf.cache_active = False
from astroquery.mast import Observations  # noqa: E402
from astroquery.mast import conf as mast_conf  # noqa: E402

mast_conf.timeout = 120
SCRIPT = "c01b_latest_sectors"


def seq_counts(tbl):
    if tbl is None or len(tbl) == 0:
        return {}
    out = {}
    for s in tbl["sequence_number"]:
        try:
            s = int(s)
        except Exception:
            continue
        out[s] = out.get(s, 0) + 1
    return dict(sorted(out.items()))


def main():
    res = {"script": SCRIPT, "utc": C.utc(), "mast": {}, "wtv": {}}
    # ---- SPOC FFI observations (TESS collection, image) for sectors >= 95 ----
    for label, crit in (
        ("spoc_ffi", dict(obs_collection="TESS", dataproduct_type="image", provenance_name="SPOC",
                          sequence_number=[95, 300])),
        ("tica_ffi", dict(obs_collection="HLSP", provenance_name="TICA", sequence_number=[95, 300])),
    ):
        with tag(f"mast_latest_{label}") as rc:
            try:
                tb = Observations.query_criteria(**crit)
                cnt, err = seq_counts(tb), None
                tmin = {}
                for r in tb:
                    s = int(r["sequence_number"])
                    a, b = float(r["t_min"]), float(r["t_max"])
                    lo, hi = tmin.get(s, (np.inf, -np.inf))
                    tmin[s] = (min(lo, a), max(hi, b))
            except Exception as e:  # noqa: BLE001
                cnt, err, tmin = None, f"{type(e).__name__}: {e}", {}
        res["mast"][label] = {"criteria": {k: v for k, v in crit.items()}, "rows_per_sector": cnt, "error": err,
                              "sector_mjd_range": {s: [round(v[0], 5), round(v[1], 5)] for s, v in tmin.items()},
                              "sector_btjd_range": {s: [round(v[0] + C.MJD_TO_BTJD, 5), round(v[1] + C.MJD_TO_BTJD, 5)]
                                                    for s, v in tmin.items()},
                              "receipts": [r["receipt"] for r in rc]}
        log(SCRIPT, f"{label}: {cnt} err={err}")
    # ---- HLSP light-curve families: total count for sectors >= 99, then per sector only if non-zero ----
    ffi_max = max([int(s) for s in (res["mast"]["spoc_ffi"]["rows_per_sector"] or {}).keys()] +
                  [int(s) for s in (res["mast"]["tica_ffi"]["rows_per_sector"] or {}).keys()] + [98])
    for prov in ("QLP", "TESS-SPOC", "TGLC", "TARS", "GSFC-ELEANOR-LITE"):
        counts = {}
        with tag(f"mast_count_{prov}") as rc:
            try:
                total = int(Observations.query_criteria_count(provenance_name=prov, sequence_number=[99, 300]))
            except Exception as e:  # noqa: BLE001
                total = f"{type(e).__name__}: {e}"
            if isinstance(total, int) and total > 0:
                for s in range(99, ffi_max + 1):
                    try:
                        counts[s] = int(Observations.query_criteria_count(provenance_name=prov,
                                                                          sequence_number=[s, s]))
                    except Exception as e:  # noqa: BLE001
                        counts[s] = f"{type(e).__name__}: {e}"
        res["mast"][f"count_{prov}"] = {"count_sectors_ge_99": total, "counts_per_sector": counts,
                                        "receipts": [r["receipt"] for r in rc]}
        log(SCRIPT, f"count {prov}: >=99 total={total} per-sector={counts}")
    # ---- WTV pointing predictions per target ----
    for tic, t in TARGETS.items():
        url = "https://heasarc.gsfc.nasa.gov/cgi-bin/tess/webtess/wtv.py"
        f = fetch(url, f"wtv_{tic}", params={"Entry": f"{t['ra']:.6f},{t['dec']:.6f}"})
        txt = f.text or ""
        rows = []
        # WTV reports lines such as "Sector 1, Camera 4, CCD 4, Col ... Row ..." (format parsed loosely)
        for m in re.finditer(r"[Ss]ector\s*(\d+)\D{0,40}?[Cc]amera\s*(\d)\D{0,40}?CCD\s*(\d)", txt):
            rows.append([int(m.group(1)), int(m.group(2)), int(m.group(3))])
        res["wtv"][tic] = {"status": f.status, "describe": f.describe(), "parsed_sector_camera_ccd": rows,
                           "receipts": f.receipt_files, "raw": f.raw_files}
        log(SCRIPT, f"WTV {tic}: {f.describe()} parsed {len(rows)} rows")
    save_json(C.PARTS / "c01b_latest_sectors.json", res)


if __name__ == "__main__":
    main()
