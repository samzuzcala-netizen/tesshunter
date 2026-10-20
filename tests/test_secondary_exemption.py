"""Tests for the radius-aware ultra-hot-Jupiter secondary-eclipse exemption.

WASP-18 b is recovered at a period error of 0.0002% with SNR 733 and is still
labelled "likely false positive": it carries exactly two high-risk flags,
elevated SNR and a detected secondary eclipse, and any two stack to an
automatic FP verdict. But its secondary is 0.07 ppt against an 8.93 ppt
primary — 0.8% — which is thermal emission from a tidally locked gas giant,
not a stellar eclipse.

The exemption must be narrow. The two control tests below are the point: a
genuine EB secondary, and a shallow secondary on a companion too large to be a
planet, must both still flag.
"""

import numpy as np
import lightkurve as lk
import pytest
from astropy.time import Time
from astropy import units as u

from tesshunter.vetting import (
    run_vetting,
    implied_companion_radius_rjup,
    PLANETARY_SECONDARY_MAX_RATIO,
    RADIUS_HIGH_RISK_RJUP,
    VERDICT_FP,
)


def _eclipsing_lc(period, t0, duration, primary_ppt, secondary_ppt,
                  baseline=27.0, cadence_min=2.0, noise_ppt=0.05, seed=4):
    """Primary at phase 0 and a secondary at phase 0.5, in plain BTJD floats."""
    n = int(baseline * 1440.0 / cadence_min)
    t = 1000.0 + np.arange(n) * (cadence_min / 1440.0)
    flux = np.ones(n)
    ph = ((t - t0 + 0.5 * period) % period) - 0.5 * period
    flux[np.abs(ph) <= 0.5 * duration] -= primary_ppt / 1000.0
    ph_sec = ((t - t0 - 0.5 * period + 0.5 * period) % period) - 0.5 * period
    flux[np.abs(ph_sec) <= 0.5 * duration] -= secondary_ppt / 1000.0
    flux += np.random.default_rng(seed).normal(0.0, noise_ppt / 1000.0, n)
    return lk.LightCurve(
        time=Time(t, format="btjd", scale="tdb"),
        flux=flux * u.dimensionless_unscaled,
        flux_err=np.full(n, noise_ppt / 1000.0) * u.dimensionless_unscaled,
    )


# WASP-18 b, as measured in the stored reference run.
W18 = dict(period=0.9414525, t0=1000.4, duration=0.0854,
           primary_ppt=8.93, rstar=1.35, snr=733.0)


def test_wasp18_like_secondary_does_not_auto_veto():
    """The real case: 0.07 ppt secondary on a 1.24 R_Jup companion.

    The flag MUST still be raised - the measurement is real and a reader has to
    see it. What must not happen is the flag stacking with elevated SNR into an
    automatic false-positive verdict.
    """
    r = implied_companion_radius_rjup(W18["primary_ppt"], W18["rstar"])
    assert r is not None and r <= RADIUS_HIGH_RISK_RJUP, r

    lc = _eclipsing_lc(W18["period"], W18["t0"], W18["duration"],
                       W18["primary_ppt"], 0.07)
    res = run_vetting(lc, W18["period"], W18["t0"], W18["duration"],
                      W18["primary_ppt"], n_sectors=2, snr=W18["snr"],
                      stellar_radius_rsun=W18["rstar"])
    assert [f for f in res.high_risk_flags if "secondary" in f.lower()], \
        "the secondary measurement must remain visible"
    assert res.secondary_is_planetary is True
    assert res.verdict != VERDICT_FP, (
        f"verdict={res.verdict} flags_high={res.high_risk_flags}"
    )
    assert any("dayside" in n for n in res.notes)


def test_genuine_eb_secondary_still_auto_vetoes():
    """CONTROL: a secondary 34% of the primary is a stellar eclipse."""
    lc = _eclipsing_lc(W18["period"], W18["t0"], W18["duration"],
                       W18["primary_ppt"], 3.0)
    res = run_vetting(lc, W18["period"], W18["t0"], W18["duration"],
                      W18["primary_ppt"], n_sectors=2, snr=W18["snr"],
                      stellar_radius_rsun=W18["rstar"])
    assert [f for f in res.high_risk_flags if "secondary" in f.lower()]
    assert res.secondary_is_planetary is False
    assert res.verdict == VERDICT_FP


def test_late_m_companion_eb_is_never_called_promising():
    """The adversarial case: radius alone CANNOT separate a gas giant from a
    late-M companion - both are ~1-1.2 R_Jup - so a shallow-secondary EB can
    satisfy the exemption's conditions.

    The design must therefore fail safe: the flag is retained, so such a system
    lands on "ambiguous / manual vetting", never on "promising". An earlier
    design suppressed the flag outright and DID promote this case; this test is
    the regression guard for that.
    """
    lc = _eclipsing_lc(2.7, 1000.6, 0.11, W18["primary_ppt"], 0.05)
    res = run_vetting(lc, 2.7, 1000.6, 0.11, W18["primary_ppt"],
                      n_sectors=2, snr=W18["snr"], stellar_radius_rsun=W18["rstar"])
    assert [f for f in res.high_risk_flags if "secondary" in f.lower()], \
        "the secondary must stay visible so a human can adjudicate"
    assert "promising" not in str(res.verdict).lower(), res.verdict


def test_shallow_secondary_on_an_oversized_companion_still_flags():
    """CONTROL: the exemption is radius-aware, not ratio-only.

    A 30 ppt primary on a 1.35 R_Sun star implies ~2.3 R_Jup — brown-dwarf
    territory — so even a tiny secondary must keep flagging.
    """
    deep = 30.0
    r = implied_companion_radius_rjup(deep, W18["rstar"])
    assert r is not None and r > RADIUS_HIGH_RISK_RJUP, r

    lc = _eclipsing_lc(W18["period"], W18["t0"], W18["duration"], deep, 0.2)
    res = run_vetting(lc, W18["period"], W18["t0"], W18["duration"], deep,
                      n_sectors=2, snr=W18["snr"], stellar_radius_rsun=W18["rstar"])
    assert [f for f in res.high_risk_flags if "secondary" in f.lower()]


def test_exemption_requires_a_known_stellar_radius():
    """With no radius there is no way to tell a planet from a companion."""
    lc = _eclipsing_lc(W18["period"], W18["t0"], W18["duration"],
                       W18["primary_ppt"], 0.07)
    res = run_vetting(lc, W18["period"], W18["t0"], W18["duration"],
                      W18["primary_ppt"], n_sectors=2, snr=W18["snr"],
                      stellar_radius_rsun=None)
    assert [f for f in res.high_risk_flags if "secondary" in f.lower()]


def test_ratio_threshold_is_the_documented_boundary():
    assert 0.0 < PLANETARY_SECONDARY_MAX_RATIO < 1.0
    # WASP-18 b sits an order of magnitude inside it.
    assert (0.07 / W18["primary_ppt"]) < PLANETARY_SECONDARY_MAX_RATIO / 5.0
