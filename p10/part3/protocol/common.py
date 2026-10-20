"""Isolated paths and durable receipts for the bounded prompt 10.3 experiment."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os

REPO = Path(__file__).resolve().parents[3]
ROOT = REPO / "p10/part3"
DATA = REPO / "data/survey/p10/part3"


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value, *, replace=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        raise FileExistsError(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def environment(offline=True):
    os.environ.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
        LIGHTKURVE_CACHE=str(REPO / "data/cache/lightkurve"), OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1",
        NUMBA_NUM_THREADS="1", MPLCONFIGDIR=str(ROOT / "work/matplotlib"))
    if offline:
        os.environ["TESSHUNTER_OFFLINE"] = "1"
    else:
        os.environ.pop("TESSHUNTER_OFFLINE", None)


def initialize():
    for name in ("protocol", "manifests", "results", "logs", "work", "tests"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)


def host_hash(tic, purpose="development"):
    return hashlib.sha256(f"20260914:p10_3:{purpose}:{int(tic)}".encode()).hexdigest()
