# TIC 404927114: scientific follow-up of the 27.5434-day signal

**Disposition: UNRESOLVED. Background and reduction effects are favored over a
stable transit on the target, but this investigation does not establish a unique
cause or identify an eclipsing contaminant. The original P8 HOLD remains unchanged.**

The strongest positive evidence concerns the background: at several predicted
events, the original aperture follows the diffuse field almost exactly, including
two large *brightenings* in sector 98. After fitting the spatial background and
image-registration terms, the target has only **0.77 ± 0.47 ppt** of mean dimming
(1.63 sigma). A search for displaced dimming within 90 arcseconds gives no
statistically persuasive location. Older TESS observations do not reproduce the
dip. These findings disfavor the simple, persistent, target-hosted transit model;
they do not prove that every component of the signal is instrumental.

![Comparison of reductions and older-epoch timing test](../followups/tic404927114/figures/evidence_comparison.png)

## Scope and provenance

Work began on a clean `improve/recovery` checkout at `fbc68571`. The handoff,
audit, target packet, Stage A–D records, physical fit, pixel/FPP records, catalogue
cone, review evidence and download-repair record were inspected. No applicable
`AGENTS.md` was found in the repository or its ancestor directories.

The separate [follow-up directory](../followups/tic404927114/) contains executable
code, initial diagnostic configuration, documented amendments, cached public
responses, measurements, figures and preserved failed attempts. No P8 input,
selection rule, packet or verdict was overwritten. Nothing was submitted externally.

All **12 locally cached 21×21 TESScut cubes** were inspected: sectors 61, 63, 66,
67, 68, 87, 88, 90, 93, 94, 95 and 98. The repaired download coverage is complete;
missing downloads are not the explanation. All **22 cached QLP sectors** were
examined, including ten older 600-second sectors, 27–29, 31–32, 34–35 and 37–39.
Those older sectors provide additional observing epochs outside the frozen P8
200-second search. This is not a claim to have downloaded every historical TESS
observation of this sky position.

