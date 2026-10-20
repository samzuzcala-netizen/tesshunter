# DECISION POINT 1

Core-only is the registered recommendation [A]. Extension eligibility is not measured completeness [I].

| Part | Base queue-h [A/I] | With margin [A/I] |
|---|---:|---:|
| 0 | 3.10 to 3.10 | 3.88 to 3.88 |
| 1 | 1.20 to 1.20 | 1.50 to 1.50 |
| 2 | 55.10 to 55.10 | 68.87 to 68.87 |
| 3 | 0.00 to 0.00 | 0.00 to 0.00 |
| 4 | 28.22 to 28.22 | 35.27 to 35.27 |
| 5 | 57.53 to 70.26 | 71.91 to 87.82 |
| 6 | 1.00 to 1.00 | 1.25 to 1.25 |

Total with margin: 182.68 to 198.59 queue-h [I].
Separate C retry tail: up to 63 queue-h [A].
Decision points [A]: launch approval after Part 0; any stop rule; final delivery.

Assumptions
[A] Section 6.1 stage-load rates apply to the frozen-policy eligible population.
[A] Calibration stage-load and preparation proportions scale within their own full-injection, 2b-injection or host cohorts; both real-host legs scale only with eligible TCE hosts.
[A] Both 30-job calibration C allocations remain conservatively priced even when fewer calibration hosts qualify; actual job manifests replace phase costs when available.
[A] Queue costs are job-wall sums divided by the measured concurrency once.
[A] The 1.25 margin is applied once; C retries remain a separate tail.
[I] Calendar conversion at duty 0.553 is conditional and promises no completion date.
[A/I] Part 4 TTT line items scale with measured N1; natural late-stage load scales with eligible calibration hosts. The inherited rounding residual is retained.
[A/I] The mixed-stage P9 allocation and extension-calibration allocation scale conservatively by the larger raised search/A pilot factor because their inherited budgets are not fully decomposed.
[A/I] Extension variable allocations and download/storage estimates scale with measured ranked pool size; the acquisition pilot stays fixed. Retry-tail and core-storage allocations remain conservative inherited upper bounds.

| Core scenario | Queue-hours with margin [I] |
|---|---:|
| archival | 182.68 to 198.59 |
| ADOPT_SML_ratio_1 | 214.77 to 230.68 |
| ADOPT_SML_ratio_3_ceiling | 316.50 to 332.41 |

| Extension | Ranked stars [M] | Additional queue-hours with margin [I] | D storage GB [I] |
|---|---:|---:|---:|
| E1 | 1000 | 48.76 to 61.26 | 48.0 |
| E2 | 7989 | 271.27 to 368.77 | 383.0 |

Measured N1 is below 20: LB1a cannot be decisive and the registered launch bar cannot be met. This is reported, not a stop; the final search still depends on the user's launch approval [A/M].


## Part 0 measurements [M]

| Cohort | Eligible | Ineligible | Novelty rejected | Unknown |
|---|---:|---:|---:|---:|
| p8_2000 | 1622 | 378 | 0 | 0 |
| p10_436 | 436 | 0 | 0 | 0 |
| calibration_300 | 241 | 59 | 0 | 0 |

Eligible injection rows [M]: {"2b": {"calibration_hosts": 272, "calibration_injections": 600, "eligible": 494, "total": 600}, "full": {"calibration_hosts": 300, "calibration_injections": 2100, "eligible": 1687, "total": 2100}}.
Catalogue hard-stop counts [M]: {"CLEAN": 2000, "FLAG": 436}.
Independent negatives N1: 6 [M]; source: fallback TESS-EB; fetch path: `data/cache/catalogs/tess_eb/raw/hlsp_tess-ebs_s0001-s0026_v1.0_cat.csv`.
The fetch attempt URLs, UTC, bytes, hashes and relaxation counts are in `p12/manifests/ttt_fetch.json` [M].
Latest public QLP sector: 105 [M]. Per-star coverage above 105: UNMEASURED [M]. Directory membership does not measure per-star above-105 coverage; no per-star calls performed

## Pilot costs [M]

| Stage | COMPLETE | Unknown | Mean job wall, s | Queue s/job at 24 workers | Value used |
|---|---:|---:|---:|---:|---:|
| search | 24 | 0 | 765.782 | 31.908 | 31.908 (pilot) |
| A | 41 | 0 | 353.224 | 14.718 | 15.500 (inherited floor) |

Pilot results were used only for timing and counts. No per-candidate measurement was displayed or reused [M].

## Recommendation and decision [A/I]

Core only. The ranked E2 pool has 7989 stars, including 5157 at Tmag 13.5–14 [M]. The extension requires its own calibration; the inherited whole-funnel recovery in this faint band is 41% [P10.3]. Its additional cost and storage are explicit in the forecast [I].
Pause here. The user chooses core, E1 or E2 and writes `p12/manifests/decision_point_1.json`. The agent has not written that file [M].
The three human decision points remain launch approval after Part 0, any stop rule, and final delivery [A].

