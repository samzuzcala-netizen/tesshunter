"""Only exactly reproduced TLS empty-duration chi2 sentinels may pass validation."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import numpy as np
import pytest
from transitleastsquares.stats import spectra

PROTOCOL = Path(__file__).resolve().parents[1] / "p10/protocol"
sys.path.insert(0, str(PROTOCOL))
spec = importlib.util.spec_from_file_location("checked_eb", PROTOCOL / "run_original_adversarial_c_checked.py")
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)


def data():
    chi2 = np.array([np.inf, 2., 3., 4., 5., 6.])
    sr, raw, power, _, _ = spectra(chi2, 3)
    return dict(periods=np.arange(1., 7.), chi2=chi2, SR=sr, power_raw=raw, power=power)


def test_positive_infinity_requires_exact_empty_duration_proof_and_changes_no_array():
    arrays = data(); before = deepcopy(arrays)
    assert A.check_arrays(arrays, 3, np.isposinf(arrays["chi2"])) == 1
    assert all(np.array_equal(arrays[k], before[k]) for k in arrays)
    with pytest.raises(RuntimeError, match="Unproved"): A.check_arrays(arrays, 3)


@pytest.mark.parametrize("damage", ["nan", "negative_inf", "zero", "all_inf", "finite_power_nan", "changed_raw", "changed_sr", "missing", "shape", "wrong_empty_mask"])
def test_other_invalid_arrays_or_unreproduced_normalization_are_rejected(damage):
    arrays = data(); empty = np.isposinf(arrays["chi2"])
    if damage == "nan": arrays["chi2"][1] = np.nan
    elif damage == "negative_inf": arrays["chi2"][1] = -np.inf
    elif damage == "zero": arrays["chi2"][1] = 0
    elif damage == "all_inf": arrays["chi2"][:] = np.inf
    elif damage == "finite_power_nan": arrays["power"][1] = np.nan
    elif damage == "changed_raw": arrays["power_raw"][1] = np.nextafter(arrays["power_raw"][1], np.inf)
    elif damage == "changed_sr": arrays["SR"][0] = 0.1
    elif damage == "missing": arrays.pop("power_raw")
    elif damage == "shape": arrays["SR"] = arrays["SR"][:-1]
    else: empty[0] = False
    with pytest.raises(RuntimeError): A.check_arrays(arrays, 3, empty)


def test_successful_original_validation_is_returned_unchanged(monkeypatch):
    expected = {"id":"finite_case", "a_installed":"PASS", "wall_s":12.3}
    monkeypatch.setattr(A, "load_contract", lambda: {})
    monkeypatch.setattr(A, "ORIGINAL_VALIDATE", lambda item: expected)
    assert A.validate_case({"id":"finite_case"}) is expected


def test_other_original_validation_failures_are_never_relaxed(monkeypatch):
    monkeypatch.setattr(A, "load_contract", lambda: {})
    def fail(item): raise RuntimeError("Candidate changed")
    monkeypatch.setattr(A, "ORIGINAL_VALIDATE", fail)
    with pytest.raises(RuntimeError, match="Candidate changed"): A.validate_case({"id":"bad"})
