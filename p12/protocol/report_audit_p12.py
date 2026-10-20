"""Part 6c: ``docs/AUDIT_P12.md`` (page one as 2a), and ``finalize``: the final state on line 1 (section 8).

``reports_p12.py audit`` writes the document with the state provisionally named from the measured conditions;
``reports_p12.py audit finalize`` (after ``final_shutdown``) evaluates every condition of section 8, including
the final integrity check and the ``DISABLED_VERIFIED`` receipt, and rewrites line 1 of ``docs/AUDIT_P12.md``
and ``HANDOFF_P12.md`` with exactly one state. "Discovered", "found" and "confirmed" are never written about a
pipeline product.
"""
from p12_common import REPO, ROOT, read, write, sha, utc
import csv
import json
import math

AUDIT = REPO / 'docs/AUDIT_P12.md'
HANDOFF = REPO / 'HANDOFF_P12.md'
VALIDATION_SENTENCE = ('The field\'s validation bar (resolved source, localised repeated dimming, low FPP) is out of reach for TESS FFI '
                       'photometry alone at Tmag 13.5; this is a candidate for follow-up, not a validated planet.')
P8_FUNNEL = '13,252 / 3,688 / 189 / 19 / 19 / 6; 0 SUBMIT, 2 HOLD, 4 KILL (docs/AUDIT_P8.md)'
P10_3_FUNNEL = '174 -> 131 -> 37 -> 13 -> 13 (FUNNEL_RETENTION_P10_3.md)'


def _load(rel):
    path = REPO / rel
    return read(path) if path.exists() else None


def _rows():
    path = ROOT / 'results/candidates_p12.csv'
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def conditions():
    """Section 8, measured: every condition of the delivered states and what is missing."""
    out = {}
    freeze = ROOT / 'manifests/freeze_p12_0.json'
    out['freeze_exists'] = freeze.exists()
    if freeze.exists():
        frozen = read(freeze)['utc']
        launches = [read(p)['utc'] for p in (ROOT / 'results/controllers').glob('*/launch.json')
                    if p.parent.name.startswith(('neg_', 'bar_', 'final_'))]
        out['freeze_predates_every_launch'] = all(frozen < t for t in launches)
    bar = _load('p12/results/part4/launch_bar.json')
    out['bar_met'] = (bar or {}).get('bar_met')
    closure = _load('p12/results/controllers/final_search/closure.json')
    out['final_search_closed'] = bool(closure and closure.get('status') == 'CLOSED')
    rows = _rows()
    b_passers = [r for r in rows if r.get('B') == 'PASS']
    out['every_B_passer_has_C'] = all(r.get('C') in ('PASS', 'FAIL', 'UNRESOLVED') for r in b_passers)
    c_cases = [r for r in rows if r.get('C') in ('PASS', 'UNRESOLVED')]
    out['every_C_case_has_D'] = all(r['verdict'].startswith(('SUBMIT', 'HOLD', 'KILL')) for r in c_cases)
    entry = _load('p12/results/integrity_entry/summary.json') or {}
    final = _load('p12/results/integrity_final/summary.json') or {}
    out['integrity_entry_zero'] = entry.get('mismatches', entry.get('n_mismatches')) == 0
    out['integrity_final_zero'] = final.get('mismatches', final.get('n_mismatches')) == 0 if final else None
    supervision = _load('p12/manifests/final_supervision_disabled.json') or {}
    out['routine_disabled_verified'] = supervision.get('status') == 'DISABLED_VERIFIED'
    stops = sorted(p.name for p in (ROOT / 'manifests').glob('stop_*.json'))
    out['stop_receipts'] = stops
    return out


def state(c):
    delivered = all(c.get(k) for k in ('freeze_exists', 'freeze_predates_every_launch', 'final_search_closed', 'every_B_passer_has_C',
                                         'every_C_case_has_D', 'integrity_entry_zero', 'integrity_final_zero', 'routine_disabled_verified'))
    if delivered:
        return 'FINAL_SEARCH_DELIVERED_BAR_MET' if c.get('bar_met') else 'FINAL_SEARCH_DELIVERED_BAR_NOT_MET'
    if c.get('final_search_closed'):
        return 'STOPPED_AFTER_FINAL_SEARCH_INCOMPLETE'
    return 'STOPPED_BEFORE_FINAL_SEARCH'


def _bar_lines(bar):
    lines = ['| clause | number | N | Wilson 95% | decisive | outcome |', '|---|---:|---:|---|---|---|']
    for c in bar['clauses']:
        w = c.get('wilson95') or c.get('wilson95_of_ratio') or [None, None]
        ws = f"{100 * w[0]:.1f}-{100 * w[1]:.1f}%" if w and w[0] is not None else 'n/a'
        number = f"{c['number']:.3f}" if isinstance(c['number'], float) else c['number']
        lines.append(f"| {c['clause']} | {number} | {c['N']} | {ws} | {c['decisive']} | {c['printed']} |")
    return lines


