from pathlib import Path
from datetime import datetime,timezone
import argparse,json,shutil,subprocess,sys,time,tomllib

R=Path(r'C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter')
sys.path.insert(0,str(R/'p10/protocol'))
import run_part2d_injection_search as Q
O=R/'p10/results/part2d_calibration_20260912'
ap=argparse.ArgumentParser();ap.add_argument('stamp');args=ap.parse_args()
W=O/'heartbeat_checks'/args.stamp
assert W.resolve().is_relative_to((O/'heartbeat_checks').resolve())
r=Q.read(W/'check.json');art=Q.read(W/'new_settled_injection_artifacts.json')
assert r['state']=='healthy_injection_calibration_running' and r['schedule_minutes']==120
assert r['extrapolated_remaining_injection_h']>2
assert all(w['extrapolated_remaining_h']>2 for w in r['rolling_windows'] if w['minutes']>=30)
assert r['newly_checkpointed']==len(art['new_complete_job_ids'])
def git(*argv):
    p=subprocess.run(['git','-C',str(R),'-c','maintenance.auto=false','-c','gc.auto=0',*argv],capture_output=True,text=True)
    if p.returncode:raise RuntimeError(p.stderr)
    return p.stdout
assert not git('diff','--cached','--name-only').strip()
assert not git('diff','--name-only').strip()
actual=tomllib.loads(Path(r'C:\Users\seanj\.codex\automations\continue-local-p10-execution\automation.toml').read_text())
expected=Q.read(Path('work/p10_20260912T110717Z_automation_expected.json'))
for k in ('id','kind','name','prompt','rrule','status'):assert actual[k]==expected[k],k
assert actual['target_thread_id']==expected['targetThreadId']
Q.save(W/'schedule_verified.json',dict(utc=Q.utc(),saved=actual,full_prompt_unchanged=True,minutes=120,
    reason='The 30/60/120-minute throughput windows and whole-phase rate all imply more than two hours of injection work; all five bootstrap levels remain afterward.'),exclusive=True)
p8=R/'data/survey/p8/completeness_p8.json';baseline=Q.read(p8)
generated=datetime.fromisoformat(baseline['generated_utc'].replace('Z','+00:00'))
mtime=datetime.fromtimestamp(p8.stat().st_mtime,timezone.utc)
Q.save(W/'bootstrap_reference_timing.json',dict(utc=Q.utc(),source=str(p8.relative_to(R)),sha256=Q.sha(p8),
    generated_utc=baseline['generated_utc'],file_mtime_utc=mtime.isoformat(),generated_to_mtime_seconds=(mtime-generated).total_seconds(),
    n_boot_by_level={k:(v.get('logistic') or {}).get('n_boot') for k,v in baseline['levels'].items()},
    interpretation='The original result timestamp is assigned before its five logistic fits; the original file mtime is about 153 seconds later. This is a metadata-based timing reference, not a fresh benchmark or guaranteed duration. It excludes the earlier result/funnel loading and later report writing, and may depend on preserved filesystem timestamps. No near-finish schedule was based on this reference at the current check.'),exclusive=True)
