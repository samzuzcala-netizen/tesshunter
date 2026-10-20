from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse, json, os, shutil, subprocess, sys, time, tomllib

R=Path(r'C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter')
sys.path.insert(0,str(R/'p10/protocol'))
import run_part2d_yield_projection as Y
O=Y.OUT;F=O/'finalization_20260912'
ap=argparse.ArgumentParser();ap.add_argument('inspection');args=ap.parse_args()
inspection=O/args.inspection
assert inspection.resolve().is_relative_to(O.resolve())
assert not (F/'precommit_verification.json').exists()

def git(*argv, check=True):
    p=subprocess.run(['git','-C',str(R),'-c','maintenance.auto=false','-c','gc.auto=0',
        '-c','core.quotePath=false',*argv],capture_output=True,text=True,encoding='utf-8')
    if check and p.returncode:raise RuntimeError(p.stderr+p.stdout)
    return p

head=git('rev-parse','HEAD').stdout.strip()
assert head=='726eb7965fa63eeb8ab3a10926c3c0a579359d03',head
assert not git('diff','--cached','--name-only').stdout.strip()
assert set(git('diff','--name-only').stdout.splitlines())=={'HANDOFF_P10.md','RESUME_P10.md','docs/RULES.md'}
assert Y.section_zero_sha()==Y.FROZEN
current=Y.read(inspection)
assert current['state']['status']=='calibration_complete_review_required'
assert all(c['complete'] and not c['invalid'] for c in current['census'].values())
assert not current['process_snapshot']['processes'] and not current['process_snapshot']['inaccessible_pids']
assert not (O/'calibration.lock').exists() and not (O/'calibration_checked.lock').exists()
actual=tomllib.loads(Path(r'C:\Users\seanj\.codex\automations\continue-local-p10-execution\automation.toml').read_text(encoding='utf-8'))
expected=Y.read(F/'automation_update_receipt.json')['requested_update']
for k in ('id','kind','name','prompt','rrule','status'):assert actual[k]==expected[k],k
assert actual['target_thread_id']==expected['targetThreadId'] and actual['status']=='PAUSED'
decision=Y.read(O/'stop_rule_1_decision.json')
assert decision['status']=='STOP_RULE_1_FAILED' and not decision['proceed_to_parts_3_to_5']
for p,h in decision['inputs_sha256'].items():assert Y.sha(R/p)==h,p
cal=Y.read(O/'full_calibration_closed_seal_20260912.json')
model=Y.read(Y.MODEL/'closed_seal.json')
assert model['status']=='yield_model_closed_verified'
cal_paths={row['path'] for row in cal['files']}
assert {p.relative_to(R).as_posix() for p in Y.CAL.rglob('*') if p.is_file()}==cal_paths
all_artifacts=cal['files']+model['files']
def verify(row):
    p=R/row['path']
    assert p.stat().st_size==row['bytes'] and Y.sha(p)==row['sha256'],row['path']
    return row['bytes']
total=0
with ThreadPoolExecutor(max_workers=4) as pool:
    for i,n in enumerate(pool.map(verify,all_artifacts),1):
        total+=n
        if i%5000==0:print(f'Verified {i:,}/{len(all_artifacts):,} closed calibration/model artifacts',flush=True)
for path,sha in Y.read(Y.MODEL/'manifest.json')['sources_sha256'].items():assert Y.sha(R/path)==sha,path
for pair in Y.read(Y.MODEL/'manifest.json')['noise_copies']:
    assert Y.sha(R/pair['original'])==Y.sha(R/pair['copy'])==pair['sha256']
code=['p10/protocol/p10_expected_yield_engine.py','p10/protocol/run_part2d_yield_projection.py',
      'p10/protocol/report_part2d_stop_rule.py','tests/test_p10_yield_projection.py']
docs=['HANDOFF_P10.md','RESUME_P10.md','docs/RULES.md','docs/AUDIT_P10.md']
def allowed(path):
    return path in cal_paths or path.startswith('p10/results/part2d_calibration_20260912/') or path in code+docs
