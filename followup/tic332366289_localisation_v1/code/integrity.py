"""Before/after integrity hashes of the historical files this follow-up reads.

Scope: exactly the files listed in HISTORICAL_FILES below (packet, case
records, cached pixel cubes and light curves, the two inspected source files,
the sector policy). It does not cover the rest of the repository.

usage: python integrity.py before|after
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import common as C


def historical_files():
    files = []
    files += sorted(p for p in C.PACKET.iterdir() if p.is_file())
    for sub in ["stageA", "stageB", "stageC", "stageD", "secondary", "fit", "events",
                "eb_screen", "pixels", "neighbours", "prep", "expensive", "tls"]:
        d = C.CASE / sub
        if d.is_dir():
            files += sorted(p for p in d.iterdir() if p.is_file())
    files += [C.TESSCUT[s] for s in sorted(C.TESSCUT)]
    files += [C.spoc_lc(s) for s in (57, 77, 78, 79, 80, 84)]
    files += [C.REPO / "src" / "tesshunter" / "centroid.py",
              C.REPO / "p12" / "protocol" / "rules_p12.py",
              C.REPO / "p10" / "part3" / "manifests" / "sector_policy_effective.json"]
    return files


def main(which: str) -> None:
    assert which in ("before", "after")
    rows = []
    for p in historical_files():
        st = p.stat()
        rows.append({"path": str(p), "bytes": st.st_size, "mtime_ns": st.st_mtime_ns,
                     "sha256": C.sha256(p)})
    out = {"utc": datetime.now(timezone.utc).isoformat(), "which": which,
           "scope": "only the historical files listed here (read-only inputs of this follow-up)",
           "n_files": len(rows), "files": rows}
    C.write_json(C.INPUTS / f"integrity_{which}.json", out)
    if which == "after":
        import json
        before = json.load(open(C.INPUTS / "integrity_before.json"))
        b = {r["path"]: r for r in before["files"]}
        diffs = []
        for r in rows:
            o = b.get(r["path"])
            if o is None or o["sha256"] != r["sha256"] or o["bytes"] != r["bytes"] or o["mtime_ns"] != r["mtime_ns"]:
                diffs.append(r["path"])
        missing = sorted(set(b) - {r["path"] for r in rows})
        res = {"n_compared": len(rows), "n_changed": len(diffs), "changed": diffs, "missing": missing}
        C.write_json(C.INPUTS / "integrity_compare.json", res)
        print(res)
    print(which, len(rows), "files hashed")


if __name__ == "__main__":
    main(sys.argv[1])
