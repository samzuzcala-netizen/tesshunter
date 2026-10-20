import common as C
cfg=dict(candidate=332366289,created_utc=C.datetime.datetime.now(C.datetime.timezone.utc).isoformat(),adopted_followup_choices=True,EA=C.EA,EF=C.EF,sectors=C.SECTORS,
 baseline='linear, ordinary least squares on both sides only; no flux clipping',guard_days=1/24,reference_days=5/24,
 depth='exposure-integrated box coefficient in baseline-normalised residuals; positive is dimming; fit in-event overlap only',
 gap='reject a local window crossing gaps >2.5 native cadences in usable data or a momentum dump; diagnostic failure remains missing',
 coverage_min=0.75,reference_side_min=0.6,spoc_bad_bits=191,cutout_good='QUALITY==0; matched SPOC bad bits excluded',
 qlp_bad='all nonzero quality except low-precision bit (4096 pre56,1073741824 post56); no use of DET_FLUX_ERR',
 background='fixed faintest 20% of median-image pixels outside radius 4 px and outside optimal aperture; per-frame median; aperture sum minus n_pix*background',
 controls='same estimator; 0.65 d grid, non-overlapping 14.3 h windows, exclude +/-full local span of either ephemeris; all valid windows, max60/sector',
 error='max(local white standard error, control sample SD, 1.4826 MAD, control RMS about zero); scale by sqrt(control median effective in count/event effective count) if event has fewer samples',
 pdc_difference='paired depth differences on same-time common finite mask; empirical control difference errors, preserves covariance; convert SAP to target fraction using CROWDSAP',
 injections='all valid controls (max60/sector), raw SAP/optimal/small; exposure-integrated box at inherited kept PDCSAP 6.50ppt and SAP 3.76ppt; incremental recovery plus absolute recovery; retain negative depths',
 independent_raw_event='SAP depth/error >=2.5 AND optimal pixel depth/error >=2 AND same sign, paired discrepancy <3 combined sigma; exploratory moderate evidence, not a 3-sigma detection',
 period_range_days=[1,100],alias='all integer delta_t/n from the widest-separated individually supported primary raw pair; anchor times fixed EA centres; phase/period tolerance envelope sampled at 5x5 offsets +/-EA half-duration at each endpoint; require consistency with all other supported anchors',
 alias_reject='other covered raw SAP epochs (exclude anchors and E39) weighted joint depth below anchor depth by >=3 combined sigma; survive if any tolerance-grid ephemeris is not rejected; missing coverage never rejects',
 conditional_alias='if fewer than two independently supported raw events, no data-supported alias enumeration; separately label conditional s57+s80 hypothesis for coverage planning, never claim these periods are measured',
 map=dict(P_min=C.EA[0]-0.003,P_max=C.EA[0]+0.003,nP=121,T0_min=C.EA[1]-0.06,T0_max=C.EA[1]+0.06,nT0=81,model='fixed EA duration, SAP only with CROWDSAP conversion; common nonnegative depth; calibrated per-event errors; excluded E39 never pooled; report coverage counts and both all-epoch and pre56 maps; no significance from maximisation'),
 status_precedence=['OPERATIONAL_BLOCKED if essential acquisition/analysis fails','PERIOD_REFUTED if both fixed EA and EF raw other-epoch tests reject at >=3 sigma AND entire joint ephemeris box rejects reference depth','NOT_SUPPORTED if retained raw SAP joint SNR <3 or optimal pixel joint SNR <3','PDC_DEPENDENT if retained PDCSAP SNR>=3 but raw SAP SNR<2 and paired enhancement>=3 sigma for any event','PERIOD_AMBIGUOUS if fewer than two supported raw events or multiple aliases survive or timing envelope not excluded','RAW_SIGNAL_CONSISTENT only with >=2 supported raw events, consistent depth chi-square p>=0.01, one alias survives and back projection not rejected'],
 e39='diagnostic only, never pooled or used to reject aliases; diagnostics for candidate predictions in s84 supplied',seed=332366289,workers=1,numerical_threads=1,wall_hours=3,download_bytes=5000000000)
