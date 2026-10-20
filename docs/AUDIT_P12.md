# AUDIT_P12. Final state: FINAL_SEARCH_DELIVERED_BAR_NOT_MET
Launch bar not met: clause LB1a (NOT MEASURED: 0 of 1).
The candidates below were produced under rules whose pre-registered launch bar was not met (clause LB1a: 0 of 1); submission is not recommended until a decisive, unexposed measurement of that clause exists.

> **Added by the session at final delivery (2026-10-01), not by the frozen generator:** every post-freeze operation, the three STOP decisions (STOP-4 CONTINUE, STOP-7 on LB3 CONTINUE, STOP-7 on final Stage B REPAIR), the 54 repaired Stage B cases, the frozen-code defects worked around without changing frozen bytes, and the finalization at decision point 3 are in `p12/results/POST_FREEZE_INCIDENTS_P12.md` (machine record `p12/manifests/post_freeze_operations.jsonl`).


Generated 2026-10-01T15:03:16.571479+00:00 by `p12/protocol/report_audit_p12.py`. Every number is [M] unless marked.

## 1. The launch bar

| clause | number | N | Wilson 95% | decisive | outcome |
|---|---:|---:|---|---|---|
| LB1a | 0 | 1 | 0.0-79.3% | False | NOT MEASURED |
| LB1b | 0 | 1 | 0.0-79.3% | False | NOT MEASURED |
| LB2a | 0 | 13 | 0.0-22.8% | True | HOLDS |
| LB2b | 0 | 1 | 0.0-79.3% | False | NOT MEASURED |
| LB3 | 0 | 0 | n/a | False | NOT MEASURED |
| LB4 | 0.957 | 558 | 93.7-97.1% | True | HOLDS |

bar_met = False. What N can detect: the Wilson 95% upper bound is 11.4% on 0 of 30, 16.7% on 1 of 30, 22.8% on 0 of 13, 43.4% on 0 of 5; the bar detects a gross specificity failure (one binary in ten passing) and cannot detect a 3% false-SUBMIT rate.
LB1c (reported, never bar material): {"LB1c_end_to_end": "NOT MEASURED", "LB1c_at_D": "NOT MEASURED"}.

## 2. The candidate list

### Tier 2: pixel-supported candidates

