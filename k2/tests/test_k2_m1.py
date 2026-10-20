"""RULES_K2 section 4 (M1): a two-planet synthetic system.  Unmasked, the blind TLS strongest peak is the
stronger planet b; with b masked as a sibling (+/- 1 x T14), the blind TLS returns planet c's own period."""
import numpy as np

import c_input_k2 as CI


def _system(seed=7):
    rng = np.random.default_rng(seed)
    t = np.arange(0.0, 60.0, 30.0 / 1440.0)
    f = np.ones_like(t)
    planets = {"b": (3.3, 0.71, 2.4 / 24, 4e-3), "c": (7.9, 2.05, 3.0 / 24, 1.6e-3)}
    for p, t0, t14, depth in planets.values():
        ph = np.abs(((t - t0 + 0.5 * p) % p) - 0.5 * p)
        f -= depth * (ph < 0.5 * t14)
    f += rng.normal(0.0, 5e-4, t.size)
    return t, f, np.full(t.size, 5e-4), planets


def _tls(t, f, e):
    import audit_p5 as A
    A.set_input_config(None)
    r = A.run_tls(t, f, e, 0.8, 20.0, 0.75, 0.78, 3, 4)
    return float(r.period)


def test_sibling_mask_returns_masked_planets_own_period():
    t, f, e, planets = _system()
    arrays = {"time": t, "flux": f, "flux_err": e, "time_unbinned": t, "sector_unbinned": np.full(t.size, 60)}
    prods = [{"sector": 60, "cadence_s": 1800.0}]
    p_b, t0_b, t14_b, _ = planets["b"]
    p_c = planets["c"][0]
    t1, f1, e1, _ = CI.transform(arrays, prods, "K1")
    assert abs(_tls(t1, f1, e1) / p_b - 1.0) < 0.01
    sib = [{"candidate_id": "b", "period": p_b, "t0": t0_b, "t14": t14_b, "stitch_snr": 50.0}]
    t2, f2, e2, info = CI.transform(arrays, prods, "K1", sib)
    assert info["n_sibling_masked"] > 0
    assert abs(_tls(t2, f2, e2) / p_c - 1.0) < 0.01
