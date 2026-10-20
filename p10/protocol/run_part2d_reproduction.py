"""Run the Part 2d regression gates with every new artifact routed into P10.

The P7 numerical algorithm is unchanged. The P8 check explicitly separates
cached-byte idempotence from fresh event/rule recomputation on saved TLS inputs.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "p10/results/part2d_20260911"
SCRATCH = REPO / "data/survey/p10/part2d"
P8 = REPO / "data/survey/p8"
sys.path[:0] = [str(REPO / "scripts"), str(REPO / "src"), str(Path(__file__).parent)]


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def run(name, args):
    cmd = [sys.executable, *map(str, args)]
    print(utc(), name, "START", flush=True)
    with (OUT / f"{name}.log").open("x", encoding="utf-8") as log:
        code = subprocess.run(cmd, cwd=REPO, stdout=log, stderr=subprocess.STDOUT).returncode
    save(f"{name}_exit.json", dict(utc=utc(), command=cmd, exit=code))
    if code:
        raise RuntimeError(f"{name} exited {code}; see its P10 log")
    print(utc(), name, "DONE", flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lock = OUT / "reproduction.lock"
    with lock.open("x", encoding="utf-8") as stream:
        json.dump(dict(pid=os.getpid(), started_utc=utc()), stream)
    try:
        run("full_pytest", ["-m", "pytest", "-q"])
        # P7 scratch inputs are hard-linked: prove the originals remain intact.
        originals = sorted(p for p in (REPO / "data/survey/p6").rglob("*")
                           if p.is_file() and p.suffix in (".json", ".npz"))
        original_hashes = {str(p.relative_to(REPO)): sha(p) for p in originals}
        save("p7_original_inputs_before.json", original_hashes)
        run("p7_all_16", ["p10/protocol/p7_reproduce_p10.py", "all", "--slices", "16"])
        p7 = json.loads((SCRATCH / "p7/reproduce_p7.json").read_text(encoding="utf-8"))
        for part in p7["parts"].values():
            for key in ("n_field_differences", "n_decision_differences",
                        "worst_relative_difference", "n_records_with_a_difference",
                        "worst_absolute_array_difference"):
                assert part.get(key, 0) == 0, (part["part"], key, part.get(key))
        assert sum(p["n_records"] for p in p7["parts"].values()) == 823
        assert all(sha(REPO / p) == h for p, h in original_hashes.items())
        save("p7_verified.json", dict(utc=utc(), records=823, slices=16,
             field_differences=0, decision_differences=0, worst_relative_difference=0.0,
             original_files_unchanged=len(original_hashes), summary_sha256=sha(SCRATCH / "p7/reproduce_p7.json")))
        replay_p8()
        save("reproduction_complete.json", dict(utc=utc(), status="all_checks_passed"))
    except BaseException as exc:
        save("reproduction_failure.json", dict(utc=utc(), error=repr(exc)))
        raise
    finally:
        lock.unlink()


def replay_p8():
    from p7_reproduce_p10 import diff_records
    population = sorted(p.stem for p in (P8 / "stageA").glob("*.json")
                        if json.loads(p.read_text(encoding="utf-8")).get("rules_version") == "p8.0"
                        and json.loads(p.read_text(encoding="utf-8")).get("decision") in ("PASS", "FAIL"))
    selected = random.Random(20260908).sample(population, 20)
    rows = list(csv.DictReader((P8 / "survivors.csv").open(newline="", encoding="utf-8")))
    def key(row):
        return f"tic{int(row['tic_id'])}_P{float(row['period_days']):.4f}"
    selected_rows = [r for r in rows if key(r) in selected]
    assert len(selected_rows) == 20
    sources = {P8 / "survivors.csv", P8 / "candidates.csv"}
    for k in selected:
        sources.add(P8 / "stageA" / f"{k}.json")
        sources.add(P8 / "prep" / f"{k}.json")
        sources.add(P8 / "tls" / f"{k}_lc.npz")
        sources.add(P8 / "tls" / f"{k}_forced.json")
    source_hashes = {str(p.relative_to(REPO)): sha(p) for p in sorted(sources)}
    save("p8_replay_selection.json", dict(utc=utc(), seed=20260908,
         population="sorted settled p8.0 Stage A record keys", population_size=len(population),
         algorithm="Python random.Random(seed).sample(population, 20)", selected=selected,
         original_sha256=source_hashes, stages_replayed=["A"], no_new_heldout_outcomes=True))
    for mode in ("cached", "fresh"):
        root = SCRATCH / "p8_replay" / mode
        root.mkdir(parents=True, exist_ok=False)
        with (root / "survivors.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(selected_rows)
        shutil.copy2(P8 / "candidates.csv", root / "candidates.csv")
        for k in selected:
            for sub, filename in (("prep", f"{k}.json"), ("tls", f"{k}_lc.npz"),
                                  ("tls", f"{k}_forced.json"), ("stageA", f"{k}.json")):
                if mode == "fresh" and sub == "stageA":
                    continue
                (root / sub).mkdir(exist_ok=True)
                shutil.copy2(P8 / sub / filename, root / sub / filename)
        run(f"p8_{mode}", ["scripts/p8_funnel.py", "--rules", "p8.0", "--root", root,
                          "stageA", "--slices", "16", "--threads", "1"])
        evidence = []
        for k in selected:
            old = P8 / "stageA" / f"{k}.json"
            new = root / "stageA" / f"{k}.json"
            a, b = json.loads(new.read_text(encoding="utf-8")), json.loads(old.read_text(encoding="utf-8"))
            comparison = diff_records(a, b)
            same = new.read_bytes() == old.read_bytes()
            evidence.append(dict(key=k, original_sha256=sha(old), replay_sha256=sha(new),
                                 byte_identical=same, scientific_comparison=comparison))
            assert a["decision"] == b["decision"] and a["rules_version"] == "p8.0"
            assert comparison["n_differences"] == 0 and comparison["worst_relative"] == 0.0
            if mode == "cached":
                assert same, k
        assert all(sha(REPO / p) == h for p, h in source_hashes.items())
        save(f"p8_{mode}_verified.json", dict(utc=utc(), mode=mode, n=20,
             byte_identical=sum(r["byte_identical"] for r in evidence), original_sources_unchanged=True,
             description=("CLI cached-record idempotence; exact bytes and hashes" if mode == "cached" else
                 "Fresh event and Stage A rule computation on original saved preparation/forced TLS inputs; "
                 "timestamps and measured seconds are expected to differ. The existing P7 comparator is "
                 "reported separately, never counted as fresh byte identity."), rows=evidence))


if __name__ == "__main__":
    main()
