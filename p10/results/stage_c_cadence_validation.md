# P10 completed cadence comparison

19/37 decisions agree; 35/37 were required. The registered injection-C cadence is **native**, with **30 injections (10 per bin)**. The sample has not been drawn.

The existing 600-s branch changes bin averages, per-bin uncertainties and cadence-dependent clipping together. The row mechanisms identify the measured decision changes; no separate causal counterfactual was run or threshold retuned.

All 37 cases use the same p8.0 decision rule and identical unbinned arrays. All saved peak tables and p8.0 decisions reproduce. No new raw array is missing or nonfinite. The original three pilot timings and all 21 pre-resume workspaces are preserved.

| Key | Change | Native SDE | 600-s strongest period / SDE | 600-s local SDE | Decision mechanism |
|---|---|---:|---:|---:|---|
| tic144277542_P12.9812 | PASS -> FAIL | 14.9120 | 94.905133 / 10.0748 | 5.8241 | survey_window_SDE_below_9 |
| tic154566869_P8.9053 | PASS -> FAIL | 13.7371 | 37.299347 / 9.8632 | 5.4744 | survey_window_SDE_below_9 |
| tic155895971_P13.1279 | PASS -> FAIL | 10.2282 | 16.761576 / 7.8124 | 4.0631 | survey_window_SDE_below_9 |
| tic230120862_P16.7959 | PASS -> FAIL | 16.6568 | 78.454748 / 14.9775 | 5.6995 | survey_window_SDE_below_9 |
| tic404927114_P27.5436 | PASS -> FAIL | 15.8618 | 99.566208 / 10.9763 | 6.4063 | survey_window_SDE_below_9 |
| tic80256158_P10.8184 | PASS -> FAIL | 14.0544 | 16.200686 / 9.2732 | 6.6546 | survey_window_SDE_below_9 |
| tic231702397_P5.0783 | PASS -> FAIL | 75.9679 | 64.702142 / 10.9072 | 10.0495 | unrelated_stronger_peak |
| tic102734241_P10.9047 | PASS -> FAIL | 18.5734 | 68.594532 / 13.3359 | 3.1227 | survey_window_SDE_below_9 |
| tic271971130_P19.2884 | PASS -> FAIL | 88.6358 | 49.067851 / 9.9472 | 5.6061 | survey_window_SDE_below_9 |
| tic389900760_P5.8005 | PASS -> FAIL | 33.3788 | 15.358210 / 5.6372 | 3.1397 | survey_window_SDE_below_9 |
| tic259168516_P4.8025 | PASS -> FAIL | 116.0827 | 95.783732 / 8.7414 | 3.4830 | survey_window_SDE_below_9 |
| tic181804752_P4.9893 | PASS -> FAIL | 95.5495 | 4.344235 / 8.0228 | 7.9972 | survey_window_SDE_below_9 |
| tic178709444_P3.4721 | PASS -> FAIL | 131.2420 | 1.737851 / 7.5807 | 7.4162 | survey_window_SDE_below_9 |
| tic161032923_P3.9644 | PASS -> FAIL | 46.6608 | 61.972176 / 17.1866 | 9.4474 | unrelated_stronger_peak |
| tic284441182_P2.5272 | PASS -> FAIL | 38.1608 | 105.210657 / 7.1363 | 5.9113 | survey_window_SDE_below_9 |
| tic237222864_P10.2888 | FAIL -> PASS | 3.5566 | 20.577453 / 27.1639 | 26.0694 | installed_SDE_above_9_at_depth_consistent_2_to_1_alias |
| tic377293776_P2.0439 | PASS -> FAIL | 28.5678 | 17.264425 / 9.1187 | 4.6186 | survey_window_SDE_below_9 |
| tic177079323_P5.7518 | PASS -> FAIL | 35.9783 | 85.680862 / 9.6017 | 3.2050 | survey_window_SDE_below_9 |

Legacy spectra lack power_raw; their raw robust statistic is null here, never replaced by an installed-power proxy. Native raw-array validation is separate from this cadence comparison.

Cadence validation only. Native significant-peak/fallback adoption, adversarial controls and injection-C retention remain pending.
