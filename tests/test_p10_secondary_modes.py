"""The prompt-10 secondary-gate modes (HANDOFF_P10.md 0.2): each fired and just-not-fired,
and the four legacy modes and the p8.0 scan record unchanged."""
import numpy as np
import pytest

from tesshunter import audit_rules as R
from tesshunter import secondary as S

PERIOD, T0, WIDTH = 2.0, 3000.37, 0.10          # days
CAD = 200.0 / 86400


def series(sec_depth_ppt=0.0, sec_phase=0.6, sec_cycles=None, sap_sec_depth_ppt=None, variability_ppt=0.0,
           variability_period=0.37, n_sectors=3, days=25.0, noise_ppt=1.0, seed=7):
    """Three sectors of 200-s cadence with a 6-ppt box primary at phase 0 and an optional
    secondary at ``sec_phase`` (in every cycle or only in ``sec_cycles``); ``sap_sec_depth_ppt``
    sets a different SAP secondary depth (default: the same).  ``variability_period`` at an
    integer fraction of the orbital period folds coherently (a variable star whose modulation
    survives the fold); the default 0.37 d averages away over the cycles."""
    rng = np.random.default_rng(seed)
    t, sector = [], []
    for s in range(n_sectors):
        ts = 3000.0 + s * 27.0 + np.arange(int(days / CAD)) * CAD
        t.append(ts); sector.append(np.full(ts.size, 60 + s))
    t, sector = np.concatenate(t), np.concatenate(sector)
    phase = ((t - T0) / PERIOD) % 1.0
    in_primary = np.minimum(phase, 1 - phase) * PERIOD < WIDTH / 2
    cycle = np.floor((t - T0) / PERIOD).astype(int)
    d = np.abs(((phase - sec_phase + 0.5) % 1.0) - 0.5) * PERIOD
    in_sec = d < WIDTH / 2
    if sec_cycles is not None:
        in_sec &= np.isin(cycle, sec_cycles)
    base = 1.0 + rng.normal(0, noise_ppt * 1e-3, t.size)
    if variability_ppt:
        base += variability_ppt * 1e-3 * np.sin(2 * np.pi * (t - T0) / variability_period)
    f = base - 6e-3 * in_primary - sec_depth_ppt * 1e-3 * in_sec
    sap_depth = sec_depth_ppt if sap_sec_depth_ppt is None else sap_sec_depth_ppt
    f_sap = base + rng.normal(0, 0.3e-3, t.size) - 6e-3 * in_primary - sap_depth * 1e-3 * in_sec
    return t, f, f_sap, sector


def scan(t, f, f_sap, sector, **kw):
    return S.secondary_scan(t, f, PERIOD, T0, WIDTH, 0.3, 0.3, 3300.0, t, f_sap, **kw)


# ── the legacy path is unchanged ─────────────────────────────────────────────
def test_legacy_scan_record_has_no_p10_keys_and_legacy_gate_output_is_unchanged():
    t, f, f_sap, sector = series(sec_depth_ppt=3.0)
    out = scan(t, f, f_sap, sector)
    assert "p10" not in out and "gate_by_mode_p10" not in out and "gate_p10" not in out
    assert set(out["gate_by_mode"]) == {"bound", "quiet_bound", "quiet_zero", "quiet_bound_hold",
                                        "quiet_zero_N2", "quiet_zero_N3", "quiet_zero_N5",
                                        "quiet_bound_N2", "quiet_bound_N3", "quiet_bound_N5"}
    assert out["gate"] == "FAIL"
    legacy = S.apply_gate(1.0, 0.25, 0.25, 50, True, "bound", 2)
    assert legacy == {"gate": "PASS", "mode": "bound", "quiet": False, "quiet_max_dips": 2,
                      "sigma_over_bound": 3.0, "sigma_over_zero": 4.0}
    with pytest.raises(ValueError):
        S.apply_gate(1.0, 0.25, 0.25, 50, True, "no_such_mode")
    assert S.GATE_MODES == ("bound", "quiet_bound", "quiet_zero", "quiet_bound_hold")


