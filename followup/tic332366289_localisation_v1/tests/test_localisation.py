"""Focused tests for the TIC 332366289 localisation follow-up (run with pytest -p no:cacheprovider)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import common as C  # noqa: E402
import diffimg  # noqa: E402
import fitting  # noqa: E402
import prf as P  # noqa: E402
import windows as W  # noqa: E402


@pytest.fixture(scope="module")
def tprf():
    return P.TessPRF(4, 4, 1840.0, 36.0)


# ------------------------------------------------------------------ PRF
def test_prf_normalisation_any_subpixel_phase(tprf):
    rng = np.random.default_rng(1)
    for _ in range(20):
        xs, ys = 15 + rng.uniform(-0.5, 0.5), 15 + rng.uniform(-0.5, 0.5)
        img = tprf.render(xs, ys, (31, 31))
        assert 0.97 < img.sum() < 1.02


def test_prf_translation_and_peak(tprf):
    a = tprf.render(10.3, 9.8, (21, 21))
    b = tprf.render(11.3, 9.8, (21, 21))
    assert np.allclose(a[:, :-1], b[:, 1:], atol=1e-12)
    c = tprf.render(10.0, 12.0, (21, 21))
    assert np.unravel_index(np.argmax(c), c.shape) == (12, 10)  # (row, col)


def test_prf_header_conventions_and_axis():
    img = P.load_grid_prf(4, 4, 1, 2092)
    assert img.shape == (117, 117)
    assert np.unravel_index(np.argmax(img), img.shape) == (58, 58)
    assert abs(img.sum() - 81.0) < 0.5


def test_width_scale_conserves_flux(tprf):
    for w in (0.9, 1.1):
        assert 0.96 < tprf.render(15.2, 14.7, (31, 31), w).sum() < 1.03


def test_gauss_prf_normalised():
    g = P.GaussPRF(0.7)
    assert abs(g.render(10.4, 9.6, (21, 21)).sum() - 1.0) < 1e-6


# ------------------------------------------------------------------ WCS / pixel convention
def test_wcs_roundtrip_and_spoc_aperture_on_target():
    import data as Dm
    import scene as Sc
    S = Dm.load_sector(57)
    cat = Sc.load_catalogue()
    ids = [c["source_id"] for c in cat]
    k = ids.index(C.GAIA_TARGET)
    ra, dec, x, y, _ = Sc.scene_positions(S, [cat[k]], 2869.87)
    rr, dd = S.wcs.all_pix2world(x, y, 0)
    assert abs(rr[0] - ra[0]) < 1e-7 and abs(dd[0] - dec[0]) < 1e-7
    ap = S.spoc["aperture_mask"]
    yy, xx = np.nonzero(ap)
    assert abs(xx.mean() - x[0]) < 1.0 and abs(yy.mean() - y[0]) < 1.0
    # the target is the brightest thing within 1.5 px of its WCS position in the median image
    med = np.median(S.flux[S.good][:500], axis=0)
    cy, cx = int(round(y[0])), int(round(x[0]))
    sub = med[cy - 1:cy + 2, cx - 1:cx + 2]
    assert np.unravel_index(np.argmax(sub), sub.shape) in [(1, 1), (0, 1), (1, 0), (1, 2), (2, 1)]


def test_gaia_ids_are_exact_strings():
    import scene as Sc
    cat = Sc.load_catalogue()
    ids = {c["source_id"] for c in cat}
    for sid in [C.GAIA_TARGET] + C.LISTED_NEIGHBOURS:
        assert sid in ids
    assert all(isinstance(c["source_id"], str) and c["source_id"].isdigit() for c in cat)


# ------------------------------------------------------------------ windows / masks
class _FakeSector:
    def __init__(self, n=600, shape=(11, 11), seed=0, noise=1.0):
        rng = np.random.default_rng(seed)
        self.time = 100.0 + np.arange(n) * (200.0 / 86400.0)
        self.good = np.ones(n, bool)
        self.dump = np.zeros(n, bool)
        self.flux = 50.0 + rng.normal(0, noise, (n,) + shape)


def test_window_roles_by_time_not_index():
    S = _FakeSector()
    tc = S.time[300]
    role, st = W.select(S.time, S.good, S.dump, tc, 0.0928)
    perm = np.random.default_rng(3).permutation(S.time.size)
    role2, _ = W.select(S.time[perm], S.good[perm], S.dump[perm], tc, 0.0928)
    assert np.array_equal(role[perm], role2)
    assert st["n_in_good"] in (40, 41) and st["n_ref_left_good"] == 90 and st["n_ref_right_good"] == 90


def test_momentum_dump_is_not_bridged():
    S = _FakeSector()
    tc = S.time[300]
    S.dump[300 - 40] = True  # a dump in the left reference span
    role, st = W.select(S.time, S.good, S.dump, tc, 0.0928)
    left = np.nonzero(role == W.ROLE_REF_L)[0]
    assert left.min() > 260
    assert (role[:260] == W.ROLE_REF_L).sum() == 0


# ------------------------------------------------------------------ sign, units, uncertainty
def _inject(S, tc, dur, prf, xs, ys, A):
    cube = S.flux.copy()
    inw = np.abs(S.time - tc) <= dur / 2
    cube[inw] -= A * prf.render(xs, ys, cube.shape[1:])[None]
    return cube


def test_sign_and_amplitude_units(tprf):
    S = _FakeSector(noise=0.0)
    S.flux += 400.0 * tprf.render(5.0, 5.0, (11, 11))[None]
    tc = S.time[300]
    cube = _inject(S, tc, 0.0928, tprf, 5.2, 4.9, 3.0)
    di = diffimg.difference_image(S, tc, 0.0928, cube=cube)
    assert di["D"][5, 5] > 0  # flux lost -> positive
    f = fitting.EventFitter(tprf, (5.0, 5.0), (11, 11), half=5, grid_half=1.0, grid_step=0.05)
    sig = np.full((11, 11), 0.01)
    m = f.fit_map(di["D"], sig)
    assert abs(m["best_A"] - 3.0) < 0.05
    assert abs(m["best_x"] - 5.2) < 0.051 and abs(m["best_y"] - 4.9) < 0.051


def test_formal_uncertainty_matches_scatter():
    rng = np.random.default_rng(7)
    Ds = []
    sig = None
    for k in range(150):
        S = _FakeSector(seed=100 + k, noise=1.0)
        di = diffimg.difference_image(S, S.time[300], 0.0928)
        Ds.append(di["D"]); sig = di["sigma"]
    emp = np.std(np.array(Ds), axis=0)
    ratio = np.median(emp / sig)
    assert 0.85 < ratio < 1.15, ratio


def test_amplitude_error_matches_scatter(tprf):
    As, sAs = [], []
    for k in range(120):
        S = _FakeSector(seed=500 + k, noise=1.0)
        di = diffimg.difference_image(S, S.time[300], 0.0928)
        f = fitting.EventFitter(tprf, (5.0, 5.0), (11, 11), half=5, grid_half=0.5, grid_step=0.5)
        A, sA, _, _ = f.fit_at(di["D"], di["sigma"], [5.0], [5.0])
        As.append(A[0]); sAs.append(sA[0])
    assert 0.8 < np.std(As) / np.median(sAs) < 1.2


def test_inject_path_equals_cube_edit(tprf):
    """The fast injection path must equal editing the cube with the same shape."""
    S = _FakeSector(noise=1.0, seed=42)
    tc = S.time[300]
    img = tprf.render(5.3, 4.8, (11, 11))
    shape = diffimg.trapezoid_shape(S.time, tc, 0.0928)
    cube = S.flux - (2.5 * shape)[:, None, None] * img[None]
    a = diffimg.difference_image(S, tc, 0.0928, cube=cube, noise="p2p", bkg_regressor=True)
    b = diffimg.difference_image(S, tc, 0.0928, noise="p2p", bkg_regressor=True,
                                 inject={"img": img, "A": 2.5, "tc": tc, "dur": 0.0928})
    assert np.allclose(a["D"], b["D"], atol=1e-10) and np.allclose(a["sigma"], b["sigma"], atol=1e-10)


def test_dimming_boundary_ignores_brightening(tprf):
    """R2: a pure brightening (negative A) must not be localised as a dimming source."""
    S = _FakeSector(noise=0.0)
    tc = S.time[300]
    img = tprf.render(7.0, 3.0, (11, 11))
    di = diffimg.difference_image(S, tc, 0.0928, inject={"img": img, "A": -5.0, "tc": tc, "dur": 0.0928})
    f = fitting.EventFitter(tprf, (5.0, 5.0), (11, 11), half=5, grid_half=4.5, grid_step=0.25)
    m = f.fit_map(di["D"], np.full((11, 11), 0.05))
    assert m["best_A"] < 0 and abs(m["best_x"] - 7.0) < 0.3      # signed fit finds the brightening
    assert m["bestp_chi2"] >= m["chi2_0"] - 1e-6 or m["bestp_A"] > 0  # dimming map gains nothing from it
    assert m["chi2_0"] - m["bestp_chi2"] < 0.05 * (m["chi2_0"] - m["best_chi2"])


# ------------------------------------------------------------------ blended-star regression
def test_blended_star_one_pixel_off_target(tprf):
    """Shallow eclipse on a faint star 1 px from a bright target: the flux-weighted
    centroid barely moves, but the difference image puts the missing light on the
    eclipsing star."""
    S = _FakeSector(n=600, shape=(15, 15), noise=0.0)
    S.flux[:] = 100.0
    xt, yt, xn, yn = 7.0, 7.0, 8.0, 7.0
    S.flux += 2000.0 * tprf.render(xt, yt, (15, 15))[None] + 100.0 * tprf.render(xn, yn, (15, 15))[None]
    rng = np.random.default_rng(11)
    S.flux += rng.normal(0, 0.5, S.flux.shape)
    tc = S.time[300]
    A = 0.10 * 100.0  # 10% eclipse of the neighbour -> 10 e-/s = 4.8 ppt of the blend
    cube = _inject(S, tc, 0.0928, tprf, xn, yn, A)
    # ordinary flux-weighted centroid shift (background-subtracted 5x5 box)
    inw = np.abs(S.time - tc) <= 0.0928 / 2
    def cen(fr):
        b = fr[:, 5:10, 5:10] - 100.0
        yy, xx = np.mgrid[5:10, 5:10]
        return (b * xx).sum(axis=(1, 2)) / b.sum(axis=(1, 2))
    shift = abs(np.mean(cen(cube[inw])) - np.mean(cen(cube[~inw])))
    assert shift < 0.01  # tiny ordinary centroid motion
    di = diffimg.difference_image(S, tc, 0.0928, cube=cube)
    f = fitting.EventFitter(tprf, (xt, yt), (15, 15), half=5, grid_half=2.0, grid_step=0.05)
    m = f.fit_map(di["D"], di["sigma"])
    assert abs(m["best_x"] - xn) < 0.15 and abs(m["best_y"] - yn) < 0.15
    _, _, c_t, _ = f.fit_at(di["D"], di["sigma"], [xt], [yt])
    _, _, c_n, _ = f.fit_at(di["D"], di["sigma"], [xn], [yn])
    assert c_t[0] - c_n[0] > 25.0
