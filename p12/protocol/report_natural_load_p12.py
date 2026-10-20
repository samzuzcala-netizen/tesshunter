"""Part 5f: ``p12/results/natural_load_p12.json``, per-star counts at every stage of the final search.

Groups: the 2,000-origin stars (``source_set`` p8_2000), the 436 TCE hosts (p10_436) apart, and E1 when it ran.
Beside them the P10 false-alarm rates (accepted 11.65, pre-gate 2.363, A 0.150, S 0.0067 per star) and the
P10.3 rates on the 436 (9.93, 2.53, 0.672, 0.067, 0.011). Every star searched COMPLETE is in the denominator;
unknowns are listed per stage. The S row counts S on A passers only (the seeded 10% of A failures is its own row).
"""
from p12_common import REPO, ROOT, read, write, sha, utc
import json

import plan_part2_p12 as P2
import stats_p12

P10_FA = dict(accepted=11.65, pregate=2.363, A=0.150, S=0.0067)
P10_3 = dict(accepted=9.93, pregate=2.53, A=0.672, S=0.067, B=0.011)
LABEL = 'final'


def build():
    lock = read(ROOT / 'manifests/final_predictions_lock.json')
    cases = read(ROOT / 'manifests/part5/final_cases.json')['cases']
    # Core stars carry their source set; every other searched star is an E1 extension star.
    groups = {int(r['tic_id']): r['source_set'] for r in P2._csv(ROOT / 'manifests/targets_p12_core.csv')}
    c_path = ROOT / f'results/funnel/{LABEL}/C_closure_final_C.json'
    c_rows = {r['candidate_id']: r['decision'] for r in read(c_path)['rows']} if c_path.exists() else {}
    stars = {}
    for job in lock['jobs']:
        tic = int(job['job_id'][3:]) if job['job_id'].startswith('tic') else int(job.get('tic_id') or 0)
        group = groups.get(tic, 'E1')
        stars[tic] = dict(group=group, status=job['status'], accepted=len(job['accepted']) if job['status'] == 'COMPLETE' else None)
    counts = {}
    for case in cases:
        tic = int(case['tic_id'])
        cid = case['candidate_id']
        a = P2._decision(P2._receipt(LABEL, 'A', cid)[0])
        s = P2._decision(P2._receipt(LABEL, 'S', cid)[0]) if P2._receipt(LABEL, 'S', cid)[0] else None
        b = P2._decision(P2._receipt(LABEL, 'B', cid)[0]) if P2._receipt(LABEL, 'B', cid)[0] else None
        c = c_rows.get(cid)
        d = read(ROOT / f'results/funnel/final_D/D/{cid}.json') if (ROOT / f'results/funnel/final_D/D/{cid}.json').exists() else None
        row = counts.setdefault(tic, dict(pregate=0, A=0, A_unknown=0, S=0, S_on_A_fail_sample=0, B=0, C_pass=0, C_unresolved=0,
                                          D=0, SUBMIT=0, HOLD=0, KILL=0))
        row['pregate'] += 1
        row['A'] += a == 'PASS'
        row['A_unknown'] += a == 'OPERATIONAL_UNKNOWN'
        if a == 'PASS':
            row['S'] += s in ('PASS', 'HOLD')
            row['B'] += s in ('PASS', 'HOLD') and b == 'PASS'
        elif s is not None:
            row['S_on_A_fail_sample'] += s in ('PASS', 'HOLD')
        row['C_pass'] += c == 'PASS'
        row['C_unresolved'] += c == 'UNRESOLVED'
        if d and d.get('status') == 'COMPLETE':
            verdict = (d.get('verdicts') or {}).get('p12.0', {}).get('verdict')
            row['D'] += 1
            if verdict in ('SUBMIT', 'HOLD', 'KILL'):
                row[verdict] += 1
    table = {}
    for group in ('p8_2000', 'p10_436', 'E1'):
        members = [t for t, s in stars.items() if s['group'] == group]
        complete = [t for t in members if stars[t]['status'] == 'COMPLETE']
        if not members:
            continue
        n = len(complete)
        totals = dict(accepted=sum(stars[t]['accepted'] or 0 for t in complete))
        for key in ('pregate', 'A', 'A_unknown', 'S', 'S_on_A_fail_sample', 'B', 'C_pass', 'C_unresolved', 'D', 'SUBMIT', 'HOLD', 'KILL'):
            totals[key] = sum(counts.get(t, {}).get(key, 0) for t in complete)
        table[group] = dict(stars=len(members), searched_complete=n, unknown=len(members) - n, totals=totals,
                            per_star={k: (v / n if n else None) for k, v in totals.items()},
                            stars_with_any={k: stats_p12.rate(sum(1 for t in complete if counts.get(t, {}).get(k, 0)), n)
                                            for k in ('pregate', 'A', 'S', 'B', 'C_pass', 'D')})
    result = dict(utc=utc(), groups=table, p10_false_alarm_rates_per_star=P10_FA, p10_3_rates_per_star_436=P10_3,
                  lock_sha256=sha(ROOT / 'manifests/final_predictions_lock.json'),
                  note='the 436 are development-exposed TCE hosts; their rates are reported apart from the 2,000-origin stars')
    write(ROOT / 'results/natural_load_p12.json', json.loads(json.dumps(result, default=float)),
          replace=(ROOT / 'results/natural_load_p12.json').exists())
    print(json.dumps({g: v['per_star'] for g, v in table.items()}, default=float)[:600], flush=True)
    return result


def main(argv):
    build()
    return 0
