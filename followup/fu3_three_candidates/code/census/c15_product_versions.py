"""Tabulate product versions / data-release identifiers per target, provenance and sector from the MAST
product lists saved by c01 (no network).  Output: tables/product_versions.csv and a compact JSON summary."""
import csv
import json
import re

import census_common as C

rows = []
for tic in C.TARGETS:
    d = json.loads((C.TABLES / f"mast_tess_{tic}.json").read_text(encoding="utf-8"))
    for p in d["products"]:
        fn = p.get("productFilename") or ""
        if not fn.endswith((".fits", ".txt")) or "postcard" in fn or "_bkg" in fn or "_pm." in fn:
            continue
        m = re.search(r"-s0*(\d{1,3})[-_]", fn) or re.search(r"_s0*(\d{1,3})-", fn) or re.search(r"s0*(\d{1,3})", fn)
        sector = int(m.group(1)) if m else None
        prov = ("SPOC-2min" if fn.startswith("tess2") else fn.split("_")[1].upper())
        vtag = re.search(r"_tess_(v[0-9.]+)_", fn)
        rows.append({"tic": tic, "provenance": prov, "sector": sector, "file": fn,
                     "file_version_tag": vtag.group(1) if vtag else None, "prvversion": p.get("prvversion"),
                     "size_bytes": p.get("size"), "dataRights": p.get("dataRights")})
rows.sort(key=lambda r: (r["tic"], r["provenance"], r["sector"] or 0, r["file"]))
with open(C.TABLES / "product_versions.csv", "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
summ = {}
for r in rows:
    if r["file"].endswith(".txt") or "_tp." in r["file"]:
        continue
    k = f"{r['tic']}|{r['provenance']}"
    summ.setdefault(k, []).append(f"S{r['sector']}:{r['file_version_tag'] or ''}/{r['prvversion'] or ''}")
C.save_json(C.TABLES / "product_versions_summary.json", summ)
for k, v in summ.items():
    print(k, " ".join(v))
