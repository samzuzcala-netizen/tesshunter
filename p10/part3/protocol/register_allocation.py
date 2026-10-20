"""Prospective user allocation and supervision amendment; no prediction access."""
from common import REPO,ROOT,read,write,sha,utc
from registration_chain import verify
import math,csv


def main():
    verify()
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Owner still alive')
    ordered=read(ROOT/'manifests/evaluation_order.json');timing=read(ROOT/'results/timing_pilot_summary.json')
    ledger=read(ROOT/'manifests/resource_ledger.json');remaining=31.98-ledger['new_queue_hours']
    hosts=[r['tic_id'] for r in ordered['order']];pilot=[r['tic_id'] for r in ordered['pilot']]
    assert len(hosts)==len(set(hosts))==436 and len(pilot)==6 and set(pilot)<=set(hosts)
    # A deliberately conservative tail cross-check, distinct from the user's planning figures.
    waves=math.ceil(430/24);a_jobs=math.ceil(436*sum(timing['candidate_counts']['survey_p10']['n_pre_gate'])/6)-17
    tail=dict(survey_p10=waves*max(1682,timing['search']['survey_p10']['wall']['max'])/3600,
              survey_p8=waves*timing['search']['survey_p8']['wall']['max']/3600,
              stage_A=math.ceil(a_jobs/24)*max(517,timing['stageA_wall']['p90'])/3600,
              S_B=.1,forced_fits=1450*120/24/3600,matching_analysis=1.)
    tail_total=sum(tail.values())*1.25
    assert tail_total<remaining
    allocation=dict(schema='p10.3-allocation-v1',utc=utc(),authorization='Explicit user main-session allocation review in this task before further science',
        evaluation_level='all_eligible',evaluation_count=436,selected_tic_ids=hosts,
        paired_survey_p8_level='all_eligible',paired_survey_p8_count=436,paired_survey_p8_tic_ids=hosts,
        reused_pilot_tic_ids=pilot,new_jobs_per_preset=430,preset_sequence=['survey_p10','survey_p8'],
        selection_frozen=True,decision_source='User-directed prospective allocation; not selected from retention outcomes',
        prior_nested_order_sha256=sha(ROOT/'manifests/evaluation_order.json'),pilot_summary_sha256=sha(ROOT/'results/timing_pilot_summary.json'),
        planning_basis=dict(source='User-supplied planning estimates, preserved as stated',
            survey_p10_seconds_per_star=1052,survey_p8_seconds_per_star=275,stage_A_candidates_per_star=2.8,stage_A_p90_seconds=269,
            forced_families_approx=1450,forced_seconds_per_family=120,workers=24,
            component_hours=dict(survey_p10=5.2,survey_p8=1.4,stage_A=3.9,S_B=.1,forced_fits=2.,matching_analysis=1.),
            subtotal_hours=13.6,margin_factor=1.25,total_with_margin_hours=17.,claimed_C_headroom_hours=11.2),
        tail_crosscheck=dict(method='18 waves of historical P10 maximum; observed P8 maximum; 51 waves of max(historical A p90, pilot A p90); user S/B/F/analysis estimates retained; 25% margin',
            component_hours=tail,forecast_hours=tail_total,remaining_hours=remaining,fits=True,
            scope='Conservative comparison for E/A timings; S/B and forced-fit costs remain planning assumptions, not upper bounds.'),
        prediction_lock_order='Freeze membership and runtime/job manifests before launch; lock every completed preset prediction manifest after its search closes and before any Part F sidecar access.',
        scientific_thresholds_changed=False)
    write(ROOT/'manifests/allocation.json',allocation)
    policy=dict(schema='p10.3-supervision-v3',utc=utc(),authorization='Latest user amendment to section 4a supersedes the earlier sentence retaining N_C/H pauses',
        normal_interval_minutes=60,early_check_minutes=10,short_final_interval='Only when a current forecast predicts closure within the next hour',
        auto_advance=True,sequence=['search_survey_p10','search_survey_p8','funnel_A','funnel_S','funnel_B','freeze_N_C','Part_F','funnel_C','Part_H','final_delivery'],
        pause_only=['Part I stop','integrity failure','final delivery'],pause_at_N_C=False,pause_at_H=False,
        C=dict(formula='floor((remaining_hours - 3.0) * 3 / 3.4)',ledger_snapshot='Immediately after Part G B closure',reserve_hours=3.,tail_hours=3.4,max_concurrent=3,
            eligibility='TCE-matched likely-periodic B passers',ordering='Descending expected SNR; stable candidate ID tie-break',
            negative_formula_result='Record raw result; zero runnable jobs when the formula is negative',record_before_first_launch=True),
        H=dict(compute_registered_rule=True,write_five_autopsies_if_fires=True,cost_iteration_as_next_step=True,execute_p10_1_iteration=False),
        unchanged=['One attempt per scientific job','At most 24 active cores','Single-thread BLAS','31.98 new scientific union hours','15 GB cumulative acquisition','25 GB C: free floor','No sidecar access before both prediction locks','No Stage D, final tiers, packets, CTOI, push, full survey'])
    write(ROOT/'manifests/supervision_policy_v3.json',policy)
    note=f'''# User allocation and supervision amendment — {allocation['utc']}\n\n[A] The user prospectively selected all 436 eligible stars for survey_p10 and paired survey_p8, reusing the six pilot hosts for both presets. There are 430 new jobs per preset, in the existing registered nested order. survey_p10 runs first, survey_p8 second. No retention outcome selected the population.\n\n[A] The user's stated planning basis is 5.2 h P10, 1.4 h P8, 3.9 h A, 0.1 h S/B, 2.0 h forced fits and 1.0 h matching/analysis: 13.6 h times 1.25 = 17.0 h against {remaining:.6f} h remaining. Those rounded planning estimates are preserved in allocation.json. A separate tail check uses the historical P10 maximum, observed P8 maximum and historical Stage A p90; it totals {tail_total:.6f} h with margin. S/B and forced-fit planning rates remain unmeasured assumptions.\n\n[A] The latest supervision amendment supersedes the earlier same-message request to pause at N_C and H. Auto-advance through the registered sequence. At B closure record N_C = floor((remaining_hours - 3.0) * 3 / 3.4) from that ledger snapshot, order qualifying TCE-matched likely-periodic B passers by descending expected SNR, and use at most three concurrent C runs. Record the raw cap even when negative; zero jobs can run under a negative cap. Compute H, write five autopsies if its registered rule fires, and cost p10.1 only; never execute the iteration. Pause only for Part I stops, integrity failures or final delivery.\n\n[A] Complete predictions cannot exist before the remaining searches. Freeze membership, runtime inputs and planned manifests now. After each preset closes, lock every accepted candidate and its period, epoch, duration, depth, stitch SNR, partition and budget flags, including reused pilot output hashes and operational-unknown accounting. Both completed locks are mandatory before Part F opens the sidecar.\n\nNo scientific threshold, historic source or prior registration byte is changed. The original D1-D4-effective preregistration remains unchanged; this new version and the allocation/policy are pinned by registration_execution_v3.json.\n'''
    doc=ROOT/'ALLOCATION_AND_SUPERVISION_20260915.md';doc.write_text(note,encoding='utf-8')
    effective=ROOT/'PREREGISTRATION_P10_3_E20260915.md'
    effective.write_bytes((ROOT/'PREREGISTRATION_P10_3.md').read_bytes()+b'\n\n'+note.encode())
    write(ROOT/'manifests/registration_execution_v3.json',dict(utc=utc(),prior_chain='p10/part3/manifests/registration_amendments_D1_D4.json',prior_chain_sha256=sha(ROOT/'manifests/registration_amendments_D1_D4.json'),
        hashes={p.relative_to(REPO).as_posix():sha(p) for p in [ROOT/'manifests/allocation.json',ROOT/'manifests/supervision_policy_v3.json',doc,effective]},
        original_effective_preregistration_preserved=True,scientific_thresholds_changed=False))
    rows={int(r['tic_id']):r for r in csv.DictReader((ROOT/'manifests/targets_eligible.csv').open())}
    with (ROOT/'manifests/targets_evaluated.csv').open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=next(iter(rows.values())).keys());w.writeheader();w.writerows(rows[t] for t in hosts)
    print(dict(level='all_eligible',hosts=436,new_jobs_per_preset=430,user_planning_hours=17.,tail_check_hours=tail_total,remaining_hours=remaining))


if __name__=='__main__':main()
