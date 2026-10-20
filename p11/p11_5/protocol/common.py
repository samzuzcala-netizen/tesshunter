"""Isolated P11.5 paths, immutable receipts and single-thread science environment."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

REPO = Path(__file__).resolve().parents[3]
ROOT = REPO / 'p11/p11_5'
DATA = REPO / 'data/survey/p11/p11_5'

def utc():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path, value, *, replace=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        raise FileExistsError(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(tmp, path)

def event(kind, **fields):
    path = ROOT / 'manifests/events.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(dict(utc=utc(), event=kind, **fields), allow_nan=False) + '\n')
        f.flush()
        os.fsync(f.fileno())

def order(tic, purpose):
    return hashlib.sha256(f'20260913:p11_5:{purpose}:{int(tic)}'.encode()).hexdigest()

def environment():
    os.environ.update(TESSHUNTER_OFFLINE='1', PYTHONIOENCODING='utf-8',
        PYTHONDONTWRITEBYTECODE='1', LIGHTKURVE_CACHE=str(REPO / 'data/cache/lightkurve'),
        OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
        NUMEXPR_NUM_THREADS='1', NUMBA_NUM_THREADS='1',
        MPLCONFIGDIR=str(ROOT / 'work/matplotlib'))

def resume(text):
    (ROOT / 'RESUME_P11_5.md').write_text('# P11.5 active\n\n' + text + '\n', encoding='utf-8')
