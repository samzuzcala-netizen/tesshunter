"""Plan only unattempted A/S/B prerequisites after an owner closes.

Existing terminal outcomes, including operational unknowns, are immutable and
are never retried here. Search failures require a separate explicit decision.
Run reconcile_operational.py first. Each selected host remains in its original
paired denominator regardless of the measured A decision.
"""
from common import *
import sys


def eligibility(runtime, a):
    m = a.get('measurement', {})
    return a.get('status') == 'COMPLETE' and bool(
        m.get('decision') == 'PASS' or
        runtime.get('engineering_label') and m.get('chosen_ephemeris'))


def required_missing(runtime, records):
    """Pure scheduling rule. A measured unknown is a terminal result."""
    if 'A' not in records:
        return ['A']
    if not eligibility(runtime, records['A']):
        return []
    return [s for s in ('S', 'B') if s not in records]


def main(name):
    if (ROOT/'manifests/controller_owner.json').exists():
        raise RuntimeError('Wait for the active scientific owner to close')
    selection = read(ROOT/'manifests/development_selection.json')
    ids = set()
    missing_searches = []
    for jid in selection['series_ids']:
        search = ROOT/f'results/search/{jid}.json'
        pred = ROOT/f'results/predictions/{jid}.json'
        if not search.exists() or not pred.exists():
            missing_searches.append(jid)
            continue
        ids.update(r['candidate_id'] for r in read(pred)['predictions']
                   if r['passes_pregate'])
    ids.update(r['candidate_id'] for r in read(ROOT/'manifests/control_joins.json')['rows']
               if r.get('candidate_id'))
    jobs = {s: [] for s in ('A', 'S', 'B')}
    retained = []
    for cid in sorted(ids):
        path = ROOT/f'manifests/runtime_funnel/{cid}.json'
        runtime = read(path)
        records = {}
        for s in ('A', 'S', 'B'):
            p = ROOT/f'results/funnel/{s}/{cid}.json'
            if p.exists():
                record = read(p)
                if record['candidate_id'] != cid or record['input_key'] != runtime['input_key']:
                    raise ValueError('Existing prerequisite identity differs: '+cid+' '+s)
                records[s] = record
                retained.append(dict(candidate_id=cid, stage=s,
                    status=record['status'], result_sha256=sha(p)))
        for s in required_missing(runtime, records):
            jobs[s].append(dict(job_id=s+'_'+cid,
                command=['p11/p11_5/protocol/funnel_worker.py',s,path.relative_to(REPO).as_posix()],
                source_paths=sorted(runtime['source_hashes'])))
    for s, rows in jobs.items():
        write(ROOT/f'manifests/{name}_{s}.json', rows)
    write(ROOT/f'results/{name}.json', dict(utc=utc(),
        required_candidates=len(ids), missing_searches=missing_searches,
        unattempted_stage_counts={s:len(rows) for s,rows in jobs.items()},
        immutable_existing_results=retained, existing_terminal_outcomes_retried=False,
        next_action='If needed run A, reconcile and replan. Then S, reconcile and replan, then B. Use only new owner names and the original per-stage deadline. C handoff follows complete terminal prerequisites.'))
    print('Missing searches',len(missing_searches),'unattempted stages',
          {s:len(rows) for s,rows in jobs.items()})
    if missing_searches:
        raise SystemExit(2)


if __name__ == '__main__':
    main(sys.argv[1])
