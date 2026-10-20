"""P12 A / S / B worker for every instrument after Part 0 (copy of ``funnel_worker_p12`` / P10.3
``funnel_worker.py``, generalised).

Each candidate runs in its own case root ``DATA/funnel/<label>/cases/<cid>/`` (the C and D
stages later reuse that root). Products come from the frozen input policy
(``policy_products_p12.install(tic, arm)``) or, for an injection, from the frozen injected raw
arrays written evaluator-side by ``prepare_injections_p12`` (index and every array verified by
SHA-256; the worker never sees the injection parameters). Rules: A, S and B run p10.0 under
p12.0 (``rules_p12.configure_early_funnel``). The receipt goes to
``results/funnel/<label>/<stage>/<cid>.json`` (``<stage>_a2`` for the one recorded retry pass).

Superseded 2026-09-23 (AMENDMENTS_P12.md): a case root's one survivor row carries ``rank`` 1 when the collect row has
none (``revet_p6.jobs`` reads it; the Part 2 collect rows are the P10 candidate columns, which have no rank).
"""
from p12_common import REPO, ROOT, DATA, environment, read, write, sha, utc, redirect_audit_cache
environment()
import csv
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from blind_io_p12 import install as install_guard, summary as guard_summary
from blind_search_worker_p12 import safe

RUNTIME_FIELDS = {'candidate_id', 'tic_id', 'candidate', 'all_candidates', 'star', 'products', 'neighbours_reference',
                  'label', 'instrument', 'route', 'root', 'source_hashes', 'attempt', 'population_tier'}
TRUTH_KEYS = ('truth', 'injection', 'injection_model', 'fixed_absolute_model')


