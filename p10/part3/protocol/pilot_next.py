"""Mechanical closed-phase pilot transitions; allocation always returns to main."""
from common import REPO,ROOT,read,write,sha,utc
from registration_chain import verify
import shutil,subprocess,sys,json


def run(script,log):
    with log.open('x',encoding='utf-8') as stream:
        result=subprocess.run([sys.executable,str(ROOT/'protocol'/script)],cwd=REPO,stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(f'{script} failed; main-session review required (log {log.relative_to(REPO)})')


def main():
    verify()
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('An owner is still present')
    progress=read(ROOT/'progress.json');phase=progress['phase']
    closure=read(ROOT/f'results/controllers/{phase}/closure.json')
    if closure['status']!='CLOSED' or not closure['all_owned_workers_closed'] or not closure['source_hashes_unchanged']:raise RuntimeError('Phase did not close cleanly')
    if shutil.disk_usage(REPO).free<28000000000:raise RuntimeError('Storage preflight needs main-session review')
    if read(ROOT/'manifests/resource_ledger.json')['new_queue_hours']>=31.98:raise RuntimeError('No new scientific budget remains')
    if phase=='timing_pilot_search':
        plan=ROOT/'manifests/timing_pilot_A_jobs.json'
        if not plan.exists():run('prepare_pilot_stage_a.py',ROOT/'logs/timing_pilot_collect.log')
        dispatch=read(ROOT/'results/timing_pilot_A_dispatch.json')
        # This is a registered phase, not a level/allocation decision.
        result=dict(utc=utc(),action='LAUNCH_REGISTERED_PILOT_A',phase='timing_pilot_A',
            jobs='p10/part3/manifests/timing_pilot_A_jobs.json',workers=24,deadline_seconds=1200,
            forecast_minutes=dispatch['forecast_minutes'],jobs_count=dispatch['n_pre_gate'],
            controller='p10/part3/protocol/controller_v2.py',source_sha256=sha(__file__))
    elif phase=='timing_pilot_A':
        path=ROOT/'results/timing_pilot_summary.json'
        if not path.exists():run('summarize_timing_pilot.py',ROOT/'logs/timing_pilot_summary.log')
        result=dict(utc=utc(),action='PAUSE_FOR_MAIN_ALLOCATION_REVIEW',summary=path.relative_to(REPO).as_posix(),
                    meaning='Pilot and A timing are complete; evaluation level and paired P8 allocation have not been selected.',source_sha256=sha(__file__))
    else:raise RuntimeError('No mechanical pilot transition registered for '+phase)
    out=ROOT/f'results/pilot_transition_after_{phase}.json'
    if not out.exists():write(out,result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
