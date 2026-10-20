"""P9 paths and immutable evidence helpers. No truth imports in execution.

P12 held-out copy of ``p9/common.py`` (4c). Edits, each tested in ``p12/tests/test_heldout_p12.py``:
(1) ``BASE = p12/heldout/baseline/source``, the hashed snapshot of ``src/`` and ``scripts/`` at HEAD
    (``p12/manifests/heldout_source_seal.json``); the P12 overlay (``p12/protocol``, ``p10/protocol``)
    is imported from its frozen location after the snapshot and hashed in the same seal.
(5) outputs under ``p12/heldout/{results,logs,work}``; Lightkurve / TESScut cache
    ``data/survey/p12/heldout/lightkurve/``.
(6) inputs read-only from ``p9/inputs/raw`` with the harness's own selection (``select_products``: the
    frozen sector policy, sectors 56 to 105 without the excluded QLP sectors, one product per sector by
    the audit author preference), recorded per host in ``p12/heldout/manifests/input_selection.json``.
"""
from pathlib import Path
import hashlib, json, os, sys, datetime
H = Path(__file__).resolve().parent
REPO = next(p for p in H.parents if (p / 'p9').is_dir() and (p / 'p12').is_dir())
P9 = REPO / 'p9'
BASE = H / 'baseline/source'
OVERLAY = (REPO / 'p12/protocol', REPO / 'p10/protocol')
CACHE = REPO / 'data/survey/p12/heldout/lightkurve'
POLICY = REPO / 'p10/part3/manifests/sector_policy_effective.json'
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
def base_first():
    """Keep the snapshot ahead of any live path a later import inserted (edit 1)."""
    for path in reversed([str(BASE/'src'), str(BASE/'scripts')]):
        while path in sys.path: sys.path.remove(path)
        sys.path.insert(0, path)
    for path in OVERLAY:
        if str(path) not in sys.path: sys.path.append(str(path))
def frozen_imports():
    base_first()
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['LIGHTKURVE_CACHE'] = str(CACHE)
    os.environ['TESSHUNTER_OFFLINE'] = '1'
    for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS']:
        os.environ[k] = '1'
def verify_seal():
    """Every snapshot and overlay file equals the held-out source seal (a mismatch is STOP-1)."""
    seal = read(REPO / 'p12/manifests/heldout_source_seal.json')
    bad = [name for name, digest in seal['files'].items() if not (REPO/name).is_file() or sha(REPO/name) != digest]
    present = {p.relative_to(REPO).as_posix() for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    extra = sorted(present - set(seal['files']))
    if bad or extra:
        raise RuntimeError(f'STOP-1 held-out source seal mismatch: {bad[:5]} extra {extra[:5]}')
    return seal
def select_products(tic):
    """Edit (6): the harness's own selection from the P9 raw inputs under the frozen sector policy."""
    policy = read(POLICY)
    sectors, excluded = set(policy['sectors']), set(policy['excluded_qlp'])
    preference = {'SPOC': 0, 'TESS-SPOC': 1, 'QLP': 2}
    index_path = P9/'inputs/raw'/f'tic{int(tic)}'/'index.json'
    index = read(index_path)
    best, dropped = {}, []
    for p in index.get('products', []):
        if 'file' not in p: continue
        s = int(p['sector'])
        if s not in sectors: dropped.append(dict(file=p['file'], reason='sector outside the frozen policy (56 to 105)')); continue
        if p.get('author') == 'QLP' and s in excluded: dropped.append(dict(file=p['file'], reason='QLP sector excluded by the frozen policy')); continue
        if p.get('author') not in preference: dropped.append(dict(file=p['file'], reason='author outside the audit preference')); continue
        if s not in best or preference[p['author']] < preference[best[s]['author']]:
            if s in best: dropped.append(dict(file=best[s]['file'], reason='lower author preference in the same sector'))
            best[s] = p
        else:
            dropped.append(dict(file=p['file'], reason='lower author preference in the same sector'))
    chosen = [best[s] for s in sorted(best)]
    return dict(tic_id=int(tic), index=index_path.relative_to(REPO).as_posix(), index_sha256=sha(index_path),
                selected=[dict(sector=int(p['sector']), author=p['author'], cadence_s=p.get('cadence_s'), file=p['file'],
                               sha256=sha(index_path.parent/p['file'])) for p in chosen], dropped=dropped,
                policy=POLICY.relative_to(REPO).as_posix(), policy_sha256=sha(POLICY))
def load_products(tic):
    """The selected products (every stored array plus the index metadata), each verified by SHA-256."""
    import numpy as np
    recorded = read(H/'manifests/input_selection.json')['hosts'][str(int(tic))]
    fresh = select_products(tic)
    if fresh['selected'] != recorded['selected'] or fresh['index_sha256'] != recorded['index_sha256']:
        raise RuntimeError('Held-out input selection changed since it was recorded')
    meta = {p['file']: p for p in read(P9/'inputs/raw'/f'tic{int(tic)}'/'index.json')['products'] if 'file' in p}
    out = []
    for rec in recorded['selected']:
        path = P9/'inputs/raw'/f'tic{int(tic)}'/rec['file']
        if sha(path) != rec['sha256']: raise RuntimeError('Held-out raw input changed: ' + rec['file'])
        # As policy_products_p12.load_policy_products: every stored array, then the index metadata.
        with np.load(path, allow_pickle=False) as z:
            p = {k: np.asarray(z[k]).copy() for k in z.files}
        p.update(meta[rec['file']])
        out.append(p)
    if not out: raise RuntimeError(f'TIC {tic}: no held-out product under the frozen policy')
    return out
def install_products(tic):
    """Patch both historical loaders for exactly one held-out TIC; return a restorer."""
    from tesshunter import survey_p8
    import audit_p5
    previous = survey_p8.load_audit_products, audit_p5.load_products
    def products(requested, *args, **kwargs):
        if int(requested) != int(tic): raise RuntimeError('Held-out product request for another star')
        return load_products(tic)
    survey_p8.load_audit_products = products; audit_p5.load_products = products
    def restore():
        survey_p8.load_audit_products, audit_p5.load_products = previous
    return restore
