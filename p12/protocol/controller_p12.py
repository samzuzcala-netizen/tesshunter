"""P12 owning controller, copied from controller_v4.py with isolated receipts.

Payloads remain top-level subprocesses. The controller's event loop enforces
deadlines; the session supervises only with the registered check-in routine.
"""
from p12_common import REPO, ROOT, DATA, environment, read, write, sha, utc
from guards_p12 import assert_no_integrity_failure, verify_freeze, require_hash
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import traceback
import psutil


def safe_write(path, value, replace=False):
    return write(path, value, replace=replace)


def identity(process):
    return dict(pid=process.pid, create_time=process.create_time(), command=process.cmdline())


def identity_alive(row):
    try:
        proc = psutil.Process(row['pid'])
        return abs(proc.create_time() - row['create_time']) < .01 and proc.cmdline() == row['command']
    except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
        return False


def terminate_owned(row):
    if not identity_alive(row):
        return
    process = psutil.Process(row['pid'])
    children = []
    try:
        children = [(child, identity(child)) for child in process.children(recursive=True)]
    except psutil.NoSuchProcess:
        return
    for child, child_id in reversed(children):
        if identity_alive(child_id):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
    if identity_alive(row):
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs([p for p, _ in children] + [process], timeout=5)


def _other_python():
    me = psutil.Process()
    allowed = {me.pid}
    command = me.cmdline()
    for parent in me.parents():
        try:
            if parent.cmdline()[1:] == command[1:]:
                allowed.add(parent.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    result = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.pid not in allowed and (proc.info['name'] or '').lower().startswith('python'):
                result.append(identity(proc))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return result


def _storage(configuration):
    c_free = shutil.disk_usage(REPO).free
    d_free = shutil.disk_usage(DATA.resolve()).free
    if c_free < configuration['budget']['c_free_floor_bytes'] + 1_000_000_000:
        raise RuntimeError('STOP-2 STORAGE_C_BELOW_FLOOR_PLUS_1GB')
    if d_free < configuration['budget']['d_free_floor_bytes']:
        raise RuntimeError('STOP-2 STORAGE_D_BELOW_FLOOR')
    return c_free, d_free


def _apply_allocation():
    me = psutil.Process()
    cpus = [0, 2, 4, 6, 8, 10, 12, 14] + list(range(16, 32)) if psutil.cpu_count() == 32 else me.cpu_affinity()[:24]
    spec = importlib.util.spec_from_file_location('p12_cpu_allocation', REPO / 'p11/p11_5/protocol/cpu_allocation.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cpus, module.apply_current(cpus)


def _valid_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value):
        raise ValueError('Invalid phase/job identifier')
    return value


def _registration(phase):
    sequence_path = ROOT / 'manifests/phase_sequence.json'
    if not sequence_path.exists():
        return None
    plans = [row for row in read(sequence_path)['phases'] if row['name'] == phase]
    if not plans:
        raise RuntimeError('Phase absent from registered sequence')
    if plans[0]['part'] > 0:
        from register_p12 import verify
        return verify()
    return None


def _hashes(mapping):
    if not isinstance(mapping, dict) or not mapping:
        raise RuntimeError('Frozen source_hashes must be nonempty')
    for name, expected in mapping.items():
        path = REPO / name
        digest = expected.get('sha256') if isinstance(expected, dict) else expected
        if not path.resolve().is_relative_to(REPO.resolve()) or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise RuntimeError('Invalid frozen source identity')
        require_hash(path, digest, 'Worker or import')


def _validate_jobs(jobs):
    if not isinstance(jobs, list) or len({j['job_id'] for j in jobs}) != len(jobs):
        raise RuntimeError('Invalid or duplicated frozen jobs')
    for job in jobs:
        _valid_name(job['job_id'])
        if job.get('attempt') not in (1, 2):
            raise RuntimeError('Attempt must be 1 or 2')
        args = job.get('arguments')
        if not isinstance(args, list) or not args or not all(isinstance(a, str) for a in args):
            raise RuntimeError('Worker arguments must include a script')
        script = REPO / args[0]
        if not script.is_file() or not script.resolve().is_relative_to((ROOT).resolve()):
            raise RuntimeError('P12 worker script must be isolated under p12')
        _hashes(job.get('source_hashes'))
        if script.relative_to(REPO).as_posix() not in job['source_hashes']:
            raise RuntimeError('Worker script is not pinned in source_hashes')
        result = REPO / job['result_path']
        if not any(result.resolve().is_relative_to(root.resolve()) for root in (ROOT, DATA)):
            raise RuntimeError('Result path outside P12 roots')


def build_retry(phase, retry_of):
    _valid_name(phase); _valid_name(retry_of)
    folder = ROOT / 'results/controllers' / retry_of
    closure = read(folder / 'closure.json')
    if closure['status'] != 'CLOSED' or not closure['all_owned_workers_closed']:
        raise RuntimeError('Retry requires a closed original phase')
    launch = read(folder / 'launch.json')
    original = launch['frozen_jobs']
    rows = []
    for job in original:
        receipt = read(folder / 'attempts' / (job['job_id'] + '.json'))
        if receipt['status'] not in ('TIMEOUT', 'OPERATIONAL_UNKNOWN'):
            continue
        if receipt.get('attempt') != 1:
            raise RuntimeError('Only the one recorded retry pass is permitted')
        retry = dict(job, attempt=2, retry_of=retry_of, original_receipt_sha256=sha(folder / 'attempts' / (job['job_id'] + '.json')))
        # Worker command/result membership remains the original registered job;
        # retry-aware builders may supply an explicit attempt-2 destination.
        if 'retry_arguments' in job:
            retry['arguments'] = job['retry_arguments']
        if 'retry_result_path' in job:
            retry['result_path'] = job['retry_result_path']
        rows.append(retry)
    output = ROOT / 'manifests' / (phase + '_jobs.json')
    write(output, rows)
    write(ROOT / 'manifests' / (phase + '_retry_plan.json'), dict(utc=utc(), retry_of=retry_of, attempt=2,
          original_closure_sha256=sha(folder / 'closure.json'), jobs_sha256=sha(output), jobs=len(rows)))
    return output


def run_phase(phase, jobs, workers, deadline, *, retry_of=None):
    _valid_name(phase)
    configuration = read(ROOT / 'protocol/config.json')
    if not 1 <= workers <= 24 or deadline <= 0:
        raise ValueError('Invalid workers/deadline')
    if phase.endswith(('_C', '_C_retry')) and workers > 3:
        raise ValueError('Stage C permits at most 3 x 8 TLS threads')
    owner_path = ROOT / 'manifests/controller_owner.json'
    if owner_path.exists():
        existing = read(owner_path)
        raise RuntimeError('EXCLUSIVE_OWNER' if identity_alive(existing) else 'STOP-5 RECYCLED_OR_LOST_OWNER')
    assert_no_integrity_failure(ROOT)
    freeze = verify_freeze(phase)
    registration = _registration(phase)
    _storage(configuration)
    others = _other_python()
    if others:
        raise RuntimeError('Other Python processes exist; preflight refused')
    if retry_of:
        jobs = build_retry(phase, retry_of)
    jobs_path = Path(jobs) if isinstance(jobs, (str, Path)) else None
    if jobs_path is not None:
        jobs_path = jobs_path if jobs_path.is_absolute() else REPO / jobs_path
        if not jobs_path.resolve().is_relative_to((ROOT / 'manifests').resolve()):
            raise RuntimeError('Jobs manifest must be under p12/manifests')
        job_rows = read(jobs_path)
    else:
        jobs_path = ROOT / 'manifests' / (phase + '_jobs.json')
        job_rows = jobs
        write(jobs_path, job_rows)
    _validate_jobs(job_rows)
    cpus, qos = _apply_allocation()
    owner = dict(**identity(psutil.Process()), phase=phase, started_utc=utc(), cpus=cpus, qos=qos)
    out = ROOT / 'results/controllers' / phase
    if out.exists():
        raise FileExistsError('Phase receipts already exist; recover or use a separate retry phase')
    sources = {p.relative_to(REPO).as_posix(): sha(p) for p in (ROOT / 'protocol').glob('*.py')}
    sources[jobs_path.relative_to(REPO).as_posix()] = sha(jobs_path)
    sources[(ROOT / 'protocol/config.json').relative_to(REPO).as_posix()] = sha(ROOT / 'protocol/config.json')
    for job in job_rows:
        sources.update(job['source_hashes'])
    if registration:
        # The effective sealed hashes: the base seal folded with its hash-linked chain additions
        # (a superseded module carries its chain hash, not its base-seal hash).
        from register_p12 import effective, _links
        registration_path = ROOT / 'manifests/registration_seal.json'
        effective_hashes, _, _, _ = effective()
        sources.update(effective_hashes)
        sources[registration_path.relative_to(REPO).as_posix()] = sha(registration_path)
        for link in _links():
            sources[link.relative_to(REPO).as_posix()] = sha(link)
    # Exclusive creation is the final operation before owning the phase.
    write(owner_path, owner)
    start = time.monotonic()
    active, completed, pending = {}, [], list(job_rows)
    status, error = 'RUNNING', None
    ledger_path = ROOT / 'manifests/resource_ledger.json'
    ledger = read(ledger_path) if ledger_path.exists() else {'intervals': [], 'new_queue_hours': 0}
    prior = float(ledger.get('new_queue_hours', ledger.get('scientific_queue_hours', 0)))
    out.mkdir(parents=True)
    write(out / 'launch.json', dict(utc=utc(), owner=owner, jobs=len(job_rows), frozen_jobs=job_rows,
          jobs_path=jobs_path.relative_to(REPO).as_posix(), jobs_sha256=sha(jobs_path), workers=workers,
          deadline=deadline, deadline_s=deadline, source_hashes=sources, freeze_verification=freeze,
          registration_verification=registration, retry_of=retry_of))

    def sample(row):
        tree = row.setdefault('tree', {})
        if identity_alive(row):
            try:
                proc = psutil.Process(row['pid'])
                for child in [proc] + proc.children(recursive=True):
                    try:
                        ident = identity(child)
                        key = (ident['pid'], ident['create_time'])
                        tree[key] = dict(**ident, cpu_seconds=sum(child.cpu_times()[:2]))
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except psutil.NoSuchProcess:
                pass
        return sum(p['cpu_seconds'] for p in tree.values())

    def finish(jid, row, outcome, code, reason=None):
        cpu = sample(row)
        terminate_owned(row)
        for child in reversed(list(row.get('tree', {}).values())):
            terminate_owned(child)
        row['handle'].close()
        result = REPO / row['job']['result_path']
        if outcome == 'COMPLETE' and not result.is_file():
            outcome, reason = 'OPERATIONAL_UNKNOWN', 'Worker exited zero without its result'
        record = dict(job_id=jid, started_utc=row['started_utc'], completed_utc=utc(),
            wall_seconds=time.monotonic() - row['timer'], cpu_seconds=cpu, sampled_cpu_seconds=cpu,
            pid=row['pid'], create_time=row['create_time'], command=row['command'], identity={k: row[k] for k in ('pid', 'create_time', 'command')},
            process_tree=list(row.get('tree', {}).values()), exit_code=code, status=outcome,
            attempt=row['job']['attempt'], deadline_s=deadline, result_path=row['job']['result_path'],
            result_sha256=sha(result) if result.is_file() else None, reason=reason)
        write(row['receipt'], record)
        completed.append(record)
        del active[jid]

    def progress():
        c_free, d_free = shutil.disk_usage(REPO).free, shutil.disk_usage(DATA.resolve()).free
        worker_rows = [dict(job_id=jid, **{k: r[k] for k in ('pid', 'create_time', 'command')},
            elapsed_seconds=time.monotonic()-r['timer'], cpu_seconds=sample(r), process_tree=list(r.get('tree', {}).values()))
            for jid, r in active.items()]
        snapshot = dict(utc=utc(), phase=phase, status=status, owner=owner, total=len(job_rows),
            completed=len(completed), pending=len(pending), active=len(active), unknowns=sum(r['status'] != 'COMPLETE' for r in completed),
            workers=worker_rows, c_free_bytes=c_free, d_free_bytes=d_free, queue_hours=(time.monotonic()-start)/3600,
            new_queue_hours=prior+(time.monotonic()-start)/3600, error=error)
        write(out / 'progress.json', snapshot, replace=True)
        write(ROOT / 'progress.json', snapshot, replace=True)

    try:
        while pending or active:
            assert_no_integrity_failure(ROOT)
            verify_freeze(phase)
            _hashes(sources)
            _storage(configuration)
            if (ROOT / 'manifests/USER_STOP').exists():
                raise RuntimeError('STOP-4 USER_STOP')
            forecast_path = ROOT / 'manifests/forecast_p12.json'
            if forecast_path.exists():
                forecast = read(forecast_path).get('phases', {}).get(phase, {})
                limit = forecast.get('with_margin_queue_hours')
                if limit and (time.monotonic()-start)/3600 > 2 * limit and not (ROOT / 'manifests' / ('CONTINUE_' + phase)).exists():
                    raise RuntimeError('STOP-6 PHASE_OVERRUN')
            while pending and len(active) < workers:
                job = pending.pop(0); jid = job['job_id']
                log = out / 'logs' / (jid + '.log'); log.parent.mkdir(parents=True, exist_ok=True)
                handle = log.open('x', encoding='utf-8')
                command = [sys.executable, *job['arguments']]
                online = any(word in phase for word in ('download', 'catalog', 'probe', 'neighbour', 'ttt_fetch')) or phase.endswith(('_D', '_D_retry'))
                proc = subprocess.Popen(command, cwd=REPO, stdout=handle, stderr=subprocess.STDOUT,
                    env=environment(offline=not online), creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                observed = psutil.Process(proc.pid)
                row = dict(**identity(observed), job=job, proc=proc, handle=handle, timer=time.monotonic(),
                    started_utc=utc(), receipt=out / 'attempts' / (jid + '.json'))
                active[jid] = row
                write(out / 'started' / (jid + '.json'), dict(job_id=jid, **{k: row[k] for k in ('pid','create_time','command','started_utc')},
                    attempt=job['attempt'], deadline_s=deadline, result_path=job['result_path']))
            for jid, row in list(active.items()):
                sample(row)
                code = row['proc'].poll()
                timed_out = code is None and time.monotonic()-row['timer'] >= deadline
                if timed_out:
                    terminate_owned(row); code = row['proc'].wait(timeout=10)
                if code is not None:
                    finish(jid, row, 'TIMEOUT' if timed_out else 'COMPLETE' if code == 0 else 'OPERATIONAL_UNKNOWN', code)
            progress()
            if pending or active:
                time.sleep(configuration.get('supervision', {}).get('progress_seconds', 3))
        status = 'CLOSED'
    except BaseException as exc:
        status, error = 'FAILED', f'{type(exc).__name__}: {exc}'
        for jid, row in list(active.items()):
            finish(jid, row, 'INTERRUPTED_UNKNOWN', None, error)
        write(ROOT / 'manifests' / ('stop_controller_' + phase + '.json'),
            dict(utc=utc(), trigger=error, phase=phase, owner=owner, existing_attempts=len(completed)))
    finally:
        elapsed = time.monotonic()-start
        unchanged = all((REPO / p).is_file() and sha(REPO / p) == (h.get('sha256') if isinstance(h, dict) else h) for p, h in sources.items())
        workers_closed = not active and all(not identity_alive(p) for r in completed for p in r.get('process_tree', []))
        if not unchanged or not workers_closed:
            status, error = 'FAILED', error or 'STOP-1 source changed or owned process remains'
        closure = dict(utc=utc(), phase=phase, owner=owner, status=status, error=error, queue_hours=elapsed/3600,
            completed=len(completed), pending=len(pending), unknowns=sum(r['status'] != 'COMPLETE' for r in completed),
            total=len(job_rows), all_owned_workers_closed=workers_closed, source_hashes_unchanged=unchanged,
            source_hashes=sources, jobs_sha256=sha(jobs_path), retry_of=retry_of)
        write(out / 'closure.json', closure)
        ledger['new_queue_hours'] = prior + elapsed/3600
        ledger['scientific_queue_hours'] = ledger['new_queue_hours']
        ledger.setdefault('intervals', []).append(dict(phase=phase, start=owner['started_utc'], end=closure['utc'], hours=elapsed/3600,
            job_wall_hours=sum(r['wall_seconds'] for r in completed)/3600))
        write(ledger_path, ledger, replace=True)
        progress()
        if owner_path.exists() and read(owner_path) == owner and workers_closed:
            owner_path.unlink()
    return closure


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', required=True); ap.add_argument('--jobs')
    ap.add_argument('--workers', required=True, type=int); ap.add_argument('--deadline', required=True, type=float)
    ap.add_argument('--retry-of')
    args = ap.parse_args(argv)
    result = run_phase(args.phase, args.jobs or ROOT / 'manifests' / (args.phase + '_jobs.json'),
                       args.workers, args.deadline, retry_of=args.retry_of)
    print(json.dumps(result), flush=True)
    return 0 if result['status'] == 'CLOSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
