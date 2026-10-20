"""Fresh supervision shutdown verification, copied from final_shutdown_v1.py.

The app tool pauses the routine; this verifier never rewrites automation TOML.
An ACTIVE routine refuses verification and requires that app action.
"""
from p12_common import REPO, ROOT, read, write, sha, utc
from controller_p12 import identity_alive
from pathlib import Path
import hashlib
import json
import os
import psutil
import tomllib

AUTOMATIONS = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'automations'


def _science_processes():
    me = psutil.Process()
    current = me.cmdline()
    allowed = {me.pid}
    for ancestor in me.parents():
        try:
            if ancestor.cmdline()[1:] == current[1:]:
                allowed.add(ancestor.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    result = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            if proc.pid in allowed or not (proc.info['name'] or '').lower().startswith('python'):
                continue
            args = ' '.join(proc.info['cmdline'] or []).replace('\\', '/').lower()
            if any(marker in args for marker in ('p12/protocol', 'p10/part3/protocol', 'p11/p11_5/protocol', 'p9/runner.py', 'scripts/run_survey.py')):
                result.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return result


def verify_shutdown():
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Owner receipt remains')
    historical = []
    for ident in ('prompt-10-3-hourly-check-in', 'continue-local-p10-execution'):
        path = AUTOMATIONS / ident / 'automation.toml'
        config = tomllib.loads(path.read_text(encoding='utf-8'))
        if config['status'] != 'PAUSED':
            raise RuntimeError('Historical automation must remain PAUSED: ' + ident)
        historical.append(dict(id=ident, status=config['status'], toml_sha256=sha(path)))
    schedule_path = ROOT / 'manifests/checkin_schedule.json'
    schedule = read(schedule_path) if schedule_path.exists() else None
    ident = (schedule or {}).get('id', (schedule or {}).get('automation_id', 'prompt-12-hourly-check-in'))
    routine = AUTOMATIONS / ident / 'automation.toml'
    if routine.exists():
        config = tomllib.loads(routine.read_text(encoding='utf-8'))
        if config.get('status') != 'PAUSED':
            raise RuntimeError('PAUSE ROUTINE_ACTIVE: use app automation_update before shutdown verification')
        digest = hashlib.sha256(config['prompt'].encode()).hexdigest()
        if not schedule or digest != schedule.get('prompt_sha256'):
            raise RuntimeError('Check-in routine prompt SHA changed or schedule missing')
        routine_status = dict(id=ident, configured_status='PAUSED', prompt_sha256=digest, toml_sha256=sha(routine))
    else:
        if schedule and schedule.get('facility') not in (None, 'none', 'NONE'):
            raise RuntimeError('Recorded routine cannot be re-read by id')
        routine_status = dict(id=ident, configured_status='ABSENT_NOT_ARMED', prompt_sha256=None)
    claude = (schedule or {}).get('claude_facility')
    if claude:
        # A Claude session cron lives in the session's memory; the session deletes it and
        # saves the listing read back after the delete, which this verifier re-reads.
        if claude.get('status') != 'DELETED':
            raise RuntimeError('PAUSE ROUTINE_ACTIVE: delete the Claude session check-in before shutdown verification')
        listing_path = REPO / claude.get('listing_after_delete', '')
        if not claude.get('listing_after_delete') or not listing_path.is_file():
            raise RuntimeError('Claude check-in deletion listing missing')
        listing = read(listing_path)
        last_change = max((row.get('utc', '') for row in claude.get('changes', [])), default='')
        if listing.get('utc', '') < last_change or any(str(job.get('id')) == str(claude.get('job_id'))
                                                       for job in listing.get('jobs', [])):
            raise RuntimeError('Claude check-in still listed or listing predates the last change')
        if hashlib.sha256(claude['prompt'].encode()).hexdigest() != claude.get('prompt_sha256'):
            raise RuntimeError('Claude check-in prompt SHA changed')
        routine_status['claude_facility'] = dict(job_id=claude.get('job_id'), configured_status='DELETED',
            prompt_sha256=claude.get('prompt_sha256'), listing_sha256=sha(listing_path),
            firings=len(claude.get('firings', [])))
    closures = []
    for path in (ROOT / 'results/controllers').glob('*/closure.json'):
        closure = read(path)
        if closure['status'] != 'CLOSED' or not closure['all_owned_workers_closed']:
            raise RuntimeError('Controller closure not verified: ' + path.parent.name)
        if identity_alive(closure['owner']):
            raise RuntimeError('Recorded controller identity remains alive')
        for attempt_path in (path.parent / 'attempts').glob('*.json'):
            attempt = read(attempt_path)
            if identity_alive(attempt) or any(identity_alive(item) for item in attempt.get('process_tree', [])):
                raise RuntimeError('Recorded worker identity remains alive')
        closures.append(dict(phase=path.parent.name, closure_sha256=sha(path), pending=closure.get('pending', 0)))
    remaining = _science_processes()
    if remaining:
        raise RuntimeError('Science Python process remains: ' + json.dumps(remaining))
    checkins_path = ROOT / 'logs/checkins.jsonl'
    checks = [json.loads(line) for line in checkins_path.read_text(encoding='utf-8-sig').splitlines() if line.strip()] if checkins_path.exists() else []
    receipt = dict(utc=utc(), status='DISABLED_VERIFIED', routine=routine_status, historical_automations=historical,
        checkin_count=len(checks), first_firing=checks[0]['checkin_utc'] if checks else None,
        last_firing=checks[-1]['checkin_utc'] if checks else None, owner_file_absent=True,
        recorded_controller_identities_dead=True, no_science_python_process=True, closed_phases=closures,
        method='Fresh configuration reread by id after app pause, or verified absent routine; no direct TOML mutation')
    output = ROOT / 'manifests/final_supervision_disabled.json'
    if output.exists():
        receipt['previous_receipt_sha256'] = sha(output)
    write(output, receipt, replace=output.exists())
    return receipt


def main(argv=None):
    print(json.dumps(verify_shutdown()), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
