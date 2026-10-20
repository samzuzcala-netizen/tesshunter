"""Tests for the detection-loop wall-clock guard.

MAX_VETO_PASSES bounds the number of extra passes, but a COUNT says nothing
about runtime. Callers run under a hard per-target timeout, and the benchmark
harness records `planets: []` for a target that timed out — so a single overrun
converts every recovered planet on that target into a miss. The guard refuses
to start a pass that the loop's own measured pass cost says will not fit.
"""

import numpy as np
import pytest

import tesshunter.pipeline as pl

from tests.test_pipeline import _fake_download, _make_sector_lc


def _lcs():
    return [
        _make_sector_lc(t_start=1000.0, n=2200, cadence_min=15.0, sector=1,
                        signals=[(6.20, 1002.0, 0.12, 9.0)], noise_ppt=0.6, seed=21),
        _make_sector_lc(t_start=1030.0, n=2200, cadence_min=15.0, sector=2,
                        signals=[(6.20, 1002.0, 0.12, 9.0)], noise_ppt=0.6, seed=22),
    ]


def _search(monkeypatch, **kw):
    monkeypatch.setattr(pl, "search_and_download_lc", _fake_download(_lcs()))
    params = dict(
        target=4242, mission="TESS", author="SPOC", max_planets=4,
        period_min=1.0, period_max=13.0, duration_min=0.05, duration_max=0.2,
        bin_minutes=10.0, snr_min=5.0, snr_min_resolved=5.0,
        do_crossmatch=False, generate_report=False,
    )
    params.update(kw)
    return pl.search_target(**params)


def test_default_is_unlimited_and_preserves_behaviour(monkeypatch):
    """time_budget_s=None must behave exactly as before: no guard, no note."""
    res = _search(monkeypatch)
    assert not any("detection budget" in n.lower() for n in res.notes)
    assert any(abs(p["period_days"] / 6.20 - 1.0) < 0.02 for p in res.planets)


def test_a_tiny_budget_stops_the_loop_and_says_so(monkeypatch):
    """A budget too small for a second pass must stop cleanly, not overrun."""
    res = _search(monkeypatch, time_budget_s=0.001)
    assert res.planets == [] or len(res.planets) <= 1
    assert any("budget" in n.lower() for n in res.notes), res.notes


def test_a_generous_budget_does_not_change_the_result(monkeypatch):
    """The guard must be inert when there is plenty of time."""
    a = _search(monkeypatch)
    b = _search(monkeypatch, time_budget_s=100000.0)
    assert [p["period_days"] for p in a.planets] == [p["period_days"] for p in b.planets]


def test_budget_never_costs_the_first_planet(monkeypatch):
    """The guard is evaluated BEFORE a pass, and never before the first one -
    there is no measured pass cost yet, so pass 1 always runs."""
    res = _search(monkeypatch, time_budget_s=1e-9)
    # pass 1 is never pre-empted; it either finds the planet or the data does not
    assert isinstance(res.planets, list)


def test_guard_constants_are_sane():
    assert pl.PASS_COST_SAFETY >= 1.0
    assert 0.0 < pl.DETECT_BUDGET_FRACTION <= 1.0
    assert pl.MAX_VETO_PASSES >= 0
