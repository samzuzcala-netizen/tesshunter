# The audit rules: every threshold, its origin, and its measured effect

Written 2026-09-03 (prompt 7). Every number below is stated once in
`src/tesshunter/audit_rules.py` and copied into every record the rules produce.
The rule code is `tesshunter.audit_prep` (preprocessing), `tesshunter.event_vet`
(the per-event examination, the removal rules and the kept-event statistics),
`tesshunter.star_vet` (the star-level tests) and `tesshunter.secondary` (the
full-phase secondary scan). `scripts/audit_p5.py` and `scripts/revet_p6.py` are
drivers over them.

Evidence tags: **[P5]** adopted in prompt 5 (`docs/AUDIT.md` section 1),
**[P6]** adopted or restated in prompt 6 (`docs/REVET.md` section 2), **[P7]**
introduced by prompt 7. In sections 0-7, **[M]** means measured in prompt 7 over all 405 survivors; section 8 labels the prompt-8 measurements **[P8]**.

**Nothing in this document is a verdict on any candidate.** The measured-effect
columns are counts of how many candidates a rule moves, not decisions about
them. The pipeline finds candidates.

## 0. The named rule sets

| set | version | the four prompt-7 options | used by |
|---|---|---|---|
| `LEGACY_RULES` | `p6.2` | all off | `audit_p5.py` and `revet_p6.py` by default, and `scripts/p7_reproduce.py`, so every P5 and P6 record still reproduces |
| `DEFAULT_RULES` | `p7.0` | all on | the unchanged package default; `--rules p7.0` on either driver |
| `P8_RULES` | `p8.0` | all on; the measured gate choices are retained | the P8 funnel with `--rules p8.0`; Stage B window values are stored without rounding |

A partial combination is stamped `p7.0-partial`, so a mixed-vintage directory
stays detectable. **[M]** `scripts/p7_reproduce.py` re-derived 823 prompt-6
records (405 Stage A, 405 prepare, 7 Stage B, 6 Stage C forced TLS) through the
ported code under `p6.2`: **0 field differences, 0 decision differences, largest
relative difference 0.0** — the seven prepared arrays of all 405 candidates are
bitwise identical to prompt 6's.

## 1. Preprocessing (`tesshunter.audit_prep`)

| rule | threshold | origin | measured effect on the 405 |
|---|---|---|---|
| quality mask | lightkurve default bitmask `17087` | [P5] | applied to every product |
| QLP low-precision flag | `2^12` sectors 1-55, `2^30` from sector 56 | [P5] | the flag the survey's `ffi.py` also masks; without it TLS fits sub-cadence "transits" to QLP garbage |
| product dropped | fewer than 50 usable cadences | [P5] | rare; recorded per product |
| detrend | wotan biweight, window `3 x T14`, floor `0.75 d`, cap `1.5 d`, break tolerance `0.5 d`, edge cutoff `0` | [P5] | the window is at its 0.75 d floor for most of the list |
| upward clip | `4 sigma`, upward only | [P5] | dips are what is being looked for, so only flares are clipped |
| isolated single-cadence dip | a point `< -6 sigma` whose two neighbours are both `> -2 sigma` | [P5] | no transit at P >= 0.5 d lasts one cadence |
| isolated single-bin dip | the same rule on the 30-minute bins | [P5] | |
| deep clip | bins deeper than `max(3 x candidate depth, 10 MAD)` | [P5] | keeps a binary host's eclipses out of the spectrum the candidate is tested in; prompt 6 measured deep points actually clipped on 69 of the 109 candidates that sit on a deep-event host |
| bins | 30 minutes; the bin error is the in-bin scatter at `>= 3` points, else propagated | [P5] | |
| **transit-masked detrend** | in-transit cadences within `1 duration` of every predicted mid-time kept out of the trend fit | **[P7]** | **[M]** see section 5, option 3 |

## 2. The per-event removal rules (`tesshunter.event_vet`)

An epoch counts as **observed** at in-transit coverage `>= 50%` with at least
`10` out-of-transit baseline cadences. The local baseline is a quadratic on the
quality-clean out-of-transit points within `max(3 durations, 0.5 d)`, with
out-of-transit starting at `1.3 x` the half-duration.

An observed event is **removed** when any of these holds. The last column is
prompt 6's census over all 405 (candidates whose *strongest* event the rule
removed / events it removed), which is the measured cost of each rule.

| rule | threshold | origin | carried / removed [P6] |
|---|---|---|---|
| momentum dump | quality bit `32` within `max(duration, 0.25 d)` | [P5] | 43 / 818 |
| sector or orbit edge | mid-transit within `max(duration, 0.2 d)` of a series edge or a gap `> 0.5 d` | [P5] | 30 / 369 |
| PDC gap | the same distance to a gap PDC cut out of the corrected flux, when it is not already an edge | [P5] | 93 / 374 |
| quality-flagged in transit | `> 20%` of in-transit cadences carry a default-bitmask flag | [P5] | 36 / 616 |
| scattered-light flags | `> 20%` of cadences within one duration carry bits `2048/4096` | [P5] | 88 / 1103 |
| SAP baseline ramp | the baseline changes by more than `1 x` the candidate depth across the event | [P5] | 117 / 790 |
| scattered-light ramp | background `> 2 x` the sector median **and** changing by `> 1 x` the median across the window | [P5] | 78 / 1064 |
| dip absent in SAP | the dip is `> 5 sigma` in the corrected flux and the SAP depth is `< 30%` of it | [P5] | 124 / 164 |

