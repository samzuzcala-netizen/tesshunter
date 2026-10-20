"""T1 flagship: end-to-end injection-recovery on gapped, VARIABLE data THROUGH flatten.

A 4 ppt box transit is injected into a light curve with 15 ppt sinusoidal
stellar variability (spot modulation of an active dwarf), one 3.2-day
downlink gap plus four short gaps, at a configurable 2-minute cadence —
all via the extended ``utils.make_synthetic_lightcurve``.

The signal is then recovered through the REAL chain:

* ``preprocess`` (default ``window_days``) → ``bin_lightcurve`` → ``run_bls``
  recovers the injected period within 2%;
* ``pipeline.search_target`` (monkeypatched download) recovers period within
  2% AND depth within 35% — the two-pass flatten (defect P4) masks the
  candidate before the second trend fit so the depth survives detrending.

On the SHIPPED code this test would have FAILED: flatten was dead (lightkurve
silently median-subtracted every gap-bounded segment with the old 13.5-day
window), so the 15 ppt variability swamped the 4 ppt transit.  The no-flatten
control below reproduces that failure mode explicitly.

All tests are deterministic (fixed seeds) and network-free.
"""

import numpy as np
import lightkurve as lk
import pytest
from astropy.time import Time
from astropy import units as u

import tesshunter.pipeline as pl
from tesshunter.utils import make_synthetic_lightcurve
from tesshunter.preprocessing import preprocess, bin_lightcurve
from tesshunter.bls_search import run_bls


# ── Injection parameters ──────────────────────────────────────────────────────

INJ_PERIOD = 4.37    # days
INJ_DEPTH = 4.0      # ppt
INJ_DUR = 0.12       # days
INJ_T0 = 1.3         # days (BTJD 2457001.3 after conversion)

VAR_AMP_PPT = 15.0   # 1.5% spot modulation — typical active dwarf, ~4× depth
VAR_PERIOD = 6.3     # days — rotation period, incommensurate with 4.37 d
VAR_PHASE = 0.7      # radians

#: One multi-day downlink gap plus four short (0.3–0.4 d) gaps.
GAPS = [
    (12.4, 15.6),    # 3.2-day downlink gap
    (5.9, 6.3),
    (9.7, 10.0),
    (19.2, 19.6),
    (23.5, 23.8),
]


def _gapped_variable_df():
    """The flagship data set: gapped, variable, 2-min cadence, 27-d baseline."""
    return make_synthetic_lightcurve(
        baseline_days=27.0,
        period_days=INJ_PERIOD,
        depth_ppt=INJ_DEPTH,
        duration_days=INJ_DUR,
        t0=INJ_T0,
        noise_ppt=0.8,
        seed=2026,
        cadence_minutes=2.0,
        gaps=GAPS,
        variability_amplitude_ppt=VAR_AMP_PPT,
        variability_period_days=VAR_PERIOD,
        variability_phase=VAR_PHASE,
    )


def _to_lc(df, sector=1, author="SPOC") -> lk.LightCurve:
    lc = lk.LightCurve(
        time=Time(df["time"].values + 2457000, format="btjd", scale="tdb"),
        flux=df["flux"].values * u.dimensionless_unscaled,
        flux_err=df["flux_err"].values * u.dimensionless_unscaled,
    )
    lc.meta["SECTOR"] = sector
    lc.meta["AUTHOR"] = author
    return lc


# ── make_synthetic_lightcurve extension: new kwargs behave as documented ──────

