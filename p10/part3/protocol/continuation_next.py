"""Mechanical continuation after the user-frozen all-436 allocation."""
from common import REPO,ROOT,read,write,sha,utc
from registration_execution_v3 import verify
import json,shutil,traceback


def launch_result(plan):
    jobs=plan['jobs'] if 'jobs' in plan else f'p10/part3/manifests/{plan["phase"]}_jobs.json'
    count=plan.get('jobs_count',plan.get('new_jobs'))
    remaining=31.98-read(ROOT/'manifests/resource_ledger.json')['new_queue_hours']
    if plan['forecast_minutes']/60>remaining:raise RuntimeError('BUDGET_FORECAST_EXCEEDS_REMAINING: apply registered resource and Part I rules without inventing a smaller allocation')
    if sha(REPO/jobs)!=plan['jobs_sha256']:raise RuntimeError('Frozen next-phase job manifest changed')
    return dict(utc=utc(),action='LAUNCH_REGISTERED_PHASE',phase=plan['phase'],jobs=jobs,jobs_count=count,
                workers=plan['workers'],deadline_seconds=plan['deadline_seconds'],forecast_minutes=plan['forecast_minutes'],
                controller='p10/part3/protocol/controller_v3.py',remaining_new_hours=remaining)


def main():
    verify(require_launch_seal=True)
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Owner is still present')
    phase=read(ROOT/'progress.json')['phase'];closure=read(ROOT/f'results/controllers/{phase}/closure.json')
    if closure['status']!='CLOSED' or not closure['all_owned_workers_closed'] or not closure['source_hashes_unchanged']:raise RuntimeError('INTEGRITY_OR_PHASE_FAILURE: closed phase verification failed')
    if shutil.disk_usage(REPO).free<28000000000:raise RuntimeError('STORAGE_ACTION_REQUIRED: within 3 GB of the floor; use registered storage policy')
    if phase=='search_survey_p10':
        from lock_predictions import lock
        lock('survey_p10')
        result=launch_result(read(ROOT/'manifests/search_survey_p8_preflight.json'))
    elif phase=='search_survey_p8':
        from lock_predictions import lock,both_locked
        lock('survey_p8');both_locked()
        from full_funnel_plan import prepare_A
        result=launch_result(prepare_A())
    elif phase in ('funnel_A','funnel_S'):
        from full_funnel_plan import prepare_stage
        result=launch_result(prepare_stage('S' if phase=='funnel_A' else 'B'))
    elif phase=='funnel_B':
        from full_funnel_plan import freeze_C_cap
        from lock_predictions import both_locked
        cap=freeze_C_cap();both_locked()
        result=dict(utc=utc(),action='PREPARE_REGISTERED_PART_F',C_cap=cap['N_C'],max_runnable_C=cap['max_runnable'],
                    instruction='Continue Part F matching/forced fits, then bounded C and H under the registered protocol and user supervision amendment. Implement remaining isolated handlers between closed phases if needed. Do not request another main-session allocation or N_C/H review. Never execute p10.1.',
                    prediction_locks_verified=True,registration_sha256=sha(ROOT/'manifests/registration_execution_v3.json'))
    else:
        result=dict(utc=utc(),action='CONTINUE_REGISTERED_SEQUENCE',closed_phase=phase,
                    instruction='Continue the next registered Part F/C/H/final-delivery operation under supervision_policy_v3.json. Only Part I stop, integrity failure or final delivery pauses; p10.1 is costed only.')
    path=ROOT/f'results/transition_after_{phase}.json'
    if not path.exists():write(path,result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        p=ROOT/'results/continuation_failure.json'
        if not p.exists():write(p,dict(utc=utc(),error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc()))
        raise
