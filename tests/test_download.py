"""Tests for download-module dedup, unit-aware normalisation, and provenance.

All tests use synthetic in-memory light curves with fake meta — no network.
"""

import numpy as np
import pytest
import lightkurve as lk
from astropy.time import Time
from astropy import units as u

from tesshunter.download import dedupe_collection, stitch_collection


def _make_lc(
    n=200,
    unit_number=1,
    author="SPOC",
    cadence_s=120.0,
    flux=None,
    flux_err=None,
    flux_unit=u.dimensionless_unscaled,
    t_start=1000.0,
    unit_key="SECTOR",
) -> lk.LightCurve:
    """Helper: build a synthetic LightCurve with fake product meta."""
    dt = cadence_s / 86400.0
    time = Time(t_start + np.arange(n) * dt, format="btjd", scale="tdb")
    if flux is None:
        flux = np.ones(n)
    kwargs = {}
    if flux_err is not None:
        kwargs["flux_err"] = np.asarray(flux_err, dtype=float) * flux_unit
    lc = lk.LightCurve(
        time=time,
        flux=np.asarray(flux, dtype=float) * flux_unit,
        **kwargs,
    )
    lc.meta[unit_key] = unit_number
    if author is not None:
        lc.meta["AUTHOR"] = author
    return lc


# ── dedupe_collection ─────────────────────────────────────────────────────────

def test_dedupe_keeps_one_product_per_unit_by_author_priority():
    """Duplicate sectors collapse to one winner: SPOC > TESS-SPOC > QLP."""
    lcc = lk.LightCurveCollection([
        _make_lc(unit_number=1, author="QLP", cadence_s=1800),
        _make_lc(unit_number=1, author="SPOC", cadence_s=120),
        _make_lc(unit_number=1, author="TESS-SPOC", cadence_s=600),
        _make_lc(unit_number=2, author="QLP", cadence_s=1800, t_start=1030.0),
    ])
    deduped = dedupe_collection(lcc, mission="TESS")
    assert len(deduped) == 2, "One product per distinct unit"
    winners = {lc.meta["SECTOR"]: lc.meta.get("AUTHOR") for lc in deduped}
    assert winners[1] == "SPOC", "SPOC must beat TESS-SPOC and QLP"
    assert winners[2] == "QLP", "Sole product for its unit survives"


def test_dedupe_tolerates_missing_author_meta():
    """A product without AUTHOR meta must not crash and must rank last."""
    lcc = lk.LightCurveCollection([
        _make_lc(unit_number=3, author=None, cadence_s=1800),
        _make_lc(unit_number=3, author="TESS-SPOC", cadence_s=600),
    ])
    deduped = dedupe_collection(lcc, mission="TESS")
    assert len(deduped) == 1
    assert deduped[0].meta.get("AUTHOR") == "TESS-SPOC"


def test_dedupe_max_units_caps_distinct_units_not_products():
    """max_units counts DISTINCT observing units, sorted by unit number."""
    lcc = lk.LightCurveCollection([
        _make_lc(unit_number=1, author="SPOC"),
        _make_lc(unit_number=1, author="QLP", cadence_s=1800),
        _make_lc(unit_number=2, author="QLP", cadence_s=1800, t_start=1030.0),
        _make_lc(unit_number=3, author="SPOC", t_start=1060.0),
        _make_lc(unit_number=4, author="SPOC", t_start=1090.0),
    ])
    deduped = dedupe_collection(lcc, mission="TESS", max_units=2)
    units = [lc.meta["SECTOR"] for lc in deduped]
    assert units == [1, 2], f"First 2 distinct units expected, got {units}"


def test_dedupe_k2_priority():
    """K2 priority: K2 > EVEREST > K2SFF."""
    lcc = lk.LightCurveCollection([
        _make_lc(unit_number=12, author="K2SFF", cadence_s=1800, unit_key="CAMPAIGN"),
        _make_lc(unit_number=12, author="K2", cadence_s=1800, unit_key="CAMPAIGN"),
        _make_lc(unit_number=12, author="EVEREST", cadence_s=1800, unit_key="CAMPAIGN"),
    ])
    deduped = dedupe_collection(lcc, mission="K2")
    assert len(deduped) == 1
    assert deduped[0].meta.get("AUTHOR") == "K2"


def test_stitch_dedupes_duplicate_sectors_by_default():
    """stitch_collection must not double-count cadences from duplicate pipelines."""
    lcc = lk.LightCurveCollection([
        _make_lc(n=300, unit_number=1, author="SPOC", cadence_s=120),
        _make_lc(n=100, unit_number=1, author="QLP", cadence_s=1800),
    ])
    stitched = stitch_collection(lcc)
    assert len(stitched) == 300, "Duplicate sector must be deduplicated, not concatenated"


# ── unit-aware normalisation ──────────────────────────────────────────────────

