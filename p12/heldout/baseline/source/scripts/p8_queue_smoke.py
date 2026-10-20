"""Replay settled injection/control records through the shared-queue workers and hash-check them."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "scripts")]
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data/cache/lightkurve"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def hashes(roots_and_keys):
    paths = []
    for root, key in roots_and_keys:
        for directory, suffix in (("stageA", ".json"), ("secondary", ".json"), ("prep", ".json"),
                                  ("tls", "_forced.json"), ("tls", "_lc.npz")):
            path = root / directory / f"{key}{suffix}"
            if path.exists():
                paths.append(path)
    return {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def main():
    import audit_p5 as A
    import p8_completeness as C
    import p8_funnel as F
    from p8_work_queue import create_queue

    injections = C.recovered_jobs(C._load_results(C.INJ_RUN))[:5]
    C.load_funnel_outcomes(injections, rules="p7.0")
    F.set_root(C.FA_ROOT)
    F.set_rules("p7.0")
    controls = F.V.jobs()[:5]
    for job in controls:
        C.require_settled_record(C.FA_ROOT / "stageA" / f"{F.V.kkey(job['tic_id'], job['period'])}.json",
                                 "p7.0", "decision", ("PASS", "FAIL"))
    selected = [(C.INJ_ROOT / j["job_id"], C.kkey(j["tic_id"], j["period_days"])) for j in injections]
    selected += [(C.FA_ROOT, F.V.kkey(j["tic_id"], j["period"])) for j in controls]
    before = hashes(selected)
    queue = C.P8 / "logs" / f"queue_smoke_inj_{time.time_ns()}.sqlite"
    create_queue(queue, [j["job_id"] for j in injections])
    C.run_slice(0, 1, "p7.0", False, queue)
    if hasattr(A, "_load_products_uninjected"):
        A.load_products = A._load_products_uninjected
    F.set_root(C.FA_ROOT)
    F.set_rules("p7.0")
    queue = C.P8 / "logs" / f"queue_smoke_fa_{time.time_ns()}.sqlite"
    create_queue(queue, [F.V.kkey(j["tic_id"], j["period"]) for j in controls])
    F.run_slice("A", 0, 1, 1, 5, False, queue)
    after = hashes(selected)
    changed = [path for path in before if before[path] != after.get(path)]
    result = {"generated_utc": C.utc(), "n_injections": len(injections), "n_controls": len(controls),
              "n_files_hashed": len(before), "changed": changed, "hashes": before}
    A.jdump(C.P8 / "queue_smoke_p8.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "hashes"}), flush=True)
    if changed:
        raise SystemExit("shared-queue replay changed a cached scientific record")


if __name__ == "__main__":
    main()