**[P6]** Over all 405: the strongest event survives every rule for 103
candidates, 302 lose it to at least one rule, and 2,957 of 8,697 observed epochs
(34%) are removed.

## 3. The kept-event statistics and the six Stage A criteria

Measured on the kept events in the wotan-detrended corrected flux, under the
ephemeris that gives the candidate the most credit (the one passing the most
criteria, ties broken by kept-event SNR). All six must hold.

| criterion | threshold | origin | failing under `p6.2` [P6] | failing under `p7.0` [M] |
|---|---|---|---:|---:|
| kept events | `>= 3` | [P6] | 52 | 62 |
| kept-event SNR | `>= 7` | [P6] | 345 | 337 |
| top-event share of the summed `(depth/error)^2` | `<= 0.50` | [P6] | 251 | 281 |
| SNR without the strongest kept event | `>= 5` | [P6] | 356 | 351 |
| kept depth / survey depth | `0.5` to `2.0` | [P6] | 359 | 349 |
| per-event depths consistent with a constant | `p >= 1e-3` | [P6] | 75 | 104 |

**[M]** Movement between the two sets, all 405: the depth window is gained by 14
candidates and lost by 4; depth consistency is gained by 13 and lost by 42; the
top-event share is gained by 12 and lost by 42. The two prompt-7 options that
touch these criteria pull in **opposite** directions — see section 5.

| red-noise inflation | threshold | origin |
|---|---|---|
| beta from binned out-of-transit residuals, bins of `duration / 3` | needs `> 60` cadences and `>= 3` bins | **[P7]**, the recipe already in `audit_p5.fit_step` |
| beta clipped to | `[1, 5]` | **[P7]** |

## 4. The star-level tests (`tesshunter.star_vet`)

### Stage B (i): the phase-independent window test — kills

A sector of cadence `<= 600 s` spanning `>= 1.5` candidate periods excludes the
period if its deepest transit-length running window is shallower than
`depth / 3` while the noise of a window mean is below `depth / 5`; a window
counts only at `>= 60%` fill. The window is `expected_t14_hours`. One excluding
sector kills. **[P6]** All thresholds prompt 6's.

**Its known limit [P6]:** a TESS sector spans about 25 d, so only P below roughly
17 d can be tested at all; five of the seven Stage B candidates had **zero**
testable sectors. **[M]** Over the 405 the test has no power on **295 of 405**
candidates (median period 72.2 d) and power on 110 (median period 12.2 d).

### Stage B (i-b): the long-period window test — flags, never kills **[P7]**

Where no sector spans `1.5` periods, count the sectors in which at least one
predicted epoch was observed and **every** one of them was removed by the event
rules, against the number of such sectors. Above `0.5` the candidate is flagged.

### Stage B (ii): Gaia DR3 — flags, never kills

| flag | threshold | origin |
|---|---|---|
| RUWE | `> 1.4` | [P6] |
| `ipd_frac_multi_peak` | `> 10%` | [P6] |
| `astrometric_excess_noise_sig` | `> 2` | [P6] |
| `non_single_star` | set | [P6] |
| `phot_variable_flag` | `VARIABLE` | [P6] |
| a neighbour within `3 px` bright enough to make the depth if totally eclipsed | | [P5] |
| Gaia RV amplitude | `> 4 x` the per-epoch error `x sqrt(N)` | [P5] |
| a VSX entry within `1 arcmin` | | [P6] |

### Stage B (iii): a deep-event host — flags, never kills

Another accepted candidate on the same star at `>= 30 ppt` **or** `>= 5 x` this
candidate's depth. **[P6]** 109 of the 405; on 69 of them the deep events are
inside the candidate's own search data.

## 5. The full-phase secondary scan (`tesshunter.secondary`) **[P7]**

Fold on the candidate ephemeris, scan every phase on a `0.002` grid for box dips
above `5 sigma`, merge dips closer than `0.02` in phase, refine each on a
`0.0004` grid over `+/- 0.01`. A dip within `0.03` of phase 0 is the primary.
The deepest other dip is re-measured in **raw SAP** (detrended with the same
biweight), and compared with the deepest secondary an irradiated planet could
produce at the star's circular-orbit a/R* — `vetting.planetary_secondary_bound_ppt`
at geometric albedo `0.3`.

* **gate FAIL**: the SAP depth exceeds that bound by more than `3 sigma`.
* **variability flag**: more than `5` dips at scattered phases; no secondary is claimed.

## 6. Measured effect of each prompt-7 option on the 405 [M]

Report-only. `scripts/p7_options.py`, records in `data/survey/p7/options/` and
`data/survey/p7/options_p7.json`. Each candidate is measured under the ephemeris
prompt 6 chose for it. Baseline: 7 Stage A PASS, 398 FAIL.

### Option 1 — the full-phase secondary scan

| quantity | value |
|---|---:|
| candidates scanned | 405 |
| dips above 5 sigma: median / p90 / max | 2 / 17.6 / 45 |
| scans with no dip at phase 0 (never gated: there is nothing for a secondary to belong to) | 106 |
| of those, dips elsewhere in the fold anyway | 59 |
| clean scans (a primary and nothing else) | 65 |
| **reach the gate** (a primary and at least one other dip) | **234** |
| variability-flagged (> 5 dips) | 99 |
| **gate FAIL** | **156** of the 234 |
| of those, variability-flagged | 78 |
| of those, quiet scans (<= 2 dips) | 41 |
| gate FAIL among the 7 Stage A passers | **6** |
| gate measured in SAP / in the detrended flux | 234 / 0 |
| deepest off-phase dip is a *bump* in SAP (negative depth) | 34 |

