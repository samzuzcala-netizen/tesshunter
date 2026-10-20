"""Record fresh app-verified supervision shutdown; never edits automation TOML."""
from common import REPO,ROOT,read,write,sha,utc,environment
environment()
from pathlib import Path
import hashlib,json,tomllib,psutil,shutil

def main():
    assert not (ROOT/'manifests/controller_owner.json').exists()
    assert read(ROOT/'results/final_reports_ready.json')['status']=='REPORTS_READY_FOR_FINAL_SHUTDOWN'
    assert not (ROOT/'DECISION_P10_3.md').exists()
    base=Path(r'C:\Users\seanj\.codex\automations')
    config_path=base/'prompt-10-3-hourly-check-in/automation.toml'
    old_path=base/'continue-local-p10-execution/automation.toml'
    cfg=tomllib.loads(config_path.read_text(encoding='utf-8'));old=tomllib.loads(old_path.read_text(encoding='utf-8'))
    assert cfg['status']==old['status']=='PAUSED'
    schedule=read(ROOT/'manifests/checkin_schedule.json')
    prompt_sha=hashlib.sha256(cfg['prompt'].encode()).hexdigest()
    assert prompt_sha==schedule['prompt_sha256'], 'Automation prompt changed at final pause'
    assert cfg['target_thread_id']==schedule['target_thread_id']
    checks=[json.loads(s) for s in (ROOT/'logs/checkins.jsonl').read_text(encoding='utf-8-sig').splitlines() if s.strip()]
    assert len(checks)==schedule['count']==34
    closures=[]
    for path in (ROOT/'results/controllers').glob('*/closure.json'):
        d=read(path);assert d['status']=='CLOSED' and d['all_owned_workers_closed'] and d['pending']==0
        try:
            p=psutil.Process(d['owner']['pid']);assert abs(p.create_time()-d['owner']['create_time'])>=.01
        except psutil.NoSuchProcess:pass
        closures.append(dict(phase=path.parent.name,owner=d['owner'],closure_sha256=sha(path)))
    disk={drive:psutil.disk_usage(drive+':\\').free for drive in ('C','D')}
    assert disk['C']>25_000_000_000
    receipt=dict(utc=utc(),status='DISABLED_VERIFIED',automation_id=cfg['id'],automation_name=cfg['name'],
        configured_status=cfg['status'],target_thread_id=cfg['target_thread_id'],rrule=cfg['rrule'],prompt_sha256=prompt_sha,
        automation_toml_sha256=sha(config_path),old_p10_id=old['id'],old_p10_status=old['status'],old_p10_toml_sha256=sha(old_path),
        checkin_count=len(checks),first_firing=schedule['first_firing'],last_firing=schedule['last_firing'],
        prior_schedule=schedule,prior_schedule_sha256=sha(ROOT/'manifests/checkin_schedule.json'),
        disk_free_bytes=disk,owner_file_absent=True,recorded_controller_identities_dead=True,closed_phases=closures,
        method='App automation_update set PAUSED; fresh TOML reread verifies status and unchanged prompt; no direct configuration-file edit',
        final_scientific_phase='autopsies',final_scientific_closure='2026-09-15T22:41:47.553867+00:00',
        finalization_compute_class='Engineering; no remaining scientific job or future launch')
    write(ROOT/'manifests/final_supervision_disabled.json',receipt)
    schedule.update(utc=utc(),verified_status='PAUSED',phase='FINAL_CLOSED',owner_pid=None,owner_creation_time=None,
        current_operation='Final delivery; all science closed',early_check_pending=False,
        disabled_verified_receipt='manifests/final_supervision_disabled.json',last_closed_scientific_phase='autopsies')
    write(ROOT/'manifests/checkin_schedule.json',schedule,replace=True)
    ledger=read(ROOT/'manifests/resource_ledger.json')
    ledger.update(utc=utc(),supervisor_status='PAUSED_FINAL_DELIVERY',phase_state='FINAL_CLOSED',scientific_endpoint_reached=True,
        final_state='RETENTION_MEASURED_CALIBRATION_OPTIMISTIC',checkin_count=len(checks),
        checkin_schedule_state={k:schedule.get(k) for k in ('verified_status','phase','current_interval_minutes','first_firing','last_firing','count')},
        supervisor_pause_verification='manifests/final_supervision_disabled.json',final_disk_free_bytes=disk,
        finalization_engineering_only=True,iteration_executed=False)
    write(ROOT/'manifests/resource_ledger.json',ledger,replace=True)
    current=f'''# Final P10.3 handoff — {utc()}

**RETENTION_MEASURED_CALIBRATION_OPTIMISTIC.** All 436 eligible stars were evaluated under both presets. Parts A–H, the required five autopsies and final compatibility/historical integrity checks are complete. All owned science is closed. The hourly routine is PAUSED and freshly verified; the old P10 routine remains PAUSED. No further science is scheduled or authorized under this completed run.

Union in-band forced-present family recovery: P10 174/432, P8 150/432. The family funnel is 174 → 131 → 37 → 13 → 13 through B; C has eight passing families, one failing family, four not run and two propagated A unknowns. Six candidate-level C cases were run (five pass, one fail), all eligible under the fixed N_C=13 cap. Both H fits on 89 independent qualifying families have negative slopes and unstable extrapolated SNR50 crossings; the literal rule fires without yielding a useful monotonic sensitivity threshold.

Five autopsies are complete and sealed. p10.1 is costed only, never executed. Current new scientific charge: {ledger['new_queue_hours']:.9f}/31.98 h; acquisition upper charge 12,105,787,657/15,000,000,000 bytes. The two A timeouts and 24 forced-fit errors remain unknown; all 24 forced errors lie outside the search period domain. Final source/data/delivery sealing and the local commit are engineering closeout; the exported delivery receipt records the final revision.

The final DECISION, SEARCH_RETENTION, FUNNEL_RETENTION, CALIBRATION_CHECK and AUTOPSIES reports supersede all earlier running or paused handoffs below. Preserve the registered evidence; do not relaunch a worker, rerun a bootstrap for a different result, change a locked prediction, or execute an iteration. All original 531 stars are development-exposed. Part 5 needs separate authorization and independent specificity/endpoint validation.

## Assumptions for this handoff

[A] Latest user allocation/supervision amendments and fixed p10.0 rules govern. [M] Counts come from sealed receipt aggregates. [I] Signal retention does not establish planet classification or endpoint performance. The dated text below is history, not an active execution plan.

---

'''
    handoff=ROOT/'HANDOFF_P10_3.md';handoff.write_text(current+handoff.read_text(encoding='utf-8'),encoding='utf-8')
    with (ROOT/'RESUME_P10_3.md').open('a',encoding='utf-8') as f:
        f.write(f'\n{utc()} [M]: FINAL_CLOSED. All 436 paired searches, F/G/H and five autopsies complete; no owner alive. Both H rules fire with negative slopes and unstable SNR50 interpretation. New queue {ledger["new_queue_hours"]:.9f}/31.98 h; acquisition upper charge 12105787657 bytes; C free {disk["C"]/1e9:.3f} GB. Routine PAUSED and freshly verified in manifests/final_supervision_disabled.json; 34 actual check-ins retained. Final seals/local commit and export are engineering delivery; no further science or p10.1 iteration.\n')
    write(ROOT/'results/autopsy_visual_qa.json',dict(utc=utc(),status='PASS',original_plots_inspected=5,
        original_measurements_preserved=True,corrected_display_inspected=True,
        annotated_empty_panel='results/autopsies/tic29002055_family000007_display_v2.png',
        note='Four original plots readable; fifth has no finite detrended depths. Presentation-only v2 explicitly annotates the missing measurement. No clipped axes or labels in displayed images.'))
    print(json.dumps(dict(status=receipt['status'],checkins=len(checks),new_queue_hours=ledger['new_queue_hours'],disk=disk)))

if __name__=='__main__':main()
