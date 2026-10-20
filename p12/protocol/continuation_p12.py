"""Mechanical P12 continuation, copied from continuation_next.py.

Only registered, implemented phases are executable. Missing decisions or
modules remain explicit pauses, never inferred scientific choices.
"""
from p12_common import REPO, ROOT, PY, read, write, sha, utc, environment
from guards_p12 import verify_freeze, assert_no_integrity_failure
import argparse
import json
import os
from pathlib import Path
import subprocess
import psutil
import shutil


def _field(value, field):
    for key in field.split('.'):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def _condition(condition, decisions):
    path = condition['path']
    if path not in decisions:
        return None
    actual = _field(decisions[path], condition['field'])
    if actual is None:
        return None
    return actual in condition['in'] if 'in' in condition else actual == condition['equals']


def next_phase(sequence, current, decisions):
    phases = sequence['phases'] if isinstance(sequence, dict) else sequence
    names = [p['name'] for p in phases]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate phase name')
    if current is not None and current not in names:
        raise ValueError('Current phase absent from registered sequence')
    start = names.index(current) + 1 if current is not None else 0
    skipped = []
    for index in range(start, len(phases)):
        phase = phases[index]
        if any(dep not in names[:index] for dep in phase.get('depends_on', [])):
            raise ValueError('Dependency does not precede phase: ' + phase['name'])
        condition = phase.get('condition')
        answer = _condition(condition, decisions) if condition else True
        if answer is None:
            return dict(action='PAUSE', reason='DECISION_MISSING ' + condition['path'], phase=phase['name'])
        if answer is False:
            skipped.append(phase['name'])
            continue
        if phase['kind'] == 'decision':
            if phase.get('path') and phase['path'] in decisions:
                condition = {k: phase[k] for k in ('path', 'field', 'in', 'equals') if k in phase}
                if _condition(condition, decisions):
                    skipped.append(phase['name'])
                    continue
            return dict(action='PAUSE', reason=phase['name'], phase=phase['name'], skipped=skipped)
        return dict(action='EXECUTE', phase=phase['name'], plan=phase, skipped=skipped)
    return dict(action='PAUSE', reason='decision_point_3', phase=None, skipped=skipped)


def _decisions(sequence):
    paths = set()
    for phase in sequence['phases']:
        if phase.get('condition'):
            paths.add(phase['condition']['path'])
        if phase['kind'] == 'decision' and phase.get('path'):
            paths.add(phase['path'])
    return {name: read(REPO / name) for name in paths if (REPO / name).is_file()}


def _preflight(plan):
    from controller_p12 import _storage, _validate_jobs, _other_python
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Owner remains present')
    assert_no_integrity_failure(ROOT)
    _storage(read(ROOT / 'protocol/config.json'))
    if _other_python():
        raise RuntimeError('Other Python process prevents launch')
    verify_freeze(plan['name'])
    if plan['name'] == 'registration' and not (ROOT / 'PREREGISTRATION_P12.md').is_file():
        raise RuntimeError('OPEN: preregistration not yet written; registration waits for it')
    if plan['part'] > 0 and plan['name'] != 'registration':
        from register_p12 import verify
        verify()
    if plan['kind'] == 'controller':
        jobs = ROOT / 'manifests' / (plan['name'] + '_jobs.json') if not plan.get('jobs') else REPO / plan['jobs']
        if not jobs.is_file() and not plan.get('retry_of'):
            raise RuntimeError('OPEN: registered jobs manifest not implemented')
        if jobs.is_file():
            _validate_jobs(read(jobs))
    elif plan['kind'] in ('evaluator', 'gate'):
        script = REPO / plan.get('script', '')
        if not plan.get('script') or not script.is_file():
            raise RuntimeError('OPEN: registered action not implemented: ' + plan['name'])
        if not script.resolve().is_relative_to((ROOT / 'protocol').resolve()):
            raise RuntimeError('Action script outside P12 protocol')


