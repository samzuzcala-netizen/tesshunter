# Planet candidates

All entries are **planet candidates**: periodic transit-like signals in public TESS data that passed this project's
vetting funnel. None is confirmed or statistically validated. Dates are UTC and come from the pipeline's own run
receipts (the search receipt for "first detected", the Stage A vetting receipt for "vetting pass"). Machine-readable
copy: [candidates.csv](candidates.csv).

Status checked on 2026-10-19: none of these TIC IDs appears in the ExoFOP TOI list (8,151 entries) or CTOI list
(5,138 entries), nor in the public candidate list of github.com/eumemic/exoplanets.

## New candidates from S1 batch 1 (2,000 M and K dwarfs searched 2026-10-16 to 2026-10-18)

| TIC | P (d) | T0 (BJD_TDB) | Depth (ppm) | T14 (h) | ~Rp (R⊕) | Verdict | First detected | Vetting pass | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 382098683 | 4.351685 ± 8e-06 | 2458329.13902 ± 0.0033 | 416 | 1.738 | 1.31 | SUBMIT | 2026-10-16 | 2026-10-18 | 4.35 d, ~1.3 R⊕. Archival follow-up: reports/TESS_three_candidate_archival_constraints.pdf |
| 188830138 | 1.181024 ± 3e-06 | 2458764.89089 ± 0.00345 | 347 | 1.64 | 1.43 | SUBMIT | 2026-10-16 | 2026-10-17 | 1.18 d, ~1.4 R⊕. Archival follow-up: reports/TESS_three_candidate_archival_constraints.pdf |
| 116046773 | 5.650272 ± 1.5e-05 | 2458987.88262 ± 0.00263 | 866 | 2.054 | 2.29 | SUBMIT | 2026-10-16 | 2026-10-17 | 5.65 d, ~2.3 R⊕. Vetting: reports/TESS_batch1_deep_analysis.pdf, reports/TESS_seven_candidate_continuation.pdf |
| 201247574 | 16.560576 ± 5.2e-05 | 2458333.60991 ± 0.00633 | 1,559 | 3.24 | 2.44 | HOLD | 2026-10-17 | 2026-10-17 | 16.56 d, ~2.4 R⊕. Archival follow-up: reports/TESS_three_candidate_archival_constraints.pdf |
| 262843927 | 24.108929 | 2458332.78771 | 1,245 | 3.71 | 1.99 | HOLD | 2026-10-17 | 2026-10-18 | 24.11 d, ~2.0 R⊕. Deep follow-up (FU3): top tier; likely unresolved stellar companion; imaging is the next step |
| 270573718 | 41.383701 ± 0.000101 | 2458334.90375 ± 0.00379 | 2,058 | 3.763 | 2.12 | HOLD | 2026-10-16 | 2026-10-18 | 41.38 d, ~2.1 R⊕. Deep follow-up (FU3): second tier; season-level transit-timing offsets unresolved |

TIC 193718989 (P = 24.533 d) was also found by this survey and passed every stage, but it was first posted publicly
by github.com/eumemic/exoplanets on 2026-10-08, so it is not claimed here.

## Further S1 batch-1 candidates under review

| TIC | P (d) | T0 (BJD_TDB) | Depth (ppm) | T14 (h) | ~Rp (R⊕) | Verdict | First detected | Vetting pass | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 207432717 | 43.44458 | 2458767.3044 | 3,771 | 4.56 | 3.67 | HOLD | 2026-10-17 |  | 43.4 d, ~3.7 R⊕; only 4 events; FPP 8% (pipeline) |
| 155949537 | 38.89178 | 2458958.84697 | 1,956 | 4.26 | 2.56 | HOLD | 2026-10-17 |  | 38.9 d, ~2.6 R⊕; only 3 events; FPP 0.9% (pipeline) |
| 18229070 | 22.94881 | 2458996.75547 | 1,394 | 5.86 | 2.18 | HOLD | 2026-10-17 |  | 22.9 d, ~2.2 R⊕; strongest raw signal of the rest; pipeline scene used a wrong Gaia source (fixed ID bug); nearby-binary scenario open |

## Earlier leads

| TIC | P (d) | T0 (BJD_TDB) | Depth (ppm) | T14 (h) | ~Rp (R⊕) | Verdict | First detected | Vetting pass | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 9066956 | 0.71344765 ± 6e-07 | 2460182.82435 ± 0.0006 | 4,070 | 0.72 | 2.6-3.4 | SUBMIT | 2026-10-05 | 2026-10-06 | Ultra-short period around an M dwarf; signal real and on target over 7 years; main loophole a diluted triple; one ground transit in r' decides it |
| 332366289 | 18.748085 | 2459869.87007 |  | 2.23 |  | SUBMIT (P12) | 2026-10-01 |  | Weak: period ambiguous, localisation unresolved; needs new data |

## Reading the table

- **P, T0:** linear ephemeris; T0 is a mid-transit time in BJD_TDB. Blank uncertainties mean the fit covariance was
  singular.
- **Depth, T14, Rp:** from the pipeline's transit fit; Rp assumes the TIC stellar radius and no dilution by an
  unresolved companion.
- **Verdict:** SUBMIT means the candidate met the pipeline's submission bar; HOLD means it passed the funnel with an
  open issue. The reports in [reports/](reports/) and [followup/](followup/) give the evidence for each.
- What would confirm or reject them: ground-based transit photometry at the predicted times, high-resolution imaging
  and radial velocities. Collaboration on follow-up is welcome.
