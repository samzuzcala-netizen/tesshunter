"""Census tasks 6/10/11 (discovery step): find the VizieR catalogue identifiers to query.
Vizier.find_catalogs for keyword sets (recorded verbatim) and description look-ups for the identifiers named in
the task.  Output: parts/c04a_vizier_discover.json.  No sky queries here.
"""
from __future__ import annotations

import census_common as C
from census_common import log, save_json, tag

from astroquery import cache_conf

cache_conf.cache_active = False
from astroquery.vizier import Vizier  # noqa: E402

SCRIPT = "c04a_vizier_discover"
KEYWORDS = [
    "TESS eclipsing binaries", "eclipsing binaries TESS full-frame images", "TESS eclipsing binary catalog",
    "LAMOST DR10", "LAMOST DR9", "LAMOST DR8", "LAMOST low resolution", "LAMOST medium resolution",
    "GALAH DR4", "GALAH DR3", "RAVE DR6", "APOGEE DR17",
    "SOAR speckle TESS", "speckle imaging TESS objects of interest", "high-resolution imaging TESS",
    "Catalina periodic variables", "CRTS variable stars", "WISE periodic variable stars",
    "ASAS-SN variable stars", "ATLAS variable stars", "ZTF periodic variables",
    "HARPS radial velocities", "Gaia DR3 variability",
]
IDS = ["J/ApJS/258/16", "B/vsx", "II/366", "J/AJ/156/241", "J/ApJS/249/18", "II/365", "J/ApJS/237/28",
       "J/ApJS/213/9", "J/MNRAS/469/3688", "V/164", "J/MNRAS/506/150", "III/283", "III/286", "J/AJ/159/19",
       "J/AJ/162/192", "J/A+A/636/A74", "I/358"]


def main():
    v = Vizier(row_limit=50)
    v.TIMEOUT = 120
    res = {"script": SCRIPT, "utc": C.utc(), "keywords": {}, "ids": {}}
    for kw in KEYWORDS:
        with tag(f"vizier_find_{C.safe_name(kw, 40)}") as rc:
            try:
                d = v.find_catalogs(kw, max_catalogs=40)
                res["keywords"][kw] = {"catalogs": {k: getattr(val, "description", str(val)) for k, val in d.items()},
                                       "error": None}
            except Exception as e:  # noqa: BLE001
                res["keywords"][kw] = {"catalogs": {}, "error": f"{type(e).__name__}: {e}"}
        res["keywords"][kw]["receipts"] = [r["receipt"] for r in rc]
        log(SCRIPT, f"{kw!r}: {len(res['keywords'][kw]['catalogs'])} {res['keywords'][kw]['error']}")
    for cid in IDS:
        with tag(f"vizier_desc_{C.safe_name(cid, 40)}") as rc:
            try:
                d = v.find_catalogs(cid, max_catalogs=10)
                res["ids"][cid] = {"catalogs": {k: getattr(val, "description", str(val)) for k, val in d.items()},
                                   "error": None}
            except Exception as e:  # noqa: BLE001
                res["ids"][cid] = {"catalogs": {}, "error": f"{type(e).__name__}: {e}"}
        res["ids"][cid]["receipts"] = [r["receipt"] for r in rc]
        log(SCRIPT, f"{cid}: {res['ids'][cid]['catalogs']}")
    save_json(C.PARTS / "c04a_vizier_discover.json", res)


if __name__ == "__main__":
    main()
