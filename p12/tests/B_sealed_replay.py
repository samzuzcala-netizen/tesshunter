"""Guarded subprocess for lane B's explicitly allowed sealed engineering reads."""
from pathlib import Path
import sys
REAL_REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REAL_REPO/'p12/protocol'))
from p12_common import environment,read,write,sha,utc,append_jsonl,host_hash
environment()
from blind_io_p12 import install
import csv
import contextlib
import io
import json
import itertools


def observed(path,tic,purpose,reader):
    append_jsonl(REAL_REPO/'p12/tests/B_exposure_ledger.jsonl',dict(utc=utc(),star=tic,stage=purpose,
        path=Path(path).relative_to(REAL_REPO).as_posix(),reader=reader,prompt_of_origin='P10.3' if '/p10/part3/' in Path(path).as_posix() else 'P11' if '/p11/' in Path(path).as_posix() else 'P10 2d'))


def link_host(repo,tic,job):
    from B_fixtures import link_file
    raw=REAL_REPO/f'data/survey/audit_lc/tic{tic}'
    observed(raw/'index.json',tic,'raw acquisition index','B_sealed_replay.link_host')
    link_file(raw/'index.json',repo/raw.relative_to(REAL_REPO)/'index.json')
    for metadata in read(raw/'index.json')['products']:
        if 'file' in metadata:
            observed(raw/metadata['file'],tic,'raw array identity/preparation','B_sealed_replay.link_host')
            link_file(raw/metadata['file'],repo/raw.relative_to(REAL_REPO)/metadata['file'])
    for name in job['source_paths']:
        observed(REAL_REPO/name,tic,'FITS source identity','B_sealed_replay.link_host')
        link_file(REAL_REPO/name,repo/name)


def input_replay(tmp):
    import pytest
    import input_identity_p12 as I
    import policy_products_p12 as P
    import verify_prepare_p12 as V
    from B_fixtures import roots
    with pytest.MonkeyPatch.context() as patch:
        repo,root,_=roots(patch,tmp,I,P,V)
        eligible=[];historical=REAL_REPO/'p10/part3'
        for path in (historical/'results/native_noise').glob('tic*.json'):
            observed(path,int(path.stem[3:]),'sealed input eligibility','test_five_sealed_436_status_and_prepared_sha256')
            row=read(path)
            if row['status']=='INPUT_ELIGIBLE':eligible.append(row)
        chosen=sorted(eligible,key=lambda r:host_hash(r['tic_id'],'p12:input-fixture',2026092002))[:5]
        assert len(chosen)==5
        for expected in chosen:
            tic=expected['tic_id'];job_path=historical/f'manifests/input_jobs/tic{tic}.json'
            observed(job_path,tic,'sealed source manifest','test_five_sealed_436_status_and_prepared_sha256')
            job=read(job_path);link_host(repo,tic,job);write(root/f'manifests/input_jobs/tic{tic}.json',job)
            with contextlib.redirect_stdout(io.StringIO()):actual=V.main(tic)
            assert actual['status']==expected['status']
            assert actual['prepared_sha256']==expected['prepared_sha256']
    print(json.dumps(dict(check='five sealed status/prepared hashes',passed=5)))


