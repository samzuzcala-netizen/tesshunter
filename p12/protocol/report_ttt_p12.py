"""Part 4b / LB1c scoring of the TESS Ten Thousand negatives, after the prediction lock and the forced route.

``reports_p12.py ttt`` writes ``p12/results/part4/ttt_table.json`` (LB1a end to end, LB1b at D);
``reports_p12.py ttta`` writes ``p12/results/part4/ttta_table.json`` (LB1c, the adjacent domain, reported and
never part of ``bar_met``). The evaluator opens the guarded ephemerides only here, after the lock.

A negative is SUBMIT-equivalent when a candidate on it matching the binary's catalogue period family (exact or
2, 3, 1/2, 1/3 within 1%) ends SUBMIT (tier 1 or 2) under p12.0 with the 4a redaction. End to end: the
candidate also passed S (PASS or HOLD) and B (PASS), the final search's route. At D: under the forced route,
over the negatives whose family candidate reached D. N1 = stars searched COMPLETE; a star with fewer than 3
usable sectors never entered the search and leaves N1.
"""
from p12_common import REPO, ROOT, DATA, read, write, sha, utc, append_jsonl
import json
from pathlib import Path

import plan_part2_p12 as P2
import stats_p12

SETS = {'ttt': dict(manifest='manifests/ttt_negatives.csv', alias='tenk', truth='negatives/truth/ttt_ephemerides.json',
                    out='results/part4/ttt_table.json', clauses=('LB1a', 'LB1b'), threshold_n=20),
        'ttta': dict(manifest='manifests/ttt_adjacent_negatives.csv', alias='tenka', truth='negatives/truth/ttt_adjacent_ephemerides.json',
                     out='results/part4/ttta_table.json', clauses=('LB1c_end_to_end', 'LB1c_at_D'), threshold_n=20)}
RATIOS = (1, 2, 3, 0.5, 1 / 3)
PERIOD_COLUMNS = ('period_days', 'period', 'Per', 'P')


def _periods(record):
    for name in PERIOD_COLUMNS:
        try:
            value = float(record.get(name))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def family(period, binary):
    """The ratio of the binary period family this candidate period sits on (within 1%), else None."""
    for ratio in RATIOS:
        if abs(period / (binary * ratio) - 1) <= 0.01:
            return ratio
    return None


def _d(label, alias, cid, root, key):
    receipt_path = ROOT / f'results/funnel/neg_{alias}_D/D/{cid}.json'
    record_path = REPO / root / 'stageD' / f'{key}.json'
    receipt = read(receipt_path) if receipt_path.exists() else None
    record = read(record_path) if record_path.exists() else {}
    tiers = record.get('tiers') or {}
    return dict(status=(receipt or {}).get('status'), verdict=tiers.get('verdict'), deciding=tiers.get('deciding_condition'),
                candidate_tier=(tiers.get('candidate_tier') or {}).get('candidate_tier'),
                fired=sorted(n for n, c in (tiers.get('conditions') or {}).items() if c.get('fired')),
                not_measurable=tiers.get('not_measurable'), k10=(tiers.get('conditions') or {}).get('K10'),
                f5=(tiers.get('flags') or {}).get('F5'), redacted=record.get('redacted'))