when=datetime.fromisoformat(r['utc']).strftime('%Y-%m-%d %H:%M UTC')
evidence=W.relative_to(R).as_posix()
hp=R/'HANDOFF_P10.md';raw=hp.read_bytes();marker=b'## 0. Pre-registered decision rules'
assert Q.frozen_section_sha()==Q.FROZEN_SHA
windows={w['minutes']:w for w in r['rolling_windows']}
note=f'''### Injection calibration: {r['completed_injections']}/1,240 pairs verified, {when} [M]

**{r['completed_injections']}/1,240 recovered injections have complete valid A/S pairs**, with {r['remaining_injections']} remaining at this checkpoint. This adds {r['newly_checkpointed']} settled injection groups since the prior checkpoint, preserving {len(art['files'])} new artifacts. The canonical inspection rehashed all frozen source/input files and found no invalid records; subsequent source/correction-manifest and owner/child creation-time checks still pass. All 16 worker indices are present and {r['matching_workers_with_cpu_progress']} continuing worker interpreters show positive CPU deltas. The original controller remains closed, and the same checked controller continues injection A/S without restart. The completed FA calibration and conservative workload bound remain unchanged. The 774-pass/1-skip baseline and subsequent focused tests were not repeated without a source change.

**Keep the two-hour cadence.** The whole-phase rate is {r['completed_pairs_per_hour']:.2f} complete pairs/hour and extrapolates {r['extrapolated_remaining_injection_h']:.2f} hours remaining. The 30/60/120-minute windows give {windows[30]['extrapolated_remaining_h']:.2f}/{windows[60]['extrapolated_remaining_h']:.2f}/{windows[120]['extrapolated_remaining_h']:.2f} hours. The shorter 15-minute window gives {windows[15]['extrapolated_remaining_h']:.2f} hours for injection work alone; it does not establish a complete-calibration finish within two hours, since all five 1000-bootstrap levels follow. These are descriptive rates over a changing search-SNR-ordered host mix, not a firm ETA. The existing automation's full prompt, target and ACTIVE 120-minute schedule were verified unchanged. A separate P8 file-metadata timing reference for the bootstrap is saved with its limitations and was not used to claim an early finish.

Evidence: `{evidence}/`, including both worker samples, named-record validation/census, exact new artifact hashes and schedule verification. Continue with `p10/protocol/run_part2d_calibration_checked.py inspect`. Do not duplicate a healthy owner, repeat prepare/register/completed FA work, or edit manifest-frozen source/input. On complete calibration closure, validate/seal all results and continue the final level table, new-curve yield and original Stop Rule 1 review. SNR50_S<=14.0 remains pending; the conservative 148.931095986 central-model load bound is not a completed stop-rule decision. No new real/held-out candidate outcomes were opened.

'''
hp.write_bytes(raw.replace(marker,note.encode()+marker,1));assert Q.frozen_section_sha()==Q.FROZEN_SHA
rp=R/'RESUME_P10.md'
entry=f'''# P10 current check: {r['completed_injections']}/1,240 injection funnels complete

At {when}, **{r['completed_injections']} recovered injections have valid completed A/S pairs; {r['remaining_injections']} remain**. All frozen source/input hashes, the original checked-owner/child identities and current worker progress verify. All 16 workers continue; no invalid saved record was found. This checkpoint adds {r['newly_checkpointed']} complete artifact groups. FA calibration remains closed (709 A / 111 S records; FA_S=2/300), with its earlier decision equality and schema-guard recovery fully preserved.

The existing heartbeat is verified ACTIVE every **two hours**, with its full prompt unchanged. The 30/60/120-minute windows imply {windows[30]['extrapolated_remaining_h']:.2f}/{windows[60]['extrapolated_remaining_h']:.2f}/{windows[120]['extrapolated_remaining_h']:.2f} hours of injection work; five 1000-bootstrap level fits follow. The faster 15-minute sample does not support a complete-queue early wake. Latest evidence: `{evidence}/`.

Use `p10/protocol/run_part2d_calibration_checked.py inspect`; current state/lock/logs are in `p10/results/part2d_calibration_20260912/`, scientific outputs in `data/survey/p10/part2d/calibration/`. Preserve the healthy owner and every frozen worker/input byte. Do not repeat prepare/register, completed FA phases or old controllers. When calibration closes, validate/seal results, report the full table beside p8.0 in docs/RULES.md, finish the new-curve yield/uncertainty review and apply original Stop Rule 1. The independent conservative load bound is 148.931095986 under its stated central-model assumptions; **SNR50_S<=14.0 remains pending**, so later stages remain closed. Preserve all original exposure boundaries and later stop rules. Earlier entries are historical.

---

'''
rp.write_bytes(entry.encode()+rp.read_bytes())
shutil.copy2(Path(__file__),W/Path(__file__).name)
paths=['HANDOFF_P10.md','RESUME_P10.md',evidence]+[row['path'] for row in art['files']]
for row in art['files']:
    assert Q.sha(R/row['path'])==row['sha256'],row['path']
fp=Path('work')/f'p10_stage_calibration_{args.stamp}.txt'
fp=fp.resolve();fp.write_bytes(b'\0'.join(p.encode() for p in sorted(set(paths)))+b'\0')
for attempt in range(3):
    try:
        git('-c','core.safecrlf=false','add',f'--pathspec-from-file={fp}','--pathspec-file-nul');break
    except RuntimeError as exc:
        if 'Permission denied' not in str(exc) or attempt==2:raise
        assert not git('diff','--cached','--name-only').strip();time.sleep(.5)
staged=git('diff','--cached','--name-only').splitlines()
assert all(p in paths or p.startswith(evidence+'/') for p in staged)
assert not git('diff','--cached','--check').strip()
out=git('commit','-m',f"Prompt 10: checkpoint {r['completed_injections']} complete injection funnels")
Path('work',f'p10_commit_calibration_{args.stamp}.log').write_text(out,encoding='utf-8')
assert not git('diff','--name-only').strip()
assert Q.frozen_section_sha()==Q.FROZEN_SHA
print(json.dumps(dict(commit=git('rev-parse','HEAD').strip(),files=len(staged),completed=r['completed_injections'],
    new_complete=r['newly_checkpointed'],remaining=r['remaining_injections'],schedule_minutes=120),indent=2))
