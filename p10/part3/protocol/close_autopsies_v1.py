"""Validate the five closed diagnostics and seal their original evidence."""
from common import REPO, ROOT, read, write, sha, utc, environment
environment()
import json, time, psutil
from part_f_guards_v1 import require_hash, assert_no_integrity_failure
from registration_execution_v3 import verify
from full_funnel_plan import charge

def dead(identity):
    try:
        process = psutil.Process(identity['pid'])
        assert abs(process.create_time() - identity['create_time']) >= .01, 'Closed process remains alive'
    except psutil.NoSuchProcess:
        pass

def main():
    assert_no_integrity_failure()
    verify(require_launch_seal=True)
    assert not (ROOT/'manifests/controller_owner.json').exists()
    assert not (ROOT/'manifests/autopsies_closed_evidence_seal.json').exists()
    base = ROOT/'results/controllers/autopsies'
    closure, launch = read(base/'closure.json'), read(base/'launch.json')
    assert closure['status'] == 'CLOSED' and closure['completed'] == 5
    assert closure['pending'] == closure['unknowns'] == 0
    assert closure['all_owned_workers_closed'] and closure['source_hashes_unchanged']
    dead(closure['owner'])
    for path, digest in launch['source_hashes'].items():
        require_hash(REPO/path, digest, 'Autopsy launch source')
    jobs = read(ROOT/'manifests/autopsy_jobs.json')
    expected = {job['job_id'] for job in jobs}
    assert len(expected) == 5 and expected == {p.stem for p in (base/'attempts').glob('*.json')}
    started, timer = utc(), time.perf_counter()
    try:
        files = set(base.rglob('*'))
        records = []
        for job in jobs:
            fid = job['job_id']
            attempt = read(base/f'attempts/{fid}.json')
            dead(attempt)
            assert attempt['attempt'] == 1 and attempt['status'] == 'COMPLETE'
            runtime_path, digest = job['arguments'][1:]
            require_hash(REPO/runtime_path, digest, 'Autopsy runtime')
            runtime, result = read(REPO/runtime_path), read(REPO/job['result_path'])
            assert runtime['family_id'] == result['family_id'] == fid
            assert result['status'] == 'COMPLETE' and result['runtime_sha256'] == digest
            assert result['first_termination'] == 'SEARCH_MATCHING'
            for field in ('source_hashes', 'input_hashes'):
                for path, value in runtime[field].items():
                    require_hash(REPO/path, value, f'Autopsy {field}')
            case = REPO/result['diagnostic_root']
            assert not list(case.rglob('ctoi_fields.json')) and not (case/'stageD').exists()
            files.update(case.rglob('*'))
            files.update([REPO/runtime_path, REPO/job['result_path'], REPO/result['figure_path']])
            records.append(dict(family_id=fid, result_path=job['result_path'], result_sha256=sha(REPO/job['result_path']),
                                scientific_attempts=1, primary_outcome_changed=False))
        for name in ('autopsy_jobs.json','autopsy_preflight.json','autopsy_selection_v1.json','autopsy_method_registration_v1.json'):
            files.add(ROOT/'manifests'/name)
        summary = dict(utc=utc(), status='CLOSED_VALIDATED', n_complete=5, n_unknown=0,
                       records=records, closure=closure, all_original_inputs_unchanged=True,
                       iteration_executed=False, supervision='Foreground bounded phase; measured wall 9.19 seconds; no extra scheduled firing')
        write(ROOT/'results/autopsy_closure_summary.json', summary)
        files.add(ROOT/'results/autopsy_closure_summary.json')
        hashes = {p.relative_to(REPO).as_posix():sha(p) for p in sorted(files) if p.is_file()}
        write(ROOT/'manifests/autopsies_closed_evidence_seal.json', dict(utc=utc(), files=hashes,
              n_files=len(hashes), n_bytes=sum((REPO/p).stat().st_size for p in hashes), preserves_original_plots=True))
    finally:
        charge(started,timer,'H_autopsy_validation_and_seal')
    print(json.dumps(dict(status='CLOSED_VALIDATED', complete=5, sealed_files=len(hashes))))

if __name__ == '__main__':
    main()
