"""Part 4e: ``p12/results/SPECIFICITY_P12.md`` (and ``p12/results/part4/fa_natural_table.json``).

Per set and stage, survivors with Wilson intervals; a one-paragraph autopsy of every negative that reached D
(conditions fired, not measurable, F5, K10 values); the 4d natural-load rows in the stop-rule-2 form (a SUBMIT
there is a candidate, flagged ``opened_in_part4``); LB1c as "adjacent domain (K and late-K dwarfs), not the
M-dwarf domain"; and two zero-compute labelled rows: set (i) S kills against SPOC DV secondary statistics in the
P12 sidecar where a TCE exists, and the P8 170 and P10.3 24 S rejections against TESS-EB and VSX in the snapshot.
"""
from p12_common import REPO, ROOT, DATA, read, write, sha, utc, append_jsonl
import csv
import json

import plan_part2_p12 as P2
import stats_p12


def _fmt(rate):
    lo, hi = rate['wilson95'] if rate.get('wilson95') else (None, None)
    if rate['n'] == 0:
        return '0 / 0'
    return f"{rate['k']} / {rate['n']} ({100 * rate['fraction']:.1f}%, Wilson 95% {100 * lo:.1f}-{100 * hi:.1f}%)"


def natural():
    """4d: the E_cal false-alarm A passers through forced C and unredacted D."""
    arm = 'sml' if read(ROOT / 'results/part2/photometry_decision.json')['decision'] == 'ADOPT_SML' else 'archival'
    label = P2.LABEL[arm]
    closure_path = ROOT / f'results/funnel/{label}/C_closure_neg_fa_C.json'
    rows = read(closure_path)['rows'] if closure_path.exists() else []
    out, counts = [], dict(A_passers=len(rows), C_pass=0, C_unresolved=0, D=0, SUBMIT=0, HOLD=0, KILL=0)
    for r in rows:
        counts['C_pass'] += r['decision'] == 'PASS'
        counts['C_unresolved'] += r['decision'] == 'UNRESOLVED'
        receipt = None
        for phase in ('neg_fa_D', 'neg_fa_D_retry'):
            path = ROOT / f'results/funnel/{phase}/D/{r["candidate_id"]}.json'
            if path.exists():
                receipt = read(path)
        verdict = ((receipt or {}).get('verdicts') or {}).get('p12.0', {}) if receipt else {}
        if verdict.get('verdict'):
            counts['D'] += 1
            counts[verdict['verdict']] = counts.get(verdict['verdict'], 0) + 1
        out.append(dict(candidate_id=r['candidate_id'], tic_id=r['tic_id'], C=r['decision'], D=verdict.get('verdict'),
                        deciding=verdict.get('deciding_condition'), candidate_tier=verdict.get('candidate_tier'),
                        opened_in_part4=True))
    n = counts['A_passers']
    table = dict(utc=utc(), arm=arm, counts=counts, rates={k: stats_p12.rate(v, n) for k, v in counts.items() if k != 'A_passers'},
                 rows=out, form='stop-rule-2 form, a natural rate; unlabelled final-population stars: a SUBMIT here is a candidate '
                                'listed with opened_in_part4, and its star\'s Part 5 verdict is the one delivered')
    write(ROOT / 'results/part4/fa_natural_table.json', table, replace=(ROOT / 'results/part4/fa_natural_table.json').exists())
    return table


def _autopsy(row):
    fired = ', '.join(row.get('fired') or []) or 'none'
    missing = ', '.join(row.get('not_measurable') or []) or 'none'
    k10 = row.get('k10') or {}
    return (f"- **TIC {row['tic_id']} {row.get('candidate_id')}** (family ratio {row.get('family_ratio')}): "
            f"verdict {row.get('verdict')} ({row.get('deciding') or 'no condition'}); fired {fired}; not measurable {missing}; "
            f"F5 {json.dumps(row.get('f5'), default=str)[:160]}; K10 {k10.get('fired')} ({str(k10.get('detail'))[:160]})"
            f"{'; catalogue redacted (4a)' if row.get('redacted') else ''}.")


def zero_compute_rows():
    """Two labelled rows computed from records already on disk, no new measurement."""
    rows = []
    ttt = read(ROOT / 'results/part4/ttt_table.json')
    sidecar = read(ROOT / 'manifests/sidecar_p12.json')
    tce = {}
    with (REPO / sidecar['path']).open(newline='', encoding='utf-8-sig') as stream:
        for r in csv.DictReader(stream):
            tce.setdefault(int(r['ticid']), []).append(r)
    s_kills = [(s['tic_id'], c) for s in ttt['stars'] for c in s['candidates'] if c.get('A') == 'PASS' and c.get('S') == 'FAIL']
    with_tce = [(t, c) for t, c in s_kills if t in tce]
    rows.append(dict(row='set (i) S kills against SPOC DV secondary statistics (P12 sidecar)', S_kills=len(s_kills),
                     with_a_TCE=len(with_tce), tce_rows=[dict(tic_id=t, candidate_id=c['candidate_id'],
                     tces=[dict(tceid=r['tceid'], period=r['tce_period'], depth_ppm=r['tce_depth']) for r in tce[t]]) for t, c in with_tce],
                     label='zero-compute, labelled; the sidecar carries no DV secondary statistic column, so the row lists the TCEs matched'))
    append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=None, stage='Part 4e zero-compute row (sidecar vs TTT S kills)',
        path=sidecar['path'], reader='report_specificity_p12.py', prompt_of_origin='P12', content='TCE rows of TTT stars with an S kill'))
    rows.append(dict(row='P8 170 and P10.3 24 S rejections against TESS-EB and VSX in the snapshot',
                     label='zero-compute, labelled; reported from the snapshot hard-stop table and the recorded rejections',
                     source='p12/manifests/hard_stop_p12.json; data/survey/p8/secondary; p10/part3 secondary records'))
    return rows


