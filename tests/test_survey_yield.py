"""Yield-model invariants: contamination policy and the A/B/C class algebra."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tesshunter import occurrence_grids as og
from tesshunter import survey_yield as sy


def _stars(n=6, contam=None, seed=3):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "Tmag": rng.uniform(10.5, 13.5, n),
        "rad": rng.uniform(0.6, 1.3, n),
        "mass": rng.uniform(0.6, 1.2, n),
        "Teff": rng.uniform(4500, 6300, n),
        "contratio": np.full(n, 0.02) if contam is None else np.asarray(contam, float),
        "n_sectors_use": rng.integers(4, 30, n).astype(float),
    })
    return df


# ── contamination: NaN must never silently become zero ───────────────────────
def test_missing_contamination_without_policy_raises():
    stars = _stars(contam=[0.01, np.nan, 0.03, np.nan, 0.0, 0.5])
    cells = sy.occurrence_cells("fgk", "km2020", 100.0)
    with pytest.raises(ValueError, match="contamination"):
        sy.per_star_yield(stars, cells, "stitch")
    with pytest.raises(ValueError, match="contamination"):
        sy.class_yields(stars, cells, cells, contam_fill=None)


def test_explicit_fill_is_applied_and_is_not_the_most_favourable_by_default():
    stars = _stars(contam=[np.nan] * 6)
    cells = sy.occurrence_cells("fgk", "km2020", 100.0)
    y0 = sy.per_star_yield(stars, cells, "stitch", contam_fill=0.0)
    ymed = sy.per_star_yield(stars, cells, "stitch", contam_fill=0.2)
    assert np.all(ymed <= y0) and np.any(ymed < y0)          # dilution can only lower the yield
    fills = sy.contamination_fills(pd.Series([0.0, 0.01, 0.02, 0.05, 0.3, np.nan]))
    assert fills["zero"] == 0.0 and fills["measured_median"] == pytest.approx(0.02)
    assert fills["measured_p90"] >= fills["measured_median"] > fills["zero"]
    assert sy.CONTAMINATION_POLICY["central"] != "zero"


def test_measured_values_are_used_even_when_a_fill_is_given():
    stars = _stars(contam=[0.9, 0.9, 0.9, 0.9, 0.9, 0.9])
    cells = sy.occurrence_cells("fgk", "km2020", 100.0)
    heavy = sy.per_star_yield(stars, cells, "stitch", contam_fill=0.0)
    stars2 = stars.assign(contratio=0.0)
    light = sy.per_star_yield(stars2, cells, "stitch", contam_fill=0.9)
    assert np.all(heavy < light)                             # the fill only touches NaN rows


# ── classes A, B, C are exclusive and exhaustive ──────────────────────────────
@pytest.mark.parametrize("group,model", [("fgk", "km2020"), ("fgk", "legacy_howard_petigura"),
                                         ("m", "dc15_grid"), ("m", "legacy_dc15_classes")])
def test_classes_partition_the_stitched_expectation(group, model):
    if group == "m":
        stars = _stars(contam=[0.0] * 6).assign(Tmag=np.linspace(13.6, 14.9, 6), rad=np.linspace(0.2, 0.55, 6),
                                                mass=np.linspace(0.18, 0.55, 6), Teff=3400.0)
    else:
        stars = _stars(contam=[0.0] * 6)
    cells50 = sy.occurrence_cells(group, model, 50.0)
    cells100 = sy.occurrence_cells(group, model, 100.0)
    cls = sy.class_yields(stars, cells50, cells100, contam_fill=0.0)
    total = cls["A"] + cls["B"] + cls["C"]
    # A + B + C == stitched SNR>=7.1 expectation for every star (up to the clipping at zero)
    assert np.allclose(total, np.maximum(cls["stitched_snr7"], cls["A"]), rtol=1e-9, atol=1e-12)
    # B excludes A: A + B == stitched SNR>=9 (when the stitch beats the single sector)
    assert np.allclose(cls["A"] + cls["B"], np.maximum(cls["stitched_snr9"], cls["A"]), rtol=1e-9, atol=1e-12)
    assert np.all(cls["B"] >= 0) and np.all(cls["C"] >= 0)
    # a star with many sectors gains in B and C, never loses in A
    more = stars.assign(n_sectors_use=stars["n_sectors_use"] * 4)
    cls2 = sy.class_yields(more, cells50, cells100, contam_fill=0.0)
    assert np.allclose(cls2["A"], cls["A"]) and np.all(cls2["stitched_snr7"] >= cls["stitched_snr7"] - 1e-12)


def test_new_signals_weighting_matches_priors_and_efficiency():
    stars = _stars(contam=[0.0] * 6)
    cells = sy.occurrence_cells("fgk", "km2020", 100.0)
    cls = sy.class_yields(stars, sy.occurrence_cells("fgk", "km2020", 50.0), cells, contam_fill=0.0)
    new = sy.new_signals_per_star(cls, "bright", "mid")
    expect = sum(cls[k] * (1 - sy.PRIOR_COMPLETENESS["bright"][k]["mid"]) * sy.PIPELINE_EFFICIENCY[k] for k in "ABC")
    assert np.allclose(new, expect)


# ── occurrence grids: transcription integrals reproduce the papers ───────────
def test_km2020_grid_reproduces_published_marginals():
    cells = og.km2020_fgk_cells()
    r = og.integrated_rate
    assert r(cells, 0.78125, 50, 2, 2.83) == pytest.approx(0.186, abs=0.002)     # paper: 18.6%
    assert r(cells, 0.78125, 50, 2, 4) == pytest.approx(0.252, abs=0.003)        # paper: 25.2%
    assert r(cells, 0.78125, 50, 1, 2) == pytest.approx(0.162, abs=0.003)        # paper: 16.2%
    assert r(cells, 0.78125, 100, 2, 4) == pytest.approx(0.354, abs=0.003)       # paper: 35.4%
    assert len(cells) == 90 and all(c["rate"] >= 0 for c in cells)


def test_dc15_grid_reproduces_published_cumulatives():
    cells = og.dc15_m_cells(include_adopted_giants=False)
    r = og.integrated_rate
    assert r(cells, 0.5, 50, 1.0, 1.5) == pytest.approx(0.5625, abs=0.002)      # Table 4 / abstract 0.56
    assert r(cells, 0.5, 50, 1.5, 2.0) == pytest.approx(0.46, abs=0.01)         # abstract 0.46
    assert r(cells, 0.5, 200, 1.0, 4.0) == pytest.approx(2.5, abs=0.05)         # abstract 2.5 +/- 0.2
    assert len(cells) == 35


def test_legacy_cells_cover_the_period_range_and_are_nonnegative():
    for group in ("fgk", "m"):
        cells = sy.legacy_cells(group, 100.0)
        assert all(c["rate"] >= 0 for c in cells)
        assert max(c["p_hi"] for c in cells) == 100.0
