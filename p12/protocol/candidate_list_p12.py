"""Part 5f: ``p12/results/candidates_p12.csv``, every eligible star and every accepted signal of the final search.

Per signal: last stage, stage decisions, verdict (SUBMIT tier 1 or 2, HOLD, KILL with condition, UNRESOLVED,
UNKNOWN, INPUT_INELIGIBLE; ``REJECT_NOVELTY`` is the hard stop's K0 wording in the tiers), ``score_v2`` (the C
scheduling score where computed), F1 to F10, F7, ``population_tier``, ``opened_in_part4`` (a star whose E_cal
false-alarm case reached Part 4d), and the packet path. A star searched COMPLETE with no accepted signal has one
row with ``last_stage`` search. A star whose search stayed unknown after the retry is UNKNOWN.
"""
from p12_common import REPO, ROOT, read, write, sha, utc
import csv
import json

import plan_part2_p12 as P2

LABEL = 'final'
FIELDS = ['tic_id', 'candidate_id', 'key', 'population_tier', 'source_set', 'period_days', 'epoch_btjd', 'duration_days',
          'depth_ppt', 'stitch_snr', 'fit_period', 'fit_period_err', 'fit_t0_btjd', 'fit_t0_err', 'fit_t14_hours', 'fit_depth_ppt', 'last_stage', 'pregate', 'A', 'S', 'B', 'C', 'verdict', 'deciding_condition',
          'candidate_tier', 'validation_status', 'fired', 'not_measurable', 'score_v2'] + [f'F{i}' for i in range(1, 11)] + [
          'opened_in_part4', 'packet', 'budget_exhausted']


def _flags(tiers):
    flags = tiers.get('flags') or {}
    return {f'F{i}': json.dumps(flags.get(f'F{i}'), default=str) if flags.get(f'F{i}') is not None else '' for i in range(1, 11)}


