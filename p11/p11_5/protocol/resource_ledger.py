"""Final expenditure ledger from immutable owner/case/acquisition receipts."""
from common import *
import sys,shutil,datetime,collections

CARRY_HOURS=.920809591111111
CARRY_BYTES=81827574

def stamp(value):
    return datetime.datetime.fromisoformat(value).timestamp()

def union(intervals):
    merged=[]
    for start,end in sorted(intervals):
        if end<start:raise ValueError('Negative interval')
        if merged and start<=merged[-1][1]:merged[-1][1]=max(end,merged[-1][1])
        else:merged.append([start,end])
    return merged

def build(final=True):
    if final and (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Live scientific owner at final accounting')
    events=[json.loads(s) for s in (ROOT/'manifests/events.jsonl').read_text().splitlines()]
    starts={};phases=[];intervals=[]
    for e in events:
        if e['event'] not in ('science_start','science_end'):continue
        identity=(e['pid'],e['create_time'])
        if e['event']=='science_start':
            if identity in starts:raise ValueError('Duplicate owner identity')
            starts[identity]=e
        else:
            begin=starts.pop(identity,None)
            if begin is None:raise ValueError('End without owner start')
            finish=stamp(e['utc']);start=min(stamp(begin['utc']),finish-e['wall_seconds'])
            intervals.append((start,finish));phases.append(dict(phase=e.get('phase'),start_utc=begin['utc'],end_utc=e['utc'],
                charged_seconds=finish-start,recorded_wall_seconds=e['wall_seconds'],pid=e['pid'],completed=e.get('completed')))
    if starts and final:raise ValueError('Unclosed science intervals')
    for begin in starts.values():
        intervals.append((stamp(begin['utc']),stamp(utc())))
    auxiliary=[]
    extra_paths=list((ROOT/'results').glob('archive_*pilot.json'))+list((ROOT/'results/storage_batches').glob('*.json'))
    for path in sorted(extra_paths):
        item=read(path)
        if item.get('utc') and item.get('wall_seconds') is not None:
            finish=stamp(item['utc']);intervals.append((finish-item['wall_seconds'],finish))
            auxiliary.append(dict(path=path.relative_to(REPO).as_posix(),sha256=sha(path),
                wall_seconds=item['wall_seconds'],cpu_seconds=item.get('cpu_seconds',0),purpose='Lossless evidence storage work'))
    for path in (ROOT/'results/acquisition').glob('*.json'):
        item=read(path)
        if item.get('utc') and item.get('wall_seconds') is not None:
            finish=stamp(item['utc']);intervals.append((finish-item['wall_seconds'],finish))
    merged=union(intervals);seconds=sum(b-a for a,b in merged)
    receipts=[];failures=[]
    for folder in sorted((ROOT/'results/controllers').iterdir()):
        if not folder.is_dir():continue
        for path in sorted(folder.glob('*.json')):
            r=read(path)
            if 'job_id' not in r or 'started_unix' not in r:continue
            command=r.get('command',[]);measurement_status=None;measurement_path=None
            if command and command[0].endswith('funnel_worker.py'):
                runtime=read(REPO/command[-1]);measurement_path=ROOT/f"results/funnel/{command[1]}/{runtime['candidate_id']}.json"
            elif command and command[0].endswith('c_v2_worker.py'):
                handoff=read(REPO/command[-1]);measurement_path=ROOT/f"results/funnel/C_v2/{handoff['candidate_id']}.json"
            if measurement_path is not None and measurement_path.exists():measurement_status=read(measurement_path).get('status')
            effective_status=measurement_status if measurement_status in ('INPUT_ERROR','TIMEOUT') else r['status']
            item=dict(phase=folder.name,path=path.relative_to(REPO).as_posix(),sha256=sha(path),
                job_id=r['job_id'],status=effective_status,controller_status=r['status'],
                measurement_operational_status=measurement_status,
                measurement_path=measurement_path.relative_to(REPO).as_posix() if measurement_path is not None and measurement_path.exists() else None,
                wall_seconds=r['wall_seconds'],
                sampled_process_tree_cpu_seconds=r.get('measured_process_tree_cpu_seconds'),
                peak_tree_rss_bytes=r.get('peak_tree_rss_bytes'))
            receipts.append(item)
            if effective_status!='COMPLETE':failures.append(item)
    downloaded=[]
    for path in sorted((ROOT/'results/acquisition').glob('*.json')):
        r=read(path);downloaded.append(dict(path=path.relative_to(REPO).as_posix(),sha256=sha(path),bytes=r.get('bytes',0),
            url=r.get('url'),status_code=r.get('status_code')))
    network=[]
    for path in sorted((ROOT/'results/network').glob('*.jsonl')):
        lines=path.read_text().splitlines();last=None
        for line in reversed(lines):
            try:last=json.loads(line);break
            except json.JSONDecodeError:continue
        if last:network.append(dict(path=path.relative_to(REPO).as_posix(),sha256=sha(path),bytes=last['cumulative_response_body_bytes']))
    bytes_new=sum(r['bytes'] for r in downloaded+network)
    output=dict(utc=utc(),final=final,prior_charged_hours=CARRY_HOURS,
        p11_5_scientific_union_hours=seconds/3600,cumulative_charged_hours=CARRY_HOURS+seconds/3600,
        remaining_queue_hours=48-CARRY_HOURS-seconds/3600,union_intervals_unix=merged,phases=phases,
        case_count=len(receipts),case_status_counts=dict(collections.Counter(r['status'] for r in receipts)),
        actual_experiment_job_wall_seconds=sum(r['wall_seconds'] for r in receipts)+sum(r['wall_seconds'] for r in auxiliary),
        actual_experiment_sampled_process_tree_cpu_seconds=sum(r['sampled_process_tree_cpu_seconds'] or 0 for r in receipts)+sum(r['cpu_seconds'] for r in auxiliary),
        auxiliary_evidence_storage=auxiliary,
        maximum_measured_case_tree_rss_bytes=max((r['peak_tree_rss_bytes'] or 0 for r in receipts),default=0),
        cpu_measurement_limit='Controller samples process-tree CPU each second. It includes initialization but can miss the final sampling tail; worker body CPU is separately preserved. The sampled total is not claimed to be exact whole-process CPU. Standalone method totals retain their full shared scientific work and failed-attempt expenditure is separately reported.',
        prior_acquisition_bytes=CARRY_BYTES,p11_5_acquisition_bytes=bytes_new,cumulative_acquisition_bytes=CARRY_BYTES+bytes_new,
        acquisition=downloaded,network_response_bodies=network,free_disk_bytes=shutil.disk_usage(REPO).free,
        failures=failures,case_receipts=receipts,user_pauses=[e for e in events if e['event'].startswith('user_pause')],
        accounting='Union of owning-controller scientific intervals including all failures/stalls, acquisition intervals and lossless evidence-storage intervals, plus unchanged conservative P11 carry. Overlapping intervals count once. Idle assistant analysis and software regression are not active scientific queues. HTTP response bodies are counted on all instrumented attempts; no light-curve acquisitions were silently inferred from cache hits.')
    write(ROOT/('results/resource_accounting_final.json' if final else 'results/resource_accounting_snapshot.json'),output,replace=not final)
    print(json.dumps({k:output[k] for k in ('cumulative_charged_hours','remaining_queue_hours','cumulative_acquisition_bytes','free_disk_bytes','case_count','case_status_counts')}))
    return output

if __name__=='__main__':build('--snapshot' not in sys.argv)
