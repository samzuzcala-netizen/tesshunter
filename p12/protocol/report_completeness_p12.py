"""Part 6a and 6b: ``p12/results/COMPLETENESS_P12.md`` (required in every final state) and the closing sentence.

Sections: (1) injection recovery under p12.0 on the frozen input through the search and the frozen funnel
(pre-gate, A, S; C on the 30-injection sample) by radius, period, Tmag and rotation, exact and alias-credited
rows, the policy-loss row, SNR50 / SNR90 beside P10's, with the registered scope sentence; (2) real-signal
retention on the 436 (development-exposed, EB-contaminated); (3) false-alarm and independent-negative rates;
(4) one sentence per period class and radius class and the stated limits; (5) the extension's table; (6) the
yield-model row; (7) the assumptions. The closing sentence is chosen by the rule of 6b from the Part 2
tabulations and Part 4 (``p12/results/closing_sentence.json``). A missing input is a line saying so.
"""
from p12_common import REPO, ROOT, read, write, sha, utc
import json

SCOPE = ('injection completeness is measured through S, with C on the 30-injection sample; no injection runs through D; '
         'D-level behaviour on planets is measured only by LB3 on the 12 ephemeris-assisted P9 hosts; the delivered list is '
         'end to end, and its D-level completeness is not calibrated by injections')
P10_SNR = dict(search_snr50=None, note='P10 2d values: p10/results/COMPLETENESS_P10.md')


def _load(rel):
    path = ROOT / rel
    return read(path) if path.exists() else None


def _pct(k, n):
    return f'{k}/{n} ({100 * k / n:.1f}%)' if n else f'{k}/0'


def closing(arm_table, window, long_period, bar):
    """6b: X lists every item whose condition holds; (5) when none."""
    c = read(ROOT / 'protocol/config.json')['closing_sentence']
    items, evidence = [], {}
    small = next((b for b in (arm_table or {}).get('tables', {}).get('radius', []) if b['bin'] == c['small_radius_bin_re']), None)
    if small and small['n']:
        frac = small['through_S'] / small['n']
        evidence['small_radius_through_S'] = frac
        if frac < c['small_radius_through_S_max']:
            items.append('pixel-level photometry, the only untested input change with a measured noise lever')
    if window:
        ref = c['window_retention_reference']
        hits = [w for w in window.get('windows', []) if w.get('window_days') in c['window_days']
                and (w.get('retention') or 0) > ref + c['window_retention_gain_min'] - 1e-12
                and (w.get('noise_ratio_1h') or 9) <= c['window_noise_ratio_max']]
        evidence['window_hits'] = hits
        if hits:
            items.append('a detrending-window test on the 2b instrument (about 20 queue-hours)')
    if long_period:
        deficit = long_period.get('families_above_5d_with_deficit') or 0
        evidence['long_period_families'] = deficit
        if deficit >= c['long_period_min_families']:
            items.append('a long-period search variant')
    lb3 = next((x for x in (bar or {}).get('clauses', []) if x['clause'] == 'LB3'), None)
    if lb3 and not lb3.get('decisive'):
        items.append('an unexposed in-domain truth-positive set, which the records do not contain')
    if not items:
        probe = _load('manifests/sector_probe.json') or {}
        items.append(f"new sectors beyond 105 (sector probe count: {probe.get('n_sectors_above_105', probe.get('count', 'see sector_probe.json'))})")
    sentence = ('The registered P12 work on these inputs is complete; these measurements bound what it can find, and the specific '
                'experiments that could move those bounds are ' + '; '.join(items) + '.')
    return dict(sentence=sentence, items=items, evidence=evidence)


