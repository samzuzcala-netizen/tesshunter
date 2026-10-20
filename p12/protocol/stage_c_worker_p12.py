"""One top-level p10.0 Stage C job in the candidate's case root (copy of P10.3
``stage_c_worker_v1.py``): strongest peak with the conditional robust fallback, the
one-cadence duration floor, native cadence, 8 TLS threads, oversampling 3, spectra saved
(gotcha 7: C runs only as a top-level process, never inside a pool worker).

The receipt carries ``deadline_s`` and ``attempt``; a TIMEOUT is written by the controller, and
a second TIMEOUT is closed UNRESOLVED by ``close_stage_c_p12`` (never a rejection).
"""
from p12_common import REPO, ROOT, DATA, environment, read, write, sha, utc
environment()
import sys
import time
import traceback
from pathlib import Path

from blind_io_p12 import install as install_guard, summary as guard_summary
from blind_search_worker_p12 import safe

RUNTIME_FIELDS = {'candidate_id', 'tic_id', 'base_runtime_path', 'base_runtime_sha256', 'label', 'instrument', 'route',
                  'upstream', 'threads', 'oversampling', 'deadline_s', 'attempt', 'source_hashes'}


def stage_decision(receipt):
    if not receipt or receipt.get('status') != 'COMPLETE':
        return 'OPERATIONAL_UNKNOWN'
    m = receipt.get('measurement') or {}
    d = m.get('decision', m.get('gate'))
    return d if d in ('PASS', 'FAIL', 'HOLD') else 'OPERATIONAL_UNKNOWN'


ROUTES = ('normal', 'forced_negatives', 'injection_sample')


def validate_upstream(route, receipts):
    """normal: A PASS, S PASS or HOLD, B PASS (5d); forced_negatives: A PASS (4a); injection_sample: A PASS and S PASS
    or HOLD, the 30-injection C sample of 2a step 4 (injections never run B, which 2a registers on false alarms only)."""
    if route not in ROUTES:
        raise RuntimeError('Unregistered C route')
    if stage_decision(receipts.get('A')) != 'PASS':
        raise RuntimeError('Stage C requires a Stage A PASS')
    if route in ('normal', 'injection_sample') and stage_decision(receipts.get('S')) not in ('PASS', 'HOLD'):
        raise RuntimeError(f'Stage C on the {route} route requires S PASS/HOLD')
    if route == 'normal' and stage_decision(receipts.get('B')) != 'PASS':
        raise RuntimeError('Stage C on the normal route requires B PASS')


def main(runtime_path, expected_sha256):
    runtime_path = Path(runtime_path)
    if not runtime_path.is_absolute():
        runtime_path = REPO / runtime_path
    guard = install_guard(ROOT / f'results/funnel_io/{runtime_path.parent.name}/C_{runtime_path.stem}.jsonl')
    if sha(runtime_path) != expected_sha256:
        raise RuntimeError('Frozen C runtime changed')
    runtime = read(runtime_path)
    if set(runtime) != RUNTIME_FIELDS:
        raise RuntimeError('Unregistered C runtime fields')
    if runtime['threads'] != 8 or runtime['oversampling'] != 3:
        raise RuntimeError('C execution arguments differ from the registered 8 threads / oversampling 3')
    for name, digest in runtime['source_hashes'].items():
        if sha(REPO / name) != digest:
            raise RuntimeError('C registered source changed: ' + name)
    if sha(REPO / runtime['base_runtime_path']) != runtime['base_runtime_sha256']:
        raise RuntimeError('C base runtime changed')
    cid, attempt, label = runtime['candidate_id'], int(runtime['attempt']), runtime['label']
    folder = 'C' if attempt == 1 else 'C_a2'
    destination = ROOT / f'results/funnel/{label}/{folder}/{cid}.json'
    if destination.exists():
        raise FileExistsError(destination)
    upstream = {}
    for stage, ref in runtime['upstream'].items():
        if sha(REPO / ref['path']) != ref['sha256']:
            raise RuntimeError('C upstream evidence changed')
        upstream[stage] = read(REPO / ref['path'])
    validate_upstream(runtime['route'], upstream)
    base = read(REPO / runtime['base_runtime_path'])
    import funnel_stage_p12 as W
    started, timer, cpu = utc(), time.perf_counter(), time.process_time()
    F, A, root, restore = W.setup(base)
    try:
        rule_set = F.V.RULE_SET
        if (rule_set.version != 'p10.0' or rule_set.stagec_peak_rule != 'strongest' or
                not rule_set.stagec_sde_robust_fallback or not rule_set.duration_floor_cadence):
            raise RuntimeError('C scientific route differs from frozen p10.0')
        job = F.V.jobs()[0]
        measurement = F.V.stagec_one(job, threads=8, oversampling=3, force=False)
        decision = measurement.get('decision')
        status = 'COMPLETE' if decision in ('PASS', 'FAIL') else 'OPERATIONAL_UNKNOWN'
        receipt = dict(candidate_id=cid, tic_id=runtime['tic_id'], stage='C', status=status, decision=decision,
                       measurement=measurement, label=label, route=runtime['route'], case_root=base['root'],
                       threads=8, oversampling=3, rules_version='p10.0', deadline_s=runtime['deadline_s'], attempt=attempt)
    except Exception as exc:
        receipt = dict(candidate_id=cid, tic_id=runtime['tic_id'], stage='C', status='OPERATIONAL_UNKNOWN', label=label,
                       deadline_s=runtime['deadline_s'], attempt=attempt, error=f'{type(exc).__name__}: {exc}'[:500],
                       traceback=traceback.format_exc()[-3000:])
    finally:
        if restore:
            restore()
    receipt.update(started_utc=started, completed_utc=utc(), wall_seconds=time.perf_counter() - timer,
                   cpu_seconds=time.process_time() - cpu, runtime_sha256=expected_sha256, io=guard_summary(guard))
    write(destination, safe(receipt))
    write(ROOT / f'results/funnel_timing/{label}/{folder}/{cid}.json',
          {k: v for k, v in safe(receipt).items() if k not in ('measurement', 'io', 'traceback')})
    print('C', receipt['status'], flush=True)
    if receipt['status'] != 'COMPLETE':
        raise SystemExit(2)


if __name__ == '__main__':
    main(*sys.argv[1:])
