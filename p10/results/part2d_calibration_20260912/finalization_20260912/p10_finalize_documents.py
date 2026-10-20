from pathlib import Path
import sys, json, hashlib, subprocess, time, shutil
R=Path(r'C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter')
sys.path.insert(0,str(R/'p10/protocol'))
import run_part2d_yield_projection as Y
O=Y.OUT;F=O/'finalization_20260912'
assert Y.section_zero_sha()==Y.FROZEN
paused=Y.read(F/'automation_paused_verified.json');assert paused['status']=='PAUSED' and all(paused['checks'].values())
d=Y.read(O/'stop_rule_1_decision.json');assert d['status']=='STOP_RULE_1_FAILED' and not d['proceed_to_parts_3_to_5']
assert Y.sha(R/'p10/protocol/report_part2d_stop_rule.py')==d['report_generator_sha256']
for p,h in d['inputs_sha256'].items():assert Y.sha(R/p)==h,p
# Verify the routing receipt accounts for every adapter byte after newline normalization.
routing=Y.read(O/'yield_engine_routing.json')
original=(R/'scripts/p8_expected_yield.py').read_text(encoding='utf-8')
for change in routing['edits']:
    assert original.count(change['old'])==change['count'],change['old']
    original=original.replace(change['old'],change['new'])
adapter=(R/'p10/protocol/p10_expected_yield_engine.py').read_text(encoding='utf-8')
header=adapter[:adapter.index('"""')]
assert adapter==header+original
command=[sys.executable,'-B','-m','pytest','tests/test_p10_yield_projection.py','tests/test_p10_load_bound.py','tests/test_p8_yield.py','-q']
start=time.perf_counter();p=subprocess.run(command,cwd=R,capture_output=True,text=True,encoding='utf-8')
with (F/'yield_verification_tests.log').open('x',encoding='utf-8') as f:f.write(p.stdout+p.stderr)
assert p.returncode==0 and '13 passed' in p.stdout,p.stdout+p.stderr
Y.save(F/'yield_verification_tests.json',dict(utc=Y.utc(),command=command,returncode=p.returncode,
    seconds=time.perf_counter()-start,summary='13 passed; one known optional lightkurve warning',
    adapter_fully_accounted_for_by_routing_receipt=True,
    sources_sha256={str(x.relative_to(R)):Y.sha(x) for x in [R/'p10/protocol/p10_expected_yield_engine.py',
       R/'p10/protocol/run_part2d_yield_projection.py',R/'tests/test_p10_yield_projection.py']},
    original_preflight_correction='An initial preflight referenced nonexistent src/tesshunter/rules.py before creating a model root or executing the engine. Corrected to the existing audit_rules.py; all input copies and the one numerical model execution followed that correction.'))
