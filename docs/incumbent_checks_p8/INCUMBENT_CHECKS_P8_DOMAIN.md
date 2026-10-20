# Incumbent-claim check on the P8 domain

Side analysis, 2026-09-07 (local evening; TOI snapshot 2026-09-08T03:32:39Z UTC). Read-only against the repository. Written while the P9 pilot was running, so nothing was placed inside the git tree. **Move this directory into `docs/` and commit it once P9 has finished and its baseline checks are closed.** Everything needed to reproduce it is in this directory.

> Moved from `../P9_SIDE_INCUMBENT_CHECKS_2026-09-07/` into `docs/incumbent_checks_p8/` and committed in prompt 10 Part 0a (2026-09-08). `REPO` in `incumbent_checks.py` is now resolved relative to the repository root. The script was re-run on the frozen `toi_exofop.csv` after the move; `incumbent_checks.out` and `domain_tois.csv` were byte-identical to the stored files. The sha256 quoted in section 2 was corrected from a transcription error (`...d5daa8...`) to the value in `toi_fetch_stamp.txt` (`...d5faa8...`), which is the measured hash of the file.

Evidence tags follow the repository convention: [M] measured here, [P8] inherited from prompt 8 records, [A] adopted assumption, [I] inference.

## 0. One-paragraph summary

P8 searched 2,000 faint mid-to-late M dwarfs at 200-second FFI cadence (sectors 56 onward) and ended with 0 SUBMIT, 2 HOLD, 4 KILL. Three explanations were on the table: the incumbents (QLP, SPOC, community searches) had already claimed everything findable, the occurrence model overstated how many detectable planets exist, or the pipeline discards real planets it should keep. This check tests the first. **It is refuted.** In the 11,491-star domain the population builder considered, the incumbents and the community have claimed about 2 funnel-grade small planets against a modelled 79 [M]. QLP has alerted zero TOIs in the domain [M]. The domain is effectively unsearched to TessHunter's depth. That moves the explanation onto the pipeline (first, and testable by P9) and the occurrence model (second, worth tens of percent, not a factor of several). A secondary finding: the hard stop rejected 531 domain stars for a bare SPOC threshold-crossing event, and those are the brightest and best-observed stars in the domain, carrying a modelled 5.1 funnel-grade planets, a quarter of the selected population's expected 19 [M].

## 1. Question and prior beliefs

The yield model behind P8 (`data/survey/p8/expected_yield_p8.json`) predicted 19.0 planets in the 2,000 selected stars that would pass the early funnel (pre-gate, Stage A, secondary scan) if nobody had searched those stars before, and applied incumbent-completeness priors of 0.6, 0.4 and 0.1 (mid) across three signal classes to arrive at 11.7 "new" signals [P8]. In the conversation preceding this check I argued the opposite direction: that incumbents working at SNR 7 to 9 on the same products would have claimed about 90 percent of anything TessHunter carries at SNR50 near 20, leaving one or two new planets, which would make the zero result unremarkable [I, now withdrawn]. Both positions were untested. This check measures the claimed fraction directly.

## 2. Inputs

| input | path | provenance |
|---|---|---|
| Population pool with crossmatch outcome, 117,171 rows | `data/survey/cache/p8/pool_after_xmatch.csv` | P8 population builder, 2026-09-04 |
| Selected population, 2,000 rows | `data/survey/targets_p8.csv` | P8 |
| Yield model with per-star sigma, cadence counts, detectability, logistic curves | `data/survey/p8/expected_yield_p8.json` | P8, generated 2026-09-05T23:27:50Z |
| TOI table | `toi_exofop.csv` in this directory | ExoFOP `download_toi.php?output=csv`, fetched 2026-09-08T03:32:39Z, sha256 `00fd7a4cc2885e1bd09b26852b3778be0e74cb44fc15d5faa8cadcd5dac7abbb`, 8,148 rows |
| CTOI table, normalized and raw | `data/cache/catalogs/ctoi/` | repository cache, fetched 2026-09-01 |
| TESS-EB normalized | `data/cache/catalogs/tess_eb/` | repository cache, 2026-09-01 |

