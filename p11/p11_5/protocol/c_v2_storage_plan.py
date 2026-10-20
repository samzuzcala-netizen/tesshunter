"""Finite corrected-C batches with independently charged, lossless packing."""
from common import *
environment()
import math,shutil,sys
import psutil
from resource_ledger import build

WORKERS=24
C_SECONDS=600
PACK_SECONDS=300
FLOOR=30000000000
BUFFER=500000000
METADATA=250000000
PACK_SOURCES=('common.py','model_storage.py','model_pack_worker.py',
              'cpu_allocation.py','owned_worker.py','record_io.py','controller_v2.py')


def split_batches(items,capacity):
    if len({x['job']['job_id'] for x in items})!=len(items):
        raise ValueError('Duplicate corrected-C job')
    groups=[];group=[];size=0.
    for item in items:
        amount=item['predicted_npz_bytes']
        if amount<=0 or amount>capacity:
            raise ValueError('A model does not fit the finite batch capacity')
        if group and size+amount>capacity:
            groups.append(group);group=[];size=0.
        group.append(item);size+=amount
    if group:groups.append(group)
    return groups


def queue_bound(n,seconds,workers=WORKERS):
    return (math.ceil(n/workers)+1)*seconds/3600 if n else 0.


def packing_workers(sizes,free,available,peak):
    for workers in (24,16,12,8,4,2,1):
        count=min(workers,len(sizes))
        temporary=1.05*sum(sorted(sizes,reverse=True)[:count])+METADATA
        if free-FLOOR>=temporary and available>=count*peak+2500000000:
            return workers
    raise RuntimeError('Even one bounded packing worker lacks storage or memory headroom')


def closed_guard():
    if (ROOT/'manifests/controller_owner.json').exists():
        raise RuntimeError('Wait for the owning controller to close')


def write_or_verify(path,value):
    if Path(path).exists():
        if digest(read(path))!=digest(value):raise ValueError('Existing packing manifest identity differs')
    else:write(path,value)


def closed_manifest(path,expected_count):
    receipt=ROOT/'results/controllers'/Path(path).stem/'closed.json'
    record=read(receipt)
    if record['failure'] is not None or record['pending'] or record['completed']!=expected_count:
        raise RuntimeError('The preceding finite owner did not complete its attempted manifest')
    if not record['source_hashes_verified_at_end']:
        raise ValueError('The preceding owner source hashes changed')
    return receipt


