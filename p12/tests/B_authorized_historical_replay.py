"""Lead-only sealed calibration evaluator; explicit E3 scope, no blind search."""
from pathlib import Path
import ast
import csv
import hashlib
import itertools
import json
import math
import os
import sys

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'p12/protocol'))
from p12_common import ROOT,read,write,sha,utc,append_jsonl,environment
environment()
from blind_io_p12 import install
import score_injections_p12 as scoring
from analyze_completeness import classify
from tesshunter import survey


def run(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    auth_path=ROOT/'manifests/historical_replay_authorization.json'
    auth=read(auth_path)
    assert auth['status']=='AUTHORIZED_REPAIR_AND_RESUMPTION'
    assert sha(ROOT/'protocol/blind_io_p12.py')==auth['guard_source_sha256']
    jobs={r['job_id']:int(r['tic_id']) for r in auth['jobs']}
    assert len(jobs)==20
    seal_path=REPO/'p10/results/part2d_calibration_20260912/full_calibration_closed_seal_20260912.json'
    seal=read(seal_path)
    assert seal['status']=='full_calibration_closed_verified'
    sealed={r['path']:r['sha256'] for r in seal['files']}
    search_seal_path=REPO/'p10/results/part2d_20260911/injection_search_closed_seal_20260912.json'
    search_seal=read(search_seal_path)
    assert search_seal['status']=='closed_search_verified'
    for row in search_seal['files']:
        assert row['path'] not in sealed or sealed[row['path']]==row['sha256']
        sealed[row['path']]=row['sha256']
    guard=install(destination/'guard.jsonl')
    search=REPO/'data/survey/p10/part2d/injection_search/results'
    funnel=REPO/'data/survey/p10/part2d/calibration/inj_funnel'
    allowed_search={os.path.normcase(os.path.realpath(search/(job+'.json'))) for job in jobs}
    allowed_funnel=[os.path.normcase(os.path.realpath(funnel/job))+os.sep for job in jobs]
    search_prefix=os.path.normcase(os.path.realpath(search))+os.sep
    funnel_prefix=os.path.normcase(os.path.realpath(funnel))+os.sep
    p9_prefix=os.path.normcase(os.path.realpath(REPO/'p9'))+os.sep
    def narrow_guard(event,args):
        if event!='open' or not args or isinstance(args[0],int):return
        path=os.path.normcase(os.path.realpath(os.fsdecode(args[0])))
        if path.startswith(p9_prefix):raise PermissionError('P9 is outside the E3 evaluator scope')
        if path.startswith(search_prefix) and path not in allowed_search:
            raise PermissionError('Unselected historical injection')
        if path.startswith(funnel_prefix) and not any(path.startswith(prefix) for prefix in allowed_funnel):
            raise PermissionError('Unselected historical funnel')
    sys.addaudithook(narrow_guard)
    seen={}
    def observed(path,tic,stage,*,truth=False,require_seal=False):
        path=Path(path);relative=path.relative_to(REPO).as_posix()
        expected=sealed.get(relative)
        if require_seal:assert expected is not None,'Historical input absent from closed seal'
        append_jsonl(ROOT/'manifests/exposure_ledger.jsonl',dict(utc=utc(),star=tic,stage=stage,path=relative,
            reader='lead E3 historical replay evaluator',prompt_of_origin='P10 2d',
            authorization='p12/manifests/historical_replay_authorization.json',
            calibration_truth=truth,p9_truth=False,sidecar=False,ttt_table=False,
            expected_sealed_sha256=expected))
        digest=sha(path)
        if expected:assert digest==expected,'Historical input hash mismatch'
        seen[relative]=digest
        return path
    baseline=observed(REPO/auth['baseline_table'],None,'selected twenty outcome rows',require_seal=True)
    assert sha(baseline)==auth['baseline_sha256']
    with baseline.open(newline='',encoding='utf-8-sig') as stream:
        rows=list(itertools.islice(csv.DictReader(stream),20))
    assert [r['job_id'] for r in rows]==list(jobs)
    prepared={};checks=[];failures=[]
    scalar_names=None
    for expected in rows:
        job=expected['job_id'];tic=jobs[job]
        path=observed(search/(job+'.json'),tic,'historical locked prediction and embedded calibration truth',truth=True,require_seal=True)
        record=read(path)
        assert record['job_id']==job and int(record['tic_id'])==tic
        original=classify(record)
        fun={}
        if original['status']=='recovered':
            key=f'tic{tic}_P{original["matched_period"]:.4f}.json'
            a=read(observed(funnel/job/'stageA'/key,tic,'sealed injection Stage A',require_seal=True))
            s=read(observed(funnel/job/'secondary'/key,tic,'sealed injection secondary',require_seal=True))
            chosen=(a.get('per_ephemeris') or {}).get(a.get('chosen_ephemeris')) or {}
            det=chosen.get('det_kept') or {}
            fun=dict(stageA=a.get('decision'),secondary_gate=s.get('gate'),
                kept_snr=chosen.get('kept_snr'),n_kept=chosen.get('n_kept'),
                depth_over_survey=chosen.get('depth_over_survey_depth'),stageA_criteria=a.get('criteria'),
                gate_by_mode=(s.get('secondary') or {}).get('gate_by_mode'),
                p_const_white=det.get('p_const_white'),p_const_inflated=det.get('p_const_inflated'))
        if tic not in prepared:
            cached=survey.stitched_path(tic,survey.get_config('survey_p10'),None)
            observed(cached,tic,'uninjected historical native prepared array')
            observed(cached.with_suffix('.json'),tic,'uninjected preparation provenance')
            lc,prov=survey.load_stitched(cached)
            prepared[tic]=dict(time=lc.time.value,flux=lc.flux.value,rotation_proxy=prov.get('rotation_proxy'))
        injection={k:expected[k] for k in ('period','period_bin','rp_earth','rp_rs','b','tmag')}
        injection.update(record['injection'])
        row=dict(job_id=job,tic_id=tic,injection=injection,injection_model=record['injection_model'],funnel=fun)
        predictions=dict(status=record['status'],result=record.get('result'),wall_s=record.get('wall_s'))
        actual=scoring.score_row(row,predictions,prepared[tic])
        mismatch=[]
        for key,value in expected.items():
            got=actual[key]
            if isinstance(got,bool):equal=value==str(got)
            elif got is None:equal=value in ('','None','nan')
            elif isinstance(got,(int,float)):
                number=float(value) if value else float('nan')
                equal=(math.isnan(float(got)) and math.isnan(number)) or float(got)==number
            else:equal=str(got)==value
            if not equal:mismatch.append(key)
        if mismatch:failures.append(dict(job_id=job,fields=mismatch))
        checks.append(dict(job_id=job,tic_id=tic,fields_checked=len(expected),mismatch_fields=mismatch,
            historical_prediction_sha256=seen[path.relative_to(REPO).as_posix()],
            exact_scalar_equality=not mismatch))
    assert all(sha(REPO/path)==digest for path,digest in seen.items()),'Historical input changed during replay'
    result=dict(utc=utc(),status='PASS' if not failures else 'FAIL',required=auth['selection'],
        rows_checked=len(checks),passed=sum(not c['mismatch_fields'] for c in checks),failures=failures,
        comparisons=checks,historical_inputs=seen,authorization_sha256=sha(auth_path),
        historical_seal_sha256=sha(seal_path),historical_search_seal_sha256=sha(search_seal_path),
        scorer_sha256=sha(ROOT/'protocol/score_injections_p12.py'),
        evaluator_sha256=sha(__file__),truth_opened=True,truth_scope='Only user-authorized twenty historical P10 2d injection records',
        full_historical_replay_completed=len(checks)==20 and not failures,
        historical_files_changed=False,blind_worker_access_changed=False,expectation_changed=False,
        equality='Exact scalar equality after CSV type conversion; no numeric tolerance',
        safe_table=auth['baseline_table'],safe_table_sha256=auth['baseline_sha256'])
    write(destination/'replay.json',result)
    write(ROOT/'tests/B_required_historical_replay.json',result,replace=True)
    print(json.dumps({k:result[k] for k in ('status','rows_checked','passed','failures','full_historical_replay_completed')}))
    assert not failures,'Historical scalar replay differs'
    return result


if __name__=='__main__':run(Path(sys.argv[1]))
