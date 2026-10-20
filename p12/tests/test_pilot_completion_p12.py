from pathlib import Path
from types import SimpleNamespace
import csv
import hashlib
import pytest
import json
import subprocess
import sys
import pilot_plan_p12 as P
import part0_handoff_p12 as H
import funnel_plan_p12 as F
from p12_common import read, write, sha


def test_sealed_stageA_replay_executes_with_counts_only_output(tmp_path):
    from p12_common import REPO
    destination=tmp_path/'stageA_fixture'
    completed=subprocess.run([sys.executable,'p12/tests/replay_stageA_p12.py',str(destination)],
        cwd=REPO,capture_output=True,text=True,timeout=1200)
    assert completed.returncode==0
    verdict=json.loads(completed.stdout)
    assert verdict==dict(status='PASS',passed=1,failed=0)
    assert completed.stderr==''
    receipt=read(destination/'replay.json')
    assert receipt['byte_identical'] and receipt['expected_sha256']==receipt['actual_sha256']
    assert receipt['io']['protected_opened'] is False and not receipt['scientific_fields_mocked']


def test_pilot_has_eight_eligible_hosts_per_fixed_band():
    rows = [dict(tic_id=str(100*band+i), tmag=12.5+.5*band+.01*i)
            for band in range(3) for i in range(1, 13)]
    eligible = {int(row['tic_id']) for row in rows if int(row['tic_id']) % 100 != 1}
    rows += [dict(tic_id='9999', tmag=14.0), dict(tic_id='9998', tmag=12.49)]
    eligible.update((9999, 9998))
    actual = P.selected_hosts(list(reversed(rows)), eligible)
    assert len(actual) == 24 and len({row['tic_id'] for row in actual}) == 24
    for band in range(3):
        candidates = [row for row in rows if int(row['tic_id']) in eligible
                      and 12.5+.5*band <= row['tmag'] < 13+.5*band]
        expected = sorted(candidates, key=lambda row: hashlib.sha256(
            ('20260920:p12:timing:' + row['tic_id']).encode()).digest())[:8]
        assert actual[8*band:8*band+8] == expected
    with pytest.raises(RuntimeError, match='Fewer than eight'):
        P.selected_hosts(rows, {100+i for i in range(1, 8)})


def test_pilot_builder_refuses_missing_or_changed_parity(tmp_path, monkeypatch):
    root = tmp_path / 'p12'; monkeypatch.setattr(P, 'ROOT', root); monkeypatch.setattr(P, 'REPO', tmp_path)
    write(root / 'tests/pilot_stageA_replay.json', dict(status='FAIL', byte_identical=False))
    with pytest.raises(RuntimeError, match='replay has not passed'):
        P.prepare_search()
    source = root / 'protocol/funnel_worker_p12.py'; source.parent.mkdir(); source.write_text('original')
    write(root / 'tests/pilot_stageA_replay.json', dict(status='PASS', byte_identical=True,
        p12_sources={'p12/protocol/funnel_worker_p12.py': sha(source)}), replace=True)
    source.write_text('changed')
    with pytest.raises(RuntimeError, match='differs from tested source'):
        P.prepare_search()
    assert not (root / 'manifests/pilot_search_jobs.json').exists()


def phase_fixture(root, phase, count, workers=24):
    folder = root / 'results/controllers' / phase
    write(folder / 'closure.json', dict(status='CLOSED', all_owned_workers_closed=True,
        source_hashes_unchanged=True, pending=0, total=count, unknowns=0, queue_hours=.5))
    jobs = [dict(job_id='j'+str(i)) for i in range(count)]
    write(folder / 'launch.json', dict(workers=workers, frozen_jobs=jobs))
    for i, job in enumerate(jobs):
        write(folder / 'attempts' / (job['job_id']+'.json'), dict(job_id=job['job_id'],
            status='COMPLETE', wall_seconds=960, sampled_cpu_seconds=900))
    return folder


def test_pilot_timing_converts_production_wall_once_without_result_reads(tmp_path, monkeypatch):
    root = tmp_path / 'p12'; monkeypatch.setattr(H, 'ROOT', root); monkeypatch.setattr(H, 'REPO', tmp_path)
    phase_fixture(root, 'pilot_search', 24); phase_fixture(root, 'pilot_A', 5)
    result = H.timing()
    assert result['search_converted_queue_seconds_per_star'] == 40
    assert result['A_converted_queue_seconds_per_star'] == 40
    assert result['A_n_complete'] == 5 and not result['candidate_measurements_opened']
    assert all('/controllers/' in p for p in result['source_closure_paths'].values())


