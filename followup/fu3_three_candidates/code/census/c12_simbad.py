"""Census task 12 (bibliographic part): SIMBAD (CDS TAP) entries for the three targets, all identifiers and the
list of references (bibcodes) attached to each object, plus any SIMBAD object within 60" (with otype)."""
from __future__ import annotations

import csv
import io

import census_common as C
from census_common import TARGETS, fetch, log, save_json

SCRIPT = "c12_simbad"
TAP = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"


def q(query, label):
    f = fetch(TAP, label, method="POST", timeout=(30, 120),
              data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": query})
    rows = None
    if f.ok and not (f.text or "").lstrip().startswith("<"):
        rows = list(csv.DictReader(io.StringIO(f.text)))
    return {"query": query, "status": f.status, "describe": f.describe(), "rows": rows,
            "error_head": None if rows is not None else (f.text or f.exc or "")[:400],
            "receipts": f.receipt_files, "raw": f.raw_files}


def main():
    res = {"script": SCRIPT, "utc": C.utc(), "targets": {}}
    for tic, t in TARGETS.items():
        ids = f"'TIC {tic}', 'Gaia DR3 {t['gaia']}'"
        r1 = q("SELECT b.oid, b.main_id, b.otype, b.sp_type, b.nbref, b.ra, b.dec, i.id FROM ident AS i "
               f"JOIN basic AS b ON i.oidref = b.oid WHERE i.id IN ({ids})", f"simbad_ident_{tic}")
        rec = {"lookup": r1}
        oids = sorted({r["oid"] for r in (r1["rows"] or [])})
        if oids:
            ol = ",".join(oids)
            rec["all_ids"] = q(f"SELECT oidref, id FROM ident WHERE oidref IN ({ol})", f"simbad_allids_{tic}")
            # "year" is an ADQL reserved word and must be double-quoted (SIMBAD TAP error message, 2026-10-18)
            rec["refs"] = q('SELECT h.oidref, r.bibcode, "year", r.title FROM has_ref AS h JOIN ref AS r ON '
                            f'h.oidbibref = r.oidbib WHERE h.oidref IN ({ol}) ORDER BY "year"',
                            f"simbad_refs_{tic}")
        rec["cone60"] = q("SELECT main_id, otype, ra, dec, nbref, DISTANCE(POINT('ICRS', ra, dec), POINT('ICRS', "
                          f"{t['ra']:.6f}, {t['dec']:.6f}))*3600 AS sep_arcsec FROM basic WHERE CONTAINS(POINT('ICRS', "
                          f"ra, dec), CIRCLE('ICRS', {t['ra']:.6f}, {t['dec']:.6f}, {60 / 3600:.8f})) = 1 "
                          "ORDER BY sep_arcsec", f"simbad_cone60_{tic}")
        res["targets"][tic] = rec
        log(SCRIPT, f"{tic}: lookup={r1['rows']} refs={None if 'refs' not in rec else (rec['refs']['rows'] or [])[:20]} "
                    f"cone60={[(r['main_id'], r['otype'], round(float(r['sep_arcsec']), 1)) for r in (rec['cone60']['rows'] or [])]}")
    save_json(C.PARTS / "c12_simbad.json", res)


if __name__ == "__main__":
    main()
