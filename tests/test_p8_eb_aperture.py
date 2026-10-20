import importlib.util
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location("p8_eb_aperture", Path(__file__).resolve().parents[1] / "scripts/p8_eb_aperture.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_variable_background_is_removed_without_removing_source_dimming():
    background = np.linspace(5, 30, 40)
    image = np.broadcast_to(background[:, None, None], (40, 21, 21)).copy()
    source_flux = np.full(40, 100.)
    source_flux[10:15] -= 20
    image[:, 10, 10] += source_flux
    source = {"x": 10., "y": 10., "G": 14.}
    measured, aperture, sky = module.extract(image, source, [source])
    np.testing.assert_allclose(measured, source_flux)
    assert aperture.sum() == 5
    assert sky.sum() >= 20
