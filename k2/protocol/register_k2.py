"""Hash RULES_K2.md (and later amendments) into k2/manifests/registration.json (pattern of register_k1.py)."""
import json
import sys

from k2_common import K2, REPO, sha, read, write, utc


def register(note="initial registration before any K2 measurement"):
    path = K2 / "manifests" / "registration.json"
    rules = K2 / "protocol" / "RULES_K2.md"
    entry = {"utc": utc(), "file": rules.relative_to(REPO).as_posix(), "sha256": sha(rules), "note": note}
    amendments = sorted((K2 / "protocol").glob("AMENDMENT_K2_*.md"))
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
    reg = {"prompt": "K2", "registered_utc": entry["utc"], "rules": entry, "amendments": [], "chain": [entry]}
    write(path, reg)
    return reg


def verify():
    reg = read(K2 / "manifests" / "registration.json")
    rules = K2 / "protocol" / "RULES_K2.md"
    return {"rules_registered_sha256": reg["rules"]["sha256"], "rules_now_sha256": sha(rules),
            "chain_last_sha256": reg["chain"][-1]["sha256"],
            "amendments": [dict(a, unchanged=sha(REPO / a["file"]) == a["sha256"]) for a in reg["amendments"]]}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        print(json.dumps(verify(), indent=1))
    else:
        print(json.dumps(register(*sys.argv[1:2]), indent=1))
