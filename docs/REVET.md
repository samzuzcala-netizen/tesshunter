# Re-vetting of all 405 P4 survivors under the prompt-5 audit rules (prompt 6)

Date: 2026-09-03. Branch `improve/recovery`. Every candidate was processed by the same final
code, stamped `rules_version = "p6.2"` in every record (`data/survey/p6/`).

Evidence tags: **[M]** measured in this session, **[P4]** taken from the P4 survivor row, packet
or case file, **[A]** an adopted threshold or assumption of this re-vetting. The pipeline finds
candidates; nothing here is a detection and nothing was submitted anywhere.

## Result in one line

**Nothing survives. The ordered list to submit is empty: SUBMIT 0, HOLD 0, KILL 405.** Seven of
the 405 survivors passed the per-event test (Stage A), six of those passed the star-level tests
(Stage B), and none of the six was re-detected by a blind Transit Least Squares search at its own
period (Stage C), so Stage D audited nothing and no `ctoi_fields.json` was filled. The census
below says why: **302 of the 405 survivors (75%) are carried by an event that the removal rules
delete**, and the largest single class is still the one prompt 5 found in the top ten — a dip that
exists in the corrected flux and not in the raw SAP flux.

The one borderline kill in the funnel, rank 16, was re-analysed afterwards and is **settled**: it
is an eccentric eclipsing binary with a 52-sigma secondary eclipse at phase 0.605 that no stage of
the funnel, and no P4 packet, ever looked for. Section 10.

## 1. The funnel

| stage | what it tests | entered | records | PASS | stars in | stars out |
|---|---|---:|---:|---:|---:|---:|
| A | every predicted epoch over the whole baseline, removal rules of `AUDIT.md` 1.3 | 405 | 405 | 7 | 261 | 5 |
| B | phase-independent sector test (kills); Gaia / deep-event host (flag only) | 7 | 7 | 6 | 5 | 4 |
| C | blind TLS 0.5-110 d, oversampling 3 | 6 | 6 | 0 | 4 | 0 |
| D | full prompt-5 audit of every Stage C PASS | 0 | 0 | 0 | 0 | 0 |

[M] `data/survey/p6/funnel_p6.json`. All 405 Stage A records exist, all carry `rules_version
"p6.2"`, and none is an ERROR. Fewer than 40 stars reached Stage C, so Stage C ran at the default
oversampling 3, not 2.

**Stage 0** [M]: 261 stars, 9,292 products (564 SPOC 2-min, 3,490 TESS-SPOC, 5,238 QLP), 0 failed
products, 4.8 GB, 62 minutes on four workers with one `search_lightcurve` per star. One star
(TIC 160619012) hung on a stalled MAST read, was killed and re-downloaded alone in 33.5 s; two
single products failed on transport errors and were re-downloaded, after which every star has zero
failures. Eleven stars carry a TESS-SPOC product whose header `SECTOR` is 1751: a real 7.2-day
200-s window at BTJD 4055.8-4063.0 that overlaps no other product and is carried through as its
own unit.

## 2. Thresholds, stated once and applied to all 405 [A]

Stage A — under the ephemeris that gives the candidate the most credit (the one passing the most
criteria; ties broken by kept-event SNR), all six must hold, measured on the kept events in the
wotan-detrended corrected flux:

| criterion | threshold |
|---|---|
| kept events | >= 3 |
| kept-event SNR (weighted mean depth / its error) | >= 7 |
| share of the summed (depth/error)^2 carried by the strongest kept event | <= 0.50 |
| kept-event SNR with that event removed | >= 5 |
| kept weighted depth, in units of the survey depth | 0.5 to 2.0 |
| per-event depths consistent with a constant | p >= 1e-3 |

Event removal is exactly `docs/AUDIT.md` section 1 step 3, unchanged: momentum dump within one
duration; sector, orbit or PDC-gap edge within one duration; more than 20% of in-transit cadences
quality-flagged or of near-transit cadences scattered-light flagged; scattered-light or SAP-baseline
ramp; a dip above 5 sigma in the corrected flux at below 30% of that depth in SAP.

Stage B — (i) a sector of cadence <= 600 s spanning >= 1.5 candidate periods excludes the period if
its deepest transit-length running window is shallower than depth/3 while the noise of a window mean
is below depth/5; a window counts only if >= 60% of its cadences are present [A]; one excluding
sector kills. The window is the central-transit duration `expected_t14_hours`, as specified.
(ii) Gaia DR3 flags: RUWE > 1.4, `ipd_frac_multi_peak` > 10%, `astrometric_excess_noise_sig` > 2,
`non_single_star` set, `phot_variable_flag` VARIABLE, a neighbour within 3 px bright enough to make
the depth if totally eclipsed, a Gaia RV amplitude above 4x its per-epoch error times sqrt(N), or a
VSX entry within 1 arcmin. (iii) another accepted candidate on the same star at >= 30 ppt **or**
>= 5x this candidate's depth. (ii) and (iii) flag but never kill; a flagged candidate can reach HOLD
at most.

