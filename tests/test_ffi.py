"""FFI product ingestion (tesshunter.ffi): per-author flux columns, the QLP
low-precision bit, segment-edge trimming, per-product binning to a common
cadence, and stitching with provenance. Synthetic products only; no network.
Time frame: plain BTJD.
"""

import numpy as np
import lightkurve as lk
import pytest
from astropy import units as u
from astropy.time import Time

from tesshunter import ffi


def _qlp_product(sector, t0=1000.0, n=1300, cadence_min=30.0, low_precision_every=7,
                 dip_at=None, seed=0):
    """A QLP-like product: dimensionless sap/kspsap columns, quality bits."""
    rng = np.random.default_rng(seed)
    t = t0 + np.arange(n) * cadence_min / 1440.0
    sap = 1.0 + rng.normal(0, 5e-4, n) + 0.004 * np.sin(2 * np.pi * t / 3.0)
    ksp = 1.0 + rng.normal(0, 5e-4, n)
    if dip_at is not None:
        sap[np.abs(t - dip_at) < 0.05] -= 0.01
        ksp[np.abs(t - dip_at) < 0.05] -= 0.01
    err = np.full(n, 5e-4)
    quality = np.zeros(n, dtype=int)
    bit = ffi.QLP_LOW_PRECISION_BIT_S56_PLUS if sector >= 56 else ffi.QLP_LOW_PRECISION_BIT_S1_55
    quality[::low_precision_every] = bit
    lc = lk.LightCurve(time=Time(t, format="btjd", scale="tdb"),
                       flux=sap * u.dimensionless_unscaled,
                       flux_err=err * u.dimensionless_unscaled)
    lc["sap_flux"] = sap * u.dimensionless_unscaled
    det = "det_flux" if sector >= 56 else "kspsap_flux"
    lc[det] = ksp * u.dimensionless_unscaled
    lc[det + "_err"] = err * u.dimensionless_unscaled
    lc["quality"] = quality
    lc.meta["SECTOR"] = sector
    lc.meta["AUTHOR"] = "QLP"
    lc.meta["FLUX_ORIGIN"] = "sap_flux"
    return lc


def _spoc_like_product(sector, author, t0=1000.0, n=19440, cadence_min=2.0, seed=1):
    rng = np.random.default_rng(seed)
    t = t0 + np.arange(n) * cadence_min / 1440.0
    pdc = 6000.0 * (1.0 + rng.normal(0, 1e-3, n))
    lc = lk.LightCurve(time=Time(t, format="btjd", scale="tdb"),
                       flux=pdc * u.electron / u.s,
                       flux_err=np.full(n, 6.0) * u.electron / u.s)
    lc["pdcsap_flux"] = pdc * u.electron / u.s
    lc["pdcsap_flux_err"] = np.full(n, 6.0) * u.electron / u.s
    lc["quality"] = np.zeros(n, dtype=int)
    lc.meta["SECTOR"] = sector
    lc.meta["AUTHOR"] = author
    lc.meta["FLUX_ORIGIN"] = "pdcsap_flux"
    return lc


def test_qlp_kspsap_column_and_low_precision_bit_sector_lt_56():
    lc = _qlp_product(sector=12)
    new, prep = ffi.select_flux_column(lc, qlp_flux="kspsap", qlp_low_precision_mask=True)
    assert new is not None
    assert prep.flux_column == "kspsap_flux"
    assert prep.flux_err_column == "kspsap_flux_err"
    n_flagged = int(np.sum(lc["quality"].value != 0))
    assert len(new) == len(lc) - n_flagged
    assert prep.n_after_quality == len(new)
    assert np.array_equal(new.flux.value, lc["kspsap_flux"].value[lc["quality"].value == 0])
    assert new.meta["SECTOR"] == 12 and new.meta["AUTHOR"] == "QLP"


def test_qlp_det_column_sector_ge_56_and_sap_choice():
    lc = _qlp_product(sector=61)
    new, prep = ffi.select_flux_column(lc, qlp_flux="kspsap", qlp_low_precision_mask=False)
    assert prep.flux_column == "det_flux" and prep.flux_err_column == "det_flux_err"
    assert len(new) == len(lc)          # mask off: nothing removed
    new2, prep2 = ffi.select_flux_column(lc, qlp_flux="sap", qlp_low_precision_mask=True)
    assert prep2.flux_column == "sap_flux" and prep2.flux_err_column == "det_flux_err"
    assert np.array_equal(new2.flux.value, lc["sap_flux"].value[lc["quality"].value == 0])


