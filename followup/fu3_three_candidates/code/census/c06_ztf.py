"""Census task 8: ZTF light curves from the IRSA ZTF light-curve API (TIC 193718989 only; the two southern
targets are NOT_APPLICABLE, Dec < -31).

Queries the target and every Gaia DR3 neighbour within 60" with G < 21, positions propagated from Gaia DR3
(epoch 2016.0) to 2020.0 with Gaia proper motions (2-parameter sources kept at their 2016.0 position), radius
0.0014 deg (5.04").  The default collection is recorded; the target is re-queried with the explicit latest
collection named on the IRSA API documentation page to establish which data release the default returns.
Nothing is fitted.  Saved CSVs are copies of the raw responses.
"""
from __future__ import annotations

import csv
import io
import json
import re
from collections import defaultdict

import census_common as C
from census_common import fetch, log, save_json

SCRIPT = "c06_ztf"
TIC = 193718989
API = "https://irsa.ipac.caltech.edu/cgi-bin/ZTF/nph_light_curves"
DOC = "https://irsa.ipac.caltech.edu/docs/program_interface/ztf_lightcurve_api.html"
OUTDIR = C.OUT / "ztf"


def summarize(text, qra, qdec):
    rows = list(csv.DictReader(io.StringIO(text)))
    s = {"n_rows": len(rows), "columns": list(rows[0].keys()) if rows else None, "by_band": {}, "oids": {}}
    byb = defaultdict(list)
    for r in rows:
        byb[r.get("filtercode")].append(r)
    for b, rr in byb.items():
        mjd = [float(r["mjd"]) for r in rr if r.get("mjd")]
        s["by_band"][b] = {"n": len(rr), "n_catflags0": sum(1 for r in rr if str(r.get("catflags")).strip() == "0"),
                           "mjd_min": min(mjd) if mjd else None, "mjd_max": max(mjd) if mjd else None,
                           "n_oids": len({r.get("oid") for r in rr}),
                           "median_mag": sorted(float(r["mag"]) for r in rr if r.get("mag"))[len(rr) // 2] if rr else None}
    byo = defaultdict(list)
    for r in rows:
        byo[r.get("oid")].append(r)
    for o, rr in byo.items():
        ra = sum(float(r["ra"]) for r in rr) / len(rr)
        dec = sum(float(r["dec"]) for r in rr) / len(rr)
        s["oids"][o] = {"n": len(rr), "filtercode": sorted({r.get("filtercode") for r in rr}),
                        "field": sorted({r.get("field") for r in rr}), "mean_ra": ra, "mean_dec": dec,
                        "sep_from_query_arcsec": round(C.sep_arcsec(qra, qdec, ra, dec), 3)}
    return s


def query(label, ra, dec, collection=None):
    # build the query string by hand so that spaces are sent as %20 (as in the IRSA documentation example)
    url = f"{API}?POS=CIRCLE%20{ra:.7f}%20{dec:.7f}%200.0014&BANDNAME=g,r,i&FORMAT=csv"
    if collection:
        url += f"&COLLECTION={collection}"
    return fetch(url, label, timeout=(30, 120))


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    res = {"script": SCRIPT, "utc": C.utc(), "doc": None, "queries": []}
    fd = fetch(DOC, "ztf_api_doc")
    drs = sorted({int(m) for m in re.findall(r"ztf_dr(\d+)", fd.text or "")})
    m = re.findall(r"[^.]*(?:default|latest)[^.]*\.", re.sub(r"<[^>]+>", " ", fd.text or ""), flags=re.I)
    res["doc"] = {"status": fd.status, "describe": fd.describe(), "receipts": fd.receipt_files, "raw": fd.raw_files,
                  "ztf_dr_mentions": drs, "default_or_latest_sentences": [re.sub(r"\s+", " ", x).strip()[:300] for x in m[:8]]}
    log(SCRIPT, f"doc: {fd.describe()} DR mentions={drs}")
    g = json.loads((C.TABLES / "gaia_dr3_census.json").read_text(encoding="utf-8"))
    cone = g["queries"][f"cone90_{TIC}"]["rows"]
    targets = []
    for r in cone:
        sep, gmag = float(r["sep_arcsec"]), float(r["phot_g_mean_mag"]) if r["phot_g_mean_mag"] else 99.0
        if sep > 60.0 or gmag >= 21.0:
            continue
        ra, dec = float(r["ra"]), float(r["dec"])
        pm = (r["pmra"] not in ("", None)) and (r["pmdec"] not in ("", None))
        if pm:
            import math
            dt = 2020.0 - 2016.0
            dec2 = dec + float(r["pmdec"]) * dt / 3.6e6
            ra2 = ra + float(r["pmra"]) * dt / 3.6e6 / math.cos(math.radians(dec))
        else:
            ra2, dec2 = ra, dec
        targets.append({"source_id": r["source_id"], "sep_arcsec_2016": sep, "G": gmag, "ra_2020": ra2,
                        "dec_2020": dec2, "pm_applied": pm, "is_target": sep < 0.01})
    for tg in targets:
        f = query(f"ztf_lc_{tg['source_id']}", tg["ra_2020"], tg["dec_2020"])
        rec = dict(tg)
        rec.update({"status": f.status, "describe": f.describe(), "receipts": f.receipt_files, "raw": f.raw_files})
        txt = f.text or ""
        if f.ok and not txt.lstrip().startswith("<"):
            rec["summary"] = summarize(txt, tg["ra_2020"], tg["dec_2020"])
            p = OUTDIR / f"ztf_lc_gaia{tg['source_id']}.csv"
            C._check_write(p)
            p.write_bytes(f.resp.content)
            rec["saved_csv"] = str(p)
            rec["sha256"] = C.sha256_bytes(f.resp.content)
        else:
            rec["error"] = (txt or f.exc or "")[:500]
        res["queries"].append(rec)
        log(SCRIPT, f"{tg['source_id']} sep={tg['sep_arcsec_2016']:.1f} G={tg['G']:.2f}: {f.describe()} "
                    f"bands={ {b: v['n'] for b, v in rec.get('summary', {}).get('by_band', {}).items()} }")
    # explicit-collection check for the target
    if drs:
        latest = f"ztf_dr{max(drs)}"
        tg = next(x for x in targets if x["is_target"])
        f = query(f"ztf_lc_target_{latest}", tg["ra_2020"], tg["dec_2020"], collection=latest)
        d0 = next(q for q in res["queries"] if q["is_target"])
        res["collection_check"] = {"collection": latest, "status": f.status, "describe": f.describe(),
                                   "receipts": f.receipt_files, "raw": f.raw_files,
                                   "sha256": C.sha256_bytes(f.resp.content) if f.resp is not None else None,
                                   "default_sha256": d0.get("sha256"),
                                   "identical_to_default": (f.resp is not None and d0.get("sha256") ==
                                                            C.sha256_bytes(f.resp.content)),
                                   "error_head": None if f.ok else (f.text or f.exc or "")[:400]}
        if f.ok and not (f.text or "").lstrip().startswith("<"):
            res["collection_check"]["summary_by_band"] = summarize(f.text, tg["ra_2020"], tg["dec_2020"])["by_band"]
        log(SCRIPT, f"collection check {latest}: {f.describe()} identical={res['collection_check']['identical_to_default']}")
    save_json(C.PARTS / "c06_ztf.json", res)


if __name__ == "__main__":
    main()
