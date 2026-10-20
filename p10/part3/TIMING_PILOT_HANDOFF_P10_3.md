# P10.3 timing pilot: main-session review handoff

The paired timing pilot is complete: **12 search jobs and 17 Stage A jobs**, all completed without operational unknowns. Loaded source hashes remained unchanged. The registered search file-access audit passed. Both owners and all recorded worker identities are closed; the hourly routine is verified **PAUSED**, and the old P10 routine remains paused.

## Measured job durations

Controller wall times in seconds include worker startup. These are timing measurements, not retention results.

| Phase | Jobs | Mean | Median | p90 | Maximum |
|---|---:|---:|---:|---:|---:|
| survey_p10 search | 6 | 760.6 | 1051.6 | 1139.1 | 1161.7 |
| survey_p8 search | 6 | 228.8 | 274.9 | 358.8 | 364.9 |
| Stage A | 17 | 141.6 | 109.6 | 268.6 | 374.1 |

CPU distributions and individual timings are preserved in timing_pilot_summary.json. The session read only durations, CPU, candidate counts and operational status. Stage A decisions and criteria, ephemerides, matches and retention outcomes were not opened for review. No Part F matching or TCE forced fit has run.

## Budget and next decision

Closed new scientific union time is **3.768335 of 31.98 hours**, leaving **28.211665 hours**. The paired search phase used 0.322712 union hours and Stage A used 0.103963. Cumulative acquisition charge is **12.105788 of 15 GB**, including prior work and the unreconciled reservation. C: has 50.218 GB free. All 14 check-ins are reconciled into the schedule and resource ledger.

The main session must forecast the remaining E/F/G work using the observed distributions and registered historical tails, with 25% margin, then record the evaluation level and paired P8 allocation prospectively. Registered levels are 436, 400, 300 and 200. **No level or P8 allocation has been selected.** The routine will remain paused until the required main-session review is recorded.

Part D remains complete with 436 eligible stars and 95 independent likely-periodic in-band families; STOP-1 does not fire. This is an interim allocation handoff, not a scientific endpoint or final decision. Closed pilot evidence is sealed by opaque-byte hashes; the final prediction manifests remain to be prepared for the selected evaluation.

Recorded 2026-09-15T05:12:57.033554+00:00.
