"""Shared utilities, including synthetic light curve generation for tests."""

from __future__ import annotations

import re
import numpy as np
import pandas as pd
from pathlib import Path


def ensure_dirs(*dirs: Path) -> None:
    """Create directories if they do not exist."""
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def safe_dirname(name: str) -> str:
    """Sanitise a target label so it can be used safely as a directory name.

    Replaces every character that Windows or POSIX path parsers treat as a
    separator or reserved character ( / \\ : * ? " < > | ) with an underscore,
    then strips leading/trailing whitespace and underscores.

    Examples
    --------
    >>> safe_dirname("L 98-59 / TOI-175")
    'L 98-59 _ TOI-175'
    >>> safe_dirname("TIC 440887364")
    'TIC 440887364'
    """
    sanitised = re.sub(r'[/\\:*?"<>|]', "_", name)
    return sanitised.strip()


def make_synthetic_lightcurve(
    n_points: int = 1000,
    baseline_days: float = 27.0,
    period_days: float = 3.5,
    depth_ppt: float = 5.0,
    duration_days: float = 0.1,
    t0: float = 1.0,
    noise_ppt: float = 1.0,
    seed: int = 42,
    cadence_minutes: float | None = None,
    gaps: list[tuple[float, float]] | None = None,
    variability_amplitude_ppt: float = 0.0,
    variability_period_days: float = 3.0,
    variability_phase: float = 0.0,
) -> pd.DataFrame:
    """Return a synthetic light curve with a box-transit signal injected.

    Parameters
    ----------
    n_points:       Number of cadences (ignored when ``cadence_minutes`` is
                    given, which fixes the sampling instead).
    baseline_days:  Total time span in days.
    period_days:    Orbital period of injected signal.
    depth_ppt:      Transit depth in parts per thousand.
    duration_days:  Transit duration in days.
    t0:             Time of first transit mid-point (days).
    noise_ppt:      White noise amplitude in parts per thousand.
    seed:           Random seed for reproducibility.
    cadence_minutes: When given, sample on a uniform grid with this cadence
                    (``np.arange(0, baseline_days, cadence_minutes/1440)``)
                    instead of ``np.linspace(0, baseline_days, n_points)``.
                    Default None keeps the historic linspace behaviour.
    gaps:           Optional list of ``(gap_start_day, gap_end_day)`` windows;
                    cadences with ``gap_start <= t < gap_end`` are removed,
                    emulating downlink / momentum-dump gaps. Default None
                    (no gaps).
    variability_amplitude_ppt: Amplitude of a sinusoidal stellar-variability
                    term added to the flux, in parts per thousand. Default
                    0.0 (no variability — historic behaviour).
    variability_period_days: Period of the variability sinusoid (days).
    variability_phase: Phase offset of the variability sinusoid (radians).

    Notes
    -----
    All new keyword arguments default to values that reproduce the original
    behaviour EXACTLY (identical time grid and identical RNG draws): the
    single ``rng.normal`` noise draw happens after the deterministic transit
    and variability injections, so seeded outputs are unchanged when the new
    options are left at their defaults.

    Returns
    -------
    DataFrame with columns: time, flux, flux_err
    """
    rng = np.random.default_rng(seed)
    if cadence_minutes is not None:
        time = np.arange(0.0, baseline_days, cadence_minutes / 1440.0)
    else:
        time = np.linspace(0.0, baseline_days, n_points)

    # Remove gap windows (downlink / momentum-dump emulation)
    if gaps:
        keep = np.ones(time.size, dtype=bool)
        for gap_start, gap_end in gaps:
            keep &= ~((time >= gap_start) & (time < gap_end))
        time = time[keep]

    n = time.size
    flux = np.ones(n)

    # Inject transits
    depth_frac = depth_ppt / 1000.0
    phase = ((time - t0) % period_days) / period_days  # 0 to 1
    half_dur = duration_days / period_days / 2.0
    in_transit = (phase < half_dur) | (phase > 1.0 - half_dur)
    flux[in_transit] -= depth_frac

    # Sinusoidal stellar variability (deterministic — no RNG draws)
    if variability_amplitude_ppt != 0.0:
        flux += (variability_amplitude_ppt / 1000.0) * np.sin(
            2.0 * np.pi * time / variability_period_days + variability_phase
        )

    # Add white noise
    noise_frac = noise_ppt / 1000.0
    flux += rng.normal(0.0, noise_frac, n)

    flux_err = np.full(n, noise_frac)

    return pd.DataFrame({"time": time, "flux": flux, "flux_err": flux_err})


def phase_fold(time: np.ndarray, period: float, t0: float) -> np.ndarray:
    """Return phase in [-0.5, 0.5] for a given period and epoch."""
    phase = ((time - t0) % period) / period
    phase[phase > 0.5] -= 1.0
    return phase


def ppt_to_fraction(ppt: float) -> float:
    return ppt / 1000.0


def fraction_to_ppt(frac: float) -> float:
    return frac * 1000.0


def estimate_planet_radius(
    depth_frac: float,
    stellar_radius_rsun: float,
) -> float | None:
    """Estimate planet radius in Earth radii from transit depth and stellar radius.

    Uses Rp/Rs = sqrt(depth). Returns None if inputs are invalid.
    """
    if depth_frac <= 0 or stellar_radius_rsun <= 0:
        return None
    rsun_to_rearth = 109.076  # 1 R_sun = 109.076 R_earth
    rp_rs = np.sqrt(depth_frac)
    return rp_rs * stellar_radius_rsun * rsun_to_rearth
