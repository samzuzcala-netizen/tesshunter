"""Part 2c: the paired photometry decision ``ADOPT_SML`` or ``KEEP_ARCHIVAL`` (copy of the P10
``compare_injection_variants`` / ``compare_false_alarm_variants`` pattern, registered clauses).

Paired on identical job and host ids; arm A's 2b rows are the baseline. Expected-SNR bins use
arm A's expected SNR (the uninjected archival array). An operational unknown after the retry pass
counts as a miss in B and a recovery in A (the pair-completeness clause). Every clause is required.
"""
from p12_common import REPO, ROOT, read, write, sha, utc
import argparse
import csv
import json
import statistics
from pathlib import Path

import numpy as np

LABEL = {'archival': 'cal_archival', 'sml': 'cal_sml'}


def _csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))


def _decision(receipt):
    if not receipt or receipt.get('status') != 'COMPLETE':
        return 'OPERATIONAL_UNKNOWN'
    m = receipt.get('measurement') or {}
    d = m.get('decision', m.get('gate'))
    return d if d in ('PASS', 'FAIL', 'HOLD') else 'OPERATIONAL_UNKNOWN'


def _stage(label, stage, cid):
    for folder in (f'{stage}_a2', stage):
        path = ROOT / f'results/funnel/{label}/{folder}/{cid}.json'
        if path.exists():
            return read(path)
    return None


def levels(arm):
    """Per injection job: search status, pre-gate, A, S (the funnel through S)."""
    label = LABEL[arm]
    outcomes = {r['job_id']: r for r in _csv(ROOT / f'results/part2/injection_outcomes_{arm}.csv')}
    cases = {c['candidate_id']: c for c in read(ROOT / f'manifests/part2/{label}_cases.json')['cases'] if c['kind'] == 'injection'}
    out = {}
    for jid, row in outcomes.items():
        recovered = row['status'] == 'recovered'
        unknown = row['status'] == 'operational_unknown'
        case = cases.get(jid)
        a = _decision(_stage(label, 'A', jid)) if case else None
        s = _decision(_stage(label, 'S', jid)) if case else None
        through = bool(recovered and case and case['pregate'] and a == 'PASS' and s in ('PASS', 'HOLD'))
        funnel_unknown = bool(recovered and case and (a == 'OPERATIONAL_UNKNOWN' or (a == 'PASS' and s == 'OPERATIONAL_UNKNOWN')))
        out[jid] = dict(tic_id=int(row['tic_id']), snr_expected=float(row['snr_expected']), recovered=recovered,
                        search_unknown=unknown, through_S=through, funnel_unknown=funnel_unknown,
                        wall_s=float(row['wall_s']) if row.get('wall_s') not in (None, '') else None)
    return out


def false_alarms(arm):
    label = LABEL[arm]
    cases = [c for c in read(ROOT / f'manifests/part2/{label}_cases.json')['cases'] if c['kind'] == 'false_alarm']
    s_pass = sum(1 for c in cases if _decision(_stage(label, 'A', c['candidate_id'])) == 'PASS'
                 and _decision(_stage(label, 'S', c['candidate_id'])) in ('PASS', 'HOLD'))
    return dict(pregate_passers=len(cases), S_passers=s_pass)


def paired_gain(a, b, jobs, field, seed=2026092001, draws=10000):
    hosts = sorted({a[j]['tic_id'] for j in jobs})
    index = {h: i for i, h in enumerate(hosts)}
    den, delta = np.zeros(len(hosts)), np.zeros(len(hosts))
    ya = yb = 0
    for j in jobs:
        # Pair completeness (2c): a job unknown in either arm counts a miss in B and a recovery in A.
        unknown = a[j]['search_unknown'] or a[j]['funnel_unknown'] or b[j]['search_unknown'] or b[j]['funnel_unknown']
        va = True if unknown else bool(a[j][field])
        vb = False if unknown else bool(b[j][field])
        den[index[a[j]['tic_id']]] += 1
        delta[index[a[j]['tic_id']]] += int(vb) - int(va)
        ya += va; yb += vb
    n = len(jobs)
    result = dict(n=n, hosts=len(hosts), baseline=int(ya), proposed=int(yb),
                  baseline_rate=ya / n if n else None, proposed_rate=yb / n if n else None,
                  gain_pp=(yb - ya) / n * 100 if n else None, ci95_pp=None)
    if n:
        rng = np.random.Generator(np.random.PCG64(seed))
        w = rng.multinomial(len(hosts), np.full(len(hosts), 1 / len(hosts)), size=draws)
        d, x = w @ den, w @ delta
        good = d > 0
        result['ci95_pp'] = (np.percentile(x[good] / d[good], [2.5, 97.5]) * 100).tolist()
    return result


def median_wall(phase, job_ids=None):
    folder = ROOT / 'results/controllers' / phase / 'attempts'
    walls = [read(p)['wall_seconds'] for p in folder.glob('*.json')
             if read(p)['status'] == 'COMPLETE' and (job_ids is None or p.stem in job_ids)]
    return statistics.median(walls) if walls else None


def unknown_fraction(levels_by_job, jobs):
    unknown = sum(1 for j in jobs if levels_by_job[j]['search_unknown'] or levels_by_job[j]['funnel_unknown'])
    return unknown / len(jobs) if jobs else None