untracked=git('ls-files','--others','--exclude-standard').stdout.splitlines()
outside=sorted(p for p in untracked if not allowed(p))
Y.save(F/'unrelated_untracked_preserved.json',dict(utc=Y.utc(),paths=outside,
    statement='These pre-existing untracked paths are not staged, deleted or rewritten by the final stop checkpoint.'))
Y.save(F/'precommit_verification.json',dict(utc=Y.utc(),status='ready_for_local_final_stop_commit',
    parent_commit=head,full_section_0_sha256=Y.FROZEN,source_and_original_input_verification=str(inspection.relative_to(R)),
    inspection_sha256=Y.sha(inspection),complete_census=current['census'],owners_remaining=0,inaccessible_processes=0,
    calibration_artifacts_verified=len(cal['files']),model_artifacts_verified=len(model['files']),
    total_artifact_bytes=total,original_2000_noise_hashes_unchanged=True,
    yield_source_hashes_unchanged=True,automation_status='PAUSED',normal_interval_minutes=120,
    decision='STOP_RULE_1_FAILED',no_later_stage_outcomes_opened=True,
    source_document_paths=code+docs,unrelated_untracked_paths_preserved=len(outside)))
shutil.copy2(Path(__file__),F/Path(__file__).name)
paths=sorted(cal_paths|{p.relative_to(R).as_posix() for p in O.rglob('*') if p.is_file()}|set(code+docs))
assert all(allowed(p) for p in paths)
assert not any(p.endswith('.lock') or '__pycache__' in p for p in paths)
pathfile=Path('work/p10_final_stop_pathspec.txt').resolve()
pathfile.write_bytes(b'\0'.join(p.encode('utf-8') for p in paths)+b'\0')
print(f'Staging only {len(paths):,} verified P10 paths; {len(outside):,} unrelated untracked paths preserved',flush=True)
for attempt in range(3):
    staged=git('-c','core.safecrlf=false','add','-f',f'--pathspec-from-file={pathfile}','--pathspec-file-nul',check=False)
    if staged.returncode==0:break
    assert 'Permission denied' in staged.stderr and attempt<2,staged.stderr
    assert not git('diff','--cached','--name-only').stdout.strip()
    time.sleep(.5)
staged_paths=git('diff','--cached','--name-only').stdout.splitlines()
assert staged_paths and all(allowed(p) for p in staged_paths)
git('diff','--cached','--check','--',*code,*docs)
whole_check=git('diff','--cached','--check',check=False)
Path('work/p10_final_staged_whitespace.log').write_text(whole_check.stdout+whole_check.stderr,encoding='utf-8')
if whole_check.returncode:
    assert all(line.split(':')[0] not in code+docs for line in whole_check.stdout.splitlines() if ':' in line)
    print('Original generated-output whitespace diagnostics retained; source/document checks pass.',flush=True)
commit=git('commit','-m','Prompt 10: close full calibration and stop at original recovery threshold')
Path('work/p10_final_commit.log').write_text(commit.stdout+commit.stderr,encoding='utf-8')
new_head=git('rev-parse','HEAD').stdout.strip()
assert new_head!=head
assert not git('diff','--name-only').stdout.strip()
assert not git('diff','--cached','--name-only').stdout.strip()
assert Y.section_zero_sha()==Y.FROZEN
after=git('ls-files','--others','--exclude-standard').stdout.splitlines()
assert sorted(after)==outside
tracked=set(git('ls-files').stdout.splitlines())
assert set(paths)<=tracked
post=dict(utc=Y.utc(),status='final_stop_committed',commit=new_head,parent_commit=head,
          changed_paths=len(staged_paths),verified_P10_paths=len(paths),
          calibration_artifacts=len(cal['files']),model_artifacts=len(model['files']),
          source_and_documents_whitespace_check='passed',generated_output_whitespace_returncode=whole_check.returncode,
          tracked_worktree_clean=True,unrelated_untracked_paths_preserved=len(outside),
          full_section_0_sha256=Y.FROZEN,automation_status='PAUSED',normal_interval_minutes=120,
          stop_reason='After-A/S SNR50 18.261241176064384 exceeds 14.0; Parts 3–5 not run')
Y.save(Path('work/p10_final_checkpoint_receipt.json'),post)
print(json.dumps(post,indent=2),flush=True)
