"""Prospective bounded corrected-C allocation, without reading C decisions."""
from common import *
environment()
import sys,math,shutil
import psutil
from resource_ledger import build

def main(mode):
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Existing scientific owner is active')
    jobs=read(ROOT/'manifests/c_v2_jobs.json')
    if mode=='pilot':
        # Metadata-only identity order; choosing a real case does not consult its
        # old or new C measurement. The selected complete population is fixed.
        ordered=sorted(jobs,key=lambda j:order(read(REPO/read(REPO/j['command'][-1])['runtime_path'])['tic_id'],'timing')+j['job_id'])
        if not ordered:raise ValueError('No corrected C jobs')
        write(ROOT/'manifests/c_v2_memory_pilot_jobs.json',ordered[:1])
        print('One corrected C native memory pilot frozen',ordered[0]['job_id'])
        return
    if mode!='remaining':raise ValueError('Use pilot or remaining')
    receipt=read(ROOT/'results/controllers/c_v2_memory_pilot_jobs/closed.json')
    if receipt['completed']!=1:raise ValueError('Memory pilot is incomplete')
    pilot=read(ROOT/'manifests/c_v2_memory_pilot_jobs.json')[0]
    timing=read(ROOT/f"results/controllers/c_v2_memory_pilot_jobs/{pilot['job_id']}.json")
    pilot_handoff=read(REPO/pilot['command'][-1])
    pilot_points=int(read(REPO/pilot_handoff['prep_metadata_path'])['n_binned'])
    if pilot_points<=0 or not timing.get('peak_tree_rss_bytes'):
        raise ValueError('Native memory pilot lacks usable size/RSS measurements')
    resource=build(final=False)
    remaining=[j for j in jobs if not (ROOT/f"results/funnel/C_v2/{read(REPO/j['command'][-1])['candidate_id']}.json").exists()]
    point_counts=[int(read(REPO/read(REPO/j['command'][-1])['prep_metadata_path'])['n_binned']) for j in remaining]
    maximum_points=max(point_counts,default=pilot_points)
    # A conservative engineering envelope supplements the measured pilot. The
    # previous finite-C pilot used at most 371.3 MB for 163,028 native points.
    # Retain 512 MiB fixed overhead, 1 KiB per native point and 25% headroom;
    # raise the fixed component if this corrected pilot exceeds that envelope.
    fixed=max(512*1024**2,timing['peak_tree_rss_bytes']-1024*pilot_points)
    predicted_peak=1.25*(fixed+1024*maximum_points)
    available=psutil.virtual_memory().available
    memory_fits=24*predicted_peak+2500000000<=available
    densities=[]
    archive_sizes={p.stem:p.stat().st_size for p in (DATA/'c_models').glob('*.npz')}
    for path in sorted((ROOT/'results/model_storage').glob('*.json')):
        packed=read(path)
        if packed.get('candidate_id') and packed.get('original_container_bytes_identical'):
            archive_sizes.setdefault(packed['candidate_id'],packed['original_bytes'])
    for cid,size in sorted(archive_sizes.items()):
        metadata=list((DATA/f'funnel/{cid}/prep').glob('*.json'))
        if len(metadata)==1:
            n=int(read(metadata[0])['n_binned'])
            if n>0:densities.append(size/n)
    if not densities:raise ValueError('Retained finite-C model storage pilot is required')
    predicted_model_bytes=1.25*max(densities)*sum(point_counts)+250000000
    free_disk=shutil.disk_usage(REPO).free
    storage_fits=predicted_model_bytes+30000000000<=free_disk
    # Deadline upper bound is stronger than an optimistic scale-up extrapolation.
    # Reserve a full wave for launch/receipt overhead and retain prior validation
    # and analysis reserves before authorizing this finite queue.
    queue_hours=(math.ceil(len(remaining)/24)+1)*600/3600
    reserve_validation=15.;reserve_analysis=2.
    fits=queue_hours+reserve_validation+reserve_analysis<=resource['remaining_queue_hours']
    write(ROOT/'manifests/c_v2_affordability.json',dict(utc=utc(),remaining_jobs=len(remaining),
        native_pilot_operational_status=timing['status'],native_pilot_wall_seconds=timing['wall_seconds'],
        native_pilot_peak_tree_rss_bytes=timing['peak_tree_rss_bytes'],
        conservative_deadline_queue_hours=queue_hours,remaining_total_queue_hours=resource['remaining_queue_hours'],
        conditional_validation_reserve_hours=reserve_validation,analysis_reserve_hours=reserve_analysis,
        fits_remaining_budget=fits,workers=24,case_deadline_seconds=600,
        memory_guard=dict(pilot_native_points=pilot_points,maximum_remaining_native_points=maximum_points,
            fixed_overhead_bytes=fixed,bytes_per_native_point=1024,headroom_factor=1.25,
            predicted_largest_case_peak_bytes=predicted_peak,available_memory_bytes=available,
            unallocated_floor_bytes=2500000000,fits_24_workers=memory_fits,
            meaning='Conservative size-scaled engineering envelope plus measured native pilot; live available-memory guard remains enabled'),
        storage_guard=dict(native_model_pilots=len(densities),maximum_measured_archive_bytes_per_point=max(densities),
            native_points_in_remaining_jobs=sum(point_counts),headroom_factor=1.25,
            metadata_reserve_bytes=250000000,predicted_new_model_bytes=predicted_model_bytes,
            current_free_disk_bytes=free_disk,required_free_disk_floor_bytes=30000000000,
            full_plain_model_queue_fits=storage_fits,
            fallback='If necessary, prospectively register finite C batches and verified lossless archive packing; preserve all candidate jobs and original logical bytes. Do not discard controls or change thresholds.'),
        decisions_or_recovery_counts_read=False,unchanged_development_selection_sha256=sha(ROOT/'manifests/development_selection.json')))
    if not fits:raise RuntimeError('Corrected C plus retained reserves exceeds remaining cap; prospective budget review is required')
    if not memory_fits:raise RuntimeError('Corrected C 24-worker memory envelope does not fit; prospective allocation review is required')
    if not storage_fits:raise RuntimeError('Corrected C full plain-archive queue does not fit disk headroom; register bounded storage batches before launch')
    write(ROOT/'manifests/c_v2_remaining_jobs.json',remaining)
    print('Corrected C remaining jobs frozen',len(remaining),'deadline queue upper bound hours',queue_hours)

if __name__=='__main__':main(sys.argv[1])
