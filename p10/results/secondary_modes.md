# Part 2a: the secondary-scan modes, measured [M]

Generated 2026-09-08T13:38:50Z. Records: inj 1093 OK / 0 error, adv 40 OK / 0 error, p8pass 189 OK / 0 error, p6eb 1 OK / 0 error, dev 20 OK / 0 error.

Rescanned `bound` gate against the saved p8.0 decision: inj 0 of 1093 disagree; adv 0 of 40 disagree; p8pass 0 of 189 disagree; p6eb 0 of 1 disagree; dev 0 of 20 disagree.

| mode | injection false kills (FK) | adversarial kills retained (KR) | EBs killed | blends killed | TIC 233007823 | eligible |
|---|---:|---:|---:|---:|---|---|
| bound | 189/1093 (17.3%) | 26/26 (100%) | 17/18 | 9/22 | FAIL | yes |
| empirical_bound | 133/1093 (12.2%) | 21/26 (81%) | 16/18 | 5/22 | FAIL | no |
| recurrent_bound | 40/1093 (3.7%) | 18/26 (69%) | 14/18 | 4/22 | FAIL | no |
| recurrent_bound_corr | 40/1093 (3.7%) | 18/26 (69%) | 14/18 | 4/22 | FAIL | no |

**Decision (rule: lowest injection false-kill rate among modes retaining >= 90% of the p8.0 bound kills on the adversarial EB and blend set and failing TIC 233007823; an exact tie in FK goes to the simpler mode (bound < empirical_bound < recurrent_bound < recurrent_bound_corr)): `bound`.**

P8 Stage A passers (descriptive, never in the rule): 170 p8.0 rejections would PASS under bound: 0, empirical_bound: 124, recurrent_bound: 128, recurrent_bound_corr: 128; the 19 p8.0 passers would FAIL under bound: 0, empirical_bound: 0, recurrent_bound: 0, recurrent_bound_corr: 0.

| review class of the rejection | n | pass under bound | empirical_bound | recurrent_bound | recurrent_bound_corr |
|---|---:|---:|---:|---:|---:|
| eclipse_like | 80 | 0 | 58 | 62 | 62 |
| modulation | 58 | 0 | 38 | 38 | 38 |
| other | 31 | 0 | 28 | 28 | 28 |
| unreviewed | 1 | 0 | 0 | 0 | 0 |

| P6 / development record | reference gate | bound | empirical_bound | recurrent_bound | recurrent_bound_corr | scatter (ppt) | SAP sigma | recurs |
|---|---|---|---|---|---|---:|---:|---|
| tic233007823_P17.4683 | FAIL | FAIL | FAIL | FAIL | FAIL | 0.07736252358097012 | 54.24 | True |
| tic161032923_P19.8263 | FAIL | FAIL | FAIL | FAIL | FAIL | 0.5947915160594358 | 5.68 | True |
| tic161032923_P3.9644 | PASS | PASS | PASS | PASS | PASS | None | None | None |
| tic181804752_P14.9697 | FAIL | FAIL | FAIL | FAIL | FAIL | 1.1843148680093563 | 17.4 | True |
| tic181804752_P20.9575 | FAIL | FAIL | FAIL | FAIL | FAIL | 1.292592558131726 | 15.4 | True |
| tic181804752_P4.9893 | PASS | PASS | PASS | PASS | PASS | None | None | None |
| tic237222864_P10.2888 | PASS | PASS | PASS | PASS | PASS | None | None | None |
| tic271971130_P19.2884 | PASS | PASS | PASS | PASS | PASS | None | None | None |
| tic284441182_P10.1083 | FAIL | FAIL | FAIL | FAIL | FAIL | 0.275503340024567 | 9.49 | True |
| tic284441182_P15.1626 | FAIL | FAIL | PASS | PASS | PASS | 0.40776610937982427 | 3.72 | True |
| tic284441182_P18.0890 | PASS | PASS | PASS | PASS | PASS | None | None | None |
| tic284441182_P2.5272 | PASS | PASS | PASS | PASS | PASS | None | None | None |
| tic335590096_P1.5228 | PASS | PASS | PASS | PASS | PASS | None | None | None |
| tic335590096_P13.7047 | FAIL | FAIL | FAIL | FAIL | FAIL | 1.902028747779335 | 53.81 | True |
| tic33595516_P0.7655 | PASS | PASS | PASS | PASS | PASS | None | None | None |
| tic33595516_P10.7177 | FAIL | FAIL | FAIL | FAIL | FAIL | 0.2992023806560598 | 14.63 | True |
| tic33595516_P14.5443 | FAIL | FAIL | FAIL | FAIL | FAIL | 0.2987322956207096 | 12.49 | True |
| tic33595516_P15.3098 | FAIL | FAIL | FAIL | FAIL | FAIL | 0.3435782097848338 | 13.56 | True |
| tic377293776_P10.2197 | FAIL | FAIL | FAIL | FAIL | FAIL | 0.06237509238833171 | 10.51 | True |
| tic377293776_P16.3513 | FAIL | FAIL | FAIL | PASS | PASS | 0.061278401956362825 | 56.55 | False |
| tic377293776_P2.0439 | PASS | PASS | PASS | PASS | PASS | None | None | None |
