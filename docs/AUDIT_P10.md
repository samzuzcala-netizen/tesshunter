# P10 audit: stopped by original Stop Rule 1

P10's authorized execution ended at Part 2d on 2026-09-12. The repair/calibration work is complete; Parts 3–5 and their candidate/holdout evaluations were not run.

The rule required after-A/S SNR50 <=14.0 and projected C load <=150. The measured after-A/S value is **18.26124 [17.68572, 18.95767]**, so the first condition fails. The pre-gated whole-funnel value is separately **18.62889 [18.05200, 19.31654]**; it also fails. The frozen handoff's baseline 20.19 identifies the former level; earlier operational naming is disclosed, and frozen section 0 is unchanged.

All 2,100 original injections completed successfully, with 1,240 recovered, 765 missed and 95 uncredited aliases. A passes 1,164 and S passes 964 of those; the full pre-gated path leaves 952. Bound S rejects 200/1,164 A passers, the main remaining downstream sensitivity loss. Recovery improves, but insufficiently under the original threshold.

FA_S=2/300, excluding the seeded A-failure sample. The original P8/DC15 numerical model, new pre-gated curve and claimed fraction 0.03 yield 21.086755 signals on the original 2,000 stars. Their saved measured-noise inputs remain byte-identical. HU19 sensitivity is 27.634104; search-only yield is 28.277649. Up to 531 unmeasured additions contribute at most 31.337769 under the recorded geometric bound. The central C-load expectation range is 37.960088–69.297857, which satisfies the workload criterion but does not override the independent recovery failure.

The complete level table, bootstrap intervals, A failures, S modes, FA census, timing and bin diagnostics are in `../p10/results/part2d_calibration_20260912/STOP_RULE_1.md`, `COMPLETENESS_P10.md` and `stop_rule_1_decision.json`. The full calibration seal hashes 15,583 files / 7,915,270,129 bytes. `yield_model/` preserves the original-noise copies, routing, source/input hashes, one numerical execution and a separate closed seal.

P7 reproduces 823 records at 0/0/0.0, preserving 2,513 P6 hashes. The seeded cached P8 replay is 20/20 byte-identical; separate fresh replay is scientifically exact with differing timestamps/runtimes. Latest full regression: 774 passed, 1 skipped; later correction and bound checks pass, and 13 final yield/bound/legacy-model tests pass. The calibration schema-only guard recovery reused every completed A record after verified original-owner closure. No original worker threshold or result was changed.

The bound secondary mode, selected e search, strongest-peak C(a), conditional robust fallback and one-cadence duration floor remain the recorded choices. The three-of-seven alias-control passes, two out-of-grid TIC 92743594 controls, catalogue-windowed development exposure, corrected exact-unit EB run and original suspended injection timings remain disclosed in RULES.md section 9 and the handoff.

The expectation range is not a confidence interval or realized-count bound. The bootstrap omits within-star dependence; occurrence shape, empirical FA extrapolation and later B/C/D survival remain limitations. No new Part 3 stars were selected and no later real/held-out outcomes or TCE ephemerides were opened. There is no new detection, confirmed planet or submission.

The existing two-hour adaptive heartbeat is verified PAUSED under the original stop instruction. `../p10/results/part2d_calibration_20260912/finalization_20260912/automation_paused_verified.json` records the exact schedule/prompt verification. Resume instructions now lead with the final stop; previous progress entries remain historical. All work is retained locally without a push or external submission.
