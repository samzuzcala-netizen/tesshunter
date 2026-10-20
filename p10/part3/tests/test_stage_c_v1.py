import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'protocol'))
from stage_c_plan_v1 import select_candidates
from stage_c_worker_v1 import validate_upstream
from part_f_guards_v1 import IntegrityFailure

def rec(decision='PASS',status='COMPLETE'):
    return dict(tic_id=1,status=status,measurement={'decision':decision})

def row(cid,snr,**changes):
    r=dict(row_id=cid+str(snr),family_id='f1',tic_id=1,independence='INDEPENDENT',in_band=True,
        likely_periodic=True,expected_snr=snr,presets={'survey_p10':{'associations':[
        {'candidate_id':cid,'recovered':True,'alias':'1:1'}]}})
    r.update(changes);return r

def test_c_selection_orders_unique_candidates_and_keeps_matched_witnesses():
    rows=[row('c2',20),row('c1',20),row('c3',40),row('c3',10)]
    r=select_candidates(rows,{cid:rec() for cid in ('c1','c2','c3','unmatched')},2)
    assert [x['candidate_id'] for x in r['selected']]==['c3','c1']
    assert len(r['selected'][0]['qualifying_rows'])==2
    assert {x['reason'] for x in r['excluded']}=={'UNMATCHED_B_SURVIVOR','C_CAP_NOT_RUN'}

def test_c_requires_likely_in_domain_match_b_pass_and_finite_rank():
    rows=[row('outside',90,in_band=False),row('weak',80,likely_periodic=False),row('bad',None),
        row('hold',70),row('unknown',60),row('good',1)]
    receipts={c:rec() for c in ('outside','weak','bad','good')}
    receipts.update(hold=rec('HOLD'),unknown=rec('PASS','OPERATIONAL_UNKNOWN'))
    r=select_candidates(rows,receipts,13)
    assert [x['candidate_id'] for x in r['selected']]==['good']
    assert r['n_B_pass']==4
    assert {x['reason'] for x in r['excluded']}=={'NO_LIKELY_PERIODIC_IN_DOMAIN_MATCH','EXPECTED_SNR_UNMEASURED'}

@pytest.mark.parametrize('cap',[0,-2])
def test_c_negative_cap_never_launches(cap):
    r=select_candidates([row('c1',4)],{'c1':rec()},cap)
    assert r['cap']==cap and not r['selected'] and r['excluded'][0]['reason']=='C_CAP_NOT_RUN'

def test_c_alias_match_counts_but_failed_epoch_does_not():
    good=row('alias',8);good['presets']['survey_p10']['associations'][0]['alias']='2:1'
    bad=row('epoch',30);bad['presets']['survey_p10']['associations'][0]['recovered']=False
    r=select_candidates([good,bad],{'alias':rec(),'epoch':rec()},13)
    assert [x['candidate_id'] for x in r['selected']]==['alias']

def test_upstream_requires_actual_A_B_pass_and_carries_S_hold():
    validate_upstream({'A':rec(),'S':rec('HOLD'),'B':rec()})
    for stage in ('A','S','B'):
        rows={'A':rec(),'S':rec(),'B':rec()};rows[stage]=rec('FAIL')
        with pytest.raises(IntegrityFailure):validate_upstream(rows)
    with pytest.raises(IntegrityFailure):validate_upstream({'A':rec(),'S':rec(),'B':rec('PASS','OPERATIONAL_UNKNOWN')})

def test_real_C_adapter_setup_in_fresh_process(tmp_path):
    import subprocess,json
    module=Path(__file__).resolve().parents[1]/'protocol'
    script='''
import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import stage_c_worker_v1 as W
root=Path(sys.argv[2]);W.REPO=root;W.DATA=root/'data/survey/p10/part3'
cid='tic42_p01'
candidate=dict(tic_id=42,rank=1,planet_num=1,period_days=2,epoch_btjd=.5,duration_days=.05,
 depth_ppt=1,stitch_snr=10,stitch_n_transits=5,n_units=3)
star=dict(radius_rsun=.3,mass_msun=.3,teff_k=3300,tmag=13,ra_deg=12,dec_deg=30)
base=dict(candidate_id=cid,tic_id=42,candidate=candidate,star=star,all_candidates=[candidate],raw_products=[])
runtime=dict(candidate_id=cid,tic_id=42,output_root=f'data/survey/p10/part3/funnel/C_cases_v1/{cid}')
F,job,out=W.setup_case(runtime,base)
import audit_p5 as A
assert A.OUT==out and F.V.OUT_ROOT==out and job['tic_id']==42 and job['period']==2
assert F.V.RULE_SET.stagec_peak_rule=='strongest' and F.V.RULE_SET.stagec_sde_robust_fallback
assert F.V.RULE_SET.duration_floor_cadence and F.V.RULE_SET.version=='p10.0'
assert A.load_products(42)==[] and A.stellar_from_cache(42)['radius']==.3
assert not list(out.rglob('*.json')) and not list(out.rglob('*.npz'))
try:W.setup_case(runtime,base)
except FileExistsError:pass
else:raise AssertionError('Repeated C setup was allowed')
print(json.dumps(dict(status='PASS',root=str(out),scientific_calls=0)))
'''
    result=subprocess.run([sys.executable,'-c',script,str(module),str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert json.loads(result.stdout.strip())['scientific_calls']==0

def test_C_rejects_a_prior_case_output_root(tmp_path,monkeypatch):
    import stage_c_worker_v1 as W
    monkeypatch.setattr(W,'REPO',tmp_path);monkeypatch.setattr(W,'DATA',tmp_path/'data/survey/p10/part3')
    runtime=dict(candidate_id='c1',tic_id=1,output_root='data/survey/p10/part3/funnel/cases/c1')
    with pytest.raises(IntegrityFailure):W.setup_case(runtime,dict(candidate_id='c1',tic_id=1))
    assert not (tmp_path/'data').exists()