p=C.WS/'config.json'
if p.exists(): raise RuntimeError('Config already exists; no silent overwrite')
C.write(p,cfg)
text='''# TIC 332366289 light-curve follow-up: predeclared plan

This is a new candidate-only post-P12 analysis. No historical code is executed and no P12 verdict or tier changes. Localisation v1 is historical input only. Choices here are adopted follow-up choices, not P12 rules. Configuration timestamp and SHA256 establish that this plan predates new depths.

## Inputs and identity
Read cached TESS-SPOC/QLP and TESScut for this star only. One MAST observation search and one aggregate product-list request; per-product downloads for sectors 24–53. Download earlier cubes only when an EA/EF epoch has data. Verify TIC identity, BTJD/TDB, native cadence, exposure, one-to-one nearest-time matching within half a cadence, and exact CCD-origin aperture mapping. Retain original times and offsets. Never transfer masks by index. All historical files opened are hashed before and after, including files scanned for K9 code. Files merely listed are outside content-integrity scope. Only new directories receive writes.

## Fixed local measurement
Process each sector separately. Primary EA duration 0.0928318 d; EF sensitivity 1.93 h. Linear OLS baseline uses two 5-hour reference windows after a 1-hour guard on either side of half-duration. Guard covers the EA/EF difference across the full baseline. Fit an exposure-integrated box to fractional residuals, without positivity constraint or flux clipping. Require >=75% in-event exposure coverage and >=60% of each reference side. Reject windows crossing >2.5-cadence gaps or momentum dumps; E39 uses the same recipe and may be unmeasurable in PDC. Scattered-light flags are recorded, not silently removed. All photometries use this recipe.

Extract optimal and central 3x3 cutout apertures with per-frame background subtracted. Background pixels are the fixed faintest 20% of the median sector image outside 4 px and the optimal aperture; median across those pixels in each frame. Save masks and background. SAP and optimal-aperture depths divided by CROWDSAP approximate target fractional depths; PDCSAP already includes crowding and flux-fraction corrections. FLFRCSAP cancels from fractional depths but matters in absolute flux comparison. Small-aperture and QLP dilution is unknown; report their native fractional depths and do not pool them with SAP or claim independent photons.

## Controls and injections
Controls use a deterministic 0.65-d grid (nonoverlapping local windows), excluding either ephemeris by a full-window margin. Use all valid windows, max60/sector. Error is the maximum of local white error, control SD, robust MAD and RMS about zero. Sparse events get a count correction. Report sample sizes, null bias and empirical ranks. Empirical controls are too few to certify Gaussian 3-sigma tails. Differences use paired common-time controls to retain SAP/PDC covariance.

Inject exposure-integrated boxes into SAP and both background-subtracted pixel curves at inherited 6.50 and 3.76 ppt. Record incremental recovered depth, absolute recovery, bias and scatter for every valid control. No recipe selection on event outcomes.

## Period and decisions
Enumerate every EA/EF cycle intersecting every sector range, including gaps and no-coverage rows. Compare earlier raw SAP epochs to retained-event raw depth with combined calibrated errors. Evaluate a bounded 121x81 (P,T0) map around both ephemerides, SAP only, fixed duration, common nonnegative depth. Keep pre56 and all-epoch maps, counts and coverage. Map likelihood is descriptive, not calibrated discovery significance.

Independent raw support requires SAP SNR>=2.5, optimal-pixel SNR>=2, positive depths and agreement within 3 combined sigma. This is moderate exploratory evidence, not a claim of 3-sigma single-event detection. Use the widest supported pair to enumerate delta_t/n periods from 1–100 d. For each test 5x5 endpoint offsets within half an EA duration, all covered data, exclude anchors, never pool E39. Reject only when the joint other-epoch raw depth falls >=3 combined sigma below the anchor depth for every tested timing variant. This finite grid cannot exclude all continuous timing possibilities; surviving aliases are bounded hypotheses. If <2 supported events, show a separately labelled conditional s57+s80 coverage test only.

Status precedence and full numeric rules are in config.json. PDC-dependent requires PDC SNR>=3, SAP SNR<2 and paired enhancement>=3 sigma in a retained event. Refutation requires rejection of EA, EF and the entire bounded map at the reference depth. No significant joint raw signal takes NOT_SUPPORTED; otherwise unresolved period support takes PERIOD_AMBIGUOUS. OPERATIONAL_BLOCKED has priority if essential inputs or steps fail. E39 is always diagnostic, including in alias tests. Report secondary flags and independent-event counts without changing P12.

## Resource and preservation controls
Single process, one numerical thread, 3-hour wall ceiling including preflight, 5 GB received-download ceiling; 5-minute finalisation reserve. Network connect/read timeouts 20/120 s, product wall 600 s; at most one transport retry, no repeated searches. Checkpoints after acquisition, extraction, depths and periods. No workers, automations, external submissions or git mutations. Review all PNGs before packaging. Bundle contains code, tests, compact results and figures, no FITS/caches.
'''
(C.WS/'PLAN.md').write_text(text,encoding='utf-8')
C.write(C.WS/'inputs/premeasurement_seal.json',{'created_utc':cfg['created_utc'],'config_sha256':C.sha(p),'plan_sha256':C.sha(C.WS/'PLAN.md'),'depths_measured':False})
print('Predeclared',cfg['created_utc'])
