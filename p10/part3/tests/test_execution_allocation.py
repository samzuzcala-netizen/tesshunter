import shutil
import pytest
from common import REPO,ROOT,read,write,sha
from registration_execution_v3 import verify


@pytest.mark.parametrize('changed',[
    'p10/part3/manifests/allocation.json','p10/part3/manifests/supervision_policy_v3.json',
    'p10/part3/PREREGISTRATION_P10_3_E20260915.md','p10/part3/manifests/registration_amendments_D1_D4.json'])
def test_user_allocation_chain_detects_tampering(tmp_path,changed):
    old=read(ROOT/'manifests/registration_amendments_D1_D4.json');new=read(ROOT/'manifests/registration_execution_v3.json')
    files=set(read(ROOT/'manifests/registration_seal.json')['hashes'])|set(old['prelaunch_amendment_hashes'])|set(new['hashes'])
    files.update([old['original_preregistration_snapshot'],old['amendment_document'],'p10/part3/manifests/registration_seal.json','p10/part3/manifests/registration_amendments_D1_D4.json','p10/part3/manifests/registration_execution_v3.json'])
    for name in files:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(REPO/name,p)
    assert verify(tmp_path,tmp_path/'p10/part3')['allocation_sha256']
    p=tmp_path/changed;p.write_bytes(p.read_bytes()+b' ')
    with pytest.raises(RuntimeError):verify(tmp_path,tmp_path/'p10/part3')


def test_frozen_full_membership_reuses_exact_pilot_without_rerun():
    a=read(ROOT/'manifests/allocation.json');pilot=set(a['reused_pilot_tic_ids'])
    assert a['selection_frozen'] and a['evaluation_level']=='all_eligible'
    assert len(set(a['selected_tic_ids']))==436 and a['selected_tic_ids']==a['paired_survey_p8_tic_ids']
    expected=set(a['selected_tic_ids'])-pilot
    for preset in a['preset_sequence']:
        jobs=read(ROOT/f'manifests/search_{preset}_jobs.json')
        assert len(jobs)==430
        ids=set()
        for j in jobs:
            path=REPO/j['arguments'][1];assert sha(path)==j['arguments'][2]
            r=read(path);ids.add(r['tic_id'])
            assert set(r)=={'job_id','tic_id','preset','star','prepared_path','prepared_sha256','provenance_sha256','ingest_key','source_hashes'}
        assert ids==expected and not ids&pilot

def test_execution_launch_seal_rejects_mutated_frozen_input(tmp_path):
    from registration_execution_v3 import verify_launch_inputs
    root=tmp_path/'p10/part3';chain=root/'manifests/registration_execution_v3.json'
    write(chain,dict(registered=True))
    p=root/'manifests/sample_runtime.json';write(p,dict(tic_id=42))
    write(root/'manifests/execution_launch_seal.json',dict(registration_sha256=sha(chain),hashes={p.relative_to(tmp_path).as_posix():sha(p)}))
    assert verify_launch_inputs(tmp_path,root)
    p.write_bytes(p.read_bytes()+b' ')
    with pytest.raises(RuntimeError):verify_launch_inputs(tmp_path,root)