Stage C — PASS means the strongest blind TLS peak lies within 1% of the survey period at SDE >= 9.
An exact 2:1 or 1:2 alias within 1% at SDE >= 9 passes only if TLS's per-transit depths at that
period are consistent with a constant at p >= 1e-3 [A]. Preprocessing is the `tls` step's final
form: default quality mask plus QLP's low-precision flag (2^12 for sectors 1-55, 2^30 from 56),
isolated single-cadence dips dropped, binned points deeper than 3x the candidate depth dropped.

### A limitation of test (i) that the records make visible [M]

The window is `expected_t14_hours` (a central transit), but the survey's own box duration is
usually shorter. A T14-long window then averages in out-of-transit cadences and measures a
shallower dip than the transit really has, against a threshold of only depth/3. On the one
candidate the test killed, the median deepest window is 1.40 ppt with the T14 window and 2.63 ppt
with the survey's own duration, a dilution factor of 1.9 against a tolerance of 3. Every Stage B
record carries `median_deepest_window_ppt_at_survey_duration`, `survey_duration_over_t14` and a
per-sector `margin_over_threshold` so the effect is auditable. The decision uses the specified
T14 column only; the one borderline case is called out in section 5.

Test (i) also has no power at long periods: a TESS sector spans about 25 days, so only candidates
with P below roughly 17 days can have a sector covering 1.5 periods. Five of the seven Stage B
candidates had **zero** sectors that could test them phase-independently.

## 3. Stage A: what the 398 failures fail

| criterion | candidates failing it |
|---|---:|
| kept depth outside 0.5-2 x the survey depth | 359 |
| SNR without the strongest kept event < 5 | 356 |
| kept-event SNR < 7 | 345 |
| strongest kept event carries > 50% of the signal | 251 |
| per-event depths inconsistent with a constant (p < 1e-3) | 75 |
| fewer than 3 kept events | 52 |

Criteria passed, out of six: 6 -> 7 candidates, 5 -> 24, 4 -> 16, 3 -> 114, 2 -> 184, 1 -> 56,
0 -> 4. The ephemeris that gave the candidate the most credit was the forced-TLS one for 234
candidates, the survey's own for 163 and the P4 packet refit for 8 (31 candidates have a packet).
One candidate (rank 357, TIC 219420268, P = 1.579 d) had a degenerate narrow TLS that fits no
transit at all and returns null counts; it was examined under the survey ephemeris alone and its
record says so.

The dominant failure is the same one prompt 5 found: the survey's depth is not reproduced by the
clean events. 359 of 405 candidates carry a kept-event depth outside half to twice what the survey
reported, and 356 lose their signal entirely when the single strongest event is removed.

### Near misses: the 24 candidates that fail exactly one criterion

None of these entered Stage B; they are listed so a reader can see what the single rule excluded.

