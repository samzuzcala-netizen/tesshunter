"""Synthetic paired scoring checks; no experiment predictions are opened."""
import importlib.util
from pathlib import Path
import sys
import pytest

def evaluator():
    folder=Path(__file__).resolve().parents[1]/'protocol';sys.path.insert(0,str(folder))
    def load(name,path):
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module
    common=load('p11_5_eval_test_common',folder/'common.py')
    previous=sys.modules.get('common');sys.modules['common']=common
    try:return load('p11_5_evaluator_test',folder/'evaluate.py')
    finally:
        if previous is None:sys.modules.pop('common',None)
        else:sys.modules['common']=previous

@pytest.mark.parametrize('corrected_C_available',[True,False])
def test_paired_selection_and_no_fallback_to_original_C(tmp_path,monkeypatch,corrected_C_available):
    module=evaluator();root=tmp_path/'p11/p11_5'
    monkeypatch.setattr(module,'REPO',tmp_path);monkeypatch.setattr(module,'ROOT',root)
    path_for=lambda cid,stage:root/f'results/funnel/{"C_v2" if stage=="C" else stage}/{cid}.json'
    monkeypatch.setattr(module,'stage_path',path_for)
    def put(path,value):module.write(root/path,value)
    selection=dict(host_ids=[1,2],series_ids=['tic1','tic2','inj1','inj2'])
    put('manifests/development_selection.json',selection)
    put('manifests/development_prediction_freeze.json',dict(selection_sha256=module.sha(root/'manifests/development_selection.json'),hashes={}))
    put('manifests/development_order.json',dict(order=[dict(tic_id=i,stratum='fixture') for i in (1,2)]))
    model=dict(period=3.,t0=1.,t14_days=.1)
    put('manifests/injections_evaluator.json',[dict(job_id=f'inj{i}',fixed_absolute_model=model,original={'rp_earth':2.}) for i in (1,2)])
    eph=dict(period_days=3.,epoch_btjd=1.,duration_days=.1)
    for i in (1,2):
        put(f'results/reference_snr/tic{i}.json',dict(rows=[dict(job_id=f'inj{i}',snr_expected=10.)]))
        for kind in ('tic','inj'):
            jid=f'{kind}{i}';candidates=[]
            if kind=='inj':candidates=[dict(candidate_id=f'planet{i}',methods=['R0','R1'] if i==1 else ['R1'],passes_pregate=True,ephemeris=eph)]
            put(f'results/predictions/{jid}.json',dict(tic_id=i,predictions=candidates))
            put(f'results/search/{jid}.json',dict(timings={f'{m}_deployable_{cost}':100. for m in ('R0','R1') for cost in ('wall','cpu')}))
    controls=[dict(collection='S_original_40',original_id=f'control{i}',candidate_id=f'control{i}',original_protected_rejection=True) for i in range(26)]
    put('manifests/control_joins.json',dict(rows=controls))
    for cid in ['planet1','planet2']+[r['candidate_id'] for r in controls]:
        control=cid.startswith('control')
        for stage in ('A','S','B'):
            m=dict(gate='FAIL' if control else 'PASS',secondary={'gate_by_mode_p10':{'recurrent_bound':'PASS'}}) if stage=='S' else dict(decision='PASS')
            put(f'results/funnel/{stage}/{cid}.json',dict(status='COMPLETE',measurement=m,wall_seconds=5.,cpu_seconds=5.))
        c=dict(status='COMPLETE',measurement={'primary':eph},wall_seconds=10.,cpu_seconds=10.,
            policy_decisions={f'D{d}_E{e}':{'status':'UNRESOLVED' if control else 'PASS'} for d in (25,36,49,64,81,100) for e in (6,10)})
        put(f'results/funnel/C/{cid}.json',c)
        if corrected_C_available:put(f'results/funnel/C_v2/{cid}.json',c)
    module.evaluate();result=module.read(root/'results/development_evaluation.json')
    assert result['selected_search']=='R1'
    assert result['search_low']['wins']==1 and result['search_low']['losses']==0
    assert result['search_low']['baseline']==1 and result['search_low']['proposed']==2
    if corrected_C_available:
        assert result['finalist']=='R1_S0_D100_E10'
        assert not result['operationally_failed_required_stages']
    else:
        assert result['finalist'] is None
        assert all(p['low']['proposed']==0 for p in result['policies'])
        assert any(r['stage']=='C' for r in result['operationally_failed_required_stages'])