The crossmatch module was not imported and no cache was refreshed, because the catalogue cache was one day from its seven-day refresh and P9's Stage D reads it. Files were read directly with pandas.

## 3. Method

**Domain.** The POPULATION_P8 cuts applied to the pool: TIC Teff below 3600 K, TIC radius below 0.45 Rsun, Tmag 12.5 to 14.0, absolute galactic latitude at least 20 degrees, at least 3 sectors at 200 s with a QLP or TESS-SPOC light curve, and FFI-only (2-minute sectors a strict minority of the search sectors). This gives 11,491 stars before the Gaia dwarf check and the hard stop; 10,513 pass the Gaia check, against 10,512 in the memo [M].

**Noise model.** From the 2,000 selected stars' measured per-cadence scatter: ln(sigma_ppt) = -8.878 + 0.810 Tmag, residual standard deviation 0.223 in ln sigma; median 9,127 cadences per 200-s sector [M]. Domain stars outside the 2,000 get sigma from Tmag and cadence count from sector count.

**Detectability extrapolation.** The model's per-star funnel-detectable count was fit as a quadratic in ln(n_cadences / sigma^2) on the 2,000; the fit sums to 18.54 against the actual 19.00, residual 0.237 in ln [M]. The same fit applied to domain stars gives the model's prediction for stars it never scored. The domain's median sensitivity metric is 656 against 1,964 for the selected 2,000, so this is an extrapolation toward less sensitive stars [A].

**P8-condition SNR of a catalogued signal.** SNR = (depth / sigma) x sqrt(n_cadences x T14 / P), with depth, duration and period from the catalogue and sigma and cadence count from the star. This mirrors the yield model's phase-averaged matched-filter SNR [A]. Funnel probability from the yield file's central curve, p = 1 / (1 + exp(-(a + b ln SNR))) with a = -5.153, b = 1.708 (SNR50 20.4, SNR90 74.0); search-only a = -6.448, b = 2.503 [P8].

**Claimed count.** Sum of funnel probability over catalogued planet-like signals (TFOPWG PC, APC, CP, KP, or unpromoted CTOI not dispositioned FP or FA) on domain stars with period 0.5 to 30 d.

**Check 2.** The TOI table's Detection column takes values SPOC, QLP, FAINT, SPOC/QLP, SPOC/FAINT, CTOI, UNKNOWN. Joint SPOC/QLP detection was tabulated by Tmag, host temperature and pipeline SNR as a capture-recapture proxy.

## 4. Results

### 4.1 Domain and hard stop [M]

| | count |
|---|---:|
| domain stars before the hard stop | 11,491 |
| CLEAN / REJECT / FLAG | 10,903 / 552 / 36 |
| REJECT for a bare SPOC TCE (no other source) | 531 |
| REJECT with any TOI on the star | 16 |
| REJECT with any CTOI | 12 |
| REJECT with a TESS-EB entry | 6 |
| REJECT with a NASA archive entry | 0 |

### 4.2 TOIs on domain stars [M]

Six TOIs on six hosts, all REJECT. Detection: SPOC 5, CTOI 1, QLP 0. TFOPWG: PC 2, FP 2, FA 2. No TOI alerted after the 2026-09-04 crossmatch on any domain star, and no TOI at all on the 2,000 searched stars.

| TOI | TIC | tfop | detection | P (d) | Rp (Re) | depth (ppm) | Tmag | sectors at 200 s | pipeline SNR | P8-condition SNR | funnel prob. |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 7688.01 | 80429950 | PC | CTOI | 2.540 | 2.95 | 4,895 | 13.59 | 4 | 8.5 | 19.1 | 0.47 |
| 7694.01 | 199572211 | PC | SPOC | 13.672 | 2.07 | 2,262 | 13.25 | 12 | 12.7 | 11.2 | 0.26 |

Both sit at the incumbents' SNR floor. Claimed funnel-grade planets from TOIs: 0.7 (search-grade 1.1). Moving sigma by one residual standard deviation gives 0.6 to 0.9.

### 4.3 CTOIs on domain stars [M]

