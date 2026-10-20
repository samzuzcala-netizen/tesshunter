# P9 planet-by-planet autopsies

Every card uses an individually locked blind outcome. Published ephemerides are used only for the labelled diagnostics. First termination is distinct from contributing evidence. Retained planets are included for comparison.

## Kepler-560 b — search

TIC 239275865; published period 18.477644 d; radius 1.72 Earth radii; duration 1.88 h.
Observed opportunities: 5; expected model SNR: 1.07; box-model expected SNR: 1.03; cadence MAD: 28.9 ppt.
Published timing-error scale at the end of observations / duration: 0.0587. TTV flag: 1.

Evidence and interpretation:

- Blind search accepted 7 signals on the host; none satisfies this planet’s exact period-and-event rule.
- Recorded native search notes, contributing context rather than a causal rescue: ['[chunk0] Planet 1 at P=2.6986 d does not carve a gate-6 exclusion zone: a/R* inconsistent with the star (density ratio 0.01)', '[chunk0] Detection stopped after planet 1: masking P=2.6986 d (width_factor=7) would remove 100% of cadences', '[chunk1] Planet 1 at P=13.6952 d does not carve a gate-6 exclusion zone: Rp/R* 0.460 > 0.2', '[chunk1] Planet 2 at P=18.9343 d does not carve a gate-6 exclusion zone: Rp/R* 0.258 > 0.2', '[chunk1] Planet 3 at P=16.4180 d does not carve a gate-6 exclusion zone: Rp/R* 0.241 > 0.2', '[stitch] Planet 1 at P=23.1812 d does not carve a gate-6 exclusion zone: Rp/R* 0.452 > 0.2', '[stitch] Planet 2 at P=21.7147 d does not carve a gate-6 exclusion zone: Rp/R* 0.481 > 0.2', '[stitch] Planet 3 at P=27.7899 d does not carve a gate-6 exclusion zone: Rp/R* 0.242 > 0.2']
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': False, 'top_share_le_50pct': False, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': False, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 2, 'all_passed': False, 'n_kept': 4, 'kept_snr': -0.58, 'top_event_share': 0.76, 'snr_without_top': -1.47, 'kept_depth_ppt': -1.507, 'kept_depth_err_ppt': 2.586, 'depth_over_survey_depth': -0.66, 'p_const': 0.32666686463932726, 'top_event_n': 299}
- Counterfactual kept-event depth SNR=-0.58; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'momentum_dump': 1, 'sector_orbit_edge': 1}

Contributing tags: expected_SNR_below_pregate_scale, catalogue_TTV_flag_causal_role_unresolved, large_periodic_variability_proxy_may_include_transit_or_artifact, mask_width_stop_recorded_not_proven_causal.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/98d583bf16dc59/autopsy.png)

[Machine-readable diagnostic](diagnostics/98d583bf16dc59/diagnostic.json) · [Locked host outcome](results/locks/tic239275865.json)

## Kepler-629 b — search

TIC 122063843; published period 7.2385854 d; radius 1.38 Earth radii; duration 3.11 h.
Observed opportunities: 12; expected model SNR: 1.21; box-model expected SNR: 1.29; cadence MAD: 4.56 ppt.
Published timing-error scale at the end of observations / duration: 0.0703. TTV flag: 0.

Evidence and interpretation:

- Blind search accepted 7 signals on the host; none satisfies this planet’s exact period-and-event rule.
- Recorded native search notes, contributing context rather than a causal rescue: ['[stitch] Planet 3 at P=26.9792 d does not carve a gate-6 exclusion zone: Rp/R* 0.269 > 0.2']
- 3 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': False, 'top_share_le_50pct': False, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': False, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 2, 'all_passed': False, 'n_kept': 5, 'kept_snr': -0.86, 'top_event_share': 0.88, 'snr_without_top': -1.58, 'kept_depth_ppt': -0.245, 'kept_depth_err_ppt': 0.286, 'depth_over_survey_depth': -1.08, 'p_const': 0.053532868188276406, 'top_event_n': 760}
- Counterfactual kept-event depth SNR=-0.86; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'sap_baseline_ramp': 6, 'momentum_dump': 2, 'pdc_gap': 1, 'scattered_light_flag': 1}

Contributing tags: expected_SNR_below_pregate_scale.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/465c3b4aa82693/autopsy.png)

[Machine-readable diagnostic](diagnostics/465c3b4aa82693/diagnostic.json) · [Locked host outcome](results/locks/tic122063843.json)

## TOI-4860 b — retained

TIC 335590096; published period 1.5227591 d; radius 8.7 Earth radii; duration 1.23 h.
Observed opportunities: 43; expected model SNR: 133; box-model expected SNR: 166; cadence MAD: 10.7 ppt.
Published timing-error scale at the end of observations / duration: 0.00352. TTV flag: 0.

Evidence and interpretation:

- Final review: Useful scientific HOLD: a coherent, physically fitted transit and repeatable primary dimming in the target vicinity survive all automated gates, with no demonstrated nonplanetary cause in the saved evidence. Stage B caps this signal because two neighbours can produce its depth and another accepted deep signal exists on the same host. The combined centroid displacement is only 0.00595 pixel (0.125 arcsec) but formally 9.4 sigma; that statistic alone does not localize the dimming or justify KILL. Native FPP is approximately 4e-15 under its circular-aperture assumptions, which does not remove the source/dilution limitation. Phase-0.5 raw aperture outliers differ across sectors and occur amid large background excursions; the sector-63 box statistic alone is not a repeatable target secondary. This is an unblinded review of blind measurements, without using the published object label to establish retention.
- Blind A chose tls: tls ephemeris, 36 kept events, SNR 117.73, top share 0.04, SNR w/o top 115.54, depth 52.682 ppt = 1.064x survey, p_const 0.35; all six criteria pass. Failed criteria: [].
- Blind secondary scan: CLEAN: no dip above 5 sigma at any other phase
- Blind B: 3 sector(s) could test the period phase-independently, none excludes it; 2 star-level flag(s): 2 neighbour(s) within 3 px bright enough to make the depth if totally eclipsed; same star carries 1 accepted candidate(s) up to 49.27 ppt (>= 30.0 ppt): possible binary host
- Blind C strongest P=1.52 d, SDE=141; maximum near the survey seed SDE=141; survey-region rank=1. strongest peak 1.52275 d is within 1% of the survey period at SDE 141.0
- 16 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': True, 'top_share_le_50pct': True, 'snr_without_top_ge_5': True, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 6, 'all_passed': True, 'n_kept': 36, 'kept_snr': 112.92, 'top_event_share': 0.04, 'snr_without_top': 110.69, 'kept_depth_ppt': 40.633, 'kept_depth_err_ppt': 0.36, 'depth_over_survey_depth': 0.7, 'p_const': 0.15619772372747703, 'top_event_n': -4}
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'pdc_gap': 3, 'momentum_dump': 3, 'scattered_light_flag': 8, 'scattered_light_ramp': 5, 'quality_flagged': 1}

Contributing tags: no additional cause assigned.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/ba38786fba9096/autopsy.png)

[Machine-readable diagnostic](diagnostics/ba38786fba9096/diagnostic.json) · [Locked host outcome](results/locks/tic335590096.json)

## TOI-6002 b — D

TIC 102734241; published period 10.904821 d; radius 1.65 Earth radii; duration 1.66 h.
Observed opportunities: 10; expected model SNR: 10.1; box-model expected SNR: 9.75; cadence MAD: 6.85 ppt.
Published timing-error scale at the end of observations / duration: 0.0626. TTV flag: 0.

Evidence and interpretation:

- Final review: Unresolved scientific HOLD, not credited as useful retention under the preregistered rubric. The photometric fit is coherent, but primary difference images are dominated by broad background residuals and unrelated bright-source residuals. They do not show a convincing repeatable compact dimming patch attributable to the target vicinity. The native fixed-annulus aperture extraction is unavailable in this crowded field. Native FPP is 0.243 and NFPP 0.199 across 3463 TIC stars and 192 scenarios; these probabilities do not establish which source dims. The combined centroid shift is 0.026 arcsec at 2.67 sigma, with some sector flags, and cannot settle localization. There is no demonstrated nonplanetary cause that warrants KILL, but a generic source-unresolved status with this pixel evidence does not satisfy useful-HOLD criteria. The original B cap is preserved. This decision uses the blind measurements and does not inherit the published object label.
- Blind A chose survey: survey ephemeris, 8 kept events, SNR 7.34, top share 0.28, SNR w/o top 6.25, depth 3.684 ppt = 1.174x survey, p_const 0.81; all six criteria pass. Failed criteria: [].
- Blind secondary scan: CLEAN: no dip above 5 sigma at any other phase
- Blind B: 4 sector(s) could test the period phase-independently, none excludes it; 2 star-level flag(s): 200 neighbour(s) within 3 px bright enough to make the depth if totally eclipsed; VSX entry within 1 arcmin ()
- Blind C strongest P=10.9 d, SDE=18.6; maximum near the survey seed SDE=18.6; survey-region rank=1. strongest peak 10.90509 d is within 1% of the survey period at SDE 18.6
- 9 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': True, 'top_share_le_50pct': True, 'snr_without_top_ge_5': True, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 6, 'all_passed': True, 'n_kept': 8, 'kept_snr': 7.02, 'top_event_share': 0.31, 'snr_without_top': 5.82, 'kept_depth_ppt': 3.159, 'kept_depth_err_ppt': 0.45, 'depth_over_survey_depth': 0.816, 'p_const': 0.4611970904214364, 'top_event_n': 153}
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'sector_orbit_edge': 1, 'pdc_gap': 1, 'scattered_light_flag': 1}

