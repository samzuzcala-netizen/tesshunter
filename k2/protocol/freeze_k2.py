"""K2 Part 4 freeze (RULES_K2 section 6): ``k2/protocol/config.json`` = K1's frozen configuration plus the adopted
C1 / A1 / M1, and ``k2/manifests/freeze_k2.json`` (source hashes of every K2 protocol file, K1's frozen config and
freeze, every touched ``src`` module, the K2 registration and amendments, the decisions).  Input:
``k2/results/decisions_k2.json``.  Refuses to overwrite an existing freeze unless ``--amendment <file>`` is given.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

from k2_common import REPO, K1, K2, read, write, sha, utc

TOUCHED_SRC = ["bls_search.py", "survey.py", "survey_p8.py", "pipeline.py", "event_vet.py", "star_vet.py",
               "secondary.py", "k1_rules.py", "audit_rules.py", "audit_prep.py", "stage_c.py", "verdict_tiers.py"]
WORKERS = {"download": 4, "search": 24, "A": 16, "S": 10, "B": 10, "C": 6, "C_tls_threads": 4, "D": 6}


def build_config(dec: dict) -> dict:
    k1 = read(K1 / "protocol" / "config.json")
    return {"k1_frozen_config_sha256": sha(K1 / "protocol" / "config.json"), "k1": k1,
            "c_variant": dec["C1"]["adopted"] or "K1", "c_bin_errors": "propagated (AMENDMENT_K2_20261014_1)",
            "a1_scope": dec["A1"]["adopted"], "m1": bool(dec["M1"]["adopted"]),
            "s_mode": k1["s_mode"], "preset": k1["preset"], "time_budget_s": k1["time_budget_s"],
            "stage_c": "p10.0 strongest-peak rule on the C1 input; blind TLS 0.5-110 d; oversampling per c_input_k2",
            "workers": WORKERS, "decisions": dec,
            "operations": {"controller": "k2/protocol/controller_k2.py (K1 workers with K1_DATA = D:/tesshunter_k2)",
                           "supervision": "k2/work/wait_k2.sh background waiter (<= 60 min), checkin_k2.py",
                           "deadlines_s": {"search": "budget x 1.6 + 900", "A": 1800, "S": 600, "B": 600, "C": 57600,
                                           "D": 5400}}}


def hashes() -> dict:
    files = sorted(glob.glob(str(K2 / "protocol" / "*.py")) + glob.glob(str(K2 / "protocol" / "*.ps1"))
                   + glob.glob(str(K2 / "protocol" / "*.md")) + glob.glob(str(K1 / "protocol" / "*.py")))
    out = {str(Path(f).relative_to(REPO)).replace("\\", "/"): sha(f) for f in files if not f.endswith("config.json")}
    for m in TOUCHED_SRC:
        out[f"src/tesshunter/{m}"] = sha(REPO / "src" / "tesshunter" / m)
    for s in ("audit_p5.py", "revet_p6.py"):
        out[f"scripts/{s}"] = sha(REPO / "scripts" / s)
    out["p10/protocol/p10_funnel_calibration.py"] = sha(REPO / "p10" / "protocol" / "p10_funnel_calibration.py")
    out["k1/manifests/freeze_k1.json"] = sha(K1 / "manifests" / "freeze_k1.json")
    return out


def main(amendment=None):
    cfg_path, frz_path = K2 / "protocol" / "config.json", K2 / "manifests" / "freeze_k2.json"
    if frz_path.exists() and not amendment:
        raise SystemExit("freeze exists; changes need --amendment <file>")
    dec = read(K2 / "results" / "decisions_k2.json")
    write(cfg_path, build_config(dec), replace=True)
    frz = {"utc": utc(), "config_sha256": sha(cfg_path), "registration": read(K2 / "manifests" / "registration.json"),
           "rules_sha256": sha(K2 / "protocol" / "RULES_K2.md"), "sources": hashes(), "decisions": dec,
           "amendment": amendment, "python": sys.version}
    if frz_path.exists():
        prev = frz_path.with_name(f"freeze_k2_superseded_{utc().replace(':', '')[:15]}.json")
        frz_path.replace(prev)
        frz["supersedes"] = str(prev)
    write(frz_path, frz)
    print(json.dumps({"config_sha256": frz["config_sha256"], "n_sources": len(frz["sources"]),
                      "c_variant": dec["C1"]["adopted"], "a1": dec["A1"]["adopted"], "m1": dec["M1"]["adopted"]}, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--amendment")
    main(ap.parse_args().amendment)
