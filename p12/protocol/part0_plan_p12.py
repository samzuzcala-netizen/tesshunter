"""Mechanical Part 0 job preparation; no scientific result is displayed."""
from p12_common import REPO,ROOT,read,write,sha

def source_snapshot():
    files=[p for directory in (ROOT/'protocol',REPO/'src/tesshunter') for p in directory.glob('*.py')]
    files += [ROOT/'protocol/config.json',ROOT/'protocol/launch_detached_p12.ps1']
    return {p.relative_to(REPO).as_posix():sha(p) for p in files}

def prepare_controller(plan):
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Owner remains')
    phase=plan['name']
    if phase in ('sector_probe','ttt_fetch'):
        result='sector_probe.json' if phase=='sector_probe' else 'ttt_fetch.json'
        rows=[dict(job_id=phase,attempt=1,arguments=[plan['script']],
            result_path='p12/manifests/'+result,source_hashes=source_snapshot())]
        write(REPO/plan['jobs'],rows)
        return rows
    if phase=='pilot_search':
        from pilot_plan_p12 import prepare_search
        return prepare_search()
    raise RuntimeError('OPEN: no registered Part 0 builder for '+phase)