106 + 65 + 234 = 405. Every candidate that reaches the gate had its deepest
off-phase dip re-measured in SAP, so no gate decision anywhere rests on the
corrected flux alone.

The gate on the seven Stage A passers, with the SAP depth it decides on:

| rank | TIC | dips | primary (ppt) | second dip: phase, depth, sigma | SAP depth (ppt) | planet bound (ppt) | sigma over it | gate |
|---:|---:|---:|---:|---|---:|---:|---:|---|
| 16 | 233007823 | 2 | 2.637 | 0.6048, 2.505, 52.0 | 2.547 +/- 0.047 | 1.09e-03 | 54.2 | **FAIL** |
| 98 | 201247574 | 2 | 1.379 | 0.4308, 0.719, 5.7 | 0.281 +/- 0.128 | 2.93e-04 | 2.2 | PASS |
| 250 | 219419204 | 15 | 0.550 | 0.4408, 0.884, 20.3 | 0.221 +/- 0.046 | 3.06e-05 | 4.8 | **FAIL** |
| 279 | 188830181 | 41 | 28.753 | 0.5276, 12.216, 17.4 | 13.178 +/- 0.732 | 1.64e-03 | 18.0 | **FAIL** |
| 289 | 43668893 | 16 | 2.431 | 0.6040, 2.379, 10.5 | 1.713 +/- 0.206 | 3.38e-04 | 8.3 | **FAIL** |
| 325 | 219419204 | 17 | 0.973 | 0.3020, 1.147, 21.4 | 0.213 +/- 0.056 | 4.38e-05 | 3.8 | **FAIL** |
| 398 | 43668893 | 14 | 2.903 | 0.3664, 2.274, 10.0 | 2.013 +/- 0.224 | 3.80e-04 | 9.0 | **FAIL** |

Rank 16 is the case the scan was built for and it reproduces the prompt-6
re-analysis independently (`docs/REVET.md` section 10: 2.637 +/- 0.048 ppt at
phase 0.9996, 2.505 +/- 0.048 ppt at 0.6048, 0.95 x the primary, a/R* 27.0,
T_eq 780 K). Rank 98 is the one passer the gate keeps, and it keeps it for the
right reason: the second dip is 0.719 ppt in the corrected flux and only
0.281 +/- 0.128 ppt in SAP, so the SAP measurement pulls it back under the gate.

**A caution about what this gate actually tests [M].** At these periods the
planetary bound is `3e-5` to `2e-3` ppt — thousands of times below the
measurement precision. "More than 3 sigma above the bound" therefore reduces, in
this population, to "the SAP depth at the deepest off-phase dip is more than 3
sigma from zero". That is a correct statement about planets and it is why the
gate is decisive on rank 16; but it means the gate fires on any star with
ppt-level variability at any phase, which is why it fails 156 of 405. The
`variability_flag` separates the two cases (78 of the 156 failures are flagged;
41 have quiet scans of at most two dips, which are the genuine secondary-eclipse
detections). A second pass should decide whether the gate should require a quiet
scan as well; this pass does not change it.

### Option 2 — red-noise-inflated depth consistency

| quantity | value |
|---|---:|
| per-sector beta, median over candidates: p25 / median / p75 / max | 1.045 / 1.083 / 1.184 / 5.0 |
| per-sector beta, worst sector: median / p90 / max | 1.959 / 4.581 / 5.0 |
| candidates with a sector at the cap of 5 | 31 |
| depth consistency changes fail -> pass | 34 |
| of those, then pass all six criteria | 10 |
| Stage A PASS under this option alone (vs 7) | 17 |
| the 7 prompt-6 passers that still pass | 7 |

Of the 18 candidates that fail **only** depth consistency (`docs/REVET.md`
section 3), **10 now pass it**. The split is informative: the ones that flip are
the ones with large beta (rank 27, `p 1.4e-35 -> 0.65` at beta 5.0; rank 29,
`2e-48 -> 0.50`; rank 32, `8.4e-80 -> 0.39`; rank 234, `1.2e-24 -> 0.97`), and
the ones that do not flip are the deep eclipsing binaries the rule is there to
catch (rank 9, TIC 167304394, `9.2e-68 -> 8.5e-15`; rank 13, `0 -> 1e-184`;
rank 7, `2.5e-199 -> 6.2e-37`). **The inflation is powerful and it is a real
finding that it is:** a beta clipped at 5 can turn `p = 1e-24` into `p = 0.97`.
The white p-value stays on every record so the size of the correction is always
visible.

### Option 3 — the transit-masked detrend

Prompt 6 observed that every clean signal in the population comes back at 0.5-0.9
of its survey depth. **[M]** That is reproduced and it is the biweight absorbing
the transit:

| population | measure | unmasked | masked | masked / unmasked |
|---|---|---:|---:|---:|
| the 24 near misses (5 of 6 criteria) | depth / survey depth, p10 | 0.535 | 0.621 | |
| | median | **0.667** | **0.830** | **1.224** |
| | p90 | 0.779 | 1.257 | 1.899 |
| kept SNR >= 7 (60 candidates) | median | 0.611 | 0.806 | 1.323 |
| | inside the 0.5-2.0 window | 35 | 40 | |
| kept SNR >= 20 (24 candidates) | median | 0.596 | 0.778 | 1.340 |
| | inside the 0.5-2.0 window | 13 | 17 | |
| all 405 | median | 0.046 | 0.058 | 1.211 |
| | depth ratio increased / decreased | | | 304 / 93 |

