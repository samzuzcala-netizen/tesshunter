"""P12 planning and measured resource ledger; units are explicit queue time."""
from p12_common import REPO, ROOT, read, write, sha, utc
import argparse
import json
import math
from pathlib import Path


def queue_seconds_per_job(walls, workers):
    if not isinstance(workers, int) or workers <= 0:
        raise ValueError('Worker width must be a positive integer')
    if not walls:
        return None
    if any(not math.isfinite(value) or value < 0 for value in walls):
        raise ValueError('Finite nonnegative job walls required')
    return sum(walls) / len(walls) / workers


def _range(low, high, margin):
    return dict(base_queue_hours=[low, high], with_margin_queue_hours=[low * margin, high * margin])


def _counts():
    # Only an explicit aggregate contract is accepted; no per-star inspection.
    adopted = dict(core_eligible=2000, tce_eligible=436, calibration_eligible=300,
                   injections_eligible=2100, two_b_injections_eligible=600)
    path = ROOT / 'manifests/eligibility_p12.json'
    if not path.exists():
        return adopted, 'ADOPTED_COUNTS_UNMEASURED'
    receipt = read(path)
    counts = receipt.get('forecast_counts')
    if counts is None and 'counts' in receipt and 'injections' in receipt:
        counts = dict(core_eligible=receipt['counts']['p8_2000'].get('INPUT_ELIGIBLE', 0),
            tce_eligible=receipt['counts']['p10_436'].get('INPUT_ELIGIBLE', 0),
            calibration_eligible=receipt['counts']['calibration_300'].get('INPUT_ELIGIBLE', 0),
            injections_eligible=receipt['injections']['full']['eligible'],
            two_b_injections_eligible=receipt['injections']['2b']['eligible'])
    if not isinstance(counts, dict):
        raise RuntimeError('Eligibility forecast_counts aggregate required; refusing to guess counts')
    for key in adopted:
        if key not in counts or not isinstance(counts[key], int) or counts[key] < 0:
            raise ValueError('Invalid eligibility aggregate: ' + key)
    return {key: counts[key] for key in adopted}, 'MEASURED_ELIGIBILITY'


def forecast_after_part2():
    """6.1: after Part 2 re-render with the measured ratio, carrying every measured
    repricing of Part 0 and decision point 1 forward (Part 4 cohort, tier rows)."""
    configuration = read(ROOT / 'protocol/config.json')
    decision = read(ROOT / 'results/part2/photometry_decision.json')
    sml = decision['decision'] == 'ADOPT_SML'
    ratio = 1.0
    if sml:
        ratio = decision.get('median_wall_ratio')
        if not isinstance(ratio, (int, float)) or not math.isfinite(ratio) or ratio <= 0:
            raise ValueError('ADOPT_SML requires a measured median_wall_ratio')
        if ratio > configuration['photometry_bar']['wall_ratio_max']:
            raise ValueError('ADOPT_SML measured ratio exceeds registered ceiling 3')
        ratio = max(1.0, ratio)
    path = ROOT / 'manifests/forecast_p12.json'
    previous = read(path)
    if previous.get('after_part2'):
        raise FileExistsError('Part 2 re-render already written')
    backup = ROOT / 'manifests/forecast_before_part2.json'
    write(backup, previous)
    result = json.loads(json.dumps(previous))
    margin = result['forecast_margin']
    if sml:
        extra2 = sum(result['part2_adopt_sml_components_queue_hours'].values())
        core5 = result['part5_components_queue_hours']['search'] + result['part5_components_queue_hours']['A']
        extra5 = core5 * (ratio - 1)
        for part, extra in (('2', extra2), ('5', extra5)):
            low, high = result['parts'][part]['base_queue_hours']
            result['parts'][part] = _allocation(low + extra, high + extra, margin)
        low, high = result['total']['base_queue_hours']
        result['total'] = _allocation(low + extra2 + extra5, high + extra2 + extra5, margin)
        result['separate_C_retry_tail_queue_hours'] += 10
        result['calendar_days_at_historical_duty'] = [v / .553 / 24 for v in result['total']['with_margin_queue_hours']]
        result['calendar_days_at_full_duty'] = [v / 24 for v in result['total']['with_margin_queue_hours']]
    result.update(utc=utc(), after_part2=True, adopted_arm='sml' if sml else 'archival',
                  measured_sml_wall_ratio=ratio if sml else None, previous_forecast_sha256=sha(path),
                  photometry_decision_sha256=sha(ROOT / 'results/part2/photometry_decision.json'))
    result['forecast_text'] = ('FORECAST AFTER PART 2\n\n' + f"Adopted arm: {result['adopted_arm']}; measured wall ratio "
        f"{ratio:.3f} [M].\nTotal with margin: " + ' to '.join(f'{v:.2f}' for v in result['total']['with_margin_queue_hours'])
        + ' queue-h [I].\n\n' + previous.get('forecast_text', ''))
    write(path, result, replace=True)
    return result