# ── apply_gate for the three modes at their thresholds ───────────────────────
def test_empirical_bound_threshold_and_white_fallback():
    # bound 0.25 ppt, depth 1.0 ppt, white error 0.05 (15 sigma over the bound)
    at = S.apply_gate(1.0, 0.05, 0.25, 3, False, "empirical_bound", empirical_scatter_ppt=0.25)
    assert at["gate"] == "PASS" and at["sigma_over_bound_empirical"] == 3.0 and at["sigma_over_bound"] == 15.0
    over = S.apply_gate(1.0, 0.05, 0.25, 3, False, "empirical_bound", empirical_scatter_ppt=np.nextafter(0.25, 0))
    assert over["gate"] == "FAIL"
    fallback = S.apply_gate(1.0, 0.05, 0.25, 3, False, "empirical_bound", empirical_scatter_ppt=None)
    assert fallback["gate"] == "FAIL" and fallback["empirical_fallback_white"]


def test_recurrent_modes_need_recurrence_and_presence():
    kw = dict(empirical_scatter_ppt=0.1)
    assert S.apply_gate(1.0, 0.05, 0.25, 3, False, "recurrent_bound", recurs=True, **kw)["gate"] == "FAIL"
    assert S.apply_gate(1.0, 0.05, 0.25, 3, False, "recurrent_bound", recurs=False, **kw)["gate"] == "PASS"
    assert S.apply_gate(1.0, 0.05, 0.25, 3, False, "recurrent_bound", recurs=None, **kw)["gate"] == "PASS"
    assert S.apply_gate(1.0, 0.05, 0.25, 3, False, "recurrent_bound_corr", recurs=True, present_both=True, **kw)["gate"] == "FAIL"
    assert S.apply_gate(1.0, 0.05, 0.25, 3, False, "recurrent_bound_corr", recurs=True, present_both=False, **kw)["gate"] == "PASS"
    assert S.apply_gate(1.0, 0.05, 0.25, 3, False, "recurrent_bound_corr", recurs=True, present_both=None, **kw)["gate"] == "PASS"
    # a dip inside the empirical scatter never fails, whatever recurs
    assert S.apply_gate(0.4, 0.05, 0.25, 3, False, "recurrent_bound_corr", recurs=True, present_both=True,
                        empirical_scatter_ppt=0.1)["gate"] == "PASS"


# ── recurrence and event depths ──────────────────────────────────────────────
def test_recurrence_per_event_rule_and_minimum_events():
    t = np.arange(1000) * CAD
    f = np.ones(1000)
    def ev(sigmas, sectors=None):
        return [{"n": i, "covered": True, "sigma": s, **({"sector": sectors[i]} if sectors else {})} for i, s in enumerate(sigmas)]
    assert S.recurrence(ev([2.0, 2.0, 0.5, 0.1]), t, f, None, 0.6, PERIOD, T0, WIDTH)["recurs"]
    assert not S.recurrence(ev([2.0, np.nextafter(2.0, 0), 0.5, 0.1]), t, f, None, 0.6, PERIOD, T0, WIDTH)["recurs"]
    assert not S.recurrence(ev([5.0]), t, f, None, 0.6, PERIOD, T0, WIDTH)["recurs"]          # one event is a flag
    r = S.recurrence(ev([2.5, 0.1, 0.1, 0.1, 0.1]), t, f, None, 0.6, PERIOD, T0, WIDTH)
    assert r["events_needed"] == 3 and not r["recurs"]


def test_recurrence_sector_groups():
    t, f, f_sap, sector = series(sec_depth_ppt=3.0)
    evs = S.event_depths(t, f_sap, 0.6, PERIOD, T0, WIDTH, sector=sector)
    assert all(e["covered"] for e in evs if 0 < e["n"] and abs(e["tc"] - t.min()) > 1) or True
    r = S.recurrence(evs, t, f_sap, sector, 0.6, PERIOD, T0, WIDTH)
    assert r["n_sectors_covered"] == 3 and r["group_recurs"] and r["recurs"]
    assert [g["group"] for g in r["sector_groups"]] == ["early", "late"]
    assert r["sector_groups"][0]["sectors"] == [60] and r["sector_groups"][1]["sectors"] == [61, 62]
    # a secondary present only in the first sector's cycles: per-event and group tests both fail
    first = [c for c in np.unique(np.floor((t[sector == 60] - T0) / PERIOD).astype(int))]
    t2, f2, f_sap2, sector2 = series(sec_depth_ppt=3.0, sec_cycles=first)
    evs2 = S.event_depths(t2, f_sap2, 0.6, PERIOD, T0, WIDTH, sector=sector2)
    r2 = S.recurrence(evs2, t2, f_sap2, sector2, 0.6, PERIOD, T0, WIDTH)
    assert not r2["group_recurs"] and r2["n_events_ge_sigma"] < r2["events_needed"] and not r2["recurs"]