Contributing tags: final_review_or_fit_ephemeris.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/9c826f0e0da779/autopsy.png)

[Machine-readable diagnostic](diagnostics/9c826f0e0da779/diagnostic.json) · [Locked host outcome](results/locks/tic102734241.json)

## TOI-5716 b — search

TIC 298074836; published period 6.7663 d; radius 0.96 Earth radii; duration 1.06 h.
Observed opportunities: 10; expected model SNR: 4.61; box-model expected SNR: 5.23; cadence MAD: 5.28 ppt.
Published timing-error scale at the end of observations / duration: 0.0676. TTV flag: 0.

Evidence and interpretation:

- Blind search accepted 4 signals on the host; none satisfies this planet’s exact period-and-event rule.
- 2 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': False, 'top_share_le_50pct': True, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 4, 'all_passed': False, 'n_kept': 8, 'kept_snr': 4.74, 'top_event_share': 0.41, 'snr_without_top': 3.62, 'kept_depth_ppt': 1.984, 'kept_depth_err_ppt': 0.418, 'depth_over_survey_depth': 0.993, 'p_const': 0.10287614531425184, 'top_event_n': 248}
- Counterfactual kept-event depth SNR=4.74; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'sector_orbit_edge': 1, 'scattered_light_ramp': 2, 'scattered_light_flag': 3, 'pdc_gap': 1}

Contributing tags: expected_SNR_below_pregate_scale.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/5246ac243926d5/autopsy.png)

[Machine-readable diagnostic](diagnostics/5246ac243926d5/diagnostic.json) · [Locked host outcome](results/locks/tic298074836.json)

## LP 791-18 c — retained

TIC 181804752; published period 4.98991 d; radius 2.49 Earth radii; duration 1.38 h.
Observed opportunities: 14; expected model SNR: 34.5; box-model expected SNR: 44.3; cadence MAD: 7.92 ppt.
Published timing-error scale at the end of observations / duration: 0.0107. TTV flag: 1.

Evidence and interpretation:

- Final review: Useful scientific HOLD based on repeated coherent photometry and compact target-vicinity dimming, with specific source/astrometry follow-up required. All three available pixel sectors and raw-aperture/background panels were inspected. There is no comparably repeatable primary-like target secondary: phase-0.5 raw-aperture depths are -0.61, -5.76 and +1.57 ppt, with positive sector-100 depth only 1.17 white-noise sigma. Some secondary difference residuals and large off-transit background structures remain, so the images are not a clean-source certificate. The density-prior physical fit has radius 2.432 Earth radii, impact parameter 0.536 and duration 1.138 h with no native uncertainty flags. The native C summary reports a much shorter TLS duration (0.0627 h); D uses its independently fitted all-transit duration and this discrepancy is retained as a diagnostic limitation. FPP is 0.07073 and NFPP 1.61e-8 over 18 scenarios and 60 stars, dominated among false-positive scenarios by an unresolved secondary-star planet; this does not establish the host. The combined centroid is 0.0659 arcsec at 3.06 sigma, with sector 63 individually flagged at 4.22 sigma. Stage B records astrometric excess-noise significance 6.2, five capable neighbours and a VSX entry. These limitations prevent submission-equivalent eligibility. No published planet label or ephemeris supplies a scientific pass.
- Blind A chose tls: tls ephemeris, 14 kept events, SNR 32.1, top share 0.15, SNR w/o top 29.66, depth 17.779 ppt = 0.964x survey, p_const 0.27; all six criteria pass. Failed criteria: [].
- Blind secondary scan: CLEAN: no dip above 5 sigma at any other phase
- Blind B: 3 sector(s) could test the period phase-independently, none excludes it; 3 star-level flag(s): astrometric_excess_noise_sig 6.2 > 2.0; 5 neighbour(s) within 3 px bright enough to make the depth if totally eclipsed; VSX entry within 1 arcmin ()
- Blind C strongest P=4.99 d, SDE=95.5; maximum near the survey seed SDE=95.5; survey-region rank=1. strongest peak 4.98993 d is within 1% of the survey period at SDE 95.5
- 15 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': True, 'top_share_le_50pct': True, 'snr_without_top_ge_5': True, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 6, 'all_passed': True, 'n_kept': 14, 'kept_snr': 28.43, 'top_event_share': 0.14, 'snr_without_top': 26.36, 'kept_depth_ppt': 11.905, 'kept_depth_err_ppt': 0.419, 'depth_over_survey_depth': 0.629, 'p_const': 0.19959034850590443, 'top_event_n': 507}
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'scattered_light_flag': 1}

Contributing tags: catalogue_TTV_flag_causal_role_unresolved.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/4dcec2621b8353/autopsy.png)

[Machine-readable diagnostic](diagnostics/4dcec2621b8353/diagnostic.json) · [Locked host outcome](results/locks/tic181804752.json)

## TOI-3235 b — retained

TIC 243641947; published period 2.5926184 d; radius 11.4 Earth radii; duration 1.48 h.
Observed opportunities: 26; expected model SNR: 109; box-model expected SNR: 198; cadence MAD: 7.6 ppt.
Published timing-error scale at the end of observations / duration: 0.00382. TTV flag: 0.

Evidence and interpretation:

- Final review: Useful scientific HOLD based on a highly coherent fitted event and strong repeatable compact primary dimming in the target vicinity. The frozen B flags include astrometric excess-noise significance 3.6, possible contaminating neighbours and a VSX entry. A free-density fit is preferred over the stellar-density prior by delta chi-square 273; the ratio of fitted to catalogue density is 1.70. Native FPP/NFPP round to zero with essentially all weight on a planet orbiting the primary of an unresolved binary; this model concentration is not proof of the source or dilution. Centroid displacement is 0.00498 pixel (0.105 arcsec), formally 16.8 sigma, so a scalar significance cannot distinguish dilution-induced motion from an off-target event. The original aperture extractor is unavailable in all sectors because the crowded field leaves insufficient clean sky pixels. The successful native difference measurements support a specific source/density follow-up, while the auxiliary extraction limitation remains explicit. No published planet label supplies the verdict.
- Blind A chose tls: tls ephemeris, 26 kept events, SNR 242.94, top share 0.06, SNR w/o top 235.23, depth 79.755 ppt = 1.408x survey, p_const 0.17; all six criteria pass. Failed criteria: [].
- Blind secondary scan: CLEAN: no dip above 5 sigma at any other phase
- Blind B: 3 sector(s) could test the period phase-independently, none excludes it; 4 star-level flag(s): astrometric_excess_noise_sig 3.6 > 2.0; 47 neighbour(s) within 3 px bright enough to make the depth if totally eclipsed; VSX entry within 1 arcmin (); same star carries 1 accepted candidate(s) up to 57.95 ppt (>= 30.0 ppt): possible binary host
- Blind C strongest P=2.59 d, SDE=269; maximum near the survey seed SDE=269; survey-region rank=1. strongest peak 2.59261 d is within 1% of the survey period at SDE 268.8
- 21 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': True, 'top_share_le_50pct': True, 'snr_without_top_ge_5': True, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': False}, 'n_criteria_passed': 5, 'all_passed': False, 'n_kept': 26, 'kept_snr': 223.62, 'top_event_share': 0.06, 'snr_without_top': 216.71, 'kept_depth_ppt': 61.367, 'kept_depth_err_ppt': 0.274, 'depth_over_survey_depth': 0.785, 'p_const': 3.855587793238078e-06, 'top_event_n': 562}
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'scattered_light_flag': 2, 'quality_flagged': 1}

Contributing tags: no additional cause assigned.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/422726f2b0d498/autopsy.png)

[Machine-readable diagnostic](diagnostics/422726f2b0d498/diagnostic.json) · [Locked host outcome](results/locks/tic243641947.json)

## LP 791-18 b — search

TIC 181804752; published period 0.9479981 d; radius 1.21 Earth radii; duration 0.62 h.
Observed opportunities: 74; expected model SNR: 13.7; box-model expected SNR: 15.3; cadence MAD: 7.92 ppt.
Published timing-error scale at the end of observations / duration: 0.2. TTV flag: 0.

Evidence and interpretation:

- Blind search accepted 9 signals on the host; none satisfies this planet’s exact period-and-event rule.
- Recorded native search notes, contributing context rather than a causal rescue: ['[chunk2] Planet 2 at P=11.8347 d does not carve a gate-6 exclusion zone: a/R* inconsistent with the star (density ratio 0.03)']
- 29 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Recorded local competition in chunk0, pass 2: near-period 0.9485 d candidate passed internal gates at composite 5.2 (log line 218), but 10.232323 d won at composite 5.33 (line 247). Period proximity is diagnostic only; no alternative global recovery is credited.
- Recorded local competition in chunk0, pass 3: near-period 0.9485 d candidate passed internal gates at composite 4.29 (log line 300), but 3.317685 d won at composite 5.02 (line 371). Period proximity is diagnostic only; no alternative global recovery is credited.
- Recorded local competition in chunk2, pass 2: near-period 0.9477 d candidate passed internal gates at composite 4.67 (log line 890), but 11.83472 d won at composite 5.81 (line 985). Period proximity is diagnostic only; no alternative global recovery is credited.
- Recorded local competition in chunk2, pass 3: near-period 0.9477 d candidate passed internal gates at composite 3.88 (log line 1005), but 8.539564 d won at composite 5.24 (line 1096). Period proximity is diagnostic only; no alternative global recovery is credited.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': True, 'top_share_le_50pct': True, 'snr_without_top_ge_5': True, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 6, 'all_passed': True, 'n_kept': 69, 'kept_snr': 10.22, 'top_event_share': 0.08, 'snr_without_top': 9.86, 'kept_depth_ppt': 2.86, 'kept_depth_err_ppt': 0.28, 'depth_over_survey_depth': 0.681, 'p_const': 0.9701559604096843, 'top_event_n': 2447}
- Counterfactual kept-event depth SNR=10.2; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'momentum_dump': 2, 'pdc_gap': 4, 'scattered_light_flag': 10, 'scattered_light_ramp': 2, 'quality_flagged': 2, 'sector_orbit_edge': 1}