| rank | TIC | P (d) | survey depth (ppt) | ephemeris | kept / observed | kept SNR | kept depth (ppt) | x survey | p(const) | the criterion it fails |
|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---|
| 7 | 356976754 | 11.7890 | 3.97 | survey | 65 / 80 | 46.38 | 3.048 | 0.77 | 2.5e-199 | depths inconsistent |
| 9 | 167304394 | 22.7802 | 59.03 | tls | 26 / 41 | 685.85 | 45.163 | 0.77 | 9.2e-68 | depths inconsistent |
| 13 | 219087933 | 10.5395 | 15.89 | survey | 80 / 102 | 182.99 | 11.350 | 0.71 | 0 | depths inconsistent |
| 18 | 290470328 | 7.4070 | 6.82 | tls | 20 / 27 | 30.09 | 4.910 | 0.72 | 2.6e-19 | depths inconsistent |
| 27 | 38763320 | 74.8826 | 2.76 | survey | 11 / 15 | 25.99 | 2.144 | 0.78 | 1.4e-35 | depths inconsistent |
| 28 | 284190863 | 18.7036 | 1.22 | survey | 22 / 30 | 21.04 | 0.948 | 0.78 | 1.5e-04 | depths inconsistent |
| 29 | 38763320 | 55.5275 | 2.59 | survey | 12 / 21 | 28.33 | 2.284 | 0.88 | 2.0e-48 | depths inconsistent |
| 32 | 38763320 | 37.8613 | 2.35 | survey | 21 / 33 | 22.39 | 1.486 | 0.63 | 8.4e-80 | depths inconsistent |
| 55 | 167306694 | 68.8041 | 0.66 | survey | 12 / 15 | 13.04 | 0.413 | 0.62 | 4.9e-23 | depths inconsistent |
| 63 | 356976754 | 13.6310 | 4.04 | survey | 58 / 73 | 44.42 | 2.704 | 0.67 | 2.9e-193 | depths inconsistent |
| 70 | 443906905 | 1.8313 | 1.15 | tls | 73 / 107 | 14.41 | 0.464 | 0.40 | 0.01 | depth outside 0.5-2x |
| 75 | 154841570 | 14.1187 | 5.22 | survey | 21 / 23 | 16.48 | 3.354 | 0.64 | 3.2e-15 | depths inconsistent |
| 82 | 167306694 | 89.7410 | 0.94 | survey | 7 / 10 | 9.89 | 0.493 | 0.52 | 5.6e-12 | depths inconsistent |
| 146 | 356976754 | 1.1052 | 4.58 | tls | 648 / 850 | 143.46 | 2.562 | 0.56 | 0 | depths inconsistent |
| 150 | 142750265 | 54.5464 | 18.89 | tls | 3 / 3 | 15.02 | 3.222 | 0.17 | 0 | depth outside 0.5-2x |
| 183 | 289722962 | 90.9529 | 2.85 | survey | 5 / 7 | 13.77 | 2.302 | 0.81 | 8.8e-28 | depths inconsistent |
| 202 | 188830181 | 59.6804 | 35.52 | survey | 6 / 8 | 21.05 | 26.013 | 0.73 | 2.3e-06 | depths inconsistent |
| 234 | 355650616 | 1.4467 | 3.61 | tls | 114 / 162 | 39.57 | 2.380 | 0.66 | 1.2e-24 | depths inconsistent |
| 265 | 289722962 | 77.6416 | 3.54 | survey | 5 / 8 | 10.99 | 2.244 | 0.63 | 3.7e-37 | depths inconsistent |
| 287 | 154841570 | 59.1472 | 5.57 | survey | 5 / 6 | 11.17 | 3.711 | 0.67 | 6.0e-05 | depths inconsistent |
| 294 | 290470328 | 73.3093 | 5.32 | survey | 3 / 4 | 10.36 | 3.617 | 0.68 | 0.07 | top event > 50% |
| 343 | 404348184 | 45.7021 | 16.42 | survey | 3 / 4 | 15.87 | 9.796 | 0.60 | 0.01 | top event > 50% |
| 346 | 404348184 | 46.5434 | 15.19 | survey | 3 / 4 | 17.54 | 10.127 | 0.67 | 0.03 | top event > 50% |
| 384 | 154841570 | 78.0487 | 5.61 | tls | 4 / 4 | 8.02 | 3.270 | 0.58 | 0 | top event > 50% |

Eighteen of these fail only the depth-consistency test (two fail only the depth ratio and four
only the top-event share), and their kept-event SNRs (8 to 686) show
that the events are real dips, not noise. They are the population the survey was always going to
find: eclipsing binaries and spotted, rotating stars whose per-event depths vary by tens of sigma.
Rank 9 (TIC 167304394, kept depth 45.16 ppt at SNR 686) is prompt 5's eclipsing binary in an
equal-brightness Gaia pair, and it fails here for the same reason it did there. Note also that
every one of the 24 has a kept depth of 0.17 to 0.88 times the survey depth: the wotan biweight
window absorbs part of the transit, so a depth ratio near 0.7 is the norm for a real dip and is
not by itself evidence against one.

## 4. The artefact census over all 405

A candidate is **carried by** an artefact class when its strongest observed event — the one with
the largest (depth/error)^2 in the detrended corrected flux — was removed by that rule. The
classes are not exclusive: one event can trip several rules, and the "candidates carried by it"
columns therefore sum to more than the number carried.

**Under the ephemeris that gives the candidate the most credit** [M]: the strongest event survives
every rule for **103** of the 405 candidates; **302** are carried by at least one class;
**2,957 of 8,697 observed epochs (34%) were removed.**

