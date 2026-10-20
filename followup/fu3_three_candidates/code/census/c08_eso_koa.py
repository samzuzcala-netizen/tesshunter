"""Census task 10 (non-VizieR part): ESO archive (programmatic TAP: ivoa.ObsCore Phase-3 products and dbo.raw
raw frames) and the Keck Observatory Archive TAP service (anonymous; public metadata only).

ESO ObsCore: footprint intersection with a 10" circle around the epoch-2000 TIC position.
ESO raw: telescope pointing within a 30" box (raw-frame RA/Dec are pointing coordinates; for imagers these are
field centres, so a raw-frame miss does not exclude the target lying in a large field).
KOA: TAP_SCHEMA.tables is listed first; instrument tables with ra/dec columns are then cone-searched (30").
"""
from __future__ import annotations

import csv
import io

import census_common as C
from census_common import TARGETS, fetch, log, save_json

SCRIPT = "c08_eso_koa"
ESO_TAP = "https://archive.eso.org/tap_obs/sync"
KOA_TAP = "https://koa.ipac.caltech.edu/TAP/sync"


def tap(url, query, label, fmt="csv"):
    f = fetch(url, label, method="POST", timeout=(30, 120),
              data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": fmt, "QUERY": query})
    rows, err = None, None
    txt = f.text or ""
    if f.ok and not txt.lstrip().startswith("<"):
        try:
            rows = list(csv.DictReader(io.StringIO(txt)))
        except Exception as e:  # noqa: BLE001
            err = f"csv parse: {e}"
    elif f.ok and txt.lstrip().startswith("<"):
        try:
            from astropy.io.votable import parse_single_table
            t = parse_single_table(io.BytesIO(f.resp.content)).to_table()
            rows = [{c: (None if v is None else str(v)) for c, v in zip(t.colnames, r)} for r in t]
        except Exception as e:  # noqa: BLE001
            err = f"non-CSV body: {txt[:400]!r} ({type(e).__name__})"
    else:
        err = f"{f.describe()}: {(txt or f.exc or '')[:400]!r}"
    return {"query": query, "status": f.status, "n_rows": None if rows is None else len(rows), "rows": rows,
            "error": err, "receipts": f.receipt_files, "raw": f.raw_files}


def main():
    res = {"script": SCRIPT, "utc": C.utc(), "eso": {}, "koa": {}}
    for tic, t in TARGETS.items():
        ra, dec = t["ra"], t["dec"]
        q1 = ("SELECT obs_collection, obs_id, dp_id, instrument_name, target_name, s_ra, s_dec, t_min, t_max, "
              "em_min, em_max, dataproduct_type, obs_release_date, proposal_id, abmaglim, snr, em_res_power "
              f"FROM ivoa.ObsCore WHERE INTERSECTS(s_region, CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {10 / 3600:.8f})) = 1")
        r1 = tap(ESO_TAP, q1, f"eso_obscore_{tic}")
        import math
        dra = 30 / 3600 / math.cos(math.radians(dec))
        q2 = ("SELECT dp_id, date_obs, mjd_obs, instrument, object, ra, dec, dp_cat, dp_type, dp_tech, prog_id, "
              f"exposure, release_date FROM dbo.raw WHERE ra BETWEEN {ra - dra:.6f} AND {ra + dra:.6f} AND "
              f"dec BETWEEN {dec - 30 / 3600:.6f} AND {dec + 30 / 3600:.6f}")
        r2 = tap(ESO_TAP, q2, f"eso_raw_{tic}")
        res["eso"][tic] = {"obscore_10arcsec": r1, "raw_30arcsec_box": r2}
        log(SCRIPT, f"ESO {tic}: obscore n={r1['n_rows']} err={r1['error']}; raw n={r2['n_rows']} err={r2['error']}")
    # ---- KOA ----
    meta = tap(KOA_TAP, "SELECT table_name, description FROM TAP_SCHEMA.tables", "koa_tables")
    res["koa"]["tables"] = meta
    log(SCRIPT, f"KOA tables: n={meta['n_rows']} err={meta['error']}")
    inst_tables = []
    if meta["rows"]:
        for r in meta["rows"]:
            tn = (r.get("table_name") or "").strip()
            if tn.lower().startswith("koa_") and not tn.lower().startswith("koa_ancillary"):
                inst_tables.append(tn)
    res["koa"]["instrument_tables"] = inst_tables
    res["koa"]["cones"] = {}
    for tic, t in TARGETS.items():
        per = {}
        for tn in inst_tables:
            q = (f"SELECT * FROM {tn} WHERE CONTAINS(POINT('ICRS', ra, dec), "
                 f"CIRCLE('ICRS', {t['ra']:.6f}, {t['dec']:.6f}, {30 / 3600:.8f})) = 1")
            r = tap(KOA_TAP, q, f"koa_{tn}_{tic}")
            per[tn] = r
            if r["n_rows"] or r["error"]:
                log(SCRIPT, f"KOA {tic} {tn}: n={r['n_rows']} err={str(r['error'])[:150]}")
        res["koa"]["cones"][tic] = per
        log(SCRIPT, f"KOA {tic}: tables queried={len(per)} with rows={[k for k, v in per.items() if v['n_rows']]}")
    save_json(C.PARTS / "c08_eso_koa.json", res)


if __name__ == "__main__":
    main()