Contributing tags: higher_SNR_search_miss_requires_attention, local_near_period_candidate_lost_composite_selection.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/a098bef9d9e8f5/autopsy.png)

[Machine-readable diagnostic](diagnostics/a098bef9d9e8f5/diagnostic.json) · [Locked host outcome](results/locks/tic181804752.json)

## TOI-849 b — search

TIC 33595516; published period 0.765548 d; radius 3.64 Earth radii; duration 1.45 h.
Observed opportunities: 110; expected model SNR: 38.6; box-model expected SNR: 40.6; cadence MAD: 1.85 ppt.
Published timing-error scale at the end of observations / duration: 2.71. TTV flag: 0.

Evidence and interpretation:

- Accepted near-period signals failed alignment: [{'planet_num': 1, 'period': 0.7655350424820992, 'match': {'ratio': 1, 'period_fraction': 1.6925807265866233e-05, 'matched': False, 'matched_events': 0, 'n_truth_opportunities': 110, 'n_found_opportunities': 110, 'truth_fraction': 0.0, 'found_fraction': 0.0, 'mean_normalized_timing_residual': None}}]
- Blind search accepted 4 signals on the host; none satisfies this planet’s exact period-and-event rule.
- Post-lock alternative published timing matches existing blind outputs: {'reference': '<a refstr=ARMSTRONG_ET_AL__2020 href=https://ui.adsabs.harvard.edu/abs/2020Natur.583...39A/abstract target=ref>Armstrong et al. 2020</a>', 'default_flag': 0, 'period': 0.76552414, 'epoch_btjd': 1394.7376799997874, 'duration_hours': 1.57, 'duration_source': 'same published PS solution', 'ephemeris_sigma_over_duration': 0.15884033754981727, 'candidate_matches': [{'key': 'tic33595516_P0.7655', 'event_match': {'ratio': 1, 'period_fraction': 1.4241852777097108e-05, 'matched': True, 'matched_events': 110, 'n_truth_opportunities': 111, 'n_found_opportunities': 110, 'truth_fraction': 0.990990990990991, 'found_fraction': 1.0, 'mean_normalized_timing_residual': 0.0952219450240787}, 'timing': {'median_absolute_hours': 0.10609620403556619, 'minimum_absolute_hours': 0.08856501280388329, 'maximum_absolute_hours': 0.18956560697915847}}], 'diagnostic_existing_path': {'search': True, 'pre': True, 'A': True, 'S': True, 'B': True, 'C': True, 'D_submit': False, 'D_useful': True}, 'diagnostic_first_termination': 'retained', 'primary_credit': False, 'no_scientific_stage_rerun': True}. This is a truth-timing sensitivity, not a search rerun, a changed verdict or primary recovery credit.
- Recorded native search notes, contributing context rather than a causal rescue: ['[chunk0] Detection stopped after planet 1: masking P=0.7655 d (width_factor=7) would remove 100% of cadences', '[chunk1] Detection stopped after planet 1: masking P=0.7655 d (width_factor=7) would remove 100% of cadences']
- 11 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': False, 'top_share_le_50pct': True, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': False, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 3, 'all_passed': False, 'n_kept': 99, 'kept_snr': -3.83, 'top_event_share': 0.22, 'snr_without_top': -4.09, 'kept_depth_ppt': -0.136, 'kept_depth_err_ppt': 0.036, 'depth_over_survey_depth': -0.096, 'p_const': 0.9935891892213673, 'top_event_n': 3041}
- Counterfactual kept-event depth SNR=-3.83; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'scattered_light_ramp': 17, 'scattered_light_flag': 17, 'sap_baseline_ramp': 5, 'pdc_gap': 9, 'momentum_dump': 5, 'quality_flagged': 7, 'sector_orbit_edge': 1}

Contributing tags: higher_SNR_search_miss_requires_attention, near_period_but_failed_multi_event_alignment, published_ephemeris_uncertainty_material, alternative_published_ephemeris_matches_locked_signal_no_primary_credit, mask_width_stop_recorded_not_proven_causal.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/b6177baeeb2a65/autopsy.png)

[Machine-readable diagnostic](diagnostics/b6177baeeb2a65/diagnostic.json) · [Locked host outcome](results/locks/tic33595516.json)

## Kepler-1328 b — search

TIC 164778883; published period 4.5215889 d; radius 0.98 Earth radii; duration 3.49 h.
Observed opportunities: 22; expected model SNR: 0.353; box-model expected SNR: 0.403; cadence MAD: 7.5 ppt.
Published timing-error scale at the end of observations / duration: 0.188. TTV flag: 0.

Evidence and interpretation:

- Blind search accepted 5 signals on the host; none satisfies this planet’s exact period-and-event rule.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': False, 'kept_snr_ge_7': False, 'top_share_le_50pct': False, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': False, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 1, 'all_passed': False, 'n_kept': 2, 'kept_snr': -0.61, 'top_event_share': 1.0, 'snr_without_top': -0.84, 'kept_depth_ppt': -0.329, 'kept_depth_err_ppt': 0.537, 'depth_over_survey_depth': -3.995, 'p_const': 0.5634568272198128, 'top_event_n': 1189}
- Counterfactual kept-event depth SNR=-0.61; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'scattered_light_ramp': 2, 'sap_baseline_ramp': 21, 'momentum_dump': 3, 'scattered_light_flag': 2, 'pdc_gap': 1}

Contributing tags: expected_SNR_below_pregate_scale.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/69a4e349a89233/autopsy.png)

[Machine-readable diagnostic](diagnostics/69a4e349a89233/diagnostic.json) · [Locked host outcome](results/locks/tic164778883.json)

## HIP 97166 b — C

TIC 237222864; published period 10.288914 d; radius 2.48 Earth radii; duration 1.53 h.
Observed opportunities: 37; expected model SNR: 69.6; box-model expected SNR: 53.1; cadence MAD: 0.518 ppt.
Published timing-error scale at the end of observations / duration: 0.0201. TTV flag: 0.

Evidence and interpretation:

- First-termination record: strongest peak 10.28867 d (SDE 3.6, alias 1:1 at 0.000); SDE within 1% of the survey period 3.5565640212472625
- Blind A chose survey: survey ephemeris, 33 kept events, SNR 41.79, top share 0.05, SNR w/o top 40.83, depth 0.771 ppt = 1.11x survey, p_const 0.03; all six criteria pass. Failed criteria: [].
- Blind secondary scan: CLEAN: no dip above 5 sigma at any other phase
- Blind B: 17 sector(s) could test the period phase-independently, none excludes it; 2 star-level flag(s): astrometric_excess_noise_sig 6.2 > 2.0; 1 neighbour(s) within 3 px bright enough to make the depth if totally eclipsed
- Blind C strongest P=10.3 d, SDE=3.56; maximum near the survey seed SDE=3.56; survey-region rank=1. strongest peak 10.28867 d (SDE 3.6, alias 1:1 at 0.000); SDE within 1% of the survey period 3.5565640212472625
- Saved native spectrum minimum is -336.04669 at 0.5946280368 d; that single bin contributes 99.864149% of total centered power variance across 113081 trials. TLS uses the global standard deviation in SDE normalization. No bin is removed, no alternative SDE is scored, and raw chi-square trial residuals were not saved to establish the upstream origin.
- 11 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': True, 'top_share_le_50pct': True, 'snr_without_top_ge_5': True, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 6, 'all_passed': True, 'n_kept': 33, 'kept_snr': 42.36, 'top_event_share': 0.05, 'snr_without_top': 41.37, 'kept_depth_ppt': 0.73, 'kept_depth_err_ppt': 0.017, 'depth_over_survey_depth': 0.855, 'p_const': 0.018117910293845296, 'top_event_n': 186}
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'pdc_gap': 2, 'sector_orbit_edge': 1, 'scattered_light_ramp': 1, 'scattered_light_flag': 2, 'momentum_dump': 1}

Contributing tags: C_SDE_below_threshold.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/79bedbb8b7444c/autopsy.png)

[Machine-readable diagnostic](diagnostics/79bedbb8b7444c/diagnostic.json) · [Locked host outcome](results/locks/tic237222864.json)

## TOI-1680 b — retained

TIC 259168516; published period 4.8026345 d; radius 1.47 Earth radii; duration 1.19 h.
Observed opportunities: 90; expected model SNR: 28.6; box-model expected SNR: 28; cadence MAD: 6.34 ppt.
Published timing-error scale at the end of observations / duration: 0.0288. TTV flag: 0.

Evidence and interpretation:

