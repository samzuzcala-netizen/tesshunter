import numpy as np
import pytest

from tesshunter.tls_epoch import final_T0_fit


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("margin", [0, 0.01, 0.2])
def test_epoch_scan_matches_upstream_exactly(seed, margin):
    from transitleastsquares.stats import final_T0_fit as original
    rng = np.random.default_rng(seed)
    period = 0.5 + rng.random() * 25
    t = np.sort(2800 + rng.random(700) * 800)
    # Exercise exact phase ties and the stable-sort fallback as well as phase wraps.
    if seed % 2:
        t[20:23] = t[20]
    y = 1 + rng.normal(0, 0.005, len(t))
    y[35:45] -= 0.02
    duration = 17 + seed * 6
    signal = 1 - 0.1 * np.sin(np.linspace(0, np.pi, duration)) ** 2
    arguments = dict(signal=signal, depth=0.98, t=t, y=y, dy=rng.uniform(0.001, 0.02, len(t)),
                     period=period, T0_fit_margin=margin, show_progress_bar=False, verbose=False)
    assert final_T0_fit(**arguments) == original(**arguments)


def test_epoch_scan_preserves_first_minimum_for_identical_flux():
    from transitleastsquares.stats import final_T0_fit as original
    t = 3000 + np.arange(400) / 432
    args = dict(signal=np.full(12, 0.99), depth=0.99, t=t, y=np.ones(len(t)), dy=np.ones(len(t)),
                period=0.8, T0_fit_margin=0.01, show_progress_bar=False, verbose=False)
    assert final_T0_fit(**args) == original(**args) == min(t)


def test_epoch_scan_restores_upstream_after_an_exception():
    import importlib
    from tesshunter.tls_epoch import equivalent_epoch_scan
    main = importlib.import_module("transitleastsquares.main")
    original = main.final_T0_fit
    with pytest.raises(RuntimeError, match="power failed"):
        with equivalent_epoch_scan():
            assert main.final_T0_fit is final_T0_fit
            raise RuntimeError("power failed")
    assert main.final_T0_fit is original


def test_epoch_scan_retains_unknown_upstream_version(monkeypatch):
    import importlib
    from tesshunter.tls_epoch import equivalent_epoch_scan
    version = importlib.import_module("transitleastsquares.version")
    main = importlib.import_module("transitleastsquares.main")
    original = main.final_T0_fit
    monkeypatch.setattr(version, "TLS_VERSIONING", "future")
    with equivalent_epoch_scan():
        assert main.final_T0_fit is original


@pytest.mark.parametrize("native", [False, True])
def test_audit_routes_only_native_tls_to_equivalent_epoch_scan(monkeypatch, native):
    import importlib
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import audit_p5 as A
    from tesshunter.survey import get_config
    tls = importlib.import_module("transitleastsquares")
    main = importlib.import_module("transitleastsquares.main")
    original = main.final_T0_fit
    monkeypatch.setattr(A, "INPUT_CONFIG", get_config("survey_p8") if native else None)

    class Model:
        def __init__(self, *arrays):
            pass

        def power(self, **arguments):
            assert arguments["T0_fit_margin"] == 0.01
            assert main.final_T0_fit is (final_T0_fit if native else original)
            return "fit"

    monkeypatch.setattr(tls, "transitleastsquares", Model)
    assert A.run_tls([], [], [], 1, 2, 0.3, 0.3, 5, 1) == "fit"
    assert main.final_T0_fit is original
