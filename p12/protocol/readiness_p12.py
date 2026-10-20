"""The freeze-readiness gate (Part 3, before ``freeze``): every module a later phase runs exists and is sealed.

The freeze hashes every ``p12/protocol/*.py`` and, from then on, no source may change (a mismatch is STOP-1).
So before it is written, every script, planner and worker that a phase after the freeze names must exist
under ``p12/`` and be sealed by the registration chain, the held-out harness must be installed, and no
draft may remain only in ``p12/work/dev``. Output ``p12/manifests/freeze_readiness.json``; exit 3 (an OPEN
item, which the continuation reports as a pause) when anything is missing.
"""
from p12_common import REPO, ROOT, read, write, sha, utc
import json
import sys

HARNESS = ('common.py', 'runner.py', 'dispatch.py', 'prepare.py', 'scoring.py', 'metrics.py', 'p9_scoring_adapter.py')


def _named(phase):
    names = []
    for field in ('script',):
        if phase.get(field):
            names.append(phase[field])
    if phase.get('planner'):
        names.append(phase['planner']['script'])
    for value in (phase.get('args') or []) + ((phase.get('planner') or {}).get('args') or []):
        if isinstance(value, str) and value.endswith('.py') and '/' in value:
            names.append(value)
    return names


def check():
    from register_p12 import effective, verify
    verify()
    hashes, python, problems, _ = effective()
    sequence = read(ROOT / 'manifests/phase_sequence.json')['phases']
    names = [p['name'] for p in sequence]
    after = sequence[names.index('freeze'):]
    missing, unsealed, workers = [], [], set()
    for phase in after:
        for name in _named(phase):
            path = REPO / name
            if not path.is_file():
                missing.append(dict(phase=phase['name'], file=name))
            elif name.startswith('p12/') and name not in hashes:
                unsealed.append(dict(phase=phase['name'], file=name))
    for name in HARNESS:
        rel = f'p12/heldout/{name}'
        if not (REPO / rel).is_file():
            missing.append(dict(phase='harness', file=rel))
        elif rel not in hashes:
            unsealed.append(dict(phase='harness', file=rel))
    for worker in ('stage_d_worker_p12.py', 'funnel_stage_p12.py', 'stage_c_worker_p12.py', 'blind_search_worker_p12.py',
                   'neighbours_worker_p12.py', 'download_star_p12.py', 'verify_prepare_p12.py'):
        rel = f'p12/protocol/{worker}'
        workers.add(rel)
        if rel not in hashes:
            unsealed.append(dict(phase='worker', file=rel))
    drafts = sorted(p.relative_to(REPO).as_posix() for p in (ROOT / 'work/dev').rglob('*.py')) if (ROOT / 'work/dev').exists() else []
    pending = [d for d in drafts if not (ROOT / 'protocol' / d.split('/')[-1]).exists()
               and not (ROOT / 'heldout' / d.split('/')[-1]).exists()]
    status = 'READY' if not (missing or unsealed or pending or problems) else 'OPEN'
    result = dict(utc=utc(), status=status, phases_checked=len(after), missing=missing, unsealed=unsealed,
                  drafts_not_installed=pending, chain_problems=problems, workers=sorted(workers),
                  rule='every module a phase after the freeze runs exists and is sealed before freeze_p12_0.json is written')
    write(ROOT / 'manifests/freeze_readiness.json', result, replace=(ROOT / 'manifests/freeze_readiness.json').exists())
    print(json.dumps(dict(status=status, missing=len(missing), unsealed=len(unsealed), drafts=len(pending))), flush=True)
    return 0 if status == 'READY' else 3


if __name__ == '__main__':
    raise SystemExit(check())