def test_pilot_timing_rejects_wrong_width_and_retains_unknown_denominator(tmp_path, monkeypatch):
    root = tmp_path / 'p12'; monkeypatch.setattr(H, 'ROOT', root); monkeypatch.setattr(H, 'REPO', tmp_path)
    folder = phase_fixture(root, 'pilot_search', 24, workers=8)
    with pytest.raises(RuntimeError, match='production width'):
        H.timing()
    launch = read(folder/'launch.json'); launch['workers'] = 24; write(folder/'launch.json', launch, replace=True)
    row = read(folder/'attempts/j0.json'); row['status'] = 'TIMEOUT'; write(folder/'attempts/j0.json', row, replace=True)
    closure = read(folder/'closure.json'); closure['unknowns'] = 1; write(folder/'closure.json', closure, replace=True)
    phase_fixture(root, 'pilot_A', 0)
    result=H.timing()
    assert result['search_n_complete']==23 and result['search_n_unknown']==1
    assert len(result['search_job_walls_seconds'])==23
    assert result['A_n_complete']==0 and result['A_converted_queue_seconds_per_star'] is None


def test_pilot_collector_uses_p10_pregate_and_emits_only_aggregate_stdout(tmp_path, monkeypatch, capsys):
    root = tmp_path/'p12'; data = tmp_path/'data'; (root/'logs').mkdir(parents=True)
    monkeypatch.setattr(F,'ROOT',root); monkeypatch.setattr(F,'REPO',tmp_path); monkeypatch.setattr(F,'DATA',data)
    monkeypatch.setattr(F,'install',lambda path:None); monkeypatch.setattr(F,'summary',lambda guard:dict(protected_opened=False))
    monkeypatch.setattr(F,'source_hashes',lambda:{})
    monkeypatch.setattr(F,'inspect',lambda path:dict(forbidden=[],malformed_rows=0,sha256='fixture'))
    phase=phase_fixture(root,'pilot_search',1)
    result_path=data/'pilot/runs/survey_p10/results/tic7.json'
    planet=dict(planet_num=1,search='short',period_days=2.,epoch_btjd=1.,duration_days=.1,depth_ppt=3.,
        snr=9.,stitch_snr=8.,stitch_n_transits=4,stitch_epoch_consistent=True)
    fail=dict(planet,planet_num=2,stitch_snr=7.)
    write(result_path,dict(status='ok',tic_id=7,result=dict(planets=[planet,fail])))
    receipt=root/'results/search_receipts/tic7.json'
    write(receipt,dict(preset='survey_p10',status='COMPLETE',result_path=result_path.relative_to(tmp_path).as_posix(),
        result_sha256=sha(result_path),file_access_log='fixture_io.jsonl'))
    attempt=read(phase/'attempts/j0.json'); attempt.update(result_path=receipt.relative_to(tmp_path).as_posix(),result_sha256=sha(receipt))
    write(phase/'attempts/j0.json',attempt,replace=True)
    monkeypatch.setattr(F,'_closed_phase',lambda folder:(read(folder/'closure.json'),read(folder/'launch.json')))
    target=root/'manifests/pilot_targets.csv';target.parent.mkdir(exist_ok=True)
    star=dict(tic_id=7,radius_rsun=.3,mass_msun=.3,teff_k=3300,tmag=13,ra_deg=1,dec_deg=2)
    with target.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(star));writer.writeheader();writer.writerow(star)
    write(root/'manifests/input_identity/tic7.json',dict(fixture=True))
    result=F.collect('pilot')
    jobs=read(root/'manifests/pilot_A_jobs.json')
    assert result['n_accepted']==2 and result['n_pre_gate']==1 and len(jobs)==1
    assert jobs[0]['job_id']=='tic7_p01' and jobs[0]['arguments'][1]=='A'
    runtime=read(tmp_path/jobs[0]['arguments'][2])
    assert runtime['phase']=='pilot' and runtime['arm']=='archival' and runtime['candidate']['planet_num']=='1'
    output=capsys.readouterr().out
    assert 'period_days' not in output and 'tic7' not in output
