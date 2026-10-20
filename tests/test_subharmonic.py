"""Tests for subharmonic_occupancy() and the descend-to-fundamental step.

This is the highest-risk change in the improvement set: it can move a period,
so a false positive here would CREATE aliases rather than remove them. The
regression guards below are therefore at least as important as the positive
cases.

Ground truth is exact by construction — transits are injected at a known
period, so whether a trial period is a super-harmonic is not a matter of
judgement.
"""

import numpy as np
import lightkurve as lk
import pandas as pd
import pytest
from astropy.time import Time
from astropy import units as u

from tesshunter import bls_search as bs


def _lc(period, depth_ppt=6.0, duration=0.09, t0=1002.0, baseline=60.0,
        cadence_min=10.0, noise_ppt=0.0, seed=3, second=None):
    """Light curve with box transits at `period`. Times are plain BTJD floats,
    so an ephemeris epoch is expressed in the SAME frame as lc.time.value."""
    n = int(baseline * 1440.0 / cadence_min)
    t = 1000.0 + np.arange(n) * (cadence_min / 1440.0)
    flux = np.ones(n)
    for p, t0_, dur, dep in [(period, t0, duration, depth_ppt)] + list(second or []):
        phase = ((t - t0_ + 0.5 * p) % p) - 0.5 * p
        flux[np.abs(phase) <= 0.5 * dur] -= dep / 1000.0
    if noise_ppt:
        flux += np.random.default_rng(seed).normal(0.0, noise_ppt / 1000.0, n)
    return lk.LightCurve(
        time=Time(t, format="btjd", scale="tdb"),
        flux=flux * u.dimensionless_unscaled,
        flux_err=np.full(n, 1e-4) * u.dimensionless_unscaled,
    )


# ── positive cases: the fold really is over-subdivided ────────────────────────

def test_detects_2x_superharmonic():
    """True period 3.36 d; asked about 6.72 d -> must flag m=2."""
    lc = _lc(3.3602)
    flag, weakest = bs.subharmonic_occupancy(lc, 2 * 3.3602, 1002.0, 0.09, 2)
    assert flag is True
    assert weakest > 0.8            # intermediate dip is the same transit


def test_detects_3x_superharmonic():
    lc = _lc(3.7959)
    flag, weakest = bs.subharmonic_occupancy(lc, 3 * 3.7959, 1002.0, 0.09, 3)
    assert flag is True
    assert weakest > 0.8


# ── REGRESSION GUARDS: must not fire on a genuine fundamental ─────────────────

@pytest.mark.parametrize("m", [2, 3])
def test_does_not_fire_on_the_true_fundamental(m):
    """The critical guard. Folding at the TRUE period leaves the intermediate
    phases empty, so descending would invent a spurious P/2 or P/3."""
    lc = _lc(3.3602)
    flag, _ = bs.subharmonic_occupancy(lc, 3.3602, 1002.0, 0.09, m)
    assert flag is False


@pytest.mark.parametrize("m", [2, 3])
def test_does_not_fire_with_realistic_noise(m):
    lc = _lc(5.6605, depth_ppt=3.4, noise_ppt=1.0)
    flag, _ = bs.subharmonic_occupancy(lc, 5.6605, 1002.0, 0.09, m)
    assert flag is False


def test_does_not_fire_on_a_near_resonant_sibling():
    """TOI-270 c (5.6605 d) and d (11.3797 d) are close to 2:1 but NOT exact.

    Folding d at its own period must not be called a super-harmonic just
    because a sibling planet exists near half that period - the sibling drifts
    across the fold instead of sitting at phase 0.5.
    """
    lc = _lc(11.3797, depth_ppt=2.9, duration=0.085, t0=1003.0,
             second=[(5.6605, 1001.0, 0.069, 3.4)])
    flag, _ = bs.subharmonic_occupancy(lc, 11.3797, 1003.0, 0.085, 2)
    assert flag is False


