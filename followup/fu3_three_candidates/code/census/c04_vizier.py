"""Census tasks 6, 10 (VizieR part) and 11 (VizieR part): 60-arcsec cones in VizieR catalogues.

Every row within 60" of the TIC epoch-2000 position is listed with:
  sep_tic2000     separation from the TIC epoch-2000 position,
  sep_cat_epoch   separation from the target position propagated (linear pm) to the assumed catalogue epoch,
  min_sep_1990_2025  closest approach of the moving target to the catalogue position over 1990-2025,
plus any period-like columns, with agreement flags against P, 2P and P/2 (1%).  Position match rules:
Gaia-precision catalogues <= 2" (at the catalogue epoch), TESS-based catalogues <= 21"; for periodic-variable
catalogues the period agreement is reported separately and no match is declared on position alone.
VizieR's computed _RAJ2000/_DEJ2000 (J2000 equinox, at the catalogue's own epoch) are used as positions.
"""
from __future__ import annotations

import math
import re

import census_common as C
from census_common import TARGETS, log, save_json, tag

import numpy as np
from astroquery import cache_conf

cache_conf.cache_active = False
import astropy.units as u  # noqa: E402
from astropy.coordinates import SkyCoord  # noqa: E402
from astroquery.vizier import Vizier  # noqa: E402

SCRIPT = "c04_vizier"
# (catalogue, group, rule, assumed position epoch, note)
CATS = [
    ("J/ApJS/258/16", "tess_eb", "tess21", 2000.0, "Prsa+2022 TESS EBs S1-26 (2-min), TIC positions"),
    ("J/ApJ/912/123", "tess_eb", "tess21", 2000.0, "Justesen & Albrecht 2021 TESS (FFI) EB orbital parameters"),
    ("J/ApJS/259/50", "tess_eb", "tess21", 2000.0, "Shi+2022 EA-type EBs observed by TESS"),
    ("J/AJ/170/356", "tess_eb", "tess21", 2000.0, "Tang+2025 TESS catalog of eccentric EBs"),
    ("J/ApJS/279/50", "tess_eb", "tess21", 2000.0, "Kostov+2025 TESS EBs from FFIs (TESS Ten Thousand)"),
    ("J/MNRAS/511/4285", "tess_eb", "tess21", 2015.5, "Battley+2022 CDIPS Year-1 EB candidates"),
    ("J/A+A/652/A120", "tess_eb", "tess21", 2000.0, "IJspeert+2021 OBA-type EBs from TESS"),
    ("J/ApJS/254/39", "toi", "tess21", 2000.0, "Guerrero+2021 TOI catalogue (S1-26 snapshot)"),
    ("B/vsx", "variable", "var", 2000.0, "AAVSO VSX (VizieR live copy)"),
    ("II/366", "variable", "var", 2015.5, "ASAS-SN variable stars (catv2021)"),
    ("J/AJ/156/241", "variable", "var", 2017.0, "ATLAS variables (Heinze+2018)"),
    ("J/ApJS/249/18", "variable", "var", 2018.5, "ZTF periodic variables (Chen+2020)"),
    ("J/ApJS/237/28", "variable", "var", 2010.5, "WISE periodic variables (Chen+2018)"),
    ("J/ApJS/213/9", "variable", "var", 2008.0, "Catalina CSS periodic variables (Drake+2014)"),
    ("J/MNRAS/469/3688", "variable", "var", 2008.0, "Catalina CSS/SSS periodic variables (Drake+2017)"),
    ("V/164", "spectro", "gaia2", 2000.0, "LAMOST DR5 (Luo+2019)"),
    ("V/162", "spectro", "gaia2", 2000.0, "LAMOST DR11 (Luo+2026)"),
    ("J/ApJS/282/29", "spectro", "gaia2", 2000.0, "LAMOST DR11 low-resolution M-type star catalogue"),
    ("J/MNRAS/506/150", "spectro", "gaia2", 2015.5, "GALAH DR3 (Buder+2021)"),
    ("J/other/PASA/42.51", "spectro", "gaia2", 2016.0, "GALAH DR4 (Buder+2025)"),
    ("III/283", "spectro", "gaia2", 2000.0, "RAVE DR6 (Steinmetz+2020)"),
    ("III/286", "spectro", "gaia2", 2000.0, "APOGEE-2 DR17 allStar (Abdurro'uf+2022)"),
    ("J/A+A/636/A74", "spectro", "gaia2", 2000.0, "HARPS RV database (Trifonov+2020)"),
    ("J/AJ/159/19", "imaging", "tess21", 2000.0, "SOAR TESS survey I (Ziegler+2020)"),
    ("J/AJ/162/192", "imaging", "tess21", 2000.0, "SOAR TESS survey II (Ziegler+2021)"),
    ("J/AJ/161/164", "imaging", "tess21", 2000.0, "Gemini/WIYN speckle of TESS stars (Howell+2021)"),
    ("J/AJ/165/180", "imaging", "gaia2", 2000.0, "SOAR speckle survey results (Tokovinin 2023)"),
    ("B/wds", "imaging", "gaia2", 2000.0, "Washington Double Star catalogue (VizieR live copy)"),
]
PER_RE = re.compile(r"^(per|period|p|prd|porb|p_orb|lsper|pfin|perlc|plc|per[a-z0-9_]*|period[a-z0-9_]*)$", re.I)