| artefact class | candidates carried by it | events removed by it |
|---|---:|---:|
| dip absent in SAP (made by the flux correction) | 124 | 164 |
| SAP baseline ramp across the event | 117 | 790 |
| PDC gap within one duration | 93 | 374 |
| scattered-light flag on > 20% of near-transit cadences | 88 | 1103 |
| scattered-light ramp (background > 2x sector median, doubling) | 78 | 1064 |
| momentum dump within one duration | 43 | 818 |
| quality-flagged > 20% of in-transit cadences | 36 | 616 |
| sector or orbit edge within one duration | 30 | 369 |

**Under the survey ephemeris** (the one the frozen ranking scored) [M]: strongest event kept for
**109**; carried by a class **296**; 3,106 of 8,550 observed epochs (36%) removed. Class counts:
dip absent in SAP 116, SAP baseline ramp 127, PDC gap 96, scattered-light flag 96, scattered-light
ramp 71, momentum dump 43, quality-flagged 22, sector/orbit edge 27. The two ephemerides give the
same picture, so the census does not depend on which one is used.

### Which sectors and camera/CCD combinations produce the PDC-made dips [M]

Every (sector, camera, CCD, product) whose events were removed as a dip absent from SAP or as
abutting a PDC gap, ordered by events removed. Prompt 5 saw this on sectors 15, 19, 74, 76 and 82
in three stars; over 405 candidates it spreads across 232 sector/camera/CCD combinations from
sector 1 to sector 105, concentrated in the recent northern-field products on cameras 3 and 4.

| sector | camera | CCD | product | events removed | stars | classes |
|---:|---:|---:|---|---:|---:|---|
| 82 | 4 | 3 | TESS-SPOC | 10 | 5 | pdc_gap 10, scattered_light_flag 8, dip_absent_in_sap 3, scattered_light_ramp 3, sap_baseline_ramp 2 |
| 85 | 1 | 3 | TESS-SPOC | 8 | 3 | pdc_gap 8, scattered_light_flag 6, scattered_light_ramp 2, dip_absent_in_sap 1, sap_baseline_ramp 1, momentum_dump 1 |
| 74 | 3 | 3 | TESS-SPOC | 7 | 6 | pdc_gap 7, scattered_light_flag 7, dip_absent_in_sap 2, scattered_light_ramp 1, sap_baseline_ramp 1 |
| 85 | 4 | 4 | TESS-SPOC | 6 | 4 | pdc_gap 6, scattered_light_flag 4, scattered_light_ramp 3, dip_absent_in_sap 2, momentum_dump 1 |
| 97 | 4 | 1 | SPOC | 6 | 3 | pdc_gap 6, scattered_light_flag 6, scattered_light_ramp 2, momentum_dump 2, dip_absent_in_sap 2 |
| 55 | 4 | 1 | TESS-SPOC | 6 | 4 | pdc_gap 6, scattered_light_flag 4 |
| 79 | 2 | 1 | TESS-SPOC | 6 | 4 | pdc_gap 6, scattered_light_flag 6, dip_absent_in_sap 1, sap_baseline_ramp 1 |
| 84 | 4 | 4 | TESS-SPOC | 6 | 5 | pdc_gap 6, scattered_light_flag 6, dip_absent_in_sap 2, scattered_light_ramp 1 |
| 42 | 4 | 1 | TESS-SPOC | 5 | 2 | pdc_gap 5, scattered_light_flag 5, sap_baseline_ramp 3, scattered_light_ramp 2 |
| 102 | 4 | 3 | QLP | 5 | 3 | dip_absent_in_sap 5, quality_flagged 4 |
| 96 | 2 | 1 | QLP | 5 | 5 | dip_absent_in_sap 5, scattered_light_ramp 5, scattered_light_flag 4, sap_baseline_ramp 4, quality_flagged 1 |
| 75 | 3 | 1 | TESS-SPOC | 5 | 2 | pdc_gap 5, scattered_light_flag 5, scattered_light_ramp 2, sap_baseline_ramp 1 |
| 71 | 4 | 3 | TESS-SPOC | 5 | 1 | pdc_gap 5, scattered_light_flag 5, scattered_light_ramp 4 |
| 67 | 4 | 4 | TESS-SPOC | 5 | 3 | pdc_gap 5, dip_absent_in_sap 1, scattered_light_ramp 1, scattered_light_flag 1, momentum_dump 1, sap_baseline_ramp 1 |
| 75 | 3 | 3 | TESS-SPOC | 5 | 3 | dip_absent_in_sap 5, pdc_gap 4, scattered_light_flag 4, sap_baseline_ramp 1 |

