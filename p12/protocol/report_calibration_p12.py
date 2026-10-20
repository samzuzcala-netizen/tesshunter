"""Part 2a step 6 / 2c: ``COMPLETENESS_ARM_{A,B}.{md,json}`` in the tables of ``COMPLETENESS_P10.md``.

Denominator: every injection on an E_cal host (eligible under the frozen policy); injections on
ineligible hosts are the policy-loss row, never misses. Levels: search only (exact credit),
alias-credited search, search + pre-gate, search + A, search + A + S, the whole funnel (pre-gate,
A, S). SNR50 / SNR90 by the historical two-parameter logistic in ln(SNR)
(``scripts/analyze_completeness.logistic_fit``, 1,000 resamples). False alarms per star per stage
on the E_cal false-alarm stars; C retention on the 30-injection sample. Every number is [M].
"""
from p12_common import REPO, ROOT, read, write, sha, utc
import csv
import json
import sys
from pathlib import Path

import numpy as np

LABEL = {'archival': 'cal_archival', 'sml': 'cal_sml'}
ARM_NAME = {'archival': 'A', 'sml': 'B'}
SNR_EDGES = [0, 5, 7.1, 9, 12, 20, 50, 1e9]
ROT_EDGES = [0.0, 0.5, 1.0, 3.0, 10.0, 1e9, float('inf')]


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


def _logistic(snr, ok):
    for path in (REPO / 'src', REPO / 'scripts'):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from analyze_completeness import logistic_fit
    snr, ok = np.asarray(snr, float), np.asarray(ok, bool)
    valid = np.isfinite(snr) & (snr > 0)
    if valid.sum() < 10 or ok[valid].all() or not ok[valid].any():
        return None
    return logistic_fit(snr[valid], ok[valid])


def injection_rows(arm, outcomes_csv=None, cases_path=None):
    """Per-injection outcome at every level (search, pre-gate, A, S, the whole funnel); LB4 reads these rows."""
    label = LABEL[arm]
    outcomes = _csv(outcomes_csv or ROOT / f'results/part2/injection_outcomes_{arm}.csv')
    cases = read(cases_path or ROOT / f'manifests/part2/{label}_cases.json')
    by_case = {c['candidate_id']: c for c in cases['cases']}
    rows = []
    for r in outcomes:
        jid = r['job_id']
        case = by_case.get(jid)
        a = _decision(_stage(label, 'A', jid)) if case else None
        s = _decision(_stage(label, 'S', jid)) if case else None
        recovered = r['status'] == 'recovered'
        rows.append(dict(job_id=jid, tic_id=int(r['tic_id']), snr=float(r['snr_expected']), period=float(r['period']),
                         rp=float(r['rp_earth']) if r.get('rp_earth') not in (None, '') else None,
                         tmag=float(r['tmag']) if r.get('tmag') not in (None, '') else None,
                         rot=float(r['rot_amp_ppt']) if r.get('rot_amp_ppt') not in (None, '') else None,
                         status=r['status'], recovered=recovered, alias=r['status'] == 'alias',
                         pregate=bool(recovered and case and case['pregate']), A=a, S=s,
                         through_A=bool(recovered and a == 'PASS'),
                         through_S=bool(recovered and a == 'PASS' and s in ('PASS', 'HOLD')),
                         whole=bool(recovered and case and case['pregate'] and a == 'PASS' and s in ('PASS', 'HOLD'))))
    return rows, cases


