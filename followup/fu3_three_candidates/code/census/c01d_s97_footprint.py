"""Footprint check for TIC 270573718 in Sector 97: the 15" MAST cone returned the TICA S97 cam4/ccd1 FFI
observation but no SPOC S97 FFI observation.  This fetches the SPOC observation tess-s0097-4-1 (same
camera/CCD) by obs_id so that its s_region polygon can be compared (one light MAST query)."""
from __future__ import annotations

import census_common as C
from census_common import log, save_json, tag

from astroquery import cache_conf

cache_conf.cache_active = False
from astroquery.mast import Observations  # noqa: E402
from astroquery.mast import conf as mast_conf  # noqa: E402

mast_conf.timeout = 120
SCRIPT = "c01d_s97_footprint"


def main():
    res = {"script": SCRIPT, "utc": C.utc(), "rows": []}
    with tag("mast_obsid_tess-s0097-4-1") as rc:
        try:
            tb = Observations.query_criteria(obs_id="tess-s0097-4-1")
            for r in tb:
                res["rows"].append({k: (r[k].item() if hasattr(r[k], "item") else r[k])
                                    for k in ("obs_id", "obsid", "s_region", "t_min", "t_max", "sequence_number",
                                              "provenance_name")})
            res["error"] = None
        except Exception as e:  # noqa: BLE001
            res["error"] = f"{type(e).__name__}: {e}"
    res["receipts"] = [r["receipt"] for r in rc]
    log(SCRIPT, f"rows={len(res['rows'])} err={res['error']}")
    save_json(C.PARTS / "c01d_s97_footprint.json", res)


if __name__ == "__main__":
    main()
