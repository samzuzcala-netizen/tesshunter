"""Fixed 24-host timing pilot; never exports per-candidate science to the lead."""
from p12_common import REPO,ROOT,DATA,read,write,sha,utc,append_jsonl
from part0_plan_p12 import source_snapshot
import csv,hashlib,json

def selected_hosts(rows,eligible):
    selected=[]
    for low,high in ((12.5,13.),(13.,13.5),(13.5,14.)):
        band=[row for row in rows if int(row['tic_id']) in eligible and low<=float(row['tmag'])<high]
        band.sort(key=lambda row:hashlib.sha256(f'20260920:p12:timing:{int(row["tic_id"])}'.encode()).hexdigest())
        if len(band)<8:raise RuntimeError('Fewer than eight eligible pilot hosts in a magnitude band')
        selected.extend(band[:8])
    return selected

def prepare_search():
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Owner remains')
    parity=read(ROOT/'tests/pilot_stageA_replay.json')
    if parity['status']!='PASS' or not parity['byte_identical']:raise RuntimeError('Required Stage A replay has not passed')
    for name,digest in parity['p12_sources'].items():
        if sha(REPO/name)!=digest:raise RuntimeError('Pilot implementation differs from tested source')
    eligibility=read(ROOT/'manifests/eligibility_p12.json')
    if not eligibility['complete'] or eligibility['n_unknown']:raise RuntimeError('Eligibility incomplete')
    eligible={int(tic) for tic,row in eligibility['per_star'].items() if row['status']=='INPUT_ELIGIBLE' and row['source_set']=='p8_2000'}
    with (REPO/'data/survey/targets_p8.csv').open(newline='',encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream))
    selected=selected_hosts(rows,eligible);snapshot=source_snapshot();jobs=[]
    selected_path=ROOT/'manifests/pilot_targets.csv'
    with selected_path.open('x',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(selected[0]));writer.writeheader();writer.writerows(selected)
    for star in selected:
        tic=int(star['tic_id']);prepared=read(ROOT/f'results/native_noise/archival/tic{tic}.json');jid=f'tic{tic}'
        if prepared['status']!='INPUT_ELIGIBLE':raise RuntimeError('Pilot input no longer eligible')
        search_star={key:float(star[key]) for key in ('radius_rsun','mass_msun','teff_k','tmag','ra_deg','dec_deg')}
        runtime=dict(tic_id=tic,preset='survey_p10',job_id=jid,star=search_star,
            prepared_path=prepared['prepared_path'],prepared_sha256=prepared['prepared_sha256'],
            provenance_sha256=prepared['provenance_sha256'],ingest_key=prepared['ingest_key'],source_hashes=snapshot,
            run='data/survey/p12/pilot/runs/survey_p10')
        path=ROOT/f'manifests/pilot_search_runtime/{jid}.json';write(path,runtime)
        jobs.append(dict(job_id=jid,attempt=1,arguments=['p12/protocol/blind_search_worker_p12.py',path.relative_to(REPO).as_posix(),sha(path)],
            result_path=f'p12/results/search_receipts/pilot/runs/survey_p10/{jid}.json',
            source_hashes=dict(snapshot,**{path.relative_to(REPO).as_posix():sha(path)})))
        append_jsonl(ROOT/'manifests/exposure_ledger.jsonl',dict(utc=utc(),star=tic,stage='pilot_search',reader='timing only',
            path=runtime['run'],per_candidate_output_to_lead=False,scientific_reuse=False))
    write(ROOT/'manifests/pilot_search_jobs.json',jobs)
    write(ROOT/'manifests/pilot_selection.json',dict(utc=utc(),n_hosts=24,per_band=8,seed_text='20260920:p12:timing:<integer TIC>',
        selected_targets_sha256=sha(selected_path),workers=24,deadline_s=3600,result_use='timing and counts only'))
    # Complete 0h reporting before the human population choice; no new science phase.
    sequence=read(ROOT/'manifests/phase_sequence.json');phases=sequence['phases']
    index=next(i for i,p in enumerate(phases) if p['name']=='forecast')
    phases.insert(index,dict(name='pilot_timing',part=0,kind='evaluator',depends_on=['pilot_A'],script='p12/protocol/part0_handoff_p12.py',args=['timing']))
    phases[index+1]['depends_on']=['pilot_timing']
    index=next(i for i,p in enumerate(phases) if p['name']=='commit_part_0')
    phases.insert(index,dict(name='decision_point_1_report',part=0,kind='evaluator',depends_on=['forecast'],script='p12/protocol/part0_handoff_p12.py',args=['report']))
    phases[index+1]['depends_on']=['decision_point_1_report']
    write(ROOT/'manifests/phase_sequence.json',sequence,replace=True)
    return jobs