def forecast(*, after_part2=False):
    if after_part2:
        return forecast_after_part2()
    configuration = read(ROOT / 'protocol/config.json')
    margin = float(configuration['forecast_margin'])
    if margin != 1.25:
        raise ValueError('Registered forecast margin changed')
    counts, count_status = _counts()
    units = dict(configuration['forecast_units'])
    pilot_path = ROOT / 'results/pilot_timing.json'
    pilot = read(pilot_path) if pilot_path.exists() else {}
    pilot_units = {}
    if pilot and pilot.get('production_workers') != 24:
        raise ValueError('Pilot must use production width of 24')
    for label, key in [('search', 'search_queue_seconds'), ('A', 'A_queue_seconds')]:
        measured = queue_seconds_per_job(pilot.get(label + '_job_walls_seconds', []), 24)
        pilot_units[label] = dict(measured_queue_seconds_per_job=measured, adopted_queue_seconds_per_job=units[key],
            status='MEASURED' if measured is not None else 'UNMEASURED',
            n_complete=pilot.get(label + '_n_complete', len(pilot.get(label + '_job_walls_seconds', []))),
            n_unknown=pilot.get(label + '_n_unknown'))
        if measured is not None:
            units[key] = max(units[key], measured)
    sml, ratio = False, 1.0
    decision_path = ROOT / 'results/part2/photometry_decision.json'
    if after_part2:
        decision = read(decision_path)
        sml = decision['decision'] == 'ADOPT_SML'
        if sml:
            ratio = decision.get('median_wall_ratio')
            if not isinstance(ratio, (int, float)) or not math.isfinite(ratio) or ratio <= 0:
                raise ValueError('ADOPT_SML requires a measured median_wall_ratio')
            if ratio > configuration['photometry_bar']['wall_ratio_max']:
                raise ValueError('ADOPT_SML measured ratio exceeds registered ceiling 3')
            ratio = max(1.0, ratio)  # measured costs never lower the adopted forecast
    core_scale = (counts['core_eligible'] + counts['tce_eligible']) / 2436
    cal_scale = counts['injections_eligible'] / 2100
    host_scale = counts['calibration_eligible'] / 300
    real_scale = counts['tce_eligible'] / 436
    two_b_scale = counts['two_b_injections_eligible'] / 600
    search_scale = units['search_queue_seconds'] / configuration['forecast_units']['search_queue_seconds']
    a_scale = units['A_queue_seconds'] / configuration['forecast_units']['A_queue_seconds']
    # Section 6.1's registered ranges, with the priced search/A sub-lines.
    final_search = 22.7 * core_scale * search_scale
    a_load = counts['core_eligible']*2.363 + counts['tce_eligible']*2.532
    final_a = 25.4 * a_load/(2000*2.363+436*2.532) * a_scale
    c_low = counts['core_eligible']*.0067 + counts['tce_eligible']*.067
    c_high = counts['core_eligible']*.0067*3 + counts['tce_eligible']*.067
    c_low_scale = c_low/(2000*.0067+436*.067)
    c_high_scale = c_high/(2000*.0067*3+436*.067)
    # Residuals are C/D/cutout/S/B costs, priced with the separate natural-load bounds.
    final_fixed = [(66.0-48.1)*c_low_scale, (81.3-48.1)*c_high_scale]
    cal_a_load_scale = (1184*cal_scale+709*host_scale)/1893
    cal_b_load_scale = (600*two_b_scale+300*host_scale)/900
    remaining_scale = max(0, counts['injections_eligible']-counts['two_b_injections_eligible'])/1500
    c_sample = 10.8  # The registered 30-job sample remains a conservative allocation.
    part2_components = dict(
        prepare=1.0*host_scale,
        archival_search=21.1*(counts['injections_eligible']+counts['calibration_eligible'])/2400*search_scale,
        archival_A=8.2*cal_a_load_scale*a_scale,
        archival_S_B=.4*cal_a_load_scale,
        archival_C=c_sample,
        archival_real436=3.8*real_scale*search_scale,
        sml_store_prepare=1.0*host_scale,
        sml_subset_search=7.9*cal_b_load_scale*search_scale,
        sml_real436=3.8*real_scale*search_scale,
        sml_subset_A=5.5*cal_b_load_scale*a_scale,
        sml_subset_S=.1*cal_b_load_scale,
        tabulations=.2)
    adopted_sml_components = dict(remaining_search=13.2*remaining_scale*search_scale,
        remaining_A=4.3*remaining_scale*a_scale,remaining_C=c_sample,remaining_prepare=1.2*remaining_scale)
    sml_extra = sum(adopted_sml_components.values())
    part2_total = sum(part2_components.values()) + (sml_extra if sml else 0)
    parts = {
        '0': _range(3.1 + max(0, (counts['core_eligible']+counts['tce_eligible'])*units['verify_queue_seconds']/3600-1.0), 3.1 + max(0, (counts['core_eligible']+counts['tce_eligible'])*units['verify_queue_seconds']/3600-1.0), margin),
        '1': _range(1.2, 1.2, margin),
        '2': _range(part2_total, part2_total, margin),
        '3': _range(0, 0, margin),
        '4': _range(44.6, 44.6, margin),
        '5': _range(final_fixed[0]+(final_search+final_a)*ratio, final_fixed[1]+(final_search+final_a)*ratio, margin),
        '6': _range(1.0, 1.0, margin)}
    total_low = sum(row['base_queue_hours'][0] for row in parts.values())
    total_high = sum(row['base_queue_hours'][1] for row in parts.values())
    archival_base = [total_low-(sml_extra if sml else 0)-(final_search+final_a)*(ratio-1),
                     total_high-(sml_extra if sml else 0)-(final_search+final_a)*(ratio-1)]
    scenarios = {
        'archival': _range(*archival_base, margin),
        'ADOPT_SML_ratio_1': _range(*(value+sml_extra for value in archival_base), margin),
        'ADOPT_SML_ratio_3_ceiling': _range(*(value+sml_extra+2*(final_search+final_a) for value in archival_base), margin)}
    retry_tail = 73 if sml else 63
    phases = {}
    # Known jobs manifests provide exact queue denominators to STOP-6.
    for path in sorted((ROOT / 'manifests').glob('*_jobs.json')):
        jobs = read(path)
        if not isinstance(jobs, list):
            continue
        phase = path.name[:-10]
        n = len(jobs)
        if phase.endswith(('_C_retry',)):
            hours = n*36000/3/3600
        elif phase.endswith('_C'):
            hours = n*units['C_queue_hours']
        elif phase.endswith(('_D','_D_retry')):
            hours = n*units['D_queue_minutes']/60
        elif phase.endswith(('_A','_A_retry')):
            hours = n*units['A_queue_seconds']/3600
            if phase.startswith('final_') and sml:
                hours *= ratio
        elif phase.endswith(('_S','_S_retry')):
            hours = n*units['S_queue_seconds']/3600
        elif phase.endswith(('_B','_B_retry')):
            hours = n*units['B_queue_seconds']/3600
        elif 'search' in phase or 'real436' in phase:
            hours = n*units['search_queue_seconds']/3600
            if phase.startswith('final_') and sml:
                hours *= ratio
        elif 'verify' in phase:
            hours = n*units['verify_queue_seconds']/3600
        elif 'download' in phase:
            hours = n*units['download_queue_seconds']/3600
        else:
            continue
        phases[phase] = dict(jobs=n, base_queue_hours=hours, with_margin_queue_hours=hours*margin, jobs_sha256=sha(path))
    result = dict(utc=utc(), schema='p12-forecast-v1', after_part2=after_part2, count_status=count_status,
        counts=counts, unit_costs=units, pilot=pilot_units, forecast_margin=margin,
        adopted_arm='sml' if sml else 'archival', measured_sml_wall_ratio=ratio if after_part2 and sml else None,
        parts=parts, part2_base_components_queue_hours=part2_components,
        part2_adopt_sml_components_queue_hours=adopted_sml_components,
        part5_components_queue_hours=dict(search=final_search*ratio,A=final_a*ratio,other_lower=final_fixed[0],other_upper=final_fixed[1]),
        total=_range(total_low,total_high,margin), scenarios=scenarios,
        separate_C_retry_tail_queue_hours=retry_tail, phases=phases,
        calendar_days_at_historical_duty=[total_low*margin/.553/24,total_high*margin/.553/24],
        calendar_days_at_full_duty=[total_low*margin/24,total_high*margin/24],
        retry_tail_not_in_base_or_margin=True, queue_cap=None,
        extensions={'E1':dict(stars=1000,**_range(39,49,margin),http_GB=26,disk_D_GB=48),
                    'E2':dict(stars=7989,**_range(217,295,margin),http_GB=[40,211],disk_D_GB=383,relocate_existing_GB=82)},
        disk_D_GB=[175,220] if sml else [165,210],disk_C_GB_upper=3,http_GB=[72,115],
        assumptions=['[A] Section 6.1 stage-load rates apply to the frozen-policy eligible population.',
                     '[A] Calibration stage-load and preparation proportions scale within their own full-injection, 2b-injection or host cohorts; both real-host legs scale only with eligible TCE hosts.',
                     '[A] Both 30-job calibration C allocations remain conservatively priced even when fewer calibration hosts qualify; actual job manifests replace phase costs when available.',
                     '[A] Queue costs are job-wall sums divided by the measured concurrency once.',
                     '[A] The 1.25 margin is applied once; C retries remain a separate tail.',
                     '[I] Calendar conversion at duty 0.553 is conditional and promises no completion date.'])
    result['forecast_text'] = render(result)
    path = ROOT / 'manifests/forecast_p12.json'
    if path.exists():
        previous = read(path)
        if not after_part2:
            raise FileExistsError('Initial forecast already exists')
        backup = ROOT / 'manifests/forecast_before_part2.json'
        if not backup.exists():
            write(backup, previous)
        result['previous_forecast_sha256'] = sha(path)
    write(path, result, replace=path.exists())
    return result


