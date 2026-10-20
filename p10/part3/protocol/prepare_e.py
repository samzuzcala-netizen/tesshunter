"""Freeze the full nested order and six-star timing pilot before blind search."""
from common import REPO,ROOT,DATA,read,write,sha,utc,environment
environment()
from registration_chain import verify
from nested_order import order,timing_pilot
import csv,sys


def main():
    verify()
    d=read(ROOT/'results/part_d.json')
    if d['STOP_1_fired']:raise RuntimeError('STOP-1 requires main-session delivery')
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Controller already owns the machine')
    targets={int(r['tic_id']):r for r in csv.DictReader((ROOT/'manifests/targets_eligible.csv').open())}
    metadata=[]
    for tic,row in targets.items():
        n=read(ROOT/f'results/native_noise/tic{tic}.json')
        metadata.append(dict(tic_id=tic,tmag=float(row['tmag']),n_usable_sectors=len(n['usable_sectors']),n_cad=n['n_cad']))
    nested=order(metadata);pilot=timing_pilot(metadata)
    sizes=list(dict.fromkeys([len(nested)]+[n for n in (400,300,200) if n<=len(nested)]))
    write(ROOT/'manifests/evaluation_order.json',dict(utc=utc(),order=nested,pilot=pilot,levels=sizes,
        outcomes_inspected=False,selection_frozen=False,selection_pending_timing_pilot=True,source_sha256=sha(ROOT/'protocol/nested_order.py')))
    sys.path.insert(0,str(REPO/'src'))
    from tesshunter import survey
    sources={p.relative_to(REPO).as_posix():sha(p) for p in (REPO/'src/tesshunter').glob('*.py')}
    sources.update({p:sha(REPO/p) for p in ['p10/part3/protocol/blind_search_worker.py','p10/part3/protocol/blind_io.py','p10/part3/protocol/common.py','p10/part3/protocol/science_json.py']})
    jobs=[]
    for preset in ('survey_p10','survey_p8'):
        for entry in pilot:
            tic=entry['tic_id'];n=read(ROOT/f'results/native_noise/tic{tic}.json');r=targets[tic]
            star={k:float(r[k]) for k in ('radius_rsun','mass_msun','teff_k','tmag','ra_deg','dec_deg')}
            runtime=dict(job_id=f'{preset}_tic{tic}',tic_id=tic,preset=preset,star=star,
                         prepared_path=n['prepared_path'],prepared_sha256=n['prepared_sha256'],provenance_sha256=n['provenance_sha256'],ingest_key=n['ingest_key'],source_hashes=sources)
            path=ROOT/f'manifests/search_runtime/{preset}_tic{tic}.json';write(path,runtime)
            jobs.append(dict(job_id=runtime['job_id'],arguments=['p10/part3/protocol/blind_search_worker.py',path.relative_to(REPO).as_posix(),sha(path)],
                             result_path=f'p10/part3/results/search_receipts/{preset}/tic{tic}.json'))
    write(ROOT/'manifests/timing_pilot_search_jobs.json',jobs)
    write(ROOT/'manifests/timing_pilot_preflight.json',dict(utc=utc(),hosts=6,search_jobs=12,workers=24,deadline_seconds=3600,
        historical_max_seconds=1682,forecast_minutes=1682*1.25/60,hard_search_phase_minutes=60,
        layout='Same 24-core affinity and top-level single-thread worker layout as production; 12 jobs available in the paired six-host pilot',
        next='Machine-only collect and Stage A timing on each P10 pre-gate survivor, then main-session level/P8 allocation review',
        blind_outcomes_read_for_selection=False,source_hashes=sources))
    print('Frozen nested order',len(nested),'hosts; timing pilot',[(r['tic_id'],r['tercile']) for r in pilot],flush=True)


if __name__=='__main__':main()