def min_sep_over_epochs(tic, ra, dec, e0=1990.0, e1=2025.0):
    best = None
    for e in np.linspace(e0, e1, 71):
        pra, pdec = C.pos_at_epoch(tic, float(e))
        s = C.sep_arcsec(pra, pdec, ra, dec)
        if best is None or s < best[0]:
            best = (s, float(e))
    return best


def per_agree(p, P):
    out = {}
    for name, ref in (("P", P), ("2P", 2 * P), ("P/2", P / 2)):
        out[name] = abs(p - ref) / ref <= 0.01
    return out


def val(x):
    if x is None or x is np.ma.masked:
        return None
    if hasattr(x, "item"):
        x = x.item()
    if isinstance(x, bytes):
        x = x.decode()
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def main():
    v = Vizier(columns=["**", "_RAJ2000", "_DEJ2000", "+_r"], row_limit=-1)
    v.TIMEOUT = 120
    res = {"script": SCRIPT, "utc": C.utc(), "radius_arcsec": 60, "catalogues": CATS, "results": {}}
    for tic, t in TARGETS.items():
        coord = SkyCoord(t["ra"], t["dec"], unit="deg")
        out = {}
        for cat, group, rule, epoch, note in CATS:
            rec = {"catalogue": cat, "group": group, "rule": rule, "assumed_epoch": epoch, "note": note,
                   "tables": {}, "error": None}
            with tag(f"vizier_{C.safe_name(cat, 30)}_{tic}") as rc:
                try:
                    tl = v.query_region(coord, radius=60 * u.arcsec, catalog=cat)
                except Exception as e:  # noqa: BLE001
                    tl, rec["error"] = None, f"{type(e).__name__}: {e}"
            rec["receipts"] = [r["receipt"] for r in rc]
            rec["raw"] = [r["raw"] for r in rc if r.get("raw")]
            rec["http"] = [r["status"] for r in rc]
            if tl is not None:
                for tname in tl.keys():
                    tb = tl[tname]
                    rows = []
                    for r in tb:
                        ra, dec = val(r["_RAJ2000"]), val(r["_DEJ2000"])
                        d = {c: val(r[c]) for c in tb.colnames}
                        if ra is None or dec is None:
                            d["_sep_note"] = "no position"
                            rows.append(d)
                            continue
                        ra, dec = float(ra), float(dec)
                        pra, pdec = C.pos_at_epoch(tic, epoch)
                        ms = min_sep_over_epochs(tic, ra, dec)
                        d["sep_tic2000"] = round(C.sep_arcsec(t["ra"], t["dec"], ra, dec), 3)
                        d["sep_cat_epoch"] = round(C.sep_arcsec(pra, pdec, ra, dec), 3)
                        d["min_sep_1990_2025"] = round(ms[0], 3)
                        d["min_sep_epoch"] = round(ms[1], 1)
                        pers = {}
                        for c in tb.colnames:
                            if PER_RE.match(c) and isinstance(d.get(c), (int, float)) and d.get(c):
                                pers[c] = {"value": d[c], "unit": str(tb[c].unit) if tb[c].unit else None,
                                           "agree_1pct": per_agree(float(d[c]), t["P"])}
                        d["period_columns"] = pers
                        lim = 21.0 if rule == "tess21" else 2.0
                        d["position_match"] = (d["sep_cat_epoch"] <= lim) if rule != "var" else None
                        d["position_within_2arcsec_cat_epoch"] = d["sep_cat_epoch"] <= 2.0
                        rows.append(d)
                    rows.sort(key=lambda d: d.get("sep_cat_epoch", 1e9))
                    rec["tables"][tname] = {"n": len(rows), "rows": rows,
                                            "description": getattr(tb, "meta", {}).get("description")}
            out[cat] = rec
            n = sum(x["n"] for x in rec["tables"].values())
            log(SCRIPT, f"{tic} {cat}: tables={list(rec['tables'].keys())} n={n} err={rec['error']} http={rec['http']}")
        res["results"][tic] = out
    save_json(C.TABLES / "vizier_cones.json", res)
    # compact part file
    comp = {"script": SCRIPT, "utc": res["utc"], "summary": {}}
    for tic, out in res["results"].items():
        comp["summary"][tic] = {cat: {"error": r["error"], "http": r["http"],
                                      "n_by_table": {k: v["n"] for k, v in r["tables"].items()},
                                      "receipts": r["receipts"]} for cat, r in out.items()}
    save_json(C.PARTS / "c04_vizier.json", comp)


if __name__ == "__main__":
    main()
