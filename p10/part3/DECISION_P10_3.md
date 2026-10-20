# RETENTION_MEASURED_CALIBRATION_OPTIMISTIC

[M] P10.3 is complete through the registered measured sequence, including the five required autopsies. The hourly routine is disabled and verified, all owned scientific processes are closed, and the old P10 routine remains paused. No Part I stop fired. The user-authorized automatic continuation ends at this final delivery.

## Populations actually evaluated

[M] Original list: **531** bare-SPOC-TCE domain stars. Input-eligible: **436** after 58 Gaia exclusions and 37 verified-coverage exclusions. Evaluated: **436 under each preset**, with six timing-pilot hosts reused and 430 new hosts per preset. All 473 Gaia-passing stars pass the corrected FFI-majority cut. There are 2,363 evaluated TCE rows, 1,449 distinct period families and 503 in-band families. All original 531 stars are development-exposed from Part F and cannot be reused as a holdout.

## Search retention


| Stratum | Preset | Present in-band family recovery; 95% CI | All in-band family recovery; 95% CI |
|---|---|---|---|
| INDEPENDENT | survey_p10 | 156/377; 41.379% [35.216, 47.859] | 168/434; 38.710% [33.196, 44.529] |
| INDEPENDENT | survey_p8 | 138/377; 36.605% [30.690, 42.857] | 147/434; 33.871% [28.542, 39.535] |
| OVERLAPPING | survey_p10 | 65/112; 58.036% [48.958, 67.708] | 67/129; 51.938% [42.675, 61.538] |
| OVERLAPPING | survey_p8 | 56/112; 50.000% [40.833, 59.804] | 58/129; 44.961% [35.861, 54.478] |
| UNION | survey_p10 | 174/432; 40.278% [34.473, 46.437] | 187/503; 37.177% [31.886, 42.857] |
| UNION | survey_p8 | 150/432; 34.722% [29.241, 40.594] | 160/503; 31.809% [26.839, 37.177] |



[M] The union present-signal paired advantage is **+5.556 percentage points [2.494, 8.772]** for P10 over P8. Exact versus alias recovery and every model-SNR, expected-SNR, period and raw-row table are in `SEARCH_RETENTION_P10_3.md`. All fractions use the registered 10,000 whole-host bootstrap. Absence is separated from a present-signal miss; outside-domain families are not search failures.

## Early-funnel retention and attributed rejections


| Stage | At risk | Pass | New known fail | Cumulative unknown | C not run | Unknown/not run at risk | Conditional retention; 95% CI | Cumulative retention; 95% CI |
|---|---|---|---|---|---|---|---|---|
| search | 432 | 174 | 258 | 0 | 0 | 0 | 174/432; 40.278% [34.473, 46.437] | 174/432; 40.278% [34.473, 46.437] |
| pre_gate | 174 | 131 | 43 | 0 | 0 | 0 | 131/174; 75.287% [67.307, 82.840] | 131/432; 30.324% [24.784, 36.364] |
| A | 131 | 37 | 92 | 2 | 0 | 2 | 37/129; 28.682% [19.328, 38.637] | 37/430; 8.605% [5.529, 12.153] |
| S | 37 | 13 | 24 | 2 | 0 | 0 | 13/37; 35.135% [14.706, 55.263] | 13/430; 3.023% [1.084, 5.459] |
| B | 13 | 13 | 0 | 2 | 0 | 0 | 13/13; 100.000% [100.000, 100.000]; valid 9997 | 13/430; 3.023% [1.084, 5.459] |
| C | 13 | 8 | 1 | 2 | 4 | 4 | 8/9; 88.889% [50.000, 100.000]; valid 9940 | 8/426; 1.878% [0.237, 4.028] |



[M] Of 174 recovered union present families, pre-gate removes 43. Stage A removes a further 92 and leaves two unknown; bound S removes 24; B removes none. Thirteen families reach B. C has eight passing families, one failing family, four not run and the two propagated A unknowns. Candidate-level C used six runs (five PASS, one FAIL), because multiple alias-associated families can share one candidate. N_C was fixed at 13 from the B-closure ledger; all six qualifying candidates were tested. Eighteen unmatched and five nonqualifying B survivors were excluded by the registered selection, not by capacity.

[M] `FUNNEL_RETENTION_P10_3.md` gives every recorded A criterion, S bound-mode reason, per-loss candidate path and expected-SNR comparison with historic injections. These are rejections of periodic-signal associations, not demonstrated losses of planets.

## Natural load