def test_magnitude_transit_stays_a_dip():
    """A transit in magnitudes (fainter = larger mag) must map to a flux DIP."""
    rng = np.random.default_rng(0)
    n = 400
    mags = np.full(n, 12.0) + rng.normal(0, 0.001, n)
    transit = np.arange(100, 120)
    mags[transit] += 0.011           # ~1% dimming
    lc = _make_lc(n=n, unit_number=5, author="CDIPS", flux=mags, flux_unit=u.mag)
    stitched = stitch_collection(lk.LightCurveCollection([lc]))
    flux = stitched.flux.value
    in_t = np.median(flux[transit])
    out_t = np.median(np.delete(flux, transit))
    assert in_t < out_t, "Magnitude transit must become a flux dip, not a brightening"
    assert in_t < out_t - 0.005, "Dip depth (~1%) must survive conversion"
    assert abs(np.nanmedian(flux) - 1.0) < 0.01, "Converted flux should be ~1.0"


def test_zero_centered_ppm_flux_is_converted():
    """Zero-centered ppm flux becomes 1 + x/1e6, never a divide-by-median."""
    rng = np.random.default_rng(1)
    n = 400
    x = rng.normal(0, 100, n)        # ppm scatter around zero
    transit = np.arange(50, 70)
    x[transit] -= 5000.0             # 5000 ppm dip
    lc = _make_lc(n=n, unit_number=6, author="TASOC", flux=x, flux_unit=u.Unit("ppm"))
    stitched = stitch_collection(lk.LightCurveCollection([lc]))
    flux = stitched.flux.value
    assert abs(np.nanmedian(flux) - 1.0) < 1e-3, "ppm conversion should centre on 1.0"
    assert np.nanstd(flux) < 0.01, "Conversion must not amplify scatter"
    assert np.median(flux[transit]) < 0.996, "5000 ppm dip must be preserved"


def test_zero_centered_unknown_unit_is_skipped_never_divided():
    """Zero-centered flux in an unknown unit must be skipped, not normalised."""
    rng = np.random.default_rng(2)
    n = 400
    x = rng.normal(0, 1e-4, n)       # zero-centered, dimensionless — unit unknown
    bad = _make_lc(n=n, unit_number=7, author="MYSTERY", flux=x)
    good = _make_lc(
        n=250, unit_number=8, author="SPOC", t_start=1200.0,
        flux=1.0 + rng.normal(0, 1e-4, 250),
    )
    stitched = stitch_collection(lk.LightCurveCollection([bad, good]))
    assert len(stitched) == 250, "Zero-centered unknown-unit product must be dropped"
    assert np.nanstd(stitched.flux.value) < 0.01, (
        "Dividing by a near-zero median would have exploded the scatter"
    )
    provenance = stitched.meta["TESSHUNTER_PROVENANCE"]
    assert [p["unit"] for p in provenance] == [8], "Skipped product must not appear in provenance"


# ── flux_err fill ─────────────────────────────────────────────────────────────

def test_missing_flux_err_filled_with_local_not_global_scatter():
    """Missing flux_err must use robust local scatter, not a global std.

    A deep transit inflates the global std by ~an order of magnitude; the
    point-to-point (diff-based) estimate must stay at the true noise level.
    """
    rng = np.random.default_rng(3)
    noise = 5e-4
    flux = 1.0 + rng.normal(0, noise, 500)
    flux[200:300] -= 0.02            # deep transit over 20% of the cadences
    lc = _make_lc(n=500, unit_number=9, author="SPOC", flux=flux)
    stitched = stitch_collection(lk.LightCurveCollection([lc]))
    filled = float(np.median(stitched.flux_err.value))
    global_std = float(np.nanstd(flux))
    assert 0.3 * noise < filled < 3.0 * noise, (
        f"Filled err {filled:.2e} should track the true noise {noise:.0e}"
    )
    assert filled < 0.3 * global_std, (
        f"Filled err {filled:.2e} must not be the global std {global_std:.2e} "
        "(which is inflated by the transit)"
    )


# ── provenance meta ───────────────────────────────────────────────────────────

def test_stitched_meta_records_provenance():
    """Stitched output must record per-product provenance and the unit list."""
    lcc = lk.LightCurveCollection([
        _make_lc(n=300, unit_number=1, author="SPOC", cadence_s=120),
        _make_lc(n=120, unit_number=2, author="QLP", cadence_s=1800, t_start=1030.0),
    ])
    stitched = stitch_collection(lcc)
    assert stitched.meta["SECTOR"] == "multi", "Backward-compat SECTOR flag must remain"
    assert stitched.meta["TESSHUNTER_UNITS"] == [1, 2]
    provenance = stitched.meta["TESSHUNTER_PROVENANCE"]
    assert len(provenance) == 2
    for entry in provenance:
        assert set(entry) == {"unit", "author", "n_cadences", "cadence_s"}
    by_unit = {p["unit"]: p for p in provenance}
    assert by_unit[1]["author"] == "SPOC"
    assert by_unit[1]["n_cadences"] == 300
    assert by_unit[1]["cadence_s"] == pytest.approx(120.0, rel=0.01)
    assert by_unit[2]["author"] == "QLP"
    assert by_unit[2]["cadence_s"] == pytest.approx(1800.0, rel=0.01)
