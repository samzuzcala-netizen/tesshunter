"""Hash RULES_K1.md (and later amendments) into k1/manifests/registration.json."""
import sys
from k1_common import ROOT, REPO, sha, read, write, utc


def register(note="initial registration before any calibration run"):
    path = ROOT / "manifests" / "registration.json"
    rules = ROOT / "protocol" / "RULES_K1.md"
    entry = {"utc": utc(), "file": rules.relative_to(REPO).as_posix(), "sha256": sha(rules), "note": note}
    amendments = sorted((ROOT / "protocol").glob("AMENDMENT_K1_*.md"))
    if path.exists():
        reg = read(path)
        known = {a["file"] for a in reg["amendments"]}
        for a in amendments:
            rel = a.relative_to(REPO).as_posix()
            if rel not in known:
                reg["amendments"].append({"utc": utc(), "file": rel, "sha256": sha(a)})
        reg["chain"].append(entry)
        write(path, reg, replace=True)
        return reg
    reg = {"prompt": "K1", "registered_utc": entry["utc"], "rules": entry, "amendments": [], "chain": [entry]}
    write(path, reg)
    return reg


def verify():
    reg = read(ROOT / "manifests" / "registration.json")
    rules = ROOT / "protocol" / "RULES_K1.md"
    return {"rules_registered_sha256": reg["rules"]["sha256"], "rules_now_sha256": sha(rules),
            "unchanged_since_registration": reg["rules"]["sha256"] == sha(rules),
            "amendments": [dict(a, unchanged=sha(REPO / a["file"]) == a["sha256"]) for a in reg["amendments"]]}


if __name__ == "__main__":
    import json
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        print(json.dumps(verify(), indent=1))
    else:
        print(json.dumps(register(), indent=1))
