"""Select the prospectively capped TCE-matched likely-periodic B survivors."""
from common import REPO,ROOT,DATA,read,write,sha,utc,environment
environment()
import json
import math
import time
from collections import Counter
from full_funnel_plan import stage_decision,charge
from part_f_math_v1 import finite
from part_f_guards_v1 import require_hash,assert_no_integrity_failure,IntegrityFailure
from registration_execution_v3 import verify
from lock_predictions import both_locked


def select_candidates(rows, b_receipts, cap):
    matched={}
    for row in rows:
        for association in row['presets']['survey_p10']['associations']:
            if not association['recovered']:continue
            cid=association['candidate_id']
            matched.setdefault(cid,[]).append(dict(row_id=row['row_id'],family_id=row['family_id'],
                tic_id=row['tic_id'],independence=row['independence'],in_band=row['in_band'],
                likely_periodic=row['likely_periodic'],expected_snr=row['expected_snr'],alias=association['alias']))
    eligible,excluded=[],[]
    for cid,receipt in sorted(b_receipts.items()):
        if stage_decision(receipt)!='PASS':continue
        witnesses=matched.get(cid,[])
        qualifying=[r for r in witnesses if r['in_band'] and r['likely_periodic']]
        ranked=[r for r in qualifying if finite(r['expected_snr']) is not None and r['expected_snr']>=0]
        base=dict(candidate_id=cid,tic_id=receipt['tic_id'],matched_rows=witnesses,qualifying_rows=qualifying,
            B_decision='PASS')
        if not qualifying:
            excluded.append(dict(base,reason='UNMATCHED_B_SURVIVOR' if not witnesses else 'NO_LIKELY_PERIODIC_IN_DOMAIN_MATCH'))
        elif not ranked:
            excluded.append(dict(base,reason='EXPECTED_SNR_UNMEASURED'))
        else:
            eligible.append(dict(base,ranking_expected_snr=max(r['expected_snr'] for r in ranked)))
    eligible.sort(key=lambda r:(-r['ranking_expected_snr'],r['candidate_id']))
    limit=max(0,int(cap))
    for rank,row in enumerate(eligible,1):row['rank']=rank
    selected=eligible[:limit]
    excluded.extend(dict(r,reason='C_CAP_NOT_RUN') for r in eligible[limit:])
    return dict(eligible=eligible,selected=selected,excluded=excluded,
        n_B_pass=sum(stage_decision(r)=='PASS' for r in b_receipts.values()),
        cap=int(cap),n_selected=len(selected),n_eligible=len(eligible))


def main():
    assert_no_integrity_failure();verify(require_launch_seal=True);both_locked()
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Controller still active')
    target=ROOT/'manifests/stage_C_selection_v1.json'
    if target.exists():raise RuntimeError('Stage C selection already exists; no overwrite')
    for name in ('early_funnel_closed_evidence_seal.json','forced_fits_closed_evidence_seal.json'):
        for path,digest in read(ROOT/'manifests'/name)['files'].items():require_hash(REPO/path,digest,'Closed science')
    method_path=ROOT/'manifests/stage_C_method_registration_v1.json';method=read(method_path)
    for path,digest in method['source_hashes'].items():require_hash(REPO/path,digest,'Registered C source')
    cap_path=ROOT/'manifests/C_cap_at_B_closure.json';cap=read(cap_path)
    require_hash(ROOT/'manifests/resource_ledger_at_B_closure.json',cap['ledger_sha256'],'B-closure ledger')
    if math.floor((cap['remaining_hours_at_B_closure']-3)*3/3.4)!=cap['N_C']:
        raise IntegrityFailure('Frozen C cap arithmetic differs')
    started,timer=utc(),time.perf_counter()
    try:
        matching=read(ROOT/'results/matching.json')
        b_receipts={p.stem:read(p) for p in (ROOT/'results/funnel/B').glob('*.json')}
        selection=select_candidates(matching['rows'],b_receipts,cap['N_C'])
        selection.update(utc=utc(),status='LOCKED_BEFORE_FIRST_C_LAUNCH',
            cap_sha256=sha(cap_path),matching_sha256=sha(ROOT/'results/matching.json'),
            method_registration_sha256=sha(method_path),presence_used_for_C_selection=False,
            B_status_counts=dict(Counter(stage_decision(r) for r in b_receipts.values())))
        write(target,selection)
        entries={r['candidate_id']:r for r in read(ROOT/'manifests/full_funnel_candidates.json')['entries']}
        jobs=[]
        for selected in selection['selected']:
            cid=selected['candidate_id'];base=entries[cid]
            require_hash(REPO/base['runtime_path'],base['runtime_sha256'],'Frozen candidate runtime')
            upstream={f'p10/part3/results/funnel/{stage}/{cid}.json':sha(ROOT/f'results/funnel/{stage}/{cid}.json') for stage in ('A','S','B')}
            runtime=dict(candidate_id=cid,tic_id=selected['tic_id'],base_runtime_path=base['runtime_path'],
                base_runtime_sha256=base['runtime_sha256'],source_hashes=method['source_hashes'],
                method_registration_sha256=sha(method_path),selection_sha256=sha(target),
                selection_path=target.relative_to(REPO).as_posix(),upstream_hashes=upstream,
                threads=8,oversampling=3,output_root=f'data/survey/p10/part3/funnel/C_cases_v1/{cid}',
                implementation='Unchanged p10.0 strongest-peak plus conditional robust fallback; audit_p5.tls_step')
            if (REPO/runtime['output_root']).exists():raise IntegrityFailure('C output root already exists')
            path=ROOT/f'manifests/stage_C_runtime/{cid}.json';write(path,runtime)
            jobs.append(dict(job_id=cid,arguments=['p10/part3/protocol/stage_c_worker_v1.py',path.relative_to(REPO).as_posix(),sha(path)],
                result_path=f'p10/part3/results/funnel/C/{cid}.json'))
        job_path=ROOT/'manifests/funnel_C_jobs.json';write(job_path,jobs)
        waves=math.ceil(len(jobs)/3)
        plan=dict(utc=utc(),action='LAUNCH_REGISTERED_PHASE',phase='funnel_C',
            controller='p10/part3/protocol/controller_v4.py',jobs=job_path.relative_to(REPO).as_posix(),
            jobs_sha256=sha(job_path),jobs_count=len(jobs),workers=3,threads_per_job=8,deadline_seconds=12240,
            forecast_minutes=waves*3.4*60,forecast_method='Complete three-worker waves at the registered 3.4-hour tail; final partial wave included',
            C_cap=cap['N_C'],waves=waves,selection_sha256=sha(target),
            method_registration_sha256=sha(method_path),hard_budget_enforced=True)
        write(ROOT/'manifests/funnel_C_preflight.json',plan)
        print(json.dumps(dict(phase='STAGE_C_READY',B_pass=selection['n_B_pass'],eligible=selection['n_eligible'],
            selected=selection['n_selected'],cap=cap['N_C'],exclusions=dict(Counter(r['reason'] for r in selection['excluded'])),plan=plan)))
    finally:charge(started,timer,'G_C_selection_and_dispatch')


if __name__=='__main__':main()
