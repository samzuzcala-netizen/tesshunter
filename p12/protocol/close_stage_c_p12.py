"""Close a Stage C phase and its one recorded retry (copy of P10.3 ``close_stage_c_v1.py``).

Per job: attempt 1 COMPLETE -> its PASS / FAIL; otherwise the retry's PASS / FAIL; a job that
did not complete after the retry (a second TIMEOUT or an operational failure) is UNRESOLVED
with both receipts, never a rejection. For an UNRESOLVED case the closer writes the case root's
``stageC/<key>.json`` with decision UNRESOLVED under the stage rules and input configuration,
so Stage D (H6) can read it. Output ``results/funnel/<label>/C_closure_<phase>.json``.
"""
from p12_common import REPO, ROOT, DATA, environment, read, write, sha, utc
environment()
import argparse
import json
import sys
from pathlib import Path


def _closure(phase):
    path = ROOT / 'results/controllers' / phase / 'closure.json'
    if not path.exists():
        return None, None
    closure = read(path)
    if closure['status'] != 'CLOSED' or not closure['all_owned_workers_closed'] or closure.get('pending'):
        raise RuntimeError(f'{phase} did not close cleanly')
    return closure, read(ROOT / 'results/controllers' / phase / 'launch.json')


def _audit_rules():
    for path in (REPO / 'src', REPO / 'scripts'):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    import audit_p5 as A
    from tesshunter.survey import get_config
    A.set_input_config(get_config('survey_p10'))
    A.set_rules('p10.0')
    return A


def close(phase):
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Owner remains')
    closure, launch = _closure(phase)
    if closure is None:
        raise RuntimeError(f'{phase} has no closure')
    retry_closure, retry_launch = _closure(phase + '_retry')
    retry_jobs = {j['job_id']: j for j in (retry_launch or {}).get('frozen_jobs', [])}
    A = _audit_rules()
    rows, counts = [], {}
    for job in launch['frozen_jobs']:
        jid = job['job_id']
        first = read(ROOT / 'results/controllers' / phase / 'attempts' / f'{jid}.json')
        base_runtime = read(REPO / read(REPO / job['arguments'][1])['base_runtime_path'])
        label = read(REPO / job['arguments'][1])['label']
        receipts = [dict(attempt=1, controller_status=first['status'], receipt=job['result_path'])]
        decision = None
        if first['status'] == 'COMPLETE':
            decision = read(REPO / job['result_path'])['decision']
        elif jid in retry_jobs:
            second = read(ROOT / 'results/controllers' / (phase + '_retry') / 'attempts' / f'{jid}.json')
            receipts.append(dict(attempt=2, controller_status=second['status'], receipt=retry_jobs[jid]['result_path']))
            if second['status'] == 'COMPLETE':
                decision = read(REPO / retry_jobs[jid]['result_path'])['decision']
        if decision not in ('PASS', 'FAIL'):
            decision = 'UNRESOLVED'
            cand = base_runtime['candidate']
            key = f"tic{int(base_runtime['tic_id'])}_P{float(cand['period_days']):.4f}"
            record = dict(key=key, tic_id=int(base_runtime['tic_id']), decision='UNRESOLVED', rules_version=A.RULES_VERSION,
                          input_config=A.input_config(), reason='Stage C did not complete within its registered deadline after the one '
                          'recorded retry (12,240 s, then 36,000 s): UNRESOLVED, never a rejection; D runs and H6 caps the verdict at HOLD',
                          attempts=receipts, deadlines_s=[12240, 36000], closed_utc=utc())
            target = REPO / base_runtime['root'] / 'stageC' / f'{key}.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            A.jdump(target, record)
        counts[decision] = counts.get(decision, 0) + 1
        rows.append(dict(job_id=jid, candidate_id=base_runtime['candidate_id'], tic_id=int(base_runtime['tic_id']),
                         decision=decision, attempts=receipts, case_root=base_runtime['root'], label=label))
    labels = sorted({r['label'] for r in rows}) or ['empty']
    result = dict(utc=utc(), phase=phase, retry_phase=phase + '_retry' if retry_closure else None, counts=counts, rows=rows,
                  closure_sha256=sha(ROOT / 'results/controllers' / phase / 'closure.json'),
                  retry_closure_sha256=sha(ROOT / 'results/controllers' / (phase + '_retry') / 'closure.json') if retry_closure else None,
                  rule='C PASS / FAIL from the first completed attempt; not completed after the one retry = UNRESOLVED')
    out = ROOT / f'results/funnel/{labels[0]}/C_closure_{phase}.json'
    write(out, result, replace=out.exists())
    print(json.dumps(dict(phase=phase, counts=counts)), flush=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('phase')
    args = parser.parse_args(argv)
    close(args.phase)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
