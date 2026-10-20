# Independent audit of the top-10 survey candidates (prompt 5)

Date: 2026-09-03. Branch `improve/recovery`. Auditor stance: every candidate
is a false positive until the audit fails to prove it. The pipeline finds
candidates; nothing in this document is a detection, and nothing was submitted
anywhere. The human reads this, opens the packets, and decides.

Evidence tags: [M] measured in this audit, [P4] a number taken from the P4
packets or case files, [A] adopted assumption or threshold.

Everything the audit measured is under `data/survey/p5/` (one JSON per step
and candidate) and was produced by `scripts/audit_p5.py`, which shares no
light-curve code with the survey pipeline: its own MAST cache, its own
detrending (wotan), its own search (Transit Least Squares), its own per-event
bookkeeping, its own Gaia / SIMBAD / VSX queries. Only the hard-stop
cross-match reuses the package, because the six catalogs and their version
stamps live there.

## 1. What was done to each candidate

1. **Fresh download** [M]. `LIGHTKURVE_CACHE` pointed at an empty directory
   (`data/cache/audit_lightkurve`); every SPOC 2-minute, TESS-SPOC and QLP
   light curve of the star was downloaded again from MAST with
   `quality_bitmask="none"` so that every cadence and its flags are available.
   12 stars, 506 products, 0 download failures, 9 minutes.
2. **Blind re-detection with a different method** [M]. One product per
   sector (SPOC 2-min, else TESS-SPOC, else QLP), default quality mask,
   normalised per product, detrended per product with a wotan biweight of
   window 3 x the central-transit duration at the candidate period
   (floor 0.75 d, cap 1.5 d), upward outliers clipped at 4 sigma, binned to
   30 minutes, then Transit Least Squares over 0.5 to 110 d with
   oversampling 3 (290,000 trial periods on a 1,979-d baseline) and 20
   threads. Three preprocessing rules were added after the first pass and
   every candidate was re-run under them [A]: QLP's own low-precision flag
   (2^12 in sectors 1-55, 2^30 from sector 56, the flag the survey's
   `ffi.py` also masks) is applied to QLP products; isolated single-cadence
   dips (a point more than 6 sigma low between two normal neighbours, which
   no transit at these periods can produce) are dropped; and binned points
   deeper than 3 x the candidate depth (or 10 MAD) are dropped, so that
   eclipses of a binary host or multi-cadence garbage cannot dominate the
   spectrum the candidate is tested in (TLS fits sub-cadence "transits" of
   arbitrary depth to such points). The counts removed are recorded per
   candidate. The candidate PASSES only if the strongest TLS peak is within
   1% of the survey period at SDE >= 9 (an exact 2:1, 1:2 or 3:1 alias
   within 1% at SDE >= 9 is recorded as ALIAS; a match or alias below SDE 9
   is WEAK); otherwise it is downgraded (FAIL). The TLS power at the survey
   period and the rank of that period among the peaks are recorded either
   way. A second, narrow TLS (+/- 1.5% around the survey period) is run only
   to get a whole-baseline ephemeris and TLS's per-transit depths; it is not
   a detection.
3. **Every event in the raw SAP flux** [M]. For each predicted transit epoch
   over the full baseline (survey ephemeris, P4 packet ephemeris and the
   forced-TLS ephemeris, each examined separately), the product that
   observed it is opened with all cadences. The event is measured twice: in
   the detrended corrected flux (the TLS input) and in the raw SAP flux
   against a local quadratic baseline fitted to the out-of-transit cadences
   within +/- max(3 durations, 0.5 d). An event is REMOVED when any of the
   following holds [A]:
   * a momentum dump (quality bit 32) within one duration of mid-transit;
   * mid-transit within one duration of a sector edge or an orbit gap
     (> 0.5 d) of the SAP series, or within one duration of a gap PDC cut
     out of the corrected flux;
   * more than 20% of the in-transit cadences carry a default-bitmask
     quality flag, or more than 20% of the cadences within one duration
     carry the scattered-light flags (bits 2048, 4096);
   * a scattered-light ramp: background above 2 x the sector median and
     doubling across the window, or the SAP baseline changing by more than
     one candidate depth across the event;
   * the dip is significant (> 5 sigma) in the corrected flux but absent in
     the SAP flux (SAP depth below 30% of the corrected depth), i.e. it was
     made by the PDC correction.
   The SNR is then recomputed from the kept events as the inverse-variance
   weighted mean depth over its error, for the detrended flux and for the SAP
   flux separately.
4. **Depth consistency** [M]. Chi-square of the kept per-event depths about
   their weighted mean; the share of the summed (depth/error)^2 carried by the
   single strongest event; the SNR without that event. A candidate whose
   strongest event carries more than half of the signal, or whose SNR falls
   below 7 without it, is "carried by one event" and downgraded.
5. **Gaia DR3, SIMBAD, VSX** [M]. One ADQL cone of 1 arcmin on
   `gaiadr3.gaia_source` joined to `vari_classifier_result`: the target's
   RUWE, `phot_variable_flag`, `non_single_star`, `ipd_frac_multi_peak`,
   astrometric excess noise, `rv_amplitude_robust`, and every neighbour's
   magnitude and separation. For each neighbour the largest depth it could
   produce in the aperture if totally eclipsed is f/(1+f) with f its flux
   ratio to the target (Gaia RP where available, else G); neighbours within
   3 pixels (63 arcsec) bright enough to make the candidate depth are
   counted. SIMBAD object types and VSX entries within 1 arcmin. The Gaia RV
   amplitude is compared with the expected peak-to-peak scatter of the
   epoch RVs (about 4 x the per-epoch error, itself the quoted error times
   the square root of the number of transits) before it is called evidence.
6. **Hard stop again** [M]. The six catalogs (TOI, CTOI, NASA PS and
   PSCompPars, SPOC TCE, TESS EB) were re-downloaded at 13:39-13:44 UTC and
   the target and every TIC neighbour within the match radius were checked.
7. **The P4 case file last.** Read after steps 1-6 were measured; agreement
   and disagreement stated per candidate.