Thirteen entries on twelve stars; two are the promoted TOIs above. Of the nine unpromoted in-band entries not dispositioned FP or FA, four are under 4 Earth radii (funnel probabilities 0.50, 0.44, 0.33, 0.17; sum 1.44). The other five are not small planets: two entries on TIC 406276109 with depths above 900,000 ppm, TIC 165227846 at 131,000 ppm and 18 Earth radii, TIC 298600232 at 53,000 ppm and 9.8 Earth radii, plus two with no period. Two CTOI duration entries (0.06 h and 0.065 h) are clearly bad values and were left as-is.

### 4.4 Claimed against modelled [M]

| | funnel-grade | search-grade |
|---|---:|---:|
| claimed by TOIs (planet candidates) | 0.7 | 1.1 |
| claimed by unpromoted CTOIs under 4 Re | 1.4 | |
| claimed including the giant/EB-like CTOIs | 6.1 | |
| model, same 11,491 stars, if unsearched | 78.7 | 102.5 |
| claimed fraction, small planets | 0.03 | 0.01 |

The yield model's mid prior implied a claimed fraction of about 0.4 for the selected stars. The measured fraction is a few percent.

### 4.5 The 531 stars rejected for a bare SPOC TCE [M]

TCE labels are multi-sector 2-minute runs (for example `TCE s0001-s0039 pn1`). These stars have 1 to 8 sectors on the 2-minute target lists, 0 to 5 of them inside the search window, so they satisfy the FFI-only rule.

| | TCE-rejected 531 | CLEAN domain 10,903 |
|---|---:|---:|
| median Tmag | 13.31 | 13.59 |
| median sectors at 200 s | 15 | 4 |
| sensitivity metric quartiles | 1,274 / 2,143 / 4,105 | selected-2,000 median 1,964 |
| modelled funnel-detectable planets | 5.1 (0.0096 per star) | 73.2 (top 2,000 by the proxy: 20.0) |
| would rank inside the top 2,000 if CLEAN | 355 | |

### 4.6 Check 2, joint detection in the TOI table [M]

| stratum | SPOC-found | QLP-found | both | fraction of SPOC-found also QLP |
|---|---:|---:|---:|---|
| all stars, Tmag below 10.5 | 681 | 796 | 212 | 0.31 (0.28-0.35) |
| all stars, Tmag 12.5-13.5 | 169 | 1,915 | 12 | 0.07 (0.04-0.12) |
| M dwarfs (Teff below 4000 K), Tmag 12.5-13.5 | 51 | 38 | 2 | 0.04 (0.01-0.13) |
| M dwarfs, Tmag below 13.5, pipeline SNR 20-50 | 41 | 44 | 15 | 0.37 (0.24-0.52) |
| pool stars with a 2-minute sector, QLP-found also SPOC-found | 10 | | 0 | 0.00 (0.00-0.28) |

Wilson 95 percent intervals. The bright-star row shows the Detection field records joint detection only at alert time: QLP certainly co-detects far more than 31 percent of SPOC planets on bright stars. **This column cannot measure completeness and Check 2 is inconclusive.** The only usable fact from it is direct: zero QLP-detected TOIs in the domain.

## 5. Interpretation

**Novelty is eliminated as the explanation for zero submissions [I from M].** The domain is not picked over. QLP's main search stops at Tmag 13.5 and its faint-star releases have not reached this population at sectors 56 onward in any volume; TESS-SPOC has promoted two marginal candidates. The yield model's "new" fraction for the selected 2,000 should have been near one, which raises its early-funnel expectation from 11.7 to about 19.

**The early-funnel counts cannot split the remaining two hypotheses [M].** Observed P8 counts and the noise-only predictions from the 300 uninjected calibration stars:

| stage | observed, 2,000 stars | noise prediction (central, 95 percent Poisson on the calibration count) | model's real signals if unsearched |
|---|---:|---|---:|
| Stage A pass | 189 | 240 (168-332), from 36 events | about 24 |
| Stage A plus secondary | 19 | 13.3 (1.6-48), from 2 events | 19 |

The 300 calibration stars are a subset of the 2,000; they contributed 36 of the 189 Stage A passers, the other 1,700 stars 0.090 per star. The observed Stage A count sits at the low edge of noise-plus-model, so the full 19 to 24 real signals are mildly disfavoured but not excluded, and the secondary-level noise rate rests on two events and constrains nothing.