def _native_shell():
    """PowerShell 7 when present; otherwise Windows PowerShell 5.1 with its default module
    path (the 2026-09-23 startup failure was an inherited PowerShell 7 module path, not 5.1)."""
    env = environment()
    shell = shutil.which('pwsh')
    if shell:
        return shell, env
    windows = Path(os.environ.get('SystemRoot', r'C:\WINDOWS')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    if not windows.is_file():
        raise RuntimeError('No PowerShell runtime for detached launch')
    env = dict(env)
    env.pop('PSModulePath', None)
    probe = subprocess.run([str(windows), '-NoProfile', '-Command', 'Get-Command Get-FileHash,Get-CimInstance | Out-Null'],
                           env=env, capture_output=True, text=True, timeout=120)
    if probe.returncode != 0:
        raise RuntimeError('Windows PowerShell lacks the launcher cmdlets')
    return str(windows), env


def _launch(plan):
    _preflight(plan)
    phase = plan['name']
    jobs = plan.get('jobs', 'p12/manifests/' + phase + '_jobs.json')
    args = [str(PY), 'p12/protocol/controller_p12.py', '--phase', phase, '--jobs', jobs,
            '--workers', str(plan['workers']), '--deadline', str(plan['deadline_s'])]
    if plan.get('retry_of'):
        args += ['--retry-of', plan['retry_of']]
    command = subprocess.list2cmdline(args)
    if any(x in command for x in ('\n', '\r', '%', '&', '|', '<', '>')):
        raise ValueError('Unsafe CMD launcher argument')
    launcher = ROOT / 'work' / (phase + '_launch.cmd')
    launcher.parent.mkdir(parents=True, exist_ok=True)
    log = ROOT / 'logs' / ('controller_' + phase + '.log')
    body = '@echo off\ncd /d "' + str(REPO) + '"\n' + command + ' > "' + str(log) + '" 2>&1\nif %errorlevel% neq 0 exit /b %errorlevel%\n'
    with launcher.open('x', encoding='utf-8', newline='\r\n') as stream:
        stream.write(body)
    native = ROOT / 'protocol/launch_detached_p12.ps1'
    if not native.is_file():
        raise RuntimeError('Native detached launcher missing')
    from controller_p12 import identity
    me = psutil.Process()
    blockers = [identity(p) for p in [me] + me.parents() if p.name().lower().startswith('python')]
    receipt = dict(utc=utc(), phase=phase, repo=str(REPO), blockers=blockers,
        launcher=launcher.relative_to(REPO).as_posix(),
        launcher_sha256=sha(launcher), jobs=jobs, jobs_sha256=sha(REPO / jobs) if (REPO / jobs).exists() else None,
        command=args, hidden=True, early_check_minutes=10,
        interval_minutes=60, early_check_pending=True, scheduling_action='Use registered scheduling facility; no polling')
    native_plan = ROOT / 'manifests' / (phase + '_native_launch.json')
    write(native_plan, receipt)
    with (ROOT / 'logs' / ('native_launcher_' + phase + '.log')).open('x', encoding='utf-8') as stream:
        shell, env = _native_shell()
        launched = subprocess.Popen([shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(native), '-PlanPath', str(native_plan)],
            cwd=REPO, env=env, stdout=stream, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
    receipt['native_launcher_pid'] = launched.pid
    receipt['native_shell'] = shell
    receipt['controller_start_waits_for_caller_exit'] = True
    with (REPO / 'RESUME_P12.md').open('a', encoding='utf-8') as stream:
        stream.write('\n' + utc() + ' [M]: running ' + phase + '; run checkin_p12.py first at the registered check time.\n')
    return receipt


def _commit(plan):
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Commit refused while owner present')
    base = ['git', '-c', 'maintenance.auto=false', '-c', 'gc.auto=0', '-c', 'gc.autoDetach=false', '-c', 'core.autocrlf=false']
    paths = ['p12', 'HANDOFF_P12.md', 'RESUME_P12.md']
    paths += [p for p in ('docs/AUDIT_P12.md', 'docs/packets/audit_p12') if (REPO / p).exists()]
    for attempt in range(2):
        added = subprocess.run(base + ['add', '--', *paths], cwd=REPO, capture_output=True, text=True)
        if added.returncode == 0:
            break
    added.check_returncode()
    subprocess.run(base + ['add', '--renormalize', '--', *paths], cwd=REPO, check=True, capture_output=True, text=True)
    subprocess.run(base + ['commit', '-m', plan['message']], cwd=REPO, check=True, capture_output=True, text=True)


def _broken_after_retry(phase, closure):
    """STOP-7: more than 5% operational unknowns after the one recorded retry pass,
    outside Stage C (whose timeouts become UNRESOLVED by rule)."""
    if not closure.get('retry_of') or phase.endswith(('_C', '_C_retry')):
        return False
    original = read(ROOT / 'results/controllers' / closure['retry_of'] / 'closure.json')
    total = max(original.get('total', 0), 1)
    return closure.get('unknowns', 0) / total > .05


def _run_planner(plan):
    """A registered planner writes a later-part jobs manifest from closed receipts."""
    planner = plan.get('planner')
    if not planner:
        raise RuntimeError('OPEN: registered jobs manifest not implemented: ' + plan['name'])
    script = REPO / planner['script']
    if not script.is_file() or not script.resolve().is_relative_to((ROOT / 'protocol').resolve()):
        raise RuntimeError('OPEN: registered planner not implemented: ' + plan['name'])
    subprocess.run([str(PY), planner['script'], *planner.get('args', [])], cwd=REPO,
                   env=environment(), timeout=planner.get('deadline_s', 3600), check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(); parser.add_argument('--launch', action='store_true')
    args = parser.parse_args(argv)
    current = read(ROOT / 'progress.json')['phase']
    closure = read(ROOT / 'results/controllers' / current / 'closure.json')
    if closure['status'] != 'CLOSED' or not closure['all_owned_workers_closed'] or not closure['source_hashes_unchanged']:
        raise RuntimeError('INTEGRITY_OR_PHASE_FAILURE')
    if closure.get('pending', 0) or closure.get('recovery'):
        raise RuntimeError('INCOMPLETE_PHASE_REQUIRES_RECONCILIATION')
    # Operational unknowns stay in every denominator; the registered retry phase
    # follows its primary. After the retry pass more than 5% is STOP-7.
    if _broken_after_retry(current, closure):
        print(json.dumps(dict(action='PAUSE', reason='STOP-7 BROKEN_PHASE ' + current, phase=current)), flush=True)
        return 0
    sequence = read(ROOT / 'manifests/phase_sequence.json')
    while True:
        result = next_phase(sequence, current, _decisions(sequence))
        if not args.launch or result['action'] == 'PAUSE':
            print(json.dumps(result), flush=True)
            return 0
        plan = result['plan']
        transition_path = ROOT / 'results' / ('transition_after_' + current + '.json')
        if transition_path.exists():
            old = read(transition_path)
            if old.get('status') == 'COMPLETE' and old.get('plan') == plan:
                for name, digest in old.get('source_hashes', {}).items():
                    if sha(REPO / name) != digest:
                        raise RuntimeError('Completed transition source changed')
                current = plan['name']
                continue
            raise RuntimeError('Existing transition cannot be safely repeated')
        try:
            if plan['kind'] == 'controller':
                jobs_path = REPO / plan.get('jobs', 'p12/manifests/' + plan['name'] + '_jobs.json')
                if not jobs_path.exists() and plan['part'] == 0:
                    from part0_plan_p12 import prepare_controller
                    prepare_controller(plan)
                elif not jobs_path.exists() and not plan.get('retry_of'):
                    _run_planner(plan)
            _preflight(plan)
        except RuntimeError as exc:
            if str(exc).startswith('OPEN:'):
                print(json.dumps(dict(action='PAUSE', reason=str(exc), phase=plan['name'])), flush=True)
                return 0
            raise
        if plan['kind'] == 'controller':
            receipt = _launch(plan)
            write(ROOT / 'results' / ('transition_after_' + current + '.json'), dict(result, utc=utc(), launch=receipt))
            print(json.dumps(result), flush=True)
            return 0
        if plan['kind'] == 'commit':
            _commit(plan)
        else:
            subprocess.run([str(PY), plan['script'], *plan.get('args', [])], cwd=REPO,
                env=environment(), timeout=plan.get('deadline_s', 3600), check=True)
        source_hashes = {plan['script']: sha(REPO / plan['script'])} if plan.get('script') else {}
        write(transition_path, dict(result, utc=utc(), status='COMPLETE', source_hashes=source_hashes))
        current = plan['name']


if __name__ == '__main__':
    raise SystemExit(main())
