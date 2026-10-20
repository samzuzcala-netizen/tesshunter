"""Part 0 timing and decision-point reporting from aggregate receipts only."""
from p12_common import REPO, ROOT, read, write, sha, utc
from ledger_p12 import queue_seconds_per_job
import argparse
import csv
import json
import math


def closed_attempts(phase, workers):
    folder = ROOT / 'results/controllers' / phase
    closure = read(folder / 'closure.json')
    launch = read(folder / 'launch.json')
    if (closure['status'] != 'CLOSED' or not closure['all_owned_workers_closed']
            or not closure['source_hashes_unchanged'] or closure.get('pending', 0)
            or closure.get('recovery')):
        raise RuntimeError('Phase is not closed: ' + phase)
    if launch['workers'] != workers:
        raise RuntimeError('Pilot production width differs from 24')
    jobs = launch['frozen_jobs']
    rows = [read(folder / 'attempts' / (job['job_id'] + '.json')) for job in jobs]
    if len(rows) != closure['total'] or len({r['job_id'] for r in rows}) != len(jobs):
        raise RuntimeError('Pilot attempt accounting differs')
    if any(row['job_id'] != job['job_id'] for row, job in zip(rows, jobs)):
        raise RuntimeError('Pilot job identity differs')
    if sum(r['status'] != 'COMPLETE' for r in rows) != closure['unknowns']:
        raise RuntimeError('Pilot unknown count differs')
    return closure, rows


def timing():
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Owner remains')
    result = dict(utc=utc(), production_workers=24, source_closure_paths={},
                  source_closure_sha256={}, result_use='timing and counts only',
                  candidate_measurements_opened=False)
    for label, phase in (('search', 'pilot_search'), ('A', 'pilot_A')):
        closure, rows = closed_attempts(phase, 24)
        # Controller receipts contain process costs, never scientific measurements.
        complete = [row for row in rows if row['status'] == 'COMPLETE']
        walls = [float(row['wall_seconds']) for row in complete]
        cpu = [float(row['sampled_cpu_seconds']) for row in complete]
        if any(not math.isfinite(v) or v < 0 for v in walls + cpu):
            raise ValueError('Invalid pilot process cost')
        result[label + '_job_walls_seconds'] = walls
        result[label + '_sampled_cpu_seconds'] = cpu
        result[label + '_n_complete'] = len(complete)
        result[label + '_n_unknown'] = len(rows) - len(complete)
        result[label + '_queue_hours'] = closure['queue_hours']
        result[label + '_converted_queue_seconds_per_star'] = queue_seconds_per_job(walls, 24)
        path = ROOT / 'results/controllers' / phase / 'closure.json'
        result['source_closure_paths'][label] = path.relative_to(REPO).as_posix()
        result['source_closure_sha256'][label] = sha(path)
    if result['search_n_complete'] + result['search_n_unknown'] != 24:
        raise RuntimeError('Pilot search denominator is not 24')
    # Pilot unknowns stay in their denominators; only COMPLETE walls price units.
    # This is the Part 0g measurement contract, not a retry or a scientific rejection.
    from lock_predictions_p12 import inspect
    for path in (ROOT/'results/funnel_io').glob('A_*.jsonl'):
        audit=inspect(path)
        if audit['forbidden'] or audit['malformed_rows']:
            raise RuntimeError('Pilot Stage A blind I/O failed')
    write(ROOT / 'results/pilot_timing.json', result)
    print(json.dumps({k: v for k, v in result.items() if k.endswith(('_n_complete', '_n_unknown', '_converted_queue_seconds_per_star'))}))
    return result


