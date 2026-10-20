"""Preserve uniformly interrupted partial snapshots before a source-repaired resume."""
from common import *
import psutil

def main():
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Scientific owner is still registered')
    folder=ROOT/'results/controllers/development_complete';closed=read(folder/'closed.json')
    if closed['failure']!="PermissionError(13, 'Access is denied')":raise ValueError('Unexpected interruption; review required')
    identity=closed['identity']
    try:
        process=psutil.Process(identity['pid'])
        if process.create_time()==identity['create_time']:raise RuntimeError('Original owner is still running')
    except psutil.NoSuchProcess:pass
    rows=[]
    for case in closed['failures']:
        if case['status']!='INTERRUPTED' or case['stage']!='search':raise ValueError('Not a uniformly controller-interrupted search')
        try:
            process=psutil.Process(case['pid'])
            if process.create_time()==case['create_time']:raise RuntimeError('Interrupted worker remains alive')
        except psutil.NoSuchProcess:pass
        jid=case['key'];source=(DATA/'search_snapshots'/jid).resolve()
        destination=(DATA/'interrupted_snapshots/development_complete'/jid).resolve()
        boundary=DATA.resolve()
        if not source.is_relative_to(boundary) or not destination.is_relative_to(boundary):raise ValueError('Snapshot move outside isolated P11.5 data')
        final=ROOT/f'results/search/{jid}.json'
        row=dict(job_id=jid,interrupted_receipt_sha256=sha(folder/(case['job_id']+'.json')),
            wall_seconds=case['wall_seconds'],cpu_seconds=case['measured_process_tree_cpu_seconds'],
            complete_prediction_present=final.exists())
        if final.exists():
            row.update(action='REUSE_COMPLETED_PREDICTION',prediction_sha256=sha(final))
        elif source.exists():
            if destination.exists():raise FileExistsError(destination)
            hashes={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*') if p.is_file()}
            # Resolved source and destination were both checked against the
            # exact new-data boundary. Rename only this incomplete snapshot
            # directory; no historical data or completed prediction is moved.
            destination.parent.mkdir(parents=True,exist_ok=True);source.rename(destination)
            if any(sha(destination/p)!=h for p,h in hashes.items()):raise ValueError('Partial snapshot bytes changed')
            row.update(action='PRESERVE_PARTIAL_AND_RECOMPUTE_UNCHANGED_SERIES',
                original_directory=source.relative_to(REPO).as_posix(),preserved_directory=destination.relative_to(REPO).as_posix(),hashes=hashes)
        else:row['action']='RECOMPUTE_UNCHANGED_SERIES_NO_PARTIAL_SNAPSHOT'
        rows.append(row)
    write(ROOT/'manifests/controller_interruption_recovery_v1.json',dict(utc=utc(),
        original_controller_closed_sha256=sha(folder/'closed.json'),
        original_worker_source_hashes_verified=closed['source_hashes_verified_at_end'],rows=rows,
        diagnosis='A complete progress.json.tmp remains from 2026-09-13T23:35:17.941207Z while the previous progress.json remains. Failure was a Windows PermissionError during the monitored progress update; exact original traceback was not captured. Replacement retries and durable tracebacks are added only in a new controller version.',
        scientific_source_config_or_input_changed=False,aggregate_efficacy_inspected=False,
        completed_results_recomputed=False,all_old_attempt_costs_retained=True,
        retry_rule='One uniform continuation after controller source repair for every interrupted eligible series, with identical inputs, detector limits and per-case deadlines. No scientific outcome selects a retry.',
        resumed_stages='Search, A, S and B; skip further superseded first-version C work and measure required final C_v2 in its separately frozen phase.',
        selected_population=dict(hosts=120,injections=242,natural_series=120)))
    print('Interrupted search attempts preserved',len(rows),'completed predictions retained',sum(r['complete_prediction_present'] for r in rows))

if __name__=='__main__':main()
