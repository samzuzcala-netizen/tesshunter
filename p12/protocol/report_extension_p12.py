"""Part 5a: ``p12/results/COMPLETENESS_EXT.{md,json}``, the E1 extension's own calibration.

600 injections on 300 eligible extension stars (``make_injection_spec_p12.py``; 1 to 4 Re, 0.5 to 30 d) and the
same 300 as false-alarm stars, through search, pre-gate, A and S under the frozen p12.0. No admission rule
depends on it: the extension is searched and the statement says what the pipeline can find there.
"""
from p12_common import REPO, ROOT, read, write, sha, utc
import csv
import json
from pathlib import Path

import numpy as np

import plan_part2_p12 as P2
import stats_p12
from report_calibration_p12 import _logistic

LABEL = 'ext_cal'
OUTCOMES = ROOT / 'results/part5/injection_outcomes_ext.csv'


def rows():
    cases = read(ROOT / f'manifests/part5/{LABEL}_cases.json')
    by_case = {c['candidate_id']: c for c in cases['cases']}
    out = []
    with OUTCOMES.open(newline='', encoding='utf-8-sig') as stream:
        for r in csv.DictReader(stream):
            case = by_case.get(r['job_id'])
            a = P2._decision(P2._receipt(LABEL, 'A', r['job_id'])[0]) if case else None
            s = P2._decision(P2._receipt(LABEL, 'S', r['job_id'])[0]) if case else None
            recovered = r['status'] == 'recovered'
            out.append(dict(job_id=r['job_id'], tic_id=int(r['tic_id']), snr=float(r['snr_expected']), period=float(r['period']),
                            rp=float(r['rp_earth']) if r.get('rp_earth') else None, tmag=float(r['tmag']) if r.get('tmag') else None,
                            status=r['status'], recovered=recovered, alias=r['status'] == 'alias',
                            pregate=bool(recovered and case and case['pregate']), through_A=bool(recovered and a == 'PASS'),
                            whole=bool(recovered and case and case['pregate'] and a == 'PASS' and s in ('PASS', 'HOLD'))))
    return out, cases


def build():
    data, cases = rows()
    configuration = read(ROOT / 'protocol/config.json')['completeness']
    n = len(data)
    snr = [r['snr'] for r in data]
    levels = []
    for name, field in (('search only', 'recovered'), ('search + pre-gate', 'pregate'), ('search + Stage A', 'through_A'),
                        ('the whole funnel (pre-gate, Stage A, secondary gate)', 'whole')):
        ok = [r[field] for r in data]
        levels.append(dict(level=name, through=int(sum(ok)), n=n, rate=stats_p12.rate(int(sum(ok)), n), logistic=_logistic(snr, ok)))

    def bins(key, edges):
        return [dict(bin=[lo, hi], **stats_p12.rate(sum(r['whole'] for r in data if r[key] is not None and lo <= r[key] < hi),
                                                    sum(1 for r in data if r[key] is not None and lo <= r[key] < hi)))
                for lo, hi in edges]
    fa = [c for c in cases['cases'] if c['kind'] == 'false_alarm']
    fa_a = [c for c in fa if P2._decision(P2._receipt(LABEL, 'A', c['candidate_id'])[0]) == 'PASS']
    fa_s = [c for c in fa_a if P2._decision(P2._receipt(LABEL, 'S', c['candidate_id'])[0]) in ('PASS', 'HOLD')]
    n_fa = len(P2._csv(ROOT / 'manifests/part5/ext_cal_hosts.csv'))
    result = dict(utc=utc(), population='E1 extension (300 eligible stars by SHA-256 of 20260920:ext_cal:<TIC>)', n_injections=n,
                  levels=levels, by_period=bins('period', configuration['period_bins_days']),
                  by_radius=bins('rp', configuration['radius_bins_re']), by_tmag=bins('tmag', configuration['tmag_bins']),
                  false_alarms=dict(stars=n_fa, accepted=cases['counts']['false_alarm_accepted'], pregate=len(fa), A=len(fa_a), S=len(fa_s),
                                    per_star={k: v / n_fa if n_fa else None for k, v in dict(pregate=len(fa), A=len(fa_a), S=len(fa_s)).items()}),
                  unknowns=cases['counts']['unknown'], scope='through S; no admission rule; stars with no calibration before P12',
                  sources={OUTCOMES.relative_to(REPO).as_posix(): sha(OUTCOMES)})
    write(ROOT / 'results/COMPLETENESS_EXT.json', json.loads(json.dumps(result, default=float)),
          replace=(ROOT / 'results/COMPLETENESS_EXT.json').exists())
    lines = ['# COMPLETENESS_EXT (E1 extension)', '', f"Generated {result['utc']}. Every number is [M]. Scope: {result['scope']}.", '',
             '| level | through / injected | Wilson 95% |', '|---|---:|---|']
    for lv in levels:
        w = lv['rate']['wilson95']
        lines.append(f"| {lv['level']} | {lv['through']} / {n} | {100 * (w[0] or 0):.1f}-{100 * (w[1] or 0):.1f}% |")
    for title, key in (('period (d)', 'by_period'), ('radius (Re)', 'by_radius'), ('Tmag', 'by_tmag')):
        lines += ['', f'### Whole-funnel recovery by {title}', '', '| bin | recovered / n |', '|---|---:|']
        for b in result[key]:
            lines.append(f"| {b['bin'][0]:g}-{b['bin'][1]:g} | {b['k']} / {b['n']} |")
    fa_ = result['false_alarms']
    lines += ['', f"False alarms on the 300 uninjected extension stars: accepted {fa_['accepted']}, pre-gate {fa_['pregate']}, "
              f"A {fa_['A']}, S {fa_['S']}; search unknowns {result['unknowns']}.", '']
    (ROOT / 'results/COMPLETENESS_EXT.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    print(json.dumps(dict(n=n, whole=levels[-1]['through'])), flush=True)
    return result


def main(argv):
    build()
    return 0
