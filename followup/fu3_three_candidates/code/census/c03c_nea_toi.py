"""NASA Exoplanet Archive TOI table (TAP) as an independent TOI source (the first c03 attempt returned
HTTP 400 'Failed to connect to cx_Oracle', a server-side error).  Queries: exact TIC match for the three
targets, 2-arcmin cones, a positive control (TIC 231663901 = TOI-101) and the table's latest rowupdate."""
from __future__ import annotations

import csv
import io

import census_common as C
from census_common import TARGETS, fetch, log, save_json

SCRIPT = "c03c_nea_toi"
TAP = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"


def q(query, label):
    f = fetch(TAP, label, params={"query": query, "format": "csv"}, timeout=(30, 120))
    rows = None
    if f.ok and not (f.text or "").lstrip().startswith("<"):
        rows = list(csv.DictReader(io.StringIO(f.text)))
    return {"query": query, "status": f.status, "describe": f.describe(), "rows": rows,
            "error_head": None if rows is not None else (f.text or f.exc or "")[:300],
            "receipts": f.receipt_files, "raw": f.raw_files}


def main():
    res = {"script": SCRIPT, "utc": C.utc(), "queries": {}}
    ids = ",".join(str(t) for t in TARGETS)
    res["queries"]["exact_tic"] = q(f"select tid,toi,tfopwg_disp,ra,dec,pl_orbper,pl_tranmid,rowupdate from toi "
                                    f"where tid in ({ids})", "nea_toi_exact")
    res["queries"]["control_toi101"] = q("select tid,toi,tfopwg_disp,pl_orbper from toi where tid=231663901",
                                         "nea_toi_control")
    res["queries"]["max_rowupdate"] = q("select max(rowupdate) as last_update, count(*) as n from toi",
                                        "nea_toi_maxrowupdate")
    for tic, t in TARGETS.items():
        res["queries"][f"cone2_{tic}"] = q(
            f"select tid,toi,tfopwg_disp,ra,dec,pl_orbper from toi where contains(point('icrs',ra,dec),"
            f"circle('icrs',{t['ra']:.6f},{t['dec']:.6f},{2 / 60:.6f}))=1", f"nea_toi_cone2_{tic}")
    for k, v in res["queries"].items():
        log(SCRIPT, f"{k}: {v['describe']} rows={None if v['rows'] is None else len(v['rows'])} "
                    f"{(v['rows'] or [])[:2]} err={v['error_head']}")
    save_json(C.PARTS / "c03c_nea_toi.json", res)


if __name__ == "__main__":
    main()