Over all 405 the depth criterion is gained by 14 candidates and lost by 4, and
4 candidates pass all six under this option alone. The whole-population medians
are near zero because most of the 405 have no depth in clean events at all —
that is prompt 6's null, not a property of the detrend.

### Option 4 — the long-period window test

| quantity | value |
|---|---:|
| candidates it applies to (no sector spans 1.5 periods) | 295 |
| candidates it does not (Stage B (i) has power) | 110 |
| median survey period, applies / does not | 72.2 d / 12.2 d |
| sectors with an observed epoch, where it applies: median / p90 | 7 / 15 |
| fraction of sectors fully removed: median / p75 / p90 | 0.40 / 0.50 / 0.667 |
| **flagged** (fraction > 0.5) | **72** |
| flagged among the 7 Stage A passers | 1 (rank 250) |
| flagged among the 398 failures | 71 |

The test gives the long-period majority of the list a phase-independent
statement it never had, at the cost of nothing: it flags and never kills.

### All four together (`p7.0`)

| | `p6.2` | `p7.0` |
|---|---:|---:|
| Stage A PASS | 7 | **1** |
| Stage A FAIL | 398 | 404 |

Six candidates change, all PASS -> FAIL, **all six on the secondary gate**
(ranks 16, 250, 279, 289, 325, 398). **No candidate changes FAIL -> PASS.** The
one survivor is rank 98, TIC 201247574 — which prompt 6 identified as a
catalogued rotational variable (Gaia VARIABLE / SOLAR_LIKE, VSX ROT), so the
change is not a new candidate. 152 candidates keep their decision but gain a
variability or long-period flag.

The six pass-to-fail agree, one for one, with what prompt 6 concluded about those
same candidates on independent evidence (`docs/REVET.md` section 5): a catalogued
contact eclipsing binary, an eccentric eclipsing binary, and two stars whose Gaia
astrometry is not that of a single object.

## 7. The v2 ranking score

Defined in `docs/RANKING_SCORE.md` section 5; the frozen P4 score is unchanged.
**[M]** Over the 405: Spearman rho between the frozen rank and the v2 rank is
**-0.0063 (p = 0.90)** — the two orderings are unrelated. 156 rows are zeroed by
the secondary gate, 221 score exactly zero, and the maximum is 1.735 out of 2.
The Gaia penalty could be evaluated for only **36 of 405** candidates, because
Gaia DR3 was queried in prompts 5 and 6 only for the stars that reached Stage B
and prompt 7 queries nothing; every row records whether it had a cached record.

## 8. The prompt-8 decisions, measured (p8.0) **[P8]**

Instrument (`scripts/p8_decisions.py`): 1163 recovered prompt-8 injections (planets by construction), the 405 prompt-6 candidates under their prompt-6 ephemerides, and 18 adversarial eclipsing binaries plus 22 blends under their catalogued ephemerides. X = 90%, fixed before the measurement.

The variant instrument holds each event ephemeris fixed and uses it for the masked detrend. The injection ephemeris is the one selected by Stage A; the reference ephemerides are those stated above. This differs from a full Stage A run, which detrends around the survey ephemeris before fitting TLS. Thus the masked/cap5 column is a controlled variant measurement and need not exactly replay the stored Stage A decisions. The separate completeness calibration measures the actual full Stage A pipeline.

Current injection and adversarial scans supply their recorded gate variants, evaluated before the SAP display values were rounded. Their quiet-gate N counts the full phase-scan dip list, whereas the reported independent-dip count excludes primary shoulders; reconstructing gates from that count changes the implemented variants. Older prompt-7 scans lack variant decisions and use the documented shoulder reconstruction; the 405 are diagnostic only for Decision 1.

### Decision 1: the secondary gate (1089 Stage A-passing injections; p7.0 kills: 26 of the adversarial set, 152 of the 405)

| variant | injection completeness | injections held | adversarial kills retained | EBs killed | blends killed | 405 FAIL | 405 HOLD | eligible |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| bound | 901/1089 (82.7%) | 0 | 26/26 (100%) | 17/18 | 9/22 | 152 | 0 | yes |
| quiet_bound | 1029/1089 (94.5%) | 0 | 3/26 (12%) | 0/18 | 3/22 | 45 | 0 | no |
| quiet_zero_N2 | 1029/1089 (94.5%) | 0 | 3/26 (12%) | 0/18 | 3/22 | 45 | 0 | no |
| quiet_zero_N3 | 1003/1089 (92.1%) | 0 | 3/26 (12%) | 0/18 | 3/22 | 63 | 0 | no |
| quiet_zero_N5 | 965/1089 (88.6%) | 0 | 5/26 (19%) | 0/18 | 5/22 | 80 | 0 | no |
| quiet_bound_hold | 1029/1089 (94.5%) | 63 | 3/26 (12%) | 0/18 | 3/22 | 45 | 86 | no |

**Decision 1: `bound`** (highest completeness among variants retaining >= 90% of the p7.0 gate kills on the adversarial EBs and blends; ties to more kills, then to p7.0).

### Decisions 2 and 3 together: depth consistency and the masked detrend (1163 recovered injections; reference kill set 58 candidates, of which p7.0 fails 40 on depth consistency)