def build(arm):
    label = LABEL[arm]
    configuration = read(ROOT / 'protocol/config.json')
    inputs = read(ROOT / 'manifests/part2/inputs.json')
    rows, cases = injection_rows(arm)
    n = len(rows)
    snr = [r['snr'] for r in rows]
    level_defs = [('search only', 'recovered'), ('search, alias credited', None), ('search + pre-gate', 'pregate'),
                  ('search + Stage A', 'through_A'), ('search + Stage A + secondary gate', 'through_S'),
                  ('the whole funnel (pre-gate, Stage A, secondary gate)', 'whole')]
    levels = []
    for name, field in level_defs:
        ok = [r['recovered'] or r['alias'] for r in rows] if field is None else [r[field] for r in rows]
        levels.append(dict(level=name, through=int(sum(ok)), n=n, fraction=sum(ok) / n if n else None,
                           logistic=_logistic(snr, ok)))
    spec = inputs['injections']['full' if arm == 'archival' else '2b']
    policy_loss = dict(level='policy loss (INPUT_INELIGIBLE hosts, not misses)', n=len(spec['input_ineligible_job_ids']),
                       of_total=spec['total'])
    scored = {r['job_id'] for r in rows}
    unprepared = sorted(set(spec['eligible_job_ids']) - scored)
    operational = dict(level='operational unknowns (kept in every denominator, never misses)',
                       preparation_or_search_unknown=len(unprepared) + sum(r['status'] == 'operational_unknown' for r in rows),
                       unprepared_job_ids=unprepared)

    def bins(key, edges_list):
        out = []
        for lo, hi in edges_list:
            sub = [r for r in rows if r[key] is not None and lo <= r[key] < hi]
            out.append(dict(bin=[lo, hi], n=len(sub), recovered=sum(r['recovered'] for r in sub),
                            through_S=sum(r['through_S'] for r in sub), whole=sum(r['whole'] for r in sub)))
        return out
    completeness = configuration['completeness']
    tables = dict(expected_snr=bins('snr', list(zip(SNR_EDGES, SNR_EDGES[1:]))),
                  period=bins('period', completeness['period_bins_days']),
                  radius=bins('rp', completeness['radius_bins_re']),
                  tmag=bins('tmag', completeness['tmag_bins']),
                  rotation=bins('rot', list(zip(ROT_EDGES, ROT_EDGES[1:]))))
    fa = [c for c in cases['cases'] if c['kind'] == 'false_alarm']
    n_fa_stars = len(_csv(ROOT / 'manifests/part2/e_cal_hosts.csv'))
    fa_a = [c for c in fa if _decision(_stage(label, 'A', c['candidate_id'])) == 'PASS']
    fa_s = [c for c in fa_a if _decision(_stage(label, 'S', c['candidate_id'])) in ('PASS', 'HOLD')]
    fa_b = [c for c in fa_s if _decision(_stage(label, 'B', c['candidate_id'])) == 'PASS']
    false_alarms = dict(stars=n_fa_stars, accepted=cases['counts']['false_alarm_accepted'], pregate=len(fa), A=len(fa_a),
                        S=len(fa_s), B=len(fa_b), per_star={k: (v / n_fa_stars if n_fa_stars else None) for k, v in
                                                             dict(accepted=cases['counts']['false_alarm_accepted'], pregate=len(fa),
                                                                  A=len(fa_a), S=len(fa_s), B=len(fa_b)).items()},
                        search_unknowns=cases['counts']['unknown'])
    c_path = ROOT / f'results/funnel/{label}/C_closure_{"cal_a_C" if arm == "archival" else "cal_b_full_C"}.json'
    c_retention = read(c_path)['counts'] if c_path.exists() else None
    return dict(utc=utc(), arm=arm, label=label, n_injections=n, n_eligible=len(spec['eligible_job_ids']), levels=levels,
                policy_loss=policy_loss, operational_unknowns=operational, tables=tables,
                false_alarms=false_alarms, C_retention_30_sample=c_retention, rules_version='p12.0 (A, S as p10.0)',
                scope='injection completeness through S; C on the 30-injection sample; no injection runs through D',
                sources={name: sha(ROOT / name) for name in (f'results/part2/injection_outcomes_{arm}.csv',
                                                             f'manifests/part2/{label}_cases.json', 'manifests/part2/inputs.json')})


def markdown(result):
    f = lambda x: 'n/a' if x is None or (isinstance(x, float) and not np.isfinite(x)) else f'{x:.1f}'
    lines = [f"# Completeness, arm {ARM_NAME[result['arm']]} ({result['arm']}) under the frozen input policy", '',
             f"Generated {result['utc']} by `p12/protocol/report_calibration_p12.py`. Every number is [M]. Scope: {result['scope']}.", '',
             '## Recovery at each level', '', '| level | through / injected | fraction | SNR50 (16-84%) | SNR90 (16-84%) |', '|---|---:|---:|---|---|']
    for lv in result['levels']:
        lg = lv['logistic'] or {}
        s50, s90 = lg.get('snr50_16_84') or [None, None], lg.get('snr90_16_84') or [None, None]
        lines.append(f"| {lv['level']} | {lv['through']:,} / {lv['n']:,} | {100 * (lv['fraction'] or 0):.1f}% | "
                     f"{f(lg.get('snr50'))} ({f(s50[0])}-{f(s50[1])}) | {f(lg.get('snr90'))} ({f(s90[0])}-{f(s90[1])}) |")
    pl = result['policy_loss']
    ou = result['operational_unknowns']
    lines += [f"| {pl['level']} | {pl['n']:,} of {pl['of_total']:,} injections | | | |",
              f"| {ou['level']} | {ou['preparation_or_search_unknown']:,} of {result['n_eligible']:,} eligible | | | |", '']
    for name, rows in result['tables'].items():
        lines += [f'### By {name}', '', '| bin | n | search only | through S | whole funnel |', '|---|---:|---:|---:|---:|']
        for r in rows:
            pct = lambda k: f"{k}/{r['n']} ({100 * k / r['n']:.0f}%)" if r['n'] else '0/0'
            lines.append(f"| {r['bin'][0]:g}-{r['bin'][1]:g} | {r['n']} | {pct(r['recovered'])} | {pct(r['through_S'])} | {pct(r['whole'])} |")
        lines.append('')
    fa = result['false_alarms']
    lines += ['## False alarms on the E_cal stars (uninjected arrays)', '', '| stage | count | per star |', '|---|---:|---:|']
    for k in ('accepted', 'pregate', 'A', 'S', 'B'):
        lines.append(f"| {k} | {fa[k]} | {fa['per_star'][k]:.4f} |" if fa['per_star'][k] is not None else f"| {k} | {fa[k]} | n/a |")
    lines += ['', f"Search operational unknowns: {fa['search_unknowns']}.", '',
              f"## Stage C on the 30-injection sample", '', json.dumps(result['C_retention_30_sample']), '']
    return '\n'.join(lines)


def main(argv):
    arm = argv[0]
    result = build(arm)
    name = f'COMPLETENESS_ARM_{ARM_NAME[arm]}'
    write(ROOT / f'results/part2/{name}.json', json.loads(json.dumps(result, default=float)), replace=False)
    (ROOT / f'results/part2/{name}.md').write_text(markdown(result), encoding='utf-8')
    print(json.dumps(dict(arm=arm, n=result['n_injections'], whole=result['levels'][-1]['through'])), flush=True)
    return 0
