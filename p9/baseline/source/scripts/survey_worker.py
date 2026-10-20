"""One survey job in one process: ``python scripts/survey_worker.py --job JOB.json --out RESULT.json``.

Reads the job file written by ``run_survey.py``, runs ``tesshunter.survey.run_job``
and writes the result atomically. Exit code 0 on an ``ok`` or ``no_data``
result, 1 on ``error`` (the orchestrator decides about retries). Single
threaded by construction: BLAS/OpenMP thread counts are pinned to 1 before
numpy is imported so 16-20 workers do not oversubscribe the machine.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_var, "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
# No MAST call may hang a worker forever (P3 lesson: eight workers sat six
# hours on an open connection); the orchestrator timeout is the backstop.
import socket
socket.setdefaulttimeout(300.0)

REPO = Path(__file__).resolve().parent.parent
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data" / "cache" / "lightkurve"))
sys.path.insert(0, str(REPO / "src"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--no-download", action="store_true",
                    help="fail with no_data instead of contacting MAST when the stitched cache misses")
    args = ap.parse_args()

    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    from tesshunter import survey

    job = json.loads(Path(args.job).read_text(encoding="utf-8"))
    t0 = time.perf_counter()
    rec = survey.run_job(job, cache_dir=Path(args.cache_dir) if args.cache_dir else None,
                         allow_download=not args.no_download)
    rec["wall_s"] = time.perf_counter() - t0
    rec["attempt_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec["pid"] = os.getpid()
    survey.write_json_atomic(Path(args.out), rec)
    print(f"[{rec['job_id']}] {rec['status']} wall={rec['wall_s']:.0f}s "
          f"planets={len((rec.get('result') or {}).get('planets', []) or [])}", flush=True)
    return 0 if rec["status"] in ("ok", "no_data") else 1


if __name__ == "__main__":
    sys.exit(main())