def test_synthetic_defaults_bitwise_unchanged():
    """New kwargs at their defaults reproduce the ORIGINAL algorithm exactly.

    Guard for every existing test that calls make_synthetic_lightcurve: the
    extension must not perturb the time grid or the seeded RNG stream.
    """
    df = make_synthetic_lightcurve()   # all defaults

    # Reimplementation of the pre-extension algorithm, verbatim:
    rng = np.random.default_rng(42)
    t = np.linspace(0.0, 27.0, 1000)
    flux = np.ones(1000)
    phase = ((t - 1.0) % 3.5) / 3.5
    half_dur = 0.1 / 3.5 / 2.0
    flux[(phase < half_dur) | (phase > 1.0 - half_dur)] -= 5.0 / 1000.0
    flux += rng.normal(0.0, 1.0 / 1000.0, 1000)

    assert np.array_equal(df["time"].values, t)
    assert np.array_equal(df["flux"].values, flux)
    assert np.array_equal(df["flux_err"].values, np.full(1000, 1.0 / 1000.0))

    # Passing the new kwargs explicitly at their defaults changes nothing.
    df2 = make_synthetic_lightcurve(
        cadence_minutes=None, gaps=None, variability_amplitude_ppt=0.0,
        variability_period_days=3.0, variability_phase=0.0,
    )
    assert df.equals(df2)


def test_synthetic_cadence_minutes_sets_uniform_grid():
    df = make_synthetic_lightcurve(cadence_minutes=10.0, baseline_days=5.0)
    t = df["time"].values
    assert t[0] == 0.0
    assert t.max() < 5.0
    assert np.allclose(np.diff(t), 10.0 / 1440.0)


def test_synthetic_gaps_remove_time_windows():
    df = _gapped_variable_df()
    t = df["time"].values
    for gap_start, gap_end in GAPS:
        assert not np.any((t >= gap_start) & (t < gap_end)), (
            f"cadences remain inside gap ({gap_start}, {gap_end})"
        )
    # The multi-day gap must survive as an actual >3-day hole in the sampling
    assert np.max(np.diff(t)) > 3.0
    # ...and several short gaps (>10 min) must exist besides it
    assert np.sum(np.diff(t) > 0.1) >= len(GAPS)


def test_synthetic_variability_is_exact_sinusoid():
    """With zero noise and zero depth the flux is exactly 1 + A·sin(ωt + φ)."""
    df = make_synthetic_lightcurve(
        n_points=500, baseline_days=10.0, depth_ppt=0.0, noise_ppt=0.0,
        variability_amplitude_ppt=10.0, variability_period_days=5.0,
        variability_phase=0.3,
    )
    t = df["time"].values
    expected = 1.0 + 0.010 * np.sin(2.0 * np.pi * t / 5.0 + 0.3)
    assert np.allclose(df["flux"].values, expected, atol=1e-12)


# ── Flagship: full pipeline (search_target) recovery ──────────────────────────

@pytest.fixture(scope="module")
def flagship_result():
    """One shared search_target run on the gapped, variable data set."""
    lc = _to_lc(_gapped_variable_df())

    def _download(*args, **kwargs):
        lcc = lk.LightCurveCollection([lc])
        lcc.tesshunter_events = []
        return lcc

    mp = pytest.MonkeyPatch()
    mp.setattr(pl, "search_and_download_lc", _download)
    try:
        res = pl.search_target(
            target=424242,
            mission="TESS",
            author="SPOC",
            period_min=1.0,
            period_max=8.0,
            duration_min=0.04,
            duration_max=0.3,
            max_planets=1,
            bin_minutes=10.0,
            top_n=5,
            min_transits=2,
            mask_width_factor=3.0,
            stellar_radius_rsun=0.95,
        )
    finally:
        mp.undo()
    return res


