"""Fixed-period, fixed-duration two-level box fit, frozen before Part F.

The optimized phase is the exact best positive-depth least-squares partition
among circular window boundaries and their intervening intervals. The standard
error is conditional on the selected window, with a common residual variance.
No correction for phase selection or correlated noise is added to the registered
three-standard-error presence rule.
"""
import math
import numpy as np


def presence(depth, standard_error):
    if not (math.isfinite(depth) and math.isfinite(standard_error) and standard_error > 0):
        return 'OPERATIONAL_UNKNOWN'
    return 'PRESENT' if depth > 0 and depth >= 3*standard_error else 'ABSENT'


def _best_partition(time, flux, period, duration):
    reference = float(np.min(time))
    phase = np.remainder(time-reference, period)
    order = np.argsort(phase, kind='stable')
    phase = phase[order]
    values = flux[order]-np.mean(flux)
    n = len(phase)
    doubled = np.concatenate((phase, phase+period))
    cumulative = np.concatenate(([0.0], np.cumsum(np.tile(values, 2), dtype=np.float64)))
    boundaries = np.unique(np.concatenate((phase, np.remainder(phase-duration, period))))
    next_boundary = np.concatenate((boundaries[1:], boundaries[:1]+period))
    interiors = np.remainder((boundaries+next_boundary)/2, period)
    starts = np.unique(np.concatenate((boundaries, interiors)))
    left = np.searchsorted(doubled, starts, side='left')
    right = np.searchsorted(doubled, starts+duration, side='left')
    inside = right-left
    outside = n-inside
    valid = (inside > 0) & (outside > 0)
    if not np.any(valid):
        raise ValueError('No phase partition contains both in- and out-of-transit samples')
    sums = cumulative[right]-cumulative[left]
    depth = np.zeros(len(starts), dtype=float)
    total = float(np.sum(values))
    depth[valid] = (total-sums[valid])/outside[valid]-sums[valid]/inside[valid]
    score = np.full(len(starts), -np.inf)
    score[valid] = np.maximum(depth[valid], 0)**2/(1/inside[valid]+1/outside[valid])
    # Sorted phase starts and first argmax are the prospective stable tie rule.
    best = int(np.argmax(score))
    mask = np.zeros(n, dtype=bool)
    mask[order[np.arange(left[best], right[best]) % n]] = True
    epoch = reference + float((starts[best]+duration/2) % period)
    return mask, epoch, float(starts[best]), int(len(starts))


def fit_box(time, flux, period_days, duration_days, cadence_days, epoch_btjd=None):
    time, flux = np.asarray(time, dtype=float), np.asarray(flux, dtype=float)
    if time.ndim != 1 or flux.ndim != 1 or time.shape != flux.shape:
        raise ValueError('Time and flux must be equal-length vectors')
    good = np.isfinite(time) & np.isfinite(flux)
    time, flux = time[good], flux[good]
    if len(time) < 3:
        raise ValueError('Insufficient finite samples for two fitted levels')
    numbers = (period_days, duration_days, cadence_days)
    if not all(math.isfinite(x) and x > 0 for x in numbers):
        raise ValueError('Period, duration and measured cadence must be finite and positive')
    duration = max(float(duration_days), float(cadence_days))
    if duration >= period_days:
        raise ValueError('A full-period box cannot identify depth')
    fixed = epoch_btjd is not None
    if fixed:
        if not math.isfinite(epoch_btjd):
            raise ValueError('Nonfinite fixed epoch')
        mask = np.remainder(time-epoch_btjd+duration/2, period_days) < duration
        epoch, start, trials = float(epoch_btjd), None, 1
    else:
        mask, epoch, start, trials = _best_partition(time, flux, period_days, duration)
    ni, no = int(mask.sum()), int((~mask).sum())
    if ni == 0 or no == 0:
        raise ValueError('No measured in- or out-of-transit level')
    inside, outside = float(np.mean(flux[mask])), float(np.mean(flux[~mask]))
    depth = outside-inside
    residuals = flux-np.where(mask, inside, outside)
    sse = float(np.dot(residuals, residuals))
    variance = sse/(len(flux)-2)
    error = math.sqrt(variance*(1/ni+1/no))
    state = presence(depth, error)
    return dict(status='COMPLETE' if state != 'OPERATIONAL_UNKNOWN' else 'OPERATIONAL_UNKNOWN',
                presence=state, period_days=float(period_days), epoch_btjd=epoch,
                epoch_mode='FIXED_CHECKABLE_EPOCH' if fixed else 'BEST_PHASE',
                duration_input_days=float(duration_days), cadence_days=float(cadence_days),
                duration_days=duration, duration_floored=duration_days < cadence_days,
                n_cad=len(flux), n_in=ni, n_out=no, fitted_inside=inside, fitted_outside=outside,
                depth_fraction=depth, depth_standard_error_fraction=error,
                depth_ppm=depth*1e6, depth_standard_error_ppm=error*1e6,
                depth_sigma=depth/error if error > 0 else None,
                residual_variance=variance, residual_degrees_of_freedom=len(flux)-2,
                phase_start_days=start, phase_partitions_evaluated=trials,
                error_model='Unweighted two-level OLS; common residual variance, conditional on selected phase')
