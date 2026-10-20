"""Prompt 3 part B: the TRICERATOPS wrapper's helpers and result contract,
with TRICERATOPS itself replaced by a stub (no network)."""

import json
import sys
import types

import numpy as np
import pandas as pd
import pytest

from tesshunter import fpp


def test_circular_aperture_contains_centre_and_respects_radius():
    ap = fpp.circular_aperture(100.3, 200.7, 2.0)
    assert ap.ndim == 2 and ap.shape[1] == 2
    assert any((abs(c - 100) < 1e-9 and abs(r - 201) < 1e-9) for c, r in ap)
    assert np.all((ap[:, 0] - 100.3) ** 2 + (ap[:, 1] - 200.7) ** 2 <= 4.0 + 1e-9)
    assert 9 <= len(ap) <= 21


def test_fold_keeps_a_window_around_transit():
    t = 1000.0 + np.arange(0, 20, 2.0 / 1440.0)
    f = np.ones_like(t)
    ph, fl = fpp.fold_for_triceratops(t, f, period=3.0, t0=1001.0, duration=0.1, window_durations=3.0)
    assert ph.size > 0 and np.all(np.abs(ph) <= 0.3 + 1e-9)
    assert np.all(np.diff(ph) >= 0)


class _StubTarget:
    """Mimics triceratops.target for the wrapper's control flow."""
    instances = []

    def __init__(self, ID, sectors, search_radius=10, mission="TESS", lightkurve_cache_dir=None,
                 trilegal_fname=None, **kwargs):
        self.ID = ID
        self.sectors = list(sectors)
        self.trilegal_fname = trilegal_fname
        self.stars = pd.DataFrame({"ID": [ID, 111], "Tmag": [10.0, 13.0]})
        self.pix_coords = [np.array([[50.0, 60.0], [52.0, 61.0]]) for _ in sectors]
        self.calls = []
        _StubTarget.instances.append(self)

    def get_spoc_apertures(self):
        return [None for _ in self.sectors]

    def calc_depths(self, tdepth, all_ap_pixels=None, dilution_corrected=True):
        self.calls.append(("depths", tdepth, None if all_ap_pixels is None else len(all_ap_pixels)))

    def calc_probs(self, time, flux_0, flux_err_0, P_orb, **kw):
        self.calls.append(("probs", P_orb, kw["N"]))
        self.probs = pd.DataFrame({"ID": [self.ID, self.ID, 111], "scenario": ["TP", "EB", "NTP"],
                                   "prob": [0.9, 0.05, 0.05]})
        self.FPP = 0.10
        self.NFPP = 0.05


@pytest.fixture
def stub_triceratops(monkeypatch):
    mod = types.ModuleType("triceratops.triceratops")
    mod.target = _StubTarget
    pkg = types.ModuleType("triceratops")
    pkg.triceratops = mod
    pkg.__version__ = "stub"
    monkeypatch.setitem(sys.modules, "triceratops", pkg)
    monkeypatch.setitem(sys.modules, "triceratops.triceratops", mod)
    # no TESScut in tests: every requested sector counts as available
    monkeypatch.setattr(fpp, "_sectors_with_cutouts", lambda tic, sectors, ra, dec, n: (list(sectors), []))
    _StubTarget.instances.clear()
    return mod


