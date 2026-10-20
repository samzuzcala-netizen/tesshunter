"""P11 compatibility receipts; preserve the historical verifier output exactly."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def main(label):
    import psutil
    root = REPO / "p11/results" / label
    root.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update(TESSHUNTER_OFFLINE="1", PYTHONIOENCODING="utf-8",
               LIGHTKURVE_CACHE=str(REPO / "data/cache/lightkurve"),
               OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
               MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1",
               MPLCONFIGDIR=str(REPO / "p11/work/matplotlib"))
    git = lambda *args: subprocess.check_output(["git", *args], cwd=REPO, text=True)
    (root / "git_status.txt").write_text(git("status", "--porcelain=v1", "--untracked-files=all"), encoding="utf-8")
    versions = {}
    for name in ("numpy", "scipy", "astropy", "lightkurve", "transitleastsquares", "wotan", "batman-package", "pytest", "psutil"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    owners = []
    for p in psutil.process_iter(["pid", "ppid", "name", "cmdline", "create_time"]):
        try:
            if "python" in (p.info["name"] or "").lower():
                owners.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    receipt = dict(started_utc=utc(), interpreter=sys.executable, python=sys.version,
                   head=git("rev-parse", "HEAD").strip(), branch=git("branch", "--show-current").strip(),
                   tracked_diff=git("diff", "--stat"), staged_diff=git("diff", "--cached", "--stat"),
                   cpu_logical=psutil.cpu_count(), memory_bytes=psutil.virtual_memory().total,
                   disk=shutil.disk_usage(REPO)._asdict(), versions=versions, python_owners=owners,
                   environment={k: env[k] for k in ("TESSHUNTER_OFFLINE", "LIGHTKURVE_CACHE", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")})
    write(root / "entry.json", receipt)
    start = time.perf_counter()
    with (root / "pytest.log").open("w", encoding="utf-8") as log:
        code = subprocess.run([sys.executable, "-m", "pytest", "-q", "-o", "cache_dir=p11/work/pytest_cache"],
                              cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    receipt["pytest"] = dict(exit_code=code, wall_seconds=time.perf_counter() - start,
                             log_sha256=sha(root / "pytest.log"))
    print("pytest", receipt["pytest"], flush=True)
    historical = REPO / "p9/results/verification.json"
    old = historical.read_bytes()
    (root / "p9_verification_original.bin").write_bytes(old)
    start = time.perf_counter()
    try:
        with (root / "p9_verify.log").open("w", encoding="utf-8") as log:
            code = subprocess.run([sys.executable, "p9/verify.py"], cwd=REPO, env=env,
                                  stdout=log, stderr=subprocess.STDOUT).returncode
        new = historical.read_bytes()
        (root / "p9_verification.json").write_bytes(new)
        measured = json.loads(new)
        receipt["p9_verifier"] = dict(exit_code=code, wall_seconds=time.perf_counter() - start,
                                     passing_checks=sum(v is True for v in measured["checks"].values()),
                                     failures=measured["failures"])
    finally:
        historical.write_bytes(old)
        receipt["p9_original_restored"] = historical.read_bytes() == old
        receipt["p9_original_sha256"] = hashlib.sha256(old).hexdigest()
        receipt["completed_utc"] = utc()
        write(root / "entry.json", receipt)
    print(json.dumps(receipt["p9_verifier"]), flush=True)
    print("historical verifier restored", receipt["p9_original_restored"], flush=True)
    return 0 if receipt["pytest"]["exit_code"] == 0 and receipt["p9_original_restored"] and receipt["p9_verifier"]["failures"] == ["baseline_git_HEAD_unchanged"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    raise SystemExit(main(parser.parse_args().label))