def render(result):
    lines = ['DECISION POINT 1' if not result['after_part2'] else 'FORECAST AFTER PART 2', '',
             'Core-only is the registered recommendation [A]. Extension eligibility is not measured completeness [I].', '',
             '| Part | Base queue-h [A/I] | With margin [A/I] |',
             '|---|---:|---:|']
    for part, row in result['parts'].items():
        lines.append('| '+part+' | '+' to '.join(f'{v:.2f}' for v in row['base_queue_hours'])+' | '+' to '.join(f'{v:.2f}' for v in row['with_margin_queue_hours'])+' |')
    lines += ['', 'Total with margin: '+' to '.join(f'{v:.2f}' for v in result['total']['with_margin_queue_hours'])+' queue-h [I].',
              f"Separate C retry tail: up to {result['separate_C_retry_tail_queue_hours']} queue-h [A].",
              'Decision points [A]: launch approval after Part 0; any stop rule; final delivery.',
              '', 'Assumptions', *result['assumptions']]
    return '\n'.join(lines)


def _allocation(low, high, margin):
    return dict(base_queue_hours=[low, high], with_margin_queue_hours=[low * margin, high * margin])


def price_decision_point_1():
    """Re-render the forecast with the chosen tier's rows and the LB1c line (decision point 1).

    E1 adds its extension row (0e ranking, pilot-scaled search/A units) to Part 5; the LB1c
    amendment reuses the 4b line per selected star (6.1: acquisition .15, neighbours .14,
    search .27, A .4, C 10.8, D 3.8, cutouts .3 queue-h per 30 stars) in Part 4. The
    acquisition pilot of 5a is unmeasured here; its per-star bytes and wall replace 12.9
    queue-s and 48 MB per star when higher (``price_phase`` at that phase).
    """
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Owner remains')
    decision = read(ROOT / 'manifests/decision_point_1.json')
    tier = decision['tier']
    path = ROOT / 'manifests/forecast_p12.json'
    original = read(path)
    if original.get('population_tier'):
        raise FileExistsError('Decision point 1 already priced')
    backup = ROOT / 'manifests/forecast_before_decision_point_1.json'
    write(backup, original)
    result = json.loads(json.dumps(original))
    margin = result['forecast_margin']
    if margin != 1.25:
        raise ValueError('Registered forecast margin changed')
    search = max(1., result['unit_costs']['search_queue_seconds'] / 31.9)
    stage_a = max(1., result['unit_costs']['A_queue_seconds'] / 15.5)
    selection = read(ROOT / 'manifests/ttt_adjacent_selection.json')
    n = int(selection['selected'])
    lb1c = dict(lb1c_acquisition=.15*n/30, lb1c_neighbours=.14*n/30, lb1c_search=.27*n/30*search,
                lb1c_A=.4*n/30*stage_a, lb1c_C=10.8*n/30, lb1c_D=3.8*n/30, lb1c_cutouts=.3*n/30)
    lb1c_total = sum(lb1c.values())
    ext = result['extensions'].get(tier) if tier in ('E1', 'E2') else None
    ext_range = ext['base_queue_hours'] if ext else [0., 0.]
    part4 = result['parts']['4']['base_queue_hours'][0] + lb1c_total
    result['parts']['4'] = _allocation(part4, part4, margin)
    result['part4_base_components_queue_hours'].update(lb1c)
    low5, high5 = result['parts']['5']['base_queue_hours']
    result['part5_core_base_queue_hours'] = [low5, high5]
    result['parts']['5'] = _allocation(low5 + ext_range[0], high5 + ext_range[1], margin)
    result['part5_components_queue_hours']['extension_' + tier] = ext_range if ext else None
    delta = [lb1c_total + ext_range[0], lb1c_total + ext_range[1]]
    result['total'] = _allocation(*(v + d for v, d in zip(result['total']['base_queue_hours'], delta)), margin)
    for key, row in result['scenarios'].items():
        result['scenarios'][key] = _allocation(*(v + d for v, d in zip(row['base_queue_hours'], delta)), margin)
    # Separate tail (10% of C jobs at up to 10 h, 3 concurrent): 30 LB1c C jobs; E1 at 3x the false-alarm rate.
    tail_lb1c = .1 * (30 * n / 30) * 10 / 3
    tail_ext = (.1 * 20 * 10 / 3) if tier == 'E1' else (.1 * 161 * 10 / 3 if tier == 'E2' else 0.)
    result['separate_C_retry_tail_queue_hours'] = original['separate_C_retry_tail_queue_hours'] + tail_lb1c + tail_ext
    result['calendar_days_at_historical_duty'] = [v / .553 / 24 for v in result['total']['with_margin_queue_hours']]
    result['calendar_days_at_full_duty'] = [v / 24 for v in result['total']['with_margin_queue_hours']]
    result['http_GB'] = [original['http_GB'][0] + (ext or {}).get('http_GB', 0) + .8*n/30,
                         original['http_GB'][1] + (ext or {}).get('http_GB', 0) + .8*n/30 + 24*n/30]
    result['disk_D_GB'] = [original['disk_D_GB'][0] + (ext or {}).get('disk_D_GB', 0) + 1.4*n/30,
                           original['disk_D_GB'][1] + (ext or {}).get('disk_D_GB', 0) + 1.4*n/30 + 24*n/30]
    result.update(population_tier=tier, decision_point_1_sha256=sha(ROOT / 'manifests/decision_point_1.json'),
        lb1c=dict(selected=n, base_queue_hours=lb1c_total, with_margin_queue_hours=lb1c_total*margin,
                  components=lb1c, reported_never_bar_met=True, selection_sha256=sha(ROOT / 'manifests/ttt_adjacent_selection.json')),
        extension_acquisition_pilot=dict(status='UNMEASURED', unit_download_queue_seconds=result['unit_costs']['download_queue_seconds'],
            unit_disk_MB_per_star=48, rule='final_ext_download_pilot per-star bytes and queue-s replace these when higher'),
        previous_forecast_sha256=sha(path), timing_pilot_units=dict(search=result['unit_costs']['search_queue_seconds'],
            A=result['unit_costs']['A_queue_seconds'], source='p12/results/pilot_timing.json (0g), higher of pilot and 6.1'))
    result['assumptions'] = list(result['assumptions']) + [
        f'[A/I] Decision point 1 chose {tier}; its extension row (0e-ranked count, pilot-scaled search and A units) is added to Part 5.',
        f'[A/I] LB1c reuses the 4b line per selected star ({n} of 30) in Part 4; it is reported and never part of bar_met.',
        '[A] The 5a acquisition pilot is unmeasured here; its per-star bytes and wall replace the adopted units when higher.']
    lines = [f'DECISION POINT 1: tier {tier} chosen', '', '| Part | Base queue-h [A/I] | With margin [A/I] |', '|---|---:|---:|']
    for part, row in result['parts'].items():
        lines.append('| ' + part + ' | ' + ' to '.join(f'{v:.2f}' for v in row['base_queue_hours']) + ' | '
                     + ' to '.join(f'{v:.2f}' for v in row['with_margin_queue_hours']) + ' |')
    lines += ['', f"Part 4 includes LB1c ({n} stars): {lb1c_total:.2f} base queue-h [A/I].",
              f"Part 5 includes {tier}: {ext_range[0]:.2f} to {ext_range[1]:.2f} base queue-h [A/I].",
              'Total with margin: ' + ' to '.join(f'{v:.2f}' for v in result['total']['with_margin_queue_hours']) + ' queue-h [I].',
              f"Separate C retry tail: up to {result['separate_C_retry_tail_queue_hours']:.1f} queue-h [A].",
              'Calendar at duty 0.553: ' + ' to '.join(f'{v:.1f}' for v in result['calendar_days_at_historical_duty']) + ' days [I]; no date is promised.',
              '', 'Assumptions', *result['assumptions']]
    result['forecast_text'] = '\n'.join(lines)
    write(path, result, replace=True)
    write(ROOT / 'manifests/forecast_decision_point_1_pricing.json', dict(utc=utc(), status='COMPLETE', tier=tier,
        input_forecast_sha256=sha(backup), output_forecast_sha256=sha(path), lb1c_selected=n,
        lb1c_base_queue_hours=lb1c_total, extension_base_queue_hours=ext_range, source_sha256=sha(__file__)))
    return result


