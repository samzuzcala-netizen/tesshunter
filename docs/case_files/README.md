# Case files for the top-10 survivors (prompt 4, step 6)

One half-page file per candidate, written by hand from the packet in
`docs/packets/survey_v1/<same name>/` after the expensive steps (whole-stitch
refit, centroid on every sector with pixel data, TIC contamination,
TRICERATOPS) had run. Ranks are the FINAL frozen-score ranks of
`data/survey/p4/survivors.csv` (S_fpp from the measured FPP). Every file has
the same four parts: the signal, why it is likely real, what would kill it,
what would settle it. Evidence tags: [M] measured in this survey or the
packet, [A] adopted assumption. Nothing here is a detection and nothing has
been submitted; prompt 5 audits these files last, after its own independent
re-detection.

Two properties of the P3 fit matter for reading the numbers, both recorded
in `HANDOFF_P4.md` as open items: on 30-minute stitches with a large
red-noise beta the fit sometimes takes neither the density flag (which uses
the beta-discounted delta chi2) nor the density prior (which uses the raw
delta chi2), and then reports the free solution on the grazing rail
(b = 1.2, Rp/R* and T14 with errors larger than the values); where that
happened the case file quotes the BLS box and the duration-averaged depth
instead. And the survey's BLS box duration is capped at 0.5 d (12.0 h) and
floored at 0.045 d (1.08 h); a value at either rail is flagged in the file.

| final rank | file | TIC | P (d) | final verdict | FPP |
|---:|---|---:|---:|---|---:|
| 1 | `tic233211748_P65.0083.md` | 233211748 | 65.0083 | ambiguous / manual vetting required | 0.000 |
| 2 | `tic212261364_P8.9538.md` | 212261364 | 8.9538 | promising planet candidate | 0.008 |
| 3 | `tic160619045_P91.6642.md` | 160619045 | 91.6642 | ambiguous / manual vetting required | 0.000 |
| 4 | `tic334678787_P46.2063.md` | 334678787 | 46.2063 | promising planet candidate | 0.000 |
| 5 | `tic290350156_P13.2030.md` | 290350156 | 13.2030 | ambiguous / manual vetting required | 0.012 |
| 6 | `tic21124154_P89.2278.md` | 21124154 | 89.2278 | likely false positive | 0.143 |
| 7 | `tic356976754_P11.7890.md` | 356976754 | 11.7890 | likely false positive | 0.458 |
| 8 | `tic246937997_P2.4571.md` | 246937997 | 2.4571 | likely false positive | 0.249 |
| 9 | `tic167304394_P22.7802.md` | 167304394 | 22.7802 | likely false positive | 0.833 (uniform posterior) |
| 10 | `tic233200485_P70.6808.md` | 233200485 | 70.6808 | likely false positive | 0.900 (uniform posterior) |