def build():
    bar = read(ROOT / 'results/part4/launch_bar.json')
    ttt = read(ROOT / 'results/part4/ttt_table.json')
    ttta = read(ROOT / 'results/part4/ttta_table.json') if (ROOT / 'results/part4/ttta_table.json').exists() else None
    p9n = read(ROOT / 'results/part4/p9_negatives_table.json')
    p9p = read(ROOT / 'results/part4/p9_positives_table.json')
    fa = natural()
    lines = ['# SPECIFICITY_P12', '', f"Generated {utc()} by `p12/protocol/report_specificity_p12.py`. Every number is [M]; "
             'nothing in Part 4 changes a rule; a failure is a label.', '', '## The launch bar', '',
             '| clause | measured | N | Wilson 95% | threshold | printed |', '|---|---:|---:|---|---|---|']
    for c in bar['clauses']:
        w = c.get('wilson95') or c.get('wilson95_of_ratio') or [None, None]
        ws = f"{100 * w[0]:.1f}-{100 * w[1]:.1f}%" if w and w[0] is not None else 'n/a'
        lines.append(f"| {c['clause']} | {c['number']} | {c['N']} | {ws} | {c['threshold']} | {c['printed']} |")
    lines += ['', f"bar_met = **{bar['bar_met']}** ({bar['rule']}). What N can detect: {bar['what_N_can_detect']}.", '']
    for title, table in (('Set (i): TESS Ten Thousand binaries, in-domain (LB1a, LB1b)', ttt),
                         ('LB1c: adjacent domain (K and late-K dwarfs), not the M-dwarf domain (reported, never part of bar_met)', ttta)):
        if not table:
            continue
        lines += [f'## {title}', '', f"Targets {table['targets']}; N1 (searched COMPLETE) {table['N1']}; N1_D {table['N1_D']}.", '',
                  '| stage | stars of N1 with a candidate there |', '|---|---|']
        for stage, rate in table['stars_reaching_of_N1'].items():
            lines.append(f"| {stage} | {_fmt(rate)} (candidates: {table['candidate_counts'][stage]}) |")
        lines += ['', '### Autopsies of every candidate that reached D', '']
        lines += [_autopsy(r) for r in table['reached_D']] or ['None reached D.']
        lines.append('')
    lines += ['## Set (iii): the P9 held-out negatives (LB2a, LB2b)', '',
              f"LB2a {p9n['LB2a']['number']} / {p9n['LB2a']['N']} end to end; LB2b {p9n['LB2b']['number']} / {p9n['LB2b']['N']} at D "
              f"({'decisive' if p9n['LB2b']['decisive'] else 'NOT MEASURED'}).", '']
    for r in p9n['rows']:
        for a in r['at_D']:
            lines.append(_autopsy(dict(a, tic_id=r['tic_id'], candidate_id=a.get('key'), deciding=a.get('deciding_condition'))))
    lines += ['', '## The P9 positives', '', f"Blind leg: {p9p['blind']['n_D']} of {p9p['blind']['n_signals']} signals reached D.",
              f"Ephemeris-assisted (LB3; ephemeris-assisted, not a funnel retention): {p9p['ephemeris_assisted']['LB3']['number']} of "
              f"n_fit {p9p['ephemeris_assisted']['n_fit']} KILLed by K6, K8 or K10.", '',
              '## Set (ii): natural load of the E_cal false-alarm stars (reported, not a bar clause)', '',
              f"{fa['form']}.", '', '| stage | of the A passers |', '|---|---|']
    for stage, rate in fa['rates'].items():
        lines.append(f'| {stage} | {_fmt(rate)} |')
    lines += ['', '## Zero-compute labelled rows', '']
    for row in zero_compute_rows():
        lines.append(f"- {row['row']}: {json.dumps({k: v for k, v in row.items() if k not in ('row', 'tce_rows')}, default=str)}")
    (ROOT / 'results/SPECIFICITY_P12.md').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(bar_met=bar['bar_met'], natural_submit=fa['counts'].get('SUBMIT', 0))), flush=True)


def main(argv):
    build()
    return 0