## Provenance and resolved stops

The sprint is closed by the user. Its original T0 and complete handoff remain in `p12/manifests/closed_sprint_20260922/`; section 10 no longer limits this continuation [A/M].
The audit-only commit is `22a779d0456b81bce24fc9caa60c4fb86c8ba574` [M]. Normal verification uses its recorded source-refresh manifest with identical scientific job payloads [M].
The failed initial native launcher started no controller and no scientific job. Its logs and the PowerShell 7 repair are preserved under `p12/manifests/verify_core_startup_failure_1/` [M].
The earlier count and replay stop receipts and authorized resolutions remain preserved. The 118-test correction and exact historical exposures are recorded in `p12/protocol/AMENDMENTS_P12.md`; no new exception is authorized here [M].
PROMPT_P12.md SHA-256: `8be9b707fa7da8a4c0e86e182f92963e21ec3f6fc4c799d52dda5612354b68a3` [M].

## Original entry and sprint evidence

The archived sprint handoff retains the full Part 0a table, test and integrity receipts, original T0, prior stops and their resolutions [M].
Current evidence: `p12/results/decision_point_1_report.json`, `p12/results/pilot_timing.json`, and `p12/manifests/forecast_p12.json` [M].

Resume here: decision point 1; wait for the user population choice.


## Temporary supervision authority and TTT reconciliation [A/M]

The user authorized judgement-based resolution of stop rules through 2026-09-23 08:00 America/New_York (EDT); decision point 1 remains a mandatory stop. The exact instruction and UTC expiry are in `p12/manifests/temporary_supervision_authorization.json`. This overrides the earlier stop-and-ask wording only within that window. No decision-point choice was written.

TTT attempt 1 failed operationally and is preserved with its original controller receipt and the byte-identical `p12/manifests/ttt_fetch_attempt1.json`. VizieR timed out; the arXiv archive contained no full machine-readable table. Reconciliation reused those bounded attempts and the prescribed read-only fallback. Catalogue membership, metadata cuts, relaxation order and hash ordering were retained; every selected ephemeris required strict validation. Repair tests: 48 passed, zero failures. The resolution is `p12/manifests/ttt_reconciliation.json`.

Part 0 N1 is the selected negative cohort available for the later search. The final launch-bar denominator requires COMPLETE searches in Part 4 and has not yet been measured.


Part 0 packaging reconciliation [M]: the first scoped Git staging operation returned 128 after all measurements and the decision-point report were complete. Its stderr was not retained; the cause is undetermined. Repeating the same scoped command succeeded. The retry preserves the completed measurement transitions and performs only the Part 0 commit; no owner or population decision is present. Receipt: `p12/manifests/part0_packaging_reconciliation.json`.


Final decision-point pause [M]: the hourly routine is PAUSED, no owner or science process remains, and final_supervision_disabled.json was freshly verified. The historical console/filename incident is resolved by the user's ruling in normal_exposure_resolution.json; it is a ledger entry and is not a new P12 candidate exposure.


## Part 0f attempt 4 and schedule verification — 2026-09-23T14:52:46.820471+00:00 [M]

One authorized parser repair added ordinary tabular and AASTeX deluxetable support. The pinned arXiv source contains a 30-row binary table in main.tex, inside sidewaystable/tabular. Its caption explicitly states that the full table is a separate machine-readable online supplement; the archive contains no separate machine-readable table. Attempt 4 parsed those 30 rows but rejected the abbreviated table as the full catalogue. Status: UNAVAILABLE (ONLY_EXPLICITLY_ABBREVIATED_TABLES). Wall time: 0.209 seconds; enforced deadline: 600 seconds. The original download was reused with its URL, byte count and SHA-256, and no new HTTP request was made. No ephemeris values were displayed.

Final N1 remains 6, from fallback TESS-EB. The selection manifest and guarded ephemerides are byte-identical to the previous decision-point delivery. All selection cuts, exclusions, relaxation order and hash ordering are unchanged, confirmed by the selection-function AST comparison. Parser/selection regression tests: 37 passed, zero failures. The numerical forecast is unchanged. N1 remains below 20, so LB1a is not decisive and the launch bar cannot be met with this cohort.

The actual app-owned automation was PAUSED before this follow-up; its saved ten-minute interval was not an armed schedule. It remains PAUSED, with the stored interval reset to sixty minutes. The scheduling helper and saved instructions now enforce one ten-minute early check followed by hourly checks. No shortened repeating final intervals are used. The change is in p12/manifests/checkin_schedule.json. The earlier temporary stop-rule authority has expired. Decision point 1 remains mandatory; no population choice has been written and Part 1 has not started.

Evidence: p12/results/ttt_fetch/attempt4.json, p12/manifests/ttt_attempt4_plan.json, p12/manifests/ttt_fetch.json, and p12/manifests/final_supervision_disabled.json.
