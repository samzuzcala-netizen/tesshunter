"""Mechanical full-population A/S/B dispatch, preserving sealed pilot measurements."""
from common import REPO,ROOT,DATA,read,write,sha,utc,environment
environment()
from registration_execution_v3 import verify
from lock_predictions import both_locked
from funnel_worker import legacy
from input_identity import choose_verified
import csv,time,math,contextlib


def stage_decision(receipt):
    if not receipt or receipt.get('status')!='COMPLETE':return 'OPERATIONAL_UNKNOWN'
    m=receipt.get('measurement') or {};d=m.get('decision',m.get('gate'))
    return d if d in ('PASS','FAIL','HOLD') else 'OPERATIONAL_UNKNOWN'


def stage_allowed(stage,a=None,s=None):
    if stage=='S':return stage_decision(a)=='PASS'
    if stage=='B':return stage_decision(a)=='PASS' and stage_decision(s) in ('PASS','HOLD')
    raise ValueError(stage)


def charge(started,timer,phase):
    ledger=read(ROOT/'manifests/resource_ledger.json');hours=(time.perf_counter()-timer)/3600
    ledger['new_queue_hours']+=hours;ledger['utc']=utc()
    ledger['intervals'].append(dict(phase=phase,start=started,end=ledger['utc'],hours=hours))
    write(ROOT/'manifests/resource_ledger.json',ledger,replace=True)


def source_hashes():
    result={p.relative_to(REPO).as_posix():sha(p) for p in (REPO/'src/tesshunter').glob('*.py')}
    for name in ['scripts/revet_p6.py','scripts/audit_p5.py','p10/protocol/p10_funnel_calibration.py','p10/part3/protocol/funnel_worker.py','p10/part3/protocol/blind_io.py','p10/part3/protocol/common.py','p10/part3/protocol/science_json.py']:
        result[name]=sha(REPO/name)
    return result


def prepare_A():
    verify();locks=both_locked()
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Owner present')
    target=ROOT/'manifests/funnel_A_jobs.json'
    if target.exists():return read(ROOT/'manifests/funnel_A_preflight.json')
    started=utc();timer=time.perf_counter();collection=DATA/'funnel/full_collection'
    F=legacy(collection)
    with (ROOT/'logs/full_collect.log').open('x',encoding='utf-8') as log,contextlib.redirect_stdout(log):
        counts=F.collect(DATA/'runs/survey_p10',ROOT/'manifests/targets_evaluated.csv')
    candidates=list(csv.DictReader((collection/'candidates.csv').open()));survivors=list(csv.DictReader((collection/'survivors.csv').open()))
    locked=read(ROOT/'manifests/predictions_survey_p10.json')
    expected={q['candidate_id'] for h in locked['hosts'] for q in h['accepted']}
    observed={f"tic{int(c['tic_id'])}_p{int(c['planet_num']):02d}" for c in candidates}
    if expected!=observed:raise RuntimeError('INTEGRITY_FAILURE: collected candidates differ from the locked predictions')
    targets={int(r['tic_id']):r for r in csv.DictReader((ROOT/'manifests/targets_evaluated.csv').open())}
    sources=source_hashes();config=read(ROOT/'protocol/config.json');jobs=[];all_entries=[];reused=[]
    pilot_ids={j['job_id'] for j in read(ROOT/'manifests/timing_pilot_A_jobs.json')}
    oldseal=read(ROOT/'manifests/timing_pilot_closed_evidence_seal.json')['files']
    for candidate in survivors:
        tic=int(candidate['tic_id']);cid=f'tic{tic}_p{int(candidate["planet_num"]):02d}'
        path=ROOT/f'manifests/funnel_runtime/{cid}.json'
        if path.exists():
            old=read(path)
            if {k:v for k,v in old['candidate'].items() if k!='rank'}!={k:v for k,v in candidate.items() if k!='rank'}:raise RuntimeError('Pilot candidate identity changed')
            if cid not in pilot_ids:raise RuntimeError('Unexpected previous candidate runtime')
        else:
            identity=read(ROOT/f'results/input_identity/tic{tic}.json');selected=choose_verified(identity['records'],config)
            star={k:float(targets[tic][k]) for k in ('radius_rsun','mass_msun','teff_k','tmag','ra_deg','dec_deg')}
            nb=DATA/f'neighbours/tic{tic}.json'
            if not read(ROOT/f'results/neighbour_receipts/{tic}.json').get('ok'):raise RuntimeError('Missing Part D neighbour receipt')
            runtime=dict(candidate_id=cid,tic_id=tic,candidate=candidate,all_candidates=[c for c in candidates if int(c['tic_id'])==tic],star=star,
                raw_products=[{k:p[k] for k in ('metadata','raw_path','raw_sha256')} for p in selected],source_hashes=sources,
                neighbours_reference=dict(path=nb.relative_to(REPO).as_posix(),sha256=sha(nb)))
            write(path,runtime)
        entry=dict(candidate_id=cid,tic_id=tic,runtime_path=path.relative_to(REPO).as_posix(),runtime_sha256=sha(path));all_entries.append(entry)
        if cid in pilot_ids:
            p=ROOT/f'results/funnel/A/{cid}.json'
            if sha(p)!=oldseal[p.relative_to(REPO).as_posix()]['sha256']:raise RuntimeError('Sealed pilot Stage A changed')
            if read(p)['status']!='COMPLETE':raise RuntimeError('Unusable pilot Stage A reuse')
            reused.append(dict(candidate_id=cid,receipt_sha256=sha(p),pilot_rank_preserved=True))
        else:
            if (ROOT/f'results/funnel/A/{cid}.json').exists():raise RuntimeError('No Stage A retry is authorized')
            jobs.append(dict(job_id=cid,arguments=['p10/part3/protocol/funnel_worker.py','A',entry['runtime_path'],entry['runtime_sha256']],result_path=f'p10/part3/results/funnel/A/{cid}.json'))
    if len(reused)!=17:raise RuntimeError('Pilot Stage A reuse count changed')
    write(ROOT/'manifests/full_funnel_candidates.json',dict(utc=utc(),n_accepted=counts['n_accepted_candidates'],n_pre_gate=len(survivors),entries=all_entries,reused_pilot_A=reused,
        collection_root=collection.relative_to(REPO).as_posix(),collection_hashes={p.name:sha(p) for p in collection.glob('*.csv')},prediction_locks=locks,
        pilot_reuse_note='Scientific measurements, runtime and local pilot rank remain unchanged; global collection rank is reporting metadata only.'))
    write(target,jobs)
    forecast=math.ceil(len(jobs)/24)*517*1.25/60
    plan=dict(utc=utc(),phase='funnel_A',jobs=target.relative_to(REPO).as_posix(),jobs_count=len(jobs),reused=17,workers=24,deadline_seconds=1200,forecast_minutes=forecast,jobs_sha256=sha(target))
    write(ROOT/'manifests/funnel_A_preflight.json',plan);charge(started,timer,'full_collect_and_A_dispatch');return plan


