import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from p12_common import REPO, sha, write, read

DEV = Path(__file__).resolve().parents[1] / 'work/dev'
if DEV.is_dir() and str(DEV) not in sys.path:
    sys.path.append(str(DEV))

import plan_part2_p12 as P
import retention_p12 as RET
import compare_arms_p12 as CMP
import sml_gate_p12 as G
import funnel_stage_p12 as FS
from ledger_helper import ledger_once


def _result(tic):
    planets = [dict(planet_num=1, search='s', period_days=2.5, epoch_btjd=3000.1, duration_days=0.05, depth_ppt=2.0, snr=12.0,
                    n_transits_observed=9, stitch_snr=10.0, stitch_n_transits=9, stitch_epoch_consistent=True,
                    stitch_period_days=2.5, stitch_depth_ppt=2.1, verdict='candidate'),
               dict(planet_num=2, search='s', period_days=7.1, epoch_btjd=3001.2, duration_days=0.07, depth_ppt=1.0, snr=8.0,
                    n_transits_observed=3, stitch_snr=6.0, stitch_n_transits=3, stitch_epoch_consistent=True,
                    stitch_period_days=7.1, stitch_depth_ppt=1.1, verdict='candidate')]
    return dict(status='ok', tic_id=tic, n_units=4, baseline_days=300.0, n_cadences_raw=5000,
                rotation_proxy=dict(peak_period_days=3.0, semi_amplitude_ppt=0.4, scatter_ppt=1.0), prepare_counters=dict(mad_ppt=2.2),
                result=dict(planets=planets, vetting=[dict(planet_num=1, flags_high=['x'], flags_medium=[])], notes=[]))


def test_collect_rows_equal_the_p10_collect(tmp_path, monkeypatch):
    sys.path[:0] = [str(REPO / 'src'), str(REPO / 'scripts'), str(REPO / 'p10/protocol')]
    import p10_funnel_calibration as F
    run = tmp_path / 'run'
    (run / 'results').mkdir(parents=True)
    (run / 'results/tic7.json').write_text(json.dumps(_result(7)))
    star = dict(tic_id=7, tmag=13.0, teff_k=3300.0, radius_rsun=0.3, mass_msun=0.3, ra_deg=1.0, dec_deg=2.0)
    targets = tmp_path / 'targets.csv'
    with targets.open('w', newline='', encoding='utf-8') as stream:
        w = csv.DictWriter(stream, fieldnames=list(star)); w.writeheader(); w.writerow(star)
    monkeypatch.setattr(F, 'OUT', tmp_path / 'out'); monkeypatch.setattr(F, 'CANDIDATES', tmp_path / 'out/candidates.csv')
    monkeypatch.setattr(F, 'SURVIVORS', tmp_path / 'out/survivors.csv')
    F.collect(run, targets)
    expected = list(csv.DictReader((tmp_path / 'out/candidates.csv').open(encoding='utf-8')))
    rows = P.collect_rows(_result(7), {k: str(v) for k, v in star.items()})
    assert [{k: str(v) for k, v in r.items()} for r in rows] == expected
    assert [r['passes_pregate'] for r in rows] == [True, False]


def test_c_sample_reproduces_the_p10_design():
    passers = [dict(candidate_id=f'inj{i:05d}', snr_expected=s) for i, s in enumerate(np.linspace(7, 49.9, 90))]
    chosen, bins = P.sample_bins(passers, [[7, 12], [12, 20], [20, 50]], 10, 20260908)
    rng = np.random.default_rng(20260908)
    expected = []
    for lo, hi in ((7, 12), (12, 20), (20, 50)):
        pool = sorted([p for p in passers if lo <= p['snr_expected'] < hi], key=lambda p: p['candidate_id'])
        pick = rng.choice(len(pool), size=min(10, len(pool)), replace=False)
        expected += [pool[i]['candidate_id'] for i in sorted(pick)]
    assert [c['candidate_id'] for c in chosen] == expected and len(chosen) == 30 and all(b['pool'] >= 10 for b in bins)


