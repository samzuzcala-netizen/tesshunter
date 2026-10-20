# Part 2c: complete C decision [M, A]

**Retain strongest-peak (a); retain the conditional robust fallback and cadence duration floor.**

The comparative adoption conditions in frozen section 0.4 all pass. PROMPT_P10.md 2c(ii) additionally requires the alias rule to fail every half/double-period case; section 0.11 does not waive it. Three of seven pass both (a) and (b), so that required check fails. Retain (a) under the stated otherwise-keep-(a) fallback rather than claim the absolute alias requirement passed. This records the literal pre-existing requirement after its result was measured; it changes no threshold, input, decision or frozen-section text. The baseline also has these three passes, which remain a demonstrated C limitation.

| Injection expected-SNR bin | n | a installed/fallback passes | b installed/fallback passes |
|---|---:|---:|---:|
| 7_12 | 10 | 8 / 8 | 10 / 10 |
| 12_20 | 10 | 6 / 6 | 9 / 9 |
| 20_50 | 10 | 10 / 10 | 10 / 10 |
| all | 30 | 24 / 24 | 29 / 29 |

No adversarial FAIL-to-PASS change occurs under (b) or fallback. Every paired EB column has 16 PASS and 25 FAIL. Only the named positive HIP 97166 b flips under fallback among the 37 native cases.

| Half/double EB candidate | Catalogue alias | a | b |
|---|---|---|---|
| eb_tic178858648_candidate1 | 1:2 | PASS | PASS |
| eb_tic239022536_candidate1 | 1:2 | FAIL | FAIL |
| eb_tic184246521_candidate1 | 1:2 | FAIL | FAIL |
| eb_tic20876588_candidate1 | 1:2 | FAIL | FAIL |
| eb_tic237116051_candidate1 | 1:2 | PASS | PASS |
| eb_tic272598447_candidate1 | 1:2 | PASS | PASS |
| eb_tic272598447_candidate3 | 2:1 | FAIL | FAIL |

Both TIC 92743594 candidates lie below their inherited blind grid (R_star=M_star=30.2557). Their FAILs are missing local-period coverage, not demonstrated alias rejection. Original stellar inputs and all +inf empty-duration chi2 values are preserved with exact proofs.

The original adversarial search itself was catalogue-windowed and usually used up to three SPOC 120-s sectors with a 600-s search bin. These are existing development controls, not an independent blind or in-domain holdout.

The thirteenth injection's original raw wall includes its recorded suspension; no timing is rewritten.