| detrend | errors | threshold | all six pass (injections) | depth-consistency pass | depth-window pass | p7.0 kills retained | p6.2 kills retained | 405 depth fail | 405 all six | eligible |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| unmasked | white | 0.001 | 1040/1163 (89.4%) | 93.1% | 99.1% | 95% | 100% | 75 | 7 | yes |
| unmasked | white | 0.0001 | 1067/1163 (91.7%) | 95.7% | 99.1% | 92% | 92% | 69 | 8 | yes |
| unmasked | white | 1e-05 | 1080/1163 (92.9%) | 96.9% | 99.1% | 92% | 90% | 64 | 9 | yes |
| unmasked | cap2 | 0.001 | 1094/1163 (94.1%) | 98.0% | 99.1% | 82% | 75% | 50 | 13 | no |
| unmasked | cap3 | 0.001 | 1094/1163 (94.1%) | 98.1% | 99.1% | 78% | 62% | 45 | 16 | no |
| unmasked | cap5 | 0.001 | 1094/1163 (94.1%) | 98.1% | 99.1% | 75% | 58% | 41 | 17 | no |
| masked | white | 0.001 | 1011/1163 (86.9%) | 89.6% | 99.1% | 100% | 100% | 152 | 4 | yes |
| masked | white | 0.0001 | 1044/1163 (89.8%) | 92.7% | 99.1% | 100% | 98% | 127 | 5 | yes |
| masked | white | 1e-05 | 1067/1163 (91.7%) | 94.7% | 99.1% | 98% | 96% | 106 | 5 | yes |
| masked | cap2 | 0.001 | 1088/1163 (93.6%) | 96.5% | 99.1% | 100% | 85% | 110 | 8 | yes |
| masked | cap3 | 0.001 | 1088/1163 (93.6%) | 96.6% | 99.1% | 100% | 77% | 107 | 8 | yes |
| masked | cap5 | 0.001 | 1089/1163 (93.6%) | 96.7% | 99.1% | 100% | 73% | 104 | 10 | yes |

**Decisions 2 and 3: `masked|cap5|0.001`** (highest all-six Stage A completeness among combinations retaining >= 90% of the p7.0 depth-consistency kills on the reference set (the 18 + adversarial EBs and blends); ties to more kills, then to p7.0).

Depth-consistency p-values on the recovered injections (constant injected depth). The uniform reference assumes the error model is correct; recovery selection, ephemeris estimation and event removal also condition this sample. The fractions below threshold are measured injection rejection rates, not unconditional nominal false-positive probabilities.

| detrend | errors | n | below 1e-3 | below 1e-2 | below 0.05 | median | KS uniform p |
|---|---|---:|---:|---:|---:|---:|---:|
| unmasked | white | 1163 | 6.9% | 12.2% | 22.5% | 0.268 | 3.7e-58 |
| unmasked | cap2 | 1163 | 2.0% | 4.1% | 9.4% | 0.535 | 0.00029 |
| unmasked | cap3 | 1163 | 1.9% | 4.0% | 9.3% | 0.540 | 0.00013 |
| unmasked | cap5 | 1163 | 1.9% | 4.0% | 9.3% | 0.540 | 7.5e-05 |
| masked | white | 1163 | 10.4% | 21.9% | 36.9% | 0.129 | 4.9e-162 |
| masked | cap2 | 1163 | 3.5% | 7.6% | 17.0% | 0.348 | 9.9e-29 |
| masked | cap3 | 1163 | 3.4% | 7.4% | 16.9% | 0.353 | 5.2e-28 |
| masked | cap5 | 1163 | 3.3% | 7.4% | 16.8% | 0.353 | 1e-27 |


The frozen set keeps secondary `bound`, masked detrending, inflated depth consistency, `beta_max=5`, and `p_min=1e-3`. Both white and inflated p-values remain in each record. `exact_t14_record=True` stores the Stage B window and duration without rounding and gives the set its distinct `p8.0` version. `DEFAULT_RULES` remains `p7.0` and `LEGACY_RULES` remains `p6.2`.

The best eligible cap-5 combination passes 1,089 injections, one more than cap 2 or cap 3. This follows the preregistered count comparison; it does not establish a statistically significant superiority for cap 5. The full Stage A calibration passes 1,093 injections: four differences from the fixed-ephemeris instrument are explained by exact replays with its original survey mask (`data/survey/p8/decision_mask_replay*.json`).

**[P8]** After freezing this implementation, `p7_reproduce.py all --slices 16 --out data/survey/p8/reproduce_p7_p8.json` re-derived all 823 historical records: **0 field differences, 0 decision differences, 0.0 worst relative difference**. The reproduced set is `p6.2`; the existing P7 option records were retained unchanged. The P8 version and boundary checks passed alongside the gate-serialization regression (12 tests).

**[P8]** The full suite passed **557 tests, 1 skipped**, with 9 dependency/deprecation warnings in 185.27 seconds. The real candidate list remained unopened through these checks and the P8 freeze commit.

## 9. The frozen prompt-10 rule set `p10.0` **[P10]**

Pre-registered in `HANDOFF_P10.md` section 0 (2026-09-08) before any measurement it judges. The rule code is `tesshunter.verdict_tiers`; every number is a `TIER_*` constant of `tesshunter.audit_rules`. `RuleSet` gains four prompt-10 fields (`verdict_tiers`, `stagec_peak_rule`, `stagec_sde_robust_fallback`, `duration_floor_cadence`); at their defaults every earlier set keeps its version string, so `p8.0`, `p7.0` and `p6.2` records replay unchanged. `P10_RULES` is now frozen in Part 2d: `p8.0` with `verdict_tiers="p10"`, `stagec_peak_rule="strongest"`, `stagec_sde_robust_fallback=True`, and `duration_floor_cadence=True`. The secondary gate remains `bound`. Other combinations of the prompt-10 fields are stamped `p10.0-partial`.

