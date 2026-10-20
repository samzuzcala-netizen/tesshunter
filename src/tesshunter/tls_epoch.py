"""An equivalent native-cadence implementation of TLS 1.32's final epoch scan.

Changing epoch rotates the phase order. Sort once, then verify the rotated ordering at
every trial; ties or floating-point ordering changes fall back to the original stable
sort. The trial epochs, template, score, and first-minimum tie rule are unchanged.

TLS 1.32's flux-derived weights (including its second roll) are deliberately retained:
correcting that upstream behavior here would change the calibrated experiment.
Estimator conventions follow transitleastsquares.stats.final_T0_fit, Michael Hippke,
MIT license (third_party/transitleastsquares.LICENSE).
"""
from __future__ import annotations

from contextlib import contextmanager
import importlib

import numpy as np


@contextmanager
def equivalent_epoch_scan():
    """Temporarily use the equivalent scan in one TLS call; retain unknown TLS versions."""
    from transitleastsquares.version import TLS_VERSIONING
    main = importlib.import_module("transitleastsquares.main")
    original = main.final_T0_fit
    if TLS_VERSIONING == "1.32":
        main.final_T0_fit = final_T0_fit
    try:
        yield
    finally:
        main.final_T0_fit = original


def final_T0_fit(signal, depth, t, y, dy, period, T0_fit_margin, show_progress_bar, verbose):
    from transitleastsquares import tls_constants
    from transitleastsquares.core import fold

    duration = len(signal)
    scale = tls_constants.SIGNAL_DEPTH / (1 - depth)
    signal = 1 - ((1 - signal) / scale)
    size = np.size(y)
    points = size if T0_fit_margin == 0 else int(size / (T0_fit_margin * duration))
    points = min(points, size)
    epochs = np.linspace(start=np.min(t), stop=np.min(t) + period, num=points)
    if verbose:
        print("Searching for best T0 for period", format(period, ".5f"), "days")
    if not len(epochs):
        return 0
    initial = np.argsort(fold(time=t, period=period, T0=epochs[0]), kind="mergesort")
    ordered_t, ordered_y = t[initial], y[initial]
    roll = int(duration / 2) + 1
    baseline = np.ones(len(y[duration:]))
    lowest, best, previous_cut = float("inf"), 0, None
    for epoch in epochs:
        phases = fold(time=ordered_t, period=period, T0=epoch)
        delta = np.diff(phases)
        cyclic = (np.all(delta > 0) or
                  (np.count_nonzero(delta < 0) == 1 and not np.any(delta == 0) and phases[-1] < phases[0]))
        if cyclic:
            cut = (int(np.argmin(phases)) - roll) % size
            if cut == previous_cut:
                continue  # same ordered flux and score; the upstream strict '<' keeps the first epoch
            flux = np.concatenate([ordered_y[cut:], ordered_y[:cut]])
            weight_cut = (cut - roll) % size
            weights = np.concatenate([ordered_y[weight_cut:], ordered_y[:weight_cut]])
            previous_cut = cut
        else:
            order = np.argsort(fold(time=t, period=period, T0=epoch), kind="mergesort")
            flux = y[order]
            flux = np.concatenate([flux[-roll:], flux[:-roll]])
            weights = np.concatenate([flux[-roll:], flux[:-roll]])
            previous_cut = None
        in_transit = np.sum((flux[:duration] - signal) ** 2 / weights[:duration] ** 2)
        out_of_transit = np.sum((flux[duration:] - baseline) ** 2 / weights[duration:] ** 2)
        score = in_transit + out_of_transit
        if score < lowest:
            lowest, best = score, epoch
    return best