- Final review: Useful scientific HOLD: coherent repeated photometry and target-vicinity dimming support a specific source/background investigation, with no demonstrated nonplanetary explanation. All 19 selected pixel sectors and all seven pages of both difference and raw-aperture evidence were reviewed. FPP is 0.02743 and NFPP 2.61e-11 over 21 scenarios and 163 stars, with most false-positive probability in the unresolved secondary-star planet scenario; model priors do not establish the host. The weighted centroid is 0.0127 arcsec at 1.59 sigma, but sectors 56, 59, 73 and 80 are individually flagged. Broad primary residuals dominate sectors 74, 80 and 86; sector 60 has an incomplete cutout edge. The auxiliary aperture extraction is available in all sectors but is not uniformly clean: sector 59 returns a negative primary depth, while sectors 60 and 73 return apparent phase-0.5 dips of 40.0 and 54.0 ppt amid very large background and baseline structures. Those dips lack a consistently repeated target-localized secondary across the other sectors; they remain limitations, not an adopted eclipse detection or a clean-source certificate. Source confusion and background systematics prevent submission-equivalent eligibility. Published labels and ephemerides supply no evidence for this verdict.
- Blind A chose tls: tls ephemeris, 80 kept events, SNR 26.44, top share 0.03, SNR w/o top 26.06, depth 4.279 ppt = 1.068x survey, p_const 0.24; all six criteria pass. Failed criteria: [].
- Blind secondary scan: CLEAN: no dip above 5 sigma at any other phase
- Blind B: 19 sector(s) could test the period phase-independently, none excludes it; 1 star-level flag(s): 13 neighbour(s) within 3 px bright enough to make the depth if totally eclipsed
- Blind C strongest P=4.8 d, SDE=116; maximum near the survey seed SDE=116; survey-region rank=1. strongest peak 4.80261 d is within 1% of the survey period at SDE 116.1
- 15 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': True, 'top_share_le_50pct': True, 'snr_without_top_ge_5': True, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 6, 'all_passed': True, 'n_kept': 79, 'kept_snr': 26.61, 'top_event_share': 0.03, 'snr_without_top': 26.22, 'kept_depth_ppt': 4.061, 'kept_depth_err_ppt': 0.153, 'depth_over_survey_depth': 0.998, 'p_const': 0.13838102760794177, 'top_event_n': 336}
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'momentum_dump': 6, 'scattered_light_flag': 9, 'scattered_light_ramp': 7, 'sector_orbit_edge': 3, 'sap_baseline_ramp': 2, 'pdc_gap': 1, 'quality_flagged': 1}

Contributing tags: no additional cause assigned.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/9215c347814feb/autopsy.png)

[Machine-readable diagnostic](diagnostics/9215c347814feb/diagnostic.json) · [Locked host outcome](results/locks/tic259168516.json)

## Kepler-994 b — search

TIC 158983792; published period 1.1511665 d; radius 1.6 Earth radii; duration 1.19 h.
Observed opportunities: 95; expected model SNR: 4.75; box-model expected SNR: 4.87; cadence MAD: 6.8 ppt.
Published timing-error scale at the end of observations / duration: 0.0565. TTV flag: 0.

Evidence and interpretation:

- Blind search accepted 6 signals on the host; none satisfies this planet’s exact period-and-event rule.
- Recorded native search notes, contributing context rather than a causal rescue: ['[chunk0] Planet 1 at P=20.9527 d does not carve a gate-6 exclusion zone: Rp/R* 0.277 > 0.2', '[chunk0] Planet 3 at P=12.9341 d does not carve a gate-6 exclusion zone: Rp/R* 0.309 > 0.2', '[stitch] Planet 2 at P=13.4409 d does not carve a gate-6 exclusion zone: Rp/R* 0.218 > 0.2']
- 1 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': False, 'top_share_le_50pct': True, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': False, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 3, 'all_passed': False, 'n_kept': 88, 'kept_snr': 1.8, 'top_event_share': 0.12, 'snr_without_top': 1.46, 'kept_depth_ppt': 0.28, 'kept_depth_err_ppt': 0.155, 'depth_over_survey_depth': 0.379, 'p_const': 0.3620367668874212, 'top_event_n': 4654}
- Counterfactual kept-event depth SNR=1.8; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'scattered_light_flag': 17, 'pdc_gap': 4, 'momentum_dump': 5, 'scattered_light_ramp': 4, 'sector_orbit_edge': 1, 'sap_baseline_ramp': 1}

Contributing tags: expected_SNR_below_pregate_scale.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/ace1f11abf85b6/autopsy.png)

[Machine-readable diagnostic](diagnostics/ace1f11abf85b6/diagnostic.json) · [Locked host outcome](results/locks/tic158983792.json)

## Kepler-995 b — search

TIC 120315006; published period 28.267317 d; radius 2.7 Earth radii; duration 4.57 h.
Observed opportunities: 3; expected model SNR: 0.985; box-model expected SNR: 1.02; cadence MAD: 14.6 ppt.
Published timing-error scale at the end of observations / duration: 0.0901. TTV flag: 0.

Evidence and interpretation:

- Blind search accepted 4 signals on the host; none satisfies this planet’s exact period-and-event rule.
- Recorded native search notes, contributing context rather than a causal rescue: ['[chunk1] Planet 2 at P=22.7831 d does not carve a gate-6 exclusion zone: Rp/R* 0.325 > 0.2', '[stitch] Planet 2 at P=22.7806 d does not carve a gate-6 exclusion zone: Rp/R* 0.319 > 0.2', '[stitch] Planet 3 at P=21.6389 d does not carve a gate-6 exclusion zone: Rp/R* 0.320 > 0.2']
- 2 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Recorded local competition in stitch, pass 2: near-period 28.0238 d candidate passed internal gates at composite 5.36 (log line 600), but 22.780642 d won at composite 5.66 (line 627). Period proximity is diagnostic only; no alternative global recovery is credited.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': False, 'kept_snr_ge_7': False, 'top_share_le_50pct': False, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': False, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 1, 'all_passed': False, 'n_kept': 2, 'kept_snr': -0.39, 'top_event_share': 1.0, 'snr_without_top': -0.79, 'kept_depth_ppt': -0.515, 'kept_depth_err_ppt': 1.329, 'depth_over_survey_depth': -0.538, 'p_const': 0.5156785487266269, 'top_event_n': 189}
- Counterfactual kept-event depth SNR=-0.39; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'sap_baseline_ramp': 1}

Contributing tags: expected_SNR_below_pregate_scale, local_near_period_candidate_lost_composite_selection.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/95eae91e000f28/autopsy.png)

[Machine-readable diagnostic](diagnostics/95eae91e000f28/diagnostic.json) · [Locked host outcome](results/locks/tic120315006.json)

## Kepler-922 b — search

TIC 48448415; published period 0.93846683 d; radius 1.42 Earth radii; duration 1.27 h.
Observed opportunities: 116; expected model SNR: 1.82; box-model expected SNR: 1.66; cadence MAD: 6.08 ppt.
Published timing-error scale at the end of observations / duration: 0.108. TTV flag: 0.

Evidence and interpretation:

- Blind search accepted 7 signals on the host; none satisfies this planet’s exact period-and-event rule.
- Recorded native search notes, contributing context rather than a causal rescue: ['[chunk0] Planet 2 at P=19.8656 d does not carve a gate-6 exclusion zone: Rp/R* 0.279 > 0.2', '[chunk1] Planet 1 at P=26.4333 d does not carve a gate-6 exclusion zone: a/R* inconsistent with the star (density ratio 152.55)', '[stitch] Planet 3 at P=26.7250 d does not carve a gate-6 exclusion zone: Rp/R* 0.325 > 0.2']
- 2 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': False, 'top_share_le_50pct': True, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': False, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 3, 'all_passed': False, 'n_kept': 90, 'kept_snr': 0.69, 'top_event_share': 0.11, 'snr_without_top': 0.35, 'kept_depth_ppt': 0.091, 'kept_depth_err_ppt': 0.131, 'depth_over_survey_depth': 0.464, 'p_const': 0.024632845935102468, 'top_event_n': 5749}
- Counterfactual kept-event depth SNR=0.69; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'sap_baseline_ramp': 27, 'scattered_light_flag': 23, 'momentum_dump': 7, 'scattered_light_ramp': 9, 'sector_orbit_edge': 2, 'pdc_gap': 3}

Contributing tags: expected_SNR_below_pregate_scale.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/e149d2db6b69b1/autopsy.png)

[Machine-readable diagnostic](diagnostics/e149d2db6b69b1/diagnostic.json) · [Locked host outcome](results/locks/tic48448415.json)

## TOI-1080 b — retained

TIC 161032923; published period 3.9652482 d; radius 1.2 Earth radii; duration 1.02 h.
Observed opportunities: 21; expected model SNR: 13.2; box-model expected SNR: 16; cadence MAD: 4.48 ppt.
Published timing-error scale at the end of observations / duration: 0.0138. TTV flag: 0.

Evidence and interpretation:

- Final review: Useful scientific HOLD for a repeated coherent transit-like signal with a specific unresolved source limitation. All four available primary/secondary pixel panels and the physical-fit packet were inspected. The target-vicinity patch contains unresolved Gaia components. Sector 104 has a small positive phase-0.5 residual near the target and other off-target residuals, but a comparably repeated compact secondary is not established in sectors 66, 93 and 103; the native full-phase secondary gate passes. The density-prior fit gives 1.218 Earth radii, impact parameter 0.423 and duration 1.123 h, with no native uncertainty issues. Native FPP is 0.04509 and NFPP 0.002163 over fifty-four scenarios and 598 stars, including nearby EB scenarios and an unresolved secondary-star planet contribution. The native four-sector centroid is 0.0230 arcsec at 2.09 sigma, with no individual sector flags; this does not isolate the host. Stage B records astrometric excess-noise significance 2.1 and thirty capable neighbours, capping the verdict at HOLD. All four auxiliary fixed-aperture sectors are unavailable, with only 3, 4, 5 and 2 clean sky pixels under the unchanged requirement of sixteen. That missing auxiliary measurement is not evidence against contamination. No published planet label or ephemeris supplies a scientific pass.
- Blind A chose tls: tls ephemeris, 19 kept events, SNR 13.42, top share 0.13, SNR w/o top 12.46, depth 3.528 ppt = 0.788x survey, p_const 0.007; all six criteria pass. Failed criteria: [].
- Blind secondary scan: CLEAN: no dip above 5 sigma at any other phase
- Blind B: 4 sector(s) could test the period phase-independently, none excludes it; 2 star-level flag(s): astrometric_excess_noise_sig 2.1 > 2.0; 30 neighbour(s) within 3 px bright enough to make the depth if totally eclipsed
- Blind C strongest P=3.97 d, SDE=46.7; maximum near the survey seed SDE=46.7; survey-region rank=1. strongest peak 3.96526 d is within 1% of the survey period at SDE 46.7
- 16 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': True, 'top_share_le_50pct': True, 'snr_without_top_ge_5': True, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 6, 'all_passed': True, 'n_kept': 19, 'kept_snr': 14.55, 'top_event_share': 0.12, 'snr_without_top': 13.56, 'kept_depth_ppt': 3.44, 'kept_depth_err_ppt': 0.236, 'depth_over_survey_depth': 0.935, 'p_const': 0.010328605146783285, 'top_event_n': 87}
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'momentum_dump': 1, 'scattered_light_ramp': 2, 'scattered_light_flag': 3, 'pdc_gap': 2, 'quality_flagged': 1}

