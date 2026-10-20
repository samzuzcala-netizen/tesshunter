"""K1 change 7: E_new ranking reproduces the review's top-10,000 K yield (9.0) within 10% on its inputs."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import rank_k1 as RK

SRC = Path(r"C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\population_analysis_2026-10-07")


@pytest.mark.skipif(not (SRC / "pop_tiles.pkl").exists(), reason="review inputs not present")
def test_reproduces_review_top10k_within_10pct(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "work" / "reproduce_review_yield.py"
    spec = importlib.util.spec_from_file_location("repro", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "write", lambda *a, **k: None)
    mod.main()


def test_e_new_grows_with_usable_sectors_and_falls_with_noise():
    df = pd.DataFrame({"Tmag": [11.5] * 3, "rad": [0.7] * 3, "mass": [0.7] * 3, "contratio": [0.01] * 3,
                       "n_usable": [5, 15, 15], "n_2min_all": [0, 0, 0], "n_obs_le105": [5, 15, 15]})
    e = RK.e_new(df, np.array(["K_late"] * 3))
    assert e.iloc[1] > e.iloc[0] > 0
    noisy = RK.e_new(df, np.array(["K_late"] * 3), noise_scale=[1.0, 1.0, 2.0])
    assert noisy.iloc[2] < noisy.iloc[1]
