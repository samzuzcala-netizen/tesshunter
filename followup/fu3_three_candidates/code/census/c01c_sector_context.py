"""Sector context (follow-up to c01b, whose open-ended FFI range queries timed out at 120 s):
 (1) HEASARC TESS-point Web Tool (WTV v2) RA/Dec lookup per target -> predicted sector/camera/CCD/pixel for
     all pointings in the tool (the page states Cycle 9 sectors 108-121 are included);
 (2) per-sector MAST counts of SPOC FFI image observations, TICA FFI observations and QLP light curves for
     sectors >= 96, to establish the latest sectors that exist at MAST at the time of the census.
Metadata only.
"""
from __future__ import annotations

import html
import re

import census_common as C
from census_common import TARGETS, fetch, log, save_json, tag

from astroquery import cache_conf

cache_conf.cache_active = False
from astroquery.mast import Observations  # noqa: E402
from astroquery.mast import conf as mast_conf  # noqa: E402

mast_conf.timeout = 120
SCRIPT = "c01c_sector_context"
WTV = "https://heasarc.gsfc.nasa.gov/wsgi-scripts/TESS/TESS-point_Web_Tool/TESS-point_Web_Tool/wtv_v2.0.py/RADec_result"


def html_tables(t: str):
    out = []
    for tm in re.finditer(r"<table.*?</table>", t, flags=re.S | re.I):
        rows = []
        for rm in re.finditer(r"<tr.*?</tr>", tm.group(0), flags=re.S | re.I):
            cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                     for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", rm.group(0), flags=re.S | re.I)]
            if cells:
                rows.append(cells)
        out.append(rows)
    return out


def per_sector_counts(label, base, start=96, stop=125, stop_after_zeros=2):
    counts = {}
    zeros = 0
    with tag(label) as rc:
        for s in range(start, stop):
            try:
                n = int(Observations.query_criteria_count(sequence_number=[s, s], **base))
            except Exception as e:  # noqa: BLE001
                counts[s] = f"{type(e).__name__}: {e}"
                continue
            counts[s] = n
            zeros = zeros + 1 if (n == 0 and s > 98) else 0
            if zeros >= stop_after_zeros:
                break
    return counts, [r["receipt"] for r in rc]


def main():
    res = {"script": SCRIPT, "utc": C.utc(), "wtv": {}, "mast_counts": {}}
    for tic, t in TARGETS.items():
        f = fetch(WTV, f"wtv_radec_{tic}", method="POST", data={"ra": f"{t['ra']:.6f}", "dec": f"{t['dec']:.6f}"})
        tables = html_tables(f.text or "") if f.ok else []
        res["wtv"][tic] = {"status": f.status, "describe": f.describe(), "exception": f.exc, "tables": tables,
                           "receipts": f.receipt_files, "raw": f.raw_files,
                           "input": {"ra": t["ra"], "dec": t["dec"], "note": "TIC v8 epoch-2000 position"}}
        log(SCRIPT, f"WTV {tic}: {f.describe()} tables={[len(x) for x in tables]}")
    for label, base in (("spoc_ffi", dict(obs_collection="TESS", dataproduct_type="image")),
                        ("tica_ffi", dict(provenance_name="TICA")),
                        ("qlp_lc", dict(provenance_name="QLP")),
                        ("tess_spoc_lc", dict(provenance_name="TESS-SPOC"))):
        counts, rcpts = per_sector_counts(f"mast_count_{label}", base)
        res["mast_counts"][label] = {"criteria": base, "counts_per_sector": counts, "receipts": rcpts}
        log(SCRIPT, f"{label}: {counts}")
    save_json(C.PARTS / "c01c_sector_context.json", res)


if __name__ == "__main__":
    main()