def test_run_fpp_result_contract_and_cache(tmp_path, stub_triceratops):
    t = 1000.0 + np.arange(0, 27, 2.0 / 1440.0)
    f = np.ones_like(t)
    res = fpp.run_fpp(123, [1, 2], t, f, np.full(t.size, 1e-3), period=3.0, t0=1001.0,
                      duration=0.1, depth_frac=2e-3, exp_time_days=2 / 1440, tmag=10.0,
                      aperture="auto", author="SPOC", n_draws=1000, cache_dir=tmp_path,
                      red_noise_beta=2.5, fold_mode="subsample")
    assert res.available and res.fpp == 0.10 and res.nfpp == 0.05
    assert res.settings["red_noise_beta"] == 2.5
    assert abs(res.settings["flux_err_used"] - 2.5e-3) < 1e-9
    assert res.aperture_source == "circular_from_tmag"
    assert res.n_stars == 2 and res.n_scenarios == 3
    assert res.scenario_totals["TP"] == pytest.approx(0.9)
    assert (tmp_path / "tic123").exists()
    assert json.loads(open(res.result_path, encoding="utf-8").read())["fpp"] == 0.10
    assert not res.blocks_packet
    calls = _StubTarget.instances[0].calls
    assert calls[0][0] == "depths" and calls[0][2] == 2 and calls[1][2] == 1000

    # second call is served from the cache without constructing a target
    n_before = len(_StubTarget.instances)
    res2 = fpp.run_fpp(123, [1, 2], t, f, None, period=3.0, t0=1001.0, duration=0.1,
                       depth_frac=2e-3, exp_time_days=2 / 1440, tmag=10.0, aperture="auto",
                       author="SPOC", n_draws=1000, cache_dir=tmp_path, red_noise_beta=2.5,
                       fold_mode="subsample")
    assert res2.cached and res2.fpp == 0.10 and len(_StubTarget.instances) == n_before


def test_optional_input_fingerprint_separates_results_but_preserves_legacy_cache(tmp_path, stub_triceratops):
    t = 1000 + np.arange(0, 10, 200 / 86400)
    flux = 1 + np.random.default_rng(3).normal(0, .001, len(t))
    for fingerprint, cached in [(None, False), (None, True), ("native-a", False),
                                ("native-a", True), ("native-b", False)]:
        result = fpp.run_fpp(123, [60], t, flux, None, period=3., t0=1001., duration=.1,
                             depth_frac=.002, exp_time_days=200 / 86400, tmag=13.,
                             n_draws=1000, cache_dir=tmp_path, input_fingerprint=fingerprint)
        assert result.available and result.cached == cached
        if fingerprint is None:
            assert "input_fingerprint" not in result.settings
        else:
            assert result.settings["input_fingerprint"] == fingerprint
    assert len(_StubTarget.instances) == 3


def test_binned_mode_bins_the_fold_and_ignores_beta(tmp_path, stub_triceratops):
    t = 1000.0 + np.arange(0, 27, 2.0 / 1440.0)
    f = np.ones_like(t)
    res = fpp.run_fpp(124, [1], t, f, None, period=3.0, t0=1001.0, duration=0.1, depth_frac=2e-3,
                      exp_time_days=2 / 1440, tmag=10.0, aperture="circular", n_draws=1000,
                      cache_dir=tmp_path, red_noise_beta=3.0)
    assert res.available and res.settings["fold_mode"] == "binned"
    assert res.settings["red_noise_beta"] == 1.0
    assert res.settings["bin_width_days"] >= 2 / 1440
    assert res.n_points_used < 400          # +/- 0.3 d at 0.1/25 = 0.004 d bins
    bx, by, err, w = fpp.bin_fold(np.linspace(-0.3, 0.3, 5000), np.ones(5000), 0.1, 2 / 1440)
    assert abs(w - 0.004) < 1e-9 and bx.size > 100 and err >= 0


def test_run_fpp_reports_errors_instead_of_raising(tmp_path, stub_triceratops):
    res = fpp.run_fpp(5, [], np.arange(10.0), np.ones(10), None, period=1.0, t0=0.0,
                      duration=0.1, depth_frac=1e-3, exp_time_days=1e-3, cache_dir=tmp_path)
    assert not res.available and "sectors" in res.error
    res = fpp.run_fpp(5, [1], np.arange(10.0), np.ones(10), None, period=1.0, t0=0.0,
                      duration=0.1, depth_frac=1e-3, exp_time_days=1e-3, cache_dir=tmp_path)
    assert not res.available and res.error


def test_packet_gate_threshold():
    r = fpp.FPPResult(available=True, fpp=0.6)
    assert r.blocks_packet
    assert not fpp.FPPResult(available=True, fpp=0.4).blocks_packet
    assert not fpp.FPPResult(available=False, fpp=None).blocks_packet
