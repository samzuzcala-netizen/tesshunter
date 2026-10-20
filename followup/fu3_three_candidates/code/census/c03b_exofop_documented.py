"""Census task 5 (second pass): the documented ExoFOP download functions
(https://exofop.ipac.caltech.edu/tess/Introduction_to_ExoFOP_php_functions.php, fetched 2026-10-18), i.e. the
pre-built table files under /tess/json/ and the per-target download_*.php helpers, plus a positional re-match
of the MAST TOI catalogue (c03 matched it by TIC only because its RA/Dec column names were not recognised).
"""
from __future__ import annotations

import csv
import io
import json
import re

import census_common as C
from census_common import TARGETS, fetch, log, save_json

SCRIPT = "c03b_exofop_documented"
EXO = "https://exofop.ipac.caltech.edu/tess"
RA_KEYS = ("RA", "ra", "RA (deg)", "ra_deg", "TIC Right Ascension", "RA [deg]", "ra (deg)")
DEC_KEYS = ("Dec", "dec", "DEC", "Dec (deg)", "dec_deg", "TIC Declination", "Dec [deg]", "dec (deg)")
TIC_KEYS = ("TIC ID", "TIC", "tic", "tid", "ticid", "TIC_ID", "Tic Id")


def classify(f):
    if f.resp is None:
        return "EXCEPTION", f.exc
    t = (f.text or "").strip()
    if f.status != 200:
        return f"HTTP_{f.status}", t[:200]
    if t == "Array":
        return "ARRAY_BODY", t
    if t.startswith("{") or t.startswith("["):
        try:
            json.loads(t)
            return "JSON", t[:200]
        except Exception:
            return "BROKEN_JSON", t[:200]
    low = t[:2000].lower()
    if "<html" in low or "<!doctype" in low:
        txt = re.sub(r"\s+", " ", re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", t, flags=re.S))
        return "HTML", txt.strip()[:400]
    return "TEXT", t[:200]


def to_deg(ra, dec):
    try:
        return float(ra), float(dec)
    except (TypeError, ValueError):
        pass
    try:
        from astropy.coordinates import SkyCoord
        import astropy.units as u
        c = SkyCoord(str(ra), str(dec), unit=(u.hourangle, u.deg))
        return c.ra.deg, c.dec.deg
    except Exception:
        return None


def parse_table(text, delim=","):
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    if not lines:
        return []
    return list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delim))


def grep_rows(rows, tic, t, nb_ids):
    if not rows:
        return None
    keys = rows[0].keys()
    tk = next((k for k in TIC_KEYS if k in keys), None)
    rk = next((k for k in RA_KEYS if k in keys), None)
    dk = next((k for k in DEC_KEYS if k in keys), None)
    exact, nbr, pos = [], [], []
    for r in rows:
        tid = str(r.get(tk, "") or "").strip().split(".")[0].lstrip("0") if tk else ""
        if tid == str(tic):
            exact.append(r)
        elif tid and tid in nb_ids:
            nbr.append(r)
        if rk and dk:
            rd = to_deg(r.get(rk), r.get(dk))
            if rd:
                s = C.sep_arcsec(t["ra"], t["dec"], rd[0], rd[1])
                if s <= 120.0:
                    pos.append({"sep_arcsec": round(s, 2), "row": r})
    return {"tic_key": tk, "ra_key": rk, "dec_key": dk, "n_rows": len(rows), "exact": exact,
            "neighbour_tic": nbr, "within_2arcmin": pos}


def main():
    c03 = json.loads((C.PARTS / "c03_exofop.json").read_text(encoding="utf-8"))
    nb = {int(t): {str(r["ID"]) for r in v["rows"] if r.get("ID") is not None}
          for t, v in c03["tic_neighbours"].items()}
    res = {"script": SCRIPT, "utc": C.utc(), "prebuilt": {}, "per_target_calls": {}, "matches": {}}
    tables = {}
    for name in ("tois.csv", "ctois.csv", "imaging.csv", "spect.csv"):
        f = fetch(f"{EXO}/json/{name}", f"exofop_json_{name}")
        kind, info = classify(f)
        res["prebuilt"][name] = {"url": f"{EXO}/json/{name}", "status": f.status, "describe": f.describe(),
                                 "kind": kind, "info": info, "receipts": f.receipt_files, "raw": f.raw_files,
                                 "last_modified": None if f.resp is None else f.resp.headers.get("Last-Modified")}
        if kind == "TEXT":
            rows = parse_table(f.text)
            if rows and len(rows[0]) > 3:
                tables[f"exofop_{name}"] = rows
                res["prebuilt"][name]["n_rows"] = len(rows)
                res["prebuilt"][name]["columns"] = list(rows[0].keys())[:80]
        log(SCRIPT, f"json/{name}: {f.describe()} kind={kind} info={str(info)[:120]!r}")
    for tic, t in TARGETS.items():
        calls = {}
        for key, url, params in (
            ("gototicid_json", f"{EXO}/gototicid.php", {"target": f"TIC {tic}", "json": ""}),
            ("download_stellar", f"{EXO}/download_stellar.php", {"id": str(tic)}),
            ("download_planet", f"{EXO}/download_planet.php", {"id": str(tic)}),
            ("download_uploads", f"{EXO}/download_uploads.php", {"target": str(tic), "output": "csv"}),
            ("download_filelist", f"{EXO}/download_filelist.php", {"id": str(tic), "output": "csv"}),
            ("download_imaging", f"{EXO}/download_imaging.php", {"target": str(tic), "output": "csv"}),
            ("download_spect", f"{EXO}/download_spect.php", {"target": str(tic), "output": "csv"}),
            ("download_tseries", f"{EXO}/download_tseries.php", {"target": str(tic), "output": "csv"}),
            ("download_nearbytarget", f"{EXO}/download_nearbytarget.php", {"id": str(tic), "output": "csv"}),
        ):
            f = fetch(url, f"exofop_{key}_{tic}", params=params)
            kind, info = classify(f)
            calls[key] = {"url": url, "params": params, "status": f.status, "describe": f.describe(), "kind": kind,
                          "info": info, "receipts": f.receipt_files, "raw": f.raw_files,
                          "body": (f.text or "")[:3000] if kind in ("TEXT", "JSON") else None}
            log(SCRIPT, f"{tic} {key}: {f.describe()} kind={kind} info={str(info)[:100]!r}")
        res["per_target_calls"][tic] = calls
    # MAST TOI catalogue: positional + TIC re-match from the raw file saved by c03
    mast_raw = c03["toi_sources"]["mast_toi_csv"]["raw"]
    if mast_raw:
        txt = open(mast_raw[0], encoding="utf-8", errors="replace").read()
        tables["mast_toi_csv"] = parse_table(txt)
    for tic, t in TARGETS.items():
        res["matches"][tic] = {name: grep_rows(rows, tic, t, nb[tic]) for name, rows in tables.items()}
        log(SCRIPT, f"TIC {tic}: " + "; ".join(
            f"{n}: exact={len(m['exact'])} nbrTIC={len(m['neighbour_tic'])} pos2'={len(m['within_2arcmin'])} "
            f"keys={m['tic_key']},{m['ra_key']},{m['dec_key']}" for n, m in res["matches"][tic].items() if m))
    save_json(C.PARTS / "c03b_exofop_documented.json", res)


if __name__ == "__main__":
    main()
