"""Positive control for the TCE/CDPP grep: the same grep code must find TIC 231663901 (TOI-101, a 2-min target
in Sector 1) in the S1 TCE and S1 CDPP files saved by c02.  Read-only on the saved raw files."""
import json

import census_common as C
from c02_tce import grep_csv

d = json.loads((C.PARTS / "c02_tce.json").read_text(encoding="utf-8"))
out = {}
for f in d["files"]:
    if f["s_start"] == 1 and f["s_stop"] in (1, 96) and f.get("raw"):
        txt = open(f["raw"][0], encoding="utf-8", errors="replace").read()
        g = grep_csv(txt, [231663901, 262843927])
        out[f["name"]] = {"rows": g["n_data_rows"], "control_231663901": len(g["matches"][231663901]),
                          "target_262843927": len(g["matches"][262843927])}
        if g["matches"][231663901] and isinstance(g["matches"][231663901][0], dict):
            r = g["matches"][231663901][0]
            out[f["name"]]["control_example"] = {k: r.get(k) for k in ("tceid", "tce_period", "tce_time0bt",
                                                                       "tce_depth", "rrmscdpp01p0")}
for k, v in out.items():
    print(k, v)
multi = [f["name"] for f in d["files"] if f["kind"] == "cdpp" and f["s_start"] != f["s_stop"]]
print("multi-sector CDPP files grepped:", multi)
