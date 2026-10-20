"""P9 paths and immutable evidence helpers. No truth imports in execution."""
from pathlib import Path
import hashlib, json, os, sys, datetime
P9 = Path(__file__).resolve().parent
REPO = P9.parent
BASE = P9 / 'baseline/source'
PYTHON = Path(sys.executable)
SEED = 20260907
def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()
def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding='utf-8')
    os.replace(tmp, path)
def frozen_imports():
    sys.path[:0] = [str(BASE/'src'), str(BASE/'scripts')]
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['LIGHTKURVE_CACHE'] = str(P9/'work/lightkurve')
    os.environ['TESSHUNTER_OFFLINE'] = '1'
    for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS']:
        os.environ[k] = '1'