def test_retention_matcher_reproduces_the_sealed_p10_3_count():
    ledger_once(None, 'Part 2 test: sealed P10.3 retention reproduced through retention_p12', 'p10/part3/results/matching.json',
                'test_part2_p12 retention', 'P10.3')
    table = RET.reproduce_p10_3()
    assert (table['recovered'], table['present_families']) == (156, 377)


def _levels(n, recovered_a, recovered_b, snr=10.0, unknown_b=0):
    a = {f'inj{i:05d}': dict(tic_id=i % 7, snr_expected=snr, recovered=i < recovered_a, through_S=i < recovered_a,
                             search_unknown=False, funnel_unknown=False) for i in range(n)}
    b = {f'inj{i:05d}': dict(tic_id=i % 7, snr_expected=snr, recovered=i < recovered_b, through_S=i < recovered_b,
                             search_unknown=i >= n - unknown_b, funnel_unknown=False) for i in range(n)}
    return a, b


def test_paired_gain_counts_an_unknown_as_a_b_miss_and_an_a_recovery():
    a, b = _levels(100, 50, 60)
    assert CMP.paired_gain(a, b, sorted(a), 'recovered')['gain_pp'] == pytest.approx(10.0)
    a, b = _levels(100, 50, 60, unknown_b=40)
    gain = CMP.paired_gain(a, b, sorted(a), 'recovered')
    assert gain['baseline'] == 90 and gain['proposed'] == 60 and gain['ci95_pp'][0] <= gain['gain_pp'] <= gain['ci95_pp'][1]


def test_sml_gate_thresholds(tmp_path, monkeypatch):
    root = tmp_path / 'p12'
    (root / 'protocol').mkdir(parents=True)
    write(root / 'protocol/config.json', dict(sml=dict(minimum_hosts=2, minimum_product_fraction=0.15)))
    (root / 'manifests/part2').mkdir(parents=True)
    (root / 'manifests/part2/e_cal_hosts.csv').write_text('tic_id\n1\n2\n3\n')
    inv = dict(products=[dict(tic_id=1, uses_sml=True, generation='QLP_pre94'), dict(tic_id=2, uses_sml=True, generation='QLP_pre94'),
                         *[dict(tic_id=3, uses_sml=False, generation='SPOC') for _ in range(8)]])
    write(root / 'manifests/sml_inventory.json', inv)
    monkeypatch.setattr(G, 'ROOT', root)
    assert G.gate()['run_arm_b'] is True
    inv['products'][1]['uses_sml'] = False
    write(root / 'manifests/sml_inventory.json', inv, replace=True)
    (root / 'manifests/sml_gate.json').unlink()
    (root / 'results/part2').mkdir(parents=True)
    assert G.gate()['run_arm_b'] is False
    assert read(root / 'results/part2/photometry_decision.json')['reason'] == 'NOT_TESTABLE'


def test_stage_runtime_refuses_truth_fields_and_changed_injected_arrays(tmp_path, monkeypatch):
    with pytest.raises(RuntimeError, match='truth'):
        FS._reject_truth({'candidate': {'injection_model': {}}})
    FS._reject_truth({'candidate': {'period_days': 1.0}})
    raw = tmp_path / 'data/raw'
    raw.mkdir(parents=True)
    np.savez_compressed(raw / 'product_000.npz', time=np.arange(3.0), flux=np.ones(3))
    index = raw / 'index.json'
    write(index, dict(tic_id=5, products=[dict(metadata=dict(sector=60, author='QLP'), raw_path='data/raw/product_000.npz',
                                                raw_sha256=sha(raw / 'product_000.npz'))]))
    monkeypatch.setattr(FS, 'REPO', tmp_path)
    loader = FS._injected_loader('data/raw/index.json', sha(index), 5)
    assert loader(5)[0]['sector'] == 60
    with pytest.raises(RuntimeError, match='another star'):
        loader(6)
    np.savez_compressed(raw / 'product_000.npz', time=np.arange(4.0), flux=np.ones(4))
    with pytest.raises(RuntimeError, match='changed'):
        loader(5)
    with pytest.raises(RuntimeError, match='index changed'):
        FS._injected_loader('data/raw/index.json', '0' * 64, 5)