def compare(out):
    config = read(ROOT / 'protocol/config.json')
    bar = config['photometry_bar']
    lo7, hi15 = config['part2']['sml_bin_R_7_15']
    lo15, hi30 = config['part2']['sml_bin_R_15_30']
    a, b = levels('archival'), levels('sml')
    two_b = sorted(j for j in b if j in a)
    in_7_15 = [j for j in two_b if lo7 <= a[j]['snr_expected'] < hi15]
    in_15_30 = [j for j in two_b if lo15 <= a[j]['snr_expected'] < hi30]
    search = paired_gain(a, b, in_7_15, 'recovered')
    funnel = paired_gain(a, b, in_7_15, 'through_S')
    strong = paired_gain(a, b, in_15_30, 'recovered')
    fa_a, fa_b = false_alarms('archival'), false_alarms('sml')
    real_a, real_b = read(ROOT / 'results/part2/retention_archival.json'), read(ROOT / 'results/part2/retention_sml.json')
    ra, rb = real_a['independent_present'], real_b['independent_present']
    wall_a = median_wall('cal_a_search', set(two_b))
    wall_b = median_wall('cal_b_search', set(two_b))
    ratio = wall_b / wall_a if wall_a and wall_b else None
    ua, ub = unknown_fraction(a, two_b), unknown_fraction(b, two_b)
    clauses = {
        'search_gain': dict(metric='R_7_15 search-only exact, B - A (pp)', value=search['gain_pp'], threshold=f">= +{bar['search_gain_pp']}",
                            passed=search['gain_pp'] is not None and search['gain_pp'] >= bar['search_gain_pp'], detail=search),
        'funnel_gain': dict(metric='R_7_15 through pre-gate, A, S, B - A (pp)', value=funnel['gain_pp'], threshold=f">= +{bar['funnel_gain_pp']}",
                            passed=funnel['gain_pp'] is not None and funnel['gain_pp'] >= bar['funnel_gain_pp'], detail=funnel),
        'strong_signals': dict(metric='R_15_30 search-only, B vs A - 2 pp', value=strong['gain_pp'], threshold=f">= -{bar['strong_max_loss_pp']}",
                               passed=strong['gain_pp'] is not None and strong['gain_pp'] >= -bar['strong_max_loss_pp'], detail=strong),
        'false_alarms_pregate': dict(metric='E_cal false-alarm pre-gate passers', value=dict(A=fa_a['pregate_passers'], B=fa_b['pregate_passers']),
                                     threshold=f"B <= {bar['pregate_load_ratio_max']} x A",
                                     passed=fa_b['pregate_passers'] <= bar['pregate_load_ratio_max'] * fa_a['pregate_passers']),
        'false_alarms_S': dict(metric='E_cal false-alarm S passers', value=dict(A=fa_a['S_passers'], B=fa_b['S_passers']),
                               threshold=f"B <= {bar['S_load_ratio_max']} x max(A, {bar['S_load_floor']})",
                               passed=fa_b['S_passers'] <= bar['S_load_ratio_max'] * max(fa_a['S_passers'], bar['S_load_floor'])),
        'real_signals': dict(metric='INDEPENDENT present families recovered on the 436, B - A', value=rb['recovered'] - ra['recovered'],
                             threshold=f">= {bar['real_gain_min']}", passed=rb['recovered'] - ra['recovered'] >= bar['real_gain_min'],
                             detail=dict(A=ra, B=rb)),
        'wall': dict(metric='median job wall of the 2b search jobs, B / A', value=ratio, threshold=f"<= {bar['wall_ratio_max']}",
                     passed=ratio is not None and ratio <= bar['wall_ratio_max'], detail=dict(A_s=wall_a, B_s=wall_b)),
        'pair_completeness': dict(metric='unknowns after the retry pass, per arm', value=dict(A=ua, B=ub),
                                  threshold=f"<= {bar['unknown_fraction_max']:.0%}",
                                  passed=ua is not None and ub is not None and ua <= bar['unknown_fraction_max'] and ub <= bar['unknown_fraction_max']),
    }
    decision = 'ADOPT_SML' if all(c['passed'] for c in clauses.values()) else 'KEEP_ARCHIVAL'
    result = dict(utc=utc(), decision=decision, median_wall_ratio=ratio, clauses=clauses, n_paired_2b=len(two_b),
                  bins=dict(R_7_15=[lo7, hi15], R_15_30=[lo15, hi30], binned_by='arm A expected SNR'),
                  rule='every clause required (PROMPT_P12.md 2c); a failed change is not adopted and not retried with a lower bar',
                  inputs={name: sha(ROOT / name) for name in ('results/part2/injection_outcomes_archival.csv', 'results/part2/injection_outcomes_sml.csv',
                                                               'results/part2/retention_archival.json', 'results/part2/retention_sml.json')})
    out = Path(out) if Path(out).is_absolute() else REPO / out
    write(out, json.loads(json.dumps(result, default=float)), replace=False)
    print(json.dumps(dict(decision=decision, failed=[k for k, c in clauses.items() if not c['passed']])), flush=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('baseline', choices=['archival'])
    parser.add_argument('proposed', choices=['sml'])
    parser.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    compare(args.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
