"""Every threshold of the prompt-5 / prompt-6 audit, stated once.

This module holds no logic beyond assembling the numbers into a dict that is
stamped into every record.  The rule code lives in :mod:`tesshunter.audit_prep`
(preprocessing), :mod:`tesshunter.event_vet` (per-event examination and the
removal rules), :mod:`tesshunter.star_vet` (the star-level tests) and
:mod:`tesshunter.secondary` (the full-phase secondary scan).

Three named rule sets exist:

``LEGACY_RULES`` (``p6.2``)
    exactly what prompts 5 and 6 applied to the top ten and to all 405
    survivors.  Every option added in prompt 7 is OFF.  ``scripts/audit_p5.py``
    and ``scripts/revet_p6.py`` use this set by default, so their records stay
    reproducible; ``scripts/p7_reproduce.py`` re-derives the P6 records with it.

``DEFAULT_RULES`` (``p7.0``)
    the same rules with the four prompt-7 options ON: the full-phase secondary
    scan, red-noise-inflated depth consistency, transit-masked detrending and
    the long-period window test.  This is the package default and the set any
    new record is stamped with.

``P8_RULES`` (``p8.0``)
    the preregistered P8 comparison retained the p7.0 gate choices: bound
    secondary gate, transit-masked detrending, and inflated depth consistency
    with beta capped at 5 and p >= 1e-3. Stage B records exact window values.
    The P8 funnel selects this set explicitly; legacy defaults are unchanged.

Origin tags: **[P5]** the threshold as adopted in prompt 5 (``docs/AUDIT.md``
section 1), **[P6]** adopted or restated in prompt 6 (``docs/REVET.md``
section 2), **[P7]** introduced by prompt 7 with the measurement that motivated
it recorded in ``docs/RULES.md``.

Nothing here decides anything about a candidate; it only names the numbers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace

# ─────────────────────────────────────────────────────────────────────────────
# Quality bits and the per-product mask
# ─────────────────────────────────────────────────────────────────────────────
#: [P5] momentum-dump (desaturation) bit.
Q_DESAT = 32
#: [P5] manual-exclude bit.
Q_MANUAL = 128
#: [P5] the two scattered-light bits (Earth/Moon in the camera).
Q_STRAYLIGHT = 2048 | 4096
#: [P5] lightkurve's "default" TESS bitmask.
Q_DEFAULT = 17087
#: [P5] lightkurve's "hard" TESS bitmask (recorded, never used by a rule).
Q_HARD = 24319
#: [P5] QLP's own low-precision flag, sectors 1-55.  The survey's ``ffi.py``
#: masks the same bit.
QLP_LOW_PRECISION_S1_55 = 2 ** 12
#: [P5] QLP's low-precision flag from sector 56 on (the bit moved).
QLP_LOW_PRECISION_S56 = 2 ** 30
#: [P5] the sector at which QLP's low-precision bit changes.
QLP_FLAG_SECTOR_SPLIT = 56

# ─────────────────────────────────────────────────────────────────────────────
# Preprocessing: detrend, clip, bin  (docs/AUDIT.md section 1 step 2)
# ─────────────────────────────────────────────────────────────────────────────
#: [P5] wotan detrending method.
WOTAN_METHOD = "biweight"
#: [P5] window = 3 x the central-transit duration at the candidate period ...
WOTAN_WINDOW_T14_MULTIPLE = 3.0
#: [P5] ... with this floor ...
WOTAN_WINDOW_MIN_DAYS = 0.75
#: [P5] ... and this cap, both in days.
WOTAN_WINDOW_MAX_DAYS = 1.5
#: [P5] wotan break tolerance (days): a gap this large splits the window.
WOTAN_BREAK_TOLERANCE = 0.5
#: [P5] wotan edge cutoff: none, so the sector edges keep their cadences.
WOTAN_EDGE_CUTOFF = 0.0
#: [P5] upward outliers only (flares, cosmic rays) are clipped, at this sigma.
UPWARD_CLIP_SIGMA = 4.0
#: [P5] an isolated single-cadence dip: this many sigma below the baseline ...
ISOLATED_DIP_SIGMA = 6.0
#: [P5] ... with both neighbours within this many sigma of it.
ISOLATED_NEIGHBOUR_SIGMA = 2.0
#: [P5] minimum cadences a product must keep to be used at all.
MIN_POINTS_PER_PRODUCT = 50
#: [P5] bin width in minutes for the search series.
BIN_MINUTES = 30.0
#: [P5] a bin's error is the in-bin scatter when it holds at least this many
#: points, otherwise the propagated per-cadence error.
BIN_MIN_POINTS_FOR_SCATTER = 3
#: [P5] binned points deeper than this multiple of the candidate depth ...
DEEP_CLIP_DEPTH_MULTIPLE = 3.0
#: [P5] ... or this multiple of the binned MAD, whichever is larger, are
#: dropped, so that a binary host's eclipses cannot dominate the spectrum the
#: candidate is being tested in.
DEEP_CLIP_MAD_MULTIPLE = 10.0

# ─────────────────────────────────────────────────────────────────────────────
# Per-event removal rules  (docs/AUDIT.md section 1 step 3)
# ─────────────────────────────────────────────────────────────────────────────
#: [P5] an epoch counts as observed only above this in-transit coverage ...
EVENT_MIN_COVERAGE = 0.5
#: [P5] ... and with at least this many out-of-transit baseline cadences.
EVENT_MIN_BASELINE_POINTS = 10
#: [P5] the local baseline half-window: this many durations ...
BASELINE_HALF_WINDOW_DURATIONS = 3.0
#: [P5] ... but never less than this, in days.
BASELINE_HALF_WINDOW_MIN_DAYS = 0.5
#: [P5] out-of-transit starts at this multiple of the half-duration.
OUT_OF_TRANSIT_MARGIN = 1.3
#: [P5] degree of the local SAP baseline polynomial.
BASELINE_POLY_DEGREE = 2
#: [P5] "within one duration" never means less than this, in days.
NEAR_EVENT_MIN_DAYS = 0.25
#: [P5] the same floor for an edge test, in days.
EDGE_MIN_WINDOW_DAYS = 0.2
#: [P5] a gap this long in the series is an orbit edge / a PDC-removed stretch.
EDGE_GAP_DAYS = 0.5
#: [P5] more than this fraction of in-transit cadences quality-flagged removes.
QUALITY_FLAG_FRACTION = 0.2
#: [P5] more than this fraction of near-transit cadences scattered-light
#: flagged removes.
STRAYLIGHT_FLAG_FRACTION = 0.2
#: [P5] the SAP baseline changing by more than this many candidate depths
#: across the event is a ramp.
SAP_RAMP_OVER_DEPTH = 1.0
#: [P5] a scattered-light ramp needs the background above this multiple of the
#: sector median ...
BKG_OVER_SECTOR_MEDIAN = 2.0
#: [P5] ... and changing by this fraction of the sector median across the
#: window (i.e. doubling).
BKG_CHANGE_OVER_MEDIAN = 1.0
#: [P5] the raw-SAP test applies only to a dip this significant in the
#: corrected flux ...
SAP_ABSENT_MIN_SIGMA = 5.0
#: [P5] ... and fires when the SAP depth is below this fraction of it.
SAP_ABSENT_RATIO = 0.3

# ─────────────────────────────────────────────────────────────────────────────
# Kept-event statistics and the Stage A criteria  (docs/REVET.md section 2)
# ─────────────────────────────────────────────────────────────────────────────
#: [P6] minimum number of kept events.
A_MIN_KEPT = 3
#: [P6] minimum kept-event SNR (weighted mean depth over its error).
A_MIN_SNR = 7.0
#: [P6] maximum share of the summed (depth/error)^2 carried by one event.
A_MAX_TOP_SHARE = 0.50
#: [P6] minimum kept-event SNR with the strongest kept event removed.
A_MIN_SNR_WO_TOP = 5.0
#: [P6] kept weighted depth, in units of the survey depth: lower bound ...
A_DEPTH_LO = 0.5
#: [P6] ... and upper bound.
A_DEPTH_HI = 2.0
#: [P6] per-event depths consistent with a constant at this p or above.
A_P_CONST = 1e-3
#: [P5] the ``events`` step's own advisory flag: more than this fraction of
#: observed events removed (never a Stage A criterion).
EVENTS_FLAG_EXCLUDED_FRACTION = 0.5
#: [P5] the ``events`` step's own advisory SNR flag (never a Stage A criterion).
EVENTS_FLAG_MIN_SNR = 7.0

# ─────────────────────────────────────────────────────────────────────────────
# Stage B: star-level tests  (docs/REVET.md section 2)
# ─────────────────────────────────────────────────────────────────────────────
#: [P6] only sectors at this cadence or faster can test a period.
B_MAX_CADENCE_S = 600.0
#: [P6] the sector must span at least this many candidate periods.
B_MIN_SPAN_PERIODS = 1.5
#: [P6] the deepest transit-length window must be shallower than this fraction
#: of the depth ...
B_DEPTH_FRAC = 1.0 / 3.0
#: [P6] ... while the noise of a window mean is below this fraction of it.
B_NOISE_FRAC = 1.0 / 5.0
#: [P6] a window counts only if this fraction of its cadences are present.
B_WINDOW_FILL = 0.6
#: [P6] Gaia RUWE above this flags the star.
B_RUWE = 1.4
#: [P6] Gaia ``ipd_frac_multi_peak`` above this per cent flags the star.
B_IPD_MULTI_PEAK = 10.0
#: [P6] Gaia ``astrometric_excess_noise_sig`` above this flags the star.
B_AEN_SIG = 2.0
#: [P5] a Gaia RV amplitude counts as evidence only above this multiple of the
#: per-epoch error.
B_RV_NOISE_MULTIPLE = 4.0
#: [P6] another accepted candidate on the star at this depth ...
B_DEEP_PPT = 30.0
#: [P6] ... or this multiple of the candidate's own depth flags a binary host.
B_DEEP_RATIO = 5.0
#: [P5] a neighbour within this many pixels counts for the dilution test.
B_NEIGHBOUR_PIXELS = 3.0
#: [P5] TESS pixel scale, arcsec.
PIXEL_ARCSEC = 21.0

# ─────────────────────────────────────────────────────────────────────────────
# Stage C: the blind search  (docs/REVET.md section 2)
# ─────────────────────────────────────────────────────────────────────────────
#: [P5] a blind TLS peak counts as a re-detection at this SDE or above.
C_SDE = 9.0
#: [P6] "within 1% of the survey period".
C_TOL = 0.01
#: [P6] a 2:1 / 1:2 alias passes only if its per-transit depths are consistent
#: at this p or above.
C_ALIAS_P_CONST = 1e-3
#: [P6] TLS oversampling for Stage C.
C_OVERSAMPLING_DEFAULT = 3
#: [P6] ... reduced to this when more than ``C_MANY_STARS`` stars reach it.
C_OVERSAMPLING_MANY = 2
#: [P6] the star count at which the cheaper oversampling is used.
C_MANY_STARS = 40
#: [P5] blind search period range, days.
C_PERIOD_MIN = 0.5
C_PERIOD_MAX = 110.0
# ── prompt-10 Part 2c (HANDOFF_P10.md 0.4) ─────────────────────────────────
#: [P10] (i) the robust statistic is consulted only when one ordinate carries more
#: than this fraction of the spectrum's centred variance (HIP 97166 b: 0.99864).
C_CONCENTRATION_TRIGGER = 0.5
#: [P10] (ii) a stronger unrelated peak blocks the survey period only when it has
#: at least this many covered transits; then the survey-period local SDE must
#: stay >= C_SDE after masking that signal.
C_RESIDUAL_MIN_TRANSITS = 3
#: [P10] (ii) the transit mask of a residual run, in durations either side of
#: every predicted mid-time of the stronger signal (the same one-duration rule
#: as the prepared detrend's MASK_DURATIONS_EITHER_SIDE below).
C_RESIDUAL_MASK_DURATIONS = 1.0

# ─────────────────────────────────────────────────────────────────────────────
# Prompt-7 option 1: the full-phase secondary scan
# ─────────────────────────────────────────────────────────────────────────────
#: [P7] a phase-scan dip counts only above this many sigma.  From the rank-16
#: re-analysis, which found the 52-sigma secondary at phase 0.605 the funnel
#: and the P4 packets (phase 0.5 only) both missed.
SEC_MIN_SIGMA = 5.0
#: [P7] two dips closer than this in phase are the same dip.
SEC_MIN_PHASE_SEPARATION = 0.02
#: [P7] the phase step of the coarse scan ...
SEC_PHASE_STEP = 0.002
#: [P7] ... and of the refinement around each dip, over +/- ``SEC_REFINE_HALF``.
SEC_REFINE_STEP = 0.0004
SEC_REFINE_HALF = 0.01
#: [P7] a dip this close to phase 0 (in either direction) is the primary.
SEC_PRIMARY_PHASE_TOLERANCE = 0.03
#: [P7] geometric albedo used for the reflected-light half of the planetary
#: bound (an upper limit, so the bound is a bound).
SEC_ALBEDO = 0.3
#: [P7] the gate: a second dip whose SAP depth exceeds the period-aware
#: planetary bound by more than this many sigma is a star-level FAIL.
SEC_GATE_SIGMA_OVER_BOUND = 3.0
#: [P7] more than this many dips at scattered phases is a variability flag,
#: not a secondary claim.
SEC_MAX_DIPS_BEFORE_VARIABILITY = 5
# ── prompt-10 Part 2a: the three measured gate modes (HANDOFF_P10.md 0.2) ──
#: [P10] ``empirical_bound``: the dip must exceed the bound by this many times
#: the scan's own off-phase scatter (the robust standard deviation of the SAP
#: box-depth track outside the primary exclusion and outside one box width of
#: the dip); the same 3 as the white-error gate, measured against a different
#: scatter.  The track needs at least this many points to define the scatter.
SEC_EMPIRICAL_SIGMA = SEC_GATE_SIGMA_OVER_BOUND
SEC_TRACK_MIN_POINTS = 20
#: [P10] ``recurrent_bound``: the per-event SAP box depth at the dip phase is at
#: least this many (white) sigma in at least this fraction of the covered
#: events (never fewer than this many events), OR the stacked depth is at least
#: this many sigma in each of two independent sector groups.  An event counts
#: as covered at this in-box coverage.
SEC_RECUR_EVENT_SIGMA = 2.0
SEC_RECUR_EVENT_FRACTION = 0.5
SEC_RECUR_MIN_EVENTS = 2
SEC_RECUR_GROUP_SIGMA = 2.0
SEC_EVENT_MIN_COVERAGE = 0.5
#: [P10] ``recurrent_bound_corr``: the dip must be present at this many sigma
#: in the SAP flux and in the corrected flux.
SEC_PRESENT_SIGMA = 3.0

# ─────────────────────────────────────────────────────────────────────────────
# Prompt-7 option 2: red-noise-inflated depth consistency
# ─────────────────────────────────────────────────────────────────────────────
#: [P7] per-sector beta is measured on residual bins of this fraction of the
#: candidate duration (the recipe already in ``audit_p5.fit_step``).
BETA_BIN_DURATION_FRACTION = 1.0 / 3.0
#: [P7] beta is clipped to this range, as in ``fit_step``.
BETA_MIN = 1.0
BETA_MAX = 5.0
#: [P7] a sector needs at least this many out-of-transit cadences to give a
#: beta; below it beta is 1.
BETA_MIN_POINTS = 60
#: [P7] and at least this many bins.
BETA_MIN_BINS = 3

# ─────────────────────────────────────────────────────────────────────────────
# Prompt-7 option 3: transit-masked detrending
# ─────────────────────────────────────────────────────────────────────────────
#: [P7] the biweight is fitted with points within this many durations of every
#: predicted mid-time masked out of the trend (and the trend interpolated
#: across them).  P6 measured the unmasked detrend returning 0.5-0.9 of the
#: survey depth for every clean signal in the population.
MASK_DURATIONS_EITHER_SIDE = 1.0

# ─────────────────────────────────────────────────────────────────────────────
# Prompt-7 option 4: the long-period window test
# ─────────────────────────────────────────────────────────────────────────────
#: [P7] the long-period test applies when no sector spans this many periods,
#: i.e. exactly where the Stage B window test has no power (P above ~17 d).
LONGP_MAX_SPAN_PERIODS = B_MIN_SPAN_PERIODS
#: [P7] a candidate whose predicted-and-observed epochs are removed in more
#: than this fraction of the sectors that predicted one is flagged, not killed.
LONGP_REMOVED_SECTOR_FRACTION = 0.5

# ─────────────────────────────────────────────────────────────────────────────
# Prompt-7: the v2 ranking score  (docs/RANKING_SCORE.md section 5)
# ─────────────────────────────────────────────────────────────────────────────
#: [P7] kept-event SNR at which the S_snr2 term saturates.
V2_SNR_SATURATION = 20.0
#: [P7] number of independent sectors showing the dip at which S_sec saturates.
V2_SECTORS_SATURATION = 4
#: [P7] a kept event counts towards the sector term above this many sigma.
V2_SECTOR_EVENT_SIGMA = 2.0
#: [P7] penalty per Gaia flag ...
V2_GAIA_FLAG_PENALTY = 0.25
#: [P7] ... and for a deep-event host.
V2_DEEP_HOST_PENALTY = 0.5

# ─────────────────────────────────────────────────────────────────────────────
# Prompt-10: the p10.0 verdict tiers (HANDOFF_P10.md section 0.1, docs/RULES.md
# section 9).  The rule code is tesshunter.verdict_tiers; every number is named
# here once.  [P10] = pre-registered in prompt 10 before any measurement.
# ─────────────────────────────────────────────────────────────────────────────
#: [P10] K5: an integer alias is one of these period ratios within TIER_ALIAS_TOL
#: (the ``_match`` list of ``scripts/audit_p5.py``; 1:1 is added for catalogue
#: periods, where the hard stop's own case is repeated so the record is complete).
TIER_ALIAS_RATIOS = {"2:1": 2.0, "1:2": 0.5, "3:1": 3.0, "1:3": 1 / 3, "3:2": 1.5, "2:3": 2 / 3}
TIER_ALIAS_TOL = 0.01
#: [P10] K5b / H4: catalogue periods are looked up within this radius (arcsec).
TIER_CATALOGUE_RADIUS_ARCSEC = 60.0
#: [P10] K6: odd/even depth difference above this many sigma kills, with at
#: least this many odd and even transits in the fit.
TIER_ODD_EVEN_SIGMA = 3.0
TIER_ODD_EVEN_MIN_TRANSITS = 2
#: [P10] K7a: the difference-image maximum pixel must lie within this many
#: pixels of a resolved Gaia neighbour and more than TIER_K7_TARGET_PX from the
#: target, at more than TIER_PIXEL_SIGMA times its event scatter.
TIER_K7_NEIGHBOUR_PX = 1.0
TIER_K7_TARGET_PX = 1.5
TIER_PIXEL_SIGMA = 3.0
#: [P10, amendment 0.11.5 of 2026-09-08] K7a's maximum is searched within this
#: many pixels of the target (the Stage B (ii) neighbour radius, B_NEIGHBOUR_PIXELS),
#: not over the whole 21 x 21 cutout, whose maximum is the largest of 441 noisy
#: pixels and lands on a resolved Gaia source by chance.  The whole-cutout
#: (literal) form is still recorded beside it on every record.
TIER_K7_SEARCH_PX = 3.0
#: [P10] K7 and K9 need this many sectors each.
TIER_MIN_SECTORS = 2
#: [P10] the fixed dilution allowance applied to the reference depth before the
#: absence (K7b) and too-shallow (K9b) comparisons (section 0.11 item 2).
TIER_DILUTION_ALLOWANCE = 0.5
#: [P10] K8: a fitted radius above this many Jupiter radii implies a stellar
#: companion (1 R_Jup = 11.209 R_Earth).
TIER_MAX_RADIUS_RJUP = 1.5
R_JUP_IN_R_EARTH = 11.209
#: [P10] K8: the density prior counts as rejected at this delta chi-square (3
#: sigma, one degree of freedom) ...
TIER_DENSITY_REJECT_DCHI2 = 9.0
#: [P10] ... and the fitted-over-catalogue density ratio must lie outside this
#: range (section 0.11 item 3).
TIER_DENSITY_RATIO_RANGE = (0.5, 2.0)
#: [P10] K9a: |Pearson r| between the raw aperture and sky series over the
#: event windows (this many fit durations either side of every event centre).
TIER_K9_CORRELATION = 0.7
TIER_K9_WINDOW_DURATIONS = 3.0
TIER_K9_MIN_POINTS = 10
#: [P10] H1: TRICERATOPS NFPP at or above this holds.
TIER_NFPP_HOLD = 0.5
#: [P10] H2: a grazing fit is unusable when the impact-parameter error exceeds
#: this or the duration error is at least the duration.
TIER_GRAZING_B_ERR = 0.5
#: [P10] H4: VSX classes on the target (within TIER_VSX_TARGET_RADIUS_ARCSEC)
#: that hold when no alias matches.
TIER_VSX_EB_CLASSES = ("EA", "EB", "EW", "ELL")
TIER_VSX_TARGET_RADIUS_ARCSEC = 21.0
#: [P10] F1: neighbours able to make the depth by total eclipse within this radius.
TIER_NEIGHBOUR_RADIUS_ARCSEC = 63.0
#: [P10] the fixed-aperture extractor needs at least this many sky pixels; a
#: sector below it is unmeasurable (K7b / K9b), never "no contamination".
TIER_MIN_SKY_PIXELS = 16

# ─────────────────────────────────────────────────────────────────────────────
# The rule sets
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RuleSet:
    """Which optional rules are on, and the version string that names the set.

    The four options are the prompt-7 fixes.  All off is ``p6.2``, exactly what
    prompts 5 and 6 ran; all on is ``p7.0``.  Any other combination is a
    measurement run and is stamped ``p7.0-partial`` so a mixed-vintage
    directory stays detectable.
    """

    secondary_scan: bool = False
    inflated_depth_consistency: bool = False
    transit_masked_detrend: bool = False
    long_period_window_test: bool = False
    # ── prompt-8 decision fields (defaults reproduce p7.0 exactly) ──────────
    #: Decision 1, the secondary gate.  "bound": p7.0, FAIL when the SAP depth of
    #: the deepest off-phase dip is > SEC_GATE_SIGMA_OVER_BOUND sigma above the
    #: planetary bound, whatever the scan looks like.  "quiet_bound": the same
    #: test, but only when the scan is quiet (at most ``secondary_quiet_max_dips``
    #: dips in total).  "quiet_zero": FAIL when the SAP depth is > 3 sigma above
    #: ZERO and the scan has at most ``secondary_quiet_max_dips`` dips.
    #: "quiet_bound_hold": "quiet_bound", and a variability-flagged scan
    #: (more than SEC_MAX_DIPS_BEFORE_VARIABILITY dips) demotes to HOLD.
    secondary_gate: str = "bound"
    secondary_quiet_max_dips: int = 2
    #: Decision 2, which depth-consistency p-value the gate reads ("white" or
    #: "inflated"; both are always on the record) and its threshold.
    depth_consistency_errors: str = "inflated"
    depth_consistency_p_min: float = A_P_CONST
    #: Decision 2/3, the red-noise beta cap (5 in p7.0; 2 and 3 measured in prompt 8).
    beta_max: float = BETA_MAX
    #: Prompt-7 finding 7: the Stage B record stores ``t14_hours`` and
    #: ``window_days`` unrounded so it can be replayed from its own fields.
    exact_t14_record: bool = False
    # ── prompt-10 fields (defaults reproduce p8.0 exactly) ──────────────────
    #: Part 1: "p8" keeps the Stage B flag cap and the p8.0 provisional verdict;
    #: "p10" evaluates the K1-K9 / H1-H4 tiers of tesshunter.verdict_tiers and
    #: stores the P8 cap as ``b_flag_cap_p8`` (no flag caps the verdict).
    verdict_tiers: str = "p8"
    #: Part 2c (ii): "strongest" is the p8.0 rule; "significant_peak" the
    #: measured variant.  Set in Part 2d after the measurement.
    stagec_peak_rule: str = "strongest"
    #: Part 2c (i): consult SDE_robust when one ordinate carries more than
    #: half of the spectrum's centred variance.  Set in Part 2d.
    stagec_sde_robust_fallback: bool = False
    #: Part 2c (iv): floor a reported TLS duration at one cadence before any
    #: matching or coverage rule (the raw value stays beside it).
    duration_floor_cadence: bool = False

    P8_FIELDS = ("secondary_gate", "secondary_quiet_max_dips", "depth_consistency_errors",
                 "depth_consistency_p_min", "beta_max", "exact_t14_record")
    P10_FIELDS = ("verdict_tiers", "stagec_peak_rule", "stagec_sde_robust_fallback",
                  "duration_floor_cadence")

    def p8_fields_at_default(self) -> bool:
        return all(getattr(self, k) == RuleSet.__dataclass_fields__[k].default for k in self.P8_FIELDS)

    def p10_fields_at_default(self) -> bool:
        return all(getattr(self, k) == RuleSet.__dataclass_fields__[k].default for k in self.P10_FIELDS)

    @property
    def version(self) -> str:
        on = (self.secondary_scan, self.inflated_depth_consistency,
              self.transit_masked_detrend, self.long_period_window_test)
        if P10_RULES is not None and self == P10_RULES:
            return "p10.0"
        if not self.p10_fields_at_default():
            return "p10.0-partial"
        if P8_RULES is not None and self == P8_RULES:
            return "p8.0"
        if not self.p8_fields_at_default():
            return "p8.0-partial"
        if not any(on):
            return "p6.2"
        if all(on):
            return "p7.0"
        return "p7.0-partial"

    @property
    def options(self) -> dict:
        return asdict(self)

    def with_options(self, **kw) -> "RuleSet":
        return replace(self, **kw)


#: [P8] Frozen from all 1,163 recovered injections and the preregistered reference
#: sets; see docs/RULES.md section 8 and data/survey/p8/decisions_p8.json.
#: Exact Stage B window fields distinguish this set while retaining p7.0 gates.
P8_RULES = RuleSet(secondary_scan=True, inflated_depth_consistency=True,
                   transit_masked_detrend=True, long_period_window_test=True,
                   secondary_gate="bound", secondary_quiet_max_dips=2,
                   depth_consistency_errors="inflated", depth_consistency_p_min=1e-3,
                   beta_max=5.0, exact_t14_record=True)

#: [P10] Part 2d freeze: retain bound and strongest-peak (a), enable the
#: conditional raw-power robust fallback and cadence duration floor, and use
#: the Part 1 verdict tiers. The complete C decision and its persistent
#: half/double-period limitation are in stage_c_adoption_20260911.json.
#: Other prompt-10 combinations remain explicitly ``p10.0-partial``.
P10_RULES = P8_RULES.with_options(verdict_tiers="p10", stagec_peak_rule="strongest",
                                stagec_sde_robust_fallback=True, duration_floor_cadence=True)

#: The frozen prompt-5 / prompt-6 rule set.  ``scripts/audit_p5.py`` and
#: ``scripts/revet_p6.py`` use it by default so their records reproduce.
LEGACY_RULES = RuleSet()

#: The prompt-7 default: the same rules with all four measured options on.
DEFAULT_RULES = RuleSet(secondary_scan=True, inflated_depth_consistency=True,
                        transit_masked_detrend=True, long_period_window_test=True)

#: Every version string this package can stamp.
KNOWN_RULES_VERSIONS = ("p6.2", "p7.0", "p7.0-partial", "p8.0", "p8.0-partial", "p10.0", "p10.0-partial")

#: Every named rule set by its version string.
NAMED_RULES = {"p6.2": LEGACY_RULES, "p7.0": DEFAULT_RULES, "p8.0": P8_RULES, "p10.0": P10_RULES}

#: The version of the package default.
RULES_VERSION = DEFAULT_RULES.version


def thresholds(rules: RuleSet | None = None) -> dict:
    """The whole threshold set as a dict, for stamping into a record.

    ``rules`` selects which option block is reported as active; the numbers
    themselves never change.
    """
    r = DEFAULT_RULES if rules is None else rules
    return {
        "rules_version": r.version,
        "options": r.options,
        "quality": {
            "default_bitmask": Q_DEFAULT, "hard_bitmask": Q_HARD,
            "desat_bit": Q_DESAT, "manual_bit": Q_MANUAL, "straylight_bits": Q_STRAYLIGHT,
            "qlp_low_precision_s1_55": QLP_LOW_PRECISION_S1_55,
            "qlp_low_precision_s56": QLP_LOW_PRECISION_S56,
            "qlp_flag_sector_split": QLP_FLAG_SECTOR_SPLIT,
        },
        "prepare": {
            "wotan_method": WOTAN_METHOD, "window_t14_multiple": WOTAN_WINDOW_T14_MULTIPLE,
            "window_min_days": WOTAN_WINDOW_MIN_DAYS, "window_max_days": WOTAN_WINDOW_MAX_DAYS,
            "break_tolerance": WOTAN_BREAK_TOLERANCE, "edge_cutoff": WOTAN_EDGE_CUTOFF,
            "upward_clip_sigma": UPWARD_CLIP_SIGMA, "isolated_dip_sigma": ISOLATED_DIP_SIGMA,
            "isolated_neighbour_sigma": ISOLATED_NEIGHBOUR_SIGMA,
            "min_points_per_product": MIN_POINTS_PER_PRODUCT, "bin_minutes": BIN_MINUTES,
            "bin_min_points_for_scatter": BIN_MIN_POINTS_FOR_SCATTER,
            "deep_clip_depth_multiple": DEEP_CLIP_DEPTH_MULTIPLE,
            "deep_clip_mad_multiple": DEEP_CLIP_MAD_MULTIPLE,
            "mask_durations_either_side": MASK_DURATIONS_EITHER_SIDE if r.transit_masked_detrend else None,
        },
        "events": {
            "min_coverage": EVENT_MIN_COVERAGE, "min_baseline_points": EVENT_MIN_BASELINE_POINTS,
            "baseline_half_window_durations": BASELINE_HALF_WINDOW_DURATIONS,
            "baseline_half_window_min_days": BASELINE_HALF_WINDOW_MIN_DAYS,
            "out_of_transit_margin": OUT_OF_TRANSIT_MARGIN,
            "baseline_poly_degree": BASELINE_POLY_DEGREE,
            "near_event_min_days": NEAR_EVENT_MIN_DAYS, "edge_min_window_days": EDGE_MIN_WINDOW_DAYS,
            "edge_gap_days": EDGE_GAP_DAYS, "quality_flag_fraction": QUALITY_FLAG_FRACTION,
            "straylight_flag_fraction": STRAYLIGHT_FLAG_FRACTION,
            "sap_ramp_over_depth": SAP_RAMP_OVER_DEPTH,
            "bkg_over_sector_median": BKG_OVER_SECTOR_MEDIAN,
            "bkg_change_over_median": BKG_CHANGE_OVER_MEDIAN,
            "sap_absent_min_sigma": SAP_ABSENT_MIN_SIGMA, "sap_absent_ratio": SAP_ABSENT_RATIO,
            "beta_inflation": {
                "bin_duration_fraction": BETA_BIN_DURATION_FRACTION, "beta_min": BETA_MIN,
                "beta_max": r.beta_max, "min_points": BETA_MIN_POINTS, "min_bins": BETA_MIN_BINS,
                "gate_reads": r.depth_consistency_errors,
            } if r.inflated_depth_consistency else None,
        },
        "stageA": {
            "min_kept_events": A_MIN_KEPT, "min_kept_event_snr": A_MIN_SNR,
            "max_top_event_share_of_snr2": A_MAX_TOP_SHARE,
            "min_snr_without_top_event": A_MIN_SNR_WO_TOP,
            "kept_depth_over_survey_depth": [A_DEPTH_LO, A_DEPTH_HI], "min_p_const": r.depth_consistency_p_min,
            "p_const_used": (r.depth_consistency_errors if r.inflated_depth_consistency else "white"),
        },
        "stageB": {
            "max_cadence_s": B_MAX_CADENCE_S, "min_span_periods": B_MIN_SPAN_PERIODS,
            "window_depth_fraction": B_DEPTH_FRAC, "window_noise_fraction": B_NOISE_FRAC,
            "window_fill_fraction": B_WINDOW_FILL, "ruwe": B_RUWE,
            "ipd_frac_multi_peak_pct": B_IPD_MULTI_PEAK, "aen_sig": B_AEN_SIG,
            "rv_noise_multiple": B_RV_NOISE_MULTIPLE,
            "deep_event_ppt": B_DEEP_PPT, "deep_event_ratio": B_DEEP_RATIO,
            "neighbour_pixels": B_NEIGHBOUR_PIXELS, "pixel_arcsec": PIXEL_ARCSEC,
            "long_period_window_test": {
                "max_span_periods": LONGP_MAX_SPAN_PERIODS,
                "removed_sector_fraction": LONGP_REMOVED_SECTOR_FRACTION,
            } if r.long_period_window_test else None,
        },
        "stageC": {
            "sde": C_SDE, "period_tolerance": C_TOL, "alias_min_p_const": C_ALIAS_P_CONST,
            "oversampling_default": C_OVERSAMPLING_DEFAULT,
            "oversampling_if_many": C_OVERSAMPLING_MANY, "many_stars": C_MANY_STARS,
            "period_min_days": C_PERIOD_MIN, "period_max_days": C_PERIOD_MAX,
        },
        "secondary": {
            "min_sigma": SEC_MIN_SIGMA, "min_phase_separation": SEC_MIN_PHASE_SEPARATION,
            "phase_step": SEC_PHASE_STEP, "refine_step": SEC_REFINE_STEP,
            "refine_half": SEC_REFINE_HALF, "primary_phase_tolerance": SEC_PRIMARY_PHASE_TOLERANCE,
            "albedo": SEC_ALBEDO, "gate_sigma_over_bound": SEC_GATE_SIGMA_OVER_BOUND,
            "max_dips_before_variability": SEC_MAX_DIPS_BEFORE_VARIABILITY,
            "gate_mode": r.secondary_gate, "quiet_max_dips": r.secondary_quiet_max_dips,
        } if r.secondary_scan else None,
        "ranking_v2": {
            "snr_saturation": V2_SNR_SATURATION, "sectors_saturation": V2_SECTORS_SATURATION,
            "sector_event_sigma": V2_SECTOR_EVENT_SIGMA,
            "gaia_flag_penalty": V2_GAIA_FLAG_PENALTY, "deep_host_penalty": V2_DEEP_HOST_PENALTY,
        },
        "tiers": tier_thresholds() if r.verdict_tiers == "p10" else None,
    }


def tier_thresholds() -> dict:
    """The p10.0 tier numbers, stamped into every tier evaluation."""
    return {
        "alias_ratios": dict(TIER_ALIAS_RATIOS), "alias_tolerance": TIER_ALIAS_TOL,
        "catalogue_radius_arcsec": TIER_CATALOGUE_RADIUS_ARCSEC,
        "odd_even_sigma": TIER_ODD_EVEN_SIGMA, "odd_even_min_transits": TIER_ODD_EVEN_MIN_TRANSITS,
        "k7_neighbour_px": TIER_K7_NEIGHBOUR_PX, "k7_target_px": TIER_K7_TARGET_PX,
        "k7_search_px": TIER_K7_SEARCH_PX,
        "pixel_sigma": TIER_PIXEL_SIGMA, "min_sectors": TIER_MIN_SECTORS,
        "dilution_allowance": TIER_DILUTION_ALLOWANCE,
        "max_radius_rjup": TIER_MAX_RADIUS_RJUP, "r_jup_in_r_earth": R_JUP_IN_R_EARTH,
        "density_reject_dchi2": TIER_DENSITY_REJECT_DCHI2, "density_ratio_range": list(TIER_DENSITY_RATIO_RANGE),
        "k9_correlation": TIER_K9_CORRELATION, "k9_window_durations": TIER_K9_WINDOW_DURATIONS,
        "k9_min_points": TIER_K9_MIN_POINTS, "nfpp_hold": TIER_NFPP_HOLD,
        "grazing_b_err": TIER_GRAZING_B_ERR, "vsx_eb_classes": list(TIER_VSX_EB_CLASSES),
        "vsx_target_radius_arcsec": TIER_VSX_TARGET_RADIUS_ARCSEC,
        "neighbour_radius_arcsec": TIER_NEIGHBOUR_RADIUS_ARCSEC, "min_sky_pixels": TIER_MIN_SKY_PIXELS,
    }


__all__ = ["RuleSet", "LEGACY_RULES", "DEFAULT_RULES", "P8_RULES", "P10_RULES", "RULES_VERSION",
           "KNOWN_RULES_VERSIONS", "NAMED_RULES", "thresholds", "tier_thresholds"]
