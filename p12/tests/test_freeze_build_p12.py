"""The Part 3 freeze entry point (AMENDMENTS_P12.md, 2026-09-26): amended constants recorded as rules_p12.install_hash
records them, so a scalar constant no longer fails the freeze."""
import json

import rules_p12
from freeze_build_p12 import amended


def test_amended_constants_keep_scalars_and_list_tuples():
    out = amended(rules_p12.AMENDED)
    assert out == {'TIER_DENSITY_RATIO_RANGE': [0.5, 2.5], 'TIER_ODD_EVEN_SIGMA': 3.5}
    json.dumps(out, allow_nan=False)


def test_amended_matches_the_install_hash_representation():
    assert amended({'a': (1, 2), 'b': 3.0, 'c': 'x'}) == {'a': [1, 2], 'b': 3.0, 'c': 'x'}