def test_flagship_recovers_period_and_depth_through_flatten(flagship_result):
    """Injected period within 2% AND depth within 35%, through real flatten.

    This is the test that would have FAILED on the shipped code: with the
    dead flatten the 15 ppt variability swamps the 4 ppt transit (see the
    no-flatten control below), and without the two-pass masked re-flatten
    the transit is partially absorbed into the trend, diluting the depth
    far beyond 35%.
    """
    res = flagship_result

    # Flatten really ran — and the P4 two-pass masked re-flatten kicked in.
    assert res.prep["flattened"] is True
    assert res.prep["two_pass_flatten"] is True
    assert res.prep["two_pass_candidate"] is not None

    assert len(res.planets) == 1, (
        f"expected exactly one accepted planet, got {res.planets}"
    )
    planet = res.planets[0]

    period_err = abs(planet["period_days"] / INJ_PERIOD - 1.0)
    assert period_err < 0.02, (
        f"period {planet['period_days']:.4f} d not within 2% of "
        f"{INJ_PERIOD} d (err {100 * period_err:.2f}%)"
    )
    depth_err = abs(planet["depth_ppt"] / INJ_DEPTH - 1.0)
    assert depth_err < 0.35, (
        f"depth {planet['depth_ppt']:.2f} ppt not within 35% of "
        f"{INJ_DEPTH} ppt (err {100 * depth_err:.1f}%)"
    )

    # Honest multi-transit accounting (>= 2-transit rule satisfied honestly)
    assert planet["n_transits_observed"] >= 2
    assert planet["single_event"] is False

    # Per-planet vetting ran and produced a real verdict
    assert len(res.vetting) == 1
    assert isinstance(planet["verdict"], str) and planet["verdict"]
    assert planet["verdict"] != "vetting error"


# ── Direct chain: preprocess (default window) → bin → run_bls ─────────────────

def test_direct_chain_recovers_period_through_flatten():
    """preprocess(window_days default) → bin → run_bls finds the period at rank 1."""
    lc = _to_lc(_gapped_variable_df())

    cleaned, rec = preprocess(lc, sigma=4.0, do_flatten=True)
    assert rec.flattened is True, "flatten must succeed on the gapped, variable LC"
    # Window math sanity: ~1-day default window, expressed in days
    assert rec.effective_window_days is not None
    assert 0.5 <= rec.effective_window_days <= 1.5

    binned = bin_lightcurve(cleaned, bin_minutes=10.0)
    assert len(binned) < len(cleaned), "binning must reduce the cadence count"

    _, _, cands = run_bls(
        binned, period_min=1.0, period_max=8.0,
        duration_min=0.04, duration_max=0.3, top_n=5,
    )
    assert not cands.empty
    top = cands.iloc[0]
    period_err = abs(top["period_days"] / INJ_PERIOD - 1.0)
    assert period_err < 0.02, (
        f"rank-1 period {top['period_days']:.4f} d not within 2% of "
        f"{INJ_PERIOD} d after detrending (err {100 * period_err:.2f}%)"
    )
    assert top["snr"] > 10
    assert int(top["n_transits_observed"]) >= 2
    assert not bool(top["single_event"])


def test_no_flatten_control_variability_swamps_transit():
    """Control proving the flagship dies without detrending (shipped behaviour).

    The shipped pipeline never actually flattened (dead flatten, defect P1/P2),
    so the search operated on data like this: the 15 ppt variability dips
    outrank the 4 ppt transit and the injected period is NOT recovered.
    """
    lc = _to_lc(_gapped_variable_df())

    cleaned, rec = preprocess(lc, sigma=4.0, do_flatten=False)
    assert rec.flattened is False

    binned = bin_lightcurve(cleaned, bin_minutes=10.0)
    _, _, cands = run_bls(
        binned, period_min=1.0, period_max=8.0,
        duration_min=0.04, duration_max=0.3, top_n=5,
    )
    assert not cands.empty
    top = cands.iloc[0]
    period_err = abs(top["period_days"] / INJ_PERIOD - 1.0)
    depth_err = abs(top["depth_ppt"] / INJ_DEPTH - 1.0)
    assert not (period_err < 0.02 and depth_err < 0.35), (
        "Without flatten the variability must swamp the transit — yet the "
        f"injected signal was recovered (P={top['period_days']:.4f} d, "
        f"depth={top['depth_ppt']:.2f} ppt). The flagship test would NOT "
        "have failed on the shipped (dead-flatten) code."
    )
