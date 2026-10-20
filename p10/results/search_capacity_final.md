# Part 2b: final paired search comparison

Measured 2026-09-10T05:30:20.000426+00:00.

The frozen rule selects **e (survey_p10_both)**. The p10.0/survey_p10 freeze follows completion of Part 2c in Part 2d.

All variants contain the same 600 seeded injections and full 300-star FA set. All searches and A/S records are complete and validated.

| Variant | R7–15 P8 | R7–15 P9 | R15–30 P8 | R15–30 P9 | FA_pre | FA_S | Median wall (s) | Exhausted partitions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| a | 119/291 | 109/291 | 230/265 | 221/265 | 576/300 = 1.920000 | 2/300 | 221.424643 | 578/3230 |
| b | 119/291 | 109/291 | 231/265 | 222/265 | 584/300 = 1.946667 | 2/300 | 256.944470 | 10/3230 |
| c | 112/291 | 110/291 | 226/265 | 217/265 | 640/300 = 2.133333 | 3/300 | 469.902493 | 1533/3230 |
| e | 146/291 | 137/291 | 233/265 | 227/265 | 709/300 = 2.363333 | 2/300 | 562.778421 | 627/3230 |

Chosen gain: 9.27835052 percentage points. FA_pre ratio to a: 1.23090278 (limit 1.5); median-wall ratio: 2.54162505 (limit 3). R7–15(b) exceeds R7–15(c), so e was the prescribed fourth variant; d was not run.

FA_S for a/b/e has equal counts, but e's surviving candidate identities differ. The seeded 10% A-failure sample is excluded from every FA_S count.

| Variant | Non-recovered injections | Epoch-matched ranking losses | Witnesses | Period-near losses |
|---|---:|---:|---:|---:|
| a | 248 | 69 | 158 | 87 |
| b | 247 | 70 | 172 | 90 |
| c | 258 | 85 | 256 | 106 |
| e | 218 | 52 | 124 | 68 |

Every competing score, all gate-confirmed witnesses and input hashes are retained in `search_injections_<variant>.json`; the corresponding paired comparison files report individual gains/losses. The final JSON includes all measurements and provenance hashes.

The existing `event_count_loss.{json,md}` reports the 10–30 d event-count mechanism without a decision: 282 recovered injections, 13 fail the kept-event count, 11 cross below three after exclusions, 7 of those passed the pre-gate, and only 1 has the event count as its sole A failure. These mechanisms overlap. The three-event threshold is unchanged.
