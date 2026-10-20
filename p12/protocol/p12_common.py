"""P12 paths and durable receipts; copied from P10.3 common, isolated roots."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import time
import uuid

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / 'p12'
DATA = REPO / 'data/survey/p12'
PY = Path(r'C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe')


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path) -> str:
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value, *, replace=False) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(value, indent=2, allow_nan=False) + '\n'
    if not replace:
        # Exclusive creation is required for owners, attempts and immutable seals.
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        return
    temp = path.with_name(path.name + f'.{os.getpid()}.{uuid.uuid4().hex}.tmp')
    with temp.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    for attempt in range(10):
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(.1 * (attempt + 1))


def append_jsonl(path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def environment(offline=True) -> dict:
    os.environ.update(PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1',
        LIGHTKURVE_CACHE=str(REPO / 'data/cache/lightkurve'), OMP_NUM_THREADS='1',
        OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1',
        NUMBA_NUM_THREADS='1', BLIS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1',
        MPLCONFIGDIR=str(ROOT / 'work/matplotlib'))
    if offline:
        os.environ['TESSHUNTER_OFFLINE'] = '1'
    else:
        os.environ.pop('TESSHUNTER_OFFLINE', None)
    return dict(os.environ)


def assert_data_root() -> Path:
    resolved = DATA.resolve(strict=True)
    expected = Path(r'D:\tesshunter_data\survey_p12').resolve(strict=True)
    if resolved != expected or resolved.drive.casefold() != 'd:':
        raise RuntimeError('P12 data junction must resolve to D:\\tesshunter_data\\survey_p12')
    return resolved


def redirect_audit_cache(audit_module) -> Path:
    assert_data_root()
    cache = DATA / 'lightkurve'
    cache.mkdir(parents=True, exist_ok=True)
    audit_module.AUDIT_CACHE = cache
    os.environ['LIGHTKURVE_CACHE'] = str(cache)
    return cache


def initialize() -> None:
    for name in ('protocol', 'manifests', 'results', 'logs', 'work', 'tests', 'heldout'):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    assert_data_root()


def host_hash(tic, purpose='development', seed=20260920) -> str:
    return hashlib.sha256(f'{seed}:{purpose}:{int(tic)}'.encode()).hexdigest()


def config() -> dict:
    return read(ROOT / 'protocol/config.json')
