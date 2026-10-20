"""Print every VizieR row found by c04 (read-only)."""
import json
import sys

import census_common as C

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d = json.loads((C.TABLES / "vizier_cones.json").read_text(encoding="utf-8"))
for tic, out in d["results"].items():
    for cat, rec in out.items():
        for tname, tb in rec["tables"].items():
            for r in tb["rows"]:
                keep = {k: v for k, v in r.items() if v not in (None, "", []) and not k.startswith("_RA") and
                        not k.startswith("_DE")}
                print(f"== {tic} {tname} :: " + json.dumps(keep, default=str)[:2500])
