"""P11-only paths, hashing, deterministic host ordering and durable receipts."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
P11 = REPO / "p11"
DATA = REPO / "data/survey/p11"


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def host_order(tic, purpose):
    return hashlib.sha256(f"20260912:{purpose}:{int(tic)}".encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def append_event(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(dict(utc=utc(), **value), allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def science_environment():
    os.environ.update(TESSHUNTER_OFFLINE="1", PYTHONIOENCODING="utf-8",
                      LIGHTKURVE_CACHE=str(REPO / "data/cache/lightkurve"),
                      OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                      MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1",
                      NUMBA_NUM_THREADS="1", MPLCONFIGDIR=str(P11 / "work/matplotlib"))
