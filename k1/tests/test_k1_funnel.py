"""K1 Part B tests, population and funnel side: changes 2, 9, 11, 12 and the Stage B cadence rule."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tesshunter import event_vet, secondary, star_vet

import gaia_ms_k1 as GM
import sector_policy_k1 as SP


# ── change 2: Gaia main-sequence check ───────────────────────────────────────
def _abs_to_apparent(mg, plx_mas):
    return mg - 5.0 * np.log10(plx_mas / 1000.0) - 5.0


def _check(bprp, mg, plx=10.0, eplx=0.1, ruwe=None):
    G = _abs_to_apparent(mg, plx)
    return GM.check_arrays([G], [G + 0.5 * bprp], [G - 0.5 * bprp], [plx], [eplx],
                           None if ruwe is None else [ruwe]).iloc[0]


@pytest.mark.parametrize("bprp", [0.98, 1.21, 1.43, 1.70, 1.84, 2.09])   # K0V..K7V, M0V, M1V
def test_k_and_m0_m1_dwarfs_pass(bprp):
    r = _check(bprp, float(GM.ms_abs_g(bprp)))
    assert r.gaia_ms_status == "PASS" and r.gaia_flags == ""


def test_subgiant_rejected_and_binary_flagged():
    ref = float(GM.ms_abs_g(1.1))
    assert _check(1.1, ref - 2.0).gaia_ms_reason == "overluminous_evolved"
    r = _check(1.1, ref - 0.7)
    assert r.gaia_ms_status == "PASS" and "possible_binary" in r.gaia_flags
    assert _check(1.1, ref + 1.5).gaia_ms_reason == "underluminous_bad_astrometry"
    assert _check(1.1, ref, eplx=4.0).gaia_ms_reason == "parallax_snr_below_5"
    assert _check(0.6, float(GM.ms_abs_g(0.6))).gaia_ms_reason == "colour_outside_k1_range"
    r = _check(1.5, float(GM.ms_abs_g(1.5)), ruwe=2.1)
    assert r.gaia_ms_status == "PASS" and "ruwe_gt_1p4" in r.gaia_flags


def test_main_sequence_table_is_the_registered_file():
    from k1_common import sha
    assert sha(GM.TABLE) == GM.TABLE_SHA256
    x, y = GM.sequence()
    assert x.min() <= 0.85 and x.max() >= 2.5 and np.all(np.diff(y) >= 0)


# ── usable-sector rule ────────────────────────────────────────────────────────
def test_usable_sector_rule():
    use = SP.usable_sectors(qlp_sectors=[5, 40, 80, 83, 85, 90, 99, 104, 105], tess_spoc_sectors=[85, 12])
    assert use == {5, 12, 40, 85, 90}
    assert SP.usable_sectors([5, 60, 70], [], s56_only=True) == {60, 70}
    assert (SP.native_cadence_s(26), SP.native_cadence_s(27), SP.native_cadence_s(56)) == (1800.0, 600.0, 200.0)
    rows = [{"author": "QLP", "sector": 30}, {"author": "TESS-SPOC", "sector": 30}, {"author": "QLP", "sector": 83},
            {"author": "SPOC", "sector": 60}, {"author": "QLP", "sector": 101}]
    assert [(r["author"], r["sector"]) for r in SP.choose_products(rows)] == [("TESS-SPOC", 30)]


# ── change 9: the K1 hard stop ────────────────────────────────────────────────
def _snapshot(tmp_path):
    def norm(name, rows):
        d = tmp_path / name
        d.mkdir(parents=True)
        pd.DataFrame(rows, columns=["source", "tic_id", "ra", "dec", "label", "detail"]).to_csv(
            d / f"{name}.normalized.csv", index=False)
    norm("toi", [["toi", 100, 10.0, 10.0, "TOI-1.01", ""]])
    norm("ctoi", [["ctoi", 101, 20.0, 10.0, "CTOI", ""]])
    norm("nasa_ps", [["nasa_ps", 102, 30.0, 10.0, "pl b", ""]])
    norm("nasa_pscomppars", [["nasa_pscomppars", 102, 30.0, 10.0, "pl b", ""]])
    norm("tess_eb", [["tess_eb", 103, 40.0, 10.0, "TESS-EB 103.1", "P=1.5d"]])
    norm("spoc_tce", [["spoc_tce", 104, 50.0, 10.0, "TCE s0001-s0013 pn1", "P=12.34567d SNR=9.1"]])
    (tmp_path / "ttt").mkdir()
    pd.DataFrame({"tic_id": [105], "RAdeg": [60.0], "DEdeg": [10.0], "period_days": [2.0]}).to_csv(
        tmp_path / "ttt" / "ttt_table3.csv", index=False)
    pd.DataFrame({"tic_id": [106], "RAdeg": [70.0], "DEdeg": [10.0], "period_days": [3.0]}).to_csv(
        tmp_path / "ttt" / "ttt_table4.csv", index=False)
    return tmp_path


def test_hard_stop_reject_flag_and_tce_sidecar(tmp_path):
    import catalog_adapter_k1 as CA
    cat = CA.K1Catalog(_snapshot(tmp_path))
    pool = pd.DataFrame({"tic_id": [100, 101, 102, 103, 105, 106, 104, 200, 201],
                         "ra": [10.0, 20.0, 30.0, 40.0, 60.0, 70.0, 50.0, 10.0 + 15 / 3600 / np.cos(np.radians(10)), 80.0],
                         "dec": [10.0] * 9})
    r = cat.check_many(pool).set_index(pool.tic_id)
    for t in (100, 101, 102, 103, 105, 106):
        assert r.loc[t, "xmatch_status"] == "REJECT"
    assert r.loc[104, "xmatch_status"] == "FLAG" and "spoc_tce" in r.loc[104, "xmatch_flags"]
    assert r.loc[200, "xmatch_status"] == "FLAG" and "known_object_within_21arcsec" in r.loc[200, "xmatch_flags"]
    assert r.loc[201, "xmatch_status"] == "CLEAN"
    side = cat.tce_sidecar([104]).to_dict(orient="records")
    assert side[0]["tce_period_days"] == pytest.approx(12.34567) and side[0]["tce_run"] == "s0001-s0013"
    assert CA.tce_period_veto(24.69, side)["veto"] and not CA.tce_period_veto(7.0, side)["veto"]


# ── change 11: bound_alias ────────────────────────────────────────────────────
def _series(period_true, depth_p, depth_s=None, phase_s=0.5, dur=2.0 / 24, days=110.0, sigma=5e-4, seed=0,
            single_event_s=False):
    rng = np.random.default_rng(seed)
    t = 2000.0 + np.arange(0, days, 600.0 / 86400.0)
    t = t[(t % 27.4) < 25.0]                           # sector gaps
    f = 1.0 + sigma * rng.standard_normal(t.size)
    ph = ((t - 2001.0) / period_true) % 1.0
    d0 = np.abs((ph + 0.5) % 1.0 - 0.5) * period_true
    f[d0 < dur / 2] -= depth_p
    if depth_s:
        ds = np.abs((ph - phase_s + 0.5) % 1.0 - 0.5) * period_true
        m = ds < dur / 2
        if single_event_s:
            m &= (t > 2040.0) & (t < 2040.0 + period_true)
        f[m] -= depth_s
    return t, f


def test_bound_alias_rescue_rate_over_noise_realisations():
    # a 2-sigma consistency test on correctly estimated errors keeps ~95% of true aliases
    n = 0
    for seed in range(20):
        t, f = _series(3.0, 2e-3, seed=seed)
        sec = secondary.secondary_scan(t, f, 6.0, 2001.0, 2.0 / 24, 0.75, 0.75, 4500.0, t, f, gate_mode="bound",
                                       k1_modes=True, t_sap_sector=np.floor((t - 2000) / 27.4))
        assert sec["gate"] == "FAIL"
        n += sec["gate_by_mode_k1"]["bound_alias"] == "PASS"
    assert n >= 16


def test_bound_alias_rescues_a_planet_searched_at_twice_its_period():
    t, f = _series(3.0, 2e-3, seed=3)
    sec = secondary.secondary_scan(t, f, 6.0, 2001.0, 2.0 / 24, 0.75, 0.75, 4500.0, t, f, gate_mode="bound",
                                   k1_modes=True, t_sap_sector=np.floor((t - 2000) / 27.4))
    assert sec["gate"] == "FAIL"                          # the p10 bound gate kills it (TOI-620 b pattern)
    assert sec["gate_by_mode_k1"]["bound_alias"] == "PASS"
    assert sec["k1"]["alias_family"]["rescued"] is True
    sec2 = secondary.secondary_scan(t, f, 6.0, 2001.0, 2.0 / 24, 0.75, 0.75, 4500.0, t, f, gate_mode="bound_alias",
                                    t_sap_sector=np.floor((t - 2000) / 27.4))
    assert sec2["gate"] == "PASS"


def test_bound_alias_still_fails_an_eb_with_a_recurrent_unequal_secondary():
    t, f = _series(4.0, 6e-3, depth_s=2.5e-3)
    sec = secondary.secondary_scan(t, f, 4.0, 2001.0, 2.0 / 24, 0.75, 0.75, 4500.0, t, f, gate_mode="bound_alias",
                                   t_sap_sector=np.floor((t - 2000) / 27.4))
    assert sec["k1"]["alias_family"]["applicable"] and not sec["k1"]["alias_family"]["depth_consistent"]
    assert sec["gate"] == "FAIL" and sec["gate_by_mode_k1"]["bound_alias"] == "FAIL"


def test_bound_alias_passes_a_non_recurrent_off_phase_feature():
    t, f = _series(5.0, 3e-3, depth_s=3e-3, phase_s=0.31, single_event_s=True)
    sec = secondary.secondary_scan(t, f, 5.0, 2001.0, 2.0 / 24, 0.75, 0.75, 4500.0, t, f, gate_mode="bound",
                                   k1_modes=True, t_sap_sector=np.floor((t - 2000) / 27.4))
    if sec.get("secondaries"):
        assert sec["gate_by_mode_k1"]["bound_alias"] == "PASS"


def test_legacy_scan_records_unchanged_without_k1():
    t, f = _series(3.0, 2e-3)
    sec = secondary.secondary_scan(t, f, 6.0, 2001.0, 2.0 / 24, 0.75, 0.75, 4500.0, t, f)
    assert "k1" not in sec and "gate_by_mode_k1" not in sec and "p10" not in sec


# ── change 12: the noise-relative SAP ramp ───────────────────────────────────
def _ev(over_depth, change_ppt, err_ppt):
    return {"desat_within_one_duration": False, "edge_within_one_duration": False,
            "frac_in_transit_quality_flagged": 0.0, "baseline_change_across_event_over_depth": over_depth,
            "bkg_change_across_window_over_median": None, "bkg_in_over_sector_median": None,
            "frac_straylight_flagged_within_one_duration": 0.0, "pdc_gap_within_one_duration": False,
            "det_depth_ppt": None, "det_depth_err_ppt": None, "sap_depth_ppt": 1.0, "sap_depth_err_ppt": err_ppt,
            "baseline_change_across_event_ppt": change_ppt, "sap_ramp_noise_threshold_ppt": 3.0 * err_ppt}


def test_sap_ramp_noise_relative_only_when_switched_on():
    ramp = "SAP baseline changes by more than one depth across the event (ramp)"
    ev = _ev(1.5, 0.75, 0.4)           # ramp 1.5 x a 0.5-ppt depth, but below 3 x 0.4 ppt of noise
    assert event_vet.SAP_RAMP_NOISE_MULTIPLE is None
    assert ramp in event_vet.removal_reasons(ev, 9, 9, False)
    saved = event_vet.SAP_RAMP_NOISE_MULTIPLE
    try:
        event_vet.SAP_RAMP_NOISE_MULTIPLE = 3.0
        assert ramp not in event_vet.removal_reasons(ev, 9, 9, False)
        assert ramp in event_vet.removal_reasons(_ev(3.0, 1.5, 0.4), 9, 9, False)
        assert ramp not in event_vet.removal_reasons(_ev(0.8, 2.0, 0.1), 9, 9, False)   # under one depth
    finally:
        event_vet.SAP_RAMP_NOISE_MULTIPLE = saved


# ── Stage B: per-window cadence rule ──────────────────────────────────────────
def _sector(cad_s, days=25.0, seed=0):
    rng = np.random.default_rng(seed)
    t = 1500.0 + np.arange(0, days, cad_s / 86400.0)
    return {"sector": 5, "author": "QLP", "cadence_s": cad_s, "time": t, "flux": 1 + 2e-4 * rng.standard_normal(t.size)}


def test_stage_b_tests_1800s_sector_only_under_per_window():
    s = [_sector(1800.0)]
    r = star_vet.phase_independent_test(s, 4.0, 3.0, t14_hours=4.0)
    assert r["sectors"][0]["tested"] is False
    saved = star_vet.B_CADENCE_RULE
    try:
        star_vet.B_CADENCE_RULE = "per_window"
        r2 = star_vet.phase_independent_test(s, 4.0, 3.0, t14_hours=4.0)
        assert r2["sectors"][0]["tested"] is True and r2["excluded"] is True     # a flat sector excludes P
        r3 = star_vet.phase_independent_test(s, 4.0, 3.0, t14_hours=1.5)          # 3 cadences only: not tested
        assert r3["sectors"][0]["tested"] is False
    finally:
        star_vet.B_CADENCE_RULE = saved