def _job_kind(phase, jobs):
    """The stage a jobs manifest runs, from its worker script (names are not case-reliable:
    the Part 1 phase is ``plumbing_d``); the phase suffix is only the fallback."""
    script = Path(jobs[0]['arguments'][0]).name if jobs else ''
    # Superseded 2026-09-23 (AMENDMENTS_P12.md): the ephemeris-assisted leg runs A then D per signal and is
    # priced as D; the novelty re-check is two bounded 600-s source fetches.
    table = (('stage_d_worker', 'D'), ('stage_c_worker', 'C'), ('blind_search_worker', 'search'),
             ('prepare_injections', 'prepare'), ('verify_prepare', 'verify'), ('download_star', 'download'),
             ('neighbours', 'neighbours'), ('ephemeris_assisted', 'D'), ('novelty', 'novelty'))
    for marker, kind in table:
        if marker in script:
            return kind
    if 'funnel_stage' in script or 'funnel_worker' in script:
        return jobs[0]['arguments'][1]
    lower = phase.lower()
    for suffix, kind in (('_c_retry', 'C'), ('_c', 'C'), ('_d_retry', 'D'), ('_d', 'D'), ('_a_retry', 'A'), ('_a', 'A'),
                         ('_s_retry', 'S'), ('_s', 'S'), ('_b_retry', 'B'), ('_b', 'B')):
        if lower.endswith(suffix):
            return kind
    for word, kind in (('search', 'search'), ('real436', 'search'), ('verify', 'verify'), ('prepare', 'prepare'),
                       ('download', 'download'), ('neighbour', 'neighbours')):
        if word in lower:
            return kind
    return 'other'


