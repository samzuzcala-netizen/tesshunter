"""Guarded full P10 calibration; original P8/P9 science is read-only.

Prepare once, then run sequential 16-worker FA A, FA S, injection A/S and
the unchanged five-level bootstrap. Analysis closure requires every expected
record to be settled under the frozen named rules and preset. Stop Rule 1
is a subsequent review, never inferred from partial calibration outcomes.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import psutil

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'p10/protocol'), str(REPO / 'scripts'), str(REPO / 'src')]
import run_part2d_injection_search as Q

OUT = REPO / 'p10/results/part2d_calibration_20260912'
CAL = REPO / 'data/survey/p10/part2d/calibration'
MANIFEST = OUT / 'calibration_manifest.json'
STATE = OUT / 'calibration_state.json'
LOCK = OUT / 'calibration.lock'
SEARCH_SEAL = Q.OUT / 'injection_search_closed_seal_20260912.json'
MARKERS = Q.MARKERS + ('run_part2d_calibration.py', 'p10_funnel_calibration.py',
                       'p10_completeness_calibration.py')
PHASES = ('fa_a', 'fa_s', 'injection_as', 'analyze')
sha, read, save, utc = Q.sha, Q.read, Q.save, Q.utc


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def process_snapshot():
    own = {os.getpid(), *(p.pid for p in psutil.Process().parents())}
    found, denied = [], []
    for p in psutil.process_iter():
        try:
            if not p.name().lower().startswith('python') or p.pid in own:
                continue
            cmd = p.cmdline()
            if not cmd:
                denied.append(p.pid)
            elif any(marker in ' '.join(cmd) for marker in MARKERS):
                cpu = p.cpu_times()
                found.append(dict(pid=p.pid, ppid=p.ppid(), created_epoch=p.create_time(),
                                  command=cmd, cpu_user_s=cpu.user, cpu_kernel_s=cpu.system))
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            denied.append(p.pid)
    return dict(utc=utc(), processes=found, inaccessible_pids=denied)


def require_free():
    snap = process_snapshot()
    require(not snap['processes'] and not snap['inaccessible_pids'],
            f'Live computation or incomplete process visibility: {snap}')
    require(not LOCK.exists(), 'Existing calibration lock requires identity review; never remove blindly')
    return snap


def verify_hashes(hashes):
    for name, digest in hashes.items():
        require(sha(REPO / name) == digest, f'Frozen source/input changed: {name}')


def verify_manifest():
    m = read(MANIFEST)
    require(Q.frozen_section_sha() == Q.FROZEN_SHA, 'Frozen section 0 changed')
    verify_hashes(m['source_sha256'])
    verify_hashes(m['input_sha256'])
    return m


def prepare():
    import p10_completeness_calibration as C
    import p10_funnel_calibration as F
    from tesshunter.survey import get_config, stitched_path
    require_free()
    require(not MANIFEST.exists(), 'Preparation is exclusive; do not repeat')
    require(not list(CAL.rglob('stageA/*.json')) and not list(CAL.rglob('secondary/*.json')),
            'Calibration records already exist before preparation')
    require(Q.frozen_section_sha() == Q.FROZEN_SHA, 'Frozen section 0 changed')
    qm = Q.verify_manifest()
    require(Q.census(qm)['all_successful'] and not Q.LOCK.exists(), 'Search is not closed')
    sealed = read(SEARCH_SEAL)
    require(sealed['status'] == 'closed_search_verified', 'Missing closed search proof')
    inputs = dict(qm['input_sha256'])
    inputs[str(Q.MANIFEST.relative_to(REPO))] = sha(Q.MANIFEST)
    inputs[str(SEARCH_SEAL.relative_to(REPO))] = sha(SEARCH_SEAL)
    for row in sealed['files']:
        require(sha(REPO / row['path']) == row['sha256'], 'Closed search artifact changed: ' + row['path'])
        inputs[row['path']] = row['sha256']
    cfg, old_cfg = get_config('survey_p10'), get_config('survey_p8')
    require(cfg.ingest_key() == old_cfg.ingest_key() == '3d160359ad', 'Ingest changed')
    records = C._load_results(C.INJ_RUN)
    original_dir = REPO / 'data/survey/runs/inj_p8/results'
    originals = {r['job_id']:r for r in C._load_results(original_dir.parent)}
    require(len(records) == len(originals) == 2100, 'Original calibration census differs')
    equal_fields = ('tic_id', 'injection', 'injection_model', 'star', 'rotation_proxy',
                    'prepare_counters', 'n_cadences_raw', 'baseline_days', 'n_units')
    for rec in records:
        old = originals[rec['job_id']]
        require(old['status'] == 'ok', 'Original calibration was not successful')
        require(all(k in rec and k in old and rec[k] == old[k] for k in equal_fields),
                'Expected-SNR input differs: ' + rec['job_id'])
        require(rec['config']['ingest_key'] == old['config']['ingest_key'] == cfg.ingest_key(),
                'Per-record ingest differs')
        path = original_dir / (rec['job_id'] + '.json')
        inputs[str(path.relative_to(REPO))] = sha(path)
    sample = list(csv.DictReader(C.SAMPLE.open(newline='', encoding='utf-8')))
    tics = {int(r['tic_id']) for r in sample}
    require(len(sample) == len(tics) == 300 and {r['tic_id'] for r in records} == tics, 'Host population differs')
    prepared = []
    for tic in sorted(tics):
        path = stitched_path(tic, cfg)
        require(path == stitched_path(tic, old_cfg), 'Prepared cache path differs')
        for p in (path, path.with_suffix('.json')):
            require(p.is_file(), 'Missing original prepared curve: ' + str(p))
            name = str(p.relative_to(REPO))
            inputs[name] = sha(p)
            prepared.append(name)
    original_cache = REPO / 'data/survey/p8/expected_snr_p8.json'
    cache = read(original_cache)
    require(set(cache) == set(originals) and all(math.isfinite(v['snr_expected']) and v['snr_expected'] >= 0
            for v in cache.values()), 'Incomplete original SNR cache')
    inputs[str(original_cache.relative_to(REPO))] = sha(original_cache)
    destination = CAL / 'expected_snr_p10.json'
    require(not destination.exists(), 'Expected-SNR destination already exists')
    CAL.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original_cache, destination)
    require(sha(destination) == sha(original_cache), 'Expected-SNR copy differs')
    inputs[str(destination.relative_to(REPO))] = sha(destination)
    save(OUT / 'expected_snr_reuse.json', dict(utc=utc(), n_injections=2100,
         equal_record_fields=equal_fields, ingest_key=cfg.ingest_key(),
         original_cache=str(original_cache.relative_to(REPO)), destination=str(destination.relative_to(REPO)),
         cache_sha256=sha(original_cache), prepared_paths=prepared,
         proof='Identical injection models, stellar inputs and preparation diagnostics; identical P8/P10 ingest and existing un-injected prepared paths. Original expected_snr numerical function unchanged. Original cache copied byte for byte; hashes of every original result/prepared input are in calibration_manifest.json.'), exclusive=True)
    fa_measurement = read(REPO / 'p10/results/search_false_alarms_e.json')
    verify_hashes(fa_measurement['inputs'])
    inputs.update(fa_measurement['inputs'])
    fa = C._load_results(C.FA_RUN)
    require(len(fa) == 300 and {r['tic_id'] for r in fa} == tics, 'FA population differs')
    for rec in fa:
        require(rec['status'] == rec.get('orchestrator_status') == 'ok', 'FA search not settled')
        require(rec['config']['name'] == 'survey_p10_both' and
                Q.effective_config(rec['config']) == Q.effective_config(get_config('survey_p10', record_traces=True).to_dict()),
                'FA selected configuration differs')
        path = C.FA_RUN / 'results' / (rec['job_id'] + '.json')
        inputs[str(path.relative_to(REPO))] = sha(path)
    F.set_root(C.FA_ROOT); F.set_rules('p10.0')
    require(F.V.RULE_SET.secondary_gate == 'bound', 'Frozen secondary mode differs')
    coll = F.collect(C.FA_RUN, C.SAMPLE)
    require(coll['n_stars_ok'] == 300 and coll['n_targets'] == 300 and coll['config'] == 'survey_p10', 'FA collect differs')
    fa_jobs = F.V.jobs()
    require(len(fa_jobs) == coll['n_pass_pregate'], 'FA candidates missing')
    require(len({F.V.kkey(j['tic_id'], j['period']) for j in fa_jobs}) == len(fa_jobs), 'FA key collision')
    jobs = C.recovered_jobs(records)
    require(len({j['job_id'] for j in jobs}) == len(jobs), 'Recovered injection collision')
    for path in (C.FA_ROOT / 'candidates.csv', C.FA_ROOT / 'survivors.csv', C.FA_ROOT / 'collect_p10.json',
                 OUT / 'expected_snr_reuse.json', OUT / 'adapter_routing.json'):
        inputs[str(path.relative_to(REPO))] = sha(path)
    sources = set((REPO / 'src').rglob('*.py')) | set((REPO / 'scripts').glob('*.py'))
    sources |= {Path(__file__).resolve(), Path(C.__file__).resolve(), Path(F.__file__).resolve(), Path(Q.__file__).resolve()}
    m = dict(utc=utc(), rules='p10.0', config='survey_p10', workers=16, phases=PHASES,
             n_injections=2100, n_fa_stars=300, recovered_jobs=jobs, fa_jobs=fa_jobs,
             source_sha256={str(p.relative_to(REPO)):sha(p) for p in sorted(sources)}, input_sha256=inputs,
             secondary_failure_sample=dict(seed=20260904, fraction=.10),
             algorithms='Original recovery definition, Stage A, bound S and 1000-bootstrap logistic fits; fresh p10.0 records, no old outcome retagging.',
             scientific_output_root=str(CAL.relative_to(REPO)), report_root=str(OUT.relative_to(REPO)))
    save(MANIFEST, m, exclusive=True)
    save(STATE, dict(utc=utc(), status='prepared', phase=None, manifest_sha256=sha(MANIFEST)), exclusive=True)
    print(json.dumps(dict(manifest=str(MANIFEST), recovered_injections=len(jobs), fa_pregate=len(fa_jobs), reused_snr=2100), indent=2))


def injection_job(row):
    return dict(rank=row['rank'], tic_id=row['tic_id'], period=float(row['period_days']),
                epoch_btjd=float(row['epoch_btjd']), duration_days=float(row['duration_days']), depth_ppt=float(row['depth_ppt']),
                stitch_snr=float(row['stitch_snr'] or 0), stitch_n_transits=int(row['stitch_n_transits'] or 0),
                n_units=int(row['n_units'] or 0), tmag=float(row['tmag'] or 0))


def check_record(path, stage, job, a_decision=None):
    import p10_funnel_calibration as F
    import audit_p5 as A
    from tesshunter.survey import get_config
    rec = read(path)
    key = F.V.kkey(job['tic_id'], job['period'])
    require(rec.get('key') == key and rec.get('rank') == job['rank'] and rec.get('tic_id') == job['tic_id'],
            'Candidate identity differs: ' + str(path))
    require(rec.get('rules_version') == 'p10.0' and rec.get('survey_preset') == 'survey_p10' and
            rec.get('input_config') == A.input_config_for(get_config('survey_p10')), 'Stale or unnamed record: ' + str(path))
    field = 'decision' if stage == 'A' else 'gate'
    require(rec.get(field) in ('PASS', 'FAIL'), 'Unsettled bound record: ' + str(path))
    require(isinstance(rec.get('seconds'), (int, float)) and math.isfinite(rec['seconds']) and rec['seconds'] >= 0,
            'Missing timing: ' + str(path))
    if stage == 'A':
        require(rec.get('survey') == {k:job[k] for k in ('period','epoch_btjd','duration_days','depth_ppt',
                'stitch_snr','stitch_n_transits','n_units','tmag')}, 'Stage A ephemeris differs: ' + str(path))
        require(rec.get('thresholds') == F.R.thresholds(F.R.P10_RULES)['stageA'], 'Stage A thresholds differ')
        root = path.parent.parent
        require((root / 'prep' / (key + '.json')).is_file() and (root / 'tls' / (key + '_lc.npz')).is_file(),
                'Missing prepared Stage A artifacts')
    else:
        require(rec.get('survey_period') == job['period'] and rec.get('survey_depth_ppt') == job['depth_ppt'],
                'Secondary ephemeris differs')
        require(rec.get('thresholds') == F.R.thresholds(F.R.P10_RULES)['secondary'], 'Secondary thresholds differ')
        require(a_decision in ('PASS', 'FAIL') and rec.get('stageA_decision') == a_decision and
                rec.get('stageA_sample') is (a_decision == 'FAIL'), 'Secondary A/sample linkage differs')
    return rec


def phase_census(phase, m):
    import p10_funnel_calibration as F
    expected = []
    fa_root = CAL / 'fa_funnel'
    if phase in ('fa_a', 'fa_s'):
        jobs = m['fa_jobs']
        if phase == 'fa_s':
            a = phase_census('fa_a', m)
            if not a['complete']:
                return dict(complete=False, expected=None, settled=0, reason='FA A not complete')
            dec = {F.V.kkey(j['tic_id'], j['period']):read(fa_root/'stageA'/(F.V.kkey(j['tic_id'],j['period'])+'.json'))['decision'] for j in jobs}
            jobs = F.select_secondary_jobs(jobs, dec)
        stage = 'A' if phase == 'fa_a' else 'S'
        folder = fa_root / ('stageA' if stage == 'A' else 'secondary')
        for j in jobs:
            key = F.V.kkey(j['tic_id'], j['period'])
            expected.append((folder/(key+'.json'),stage,j,None if stage=='A' else dec[key]))
        require({p for p in folder.glob('*.json')} <= {p for p,*_ in expected}, 'Extra FA records')
    elif phase == 'injection_as':
        require({p.name for p in (CAL/'inj_funnel').glob('*') if p.is_dir()} <= {j['job_id'] for j in m['recovered_jobs']},
                'Extra injection directory')
        for row in m['recovered_jobs']:
            j = injection_job(row); key = F.V.kkey(j['tic_id'], j['period'])
            root = CAL/'inj_funnel'/row['job_id']
            a = root/'stageA'/(key+'.json'); s = root/'secondary'/(key+'.json')
            for folder, allowed in (('stageA',a),('secondary',s)):
                require(set((root/folder).glob('*.json')) <= {allowed}, 'Extra injection stage record')
            expected.extend(((a,'A',j,None),(s,'S',j,read(a).get('decision') if a.exists() else None)))
    else:
        raise ValueError(phase)
    settled, invalid = 0, []
    for path,stage,job,a_dec in expected:
        if path.exists():
            try:
                check_record(path,stage,job,a_dec); settled += 1
            except (RuntimeError, ValueError, KeyError, OSError) as exc:
                invalid.append(dict(path=str(path.relative_to(REPO)),error=repr(exc)))
    return dict(complete=settled==len(expected) and not invalid, expected=len(expected), settled=settled,
                pending=len(expected)-settled, invalid=invalid)


def phase_command(phase):
    py = [sys.executable, '-B']
    if phase in ('fa_a','fa_s'):
        return py+[str(REPO/'p10/protocol/p10_funnel_calibration.py'),'--root',str(CAL/'fa_funnel'),'--rules','p10.0',
                   'stageA' if phase=='fa_a' else 'secondary','--slices','16','--threads','1','--shared-queue']
    return py+[str(REPO/'p10/protocol/p10_completeness_calibration.py')]+(
        ['funnel','--slices','16','--rules','p10.0','--shared-queue'] if phase=='injection_as' else ['analyze','--rules','p10.0'])


def execute():
    require_free()
    m = verify_manifest()
    state = read(STATE)
    require(state['status']=='prepared', 'Only prepared execution may start; recovery needs an explicit reviewed controller change')
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    os.environ.update(PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1', TESSHUNTER_OFFLINE='1',
                      LIGHTKURVE_CACHE=str(REPO/'data/cache/lightkurve'))
    owner = dict(pid=os.getpid(),created_epoch=psutil.Process().create_time(),utc=utc(),manifest_sha256=sha(MANIFEST))
    save(LOCK,owner,exclusive=True)
    try:
        for phase in PHASES:
            if phase=='analyze':
                require(all(phase_census(p,m)['complete'] for p in PHASES[:-1]), 'Incomplete A/S cannot enter analysis')
            command = phase_command(phase)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            log = OUT / f'{phase}_{stamp}.log'
            with log.open('x',encoding='utf-8') as stream:
                child = subprocess.Popen(command,cwd=str(REPO),stdout=stream,stderr=subprocess.STDOUT)
                save(STATE,dict(utc=utc(),status='running',phase=phase,owner=owner,child_pid=child.pid,
                     child_created_epoch=psutil.Process(child.pid).create_time(),command=command,log=str(log.relative_to(REPO)),
                     manifest_sha256=sha(MANIFEST)))
                code=child.wait()
            require(code==0, f'{phase} exited {code}; preserve logs and review before recovery')
            if phase!='analyze':
                census=phase_census(phase,m)
                save(OUT/f'{phase}_complete.json',dict(utc=utc(),phase=phase,census=census,log=str(log.relative_to(REPO))),exclusive=True)
                require(census['complete'], f'{phase} contains unsettled or invalid records: {census}')
            print(utc(),phase,'COMPLETE',flush=True)
        verify_manifest()
        report=read(CAL/'completeness_p10.json')
        require(report['n_injections']==2100 and report['n_jobs_ok']==2100 and report['config']=='survey_p10'
                and report['rules_version']=='p10.0' and report['false_alarms']['n_stars_ok']==300, 'Final calibration census differs')
        save(STATE,dict(utc=utc(),status='calibration_complete_review_required',phase=None,manifest_sha256=sha(MANIFEST)))
        print('FULL_CALIBRATION_COMPLETE; side-by-side/yield/Stop Rule 1 review is required',flush=True)
    except BaseException as exc:
        previous=read(STATE)
        save(STATE,dict(utc=utc(),status='stopped_review_required',error=repr(exc),previous_state=previous,
                       manifest_sha256=sha(MANIFEST)))
        raise
    finally:
        LOCK.unlink()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=('prepare','run','inspect'))
    args=ap.parse_args()
    if args.command=='prepare':
        prepare()
    elif args.command=='run':
        execute()
    else:
        m=verify_manifest()
        report=dict(utc=utc(),state=read(STATE),lock=read(LOCK) if LOCK.exists() else None,
                    census={p:phase_census(p,m) for p in PHASES[:-1]},process_snapshot=process_snapshot())
        path=OUT/('inspect_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
        save(path,report,exclusive=True)
        print(json.dumps(dict(receipt=str(path),state=report['state'],census=report['census'],
              processes=len(report['process_snapshot']['processes']),inaccessible_pids=report['process_snapshot']['inaccessible_pids']),indent=2))


if __name__=='__main__':
    main()