def _next_transits(row, now_btjd):
    """Next-transit windows from the D fit only while the propagated timing error is below half the duration."""
    try:
        p, t0, dur = float(row['fit_period']), float(row['fit_t0_btjd']), float(row['fit_t14_hours']) / 24
        sigma_p, sigma_t0 = float(row['fit_period_err']), float(row['fit_t0_err'])
    except (TypeError, ValueError, KeyError):
        return 'no fitted ephemeris with uncertainties'
    n = math.ceil((now_btjd - t0) / p)
    windows = []
    for k in range(n, n + 3):
        error = math.hypot(sigma_t0, k * sigma_p)
        if error >= dur / 2:
            return '; '.join(windows) or 'timing error exceeds half the duration: no window given'
        windows.append(f'BTJD {t0 + k * p:.3f} +/- {error * 24:.2f} h')
    return '; '.join(windows)


def build(finalize=False):
    c = conditions()
    final_state = state(c)
    bar = _load('p12/results/part4/launch_bar.json')
    rows = _rows()
    ledger = _load('p12/manifests/resource_ledger.json') or {}
    closing = (_load('p12/results/closing_sentence.json') or {}).get('sentence', 'The closing sentence is missing.')
    lines = [f'# AUDIT_P12. Final state: {final_state}' + ('' if finalize else ' (provisional until the final integrity check and shutdown)')]
    if bar and not bar['bar_met']:
        clause = (bar['failing'] or bar['not_decisive'] or ['LB1a'])[0]
        row = next(x for x in bar['clauses'] if x['clause'] == clause)
        lines += [f"Launch bar not met: clause {clause} ({row['printed']}: {row['number']} of {row['N']}).",
                  f"The candidates below were produced under rules whose pre-registered launch bar was not met (clause {clause}: "
                  f"{row['number']} of {row['N']}); submission is not recommended until a decisive, unexposed measurement of that clause exists."]
    lines += ['', f'Generated {utc()} by `p12/protocol/report_audit_p12.py`. Every number is [M] unless marked.', '',
              '## 1. The launch bar', '']
    lines += _bar_lines(bar) if bar else ['Missing: the launch bar was not computed (Part 4 did not close).']
    if bar:
        lines += ['', f"bar_met = {bar['bar_met']}. What N can detect: {bar['what_N_can_detect']}.",
                  f"LB1c (reported, never bar material): {json.dumps({k: v.get('printed') for k, v in (bar.get('adjacent_LB1c') or {}).items() if isinstance(v, dict)})}."]
    submits = [r for r in rows if r['verdict'].startswith('SUBMIT')]
    key = lambda r: -float(r['score_v2'] or 0)
    lines += ['', '## 2. The candidate list', '']
    for tier, title in (('2', 'Tier 2: pixel-supported candidates'), ('1', 'Tier 1: CTOI-grade candidates')):
        chosen = sorted((r for r in submits if r.get('candidate_tier') == tier), key=key)
        lines += [f'### {title}', '']
        if not chosen:
            lines += ['None.', '']
            continue
        lines += ['| TIC | P (d) | epoch (BTJD) | depth (ppt) | duration (h) | tier | deciding | F7 | F5 | score_v2 | packet |',
                  '|---|---:|---:|---:|---:|---|---|---|---|---:|---|']
        for r in chosen:
            lines.append(f"| {r['tic_id']} | {float(r['period_days']):.5f} | {float(r['epoch_btjd']):.4f} | {float(r['depth_ppt']):.3f} | "
                         f"{24 * float(r['duration_days']):.2f} | {r['candidate_tier']} | {r['deciding_condition'] or '-'} | "
                         f"{(r['F7'] or '-')[:60]} | {(r['F5'] or '-')[:40]} | {r['score_v2'] or '-'} | {r['packet'] or '-'} |")
        lines.append('')
    if not submits:
        lines += ['The list is empty: a clean null under the frozen p12.0, stated beside the completeness and specificity statements below.', '']
    holds = [r for r in rows if r['verdict'].startswith('HOLD')]
    unresolved = sum(1 for r in rows if r.get('C') == 'UNRESOLVED')
    unknown = sum(1 for r in rows if r['verdict'] == 'UNKNOWN')
    lines += ['## 3. HOLD (not for submission)', '']
    lines += [f"- TIC {r['tic_id']} P {r['period_days']} d: {r['verdict']} ({r['deciding_condition'] or '-'}); fired {r['fired'] or '-'}" for r in holds] or ['None.']
    lines += ['', f'UNRESOLVED at C (delivered with D): {unresolved}; UNKNOWN: {unknown}.', '', '## 4. Per candidate', '']
    import time
    now_btjd = time.time() / 86400 + 2440587.5 - 2457000.0
    for r in submits:
        lines += [f"### TIC {r['tic_id']} ({r['key']})", '',
                  f"TESS FFI photometry, sectors 56 to 105 under the frozen policy, `survey_p10` preset and rules p12.0: P = {float(r['period_days']):.5f} d, "
                  f"T0 = BTJD {float(r['epoch_btjd']):.4f}, depth {float(r['depth_ppt']):.3f} ppt, duration {24 * float(r['duration_days']):.2f} h. "
                  f"Tier {r['candidate_tier']} ({'pixel-supported' if r['candidate_tier'] == '2' else 'CTOI-grade'}); not claimed: a validated planet, "
                  'a resolved source, a low false-positive probability.', '',
                  ' '.join(f"{k}: {r[k] or '-'}" for k in [f'F{i}' for i in range(1, 11)]), '', VALIDATION_SENTENCE, '',
                  f"Next transits: {_next_transits(r, now_btjd)}.", '']
    comp = ROOT / 'results/COMPLETENESS_P12.md'
    lines += ['## 5. Completeness (short form; full statement in `p12/results/COMPLETENESS_P12.md`)', '']
    if comp.exists():
        lines += [l for l in comp.read_text(encoding='utf-8').splitlines() if l.startswith(('At radius', 'At P in', '**Scope'))]
    lines += ['', '## 6. Specificity', '', 'Survival of independent negatives at B, C and D with N and Wilson bounds: `p12/results/SPECIFICITY_P12.md`.']
    if bar:
        lines.append(f"What N can and cannot detect: {bar['what_N_can_detect']}.")
    lines += ['', '## 7. Cost ledger', '', f"Queue-hours (all parts): {ledger.get('new_queue_hours', 'n/a')}; details in `p12/manifests/resource_ledger.json`.", '',
              '## 8. Next steps for the user', '',
              'Open each packet under `docs/packets/audit_p12/<key>/`, fill `tag`, `candidate_name` and `paper_url` in `ctoi_fields.json`, '
              'and enter the CTOI form by hand if you choose. Nothing was submitted anywhere.', '', closing, '',
              '---', '', '## Audit detail', '', '### Funnel', '']
    counts = {}
    for r in rows:
        counts[r['last_stage']] = counts.get(r['last_stage'], 0) + 1
    natural = _load('p12/results/natural_load_p12.json') or {}
    lines += [f"P12 rows by last stage: {json.dumps(counts)}.", f"Natural load per group: {json.dumps({g: v['totals'] for g, v in natural.get('groups', {}).items()})}.",
              f"P8: {P8_FUNNEL}. P10.3: {P10_3_FUNNEL}.", '', '### S-rejected A passers (S-rejected, not verdicted)', '']
    lines += [f"- TIC {r['tic_id']} P {r['period_days']}" for r in rows if r['verdict'].startswith('REJECT_S')][:200] or ['None.']
    lines += ['', '### The 436 and the P8 B passers with a P12 record', '']
    core = {int(r['tic_id']): r['source_set'] for r in csv.DictReader((ROOT / 'manifests/targets_p12_core.csv').open(encoding='utf-8'))}
    for group in ('p10_436', 'p8_2000'):
        reached = [r for r in rows if core.get(int(r['tic_id'])) == group and r.get('B') == 'PASS']
        lines.append(f"{group}: {len(reached)} B passers in P12: " + ', '.join(f"TIC {r['tic_id']} ({r['verdict']})" for r in reached[:60]))
    lines += ['', '### Part 1 and Part 2 tables', '']
    for rel in ('p12/results/part1/plumbing_d.json', 'p12/results/part1/k10_calibration.json', 'p12/results/part1/tier_rederivation_p12.json',
                'p12/results/part2/photometry_decision.json'):
        t = _load(rel)
        lines.append(f"- `{rel}`: {json.dumps({k: v for k, v in (t or {}).items() if isinstance(v, (str, int, float, bool))})[:400]}")
    lines += ['', '### Unknowns by stage', '', json.dumps({k: sum(1 for r in rows if r.get(k) == 'OPERATIONAL_UNKNOWN') for k in ('A', 'S', 'B')}), '',
              '### Section 8 conditions', '', '```json', json.dumps(c, indent=1), '```', '']
    AUDIT.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    write(ROOT / 'results/final_state.json', dict(utc=utc(), state=final_state, finalized=finalize, conditions=c),
          replace=(ROOT / 'results/final_state.json').exists())
    if finalize and HANDOFF.exists():
        text = HANDOFF.read_text(encoding='utf-8').splitlines()
        text = [f'# HANDOFF_P12. Final state: {final_state}'] + [l for l in text[1:] if not l.lower().startswith('resume here')]
        HANDOFF.write_text('\n'.join(text) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(state=final_state, finalized=finalize, submits=len(submits), holds=len(holds))), flush=True)
    return final_state


def main(argv):
    build(finalize=bool(argv and argv[0] == 'finalize'))
    return 0