def price_phase(phase, jobs_path, *, unit_override=None):
    """Price a planner-written jobs manifest for STOP-6 (appends; never lowers a price).

    Superseded 2026-09-23 (AMENDMENTS_P12.md): the ephemeris-assisted leg is priced as D, the novelty
    re-check at 2 x 600 s, a neighbour set by its star count, and every phase by rounds of its registered
    workers (a unit is one job's share of phase wall time at its 6.1 worker count).

    Units (6.1): D 7.5 queue-min per candidate; C 0.36 queue-h per job (a C retry at its 36,000-s
    deadline, three at a time); A 15.5, S 1.3, B 0.45 queue-s per job; search 31.9 queue-s per star
    (pilot-raised); verify 1.54 queue-s per star; injection preparation twice the verify unit
    (Part 2 forecast: about 1 queue-h for up to 2,400); download 12.9 queue-s per star.
    """
    path = ROOT / 'manifests/forecast_p12.json'
    forecast = read(path)
    units = dict(forecast['unit_costs'], **(unit_override or {}))
    margin = forecast['forecast_margin']
    jobs = read(jobs_path)
    n = len(jobs)
    sml_ratio = forecast.get('measured_sml_wall_ratio') or 1.0
    final = phase.startswith('final_')
    kind = _job_kind(phase, jobs)
    retry_c = kind == 'C' and (phase.lower().endswith('_c_retry') or any(j.get('attempt') == 2 for j in jobs))
    hours = {
        'C': n * (36000 / 3 / 3600 if retry_c else units['C_queue_hours']),
        'D': n * units['D_queue_minutes'] / 60,
        'A': n * units['A_queue_seconds'] / 3600 * (sml_ratio if final else 1),
        'S': n * units['S_queue_seconds'] / 3600,
        'B': n * units['B_queue_seconds'] / 3600,
        'search': n * units['search_queue_seconds'] / 3600 * (sml_ratio if final else 1),
        'verify': n * max(units['verify_queue_seconds'], 1.54) / 3600,
        'prepare': n * 2 * max(units['verify_queue_seconds'], 1.54) / 3600,
        'download': n * units['download_queue_seconds'] / 3600,
        # Superseded 2026-09-23: a neighbour set is one job over many stars, so the 6.1 unit (16.5 min per 2,000
        # stars at 2 workers, about 1 queue-s per star for one worker) is applied to the job's registered star
        # count, floored at 0.1 h (a set's bulk SIMBAD and VSX queries); novelty: 2 x 600 s per job.
        'neighbours': max(sum(int(j.get('stars', 1)) for j in jobs) * 16.5 * 60 * 2 / 2000 / 3600, .1),
        'novelty': n * 2 * 600 / 3600,
    }.get(kind, max(n * 60 / 3600, .05))
    # Superseded 2026-09-23: every unit is a job's share of phase wall time at its 6.1 worker count (one job's own
    # wall is the unit times that count), so a phase runs in rounds of its registered workers: a row with fewer
    # workers (the 4c layout: 4 search and A workers, 2 C, 2 D) or fewer jobs than workers (a one-job D re-run)
    # is priced by its rounds. Never below the 6.1 product.
    basis = dict(search=24, A=24, S=24, B=24, verify=8, prepare=8, download=4, C=3, D=2).get(kind)
    sequence = ROOT / 'manifests/phase_sequence.json'
    row_workers = next((p.get('workers') for p in (read(sequence)['phases'] if sequence.exists() else []) if p['name'] == phase), None)
    scale = 1.0
    if basis and row_workers and n:
        rounds = -(-n // row_workers)
        scaled = hours / n * basis * rounds
        scale = max(scaled / hours, 1.0) if hours else 1.0
        hours = max(hours, scaled)
    hours = max(hours, 1 / 60)
    old = forecast['phases'].get(phase)
    row = dict(jobs=n, kind=kind, base_queue_hours=hours, with_margin_queue_hours=hours * margin, jobs_sha256=sha(jobs_path),
               priced_utc=utc(), units=units, worker_scale=scale)
    if old and old.get('with_margin_queue_hours', 0) > row['with_margin_queue_hours'] and old.get('jobs') == n:
        row.update(base_queue_hours=old['base_queue_hours'], with_margin_queue_hours=old['with_margin_queue_hours'])
    forecast['phases'][phase] = row
    write(path, forecast, replace=True)
    return row


def final():
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Owner must close before final ledger')
    path = ROOT / 'manifests/resource_ledger.json'
    ledger = read(path)
    intervals = ledger.get('intervals', [])
    total = sum(float(row['hours']) for row in intervals)
    recorded = float(ledger.get('new_queue_hours', ledger.get('scientific_queue_hours', 0)))
    if not math.isclose(total, recorded, abs_tol=1e-9):
        raise RuntimeError('Queue intervals do not reconcile')
    for row in intervals:
        closure = read(ROOT / 'results/controllers' / row['phase'] / 'closure.json')
        if not closure['all_owned_workers_closed']:
            raise RuntimeError('Owned workers remain')
        if not math.isclose(float(closure['queue_hours']), float(row['hours']), abs_tol=1e-9):
            raise RuntimeError('Closure charge differs from ledger')
    ledger.update(utc=utc(), status='FINAL_RECONCILED', interval_queue_hours=total,
        historical_costs_preserved=True, science_queue_cap=None)
    write(path, ledger, replace=True)
    return ledger


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('forecast','final'))
    parser.add_argument('--after-part2',action='store_true');parser.add_argument('--decision-point-1',action='store_true')
    args=parser.parse_args(argv)
    if args.action=='forecast' and args.decision_point_1:result=price_decision_point_1()
    else:result=forecast(after_part2=args.after_part2) if args.action=='forecast' else final()
    print(result.get('forecast_text',json.dumps(result)),flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