**What changes.** SUBMIT means a CTOI-grade candidate, not a validated planet. Stage B's flags stay measured and recorded on every record; under `p10.0` the P8 cap is stored as `b_flag_cap_p8` and no flag caps the verdict. A candidate that reaches D is evaluated in the order K0..K9, then H1..H4, then SUBMIT; the first condition that holds decides, every condition is still evaluated and recorded numerically, and a condition whose inputs are missing is "not measurable" (never "not fired"). The fresh hard stop precedes the tiers as K0 (a REJECT is not a candidate; a FLAG is an association, F7).

| tier | condition | threshold | origin |
|---|---|---|---|
| K0 | hard stop REJECT at this TIC | six catalogues, TIC match | [P1], [P8] |
| K1 | Stage A fails | the six p8.0 criteria, unchanged | [P6], [P8] |
| K2 | secondary gate fails | the selected 2a mode `bound` | [P7], [P8], [P10] |
| K3 | Stage B phase-independent exclusion | unchanged | [P6] |
| K4 | Stage C fails | strongest peak, with the conditional robust fallback and cadence floor | [P5], [P10] |
| K5 | period is an integer alias (2:1, 1:2, 3:1, 1:3, 3:2, 2:3, within 1%) of a deeper accepted signal (> 30 ppt or > 5x the depth) on the star, or of a catalogued VSX / TESS-EB / TOI / CTOI period within 1 arcmin (1:1 included) | `TIER_ALIAS_*` | [P10] |
| K6 | odd/even depth difference of the all-transit fit > 3 sigma, with >= 2 odd and >= 2 even transits | `TIER_ODD_EVEN_*` | [P3], [P10] |
| K7a | difference-image maximum within 3 px of the target (`TIER_K7_SEARCH_PX`, HANDOFF_P10.md 0.11 note 5; the whole-cutout literal form is recorded beside it) lying within 1.0 px of a resolved Gaia neighbour, > 1.5 px from the target, > 3 x its event scatter, in >= 2 sectors | `TIER_K7_*`, `TIER_PIXEL_SIGMA`, `TIER_MIN_SECTORS` | [P10] |
| K7b | net fixed-aperture depth `d_s < 0.5 D_ref - 3 sigma_s` where `0.5 D_ref >= 3 sigma_s`, in >= 2 sectors; sectors with < 16 sky pixels, a zero error or `0.5 D_ref < 3 sigma_s` are unmeasurable | `TIER_DILUTION_ALLOWANCE`, `TIER_MIN_SKY_PIXELS` | [P10] |
| K8 | fitted radius > 1.5 R_Jup (16.81 R_Earth); or density prior rejected (delta chi2 >= 9) with a converged, non-grazing fit and `rho_fit / rho_cat` outside [0.5, 2] | `TIER_MAX_RADIUS_RJUP`, `TIER_DENSITY_*` | [P10] |
| K9 | artefact-carried under D review: `|r| > 0.7` between the raw aperture and sky series over the event windows (3 fit durations) in >= 2 sectors, AND the net depth disagrees with D_ref (`> D_ref + 3 sigma_tot`, `< 0.5 D_ref - 3 sigma_tot`, or `< -3 sigma_s`) in >= 2 sectors, AND the reviewer's recorded artefact decision; the reviewer may not apply K9 when the criterion does not hold | `TIER_K9_*` | [P8] class, [P10] criterion |
| H1 | TRICERATOPS NFPP >= 0.5 on the binned fold; `fpp_uniform` is unavailable, not a HOLD | `TIER_NFPP_HOLD` | [P3], [P10] |
| H2 | fit unconverged (`uncertainty_issues`) or grazing rail with `b_err > 0.5` or `T14_err >= T14` | `TIER_GRAZING_B_ERR` | [P8], [P10] |
| H3 | a D measurement (fit, FPP, centroid, difference image, fixed aperture) did not execute; operational, cleared by a re-run | | [P10] |
| H4 | a VSX EA / EB / EW / ELL within 21 arcsec of the target whose period matches no alias (a match is K5); other classes are flags | `TIER_VSX_*` | [P10] |

`D_ref` (section 0.1.1): the adopted fit's `depth_avg_ppt` when H2 does not hold, else the Stage A kept-event weighted mean depth under the chosen ephemeris. The dilution allowance 0.5 (K7b, K9b) and the K8 factor-2 guard are the documented refinements of the prompt's defaults (HANDOFF_P10.md 0.11).

**The flag list F1-F9** travels with every SUBMIT (record, packet, `ctoi_fields.json`): F1 every neighbour within 63 arcsec that could produce the depth by total eclipse with the eclipse fraction it would need; F2 Gaia RUWE, `ipd_frac_multi_peak`, excess-noise significance, `non_single_star`, variability flag; F3 VSX and SIMBAD within 1 arcmin; F4 FPP and NFPP with caveats; F5 pixel localisation (on target / unlocalised / not measurable) with per-sector fixed-aperture depths, errors and centroid significance; F6 other accepted signals on the host; F7 TCE / TOI / CTOI association; F8 the eight-class artefact census of the events; F9 `validation_status`, the specific external evidence that would settle the source.

Tests: `tests/test_p10_tiers.py` fires and just-fails-to-fire every K and H condition at its threshold and checks that `p8.0` keeps its version, stamps no tier block, and that `revet_p6.provisional_verdict` is unchanged on a record without `tiers`.

### 9.1 The re-derivation on seen records (Part 1c) **[P10]**

