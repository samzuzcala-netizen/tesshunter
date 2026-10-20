import csv
import json
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'protocol'))
from common import write, read, sha
import prepare_part_f_v1 as planner
import forced_fit_worker_v1 as worker
import part_f_guards_v1 as guards


@pytest.fixture
def registered_fixture(tmp_path,monkeypatch):
    repo=tmp_path;root=repo/'p10/part3'
    for mod in (planner,worker):
        monkeypatch.setattr(mod,'REPO',repo);monkeypatch.setattr(mod,'ROOT',root)
    monkeypatch.setattr(guards,'ROOT',root)
    monkeypatch.setattr(planner,'verify',lambda **kwargs: {})
    write(root/'manifests/allocation.json',{'selected_tic_ids':[1,2]})
    write(root/'manifests/part_f_method_registration_v1.json',{'source_hashes':{},'assumptions':['synthetic fixture']})
    write(root/'manifests/early_funnel_closed_evidence_seal.json',{'files':{}})
    write(root/'manifests/exposure_ledger.json',{'stages':[{'tics':list(range(1,532))}],
          'part_f_opened':False,'development_exposed':False})
    write(root/'manifests/C_cap_at_B_closure.json',{'N_C':13})
    write(root/'manifests/resource_ledger.json',{'new_queue_hours':1.,'intervals':[]})
    hashes={}
    noises={}
    rng=np.random.Generator(np.random.PCG64(2026091402))
    for tic in (1,2):
        native=repo/f'data/native{tic}.npz';native.parent.mkdir(parents=True,exist_ok=True)
        t=np.sort(rng.uniform(0,20,2000));mask=((t-.5+.05)%2)<.1
        np.savez(native,time=t,flux=1-.01*mask+rng.normal(0,.001,len(t)))
        n=dict(prepared_path=native.relative_to(repo).as_posix(),prepared_sha256=sha(native),
               sigma=.001,n_cad=len(t),midpoint_btjd=10.,cadence_days=.002)
        noises[tic]=n
        p=root/f'results/native_noise/tic{tic}.json';write(p,n);hashes[p.relative_to(repo).as_posix()]=sha(p)
        for preset in ('survey_p10','survey_p8'):
            write(root/f'manifests/search_runtime/{preset}_tic{tic}.json',{'prepared_sha256':n['prepared_sha256']})
    write(root/'manifests/input_data_seal.json',{'hashes':hashes})
    seals=[]
    for preset in ('survey_p10','survey_p8'):
        hosts=[dict(tic_id=tic,status='COMPLETE',prepared_sha256=noises[tic]['prepared_sha256'],
                    accepted=[dict(candidate_id=f'tic{tic}_p01',period_days=2. if tic==1 else 20.,epoch_btjd=.5)]) for tic in (1,2)]
        p=root/f'manifests/predictions_{preset}.json';write(p,{'hosts':hosts})
        seals.append({'path':p.relative_to(repo).as_posix(),'sha256':sha(p)})
    monkeypatch.setattr(planner,'both_locked',lambda: seals)
    base=dict(ticid='1',tce_period='2',tce_period_err='0',tce_time0bt='.5',tce_duration='2.4',
              tce_depth='1000',tce_model_snr='15',tce_num_transits='4',source_filename='old.csv',
              source_row='1',independence='INDEPENDENT')
    rows=[base,dict(base,tce_period='2.005',source_filename='new.csv',independence='OVERLAPPING',
                    tce_period_err='nan',tce_model_snr='20',tce_depth='2000'),
          dict(base,ticid='2',tce_period='40',source_row='2',tce_period_err='nan')]
    side=repo/'data/sidecar.csv'
    with side.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(base));w.writeheader();w.writerows(rows)
    write(root/'manifests/sidecar.json',{'path':side.relative_to(repo).as_posix(),'sha256':sha(side)})
    return repo,root,side


def test_planner_includes_outside_family_and_stratum_representatives(registered_fixture):
    repo,root,side=registered_fixture
    planner.main()
    m=read(root/'results/matching.json')
    assert m['raw_rows']==3 and m['families']==2
    assert len(read(root/'manifests/forced_fits_jobs.json'))==2
    f=m['ephemeris_families'][0]
    assert f['representative_row_id']=='new.csv#1'
    assert f['strata']['INDEPENDENT']['representative_row_id']=='old.csv#1'
    assert f['strata']['UNION']['presets']['survey_p10']['status']=='RECOVERED_EXACT'
    outside=m['ephemeris_families'][1]
    assert outside['strata']['UNION']['presets']['survey_p10']['status']=='OUTSIDE_DOMAIN'
    assert m['rows'][-1]['presets']['survey_p10']['associations'][0]['recovered']
    exposure=read(root/'manifests/exposure_ledger.json')
    assert exposure['development_exposed'] and len(exposure['development_exposed_tic_ids'])==531
    with pytest.raises(RuntimeError,match='already opened'):planner.main()