| Stage | Candidates passed | Candidates per evaluated host; 95% CI |
|---|---|---|
| accepted | 4328 | 4328/436; 9.927 [9.486, 10.342] |
| pre_gate | 1104 | 1104/436; 2.532 [2.319, 2.750] |
| A | 293 | 293/436; 0.672 [0.553, 0.798] |
| S | 29 | 29/436; 0.067 [0.044, 0.094] |
| B | 29 | 29/436; 0.067 [0.044, 0.094] |
| C | 5 | 5/436; 0.011 [0.002, 0.023] |



[P10, I] Historic control references are 11.65 accepted, 2.36 pre-gate, 0.150 A and 0.0067 S per host. The observed A/S load is higher in this selected TCE population. Specificity cannot be inferred from those count differences.

## Part H rule and autopsies

**[M] Both literal SNR50 rules fire on 89 qualifying independent families on 74 hosts. [I] Both fitted slopes are negative; the crossings are unstable extrapolations and are not usable sensitivity thresholds.** The formal state preserves the registered trigger without claiming a reliable physical estimate of the injection-calibration shortfall.


| Preset | Slope b | SNR50 | 95% finite-bootstrap interval | Rule |
|---|---|---|---|---|
| survey_p10 | -0.16681864 | 72524.982 | [8.5345427e-19, 1.0742566e+22] | OPTIMISTIC |
| survey_p8 | -0.01632074 | 1.9940496e+28 | [4.5634333e-18, 1.1679795e+22] | OPTIMISTIC |



[M] Each fit has 9,965 finite bootstrap crossings and 35 nonfinite crossings. Four of the five highest-SNR misses have local P10 internal-gate passers that lose recorded selection. Three nominal TCE durations exceed the fixed search maximum; four nominal epochs are uncheckable. The complete five autopsies preserve the original searches and primary forced fits. Ranking is a shared contributor, not a proven single cause or a measured alternative recovery.

[A, M] **p10.1 was costed only, as the user directed.** The stipulated subset benchmark plus a conservative full 436-host rerun and 25% margin costs 22.355 h for P10 or 19.464 h for P8, against 15.825 h remaining. Even these planning costs exceed the available allocation; the full 2,100-injection revalidation cost is not newly measured. The six-host proxy conservatively charges the entire paired-pilot interval to each proposed changed preset. No iteration was launched.

## Operational unknowns by stage


| Stage | Operational unknowns | Disposition |
|---|---|---|
| Final acquisition | 0 | 473 indices; 11,532 products; final recorded product failures zero |
| survey_p10 / survey_p8 | 0 / 0 | All 436 hosts complete in each locked manifest |
| Stage A | 2 | tic177352028_p01 and tic33866201_p01; one attempt, no scientific retry |
| S / B / C | 0 / 0 / 0 | Two A family unknowns remain propagated downstream |
| Part F forced fits | 24 | All outside 0.5–30 d; no measured in- or out-of-transit level; never absent or missed |
| Autopsies | 0 | Five complete; one nominal-event detrended-depth series is unmeasured and explicitly annotated |



## Resource accounting


| Resource | Final measured/charged value |
|---|---|
| New union scientific queue-hours, failures and stalls included | 16.155157144 / 31.98 h |
| Prior cumulative hours | 16.0198 h |
| Cumulative charged scientific hours | 32.174957144 / 48 h |
| Remaining new allocation | 15.824842856 h |
| Cumulative measured acquisition bytes | 12105580809 |
| Cumulative conservative acquisition charge | 12105787657 / 15000000000 bytes |
| Unreconciled acquisition reservation included in upper charge | 206848 |
| C free at final shutdown | 49.096 GB |
| D free at final shutdown | 972.651 GB |
| Routine check-ins | 34; normal interval 60 minutes; early/final exceptions preserved |
| First / last recorded firing | 2026-09-14T17:20:24.938920+00:00 / 2026-09-15T22:21:09.634304+00:00 |
| Current supervision | DISABLED_VERIFIED |



[M] The per-interval ledger includes downloads, preparation, searches, failed/timed-out jobs, forced fits, C and descriptive analysis. Reports, integrity verification, regression checks and check-ins are engineering time. Before acquisition closeout, C reached 27.7 GB free; user-authorized relocation of the regenerable stitched cache (3,763,602,311 bytes) and TESScut cache (21,004,824,598 bytes) to D restored headroom. Original paths remain directory junctions. Both byte-count receipts are retained; no sealed evidence was moved. Entry disk measurements are retained in the entry/handoff receipts.

## Criteria not met, validation and remaining measurements

