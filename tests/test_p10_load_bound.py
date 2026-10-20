"""A conservative missing-population bound must dominate all admissible yields."""
import importlib.util
import itertools
from pathlib import Path

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p10_load_bound_test',ROOT/'p10/protocol/project_part2d_load_bound.py')
B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)


def test_maximum_subset_bound_covers_every_subset_and_probability_weighting():
    values=[.2,.7,.1,.6,.4]
    bound=B.maximum_subset_sum(values,3)
    rng=np.random.default_rng(20260908)
    for n in range(4):
        for subset in itertools.combinations(values,n):
            assert sum(subset)<=bound+1e-15
            assert sum(v*p for v,p in zip(subset,rng.uniform(0,1,n)))<=bound+1e-15


def test_geometry_matches_the_original_yield_convention():
    cells=[dict(label='test',rate=.6,p_lo=1.,p_hi=4.,r_rep=2.)]
    row=B.stellar_weights(.35,'',cells)[0]
    rp_rs=2.*B.R_EARTH_RSUN/.35
    a_rs=B.survey.a_over_rs(2.,.35,.35)
    assert row['weight']==pytest.approx(.97*.6*min(1.,(1.+rp_rs)/a_rs))
    assert B.stellar_weights(.35,'nan',cells)==B.stellar_weights(.35,'',cells)


def test_invalid_geometry_does_not_claim_a_finite_bound():
    with pytest.raises(ValueError):B.stellar_weights(float('nan'),1.,[])
    with pytest.raises(ValueError):B.maximum_subset_sum([.1,float('nan')],1)
    with pytest.raises(ValueError):B.maximum_subset_sum([.1],2)
