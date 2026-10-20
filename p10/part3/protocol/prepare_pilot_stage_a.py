"""Machine-only blind pilot collection and Stage A dispatch, no TCE access."""
from common import REPO,ROOT,DATA,read,write,sha,utc,environment
environment()
from funnel_worker import legacy
from input_identity import choose_verified
import csv,time


def main():
    started=utc();timer=time.perf_counter()
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Search controller has not closed')
    closure=read(ROOT/'results/controllers/timing_pilot_search/closure.json')
    if not closure['all_owned_workers_closed'] or not closure['source_hashes_unchanged']:raise RuntimeError('Pilot closure integrity failed')
    from verify_search_io import pilot
    pilot()
    root=DATA/'funnel'
    F=legacy(root)
    # Every P10 accepted candidate is collected; only fixed pre-gate outcomes dispatch A.
    result=F.collect(DATA/'runs/survey_p10',ROOT/'manifests/targets_eligible.csv')
    candidates=list(csv.DictReader((root/'candidates.csv').open()))
    survivors=list(csv.DictReader((root/'survivors.csv').open()))
    targets={int(r['tic_id']):r for r in csv.DictReader((ROOT/'manifests/targets_eligible.csv').open())}
    sources={p.relative_to(REPO).as_posix():sha(p) for p in (REPO/'src/tesshunter').glob('*.py')}
    for name in ['scripts/revet_p6.py','scripts/audit_p5.py','p10/protocol/p10_funnel_calibration.py',
                 'p10/part3/protocol/funnel_worker.py','p10/part3/protocol/blind_io.py','p10/part3/protocol/common.py','p10/part3/protocol/science_json.py']:
        sources[name]=sha(REPO/name)
    config=read(ROOT/'protocol/config.json');jobs=[]
    for candidate in survivors:
        tic=int(candidate['tic_id']);pn=int(candidate['planet_num']);cid=f'tic{tic}_p{pn:02d}'
        identity=read(ROOT/f'results/input_identity/tic{tic}.json')
        selected=choose_verified(identity['records'],config)
        star={k:float(targets[tic][k]) for k in ('radius_rsun','mass_msun','teff_k','tmag','ra_deg','dec_deg')}
        nb=DATA/f'neighbours/tic{tic}.json'
        nb_ref=dict(path=nb.relative_to(REPO).as_posix(),sha256=sha(nb)) if nb.exists() and read(ROOT/f'results/neighbour_receipts/{tic}.json').get('ok') else None
        runtime=dict(candidate_id=cid,tic_id=tic,candidate=candidate,all_candidates=[c for c in candidates if int(c['tic_id'])==tic],star=star,
                     raw_products=[{k:p[k] for k in ('metadata','raw_path','raw_sha256')} for p in selected],
                     source_hashes=sources,neighbours_reference=nb_ref)
        path=ROOT/f'manifests/funnel_runtime/{cid}.json';write(path,runtime)
        jobs.append(dict(job_id=cid,arguments=['p10/part3/protocol/funnel_worker.py','A',path.relative_to(REPO).as_posix(),sha(path)],
                         result_path=f'p10/part3/results/funnel/A/{cid}.json'))
    write(ROOT/'manifests/timing_pilot_A_jobs.json',jobs)
    write(ROOT/'results/timing_pilot_A_dispatch.json',dict(utc=utc(),n_accepted=result['n_accepted_candidates'],n_pre_gate=len(jobs),
        search_unknowns=closure['unknowns'],workers=24,deadline_seconds=1200,forecast_minutes=max(1,len(jobs)*517*1.25/24/60),
        algorithm='Unchanged p10_funnel_calibration collect and pre-gate; Stage A on every P10 pilot pre-gate survivor',
        source_sha256=sha(__file__),outcome_access='Machine-only dispatch; main-session forecast consumes timing/count receipts only'))
    ledger=read(ROOT/'manifests/resource_ledger.json');hours=(time.perf_counter()-timer)/3600
    ledger['new_queue_hours']+=hours
    ledger['intervals'].append(dict(phase='timing_pilot_collect',start=started,end=utc(),hours=hours))
    write(ROOT/'manifests/resource_ledger.json',ledger,replace=True)
    print('Pilot Stage A dispatch:',len(jobs),'jobs; no retention outcomes displayed',flush=True)


if __name__=='__main__':main()