def test_non_survey_author_is_dropped_with_note():
    lc = _qlp_product(sector=3)
    lc.meta["AUTHOR"] = "TASOC"
    new, prep = ffi.select_flux_column(lc)
    assert new is None
    assert any("not a survey author" in n for n in prep.notes)


def test_tess_spoc_keeps_pdcsap():
    lc = _spoc_like_product(5, "TESS-SPOC", n=1300, cadence_min=30.0)
    new, prep = ffi.select_flux_column(lc)
    assert new is not None
    assert prep.flux_column == "pdcsap_flux"
    assert np.array_equal(new.flux.value, lc["pdcsap_flux"].value)


def test_trim_segment_edges_removes_edges_and_short_segments():
    t = np.concatenate([
        1000.0 + np.arange(0, 12.0, 1 / 48),        # 12-day orbit
        1013.5 + np.arange(0, 12.0, 1 / 48),        # 12-day orbit after a 1.5-d gap
        1030.0 + np.arange(0, 0.2, 1 / 48),         # 4.8-hour sliver (< 3 x trim)
    ])
    # a 4-hour quality-mask hole inside the first orbit: NOT a real gap
    hole = (t > 1005.0) & (t < 1005.0 + 4 / 24)
    t = t[~hole]
    lc = lk.LightCurve(time=Time(t, format="btjd", scale="tdb"),
                       flux=np.ones(t.size) * u.dimensionless_unscaled,
                       flux_err=np.full(t.size, 1e-3) * u.dimensionless_unscaled)
    trimmed, n_removed = ffi.trim_segment_edges(lc, trim_minutes=120.0)
    tt = trimmed.time.value
    # Nothing within 2 h of a real edge survives, and the sliver is gone
    assert tt.min() >= 1000.0 + 2 / 24 - 1e-9
    assert not np.any((tt > 1025.5 - 2 / 24 + 1e-9) & (tt < 1030.0 + 1.0))
    assert not np.any(tt >= 1030.0)
    assert not np.any((tt > 1013.5 - 1e-9) & (tt < 1013.5 + 2 / 24 - 1e-9))
    # ...but the cadences either side of the 4-hour hole are kept
    assert np.any((tt > 1005.0 - 1 / 48 - 1e-9) & (tt < 1005.0))
    assert np.any((tt > 1005.0 + 4 / 24) & (tt < 1005.0 + 4 / 24 + 2 / 48))
    assert n_removed == len(lc) - len(trimmed) > 0
    same, zero = ffi.trim_segment_edges(lc, trim_minutes=0.0)
    assert zero == 0 and len(same) == len(lc)


def test_bin_to_cadence_only_bins_finer_products():
    fine = _spoc_like_product(1, "SPOC", n=2000, cadence_min=2.0)
    binned, did = ffi.bin_to_cadence(fine, 30.0)
    assert did is True
    assert len(binned) < len(fine)
    assert abs(np.median(np.diff(binned.time.value)) * 1440 - 30.0) < 1e-6
    coarse = _qlp_product(1, n=500, cadence_min=30.0)
    same, did2 = ffi.bin_to_cadence(coarse, 30.0)
    assert did2 is False and len(same) == len(coarse)
    ten = _qlp_product(30, n=1500, cadence_min=10.0)
    b10, did3 = ffi.bin_to_cadence(ten, 30.0)
    assert did3 is True and len(b10) < len(ten)


