import numpy as np
import pytest

from tesshunter import biweight_precision as guard


@pytest.mark.parametrize("masked", [False, True])
def test_precision_fallback_preserves_wotan_windows_and_normal_values(masked):
    from wotan import flatten
    rng = np.random.default_rng(112)
    t = np.r_[np.arange(700) / 432, 4 + np.arange(800) / 432]
    f = 1 + 0.002 * rng.normal(size=len(t)) + 0.01 * np.sin(t)
    mask = np.abs(t - 0.7) < 0.1 if masked else None
    expected = flatten(t, f, method="biweight", window_length=0.75,
                       break_tolerance=0.5, edge_cutoff=0.0, mask=mask, return_trend=True)
    actual = guard.flatten(t, f, 0.75, 0.5, 0.0, mask)
    np.testing.assert_array_equal(actual[0], expected[0])
    np.testing.assert_array_equal(actual[1], expected[1])
    assert not guard.needs_precision_guard(f)


def test_extreme_two_point_window_converges_at_float_precision():
    # The sparse sector-98 window that stalled TIC 287493127's noise preparation.
    f = np.array([0.9890676736831665, 71412088832.0, 5.2485944452173484e23])
    t = np.array([4034.3362249651004, 4034.3987261302154, 4034.4473381477906])
    assert guard.needs_precision_guard(f)
    flat, trend = guard.flatten(t, f, 0.75, 0.5, 0)
    expected_centre = np.mean(f[:2])
    np.testing.assert_allclose(trend, expected_centre, rtol=2e-15)
    assert np.all(np.isfinite(flat))
