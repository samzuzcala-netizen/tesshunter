"""Regression tests for the takeover's demonstrated Stage C contract defects."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tesshunter import audit_rules as R
from tesshunter import stage_c as C


@pytest.fixture
def scripts(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    monkeypatch.syspath_prepend(str(root / "p10/protocol"))
    return tuple(importlib.import_module(n) for n in ("audit_p5", "revet_p6", "p10_stage_c"))


def spectra(robust_at_peak=9.0):
    raw = np.tile([-1., 0., 1.], 1001)
    raw[1] = robust_at_peak * 1.4826
    installed = raw.copy() * .01
    installed[1] = 3.556564
    installed[100] = -400.
    return installed, raw


def test_installed_concentration_and_raw_sde_are_not_interchangeable():
    installed, raw = spectra(12.)
    assert C.concentration(raw)["fraction"] < .5
    result = C.sde_fallback(installed, 1, power_raw=raw)
    assert result["triggered"] and result["passes_on_robust"]
    assert result["sde_robust_at_peak"] == pytest.approx(12.)
    inverse = C.sde_fallback(raw, 1, power_raw=installed)
    assert not inverse["triggered"] and not inverse["passes_on_robust"]


@pytest.mark.parametrize("value,passes", [(9., True), (np.nextafter(9., 0), False)])
def test_raw_threshold_at_exactly_same_installed_peak(value, passes):
    installed, raw = spectra(value)
    fb = C.sde_fallback(installed, 1, power_raw=raw)
    assert fb["passes_on_robust"] is passes
    strongest = {"period": 10., "SDE": installed[1], "index": 1}
    local = {"period": 10., "sde": installed[1], "index": 1, "is_local_maximum": True}
    result = C.significant_peak(10., strongest, [], local, robust_fallback=fb)
    assert (result["decision"] == "PASS") is passes
    assert result["robust_fallback_used"] is passes
    assert C.significant_peak(10., strongest, [], dict(local, index=2), robust_fallback=fb)["decision"] == "FAIL"
    assert C.significant_peak(5., strongest, [], local, robust_fallback=fb)["decision"] == "FAIL"


def test_no_raw_proxy_and_no_alternate_robust_peak():
    installed, raw = spectra(8.)
    assert not C.sde_fallback(installed, 1)["passes_on_robust"]
    assert C.sde_fallback(installed, 1)["sde_robust_at_peak"] is None
    raw[200] = 100.
    result = C.sde_fallback(installed, 1, power_raw=raw)
    assert result["sde_robust_max"] > 9 and not result["passes_on_robust"]


def test_missing_alias_depth_measurement_never_passes_or_borrows_another_peak():
    local = {"sde": 12., "period": 9., "is_local_maximum": True}
    strongest = {"period": 40., "SDE": 30.}
    peak = {"period": 18., "SDE": 20.}
    result = C.significant_peak(9., strongest, [peak], local, alias_depths_consistent=True)
    assert result["decision"] == "NEEDS_ALIAS_DEPTH"
    assert result["stronger"][0]["blocks"] == "alias_depths_unmeasured"
    measured = C.significant_peak(9., strongest, [peak], local, alias_depths_consistent={"18.000000": False})
    assert measured["decision"] == "FAIL"


def test_driver_uses_all_stronger_peaks_beyond_top_ten(scripts, tmp_path, monkeypatch):
    A, V, _ = scripts
    p = np.arange(.5, 100., .001); w = np.zeros_like(p)
    for period, sde in list(zip(range(1, 11), range(30, 20, -1))) + [(20., 11.), (60., 10.)]:
        w[np.argmin(abs(p-period))] = sde
    top = A._peak_table(p, w)
    assert len(top) == 10 and not any(abs(x["period"]-20) < .001 for x in top)
    monkeypatch.setattr(A, "OUT", tmp_path); (tmp_path / "tls").mkdir()
    np.savez(tmp_path / "tls/tic1_P60.0000_spectrum.npz", periods=p, power=w)
    # The eleventh peak is a blocking 3:1 alias, so no TLS measurement is needed.
    monkeypatch.setattr(A, "load_prepared", lambda *args: pytest.fail("unnecessary residual TLS"))
    r = V.significant_peak_check(A, 1, 60., {"blind": {"period": top[0]["period"], "SDE": 30., "peaks": top}}, 1, 3, False)
    assert r["decision"] == "FAIL" and r["stronger"][-1]["blocks"] == "alias"
    assert len(r["stronger_peak_census"]) == 11


def test_driver_fallback_combination_reproduces_low_installed_sde_pattern(scripts, tmp_path, monkeypatch):
    A, V, _ = scripts
    w, raw = spectra(12.)
    # Arrange a sorted grid with the same low-SDE maximum in the survey window.
    p = np.linspace(9., 11., len(w)); index = len(w)//2
    w[1], w[index] = w[index], w[1]
    raw[1], raw[index] = raw[index], raw[1]
    monkeypatch.setattr(A, "OUT", tmp_path); (tmp_path / "tls").mkdir()
    np.savez(tmp_path / "tls/tic1_P10.0000_spectrum.npz", periods=p, power=w, power_raw=raw)
    fb = V.spectrum_fallback(A, 1, 10.)
    r = V.significant_peak_check(A, 1, 10., {"blind": {"period": p[index], "SDE": w[index]}}, 1, 3, False, robust=fb)
    assert r["decision"] == "PASS" and r["robust_fallback_used"]
    assert r["installed_only"]["decision"] == "FAIL"


def test_cached_tls_durations_are_floored_before_consumption_without_rewriting(scripts, tmp_path, monkeypatch):
    A, _, _ = scripts
    monkeypatch.setattr(A, "OUT", tmp_path); (tmp_path / "tls").mkdir()
    monkeypatch.setattr(A, "RULES", R.P10_RULES.with_options(duration_floor_cadence=True))
    monkeypatch.setattr(A, "cache_matches", lambda r: True)
    cad = 200 / 86400; times = np.arange(5) * cad
    monkeypatch.setattr(A, "load_prepared", lambda *args: (times, times, times))
    path = tmp_path / "tls/tic1_P10.0000.json"
    original = {"blind": {"duration_days": cad/2}, "forced": {"duration_days": cad/3}}
    path.write_text(json.dumps(original)); before = path.read_bytes()
    r = A.tls_step(1, 10., 1, 3, .5, 110., 30., None)
    for field in ("blind", "forced"):
        assert r[field]["duration_days"] == pytest.approx(cad)
        assert r[field]["duration_raw_days"] == original[field]["duration_days"]
    assert path.read_bytes() == before
    monkeypatch.setattr(A, "RULES", R.P8_RULES)
    assert A.tls_step(1, 10., 1, 3, .5, 110., 30., None) == original


def test_run_c_reuses_completed_wall_without_invoking_tls(scripts, tmp_path, monkeypatch):
    _, _, T = scripts
    (tmp_path / "stageC").mkdir()
    rec = {"key": "tic1_P10.0000", "tic_id": 1, "period": 10., "depth_ppt": 1.,
           "source_root": str(tmp_path), "lc_root": str(tmp_path), "stellar": "cache"}
    cached = {"decision": "PASS", "rules_version": "p8.0", "survey_period": 10., "survey_depth_ppt": 1.,
              "p10": {"wall_s": 1234.5, "cadence": "native", "rules": "p8.0", "input_config": {"same": True}}}
    path = tmp_path / "stageC/tic1_P10.0000.json"; path.write_text(json.dumps(cached)); before = path.read_bytes()
    monkeypatch.setattr(T, "workspace", lambda *args: tmp_path)
    a = SimpleNamespace(input_config=lambda: {"same": True})
    v = SimpleNamespace(stagec_one=lambda *a, **k: pytest.fail("completed TLS repeated"))
    monkeypatch.setattr(T, "configure", lambda *args: (a, v, None))
    assert T.run_c("p8", rec, "p8.0", "native") == cached
    assert path.read_bytes() == before


def test_p9_adapter_floors_candidate_and_keeps_truth_untouched(scripts, monkeypatch):
    adapter = importlib.import_module("p9_scoring_adapter")
    truth = {"period": 10., "duration_hours": 1.}
    blind = {"period": 10., "T0_btjd": 3000., "duration_days": 89.71/86400}
    seen = {}
    def matcher(times, actual_truth, candidate, ratio=1):
        seen.update(candidate)
        assert actual_truth is truth and ratio == 1
        return {"matched": True}
    monkeypatch.setattr(adapter.scoring, "match_signal", matcher)
    result = adapter.match_tls_signal(np.arange(20)*200/86400, truth, blind, cadence_s=200.)
    assert seen["duration"] == 200/86400
    assert result["tls_duration_floor"]["raw_days"] == blind["duration_days"]
    assert "duration_raw_days" not in blind and truth["duration_hours"] == 1.
