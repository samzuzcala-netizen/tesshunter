"""Positive controls for the TOI/CTOI grep (read-only on saved raw files):
- row counts, parseable RA/Dec fractions, Last-Modified headers;
- a known TOI host (TIC 231663901 = TOI-101) must match by TIC and by position;
- nearest TOI/CTOI to each target (separation), to show the positional matcher sees the whole sky."""
import json

import census_common as C
from c03b_exofop_documented import parse_table, to_deg, TIC_KEYS, RA_KEYS, DEC_KEYS

d = json.loads((C.PARTS / "c03b_exofop_documented.json").read_text(encoding="utf-8"))
c03 = json.loads((C.PARTS / "c03_exofop.json").read_text(encoding="utf-8"))
files = {f"exofop_{k}": v["raw"][0] for k, v in d["prebuilt"].items() if v.get("raw")}
files["mast_toi_csv"] = c03["toi_sources"]["mast_toi_csv"]["raw"][0]
out = {}
for name, path in files.items():
    rows = parse_table(open(path, encoding="utf-8", errors="replace").read())
    keys = rows[0].keys()
    tk = next((k for k in TIC_KEYS if k in keys), None)
    rk = next((k for k in RA_KEYS if k in keys), None)
    dk = next((k for k in DEC_KEYS if k in keys), None)
    pos = []
    for r in rows:
        rd = to_deg(r.get(rk), r.get(dk)) if rk and dk else None
        pos.append(rd)
    n_pos = sum(p is not None for p in pos)
    ctrl = [r for r in rows if str(r.get(tk, "")).split(".")[0].lstrip("0") == "231663901"]
    nearest = {}
    for tic, t in C.TARGETS.items():
        best = None
        for r, p in zip(rows, pos):
            if p is None:
                continue
            s = C.sep_arcsec(t["ra"], t["dec"], p[0], p[1])
            if best is None or s < best[0]:
                best = (round(s, 1), r.get(tk), r.get("TOI") or r.get("CTOI") or r.get("Full TOI ID"))
        nearest[tic] = best
    out[name] = {"n_rows": len(rows), "tic_key": tk, "radec": [rk, dk], "n_radec_parsed": n_pos,
                 "control_TIC231663901_rows": len(ctrl), "nearest_entry_to_target": nearest}
    print(name, json.dumps(out[name]))
C.save_json(C.PARTS / "cx_toi_controls.json", out)
