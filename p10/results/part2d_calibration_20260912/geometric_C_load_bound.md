# Conservative P10 Stage C workload bound

The fixed central DC15 model and claimed fraction 0.03 imply an expected-load upper bound of **148.931095986**, below the unchanged 150-run stop-rule limit. This supplies a sufficient conservative check of the workload component. **Stop Rule 1 is not yet decided:** the complete injection calibration, SNR50_S threshold and final yield review remain pending.

| Component | Expected-count upper bound |
|---|---:|
| Original 2,000 stars, perfect recovery | 100.719993837 |
| Any additional subset of at most 531 stars | 31.337768815 |
| Frozen empirical FA_S * 2,531 term | 16.873333333 |
| Total | 148.931095986 |

For each star and occurrence cell, the original P8 machinery multiplies rate, geometric transit probability, recovery probability and the unclaimed fraction, then averages over its four impact parameters. Recovery probabilities and their average are at most one. Setting all of them to one therefore bounds every possible logistic recovery curve; no prepared-noise measurement is needed for this bound.

The additional-star calculation uses the 531 largest geometric yield weights in the **entire 1,837-star bare-SPOC-only source pool**, a superset of the eventual Part 3 population. Any subset of at most 531 of those stars has a sum no larger than this value. These 531 maximizing identities are mathematical witnesses, **not selected targets**. No new candidate outcome or TCE ephemeris was inspected, and no Part 3 selection or policy was adopted.

The complete final calibration should still supply the original 2,000-star model yield with the new curve and claimed fraction 0.03. The prospective full-population signal expectation is bounded between that original-population value and that value plus 31.337768815. This is a missing-input bounding range, not a confidence interval or a measured-noise estimate for the additional stars. Report it with the calibrated yield and HU19 sensitivity.

This is a bound on **model expectation**, not on the realized candidate count. It retains the central occurrence model, stellar metadata, claimed fraction and empirical FA extrapolation assumptions. Occurrence-model sensitivity and false-alarm sampling uncertainty remain; the later realized 150-run Stage C cap still applies. Every source/input hash and per-star bound is in `geometric_C_load_bound.json`. Three focused tests verify the subset/probability bound, original geometry convention and rejection of invalid inputs.
