"""K1 change 8: Stage D uses each product's real author and exposure, and Tmag-scaled apertures."""
import numpy as np

import stage_d_packets_k1 as D
import stage_d_pixels_k1 as P


def _arrays(specs, period=7.3, t0=1500.2, dur=0.15):
    t, s = [], []
    for sector, cad, start in specs:
        tt = start + np.arange(0, 25.0, cad / 86400.0)
        t.append(tt); s.append(np.full(tt.size, sector))
    return np.concatenate(t), np.concatenate(s)


def test_fpp_uses_one_class_at_its_real_exposure_600s_vs_1800s():
    prods = [{"sector": 10, "author": "QLP", "cadence_s": 1800.0}, {"sector": 11, "author": "QLP", "cadence_s": 1799.0},
             {"sector": 40, "author": "TESS-SPOC", "cadence_s": 600.0}, {"sector": 41, "author": "TESS-SPOC", "cadence_s": 600.0}]
    t, s = _arrays([(10, 1800, 1500.0), (11, 1800, 1527.4), (40, 600, 2390.6), (41, 600, 2418.0)])
    c = D.fpp_product_class(prods, t, s, 7.3, 1500.2, 0.15)
    assert c["cadence_s"] == 600.0 and c["author"] == "TESS-SPOC" and set(c["sectors"]) <= {40, 41}
    assert c["mask"].sum() == int(np.isin(s, [40, 41]).sum())


def test_fpp_falls_back_to_1800s_when_only_1800s_has_data():
    prods = [{"sector": 10, "author": "QLP", "cadence_s": 1800.0}, {"sector": 11, "author": "QLP", "cadence_s": 1800.0}]
    t, s = _arrays([(10, 1800, 1500.0), (11, 1800, 1527.4)])
    c = D.fpp_product_class(prods, t, s, 7.3, 1500.2, 0.15)
    assert c["cadence_s"] == 1800.0 and c["author"] == "QLP"


def test_aperture_radii_scale_with_tmag_and_annulus_moves_out_for_bright_stars():
    assert P.k1_aperture_radii(13.4) == (1.0, 5.0, 9.0)            # the P12 aperture for faint stars
    r_bright = P.k1_aperture_radii(10.4)
    assert r_bright[0] > 1.0 and r_bright[1] >= 7.0
    assert P.k1_aperture_radii(9.6)[0] >= r_bright[0]


def test_extract_uses_scaled_aperture():
    cube = np.ones((5, 21, 21))
    src = {"x": 10.0, "y": 10.0}
    _, ap_faint, bk_faint = P.extract(cube, src, [], tmag=13.0)
    _, ap_bright, bk_bright = P.extract(cube, src, [], tmag=10.5)
    assert ap_bright.sum() > ap_faint.sum()
    yy, xx = np.indices((21, 21))
    r = np.hypot(xx - 10, yy - 10)
    assert r[bk_bright].min() >= 7.0 - 1e-9 and r[bk_faint].min() >= 5.0 - 1e-9
