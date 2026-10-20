"""Seal the completed P11 input-gate stop; never dispatch downstream work."""
from collections import Counter
from datetime import datetime,timezone
import csv
import heapq
import json
import re
import shutil
import time
import numpy as np
from astropy.time import Time
from scipy.stats import beta
from common import REPO,P11,DATA,utc,sha,read,write,append_event
from analyze_audit import resources


def textfile(path,text):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')


def interval(stat,percent=False):
    factor=100 if percent else 1
    lo,hi=stat['host_bootstrap_95_interval']
    return f"{factor*stat['median']:.3f} [{factor*lo:.3f}, {factor*hi:.3f}]"


def historical_schedule():
    jobs=[]
    for kind in ['inj','fa']:
        for path in sorted((REPO/f'data/survey/runs/p10_2b/e_{kind}/results').glob('*.json')):
            r=read(path);jobs.append(dict(job_id=r['job_id'],wall_seconds=r['wall_s'],path=path.relative_to(REPO).as_posix(),sha256=sha(path)))
    if len(jobs)!=900:raise RuntimeError('Historical timing census mismatch')
    schedules={}
    for workers in (16,24):
        heap=[0.0]*workers
        for job in jobs:
            start=heapq.heappop(heap);heapq.heappush(heap,start+job['wall_seconds'])
        schedules[str(workers)]=max(heap)/3600
    result=dict(utc=utc(),job_count=900,sum_job_hours=sum(j['wall_seconds'] for j in jobs)/3600,
        FIFO_injections_then_uninjected_by_job_id_simulated_queue_hours=schedules,jobs=jobs,
        scope='Historical P10 e input/job-time distribution only, including its observed tail; no new timing measurement, R1 forecast, CPU estimate or validation launch projection.',
        next_step='After corrected/common data exists, measure new-input preparation and R1/A/S/C throughput before pricing any fresh validation. R1 confirmation overhead and C cost are currently unknown.')
    write(P11/'results/costed_next_step.json',result);return result


def release_table():
    observations=[]
    for p in sorted((DATA/'acquisition').glob('mast_survey_*.json')):observations+=read(p)['data']
    cut=Time('2026-09-05T00:00:00',format='isot',scale='utc').mjd
    new={}
    for r in observations:
        s=int(r.get('sequence_number') or -1);a=r['provenance_name'];exp=float(r.get('t_exptime') or 1e9)
        if 56<=s<=104 and 100<=exp<=300 and (r.get('t_obs_release') or -1)>=cut:
            new.setdefault(int(r['target_name']),set()).add(s)
    records=read(P11/'results/coverage/per_target_inventory.json')
    out=P11/'results/coverage/new_release_coverage.csv'
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['tic_id','metadata_public_release_since_2026_09_05_sectors','newly_verified_usable_sectors','note']);w.writeheader()
        for r in records:w.writerow(dict(tic_id=r['tic_id'],metadata_public_release_since_2026_09_05_sectors=','.join(map(str,sorted(new.get(r['tic_id'],set())))),
            newly_verified_usable_sectors='',note='No new usable sector established; original release dates do not date overwritten files.'))
    return dict(targets_with_metadata_public_release_since_2026_09_05=len(new),targets_with_newly_verified_usable_coverage=0)