Full table (232 sector/camera/CCD/product combinations, 467 removed events) in
`data/survey/p6/census_p6.json`, key `chosen.pdc_made_dips_by_sector_camera_ccd`. Its shape [M]:
TESS-SPOC contributes 356 of the 467 events, SPOC 68 and QLP 43; cameras 3 and 4 carry 73% of them
(camera 4 alone 247); and 291 of 467 fall in sectors 56 and later against 93 in sectors 27-55 and
81 in sectors 1-26, so the effect is worst in the recent northern-field data at 200-s cadence. The
worst individual sectors are 85 (20 events), 75 (19), 74 (18), 84 (14) and 67 (13). Almost every
entry pairs the PDC-gap or absent-in-SAP class with the scattered-light flag or ramp: the corrected
flux makes its dips where the background is surging and PDC has cut the surrounding cadences out,
exactly as prompt 5 described.

### How many survivors per star the artefact classes explain [M]

261 stars. On **183** every survivor is carried by an artefact class; on **45** none is.

| carried / survivors on the star | stars |
|---|---:|
| 0 of 1 | 37 |
| 0 of 2, 3, 5 | 2, 5, 1 |
| 1 of 1 | 131 |
| 1 of 2, 3, 4 | 16, 4, 1 |
| 2 of 2 | 43 |
| 2 of 3, 4 | 4, 1 |
| 3 of 3 | 7 |
| 3 of 4, 5 | 4, 1 |
| 4 of 4 | 2 |
| 5 of 6 | 1 |
| 5 of 7 | 1 |

### Deep events on the same star (binary hosts) [M]

**109** of the 405 candidates sit on a star that carries another accepted candidate at >= 30 ppt or
>= 5x this candidate's depth. On **69** of them the whole-baseline preparation actually removed
binned points deeper than 3x the candidate depth, so the deep events are present in this
candidate's own search data and were folding into its whole-stitch measurement. That is prompt 5's
ranks 2 and 10 failure mode, and it applies to a sixth of the survivor list.

## 5. Every candidate that reached Stage B and Stage C

Six of the seven Stage A survivors reached the blind search; all six failed it. All five host stars
are CLEAN against the six hard-stop catalogs, re-downloaded at 18:04-18:08 UTC today
(`ctoi=2026-09-03:f6964541; nasa_ps=...a77e0fbc; nasa_pscomppars=...0ade67b2; spoc_tce=...e580dde7;
tess_eb=...43555226; toi=...cf05fbb7`), so none of these signals is an already-catalogued object.

| rank | TIC | survey P (d) | depth (ppt) | Stage A kept / obs, SNR | Stage B | strongest blind peak (d) | SDE | n tr | SDE within 1% of survey P | rank of that period | verdict |
|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| 16 | 233007823 | 17.4683 | 3.42 | 45/54, 60.3 | **FAIL** (sectors 50, 76, 80) | - | - | - | - | - | KILL |
| 98 | 201247574 | 16.5609 | 1.54 | 11/15, 10.9 | PASS, 5 flags | 101.62443 | 11.9 | 1 | 6.0 | not in top 10 | KILL |
| 250 | 219419204 | 65.0269 | 0.83 | 3/7, 9.6 | PASS, 4 flags | 79.96983 | 10.3 | 4 | 9.1 | 10 | KILL |
| 279 | 188830181 | 44.8868 | 30.38 | 4/6, 15.8 | PASS, 3 flags | 0.98650 | 17.3 | 85 | 4.7 | not in top 10 | KILL |
| 289 | 43668893 | 13.4204 | 4.17 | 5/10, 11.4 | PASS, 5 flags | 9.58541 | 10.1 | 9 | 3.8 | 10 | KILL |
| 325 | 219419204 | 76.0623 | 1.66 | 4/6, 12.4 | PASS, 3 flags | 86.06180 | 14.0 | 3 | 12.9 | 2 | KILL |
| 398 | 43668893 | 14.0370 | 5.75 | 3/8, 10.9 | PASS, 5 flags | 9.58541 | 10.1 | 9 | 4.4 | not in top 10 | KILL |

**Rank 16, TIC 233007823, P = 17.4683 d — resolved in section 10 below: an eccentric eclipsing
binary.** This was flagged as the one borderline decision in the funnel (three of sixteen testable
sectors excluded it by a 5% margin, entirely through the window-dilution effect of section 2). It
was re-analysed separately and is now settled on evidence the funnel never looked for: a secondary
eclipse at phase 0.605, 95% as deep as the primary. See section 10.

**Rank 98, TIC 201247574, P = 16.5609 d.** Gaia `phot_variable_flag` VARIABLE with class
SOLAR_LIKE, a VSX ROT entry within 1 arcmin, `astrometric_excess_noise_sig` 5.1, four neighbours
within 3 px bright enough for the depth, and an 8.41-ppt accepted candidate on the same star. The
blind search finds nothing at 16.56 d (SDE 6.0, not among the ten strongest peaks); its strongest
peak, 101.62 d at SDE 11.9, has a single transit and is not a period. A rotating spotted star.