def build():
    lock = read(ROOT / 'manifests/final_predictions_lock.json')
    cases = {c['candidate_id']: c for c in read(ROOT / 'manifests/part5/final_cases.json')['cases']}
    core = {int(r['tic_id']): r for r in P2._csv(ROOT / 'manifests/targets_p12_core.csv')}
    eligibility = read(ROOT / 'manifests/eligibility_p12.json')['per_star']
    c_path = ROOT / f'results/funnel/{LABEL}/C_closure_final_C.json'
    c_rows = {r['candidate_id']: r['decision'] for r in read(c_path)['rows']} if c_path.exists() else {}
    order_path = ROOT / 'manifests/part5/final_C_order.json'
    scores = read(order_path)['score_v2'] if order_path.exists() else {}
    natural = set()
    fa_d = ROOT / 'results/funnel/cal_archival/C_closure_neg_fa_C.json'
    if fa_d.exists():
        natural = {int(r['tic_id']) for r in read(fa_d)['rows']}
    rows = []
    searched = set()
    for job in lock['jobs']:
        tic = int(job.get('tic_id') or job['job_id'][3:])
        searched.add(tic)
        tier = 'core' if tic in core else 'E1'
        base = dict(tic_id=tic, population_tier=tier, source_set=(core.get(tic) or {}).get('source_set', 'E1'),
                    opened_in_part4=tic in natural)
        if job['status'] != 'COMPLETE':
            rows.append(dict(base, last_stage='search', verdict='UNKNOWN'))
            continue
        if not job['accepted']:
            rows.append(dict(base, last_stage='search', verdict='NO_ACCEPTED_SIGNAL'))
            continue
        for acc in job['accepted']:
            cid = acc['candidate_id']
            key = f"tic{tic}_P{float(acc['period_days']):.4f}"
            row = dict(base, candidate_id=cid, key=key, period_days=acc['period_days'], epoch_btjd=acc['epoch_btjd'],
                       duration_days=acc['duration_days'], depth_ppt=acc['depth_ppt'], stitch_snr=acc.get('stitch_snr'),
                       budget_exhausted=acc.get('partition_budget_exhausted'), pregate=cid in cases)
            if cid not in cases:
                rows.append(dict(row, last_stage='pregate', verdict='REJECT_PREGATE'))
                continue
            runtime = read(REPO / cases[cid]['runtime'])
            decisions = {}
            for stage in ('A', 'S', 'B'):
                receipt, _ = P2._receipt(LABEL, stage, cid)
                decisions[stage] = P2._decision(receipt) if receipt else None
            decisions['C'] = c_rows.get(cid)
            row.update(decisions, score_v2=scores.get(cid))
            last, verdict = 'A', None
            if decisions['A'] != 'PASS':
                verdict = 'UNKNOWN' if decisions['A'] in (None, 'OPERATIONAL_UNKNOWN') else 'REJECT_A'
            elif decisions['S'] not in ('PASS', 'HOLD'):
                last, verdict = 'S', 'UNKNOWN' if decisions['S'] in (None, 'OPERATIONAL_UNKNOWN') else 'REJECT_S (S-rejected, not verdicted)'
            elif decisions['B'] != 'PASS':
                last, verdict = 'B', 'UNKNOWN' if decisions['B'] in (None, 'OPERATIONAL_UNKNOWN') else 'REJECT_B'
            elif decisions['C'] not in ('PASS', 'UNRESOLVED'):
                last, verdict = 'C', 'UNKNOWN' if decisions['C'] is None else 'REJECT_C'
            else:
                last = 'D'
                # Attempt 1's receipt, unless it is not COMPLETE and the one recorded retry completed.
                receipt = None
                for phase in ('final_D', 'final_D_retry'):
                    path = ROOT / f'results/funnel/{phase}/D/{cid}.json'
                    if path.exists() and (receipt is None or receipt.get('status') != 'COMPLETE'):
                        receipt = read(path)
                record_path = REPO / runtime['root'] / 'stageD' / f'{key}.json'
                record = read(record_path) if record_path.exists() else {}
                tiers = record.get('tiers') or {}
                adopted = (record.get('fit') or {}).get('adopted') or {}
                row.update(fit_period=adopted.get('period'), fit_period_err=adopted.get('period_err'), fit_t0_btjd=adopted.get('t0_btjd'),
                           fit_t0_err=adopted.get('t0_err'), fit_t14_hours=adopted.get('t14_hours'),
                           fit_depth_ppt=adopted.get('depth_avg_ppt', adopted.get('depth_ppt')))
                if receipt and receipt.get('status') == 'COMPLETE' and tiers.get('verdict'):
                    verdict = tiers['verdict']
                    tier = (tiers.get('candidate_tier') or {}).get('candidate_tier')
                    row.update(deciding_condition=tiers.get('deciding_condition'), candidate_tier=tier,
                               validation_status=tiers.get('validation_status'),
                               fired='|'.join(sorted(n for n, c in (tiers.get('conditions') or {}).items() if c.get('fired'))),
                               not_measurable='|'.join(tiers.get('not_measurable') or []), packet=receipt.get('packet'),
                               **_flags(tiers))
                    if verdict == 'SUBMIT' and tier:
                        verdict = f'SUBMIT tier {tier}'
                else:
                    verdict = 'HOLD H3 (D measurement did not run after its retry)'
            rows.append(dict(row, last_stage=last, verdict=verdict))
    for tic, e in eligibility.items():
        if int(tic) not in searched and e.get('status') == 'INPUT_INELIGIBLE':
            rows.append(dict(tic_id=int(tic), population_tier='core', source_set=(core.get(int(tic)) or {}).get('source_set'),
                             last_stage='input', verdict='INPUT_INELIGIBLE'))
    path = ROOT / 'results/candidates_p12.csv'
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator='\n', extrasaction='ignore')
        writer.writeheader()
        for r in sorted(rows, key=lambda r: (r['tic_id'], str(r.get('candidate_id') or ''))):
            writer.writerow({k: ('' if r.get(k) is None else r.get(k)) for k in FIELDS})
    summary = {}
    for r in rows:
        summary[r['verdict'].split(' (')[0]] = summary.get(r['verdict'].split(' (')[0], 0) + 1
    write(ROOT / 'results/candidates_p12_summary.json', dict(utc=utc(), rows=len(rows), by_verdict=summary, csv_sha256=sha(path)),
          replace=(ROOT / 'results/candidates_p12_summary.json').exists())
    print(json.dumps(summary), flush=True)
    return rows


if __name__ == '__main__':
    build()