print(p.stdout,flush=True)
table=(O/'level_comparison_p8_p10.md').read_text(encoding='utf-8')
rp=R/'docs/RULES.md';text=rp.read_text(encoding='utf-8')
old='The full selected-preset injection calibration and Stop Rule 1 remain pending; the 600-case comparison does not establish the 2,100-job recovery curve. The original P8 result is preserved for the required side-by-side level table.'
assert text.count(old)==1 and '### 9.6' not in text
text=text.replace(old,'The full selected-preset calibration is now complete. All 2,100 searches and all 1,240 recovered-injection A/S pairs validate; the original P8 curve is preserved. Section 9.6 records the complete comparison and original Stop Rule 1 decision.')
text+='''

### 9.6 Part 2d: full calibration and Stop Rule 1 **[P10]**

**STOP.** Calibration closed on 2026-09-12 at 15:25:46 UTC. The original after-A/S SNR50 is **18.26124 [17.68572, 18.95767]**, above the required **14.0**. The central-model projected C-load range is **37.96009–69.29786**, below the 150 limit. Both conditions must pass; Parts 3–5 were not run, and the adaptive two-hour heartbeat is verified PAUSED.

All five levels use 2,100 injections and the original 1,000 individual-injection bootstrap resamples for the 16–84% intervals.

'''+table+'''
Frozen section 0.5 names a baseline of 20.19, which identifies the after-A/S level without pre-gate. Earlier operational prose used the whole pre-gated funnel name. Both are explicitly reported: 20.19 → 18.26 after A/S; 20.44 → 18.63 including the pre-gate. Both fail 14.0, and no frozen wording or criterion is changed. The original yield engine's central curve is the pre-gated whole funnel.

**Loss localization.** There are 1,240 recovered, 765 missed and 95 alias outcomes; aliases are not credited. The sequential path is 2,100 → 1,240 search → 1,184 pre-gate → 1,141 A → 952 S. Without pre-gate conditioning, A rejects 76/1,240 and bound S rejects 200/1,164 A passers (17.18%, compared with P8's 189/1,093 = 17.29%). The pre-gate removes 12 of the 964 A/S passers. Search gains 77 recoveries; the full funnel gains 56 (896 → 952). After-A SNR50 is 13.05 and rises to 18.26 after S: the retained secondary gate remains the main downstream sensitivity loss. Overlapping A criterion failures are retained in the calibration JSON; no post-hoc gate change was made.

**False alarms.** The same 300 selected-e control stars yield 709 pre-gate candidates, 45 A passers and two A+S survivors. All 709 A and 111 S records validate and their identities/decisions equal the earlier selected-e p8.0 comparison. The 66 seeded A-failure controls are excluded from FA_S. FA_S=2/300; FA_S × 2,531 = 16.873333.

**New-curve yield.** The original P8/DC15 numerical model uses the new pre-gated curve and claimed fraction 0.03 in every class. All 2,000 saved original noise records were copied byte-for-byte into P10 and verified unchanged after execution. For these stars the model predicts 21.086755 signals through the funnel (search-only 28.277649; inherited HU19 occurrence sensitivity 27.634104). Legacy low/mid/high output keys are equal because their claimed fractions are equal; they are not uncertainty bounds. The explicitly renamed P8 yield>=3 diagnostic does not decide P10 continuation.

The possible additional stars have no measured noise in this calibration. Perfect recovery and the 531 largest geometric weights of the entire 1,837-star bare-SPOC source pool bound any eventual subset of at most 531 by 31.337769 signals. This yields a central-model E_S range of 21.086755–52.424524 and expected C-load range of 37.960088–69.297857. No Part 3 population was selected and no new TCE ephemerides or candidate outcomes were opened. This range bounds the missing-population contribution under the adopted model; it is not a confidence interval or a realized-count bound. The earlier perfect-recovery all-population load bound was 148.931096.

The latest full regression was 774 passed, 1 skipped, 9 warnings, followed by ten focused correction/routing tests and three bound tests. Thirteen final yield/bound/legacy-model tests pass. Original P7 reproduction and the separately described cached/fresh P8 replay evidence remain valid. The calibration controller's schema-only validation correction preserved every worker record, numerical threshold and timing. It waited for exact original-owner closure, reused all 709 A records, and completed the remaining phases. The failed original guard report remains historical evidence.

**Assumptions and limits.** Individual-injection bootstrap intervals omit within-star dependence and population/model uncertainty. The empirical two-survivor FA rate is extrapolated unchanged. The HU19 result is the inherited occurrence-box rescaling sensitivity, with its radius/subtype assumptions, not a replacement for the central stop criterion. Later B/C/D losses and final candidate yield are unmeasured. The Part 2c alias, out-of-grid, development-exposure and suspended-timing caveats in section 9.4 remain binding.

Exact tables, all bins, decision, figure, yield/noise provenance and closed seals are under `p10/results/part2d_calibration_20260912/`; see `STOP_RULE_1.md`, `stop_rule_1_decision.json`, `full_calibration_closed_seal_20260912.json`, `expected_yield_projection_p10.json` and `yield_model/`. The calibration seal covers 15,583 files / 7,915,270,129 bytes. `finalization_20260912/automation_paused_verified.json` records the confirmed pause with the two-hour default retained. P8/P9 inputs and frozen section 0 remain unchanged.
'''
rp.write_text(text,encoding='utf-8')
hp=R/'HANDOFF_P10.md';raw=hp.read_bytes()
old_top=raw.splitlines()[2]
assert old_top.startswith(b'**Resume here: FA CALIBRATION CLOSED; INJECTION A/S RUNNING.**')
new_top=b'**FINAL STOP: original Stop Rule 1 fails.** After-A/S SNR50 is 18.26 [17.69, 18.96], above 14.0. The central-model C-load bound passes at 37.96-69.30, but both criteria are required. Parts 3-5 were not run; the adaptive two-hour heartbeat is verified PAUSED. Read the final dated entry, RESUME_P10.md and p10/results/part2d_calibration_20260912/STOP_RULE_1.md. Earlier running/pending entries are historical.'
raw=raw.replace(old_top,new_top,1)
note=f'''### Final Part 2d calibration and original Stop Rule 1: STOP, {Y.utc()} [M]

**The rerun is not justified under the original rule.** Full calibration finished 2026-09-12 15:25:46 UTC, with every required search/A/S record validated and no owner/lock remaining. The seal covers 15,583 scientific files / 7,915,270,129 bytes. Search outcomes are 1,240 recovered, 765 missed and 95 uncredited aliases on the same 2,100 original injections. The complete five-level table and 1,000-bootstrap 16–84% intervals are in docs/RULES.md 9.6 and `p10/results/part2d_calibration_20260912/STOP_RULE_1.md`.

**SNR criterion fails.** Frozen section 0.5's baseline 20.19 identifies the after-A/S level without pre-gate: **20.19277 → 18.26124 [17.68572, 18.95767]**, above 14.0. The separately reported whole-funnel value including pre-gate is **20.43521 → 18.62889 [18.05200, 19.31654]**, also above 14.0. Earlier operational naming of that whole-funnel level does not alter frozen section 0 or the stop outcome. The numerical yield follows the original P8 machinery's pre-gated curve.

**Residual loss is localized downstream to S.** Sequential counts are 2,100 → 1,240 recovered → 1,184 pre-gate → 1,141 A → 952 S. On every recovered injection, A passes 1,164 and fails 76; bound S rejects 200/1,164 (17.18%) and leaves 964 before pre-gate conditioning. Search gains 77 recoveries over P8, but the full funnel gains 56 (896 → 952). After-A SNR50 is 13.05; adding S raises it to 18.26. Bound remains the only mode that passed the frozen Part 2a negative-control requirement. No measured threshold was relaxed.

**Central workload criterion passes by a sufficient bound.** FA_S remains 2/300, excluding all seeded A-failure controls, and gives 16.873333 for 2,531 stars. The new-curve DC15 model with claimed fraction 0.03 yields 21.086755 signals for the original 2,000 stars; their 2,000 measured-noise inputs were copied byte-for-byte and remain unchanged. Search-only yield is 28.277649; the inherited HU19 occurrence sensitivity is 27.634104. Adding at most 31.337769 for up to 531 further stars gives E_S 21.086755–52.424524 and C load **37.960088–69.297857**, below 150. Both stop criteria were required, so this passing workload result cannot authorize Parts 3–5.

**Compatibility and prior choices.** The selected effective preset is e / survey_p10; bound S and strongest-peak C(a), conditional robust fallback and cadence duration floor remain frozen. Section 9.4 preserves the three-of-seven alias limitation, exact-unit EB correction, out-of-grid TIC 92743594 controls, development exposure and suspended timing. P7 remains 823 records at 0/0/0.0 with 2,513 P6 hashes unchanged. Seeded P8 cached replay is 20/20 byte-identical; fresh replay is scientifically exact but 0/20 byte-identical because timestamps/runtimes differ. The latest full suite is 774 passed/1 skipped; ten correction checks, three bound checks and thirteen final yield/bound/legacy-model checks passed. The schema-only calibration guard correction and all original worker outputs/diagnostics remain preserved.

**Operational closure.** The existing automation `continue-local-p10-execution` is verified **PAUSED** at {paused['utc']}; its normal interval remains 120 minutes and its full durable prompt begins with this final protocol stop. No duplicate routine or task was created. Evidence is `finalization_20260912/automation_paused_verified.json`. `stop_rule_1_decision.json` is the exact scientific decision. Parts 3–5 were not run and no new real/held-out outcomes or TCE ephemerides were opened. This completes the authorized branch of P10 at its original early stop. Preserve this stop on future resumes unless the user provides a new, reviewed instruction; never automatically resume the old completed queues.

**Assumptions and remaining unknowns [A].** The bootstrap resamples individual injections and omits within-star dependence. The additional-population bound uses the 531 largest geometric weights of the entire 1,837-star source pool with perfect recovery; it neither selects Part 3 stars nor invents their noise. It is an expectation bound under the central occurrence model and empirical FA extrapolation, not a confidence interval or realized-count bound. HU19 is the inherited sensitivity proxy and does not replace the central criterion. Later B/C/D survival, in-domain holdout performance and final candidate yield remain unmeasured. P8/P9 inputs and all frozen section 0 bytes remain unchanged.

'''
raw=raw.replace(b'## 0. Pre-registered decision rules',note.encode('utf-8')+b'## 0. Pre-registered decision rules',1)
hp.write_bytes(raw);assert Y.section_zero_sha()==Y.FROZEN
resume=R/'RESUME_P10.md'
entry=f'''# P10 FINAL STOP — recovery threshold failed

Recorded {Y.utc()}. **Do not resume the old queues or run Parts 3–5.** The authorized P10 branch ended at original Stop Rule 1: after-A/S SNR50 is **18.26124 [17.68572, 18.95767] > 14.0**. The whole pre-gated funnel is **18.62889 [18.05200, 19.31654]**, also above 14.0. The central projected C-load bound passes at **37.96009–69.29786 < 150**; both criteria were required. The full repair/calibration/yield results are saved, with residual sensitivity loss localized to the retained secondary gate.

All 2,100 original searches, 1,240 recovered-injection A/S pairs and five 1,000-bootstrap level fits are closed. The 15,583-file calibration seal validates; no computation owner/lock remains. The original 2,000-star new-curve yield is 21.086755 at claimed fraction 0.03 (HU19 sensitivity 27.634104); prospective E_S is bounded by 21.086755–52.424524, including up to 531 unmeasured additions. This bounds model expectations, not realized counts or statistical confidence.

**The existing adaptive routine is verified PAUSED**, with the 120-minute default retained. It was paused under the handoff's original scientific stop instruction. Its prompt now leads with the final stop; later historical execution paragraphs do not authorize another run. Do not prepare/register/restart any completed controller. Future work needs a new reviewed user instruction, while all recorded thresholds, inputs and outcome exposure remain preserved.

Read `p10/results/part2d_calibration_20260912/STOP_RULE_1.md`, `stop_rule_1_decision.json`, `expected_yield_projection_p10.json`, `full_calibration_closed_seal_20260912.json`, and `finalization_20260912/automation_paused_verified.json`; `docs/RULES.md` 9.6 and the latest dated HANDOFF entry give the complete comparison. P7/P8 compatibility is documented with the cached/fresh distinction. Parts 3–5 remain unexecuted. Earlier running/pending entries below are historical.

---

'''
resume.write_bytes(entry.encode('utf-8')+resume.read_bytes())
audit=R/'docs/AUDIT_P10.md';assert not audit.exists()
audit.write_text('''# P10 audit: stopped by original Stop Rule 1

P10's authorized execution ended at Part 2d on 2026-09-12. The repair/calibration work is complete; Parts 3–5 and their candidate/holdout evaluations were not run.

The rule required after-A/S SNR50 <=14.0 and projected C load <=150. The measured after-A/S value is **18.26124 [17.68572, 18.95767]**, so the first condition fails. The pre-gated whole-funnel value is separately **18.62889 [18.05200, 19.31654]**; it also fails. The frozen handoff's baseline 20.19 identifies the former level; earlier operational naming is disclosed, and frozen section 0 is unchanged.

All 2,100 original injections completed successfully, with 1,240 recovered, 765 missed and 95 uncredited aliases. A passes 1,164 and S passes 964 of those; the full pre-gated path leaves 952. Bound S rejects 200/1,164 A passers, the main remaining downstream sensitivity loss. Recovery improves, but insufficiently under the original threshold.

FA_S=2/300, excluding the seeded A-failure sample. The original P8/DC15 numerical model, new pre-gated curve and claimed fraction 0.03 yield 21.086755 signals on the original 2,000 stars. Their saved measured-noise inputs remain byte-identical. HU19 sensitivity is 27.634104; search-only yield is 28.277649. Up to 531 unmeasured additions contribute at most 31.337769 under the recorded geometric bound. The central C-load expectation range is 37.960088–69.297857, which satisfies the workload criterion but does not override the independent recovery failure.

The complete level table, bootstrap intervals, A failures, S modes, FA census, timing and bin diagnostics are in `../p10/results/part2d_calibration_20260912/STOP_RULE_1.md`, `COMPLETENESS_P10.md` and `stop_rule_1_decision.json`. The full calibration seal hashes 15,583 files / 7,915,270,129 bytes. `yield_model/` preserves the original-noise copies, routing, source/input hashes, one numerical execution and a separate closed seal.

P7 reproduces 823 records at 0/0/0.0, preserving 2,513 P6 hashes. The seeded cached P8 replay is 20/20 byte-identical; separate fresh replay is scientifically exact with differing timestamps/runtimes. Latest full regression: 774 passed, 1 skipped; later correction and bound checks pass, and 13 final yield/bound/legacy-model tests pass. The calibration schema-only guard recovery reused every completed A record after verified original-owner closure. No original worker threshold or result was changed.

The bound secondary mode, selected e search, strongest-peak C(a), conditional robust fallback and one-cadence duration floor remain the recorded choices. The three-of-seven alias-control passes, two out-of-grid TIC 92743594 controls, catalogue-windowed development exposure, corrected exact-unit EB run and original suspended injection timings remain disclosed in RULES.md section 9 and the handoff.

The expectation range is not a confidence interval or realized-count bound. The bootstrap omits within-star dependence; occurrence shape, empirical FA extrapolation and later B/C/D survival remain limitations. No new Part 3 stars were selected and no later real/held-out outcomes or TCE ephemerides were opened. There is no new detection, confirmed planet or submission.

The existing two-hour adaptive heartbeat is verified PAUSED under the original stop instruction. `../p10/results/part2d_calibration_20260912/finalization_20260912/automation_paused_verified.json` records the exact schedule/prompt verification. Resume instructions now lead with the final stop; previous progress entries remain historical. All work is retained locally without a push or external submission.
''',encoding='utf-8')
with (O/'STOP_RULE_1.md').open('a',encoding='utf-8') as f:
    f.write(f"\nOperational confirmation: the existing adaptive heartbeat was verified **PAUSED** at {paused['utc']}, retaining its 120-minute default. See `finalization_20260912/automation_paused_verified.json`.\n")
assert Y.section_zero_sha()==Y.FROZEN
Y.save(F/'document_update_verification.json',dict(utc=Y.utc(),status='final_stop_documents_prepared',
    section_0_unchanged=True,section_0_sha256=Y.FROZEN,automation_verified_paused=True,
    report_figure_visually_reviewed=True,
    files_sha256={str(p.relative_to(R)):Y.sha(p) for p in [hp,resume,rp,audit,O/'STOP_RULE_1.md',O/'snr50_comparison.png']}))
shutil.copy2(Path(__file__),F/Path(__file__).name)
print('Final stop documents updated; frozen section 0 unchanged.',flush=True)