`scripts/p10_tier_rederivation.py` re-scores the 19 P8 B passers and the 16 P9 final candidates from their saved records (`p10/results/tier_rederivation.csv`). It is a re-scoring under a rule written before it ran, not a rerun and not a finding about the sky; K2 and K4 are the saved p8.0 decisions.

| set | n | not permitted (C FAIL) | KILL | HOLD | SUBMIT-equivalent | deciding conditions |
|---|---:|---:|---:|---:|---:|---|
| P8 B passers | 19 | 13 | 4 | 1 | 1 | K8 x3, K9 x1, H3 x1 |
| P9 finals | 16 | 0 | 3 | 0 | 13 | K8 x2 (TOI-762 A b, TOI-5855.01 negative), K6 x1 (TOI-122 b) |

Three of the four P8 KILLs stay KILL; TIC 144277542 is SUBMIT because the K9 numeric criterion holds in one sector, not two. Twelve of the fourteen P9 useful HOLDs are SUBMIT-equivalent; two confirmed planets are killed at the pre-registered K6 and K8 thresholds. Under the literal whole-cutout K7a, TOI-6002 b would also be KILL (two 3 to 4 sigma maxima at the cutout edge, 10 px from the target). The full table and the per-condition numbers are in `HANDOFF_P10.md` section 2.

### 9.2 Part 2a: the secondary-scan modes, measured **[P10]**

Instrument `scripts/p10_secondary_modes.py` (`data/survey/p10/secondary_modes/`, `p10/results/secondary_modes.{json,md}`): one scan per candidate on identical inputs, the rescanned `bound` gate equal to the saved p8.0 decision on all 1,343 records. Pre-registered rule (HANDOFF_P10.md 0.2, Y = 90%): the lowest injection false-kill rate among modes retaining at least 90% of the p8.0 `bound` kills on the adversarial EB and blend set and failing TIC 233007823.

| mode | definition | injection false kills (1,093 A passers) | p8.0 adversarial kills retained (26) | EBs / blends killed (18 / 22) | TIC 233007823 | eligible |
|---|---|---:|---:|---|---|---|
| `bound` (p8.0) | SAP dip > bound + 3 x white error | 189 (17.3%) | 26 (100%) | 17 / 9 | FAIL | yes |
| `empirical_bound` | SAP dip > bound + 3 x the track's robust off-phase scatter | 133 (12.2%) | 21 (81%) | 16 / 5 | FAIL | no |
| `recurrent_bound` | `empirical_bound` and the dip recurs (>= 2 sigma in >= half of the covered events, never fewer than 2, or >= 2 sigma stacked in two sector groups) | 40 (3.7%) | 18 (69%) | 14 / 4 | FAIL | no |
| `recurrent_bound_corr` | `recurrent_bound` and >= 3 sigma in both the SAP and the corrected flux | 40 (3.7%) | 18 (69%) | 14 / 4 | FAIL | no |

**Decision: `bound`**, the only eligible mode; `p10.0` keeps the p8.0 secondary gate. The new modes' lost kills are mostly TFOP nearby-EB blends whose diluted secondaries lie within the scan's own scatter. Descriptively, 124 to 128 of the 170 P8 secondary rejections would pass under the new modes (their truth is unknown); every labelled planet on the development hosts passes every mode. The three modes and their measurements stay in the package for a later prompt.

### 9.3 Part 2b: the complete paired search comparison **[P10]**

Measured 2026-09-10T05:30:20.000426+00:00.

The frozen rule selects **e (survey_p10_both)**. Part 2d freezes this effective configuration as survey_p10.

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

### 9.4 Part 2c: complete controls and adoption limits **[P10]**

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

### 9.5 Part 2d: freeze and compatibility checks **[P10]**

 The full suite passed 758 tests, 1 skipped, 9 warnings (129.60 s). Eight subsequent focused ownership/provenance checks passed for the new injection controller (0.27 s). P7 ran all 16 slices through `p10/protocol/p7_reproduce_p10.py`, the exact original algorithm with all six runtime P7 paths redirected. It reproduced 823 records with 0 field differences, 0 decision differences, worst relative difference 0.0, and preserved all 2,513 original P6 JSON/NPZ file hashes. Evidence: `p10/results/part2d_20260911/` and `data/survey/p10/part2d/p7/`.

**Seeded P8 replay, actual modes.** Seed 20260908 selects 20 keys from sorted settled p8.0 Stage A records, recorded once in `p8_replay_selection.json`. The actual `scripts/p8_funnel.py --rules p8.0 --root <isolated-P10-root> stageA --slices 16 --threads 1` returns 20/20 cached records byte-identically. A separate root omits Stage A/events and recomputes them using the original saved preparation and forced-TLS inputs: every scientific field is exactly equal (P7 comparator, worst relative 0.0), while 0/20 full fresh records are byte-identical because generation times and measured seconds differ. Cached byte identity is not presented as fresh byte identity. Original selected P8 records/inputs remain unchanged. No new held-out or real-candidate stage was opened.

The full selected-preset calibration is now complete. All 2,100 searches and all 1,240 recovered-injection A/S pairs validate; the original P8 curve is preserved. Section 9.6 records the complete comparison and original Stop Rule 1 decision.


### 9.6 Part 2d: full calibration and Stop Rule 1 **[P10]**

**STOP.** Calibration closed on 2026-09-12 at 15:25:46 UTC. The original after-A/S SNR50 is **18.26124 [17.68572, 18.95767]**, above the required **14.0**. The central-model projected C-load range is **37.96009–69.29786**, below the 150 limit. Both conditions must pass; Parts 3–5 were not run, and the adaptive two-hour heartbeat is verified PAUSED.

