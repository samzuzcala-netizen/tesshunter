"""Tests for detection gates 6 (ratio-1 ringing veto) and 7 (railed duration).

Both gates block a candidate at ACCEPTANCE time inside ``_detect_planets``,
which is the only place that can move the false-positive count — vetting runs
after detection and only attaches labels.

The adversarial cases these must survive:
  * gate 6 must NOT suppress harmonics, because real systems are resonant
    (TOI-270 d/c = 2.010, L 98-59 d/c = 2.019 in the dev set alone);
  * gate 7 must NOT reject a genuinely short transit that the cadence resolves,
    only one pinned against an unresolvable grid floor.
"""

import numpy as np
import pytest

import tesshunter.pipeline as pl

from tests.test_pipeline import _fake_download, _make_sector_lc


# ── gate 6: ratio-1 neighbourhood veto ────────────────────────────────────────

def _accepted(*periods):
    return [{"planet_num": i + 1, "period_days": p} for i, p in enumerate(periods)]


def test_ringing_neighbour_flags_near_duplicate():
    """The real TOI-270 case: 6.7202 d accepted after 6.7219 d, 0.03% apart."""
    hit = pl._ringing_neighbour(6.7202, _accepted(6.7219))
    assert hit is not None and hit["planet_num"] == 1


def test_ringing_neighbour_flags_toi700_ringing():
    """TOI-700's two FPs sit 2.68% and 3.54% from accepted c at 16.0514 d."""
    assert pl._ringing_neighbour(15.6216, _accepted(16.0514)) is not None
    assert pl._ringing_neighbour(15.4829, _accepted(16.0514)) is not None


@pytest.mark.parametrize("ratio", [2.010, 2.019, 2.025, 2.890, 3.050, 0.497])
def test_ringing_neighbour_never_flags_resonant_harmonics(ratio):
    """REGRESSION GUARD: harmonics of an accepted period must survive.

    These ratios are measured from real dev-set systems. Flagging any of them
    would delete a currently-recovered planet (TOI-270 d, L 98-59 d).
    """
    accepted_p = 5.6605
    assert pl._ringing_neighbour(accepted_p * ratio, _accepted(accepted_p)) is None


def test_ringing_neighbour_boundary_is_the_documented_tolerance():
    p = 10.0
    inside = p * (1.0 + pl.RINGING_PERIOD_TOL * 0.99)
    outside = p * (1.0 + pl.RINGING_PERIOD_TOL * 1.01)
    assert pl._ringing_neighbour(inside, _accepted(p)) is not None
    assert pl._ringing_neighbour(outside, _accepted(p)) is None


def test_ringing_neighbour_empty_and_degenerate_inputs():
    assert pl._ringing_neighbour(5.0, []) is None
    assert pl._ringing_neighbour(5.0, [{"planet_num": 1, "period_days": 0.0}]) is None
    assert pl._ringing_neighbour(5.0, [{"planet_num": 1}]) is None


# ── gate 7: railed duration ───────────────────────────────────────────────────

CAD_10MIN = 10.0 / 1440.0        # 0.006944 d


def test_duration_railed_when_floor_is_unresolvable():
    """The real TRAPPIST-1 case: duration_min 0.01 d < 2 x 10-min cadence."""
    assert pl._duration_is_railed(0.01, 0.01, CAD_10MIN) is True


def test_duration_not_railed_when_floor_is_resolvable():
    """LHS 3844's duration_min of 0.008 d is below the rail check's reach only
    if unresolvable; with a fine cadence the floor is real and must be kept."""
    fine = 1.0 / 1440.0          # 1-min cadence -> 0.008 d is ~11 cadences
    assert pl._duration_is_railed(0.008, 0.008, fine) is False


def test_duration_not_railed_when_fit_is_above_the_floor():
    """LHS 3844 b truly fits at 0.01973 d against a 0.008 d floor."""
    assert pl._duration_is_railed(0.01973, 0.008, CAD_10MIN) is False


def test_duration_railed_degenerate_inputs():
    assert pl._duration_is_railed(0.01, 0.01, 0.0) is False
    assert pl._duration_is_railed(0.01, 0.0, CAD_10MIN) is False


# ── integration: identical data, gate toggled ─────────────────────────────────

def _ringing_lcs():
    """Two sectors carrying one strong transit; masking it leaves residuals."""
    return [
        _make_sector_lc(t_start=1000.0, n=2600, cadence_min=15.0, sector=1,
                        signals=[(6.20, 1002.0, 0.12, 9.0)], noise_ppt=0.6, seed=11),
        _make_sector_lc(t_start=1030.0, n=2600, cadence_min=15.0, sector=2,
                        signals=[(6.20, 1002.0, 0.12, 9.0)], noise_ppt=0.6, seed=12),
    ]


def test_gate6_does_not_lose_the_real_planet(monkeypatch):
    """Turning gate 6 on must not cost the genuine detection."""
    monkeypatch.setattr(pl, "search_and_download_lc", _fake_download(_ringing_lcs()))
    res = pl.search_target(
        target=12345, mission="TESS", author="SPOC", max_planets=3,
        period_min=1.0, period_max=13.0, duration_min=0.05, duration_max=0.2,
        bin_minutes=10.0, snr_min=5.0, snr_min_resolved=5.0,
        do_crossmatch=False, generate_report=False,
    )
    periods = [p["period_days"] for p in res.planets]
    assert any(abs(p / 6.20 - 1.0) < 0.02 for p in periods), periods


def test_gate6_blocks_a_ratio1_neighbour_of_an_accepted_planet(monkeypatch):
    """No two accepted planets may sit within RINGING_PERIOD_TOL of each other."""
    monkeypatch.setattr(pl, "search_and_download_lc", _fake_download(_ringing_lcs()))
    res = pl.search_target(
        target=12345, mission="TESS", author="SPOC", max_planets=4,
        period_min=1.0, period_max=13.0, duration_min=0.05, duration_max=0.2,
        bin_minutes=10.0, snr_min=5.0, snr_min_resolved=5.0,
        do_crossmatch=False, generate_report=False,
    )
    periods = [p["period_days"] for p in res.planets]
    for i, a in enumerate(periods):
        for b in periods[i + 1:]:
            assert abs(b / a - 1.0) > pl.RINGING_PERIOD_TOL, (
                f"accepted two candidates within the ringing tolerance: {a}, {b}"
            )