def injection_replay(tmp):
    import pytest
    import numpy as np
    import input_identity_p12 as I
    import policy_products_p12 as P
    import verify_prepare_p12 as V
    import prepare_injections_p12 as J
    from tesshunter import survey,survey_p8
    from B_fixtures import roots
    with pytest.MonkeyPatch.context() as patch:
        repo,root,_=roots(patch,tmp,I,P,V,J)
        hosts=[]
        for path in (REAL_REPO/'p11/results/input_inventory_v2').glob('tic*.json'):
            observed(path,int(path.stem[3:]),'input policy unchanged-host selection','test_five_unchanged_calibration_hosts_equal_p10')
            inv=read(path)
            if inv['original_selected_sectors']==inv['audited_selected_sectors'] and len(inv['audited_selected_sectors'])>=3:hosts.append(inv)
        chosen=sorted(hosts,key=lambda h:host_hash(h['tic_id'],'p12:input-fixture',2026092002))[:5]
        assert len(chosen)==5
        policy=read(REAL_REPO/'p10/part3/manifests/sector_policy_effective.json')
        for inv in chosen:
            tic=inv['tic_id'];paths=set()
            for r in inv['records']:
                for source in r.get('source_matches',[])+r.get('available_source_versions',[]):paths.add(source['path'])
            idx=REAL_REPO/f'data/survey/audit_lc/tic{tic}/index.json'
            job=dict(tic_id=tic,source_paths=sorted(paths),index_sha256=sha(idx),notice_snapshot_sha256=policy['notice_snapshot']['sha256'])
            link_host(repo,tic,job);write(root/f'manifests/input_jobs/tic{tic}.json',job)
            with contextlib.redirect_stdout(io.StringIO()):V.main(tic)
            cfg=survey.get_config('survey_p10')
            original=survey_p8.load_audit_products(tic,repo/'data/survey/audit_lc',sector_min=cfg.sector_min)
            original,_=survey_p8.harmonise_cadence(original,cfg.target_cadence_minutes)
            selected=P.load_policy_products(tic);selected,_=survey_p8.harmonise_cadence(selected,cfg.target_cadence_minutes)
            assert [(p['sector'],p['author']) for p in original]==[(p['sector'],p['author']) for p in selected]
            row=dict(job_id=f'fixture_tic{tic}',tic_id=tic,period=5.137,t0_frac=.37,rp_rs=.06,b=.3,a_rs=18.,u1=.3,u2=.2)
            actual,_,_,_=J.prepare_arrays(tic,row)
            expected,_,_=survey_p8.get_prepared(tic,cfg,cache_dir=tmp/'cache',lc_root=repo/'data/survey/audit_lc',injection=row)
            for key in ('time','flux','flux_err'):
                np.testing.assert_allclose(getattr(actual,key).value,getattr(expected,key).value,rtol=0,atol=1e-12,equal_nan=True)
            np.testing.assert_array_equal(actual.meta['TESSHUNTER_SECTOR'],expected.meta['TESSHUNTER_SECTOR'])
    print(json.dumps(dict(check='five unchanged-host injected array comparisons',passed=5,tolerance=1e-12)))


def outcomes_replay(tmp):
    from score_injections_p12 import levels
    path=REAL_REPO/'data/survey/p10/part2d/calibration/injection_outcomes_p10.csv'
    with path.open(newline='',encoding='utf-8-sig') as stream:
        rows=list(itertools.islice(csv.DictReader(stream),20))
    assert len(rows)==20
    for row in rows:
        observed(path,int(row['tic_id']),'sealed injection outcome level algebra','test_twenty_sealed_outcome_rows_level_algebra')
        for key,value in levels(row).items():assert value==(row[key]=='True')
    receipt=dict(utc=utc(),status='OPEN',required='twenty sealed 2d rows re-scored identically including period/window matching',
        safe_table=path.relative_to(REAL_REPO).as_posix(),safe_table_sha256=sha(path),rows_checked=20,
        completed='historical recovery labels and funnel-level algebra only',
        missing_fields=['injected absolute epoch','injected duration/model','full accepted prediction ephemerides'],
        reason='Full replay needs embedded calibration truth in sealed search results, protected by section 10b; never opened',
        truth_opened=False,full_historical_replay_completed=False)
    # This narrower algebra check does not overwrite the separately executed full replay receipt.
    write(tmp/'outcome_algebra.json',receipt)
    print(json.dumps(dict(check='twenty sealed outcome level rows',passed=20,full_period_window_replay='OPEN')))


if __name__=='__main__':
    kind=sys.argv[1];tmp=Path(sys.argv[2]);tmp.mkdir(parents=True,exist_ok=True)
    install(tmp/'fixture_guard.jsonl')
    {'input':input_replay,'injection':injection_replay,'outcomes':outcomes_replay}[kind](tmp)
