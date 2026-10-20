# Part E timing-pilot operation

## Registered sequence [A]

Part D must close, satisfy the three-sector eligibility rule and not fire STOP-1 before `prepare_e.py` freezes the nested order and six timing hosts. The timing hosts are selected solely by the registered hash, two per native-point-count tercile. Both presets receive the same frozen native arrays and ingestion key. The production controller uses the same 24-core affinity and single-thread environment; twelve paired jobs are available in this six-host pilot.

Each search has one attempt and a 3,600-second deadline. Traces and a durable Python file-open log are saved separately from its timing/count receipt. The worker blocks the ephemeris sidecar. The closed-phase I/O audit stops further work if a sidecar path appears in a log. Missing or truncated operational logs are disclosed, never treated as successful proof of coverage.

After search closure, `pilot_next.py` verifies ownership, source hashes, storage and the registration chain. It runs the registered machine-only collection and creates Stage A jobs for every P10 pilot pre-gate survivor. Those jobs use the unchanged p10.0 route, one attempt and a 1,200-second deadline. This candidate-based internal Stage A TLS is distinct from Part F's TCE-based forced fits, which remain prohibited until the prediction locks.

After Stage A closes, the same transition helper writes a timing/count-only summary and requests a main-session allocation review. It does not select an evaluation level, inspect A criteria or compute retention. The main session must prospectively select the level and paired P8 allocation before any further blind result is read for interpretation.

## Supervision [A]

Use the existing Prompt 10.3 hourly heartbeat in this task. Keep the old P10 heartbeat paused. The normal interval is 60 minutes, with one early check at about ten minutes and a shortened final interval only when the current forecast justifies it. Ordinary checks run `checkin.py` and read only progress, owner identity, the last fifty controller-log lines, disk and CPU deltas. They do not read case results or recompute science.

At clean pilot-search closure, the registered transition helper may prepare the next phase. Launch its returned Stage A manifest under `controller_v2.py`, with logs named `logs/controller_timing_pilot_A.log` and its stderr companion. If there are zero Stage A jobs, close the empty registered phase immediately, produce the summary and pause supervision without an idle scheduled interval. After nonempty Stage A closure, produce the summary, pause the heartbeat and verify its paused state before handing the allocation decision to the main session.

Any failed preflight, integrity or sidecar-access event returns to the main session. A stalled worker is stopped only after its process identity and nonadvancing CPU are verified. The controller retains timeouts and failed attempts as operational unknowns and charges their wall time. There is no outcome retry.

## Assumptions and scope

[A] The pilot is an allocation measurement. Its successful searches and Stage A records may be reused for selected evaluation hosts, preserving their original inputs and attempts. Timing hosts outside a subsequently chosen level remain timing-only and their cost remains charged. No TCE family is used to select a timing host. No final retention, calibration or endpoint claim follows from this pilot.
