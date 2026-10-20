# P10 closed false-alarm calibration

The same 300 selected-e uninjected controls were collected under `survey_p10` and processed into fresh `p10.0` A/S records. Every expected record validates against its identity, input configuration, named preset/rules, exact writer thresholds, ephemeris, timing and A/S linkage. The original A phase closed naturally; its corrected successor validated all 709 A records without re-executing them, then completed S at 2026-09-12 10:41:53 UTC.

| Level | Count | Per control star |
|---|---:|---:|
| Accepted search candidates | 3494 | 11.646667 |
| Original pre-gate | 709 | 2.363333 |
| Stage A pass | 45 | 0.150000 |
| A + secondary pass (FA_S) | 2 | 0.006666667 |

Secondary ran on all 45 A passers and the original seeded 10% A-failure sample (66 failures; 41 S PASS, 25 S FAIL). The failure sample does not contribute to FA_S. There are 111 complete S records. Against the earlier selected-e p8.0 experiment, all 709 A keys/decisions and 111 S keys/gates match exactly. This is decision equality, not a claim that fresh timestamps or every serialized field is identical.

The frozen false-alarm term for 2,531 stars is **(2/300)*2,531 = 16.873333333**. This is an extrapolated control-candidate rate, not proof that the surviving controls contain no real signals. Its sampling uncertainty and constant-per-star assumption remain. The recovery curve, model signal yield and complete Stop Rule 1 decision are still pending.

The closed seal `false_alarm_closed_seal_20260912.json` records all 4404 artifact hashes, the full metrics and comparison. Original P8/P9 outcomes, numerical thresholds and scientific worker source are unchanged.
