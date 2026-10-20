"""No partial retention estimates, lost EB collisions, or hidden control flips."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "p10_c_measurement", Path(__file__).resolve().parents[1] / "p10/protocol/measure_completed_c_controls.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


def inputs():
    items, receipts, adv = [], [], []
    for i in range(71):
        kind = "inj" if i < 30 else "adv"
        identifier, key = f"case{i}", f"key{i}"
        rec = {"key": key, "tic_id": 100 + (i - 30) % 18}
        if kind == "inj":
            rec.update(bin=list(M.BINS)[i // 10], snr_expected=(7, 12, 20)[i // 10])
        else:
            adv.append({"candidate_id": identifier, "key": key, "tic_id": rec["tic_id"],
                        "survey_to_catalogue_alias": "1:2" if i < 36 else "2:1" if i == 36 else "1:1"})
        item = {"id": identifier, "set": kind, "workspace": identifier, "record": rec}
        receipt = {"id": identifier, "set": kind, "workspace": identifier, "key": key,
                   "wall_s": 1., "fallback": {"triggered": False}, "bin": rec.get("bin"),
                   "snr_expected": rec.get("snr_expected"),
                   **{c: "PASS" if kind == "inj" else "FAIL" for c in M.COLUMNS}}
        items.append(item); receipts.append(receipt)
    return items, receipts, adv


@pytest.mark.parametrize("change", [{"status": "running"}, {"n_complete": 70}, {"active_id": "case70"}])
def test_incomplete_queue_has_no_final_measurement(change):
    state = {"status": "controls_complete_review_required", "n_expected": 71, "n_complete": 71, "active_id": None}
    state.update(change)
    with pytest.raises(RuntimeError, match="must finish"):
        M.require_complete_queue(state, False)


def test_completion_state_with_lock_still_refuses():
    with pytest.raises(RuntimeError):
        M.require_complete_queue({"status": "controls_complete_review_required", "n_expected": 71,
                                  "n_complete": 71, "active_id": None}, True)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unsettled", "wrong_bin"])
def test_partial_or_unpaired_census_cannot_report_retention(mutation):
    items, receipts, adv = inputs()
    if mutation == "missing":
        receipts.pop()
    elif mutation == "duplicate":
        receipts[-1] = deepcopy(receipts[-2])
    elif mutation == "unsettled":
        receipts[-1]["b_with_fallback"] = "NEEDS_RESIDUAL"
    else:
        receipts[0]["snr_expected"] = 12
    with pytest.raises(RuntimeError):
        M.summarize(items, receipts, adv)


def test_equal_injection_pass_rate_meets_inclusive_condition():
    result = M.summarize(*inputs())
    assert result["injection_b_pass_rate_at_least_a"] == {"installed": True, "with_fallback": True}
    assert result["injection_retention"]["all"]["b_installed"]["pass"] == 30


def test_one_lost_injection_fails_retention_condition():
    items, receipts, adv = inputs()
    receipts[0]["b_installed"] = receipts[0]["b_with_fallback"] = "FAIL"
    result = M.summarize(items, receipts, adv)
    assert not any(result["injection_b_pass_rate_at_least_a"].values())


def test_same_rounded_key_keeps_both_eb_candidates_and_exposes_bad_alias():
    items, receipts, adv = inputs()
    items[31]["record"]["key"] = receipts[31]["key"] = adv[1]["key"] = receipts[30]["key"]
    receipts[31]["b_installed"] = receipts[31]["b_with_fallback"] = "PASS"
    result = M.summarize(items, receipts, adv)
    assert result["n_adversarial_candidates"] == 41
    assert result["adversarial_a_to_b_flips"]["installed"] == ["case31"]
    assert result["half_double_passes"]["b_installed"] == ["case31"]


def test_any_eb_fallback_flip_is_exposed_even_outside_alias_subset():
    items, receipts, adv = inputs()
    receipts[-1]["a_with_fallback"] = receipts[-1]["b_with_fallback"] = "PASS"
    receipts[-1]["fallback"]["triggered"] = True
    result = M.summarize(items, receipts, adv)
    assert result["adversarial_fallback_fail_to_pass"] == {"a": ["case70"], "b": ["case70"]}
    assert result["fallback_trigger_ids"] == ["case70"]
    assert not any(result["half_double_passes"].values())


def normalized_spectrum():
    import numpy as np
    from transitleastsquares.stats import spectra
    chi2 = np.random.default_rng(1).uniform(10.0, 11.0, 600)
    chi2[123] = 2.0
    sr, raw, power, _, sde = spectra(chi2, 3)
    periods = np.linspace(0.5, 10.0, len(chi2))
    arrays = dict(periods=periods, power=power, chi2=chi2, SR=sr, power_raw=raw)
    return arrays, {"period": float(periods[np.argmax(power)]), "SDE": float(sde)}


def test_tls_scalar_and_rescaled_peak_can_differ_without_corrupt_evidence(monkeypatch):
    import numpy as np
    from transitleastsquares import transitleastsquares
    arrays, blind = normalized_spectrum()
    original = {name: value.copy() for name, value in arrays.items()}
    # This is the upstream floating-point behavior that broke exact max=SDE.
    assert float(np.max(arrays["power"])) != blind["SDE"]
    def forbidden_search(*args, **kwargs):
        pytest.fail("Saved-spectrum verification must not launch TLS")
    monkeypatch.setattr(transitleastsquares, "power", forbidden_search)
    peak = M.verify_saved_spectrum_peak(arrays, blind, 3)
    assert peak == {**blind, "index": 123}
    for name, value in arrays.items():
        np.testing.assert_array_equal(value, original[name])


@pytest.mark.parametrize("changed", ["period", "SDE", "SR", "power_raw", "power", "chi2"])
def test_peak_verification_rejects_changed_summary_or_normalization(changed):
    import numpy as np
    arrays, blind = normalized_spectrum()
    if changed in blind:
        blind[changed] = float(np.nextafter(blind[changed], np.inf))
    elif changed == "chi2":
        arrays[changed][123] *= 0.9
    else:
        arrays[changed][123] = np.nextafter(arrays[changed][123], np.inf)
    with pytest.raises(RuntimeError, match="differ"):
        M.verify_saved_spectrum_peak(arrays, blind, 3)
