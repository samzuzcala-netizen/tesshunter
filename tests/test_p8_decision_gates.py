"""Recorded gate decisions must survive serialization of rounded display values."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import p8_decisions as D


def scan():
    return {'primary': {'phase': 0.0},
            'secondaries': [{'phase': 0.0604, 'depth_ppt': 3.3583, 'err_ppt': 0.2612}],
            'deepest_secondary_in_sap': {'phase': 0.0604, 'depth_ppt': 0.7574, 'err_ppt': 0.2521},
            'planet_secondary_bound': {'max_planetary_secondary_ppt': 0.001200952706435961},
            'n_dips_above_5sigma': 8, 'period_days': 11.438573918528276,
            'box_width_days': 0.0928317766722556}


def test_exact_recorded_gate_wins_over_rounded_display_reconstruction():
    record = scan()
    assert D.gate_variants_from(record)['bound'] == 'PASS'
    gates = {name: 'PASS' for name in D.SEC_VARIANTS}
    gates.update(bound='FAIL', quiet_bound_hold='HOLD')
    record['gate_by_mode'] = gates
    assert D.gate_variants_from(record) == gates
    assert D.gate_variants_from(record) is not gates


def test_old_scan_without_variant_decisions_still_reconstructs():
    record = scan()
    record['deepest_secondary_in_sap']['depth_ppt'] = 0.758
    assert D.gate_variants_from(record)['bound'] == 'FAIL'


def test_recorded_quiet_gate_is_not_rebuilt_from_the_displayed_independent_dip_count():
    record = scan()
    record['n_dips_above_5sigma'] = 2
    record['deepest_secondary_in_sap']['depth_ppt'] = 0.758
    assert D.gate_variants_from(record)['quiet_bound'] == 'FAIL'
    gates = {name: 'PASS' for name in D.SEC_VARIANTS}
    gates['bound'] = 'FAIL'
    record['gate_by_mode'] = gates
    assert D.gate_variants_from(record) == gates


def test_incomplete_current_gate_map_is_rejected():
    record = scan()
    record['gate_by_mode'] = {'bound': 'FAIL'}
    with pytest.raises(ValueError, match='incomplete recorded secondary'):
        D.gate_variants_from(record)
