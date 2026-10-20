import json
import pytest
import input_identity_p12 as I
import policy_products_p12 as P
import verify_prepare_p12 as V
import build_input_jobs_p12 as B
from p12_common import read,write,sha,host_hash
from B_fixtures import REAL_REPO,roots,product,index,link_file


def test_identity_time_flux_quality_and_v02(monkeypatch,tmp_path):
    import numpy as np
    repo,root,_=roots(monkeypatch,tmp_path,I)
    meta,source=product(repo,1,74,version='02')
    with np.load(repo/f'data/survey/audit_lc/tic1/{meta["file"]}') as z:raw={k:z[k] for k in z.files}
    src=I.read_source(source);checks=I.compare(raw,meta,src)
    assert checks['all_required_exact']
    assert I.timing_status(meta,src[0],checks,read(root/'protocol/config.json'))=='CORRECTED_V02_SOURCE_VERIFIED'
    raw['quality'][0]=1
    assert not I.compare(raw,meta,src)['all_required_exact']


def test_missing_store_is_input_ineligible(monkeypatch,tmp_path):
    _,root,_=roots(monkeypatch,tmp_path,I,P,V)
    write(root/'manifests/input_jobs/tic1.json',dict(tic_id=1,index_sha256=None))
    assert V.main(1)['status']=='INPUT_INELIGIBLE'


def test_input_job_inventory_includes_both_c_and_redirected_d_cache(monkeypatch,tmp_path):
    import shutil
    repo,root,data=roots(monkeypatch,tmp_path,B)
    metadata,source=product(repo,1,56);index(repo,1,[metadata])
    redirected=data/'lightkurve/acquisition/tic1/attempt1/mastDownload/fixture'/source.name
    redirected.parent.mkdir(parents=True);shutil.copyfile(source,redirected)
    notice=repo/'notice.html';notice.write_text('fixture timing policy')
    policy=repo/'sector_policy.json';write(policy,dict(notice_snapshot=dict(path='notice.html',sha256=sha(notice))))
    configuration=read(root/'protocol/config.json')
    configuration.update(sector_policy_path='sector_policy.json',sector_policy_sha256=sha(policy))
    write(root/'protocol/config.json',configuration,replace=True)
    (root/'protocol/verify_prepare_p12.py').write_text('fixture worker')
    (repo/'src/tesshunter').mkdir(parents=True);(repo/'src/tesshunter/dependency.py').write_text('fixture dependency')
    jobs=B.build([2,1,1])
    first=read(root/'manifests/input_jobs/tic1.json')
    assert first['source_paths']==sorted([source.relative_to(repo).as_posix(),redirected.relative_to(repo).as_posix()])
    assert set(first['source_hashes'])==set(first['source_paths'])
    assert [j['job_id'] for j in jobs]==['tic1','tic2']
    assert 'p12/protocol/config.json' in jobs[0]['source_hashes']
    assert 'src/tesshunter/dependency.py' in jobs[0]['source_hashes']
    assert read(root/'manifests/input_jobs/tic2.json')['index_sha256'] is None


def test_five_sealed_436_status_and_prepared_sha256(tmp_path):
    import subprocess,sys
    result=subprocess.run([sys.executable,str(REAL_REPO/'p12/tests/B_sealed_replay.py'),'input',str(tmp_path)],
        cwd=REAL_REPO,capture_output=True,text=True,timeout=180)
    assert result.returncode==0,result.stderr
    assert '"passed": 5' in result.stdout