Thresholds not listed in the prompt (the 1% TLS tolerance is the prompt's;
the 20% flag fractions, the 2x background, the 30% SAP ratio, the 50% share
and SNR 7 are this audit's [A]) are stated once here and applied identically
to all ten.

## 2. Summary table

All numbers [M]; every candidate was processed by the same final code
(`data/survey/p5/audit_summary.json`). "SDE at P" is the maximum TLS SDE
within 1% of the survey period. "Clean events" is the inverse-variance
weighted mean depth of the kept events in the detrended corrected flux
under the ephemeris that gives the candidate the most credit.

| P4 rank | TIC | P (d) | survey depth (ppt) [P4] | blind TLS: strongest peak | SDE at P | TLS verdict | events observed / kept | clean events (ppt) | Gaia on the target | hard stop | verdict |
|---:|---:|---:|---:|---|---:|---|---|---:|---|---|---|
| 1 | 233211748 | 65.008 | 2.0 | 20.06 d, SDE 2.2 | 1.4 | FAIL | 13 / 6 | 0.20 +/- 0.05 | RUWE 0.87 | CLEAN | KILL |
| 2 | 212261364 | 8.954 | 7.4 | 12.25 d, SDE 10.3 (1 event) | 4.4 | FAIL | 13 / 7 | 0.19 +/- 0.14 | RUWE 1.15 | CLEAN | KILL |
| 3 | 160619045 | 91.664 | 2.0-4.3 | 10.79 d, SDE 10.4 (rotation harmonic) | 6.3 | FAIL | 11 / 6 | 0.10 +/- 0.05 | VARIABLE, SOLAR_LIKE; VSX ROT | CLEAN | KILL |
| 4 | 334678787 | 46.206 | 6.5 | 38.55 d, SDE 10.2 | 6.5 | FAIL | 19 / 14 | 0.05 +/- 0.04 | RUWE 0.81 | CLEAN | KILL |
| 5 | 290350156 | 13.203 | 10.6 | degenerate (0 transits), SDE 28 | 2.5 | FAIL | 12 / 6 | 0.54 +/- 0.21 | RUWE 1.31 | CLEAN | KILL |
| 6 | 21124154 | 89.228 | 0.8 | 97.5 d, SDE 9.4 | 6.5 | FAIL | 11 / 3 | 0.18 +/- 0.08 | RUWE 3.19 | CLEAN | KILL |
| 7 | 356976754 | 11.789 | 4.0 | 0.7368 d, SDE 58.3 (P = 16.00 x) | 4.1 | FAIL | 80 / 65 | 3.05 +/- 0.07 (varying) | RUWE 0.91 | CLEAN | KILL |
| 8 | 246937997 | 2.457 | 12.4 | 0.8197 d, SDE 6.8 (harmonics of 4.92 d) | 6.0 | WEAK | 63 / 46 | sinusoid; odd/even 5 sigma | 1.1-arcsec companion; VSX ROT, Em* | CLEAN | KILL |
| 9 | 167304394 | 22.780 | 59 | 22.7797 d, SDE 376 | 376 | PASS | 41 / 26 | 45.16 +/- 0.07 | equal pair at 0.4 arcsec, multi-peak 95% | CLEAN | KILL (EB) |
| 10 | 233200485 | 70.681 | 1.5 | 85.61 d, SDE 15.1 | 6.7 | FAIL | 13 / 11 | 0.50 +/- 0.12 | RUWE 20.7 | CLEAN | KILL |
| 14 | 284191194 | 73.719 | 2.7 | 79.23 d, SDE 8.6 | 8.3 | FAIL | 13 / 9 | 0.04 +/- 0.07 | RUWE 7.21 | CLEAN | KILL |
| 19 | 200658220 | 26.091 | 78.8 | 98.90 d, SDE 30 (1 event) | 2.7 | FAIL | 9 / 8 | 0.34 +/- 0.30 | RUWE 1.05 | CLEAN | KILL |

Reading the table: no candidate passes the blind re-detection at its survey
period except rank 9, whose signal is real and is an eclipsing binary. Every
other survey signal, once the events that coincide with dumps, edges,
scattered-light ramps, quality flags or PDC gaps are removed, leaves a set of
clean events whose weighted depth is consistent with zero or far below the
depth the survey reported.

Two systematic causes account for most of the top ten [M]:

* **Dips manufactured by the flux correction.** In TESS-SPOC PDCSAP light
  curves of the northern continuous-viewing-zone stars (ranks 1, 3, 4, 6),
  several-ppt dips appear in the corrected flux immediately before a stretch
  that PDC removed (a NaN gap of 0.5 d or more), during scattered-light
  surges (quality bits 2048/4096 set), while the raw SAP flux of the same
  cadences is flat. Sectors 15, 19, 74, 76 and 82 produced them on three
  different stars 0.6-1.5 degrees apart. QLP's detrended flux does the same
  at the onset of scattered-light ramps (rank 5's sector 102, extra TIC
  200658220's sector 102). The survey pipeline searched corrected or
  detrended flux and never looked at SAP, so these events entered as
  transits and, on a 30-minute stitch with a large red-noise beta, a single
  one of them was enough to carry a whole-stitch signal.
* **The whole-stitch re-measurement counted eclipses of a binary host and
  garbage cadences as transits.** Ranks 2 and 10 (hosts with 7-9% eclipses)
  and rank 5 (QLP low-precision cadences) reached the top ten on stitch SNRs
  of 120-124 that the independent data do not reproduce at all.

## 3. Results per candidate

Order is the P4 final rank. "Survey" numbers are [P4]; everything else is
[M] unless tagged. Per-event depths are in the wotan-detrended corrected
flux ("det") and the raw SAP flux ("SAP"); "kept" means after the removals
of section 1 step 3.

### Rank 1: TIC 233211748, P = 65.008 d

* Survey: long-period stitch search, BLS SNR 71.8, 15 transits, 2.0 ppt box
  with the duration railed at the 12-h cap; FPP 0.000; centroid 0.009 px at
  27 sigma; packet fit on the grazing rail (b = 1.2, Rp/R* 0.26 +/- 39);
  final verdict ambiguous. Frozen-score rank 1 with the maximum score 4.00.
* TLS: **FAIL.** The spectrum is featureless: strongest peak 20.06 d at SDE
  2.2; SDE within 1% of 65.0 d: 1.4. (Before the QLP low-precision flag was
  applied, a single 33-ppt spike in the QLP-only sector 50 gave an 81.2-d
  peak at SDE 14; that spike is also in the survey's data.)
* Events (survey ephemeris, 12-h duration): 31 predicted, 13 observed, 7
  removed, 6 kept; kept depth 0.20 +/- 0.05 ppt (SNR 4.2; 2.9 without the
  strongest kept event); packet ephemeris 0.17 +/- 0.05; forced-TLS
  ephemeris 0.11 +/- 0.03. The two events that carried the survey signal are
  artefacts: sector 19 (SPOC 2-min) 2.10 +/- 0.15 ppt in the corrected flux
  against -0.31 +/- 0.11 ppt in SAP, 0.08 d from a PDC gap, 41% of the
  cadences within one duration scattered-light flagged; sector 16 (SPOC)
  0.86 +/- 0.11 ppt on a SAP baseline that changes by 1.3 x the depth across
  the event, 31% scattered-light flags, 0.19 d from a PDC gap. The other
  observed epochs (SPOC sectors 21, 24; TESS-SPOC 52, 55, 57, 59, 74, 76,
  81; QLP 50, 86) are between -0.13 and +0.43 ppt with errors 0.10-0.15 ppt,
  several of them on momentum dumps or ramps. Sector 50 (QLP only) is
  entirely low-precision flagged and, before that flag was applied, its
  garbage dominated the first TLS pass (an 81.2-d peak from one 33-ppt
  spike): that is the survey's data too.
* Gaia: RUWE 0.87, no non-single-star solution, no variability flag; RV
  amplitude 5.7 km/s against 9.8 expected from noise (ratio 0.58). One
  neighbour within 3 px (G 17.6 at 31.5 arcsec, 1.5 px) could make 2 ppt
  only if totally eclipsed. SIMBAD: TYC 4432-592-1 (star). VSX: none.
  Cross-match CLEAN.
* P4 case file: agree with its second kill condition (per-unit depths
  disagree; broad, shallow, unequal dips are what scattered light and the
  chunked detrending produce at long periods) and with its request to look
  at the SPOC 2-minute events one by one in SAP: that look shows the two
  deep ones are not in SAP. Disagree that 15 events exist at one period;
  the 27-sigma centroid is moot.
* **Verdict: KILL.** Reason: the survey signal is two PDC or ramp
  artefacts in sectors 16 and 19 plus a 0.2-ppt residual at SNR 4 from the
  clean epochs; the blind search finds nothing at 65 d.

### Rank 2: TIC 212261364, P = 8.954 d

* Survey: found in the sector-1 chunk with 2 events at BLS SNR 17.4, 7.4
  ppt, 2.4 h; the whole-stitch re-measurement reported SNR 120 with 10
  transits; FPP 0.008; centroid 1.5 sigma; final verdict promising. The
  star also carries two 73-ppt eclipses (17.55 and 57.33 d) that the survey
  accepted and hard-vetoed [P4].
* TLS: **FAIL.** Strongest peak 12.25 d at SDE 10.3 from a single 1.3-ppt
  event (distinct-transit count 1); SDE within 1% of 8.954 d: 4.4. (Before
  the QLP low-precision flag was applied, the sector-95 garbage gave an
  87%-deep, 8-minute "transit" at SDE 56; that is the survey's data too.)
* Events (survey ephemeris): 288 predicted, 13 observed, 6 removed, 7 kept;
  kept depth 0.19 +/- 0.14 ppt (SNR 1.3); packet ephemeris -0.01 +/- 0.14;
  forced-TLS ephemeris -0.02 +/- 0.13. The two sector-1 events that found the candidate: BTJD 1330.45, 5.4 +/-
  0.9 ppt corrected and 7.3 +/- 1.0 ppt SAP, but a momentum dump within one
  duration; BTJD 1348.36, 2.3 +/- 0.8 corrected and 8.9 +/- 2.0 SAP with 25%
  of the in-transit cadences quality-flagged. Both removed. The nine
  epochs in sectors 27, 67, 92 and 95 are flat: -0.4 to +1.8 ppt with errors
  0.3-0.6 ppt (one at 3.2 +/- 0.7 ppt corrected has -0.8 ppt in SAP).
* Phase-independent test: the deepest 2.4-h window anywhere in sector 27
  (10-min cadence) is 1.18 ppt, in sector 67 (200 s) 2.53 ppt, in sector 92
  (QLP) 1.84 ppt, against a per-window noise of 0.40-0.44 ppt. An 8.95-d
  period places three 7.4-ppt transits in every one of those sectors
  whatever the phase; none is there. Sector 95 is dominated by the host's
  eclipses (124 ppt).
* Gaia: RUWE 1.15, `ipd_frac_multi_peak` 1%, astrometric excess noise
  0.12 mas at 15 sigma (a slight excess, consistent with the eclipsing
  companion); 19 sources within 1 arcmin (a dense field), five within 3 px
  bright enough for 7.4 ppt (G 14.1 at 57 arcsec, G 16.5 at 47 arcsec).
  RV amplitude 16.9 against 19.3 km/s from noise (ratio 0.88). SIMBAD: PM*.
  VSX: none. Cross-match CLEAN.
* P4 case file: agree (a bookkeeping survivor of a star-level problem; the
  stitch SNR of 120 is the eclipses folding into the local search). The
  audit adds a direct exclusion of the period from three sectors of
  2-minute and 10-minute data.
* **Verdict: KILL.** Reason: no 7.4-ppt event exists in sectors 27, 67 and
  92 at any phase of an 8.95-d period; the two founding events coincide
  with a momentum dump and flagged cadences; the host is an uncatalogued
  eclipsing binary.

### Rank 3: TIC 160619045, P = 91.664 d

* Survey: long-period stitch search, BLS SNR 44.4, 11 transits, 2.0-4.3
  ppt, 9.2-h box; FPP 5e-4; centroid 13.9 sigma; template odd/even 1.07
  against 7.6 ppt; grazing-rail fit; final verdict ambiguous.
* TLS: **FAIL.** Strongest peak 10.79 d at SDE 10.4 (0.44 ppt, 55 events),
  with 25.9, 21.6 and 12.9 d next: the harmonics of the star's rotational
  modulation, not a transit. SDE within 1% of 91.66 d: 6.3.
* Events (survey ephemeris, 9.2-h duration): 22 predicted, 11 observed, 5
  removed, 6 kept; kept depth 0.10 +/- 0.05 ppt (SNR 2.0); packet ephemeris
  0.05 +/- 0.05; forced-TLS ephemeris -0.11 +/- 0.05. The two deep events are PDC-made: sector 76 (TESS-SPOC),
  BTJD 3375.06, 4.8 +/- 0.2 ppt corrected (8.8 ppt on the TLS ephemeris)
  against -0.29 +/- 0.18 ppt SAP, a PDC gap 0.03-0.23 d away; sector 82,
  BTJD 3558.39, 6.3 +/- 0.3 ppt corrected against -0.66 +/- 0.13 ppt SAP,
  PDC gap 0.10 d away, 36% scattered-light flags. The sector-15 epoch
  (0.75 ppt corrected, -0.83 SAP) sits on a momentum dump at the sector
  edge. The seven remaining epochs (SPOC 19, 22, 25; TESS-SPOC 49, 52, 59,
  79) are between -0.19 and +0.28 ppt with errors 0.11-0.16 ppt.
* Gaia: RUWE 0.99; `phot_variable_flag` VARIABLE, classified SOLAR_LIKE
  (rotational modulation, score 0.45); the VSX lists it (as its Gaia DR3
  name) as type ROT with a 0.03-mag G amplitude. RV amplitude 12.4 against
  13.9 km/s from noise (ratio 0.89). Two neighbours within 3 px (G 16.2 at
  56 arcsec, G 17.6 at 58 arcsec) could make 4 ppt only with total
  eclipses. SIMBAD: none within 1 arcmin. Cross-match CLEAN.
* P4 case file: agree with its first kill condition ("a signal carried by
  a few deep events among shallow or absent ones is the classic long-period
  false alarm of a stitched FFI search") and with its request for an
  event-by-event SAP look, which is what killed it. Disagree that 11
  events exist at one period.
* **Verdict: KILL.** Reason: both deep events exist only in the PDC-corrected
  flux, abutting stretches PDC removed, and are absent in SAP; the clean
  epochs average 0.10 +/- 0.05 ppt; the star is a catalogued rotational
  variable.

### Rank 4: TIC 334678787, P = 46.206 d

* Survey: found in chunk 3 (sectors 73-86) at 46.206 d with BLS SNR 64.8 and
  4 events; whole-stitch re-measurement SNR 26.2 with 13 transits at 45.84 d
  (0.8% from the chunk period; the two were never reconciled); 6.5 ppt,
  5.8 h; FPP 3e-7, centroid 1.2 sigma, no flags; final verdict promising.
  The case file called it the only candidate with every automated check
  clean and asked prompt 5 for the 13-transit fit first.
* TLS: **FAIL.** Strongest peak 38.55 d at SDE 10.2 (0.40 ppt, a noise-level
  long-period peak; 20 events); SDE within 1% of 46.2 d: 6.5. The forced
  narrow search settles at 46.84 d because a single event does not
  constrain a period: TLS's per-transit table shows one event with SNR
  21.5 (6.55 ppt, BTJD 3327.06) and twelve observed epochs at -0.7 to
  +0.4 ppt with per-transit SNR below 1.3.
* Events (survey ephemeris, P 46.2063 d, T0 3327.072): 43 predicted, 19
  observed, 5 removed, 14 kept; kept depth 0.05 +/- 0.04 ppt (SNR 1.2); on
  the packet ephemeris -0.02 +/- 0.03 ppt; on the forced-TLS ephemeris
  0.03 +/- 0.04 ppt. The whole signal is the epoch-0 event in sector 74
  (TESS-SPOC): 6.68 +/- 0.21 ppt in the corrected flux, -0.01 +/- 0.15 ppt
  in the SAP flux of the same cadences. In the raw data the PDCSAP flux
  declines from +1.7 to -16 ppt over 16 h and then PDC removed the next
  22 h (a NaN gap 0.08 d from mid-transit); over the same hours the
  background rises from -695 to +3,800 units (a scattered-light surge,
  quality bit 4096 on 399 of the 864 cadences within +/- 1 d), while the
  SAP flux and the independent QLP flux of sector 74 show no dip (QLP
  scatter +/- 3 ppt, nothing at the epoch). Removed by four rules at once
  (scattered-light flags, PDC gap, dip absent in SAP, background surge).
  One other epoch (sector 86, QLP) has a single 2-h bin at -6 ppt on a
  background ramp with a flat SAP flux; nothing at the remaining 17.
* Gaia: RUWE 0.81, no non-single-star solution, no variability flag, a
  clean high-proper-motion K dwarf (3.6 arcsec from its epoch-2000 TIC
  position); RV amplitude 5.8 km/s against 8.6 expected from noise. No
  neighbour within 3 px bright enough to make 6.5 ppt (nearest: G 18.95 at
  53 arcsec, a Gaia-classified AGN). SIMBAD: AC +76 5597 (PM*). VSX: none.
  Cross-match CLEAN.
* P4 case file: disagree with "13 transits over five years with a
  consistent epoch" and with "promising". Agree with its own first kill
  condition: the 13-transit fit was the first thing to do, and it shows
  one event. The chunk-3 fit's "4 events, odd/even 0.5 sigma" was one
  event plus three empty or flat epochs with beta-inflated errors; the
  stitch re-measurement at 45.84 d was the local BLS folding that event
  with noise. Every downstream number (FPP 3e-7, 95% on-target, 6.9
  R_Earth) described a dip that PDC made.
* **Verdict: KILL.** Reason: a single event manufactured by the PDC
  correction at a scattered-light surge in sector 74, absent from the raw
  SAP flux and from QLP; nothing at eighteen other observed epochs. The
  star itself is clean and is not a follow-up target.

### Rank 5: TIC 290350156, P = 13.203 d

* Survey: found in chunk 3 (QLP sectors 101-103, 2025) at 13.203 d with
  BLS SNR 35.7, 10.6 ppt, 2.4 h and 3 events; whole-stitch SNR 26.8 with 9
  transits; FPP 0.012, NFPP 0.008; centroid 6.2 sigma; final verdict
  ambiguous. A 38-pc mid-M dwarf; the case file called ground-based
  photometry "the decisive test and cheap".
* TLS: **FAIL.** SDE within 1% of 13.2 d: 2.5. The strongest peaks (82.3,
  54.9, 71.8, 68.6 d at SDE 22-28) are degenerate solutions with an 8-minute
  duration and zero distinct transits, made by the multi-cadence
  scattered-light features of the 2025 QLP sectors (19 ppt in sector 102),
  which are shallower than this candidate's deep-clip threshold of 31.7 ppt
  (3 x 10.6 ppt) and so stayed in. They are not detections of anything and
  they are not at 13.2 d.
* Events (survey ephemeris): 217 predicted, 12 observed (six in the SPOC
  2-minute sectors 1, 13, 67 and six in the QLP sectors 101-103), 6
  removed, 6 kept; kept depth 0.54 +/- 0.21 ppt (SNR 2.5), carried entirely
  by the sector-101 dip (top-event share 1.0; -1.0 without it); packet
  ephemeris 0.68 +/- 0.20; forced-TLS ephemeris -0.30 +/- 0.20. The six
  SPOC epochs are flat: -0.60 to +0.14 ppt with
  errors 0.48-0.54 ppt, so a 10.6-ppt event is excluded at about 20 sigma
  at each of them. Of the QLP epochs, BTJD 4111.88 (sector 101) is a real
  dip in the data, 5.8 +/- 0.6 ppt corrected and 7.7 +/- 0.65 ppt SAP,
  mid-sector, unflagged; 4125.08 is 100% low-precision flagged on a ramp;
  4138.29 (sector 102) is 20.8 ppt on a scattered-light ramp 0.87 d from
  the edge with 26% flags; 4151.49 and 4177.90 are 100% flagged; 4164.69
  (sector 103) is 0.4 ppt corrected, 2.9 SAP, on a ramp with 32% flags.
* Phase-independent test: a 13.2-d period puts two transits in every
  27-day sector regardless of phase. The deepest 2.4-h window anywhere in
  sector 1 is 1.70 ppt, in sector 13 2.28 ppt, in sector 67 1.58 ppt
  (2-minute SPOC data, per-window noise 0.48 ppt): no 10.6-ppt event
  occurred in 2018, 2019 or 2023. In sector 101 the deepest window is the
  4111.88 event (5.78 ppt); in 102 the 19.1-ppt ramp; in 103 3.1 ppt.
* Gaia: RUWE 1.31, `ipd_frac_multi_peak` 1%, astrometric excess noise
  at 4.9 sigma; the star is 7.7 arcsec from its epoch-2000 TIC position
  (proper motion). Eight sources within 1 arcmin; three within 3 px bright
  enough for 10.6 ppt (G 14.6 at 41 arcsec, 1.9 px, up to 163 ppt; G 17.2
  at 47 arcsec; G 17.6 at 55 arcsec). SIMBAD: SCR J2155-7330 (PM*). VSX:
  none. Cross-match CLEAN.
* P4 case file: disagree with "9 events over the baseline" and with the
  cheap ground-based test as the next step; agree with its second kill
  condition (only 3 events in the fit, whole-stitch fit not done). The
  audit's whole-baseline look shows the transit absent from every
  2-minute sector.
* **Verdict: KILL** for the 13.203-d candidate. Reason: the period is
  excluded by three sectors of 2-minute data in which the event never
  occurs; what remains is one SAP-visible 5.8-7.7 ppt, 2.4-h dip at BTJD
  4111.88 in QLP data, which without a second event is not a candidate and
  may be a systematic. If a human wants to keep anything from this star,
  it is that one epoch, not the period.

### Rank 6: TIC 21124154, P = 89.228 d

* Survey: long-period stitch search, BLS SNR 24.2, 10 transits, 0.82 ppt
  box railed at 12 h; FPP 0.14 (NEB scenario 14%); template odd/even
  -0.29 against 1.74 ppt; centroid 17.9 sigma; 5 high-risk neighbours;
  final verdict likely false positive.
* TLS: **FAIL.** Strongest peak 97.5 d at SDE 9.4 (0.34 ppt, 5 events; the
  next peaks 73.2, 12.2, 48.8 d at SDE 7.5-8.3), a noise-level long-period
  forest; SDE within 1% of 89.2 d: 6.5.
* Events (survey ephemeris, 12-h duration): 22 predicted, 11 observed, 8
  removed, 3 kept; kept depth 0.18 +/- 0.08 ppt (SNR 2.4); packet ephemeris
  0.22 +/- 0.08 (3 events); forced-TLS ephemeris 0.10 +/- 0.06 (4 events).
  The removals: the sector-14 epoch is 100%
  scattered-light flagged; sectors 18, 83 and QLP 80 have SAP baselines
  changing by more than one depth across the event; sector 21 abuts a PDC
  gap; sectors 57, 60 and 74 have momentum dumps within one duration (the
  sector-60 dip, 0.92 ppt corrected, is 0.25 +/- 0.16 ppt in SAP). The
  three clean epochs (sectors 24, 41, 54) give -0.05, +0.12 and +0.43 ppt
  (errors 0.13-0.14 ppt).
* Gaia: RUWE 3.19, astrometric excess noise 0.37 mas at 199 sigma: an
  unresolved binary. Eight neighbours within 3 px bright enough for 0.8
  ppt (G 15.7 at 22.5 arcsec, 1.07 px, could make up to 34 ppt). RV
  amplitude 7.2 against 11.2 km/s from noise (ratio 0.65). SIMBAD, VSX:
  none. Cross-match CLEAN.
* P4 case file: agree (three independent kills: odd events with no dip,
  broad events, centroid plus neighbour scenario). The audit adds the Gaia
  RUWE and that no epoch shows the dip in SAP once dumps and ramps are
  removed.
* **Verdict: KILL.** Reason: no signal in the independent data (three clean
  events at 0.18 +/- 0.08 ppt; blind TLS nothing above SDE 9); an
  astrometric-binary host in a field with eight neighbours bright enough.

### Rank 7: TIC 356976754, P = 11.789 d

* Survey: stitch SNR 33.6, 67 transits, 4.0 ppt box at the 1.08-h duration
  floor; a second survivor on the same star at 13.631 d; secondary eclipse
  1.97 ppt; FPP 0.46; final verdict likely false positive.
* TLS: **FAIL.** Strongest peak 0.7368 d at SDE 58.3 (3.25 ppt, 1,112
  events), second peak 1.4736 d at SDE 32.6. The survey period is
  16.00 x 0.7368 d and the twin survivor is 18.50 x 0.7368 d. SDE within 1%
  of 11.789 d: 4.1.
* Events (survey ephemeris): 168 predicted, 80 observed, 15 removed, 65
  kept; kept depth 3.05 +/- 0.07 ppt (SNR 46) because every 11.789-d epoch
  lands on a 0.737-d dip; depths inconsistent with a constant (chi2 1,153
  for 64 dof) and odd/even 2.68 +/- 0.09 against 3.42 +/- 0.09 ppt (5.6
  sigma).
* Gaia: RUWE 0.91, no non-single-star solution, no variability flag; RV
  amplitude 15.4 km/s against an expected noise peak-to-peak of 18.4
  (inconclusive). Four neighbours within 3 px could make 4 ppt with a total
  eclipse, two with a 50% eclipse. SIMBAD and VSX: nothing within 1 arcmin.
  Cross-match CLEAN.
* P4 case file: agree that the object is stellar. Disagree on the
  mechanism: it is not a secondary eclipse at 11.789 d but a 0.7368-d
  variable (a contact or ellipsoidal binary, or a fast rotator) whose dips
  the 1-100 d search picked up at its 16th multiple.
* **Verdict: KILL.** Reason: the 11.789-d period is an alias of a 0.7368-d
  stellar variable; no transit candidate exists at the survey period.

### Rank 8: TIC 246937997, P = 2.457 d

* Survey: stitch SNR 22.8, 53 transits, 12.4 ppt box lasting 12% of the
  period, a/R* 1.6 against 7.6 from the catalog, odd/even 2 sigma, FPP 0.25,
  NFPP 0.13; likely false positive.
* TLS: **WEAK (no detection).** Strongest peak 0.8197 d at SDE 6.8, below
  the SDE 9 threshold; the five strongest peaks (0.820, 1.639, 2.459,
  4.918, 28.3 d) are the 1/6, 1/3, 1/2 and 1/1 harmonics of 4.918 d, i.e.
  the rotational modulation, not a transit. SDE within 1% of 2.457 d: 6.0.
* Events (forced-TLS ephemeris, 2.4592 d): 63 observed, 17 removed, 46 kept;
  kept depth 5.19 +/- 0.09 ppt but odd/even 4.78 against 5.72 ppt (5.2
  sigma) and chi2 239 for 44 dof: the "depth" is the sinusoid sampled at
  its minima. Under the survey ephemeris (2.45713 d, 0.08% different, so
  the phase drifts 0.4 cycles over the baseline) the kept SNR is 0.8. The
  SAP flux carries the 0.2-mag modulation directly (SAP kept SNR 229).
* Gaia: RUWE 0.82 but astrometric excess noise 0.22 mas at 44 sigma; a
  companion of G = 14.46 (delta G 1.73) at 1.1 arcsec, inside the same
  pixel, which alone could produce up to 169 ppt; three more neighbours
  within 3 px bright enough. SIMBAD: emission-line star (Em*). VSX:
  ASASSN-V J021733.88+215650.4, type ROT, period 5.2875 d, V amplitude
  0.20 mag. Cross-match CLEAN.
* P4 case file: agree (a sinusoid or ellipsoidal signal, not a transit;
  the catalog Teff/radius mismatch is the blend). The audit adds that the
  star is a catalogued rotational variable and an emission-line star with a
  1.1-arcsec companion.
* **Verdict: KILL.** Reason: rotational modulation of a known spotted,
  chromospherically active star (TESS periodicity 4.92 d, ASAS-SN 5.29 d) at
  half the rotation period; not a transit shape; blended companion.

### Rank 9: TIC 167304394, P = 22.780 d

* Survey: stitch SNR 660, 32 events, 59 ppt, Rp/R* 0.46 on the grazing
  rail, implied 3.7 R_Jup, TRICERATOPS uniform posterior; likely false
  positive.
* TLS: **PASS.** 22.7797 d at SDE 376 (2:1 alias 45.56 d at SDE 164), depth
  45 ppt on the 30-minute detrended flux, 32 distinct events. The only
  candidate of the ten whose survey period the blind search reproduces.
* Events (forced-TLS ephemeris): 112 predicted, 41 observed, 15 removed (QLP
  quality flags and ramps), 26 kept; kept depth 45.16 +/- 0.07 ppt (SNR
  686; SAP 691), odd 45.67 +/- 0.14 against even 45.01 +/- 0.08 ppt (4.3
  sigma, a 1.5% difference), event-to-event scatter about 1 ppt. A real,
  strictly periodic 4.5% eclipse.
* Gaia: the target has no RUWE (no five-parameter solution),
  `ipd_frac_multi_peak` 95%, astrometric excess noise 2.5 mas at 4,115 sigma,
  and a second Gaia source of equal brightness (G 12.64 against 12.79) at
  0.4 arcsec: an equal pair unresolved by TESS, so the eclipse on whichever
  component hosts it is about twice as deep (9-10%). A G = 14.0 star at
  22 arcsec (1.06 px) could also produce the depth. RV amplitude 51.8 km/s
  against 78.6 expected from noise (inconclusive). SIMBAD: UCAC4 114-012846
  (star). VSX: none. Cross-match CLEAN.
* P4 case file: agree (an eclipsing binary that no catalog lists). The
  audit adds the equal-brightness Gaia pair.
* **Verdict: KILL** as a planet candidate. Reason: a 4.5% (9-10% undiluted)
  eclipse with equal odd and even depths is a stellar companion on one star
  of a close pair. It is not a CTOI; a human may choose to report it to an
  eclipsing-binary catalog.

### Rank 10: TIC 233200485, P = 70.681 d

* Survey: chunk SNR 7.1 with 4 events; whole-stitch SNR 124 with 13
  transits; 1.55 ppt; uniform TRICERATOPS posterior; the same star carries
  85-ppt eclipses at 68.84 and 60.73 d; likely false positive.
* TLS: **FAIL.** After removing 9 binned points deeper than 9.25 ppt (the
  host's eclipses, 3 x the candidate depth), the strongest peak is 85.61 d
  at SDE 15.1 (0.46 ppt, 12 events); SDE within 1% of 70.68 d: 6.7 (10th
  peak).
* Events (survey ephemeris): 28 predicted, 13 observed, 2 removed, 11 kept;
  kept depth 0.50 +/- 0.12 ppt (SNR 4.1), individual depths between -0.4
  and +1.9 ppt with errors 0.3-0.8 ppt. Not a 1.5-ppt transit train; the
  stitch SNR of 124 is not reproduced.
* Gaia: RUWE 20.7, astrometric excess noise 2.02 mas at 5,279 sigma: an
  astrometric binary. Five neighbours within 3 px bright enough for 1.5
  ppt. RV amplitude ratio 0.80 (inconclusive). SIMBAD, VSX: none.
  Cross-match CLEAN.
* P4 case file: agree. The Gaia astrometry is consistent with the binary host P4
  inferred from the 85-ppt eclipses.
* **Verdict: KILL.** Reason: no periodic 1.5-ppt signal in the independent
  data (SNR 4 from 11 clean events, TLS SDE 6.7); the host is an astrometric
  and photometric binary whose eclipses made the survey's stitch SNR.

### Outside the top ten: TIC 284191194, P = 73.719 d (P4 rank 14, "promising")

P4 asked prompt 5 to re-run TRICERATOPS on this one because its FPP was a
uniform-posterior artefact. Not needed:

* TLS: **FAIL.** Nothing above SDE 8.6 anywhere (a flat forest of peaks at
  8.3-8.6, including 73.5 d at 8.3, the fifth peak), all below threshold.
* Events: 27 predicted, 13 observed, 4 removed, 9 kept; kept depth 0.04
  +/- 0.07 ppt (SNR 0.5) on the forced-TLS ephemeris, -0.2 on the survey
  ephemeris; not one of the 13 observed epochs shows a 2.7-ppt dip.
* Gaia: RUWE 7.21, astrometric excess noise 1.20 mas at 1,919 sigma
  (astrometric binary); three G 17.6-17.9 neighbours within 3 px could make
  2.7 ppt only with total eclipses. SIMBAD, VSX: none. CLEAN.
* **Verdict: KILL.** Reason: the signal is absent from the independent
  data; the host is an astrometric binary. Disagree with P4's "promising".

### Outside the top ten: TIC 200658220, P = 26.091 d (P4 rank 19, 7.9% deep, "promising")

P4 reported 7 events, FPP 4e-15, a 3.7-sigma centroid and recommended a
radial-velocity epoch. The audit finds:

* TLS: **FAIL.** Strongest peak 98.9 d at SDE 30 made by ONE event (56 ppt,
  distinct-transit count 1); SDE within 1% of 26.09 d: 2.7. Forced TLS at
  26.25 d: seven epochs with data, six flat (-2.5 to +1.7 ppt), one at 103
  ppt.
* Events (survey ephemeris): 110 predicted, 10 observed. The T0 event
  (BTJD 4150.86, sector 102, QLP) is 52.7 +/- 2.5 ppt in QLP's detrended
  flux and 0.14 +/- 0.91 ppt in the same product's SAP flux, with 30% of
  the in-transit cadences low-precision flagged, 0.9 d from the sector
  edge; in the raw data the detrended flux slides from 0 to -211 ppt over
  12 h into a scattered-light surge (background +7,500 units, SAP flux
  +2,100 ppt, low-precision flags on every cadence after +4 h). The other
  nine observed epochs (TESS-SPOC sectors 1, 2, 28; QLP 29, 68, 69, 95, 96,
  104) are flat within +/- 1.2 ppt with errors 0.7-1.1 ppt: each would show
  a 79-ppt transit at more than 60 sigma.
* Gaia: RUWE 1.05, clean astrometry; one brighter star (G 11.87,
  TYC 8464-628-1, delta G -1.78) at 57.7 arcsec (2.75 px). SIMBAD: that
  star. VSX: none. CLEAN.
* **Verdict: KILL.** Reason: a single detrending artefact at a
  scattered-light ramp, absent in SAP, not repeated at nine other observed
  epochs. Disagree with P4's "promising, 7 events".

## 4. Verdicts

| rank | TIC | P (d) | verdict | reason in one line |
|---:|---:|---:|---|---|
| 1 | 233211748 | 65.008 | KILL | the deep events are PDC-made or on ramps; clean events 0.2 ppt at SNR 4; blind TLS finds nothing at 65 d |
| 2 | 212261364 | 8.954 | KILL | no 7.4-ppt dip anywhere in sectors 27, 67, 92 (deepest 2.4-h window 1.2-2.5 ppt); the two sector-1 events sit on a momentum dump and flagged cadences; host is an eclipsing binary |
| 3 | 160619045 | 91.664 | KILL | both deep events are PDC-made (absent in SAP, abutting PDC gaps); clean events 0.10 +/- 0.05 ppt; star is a Gaia/VSX rotational variable |
| 4 | 334678787 | 46.206 | KILL | one PDC-made event in sector 74 (6.7 ppt corrected, 0.0 ppt SAP, at a scattered-light surge) and nothing at the other 18 observed epochs |
| 5 | 290350156 | 13.203 | KILL | the 10.6-ppt transit is absent from three sectors of 2-minute data where any 13.2-d period must show it six times; the dips exist only in the 2025 QLP sectors, most on ramps |
| 6 | 21124154 | 89.228 | KILL | no signal (3 clean events at 0.18 +/- 0.08 ppt; TLS nothing above SDE 8.8); RUWE 3.2 host with 8 neighbours bright enough |
| 7 | 356976754 | 11.789 | KILL | alias (16.00 x) of a 0.7368-d stellar variable |
| 8 | 246937997 | 2.457 | KILL | rotational modulation of a catalogued ROT / emission-line star at half the rotation period; 1.1-arcsec companion |
| 9 | 167304394 | 22.780 | KILL | real 4.5% eclipse (9-10% undiluted) on an equal-brightness Gaia pair: an eclipsing binary, not a planet candidate |
| 10 | 233200485 | 70.681 | KILL | no periodic 1.5-ppt signal (SNR 4); RUWE 20.7 astrometric binary hosting 8.5% eclipses |
| 14 | 284191194 | 73.719 | KILL | no signal in independent data (0.04 +/- 0.07 ppt); RUWE 7.2 binary |
| 19 | 200658220 | 26.091 | KILL | single QLP detrending artefact at a scattered-light ramp, absent in SAP; nine other epochs flat |

No HOLD verdicts: for every candidate the audit found a positive cause for
the survey signal (an artefact class, a binary host, or stellar variability)
rather than an absence of information, so there is nothing a further
measurement would change.

## 5. The list to submit

**Nothing survives.** The ordered list to submit is empty. No
`ctoi_fields.json` is filled by this prompt, and the `ctoi_fields.json`
files in `docs/packets/survey_v1/` must not be used: their periods, epochs,
depths and durations describe signals this audit could not reproduce. The
one real periodic signal (rank 9) is an eclipsing binary and is not a
CTOI.

This is consistent with the expectation P4 itself computed: 2.2 real new
signals expected among several hundred noise survivors at mid priors, with
the top ten dominated by the deepest and highest-stitch-SNR signals, which
is exactly where artefacts and binaries sort.

## 6. The three most valuable changes for a second survey pass

1. **Test every event in the raw SAP flux before it counts as a transit, and
   veto PDC-gap and scattered-light events.** Six of the twelve signals
   audited here (ranks 1, 3, 4, 5, 6 in part, and TIC 200658220) were made or
   carried by dips that exist only in the corrected or detrended flux, at
   the edge of a stretch PDC removed or at the onset of a scattered-light
   ramp (quality bits 2048/4096), with a flat SAP flux. The per-event
   rules of section 1 step 3 cost nothing and remove them; they should run
   inside the survey's whole-stitch re-measurement, and a candidate whose
   kept-event SNR falls below the gate should not reach G2. The same step
   should apply QLP's low-precision flag (2^12 for sectors 1-55, 2^30 from
   sector 56) before any flux is used, and require a candidate to be
   reproduced by a second detrending (wotan biweight) before the expensive
   stage.
2. **A star-level gate that masks deep events before the shallow search and
   demotes shallow candidates on binary hosts.** Ranks 2 and 10 reached the
   top ten on whole-stitch SNRs of 120-124 that were the eclipses of an
   uncatalogued binary folding into a +/-1% local search; ranks 6, 10 and
   the two extras have Gaia RUWE 3.2-20.7 or a 95% multi-peak fraction.
   Mask accepted events deeper than 3 x the candidate depth before
   re-measuring, carry "same star has a deep event" and Gaia RUWE /
   `ipd_frac_multi_peak` / `astrometric_excess_noise_sig` into the ranking,
   and require the whole-stitch re-measurement to reproduce the chunk depth
   within a factor of two.
3. **Replace the whole-stitch local-BLS re-measurement by a per-event
   ephemeris test, and stop ranking on stitch SNR.** A candidate found in
   one chunk should be tested by predicting its epochs across the full
   baseline and demanding that the clean, observed epochs carry the depth
   (kept-event SNR, top-event share below 50%, odd/even from those events),
   with a phase-independent check in every sector of 2-minute data
   (the deepest transit-length window). The frozen score's S_snr term
   rewarded exactly the inflated stitch SNRs; a second pass should score on
   the kept-event SNR and on the number of independent sectors that show
   the event.

Population changes worth making at the same time [A]: prefer stars with
SPOC 2-minute data in at least two sectors (the 2-minute SAP flux is what
made ranks 2 and 5 falsifiable in minutes), and treat the northern
continuous-viewing-zone sectors 74, 76 and 82 (and 15, 19) as scattered-light
sectors for these camera fields until the PDC behaviour there is understood.

### Measured over all 405 survivors (prompt 6)

These three changes were sized in prompt 6, which ran the rules of section 1
step 3 over every survivor rather than the top ten. `docs/REVET.md` has the
funnel, the per-class census and the per-candidate verdicts; the numbers that
bear on the changes above are [M]:

* Change 1 (the SAP test and the PDC-gap / scattered-light vetoes) removes the
  strongest event of **302 of the 405** survivors, and 2,957 of 8,697 observed
  epochs (34%). "Dip absent in SAP" alone carries 124 candidates; the SAP
  baseline ramp 117, the PDC gap 93, the scattered-light flag 88 and the
  scattered-light ramp 78.
* The PDC-made dips are not confined to sectors 15, 19, 74, 76 and 82: they
  appear in **232** sector/camera/CCD/product combinations from sector 1 to
  105, with TESS-SPOC contributing 356 of the 467 events, cameras 3 and 4
  carrying 73%, and 291 of 467 falling in sectors 56 and later. The worst
  sectors are 85, 75, 74, 84 and 67.
* Change 2 (star-level gates) applies to **109** candidates that sit on a star
  with another accepted candidate at >= 30 ppt or >= 5 x their own depth; on
  **69** of them the deep events are inside the candidate's own search data.
* Change 3 (stop ranking on stitch SNR) is supported directly: the frozen rank
  correlates with the number of prompt-6 Stage A criteria a candidate passes
  (Spearman rho = -0.37, p = 9e-15) but not at all with the kept-event SNR
  (rho = -0.065, p = 0.19, n = 405).

Prompt 6 ended in a clean null: no candidate was re-detected by a blind TLS at
its own period, so nothing was prepared for submission.