All five levels use 2,100 injections and the original 1,000 individual-injection bootstrap resamples for the 16–84% intervals.

| Level | P8 through / 2,100 | P10 through / 2,100 | P8 SNR50 [16–84%] | P10 SNR50 [16–84%] | P8 SNR90 [16–84%] | P10 SNR90 [16–84%] |
|---|---:|---:|---|---|---|---|
| Search only | 1,163 | 1,240 | 13.15 [12.86, 13.46] | 11.58 [11.31, 11.88] | 31.65 [30.08, 33.30] | 29.78 [28.24, 31.57] |
| Search + pre-gate | 1,121 | 1,184 | 14.08 [13.78, 14.40] | 12.74 [12.47, 13.03] | 31.44 [29.89, 33.03] | 30.12 [28.55, 31.85] |
| Search + A | 1,093 | 1,164 | 14.65 [14.31, 15.00] | 13.05 [12.73, 13.38] | 36.66 [34.67, 38.72] | 35.05 [32.98, 37.27] |
| Search + A + S | 904 | 964 | 20.19 [19.56, 20.96] | 18.26 [17.69, 18.96] | 75.18 [69.71, 81.86] | 76.96 [71.10, 84.52] |
| Search + pre-gate + A + S | 896 | 952 | 20.44 [19.80, 21.17] | 18.63 [18.05, 19.32] | 73.98 [68.55, 80.32] | 75.47 [69.78, 82.69] |

Frozen section 0.5 names a baseline of 20.19, which identifies the after-A/S level without pre-gate. Earlier operational prose used the whole pre-gated funnel name. Both are explicitly reported: 20.19 → 18.26 after A/S; 20.44 → 18.63 including the pre-gate. Both fail 14.0, and no frozen wording or criterion is changed. The original yield engine's central curve is the pre-gated whole funnel.

**Loss localization.** There are 1,240 recovered, 765 missed and 95 alias outcomes; aliases are not credited. The sequential path is 2,100 → 1,240 search → 1,184 pre-gate → 1,141 A → 952 S. Without pre-gate conditioning, A rejects 76/1,240 and bound S rejects 200/1,164 A passers (17.18%, compared with P8's 189/1,093 = 17.29%). The pre-gate removes 12 of the 964 A/S passers. Search gains 77 recoveries; the full funnel gains 56 (896 → 952). After-A SNR50 is 13.05 and rises to 18.26 after S: the retained secondary gate remains the main downstream sensitivity loss. Overlapping A criterion failures are retained in the calibration JSON; no post-hoc gate change was made.

**False alarms.** The same 300 selected-e control stars yield 709 pre-gate candidates, 45 A passers and two A+S survivors. All 709 A and 111 S records validate and their identities/decisions equal the earlier selected-e p8.0 comparison. The 66 seeded A-failure controls are excluded from FA_S. FA_S=2/300; FA_S × 2,531 = 16.873333.

**New-curve yield.** The original P8/DC15 numerical model uses the new pre-gated curve and claimed fraction 0.03 in every class. All 2,000 saved original noise records were copied byte-for-byte into P10 and verified unchanged after execution. For these stars the model predicts 21.086755 signals through the funnel (search-only 28.277649; inherited HU19 occurrence sensitivity 27.634104). Legacy low/mid/high output keys are equal because their claimed fractions are equal; they are not uncertainty bounds. The explicitly renamed P8 yield>=3 diagnostic does not decide P10 continuation.

The possible additional stars have no measured noise in this calibration. Perfect recovery and the 531 largest geometric weights of the entire 1,837-star bare-SPOC source pool bound any eventual subset of at most 531 by 31.337769 signals. This yields a central-model E_S range of 21.086755–52.424524 and expected C-load range of 37.960088–69.297857. No Part 3 population was selected and no new TCE ephemerides or candidate outcomes were opened. This range bounds the missing-population contribution under the adopted model; it is not a confidence interval or a realized-count bound. The earlier perfect-recovery all-population load bound was 148.931096.

The latest full regression was 774 passed, 1 skipped, 9 warnings, followed by ten focused correction/routing tests and three bound tests. Thirteen final yield/bound/legacy-model tests pass. Original P7 reproduction and the separately described cached/fresh P8 replay evidence remain valid. The calibration controller's schema-only validation correction preserved every worker record, numerical threshold and timing. It waited for exact original-owner closure, reused all 709 A records, and completed the remaining phases. The failed original guard report remains historical evidence.

**Assumptions and limits.** Individual-injection bootstrap intervals omit within-star dependence and population/model uncertainty. The empirical two-survivor FA rate is extrapolated unchanged. The HU19 result is the inherited occurrence-box rescaling sensitivity, with its radius/subtype assumptions, not a replacement for the central stop criterion. Later B/C/D losses and final candidate yield are unmeasured. The Part 2c alias, out-of-grid, development-exposure and suspended-timing caveats in section 9.4 remain binding.

Exact tables, all bins, decision, figure, yield/noise provenance and closed seals are under `p10/results/part2d_calibration_20260912/`; see `STOP_RULE_1.md`, `stop_rule_1_decision.json`, `full_calibration_closed_seal_20260912.json`, `expected_yield_projection_p10.json` and `yield_model/`. The calibration seal covers 15,583 files / 7,915,270,129 bytes. `finalization_20260912/automation_paused_verified.json` records the confirmed pause with the two-hour default retained. P8/P9 inputs and frozen section 0 remain unchanged.