Contributing tags: no additional cause assigned.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/e5450a129d373a/autopsy.png)

[Machine-readable diagnostic](diagnostics/e5450a129d373a/diagnostic.json) · [Locked host outcome](results/locks/tic161032923.json)

## Kepler-607 b — search

TIC 159579593; published period 0.6381632 d; radius 0.87 Earth radii; duration 1.18 h.
Observed opportunities: 154; expected model SNR: 0.612; box-model expected SNR: 0.605; cadence MAD: 9.4 ppt.
Published timing-error scale at the end of observations / duration: 0.302. TTV flag: 0.

Evidence and interpretation:

- Blind search accepted 6 signals on the host; none satisfies this planet’s exact period-and-event rule.
- Recorded native search notes, contributing context rather than a causal rescue: ['[stitch] Planet 3 at P=15.1733 d does not carve a gate-6 exclusion zone: Rp/R* 0.310 > 0.2']
- 1 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': False, 'top_share_le_50pct': True, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': False, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 3, 'all_passed': False, 'n_kept': 103, 'kept_snr': 1.37, 'top_event_share': 0.09, 'snr_without_top': 1.09, 'kept_depth_ppt': 0.27, 'kept_depth_err_ppt': 0.198, 'depth_over_survey_depth': 2.716, 'p_const': 0.19650107790294172, 'top_event_n': 8691}
- Counterfactual kept-event depth SNR=1.37; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'sap_baseline_ramp': 50, 'scattered_light_flag': 12, 'momentum_dump': 7, 'pdc_gap': 5, 'sector_orbit_edge': 3}

Contributing tags: expected_SNR_below_pregate_scale.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/e58f46054d26aa/autopsy.png)

[Machine-readable diagnostic](diagnostics/e58f46054d26aa/diagnostic.json) · [Locked host outcome](results/locks/tic159579593.json)

## TOI-762 A b — retained

TIC 178709444; published period 3.4716826 d; radius 8.34 Earth radii; duration 1.39 h.
Observed opportunities: 26; expected model SNR: 66.9; box-model expected SNR: 85.8; cadence MAD: 9.07 ppt.
Published timing-error scale at the end of observations / duration: 0.00476. TTV flag: 0.

Evidence and interpretation:

- Final review: Useful scientific HOLD for a coherent deep transit-like signal with specific unresolved source, dilution and density questions. All four available native primary/secondary pixel panels and the physical-fit packet were inspected. The field is very crowded, and nearby Gaia components within the target patch are not resolved by this qualitative review. Strong off-target bright-source dipoles appear in primary and secondary difference images, so those residuals are not assigned to a target secondary. Stage B reports fifteen capable neighbours and caps the verdict at HOLD. The all-transit fit gives 7.909 Earth radii, impact parameter 0.652 and duration about 1.33 h; the stellar-density prior is rejected with prior-minus-free delta chi-square 39.14 and fitted/catalogue density ratio 2.094. Native FPP is 4.70e-14 and NFPP 3.83e-30 across 27 scenarios and 515 stars, with the DTP scenario dominating; these model-dependent numbers do not identify the source or remove the dilution concern. The native weighted centroid combines three sectors, giving 0.00235 arcsec at 0.387 sigma. Sector 99's zero reported shift and zero uncertainty are excluded from that combination and are not a perfect localization constraint; its available pixels were nevertheless reviewed. The independent sky-subtracted aperture diagnostic is unavailable in all four sectors because only 4, 2, 1 and 4 clean sky pixels survive the unchanged requirement of sixteen. The auxiliary availability failure is explicitly retained. No published planet label or ephemeris supplies a scientific pass, and actual submission eligibility is false.
- Blind A chose tls: tls ephemeris, 25 kept events, SNR 63.8, top share 0.05, SNR w/o top 62.1, depth 26.17 ppt = 0.956x survey, p_const 0.017; all six criteria pass. Failed criteria: [].
- Blind secondary scan: CLEAN: no dip above 5 sigma at any other phase
- Blind B: 4 sector(s) could test the period phase-independently, none excludes it; 1 star-level flag(s): 15 neighbour(s) within 3 px bright enough to make the depth if totally eclipsed
- Blind C strongest P=3.47 d, SDE=131; maximum near the survey seed SDE=131; survey-region rank=1. strongest peak 3.47166 d is within 1% of the survey period at SDE 131.2
- 21 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': True, 'top_share_le_50pct': True, 'snr_without_top_ge_5': True, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 6, 'all_passed': True, 'n_kept': 25, 'kept_snr': 59.16, 'top_event_share': 0.06, 'snr_without_top': 57.51, 'kept_depth_ppt': 21.009, 'kept_depth_err_ppt': 0.355, 'depth_over_survey_depth': 0.686, 'p_const': 0.08939889310075118, 'top_event_n': 355}
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'pdc_gap': 1, 'scattered_light_flag': 3, 'scattered_light_ramp': 1}

Contributing tags: no additional cause assigned.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/ab8dcba5def0ac/autopsy.png)

[Machine-readable diagnostic](diagnostics/ab8dcba5def0ac/diagnostic.json) · [Locked host outcome](results/locks/tic178709444.json)

## Kepler-262 b — search

TIC 122673489; published period 13.060855 d; radius 1.36 Earth radii; duration 3.28 h.
Observed opportunities: 6; expected model SNR: 0.0902; box-model expected SNR: 0.114; cadence MAD: 33.1 ppt.
Published timing-error scale at the end of observations / duration: 0.515. TTV flag: 0.

Evidence and interpretation:

- Blind search accepted 8 signals on the host; none satisfies this planet’s exact period-and-event rule.
- Recorded native search notes, contributing context rather than a causal rescue: ['[chunk0] Planet 1 at P=26.9263 d does not carve a gate-6 exclusion zone: Rp/R* 0.269 > 0.2', '[chunk1] Planet 2 at P=9.5078 d does not carve a gate-6 exclusion zone: Rp/R* 0.346 > 0.2', '[stitch] Planet 2 at P=18.6522 d does not carve a gate-6 exclusion zone: Rp/R* 0.213 > 0.2', '[stitch] Planet 3 at P=14.8405 d does not carve a gate-6 exclusion zone: Rp/R* 0.348 > 0.2']
- 8 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': False, 'kept_snr_ge_7': False, 'top_share_le_50pct': False, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': False, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 1, 'all_passed': False, 'n_kept': 1, 'kept_snr': -0.26, 'top_event_share': None, 'snr_without_top': None, 'kept_depth_ppt': -1.033, 'kept_depth_err_ppt': 3.977, 'depth_over_survey_depth': -5.157, 'p_const': 1.0, 'top_event_n': 413}
- Counterfactual kept-event depth SNR=-0.26; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'sap_baseline_ramp': 5}

Contributing tags: expected_SNR_below_pregate_scale, published_ephemeris_uncertainty_material, large_periodic_variability_proxy_may_include_transit_or_artifact.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/bd83733a161614/autopsy.png)

[Machine-readable diagnostic](diagnostics/bd83733a161614/diagnostic.json) · [Locked host outcome](results/locks/tic122673489.json)

## Kepler-504 b — search

TIC 164832454; published period 9.5492754 d; radius 1.59 Earth radii; duration 1.77 h.
Observed opportunities: 12; expected model SNR: 4.19; box-model expected SNR: 4.35; cadence MAD: 8.8 ppt.
Published timing-error scale at the end of observations / duration: 0.0396. TTV flag: 0.

Evidence and interpretation:

- Blind search accepted 8 signals on the host; none satisfies this planet’s exact period-and-event rule.
- 5 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': False, 'top_share_le_50pct': True, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 4, 'all_passed': False, 'n_kept': 12, 'kept_snr': 2.86, 'top_event_share': 0.27, 'snr_without_top': 2.25, 'kept_depth_ppt': 1.303, 'kept_depth_err_ppt': 0.455, 'depth_over_survey_depth': 0.668, 'p_const': 0.7015463166059444, 'top_event_n': 558}
- Counterfactual kept-event depth SNR=2.86; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'scattered_light_ramp': 2, 'scattered_light_flag': 3}

Contributing tags: expected_SNR_below_pregate_scale.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/01ba8d0e42e0a6/autopsy.png)

[Machine-readable diagnostic](diagnostics/01ba8d0e42e0a6/diagnostic.json) · [Locked host outcome](results/locks/tic164832454.json)

## TOI-1450 A b — C_signal_switch

TIC 377293776; published period 2.0439274 d; radius 1.13 Earth radii; duration 0.988 h.
Observed opportunities: 172; expected model SNR: 27.3; box-model expected SNR: 30.1; cadence MAD: 0.857 ppt.
Published timing-error scale at the end of observations / duration: 0.0256. TTV flag: 0.

Evidence and interpretation:

