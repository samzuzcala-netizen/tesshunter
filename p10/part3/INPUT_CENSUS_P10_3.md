# Prompt 10.3 input census

## Measurements [M]

| Population cut | Remaining stars | Excluded at this cut |
|---|---:|---:|
| Source pool | 117,171 | |
| Incumbent domain | 11,491 | |
| Bare SPOC TCE rejection only | 531 | |
| Gaia dwarf pass | 473 | 58 |
| Corrected strict-minority two-minute inventory | 473 | 0 |
| Verified usable sectors after Part D | Pending | Pending |
| Evaluated by blind search | 0 | Not launched |

All 50 MIT sector lists from 56 through 105 were present, nonempty and checked.
Recomputed intersections reproduce the pool's counts on every one of the 531.
The supplied prompt's target-list directory was a transcription error: actual
MIT lists and P9's repaired parser use `data/survey/cache/twomin_lists`.

The pool-wide sidecar contains 10,382 rows selected from all 342,918 raw rows in
132 files. The original 531 have 2,809 rows and 1,669 distinct period families,
with median two rows and maximum 64 rows per star. Run duplicates remain in the
sidecar; family deduplication is confined to the census/matching code.

| Population | Stratum | Raw rows | Families | Likely-periodic in-band families | Hosts with such rows |
|---|---|---:|---:|---:|---:|
| Original 531 | INDEPENDENT | 2,037 | 1,250 | 119 | 97 |
| Original 531 | OVERLAPPING | 772 | 564 | 66 | 57 |
| Original 531 | UNION | 2,809 | 1,669 | 145 | 108 |
| After A: 473 | INDEPENDENT | 1,778 | 1,117 | 98 | 83 |
| After A: 473 | OVERLAPPING | 649 | 502 | 58 | 49 |
| After A: 473 | UNION | 2,427 | 1,493 | 120 | 90 |

Families with rows in both strata occur in both stratum tables and only once in
the union. The 98 independent qualifying families are an upper bound before
usable-sector verification, not the post-D STOP-1 count.

All 531 catalogue outcomes change from REJECT to FLAG under hard_stop_p10;
all 2,000 original P8 records are equal under both rules. The six normalized
catalogues and existing crossmatch digests are byte-identical. The comparisons
use the existing pinned catalogue snapshot, including its disclosed age; no
fresh novelty or endpoint conclusion is made.

The focused catalogue suite passed 58 tests with one skipped existing optional
test; two additional acquisition-policy/accounting tests passed. The entry full
regression passed 891 tests, one skipped, in 158.01 seconds. Entry integrity
verified 554 historical source/index records, 15,583 P10 calibration files,
16,698 raw/FITS files, 1,041 historical checks, and 63,168 P11.5 source/evidence/
data files. There were zero mismatches. Check collections overlap.

## Assumptions [A]

The fixed input cuts, independence definition, family anchoring, SNR >=12 and
>=3-transit likely-periodic definition, 0.5-30-day band, and catalogue adapter
are registered in PREREGISTRATION_P10_3.md. No flux, search outcome, forced fit
or retention statistic was used for the population selection. Input exclusions
do not count as misses. No search/funnel/calibration result has yet been measured.