**Ranks 250 and 325, TIC 219419204, P = 65.03 and 76.06 d.** Gaia RUWE 3.17 and
`astrometric_excess_noise_sig` 201.6: the astrometry of this star is not that of a single object.
The blind search prefers 79.97 d (SDE 10.3) and 86.06 d (SDE 14.0) on the two detrendings of the
same star, neither of which is either survey period. Rank 325 is the closest any candidate came to
passing — SDE 12.9 within 1% of its survey period, the second-strongest peak in the spectrum — but
the rule is that the strongest peak must be there, and it is not; the two survey periods and the
two blind peaks are four different numbers on one star with 15 observing units, which is what a
long-period systematic looks like, not a transit.

**Rank 279, TIC 188830181, P = 44.8868 d.** SIMBAD types it EB\*, VSX has an EW (contact
eclipsing binary) entry within 1 arcmin, and the same star carries a 43.89-ppt accepted candidate.
The blind search returns 0.98650 d at SDE 17.3 with 85 transits: the binary's own period, not the
survey's 44.89 d. The star is absent from the TESS EB catalog and from every SPOC TCE list, as was
prompt 5's TIC 167304394. A human may wish to report it to an eclipsing-binary catalog; it is not
a CTOI.

**Ranks 289 and 398, TIC 43668893, P = 13.4204 and 14.0370 d.** Gaia RUWE 11.60,
`astrometric_excess_noise_sig` 1559.6, `non_single_star` set, thirteen neighbours within 3 px
bright enough to make the depth, and a 50.15-ppt accepted candidate on the same star. Both
candidates return the same blind peak, 9.58541 d at SDE 10.1, and neither survey period appears.
These are the only two candidates whose phase-independent test had power and did not exclude them
(4 testable sectors each, deepest windows 7.5-7.8 ppt), which is consistent with a real deep
signal on the star — the binary, not a 13-14 d transit.

## 10. Rank 16 resolved: TIC 233007823 is an eccentric eclipsing binary

Prompt 6 flagged this candidate as the one borderline kill in the whole funnel: the only candidate
the phase-independent test excluded, and by a 5% margin that turned on the window-dilution effect
of section 2. It was re-analysed on its own (`scripts/rank16_analysis.py`,
`data/survey/p6/rank16/`). The answer is not borderline at all.

### The measurement [M]

Folding the whole 1,979-day baseline at the survey ephemeris and scanning **every** phase for a dip
returns exactly two dips above 5 sigma, and nothing else:

| dip | phase | depth (ppt) | significance | kept events after the removal rules | depth in **raw SAP** (ppt) |
|---|---:|---:|---:|---:|---:|
| primary | 0.9996 | 2.637 +/- 0.048 | 55.4 sigma | 45 of 54 | 2.664 +/- 0.042 |
| **secondary** | **0.6048** | **2.505 +/- 0.048** | **52.0 sigma** | **42 of 58** | **2.516 +/- 0.044** |

The secondary is not an artefact of the flux correction: it is present at 2.516 +/- 0.044 ppt in the
raw SAP flux, it survives every removal rule of `AUDIT.md` section 1 step 3 on 42 separate epochs,
and each individual secondary eclipse is a median 8.4-sigma detection. Its epochs are integer
multiples of the same 17.46829-day period, to within 0.006 cycles over 63 cycles.

### Why that settles it

The secondary is **0.950 +/- 0.026 times as deep as the primary**. At this period the star
(Teff 5733 K, R = 1.057 R_sun) gives a/R\* = 27.0 and a companion equilibrium temperature of 780 K,
so the deepest secondary a *planet* could produce in the TESS band is thermal 5.6e-9 ppt plus
reflected 1.1e-3 ppt, or **1.08e-3 ppt in total**. The measured secondary is **2,312 times that
bound**. A body that occults 95% as much light as it blocks has the surface brightness of a star.

The two eclipses are also consistent as one eccentric orbit, which is a weak but real check: the
secondary sits 0.1052 in phase past 0.5, giving e cos(omega) = +0.165, and it is shorter than the
primary (1.05 h against 1.80 h at half depth), giving e sin(omega) = -0.263. Together e = 0.31,
omega = -58 degrees — an admissible, unremarkable orbit. A dip at a random phase with a random
width had no reason to land there.