def register():
    closed_guard()
    test=read(ROOT/'results/c_v2_storage_plan_tests_v1.json')
    if test['exit_code']!=0 or not test['source_hashes_verified_at_end']:
        raise ValueError('Storage planner tests have not passed')
    for path,expected in test['source_hashes'].items():
        if sha(REPO/path)!=expected:raise ValueError('Tested storage planner source changed')
    refused=read(ROOT/'manifests/c_v2_affordability.json')
    pilot_job=read(ROOT/'manifests/c_v2_storage_pilot_jobs.json')[0]
    pilot_plan=read(REPO/pilot_job['command'][-1]);cid=pilot_plan['candidate_id']
    packed_path=ROOT/f'results/model_storage/C_v2/{cid}.json';packed=read(packed_path)
    timing_path=ROOT/f"results/controllers/c_v2_storage_pilot_jobs/{pilot_job['job_id']}.json"
    timing=read(timing_path)
    closed_manifest('c_v2_storage_pilot_jobs.json',1)
    if timing['status']!='COMPLETE' or not packed['original_container_bytes_identical']:
        raise ValueError('Native lossless packing pilot did not complete')
    if sha(REPO/packed['physical_archive'])!=packed['packed_sha256']:
        raise ValueError('Native packed archive changed')
    density=refused['storage_guard']['maximum_measured_archive_bytes_per_point']*1.25
    items=[]
    for job in read(ROOT/'manifests/c_v2_jobs.json'):
        handoff=read(REPO/job['command'][-1]);candidate=handoff['candidate_id']
        if (ROOT/f'results/funnel/C_v2/{candidate}.json').exists():continue
        points=int(read(REPO/handoff['prep_metadata_path'])['n_binned'])
        items.append(dict(job=job,candidate_id=candidate,native_points=points,
                          predicted_npz_bytes=points*density))
    if len(items)!=refused['remaining_jobs']:
        raise ValueError('Remaining corrected-C cohort changed before storage registration')
    ratio=max(.75,1.10*packed['packed_bytes']/packed['original_bytes'])
    full_packed=ratio*sum(x['predicted_npz_bytes'] for x in items)+METADATA
    free=shutil.disk_usage(REPO).free
    capacity=min(2400000000.,math.floor((free-FLOOR-full_packed-BUFFER)/100000000)*100000000)
    groups=split_batches(items,capacity)
    resource=build(final=False)
    rows=[]
    for index,group in enumerate(groups,1):
        rows.append(dict(index=index,c_manifest=f'p11/p11_5/manifests/c_v2_batch_{index:02d}_jobs.json',
            pack_manifest=f'p11/p11_5/manifests/c_v2_pack_batch_{index:02d}_jobs.json',
            candidate_ids=[x['candidate_id'] for x in group],jobs=len(group),
            native_points=sum(x['native_points'] for x in group),
            maximum_native_points=max(x['native_points'] for x in group),
            predicted_npz_bytes=sum(x['predicted_npz_bytes'] for x in group),
            C_deadline_queue_hours=queue_bound(len(group),C_SECONDS),
            packing_deadline_queue_hours=queue_bound(len(group),PACK_SECONDS)))
    total=sum(r['C_deadline_queue_hours']+r['packing_deadline_queue_hours'] for r in rows)
    packing_peak=max(512*1024**2,1.25*timing['peak_tree_rss_bytes'])
    record=dict(utc=utc(),remaining_candidates=len(items),workers=WORKERS,
        C_deadline_seconds=C_SECONDS,packing_deadline_seconds=PACK_SECONDS,
        candidate_order='Preserve the frozen c_v2_jobs.json order; split only by native-point storage forecast.',
        original_candidate_manifest_sha256=sha(ROOT/'manifests/c_v2_jobs.json'),
        prior_full_plain_refusal_sha256=sha(ROOT/'manifests/c_v2_affordability.json'),
        packing_pilot_receipt_sha256=sha(packed_path),packing_pilot_timing_sha256=sha(timing_path),
        measured_packing_ratio=packed['packed_bytes']/packed['original_bytes'],
        forecast_packing_ratio=ratio,forecast_ratio_is_not_a_guarantee=True,
        ratio_guard='Check actual disk, archive bytes, case hashes and memory before every finite phase. Replan only from operational storage/timing information if the envelope is exceeded; retain every scientific case and threshold.',
        predicted_all_remaining_packed_bytes=full_packed,batch_original_archive_capacity_bytes=capacity,
        free_disk_at_registration=free,free_disk_floor_bytes=FLOOR,additional_buffer_bytes=BUFFER,
        metadata_reserve_bytes=METADATA,packing_case_memory_envelope_bytes=packing_peak,
        C_fixed_memory_bytes=refused['memory_guard']['fixed_overhead_bytes'],
        C_bytes_per_native_point=1024,C_memory_headroom_factor=1.25,
        conservative_C_and_packing_queue_hours=total,validation_reserve_hours=15.,analysis_reserve_hours=2.,
        remaining_total_queue_hours=resource['remaining_queue_hours'],
        fits_budget=total+17<=resource['remaining_queue_hours'],
        source_hashes={f'p11/p11_5/protocol/{n}':sha(ROOT/'protocol'/n) for n in (*PACK_SOURCES,'c_v2_storage_plan.py')},
        scientific_source_hashes=read(ROOT/'manifests/c_v2_execution_freeze.json')['source_hashes'],
        tested_planner_receipt_sha256=sha(ROOT/'results/c_v2_storage_plan_tests_v1.json'),
        scientific_decisions_or_truth_read=False,scientific_predictions_changed=False,batches=rows)
    if not record['fits_budget']:
        write(ROOT/'manifests/c_v2_storage_plan_refused_v1.json',record)
        raise RuntimeError('Finite C and packing deadline bounds exceed the retained reserves')
    for row,group in zip(rows,groups):
        write(REPO/row['c_manifest'],[x['job'] for x in group])
        row['c_manifest_sha256']=sha(REPO/row['c_manifest'])
    write(ROOT/'manifests/c_v2_storage_plan_v1.json',record)
    print(json.dumps({k:record[k] for k in ('remaining_candidates','forecast_packing_ratio','predicted_all_remaining_packed_bytes','batch_original_archive_capacity_bytes','conservative_C_and_packing_queue_hours','remaining_total_queue_hours','fits_budget')}))
    print('Finite batches:',len(rows),'candidate counts:',[r['jobs'] for r in rows])