def test_sidecar_mismatch_stops_before_exposure(registered_fixture):
    repo,root,side=registered_fixture
    side.write_bytes(side.read_bytes()+b'\n')
    with pytest.raises(guards.IntegrityFailure,match='sidecar'):planner.main()
    assert not read(root/'manifests/exposure_ledger.json')['part_f_opened']
    assert not (root/'manifests/part_f_entry_v1.json').exists()


def test_both_prediction_locks_are_required_before_exposure(registered_fixture,monkeypatch):
    repo,root,side=registered_fixture
    def missing():raise FileNotFoundError('second prediction lock missing')
    monkeypatch.setattr(planner,'both_locked',missing)
    with pytest.raises(FileNotFoundError):planner.main()
    assert not read(root/'manifests/exposure_ledger.json')['part_f_opened']


def test_worker_fits_once_and_unknown_search_is_not_a_miss(registered_fixture):
    repo,root,side=registered_fixture
    p=root/'manifests/predictions_survey_p8.json';pred=read(p)
    pred['hosts'][0].update(status='OPERATIONAL_UNKNOWN',accepted=[])
    pred['hosts'][0].pop('prepared_sha256')
    write(p,pred,replace=True)
    planner.main()
    matching=read(root/'results/matching.json')
    assert matching['ephemeris_families'][0]['strata']['UNION']['presets']['survey_p8']['status']=='OPERATIONAL_UNKNOWN'
    job=read(root/'manifests/forced_fits_jobs.json')[0]
    # The synthetic unknown-search fixture has no sealed real prediction hash;
    # refresh its fixture runtime hash to the changed fixture, before the fit.
    runtime=read(repo/job['arguments'][1]);runtime['prediction_hashes'][p.relative_to(repo).as_posix()]=sha(p)
    write(repo/job['arguments'][1],runtime,replace=True)
    worker.main(job['arguments'][1],sha(repo/job['arguments'][1]))
    result=read(repo/job['result_path'])
    assert result['status']=='COMPLETE' and result['presence']=='PRESENT'
    assert result['scientific_attempt']==1
    with pytest.raises(RuntimeError,match='No scientific retry'):
        worker.main(job['arguments'][1],sha(repo/job['arguments'][1]))


def test_worker_records_unknown_for_unfittable_duration(registered_fixture):
    repo,root,side=registered_fixture
    planner.main();job=read(root/'manifests/forced_fits_jobs.json')[0]
    p=repo/job['arguments'][1];r=read(p);r['representative']['tce_duration']='nan';write(p,r,replace=True)
    with pytest.raises(SystemExit) as error:worker.main(job['arguments'][1],sha(p))
    assert error.value.code==2
    assert read(repo/job['result_path'])['presence']=='OPERATIONAL_UNKNOWN'


def test_worker_integrity_failure_signals_controller(registered_fixture):
    repo,root,side=registered_fixture
    planner.main();job=read(root/'manifests/forced_fits_jobs.json')[0]
    runtime=read(repo/job['arguments'][1]);noise=read(repo/runtime['noise_path']);native=repo/noise['prepared_path']
    native.write_bytes(b'changed')
    with pytest.raises(guards.IntegrityFailure):worker.main(job['arguments'][1],job['arguments'][2])
    assert (root/'results/active_integrity_failure.json').exists()
    with pytest.raises(guards.IntegrityFailure):guards.assert_no_integrity_failure(root)
    assert not (repo/job['result_path']).exists()


def test_controller_refuses_a_durable_integrity_failure_before_starting(registered_fixture,monkeypatch):
    import controller_v4 as controller
    repo,root,side=registered_fixture
    write(root/'results/active_integrity_failure.json',{'error':'synthetic integrity failure'})
    monkeypatch.setattr(controller,'ROOT',root)
    monkeypatch.setattr(sys,'argv',['controller_v4.py','--phase','test','--jobs','unused.json','--workers','1','--deadline','1'])
    with pytest.raises(guards.IntegrityFailure):controller.main()
    assert not (root/'manifests/controller_owner.json').exists()