def test_prepare_and_stitch_dedupes_bins_and_records_provenance():
    products = [
        _spoc_like_product(1, "SPOC", n=19440, cadence_min=2.0),           # wins sector 1
        _qlp_product(1, n=1300, cadence_min=30.0),                          # loses sector 1
        _qlp_product(2, t0=1030.0, n=1300, cadence_min=30.0),               # sector 2
        _spoc_like_product(30, "TESS-SPOC", t0=1800.0, n=3900, cadence_min=10.0),
    ]
    products[3]["quality"] = np.zeros(len(products[3]), dtype=int)
    tasoc = _qlp_product(2, t0=1030.0, n=1300)
    tasoc.meta["AUTHOR"] = "TASOC"
    products.append(tasoc)
    lcc = lk.LightCurveCollection(products)
    prepared, preps = ffi.prepare_products(
        lcc, qlp_flux="kspsap", qlp_low_precision_mask=True,
        edge_trim_minutes=60.0, target_cadence_minutes=30.0,
    )
    # dedupe keeps SPOC for sector 1 and QLP for sector 2 (TASOC ranks below QLP)
    assert sorted(p.meta["SECTOR"] for p in prepared) == [1, 2, 30]
    authors = {p.meta["SECTOR"]: p.meta["AUTHOR"] for p in prepared}
    assert authors == {1: "SPOC", 2: "QLP", 30: "TESS-SPOC"}
    # every prepared product is at (or coarser than) the common cadence
    for p in prepared:
        cad = np.median(np.diff(p.time.value)) * 1440
        assert cad >= 30.0 - 1e-6
    stitched = ffi.stitch_prepared(prepared, preps)
    assert stitched.meta["TESSHUNTER_UNITS"] == [1, 2, 30]
    ingest = stitched.meta["TESSHUNTER_INGEST"]
    assert len(ingest) == 3               # one record per DEDUPED product
    by_unit = {r["unit"]: r for r in ingest}
    assert by_unit[1]["binned"] is True and by_unit[1]["flux_column"] == "pdcsap_flux"
    assert by_unit[2]["binned"] is False and by_unit[2]["flux_column"] == "kspsap_flux"
    assert by_unit[30]["binned"] is True
    assert all(r["n_after_trim"] <= r["n_after_quality"] for r in ingest)
    f = stitched.flux.value
    assert abs(np.nanmedian(f) - 1.0) < 1e-3
    assert np.all(np.diff(stitched.time.value) > 0)


def test_qlp_flux_choice_rejects_unknown():
    with pytest.raises(ValueError):
        ffi._qlp_columns(5, "pdcsap")


def test_qlp_all_nan_errors_are_filled_and_product_still_bins():
    """Sector >= 56 QLP files can carry an all-NaN det_flux_err; the product
    must still get usable errors and be binned to the common cadence
    (regression: it once reached the stitch unbinned at 200 s)."""
    lc = _qlp_product(sector=95, n=11000, cadence_min=200.0 / 60.0)
    lc["det_flux_err"] = np.full(len(lc), np.nan) * u.dimensionless_unscaled
    lc["flux_err"] = np.full(len(lc), np.nan) * u.dimensionless_unscaled
    new, prep = ffi.select_flux_column(lc, qlp_flux="sap", qlp_low_precision_mask=True)
    assert new is not None
    ev = new.flux_err.value
    assert np.all(np.isfinite(ev)) and np.all(ev > 0)
    assert any("filled with the local point-to-point scatter" in n for n in prep.notes)
    assert prep.flux_err_column.endswith("+local_scatter")
    binned, did = ffi.bin_to_cadence(new, 30.0)
    assert did is True and len(binned) < len(new) / 5


def test_prepare_products_drops_unbinnable_fine_cadence():
    """A fine-cadence product that cannot be binned never enters the stitch."""
    tiny = _spoc_like_product(9, "SPOC", n=40, cadence_min=2.0)      # 80 min of data: < 10 bins
    ok = _qlp_product(10, t0=1100.0, n=1300, cadence_min=30.0)
    prepared, preps = ffi.prepare_products(lk.LightCurveCollection([tiny, ok]), target_cadence_minutes=30.0)
    assert [p.meta["SECTOR"] for p in prepared] == [10]
    assert any("could not be binned" in n for p in preps for n in p.notes)


def test_stitch_prepared_refuses_mixed_cadence():
    a = _qlp_product(1, n=1300, cadence_min=30.0)
    b = _qlp_product(2, t0=1030.0, n=8000, cadence_min=200.0 / 60.0)
    pa, ra = ffi.select_flux_column(a)
    pb, rb = ffi.select_flux_column(b)
    with pytest.raises(ValueError):
        ffi.stitch_prepared([pa, pb], [ra, rb])
