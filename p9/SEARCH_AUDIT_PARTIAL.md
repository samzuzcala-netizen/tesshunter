# P9 search-selection autopsy supplement

Post-lock recorded local selection, not alternative recovery scoring, a rescued signal or a measured variant benefit.

The frozen pipeline selects the highest composite score from internal gate survivors and stops each partition at its configured accepted-candidate limit. A local near-period BLS solution need not have a globally correct ephemeris. Logged wall-budget stops, candidate-limit stops, alias decisions and ranking are different mechanisms.

| Missed positive | Near-period log messages | Local selection losses | Recorded wall stop |
| --- | --- | --- | --- |
| Kepler-560 b | 0 | 0 | False |
| Kepler-629 b | 0 | 0 | False |
| TOI-5716 b | 0 | 0 | False |
| LP 791-18 b | 10 | 4 | False |
| TOI-849 b | 4 | 0 | False |
| Kepler-1328 b | 0 | 0 | False |
| Kepler-994 b | 0 | 0 | False |
| Kepler-995 b | 1 | 1 | False |
| Kepler-922 b | 0 | 0 | False |
| Kepler-607 b | 0 | 0 | False |
| Kepler-262 b | 0 | 0 | False |
| Kepler-504 b | 0 | 0 | False |
| Kepler-262 c | 1 | 0 | False |
| Kepler-1076 b | 0 | 0 | False |
| Kepler-195 b | 0 | 0 | False |
| Kepler-622 b | 1 | 0 | False |
| Kepler-196 b | 0 | 0 | False |

## LP 791-18 b

[Frozen search log](logs/search_tic181804752_attempt1.log); SHA256 `49e7d909107764e1e2352a41a14c312022d57137676c546ad1a36648376485ab`.

- chunk0, pass 2: a near-period 0.9485 d solution passed at SNR 7.5, composite 5.2 (log line 218); the chosen 10.232323 d candidate had composite 5.33 (line 247).
- chunk0, pass 3: a near-period 0.9485 d solution passed at SNR 6.7, composite 4.29 (log line 300); the chosen 3.317685 d candidate had composite 5.02 (line 371).
- chunk2, pass 2: a near-period 0.9477 d solution passed at SNR 6.5, composite 4.67 (log line 890); the chosen 11.834720 d candidate had composite 5.81 (line 985).
- chunk2, pass 3: a near-period 0.9477 d solution passed at SNR 5.9, composite 3.88 (log line 1005); the chosen 8.539564 d candidate had composite 5.24 (line 1096).

These choices are measured. The benefit and negative-control cost of changing them are unmeasured; no extra accepted slot or alternative ranking was run.

## Kepler-995 b

[Frozen search log](logs/search_tic120315006_attempt1.log); SHA256 `04791313ceca414a35de71a852becd2a36327011989177db085df64e69f2ecb1`.

- stitch, pass 2: a near-period 28.0238 d solution passed at SNR 5.4, composite 5.36 (log line 600); the chosen 22.780642 d candidate had composite 5.66 (line 627).

These choices are measured. The benefit and negative-control cost of changing them are unmeasured; no extra accepted slot or alternative ranking was run.