def report():
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Owner remains')
    if (ROOT / 'manifests/decision_point_1.json').exists():
        raise RuntimeError('Unexpected population decision before Part 0 report')
    eligibility = read(ROOT / 'manifests/eligibility_p12.json')
    hard_stop = read(ROOT / 'manifests/hard_stop_p12.json')
    ttt = read(ROOT / 'manifests/ttt_fetch.json')
    probe = read(ROOT / 'manifests/sector_probe.json')
    pilot = read(ROOT / 'results/pilot_timing.json')
    forecast_path = ROOT / 'manifests/forecast_p12.json'
    forecast = read(forecast_path)
    if not eligibility['complete'] or eligibility['n_unknown'] or ttt['status'] != 'COMPLETE':
        raise RuntimeError('Required Part 0 measurements are incomplete')
    successful = [attempt for attempt in ttt['attempts'] if attempt['status'] == 'COMPLETE']
    if not successful or successful[-1]['kind'] != ttt['source']:
        raise RuntimeError('TTT fetch provenance is ambiguous')
    fetch = successful[-1]
    fetch_path = fetch.get('download_path', fetch['url'])
    # Preserve raw walls and explicitly record the maximum rule in the forecast itself.
    for label, unit_key in (('search', 'search_queue_seconds'), ('A', 'A_queue_seconds')):
        row = forecast['pilot'][label]
        row['raw_complete_job_walls_seconds'] = pilot[label + '_job_walls_seconds']
        row['production_workers'] = 24
        row['conversion'] = 'mean COMPLETE job wall seconds / 24'
        row['used_queue_seconds_per_job'] = forecast['unit_costs'][unit_key]
        row['value_used'] = ('pilot' if row['measured_queue_seconds_per_job'] is not None
            and row['measured_queue_seconds_per_job'] > row['adopted_queue_seconds_per_job'] else 'inherited floor')
    forecast['pilot_timing_sha256'] = sha(ROOT / 'results/pilot_timing.json')
    extensions = {}
    for tier in ('E1', 'E2'):
        path = ROOT / 'manifests' / ('targets_ext_' + tier + '.csv')
        with path.open(newline='', encoding='utf-8-sig') as stream:
            rows = list(csv.DictReader(stream))
        extensions[tier] = dict(rows=len(rows), faint_band=sum(13.5 <= float(r['Tmag']) < 14 for r in rows), sha256=sha(path))
        if forecast['extensions'][tier]['stars'] != len(rows):
            raise RuntimeError('Extension forecast count differs from the ranked pool')
    forecast['ranked_extension_counts'] = extensions
    write(forecast_path, forecast, replace=True)
    hard_counts = {}
    for row in hard_stop['per_star'].values():
        status = row.get('hard_stop_p12', row.get('status'))
        hard_counts[status] = hard_counts.get(status, 0) + 1
    result = dict(utc=utc(), status='AWAITING_DECISION_POINT_1', forecast_sha256=sha(forecast_path),
        eligibility_counts=eligibility['counts'], injection_counts=eligibility['injections'],
        input_eligible=eligibility['n_eligible'], operational_unknowns=eligibility['n_unknown'],
        hard_stop_counts=hard_counts, N1=ttt['selection']['selected'], fetch_source=ttt['source'],
        fetch_path=fetch_path, fetch_url=fetch['url'], ttt_fetch_sha256=sha(ROOT / 'manifests/ttt_fetch.json'),
        sector_probe=probe, extensions=extensions, recommendation='core',
        decision_file_written=False, final_search_run=False)
    write(ROOT / 'results/decision_point_1_report.json', result)
    lines = ['# DECISION POINT 1', '', forecast['forecast_text'].removeprefix('DECISION POINT 1').lstrip(), '',
        '## Part 0 measurements [M]', '',
        '| Cohort | Eligible | Ineligible | Novelty rejected | Unknown |',
        '|---|---:|---:|---:|---:|']
    for name, row in eligibility['counts'].items():
        lines.append(f"| {name} | {row.get('INPUT_ELIGIBLE',0)} | {row.get('INPUT_INELIGIBLE',0)} | {row.get('REJECT_NOVELTY',0)} | {row.get('OPERATIONAL_UNKNOWN',0)} |")
    lines += ['', 'Eligible injection rows [M]: ' + json.dumps(eligibility['injections'], sort_keys=True) + '.',
        'Catalogue hard-stop counts [M]: ' + json.dumps(hard_counts, sort_keys=True) + '.',
        f"Independent negatives N1: {result['N1']} [M]; source: {ttt['source']}; fetch path: `{fetch_path}`.",
        'The fetch attempt URLs, UTC, bytes, hashes and relaxation counts are in `p12/manifests/ttt_fetch.json` [M].',
        f"Latest public QLP sector: {probe['latest_public_sector']} [M]. Per-star coverage above 105: {probe['core_above_105_status']} [M]. {probe['limitation']}",
        '', '## Pilot costs [M]', '', '| Stage | COMPLETE | Unknown | Mean job wall, s | Queue s/job at 24 workers | Value used |',
        '|---|---:|---:|---:|---:|---:|']
    for label in ('search', 'A'):
        row = forecast['pilot'][label]; walls = row['raw_complete_job_walls_seconds']
        mean = f'{sum(walls)/len(walls):.3f}' if walls else 'unmeasured'
        measured = row['measured_queue_seconds_per_job']
        converted = f'{measured:.3f}' if measured is not None else 'unmeasured'
        lines.append(f"| {label} | {row['n_complete']} | {row['n_unknown']} | {mean} | {converted} | {row['used_queue_seconds_per_job']:.3f} ({row['value_used']}) |")
    lines += ['', 'Pilot results were used only for timing and counts. No per-candidate measurement was displayed or reused [M].',
        '', '## Recommendation and decision [A/I]', '',
        f"Core only. The ranked E2 pool has {extensions['E2']['rows']} stars, including {extensions['E2']['faint_band']} at Tmag 13.5–14 [M]. The extension requires its own calibration; the inherited whole-funnel recovery in this faint band is 41% [P10.3]. Its additional cost and storage are explicit in the forecast [I].",
        'Pause here. The user chooses core, E1 or E2 and writes `p12/manifests/decision_point_1.json`. The agent has not written that file [M].',
        'The three human decision points remain launch approval after Part 0, any stop rule, and final delivery [A].',
        '', '## Provenance and resolved stops', '',
        'The sprint is closed by the user. Its original T0 and complete handoff remain in `p12/manifests/closed_sprint_20260922/`; section 10 no longer limits this continuation [A/M].',
        'The audit-only commit is `22a779d0456b81bce24fc9caa60c4fb86c8ba574` [M]. Normal verification uses its recorded source-refresh manifest with identical scientific job payloads [M].',
        'The failed initial native launcher started no controller and no scientific job. Its logs and the PowerShell 7 repair are preserved under `p12/manifests/verify_core_startup_failure_1/` [M].',
        'The earlier count and replay stop receipts and authorized resolutions remain preserved. The 118-test correction and exact historical exposures are recorded in `p12/protocol/AMENDMENTS_P12.md`; no new exception is authorized here [M].',
        f"PROMPT_P12.md SHA-256: `{sha(REPO/'PROMPT_P12.md')}` [M].",
        '', '## Original entry and sprint evidence', '',
        'The archived sprint handoff retains the full Part 0a table, test and integrity receipts, original T0, prior stops and their resolutions [M].',
        'Current evidence: `p12/results/decision_point_1_report.json`, `p12/results/pilot_timing.json`, and `p12/manifests/forecast_p12.json` [M].',
        '', 'Resume here: decision point 1; wait for the user population choice.']
    (REPO / 'HANDOFF_P12.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (REPO / 'RESUME_P12.md').write_text('resume here: decision point 1; wait for user-written population choice; no owner alive\n', encoding='utf-8')
    audit_path = REPO / 'docs/AUDIT_P12.md'
    with audit_path.open('a', encoding='utf-8') as stream:
        stream.write(f"\n\nPart 0 decision-point update {utc()} [M]: {eligibility['n_eligible']} input-eligible stars, {eligibility['n_unknown']} operational unknowns, N1={result['N1']} via {ttt['source']}. The 24-worker pilot supplies only costs/counts. Forecast and provenance are in HANDOFF_P12.md. Awaiting the user's population choice; final search has not run.\n")
    print(json.dumps({k: result[k] for k in ('status', 'input_eligible', 'operational_unknowns', 'hard_stop_counts', 'N1', 'fetch_source', 'fetch_path', 'recommendation')}))
    return result


def decision():
    """Decision point 1 resolved: the user's tier, the relocation receipts, LB1c and the
    re-rendered forecast, prepended to HANDOFF_P12.md from receipts only."""
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Owner remains')
    dp1 = read(ROOT / 'manifests/decision_point_1.json')
    forecast = read(ROOT / 'manifests/forecast_p12.json')
    if forecast.get('population_tier') != dp1['tier']:
        raise RuntimeError('Forecast not priced for the chosen tier')
    selection = read(ROOT / 'manifests/ttt_adjacent_selection.json')
    fetch = read(ROOT / 'manifests/ttt_adjacent_fetch.json')
    relocations = [read(ROOT / f'manifests/cache_relocation_{n}.json') for n in ('audit_lightkurve', 'audit_lc')]         if dp1['tier'] in ('E1', 'E2') else []
    lines = [f"# DECISION POINT 1 RESOLVED: tier {dp1['tier']} ({dp1['approved_utc']})", '',
        f"The user chose {dp1['tier']} in chat; `p12/manifests/decision_point_1.json` records it [M]. "
        'E1 stars carry population_tier "E1" in every table and packet; the extension runs as Part 5a is written, with its own '
        'calibration and no admission rule [A].', '', '## Audit-store relocation (0b, 5a) [M]', '',
        '| Store | Files before | Bytes before | Files after | Bytes after | Sample (seed 2026092002) equal |', '|---|---:|---:|---:|---:|---|']
    for r in relocations:
        lines.append(f"| `{r['what'].split(' ')[0]}` -> `{r['destination']}` | {r['files_before']} | {r['bytes_before']} | "
                     f"{r['files_after']} | {r['bytes_after']} | {r['sample']['size']} files, {r['sample']['all_equal_after']} |")
    if relocations:
        lines += ['', f"C: free after relocation: {relocations[-1]['c_free_bytes_after']/1e9:.1f} GB [M]. Paths are unchanged through the junctions."]
    c = selection['counts']
    lines += ['', '## LB1c adjacent-domain negatives (amendment 2026-09-23) [A/M]', '',
        'Reported, never part of bar_met; page one labels it "adjacent domain (K and late-K dwarfs), not the M-dwarf domain" [A]. '
        'LB1a stays as written with N1 = 1 and bar_met still requires LB1a, so the final state is BAR_NOT_MET by construction [A].', '',
        f"TIC metadata: {fetch['returned']} of {fetch['requested']} union TICs returned by MAST ({fetch['missing']} missing), "
        f"{fetch['chunks']} chunk attempts, {fetch['wall_seconds']} s [M].", '',
        '| Cut | Stars remaining |', '|---|---:|'] + [f'| {k} | {v} |' for k, v in c.items()] + ['',
        f"Selected (first {selection['cuts']['first']} by SHA-256 of 20260908:ttt:<TIC>): {selection['selected']} [M]; "
        f"overlap with the LB1a star: {len(selection['overlap_with_LB1a'])} [M]. Manifest `p12/manifests/ttt_adjacent_negatives.csv`; "
        f"ephemerides in the guarded `{selection['guarded_ephemerides_path']}` [M].",
        'The P8 pool is an M-dwarf TIC query (Teff 2,000 to 3,600 K, radius <= 0.50), so LB1c applies its enumerated cuts to the union '
        'with fresh TIC v8 metadata; no radius cut and no pool join [A].', '',
        '## Forecast re-rendered for the chosen tier [A/I]', '', forecast['forecast_text'], '',
        'Resume here: Part 1 (registration after the Part 1 modules, their tests and PREREGISTRATION_P12.md exist); '
        'the hourly check-in routine is re-armed when the first Part 1 phase launches.', '', '---', '']
    handoff = REPO / 'HANDOFF_P12.md'
    handoff.write_text('\n'.join(lines) + '\n' + handoff.read_text(encoding='utf-8'), encoding='utf-8')
    with (REPO / 'RESUME_P12.md').open('a', encoding='utf-8') as stream:
        stream.write(f"\n{utc()} [M]: decision point 1 resolved ({dp1['tier']}); audit stores relocated; LB1c selected "
                     f"{selection['selected']}; forecast re-rendered; resume here: Part 1 registration; no owner alive; "
                     'routine not armed until the first Part 1 phase.\n')
    with (REPO / 'docs/AUDIT_P12.md').open('a', encoding='utf-8') as stream:
        stream.write(f"\n\nDecision point 1 resolved {utc()} [M]: tier {dp1['tier']}; LB1c adjacent-domain set "
                     f"{selection['selected']} stars (reported, never part of bar_met); final search has not run.\n")
    result = dict(utc=utc(), tier=dp1['tier'], lb1c_selected=selection['selected'], forecast_sha256=sha(ROOT / 'manifests/forecast_p12.json'))
    print(json.dumps(result))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('timing', 'report', 'decision'))
    args = parser.parse_args(); {'timing': timing, 'report': report, 'decision': decision}[args.action]()
