"""Receipt reconciliation copied from P11.5 interruption recovery.

No completed result or partial scientific snapshot is moved or recomputed.
The isolated resume manifest contains only interrupted and unstarted jobs.
"""
from p12_common import REPO, ROOT, read, write, sha, utc
from controller_p12 import identity_alive, terminate_owned
from datetime import datetime
import argparse
import json


def reconcile(phase):
    folder = ROOT / 'results/controllers' / phase
    if not (folder / 'launch.json').is_file():
        raise RuntimeError('STOP-5 MISSING_LAUNCH_RECEIPT')
    launch = read(folder / 'launch.json')
    owner = launch['owner']
    owner_path = ROOT / 'manifests/controller_owner.json'
    if identity_alive(owner):
        raise RuntimeError('Original controller remains alive')
    if owner_path.exists():
        recorded = read(owner_path)
        if any(recorded.get(k) != owner.get(k) for k in ('pid', 'create_time', 'command', 'phase')):
            raise RuntimeError('STOP-5 RECYCLED_OWNER_RECEIPT')
    sources = launch['source_hashes']
    for name, digest in sources.items():
        expected = digest.get('sha256') if isinstance(digest, dict) else digest
        if not (REPO / name).is_file() or sha(REPO / name) != expected:
            raise RuntimeError('STOP-5 SOURCE_IDENTITY_UNRECONCILABLE: ' + name)
    jobs = launch['frozen_jobs']
    if len({j['job_id'] for j in jobs}) != len(jobs):
        raise RuntimeError('STOP-5 DUPLICATE_FROZEN_JOB')
    progress_path = folder / 'progress.json'
    progress = read(progress_path) if progress_path.exists() else {}
    snapshots = {w['job_id']: w for w in progress.get('workers', [])}
    known = {j['job_id'] for j in jobs}
    if any(path.stem not in known for path in (folder / 'attempts').glob('*.json')):
        raise RuntimeError('STOP-5 UNKNOWN_ATTEMPT_RECEIPT')
    rows, resume, completed = [], [], []
    for job in jobs:
        jid = job['job_id']
        receipt_path = folder / 'attempts' / (jid + '.json')
        started_path = folder / 'started' / (jid + '.json')
        if receipt_path.exists():
            record = read(receipt_path)
            if record['job_id'] != jid or record['attempt'] != job['attempt']:
                raise RuntimeError('STOP-5 ATTEMPT_MEMBERSHIP_MISMATCH')
            if identity_alive(record):
                terminate_owned(record)
            for child in record.get('process_tree', []):
                terminate_owned(child)
            if record['status'] == 'COMPLETE':
                result = REPO / record['result_path']
                if not result.is_file() or sha(result) != record.get('result_sha256'):
                    raise RuntimeError('STOP-5 COMPLETED_RESULT_HASH_MISMATCH')
                completed.append(jid)
            elif record['status'] == 'INTERRUPTED_UNKNOWN':
                resume.append(dict(job))
            rows.append(dict(job_id=jid, action='PRESERVE_TERMINAL_RECEIPT', receipt_sha256=sha(receipt_path),
                status=record['status'], wall_seconds=record['wall_seconds'], cpu_seconds=record.get('cpu_seconds', 0)))
            continue
        if started_path.exists():
            started = read(started_path)
            snapshot = snapshots.get(jid, {})
            terminate_owned(started)
            for child in snapshot.get('process_tree', []):
                terminate_owned(child)
            if identity_alive(started) or any(identity_alive(c) for c in snapshot.get('process_tree', [])):
                raise RuntimeError('STOP-5 INTERRUPTED_WORKER_REMAINS')
            result = REPO / job['result_path']
            boundary = progress.get('utc', launch.get('utc', started['started_utc']))
            elapsed = max(0, (datetime.fromisoformat(boundary.replace('Z', '+00:00')) -
                datetime.fromisoformat(started['started_utc'].replace('Z', '+00:00'))).total_seconds())
            wall = max(snapshot.get('elapsed_seconds', 0), elapsed)
            record = dict(started, completed_utc=utc(), status='INTERRUPTED_UNKNOWN', wall_seconds=wall,
                cpu_seconds=snapshot.get('cpu_seconds', 0), process_tree=snapshot.get('process_tree', []),
                result_path=job['result_path'], result_sha256=sha(result) if result.is_file() else None,
                exit_code=None, reason='Owner lost before durable terminal receipt',
                cost_scope='Last durable observation; unobserved tail retained as unknown')
            write(receipt_path, record)
            rows.append(dict(job_id=jid, action='INTERRUPTED_UNKNOWN', receipt_sha256=sha(receipt_path),
                wall_seconds=wall, cpu_seconds=record['cpu_seconds']))
        else:
            rows.append(dict(job_id=jid, action='PENDING_NEVER_STARTED', wall_seconds=0, cpu_seconds=0))
        resume.append(dict(job))
    for worker in progress.get('workers', []):
        if worker['job_id'] not in known:
            raise RuntimeError('STOP-5 UNKNOWN_ACTIVE_WORKER')
    recovered_path = ROOT / 'manifests' / ('recovery_' + phase + '.json')
    resume_path = ROOT / 'manifests' / ('recovery_' + phase + '_jobs.json')
    write(resume_path, resume)
    queue_hours = float(progress.get('queue_hours', 0))
    closure_path = folder / 'closure.json'
    if not closure_path.exists():
        write(closure_path, dict(utc=utc(), phase=phase, owner=owner, status='CLOSED', recovery=True,
            queue_hours=queue_hours, completed=len(jobs)-sum(r['action']=='PENDING_NEVER_STARTED' for r in rows),
            pending=sum(r['action']=='PENDING_NEVER_STARTED' for r in rows),
            unknowns=sum(r.get('status',r['action']) in ('TIMEOUT','OPERATIONAL_UNKNOWN','INTERRUPTED_UNKNOWN') for r in rows),
            total=len(jobs), all_owned_workers_closed=True, source_hashes_unchanged=True,
            source_hashes=sources, jobs_sha256=launch['jobs_sha256'],
            cost_scope='Durable observations only; owner-loss interval may have an unobserved tail'))
    ledger_path = ROOT / 'manifests/resource_ledger.json'
    ledger = read(ledger_path) if ledger_path.exists() else dict(intervals=[], new_queue_hours=0)
    if not any(item['phase'] == phase for item in ledger.get('intervals', [])):
        ledger.setdefault('intervals', []).append(dict(phase=phase, start=owner.get('started_utc'),
            end=read(closure_path)['utc'], hours=queue_hours, recovery=True, unobserved_tail_unknown=True))
        ledger['new_queue_hours'] = float(ledger.get('new_queue_hours', ledger.get('scientific_queue_hours', 0))) + queue_hours
        ledger['scientific_queue_hours'] = ledger['new_queue_hours']
        write(ledger_path, ledger, replace=True)
    result = dict(utc=utc(), phase=phase, status='RECONCILED', original_launch_sha256=sha(folder / 'launch.json'),
        rows=rows, completed_predictions_retained=completed, resume_jobs=len(resume),
        resume_manifest=resume_path.relative_to(REPO).as_posix(), resume_sha256=sha(resume_path),
        all_owned_workers_closed=True, all_old_attempt_costs_retained=True, source_hashes_unchanged=True,
        scientific_source_config_or_input_changed=False, aggregate_efficacy_inspected=False,
        unobserved_owner_loss_tail_unknown=True)
    write(recovered_path, result)
    if owner_path.exists() and read(owner_path) == owner:
        owner_path.unlink()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(); parser.add_argument('phase')
    args = parser.parse_args(argv)
    print(json.dumps(reconcile(args.phase)), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
