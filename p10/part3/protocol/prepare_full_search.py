"""Freeze both full-search job manifests; reuse completed pilot inputs and outputs."""
from common import REPO,ROOT,DATA,read,write,sha,utc,environment
environment()
from registration_execution_v3 import verify
import csv,math


def main():
    verify()
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Owner present')
    allocation=read(ROOT/'manifests/allocation.json');hosts=allocation['selected_tic_ids'];pilot=set(allocation['reused_pilot_tic_ids'])
    targets={int(r['tic_id']):r for r in csv.DictReader((ROOT/'manifests/targets_evaluated.csv').open())}
    oldseal=read(ROOT/'manifests/timing_pilot_closed_evidence_seal.json')['files']
    remaining=[]
    for preset in allocation['preset_sequence']:
        jobs=[];reused=[]
        template=read(ROOT/f'manifests/search_runtime/{preset}_tic{allocation["reused_pilot_tic_ids"][0]}.json')
        for p,h in template['source_hashes'].items():
            if sha(REPO/p)!=h:raise RuntimeError('Pilot scientific source changed: '+p)
        for tic in hosts:
            noise=read(ROOT/f'results/native_noise/tic{tic}.json');star={k:float(targets[tic][k]) for k in ('radius_rsun','mass_msun','teff_k','tmag','ra_deg','dec_deg')}
            if sha(REPO/noise['prepared_path'])!=noise['prepared_sha256'] or sha((REPO/noise['prepared_path']).with_suffix('.json'))!=noise['provenance_sha256']:raise RuntimeError('Native prepared input changed')
            runtime=dict(job_id=f'{preset}_tic{tic}',tic_id=tic,preset=preset,star=star,prepared_path=noise['prepared_path'],prepared_sha256=noise['prepared_sha256'],provenance_sha256=noise['provenance_sha256'],ingest_key=noise['ingest_key'],source_hashes=template['source_hashes'])
            path=ROOT/f'manifests/search_runtime/{preset}_tic{tic}.json'
            if tic in pilot:
                if read(path)!=runtime:raise RuntimeError('Pilot runtime changed on reuse')
                receipt_path=ROOT/f'results/search_receipts/{preset}/tic{tic}.json';receipt=read(receipt_path)
                if receipt['status']!='COMPLETE':raise RuntimeError('Pilot result cannot be reused as complete')
                for name in [receipt_path.relative_to(REPO).as_posix(),receipt['result_path'],receipt['trace_path']]:
                    if sha(REPO/name)!=oldseal[name]['sha256']:raise RuntimeError('Sealed pilot evidence changed')
                reused.append(dict(tic_id=tic,receipt_path=receipt_path.relative_to(REPO).as_posix(),receipt_sha256=sha(receipt_path),runtime_sha256=sha(path),result_sha256=receipt['result_sha256'],trace_sha256=receipt['trace_sha256']))
            else:
                if (DATA/f'runs/{preset}/results/tic{tic}.json').exists():raise RuntimeError('Unexpected pre-existing nonpilot result')
                write(path,runtime)
                jobs.append(dict(job_id=runtime['job_id'],arguments=['p10/part3/protocol/blind_search_worker.py',path.relative_to(REPO).as_posix(),sha(path)],result_path=f'p10/part3/results/search_receipts/{preset}/tic{tic}.json'))
        assert len(jobs)==430 and len(reused)==6
        phase=f'search_{preset}'
        job_path=ROOT/f'manifests/{phase}_jobs.json';write(job_path,jobs)
        forecast=allocation['tail_crosscheck']['component_hours'][preset]*1.25*60
        write(ROOT/f'manifests/{phase}_preflight.json',dict(utc=utc(),phase=phase,preset=preset,hosts=436,new_jobs=430,reused_pilot_hosts=6,workers=24,deadline_seconds=3600,
            forecast_minutes=forecast,planning_minutes=allocation['planning_basis']['component_hours'][preset]*60,
            jobs_sha256=sha(job_path),allocation_sha256=sha(ROOT/'manifests/allocation.json'),reused=reused,
            individual_runtime_and_native_hashes_verified=True,pilot_scientific_source_hashes_unchanged=True))
        plan=ROOT/f'manifests/prediction_plan_{preset}.json'
        write(plan,dict(utc=utc(),status='MEMBERSHIP_FROZEN_AWAITING_REMAINING_PREDICTIONS',preset=preset,tic_ids=hosts,
            allocation_sha256=sha(ROOT/'manifests/allocation.json'),jobs_sha256=sha(job_path),reused_pilot=reused,
            expected_terminal_hosts=436,required_candidate_fields=['period_days','epoch_btjd','duration_days','depth_ppt','stitch_snr','partition','partition_budget_exhausted'],
            final_manifest=f'p10/part3/manifests/predictions_{preset}.json',sidecar_access_permitted=False))
        remaining.append(dict(preset=preset,jobs=430,forecast_minutes=forecast))
    write(ROOT/'manifests/full_search_plan_seal.json',dict(utc=utc(),hashes={p.relative_to(REPO).as_posix():sha(p) for p in
        [ROOT/f'manifests/{prefix}_{preset}{suffix}.json' for preset in allocation['preset_sequence'] for prefix,suffix in [('search','_jobs'),('prediction_plan','')]]},
        allocation_sha256=sha(ROOT/'manifests/allocation.json'),prediction_status='Planned membership locked; final candidate predictions lock at preset closure'))
    print(dict(remaining=remaining,pilot_hosts_reused_both_presets=6))


if __name__=='__main__':main()
