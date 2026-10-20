"""Unit tests for ``tesshunter.secondary``: the full-phase secondary scan and its gate.

The scan exists because the prompt-6 funnel and the P4 packets both looked only
at phase 0.5 and missed a 52-sigma secondary at phase 0.605.  These tests pin
the three outcomes it must separate: a quiet scan with no second dip, a quiet
scan with one deep second dip (a stellar companion, which fails the gate), and a
noisy scan with dips everywhere (variability, which flags and claims nothing).

Synthetic light curves in plain BTJD, as in ``tests/test_pipeline.py``.
"""

import numpy as np
import pytest

from tesshunter import audit_rules as R
from tesshunter.secondary import box_depth, phase_scan, planet_secondary_bound, secondary_scan

PERIOD = 10.0
T0 = 1000.0
DUR = 0.2
RSTAR, MSTAR, TEFF = 1.0, 1.0, 5800.0


def _folded(primary_ppt=10.0, secondary_ppt=0.0, secondary_phase=0.6, noise_ppt=0.3,
            n_periods=30, cadence_min=20.0, seed=1, wiggles=()):
    rng = np.random.default_rng(seed)
    dt = cadence_min / 1440.0
    t = np.arange(T0 - 0.5 * PERIOD, T0 + (n_periods - 0.5) * PERIOD, dt)
    f = 1.0 + rng.normal(0, noise_ppt / 1000.0, len(t))
    ph = ((t - T0) / PERIOD) % 1.0

    def _in(p0):
        d = np.abs(((ph - p0 + 0.5) % 1.0) - 0.5) * PERIOD
        return d < DUR / 2

    f[_in(0.0)] -= primary_ppt / 1000.0
    if secondary_ppt:
        f[_in(secondary_phase)] -= secondary_ppt / 1000.0
    for p0, depth in wiggles:
        f[_in(p0)] -= depth / 1000.0
    return t, f


# ── the box measurement ──────────────────────────────────────────────────────

def test_box_depth_measures_an_injected_dip_at_its_phase():
    t, f = _folded(primary_ppt=10.0, noise_ppt=0.2)
    at_dip = box_depth(t, f, 0.0, PERIOD, T0, DUR)
    assert at_dip["depth_ppt"] == pytest.approx(10.0, rel=0.05)
    assert at_dip["sigma"] > 20
    off = box_depth(t, f, 0.35, PERIOD, T0, DUR)
    assert abs(off["depth_ppt"]) < 0.5
    assert abs(off["sigma"]) < 5


def test_box_depth_returns_none_when_there_is_too_little_data():
    t = np.linspace(1000.0, 1000.5, 40)
    assert box_depth(t, np.ones(40), 0.0, PERIOD, T0, DUR) is None


# ── the phase scan ───────────────────────────────────────────────────────────

def test_phase_scan_finds_the_primary_and_a_secondary_and_nothing_else():
    t, f = _folded(primary_ppt=10.0, secondary_ppt=9.0, secondary_phase=0.6, noise_ppt=0.3)
    dips, sig = phase_scan(t, f, PERIOD, T0, DUR)
    assert len(dips) == 2
    phases = sorted(min(d["phase"], 1 - d["phase"]) for d in dips)
    assert phases[0] < 0.02                                   # the primary, at phase ~0
    assert any(abs(d["phase"] - 0.6) < 0.01 for d in dips)
    assert sig.size > 400


def test_phase_scan_finds_nothing_in_a_flat_light_curve():
    rng = np.random.default_rng(4)
    t = np.arange(T0, T0 + 300.0, 20.0 / 1440.0)
    f = 1.0 + rng.normal(0, 3e-4, len(t))
    dips, _ = phase_scan(t, f, PERIOD, T0, DUR)
    assert dips == []


def test_phase_scan_merges_two_grid_points_of_the_same_dip():
    t, f = _folded(primary_ppt=10.0, noise_ppt=0.3)
    dips, _ = phase_scan(t, f, PERIOD, T0, DUR)
    assert len(dips) == 1                                     # not one per 0.002 grid step
    assert min(dips[0]["phase"], 1 - dips[0]["phase"]) < R.SEC_MIN_PHASE_SEPARATION


# ── the period-aware planetary bound ─────────────────────────────────────────

def test_the_planetary_bound_falls_steeply_with_period():
    hot = planet_secondary_bound(2.0, RSTAR, MSTAR, TEFF, 10.0)
    warm = planet_secondary_bound(60.0, RSTAR, MSTAR, TEFF, 10.0)
    assert hot["max_planetary_secondary_ppt"] > 100 * warm["max_planetary_secondary_ppt"]
    assert hot["a_over_rstar"] < warm["a_over_rstar"]
    assert hot["T_day_K"] > warm["T_day_K"]


