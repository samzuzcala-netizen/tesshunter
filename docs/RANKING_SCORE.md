# Frozen ranking score and automated gates for the prompt-4 survey

Written 2026-09-03, BEFORE the survey search was started (the only search
run under the P3 code at the time of writing was one 14-second smoke job on
TIC 100196477, used to confirm which fields the survey output carries; its
candidates were not read for thresholds). Implemented by
`scripts/rank_survivors.py`. Nothing below is tuned after the run: every
constant is quoted from the P2 tables (`docs/COMPLETENESS.md`) or the P3
vetting thresholds already in the code. The pipeline finds candidates;
nothing ranked here is a detection.

## 1. Automated gates (all candidates, in this order)

Each accepted candidate of every finished job is one row. A row must pass
every gate to be a "survivor". Counts after each gate go in
`docs/SURVEY_RESULTS.md`.

| gate | rule | where the constant comes from |
|---|---|---|
| G0 | the job finished with status `ok` | orchestrator |
| G1 | the candidate was accepted by the search (any sub-search) | pipeline |
| G2 | whole-stitch re-measurement: `stitch_snr >= 9` AND `stitch_epoch_consistent` | P2: the threshold at which the false-alarm and completeness tables were tabulated (1.07 not-FP candidates per star; 3% of recovered injections lost) |
| G3 | `stitch_n_transits >= 3` | P2: two-event pairings between sectors years apart are the dominant long-period false alarm (1,256 of 2,377 accepted candidates on the 300 stars had 2 transits) |
| G4 | automated light-curve verdict is not "likely false positive" | P3 vetting stack: 0 of 18 known planets were called FP in the adversarial set |
| G5 | the limb-darkened fit converged AND sees the dip: fitted depth / white-noise error >= 3 (`FIT_MIN_DEPTH_SIGMA`) | P3: every recovered dev planet is above 3 sigma (weakest 3.7); the HD 63433 rotation artifacts at BLS SNR 89 and 104 are at 1.1 and 0.3 sigma |
| G6 | one row per signal: two survivors on the same star whose periods are in a ratio of 2 or 3 (within 1%) are the same signal; the higher-scoring row is kept, the other is listed as its harmonic | merge step of the survey already removes equal periods; harmonics are the next duplicate |
| G7 | fresh hard-stop cross-match (all six catalogs re-downloaded at survivor time): status REJECT removes the row; FLAG (known object within 21 arcsec under another TIC) is kept and reported | P1 hard stop; prompt-4 step 3 |
| G8 | packet gate, top 30 only: TRICERATOPS FPP <= 0.5 | P3 rule (`fpp.FPP_MAX_FOR_PACKET`) |

Candidates failing G2 to G5 are still counted and listed in
`data/survey/p4/candidates.csv` with the gate they failed.

## 2. The score

Four terms, each in [0, 1], summed with equal weight. Score range 0 to 4.
Ties broken by `stitch_snr` (descending), then TIC ID, then period.

### S_snr: detection strength

    S_snr = clip( ln(stitch_snr / 9) / ln(50 / 9), 0, 1 )

`stitch_snr` is the BLS SNR re-measured on the whole stitched curve in a
+/-1% period window (for candidates found by the long-period stitch search
it is the search SNR itself). 9 is the gate threshold (0 there); 50 is
where the measured completeness reaches 89% (`COMPLETENESS.md`, recovery by
expected SNR: 64% at 20-50, 89% at >= 50), so the term saturates where the
search is near-complete.

### S_ntr: number of transits

    S_ntr = clip( (stitch_n_transits - 3) / (10 - 3), 0, 1 )

`stitch_n_transits` is the number of transit windows with data on the
whole stitch. 3 is the gate minimum (0 there); 10 saturates it. The P2
completeness by transit count (31% at 3-5, 40% at 6-19, 46% at >= 20
transits) is a mild dependence, which is why this term is bounded and not
logarithmic in the count.

