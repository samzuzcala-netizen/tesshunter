"""Census task 5: ExoFOP access attempts (recorded exactly), with independent TOI sources.

ExoFOP endpoints tried: the TESS index, news and help pages, the site root, the TOI and CTOI CSV downloads,
the per-target page and its &json variant, and the documented download helpers.  Every body is saved and
classified (CSV/JSON data versus HTML/'Array'/error text).  HTTP 200 with an error page counts as
ACCESS_FAILED.  Independent TOI sources: the MAST TOI catalogue CSV and the NASA Exoplanet Archive `toi`
table (TAP).  TIC neighbours within 2 arcmin come from MAST Catalogs.query_region(catalog='TIC').
"""
from __future__ import annotations

import csv
import io
import json
import re

import census_common as C
from census_common import TARGETS, fetch, log, save_json, tag

from astroquery import cache_conf

cache_conf.cache_active = False
import astropy.units as u  # noqa: E402
from astropy.coordinates import SkyCoord  # noqa: E402
from astroquery.mast import Catalogs  # noqa: E402
from astroquery.mast import conf as mast_conf  # noqa: E402

mast_conf.timeout = 120
SCRIPT = "c03_exofop"
EXO = "https://exofop.ipac.caltech.edu"


def classify(f):
    if f.resp is None:
        return "EXCEPTION", f.exc
    t = f.text or ""
    ct = (f.resp.headers.get("Content-Type") or "").lower()
    head = t.strip()[:400]
    if f.status != 200:
        return f"HTTP_{f.status}", head[:200]
    if head == "Array" or head.endswith("Array") and len(head) < 50:
        return "ARRAY_BODY", head
    if "retire" in t.lower()[:20000]:
        i = t.lower().find("retire")
        return "RETIREMENT_TEXT", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t[max(0, i - 300):i + 500]))
    if head.startswith("{") or head.startswith("["):
        try:
            json.loads(t)
            return "JSON", head[:200]
        except Exception:
            return "BROKEN_JSON", head[:200]
    if "<html" in head.lower() or "<!doctype" in head.lower():
        txt = re.sub(r"\s+", " ", re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", t, flags=re.S))
        return "HTML", txt.strip()[:600]
    if "," in head.splitlines()[0] if head else False:
        return "CSV_LIKE", head[:200]
    return "OTHER", head[:200]


def attempt(results, key, url, label, params=None):
    f = fetch(url, label, params=params)
    kind, info = classify(f)
    results[key] = {"url": url, "params": params, "status": f.status, "describe": f.describe(), "kind": kind,
                    "info": info, "content_type": None if f.resp is None else f.resp.headers.get("Content-Type"),
                    "final_url": None if f.resp is None else f.resp.url, "receipts": f.receipt_files,
                    "raw": f.raw_files}
    log(SCRIPT, f"{key}: {f.describe()} kind={kind} info={str(info)[:160]!r}")
    return f, kind


def cell(tb, k, i):
    v = tb[k][i]
    try:
        if getattr(tb[k], "mask", None) is not None and bool(tb[k].mask[i]):
            return None
    except Exception:
        pass
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, bytes):
        v = v.decode()
    if isinstance(v, float) and v != v:
        return None
    return v


def ra_dec_from_row(row, rakeys, deckeys):
    def get(keys):
        for k in keys:
            if k in row and row[k] not in (None, ""):
                return row[k]
        return None
    ra, dec = get(rakeys), get(deckeys)
    if ra is None or dec is None:
        return None
    try:
        return float(ra), float(dec)
    except ValueError:
        try:
            c = SkyCoord(ra, dec, unit=(u.hourangle, u.deg))
            return c.ra.deg, c.dec.deg
        except Exception:
            return None


