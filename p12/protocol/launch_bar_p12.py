"""Part 4e: the launch bar of 3b, written to ``p12/results/part4/launch_bar.json``.

Clauses: LB1a and LB1b (``ttt_table.json``), LB2a and LB2b (``p9_negatives_table.json``), LB3
(``p9_positives_table.json`` ephemeris-assisted rows) and LB4, computed here: Part 2's per-injection table of the
frozen arm against ``data/survey/p10/part2d/calibration/injection_outcomes_p10.csv`` on the same job ids,
restricted to injections outside the 2b subset on hosts eligible under the frozen policy; the number is
whole-funnel recovery under p12.0 over P10's ``through_funnel_pregated`` recovery of those ids, threshold >= 0.90.
``bar_met`` = LB1a decisive AND every decisive clause holds; a clause that is not decisive is NOT MEASURED and
never counts as a pass. LB1c (``ttta_table.json``) is reported beside the bar and never enters ``bar_met``.
"""
from p12_common import REPO, ROOT, read, write, sha, utc
import csv
import json
from pathlib import Path

import stats_p12

P10_OUTCOMES = REPO / 'data/survey/p10/part2d/calibration/injection_outcomes_p10.csv'
INJ_2B = REPO / 'data/survey/p10/injections_2b.csv'
DETECTS = ('the Wilson 95% upper bound is 11.4% on 0 of 30, 16.7% on 1 of 30, 22.8% on 0 of 13, 43.4% on 0 of 5; '
           'the bar detects a gross specificity failure (one binary in ten passing) and cannot detect a 3% false-SUBMIT rate')


def _csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))


def _truthy(value):
    return str(value).strip().lower() in ('true', '1', 'yes')


def lb4():
    import report_calibration_p12 as R
    decision = read(ROOT / 'results/part2/photometry_decision.json')['decision']
    arm = 'sml' if decision == 'ADOPT_SML' else 'archival'
    inputs = read(ROOT / 'manifests/part2/inputs.json')
    e_cal = set(inputs['injections']['full']['eligible_job_ids'])
    two_b = {r['job_id'] for r in _csv(INJ_2B)}
    ids = sorted(e_cal - two_b)
    if arm == 'archival':
        rows, _ = R.injection_rows('archival')
    else:
        rows, _ = R.injection_rows('sml', ROOT / 'results/part2/injection_outcomes_sml_full.csv',
                                   ROOT / 'manifests/part2/cal_sml_full_cases.json')
    now = {r['job_id']: r for r in rows}
    p10 = {r['job_id']: r for r in _csv(P10_OUTCOMES)}
    common = [j for j in ids if j in p10]
    base = [j for j in common if _truthy(p10[j].get('through_funnel_pregated'))]
    # A P12 operational unknown on a P10 recovery stays in the denominator and is not a recovery.
    ours = [j for j in base if (now.get(j) or {}).get('whole')]
    ratio = len(ours) / len(base) if base else None
    budget = dict(p12=sum(1 for j in common if 'budget' in str((now.get(j) or {}).get('status', ''))),
                  p10=sum(1 for j in common if _truthy(p10[j].get('budget_exhausted', 'False'))))
    return dict(clause='LB4', number=ratio, numerator=len(ours), N=len(base), threshold='>= 0.90', decisive=True,
                holds=(ratio is not None and ratio >= 0.90), arm=arm, job_ids=len(ids), job_ids_in_p10=len(common),
                p12_whole_funnel_all=sum(1 for j in common if (now.get(j) or {}).get('whole')),
                p12_recoveries_not_recovered_in_p10=sum(1 for j in common if (now.get(j) or {}).get('whole') and j not in set(base)),
                wilson95_of_ratio=list(stats_p12.wilson(len(ours), len(base))) if base else [None, None],
                budget_exhausted_per_job=budget,
                note='a no-regression clause across dates on the same job ids (frozen policy against the pre-P11 sector set)')


def _clause(table, name):
    row = dict(table[name])
    row['printed'] = 'NOT MEASURED' if not row.get('decisive') else ('HOLDS' if row.get('holds') else 'FAILS')
    return row


def build():
    ttt = read(ROOT / 'results/part4/ttt_table.json')
    p9n = read(ROOT / 'results/part4/p9_negatives_table.json')
    p9p = read(ROOT / 'results/part4/p9_positives_table.json')
    clauses = [_clause(ttt['clauses'], 'LB1a'), _clause(ttt['clauses'], 'LB1b'), _clause(p9n, 'LB2a'), _clause(p9n, 'LB2b'),
               _clause(p9p['ephemeris_assisted'], 'LB3')]
    four = lb4()
    four['printed'] = 'HOLDS' if four['holds'] else 'FAILS'
    clauses.append(four)
    lb1a = clauses[0]
    bar_met = bool(lb1a['decisive'] and all(c['holds'] for c in clauses if c['decisive']))
    failing = [c['clause'] for c in clauses if c['decisive'] and not c['holds']]
    not_decisive = [c['clause'] for c in clauses if not c['decisive']]
    adjacent = None
    if (ROOT / 'results/part4/ttta_table.json').exists():
        t = read(ROOT / 'results/part4/ttta_table.json')
        adjacent = dict(label='adjacent domain (K and late-K dwarfs), not the M-dwarf domain; reported, never part of bar_met',
                        **{k: _clause(t['clauses'], k) for k in t['clauses']})
    result = dict(utc=utc(), bar_met=bar_met, clauses=clauses, failing=failing, not_decisive=not_decisive,
                  lb1a_decisive=lb1a['decisive'], adjacent_LB1c=adjacent, what_N_can_detect=DETECTS,
                  rule='bar_met = LB1a decisive AND every decisive clause holds; a non-decisive clause is NOT MEASURED',
                  sources={name: sha(ROOT / name) for name in ('results/part4/ttt_table.json', 'results/part4/p9_negatives_table.json',
                                                                'results/part4/p9_positives_table.json')})
    write(ROOT / 'results/part4/launch_bar.json', json.loads(json.dumps(result, default=float)),
          replace=(ROOT / 'results/part4/launch_bar.json').exists())
    print(json.dumps(dict(bar_met=bar_met, failing=failing, not_decisive=not_decisive)), flush=True)
    return result


if __name__ == '__main__':
    build()
