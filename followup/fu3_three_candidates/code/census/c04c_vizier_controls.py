"""VizieR controls for c04: (1) every queried catalogue identifier must resolve to >= 1 table (get_catalogs with
row_limit=1), and each table is checked for position columns (a cone search silently skips tables without
positions) and for TIC / Gaia identifier columns; (2) for every table that has a TIC column, an exact TIC query
(query_constraints) is run for each target, so that position-less TESS catalogues are also covered."""
from __future__ import annotations

import census_common as C
from census_common import TARGETS, log, save_json, tag

from astroquery import cache_conf

cache_conf.cache_active = False
from astroquery.vizier import Vizier  # noqa: E402

from c04_vizier import CATS, val  # noqa: E402

SCRIPT = "c04c_vizier_controls"
POS_COLS = {"RAJ2000", "RA_ICRS", "RAdeg", "RA", "ra", "_RA", "RA_deg", "RAJ2000deg", "RA2000", "RAICRS",
            "_RAJ2000", "RAJ2000_deg", "RAGaia", "ra_deg"}
TIC_COLS = ("TIC", "TICID", "TIC_ID", "tic", "ticid", "TIC-ID", "TICv8", "TIC8")


def main():
    v1 = Vizier(columns=["**"], row_limit=1)
    v1.TIMEOUT = 120
    res = {"script": SCRIPT, "utc": C.utc(), "catalogues": {}}
    for cat, group, rule, epoch, note in CATS:
        rec = {"tables": {}, "error": None}
        with tag(f"vizier_meta_{C.safe_name(cat, 30)}") as rc:
            try:
                tl = v1.get_catalogs(cat)
            except Exception as e:  # noqa: BLE001
                tl, rec["error"] = None, f"{type(e).__name__}: {e}"
        rec["receipts"] = [r["receipt"] for r in rc]
        if tl is not None:
            for tname in tl.keys():
                cols = list(tl[tname].colnames)
                rec["tables"][tname] = {"n_cols": len(cols), "has_position": bool(POS_COLS & set(cols)),
                                        "tic_col": next((c for c in TIC_COLS if c in cols), None),
                                        "gaia_cols": [c for c in cols if "gaia" in c.lower() or c in ("Source", "DR3Name", "DR2Name")],
                                        "colnames_head": cols[:30]}
        res["catalogues"][cat] = rec
        log(SCRIPT, f"{cat}: {len(rec['tables'])} tables; pos={[t['has_position'] for t in rec['tables'].values()]} "
                    f"tic={[t['tic_col'] for t in rec['tables'].values()]} err={rec['error']}")
    # exact TIC queries for tables carrying a TIC column
    vq = Vizier(columns=["**"], row_limit=-1)
    vq.TIMEOUT = 120
    res["tic_queries"] = {}
    for cat, rec in res["catalogues"].items():
        for tname, tinfo in rec["tables"].items():
            if not tinfo["tic_col"]:
                continue
            for tic in TARGETS:
                with tag(f"vizier_tic_{C.safe_name(tname, 40)}_{tic}") as rc:
                    try:
                        tl = vq.query_constraints(catalog=tname, **{tinfo["tic_col"]: f"={tic}"})
                        rows = [{c: val(r[c]) for c in tl[k].colnames} for k in tl.keys() for r in tl[k]]
                        err = None
                    except Exception as e:  # noqa: BLE001
                        rows, err = None, f"{type(e).__name__}: {e}"
                res["tic_queries"][f"{tname}|{tic}"] = {"table": tname, "tic": tic, "tic_col": tinfo["tic_col"],
                                                         "n": None if rows is None else len(rows), "rows": rows,
                                                         "error": err, "receipts": [r["receipt"] for r in rc]}
                log(SCRIPT, f"TIC query {tname} {tic}: n={None if rows is None else len(rows)} err={err}")
    save_json(C.PARTS / "c04c_vizier_controls.json", res)


if __name__ == "__main__":
    main()
