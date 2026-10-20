"""Synthetic metadata tests; no actual fresh host selection or signal draws."""
import importlib.util
from pathlib import Path
import pytest


path = Path(__file__).resolve().parents[1] / 'protocol/validation_sampling.py'
spec = importlib.util.spec_from_file_location('p115_validation_sampling_tests', path)
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)


def rows(n=360):
    return [dict(tic_id=1000000+i, outcome_exposed=False, audit_status='COMPLETE',
        input_eligibility='D_core', tmag=12.7 + (i % 3) * .5, teff_k=3200,
        radius_rsun=.3, mass_msun=.3, galactic_lat_deg=30,
        original_p8_stellar_cuts_pass=True,
        verified_native_ffi_sectors=list(range(56, 59 + i % 3 * 3)),
        targeted_ffi_sectors=[], input_receipt_path=f'fixture/{i}.json',
        input_receipt_sha256='a'*64) for i in range(n)]


def level(hosts):
    return dict(hosts=hosts, planet_hosts=hosts//2,
                planet_cases=hosts//2*7, binary_backgrounds=40)


def test_nested_cohorts_keep_hosts_together_and_all_binary_backgrounds():
    source = rows()
    small, medium, full = [V.cohort(source, level(n)) for n in (100, 200, 300)]
    assert small['all_natural_host_ids'] == medium['all_natural_host_ids'][:100]
    assert medium['all_natural_host_ids'] == full['all_natural_host_ids'][:200]
    assert small['binary_host_ids'] == medium['binary_host_ids'] == full['binary_host_ids']
    assert small['planet_host_ids'] == medium['planet_host_ids'][:50]
    assert medium['planet_host_ids'] == full['planet_host_ids'][:100]
    for result in (small, medium, full):
        selected = result['sampled_hosts']
        assert all(r['natural'] for r in selected)
        assert sum(r['planet_injections'] for r in selected) == result['level']['planet_cases']
        assert len(set(result['binary_host_ids'])) == 40
        assert not set(result['planet_host_ids']) & set(result['binary_host_ids'])
        assert sum(r['binary_class'] == 'on_target' for r in selected) == 20
        assert sum(r['binary_class'] == 'diluted' for r in selected) == 20
    assert V.cohort(list(reversed(source)), level(300)) == full


def test_finite_population_weights_and_input_exclusions():
    source = rows()
    source[0] = dict(source[0], input_eligibility='INPUT_INELIGIBLE',
                     exclusion_reasons=['Insufficient verified FFI coverage'])
    result = V.cohort(source, level(100))
    assert result['supported_population_hosts'] == 359
    assert source[0]['tic_id'] not in result['all_natural_host_ids']
    for cells in result['role_stratum_weights'].values():
        for cell in cells.values():
            if cell['selected_hosts']:
                assert cell['analysis_weight'] * cell['selected_hosts'] == pytest.approx(cell['population_hosts'])
                assert cell['inclusion_probability'] * cell['analysis_weight'] == pytest.approx(1)
            else:
                assert cell['analysis_weight'] is None and not cell['represented']


@pytest.mark.parametrize('change', [dict(input_eligibility='UNVERIFIED_METADATA_CANDIDATE'),
    dict(outcome_exposed=True), dict(audit_status='PENDING'),
    dict(targeted_ffi_sectors=[56, 57]), dict(original_p8_stellar_cuts_pass=False),
    dict(input_receipt_sha256=''), dict(flux_metadata={'truth': {'period': 3}})])
def test_unverified_exposed_or_truth_bearing_sampling_input_is_rejected(change):
    source = rows(100)
    source[0].update(change)
    with pytest.raises(ValueError):
        V.cohort(source, level(100))


def test_exclusion_ledger_and_duplicate_hosts_are_enforced():
    source = rows(100)
    with pytest.raises(ValueError, match='Previously exposed'):
        V.cohort(source, level(100), excluded_ids=[source[0]['tic_id']])
    with pytest.raises(ValueError, match='Duplicate'):
        V.cohort(source + [source[0]], level(100))


def test_largest_affordable_level_uses_all_resource_constraints():
    forecasts = [dict(hosts=n, conservative_total_queue_hours=h,
        acquisition_fits_cumulative_limit=True, storage_preserves_30GB_floor=True,
        measured_development_throughput_sha256='b'*64) for n,h in ((100,7),(200,12),(300,17))]
    assert V.choose_level(350, forecasts, 16)['hosts'] == 200
    assert V.choose_level(250, forecasts, 20)['hosts'] == 200
    forecasts[1]['storage_preserves_30GB_floor'] = False
    assert V.choose_level(350, forecasts, 16)['hosts'] == 100
    assert V.choose_level(99, forecasts, 20) is None
    assert V.choose_level(350, forecasts, 6) is None


def test_real_selection_requires_closed_owner_and_actual_eligible_finalist():
    good = dict(finalist='R1_S0_D100_E10', policies=[dict(policy='R1_S0_D100_E10',
                eligible=True, criteria={'recovery': True, 'protection': True})])
    assert V.admission_guard(good, False) == good['finalist']
    with pytest.raises(RuntimeError, match='owner'):
        V.admission_guard(good, True)
    with pytest.raises(RuntimeError, match='finalist'):
        V.admission_guard(dict(finalist=None, policies=[]), False)
    good['policies'][0]['criteria']['protection'] = False
    with pytest.raises(RuntimeError, match='unmet'):
        V.admission_guard(good, False)