- First-termination record: Accepted ephemeris no longer matches this truth signal
- Blind A chose tls: tls ephemeris, 156 kept events, SNR 24.49, top share 0.03, SNR w/o top 24.16, depth 0.437 ppt = 1.097x survey, p_const 0.0053; all six criteria pass. Failed criteria: [].
- Blind secondary scan: CLEAN: no dip above 5 sigma at any other phase
- Blind B: 17 sector(s) could test the period phase-independently, none excludes it; 2 star-level flag(s): astrometric_excess_noise_sig 43.5 > 2.0; 9 neighbour(s) within 3 px bright enough to make the depth if totally eclipsed
- Blind C strongest P=2.04 d, SDE=28.6; maximum near the survey seed SDE=28.6; survey-region rank=1. strongest peak 2.04393 d is within 1% of the survey period at SDE 28.6
- Post-lock duration/identity audit: {'truth_id': 'TOI-1450 A b', 'key': 'tic377293776_P2.0439', 'tic_id': 377293776, 'native_C_decision': 'PASS', 'primary_termination': 'C_signal_switch', 'primary_C_match': {'ratio': 1, 'period_fraction': 2.2182765617717592e-06, 'matched': False, 'matched_events': 77, 'n_truth_opportunities': 172, 'n_found_opportunities': 77, 'truth_fraction': 0.4476744186046512, 'found_fraction': 1.0, 'mean_normalized_timing_residual': 0.1779177477853412}, 'same_C_period_and_epoch_duration_checks': {'reported_C': {'duration_seconds': 89.70925701158461, 'event_match': {'ratio': 1, 'period_fraction': 2.2182765617717592e-06, 'matched': False, 'matched_events': 77, 'n_truth_opportunities': 172, 'n_found_opportunities': 77, 'truth_fraction': 0.4476744186046512, 'found_fraction': 1.0, 'mean_normalized_timing_residual': 0.1779177477853412}, 'primary_credit': False}, 'accepted_A_duration': {'duration_seconds': 2882.4777282817017, 'event_match': {'ratio': 1, 'period_fraction': 2.2182765617717592e-06, 'matched': True, 'matched_events': 171, 'n_truth_opportunities': 172, 'n_found_opportunities': 171, 'truth_fraction': 0.9941860465116279, 'found_fraction': 1.0, 'mean_normalized_timing_residual': 0.10631294337234302}, 'primary_credit': False}, 'native_D_seed_duration': {'duration_seconds': 2882.4777282817017, 'event_match': {'ratio': 1, 'period_fraction': 2.2182765617717592e-06, 'matched': True, 'matched_events': 171, 'n_truth_opportunities': 172, 'n_found_opportunities': 171, 'truth_fraction': 0.9941860465116279, 'found_fraction': 1.0, 'mean_normalized_timing_residual': 0.10631294337234302}, 'primary_credit': False}, 'locked_D_fit_duration': {'duration_seconds': 3560.4, 'event_match': {'ratio': 1, 'period_fraction': 2.2182765617717592e-06, 'matched': True, 'matched_events': 172, 'n_truth_opportunities': 172, 'n_found_opportunities': 172, 'truth_fraction': 1.0, 'found_fraction': 1.0, 'mean_normalized_timing_residual': 0.09627078829890173}, 'primary_credit': False}, 'published_truth_duration': {'duration_seconds': 3556.7999999999997, 'event_match': {'ratio': 1, 'period_fraction': 2.2182765617717592e-06, 'matched': True, 'matched_events': 171, 'n_truth_opportunities': 172, 'n_found_opportunities': 171, 'truth_fraction': 0.9941860465116279, 'found_fraction': 1.0, 'mean_normalized_timing_residual': 0.09623517888067958}, 'primary_credit': False}}, 'existing_locked_D_fit_match': {'ratio': 1, 'period_fraction': 2.957933227243359e-07, 'matched': True, 'matched_events': 172, 'n_truth_opportunities': 172, 'n_found_opportunities': 172, 'truth_fraction': 1.0, 'found_fraction': 1.0, 'mean_normalized_timing_residual': 0.0017177119455125877}, 'outcome_locked_utc': '2026-09-08T09:46:08.789525+00:00', 'no_scientific_stage_rerun': True, 'no_primary_score_change': True}. Identical C period/epoch with alternate recorded durations is diagnostic only. Native D already uses the wider survey/C duration; no scientific stage or primary score is changed.
- Saved native spectrum minimum is -14.305825 at 107.9950531 d; that single bin contributes 0.118844% of total centered power variance across 172206 trials. TLS uses the global standard deviation in SDE normalization. No bin is removed, no alternative SDE is scored, and raw chi-square trial residuals were not saved to establish the upstream origin.
- 10 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': True, 'top_share_le_50pct': True, 'snr_without_top_ge_5': True, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': False}, 'n_criteria_passed': 5, 'all_passed': False, 'n_kept': 156, 'kept_snr': 24.45, 'top_event_share': 0.04, 'snr_without_top': 24.04, 'kept_depth_ppt': 0.393, 'kept_depth_err_ppt': 0.016, 'depth_over_survey_depth': 0.845, 'p_const': 0.0007194693837420549, 'top_event_n': 582}
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'momentum_dump': 8, 'scattered_light_ramp': 10, 'scattered_light_flag': 32, 'pdc_gap': 5, 'sap_baseline_ramp': 1, 'sector_orbit_edge': 3, 'quality_flagged': 3}

Contributing tags: C_accepted_ephemeris_fails_registered_identity_not_proof_of_physical_switch, C_reported_duration_changes_event_census_no_primary_credit.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/fc37e4cec2c714/autopsy.png)

[Machine-readable diagnostic](diagnostics/fc37e4cec2c714/diagnostic.json) · [Locked host outcome](results/locks/tic377293776.json)

## Kepler-262 c — search

TIC 122673489; published period 21.853722 d; radius 1.64 Earth radii; duration 3.49 h.
Observed opportunities: 3; expected model SNR: 0.148; box-model expected SNR: 0.121; cadence MAD: 33.1 ppt.
Published timing-error scale at the end of observations / duration: 0.329. TTV flag: 0.

Evidence and interpretation:

- Blind search accepted 8 signals on the host; none satisfies this planet’s exact period-and-event rule.
- Recorded native search notes, contributing context rather than a causal rescue: ['[chunk0] Planet 1 at P=26.9263 d does not carve a gate-6 exclusion zone: Rp/R* 0.269 > 0.2', '[chunk1] Planet 2 at P=9.5078 d does not carve a gate-6 exclusion zone: Rp/R* 0.346 > 0.2', '[stitch] Planet 2 at P=18.6522 d does not carve a gate-6 exclusion zone: Rp/R* 0.213 > 0.2', '[stitch] Planet 3 at P=14.8405 d does not carve a gate-6 exclusion zone: Rp/R* 0.348 > 0.2']
- 1 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': False, 'kept_snr_ge_7': False, 'top_share_le_50pct': False, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': False, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 1, 'all_passed': False, 'n_kept': 1, 'kept_snr': -2.78, 'top_event_share': None, 'snr_without_top': None, 'kept_depth_ppt': -12.911, 'kept_depth_err_ppt': 4.647, 'depth_over_survey_depth': -44.328, 'p_const': 1.0, 'top_event_n': 245}
- Counterfactual kept-event depth SNR=-2.78; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'sap_baseline_ramp': 2}

Contributing tags: expected_SNR_below_pregate_scale, large_periodic_variability_proxy_may_include_transit_or_artifact.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/c97c03785ccaeb/autopsy.png)

[Machine-readable diagnostic](diagnostics/c97c03785ccaeb/diagnostic.json) · [Locked host outcome](results/locks/tic122673489.json)

## Kepler-1076 b — search

TIC 399955825; published period 6.1472792 d; radius 0.8 Earth radii; duration 2.76 h.
Observed opportunities: 21; expected model SNR: 0.988; box-model expected SNR: 1.05; cadence MAD: 2.99 ppt.
Published timing-error scale at the end of observations / duration: 0.169. TTV flag: 0.

Evidence and interpretation:

- Blind search accepted 8 signals on the host; none satisfies this planet’s exact period-and-event rule.
- 1 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': False, 'top_share_le_50pct': True, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': False, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 3, 'all_passed': False, 'n_kept': 14, 'kept_snr': 2.04, 'top_event_share': 0.41, 'snr_without_top': 1.39, 'kept_depth_ppt': 0.231, 'kept_depth_err_ppt': 0.113, 'depth_over_survey_depth': 2.352, 'p_const': 0.42890892873187225, 'top_event_n': 907}
- Counterfactual kept-event depth SNR=2.04; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'sap_baseline_ramp': 10, 'scattered_light_flag': 5, 'momentum_dump': 1, 'scattered_light_ramp': 1}

Contributing tags: expected_SNR_below_pregate_scale.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/3823d9f7b2c1db/autopsy.png)

[Machine-readable diagnostic](diagnostics/3823d9f7b2c1db/diagnostic.json) · [Locked host outcome](results/locks/tic399955825.json)

## TOI-1470 c — C

TIC 284441182; published period 18.08816 d; radius 2.47 Earth radii; duration 2.7 h.
Observed opportunities: 3; expected model SNR: 13; box-model expected SNR: 13.1; cadence MAD: 2.21 ppt.
Published timing-error scale at the end of observations / duration: 0.0611. TTV flag: 0.

Evidence and interpretation:

