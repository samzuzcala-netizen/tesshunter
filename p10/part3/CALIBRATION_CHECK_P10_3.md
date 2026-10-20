# P10.3 calibration check

**Registered outcome: RETENTION_MEASURED_CALIBRATION_OPTIMISTIC.** [M] Both Part H point-value rules fire on 89 qualifying independent, likely-periodic, in-band, forced-present families on 74 hosts. All 89 have measured outcomes in both presets; the minimum of 40 is met.

**[I] Neither fitted SNR50 is a usable sensitivity threshold.** Both fitted slopes are negative, and the crossings are extreme extrapolations with unstable bootstrap intervals. The literal registered trigger is retained, but these fits do not support a stable increasing recovery-versus-SNR calibration or a quantitative factor by which injection sensitivity is optimistic.

## Registered calculation

[A] The unpenalized model is logit(p_recovered) = a + b × ln(expected SNR), with SNR50 = exp(−a/b). The rule compares that point crossing against 1.3 times the preset-specific search-only injection SNR50. Likely-periodic means model SNR ≥12 and at least three DV-run transits. The subset is INDEPENDENT, in 0.5–30 d, and forced-present. Slope constraints or a changed model were not introduced after viewing outcomes.


| Preset | N / hosts | Recovered qualifying families; 95% CI | a | b | SNR50 point | 95% finite-bootstrap interval | Injection SNR50 [P10] | Threshold | Rule |
|---|---|---|---|---|---|---|---|---|---|
| survey_p10 | 89 / 74 | 68/89; 76.404% [68.085, 84.524] | 1.8669819 | -0.16681864 | 72524.982 | [8.5345427e-19, 1.0742566e+22] | 11.58 | 15.05 | OPTIMISTIC |
| survey_p8 | 89 / 74 | 65/89; 73.034% [63.514, 81.818] | 1.063501 | -0.01632074 | 1.9940496e+28 | [4.5634333e-18, 1.1679795e+22] | 13.15 | 17.1 | OPTIMISTIC |




| Preset | Attempted draws | Finite crossing draws | Nonfinite crossing draws | Negative-slope finite draws | Positive-slope finite draws |
|---|---|---|---|---|---|
| survey_p10 | 10000 | 9965 | 35 | 7028 | 2937 |
| survey_p8 | 10000 | 9965 | 35 | 5147 | 4818 |



[M] Expected SNR in the fitted subset ranges from 12.105075 to 938.50251. Both point crossings lie beyond the measured range. The numerical fit status `IDENTIFIED` records convergence and a finite algebraic crossing; it does not establish a physically identifiable sensitivity threshold. The reported percentile intervals condition on finite crossings. Near-zero bootstrap slopes can produce extreme tails, and the P8 point lies outside its percentile interval; this is another sign of instability.

## Five required autopsies

[M] The five highest expected-SNR independent likely-periodic forced-present misses were selected from the union of the two triggered presets; all five miss in both. Their original searches and primary Part F fits remain unchanged. `AUTOPSIES_P10_3.md` gives the event-removal census, conditional epoch/alias checks, trace and log ranking witnesses, detector-budget flags, and diagnostic plots for each.

[M] Four have a recorded P10 local period-compatible internal-gate survivor that lost selection to a different period. Three nominal TCE durations exceed the frozen 4.8-hour search maximum. Four nominal epochs are uncheckable. All five have counterfactual nominal-ephemeris depth ratios below 0.5 or unmeasured; only one has a recorded detector-budget exhaustion, in P8.

[I] Local selection competition is a shared contributor in at least three cases, satisfying the evidence-count basis for costing one bounded ranking experiment. It is not proof that an alternative would produce an accepted globally matching ephemeris. The counterfactual event diagnostics are not actual Stage A losses: all five first terminate at search matching. Variability, broad nominal durations and epoch uncertainty limit causal attribution.

## Costed next step; no iteration executed

[A] The user explicitly directed that p10.1 be costed only. A future experiment would prospectively fix one ranking/selection variant, remeasure the required injection and control evidence, assess specificity and resource load, freeze the chosen preset, and rerun its paired Part E measurement. No policy was chosen from a measured variant and no variant was tested here.


| Changed preset | Measured 430-host phase (h) | Six-host conservative proxy (h) | Full 436-host rerun planning value (h) | (13.75 + rerun) × 1.25 (h) | Fits current remainder |
|---|---|---|---|---|---|
| survey_p10 | 3.8112683 | 0.32271231 | 4.1339806 | 22.354976 | False |
| survey_p8 | 1.4982053 | 0.32271231 | 1.8209176 | 19.463647 | False |



[M, A] Remaining scientific allocation at costing: 15.824843 h. The six-host timing ledger combines both presets. Charging its entire union interval to each individual changed preset is a conservative planning proxy, not a measured per-preset pilot duration or a tail guarantee. The 13.75 h [P10] is the stipulated 600-injection plus 300-control benchmark. Full 2,100-injection remeasurement remains part of the registered iteration scope; its additional cost is not newly measured here. Even the stipulated subset-based planning test exceeds the remaining budget for either preset.

[I] A future Part 5 also needs independent B/C and endpoint specificity evidence, Stage D and endpoint review, resource forecasting using the observed natural load, and explicit authorization. This development-exposed TCE set cannot serve as its holdout.

## Assumptions and evidence limits

[A] The effective preregistration, its D1–D4 amendment chain, the all_eligible allocation, and the user's prospective supervision amendment govern. Part F's computational conventions were committed before ephemeris exposure. The analysis and autopsy source registrations identify later deterministic reporting code; they do not redefine those rules.

[A] Families use the registered one-percent within-host deduplication, with a deterministic canonical forced fit and a highest-model-SNR representative within each stratum for binning. A family can occur in both strata; union families are deduplicated again. Raw rows preserve run duplicates and share their family's presence classification. Stratum totals therefore cannot simply be added for families.

[A] A recovery may use an exact period or the registered 2, 3, 1/2 or 1/3 aliases, with the conditional epoch check. Exact recovery is kept separate from alias-only recovery. The forced box depth threshold is three conditional standard errors; best-phase fitting when epoch is uncheckable includes a phase search. These errors are not a global false-alarm calibration and do not account for all correlated variability.

[A] Every displayed measured fraction has a 95% percentile interval from 10,000 paired whole-host PCG64 resamples, seed 2026091401. The same 436-host resamples are used across real-data presets and stages. Zero-denominator bootstrap draws are omitted and their valid count is disclosed. Counts alone are censuses, not binomial confidence claims. A degenerate [100,100] empirical bootstrap interval is not a guarantee of perfect population retention.

[I] These are periodic-signal retention measurements, including binaries and systematics. Expected SNR uses catalogue depth/duration and measured later-data scatter, so a large value need not describe a transit in the later data. No endpoint precision, planet yield, or discovery claim follows. Outside-domain and input-ineligible cases are never misses. Operational unknowns and C cases not run are never recoded as scientific failures. [M] All original 531 stars are development-exposed from Part F and cannot be a holdout.