def input_freeze_fixture(tmp_path,monkeypatch):
    m=evaluator();root=tmp_path/'p11/p11_5'
    monkeypatch.setattr(m,'REPO',tmp_path);monkeypatch.setattr(m,'ROOT',root)
    def put(relative,value):m.write(root/relative,value)
    def blob(relative,value=b'immutable fixture bytes'):
        p=tmp_path/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value);return p
    prepared=blob('data/prepared.npz');sidecar=blob('data/prepared.json',b'{"products": []}\n')
    snapshot=blob('data/search_snapshots/masks.npz')
    put('manifests/development_selection.json',dict(host_ids=[1],series_ids=['tic1']))
    put('manifests/development_order.json',dict(order=[]))
    put('manifests/injections_evaluator.json',[])
    put('results/reference_snr/tic1.json',dict(rows=[]))
    put('results/regression_fixture/receipt.json',dict(exit_code=0,source_hashes_verified_at_end=True))
    put('results/regression_fixture/source_freeze.json',dict(hashes={}))
    blob('p11/p11_5/results/regression_fixture/pytest.log',b'synthetic regression receipt\n')
    for name in ('evaluate.py','score_common.py','final_c.py'):
        blob('p11/p11_5/protocol/'+name,b'# synthetic source identity\n')
    put('results/prepared_provenance_review.json',dict(all_physical_truth_checks_pass=True,
        rows=[dict(sidecar_path='data/prepared.json',sidecar_sha256=m.sha(sidecar))]))
    put('manifests/c_v2_execution_freeze.json',dict(source_hashes={}))
    put('manifests/control_joins.json',dict(rows=[]))
    put('manifests/runtime_search/tic1.json',dict(prepared_path='data/prepared.npz',
        prepared_sha256=m.sha(prepared),array_key='fixture-array-key'))
    put('results/pools/tic1.json',[])
    pools=root/'results/pools/tic1.json'
    put('results/search/tic1.json',dict(input_sha256=m.sha(prepared),input_key='fixture-array-key',
        pools_path=pools.relative_to(tmp_path).as_posix(),pools_sha256=m.sha(pools),
        snapshots={'data/search_snapshots/masks.npz':m.sha(snapshot)}))
    search=root/'results/search/tic1.json'
    put('results/predictions/tic1.json',dict(search_result_sha256=m.sha(search),
        input_key='fixture-array-key',predictions=[]))
    return m,root,dict(prepared=prepared,sidecar=sidecar,snapshot=snapshot,pools=pools,
        prediction=root/'results/predictions/tic1.json')


def test_prediction_freeze_binds_runtime_arrays_provenance_and_complete_pools(tmp_path,monkeypatch):
    m,root,files=input_freeze_fixture(tmp_path,monkeypatch)
    m.freeze(root/'manifests/development_selection.json','regression_fixture')
    seal=m.read(root/'manifests/development_prediction_freeze.json')
    for path in files.values():
        assert seal['hashes'][path.relative_to(tmp_path).as_posix()]==m.sha(path)
    assert 'p11/p11_5/manifests/runtime_search/tic1.json' in seal['hashes']


@pytest.mark.parametrize('changed',['prepared','sidecar','snapshot','pools','prediction'])
def test_prediction_freeze_refuses_changed_inputs_or_prediction_link(tmp_path,monkeypatch,changed):
    m,root,files=input_freeze_fixture(tmp_path,monkeypatch)
    path=files[changed]
    if changed=='prediction':
        value=m.read(path);value['search_result_sha256']='wrong-result'
        m.write(path,value,replace=True)
    else:
        with path.open('ab') as f:f.write(b'changed')
    with pytest.raises(ValueError,match='changed|differs'):
        m.freeze(root/'manifests/development_selection.json','regression_fixture')
    assert not (root/'manifests/development_prediction_freeze.json').exists()