The new Gaia and OGLE data are independent observations. QLP, the P8 flattened
series, and this pixel analysis are different reductions of TESS measurements,
not independent detections. TESScut supplies calibrated SPOC FFIs without sky
subtraction; these are not raw detector counts. QLP uses its own extraction and
TICA calibration. That distinction matters when interpreting disagreements.
[MAST product documentation](https://outerspace.stsci.edu/plugins/viewsource/viewpagesrc.action?pageId=14563420),
[QLP release notes](https://tess.mit.edu/qlp-update/).

## Association, clocks, ephemerides and apertures

The target is **Gaia DR3 4659930359605646592**. The saved Gaia position is
RA 85.13738487221609°, Dec −66.17304928262784° at epoch 2016.0, with proper
motion (+11.0813, +104.7774) mas/yr and parallax 10.0084 mas. Its motion explains
the approximately 1.69-arcsecond difference from the TIC J2000 position. The QLP
header's original 2015.5 position and proper motion support the same association.
The separate cached `tic_gaia_id = 4659930359605646336` is rounded by 256; it is
not used as an exact identifier in this follow-up. Gaia IDs are preserved as strings.

| Saved interpretation | Period (days) | Epoch (BTJD) | Recorded width (hours) |
|---|---:|---:|---:|
| Survey / chosen Stage A | 27.543625333557717 | 2987.9321157158965 | 1.3356285131 |
| Stage A forced alternative | 27.542975244795223 | 2987.9292326166164 | 1.3356285131 in the event audit |
| Blind Stage C TLS | 27.543652012259667 | 2987.9256064131628 | 0.5987567392 reported by TLS |
| Adopted physical fit | 27.543390052635324 | 2987.928697498805 | 2.899 |

The forced TLS output separately reported a 0.5753356-hour duration. Stage A
applied the survey width to that alternative epoch/period. The physical-fit seed
used the blind period and epoch but retained the survey width as seed metadata.
TLS's reported duration is not silently treated as a physical first-to-fourth
contact duration. The [exact recovered ephemerides](../followups/tic404927114/measurements/ephemerides.json)
and [per-event differences](../followups/tic404927114/measurements/ephemeris_event_comparison.csv)
preserve these distinctions.

The fit quotes σ(P) = 0.0002485035541 days and σ(T0) = 0.006997371079 days;
its epoch–period covariance was not saved. At cycle 38, the survey prediction is
17.80 minutes later than the fit and the forced prediction 21.93 minutes earlier.
The propagated one-sigma timing error is 16.92 minutes if covariance is zero, or
at most 23.67 minutes allowing the covariance permitted by those marginal errors.
The original period/epoch searches do not supply equivalent formal uncertainties.

QLP TIME is BJD in TDB minus 2457000. TESScut headers also say TDB, but its
barycentric correction refers to the CCD centre, not this target. Across the
12 cubes, QLP minus TESScut exposure times range from −56.93 to +62.37 seconds.
Every pixel exposure was uniquely matched to a QLP exposure within 90 seconds,
then assigned that target-corrected time. Astrocut CADENCENO is zero, so it could
not be used for the match. The time convention is documented by
[MAST](https://outerspace.stsci.edu/plugins/viewsource/viewpagesrc.action?pageId=14563420).

The inherited P8 quality convention is SPOC mask 17087 **plus** QLP's
low-precision bit, 2^30 from sector 56 and 2^12 earlier. The final pixel mask is
the union of those QLP exclusions and the FFI default exclusions. A plain 17087
attempt and an overly strict all-nonzero QLP attempt are both preserved; neither
sets the final answer. The FITS and saved audit NPZ time/quality arrays agree.
See [diagnostic history](../followups/tic404927114/diagnostic_history.md) and the
[quality amendment](../followups/tic404927114/config_amendment_quality.json).

QLP aperture parameters are read from each original header, not assumed to be
constant. For example, sector 63 has BESTAP `2.5:4.0:3.0`, SMALLAP
`1.75:4.0:3.0`, and LARGEAP `3.0:4.0:3.0`. All values are in
[QLP metadata](../followups/tic404927114/measurements/qlp_metadata.json).
The new raw-aperture trace uses radius 2.5 pixels at the propagated target; its
absolute flux is not directly equated with normalized QLP SAP. The old
radius-one aperture / 5–9-pixel annulus diagnostic had only one available sky
pixel. Its minimum requirement was not lowered.

## Crowded-field method and its validation

Diagnostic choices were recorded before new pixel measurements in
[config.json](../followups/tic404927114/config.json). The primary analysis uses the
fixed physical ephemeris, a 2.899-hour box, and a ±0.4-day local window. Each
pixel gets a linear time baseline plus a signed transit coefficient. The shoulders
between 0.5 and 0.75 transit durations from centre are omitted. At least 65% of
the expected in-event exposures and 15 clean points on each flank are required.

The resulting difference image is fitted jointly with a source PRF and spatial
nuisance terms: constant, x, y, x², xy, y², the reference image, and its two first
spatial derivatives. The derivatives model small pointing displacements without
resampling the pixels. Constant neighbouring stars cancel in the temporal
contrast. A second test explicitly fits the target and its closest neighbour
simultaneously. This procedure does not require star-free pixels.

Source models use the mission's 117×117, nine-samples-per-pixel PRFs from
`start_s0004`, interpolated across detector position and subpixel phase. The
out-of-event reference image sets a common WCS translation and nonnegative
fluxes for Gaia sources brighter than G=18.5, together with quadratic sky.
Translations are about 0.15 pixel or less. Proper motions are propagated to
each sector's observing epoch; missing motions are set to zero and flagged.
Annual parallax and motion within a sector are below the useful localization
precision here. [PRF documentation](https://outerspace.stsci.edu/plugins/viewsource/viewpagesrc.action?pageId=14563420).

The target reference flux ranges from approximately 716 to 864 electrons/s in
the six usable-event sectors. Depths labelled "target-referenced" divide the
measured differential flux by this fitted flux. This accounts for detector
response and aperture throughput within the adopted model; it is not a precise
independent measurement of dilution or an intrinsic depth for a different star.
Faint omitted stars and PRF colour/model errors remain limitations.

Per-pixel weights include the delivered errors and observed reference-frame
variations. Temporal errors are checked with half-hour residual blocks. Eighty
off-event windows per sector measure the actual correlated-noise scatter. The
source-map comparison uses 2,000 control stacks; the two sector-98 events use
control pairs separated by approximately their real interval. These controls
calibrate this diagnostic, not the false-alarm probability of the original blind
search. Reusing related controls limits their effective sample size.
The quoted inverse-variance mean error treats separate event coefficients as
independent; it is a conditional summary, and residual cross-event covariance
could widen it. The paired-control source-map test partly addresses this issue
for the two events sharing sector 98.

**Spatial validation:** 864 artificial flux-loss experiments were inserted into
original pixel windows in sectors 63, 90 and 98. Positions included the target,
nearby stars and the OGLE binary. Each was recovered using the same extraction
and source search. Trials included both the nominal PRF and a PRF broadened by
0.15 pixel and displaced by (0.12, −0.09) pixel. For 4.5-ppt target injections,
34/36 nominal and 32/36 altered-PRF trials exceeded three control sigma and
localized within 0.5 pixel. The altered-PRF target flux increment averaged
96.2% of the injected increment; its 90th-percentile position error was about
0.42 pixel, or 8.8 arcseconds. That accuracy cannot distinguish stars separated
by only 4.6 arcseconds.

Not all large artificial flux losses can physically be supplied by a faint
star: 336/864 exceed the estimated total stellar flux. They are retained as
spatial stress tests, **not counted as physically plausible eclipses**. The
[qualified injection table](../followups/tic404927114/measurements/injections_with_physical_limits.csv)
records the flux assumption for every trial. A supplementary test inserts an
actual 50% eclipse on Gaia 4659942076276901120, roughly 15 arcseconds away,
using its measured reference flux. Altered-PRF recovery retains 92.8–105.1% of
that differential signal across the six real event windows.

The saved limb-darkened physical transit was also exposure-integrated with
`batman` and inserted at each of the six **actual** event windows. Expected
contrast was 2.64–3.25 electrons/s. Altered-PRF extraction retained 92.9–100.2%
of it, including the strong sector-98 background changes. These tests show that
the adopted subtraction need not erase a transit of the fitted size. Exact-model
increment recovery of unity follows from the linear estimator and is not, by
itself, independent validation. The blind position recovery and imperfect-model
tests provide the more informative checks.

![Spatial injection validation](../followups/tic404927114/figures/injection_validation.png)

## What happens at the individual events?

There are 14 predicted centres inside the 12 pixel-sector spans. Six satisfy the
new two-sided clean-coverage requirement. Sector 61 and sector 93 lack a clean
post-event flank; sector 61 also retains only 61% in-event coverage. The later
sector-66 event and sectors 67, 68 and 94 are quality-excluded; sectors 87 and
88 miss the event in gaps. These are not missing downloads and are not proofs
that the source failed to transit.

| Sector / cycle | Target depth (ppt) | Conservative error (ppt) | Raw aperture vs sky correlation | Median pixel contrast (e/s) |
|---|---:|---:|---:|---:|
| 63 / 1 | 1.606 | 1.149 | 0.99989 | +3.204 |
| 66 / 4 | 0.460 | 1.189 | 0.93139 | +0.088 |
| 90 / 28 | 0.694 | 0.977 | 0.99783 | −2.626 |
| 95 / 33 | −0.119 | 1.198 | 0.94430 | +0.378 |
| 98 / 37 | 1.065 | 1.212 | 0.99954 | −21.406 |
| 98 / 38 | 0.867 | 1.223 | 0.99841 | −10.944 |

Positive contrast means dimming. The sector-98 raw apertures **brighten** by
approximately 406 and 206 electrons/s relative to their local baselines. Those
changes track the sky and dwarf the approximately three electrons/s expected
from the fitted target transit. Removing the diffuse modes leaves weak mixed
residuals. With this wider baseline, sector 90's contrast has the opposite sign
from the earlier narrow-flank P8 diagnostic, another indication that the
background result depends on the event/baseline definition.

The weighted target result is **0.766 ± 0.469 ppt**. Its nominal Gaussian
95% interval is −0.153 to 1.684 ppt, conditional on the source/background model;
it is not an unconditional planet exclusion limit. Leaving out any one event
gives means between 0.60 and 0.93 ppt. Plane-background and no-registration
sensitivity runs also leave a weak target result. Survey/forced/blind-width
results are preserved rather than substituted for the primary measurement.

The strongest sky-map point is approximately 25.2 arcseconds west and 16.8
arcseconds north of the target, at only 3.04 empirically scaled sigma. **11.2%
of control stacks have a stronger positive maximum** somewhere in the same
90-arcsecond search region. It does not identify a stellar source, and a
source-position confidence ellipse would be misleading.

The closest Gaia source, **4659930359567234304**, lies about 4.54–4.60 arcseconds
from the target during these observations. Its PRF correlates with the target's
at 0.93–0.96. Fitting both amplitudes raises formal target errors by factors
2.7–3.6. Unconstrained fits exchange target brightening for neighbour dimming,
sometimes requiring more light than that faint neighbour can supply. Those
solutions are evidence of a degeneracy, not a detection of an eclipsing binary.
See [joint fits](../followups/tic404927114/measurements/joint_nearest_source.csv).

![Source search, controls and individual depths](../followups/tic404927114/figures/source_localization_and_controls.png)

Figures retain all individual windows, including failures:
[events 1–6](../followups/tic404927114/figures/individual_events_1.png),
[events 7–12](../followups/tic404927114/figures/individual_events_2.png),
[both sector-98 events](../followups/tic404927114/figures/individual_events_3.png),
[reference/raw/residual images](../followups/tic404927114/figures/event_difference_images.png).

The inherited 28.7-sigma centroid is not a source localization. In addition to
its susceptibility to diffuse background, the saved implementation averages
detector-column and detector-row shifts across sectors without rotating them
to a common sky frame. This follow-up uses sky coordinates for its combined
source map. The original centroid measurement is preserved.

## Light curves, additional epochs and competing periods

Using identical fixed physical event windows and local baselines, the six
usable recent QLP events give:

| Series | Mean depth ± error (ppt) | Diagnostic S/N |
|---|---:|---:|
| QLP SAP | 1.391 ± 0.708 | 1.97 |
| QLP SYS_RM | 1.516 ± 0.697 | 2.18 |
| QLP DET | 3.432 ± 0.661 | 5.20 |
| New target PRF | 0.766 ± 0.469 | 1.63 |
| Older QLP SAP, eight events | −0.233 ± 0.574 | −0.40 |
| Older QLP corrected, eight events | −0.218 ± 0.568 | −0.38 |

These are correlated reductions and cannot be multiplied as independent
likelihoods. Nevertheless, the increase after detrending is measured positive
evidence of reduction dependence. At the shorter survey width, recent QLP DET
is 4.820 ± 0.846 ppt. Its strongest event supplies 37% of positive event S/N²;
removing it leaves S/N 4.19. Recent SAP's leading event supplies 57% at that
width, and 73% at the physical width. The detection is not solely a single
event, but event concentration and reduction choice matter.

Eight usable predicted events in the ten older QLP sectors fail to reproduce
a dip. A 49-point grid spanning ±3 quoted epoch and period uncertainties gives
no positive combined S/N above **0.44**. This weakens an unchanged transit
ephemeris/depth interpretation. It is not a universal exclusion: older
extractions, cadence, dilution, variable-source behaviour and transit timing
variations are not all calibrated by this check. See
[older individual events](../followups/tic404927114/figures/older_individual_events.png),
[all sectors](../followups/tic404927114/figures/all_qlp_sectors.png), and
[uncertainty grid](../followups/tic404927114/measurements/older_ephemeris_grid.csv).

There is no corresponding set of extra eclipses at half phase: recent QLP
gives 0.016 ± 0.618 ppt in five testable windows. The two additional P/3 phase
sequences give 0.519 ± 0.358 and 0.142 ± 0.361 ppt. These extra-phase errors
use residual block estimates rather than a separately calibrated alias search.
They do not support equal-depth P/2 or P/3 repeats. A binary at 2P with unequal
eclipses, or changing stellar variability, is not excluded. The saved TLS
secondary peaks at 82.1286, 67.8371 and 54.7594 days are retained; their high
SDE values are not evidence that those are independent periodic sources.

Per-sector variability and background periodograms often peak around 11–16
days and vary by sector. Gaia's ROT/SOLAR_LIKE classification does **not** give
a catalogue rotation period: the fresh rotation-modulation-table query returns
no row. No stable 27.5434-day stellar rotation period was established.
[Periodogram figure](../followups/tic404927114/figures/variability_and_background_periods.png).

TESS's usual two-orbit sector is about 27 days, and from sector 56 it pauses
at both perigee and apogee. Sector 98 spans four orbits, explaining its two
candidate cycles; treating it as an ordinary single-cycle sector is wrong.
[Mission observing conventions](https://tess.mit.edu/observations/),
[sector 98](https://heasarc.gsfc.nasa.gov/docs/tess/sector98_summary.html).
The downloaded contact and FFI-accumulation tables were compared with the
predictions. Events do not all occupy a common distance from a gap/contact;
sectors 87/88 are unobserved at the predicted phase. Proximity of 27.5434 days
to a mission/lunar timescale alone is insufficient to declare an alias. The
sector-98 mission notes flag scattered light mainly in other cameras; attribution
of this camera-4 background specifically to Earth or Moon is therefore not made.

## Independent catalogues and photometry

The fresh Gaia 90-arcsecond cone contains only the target with a VARIABLE flag;
the Gaia eclipsing-binary-table cone returns no row. Catalogue incompleteness
prevents treating that as an absence of nearby variables.

Independent **Gaia epoch photometry** was retrieved: 166 epochs, 114 after the
stated conservative rejection flags. Times were converted from BJD_TCB −2455197.5
to the TESS TDB convention. The G-band robust scatter is 0.0090 magnitude,
consistent with variability; just **one** good epoch falls inside the nominal
transit window. It cannot test repeatable three-hour eclipses. A sparse-sampling
periodogram has its largest peak around 32.44 days, not the candidate period;
this exploratory peak is not assigned as the rotation period.
[Gaia time/flag documentation](https://gea.esac.esa.int/archive/documentation/GDR3/Gaia_archive/chap_datamodel/sec_dm_photometry/ssec_dm_epoch_photometry.html),
[figure](../followups/tic404927114/figures/independent_gaia_photometry.png).

The known neighbour **OGLE-LMC-ECL-36904**, 45.48 arcseconds from the TIC
position, has independent OGLE-IV I-band photometry and catalogue period
**1.4769968 days**, HJD eclipse epoch 2460000.7092, and primary/secondary depths
0.284/0.173 magnitude. The candidate period is about 18.65 times that value,
and candidate events sample different OGLE orbital phases. This known binary
is not a supported explanation for the 27.5434-day sequence. OGLE HJD and TESS
BJD were not equated for precision timing; the coarse phase mismatch is much
larger than that distinction. [OGLE catalogue](https://www.astrouw.edu.pl/ogle/ogle4/OCVS/lmc/ecl/),
[independent light curve](../followups/tic404927114/figures/independent_ogle_binary.png).

The saved TRICERATOPS FPP=0.201585 and NFPP=0.169895 remain conditional on its
astrophysical scenarios. They cannot establish that these dips are astrophysical,
resolve the demonstrated background effects, or outweigh the localization result.

## Remaining degeneracy and what would resolve it

The unresolved question is whether weak stellar dimming is superposed on the
large background changes, or whether variable background and the QLP correction
produce the entire selected sequence. No repeatable point source is detected
strongly enough to decide that question. The simple approximately 3.75-ppt
target-transit model is disfavored by the validated extraction and older epochs.
A much weaker target or blended-neighbour signal remains possible. No named
neighbour has positive evidence supporting it as the 27.5434-day source.

Existing data can still help: reproduce QLP's relevant extraction directly on
the corresponding TICA frames, compare with these SPOC frames exposure by
exposure, and use a larger field to fit an empirical, time-dependent PRF and
non-polynomial background. Additional archived TESS epochs and older-sector
pixels could add independent cycles and constrain dilution. These analyses can
test the calibration/background origin; none is guaranteed to identify a
subpixel stellar source at the current signal strength.

The clearest new observation is simultaneous differential photometry resolving
the target and its 4.6-arcsecond neighbour, plus the surrounding field. An image
FWHM around 2 arcseconds or better, roughly 1-ppt binned precision on the target,
and a 6–8-hour sequence covering the predicted three-hour event and both
baselines would test the remaining ambiguity. Repeat at a second predicted
epoch. The ephemeris is unconfirmed, so include its propagated timing uncertainty
and obtain an off-event control sequence. Repeated dimming on one resolved star
would identify the host; consistent absence with sufficient sensitivity would
disfavor the stellar interpretation without relying on a TESS extraction failure.

No candidate promotion or definitive rejection is made. This follow-up narrows
the evidence toward background/correction contamination while retaining the
scientifically necessary **UNRESOLVED** disposition.

## Reproduction and verification

Run the commands in the [README](../followups/tic404927114/README.md) from the
repository with its existing astronomy environment. The
[audit manifest](../followups/tic404927114/audit_manifest.json) records
hashes of original P8 evidence, all 12 pixel cubes, all 22 original QLP files,
public archive files and follow-up code. Numerical invariants and input-preservation
checks are in `verify_followup.py`; all eight check groups passed, with
[verification results](../followups/tic404927114/measurements/verification.json)
saved alongside the measurements. Figure review covered individual windows, raw/residual images,
source maps, injections and independent photometry. Production survey tests were
not rerun because production code was not changed.