def _reject_truth(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in TRUTH_KEYS or str(key).startswith('inj_'):
                raise RuntimeError('Evaluator truth field in a worker runtime')
            _reject_truth(item)
    elif isinstance(value, list):
        for item in value:
            _reject_truth(item)


def _injected_loader(index_path, expected_sha256, tic):
    index_path = REPO / index_path
    if sha(index_path) != expected_sha256:
        raise RuntimeError('Injected raw index changed')
    index = read(index_path)
    if int(index['tic_id']) != int(tic):
        raise RuntimeError('Injected raw index belongs to another host')
    records = index['products']

    def products(requested, *args, **kwargs):
        if int(requested) != int(tic):
            raise RuntimeError('Injected product request for another star')
        out = []
        for record in records:
            path = REPO / record['raw_path']
            if sha(path) != record['raw_sha256']:
                raise RuntimeError('Frozen injected raw array changed')
            with np.load(path, allow_pickle=False) as z:
                product = {k: np.asarray(z[k]) for k in z.files}
            product.update(record['metadata'])
            out.append(product)
        return out
    return products


def setup(runtime):
    for path in (REPO / 'src', REPO / 'scripts', REPO / 'p10/protocol'):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    import p10_funnel_calibration as F
    import audit_p5 as A
    from rules_p12 import configure_early_funnel
    from tesshunter import survey, survey_p8
    tic = int(runtime['tic_id'])
    root = REPO / runtime['root']
    if not root.resolve().is_relative_to(DATA.resolve()):
        raise RuntimeError('Case root outside P12 DATA')
    root.mkdir(parents=True, exist_ok=True)
    # A case root holds one survivor: its rank is 1 unless the collect row carries one (revet_p6.jobs reads it).
    columns = sorted(set(runtime['candidate']) | set(runtime['star']) | {'period_days', 'tic_id', 'rank'})
    candidate = dict(runtime['candidate'], **runtime['star'], tic_id=tic)
    candidate.setdefault('rank', 1)
    for name, rows in (('survivors.csv', [candidate]), ('candidates.csv', runtime['all_candidates'])):
        path = root / name
        if not path.exists():
            with path.open('x', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
                writer.writeheader(); writer.writerows(rows)
    F.LC_ROOT = REPO / 'data/survey/audit_lc'
    F.PACKETS = DATA / 'funnel/empty_packets'
    F.PACKETS.mkdir(parents=True, exist_ok=True)
    redirect_audit_cache(A)
    F.set_root(root)
    configure_early_funnel(F, 'p12.0')
    A.set_input_config(survey.get_config('survey_p10'))
    A.set_roots(root, REPO / 'data/survey/audit_lc')
    redirect_audit_cache(A)
    spec = runtime['products']
    restore = None
    if spec['kind'] == 'policy':
        import policy_products_p12
        restore = policy_products_p12.install(tic, spec['arm'])
    elif spec['kind'] == 'injected':
        loader = _injected_loader(spec['index'], spec['index_sha256'], tic)
        saved = (A.load_products, survey_p8.load_audit_products)
        A.load_products = loader
        survey_p8.load_audit_products = loader

        def restore():
            A.load_products, survey_p8.load_audit_products = saved
    else:
        raise RuntimeError('Unregistered product source')
    star = runtime['star']
    stellar = {'radius': star['radius_rsun'], 'mass': star['mass_msun'], 'teff': star['teff_k'],
               'tmag': star['tmag'], 'ra': star['ra_deg'], 'dec': star['dec_deg']}
    A.stellar_from_cache = lambda requested: stellar if int(requested) == tic else {}
    return F, A, root, restore


def main(stage, runtime_path, expected_sha256):
    if stage not in ('A', 'S', 'B'):
        raise ValueError('Unregistered early stage')
    runtime_path = Path(runtime_path)
    if not runtime_path.is_absolute():
        runtime_path = REPO / runtime_path
    guard = install_guard(ROOT / f'results/funnel_io/{runtime_path.parent.name}/{stage}_{runtime_path.stem}.jsonl')
    if sha(runtime_path) != expected_sha256:
        raise RuntimeError('Frozen runtime changed')
    runtime = read(runtime_path)
    if set(runtime) != RUNTIME_FIELDS:
        raise RuntimeError('Unregistered runtime fields')
    _reject_truth({k: v for k, v in runtime.items() if k != 'source_hashes'})
    cid, tic, attempt = runtime['candidate_id'], int(runtime['tic_id']), int(runtime['attempt'])
    if not runtime_path.stem.startswith(cid):
        raise RuntimeError('Runtime identity differs from its file')
    for name, digest in runtime['source_hashes'].items():
        if sha(REPO / name) != digest:
            raise RuntimeError('Frozen funnel input/source changed: ' + name)
    label = runtime['label']
    folder = stage if attempt == 1 else f'{stage}_a2'
    destination = ROOT / f'results/funnel/{label}/{folder}/{cid}.json'
    if destination.exists():
        raise FileExistsError(destination)
    F, A, root, restore = setup(runtime)
    try:
        if stage == 'B':
            nb = runtime['neighbours_reference']
            if not nb or sha(REPO / nb['path']) != nb['sha256']:
                raise RuntimeError('Complete neighbour reference missing')
            target = root / f'neighbours/tic{tic}.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            write(target, read(REPO / nb['path']), replace=target.exists())
        job = F.V.jobs()[0]
        started, timer, cpu = utc(), time.perf_counter(), time.process_time()
        if stage == 'A':
            measurement = F.V.stagea_one(job, threads=1)
        elif stage == 'S':
            measurement = F.secondary_one(job)
        else:
            measurement = F.V.stageb_one(job)
        decision = measurement.get('decision', measurement.get('gate', measurement.get('status')))
        status = 'OPERATIONAL_UNKNOWN' if decision in ('ERROR', 'SKIP', 'INPUT_ERROR', 'TIMEOUT') else 'COMPLETE'
        receipt = dict(candidate_id=cid, tic_id=tic, stage=stage, status=status, started_utc=started, completed_utc=utc(),
                       wall_seconds=time.perf_counter() - timer, cpu_seconds=time.process_time() - cpu,
                       measurement=measurement, decision=decision, runtime_sha256=sha(runtime_path), rules_version='p10.0',
                       label=label, instrument=runtime['instrument'], route=runtime['route'], attempt=attempt,
                       case_root=runtime['root'], products_kind=runtime['products']['kind'], io=guard_summary(guard),
                       population_tier=runtime['population_tier'])
    except Exception as exc:
        receipt = dict(candidate_id=cid, tic_id=tic, stage=stage, status='OPERATIONAL_UNKNOWN', label=label, attempt=attempt,
                       error=f'{type(exc).__name__}: {exc}'[:500], traceback=traceback.format_exc()[-3000:], io=guard_summary(guard))
    finally:
        if restore:
            restore()
    write(destination, safe(receipt))
    write(ROOT / f'results/funnel_timing/{label}/{folder}/{cid}.json',
          {k: v for k, v in safe(receipt).items() if k not in ('measurement', 'io', 'traceback')})
    print(stage, receipt['status'], flush=True)
    if receipt['status'] != 'COMPLETE':
        raise SystemExit(2)


if __name__ == '__main__':
    main(*sys.argv[1:])