def test_the_planetary_bound_is_far_below_a_ppt_at_long_period():
    b = planet_secondary_bound(17.5, 1.06, 1.02, 5733.0, 2.64)
    assert b["a_over_rstar"] == pytest.approx(27.0, rel=0.02)
    assert b["max_planetary_secondary_ppt"] < 0.01           # ppt: any ppt-level dip is stellar


def test_the_bound_is_zero_for_a_degenerate_primary_depth():
    assert planet_secondary_bound(10.0, RSTAR, MSTAR, TEFF, 0.0)["max_planetary_secondary_ppt"] == 0.0


# ── the gate ─────────────────────────────────────────────────────────────────

def test_a_transit_with_no_second_dip_gives_a_clean_scan_and_passes_the_gate():
    t, f = _folded(primary_ppt=10.0, secondary_ppt=0.0, noise_ppt=0.3)
    res = secondary_scan(t, f, PERIOD, T0, DUR, RSTAR, MSTAR, TEFF, t, f)
    assert res["n_dips_above_5sigma"] == 1
    assert res["secondaries"] == []
    assert res["gate"] == "PASS"
    assert res["verdict"].startswith("CLEAN")


def test_a_deep_secondary_away_from_phase_half_fails_the_gate():
    t, f = _folded(primary_ppt=10.0, secondary_ppt=9.0, secondary_phase=0.605, noise_ppt=0.3)
    res = secondary_scan(t, f, PERIOD, T0, DUR, RSTAR, MSTAR, TEFF, t, f)
    assert res["gate"] == "FAIL"
    assert res["secondaries"][0]["phase"] == pytest.approx(0.605, abs=0.01)
    assert res["secondary_over_primary_depth"] == pytest.approx(0.9, rel=0.1)
    assert res["secondary_sigma_over_planet_bound"] > R.SEC_GATE_SIGMA_OVER_BOUND
    assert "stellar companion" in res["verdict"]


def test_the_gate_is_measured_in_sap_so_a_correction_artefact_cannot_fail_a_candidate():
    t, f = _folded(primary_ppt=10.0, secondary_ppt=9.0, secondary_phase=0.6, noise_ppt=0.3)
    _, f_sap = _folded(primary_ppt=10.0, secondary_ppt=0.0, noise_ppt=0.3, seed=2)  # SAP: no secondary
    res = secondary_scan(t, f, PERIOD, T0, DUR, RSTAR, MSTAR, TEFF, t, f_sap)
    assert res["gate_measured_in"] == "sap"
    assert res["deepest_secondary_in_sap"]["depth_ppt"] == pytest.approx(0.0, abs=0.5)
    assert res["gate"] == "PASS"


def test_the_gate_falls_back_to_the_detrended_flux_when_no_sap_is_supplied():
    t, f = _folded(primary_ppt=10.0, secondary_ppt=9.0, secondary_phase=0.6, noise_ppt=0.3)
    res = secondary_scan(t, f, PERIOD, T0, DUR, RSTAR, MSTAR, TEFF)
    assert res["gate_measured_in"] == "detrended"
    assert res["deepest_secondary_in_sap"] is None
    assert res["gate"] == "FAIL"


def test_dips_at_many_phases_are_reported_as_variability_and_claim_no_secondary():
    wiggles = [(p, 6.0) for p in (0.12, 0.22, 0.34, 0.46, 0.58, 0.7, 0.82)]
    t, f = _folded(primary_ppt=10.0, noise_ppt=0.3, wiggles=wiggles)
    res = secondary_scan(t, f, PERIOD, T0, DUR, RSTAR, MSTAR, TEFF, t, f)
    assert res["n_dips_above_5sigma"] > R.SEC_MAX_DIPS_BEFORE_VARIABILITY
    assert res["variability_flag"] is True


def test_a_scan_with_no_dip_at_phase_zero_says_so_and_does_not_gate():
    rng = np.random.default_rng(6)
    t = np.arange(T0, T0 + 300.0, 20.0 / 1440.0)
    f = 1.0 + rng.normal(0, 3e-4, len(t))
    res = secondary_scan(t, f, PERIOD, T0, DUR, RSTAR, MSTAR, TEFF, t, f)
    assert res["primary"] is None
    assert res["gate"] == "PASS"
    assert "nothing to interpret" in res["verdict"]


def test_the_record_carries_the_thresholds_that_produced_it():
    t, f = _folded(primary_ppt=10.0, noise_ppt=0.3)
    res = secondary_scan(t, f, PERIOD, T0, DUR, RSTAR, MSTAR, TEFF, t, f)
    th = res["thresholds"]
    assert th["min_sigma"] == R.SEC_MIN_SIGMA
    assert th["gate_sigma_over_bound"] == R.SEC_GATE_SIGMA_OVER_BOUND
    assert th["max_dips_before_variability"] == R.SEC_MAX_DIPS_BEFORE_VARIABILITY
    assert th["albedo"] == R.SEC_ALBEDO