The eclipses are only 2.6 ppt deep, and two stars of near-equal surface brightness cannot eclipse
that shallowly, so the binary must be diluted by roughly a factor of 100. Gaia supplies candidates:
four neighbours within 3 pixels are bright enough, the nearest at 14.6 arcsec (0.70 px) with
delta-G 4.73, which would show 12.7 ppt if totally eclipsed and 2.6 ppt if eclipsed by 21%. The
host's `astrometric_excess_noise_sig` is 17.8. Whether the binary is the target or that neighbour
changes only the follow-up note, not the verdict.

### Two corrections to the prompt-6 record [M]

1. **The Stage B kill was not load-bearing.** The blind TLS was run for this candidate after the
   fact: the strongest peak is 75.58 d at SDE 15.0, and the SDE within 1% of the survey period is
   8.38, below the threshold of 9. It would have failed Stage C as well. The funnel's answer did
   not depend on the borderline test.
2. **The funnel has a real blind spot.** No stage of prompt 6 searched for a secondary eclipse, and
   [P4] the P4 packet tested only phase 0.5 — it reported "secondary at phase 0.5: not detected"
   and was correct, because this secondary is at phase 0.605. Both missed a 52-sigma feature. A
   full-phase secondary scan costs seconds per candidate and should be a gate in any second pass.

[P4] P4 had already called this candidate a likely false positive (TRICERATOPS FPP and NFPP 1.000,
stellar density ratio 0.11, a 5.8-sigma centroid shift, per-unit depths disagreeing by more than
3 sigma). **I agree with that verdict**, and the density ratio of 0.11 — a transit far too long for
a central transit at this period — is exactly what a diluted, grazing stellar eclipse looks like.
What this re-analysis adds is the mechanism, measured directly rather than inferred.

### The same scan over the other six Stage A survivors [M]

`scripts/secondary_scan.py` applies the identical scan to all seven. A dip away from phase 0 is
**not** by itself a secondary: on a variable star a box scan finds ppt-level dips at many phases.
A secondary is claimed only when the scan is otherwise quiet — exactly one other dip — and it is
significant [A].

| rank | TIC | P (d) | dips above 5 sigma | strongest other dip | reading |
|---:|---:|---:|---:|---|---|
| 16 | 233007823 | 17.4683 | **2** | phase 0.605, 52.0 sigma, 0.95 x primary | **secondary eclipse: stellar companion** |
| 98 | 201247574 | 16.5609 | 2 | phase 0.431, 5.7 sigma, 0.52 x primary | possible secondary, not decisive alone; the host is a catalogued rotational variable |
| 250 | 219419204 | 65.0269 | 15 | - | variability: dips at scattered phases, no claim |
| 279 | 188830181 | 44.8868 | 41 | - | variability: dips at scattered phases, no claim (host is a catalogued contact binary) |
| 289 | 43668893 | 13.4204 | 16 | - | variability: dips at scattered phases, no claim |
| 325 | 219419204 | 76.0623 | 17 | - | variability: dips at scattered phases, no claim |
| 398 | 43668893 | 14.0370 | 14 | - | variability: dips at scattered phases, no claim |

Rank 16 is the only one of the seven whose phase scan is quiet enough for the test to say anything
sharp, and it says the candidate is a binary. The other five stars produce ppt dips at a dozen or
more phases, which is its own verdict on how transit-like their signals are, and is consistent with
all six failing the blind TLS. Records: `data/survey/p6/secondary_scan.json`,
`data/survey/p6/rank16/{fold,shape,events_primary,events_secondary,blend,verdict}.json`.

## 6. The ordered list to submit

**Empty.** No candidate reached Stage D, so no `ctoi_fields.json` was written and there is no
ExoFOP note to draft. `docs/packets/audit_p6/` does not exist; `data/survey/p6/stageD_empty.json`
records the fact.

## 7. What this says about the survey's false-positive budget

[P4] The P4 measured model expected about **2.2 new signals** among the survivors (low 3.3, high
1.1; `data/survey/p4/expected_yield_p4.json`). Zero is inside that range, so a clean null is not by
itself evidence of a broken survey. What the census adds is the shape of the 405:

* **75% of the survivor list is explained by five instrumental effects.** 302 candidates lose their
  strongest event to a removal rule, and one third of all 8,697 observed epochs are removed. The
  survey searched corrected or detrended flux only and never looked at SAP, so the whole of the
  "dip absent in SAP" class (124 candidates) entered as transits by construction.
