# P9 reported-duration and event-identity audit

Reported-duration sensitivity of event identity after lock. Primary truth, gate decisions and nested scores remain unchanged. No replacement duration rule is calibrated.

| Candidate | Native C | C duration (s) | C duration / 200 s | Native D seed (s) | D fit (h) |
| --- | --- | --- | --- | --- | --- |
| tic231702397_P5.0783 | PASS | 462.4257718466929 | 2.3121288592334643 | 3722.8631443750955 | 1.277 |
| tic335590096_P1.5228 | PASS | 296.16030344682787 | 1.4808015172341393 | 2882.4777282817017 | 1.228 |
| tic102734241_P10.9047 | PASS | 2675.1538382593317 | 13.375769191296659 | 4808.262647013913 | 1.838 |
| tic243641947_P2.5929 | PASS | 222.381868267781 | 1.111909341338905 | 3722.8631443750955 | 1.478 |
| tic271971130_P19.2884 | PASS | 3147.181095981154 | 15.735905479905771 | 6210.110011054397 | 2.026 |
| tic389900760_P5.8005 | PASS | 266.86518703582436 | 1.334325935179122 | 2882.4777282817017 | 1.003 |
| tic259168516_P4.8025 | PASS | 1852.2333099958064 | 9.261166549979032 | 3722.8631443750955 | 1.21 |
| tic181804752_P4.9893 | PASS | 225.8255821542361 | 1.1291279107711805 | 2882.4777282817017 | 1.138 |
| tic178709444_P3.4721 | PASS | 299.94545585642095 | 1.4997272792821048 | 3722.8631443750955 | 1.33 |
| tic161032923_P3.9644 | PASS | 281.2739511839623 | 1.4063697559198116 | 2882.4777282817017 | 1.123 |
| tic284441182_P18.0890 | FAIL | 335.7795603201207 | 1.6788978016006035 | None | None |
| tic284441182_P2.5272 | PASS | 369.35751635213285 | 1.8467875817606643 | 3722.8631443750955 | 1.339 |
| tic237222864_P10.2888 | FAIL | 3534.4471313355957 | 17.67223565667798 | None | None |
| tic377293776_P2.0439 | PASS | 89.70925701158461 | 0.44854628505792304 | 2882.4777282817017 | 0.989 |
| tic33595516_P0.7655 | PASS | 1490.3077566713625 | 7.4515387833568125 | 4808.262647013913 | 1.624 |
| tic177079323_P5.7518 | PASS | 4403.83599233848 | 22.019179961692398 | 8020.665504482884 | 4.037 |
| tic230006888_P12.2789 | PASS | 5685.124546638519 | 28.425622733192593 | 13379.276436729879 | 5.098 |
| tic41422753_P2.4708 | PASS | 2339.8469439040973 | 11.699234719520486 | 8020.665504482884 | 3.422 |

## TOI-1450 A b

The primary category `C_signal_switch` means the accepted ephemeris failed the registered identity rule. It does not by itself prove a different physical signal. The following checks keep C period and epoch identical, substitute one recorded duration at a time, and apply the original match function. None earns primary credit.

| Duration source | Seconds | Matched events | Truth opportunities | Found opportunities | Identity rule |
| --- | --- | --- | --- | --- | --- |
| reported_C | 89.70925701158461 | 77 | 172 | 77 | False |
| accepted_A_duration | 2882.4777282817017 | 171 | 172 | 171 | True |
| native_D_seed_duration | 2882.4777282817017 | 171 | 172 | 171 | True |
| locked_D_fit_duration | 3560.4 | 172 | 172 | 172 | True |
| published_truth_duration | 3556.7999999999997 | 171 | 172 | 171 | True |

The independently saved final fit matches the labelled signal: {'ratio': 1, 'period_fraction': 2.957933227243359e-07, 'matched': True, 'matched_events': 172, 'n_truth_opportunities': 172, 'n_found_opportunities': 172, 'truth_fraction': 1.0, 'found_fraction': 1.0, 'mean_normalized_timing_residual': 0.0017177119455125877}. This is an existing-fit association, not repaired nested completeness.

The frozen native physical-fit adapter already uses the wider of survey and C durations for its fitting window; see `_p8_fit_input` in [audit_p5.py](baseline/source/scripts/audit_p5.py). This is existing production behavior, not a P9 rescue. The upstream cause of the very short C duration was not established. A future duration/identity protocol needs independent positive and negative evaluation; this selected example does not measure its specificity cost.