### S_fpp: false-positive probability

    S_fpp = 1 - FPP            when TRICERATOPS ran and returned a value
    S_fpp = 0.5                when TRICERATOPS has not run or failed (neutral)

TRICERATOPS runs only on the top 30 (prompt-4 step 4), so the FIRST ranking
uses 0.5 for every row, the top 30 are taken from that ranking, and the
FINAL ranking re-scores those 30 with their measured FPP while every other
row keeps 0.5. Both rankings are published. P3 measured FPP to be unstable
on inflated giants and some M dwarfs (GJ 436 b at FPP ~1 in every input
mode) and stable in the NFPP; FPP therefore enters as one bounded term of
four, never as a sole ranking key. NFPP is not in the score: NFPP >= 0.1 is
already a high-risk vetting flag (verdict "ambiguous") and FPP > 0.5 is the
packet gate G8.

### S_rho: consistency of the fitted a/R* with the star

Let `dchi2_eff` be the profile delta chi2 between the free fit and the fit
with a/R* confined to the catalog density's 3-sigma range, divided by the
red-noise beta squared, and `ratio` the free-fit stellar density over the
catalog density (both from `transit_fit`, P3 Part A).

    S_rho = 0                                    if a_rs_inconsistent
                                                 (dchi2_eff > 9 AND ratio outside a factor 3)
    S_rho = 0.5                                  if the fit did not converge or the star has
                                                 no catalog density (neutral)
    S_rho = 1                                    if dchi2_eff < 9 (the data cannot reject the
                                                 catalog density; the density prior is adopted)
    S_rho = clip( 1 - |ln ratio| / ln 3, 0, 1 )  otherwise (the data reject the catalog
                                                 value but by less than a factor 3)

The 9 and the factor 3 are the P3 flag thresholds. The piecewise form is
forced by the P3 measurement that at survey SNR the free-fit density ratio
is often meaningless while the profile test is not (a synthetic 2 R_Earth
planet at SNR 15 gave ratio ~0.04 with dchi2 < 9; the smoke job above shows
ratios of 0.01 at dchi2_eff 0.7 to 4.3 on two shallow candidates).

### Total

    score = S_snr + S_ntr + S_fpp + S_rho

## 3. What is deliberately NOT in the score

Depth, planet radius, period, equilibrium temperature, stellar type,
multiplicity, or any measure of how interesting the planet would be. The
verdict enters only as gate G4 (and, through its flags, not at all in the
score). The centroid check enters only through the final verdict shown in
the packet: P3 measured that the P0 centroid module's significance does not
separate known planets from real blends on bright stars.

## 4. Expected number of noise survivors

From `docs/COMPLETENESS.md` section 3 (300 stars, no injection): candidates
with stitch SNR >= 9, consistent epoch, verdict not FP: 1.07 per star; of
those with >= 3 transits: 0.38 per star (the number the memo tabulated) or
0.61 per star when the transit count is the whole-stitch count
(`stitch_n_transits`, the quantity gate G3 uses; 182 of 2,377 candidates).
For 819 stars that is 311 to 500 rows expected to pass G2-G4 from noise and
un-catalogued astrophysical variability alone, before G5 (the fit gate,
which P2 did not have) and before any real signal. The final document
reports the measured counts against these expectations.

## 5. The v2 score (prompt 7)

Written 2026-09-03, AFTER the survey ran and after prompts 5 and 6 measured what
the frozen score does. It is a **second** score, implemented by
`scripts/rank_survivors.py --score v2` and `tesshunter.ranking.score_v2`, written
to `data/survey/p4/survivors_score_v2.csv` and `score_v2.json`. **Everything in
sections 1 to 4 is unchanged**: `survivors.csv`, the frozen ranking and every
number it produced stay exactly as they were, and no prompt-7 code writes to them.
The pipeline finds candidates; a score orders a list and decides nothing.

