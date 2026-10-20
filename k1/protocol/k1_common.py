"""K1 paths and durable receipts (pattern of p12/protocol/p12_common.py; isolated roots)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import sys
import time
import uuid

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "k1"
DATA = Path(os.environ.get("K1_DATA", r"D:\tesshunter_k1"))
STORE = DATA / "audit_lc"
PY = Path(r"C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe")
TRUTH = ROOT / "truth"
CONTROLLERS = DATA / "controllers"
RUNS = DATA / "runs"
RECEIPTS = DATA / "funnel_receipts"
RUNTIMES = DATA / "runtimes"
JOBS = DATA / "jobs"


def environment(offline: bool = False) -> dict:
    """Set the K1 interpreter environment (before anything imports tesshunter)."""
    os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data" / "cache" / "lightkurve"))
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    # the P12 worker environment: single-threaded BLAS / OpenMP / numba, so results are bit-reproducible
    # (reduction order) and 24 parallel workers do not oversubscribe the 32 logical CPUs
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
              "NUMBA_NUM_THREADS", "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ[k] = "1"
    if offline:
        os.environ["TESSHUNTER_OFFLINE"] = "1"
    else:
        os.environ.pop("TESSHUNTER_OFFLINE", None)
    for p in (REPO / "src", REPO / "scripts", ROOT / "protocol"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    return dict(os.environ)


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _default(o):
    import numpy as np
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return o.as_posix()
    raise TypeError(f"not JSON serialisable: {type(o)}")


def safe(value):
    """Replace non-finite floats by None recursively (strict JSON)."""
    import math
    import numpy as np
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return [safe(v) for v in value.tolist()]
    if isinstance(value, np.generic):
        return safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write(path, value, *, replace: bool = False) -> None:
    """Exclusive creation by default (immutable receipts); ``replace`` writes atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(safe(value), indent=1, allow_nan=False, default=_default) + "\n"
    if not replace:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        return
    temp = path.with_name(path.name + f".{os.getpid()}.{uuid.uuid4().hex}.tmp")
    with temp.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    for attempt in range(20):
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.1 * (attempt + 1))


def append_jsonl(path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(safe(value), allow_nan=False, default=_default) + "\n")
        stream.flush()


def ledger(tic: int, use: str, stage: str, note: str = "") -> None:
    """Exposure ledger: every star K1 touches (survey-blindness record)."""
    path = ROOT / "manifests" / "exposure_ledger.csv"
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        if new:
            stream.write("utc,tic_id,use,stage,note\n")
        stream.write(f"{utc()},{int(tic)},{use},{stage},{note.replace(',', ';')}\n")