def score(name):
    spec = SETS[name]
    alias = spec['alias']
    label = f'neg_{alias}'
    lock_path = ROOT / f'manifests/neg_{name}_search_predictions_lock.json'
    lock = P2._locked(f'neg_{name}_search')
    cases = read(ROOT / f'manifests/part4/{label}_cases.json')
    closure_path = ROOT / f'results/funnel/{label}/C_closure_neg_{name}_C.json'
    c_rows = {r['candidate_id']: r['decision'] for r in read(closure_path)['rows']} if closure_path.exists() else {}
    truth_path = DATA / spec['truth']
    truth = read(truth_path)['records']
    append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=None, stage=f'Part 4 scoring of the {name} negatives',
        path=truth_path.relative_to(REPO).as_posix(), reader=f'report_ttt_p12.py {name}', prompt_of_origin='TESS Ten Thousand (guarded)',
        content='binary periods read by the evaluator after the prediction lock and the forced route'))
    binaries = {}
    for r in truth:
        p = _periods(r)
        if p:
            binaries.setdefault(int(r['tic_id']), []).append(p)
    targets = [int(r['tic_id']) for r in P2._csv(ROOT / spec['manifest'])]
    searched = {int(j['job_id'].split('_tic')[1]): j for j in lock['jobs']}
    stars, stage_counts = [], dict(accepted=0, pregate=0, A=0, S=0, B=0, C_pass=0, C_unresolved=0, D=0, SUBMIT=0)
    for tic in targets:
        job = searched.get(tic)
        noise = ROOT / f'results/native_noise/archival/tic{tic}.json'
        eligible = noise.exists() and read(noise)['status'] == 'INPUT_ELIGIBLE'
        row = dict(tic_id=tic, eligible=eligible, search=(job or {}).get('status', 'NOT_SEARCHED'),
                   binary_periods=binaries.get(tic, []), candidates=[])
        if job and job['status'] == 'COMPLETE':
            for accepted in job['accepted']:
                stage_counts['accepted'] += 1
                ratio = next((family(accepted['period_days'], b) for b in binaries.get(tic, []) if family(accepted['period_days'], b)), None)
                cid = accepted['candidate_id']
                case = next((c for c in cases['cases'] if c['candidate_id'] == cid), None)
                cand = dict(candidate_id=cid, period_days=accepted['period_days'], family_ratio=ratio, pregate=bool(case))
                if case:
                    stage_counts['pregate'] += 1
                    runtime = read(REPO / case['runtime'])
                    key = f"tic{tic}_P{float(runtime['candidate']['period_days']):.4f}"
                    for stage in ('A', 'S', 'B'):
                        cand[stage] = P2._decision(P2._receipt(label, stage, cid)[0]) if P2._receipt(label, stage, cid)[0] else None
                    cand['C'] = c_rows.get(cid)
                    cand['D'] = _d(label, alias, cid, runtime['root'], key) if cand['C'] in ('PASS', 'UNRESOLVED') else None
                    stage_counts['A'] += cand['A'] == 'PASS'
                    stage_counts['S'] += cand['A'] == 'PASS' and cand['S'] in ('PASS', 'HOLD')
                    stage_counts['B'] += cand['A'] == 'PASS' and cand['S'] in ('PASS', 'HOLD') and cand['B'] == 'PASS'
                    stage_counts['C_pass'] += cand['C'] == 'PASS'
                    stage_counts['C_unresolved'] += cand['C'] == 'UNRESOLVED'
                    reached = bool(cand['D'] and cand['D']['verdict'])
                    stage_counts['D'] += reached
                    submit = reached and cand['D']['verdict'] == 'SUBMIT'
                    stage_counts['SUBMIT'] += submit
                    cand['submit_at_D'] = submit
                    cand['submit_end_to_end'] = bool(submit and cand['S'] in ('PASS', 'HOLD') and cand['B'] == 'PASS')
                row['candidates'].append(cand)
        fam = [c for c in row['candidates'] if c['family_ratio'] is not None]
        row['family_reached_D'] = any(c.get('D') and c['D']['verdict'] for c in fam)
        row['submit_equivalent_end_to_end'] = any(c.get('submit_end_to_end') for c in fam)
        row['submit_equivalent_at_D'] = any(c.get('submit_at_D') for c in fam)
        row['non_family_submits'] = [c['candidate_id'] for c in row['candidates'] if c['family_ratio'] is None and c.get('submit_at_D')]
        stars.append(row)
    n1 = sum(1 for s in stars if s['search'] == 'COMPLETE')
    n1_d = sum(1 for s in stars if s['family_reached_D'])
    e2e = sum(1 for s in stars if s['search'] == 'COMPLETE' and s['submit_equivalent_end_to_end'])
    at_d = sum(1 for s in stars if s['family_reached_D'] and s['submit_equivalent_at_D'])
    first, second = spec['clauses']
    clauses = {first: dict(clause=first, number=e2e, N=n1, wilson95=list(stats_p12.wilson(e2e, n1)), threshold='<= 1 of N1',
                           decisive=n1 >= spec['threshold_n'], holds=(e2e <= 1) if n1 >= spec['threshold_n'] else None),
               second: dict(clause=second, number=at_d, N=n1_d, wilson95=list(stats_p12.wilson(at_d, n1_d)), threshold='<= 1 of N1_D',
                            decisive=n1_d >= 5, holds=(at_d <= 1) if n1_d >= 5 else None)}
    # Wilson intervals are star-level: stars of N1 with at least one candidate reaching the stage (candidate counts apart).
    reach = dict(accepted=lambda c: True, pregate=lambda c: c['pregate'], A=lambda c: c.get('A') == 'PASS',
                 S=lambda c: c.get('A') == 'PASS' and c.get('S') in ('PASS', 'HOLD'),
                 B=lambda c: c.get('A') == 'PASS' and c.get('S') in ('PASS', 'HOLD') and c.get('B') == 'PASS',
                 C_pass=lambda c: c.get('C') == 'PASS', C_unresolved=lambda c: c.get('C') == 'UNRESOLVED',
                 D=lambda c: bool(c.get('D') and c['D']['verdict']), SUBMIT=lambda c: bool(c.get('submit_at_D')))
    complete = [s for s in stars if s['search'] == 'COMPLETE']
    per_stage = {k: stats_p12.rate(sum(1 for s in complete if any(f(c) for c in s['candidates'])), n1) for k, f in reach.items()}
    autopsies = [dict(tic_id=s['tic_id'], candidate_id=c['candidate_id'], family_ratio=c['family_ratio'], **(c['D'] or {}))
                 for s in stars for c in s['candidates'] if c.get('D') and c['D']['verdict']]
    result = dict(utc=utc(), set=name, alias=alias, targets=len(targets), N1=n1, N1_D=n1_d, clauses=clauses, candidate_counts=stage_counts,
                  stars_reaching_of_N1=per_stage, stars=stars, reached_D=autopsies, lock_sha256=sha(lock_path),
                  truth_sha256=sha(truth_path), rule=__doc__.split('\n\n')[1].replace('\n', ' '),
                  scope='adjacent domain (K and late-K dwarfs), not the M-dwarf domain' if name == 'ttta' else 'in-domain M-dwarf binaries')
    result['packets'] = _packets(name, alias)
    write(ROOT / spec['out'], json.loads(json.dumps(result, default=float)), replace=(ROOT / spec['out']).exists())
    print(json.dumps(dict(set=name, N1=n1, end_to_end=e2e, N1_D=n1_d, at_D=at_d)), flush=True)
    return result


def _packets(name, alias):
    """Workers wrote the packets under the alias subtree (``neg_<alias>``); the evaluator copies them to the
    registered ``docs/packets/audit_p12/neg_<set>/`` (7) and records both hashes."""
    import shutil
    source = REPO / f'docs/packets/audit_p12/neg_{alias}'
    target = REPO / f'docs/packets/audit_p12/neg_{name}'
    copied = []
    if source.exists():
        for path in sorted(p for p in source.rglob('*') if p.is_file()):
            destination = target / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copyfile(path, destination)
            copied.append(dict(source=path.relative_to(REPO).as_posix(), destination=destination.relative_to(REPO).as_posix(),
                               sha256=sha(destination), identical=sha(destination) == sha(path)))
    return dict(source=source.relative_to(REPO).as_posix(), target=target.relative_to(REPO).as_posix(), files=copied)


def main(argv):
    score(argv[0] if argv else 'ttt')
    return 0
