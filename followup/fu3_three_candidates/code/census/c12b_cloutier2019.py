"""SIMBAD lists Cloutier (2019, AJ 158, 81; arXiv:1812.08145) among the references of TIC 262843927.
This script finds out in what capacity: (1) VizieR J/AJ/158/81 tables queried by position (60") and by TIC;
(2) the arXiv listing/abstract page and the ar5iv HTML rendering grepped for the TIC ID (context lines kept).
Content is treated as data."""
from __future__ import annotations

import html
import re

import census_common as C
from census_common import TARGETS, fetch, log, save_json, tag

from astroquery import cache_conf

cache_conf.cache_active = False
import astropy.units as u  # noqa: E402
from astropy.coordinates import SkyCoord  # noqa: E402
from astroquery.vizier import Vizier  # noqa: E402

from c04_vizier import val  # noqa: E402

SCRIPT = "c12b_cloutier2019"
TIC = 262843927


def main():
    res = {"script": SCRIPT, "utc": C.utc(), "vizier": {}, "ar5iv": None, "arxiv_abs": None}
    v = Vizier(columns=["**", "+_r"], row_limit=-1)
    v.TIMEOUT = 120
    t = TARGETS[TIC]
    with tag("vizier_J_AJ_158_81_cone") as rc:
        try:
            tl = v.query_region(SkyCoord(t["ra"], t["dec"], unit="deg"), radius=60 * u.arcsec, catalog="J/AJ/158/81")
            res["vizier"]["cone60"] = {k: [{c: val(r[c]) for c in tl[k].colnames} for r in tl[k]] for k in tl.keys()}
        except Exception as e:  # noqa: BLE001
            res["vizier"]["cone60"] = f"{type(e).__name__}: {e}"
    res["vizier"]["cone_receipts"] = [r["receipt"] for r in rc]
    with tag("vizier_J_AJ_158_81_meta") as rc:
        try:
            tl = Vizier(columns=["**"], row_limit=1).get_catalogs("J/AJ/158/81")
            res["vizier"]["tables"] = {k: list(tl[k].colnames) for k in tl.keys()}
        except Exception as e:  # noqa: BLE001
            res["vizier"]["tables"] = f"{type(e).__name__}: {e}"
    res["vizier"]["meta_receipts"] = [r["receipt"] for r in rc]
    log(SCRIPT, f"VizieR cone: {res['vizier']['cone60'] if isinstance(res['vizier']['cone60'], str) else {k: len(x) for k, x in res['vizier']['cone60'].items()}}")
    for key, url in (("arxiv_abs", "https://arxiv.org/abs/1812.08145"),
                     ("ar5iv", "https://ar5iv.labs.arxiv.org/html/1812.08145")):
        f = fetch(url, f"cloutier2019_{key}")
        rec = {"url": url, "status": f.status, "describe": f.describe(), "receipts": f.receipt_files, "raw": f.raw_files}
        if f.ok:
            txt = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", " ", f.text,
                                                                 flags=re.S)))
            txt = re.sub(r"\s+", " ", txt)
            hits = [m.start() for m in re.finditer(rf"(?<!\d){TIC}(?!\d)", txt)]
            rec["n_hits"] = len(hits)
            rec["contexts"] = [txt[max(0, h - 400):h + 400] for h in hits[:6]]
            m = re.search(r"(Journal reference|Comments):[^.]{0,200}", txt)
            rec["meta_snippet"] = m.group(0) if m else None
        res[key] = rec
        log(SCRIPT, f"{key}: {f.describe()} hits={rec.get('n_hits')}")
    save_json(C.PARTS / "c12b_cloutier2019.json", res)


if __name__ == "__main__":
    main()
