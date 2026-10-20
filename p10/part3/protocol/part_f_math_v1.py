"""Prospective P10.3 matching definitions; no file or catalogue access."""
import math

RATIOS = ((1.0, '1:1'), (2.0, '2:1'), (3.0, '3:1'), (0.5, '1:2'), (1/3, '1:3'))
STRATA = ('INDEPENDENT', 'OVERLAPPING', 'UNION')


def finite(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def row_id(row):
    return f"{row['source_filename']}#{int(row['source_row'])}"


def representative(rows):
    if not rows:
        raise ValueError('Empty family or stratum')
    def key(row):
        snr = finite(row.get('tce_model_snr'))
        return (-(snr if snr is not None else -math.inf),
                row['source_filename'], int(row['source_row']))
    return min(rows, key=key)


def in_band(row):
    period = finite(row.get('tce_period'))
    return period is not None and 0.5 <= period <= 30


def likely(row):
    snr, count = finite(row.get('tce_model_snr')), finite(row.get('tce_num_transits'))
    return snr is not None and snr >= 12 and count is not None and count >= 3


def expected_snr(row, noise):
    depth, duration = finite(row.get('tce_depth')), finite(row.get('tce_duration'))
    period, sigma = finite(row.get('tce_period')), finite(noise.get('sigma'))
    count = finite(noise.get('n_cad'))
    if any(x is None for x in (depth, duration, period, sigma, count)):
        return None
    if depth < 0 or min(duration, period, sigma, count) <= 0:
        return None
    return (depth * 1e-6 / sigma) * math.sqrt(count * (duration/24) / period)


def epoch_rule(row, midpoint):
    period, epoch = finite(row.get('tce_period')), finite(row.get('tce_time0bt'))
    error, duration = finite(row.get('tce_period_err')), finite(row.get('tce_duration'))
    midpoint = finite(midpoint)
    base = dict(checkable=False, mode='PERIOD_ONLY', cycles=None,
                accumulated_period_error_days=None, half_duration_days=None,
                reference_midpoint_btjd=midpoint)
    if any(v is None for v in (period, epoch, error, duration, midpoint)):
        return dict(base, reason='MISSING_OR_NONFINITE_EPHEMERIS_UNCERTAINTY')
    if period <= 0 or duration <= 0 or error < 0:
        return dict(base, reason='NONPHYSICAL_EPHEMERIS_UNCERTAINTY')
    cycles = abs((midpoint-epoch)/period)
    uncertainty, half_duration = error*cycles, duration/48
    checkable = uncertainty < half_duration
    base.update(checkable=checkable, mode='EPOCH_CHECKED' if checkable else 'PERIOD_ONLY',
                cycles=cycles, accumulated_period_error_days=uncertainty,
                half_duration_days=half_duration)
    return dict(base, reason='UNCERTAINTY_SMALL_ENOUGH' if checkable else 'UNCERTAINTY_NOT_SMALL_ENOUGH')


def nearest_cycle(value):
    """Nearest integer, deterministic upper tie, including negative epochs."""
    return math.floor(value + 0.5)


def candidate_match(row, candidate, midpoint):
    period, found = finite(row.get('tce_period')), finite(candidate.get('period_days'))
    if period is None or found is None or period <= 0 or found <= 0:
        return None
    possible = [(abs(found/(period*r)-1), order, r, label)
                for order, (r, label) in enumerate(RATIOS)]
    fraction, _, ratio, label = min(possible)
    if fraction >= 0.01:
        return None
    rule = epoch_rule(row, midpoint)
    answer = dict(candidate_id=candidate['candidate_id'], alias=label, ratio=ratio,
                  exact=ratio == 1, relative_period_error=fraction,
                  epoch=rule, epoch_agrees=None, recovered=True,
                  phase_distance_days=None, phase_modulus_days=None)
    if rule['checkable']:
        epoch, predicted_epoch = finite(row['tce_time0bt']), finite(candidate.get('epoch_btjd'))
        if predicted_epoch is None:
            answer.update(epoch_agrees=False, recovered=False, epoch_failure='MISSING_PREDICTED_EPOCH')
            return answer
        true_transit = epoch + nearest_cycle((midpoint-epoch)/period)*period
        predicted_transit = predicted_epoch + nearest_cycle((true_transit-predicted_epoch)/found)*found
        # The shared fundamental period permits the registered integer aliases:
        # an accepted 2P/3P signal need not contain every TCE transit, and P/2 or
        # P/3 must align with a TCE event. This never changes exact-match credit.
        modulus = period*min(1.0, ratio)
        delta = (predicted_transit-true_transit + modulus/2) % modulus - modulus/2
        distance = abs(delta)
        agrees = distance <= rule['half_duration_days']
        answer.update(epoch_agrees=agrees, recovered=agrees, phase_distance_days=distance,
                      phase_modulus_days=modulus, propagated_tce_transit_btjd=true_transit,
                      propagated_prediction_transit_btjd=predicted_transit)
    return answer


def model_snr_bin(value):
    value = finite(value)
    if value is None:
        return 'UNMEASURED'
    return '<9' if value < 9 else '[9,12)' if value < 12 else '[12,20)' if value < 20 else '>=20'


def expected_snr_bin(value):
    value = finite(value)
    if value is None or value < 0:
        return 'UNMEASURED'
    edges = (0, 7, 10, 15, 20, 30)
    for lo, hi in zip(edges, edges[1:]):
        if value < hi:
            return f'[{lo},{hi})'
    return '>=30'


def period_bin(value):
    value = finite(value)
    if value is None or value <= 0:
        return 'UNMEASURED'
    if value < 0.5:
        return '<0.5'
    if value > 30:
        return '>30'
    for lo, hi in ((0.5, 1), (1, 2), (2, 5), (5, 10), (10, 20)):
        if value < hi:
            return f'[{lo:g},{hi:g})'
    return '[20,30]'