def prepare_stage(stage):
    verify();both_locked()
    if stage not in ('S','B'):raise ValueError(stage)
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Owner present')
    out=ROOT/f'manifests/funnel_{stage}_jobs.json'
    if out.exists():return read(ROOT/f'manifests/funnel_{stage}_preflight.json')
    started=utc();timer=time.perf_counter();jobs=[];statuses={};entries=read(ROOT/'manifests/full_funnel_candidates.json')['entries']
    for e in entries:
        cid=e['candidate_id'];a=ROOT/f'results/funnel/A/{cid}.json';s=ROOT/f'results/funnel/S/{cid}.json'
        ar=read(a) if a.exists() else None;sr=read(s) if s.exists() else None
        d=stage_decision(ar if stage=='S' else sr);statuses[d]=statuses.get(d,0)+1
        if not stage_allowed(stage,ar,sr):continue
        if (ROOT/f'results/funnel/{stage}/{cid}.json').exists():raise RuntimeError('Scientific retry is not authorized')
        if sha(REPO/e['runtime_path'])!=e['runtime_sha256']:raise RuntimeError('Candidate runtime changed')
        jobs.append(dict(job_id=cid,arguments=['p10/part3/protocol/funnel_worker.py',stage,e['runtime_path'],e['runtime_sha256']],result_path=f'p10/part3/results/funnel/{stage}/{cid}.json'))
    write(out,jobs)
    plan=dict(utc=utc(),phase=f'funnel_{stage}',jobs=out.relative_to(REPO).as_posix(),jobs_count=len(jobs),workers=24,deadline_seconds=300,
        forecast_minutes=math.ceil(len(jobs)/24)*300/60,forecast_method='One-attempt deadline waves; no gate outcome used to change rules',jobs_sha256=sha(out),upstream_status_counts=statuses)
    write(ROOT/f'manifests/funnel_{stage}_preflight.json',plan);charge(started,timer,f'funnel_{stage}_dispatch');return plan


def freeze_C_cap():
    verify()
    out=ROOT/'manifests/C_cap_at_B_closure.json'
    if out.exists():return read(out)
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('B owner has not closed')
    closure=read(ROOT/'results/controllers/funnel_B/closure.json')
    if closure['status']!='CLOSED' or not closure['all_owned_workers_closed'] or not closure['source_hashes_unchanged']:raise RuntimeError('B closure integrity failed')
    ledger_path=ROOT/'manifests/resource_ledger.json';ledger=read(ledger_path);remaining=31.98-ledger['new_queue_hours'];raw=math.floor((remaining-3.)*3/3.4)
    result=dict(utc=utc(),B_closed_utc=closure['utc'],ledger_sha256=sha(ledger_path),new_queue_hours_at_B_closure=ledger['new_queue_hours'],remaining_hours_at_B_closure=remaining,
        formula='floor((remaining_hours - 3.0) * 3 / 3.4)',N_C=raw,max_runnable=max(0,raw),reserve_hours=3.,tail_hours=3.4,max_concurrent=3,
        selected_candidates_pending_matching=True,selection_order='Descending expected SNR among TCE-matched likely-periodic B passers; stable candidate ID tie-break',
        authorization_sha256=sha(ROOT/'manifests/supervision_policy_v3.json'),recorded_before_first_C_launch=True)
    write(out,result);return result
