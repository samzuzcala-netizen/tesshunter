"""Correct the Stage A record-schema guard without changing live worker source.

The original controller compared recorded V.THRESHOLDS['stageA'] with the
different rules-summary schema. Both carry the same numerical thresholds.
Its current FA A phase is allowed to finish normally, after which it will
stop at that guard. This successor verifies the complete A population,
preserves its results/timers, and runs only the remaining phases.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import run_part2d_calibration as C

OUT = C.OUT
MANIFEST = OUT / 'calibration_guard_correction.json'
STATE = OUT / 'calibration_checked_state.json'
LOCK = OUT / 'calibration_checked.lock'
C.MARKERS += ('run_part2d_calibration_checked.py',)
_original_check_record = C.check_record


def check_record(path, stage, job, a_decision=None):
    if stage != 'A':
        return _original_check_record(path, stage, job, a_decision)
    import p10_funnel_calibration as F
    import audit_p5 as A
    from tesshunter.survey import get_config
    F.set_rules('p10.0')
    rec = C.read(path)
    key = F.V.kkey(job['tic_id'], job['period'])
    C.require(rec.get('key') == key and rec.get('rank') == job['rank'] and rec.get('tic_id') == job['tic_id'],
              'Candidate identity differs: ' + str(path))
    C.require(rec.get('rules_version') == 'p10.0' and rec.get('survey_preset') == 'survey_p10' and
              rec.get('input_config') == A.input_config_for(get_config('survey_p10')), 'Stale or unnamed record: ' + str(path))
    C.require(rec.get('decision') in ('PASS', 'FAIL'), 'Unsettled Stage A record: ' + str(path))
    C.require(isinstance(rec.get('seconds'), (int,float)) and math.isfinite(rec['seconds']) and rec['seconds'] >= 0,
              'Missing timing: ' + str(path))
    C.require(rec.get('survey') == {k:job[k] for k in ('period','epoch_btjd','duration_days','depth_ppt',
              'stitch_snr','stitch_n_transits','n_units','tmag')}, 'Stage A ephemeris differs: ' + str(path))
    # Compare the record with the exact schema its original writer serializes.
    C.require(rec.get('thresholds') == F.V.THRESHOLDS['stageA'], 'Stage A thresholds differ')
    root = path.parent.parent
    C.require((root/'prep'/(key+'.json')).is_file() and (root/'tls'/(key+'_lc.npz')).is_file(),
              'Missing prepared Stage A artifacts')
    return rec


C.check_record = check_record


def verify():
    m = C.verify_manifest()
    correction = C.read(MANIFEST)
    C.require(correction['original_manifest_sha256'] == C.sha(C.MANIFEST), 'Original calibration manifest changed')
    C.verify_hashes(correction['source_sha256'])
    return m, correction


def register():
    import p10_funnel_calibration as F
    C.require(not MANIFEST.exists() and not STATE.exists() and not LOCK.exists(), 'Correction registration is exclusive')
    m = C.verify_manifest()
    state = C.read(C.STATE); owner = C.read(C.LOCK)
    C.require(state['status'] == 'running' and state['phase'] == 'fa_a', 'Only the original live FA A phase is eligible')
    C.require(owner == state['owner'], 'Original owner identity differs')
    process = C.psutil.Process(owner['pid'])
    C.require(process.create_time() == owner['created_epoch'], 'Original owner PID reused')
    wait_for = [dict(pid=process.pid, created_epoch=process.create_time())]
    for p in process.parents():
        if any('run_part2d_calibration.py' in arg for arg in p.cmdline()):
            wait_for.append(dict(pid=p.pid, created_epoch=p.create_time()))
    F.set_rules('p10.0')
    record_schema = F.V.THRESHOLDS['stageA']
    summary_schema = F.R.thresholds(F.R.P10_RULES)['stageA']
    shared = set(record_schema) & set(summary_schema)
    C.require(all(record_schema[k] == summary_schema[k] for k in shared), 'Numerical thresholds really differ')
    census = C.phase_census('fa_a',m)
    C.require(not census['invalid'], 'Current records fail the corrected full guard')
    correction = dict(utc=C.utc(), original_manifest_sha256=C.sha(C.MANIFEST), original_owner=owner,
        wait_for=wait_for, source_sha256={str(Path(__file__).relative_to(C.REPO)):C.sha(Path(__file__))},
        original_record_schema=record_schema, original_rule_summary_schema=summary_schema,
        shared_fields_equal=sorted(shared), current_validated_census=census,
        change='Only the Stage A validation schema changes from rules-summary metadata to the exact original V.THRESHOLDS record schema. All numerical thresholds, source/input hashes, algorithms and artifacts remain unchanged.',
        continuation='Wait for the original owner and its launcher to close naturally after FA A. Require the anticipated schema-guard stop, validate all 709 A records, preserve their bytes/timers, skip the completed A phase, then execute FA S, injection A/S and analyze.')
    C.save(MANIFEST,correction,exclusive=True)
    C.save(STATE,dict(utc=C.utc(),status='registered_wait_required',correction_sha256=C.sha(MANIFEST)),exclusive=True)
    print(json.dumps(dict(registered=True,validated_A=census['settled'],waiting_for=wait_for),indent=2))


def wait_and_run():
    m, correction = verify()
    C.require(C.read(STATE)['status'] == 'registered_wait_required', 'Successor already started or requires review')
    owner = dict(pid=os.getpid(),created_epoch=C.psutil.Process().create_time(),utc=C.utc(),correction_sha256=C.sha(MANIFEST))
    C.save(LOCK,owner,exclusive=True)
    try:
        C.save(STATE,dict(utc=C.utc(),status='waiting_for_original_fa_a_boundary',owner=owner,wait_for=correction['wait_for']))
        for item in correction['wait_for']:
            try:
                p=C.psutil.Process(item['pid'])
                C.require(p.create_time()==item['created_epoch'], 'Original owner PID identity changed')
                p.wait()
            except C.psutil.NoSuchProcess:
                pass
        C.require_free()
        verify()
        old=C.read(C.STATE)
        C.require(old['status']=='stopped_review_required' and old.get('previous_state',{}).get('phase')=='fa_a'
                  and 'fa_a contains unsettled or invalid records' in old.get('error',''),
                  'Original controller stopped for an unexpected reason; review required')
        old_phase=C.read(OUT/'fa_a_complete.json')
        C.require(old_phase['census']['invalid'] and all("RuntimeError('Stage A thresholds differ')"==r['error']
                  for r in old_phase['census']['invalid']), 'Original guard reported a different failure')
        census=C.phase_census('fa_a',m)
        C.require(census['complete'], 'Cannot skip an incomplete or invalid FA A phase')
        C.save(OUT/'fa_a_checked_complete.json',dict(utc=C.utc(),census=census,original_guard_report='fa_a_complete.json',
               correction_sha256=C.sha(MANIFEST),completed_A_reexecuted=False),exclusive=True)
        shutil.copy2(C.STATE,OUT/'original_schema_guard_stop_state.json')
        for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
            os.environ[name]='1'
        os.environ.update(PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',TESSHUNTER_OFFLINE='1',
                          LIGHTKURVE_CACHE=str(C.REPO/'data/cache/lightkurve'))
        for phase in C.PHASES[1:]:
            if phase=='analyze':
                C.require(all(C.phase_census(p,m)['complete'] for p in C.PHASES[:-1]), 'All A/S must settle before analysis')
            command=C.phase_command(phase)
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            log=OUT/f'{phase}_checked_{stamp}.log'
            with log.open('x',encoding='utf-8') as stream:
                child=subprocess.Popen(command,cwd=str(C.REPO),stdout=stream,stderr=subprocess.STDOUT)
                C.save(STATE,dict(utc=C.utc(),status='running',phase=phase,owner=owner,child_pid=child.pid,
                    child_created_epoch=C.psutil.Process(child.pid).create_time(),command=command,log=str(log.relative_to(C.REPO))))
                code=child.wait()
            C.require(code==0,f'{phase} exited {code}; preserve diagnostics and review')
            if phase!='analyze':
                census=C.phase_census(phase,m)
                C.save(OUT/f'{phase}_checked_complete.json',dict(utc=C.utc(),census=census,log=str(log.relative_to(C.REPO))),exclusive=True)
                C.require(census['complete'],f'{phase} did not settle: {census}')
            print(C.utc(),phase,'COMPLETE',flush=True)
        verify()
        report=C.read(C.CAL/'completeness_p10.json')
        C.require(report['n_injections']==2100 and report['n_jobs_ok']==2100 and report['config']=='survey_p10'
                  and report['rules_version']=='p10.0' and report['false_alarms']['n_stars_ok']==300,'Final calibration census differs')
        C.save(STATE,dict(utc=C.utc(),status='calibration_complete_review_required',phase=None,correction_sha256=C.sha(MANIFEST)))
        print('FULL_CALIBRATION_COMPLETE; side-by-side/yield/Stop Rule 1 review remains',flush=True)
    except BaseException as exc:
        old=C.read(STATE)
        C.save(STATE,dict(utc=C.utc(),status='stopped_review_required',error=repr(exc),previous_state=old))
        raise
    finally:
        LOCK.unlink()


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=('register','wait-run','inspect'))
    command=ap.parse_args().command
    if command=='register':
        register()
    elif command=='wait-run':
        wait_and_run()
    else:
        m,correction=verify()
        report=dict(utc=C.utc(),state=C.read(STATE),lock=C.read(LOCK) if LOCK.exists() else None,
                    original_state=C.read(C.STATE),original_lock=C.read(C.LOCK) if C.LOCK.exists() else None,
                    census={p:C.phase_census(p,m) for p in C.PHASES[:-1]},process_snapshot=C.process_snapshot(),
                    correction_sha256=C.sha(MANIFEST))
        path=OUT/('inspect_checked_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
        C.save(path,report,exclusive=True)
        print(json.dumps(dict(receipt=str(path),state=report['state'],census=report['census'],
              processes=len(report['process_snapshot']['processes']),inaccessible_pids=report['process_snapshot']['inaccessible_pids']),indent=2))


if __name__=='__main__':
    main()
