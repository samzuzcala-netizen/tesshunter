"""Bounded P12 supervision, copied from checkin.py; no per-case science reads."""
from p12_common import REPO, ROOT, DATA, read, write, utc, append_jsonl
from controller_p12 import identity_alive, terminate_owned
import json
import shutil
import psutil


def _tail(path):
    if not path.exists():
        return []
    with path.open('rb') as stream:
        stream.seek(0, 2)
        end = stream.tell()
        # Bounded even when a scientific library emitted an enormous line.
        stream.seek(max(0, end - 262144))
        return stream.read(262144).decode('utf-8', 'replace').splitlines()[-50:]


def _sample_cpu(worker):
    if not identity_alive(worker):
        return None
    cpu = 0
    try:
        proc = psutil.Process(worker['pid'])
        for item in [proc] + proc.children(recursive=True):
            try:
                cpu += sum(item.cpu_times()[:2])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None
    return cpu


def checkin():
    current_path = ROOT / 'progress.json'
    current = read(current_path) if current_path.exists() else {}
    phase = current.get('phase', 'IDLE')
    previous_path = ROOT / 'logs/last_checkin.json'
    previous = read(previous_path) if previous_path.exists() else {}
    configuration = read(ROOT / 'protocol/config.json')
    owner_path = ROOT / 'manifests/controller_owner.json'
    owner = read(owner_path) if owner_path.exists() else current.get('owner')
    alive = bool(owner and identity_alive(owner))
    closure_path = ROOT / 'results/controllers' / phase / 'closure.json'
    closure = read(closure_path) if closure_path.exists() else None
    old_workers = {(w['pid'], w['create_time']): w for w in previous.get('workers', [])}
    workers, stalled, killed, events = [], [], [], []
    for original in current.get('workers', []):
        worker = dict(original)
        cpu = _sample_cpu(worker)
        if cpu is None:
            worker['observed_alive'] = False
        else:
            worker.update(cpu_seconds=cpu, observed_alive=True)
            prior = old_workers.get((worker['pid'], worker['create_time']))
            if prior and cpu <= prior['cpu_seconds']:
                stalled.append(worker['job_id'])
                worker['stalled_consecutive_checks'] = prior.get('stalled_consecutive_checks', 0) + 1
                if worker['stalled_consecutive_checks'] == 1:
                    terminate_owned(worker)
                    killed.append(dict(job_id=worker['job_id'], pid=worker['pid'],
                        create_time=worker['create_time'], command=worker['command'], reason='CPU_NOT_ADVANCING'))
            else:
                worker['stalled_consecutive_checks'] = 0
        workers.append(worker)
    disks = {'C': shutil.disk_usage(REPO).free, 'D': shutil.disk_usage(DATA.resolve()).free}
    if (ROOT / 'manifests/USER_STOP').exists():
        events.append('STOP-4 USER_STOP')
    if (ROOT / 'results/active_integrity_failure.json').exists():
        events.append('STOP-1 INTEGRITY_FAILURE')
    if current and not alive and not closure:
        events.append('OWNER_GONE_WITHOUT_CLOSURE')
    if any(w.get('stalled_consecutive_checks', 0) >= 2 for w in workers):
        events.append('WORKER_STALLED_TWO_CHECKS')
    if disks['C'] < configuration['budget']['c_free_floor_bytes'] + 1_000_000_000 or disks['D'] < configuration['budget']['d_free_floor_bytes']:
        events.append('STOP-2 STORAGE_FLOOR')
    elif disks['C'] < configuration['budget']['c_free_floor_bytes'] + 3_000_000_000 or disks['D'] < configuration['budget']['d_free_floor_bytes'] + 3_000_000_000:
        events.append('STORAGE_WITHIN_3GB')
    forecast_path = ROOT / 'manifests/forecast_p12.json'
    if forecast_path.exists():
        estimate = read(forecast_path).get('phases', {}).get(phase, {}).get('with_margin_queue_hours')
        if estimate and current.get('queue_hours', 0) > 2 * estimate and not (ROOT / 'manifests' / ('CONTINUE_' + phase)).exists():
            events.append('STOP-6 PHASE_OVERRUN')
    if closure:
        if not closure.get('source_hashes_unchanged', False):
            events.append('STOP-1 SOURCE_HASH_CHANGED')
        elif closure.get('status') != 'CLOSED' or not closure.get('all_owned_workers_closed'):
            events.append(closure.get('error') or 'PHASE_NOT_CLOSED')
        elif closure.get('retry_of') and not phase.endswith(('_C_retry', '_C')):
            # The 5% of STOP-7 is of the phase's jobs: the original manifest, not the retry pass.
            original_path = ROOT / 'results/controllers' / closure['retry_of'] / 'closure.json'
            original = read(original_path) if original_path.exists() else closure
            if closure.get('unknowns', 0) / max(original.get('total', original.get('completed', 0)), 1) > .05:
                events.append('STOP-7 BROKEN_PHASE')
    if events:
        action = 'PAUSE ' + events[0]
    elif closure:
        if phase == 'pilot_A':
            action = 'PAUSE decision_point_1'
        elif phase == 'commit_part_6':
            action = 'PAUSE decision_point_3'
        elif owner_path.exists():
            action = 'PAUSE OWNER_RECEIPT_STILL_PRESENT'
        else:
            action = 'ADVANCE ' + phase
    elif alive:
        action = 'SLEEP'
    else:
        action = 'PAUSE NO_ACTIVE_PHASE'
    result = dict(current, phase=phase, workers=workers, checkin_utc=utc(), owner_alive=alive,
        closure_receipt_exists=bool(closure), observed_free_bytes=disks, stalled_job_ids=stalled,
        workers_stopped=killed, triggers=events, action=action,
        last_50_controller_lines=_tail(ROOT / 'logs' / ('controller_' + phase + '.log')),
        per_case_science_opened=False, engineering_time=True)
    append_jsonl(ROOT / 'logs/checkins.jsonl', result)
    write(previous_path, result, replace=True)
    with (REPO / 'RESUME_P12.md').open('a', encoding='utf-8') as stream:
        stream.write(f"\n{result['checkin_utc']} [M]: {phase}; {action}; completed {current.get('completed', 0)}, pending {current.get('pending', 0)}, unknowns {current.get('unknowns', 0)}; C free {disks['C']} bytes, D free {disks['D']} bytes.\n")
    return action


def main(argv=None):
    print(checkin(), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