[M] STOP-1 passed with 95 independent likely-periodic in-band eligible families (minimum 60). Input eligibility fails for the 95 enumerated original stars. The H minimum of 40 is met, but the optimistic-calibration rule fires for both presets and a useful monotonic SNR50 estimate is not obtained. Early-funnel retention is low, and one C case fails SDE. The two A and 24 forced-fit unknowns remain unresolved under the one-attempt rule. The stipulated p10.1 budget test does not fit; the user also prohibited executing it. No Part I storage, budget or integrity stop fired.

[M] Final compatibility validation: **891 passed, 1 skipped**. The separate Part 3 suite had **116 passed**, and the subsequently added two autopsy checks passed in a focused invocation. An initial combined-suite collection failed because historical and Part 3 tests import different unqualified `common` modules; that log is retained. Fresh separate processes passed without changing scientific code or outcomes.

[M] Historical read-only integrity checks passed with no mismatches or verifier errors: the P11.5 check covered 63,168 files and 26,609,076,372 bytes, alongside the P10/P11 seal and historical-entry checks. Final Part 3 parent seals and all new scientific arrays were checked separately; `results/final_evidence_audit.json` and the source/data seals describe coverage. No blind worker opened the sidecar. All five autopsy diagnostics verify unchanged original inputs.

[I] Unmeasured: B/C specificity in this population, Stage D, every endpoint precision/recall or submission claim, and retention for excluded original stars. No new planet classification is inferred. The five C passers are carried, unverdicted, with recorded F7 SPOC-TCE associations and no promotion.

[P10] The unretuned endpoint risks remain: TOI-762 A b and TOI-122 b are known confirmed planets rejected by the p10.0 tiers, and TIC 144277542 changes from artefact KILL to SUBMIT under rescoring. This run does not resolve those risks.

## What a Part 5 rerun would need

[I] Before a survey of the original 2,000 plus additional eligible stars, Part 5 needs a prospectively fixed policy, direct specificity and endpoint validation on independent data, a budget/storage forecast using this measured natural load, a coverage policy for the excluded stars, and explicit survey authorization. A proposed ranking change first needs the costed injection/control experiment and full required revalidation; its gain is currently unmeasured. Apply the named isolated hard_stop_p10 catalogue adapter and its FLAG-with-ephemeris interface without changing the old hard stop or historical sealed sources. This run provides tables and preserved associations, not survey approval.

## Delivery record

[M] The allocation and supervision amendments, prediction locks, exposure ledger, closure receipts, full tables, five autopsies, resource ledger and disabled-verified routine receipt are delivered under `p10/part3/`. The local final commit is recorded in the exported delivery receipt, avoiding a self-referential commit hash inside committed reports. Nothing is pushed. The original registration and historical evidence remain sealed.

## Assumptions and evidence limits

[A] The effective preregistration, its D1–D4 amendment chain, the all_eligible allocation, and the user's prospective supervision amendment govern. Part F's computational conventions were committed before ephemeris exposure. The analysis and autopsy source registrations identify later deterministic reporting code; they do not redefine those rules.

[A] Families use the registered one-percent within-host deduplication, with a deterministic canonical forced fit and a highest-model-SNR representative within each stratum for binning. A family can occur in both strata; union families are deduplicated again. Raw rows preserve run duplicates and share their family's presence classification. Stratum totals therefore cannot simply be added for families.

[A] A recovery may use an exact period or the registered 2, 3, 1/2 or 1/3 aliases, with the conditional epoch check. Exact recovery is kept separate from alias-only recovery. The forced box depth threshold is three conditional standard errors; best-phase fitting when epoch is uncheckable includes a phase search. These errors are not a global false-alarm calibration and do not account for all correlated variability.

[A] Every displayed measured fraction has a 95% percentile interval from 10,000 paired whole-host PCG64 resamples, seed 2026091401. The same 436-host resamples are used across real-data presets and stages. Zero-denominator bootstrap draws are omitted and their valid count is disclosed. Counts alone are censuses, not binomial confidence claims. A degenerate [100,100] empirical bootstrap interval is not a guarantee of perfect population retention.

[I] These are periodic-signal retention measurements, including binaries and systematics. Expected SNR uses catalogue depth/duration and measured later-data scatter, so a large value need not describe a transit in the later data. No endpoint precision, planet yield, or discovery claim follows. Outside-domain and input-ineligible cases are never misses. Operational unknowns and C cases not run are never recoded as scientific failures. [M] All original 531 stars are development-exposed from Part F and cannot be a holdout.
