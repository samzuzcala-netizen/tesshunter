"""Census tasks 6/11 (discovery step 2): search the TAPVizieR table metadata (TAP_SCHEMA.tables descriptions)
for TESS eclipsing-binary catalogues and for speckle / high-resolution imaging catalogues of TESS targets,
because Vizier.find_catalogs keyword search returned only TIC/ATL tables for those phrases."""
from __future__ import annotations

import csv
import io

import census_common as C
from census_common import fetch, log, save_json

SCRIPT = "c04b_vizier_tap_discover"
TAP = "https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync"
T = "SELECT table_name, description FROM TAP_SCHEMA.tables WHERE "
QUERIES = {   # TAPVizieR's ADQL parser rejected LOWER(); case variants are spelled out instead
    "tess_eclipsing": T + "(description LIKE '%clipsing%' OR description LIKE '%EBs%') AND "
                          "(description LIKE '%TESS%' OR description LIKE '%Tess%')",
    "eclipsing_ffi": T + "description LIKE '%clipsing%' AND (description LIKE '%ull-frame%' OR "
                         "description LIKE '%ull frame%' OR description LIKE '%FFI%')",
    "speckle": T + "description LIKE '%peckle%'",
    "tess_imaging": T + "description LIKE '%TESS%' AND (description LIKE '%maging%' OR "
                        "description LIKE '%ompanion%' OR description LIKE '%daptive optics%' OR "
                        "description LIKE '%ontrast%')",
    "tess_toi": T + "description LIKE '%TESS%' AND (description LIKE '%bjects of interest%' OR "
                    "description LIKE '%TOI%' OR description LIKE '%lanet candidate%' OR "
                    "description LIKE '%hreshold crossing%')",
    "lamost_dr": T + "table_name LIKE 'V/16%' OR description LIKE '%LAMOST DR1%'",
    "galah_dr4": T + "table_name LIKE 'J/other/PASA/42.51%'",
}


def main():
    res = {"script": SCRIPT, "utc": C.utc(), "queries": {}}
    for key, q in QUERIES.items():
        f = fetch(TAP, f"tapvizier_meta_{key}", method="POST",
                  data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": q}, timeout=(30, 120))
        rows = None
        if f.ok and not (f.text or "").lstrip().startswith("<"):
            rows = list(csv.DictReader(io.StringIO(f.text)))
        res["queries"][key] = {"query": q, "status": f.status, "describe": f.describe(), "rows": rows,
                               "error_head": None if rows is not None else (f.text or f.exc or "")[:600],
                               "receipts": f.receipt_files, "raw": f.raw_files}
        log(SCRIPT, f"{key}: {f.describe()} rows={None if rows is None else len(rows)}")
        for r in (rows or [])[:80]:
            print("    ", r.get("table_name"), "|", (r.get("description") or "")[:140].replace("\n", " "))
    save_json(C.PARTS / "c04b_vizier_tap_discover.json", res)


if __name__ == "__main__":
    main()