* **The frozen ranking carries some information but does not order the surviving evidence.** [M]
  The P4 rank correlates with how many of the six Stage A criteria a candidate passes (Spearman
  rho = -0.37, p = 9e-15: better-ranked candidates do pass more), but it has no relation at all to
  the kept-event SNR, the quantity that actually measures the signal in clean data (rho = -0.065,
  p = 0.19, n = 405). The seven Stage A survivors sit at ranks 16, 98, 250, 279, 289, 325 and 398,
  five of the seven below rank 200. The score's `S_snr` term ranked on whole-stitch local-BLS SNR,
  which prompt 5 showed the independent data do not reproduce.
* **A sixth of the list is shallow candidates on binary hosts.** 109 candidates sit on a star with
  a much deeper accepted candidate, and on 69 the deep events are inside this candidate's own
  search data.
* **The surviving astrophysics is eclipsing binaries and rotating stars, not transits.** The 24
  near misses fail almost entirely on depth consistency at SNR 8 to 686 — real, deep, varying
  events. Of the six candidates that reached the blind search, one host is a catalogued contact
  binary, one is a catalogued rotational variable, and two have Gaia astrometry (RUWE 3.2 and 11.6,
  excess-noise significance 202 and 1560) that is not that of a single star.
* **The budget is therefore not "2 signals lost in 403 noise events".** It is closer to "about 300
  instrumental artefacts, about 100 astrophysical false positives, and no reproducible shallow
  transit". If the real yield is 2.2, those signals are either below the survey's own detection
  threshold or were rejected before the survivor list was frozen; nothing in the 405 reproduces.

These numbers are the evidence for the second-pass changes already recommended in `docs/AUDIT.md`
section 6, and they enlarge two of them: change 1 (the SAP test) would remove 124 candidates on its
own and 302 with the full rule set, and change 2 (star-level gates) would demote 109. Change 3
(replacing the stitch SNR) is supported by the rank spread above.

## 8. Assumptions and limits [A]

1. Every threshold in section 2 is this re-vetting's choice where the prompt did not fix it, and
   was applied identically to all 405 candidates by one code version (`p6.2`).
2. "The ephemeris that gives the candidate the most credit" is operationalised as the one passing
   the most of the six Stage A criteria, ties broken by kept-event SNR. 234 candidates were judged
   on the forced-TLS ephemeris, 163 on the survey's, 8 on the packet refit.
3. The Stage B window test is diluted where the survey duration is shorter than the central-transit
   T14 (section 2), and has no power at all for periods above about 17 days.
4. The depth-consistency criterion (p >= 1e-3) is a strong filter on real but variable signals. It
   removes 75 candidates, 20 of them otherwise clean. A transit with genuine depth variation from
   red noise or spot crossings would fail it.
5. Neighbour dilution uses Gaia RP (else G) flux ratios and f/(1+f) for a totally eclipsed
   neighbour; aperture membership is approximated by separation in pixels.
6. The `fit` sub-command was never exercised: no candidate reached a verdict that needs it. It
   remains untested code.
7. The audit code is a script with no unit tests. Its rules are documented here and in
   `docs/AUDIT.md`; every intermediate number is under `data/survey/p6/`.

## 9. Where the records are

| what | path |
|---|---|
| Stage A, one record per candidate with every event and its removal reasons | `data/survey/p6/stageA/*.json`, `stageA.csv` |
| Stage B star-level records | `data/survey/p6/stageB/*.json`, `stageB.csv` |
| Stage C blind-TLS records | `data/survey/p6/stageC/*.json`, `stageC.csv` |
| Stage D | `data/survey/p6/stageD_empty.json` (no Stage C PASS) |
| the funnel and every threshold | `data/survey/p6/funnel_p6.json` |
| the artefact census | `data/survey/p6/census_p6.json` |
| generated tables reproduced above | `data/survey/p6/report_tables.md` |
| Gaia / SIMBAD / VSX per star | `data/survey/p6/neighbours/tic*.json` |
| the fresh hard stop | `data/survey/p6/crossmatch_p6.json` |
| Stage 0 download summary | `data/survey/p6/download_p6.json` |
| validation of the drivers against prompt 5 | `data/survey/p6/validation/` |
| the rank-16 re-analysis (section 10) | `data/survey/p6/rank16/`, `scripts/rank16_analysis.py` |
| the secondary-eclipse scan over all seven Stage A survivors | `data/survey/p6/secondary_scan.json`, `scripts/secondary_scan.py` |

Git-ignored and reproducible from MAST: the raw per-product arrays
(`data/survey/audit_lc/`), the detrended arrays and TLS spectra
(`data/survey/p6/tls/*.npz`) and the per-ephemeris `events/` intermediates, whose contents are
reproduced per event, with the removal reasons, inside every Stage A record.
