"""Metadata-only conditional fresh sampling; no acquisition or signal draws.

The supported population is the verified eligible part of one prospectively
frozen acquisition frame. Weights describe that finite population, not unaudited
stars outside the frame. This executable component is not a validation result.
"""
from collections import Counter
import hashlib
import math


LEVELS = ((300, 150, 1050), (200, 100, 700), (100, 50, 350))
OUTCOME_FIELDS = frozenset({
    'recovered', 'recovery', 'prediction', 'predictions', 'snr_measured',
    'candidate', 'candidates', 'truth', 'period', 't0', 'rp_rs', 'rp_earth',
    'decision', 'verdict', 'signal', 'injection',
})


def validation_hash(tic):
    return hashlib.sha256(
        f'20260913:p11_5:validation:{int(tic)}'.encode()).hexdigest()


def check_metadata_only(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in OUTCOME_FIELDS:
                raise ValueError('Outcome or signal field in sampling metadata: ' + key)
            check_metadata_only(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            check_metadata_only(item)


def audited_rows(rows, excluded_ids=()):
    """Require completed per-host input audits; missing coverage is not eligible."""
    check_metadata_only(rows)
    excluded = {int(x) for x in excluded_ids}
    seen = set()
    result = []
    for row in rows:
        tic = int(row['tic_id'])
        if tic in seen:
            raise ValueError('Duplicate audited host')
        seen.add(tic)
        if tic in excluded or row.get('outcome_exposed') is not False:
            raise ValueError('Previously exposed or exposure-unknown host')
        if row.get('audit_status') != 'COMPLETE':
            raise ValueError('Unfinished acquisition-frame audit')
        if row.get('input_eligibility') == 'INPUT_INELIGIBLE':
            if not row.get('exclusion_reasons'):
                raise ValueError('Input exclusion lacks a reason')
            continue
        if row.get('input_eligibility') != 'D_core':
            raise ValueError('Input eligibility is unverified')
        magnitude = float(row['tmag'])
        ffi = {int(s) for s in row['verified_native_ffi_sectors']}
        targeted = {int(s) for s in row['targeted_ffi_sectors']}
        values = (magnitude, float(row['teff_k']), float(row['radius_rsun']),
                  float(row['mass_msun']), float(row['galactic_lat_deg']))
        if not all(math.isfinite(x) for x in values):
            raise ValueError('Non-finite stellar metadata')
        if not (12.5 <= magnitude <= 14 and values[1] < 3600 and
                0 < values[2] < .45 and values[3] > 0 and abs(values[4]) >= 20 and
                row.get('original_p8_stellar_cuts_pass') is True):
            raise ValueError('Verified host does not meet original P8 stellar cuts')
        if len(ffi) < 3 or len(ffi & targeted) >= len(ffi) / 2:
            raise ValueError('Verified host does not meet strict FFI coverage')
        if not ffi <= set(range(56, 106)):
            raise ValueError('Sector outside the single frozen supported era')
        # Release exclusions concern QLP products, not the sector identifier
        # itself. The audited product receipt must establish usable alternatives.
        if not row.get('input_receipt_path') or not row.get('input_receipt_sha256'):
            raise ValueError('Exact audited input identity missing')
        stratum = (f'{min(2, int((magnitude - 12.5) / .5))}:'
                   f'{0 if len(ffi) <= 5 else 1 if len(ffi) <= 10 else 2}')
        result.append(dict(row, tic_id=tic, stratum=stratum,
                           hash=validation_hash(tic)))
    return result


def proportional_order(rows):
    """Deterministic proportional interleave; every prefix is a nested cohort."""
    groups = {}
    for row in rows:
        groups.setdefault(row['stratum'], []).append(row)
    for group in groups.values():
        group.sort(key=lambda r: (r['hash'], r['tic_id']))
    used = {s: 0 for s in groups}
    ordered = []
    for i in range(len(rows)):
        stratum = max(
            (s for s in groups if used[s] < len(groups[s])),
            key=lambda s: ((i + 1) * len(groups[s]) / len(rows) - used[s], s))
        ordered.append(groups[stratum][used[stratum]])
        used[stratum] += 1
    return ordered


def choose_level(eligible_count, forecasts, remaining_hours):
    """Largest level with completed input and conservative resource evidence."""
    if not math.isfinite(remaining_hours) or remaining_hours < 0:
        raise ValueError('Invalid remaining cumulative queue allowance')
    by_size = {}
    for row in forecasts:
        check_metadata_only(row)
        size = int(row['hosts'])
        if size in by_size:
            raise ValueError('Duplicate resource level')
        by_size[size] = row
    for hosts, planet_hosts, cases in LEVELS:
        forecast = by_size.get(hosts)
        if eligible_count < hosts or forecast is None:
            continue
        hours = float(forecast['conservative_total_queue_hours'])
        if not math.isfinite(hours) or hours < 0:
            raise ValueError('Invalid prospective runtime forecast')
        if (hours <= remaining_hours and
                forecast.get('acquisition_fits_cumulative_limit') is True and
                forecast.get('storage_preserves_30GB_floor') is True and
                forecast.get('measured_development_throughput_sha256')):
            return dict(hosts=hosts, planet_hosts=planet_hosts,
                        planet_cases=cases, binary_backgrounds=40,
                        full_qualification_possible=hosts == 300,
                        resource_evidence=dict(forecast))
    return None


def cohort(rows, level, excluded_ids=()):
    """Construct assignments without generating a physical signal or outcome."""
    eligible = audited_rows(rows, excluded_ids)
    ordered = proportional_order(eligible)
    canonical = next((x for x in LEVELS if x[0] == level['hosts']), None)
    if canonical is None or (level['planet_hosts'], level['planet_cases']) != canonical[1:]:
        raise ValueError('Cohort level outside the registered nested design')
    if len(ordered) < level['hosts']:
        raise ValueError('Insufficient verified fresh hosts')
    selected = ordered[:level['hosts']]
    # The mandatory binary backgrounds are identical at every possible level.
    # Planet hosts are the following nested prefix; no host receives both kinds
    # of synthetic signal, while every selected host has a natural control.
    binaries = ordered[:40]
    planets = ordered[40:40 + level['planet_hosts']]
    if not {r['tic_id'] for r in planets} <= {r['tic_id'] for r in selected}:
        raise ValueError('Planet hosts fall outside the selected natural cohort')
    if len(binaries) != 40:
        raise ValueError('Forty distinct binary backgrounds are mandatory')
    assignments = {r['tic_id']: dict(natural=True, planet_injections=0,
                                   binary_class=None) for r in selected}
    for row in planets:
        assignments[row['tic_id']]['planet_injections'] = 7
    for index, row in enumerate(binaries):
        assignments[row['tic_id']]['binary_class'] = (
            'on_target' if index % 2 == 0 else 'diluted')
    population = Counter(r['stratum'] for r in eligible)
    role_sets = dict(natural=selected, planets=planets,
                    on_target=binaries[::2], diluted=binaries[1::2])
    weights = {}
    for role, members in role_sets.items():
        counts = Counter(r['stratum'] for r in members)
        weights[role] = {s: dict(population_hosts=n, selected_hosts=counts[s],
            inclusion_probability=counts[s] / n,
            analysis_weight=n / counts[s] if counts[s] else None,
            represented=bool(counts[s])) for s, n in sorted(population.items())}
    return dict(level=dict(level), supported_population_hosts=len(eligible),
        population_scope='Verified eligible hosts in the frozen acquisition frame; no extrapolation outside that frame',
        sampled_hosts=[dict(row, **assignments[row['tic_id']]) for row in selected],
        role_stratum_weights=weights,
        all_natural_host_ids=[r['tic_id'] for r in selected],
        planet_host_ids=[r['tic_id'] for r in planets],
        binary_host_ids=[r['tic_id'] for r in binaries],
        sampling='Fixed validation-purpose SHA256 order, proportional audited-stratum prefixes; first 40 hosts are the common binary backgrounds, the next 50/100/150 are nested planet hosts; hash ordering is treated as the registered pseudorandom sampling design',
        weight_limits='Conditional finite-frame weights. Unrepresented role/stratum cells have no estimate; weights cannot restore missing coverage.',
        fresh_signals_drawn=False, fresh_outcomes_inspected=False)


def admission_guard(development, owner_active):
    if owner_active:
        raise RuntimeError('Conditional validation requires the prior owner to close')
    finalist = development.get('finalist')
    policies = [p for p in development.get('policies', []) if p.get('policy') == finalist]
    if not finalist or len(policies) != 1 or policies[0].get('eligible') is not True:
        raise RuntimeError('No eligible frozen development finalist')
    if not policies[0].get('criteria') or not all(policies[0]['criteria'].values()):
        raise RuntimeError('Development admission criteria are incomplete or unmet')
    return finalist
