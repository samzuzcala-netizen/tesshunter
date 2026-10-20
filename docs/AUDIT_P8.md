# Prompt 8: native-cadence small-star audit

**0 SUBMIT, 2 HOLD, 4 KILL** among 6 Stage C survivors [M]. The ordered submission list is empty.

The pipeline finds candidates. Nothing was submitted to an external service.

Evidence: [M] measured during P8; [Pn] inherited from prompt n; [A] adopted assumption. The rule choices were committed before any real P8 candidate entered Stage A.

## Population and search

2,000 targets; search states {'ok': 2000} [M]. Every target has a result record. 745 jobs stopped accepting additional sub-searches when their search budget was exhausted [M]. [Per-target log](../data/survey/p8/per_target_log.csv) records products, sectors, timing, fallbacks and errors.

2,000 of 2,000 population stars have cached Gaia/SIMBAD/VSX record files [M]. V2 ordering uses the Gaia target record; no verdict depends on rank.

Per-job wall time: median 204.1 s, 90th percentile 466.1 s, maximum 683.5 s [M]. [Population memo](POPULATION_P8.md) documents each cut and the selected cadence.

The input reconciliation verified 20,924 products at a common 200 s cadence [M]. 13 are from the special sector 1751, whose [mission release notes](https://heasarc.gsfc.nasa.gov/docs/tess/sector1751_summary.html) describe the January 2026 pointing. Those products were retained by the existing selection and were not used for the population's minimum sector count. The injection sample contains 0 hosts with this extra sector [M], so its unusual window is not separately calibrated. [Input validation and source hashes](../data/survey/p8/search_validation_p8.json).

The pre-search Gaia cache acquired the completed survivor-depth context for 1,396 hosts before Stage B [M]. 1,360 hosts have at least one neighbour within 63 arcsec able to produce a survivor's depth under the inherited total-eclipse dilution calculation [M]. This is the existing per-star test against any pre-gate survivor depth, using full saved magnitudes; it is a HOLD flag, not a source-location measurement. [Depth-context evidence](../data/survey/p8/neighbour_depth_context_p8.json) records source hashes and every flag change. The earlier VSX display-separation repair changed no vetting flags.

## Funnel

| Stage | Entered [M] | Passed / disposition [M] |
|---|---:|---:|
| Accepted by search | 13,252 | 13,252 |
| Pre-gate | 13,252 | 3,688 |
| A: event rules | 3,688 | 189 |
| Full-phase secondary | 189 | 19 PASS + 0 HOLD |
| B: star and independent-window tests | 19 | 19 |
| C: blind TLS | 19 | 6 |
| D: full audit | 6 | {'SUBMIT': 0, 'HOLD': 2, 'KILL': 4} |

The seeded Stage A failure sample contains 350 candidates; secondary outcomes are {'PASS': 172, 'FAIL': 178, 'HOLD': 0, 'ERROR': 0} [M].

Native-cadence Stage A measured 88.2 s per candidate at the median and 549.6 s at the 90th percentile, across 3,688 records [M].

### Blind-period verification

The verification search spans 0.5 to 110 d [A]. The population search remains the pre-registered 0.5 to 30 d band [A]; an unrelated strongest peak is not a new accepted candidate. The frozen C gate requires the strongest peak at SDE >= 9 to match the survey period within 1%, or a 2:1/1:2 alias with consistent transit depths [A]. The table retains near-survey significance even when the strongest-period requirement fails. The linked records contain the exact period/alias comparison.

| TIC | Survey P (d) [M] | Strongest blind P (d) [M] | Blind SDE [M] | SDE within 1% of survey P [M] | Transits at strongest peak [M] | C result [M] |
|---|---:|---:|---:|---:|---:|---|
| [TIC 356226514](../data/survey/p8/stageC/tic356226514_P0.5947.json) | 0.594664 | 1.190257 | 6.753 | 6.654 | 78 | FAIL |
| [TIC 273226810](../data/survey/p8/stageC/tic273226810_P0.5806.json) | 0.580590 | 87.672970 | 11.536 | 1.093 | 2 | FAIL |
| [TIC 464282202](../data/survey/p8/stageC/tic464282202_P0.8166.json) | 0.816632 | 49.765727 | 14.492 | 8.632 | 2 | FAIL |
| [TIC 237921294](../data/survey/p8/stageC/tic237921294_P18.3141.json) | 18.314069 | 91.588417 | 18.815 | 15.515 | 5 | FAIL |
| [TIC 464282202](../data/survey/p8/stageC/tic464282202_P16.7299.json) | 16.729864 | 0.811628 | 12.890 | 7.999 | 157 | FAIL |
| [TIC 237917568](../data/survey/p8/stageC/tic237917568_P18.7059.json) | 18.705946 | 67.637180 | 14.496 | 14.271 | 5 | FAIL |
| [TIC 144277542](../data/survey/p8/stageC/tic144277542_P12.9812.json) | 12.981174 | 12.981356 | 14.912 | 14.912 | 7 | PASS |
| [TIC 100273626](../data/survey/p8/stageC/tic100273626_P10.3806.json) | 10.380642 | 13.187502 | 12.790 | 10.311 | 2 | FAIL |
| [TIC 52205459](../data/survey/p8/stageC/tic52205459_P10.0755.json) | 10.075455 | 95.016961 | 15.756 | 3.041 | 1 | FAIL |
| [TIC 154566869](../data/survey/p8/stageC/tic154566869_P8.9053.json) | 8.905309 | 8.885036 | 13.737 | 13.737 | 6 | PASS |
| [TIC 394680557](../data/survey/p8/stageC/tic394680557_P29.9904.json) | 29.990440 | 53.553739 | 12.880 | 10.061 | 3 | FAIL |
| [TIC 309025900](../data/survey/p8/stageC/tic309025900_P14.9235.json) | 14.923550 | 0.993496 | 20.416 | 11.327 | 88 | FAIL |
| [TIC 154566869](../data/survey/p8/stageC/tic154566869_P2.9260.json) | 2.925987 | 13.011580 | 13.575 | 4.863 | 2 | FAIL |
| [TIC 388200613](../data/survey/p8/stageC/tic388200613_P20.8357.json) | 20.835725 | 65.304044 | 12.260 | 10.605 | 4 | FAIL |
| [TIC 404927114](../data/survey/p8/stageC/tic404927114_P27.5436.json) | 27.543625 | 27.543652 | 15.862 | 15.862 | 8 | PASS |
| [TIC 198517968](../data/survey/p8/stageC/tic198517968_P15.4315.json) | 15.431521 | 72.232116 | 26.473 | 4.478 | 1 | FAIL |
| [TIC 155895971](../data/survey/p8/stageC/tic155895971_P13.1279.json) | 13.127859 | 13.128077 | 10.228 | 10.228 | 4 | PASS |
| [TIC 230120862](../data/survey/p8/stageC/tic230120862_P16.7959.json) | 16.795892 | 16.791425 | 16.657 | 16.657 | 20 | PASS |
| [TIC 80256158](../data/survey/p8/stageC/tic80256158_P10.8184.json) | 10.818441 | 10.818371 | 14.054 | 14.054 | 8 | PASS |

## Calibration carried into the search

2,100 injections on 300 stars [M]. Calibration used p7.0; the selected p8.0 A/secondary choices are the same, with exact Stage B window metadata added. [The complete map and bootstrap intervals](COMPLETENESS_P8.md) retain every denominator.

| Calibration level | Through [M] | SNR50 [M] | SNR90 [M] |
|---|---:|---:|---:|
| search_only | 1,163/2,100 | 13.15 | 31.65 |
| search_and_pregate | 1,121/2,100 | 14.08 | 31.44 |
| search_and_stageA | 1,093/2,100 | 14.65 | 36.66 |
| search_and_stageA_and_secondary | 904/2,100 | 20.19 | 75.18 |
| full_funnel_with_pregate | 896/2,100 | 20.44 | 73.98 |

Expected new signals through the early funnel were 14.924, 11.675, 8.087 under low, mid and high incumbent-search completeness priors [M under adopted model assumptions]. Higher incumbent completeness leaves fewer new signals. The mid value passed the pre-registered 3.0 stop threshold [A]. Uninjected controls projected 13.33 early-funnel survivors over the population [M]. B/C/D efficiency was not calibrated, so these expectations do not predict the final SUBMIT count.

## Artefact census

A candidate is carried by a class when its strongest observed event is removed by that rule. The classes overlap; counts must not be summed as independent candidates. The comparison also changes population, cadence and rule version, so it does not isolate the effect of a single change.

| Class | P8 candidates [M] | P6 candidates [P6] | P8 removed events [M] | P6 removed events [P6] |
|---|---:|---:|---:|---:|
| dip_absent_in_sap | 1114 | 124 | 2517 | 164 |
| pdc_gap | 380 | 93 | 2346 | 374 |
| scattered_light_ramp | 1671 | 78 | 16128 | 1064 |
| scattered_light_flag | 651 | 88 | 11099 | 1103 |
| momentum_dump | 233 | 43 | 3971 | 818 |
| sector_orbit_edge | 120 | 30 | 1719 | 369 |
| quality_flagged | 328 | 36 | 9299 | 616 |
| sap_baseline_ramp | 2272 | 117 | 18668 | 790 |

P8: 3,170/3,688 candidates are carried by at least one class; 34,266/87,668 observed epochs were removed [M].

P8: 4,372 correction-made events in 463 sector/camera/CCD/product groups, including 3,450 (78.9%) on cameras 3 and 4 [M]. Ordinary sectors 56-105 account for 4,371; special sector 1751 accounts for 1 more [M].

P6: 302/405 candidates are carried by at least one class; 2,957/8,697 observed epochs were removed [P6].

P6: 467 correction-made events in 232 sector/camera/CCD/product groups, including 343 (73.4%) on cameras 3 and 4 [P6]. Ordinary sectors 56-105 account for 291; special sector 1751 accounts for 2 more [P6].

Flares, fast rotation and noisy faint-star QLP data were anticipated [A]. The upward clipping and measured rotation proxy were already in the search. The historical P6 count of 291 late-sector correction-made events covers ordinary sectors 56-105; the stored census also contains two from special sector 1751 [P6]. The full P8 detector/sector counts are retained in [census_p8.json](../data/survey/p8/census_p8.json).

## Individual Stage C survivors

### Rank 1: TIC 230120862, fitted P = 16.7895042 d [M]

Original survey period: 16.7958916 d [M].

**KILL**: Background/correction artifact. Difference images are dominated by changing diffuse background at both the physical-fit and original Stage A ephemerides. At the original 4.8-hour Stage A window, fixed-aperture depths are -6.620 +/-1.397, 5.083 +/-0.699, 7.158 +/-1.110 and -3.283 +/-1.643 ppt in sectors 58, 79, 83 and 86 [M], with raw changes tracking sky ramps and no stable isolated transit. The physical fit reaches a grazing rail and has unusably large geometry uncertainties.

What would change this: Independent photometry with a stable background must reproduce localized, repeated dimming at the candidate ephemeris and permit a constrained physical fit. Fixed-aperture depths remain diluted and their point-scatter errors omit correlated noise. The current measurements do not support a separate clean EB report.

[Review packet](packets/audit_p8/tic230120862_P16.7959/packet.md). FPP 0.9999999999999999; NFPP 0.9455965723553045; fpp_uniform False [M].

### Rank 2: TIC 80256158, fitted P = 10.8183939 d [M]

Original survey period: 10.8184405 d [M].

**KILL**: Background/correction artifact. The fixed target-aperture depths change sign across sectors (1.012, -1.011, 6.578 and -5.333 ppt), with raw variations tracking sky ramps and broad steps [M]. Difference images do not repeat a stable dimming point source or the fitted shallow transit.

What would change this: To reconsider: independent photometry must show repeated dimming localized to a stellar source, with a stable background and consistent depth and transit shape across sectors. Fixed-box errors use local point scatter and omit some correlated noise.

[Review packet](packets/audit_p8/tic80256158_P10.8184/packet.md). FPP 0.2112196219119783; NFPP 0.03453354721600477; fpp_uniform False [M].

### Rank 3: TIC 154566869, fitted P = 8.8852553 d [M]

Original survey period: 8.9053087 d [M].

**HOLD**: Source unresolved. Target-aperture dimming varies across sectors and is mixed with background changes; the difference images do not isolate a unique eclipsing source. FPP is 0.988154 and NFPP is 0.918773 [M], so the current evidence does not support a planet interpretation. The density prior is rejected and transit geometry remains poorly constrained.

What would change this: To reconsider: independently reproduce a repeated localized transit while fitting the variable sky/background and nearby sources, and obtain useful transit-geometry uncertainties.

[Review packet](packets/audit_p8/tic154566869_P8.9053/packet.md). FPP 0.9881538497113276; NFPP 0.9187734924382233; fpp_uniform False [M].

### Rank 4: TIC 404927114, fitted P = 27.5433901 d [M]

Original survey period: 27.5436253 d [M].

**HOLD**: Source unresolved in a crowded variable-star field. The primary difference images are weak/mixed in sector 63 and dominated by diffuse background changes in sectors 90 and 98. The fixed sky annulus leaves only one usable pixel per sector, below the required 16, so a reliable target-aperture depth could not be extracted. FPP is 0.201585 and NFPP is 0.169895 [M]; source localization is inadequate for submission.

What would change this: Source-resolving photometry or a validated crowded-field PSF/difference-image analysis must separate the target from neighbours and background, then show repeatable dimming near 27.5434 d with consistent depth. The present fixed-annulus method cannot supply that deblending. A satisfactory transit geometry alone does not resolve the contamination.

[Review packet](packets/audit_p8/tic404927114_P27.5436/packet.md). FPP 0.20158499315424983; NFPP 0.16989521969841298; fpp_uniform False [M].

### Rank 5: TIC 144277542, fitted P = 12.9813890 d [M]

Original survey period: 12.9811741 d [M].

**KILL**: Background/correction artifact. Diffuse event difference images and raw-aperture changes tracking the sky do not reproduce the fitted shallow target dip: the fixed sky-subtracted depths in sectors 95 and 104 are 0.584 +/- 1.353 and -0.481 +/- 0.720 ppt, while sector 68 has a broad unstable 33.178 +/- 4.424-ppt change [M].

What would change this: To reconsider: independent photometry must show repeated dimming localized to a stellar source while the background remains stable. These box errors use local point scatter and are not a formal exclusion probability including correlated noise.

[Review packet](packets/audit_p8/tic144277542_P12.9812/packet.md). FPP 0.04720982470459667; NFPP 0.0; fpp_uniform False [M].

### Rank 6: TIC 155895971, fitted P = 13.1281056 d [M]

Original survey period: 13.1278589 d [M].

**KILL**: Background/correction artifact. Three primary-event difference images are dominated by whole-cutout background changes, and the fixed target aperture alternates between large brightening, a weak dip and unstable gap-adjacent structure instead of a repeatable transit [M]. FPP 0.000659 is conditional on astrophysical hypotheses and does not account for this instrumental evidence.

What would change this: To reconsider: independent photometry must reproduce repeated dimming localized to a stellar source with stable background, including a consistent depth and transit shape across sectors. The fixed-box errors describe local point scatter and omit some correlated noise.

[Review packet](packets/audit_p8/tic155895971_P13.1279/packet.md). FPP 0.0006589646025492168; NFPP 5.5302725293218e-06; fpp_uniform False [M].

## Ordered local submission list

Empty. Nothing is ready for external submission under the frozen rules.

## Eclipsing-binary assessment

All 170 secondary rejections among the 189 Stage A passers received a recorded overview morphology review [M]. Forty sector-detail figures cover selected rejections, B passers and five non-random A failures that failed only depth consistency [M]; two additional harmonic figures examine TIC 233127050. The 350 randomly sampled A failures received the required secondary scans, not a systematic visual EB search. No EB-completeness claim follows from this inspection. [The final review coverage check](../data/survey/p8/eb_screen/review_scope_validation_p8.json) verifies all 170 review and plot sources.

One local EB candidate report is supported: [TIC 279426256 / Gaia DR3 5484242473249094784](eb_reports/tic279426256_vsx_fields.md), about 42.1 arcsec from searched TIC 279426252, with P = 0.7470014478 d [M]. Primary and secondary difference images follow that neighbour in sectors 61, 87 and 98, and its fixed-aperture secondary depths exceed the planetary bound [M]. This source is outside the selected small-star population. The report retains diluted depths, source-position limitations and no asserted binary subtype or formal ephemeris uncertainty. Fresh checks of all six hard-stop catalogues, plus wider VSX/SIMBAD queries, had no matching source; the report links the receipts. Uncatalogued means absent from those checked catalogues on the recorded date. Nothing was submitted externally.

Two other sharp-eclipse associations match known nearby binaries: TIC 294768511 with Gaia EB 5809727395730297856, and TIC 135048134 with SSS_J121846.5-413525 / Gaia DR3 6148217169939871872 [M from saved catalogue queries]. These are catalogue associations, without a measured pixel localization. TIC 278410520's 11.9275-d alias repeats its already-searched roughly 2.982-d signal and does not establish another binary.

TIC 233127050 has repeating SAP and corrected-flux dips at fixed diagnostic hypotheses 0.3936113 and 0.1968057 d [M]. Sixteen-sector fixed-box measurements and the two inspected folds do not identify its source or unique orbital period, and show no primary/secondary difference above 2.34 point-scatter sigma [M]. It has no additional clean EB report and was not promoted outside the survey's registered period band. The final A passer, TIC 423024752, has no stable eclipse pair in the reviewed sectors; its 27.8868807-d period is nearly 150 times the cached 0.1859128-d period of nearby VSX variable ZTF J173359.42+572551.2 (RS:, 52.5 arcsec) [M]. That possible association is not a source localization.

## Assumptions and limitations [A]

The yield model uses DC15 plus the inherited giant occurrence allowance, adopted incumbent-search priors, representative cells and phase-averaged coverage. The SNR-only logistic fit approaches unit completeness even though strong signals can still fail event vetoes; the individual-injection bootstrap omits correlation within a host. The HU19 calculation is a sensitivity proxy. No threshold was retuned on the real candidates.

TRICERATOPS uses a binned fold, the inherited circular aperture, its TIC scene and a separately cached wide Gaia background population. The P8 Gaia cone supports resolved-neighbour assessment and ranking. Uniform scenario probabilities are labelled as a failed likelihood calculation. Missing pixel/FPP information remains explicit.

The non-candidate fit exercises, including TOI-270 c and the recovered P8 injection, are preserved in [fit_exercises_p8.json](../data/survey/p8/fit_exercises_p8.json). The injection's EXERCISE verdict is never part of this survey's candidate counts. P8 physical fits start at the ephemeris accepted by Stage C and record its source hash. A regression test covers survey periods outside the local fit bounds and factor-two aliases. The first survey-seeded real fit was superseded after this mismatch was found; [the preserved diagnostic history](../data/survey/p8/fit_seed_repair/first_candidate_before/manifest.json) and the repeated injection exercise document the correction before the real refit. The frozen gates and P6/P7 fit behavior were unchanged.