- First-termination record: strongest peak 2.52711 d (SDE 32.1, alias 1:3 at 0.581); SDE within 1% of the survey period 16.8544129129266
- Blind A chose tls: tls ephemeris, 3 kept events, SNR 12.1, top share 0.48, SNR w/o top 8.9, depth 2.122 ppt = 1.249x survey, p_const 0.13; all six criteria pass. Failed criteria: [].
- Blind secondary scan: CLEAN: no dip above 5 sigma at any other phase
- Blind B: 1 sector(s) could test the period phase-independently, none excludes it; 4 star-level flag(s): astrometric_excess_noise_sig 8.7 > 2.0; Gaia phot_variable_flag VARIABLE (class -); 33 neighbour(s) within 3 px bright enough to make the depth if totally eclipsed; VSX entry within 1 arcmin ()
- Blind C strongest P=2.53 d, SDE=32.1; maximum near the survey seed SDE=16.9; survey-region rank=3. strongest peak 2.52711 d (SDE 32.1, alias 1:3 at 0.581); SDE within 1% of the survey period 16.8544129129266
- Saved native spectrum minimum is -8.6078335 at 49.05854414 d; that single bin contributes 0.048943% of total centered power variance across 151390 trials. TLS uses the global standard deviation in SDE normalization. No bin is removed, no alternative SDE is scored, and raw chi-square trial residuals were not saved to establish the upstream origin.
- 2 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': True, 'top_share_le_50pct': False, 'snr_without_top_ge_5': True, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 5, 'all_passed': False, 'n_kept': 3, 'kept_snr': 12.47, 'top_event_share': 0.51, 'snr_without_top': 8.97, 'kept_depth_ppt': 2.226, 'kept_depth_err_ppt': 0.178, 'depth_over_survey_depth': 0.962, 'p_const': 0.05120137746903234, 'top_event_n': 62}
- Truth-ephemeris event-removal classes, contributing diagnostics only: {}

Contributing tags: C_strongest_peak_period_disagreement.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/d7d670790b8323/autopsy.png)

[Machine-readable diagnostic](diagnostics/d7d670790b8323/diagnostic.json) · [Locked host outcome](results/locks/tic284441182.json)

## TOI-1470 b — retained

TIC 284441182; published period 2.527093 d; radius 2.18 Earth radii; duration 1.28 h.
Observed opportunities: 25; expected model SNR: 18.9; box-model expected SNR: 19.6; cadence MAD: 2.21 ppt.
Published timing-error scale at the end of observations / duration: 0.0566. TTV flag: 0.

Evidence and interpretation:

- Final review: Useful scientific HOLD for coherent repeated primary photometry with specific source and secondary-residual follow-up needed. All three native primary/secondary pixel sectors and the physical-fit packet were inspected. The sector-85 phase-0.5 image contains positive dimming near/below the target patch and is not dismissed. It is not reproduced as a comparable target secondary in sector 58; sector 78 has broad primary and secondary background offsets. The unchanged native full-phase secondary gate passes. The current evidence therefore does not establish a repeated stellar secondary or a unique eclipsing source. No clean auxiliary aperture measurement is available: all three sectors have zero background pixels after the unchanged Gaia mask. The native combined centroid is 0.00582 arcsec at 0.327 sigma with no individual flags, but an unresolved blend can escape that statistic. The density-prior fit gives 2.247 Earth radii, impact parameter 0.697 and duration 1.339 h with no native uncertainty issues. Native FPP is 0.07017 and NFPP 0.0003287 over sixty scenarios and 898 stars, with unresolved secondary-star planets accounting for most false-positive probability. Stage B caps the verdict at HOLD owing to astrometric excess-noise significance 8.7, Gaia variability, thirty-three capable neighbours and a VSX entry. No published planet label or ephemeris supplies a scientific pass, and the distinct failed 18-day candidate receives no benefit from this verdict.
- Blind A chose tls: tls ephemeris, 22 kept events, SNR 16.62, top share 0.13, SNR w/o top 15.59, depth 1.796 ppt = 1.056x survey, p_const 0.12; all six criteria pass. Failed criteria: [].
- Blind secondary scan: CLEAN: no dip above 5 sigma at any other phase
- Blind B: 3 sector(s) could test the period phase-independently, none excludes it; 4 star-level flag(s): astrometric_excess_noise_sig 8.7 > 2.0; Gaia phot_variable_flag VARIABLE (class -); 33 neighbour(s) within 3 px bright enough to make the depth if totally eclipsed; VSX entry within 1 arcmin ()
- Blind C strongest P=2.53 d, SDE=38.2; maximum near the survey seed SDE=38.2; survey-region rank=1. strongest peak 2.52711 d is within 1% of the survey period at SDE 38.2
- 15 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': True, 'top_share_le_50pct': True, 'snr_without_top_ge_5': True, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 6, 'all_passed': True, 'n_kept': 22, 'kept_snr': 17.69, 'top_event_share': 0.12, 'snr_without_top': 16.68, 'kept_depth_ppt': 1.713, 'kept_depth_err_ppt': 0.097, 'depth_over_survey_depth': 0.944, 'p_const': 0.28488450542052407, 'top_event_n': 663}
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'momentum_dump': 1, 'sector_orbit_edge': 1, 'sap_baseline_ramp': 1, 'scattered_light_ramp': 3, 'scattered_light_flag': 4, 'quality_flagged': 1, 'pdc_gap': 1}

Contributing tags: no additional cause assigned.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/fed7162261f6f6/autopsy.png)

[Machine-readable diagnostic](diagnostics/fed7162261f6f6/diagnostic.json) · [Locked host outcome](results/locks/tic284441182.json)

## Kepler-195 b — search

TIC 298837729; published period 8.307872 d; radius 2.03 Earth radii; duration 3.15 h.
Observed opportunities: 12; expected model SNR: 0.92; box-model expected SNR: 0.87; cadence MAD: 17 ppt.
Published timing-error scale at the end of observations / duration: 0.102. TTV flag: 1.

Evidence and interpretation:

- Blind search accepted 7 signals on the host; none satisfies this planet’s exact period-and-event rule.
- Recorded native search notes, contributing context rather than a causal rescue: ['[chunk0] Planet 1 at P=26.8534 d does not carve a gate-6 exclusion zone: Rp/R* 0.344 > 0.2', '[chunk1] Planet 2 at P=23.4434 d does not carve a gate-6 exclusion zone: Rp/R* 0.325 > 0.2', '[stitch] Planet 1 at P=29.2098 d does not carve a gate-6 exclusion zone: Rp/R* 0.224 > 0.2']
- 2 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': False, 'top_share_le_50pct': False, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': False, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 2, 'all_passed': False, 'n_kept': 10, 'kept_snr': 0.14, 'top_event_share': 0.58, 'snr_without_top': -0.45, 'kept_depth_ppt': 0.094, 'kept_depth_err_ppt': 0.689, 'depth_over_survey_depth': 0.163, 'p_const': 0.48872186769637294, 'top_event_n': 663}
- Counterfactual kept-event depth SNR=0.14; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'momentum_dump': 1, 'sector_orbit_edge': 1, 'sap_baseline_ramp': 2, 'scattered_light_flag': 3}

Contributing tags: expected_SNR_below_pregate_scale, catalogue_TTV_flag_causal_role_unresolved.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/a150bd96f39ec4/autopsy.png)

[Machine-readable diagnostic](diagnostics/a150bd96f39ec4/diagnostic.json) · [Locked host outcome](results/locks/tic298837729.json)

## Kepler-622 b — search

TIC 120254625; published period 14.282267 d; radius 2.13 Earth radii; duration 2.74 h.
Observed opportunities: 5; expected model SNR: 1.49; box-model expected SNR: 1.47; cadence MAD: 11 ppt.
Published timing-error scale at the end of observations / duration: 0.0911. TTV flag: 0.

Evidence and interpretation:

- Blind search accepted 4 signals on the host; none satisfies this planet’s exact period-and-event rule.
- 5 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': False, 'top_share_le_50pct': False, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 3, 'all_passed': False, 'n_kept': 5, 'kept_snr': 1.1, 'top_event_share': 1.0, 'snr_without_top': -0.73, 'kept_depth_ppt': 0.726, 'kept_depth_err_ppt': 0.661, 'depth_over_survey_depth': 0.708, 'p_const': 0.0284688183498193, 'top_event_n': 385}
- Counterfactual kept-event depth SNR=1.1; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {}

Contributing tags: expected_SNR_below_pregate_scale.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/4644d020c3827a/autopsy.png)

[Machine-readable diagnostic](diagnostics/4644d020c3827a/diagnostic.json) · [Locked host outcome](results/locks/tic120254625.json)

## Kepler-196 b — search

TIC 164828012; published period 20.739886 d; radius 1.9 Earth radii; duration 3.01 h.
Observed opportunities: 3; expected model SNR: 0.995; box-model expected SNR: 0.817; cadence MAD: 7.75 ppt.
Published timing-error scale at the end of observations / duration: 0.141. TTV flag: 0.

Evidence and interpretation:

- Blind search accepted 2 signals on the host; none satisfies this planet’s exact period-and-event rule.
- Recorded native search notes, contributing context rather than a causal rescue: ['[stitch] Planet 2 at P=27.9934 d does not carve a gate-6 exclusion zone: Rp/R* 0.289 > 0.2']
- 1 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': False, 'top_share_le_50pct': False, 'snr_without_top_ge_5': False, 'depth_within_0.5_2x_survey': False, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 2, 'all_passed': False, 'n_kept': 3, 'kept_snr': 2.07, 'top_event_share': 0.54, 'snr_without_top': 0.81, 'kept_depth_ppt': 1.284, 'kept_depth_err_ppt': 0.62, 'depth_over_survey_depth': 2.588, 'p_const': 0.07365657032388612, 'top_event_n': 266}
- Counterfactual kept-event depth SNR=2.07; this is selected/processed at published timing and is not blind search significance.
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'scattered_light_flag': 1}

Contributing tags: expected_SNR_below_pregate_scale.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/636d5b1ea57a07/autopsy.png)