### Why a second score

[M, prompt 6] Over all 405 survivors the frozen rank correlates with how many of
the six Stage A criteria a candidate passes (Spearman rho = -0.37, p = 9e-15) but
has **no relation at all** to the kept-event SNR, the quantity that measures a
signal in clean, independently re-measured data (rho = -0.065, p = 0.19, n = 405).
The seven Stage A survivors sit at ranks 16, 98, 250, 279, 289, 325 and 398, five
of them below rank 200. `S_snr` ranked on the whole-stitch local-BLS SNR, which
prompt 5 showed the independent data do not reproduce for any shallow candidate.

### The rule

    score_v2 = S_snr2 + S_sectors - 0.25 x (Gaia flags) - 0.5 x (deep-event host)

clipped at zero from below, and **exactly zero when the full-phase secondary scan
fails its gate**. Range 0 to 2.

#### S_snr2: the signal in clean data

    S_snr2 = clip( ln(1 + kept_snr) / ln(1 + 20), 0, 1 )

`kept_snr` is the inverse-variance weighted mean depth over its error, from the
events that survive every removal rule of `docs/AUDIT.md` section 1 step 3, under
the ephemeris that gives the candidate the most credit. 20 saturates the term:
above it the question is no longer whether there is a signal but what it is. This
replaces `S_snr` outright.

#### S_sectors: how many independent sectors show it

    S_sectors = clip( n_sectors_showing_the_dip / 4, 0, 1 )

A sector counts when at least one of its **kept** events measures the dip above
2 sigma. One sector is a sector systematic; four are not. This is the term the
prompt-5 and prompt-6 census argues for most directly: the largest artefact class
(dips absent from SAP, 124 candidates) is concentrated in particular
sector/camera/CCD combinations, so a signal confined to one sector is exactly the
shape of a false positive.

#### The penalties

0.25 for each Gaia flag actually incurred, at these thresholds:

| flag | threshold | note |
|---|---|---|
| RUWE | >= 1.4 | the Stage B number |
| `ipd_frac_multi_peak` | >= 10% | the Stage B number |
| `astrometric_excess_noise_sig` | >= 100 | **not** the Stage B number (2). At 2 the flag fires on most bright stars and would move the whole list down together; prompt 6 measured the two Stage A survivor hosts that are not single stars at 202 and 1560 |
| `non_single_star` | set | |

0.5 for a deep-event host: another accepted candidate on the same star at >= 30
ppt or >= 5 x this candidate's depth (`docs/REVET.md` section 2, Stage B (iii)).
Prompt 6 measured this on 109 of the 405. In the frozen score these were not
inputs at all; here they are subtractions, not vetoes.

#### The secondary gate

Zero when `tesshunter.secondary.secondary_scan` reports `gate: FAIL`, i.e. a dip
away from the primary whose **raw SAP** depth exceeds the deepest secondary an
irradiated planet could produce at the star's a/R* by more than 3 sigma. This is
the one term that is not a matter of degree: a stellar companion is not a planet
candidate at any score. The gate is measured in SAP so that a dip the flux
correction manufactured can never zero a candidate.

### What is deliberately NOT in v2 either

The same list as section 3, plus: TRICERATOPS FPP and the fitted stellar density.
FPP ran only on the top 30 of the frozen ranking, so including it would rank the
405 on a quantity 375 of them do not have; the density term needs a transit fit,
which the audit does not run outside Stage D. Both stay in the packet, where a
human reads them.

### Inputs, and what v2 does not do

Every input already exists on disk when v2 runs: the frozen survivor row, the
prompt-6 Stage A record (kept-event SNR, the per-event table, the deep-event-host
block), the cached Gaia neighbours record, and the prompt-7 option record (the
secondary gate). Nothing is recomputed, nothing is downloaded, and no candidate
is given a SUBMIT / HOLD / KILL verdict by the scorer.