def main():
    final=read(P11/'results/final/entry.json');integrity=read(P11/'results/historical_integrity.json')
    assert final['pytest']['exit_code']==0 and final['p9_original_restored']
    assert final['p9_verifier']['failures']==['baseline_git_HEAD_unchanged'] and integrity['status']=='PASS'
    ntests=int(re.search(r'(\d+) passed', (P11/'results/final/pytest.log').read_text(encoding='utf-8')).group(1))
    coverage=read(P11/'results/coverage/summary.json');policy=read(P11/'protocol/MAIN_INPUT_POLICY.json')
    noise=read(P11/'results/noise_summary/summary.json');stats=noise['statistics']
    allnoise=[read(p) for p in (P11/'results/noise_v2').glob('tic*.json')]
    assert len(allnoise)==60 and all(r['status']=='OK' for r in allnoise)
    for name,digest in read(P11/'protocol/registration_seal.json')['hashes'].items():assert sha(REPO/name)==digest,name
    cost=historical_schedule();releases=release_table();resource=resources()
    first_clock=datetime(2026,9,12,19,55,33,tzinfo=timezone.utc)
    resource['charged_queue_seconds_conservative']=(datetime.now(timezone.utc)-first_clock).total_seconds()+120
    resource['charged_queue_hours_conservative']=resource['charged_queue_seconds_conservative']/3600
    resource['charge_method']='Conservatively charge the entire first recorded clock-to-close span plus 120 seconds for preceding entry inspection. This overcounts code-writing, tests and idle time, and covers short interactive read-only diagnostics omitted from the per-job union.'
    resource['scientific_union_precision']='Recorded durable jobs only. The conservative charge, not this lower accounting figure, is used to certify the audit/overall cap.'
    resource['measured_completed_noise_CPU_seconds']=sum(r['cpu_seconds'] for r in allnoise)
    resource['free_disk_bytes_at_close']=shutil.disk_usage(REPO).free
    resource['audit_budget_pass_conservatively']=resource['charged_queue_seconds_conservative']<7200
    assert resource['audit_budget_pass_conservatively'] and not resource['unclosed']
    write(P11/'results/resource_accounting.json',resource)
    state='NO_QUALIFIED_GAIN';bad=len(coverage['development_hosts_failing_even_any_author_three_sector_upper_bound']);bad_inj=coverage['comparison_injections_on_hosts_failing_any_author_upper_bound']
    stages=dict(A='COMPLETE_INPUT_GATE_STOP',B='NOT_RUN_REQUIRED_COMMON_INPUTS_INCOMPLETE',C='NOT_IMPLEMENTED_OR_MEASURED_AFTER_INPUT_STOP',
                D='NOT_DRAWN_OR_RUN',E='UNESTABLISHED_EVALUATION_INCOMPLETE')
    decision=dict(utc=utc(),state=state,evaluation_status='EVALUATION_INCOMPLETE_DATA_LIMIT',reason_code='REQUIRED_COMMON_INPUTS_INCOMPLETE',
        reason=f'At least {bad}/300 required development hosts and {bad_inj}/600 comparison injections cannot meet three unaffected sectors even under the optimistic all-author public metadata bound.',
        new_recovery_gain_measured=False,scientific_efficacy_failure_claimed=False,phases=stages,validation_hosts_drawn=0,validation_injections_drawn=0,
        fresh_binary_challenges_drawn=0,new_search_variants_run=0,new_C_measurements=0,aperture_pixel_pilot_hosts=0,
        cached_hosts_with_three_sectors=policy['cached_hosts_with_three_sectors'],
        historical_contaminants='P10 C(a) persistent passes only: eb_tic178858648_candidate1, eb_tic237116051_candidate1, eb_tic272598447_candidate1. No P11 contamination rate was measured.',
        downstream_unmeasured=['B/C joint sensitivity and workload','fresh astrophysical challenge performance','fresh validation sensitivity','endpoint/D reliability','full-survey yield','candidate submission eligibility'],
        tests=dict(passed=ntests,skipped=1,P9_content_checks_passed=396,P9_expected_failure='baseline_git_HEAD_unchanged',historical_integrity=integrity['status']),
        resource_accounting=resource,actual_submission_eligible=False,automatic_continuation=False)
    write(P11/'results/decision.json',decision)
    write(P11/'results/validation_status.json',dict(state='NOT_REACHED_INPUT_GATE_STOP',predictions_frozen=False,truth_drawn=False,
        cohort_selected=False,paired_runs=0,reason=decision['reason'],reserved_531_ephemerides_opened=False,
        no_joint_policy_selected=True,interpretation='Absent validation artifacts are intentional at this authorized early stop; no empty predictions are presented as a completed evaluation.'))
    write(P11/'results/phase_status.json',stages)
    time_summary=read(P11/'results/peer_timing_quality_filtered.json')['sectors']
    total_models=read(P11/'results/instrument_noise_model.json')['rows'];model_count=sum(r['status']=='MEASURED_MODEL_DIAGNOSTIC' for r in total_models)
    h=float(resource['charged_queue_hours_conservative']);download=resource['acquired_bytes']/1e6
    audit=f'''# P11 input audit — evaluation stopped on common coverage

Recorded {decision['utc']}. The initial audit is complete. The main search/S/C experiment was not launched because its prescribed 300-host/600-injection development comparison cannot be supplied with qualifying common inputs. This is a data-limited incomplete evaluation, not a negative recovery result.

## Provenance and coverage

All **300 development hosts** were inventoried, including **8,349 raw product arrays** and their original FITS sources. TIME, selected flux, SAP and quality match exactly after reproducing Lightkurve's removal of nonfinite-TIME rows. The initial audit-reader mismatch and its correction are preserved in `results/input_inventory/`, `input_inventory_v2/` and the source snapshots; the historical arrays were never repaired in place.

All **437 cached QLP products from sectors 74–79** match corrected v02 source timestamps. The current official MAST notice still marks sectors 99–104 as awaiting corrected redelivery. Six metadata-selected fresh downloads, one per sector, have TIME and DET_FLUX identical to the cache. This checks those fixtures; it does not prove every file's redelivery state. A v01 filename by itself was never used to diagnose bad timestamps. [MAST release notices](https://archive.stsci.edu/hlsp/qlp)

The independent same-CADENCENO comparison contains **1,563 QLP/TESS-SPOC pairs**. After both P10 quality masks, sector 80 has 51/51 pairs with discrepancies exceeding 100 seconds; median offsets range **166.24–205.78 seconds**. Sector 83 has 47/47 pairs with some offsets above 10 seconds, though their medians remain near two seconds. Sector 85 has 42/54 pairs with offsets above 100 seconds. These are unresolved timing discrepancies, not transit-derived correction recipes. Both time standards and reference headers, raw extrema and quality selections are archived. No catalogue transit period, flux correlation or fitted time shift was used.

The frozen common policy excludes QLP sectors **80, 83, 85 and 99–104**, retains verified corrected 74–79 products, and preserves the original author preference and cadence/preparation rules. **241/300 cached hosts** have at least three remaining sectors; 59 do not. That count is optimistic because the original native-FFI and strict-minority two-minute requirements are additional conditions.

Current metadata was queried for all **2,000 original targets**, yielding 80,837 observation records. Even before the extra 80/83/85 exclusions, **58/300 development hosts** have fewer than three unaffected sectors under an optimistic *any-author* availability bound; **104/600 fixed comparison injections** are on those hosts. The native-FFI population bound fails for 64 hosts / 114 comparison injections. These are input-availability failures, not missed injected planets.

Six targets have sector 69 in current metadata but absent from the cached usable index; one is a development host. All six records carry a **June 2, 2025** public release date, so they are cache omissions rather than demonstrated September coverage growth. Metadata identifies {releases['targets_with_metadata_public_release_since_2026_09_05']} targets with a qualifying observation release date on or after September 5, 2026 within sectors 56–104. **Zero newly delivered usable sectors were established per target.** The full per-target tables distinguish availability, dated releases and verified usability. Original release dates cannot date an overwritten product. New metadata outside the frozen sector ceiling is disclosed in the raw inventory and not silently added.

No new real-candidate outcomes, reserved 531-star ephemerides or fresh validation hosts were opened. No conclusion is drawn about the size of a potential fresh validation pool.

## Transit-scale noise and preservation

All **60 registered audit hosts** completed: 30 at Tmag 13.5–14.0, 15 at 13.0–13.5 and 15 at 12.5–13.0. The tables record QLP before/from sector 94, source crowding, raw variability, quality, duty cycle and failures. QLP's sector-94 transition uses TGLC photometry. [MIT QLP notes](https://tess.mit.edu/qlp/)

These are descriptive cached-flux measurements. The subsequently identified 80/83/85 timing caveats remain attached to those measurements; they are not claimed as a successful common-input experiment. Each star received one registered exposure-integrated batman preservation signal, multiplied into SAP and corrected streams before detrending. These 60 engineering signals are not the proposed 1,050 validation injections.

Numbers below are medians over hosts, with 95% intervals from 10,000 bootstrap resamples within the fixed magnitude strata. They describe the deliberate 30/15/15 audit allocation, not a population-weighted survey estimate.

| Measurement | Median [95% host interval] |
|---|---:|
| Point scatter, ppt | {interval(stats['point_scatter_ppt'])} |
| 0.5-hour scatter, ppt | {interval(stats['noise_0.5h_ppt'])} |
| 1-hour scatter, ppt | {interval(stats['noise_1h_ppt'])} |
| 2-hour scatter, ppt | {interval(stats['noise_2h_ppt'])} |
| 4-hour scatter, ppt | {interval(stats['noise_4h_ppt'])} |
| 1-hour red-noise inflation | {interval(stats['red_1h'])} |
| Default injected depth retained, % | {interval(stats['depth_retained'],True)} |

![Noise and preservation](results/noise_summary/noise_audit.png)

The supplied QLP small aperture is available on **53/60 hosts**. On matched star/sector/time samples its median one-hour noise ratio to default is **{interval(stats['QLP_small_ratio_1h'])}**, about **36.1% lower noise**. Its median injected-depth retention is **{interval(stats['QLP_small_depth_retained'],True)}%**, below 95%. The large-aperture noise ratio is {interval(stats['QLP_large_ratio_1h'])}; SAP/default is {interval(stats['SAP_ratio_1h'])}. Every per-sector artifact tail and retention failure remains in the raw tables. A median zero tail difference or degenerate bootstrap is not evidence of zero artifact risk or proof of a no-worse tail.

Flux-level multiplication imposes the same fractional signal in each aperture. It cannot test real target throughput losses, changing dilution, background subtraction in pixels or centroid localization. **No TESScut/pixel pilot was run and no production extractor or aperture change is recommended for adoption.** The supplied small aperture is a useful later test target; it does not establish the joint >=15% noise / >=95% depth / no-worse-artifact requirement.

The physical noise supplement measures **{model_count}/{len(total_models)} star-sector count-noise models** using source electrons, summed sky, aperture area, live integration/read counts and the actual READNOIA–D calibration. The amplifier range is reported instead of guessing a CCD output; crowding scaling and cosmic-ray/cotrending limitations are explicit. QLP products lacking joint physical calibration remain unmeasurable. This supplement supersedes the initial compact-header placeholder, which omitted the amplifier/live-time keywords. A photon-only floor is reported beside the total model, never substituted for it. [Mission data products](https://heasarc.gsfc.nasa.gov/docs/tess/data-products.html), [cosmic-ray processing](https://heasarc.gsfc.nasa.gov/docs/tess/TESS-CosmicRayPrimer.html)

## Cost and integrity

Downloads total **{download:.3f} MB**, against 15 GB. Free disk is **{resource['free_disk_bytes_at_close']/1e9:.2f} GB**, above the 30 GB headroom. The successful noise controller used four single-thread workers after a measured **354.9 MB** memory pilot. Median / p90 / maximum host wall times were **16.63 / 37.34 / 43.60 seconds**. These are photometry-audit timings, not C_local benchmarks.

Durable scientific-job intervals total about **{resource['scientific_union_seconds']/60:.2f} minutes**. For budget certification, charge **{h:.3f} queue-hours conservatively**, covering the entire inspection-to-close span plus an initial allowance, including uninstrumented short diagnostics and engineering time. This remains below both the 2-hour audit cap and 48-hour experiment cap. The failed import attempt's 64.89 seconds and all original failed records are preserved. Complete process-tree CPU for those failed imports is unavailable; no C speed or whole-funnel CPU claim is made.

Final regression: **{ntests} passed, 1 skipped**. The P9 verifier has **396 passing content checks and only the expected HEAD-equality failure**, and its old receipt was restored byte for byte in a finally block. All **554 registered source/evidence/index hashes**, **15,583 sealed P10 calibration files**, and **16,698 raw/FITS files** verify unchanged. The old named configurations and P10's failed 18.26124-versus-14 stop remain intact.

## Costed next step, outside this execution

Restore authoritative comparable input coverage before registering another efficacy comparison. The six new release checks show the still-pending products cannot currently supply that repair. The currently missing sector-69 alternatives are historical availability, not a new release. Do not relabel a reduced development sample as the required original 300/600 population.

For scale, the full historical 900-job P10 e timing distribution sums to **{cost['sum_job_hours']:.2f} job-hours**. A FIFO simulation using each recorded job time and its tail takes **{cost['FIFO_injections_then_uninjected_by_job_id_simulated_queue_hours']['16']:.2f} hours at 16 workers**, or **{cost['FIFO_injections_then_uninjected_by_job_id_simulated_queue_hours']['24']:.2f} hours at 24**, before new A/S/C work. This is a historical scheduling scenario, not a new-input performance forecast. R1 confirmation cost and C_local throughput remain unmeasured, so a validation affordability projection cannot yet be justified. No follow-on experiment or automation was started.
'''
    textfile(P11/'INPUT_AUDIT.md',audit)
    decision_text=f'''# P11 FINAL STOP — {state}

**Evaluation incomplete: data-limited input gate.** P11 executed the registered Part A audit and stopped at the proposal's common-input endpoint. No new recovery gain was established, and no scientific efficacy failure is claimed.

At least **{bad}/300 required development hosts** cannot meet three unaffected sectors even under an optimistic current all-author metadata bound. They contain **{bad_inj}/600 fixed comparison injections**. The frozen cached policy leaves **241/300** with at least three sectors; native-FFI/minority-targeting criteria remain additional requirements. Corrected QLP 99–104 delivery is still unverified, and six current downloads preserve the old timestamps. Independent timing discrepancies in sectors 80/83/85 also remain unresolved. The required original paired population is therefore unavailable under the audited policy.

What was gained: a complete 300-host/8,349-product provenance audit, 2,000-target public coverage inventory, 60-host noise/preservation evaluation, and a measured small-aperture noise advantage worth a later controlled test. Its 93.9% median flux-injection retention and absent pixel validation do not qualify a photometry change.

Cost: **{download:.3f} MB acquired; {h:.3f} queue-hours conservatively charged**, including failed attempts and engineering/diagnostic allowance; four scientific workers maximum. Logged scientific-job union is separately reported in `results/resource_accounting.json`. There were **zero search, C_local, broad-TLS-reference or validation runs**.

Which contaminants survived: **no new P11 contaminant route was measured**. P10's existing C(a) passes remain `eb_tic178858648_candidate1`, `eb_tic237116051_candidate1` and `eb_tic272598447_candidate1`. The historical 40 S controls and 41 C candidates were not falsely joined by TIC. Their outcomes cannot establish P11's joint leakage rate.

Downstream claims still unmeasured: complete-funnel recovery, joint S/B/C discrimination, fresh EB/blend challenges, natural-control workload, C_local cost, fresh validation and D/endpoint reliability. TOI-762 A b and TOI-122 b remain confirmed planets rejected by P10's endpoint tiers; TIC 144277542 retains the artifact-KILL-to-SUBMIT rescoring risk. No tier was retuned. P10's original stop, including SNR50 18.26124 >14, remains intact.

Validation was not selected, injected or scored. No full survey, candidate submission, push, background wakeup or follow-on run occurred. This is the final state of the authorized P11 execution.

Validation of completed work: **{ntests} tests passed, 1 skipped**; P9 **396 content checks pass**, only the expected HEAD mismatch remains, and its original verification bytes are restored. Historical content checks pass without modification. See `INPUT_AUDIT.md`, `results/decision.json`, `results/historical_integrity.json` and `manifests/final_freeze.json`.
'''
    textfile(P11/'DECISION_P11.md',decision_text)
    textfile(P11/'SEARCH_ALTERNATIVES.md','''# Search alternatives — not reached

P11 stopped at the Part A common-input gate. R0/R1/R2 comparisons, alternative retention, masking snapshots and allocator admission were not run or implemented. No gain is inferred from the historical 52 ranking-loss cases or 124 witnesses. Their P10 files and hashes remain preserved. The frozen baseline remains survey_p10/e with bound S. See DECISION_P11.md and results/phase_status.json.
''')
    textfile(P11/'C_LOCAL.md','''# C_local — not reached

No C_local architecture was implemented, calibrated or timed after the input stop. The D/E grid, S0/S1/S2 families and contractual boundaries in the prospective registration are proposals, not measured or selected policies. No local-template implementation seal or joint-policy freeze was created. The historical 40 secondary controls and 41 EB C records were not joined by host alone; no missing blend measurement was inferred. No broad TLS references ran. Validation predictions, evaluator truth and paired efficacy tables are absent because this permitted phase was not reached. See results/validation_status.json.
''')
    resume=f'''# P11 FINAL STOP — NO_QUALIFIED_GAIN; evaluation incomplete

Closed {decision['utc']} at the declared data/input limit. No P11 science controller remains active. **Do not resume these completed audit queues or launch Parts B–D.** The required common 300-host/600-injection comparison is unavailable under the audited timing/coverage policy. Read DECISION_P11.md first, then INPUT_AUDIT.md and results/decision.json.

The 60-host audit is complete, including the preserved failed import attempt and corrected reader comparison. Final tests: {ntests} passed, one skipped. Historical P9/P10/raw content checks pass; P9's expected HEAD mismatch is preserved. No P10 controller or automation was started. There is no finalist, validation cohort, validation truth draw or performance claim.

All future efficacy work requires a separate reviewed protocol once authoritative/common inputs are available. Preserve all records, source snapshots, seeds, manifests and exposure ledgers. No automatic continuation is authorized.
'''
    textfile(P11/'RESUME_P11.md',resume)
    textfile(P11/'HANDOFF_P11.md',resume+'''
## Durable evidence and reproduction

Repository is the original tess-exoplanet-candidate-hunter checkout. Use the verified existing `C:\\Users\\seanj\\Downloads\\tesshunter_venv\\Scripts\\python.exe`; no environment replacement was installed. The `protocol/` directory contains the runnable audit, metadata acquisition, provenance verification and analysis code. `protocol/registration_seal.json` preserves the prospective design; `protocol/MAIN_INPUT_POLICY.json` is the final input policy, not a validation freeze.

`results/input_inventory/` preserves the initial source-reader diagnostic; `input_inventory_v2/` reproduces Lightkurve's finite-TIME selection exactly. `results/noise/` and `noise_attempt1_stop.json` preserve the module-shadowing failure. The operationally corrected, source-sealed run is `results/noise_v2/`; its 60 completed timings are immutable. `instrument_noise_model.json` supplements the abbreviated header inventory. `peer_timing_quality_filtered.json` holds independent timing witnesses. The original maps and downloads are in `data/survey/p11/` and are sealed by `manifests/data_files.json`.

To verify on this existing checkout, run `python p11/protocol/integrity_check.py`. For a new compatibility receipt, use `python p11/protocol/entry_check.py --label <new-unique-label> --include-p11`; it preserves/restores the P9 verification file in a finally block. Completed source/measurement files should not be regenerated in place. The archive requires the original repository inputs identified by the recorded hashes; it is not a portable copy of every historical TESS FITS file.

The initial audit-magnitude subset includes 60 deliberate metadata selections, so its bootstrap describes that allocation. Small-aperture gain is descriptive and fails the depth/pixel qualification requirements. Later search, C, validation and endpoint results are unmeasured. The local execution commits only explicit P11 artifacts; no push is authorized.
''')
    append_event(P11/'manifests/exposure_ledger.jsonl',dict(event='final_input_gate_stop',state=state,development_noise_hosts_measured=60,
        new_validation_hosts=0,validation_truth_drawn=False,reserved_531_ephemerides_opened=False,new_real_candidate_outcomes_opened=False,
        independent_timing_discrepancies='QLP 80/83/85; timestamps never tuned against flux',no_new_statistical_family_after_C_results='No C results exist'))
    data_files={p.relative_to(REPO).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in DATA.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    write(P11/'manifests/data_files.json',data_files)
    files=[p for p in P11.rglob('*') if p.is_file() and 'work' not in p.relative_to(P11).parts and '__pycache__' not in p.parts and p.name!='final_freeze.json']
    write(P11/'manifests/final_freeze.json',dict(utc=utc(),state=state,kind='Completed input-audit evidence freeze; no validation selection or scoring',
        source_and_evidence={p.relative_to(REPO).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in files},
        data_manifest_sha256=sha(P11/'manifests/data_files.json'),all_new_scientific_jobs_closed=True))
    print(state,'evaluation incomplete; final evidence sealed',len(files),'P11 artifacts,',len(data_files),'data files',flush=True)


if __name__=='__main__':main()