[Machine-readable diagnostic](diagnostics/636d5b1ea57a07/diagnostic.json) · [Locked host outcome](results/locks/tic164828012.json)

## TOI-715 b — retained

TIC 271971130; published period 19.288004 d; radius 1.55 Earth radii; duration 1.98 h.
Observed opportunities: 26; expected model SNR: 15.7; box-model expected SNR: 19.5; cadence MAD: 7 ppt.
Published timing-error scale at the end of observations / duration: 0.0357. TTV flag: 0.

Evidence and interpretation:

- Final review: Useful scientific HOLD based on repeated coherent transit-like photometry and recurring target-vicinity primary dimming, with unresolved source and background limitations. All nineteen available primary/secondary difference panels, the physical-fit packet and the only available auxiliary aperture curve were inspected. Several sectors are dominated by broad background changes, including primary sectors 65, 67, 68, 87, 89 and 98 and multiple phase-0.5 panels; these are not assigned to a stellar secondary. The small target patch does not resolve the overlapping Gaia components. The nineteen-sector inverse-variance centroid is only 0.00571 arcsec at 0.409 sigma, but individual sectors 68, 88, 89, 93 and 97 are flagged; cancellation across sectors cannot certify the source. The independent native sky-subtracted aperture is available only in sector 68, with primary 1.62 +/- 1.81 ppt and secondary 1.17 +/- 1.41 ppt and strong broad phase-dependent background structures. The other eighteen sectors fail the unchanged sixteen-clean-sky-pixel requirement. This auxiliary series supplies neither a significant confirmation nor a refutation of the fitted transit. The density-prior physical fit gives 1.709 Earth radii, impact parameter 0.499 and duration 2.026 h, with no native uncertainty issues. Native FPP is 0.05132 and NFPP 0.003623 over thirty scenarios and 164 stars; unresolved secondary-star planets and nearby-star scenarios retain probability. Only two of nineteen sectors span enough periods for the original phase-independent B test. These limitations prevent submission-equivalent eligibility. No published planet label or ephemeris supplies a scientific pass.
- Blind A chose tls: tls ephemeris, 25 kept events, SNR 19.7, top share 0.19, SNR w/o top 18.08, depth 4.759 ppt = 1.189x survey, p_const 0.0015; all six criteria pass. Failed criteria: [].
- Blind secondary scan: CLEAN: no dip above 5 sigma at any other phase
- Blind B: 2 sector(s) could test the period phase-independently, none excludes it; 1 star-level flag(s): 11 neighbour(s) within 3 px bright enough to make the depth if totally eclipsed
- Blind C strongest P=19.3 d, SDE=88.6; maximum near the survey seed SDE=88.6; survey-region rank=1. strongest peak 19.28808 d is within 1% of the survey period at SDE 88.6
- 13 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': True, 'top_share_le_50pct': True, 'snr_without_top_ge_5': True, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 6, 'all_passed': True, 'n_kept': 25, 'kept_snr': 19.65, 'top_event_share': 0.17, 'snr_without_top': 18.2, 'kept_depth_ppt': 4.401, 'kept_depth_err_ppt': 0.224, 'depth_over_survey_depth': 0.982, 'p_const': 0.0015155183519623239, 'top_event_n': 98}
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'pdc_gap': 1, 'scattered_light_flag': 4, 'momentum_dump': 1, 'sap_baseline_ramp': 1, 'scattered_light_ramp': 2}

Contributing tags: no additional cause assigned.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/44124069314390/autopsy.png)

[Machine-readable diagnostic](diagnostics/44124069314390/diagnostic.json) · [Locked host outcome](results/locks/tic271971130.json)

## TOI-122 b — retained

TIC 231702397; published period 5.07803 d; radius 2.72 Earth radii; duration 1.21 h.
Observed opportunities: 30; expected model SNR: 23.6; box-model expected SNR: 27.1; cadence MAD: 5.18 ppt.
Published timing-error scale at the end of observations / duration: 0.165. TTV flag: 0.

Evidence and interpretation:

- Final review: Useful scientific HOLD: repeated transit evidence and a constrained fit survive the automated funnel; the saved measurements do not demonstrate a nonplanetary cause. Five possible contaminating neighbours impose the original Stage B HOLD cap. The native FPP is 0.04944 and NFPP 0.000127 under circular-aperture assumptions, with probability on a planet orbiting a secondary star contributing substantially to FPP; this supports further source work rather than establishing planet eligibility. The combined centroid is 0.00203 pixel (0.043 arcsec), 2.35 sigma, while sector 67 alone is 6.08 sigma. A 3.1-sigma odd/even difference deserves follow-up. Raw phase-0.5 box depths have inconsistent signs across sectors; background excursions and local baselines make those unfiltered statistics insufficient evidence for a repeatable localized secondary. The difference-image maxima are not fitted source positions. No published label or ephemeris was used to supply a scientific pass in this explicitly unblinded review.
- Blind A chose tls: tls ephemeris, 25 kept events, SNR 24.58, top share 0.1, SNR w/o top 23.24, depth 5.658 ppt = 1.083x survey, p_const 0.018; all six criteria pass. Failed criteria: [].
- Blind secondary scan: CLEAN: no dip above 5 sigma at any other phase
- Blind B: 7 sector(s) could test the period phase-independently, none excludes it; 1 star-level flag(s): 5 neighbour(s) within 3 px bright enough to make the depth if totally eclipsed
- Blind C strongest P=5.08 d, SDE=76; maximum near the survey seed SDE=76; survey-region rank=1. strongest peak 5.07807 d is within 1% of the survey period at SDE 76.0
- 22 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': True, 'top_share_le_50pct': True, 'snr_without_top_ge_5': True, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 6, 'all_passed': True, 'n_kept': 25, 'kept_snr': 23.75, 'top_event_share': 0.13, 'snr_without_top': 22.3, 'kept_depth_ppt': 5.068, 'kept_depth_err_ppt': 0.213, 'depth_over_survey_depth': 0.905, 'p_const': 0.02043608679587849, 'top_event_n': 344}
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'momentum_dump': 3, 'sector_orbit_edge': 1, 'scattered_light_ramp': 4, 'scattered_light_flag': 5, 'quality_flagged': 3, 'pdc_gap': 1}

Contributing tags: no additional cause assigned.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/c2bef1bf20e75f/autopsy.png)

[Machine-readable diagnostic](diagnostics/c2bef1bf20e75f/diagnostic.json) · [Locked host outcome](results/locks/tic231702397.json)

## TOI-2120 b — retained

TIC 389900760; published period 5.7998164 d; radius 2.12 Earth radii; duration 1.01 h.
Observed opportunities: 11; expected model SNR: 14.3; box-model expected SNR: 18.5; cadence MAD: 6.59 ppt.
Published timing-error scale at the end of observations / duration: 0.0284. TTV flag: 0.

Evidence and interpretation:

- Final review: Useful scientific HOLD: a coherent photometric fit and repeatable target-vicinity dimming provide a specific basis for source follow-up, with no demonstrated nonplanetary cause. B flags astrometric excess-noise significance 2.9, possible contaminating neighbours and a VSX entry. Native FPP is 0.0886 and NFPP about 9.3e-8, with most non-target-planet probability on an unresolved secondary-star planet model; these priors cannot resolve the crowded patch. The accepted density-prior fit has impact parameter 0.848. The combined centroid displacement is 0.094 arcsec at 3.68 sigma. Sector 85 reports zero displacement and zero uncertainty and was excluded from that native weighted combination; it is not a precise no-motion constraint. Its available pixels were separately included in the four-sector difference review before locking. The auxiliary sky-annulus extraction is unavailable and its requirement was not relaxed. The published label is not used as evidence for the verdict.
- Blind A chose tls: tls ephemeris, 10 kept events, SNR 11.32, top share 0.17, SNR w/o top 10.36, depth 6.059 ppt = 1.02x survey, p_const 0.7; all six criteria pass. Failed criteria: [].
- Blind secondary scan: CLEAN: no dip above 5 sigma at any other phase
- Blind B: 4 sector(s) could test the period phase-independently, none excludes it; 3 star-level flag(s): astrometric_excess_noise_sig 2.9 > 2.0; 28 neighbour(s) within 3 px bright enough to make the depth if totally eclipsed; VSX entry within 1 arcmin ()
- Blind C strongest P=5.8 d, SDE=33.4; maximum near the survey seed SDE=33.4; survey-region rank=1. strongest peak 5.79977 d is within 1% of the survey period at SDE 33.4
- 11 BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.
- Truth-ephemeris counterfactual A criteria (excluded from primary counts): {'criteria': {'kept_events_ge_3': True, 'kept_snr_ge_7': True, 'top_share_le_50pct': True, 'snr_without_top_ge_5': True, 'depth_within_0.5_2x_survey': True, 'depths_consistent_p_ge_1e-3': True}, 'n_criteria_passed': 6, 'all_passed': True, 'n_kept': 10, 'kept_snr': 10.03, 'top_event_share': 0.16, 'snr_without_top': 9.22, 'kept_depth_ppt': 4.797, 'kept_depth_err_ppt': 0.478, 'depth_over_survey_depth': 0.56, 'p_const': 0.6576406252864064, 'top_event_n': 319}
- Truth-ephemeris event-removal classes, contributing diagnostics only: {'scattered_light_ramp': 5, 'scattered_light_flag': 5, 'momentum_dump': 1}

Contributing tags: no additional cause assigned.

TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.

![Truth-informed diagnostic](diagnostics/ac06e9278b16b4/autopsy.png)

[Machine-readable diagnostic](diagnostics/ac06e9278b16b4/diagnostic.json) · [Locked host outcome](results/locks/tic389900760.json)
