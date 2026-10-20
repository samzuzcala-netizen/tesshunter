# Stage C execution registration — 2026-09-15

[A] This record implements the unchanged p10.0 Stage C after the paired searches, full A/S/B and Part F. It adds no scientific threshold, population cut or additional iteration. The user's automatic-continuation amendment applies. The companion stage_C_method_registration_v1.json pins sources and this document before selection is locked and before any C launch.

## Population and resources [A]

The cap remains N_C = 13, computed at B closure from 18.105466883722194 remaining hours as floor((remaining_hours - 3.0) * 3 / 3.4). The exact B ledger snapshot and its original hash are retained. Later F costs do not recalculate this cap.

Use only B PASS candidates with an accepted-period/epoch association to an in-domain TCE row having model SNR >= 12 and at least three transits. Rank each candidate by the greatest finite expected SNR among its qualifying matched rows, descending, then candidate ID. Preserve all matching row witnesses and the full ranked eligible list. A qualifying candidate with no measured expected SNR is explicitly unrankable and unmeasured, rather than assigned an invented value. Keep unmatched B survivors, candidates without a qualifying in-domain match, unrankable candidates and cap exclusions in the selection manifest. Forced presence is not an additional selection criterion. All these rules precede inspection of any Stage C result.

Use controller_v4.py for at most three concurrent top-level jobs. Each job uses eight TLS processes with single-thread BLAS/Numba, within the controller's 24-core affinity. The unchanged route uses oversampling 3 (the frozen default), period grid 0.5–110 days, and its associated narrow ephemeris fit at the survey candidate's period with oversampling at least 5. These are internal measurements of the existing Stage C implementation, not repeats of a Part F family fit. The candidate period, epoch and depth come from the locked blind candidate; no TCE ephemeris enters the Stage C worker. Its Python file-open guard also prohibits the sidecar.

One C attempt has a 12,240-second deadline (the registered 3.4-hour tail). The full queue forecast is ceil(selected_count / 3) times 3.4 hours, including a partially occupied final wave. Record that forecast, the measured remaining budget and residual headroom before launching. The 31.98-hour hard cap is still enforced by the controller; failures and stalls consume queue time. No retries or outcome-based replacement jobs are allowed. If selection is empty, close an immediate zero-job controller phase and continue to analysis.

## Scientific route and isolation [A]

Each worker uses funnel_worker.legacy to select p10.0 through p10/protocol/p10_funnel_calibration.py, scripts/revet_p6.py stagec_one and scripts/audit_p5.py tls_step. The assertions require strongest-peak selection, conditional robust-SDE fallback and the one-cadence duration floor. No significant-peak alternative is selected. The original sources are unchanged and hashed.

The exact raw product list, source hashes and stellar metadata come from the already frozen early-funnel candidate runtime. Verify its hash and A PASS, S PASS/HOLD and B PASS receipts before starting. Build the same candidate tables under a fresh data/survey/p10/part3/funnel/C_cases_v1/<candidate_id> directory; refuse any existing case directory or C result. The original pilot and A/S/B case directories are never reused as C output roots. The unchanged audit preparation is recomputed from the same verified raw arrays in this new directory, including the original p10.0 preparation choices. There is no reuse of a previous C cache.

Every new C receipt records runtime/method hashes, exact resources, rule version, the complete stage measurement, timing and I/O audit. Non-PASS/FAIL or failed execution is operationally unknown. Runtime/source/input/route or sidecar-integrity failure writes the durable stop signal; it cannot be converted into a scientific rejection. Stage C writes no Stage D record, final verdict tier, packet or submission. Any carried result remains unverdicted and reports its SPOC TCE association without promotion.

## Validation and continuation

[M] Focused tests exercise rank and tie order, unique candidate selection with all witnesses, negative/zero caps, aliased recovery, failed epoch matches, likely-periodic/in-domain/finite-SNR requirements, strict upstream A/S/B routing, output-root isolation and refusal of repeated setup. A fresh child process verifies the real legacy adapter selects the exact p10.0 rules and constructs its job without running any scientific fit. Test counts and commands are recorded in the method manifest.

[A] After the C selection/job plan is locked and committed, launch the detached controller, record exact owner identity and CPU baseline, and use the existing routine's single early check followed by hourly checks. At closure, verify and seal all C evidence, then complete the search/funnel bootstrap tables and Part H, five autopsies if triggered, and cost the p10.1 next step without executing it. Implement any remaining analysis handlers between closed phases. Never pause for another N_C or H approval. Final regression, historical integrity, disabled-routine receipt, final reports/seals and a local commit remain required before final delivery.