**Ranking of the remaining explanations [I].**

1. Pipeline retention of real planets below the injection-calibrated 43 percent through the early funnel, and the uncalibrated Stage C and D on top. Stage C has a demonstrated false-kill mode (6 of 13 C failures had the survey period at SDE 10 to 15.5 but a one- or two-transit long-period strongest peak). Stage D judged all six inputs as diffuse background, with per-sector aperture errors near the 3 to 4 ppt depths this population produces. P9 measures exactly this.
2. Occurrence: about 45 percent of the model's funnel-grade planets come from the 2-4 Earth-radius class at the DC15 rate of 0.25 per star, weighted toward early M dwarfs; mid-to-late M dwarfs have fewer such planets. This can shave the prediction by a third to a half, not by ten times, and the 1.5-2 Earth-radius share (about 40 percent) is if anything higher around later M dwarfs (HU19 sensitivity in the yield file raises the mid expectation to 15.5).
3. Novelty: eliminated.

**What was wrong before this check.** The claim that incumbents at lower thresholds on the same products had already claimed most funnel-grade planets in this domain. It was a reasonable prior for bright stars and 2-minute targets and is false for faint FFI-only mid-to-late M dwarfs at sectors 56 onward.

## 6. The hard stop discards the best stars

A SPOC TCE is a threshold crossing, not a claim: most are false alarms and none has been promoted on these 531 stars. Stars with the most sectors accumulate the most TCEs, so rejecting on a bare TCE removes the deepest-observed, brightest stars in the domain. The modelled loss is 5.1 funnel-grade planets, a quarter of the selected population's 19, and these are also the stars where an incumbent saw something and did not follow up, so if the rejection is enriched in anything it is enriched in real signals.

Recommendation [I]: treat `spoc_tce` as FLAG at population time and check TCE period agreement at Stage D, or require the TCE to be a promoted TOI before rejecting. This is a target-selection change, not a scientific-threshold change, and it can be evaluated on P9's negative controls for any cost in false-positive survival.

## 7. Caveats

- Sigma is a Tmag fit with 0.223 residual in ln sigma; the claimed count moves between 0.6 and 0.9 across one sigma of that residual.
- The detectability fit reproduces the 2,000 well but extrapolates to stars three times less sensitive than the selected ones. The 78.7 is a model number under DC15 and the P8 injection curve, not a measurement of the sky.
- Catalogue depths and durations are the discovering pipelines' values; the P8-condition SNR uses them without dilution or fit corrections.
- The TOI snapshot is one day's state; TOIs alerted after 2026-09-08 will not be in it.
- The domain excludes the Gaia dwarf check and the FLAG status, which the population builder applies after these cuts; counts differ from the memo by those filters.
- The early-funnel ledger uses the yield model's own noise calibration, whose secondary-level rate rests on two events.

## 8. Implications for P9 and after

- P9's central question is now the right one: real-planet retention through search, pre-gate, A, secondary, B, C and D. Novelty does not need to be modelled as a loss for this domain.
- When P9 recomputes yield (its section 10), the incumbent prior for this population should be near zero claimed, with the occurrence-model uncertainty for 2-4 Earth-radius planets around mid-to-late M dwarfs carried explicitly.
- Any future population build should not reject on a bare SPOC TCE. Re-including the 531 stars is the cheapest yield available.
- The window is not permanent: QLP's faint-star extension will eventually cover these sectors.

## 9. Reproduction

Run with the project venv from this directory:

```bash
"C:/Users/seanj/Downloads/tesshunter_venv/Scripts/python.exe" incumbent_checks.py
```

`incumbent_checks.py` reads the repository files listed in section 2 (edit `REPO` at the top if the tree moves) and `toi_exofop.csv` beside it, and writes `domain_tois.csv`. `incumbent_checks.out` is the run used for this document. The CTOI and TCE-reject follow-ups (sections 4.3 and 4.5) were short inline scripts whose logic is described in section 3 and whose numbers are reproduced by re-running the same joins; the raw CTOI file is `data/cache/catalogs/ctoi/raw/exofop_ctoi.csv`.
