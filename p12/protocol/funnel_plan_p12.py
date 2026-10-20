"""P10-keyed collection and unchanged pre-gate for the timing-only pilot."""
from p12_common import REPO,ROOT,DATA,read,write,sha,utc,append_jsonl
from part0_plan_p12 import source_snapshot
from funnel_worker_p12 import legacy
from lock_predictions_p12 import _closed_phase,inspect
from blind_io_p12 import install,summary
import argparse,contextlib,csv,json,shutil
from pathlib import Path

def source_hashes():
    result=source_snapshot()
    for name in ('scripts/revet_p6.py','scripts/audit_p5.py','p10/protocol/p10_funnel_calibration.py'):
        result[name]=sha(REPO/name)
    return result

def collect(phase):
    if phase!='pilot':raise RuntimeError('Later-part collection requires its own registration')
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Owner remains')
    guard=install(ROOT/'logs/pilot_collect_io.jsonl')
    folder=ROOT/'results/controllers/pilot_search'
    closure,launch=_closed_phase(folder)
    if closure.get('recovery'):raise RuntimeError('Pilot search incomplete')
    audited=[];unknown=0
    collected_inputs=DATA/'funnel/pilot/complete_search_inputs'
    (collected_inputs/'results').mkdir(parents=True,exist_ok=False)
    for job in launch['frozen_jobs']:
        attempt=read(folder/'attempts'/f'{job["job_id"]}.json')
        if attempt['status']!='COMPLETE':
            unknown+=1
            log=ROOT/f'results/search_io/{Path(job["arguments"][1]).stem}.jsonl'
            if log.exists():
                audit=inspect(log)
                if audit['forbidden'] or audit['malformed_rows']:raise RuntimeError('Pilot blind I/O failed')
            continue
        receipt_path=REPO/attempt['result_path']
        if sha(receipt_path)!=attempt['result_sha256']:raise RuntimeError('Pilot receipt changed')
        receipt=read(receipt_path)
        if receipt['preset']!='survey_p10' or receipt['status']!='COMPLETE':raise RuntimeError('Wrong pilot preset/status')
        if sha(REPO/receipt['result_path'])!=receipt['result_sha256']:raise RuntimeError('Pilot result changed')
        audit=inspect(REPO/receipt['file_access_log'])
        if audit['forbidden'] or audit['malformed_rows']:raise RuntimeError('Pilot blind I/O failed')
        target=collected_inputs/'results'/f'{job["job_id"]}.json'
        shutil.copyfile(REPO/receipt['result_path'],target)
        if sha(target)!=receipt['result_sha256']:raise RuntimeError('Pilot collection input copy changed')
        audited.append(dict(job_id=job['job_id'],result_sha256=receipt['result_sha256'],io_sha256=audit['sha256']))
    write(ROOT/'manifests/pilot_predictions_integrity.json',dict(utc=utc(),jobs=audited,closure_sha256=sha(folder/'closure.json'),result_use='timing only'))
    collection=DATA/'funnel/pilot/collection';F=legacy(collection)
    with (ROOT/'logs/pilot_collect.log').open('x',encoding='utf-8') as stream,contextlib.redirect_stdout(stream):
        counts=F.collect(collected_inputs,ROOT/'manifests/pilot_targets.csv')
    with (collection/'candidates.csv').open(newline='') as stream:candidates=list(csv.DictReader(stream))
    with (collection/'survivors.csv').open(newline='') as stream:survivors=list(csv.DictReader(stream))
    with (ROOT/'manifests/pilot_targets.csv').open(newline='') as stream:targets={int(row['tic_id']):row for row in csv.DictReader(stream)}
    sources=source_hashes();jobs=[]
    for candidate in survivors:
        tic=int(candidate['tic_id']);cid=f'tic{tic}_p{int(candidate["planet_num"]):02d}'
        star={key:float(targets[tic][key]) for key in ('radius_rsun','mass_msun','teff_k','tmag','ra_deg','dec_deg')}
        identity=ROOT/f'manifests/input_identity/tic{tic}.json'
        runtime=dict(candidate_id=cid,tic_id=tic,candidate=candidate,
            all_candidates=[row for row in candidates if int(row['tic_id'])==tic],star=star,
            source_hashes=dict(sources,**{identity.relative_to(REPO).as_posix():sha(identity)}),
            neighbours_reference=None,phase='pilot',arm='archival')
        path=ROOT/f'manifests/pilot_A_runtime/{cid}.json';write(path,runtime)
        jobs.append(dict(job_id=cid,attempt=1,arguments=['p12/protocol/funnel_worker_p12.py','A',path.relative_to(REPO).as_posix(),sha(path)],
            result_path=f'p12/results/funnel/pilot/A/{cid}.json',source_hashes=dict(runtime['source_hashes'],**{path.relative_to(REPO).as_posix():sha(path)})))
        append_jsonl(ROOT/'manifests/exposure_ledger.jsonl',dict(utc=utc(),star=tic,stage='pilot_A',reader='timing only',
            path=path.relative_to(REPO).as_posix(),per_candidate_output_to_lead=False,scientific_reuse=False))
    write(ROOT/'manifests/pilot_A_jobs.json',jobs)
    result=dict(utc=utc(),n_accepted=counts['n_accepted_candidates'],n_pre_gate=len(survivors),jobs=len(jobs),workers=24,
        search_unknowns=unknown,source_sha256=sha(__file__),io=summary(guard),result_use='timing and counts only')
    write(ROOT/'manifests/pilot_A_plan.json',result)
    print(json.dumps({key:result[key] for key in ('n_accepted','n_pre_gate','jobs','workers')}))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['collect']);parser.add_argument('--phase',required=True)
    args=parser.parse_args();collect(args.phase)
