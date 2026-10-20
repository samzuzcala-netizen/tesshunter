"""ZTF data-release identification for the default IRSA LC-API collection.

The API documentation still names ztf_dr18 as current, but COLLECTION=ztf_dr18 now returns
"UsageFault: Internal error (invalid TAP query)" (c06).  The IRSA release-notes directory lists dr01..dr24
(fetched 2026-10-18).  This script repeats the target query with COLLECTION=ztf_dr24 and compares the body
with the default-collection body saved by c06 (sha256 and per-band counts)."""
from __future__ import annotations

import json

import census_common as C
from census_common import log, save_json
from c06_ztf import query, summarize

SCRIPT = "c06b_ztf_dr_check"


def main():
    z = json.loads((C.PARTS / "c06_ztf.json").read_text(encoding="utf-8"))
    tg = next(q for q in z["queries"] if q["is_target"])
    out = {"script": SCRIPT, "utc": C.utc(), "checks": []}
    for coll in ("ztf_dr24",):
        f = query(f"ztf_lc_target_{coll}", tg["ra_2020"], tg["dec_2020"], collection=coll)
        rec = {"collection": coll, "status": f.status, "describe": f.describe(), "receipts": f.receipt_files,
               "raw": f.raw_files}
        if f.ok and not (f.text or "").lstrip().startswith("<"):
            sha = C.sha256_bytes(f.resp.content)
            rec.update({"sha256": sha, "default_sha256": tg.get("sha256"), "identical_to_default": sha == tg.get("sha256"),
                        "by_band": summarize(f.text, tg["ra_2020"], tg["dec_2020"])["by_band"],
                        "default_by_band": tg["summary"]["by_band"]})
        else:
            rec["error_head"] = (f.text or f.exc or "")[:400]
        out["checks"].append(rec)
        log(SCRIPT, f"{coll}: {f.describe()} identical={rec.get('identical_to_default')}")
    save_json(C.PARTS / "c06b_ztf_dr_check.json", out)


if __name__ == "__main__":
    main()