def main():
    res = {"script": SCRIPT, "utc": C.utc(), "exofop": {}, "toi_sources": {}, "tic_neighbours": {},
           "per_target": {}}
    ex = res["exofop"]
    attempt(ex, "index", f"{EXO}/tess/", "exofop_index")
    attempt(ex, "news", f"{EXO}/tess/news.php", "exofop_news")
    attempt(ex, "help", f"{EXO}/tess/help.php", "exofop_help")
    attempt(ex, "root", f"{EXO}/", "exofop_root")
    f_toi, k_toi = attempt(ex, "toi_csv", f"{EXO}/tess/download_toi.php", "exofop_toi_csv",
                           params={"sort": "toi", "output": "csv"})
    f_ctoi, k_ctoi = attempt(ex, "ctoi_csv", f"{EXO}/tess/download_ctoi.php", "exofop_ctoi_csv",
                             params={"sort": "ctoi", "output": "csv"})
    for tic in TARGETS:
        attempt(ex, f"target_{tic}", f"{EXO}/tess/target.php", f"exofop_target_{tic}", params={"id": str(tic)})
        attempt(ex, f"target_json_{tic}", f"{EXO}/tess/target.php?id={tic}&json", f"exofop_target_json_{tic}")
        attempt(ex, f"imaging_{tic}", f"{EXO}/tess/download_imaging.php", f"exofop_imaging_{tic}",
                params={"id": str(tic), "output": "csv"})
    # ---- TIC neighbours within 2 arcmin (MAST) ----
    for tic, t in TARGETS.items():
        with tag(f"mast_tic_cone2arcmin_{tic}") as rc:
            try:
                tb = Catalogs.query_region(SkyCoord(t["ra"], t["dec"], unit="deg"), radius=2 * u.arcmin,
                                           catalog="TIC")
                keep = ("ID", "ra", "dec", "Tmag", "GAIA", "objType", "disposition", "duplicate_id",
                        "dstArcSec", "version", "Teff", "Vmag", "Jmag", "pmRA", "pmDEC", "TWOMASS", "lumclass")
                rows = [{k: cell(tb, k, i) for k in keep if k in tb.colnames} for i in range(len(tb))]
                err = None
            except Exception as e:  # noqa: BLE001
                rows, err = [], f"{type(e).__name__}: {e}"
        res["tic_neighbours"][tic] = {"n": len(rows), "error": err, "rows": rows,
                                      "receipts": [r["receipt"] for r in rc]}
        log(SCRIPT, f"TIC cone 2' {tic}: n={len(rows)} err={err}")
    # ---- independent TOI sources ----
    toi_src = res["toi_sources"]
    f_mast = fetch("https://archive.stsci.edu/missions/tess/catalogs/toi/tois.csv", "mast_toi_catalog_csv")
    toi_src["mast_toi_csv"] = {"status": f_mast.status, "describe": f_mast.describe(), "receipts": f_mast.receipt_files,
                               "raw": f_mast.raw_files,
                               "last_modified": None if f_mast.resp is None else f_mast.resp.headers.get("Last-Modified")}
    f_nea = fetch("https://exoplanetarchive.ipac.caltech.edu/TAP/sync", "nea_toi_table",
                  params={"query": "select * from toi", "format": "csv"}, timeout=(30, 120))
    toi_src["nea_toi_tap"] = {"status": f_nea.status, "describe": f_nea.describe(), "receipts": f_nea.receipt_files,
                              "raw": f_nea.raw_files}
    log(SCRIPT, f"MAST TOI csv: {f_mast.describe()}; NEA toi: {f_nea.describe()}")
    tables = {}
    for name, f, kind in (("exofop_toi", f_toi, k_toi), ("exofop_ctoi", f_ctoi, k_ctoi),
                          ("mast_toi", f_mast, None), ("nea_toi", f_nea, None)):
        if f.ok and (kind in (None, "CSV_LIKE", "OTHER")):
            txt = f.text
            lines = [ln for ln in txt.splitlines() if not ln.startswith("#")]
            try:
                rows = list(csv.DictReader(io.StringIO("\n".join(lines))))
            except Exception as e:  # noqa: BLE001
                rows = None
                toi_src.setdefault(name, {})["parse_error"] = str(e)
            if rows is not None and rows and len(rows[0]) > 3:
                tables[name] = rows
                toi_src.setdefault(name, {})["n_rows"] = len(rows)
                toi_src[name]["columns"] = list(rows[0].keys())[:60]
    # ---- grep: target TICs, TIC neighbours (2'), and positional matches within 2' ----
    for tic, t in TARGETS.items():
        nb_ids = {str(r["ID"]) for r in res["tic_neighbours"][tic]["rows"] if r.get("ID") is not None}
        per = {}
        for name, rows in tables.items():
            tic_key = next((k for k in rows[0] if k.strip().lower() in ("tic id", "tic", "tid", "tic_id", "ticid")), None)
            ra_keys = [k for k in rows[0] if k.strip().lower() in ("ra", "ra (deg)", "ra_deg", "ra[deg]")]
            dec_keys = [k for k in rows[0] if k.strip().lower() in ("dec", "dec (deg)", "dec_deg", "dec[deg]")]
            exact, nbr, pos = [], [], []
            for r in rows:
                tid = str(r.get(tic_key, "")).strip() if tic_key else ""
                tid = tid.split(".")[0].lstrip("0")
                if tid == str(tic):
                    exact.append(r)
                elif tid in nb_ids:
                    nbr.append(r)
                rd = ra_dec_from_row(r, ra_keys, dec_keys) if (ra_keys and dec_keys) else None
                if rd is not None:
                    s = C.sep_arcsec(t["ra"], t["dec"], rd[0], rd[1])
                    if s <= 120.0:
                        pos.append({"sep_arcsec": round(s, 2), "row": r})
            per[name] = {"tic_column": tic_key, "radec_columns": [ra_keys[:1], dec_keys[:1]],
                         "exact_tic_rows": exact, "neighbour_tic_rows": nbr, "within_2arcmin_rows": pos}
        res["per_target"][tic] = per
        log(SCRIPT, f"TIC {tic}: " + "; ".join(f"{n}: exact={len(v['exact_tic_rows'])} nbr={len(v['neighbour_tic_rows'])} "
                                               f"pos2'={len(v['within_2arcmin_rows'])}" for n, v in per.items()))
    save_json(C.PARTS / "c03_exofop.json", res)


if __name__ == "__main__":
    main()