def prepare(index,kind):
    closed_guard();policy=read(ROOT/'manifests/c_v2_storage_plan_v1.json')
    for path,expected in {**policy['source_hashes'],**policy['scientific_source_hashes']}.items():
        if sha(REPO/path)!=expected:raise ValueError('Registered storage/scientific source changed: '+path)
    row=policy['batches'][index-1]
    if row['index']!=index or kind not in ('C','PACK'):raise ValueError('Invalid finite phase')
    current_manifest=row['c_manifest'] if kind=='C' else row['pack_manifest']
    if (ROOT/'results/controllers'/Path(current_manifest).stem/'closed.json').exists():
        raise RuntimeError('This finite phase has already been attempted')
    for prior in policy['batches'][:index-1]:
        closed_manifest(prior['c_manifest'],prior['jobs'])
        closed_manifest(prior['pack_manifest'],len(read(REPO/prior['pack_manifest'])))
        for job in read(REPO/prior['pack_manifest']):
            frozen=read(REPO/job['command'][-1]);cid=frozen['candidate_id']
            packed=read(ROOT/f'results/model_storage/C_v2/{cid}.json')
            if (packed['original_sha256']!=frozen['archive_sha256'] or
                packed['case_sha256']!=frozen['case_sha256'] or
                sha(REPO/packed['physical_archive'])!=packed['packed_sha256'] or
                sha(REPO/frozen['case_path'])!=frozen['case_sha256']):
                raise ValueError('Preceding packed evidence identity changed')
        for cid in prior['candidate_ids']:
            if (DATA/f'c_models_v2/{cid}.npz').exists():
                raise RuntimeError('A preceding batch still has unpacked model evidence')
    if sha(REPO/row['c_manifest'])!=row['c_manifest_sha256']:
        raise ValueError('Finite scientific manifest changed')
    free=shutil.disk_usage(REPO).free;available=psutil.virtual_memory().available
    if kind=='C':
        manifest=REPO/row['c_manifest'];workers=WORKERS;seconds=C_SECONDS
        memory=1.25*(policy['C_fixed_memory_bytes']+1024*row['maximum_native_points'])*workers+2500000000
        required_disk=(1+policy['forecast_packing_ratio'])*row['predicted_npz_bytes']+METADATA+BUFFER
        current_bound=row['C_deadline_queue_hours']+row['packing_deadline_queue_hours']
    else:
        closed_manifest(row['c_manifest'],row['jobs'])
        jobs=[];sizes=[]
        hashes={f'p11/p11_5/protocol/{n}':sha(ROOT/'protocol'/n) for n in PACK_SOURCES}
        for cid in row['candidate_ids']:
            case=ROOT/f'results/funnel/C_v2/{cid}.json';record=read(case)
            if record['candidate_id']!=cid:raise ValueError('Completed C identity differs')
            archive=DATA/f'c_models_v2/{cid}.npz'
            if not archive.exists():continue
            sizes.append(archive.stat().st_size)
            plan=dict(candidate_id=cid,stage='C_v2',case_path=case.relative_to(REPO).as_posix(),case_sha256=sha(case),
                archive_path=archive.relative_to(REPO).as_posix(),archive_sha256=sha(archive),source_hashes=hashes)
            runtime=ROOT/f'manifests/runtime_model_pack/{cid}.json';write_or_verify(runtime,plan)
            jobs.append(dict(job_id='PACK_C_v2_'+cid,command=['p11/p11_5/protocol/model_pack_worker.py',runtime.relative_to(REPO).as_posix()],source_paths=sorted(hashes)))
        manifest=REPO/row['pack_manifest'];write_or_verify(manifest,jobs)
        workers=packing_workers(sizes,free,available,policy['packing_case_memory_envelope_bytes'])
        seconds=PACK_SECONDS;memory=min(workers,len(sizes))*policy['packing_case_memory_envelope_bytes']+2500000000
        required_disk=1.05*sum(sorted(sizes,reverse=True)[:workers])+METADATA
        current_bound=queue_bound(len(jobs),seconds,workers)
    future=sum(r['C_deadline_queue_hours']+r['packing_deadline_queue_hours'] for r in policy['batches'][index:])
    resource=build(final=False)
    check=dict(utc=utc(),batch=index,kind=kind,manifest=manifest.relative_to(REPO).as_posix(),manifest_sha256=sha(manifest),
        workers=workers,timeout_seconds=seconds,free_disk_bytes=free,required_additional_disk_bytes=required_disk,
        available_memory_bytes=available,required_memory_bytes=memory,
        remaining_queue_hours=resource['remaining_queue_hours'],current_and_future_bound_hours=current_bound+future,
        reserved_validation_and_analysis_hours=17.,disk_fits=free>=FLOOR+required_disk,
        memory_fits=available>=memory,budget_fits=current_bound+future+17<=resource['remaining_queue_hours'],
        policy_sha256=sha(ROOT/'manifests/c_v2_storage_plan_v1.json'),scientific_outcomes_read=False)
    directory=ROOT/'results/c_v2_batch_checks'
    serial=len(list(directory.glob(f'{index:02d}_{kind}_*.json')))+1
    write(directory/f'{index:02d}_{kind}_{serial:02d}.json',check)
    if not all(check[k] for k in ('disk_fits','memory_fits','budget_fits')):
        raise RuntimeError('Finite phase preflight requires an operational resource replan')
    print(json.dumps(check))


if __name__=='__main__':
    if sys.argv[1]=='register':register()
    else:prepare(int(sys.argv[2]),sys.argv[1])
