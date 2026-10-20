import importlib.util
from pathlib import Path

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location("p8_eb_difference_image", Path(__file__).resolve().parents[1] / "scripts/p8_eb_difference_image.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample():
    time = np.arange(0, 12, 0.01)
    image = np.array([[100., 200.], [300., 400.]])
    flux = image[None, :, :] + 2.5 * time[:, None, None]
    return time, flux


def test_linear_drift_is_removed_with_uneven_baseline_sampling():
    time, flux = sample()
    keep = ~((time % 2 > 0.75) & (time % 2 < 0.81))
    result = module.event_differences(time[keep], flux[keep], 2, 1, 0.2)
    assert len(result["counts"]) == 6
    np.testing.assert_allclose(result["difference"], 0, atol=1e-12)


def test_off_target_dimming_is_recovered_and_one_bad_event_is_resisted():
    time, flux = sample()
    phase = ((time - 1 + 1) % 2) - 1
    inside = np.abs(phase) < 0.1
    flux[inside, 1, 0] -= 15
    flux[inside & (time < 2), 0, 1] -= 500
    result = module.event_differences(time, flux, 2, 1, 0.2)
    np.testing.assert_allclose(result["difference"], [[0, 0], [15, 0]], atol=1e-12)


def test_a_missing_flank_does_not_create_a_difference_event():
    time, flux = sample()
    keep = ~((time > 0.64) & (time < 0.84))
    result = module.event_differences(time[keep], flux[keep], 2, 1, 0.2)
    assert len(result["counts"]) == 5
    assert 0 not in {c["cycle"] for c in result["counts"]}


def test_duplicate_times_are_rejected():
    time, flux = sample()
    time[1] = time[0]
    with pytest.raises(ValueError, match="unique"):
        module.event_differences(time, flux, 2, 1, 0.2)