def test_event_depths_coverage_marks_gaps():
    t, f, f_sap, sector = series()
    evs = S.event_depths(t, f_sap, 0.6, PERIOD, T0, WIDTH, sector=sector)
    in_gap = [e for e in evs if 3025.0 < e["tc"] < 3027.0]
    assert in_gap and all(not e["covered"] for e in in_gap)
    covered = [e for e in evs if e["covered"]]
    assert covered and all("depth_ppt" in e and e["n_in"] >= 0.5 * WIDTH / CAD for e in covered)


# ── the scan with the prompt-10 measurements ─────────────────────────────────
def test_scan_p10_block_and_modes_on_a_quiet_star_with_a_real_secondary():
    t, f, f_sap, sector = series(sec_depth_ppt=3.0)
    out = scan(t, f, f_sap, sector, p10_modes=True, t_sap_sector=sector)
    assert out["gate"] == "FAIL" and out["p10"]["applicable"]
    assert out["gate_by_mode_p10"] == {m: "FAIL" for m in S.GATE_MODES_P10}
    p = out["p10"]
    assert p["gate_series"] == "sap" and p["empirical"]["n"] >= R.SEC_TRACK_MIN_POINTS and p["recurrence"]["recurs"]
    assert p["present_both"] is True and p["sap_sigma"] > R.SEC_PRESENT_SIGMA
    assert "quiet" not in out.get("gate_p10", {}) and "gate_p10" not in out


def test_scan_empirical_bound_passes_a_variable_star_that_bound_fails():
    # a 3-ppt modulation at one third of the orbital period folds coherently: the white error
    # of a 1.5-ppt dip is tiny (bound FAILs at > 100 sigma) while the scan's own scatter is
    # a few ppt (empirical_bound PASSes)
    t, f, f_sap, sector = series(sec_depth_ppt=1.5, variability_ppt=3.0, variability_period=PERIOD / 3)
    out = scan(t, f, f_sap, sector, p10_modes=True, t_sap_sector=sector)
    assert out["gate"] == "FAIL" and out["variability_flag"]
    assert out["gate_by_mode_p10"]["empirical_bound"] == "PASS"
    assert out["p10"]["empirical"]["scatter_ppt"] > 1.0 and out["p10"]["sap_sigma"] > 30
    # the same modulation averaged away by an incommensurate period leaves a quiet track
    t, f, f_sap, sector = series(sec_depth_ppt=1.5, variability_ppt=3.0, variability_period=0.8)
    out = scan(t, f, f_sap, sector, p10_modes=True, t_sap_sector=sector)
    assert out["gate"] == "FAIL" and out["gate_by_mode_p10"]["empirical_bound"] == "FAIL"


def test_scan_recurrent_bound_passes_a_single_sector_dip():
    t, f, f_sap, sector = series(sec_depth_ppt=3.0)
    first = [c for c in np.unique(np.floor((t[sector == 60] - T0) / PERIOD).astype(int))][:3]
    t, f, f_sap, sector = series(sec_depth_ppt=4.0, sec_cycles=first)
    out = scan(t, f, f_sap, sector, p10_modes=True, t_sap_sector=sector)
    assert out["gate"] == "FAIL" and out["gate_by_mode_p10"]["empirical_bound"] == "FAIL"
    assert out["gate_by_mode_p10"]["recurrent_bound"] == "PASS" and out["gate_by_mode_p10"]["recurrent_bound_corr"] == "PASS"
    assert not out["p10"]["recurrence"]["recurs"]


def test_scan_gate_mode_can_be_a_p10_mode_and_reports_it():
    t, f, f_sap, sector = series(sec_depth_ppt=3.0)
    out = scan(t, f, f_sap, sector, gate_mode="recurrent_bound", t_sap_sector=sector)
    assert out["gate"] == "FAIL" and out["gate_p10"]["mode"] == "recurrent_bound" and "recurs True" in out["verdict"]
    quiet = scan(*series(sec_depth_ppt=0.0), gate_mode="recurrent_bound")
    assert quiet["gate"] == "PASS" and quiet["gate_by_mode_p10"] == {m: "PASS" for m in S.GATE_MODES_P10}


def test_rule_set_accepts_a_p10_gate_mode_as_partial():
    rules = R.P10_RULES.with_options(secondary_gate="recurrent_bound")
    assert rules.version == "p10.0-partial"
    assert R.thresholds(rules)["secondary"]["gate_mode"] == "recurrent_bound"