| TIC | P (d) | epoch (BTJD) | depth (ppt) | duration (h) | tier | deciding | F7 | F5 | score_v2 | packet |
|---|---:|---:|---:|---:|---|---|---|---|---:|---|
| 404927114 | 27.54363 | 2987.9321 | 4.856 | 1.34 | 2 | - | {"status": "CLEAN", "tic_matches": [], "neighbour_matches":  | {"localisation": "not_measurable", "n_se | 1.4486 | docs/packets/audit_p12/tic404927114_p03/tic404927114_P27.5436 |
| 332366289 | 18.74808 | 2869.8701 | 5.781 | 2.23 | 2 | - | {"status": "CLEAN", "tic_matches": [], "neighbour_matches":  | {"localisation": "unlocalised", "n_secto | - | docs/packets/audit_p12/tic332366289_p02/tic332366289_P18.7481 |

### Tier 1: CTOI-grade candidates

None.

## 3. HOLD (not for submission)

- TIC 160618340 P 1.2915077491327633 d: HOLD (H5); fired H5
- TIC 224601129 P 1.041766669986296 d: HOLD (H2); fired H2
- TIC 229764903 P 0.7998924986380511 d: HOLD (H1); fired H1|H2
- TIC 230120862 P 16.795891647111418 d: HOLD (H1); fired H1|H2
- TIC 383988275 P 13.860884611328597 d: HOLD (H1); fired H1
- TIC 411629716 P 1.218430606587379 d: HOLD (H2); fired H2
- TIC 458481937 P 1.242314147921443 d: HOLD (H2); fired H2
- TIC 459189437 P 0.9292986137681597 d: HOLD (H3); fired H3

UNRESOLVED at C (delivered with D): 0; UNKNOWN: 22.

## 4. Per candidate

### TIC 332366289 (tic332366289_P18.7481)

TESS FFI photometry, sectors 56 to 105 under the frozen policy, `survey_p10` preset and rules p12.0: P = 18.74808 d, T0 = BTJD 2869.8701, depth 5.781 ppt, duration 2.23 h. Tier 2 (pixel-supported); not claimed: a validated planet, a resolved source, a low false-positive probability.

F1: [{"source_id": 1415338306971353600, "sep_arcsec": 25.7, "sep_px": 1.22, "G": 20.401439666748047, "delta_mag": 5.41, "max_depth_ppt_total_eclipse": 6.82, "required_eclipse_fraction": 0.8476}, {"source_id": 1415338337035983488, "sep_arcsec": 33.6, "sep_px": 1.6, "G": 19.719402313232422, "delta_mag": 5.1, "max_depth_ppt_total_eclipse": 9.04, "required_eclipse_fraction": 0.6394}, {"source_id": 1415338337035990528, "sep_arcsec": 39.2, "sep_px": 1.87, "G": 18.963878631591797, "delta_mag": 4.4, "max_depth_ppt_total_eclipse": 17.15, "required_eclipse_fraction": 0.3371}, {"source_id": 1415338405755460480, "sep_arcsec": 47.8, "sep_px": 2.28, "G": 18.515827178955078, "delta_mag": 4.11, "max_depth_ppt_total_eclipse": 22.13, "required_eclipse_fraction": 0.2612}] F2: {"ruwe": 1.0966936349868774, "ipd_frac_multi_peak": 0.0, "astrometric_excess_noise_sig": 2.165614604949951, "non_single_star": 0.0, "phot_variable_flag": "NOT_AVAILABLE", "best_class_name": "", "duplicated_source": 0.0} F3: {"vsx": [], "simbad": [{"main_id": "Gaia DR3 1415338513130475136", "otype": "PM*", "sp_type": "", "sep_arcsec": 0.0}]} F4: {"fpp": 0.048611849678553254, "nfpp": 0.0, "available": true, "fpp_uniform": false, "sectors": [57, 77, 78], "caveats": "binned fold; circular aperture from Tmag; first three selected sectors; probabilities are conditional on TRICERATOPS's astrophysical scenarios and do not price instrumental artefacts"} F5: {"localisation": "unlocalised", "n_sectors_measurable": 4, "per_sector": [{"sector": 57, "net_depth_ppt": 5.5572, "net_err_ppt": 2.0701, "k7_absent": null, "note": "unmeasurable: 0.5 x D_ref 3.300 < 3 sigma_s 6.210 ppt", "k7_elsewhere": null, "difference_max_dist_target_px": 0.975, "centroid_sigma": 0.45077140808824556, "centroid_shift_px": 0.0018317219282664755}, {"sector": 77, "centroid_sigma": 0.0, "centroid_shift_px": 0.0}, {"sector": 78, "centroid_sigma": 0.0, "centroid_shift_px": 0.0}, {"sector": 79, "net_depth_ppt": -0.5763, "net_err_ppt": 1.4079, "k7_absent": null, "note": "unmeasurable: 0.5 x D_ref 3.300 < 3 sigma_s 4.224 ppt", "k7_elsewhere": null, "difference_max_dist_target_px": 2.926, "centroid_sigma": 1.4305152898413886, "centroid_shift_px": 0.012776668338338446}, {"sector": 80, "net_depth_ppt": 3.772, "net_err_ppt": 1.9222, "k7_absent": null, "note": "unmeasurable: 0.5 x D_ref 3.300 < 3 sigma_s 5.767 ppt", "k7_elsewhere": null, "difference_max_dist_target_px": 0.326, "centroid_sigma": 0.823571766361594, "centroid_shift_px": 0.002464377268444345}, {"sector": 84, "net_depth_ppt": 3.6212, "net_err_ppt": 1.9326, "k7_absent": null, "note": "unmeasurable: 0.5 x D_ref 3.300 < 3 sigma_s 5.798 ppt", "k7_elsewhere": null, "difference_max_dist_target_px": 0.52, "centroid_sigma": 5.433321023072705, "centroid_shift_px": 0.013162710976557902}]} F6: [{"period_days": "27.328428819835562", "depth_ppt": "5.196797474857549", "snr": "7.3656546159827965", "verdict": "ambiguous / manual vetting required", "stitch_snr": "7.099485621543694", "passes_pregate": "False"}, {"period_days": "14.571888156379137", "depth_ppt": "3.051960217171476", "snr": "7.293273191245426", "verdict": "promising planet candidate", "stitch_snr": "7.293273191245426", "passes_pregate": "True"}, {"period_days": "25.06989216440334", "depth_ppt": "4.422936730344997", "snr": "6.988720264677921", "verdict": "promising planet candidate", "stitch_snr": "6.824976743445252", "passes_pregate": "False"}, {"period_days": "17.842978675404183", "depth_ppt": "7.886194436384107", "snr": "6.689832576944206", "verdict": "promising planet candidate", "stitch_snr": "6.060898365497981", "passes_pregate": "False"}, {"period_days": "17.323271538812786", "depth_ppt": "7.33443374873535", "snr": "6.6698630077888295", "verdict": "promising planet candidate", "stitch_snr": "6.6698630077888295", "passes_pregate": "False"}, {"period_days": "14.977421422775759", "depth_ppt": "4.13120667645563", "snr": "6.5710945514629655", "verdict": "promising planet candidate", "stitch_snr": "6.891555425847294", "passes_pregate": "False"}, {"period_days": "15.896454650054096", "depth_ppt": "3.17069976394936", "snr": "6.553891677930608", "verdict": "ambiguous / manual vetting required", "stitch_snr": "6.553891677930608", "passes_pregate": "False"}, {"period_days": "11.5597138951567", "depth_ppt": "9.44281847520921", "snr": "6.044107162072626", "verdict": "ambiguous / manual vetting required", "stitch_snr": "5.247100856135591", "passes_pregate": "False"}, {"period_days": "10.182778775504316", "depth_ppt": "2.8236859267238943", "snr": "6.038382474416409", "verdict": "promising planet candidate", "stitch_snr": "5.3565909072797115", "passes_pregate": "False"}, {"period_days": "21.00422705110314", "depth_ppt": "2.9924288480330103", "snr": "5.831416227167561", "verdict": "promising planet candidate", "stitch_snr": "5.831416227167561", "passes_pregate": "False"}, {"period_days": "3.631206601234564", "depth_ppt": "4.348315013354783", "snr": "5.602044417466723", "verdict": "promising planet candidate", "stitch_snr": "5.171841239807996", "passes_pregate": "False"}, {"period_days": "5.656018522396237", "depth_ppt": "4.522271029475934", "snr": "5.462345407949487", "verdict": "promising planet candidate", "stitch_snr": "5.38511642253951", "passes_pregate": "False"}, {"period_days": "3.6846517588801433", "depth_ppt": "2.145550014674957", "snr": "5.119777380419905", "verdict": "promising planet candidate", "stitch_snr": "5.187527226219193", "passes_pregate": "False"}] F7: {"status": "CLEAN", "tic_matches": [], "neighbour_matches": [], "tce_association": null} F8: {"n_observed": 4, "n_excluded": 1, "n_kept": 3, "removed_by_class": {"dip_absent_in_sap": 0, "pdc_gap": 1, "scattered_light_ramp": 0, "scattered_light_flag": 1, "momentum_dump": 0, "sector_orbit_edge": 0, "quality_flagged": 0, "sap_baseline_ramp": 0}, "strongest_event_removed": false} F9: "4 Gaia neighbour(s) within 63 arcsec could produce the depth by total eclipse (nearest 25.7 arcsec, G 20.401439666748047, needing an eclipse of 85% of its light). Seeing-limited ground photometry at the predicted epochs, resolving each of them, would settle the source. TESS fixed-aperture photometry is consistent with the target in 4 sector(s) but cannot separate the target from the listed neighbours. TRICERATOPS FPP 0.0486, NFPP 0 on the binned fold; a low value does not price instrumental artefacts. Statistical validation additionally needs a resolved source, repeated localised dimming and a low FPP with the scene fixed; this candidate is submitted as a candidate, not as a validated planet." F10: {"word": "K10_FLAG", "or_variants": ["K10e", "K10s"], "or_fired": false, "K10e": {"fired": false, "measurable": true, "detail": "n_excluded / n_observed = 1/4 = 0.250 (> 0.5 fires)", "n_observed": 4, "n_excluded": 1, "fraction": 0.25}, "K10s": {"fired": false, "measurable": true, "detail": "SAP 3.755 +/- 0.838 ppt vs corrected 6.500 +/- 0.859 ppt; SAP < 0.5x False; difference > 3 sigma False; kept events in 3 sector(s)", "det_ppt": 6.5, "det_err_ppt": 0.859, "sap_ppt": 3.755, "sap_err_ppt": 0.838, "quadrature_err_ppt": 1.2000520822031018, "kept_sectors": [57, 79, 80], "sap_below_half": false, "difference_significant": false, "kept_sectors_ge_2": true}, "deciding": false}

The field's validation bar (resolved source, localised repeated dimming, low FPP) is out of reach for TESS FFI photometry alone at Tmag 13.5; this is a candidate for follow-up, not a validated planet.

Next transits: BTJD 4332.218 +/- 0.37 h; BTJD 4350.966 +/- 0.37 h; BTJD 4369.714 +/- 0.38 h.

### TIC 404927114 (tic404927114_P27.5436)

TESS FFI photometry, sectors 56 to 105 under the frozen policy, `survey_p10` preset and rules p12.0: P = 27.54363 d, T0 = BTJD 2987.9321, depth 4.856 ppt, duration 1.34 h. Tier 2 (pixel-supported); not claimed: a validated planet, a resolved source, a low false-positive probability.

F1: [{"source_id": 4659942076276901120, "sep_arcsec": 13.3, "sep_px": 0.63, "G": 17.829437255859375, "delta_mag": 4.54, "max_depth_ppt_total_eclipse": 15.02, "required_eclipse_fraction": 0.3233}, {"source_id": 4659942071944202624, "sep_arcsec": 18.3, "sep_px": 0.87, "G": 18.94882583618164, "delta_mag": 5.03, "max_depth_ppt_total_eclipse": 9.59, "required_eclipse_fraction": 0.5064}, {"source_id": 4659930325207234688, "sep_arcsec": 19.3, "sep_px": 0.92, "G": 18.802364349365234, "delta_mag": 4.86, "max_depth_ppt_total_eclipse": 11.22, "required_eclipse_fraction": 0.4328}, {"source_id": 4659930359605646720, "sep_arcsec": 21.4, "sep_px": 1.02, "G": 18.81393051147461, "delta_mag": 4.71, "max_depth_ppt_total_eclipse": 12.93, "required_eclipse_fraction": 0.3756}, {"source_id": 4659930359605646848, "sep_arcsec": 21.9, "sep_px": 1.04, "G": 18.09006118774414, "delta_mag": 4.01, "max_depth_ppt_total_eclipse": 24.21, "required_eclipse_fraction": 0.2006}, {"source_id": 4659930320913669376, "sep_arcsec": 23.2, "sep_px": 1.1, "G": 17.99725914001465, "delta_mag": 3.83, "max_depth_ppt_total_eclipse": 28.46, "required_eclipse_fraction": 0.1706}, {"source_id": 4659930355273426688, "sep_arcsec": 23.6, "sep_px": 1.12, "G": 19.65599822998047, "delta_mag": 5.5, "max_depth_ppt_total_eclipse": 6.25, "required_eclipse_fraction": 0.777}, {"source_id": 4659942076276900992, "sep_arcsec": 25.3, "sep_px": 1.2, "G": 17.939647674560547, "delta_mag": 3.9, "max_depth_ppt_total_eclipse": 26.87, "required_eclipse_fraction": 0.1807}, {"source_id": 4659930325245902336, "sep_arcsec": 29.9, "sep_px": 1.43, "G": 18.675615310668945, "delta_mag": 4.77, "max_depth_ppt_total_eclipse": 12.17, "required_eclipse_fraction": 0.399}, {"source_id": 4659931832742188160, "sep_arcsec": 30.7, "sep_px": 1.46, "G": 18.372560501098633, "delta_mag": 4.34, "max_depth_ppt_total_eclipse": 18.08, "required_eclipse_fraction": 0.2686}, {"source_id": 4659930325207235328, "sep_arcsec": 32.1, "sep_px": 1.53, "G": 19.333314895629883, "delta_mag": 5.38, "max_depth_ppt_total_eclipse": 7.02, "required_eclipse_fraction": 0.6918}, {"source_id": 4659930359566974208, "sep_arcsec": 35.3, "sep_px": 1.68, "G": 19.19379425048828, "delta_mag": 5.21, "max_depth_ppt_total_eclipse": 8.17, "required_eclipse_fraction": 0.5944}, {"source_id": 4659942071944190464, "sep_arcsec": 37.7, "sep_px": 1.8, "G": 18.822328567504883, "delta_mag": 4.92, "max_depth_ppt_total_eclipse": 10.63, "required_eclipse_fraction": 0.4568}, {"source_id": 4659930325248888960, "sep_arcsec": 38.2, "sep_px": 1.82, "G": 18.28021240234375, "delta_mag": 3.86, "max_depth_ppt_total_eclipse": 27.72, "required_eclipse_fraction": 0.1752}, {"source_id": 4659930320913657216, "sep_arcsec": 38.8, "sep_px": 1.85, "G": 19.44049835205078, "delta_mag": 5.53, "max_depth_ppt_total_eclipse": 6.12, "required_eclipse_fraction": 0.7935}, {"source_id": 4659942076276896256, "sep_arcsec": 39.0, "sep_px": 1.86, "G": 19.518598556518555, "delta_mag": 5.76, "max_depth_ppt_total_eclipse": 4.94, "required_eclipse_fraction": 0.983}, {"source_id": 4659931837077381376, "sep_arcsec": 39.8, "sep_px": 1.89, "G": 13.671984672546387, "delta_mag": -0.16, "max_depth_ppt_total_eclipse": 537.23, "required_eclipse_fraction": 0.009}, {"source_id": 4659942106310531200, "sep_arcsec": 39.8, "sep_px": 1.9, "G": 19.008712768554688, "delta_mag": 5.73, "max_depth_ppt_total_eclipse": 5.08, "required_eclipse_fraction": 0.956}, {"source_id": 4659942071944180992, "sep_arcsec": 40.5, "sep_px": 1.93, "G": 18.818531036376953, "delta_mag": 4.86, "max_depth_ppt_total_eclipse": 11.2, "required_eclipse_fraction": 0.4336}, {"source_id": 4659942110640513152, "sep_arcsec": 40.5, "sep_px": 1.93, "G": 18.67377471923828, "delta_mag": 4.73, "max_depth_ppt_total_eclipse": 12.7, "required_eclipse_fraction": 0.3824}, {"source_id": 4659931837074401536, "sep_arcsec": 40.7, "sep_px": 1.94, "G": 17.4261417388916, "delta_mag": 3.12, "max_depth_ppt_total_eclipse": 53.3, "required_eclipse_fraction": 0.0911}, {"source_id": 4659942106303967488, "sep_arcsec": 48.1, "sep_px": 2.29, "G": 19.163381576538086, "delta_mag": 5.15, "max_depth_ppt_total_eclipse": 8.61, "required_eclipse_fraction": 0.564}, {"source_id": 4659941973161065856, "sep_arcsec": 49.0, "sep_px": 2.33, "G": 18.77546501159668, "delta_mag": 4.76, "max_depth_ppt_total_eclipse": 12.34, "required_eclipse_fraction": 0.3935}, {"source_id": 4659930359566974720, "sep_arcsec": 49.6, "sep_px": 2.36, "G": 18.63530158996582, "delta_mag": 4.57, "max_depth_ppt_total_eclipse": 14.58, "required_eclipse_fraction": 0.3331}, {"source_id": 4659930359608627456, "sep_arcsec": 50.3, "sep_px": 2.39, "G": 15.871766090393066, "delta_mag": 1.67, "max_depth_ppt_total_eclipse": 177.11, "required_eclipse_fraction": 0.0274}, {"source_id": 4659942071944202752, "sep_arcsec": 53.1, "sep_px": 2.53, "G": 18.250530242919922, "delta_mag": 4.13, "max_depth_ppt_total_eclipse": 21.71, "required_eclipse_fraction": 0.2237}, {"source_id": 4659942071944192128, "sep_arcsec": 54.5, "sep_px": 2.6, "G": 19.566953659057617, "delta_mag": 5.36, "max_depth_ppt_total_eclipse": 7.1, "required_eclipse_fraction": 0.684}, {"source_id": 4659941973161052928, "sep_arcsec": 55.1, "sep_px": 2.62, "G": 18.480207443237305, "delta_mag": 4.53, "max_depth_ppt_total_eclipse": 15.22, "required_eclipse_fraction": 0.3191}, {"source_id": 4659941973161065984, "sep_arcsec": 55.4, "sep_px": 2.64, "G": 20.099990844726562, "delta_mag": 5.66, "max_depth_ppt_total_eclipse": 5.43, "required_eclipse_fraction": 0.8943}, {"source_id": 4659942076276900864, "sep_arcsec": 55.4, "sep_px": 2.64, "G": 17.437713623046875, "delta_mag": 3.31, "max_depth_ppt_total_eclipse": 45.11, "required_eclipse_fraction": 0.1077}, {"source_id": 4659941968864954752, "sep_arcsec": 55.9, "sep_px": 2.66, "G": 18.729087829589844, "delta_mag": 4.57, "max_depth_ppt_total_eclipse": 14.58, "required_eclipse_fraction": 0.3331}, {"source_id": 4659941973161052032, "sep_arcsec": 56.4, "sep_px": 2.68, "G": 17.91876983642578, "delta_mag": 3.7, "max_depth_ppt_total_eclipse": 32.14, "required_eclipse_fraction": 0.1511}, {"source_id": 4659931764022692096, "sep_arcsec": 56.4, "sep_px": 2.69, "G": 18.843751907348633, "delta_mag": 4.46, "max_depth_ppt_total_eclipse": 16.23, "required_eclipse_fraction": 0.2992}, {"source_id": 4659931832742201856, "sep_arcsec": 56.6, "sep_px": 2.69, "G": 19.590490341186523, "delta_mag": 4.98, "max_depth_ppt_total_eclipse": 10.12, "required_eclipse_fraction": 0.4799}, {"source_id": 4659930325207236224, "sep_arcsec": 56.6, "sep_px": 2.7, "G": 17.781810760498047, "delta_mag": 3.74, "max_depth_ppt_total_eclipse": 30.92, "required_eclipse_fraction": 0.1571}, {"source_id": 4659942071944209152, "sep_arcsec": 57.0, "sep_px": 2.72, "G": 18.80311393737793, "delta_mag": 4.82, "max_depth_ppt_total_eclipse": 11.7, "required_eclipse_fraction": 0.4151}, {"source_id": 4659941968871534720, "sep_arcsec": 57.3, "sep_px": 2.73, "G": 18.69400405883789, "delta_mag": 4.76, "max_depth_ppt_total_eclipse": 12.32, "required_eclipse_fraction": 0.3942}, {"source_id": 4659941968864954624, "sep_arcsec": 57.9, "sep_px": 2.76, "G": 18.877365112304688, "delta_mag": 4.83, "max_depth_ppt_total_eclipse": 11.6, "required_eclipse_fraction": 0.4186}, {"source_id": 4659931768316274304, "sep_arcsec": 58.3, "sep_px": 2.77, "G": 18.666431427001953, "delta_mag": 4.39, "max_depth_ppt_total_eclipse": 17.21, "required_eclipse_fraction": 0.2822}, {"source_id": 4659942110636643456, "sep_arcsec": 59.3, "sep_px": 2.82, "G": 16.451807022094727, "delta_mag": 2.51, "max_depth_ppt_total_eclipse": 89.94, "required_eclipse_fraction": 0.054}, {"source_id": 4659930355273395328, "sep_arcsec": 59.3, "sep_px": 2.82, "G": 17.29730224609375, "delta_mag": 3.21, "max_depth_ppt_total_eclipse": 49.56, "required_eclipse_fraction": 0.098}, {"source_id": 4659943588105397632, "sep_arcsec": 59.7, "sep_px": 2.84, "G": 18.251480102539062, "delta_mag": 4.26, "max_depth_ppt_total_eclipse": 19.44, "required_eclipse_fraction": 0.2498}] F2: {"ruwe": 1.1008936166763306, "ipd_frac_multi_peak": 0.0, "astrometric_excess_noise_sig": 0.0, "non_single_star": 0.0, "phot_variable_flag": "VARIABLE", "best_class_name": "SOLAR_LIKE", "duplicated_source": 0.0} F3: {"vsx": [{"Name": "Gaia DR3 4659930359605646592", "Type": "ROT", "Period": null, "sep_arcsec": 0.0}], "simbad": [{"main_id": "UCAC4 120-008270", "otype": "PM*", "sp_type": "", "sep_arcsec": 0.0}, {"main_id": "OGLE LMC-ECL-36904", "otype": "EB*", "sp_type": "", "sep_arcsec": 45.6}]} F4: {"fpp": 0.16801432734496247, "nfpp": 0.14464678775768125, "available": true, "fpp_uniform": false, "sectors": [61, 63, 66], "caveats": "binned fold; circular aperture from Tmag; first three selected sectors; probabilities are conditional on TRICERATOPS's astrophysical scenarios and do not price instrumental artefacts"} F5: {"localisation": "not_measurable", "n_sectors_measurable": 0, "per_sector": [{"sector": 61, "net_depth_ppt": null, "net_err_ppt": null, "k7_absent": null, "note": "unmeasurable: sector unmeasurable: Insufficient aperture or background pixels", "k7_elsewhere": null, "difference_max_dist_target_px": 0.689, "centroid_sigma": 7.334680775322424, "centroid_shift_px": 0.04479979673294406}, {"sector": 63, "net_depth_ppt": null, "net_err_ppt": null, "k7_absent": null, "note": "unmeasurable: sector unmeasurable: Insufficient aperture or background pixels", "k7_elsewhere": null, "difference_max_dist_target_px": 1.925, "centroid_sigma": 5.377574160134861, "centroid_shift_px": 0.02073742896388247}, {"sector": 66, "centroid_sigma": 8.659529357745342, "centroid_shift_px": 0.050065647297004245}, {"sector": 67, "net_depth_ppt": null, "net_err_ppt": null, "k7_absent": null, "note": "unmeasurable: sector unmeasurable: Insufficient aperture or background pixels", "k7_elsewhere": null, "difference_max_dist_target_px": 1.846, "centroid_sigma": 7.933323154723823, "centroid_shift_px": 0.031855858494827145}, {"sector": 68, "net_depth_ppt": null, "net_err_ppt": null, "k7_absent": null, "note": "unmeasurable: sector unmeasurable: Insufficient aperture or background pixels", "k7_elsewhere": null, "difference_max_dist_target_px": 1.898, "centroid_sigma": 19.065851322409987, "centroid_shift_px": 0.10207272894982995}, {"sector": 87, "centroid_sigma": 0.0, "centroid_shift_px": 0.0}, {"sector": 88, "net_depth_ppt": null, "net_err_ppt": null, "k7_absent": null, "note": "unmeasurable: sector unmeasurable: Insufficient aperture or background pixels", "k7_elsewhere": null, "difference_max_dist_target_px": 1.949, "centroid_sigma": 1.4906829249807194, "centroid_shift_px": 0.013215434970485345}, {"sector": 90, "net_depth_ppt": null, "net_err_ppt": null, "k7_absent": null, "note": "unmeasurable: sector unmeasurable: Insufficient aperture or background pixels", "k7_elsewhere": null, "difference_max_dist_target_px": 1.673, "centroid_sigma": 2.259003077272654, "centroid_shift_px": 0.015004318634609635}, {"sector": 93, "net_depth_ppt": null, "net_err_ppt": null, "k7_absent": null, "note": "unmeasurable: sector unmeasurable: Insufficient aperture or background pixels", "k7_elsewhere": null, "difference_max_dist_target_px": 1.399, "centroid_sigma": 42.37525624122812, "centroid_shift_px": 0.10497394869047069}, {"sector": 94, "centroid_sigma": 22.630446520951164, "centroid_shift_px": 0.12237349589945841}, {"sector": 95, "net_depth_ppt": null, "net_err_ppt": null, "k7_absent": null, "note": "unmeasurable: sector unmeasurable: Insufficient aperture or background pixels", "k7_elsewhere": null, "difference_max_dist_target_px": 1.462, "centroid_sigma": 3.5137043877186946, "centroid_shift_px": 0.011271728852694823}, {"sector": 98, "net_depth_ppt": null, "net_err_ppt": null, "k7_absent": null, "note": "unmeasurable: sector unmeasurable: Insufficient aperture or background pixels", "k7_elsewhere": false, "difference_max_dist_target_px": 1.849, "centroid_sigma": 3.9611273047818405, "centroid_shift_px": 0.021410154054917734}]} F6: [{"period_days": "14.528956691375901", "depth_ppt": "3.9345840716281146", "snr": "8.992037329254616", "verdict": "promising planet candidate", "stitch_snr": "6.105827790907652", "passes_pregate": "False"}, {"period_days": "26.93467278685396", "depth_ppt": "5.251458663921602", "snr": "7.951206134732675", "verdict": "promising planet candidate", "stitch_snr": "7.870820916904857", "passes_pregate": "False"}, {"period_days": "15.643361630894221", "depth_ppt": "5.044239617478126", "snr": "7.48156385395506", "verdict": "promising planet candidate", "stitch_snr": "5.998559603962218", "passes_pregate": "False"}, {"period_days": "14.982422821125667", "depth_ppt": "1.9830604857478555", "snr": "7.1871280690081845", "verdict": "promising planet candidate", "stitch_snr": "7.1871280690081845", "passes_pregate": "True"}, {"period_days": "15.982360022396412", "depth_ppt": "2.0006194973227975", "snr": "7.180664525537898", "verdict": "promising planet candidate", "stitch_snr": "7.180664525537898", "passes_pregate": "True"}, {"period_days": "13.615393343419061", "depth_ppt": "4.0365355685524325", "snr": "7.113726168688673", "verdict": "promising planet candidate", "stitch_snr": "7.061209022224173", "passes_pregate": "False"}, {"period_days": "25.104731094022473", "depth_ppt": "2.039597488967254", "snr": "6.774793516700831", "verdict": "promising planet candidate", "stitch_snr": "6.774793516700831", "passes_pregate": "False"}, {"period_days": "23.815343557318776", "depth_ppt": "3.8798497638666443", "snr": "6.5416380240372645", "verdict": "promising planet candidate", "stitch_snr": "6.178860005590139", "passes_pregate": "False"}, {"period_days": "16.439594137218847", "depth_ppt": "10.27652859135896", "snr": "6.472284526714291", "verdict": "ambiguous / manual vetting required", "stitch_snr": "6.214481578940874", "passes_pregate": "False"}, {"period_days": "17.589652927672585", "depth_ppt": "3.7754362364026166", "snr": "6.249077884066912", "verdict": "ambiguous / manual vetting required", "stitch_snr": "6.1183671548560365", "passes_pregate": "False"}, {"period_days": "28.620561884748504", "depth_ppt": "5.888290205651533", "snr": "6.206240589456474", "verdict": "promising planet candidate", "stitch_snr": "5.777388855761544", "passes_pregate": "False"}, {"period_days": "22.30567007792828", "depth_ppt": "6.613425592018463", "snr": "6.062978184419099", "verdict": "ambiguous / manual vetting required", "stitch_snr": "6.206165022301723", "passes_pregate": "False"}, {"period_days": "8.033871414509049", "depth_ppt": "4.990069207914949", "snr": "5.894218462941634", "verdict": "promising planet candidate", "stitch_snr": "6.482879674006049", "passes_pregate": "False"}, {"period_days": "17.120271931797564", "depth_ppt": "2.3260716361266107", "snr": "5.738524641787483", "verdict": "promising planet candidate", "stitch_snr": "5.738524641787483", "passes_pregate": "False"}, {"period_days": "26.114652286951433", "depth_ppt": "9.170552740315783", "snr": "5.633173363685128", "verdict": "promising planet candidate", "stitch_snr": "6.9470813746394295", "passes_pregate": "False"}, {"period_days": "25.580446287317415", "depth_ppt": "4.415674842480666", "snr": "5.549257467333411", "verdict": "promising planet candidate", "stitch_snr": "6.588881021834362", "passes_pregate": "False"}, {"period_days": "20.050474777990306", "depth_ppt": "5.54662985971142", "snr": "5.510450132163415", "verdict": "promising planet candidate", "stitch_snr": "5.933095253920864", "passes_pregate": "False"}, {"period_days": "19.738452592378067", "depth_ppt": "3.915280660314547", "snr": "5.46667336483957", "verdict": "promising planet candidate", "stitch_snr": "6.938938707543156", "passes_pregate": "False"}, {"period_days": "8.524285175424229", "depth_ppt": "2.4694813118629297", "snr": "5.032269138359716", "verdict": "promising planet candidate", "stitch_snr": "5.792318309171654", "passes_pregate": "False"}] F7: {"status": "CLEAN", "tic_matches": [], "neighbour_matches": [], "tce_association": null} F8: {"n_observed": 12, "n_excluded": 5, "n_kept": 7, "removed_by_class": {"dip_absent_in_sap": 0, "pdc_gap": 0, "scattered_light_ramp": 1, "scattered_light_flag": 0, "momentum_dump": 0, "sector_orbit_edge": 0, "quality_flagged": 5, "sap_baseline_ramp": 1}, "strongest_event_removed": true} F9: "42 Gaia neighbour(s) within 63 arcsec could produce the depth by total eclipse (nearest 13.3 arcsec, G 17.829437255859375, needing an eclipse of 32% of its light). Seeing-limited ground photometry at the predicted epochs, resolving each of them, would settle the source. TESS pixel evidence is not measurable for this candidate (no usable fixed-aperture sector); the localisation rests entirely on external photometry. TRICERATOPS FPP 0.168, NFPP 0.145 on the binned fold; a low value does not price instrumental artefacts. Statistical validation additionally needs a resolved source, repeated localised dimming and a low FPP with the scene fixed; this candidate is submitted as a candidate, not as a validated planet." F10: {"word": "K10_FLAG", "or_variants": ["K10e", "K10s"], "or_fired": false, "K10e": {"fired": false, "measurable": true, "detail": "n_excluded / n_observed = 5/12 = 0.417 (> 0.5 fires)", "n_observed": 12, "n_excluded": 5, "fraction": 0.4166666666666667}, "K10s": {"fired": false, "measurable": true, "detail": "SAP 3.698 +/- 0.668 ppt vs corrected 4.873 +/- 0.659 ppt; SAP < 0.5x False; difference > 3 sigma False; kept events in 6 sector(s)", "det_ppt": 4.873, "det_err_ppt": 0.659, "sap_ppt": 3.698, "sap_err_ppt": 0.668, "quadrature_err_ppt": 0.93835227926403, "kept_sectors": [63, 66, 90, 93, 95, 98], "sap_below_half": false, "difference_significant": false, "kept_sectors_ge_2": true}, "deciding": false}

The field's validation bar (resolved source, localised repeated dimming, low FPP) is out of reach for TESS FFI photometry alone at Tmag 13.5; this is a candidate for follow-up, not a validated planet.

Next transits: BTJD 4337.555 +/- 0.34 h; BTJD 4365.098 +/- 0.34 h; BTJD 4392.642 +/- 0.35 h.

## 5. Completeness (short form; full statement in `p12/results/COMPLETENESS_P12.md`)

**Scope.** injection completeness is measured through S, with C on the 30-injection sample; no injection runs through D; D-level behaviour on planets is measured only by LB3 on the 12 ephemeris-assisted P9 hosts; the delivered list is end to end, and its D-level completeness is not calibrated by injections.
At radius 1 to 1.41 Re the frozen pipeline recovers 41/414 (9.9%) of injected planets on stars of Tmag 12.5 to 14 with at least 3 policy sectors through the funnel to S.
At radius 1.41 to 2 Re the frozen pipeline recovers 150/408 (36.8%) of injected planets on stars of Tmag 12.5 to 14 with at least 3 policy sectors through the funnel to S.
At radius 2 to 2.83 Re the frozen pipeline recovers 303/440 (68.9%) of injected planets on stars of Tmag 12.5 to 14 with at least 3 policy sectors through the funnel to S.
At radius 2.83 to 4 Re the frozen pipeline recovers 300/425 (70.6%) of injected planets on stars of Tmag 12.5 to 14 with at least 3 policy sectors through the funnel to S.
At P in [0.5, 1.39] d the frozen pipeline recovers 240/423 (56.7%) of injected planets of 1 to 4 Re through the funnel to S.
At P in [1.39, 3.87] d the frozen pipeline recovers 240/423 (56.7%) of injected planets of 1 to 4 Re through the funnel to S.
At P in [3.88, 10.76] d the frozen pipeline recovers 185/422 (43.8%) of injected planets of 1 to 4 Re through the funnel to S.
At P in [10.8, 29.96] d the frozen pipeline recovers 129/417 (30.9%) of injected planets of 1 to 4 Re through the funnel to S.

## 6. Specificity

Survival of independent negatives at B, C and D with N and Wilson bounds: `p12/results/SPECIFICITY_P12.md`.
What N can and cannot detect: the Wilson 95% upper bound is 11.4% on 0 of 30, 16.7% on 1 of 30, 22.8% on 0 of 13, 43.4% on 0 of 5; the bar detects a gross specificity failure (one binary in ten passing) and cannot detect a 3% false-SUBMIT rate.

## 7. Cost ledger

Queue-hours (all parts): 168.28997285647247; details in `p12/manifests/resource_ledger.json`.

## 8. Next steps for the user

Open each packet under `docs/packets/audit_p12/<key>/`, fill `tag`, `candidate_name` and `paper_url` in `ctoi_fields.json`, and enter the CTOI form by hand if you choose. Nothing was submitted anywhere.

The registered P12 work on these inputs is complete; these measurements bound what it can find, and the specific experiments that could move those bounds are pixel-level photometry, the only untested input change with a measured noise lever; a detrending-window test on the 2b instrument (about 20 queue-hours); an unexposed in-domain truth-positive set, which the records do not contain.

---

## Audit detail

### Funnel

P12 rows by last stage: {"A": 5326, "pregate": 21869, "input": 378, "S": 573, "C": 62, "D": 18, "search": 2}.
Natural load per group: {"p8_2000": {"accepted": 16663, "pregate": 3291, "A": 208, "A_unknown": 8, "S": 26, "S_on_A_fail_sample": 146, "B": 26, "C_pass": 4, "C_unresolved": 0, "D": 4, "SUBMIT": 1, "HOLD": 3, "KILL": 0}, "p10_436": {"accepted": 3844, "pregate": 1099, "A": 292, "A_unknown": 7, "S": 29, "S_on_A_fail_sample": 38, "B": 29, "C_pass": 12, "C_unresolved": 0, "D": 12, "SUBMIT": 0, "HOLD": 5, "KILL": 7}, "E1": {"accepted": 7341, "pregate": 1589, "A": 153, "A_unknown": 7, "S": 25, "S_on_A_fail_sample": 84, "B": 25, "C_pass": 2, "C_unresolved": 0, "D": 2, "SUBMIT": 1, "HOLD": 0, "KILL": 1}}.
P8: 13,252 / 3,688 / 189 / 19 / 19 / 6; 0 SUBMIT, 2 HOLD, 4 KILL (docs/AUDIT_P8.md). P10.3: 174 -> 131 -> 37 -> 13 -> 13 (FUNNEL_RETENTION_P10_3.md).

### S-rejected A passers (S-rejected, not verdicted)

- TIC 5736939 P 0.8517303481344531
- TIC 5736939 P 10.64553015342411
- TIC 7773681 P 1.9369540088315917
- TIC 21028557 P 14.26810303632207
- TIC 21028557 P 10.222468126956544
- TIC 21028557 P 16.199511553635165
- TIC 21127773 P 15.523518221846741
- TIC 22478002 P 17.592642186738427
- TIC 22478002 P 10.994797299800213
- TIC 22478002 P 10.44338939208232
- TIC 29002055 P 1.9266973324182803
- TIC 29002055 P 20.254227756165093
- TIC 30186108 P 1.6490093499075824
- TIC 30941455 P 8.437197870981658
- TIC 31020027 P 13.668924642687562
- TIC 31851521 P 21.010684092371157
- TIC 31925497 P 17.62436874816842
- TIC 32090581 P 16.705142735927126
- TIC 33766463 P 24.30897306958497
- TIC 33766463 P 15.140349850834752
- TIC 33766463 P 15.69076131593631
- TIC 33866201 P 10.306374327710328
- TIC 33866201 P 13.140639618284574
- TIC 33866201 P 11.594808021836577
- TIC 33866201 P 13.913578788219382
- TIC 33866201 P 12.367899882457799
- TIC 38396980 P 18.516276023336996
- TIC 38634790 P 15.57703150532992
- TIC 48194764 P 24.111731674500515
- TIC 48194764 P 19.208134675831968
- TIC 51903915 P 13.413646818080363
- TIC 52242947 P 0.8839393140613669
- TIC 52242947 P 10.176050386755476
- TIC 52242947 P 10.600059495407187
- TIC 52243722 P 13.213392249964091
- TIC 52284854 P 0.5141508656351935
- TIC 52284854 P 10.535557644689636
- TIC 52284854 P 10.028351658174422
- TIC 52284854 P 15.424795304249189
- TIC 52284854 P 14.142381132774345
- TIC 52284854 P 13.358420639406422
- TIC 52285218 P 5.017745791308141
- TIC 55386323 P 8.792920185578048
- TIC 55555248 P 10.129802714634206
- TIC 77562120 P 0.7808292394294434
- TIC 77562120 P 10.15061511969072
- TIC 77562120 P 13.330710720339372
- TIC 77562120 P 15.225305364614185
- TIC 77562120 P 10.526370973604166
- TIC 88658497 P 1.1787675514858298
- TIC 88658497 P 12.999259097580337
- TIC 88658497 P 17.569681022263673
- TIC 92350846 P 15.707350030933442
- TIC 92350846 P 1.4255400776098865
- TIC 99769004 P 11.487660977606712
- TIC 127001750 P 1.5023064276588363
- TIC 127001750 P 10.481438509439753
- TIC 127001750 P 13.474898925231651
- TIC 127001750 P 18.003763853124667
- TIC 138345863 P 29.75532716857539
- TIC 138345863 P 11.128827806730397
- TIC 138345863 P 19.439910997511088
- TIC 141712726 P 13.268012910881462
- TIC 142085068 P 20.1972955999505
- TIC 149157628 P 12.631340068229488
- TIC 149631332 P 10.721875177818458
- TIC 149631332 P 28.414612458992966
- TIC 149631332 P 14.474067457605575
- TIC 149631332 P 10.187426038519694
- TIC 149631332 P 13.403731960600833
- TIC 150246350 P 13.844566248569205
- TIC 150272892 P 10.613326697572449
- TIC 150429987 P 12.365569054439472
- TIC 156883283 P 15.011660994827167
- TIC 157115721 P 10.866682467255876
- TIC 159312066 P 11.074051308581799
- TIC 159312066 P 23.991218420578065
- TIC 159510452 P 1.8262395914721044
- TIC 159510452 P 16.45489218655747
- TIC 160118032 P 0.702633066409416
- TIC 160118032 P 10.18796094825192
- TIC 160118032 P 14.404695851802598
- TIC 160272538 P 12.243203749350275
- TIC 160272538 P 14.238621082877264
- TIC 160491815 P 10.789961007268335
- TIC 160602230 P 0.8794509366070951
- TIC 160602230 P 10.113590648956768
- TIC 160602230 P 10.553542098003
- TIC 160618340 P 2.5828254718860673
- TIC 160618340 P 10.331576370655888
- TIC 165526906 P 10.195190419434269
- TIC 165528645 P 11.734113265477845
- TIC 165528645 P 15.645231831085848
- TIC 165530589 P 13.745099591704697
- TIC 165530589 P 19.646722821535892
- TIC 165530589 P 23.562499739593765
- TIC 165548860 P 15.385182092664593
- TIC 167244982 P 10.477989248874037
- TIC 177033503 P 12.080011882119567
- TIC 177352028 P 10.120331247625248
- TIC 177352893 P 13.294554165729055
- TIC 179381768 P 26.124086329461875
- TIC 188600399 P 13.905137540209022
- TIC 188626183 P 12.238758293912099
- TIC 188819782 P 1.6558326773828593
- TIC 188819782 P 11.59459493052997
- TIC 198185267 P 0.748656726879913
- TIC 198185267 P 10.231351719819957
- TIC 198189672 P 10.764774914807528
- TIC 198189672 P 10.316113021424734
- TIC 198236067 P 0.8936362316086846
- TIC 198236067 P 10.724112811668912
- TIC 198557860 P 11.834735790214683
- TIC 198589449 P 17.189028251388898
- TIC 199573123 P 10.086924330454643
- TIC 200650008 P 10.718623307621515
- TIC 200650008 P 14.250631823547268
- TIC 200650008 P 15.301302823423415
- TIC 200650008 P 11.739597305214561
- TIC 200650008 P 20.417877236097873
- TIC 201306711 P 0.7172875051914833
- TIC 201306711 P 13.62756513224938
- TIC 201306711 P 11.122270954823993
- TIC 201364373 P 13.404618323826142
- TIC 206327810 P 13.823963309473346
- TIC 206327810 P 10.682598872025041
- TIC 206550085 P 14.137804365581697
- TIC 206550085 P 13.302206302222325
- TIC 207142605 P 10.818231972368624
- TIC 207142605 P 10.212437985791341
- TIC 207211020 P 0.5156341097348353
- TIC 207211020 P 13.666355427522655
- TIC 207211020 P 10.054294471846315
- TIC 219019609 P 2.213397847782933
- TIC 219740029 P 4.5162942574025235
- TIC 219755626 P 0.6289083664206964
- TIC 219755626 P 10.062524041482586
- TIC 219755626 P 13.416985638173559
- TIC 219755626 P 12.578460891385353
- TIC 219755626 P 11.530178038663577
- TIC 219773818 P 12.545644701162088
- TIC 219773818 P 15.968499830324598
- TIC 219797811 P 10.08850496014765
- TIC 219806427 P 1.861131002662448
- TIC 219806427 P 11.180808334403265
- TIC 219806889 P 20.376280088485178
- TIC 219806889 P 26.063246063459772
- TIC 219806889 P 14.128364535922524
- TIC 219806889 P 22.25955275996137
- TIC 219847563 P 13.438790235348973
- TIC 219847563 P 14.562288049541529
- TIC 219847563 P 29.201606589980056
- TIC 224601129 P 10.417282949532034
- TIC 224607337 P 26.20268358306424
- TIC 229675969 P 10.251314193235618
- TIC 229764903 P 11.198748458088753
- TIC 229796245 P 13.245305126807986
- TIC 229796245 P 10.618773226375998
- TIC 230071520 P 12.51466689614802
- TIC 230071520 P 29.206036270684024
- TIC 230071520 P 10.425752437294994
- TIC 230071520 P 4.187271165550576
- TIC 230122612 P 20.859359622072038
- TIC 230122612 P 12.96443188434695
- TIC 230129453 P 13.311466208517434
- TIC 230129453 P 15.138182848816198
- TIC 230129453 P 14.248475249145775
- TIC 230383618 P 0.586832096877003
- TIC 230383618 P 10.171571262990023
- TIC 230383618 P 12.518857661719714
- TIC 230383618 P 13.88824347147032
- TIC 230383618 P 10.758518984132403
- TIC 230383618 P 11.345214980836191
- TIC 230383618 P 15.257099515731198
- TIC 231827782 P 0.6749460241698838
- TIC 231827782 P 13.517183874194604
- TIC 231827782 P 12.49176589815049
- TIC 231827782 P 10.461067517043595
- TIC 231827782 P 11.48969817344197
- TIC 231827782 P 11.131213380510301
- TIC 231852621 P 13.746259204634738
- TIC 232616666 P 14.43252751057364
- TIC 232616666 P 11.547035973319787
- TIC 232643687 P 0.7114648051032486
- TIC 232643687 P 10.314928646423494
- TIC 233060572 P 10.0827041757723
- TIC 233070089 P 10.647031963082204
- TIC 233070089 P 16.620271007924917
- TIC 233087983 P 16.530030894073086
- TIC 233089830 P 19.633390558814135
- TIC 233089830 P 13.318766496353387
- TIC 233127050 P 0.7871841844718085
- TIC 233127050 P 1.7711912998047594
- TIC 233127050 P 10.430481853290724
- TIC 233233165 P 1.7022593854179557
- TIC 233233165 P 10.221581044435027
- TIC 233233165 P 11.91387448668813
- TIC 233233165 P 13.673654340489215
- TIC 233570240 P 11.53800917057032
- TIC 233617044 P 11.093588058006413

### The 436 and the P8 B passers with a P12 record

p10_436: 29 B passers in P12: TIC 32090581 (REJECT_C), TIC 159312066 (KILL), TIC 160535706 (REJECT_C), TIC 161725589 (REJECT_C), TIC 165530589 (REJECT_C), TIC 165530589 (REJECT_C), TIC 167244982 (REJECT_C), TIC 167244982 (REJECT_C), TIC 188626183 (REJECT_C), TIC 224601129 (HOLD), TIC 229683420 (KILL), TIC 229764903 (HOLD), TIC 272781325 (KILL), TIC 282923395 (REJECT_C), TIC 284762958 (REJECT_C), TIC 288382046 (REJECT_C), TIC 298264674 (KILL), TIC 300009970 (KILL), TIC 322949743 (KILL), TIC 323598320 (REJECT_C), TIC 388106735 (REJECT_C), TIC 394244919 (REJECT_C), TIC 404411931 (REJECT_C), TIC 411629716 (HOLD), TIC 428888136 (REJECT_C), TIC 428991040 (KILL), TIC 458481937 (HOLD), TIC 459189437 (HOLD), TIC 459192460 (REJECT_C)
p8_2000: 26 B passers in P12: TIC 32032816 (REJECT_C), TIC 149038799 (REJECT_C), TIC 149103580 (REJECT_C), TIC 149157628 (REJECT_C), TIC 154566869 (REJECT_C), TIC 154566869 (REJECT_C), TIC 160618340 (HOLD), TIC 167305187 (REJECT_C), TIC 198517968 (REJECT_C), TIC 201289511 (REJECT_C), TIC 206327810 (REJECT_C), TIC 230120862 (REJECT_C), TIC 230120862 (HOLD), TIC 233073794 (REJECT_C), TIC 257463348 (REJECT_C), TIC 259266547 (REJECT_C), TIC 277749935 (REJECT_C), TIC 281599809 (REJECT_C), TIC 284191177 (REJECT_C), TIC 318181531 (REJECT_C), TIC 350137360 (REJECT_C), TIC 356226514 (REJECT_C), TIC 383988275 (HOLD), TIC 401372442 (REJECT_C), TIC 404927114 (SUBMIT tier 2), TIC 436869614 (REJECT_C)

### Part 1 and Part 2 tables

- `p12/results/part1/plumbing_d.json`: {"utc": "2026-09-23T18:47:36.462705+00:00", "status": "MATCH", "k10_word": "K10_FLAG", "updates_sha256": "a3d0d2eba1ae1fe7f6a7c06ab26ad8e7592689ee1444b3b28dcd741441a0716a", "rule": "PROMPT_P12.md 1d: a live-measurement difference is recorded with both values and the expectation updated in AMENDMENTS_P12.md; any other difference is a defect, fixed once; a second failure is STOP-3"}
- `p12/results/part1/k10_calibration.json`: {"utc": "2026-09-23T16:41:05.408881+00:00", "schema": "p12-k10-calibration-v1", "word": "K10_FLAG", "fires_on_key_record": true, "artefact_kills_fired": 2, "artefact_kill_bar": 3, "denominator": "fired / all records of the set (a not-measurable record counts as not fired)", "source_sha256": "a0fde20b3b7d989b2297c845e63eee5dff12ada0ecf18de91b01955fba38eff9", "rules_sha256": "9ddf364811bc943754d43e0
- `p12/results/part1/tier_rederivation_p12.json`: {"utc": "2026-09-23T18:47:40.041611+00:00", "label": "re-scoring of seen records under pre-registered rules, not a validation", "rules_version": "p12.0", "all_p10_reproduced": true, "source_sha256": "e55836213b44b55748b6e8adee81c4cbea24b007c2a6f8ebba42e3e4e684b508"}
- `p12/results/part2/photometry_decision.json`: {"utc": "2026-09-26T13:19:20.137199+00:00", "decision": "KEEP_ARCHIVAL", "median_wall_ratio": 0.764553156141263, "n_paired_2b": 494, "rule": "every clause required (PROMPT_P12.md 2c); a failed change is not adopted and not retried with a lower bar"}

### Unknowns by stage

{"A": 0, "S": 0, "B": 0}

### Section 8 conditions

```json
{
 "freeze_exists": true,
 "freeze_predates_every_launch": true,
 "bar_met": false,
 "final_search_closed": true,
 "every_B_passer_has_C": true,
 "every_C_case_has_D": true,
 "integrity_entry_zero": true,
 "integrity_final_zero": true,
 "routine_disabled_verified": true,
 "stop_receipts": [
  "stop_3_entry.json",
  "stop_3_integration.json",
  "stop_STOP-4_20260924T152709.json",
  "stop_STOP-6_20260923T165952Z.json",
  "stop_STOP-7_20260926T194951Z.json",
  "stop_STOP-7_20260930T015624Z.json",
  "stop_controller_cal_a_A.json",
  "stop_controller_plumbing_d.json",
  "stop_controller_plumbing_d_resume.json",
  "stop_normal_exposure.json"
 ]
}
```
