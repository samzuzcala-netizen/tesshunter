"""Shared paths, read-only guards and helpers for the three-candidate follow-up (FU3).

Every input written by earlier work is opened read-only.  All new outputs go under ROOT (code, results,
figures, manifests, report, logs) or under CACHE (large downloaded pixel/light-curve products).
"""
from __future__ import annotations

import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import hashlib
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
RES = ROOT / "results"
FIG = ROOT / "figures"
MAN = ROOT / "manifests"
LOGS = ROOT / "logs"
REPORT = ROOT / "report"
CACHE = Path(r"D:\tess_fu3_cache")
for _p in (RES, FIG, MAN, LOGS, REPORT, CACHE):
    _p.mkdir(parents=True, exist_ok=True)

# ---- read-only inputs from earlier work -------------------------------------------------------------
S1 = Path(r"D:\tesshunter_s1")
REPO = Path(r"C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter")
CODEX = Path(r"C:\Users\seanj\Documents\Codex\2026-10-18")
DEEP = CODEX / "do-an-in-depth-analysis-of"                     # original batch-1 deep vetting (19 pp)
CONT = CODEX / "continue-the-seven-candidate-tess-analysis"     # seven-candidate continuation (26 pp)
REVIEW = CODEX / "look-at-the-results-of-batch"                 # batch-1 review that chose the seven
READ_ONLY_ROOTS = (S1, REPO, CODEX)

TICS = (270573718, 262843927, 193718989)
PACKET = {
    270573718: S1 / "packets" / "s1_b1" / "tic270573718_P41.3839",
    262843927: S1 / "packets" / "s1_b1" / "tic262843927_P24.1089",
    193718989: S1 / "packets" / "s1_b1" / "tic193718989_P24.5335",
}
# The candidate id whose packet reached Stage D (filled from the packet job.json at run time).
BTJD0 = 2457000.0   # BTJD = BJD_TDB - 2457000 for TESS-SPOC, SPOC, QLP and TESScut products


def _guard(path: Path) -> None:
    p = Path(path).resolve()
    for r in READ_ONLY_ROOTS:
        try:
            p.relative_to(r.resolve())
        except ValueError:
            continue
        raise PermissionError(f"refusing to write inside a read-only input root: {p}")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(x) for x in o]
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, np.generic):
        return clean(o.item())
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, float) and not np.isfinite(o):
        return None
    return o


def save(path, obj) -> Path:
    path = Path(path)
    _guard(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(clean(obj), indent=1, allow_nan=False), encoding="utf-8")
    os.replace(tmp, path)
    return path


def save_npz(path, **arrays) -> Path:
    path = Path(path)
    _guard(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)
    return path


def sha256(path, chunk=1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def mad(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return 1.4826 * np.median(np.abs(x - np.median(x))) if len(x) else np.nan


def log(name: str, msg: str) -> None:
    line = f"{utc()} {msg}"
    print(line, flush=True)
    with open(LOGS / f"{name}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")