def test_degenerate_inputs_are_safe():
    lc = _lc(3.3602)
    assert bs.subharmonic_occupancy(lc, 6.72, 1002.0, 0.09, 1)[0] is False
    # duration so wide the k/m windows would overlap -> test is meaningless
    assert bs.subharmonic_occupancy(lc, 6.72, 1002.0, 5.0, 2)[0] is False


# ── the descent step itself ───────────────────────────────────────────────────

def _trials(*rows):
    """rows are (harmonic_label, period_days, composite_score, n_dip)."""
    return pd.DataFrame([
        {"harmonic_label": lbl, "period_days": p, "epoch_btjd": 1002.0,
         "duration_days": 0.09, "composite_score": score, "n_dip": ndip}
        for lbl, p, score, ndip in rows
    ])


def test_descend_swaps_in_the_fundamental():
    """The TOI-270 shape: the 2P row wins on composite but explains 6 events
    where the fundamental explains 12."""
    lc = _lc(3.3602)
    trial_df = _trials(("2P", 6.7204, 50.0, 6), ("P", 3.3602, 40.0, 12))
    best = trial_df.iloc[0]
    out = bs._descend_to_fundamental(lc, best, trial_df, period_min=1.0)
    assert out["harmonic_label"] == "P"
    assert abs(out["period_days"] / 3.3602 - 1.0) < 1e-6


def test_descend_is_a_noop_on_a_true_fundamental():
    lc = _lc(3.3602)
    trial_df = _trials(("P", 3.3602, 50.0, 12), ("P/2", 1.6801, 10.0, 12))
    best = trial_df.iloc[0]
    out = bs._descend_to_fundamental(lc, best, trial_df, period_min=1.0)
    assert out["harmonic_label"] == "P"


def test_descend_refused_when_the_subharmonic_explains_no_more_events():
    """THE KEY GUARD: a spurious P/2 redistributes the same transits across
    alternating epochs, so its n_dip does not rise. Without this condition the
    geometric test alone could move a correct period."""
    lc = _lc(3.3602)
    # occupancy would pass (dips really are at every half phase of 6.72), but
    # the event count does not increase
    trial_df = _trials(("2P", 6.7204, 50.0, 9), ("P", 3.3602, 40.0, 9))
    best = trial_df.iloc[0]
    out = bs._descend_to_fundamental(lc, best, trial_df, period_min=1.0)
    assert out["harmonic_label"] == "2P"


def test_descend_respects_period_min():
    """Never descend below the searched range."""
    lc = _lc(3.3602)
    trial_df = _trials(("2P", 6.7204, 50.0, 6), ("P", 3.3602, 40.0, 12))
    best = trial_df.iloc[0]
    out = bs._descend_to_fundamental(lc, best, trial_df, period_min=5.0)
    assert out["harmonic_label"] == "2P"


def test_descend_needs_a_scored_trial_row_to_move_to():
    """No row at P/m -> stay put rather than invent a period."""
    lc = _lc(3.3602)
    trial_df = _trials(("2P", 6.7204, 50.0, 6))
    best = trial_df.iloc[0]
    out = bs._descend_to_fundamental(lc, best, trial_df, period_min=1.0)
    assert out["harmonic_label"] == "2P"


# ── end to end through the resolver ───────────────────────────────────────────

def test_resolver_returns_the_fundamental_not_the_2x_alias():
    """The TOI-270 b failure mode, end to end."""
    true_p = 3.3602
    lc = _lc(true_p, depth_ppt=4.0, duration=0.06, noise_ppt=0.3)
    _, _, cands = bs.run_bls(lc, period_min=1.0, period_max=13.0,
                             duration_min=0.02, duration_max=0.15, top_n=3)
    assert not cands.empty
    resolved, trials = bs.resolve_aliases_for_candidate(
        lc, cands.iloc[0], period_min=1.0, period_max=13.0,
        duration_min=0.02, duration_max=0.15,
    )
    err = abs(float(resolved["period_days"]) / true_p - 1.0)
    assert err < 0.02, (
        f"resolver returned {resolved['period_days']:.5f} d "
        f"({resolved['harmonic_label']}) for a true period of {true_p} d"
    )