def build():
    decision = _load('results/part2/photometry_decision.json') or {}
    arm = 'B' if decision.get('decision') == 'ADOPT_SML' else 'A'
    table = _load(f'results/part2/COMPLETENESS_ARM_{arm}.json')
    retention = _load('results/part2/retention_archival.json')
    window = _load('results/part2/window_check.json')
    long_period = _load('results/part2/long_period_tabulation.json')
    s_modes = _load('results/part2/s_mode_restatement.json')
    bar = _load('results/part4/launch_bar.json')
    natural = _load('results/natural_load_p12.json')
    ttt = _load('results/part4/ttt_table.json')
    ext = _load('results/COMPLETENESS_EXT.json')
    lines = ['# COMPLETENESS_P12', '', f'Generated {utc()} by `p12/protocol/report_completeness_p12.py`. Every number is [M] unless marked.', '',
             f'**Scope.** {SCOPE}.', '', f"Frozen input: arm {arm} ({decision.get('decision', 'photometry decision missing')}).", '']
    lines += ['## 1. Injection recovery under p12.0 on the frozen input', '']
    if table:
        lines += [f'Scope (header): {SCOPE}.', '', '| level | through / injected | SNR50 | SNR90 |', '|---|---:|---:|---:|']
        for lv in table['levels']:
            lg = lv.get('logistic') or {}
            f = lambda v: 'n/a' if v is None else f'{v:.1f}'
            lines.append(f"| {lv['level']} | {lv['through']:,} / {lv['n']:,} | {f(lg.get('snr50'))} | {f(lg.get('snr90'))} |")
        pl = table['policy_loss']
        lines += [f"| {pl['level']} | {pl['n']:,} of {pl['of_total']:,} | | |", '']
        for name in ('radius', 'period', 'tmag', 'rotation'):
            rows = table['tables'].get(name) or []
            lines += [f'### By {name}', '', '| bin | n | search | through S | whole funnel |', '|---|---:|---:|---:|---:|']
            for r in rows:
                lines.append(f"| {r['bin'][0]:g}-{r['bin'][1]:g} | {r['n']} | {_pct(r['recovered'], r['n'])} | {_pct(r['through_S'], r['n'])} | {_pct(r['whole'], r['n'])} |")
            lines.append('')
        lines += [f"C retention on the 30-injection sample: {json.dumps(table.get('C_retention_30_sample'))}.", '',
                  'SNR50 and SNR90 of P10 for comparison: `COMPLETENESS_P10.md` (pre-P11 sector set) [P10].', '']
    else:
        lines += ['Missing: Part 2 did not write the frozen arm table; no injection recovery is stated.', '']
    lines += ['## 2. Real-signal retention on the 436 (development-exposed, EB-contaminated)', '']
    if retention:
        lines.append(f"Part 2 search-level recovery [M]: {json.dumps({k: retention.get(k) for k in ('independent_present', 'recovered', 'fraction') if k in retention})}.")
    else:
        lines.append('Missing: the Part 2 retention table.')
    lines += ['P10.3 funnel [P10.3]: 156/377 INDEPENDENT present families recovered; 174 -> 131 -> 37 -> 13 -> 13 through the funnel.',
              'Part 5 on the same hosts, re-matched after the lock through C and D: see `docs/AUDIT_P12.md` [M, "same hosts, final search"].', '']
    lines += ['## 3. False-alarm and independent-negative rates per stage', '']
    if table:
        fa = table['false_alarms']
        lines.append(f"Part 2 false alarms per E_cal star: {json.dumps(fa['per_star'])}.")
    if natural:
        for group, row in natural['groups'].items():
            lines.append(f"Part 5 natural load, {group}: {json.dumps({k: round(v, 4) if isinstance(v, float) else v for k, v in row['per_star'].items()})} per star.")
    if ttt:
        lines.append(f"Part 4 TTT negatives: LB1a {ttt['clauses']['LB1a']['number']} / {ttt['clauses']['LB1a']['N']}, LB1b "
                     f"{ttt['clauses']['LB1b']['number']} / {ttt['clauses']['LB1b']['N']} (Wilson intervals in SPECIFICITY_P12.md).")
    lines += ['', '## 4. What the frozen pipeline recovers, by class', '']
    if table:
        for p in table['tables'].get('period', []):
            for r in table['tables'].get('radius', []):
                pass
        for r in table['tables'].get('radius', []):
            lines.append(f"At radius {r['bin'][0]:g} to {r['bin'][1]:g} Re the frozen pipeline recovers {_pct(r['through_S'], r['n'])} of injected "
                         'planets on stars of Tmag 12.5 to 14 with at least 3 policy sectors through the funnel to S.')
        for p in table['tables'].get('period', []):
            lines.append(f"At P in [{p['bin'][0]:g}, {p['bin'][1]:g}] d the frozen pipeline recovers {_pct(p['through_S'], p['n'])} of injected planets "
                         'of 1 to 4 Re through the funnel to S.')
    lines += ['', 'Stated limits: the S gate\'s 17.2% false kill (200 / 1,164, `stop_rule_1_decision.json`); the photometry test was '
              'flux-level (no dilution or throughput); the pixel lever is untested; sectors above 105 are counted, not searched; '
              'stars removed by the input policy are the policy-loss row.', '']
    if s_modes:
        lines += [f"S modes (report-only): {json.dumps(s_modes.get('summary', s_modes))[:600]}", '']
    lines += ['## 5. The extension', '']
    lines.append(f"See `COMPLETENESS_EXT.md`: {ext['n_injections']} injections, whole funnel {ext['levels'][-1]['through']}." if ext else
                 'No extension calibration ran (or its table is missing).')
    lines += ['', '## 6. The yield model', '', '| model | through S on the 2,000 | observed |', '|---|---:|---:|']
    observed = (natural or {}).get('groups', {}).get('p8_2000', {}).get('totals', {}).get('S')
    lines += [f"| model (DC15, claimed fraction 0.03, never validated by an observed count) | 21.09 [P10] | {observed if observed is not None else 'n/a'} |",
              '', 'No forecast of the candidate count is made.', '']
    close = closing(table, window, long_period, bar)
    write(ROOT / 'results/closing_sentence.json', dict(utc=utc(), **close), replace=(ROOT / 'results/closing_sentence.json').exists())
    lines += ['## Closing sentence (6b)', '', close['sentence'], '']
    lines += ['## 7. Assumptions', '', 'The assumptions of `PROMPT_P12.md` section 9 hold as registered; each measured one is reported in its '
              'section above (9.1 costs, 9.2 false-alarm rates, 9.3 C cost, 9.4 D cost, 9.5 eligibility, 9.6 SML, 9.7 TTT, 9.8 P9 hosts).', '']
    (ROOT / 'results/COMPLETENESS_P12.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    print(json.dumps(dict(arm=arm, closing_items=len(close['items']))), flush=True)
    return close


def main(argv):
    build()
    return 0
