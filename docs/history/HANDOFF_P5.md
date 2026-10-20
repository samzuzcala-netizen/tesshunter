# HANDOFF P5: independent audit of the top-10 candidates, go or no-go

Date: 2026-09-03. Branch `improve/recovery`. Environment as in
`CTOI_PROMPTS.md` (double-nested repo, `tesshunter_venv` Python 3.13,
lightkurve 2.6.0). Two packages were added to the venv for this prompt and
are not part of the repo: `transitleastsquares` 1.32 and `wotan` 1.10 (plus
their dependency `configparser` 7.2.0).

Session start state, measured [M]: `git status` clean on 2276840 (the P4
commit); 30,660 files in `data/cache/lightkurve`, 0 zero-byte; `pytest
tests/ -q` 305 passed, 1 skipped, 172 s. End state: 305 passed, 1 skipped,
122 s; nothing under `src/` or `tests/` changed.

Evidence tags: [M] measured in this session, [P4] taken from the P4
packets or case files, [A] adopted assumption or threshold. The pipeline
finds candidates; nothing here is a detection, and nothing was submitted
anywhere.

## Result in one line

**No candidate survives. SUBMIT 0, HOLD 0, KILL 10 (plus the two extras P4
flagged). The ordered list to submit is empty and no `ctoi_fields.json` was
filled.** `docs/AUDIT.md` has the per-candidate evidence and verdicts and
the three changes recommended for a second survey pass.

| candidate (P4 rank) | blind TLS at the survey period | clean-event depth (ppt) | what the survey signal was |
|---|---|---:|---|
| 1. TIC 233211748, 65.0 d | FAIL (SDE 1.4 there; nothing anywhere, max SDE 2.2) | 0.20 +/- 0.05 (6 events) | PDC-made dip (sector 19) + ramp dip (sector 16) |
| 2. TIC 212261364, 8.95 d | FAIL (SDE 4.4) | 0.19 +/- 0.14 (7) | eclipses of the binary host folding into the stitch search; founding events on a dump and flagged cadences; 7.4-ppt transit excluded at any phase in sectors 27, 67, 92 |
| 3. TIC 160619045, 91.7 d | FAIL (SDE 6.3) | 0.10 +/- 0.05 (6) | two PDC-made dips (sectors 76, 82); Gaia/VSX rotational variable |
| 4. TIC 334678787, 46.2 d | FAIL (SDE 6.5) | 0.05 +/- 0.04 (14) | one PDC-made dip at a scattered-light surge (sector 74), absent in SAP and QLP |
| 5. TIC 290350156, 13.2 d | FAIL (SDE 2.5) | 0.54 +/- 0.21 (6) | dips only in the 2025 QLP sectors, most on ramps; transit absent from three 2-minute sectors at any phase |
| 6. TIC 21124154, 89.2 d | FAIL (SDE 6.5) | 0.18 +/- 0.08 (3) | dumps, ramps, a PDC-gap dip; RUWE 3.2 host |
| 7. TIC 356976754, 11.79 d | FAIL: 0.7368 d at SDE 58 | 3.05 +/- 0.07 (65, varying) | 16th multiple of a 0.737-d stellar variable |
| 8. TIC 246937997, 2.457 d | WEAK (max SDE 6.8, harmonics of 4.92 d) | sinusoid, odd/even 5 sigma | rotational modulation of a catalogued ROT / Em* star with a 1.1-arcsec companion |
| 9. TIC 167304394, 22.78 d | PASS (SDE 376) | 45.16 +/- 0.07 (26) | eclipsing binary in an equal-brightness Gaia pair |
| 10. TIC 233200485, 70.7 d | FAIL (SDE 6.7) | 0.50 +/- 0.12 (11) | eclipses of the RUWE-20.7 binary host in the stitch search |
| extra TIC 284191194, 73.7 d | FAIL (SDE 8.3, below threshold) | 0.04 +/- 0.07 (9) | nothing; RUWE 7.2 host |
| extra TIC 200658220, 26.1 d | FAIL (SDE 2.7) | 0.34 +/- 0.30 (8) | one QLP detrending artefact at a scattered-light ramp, absent in SAP; nine flat epochs |

Blind TLS SDE values at the survey period are the maximum within +/- 1%;
"clean-event depth" is the inverse-variance weighted mean of the per-event
depths in the wotan-detrended corrected flux after removing events on
momentum dumps, sector or orbit edges, PDC gaps, scattered-light ramps or
flags, quality-flagged cadences, and dips absent from the raw SAP flux
(rules in `docs/AUDIT.md` section 1).

## 1. What shipped

* `scripts/audit_p5.py` (new; imports nothing from `tesshunter` except the
  catalog cross-match): `download` (fresh lightkurve cache at
  `data/cache/audit_lightkurve`, every SPOC 2-min / TESS-SPOC / QLP product,
  all cadences and flags kept), `tls` (wotan biweight per product, 30-min
  bins, blind Transit Least Squares 0.5-110 d plus a forced narrow run for
  the ephemeris and per-transit table; documented clipping of isolated
  single-cadence dips and of binned points deeper than 3 x the candidate
  depth), `events` (every predicted epoch over the baseline under the
  survey, packet and forced-TLS ephemerides, measured in the corrected and
  the raw SAP flux with the removal rules, SNR recomputed from kept events,
  depth consistency, leave-one-out), `neighbours` (Gaia DR3 1-arcmin ADQL
  cone joined to the variability classifier, RUWE, non-single-star,
  multi-peak fraction, astrometric excess noise, RV amplitude against its
  noise expectation, dilution per neighbour; SIMBAD; VSX), `crossmatch`
  (hard stop with re-downloaded catalogs), `fit` (all-transit batman fit
  with the density prior adopted when the data cannot reject it, and a
  `ctoi_fields.json` writer; built for a SUBMIT verdict and not exercised on
  any candidate because none reached that verdict), `report`.
* `docs/AUDIT.md`: method, summary table, twelve per-candidate sections
  with verdicts, the empty submission list, three second-pass changes.
* `data/survey/p5/`: one JSON per step and candidate (`tls/`, `events/`
  with one file per ephemeris, `neighbours/`, `crossmatch_p5.json`,
  `audit_summary.json`), the batch driver scripts and their logs. The
  per-product arrays (`lc/`, 60 MB) and TLS spectra (`tls/*.npz`, 95 MB) are
  git-ignored and reproducible with the `download` and `tls` sub-commands.
* `.gitignore`: the two rules above.

## 2. What was measured [M]

* Downloads: 12 stars, 506 products, 0 failures, 9.1 minutes (per star 18 to
  80 s). The cache the survey used was not touched.
* Blind TLS: 12 runs, 290,000 trial periods for the 1,979-d baselines,
  60 to 620 s each on 20 threads; 32,000-40,000 binned points for the
  continuous-viewing-zone stars. Verdicts: PASS 1 (rank 9), WEAK 1 (rank 8,
  SDE 6.8), FAIL 10. The SDE within 1% of the survey period was 1.4 to 8.3
  for the eleven non-passing candidates.
* Per-event tables: 12 candidates x 3 ephemerides; 9 to 80 observed epochs
  per candidate; the dip-absent-in-SAP rule fired on ranks 1, 3, 4, 6 and on
  TIC 200658220, always at PDC gaps or scattered-light ramps.
* Phase-independent checks (deepest transit-length window per sector) for
  ranks 2 and 5: 1.2-2.5 ppt in every 2-minute or 10-minute sector against
  claimed depths of 7.4 and 10.6 ppt (per-window noise 0.4-0.5 ppt).
* Gaia DR3: RUWE 3.19 (rank 6), 7.21 (TIC 284191194), 20.7 (rank 10);
  `ipd_frac_multi_peak` 95% with an equal-brightness source 0.4 arcsec away
  (rank 9); `phot_variable_flag` VARIABLE, class SOLAR_LIKE and a VSX ROT
  entry (rank 3); VSX ROT with P 5.29 d and 0.2-mag amplitude plus a SIMBAD
  Em* type and a 1.1-arcsec companion (rank 8). No Gaia RV amplitude
  exceeded its noise expectation (ratios 0.58-0.89).
* Hard stop: the six catalogs re-downloaded 13:39-13:44 UTC (292 s); every
  digest identical to P4's download of the same morning; all 12 stars CLEAN.

## 3. What was refuted [M]

* P4's "only candidate with every automated check clean" (rank 4, TIC
  334678787): one PDC-made event; nothing at 18 other epochs.
* P4's ranks 1, 3 and 6 as multi-transit long-period signals: their deep
  events are PDC or ramp artefacts; the clean epochs carry 0.1-0.2 ppt.
* P4's ranks 2 and 5 as periodic transits: the period is excluded at any
  phase by sectors of 2-minute (and 10-minute) data.
* P4's "promising" extras: TIC 200658220 (7 events, FPP 4e-15) is one
  detrending artefact; TIC 284191194 has no signal in independent data.
* The frozen ranking's top ten as a whole: its S_snr term rewarded
  whole-stitch local-BLS SNRs (72-660) that the independent re-measurement
  does not reproduce for any shallow candidate.
* Not refuted: P4's expectation of about 2.2 real new signals among
  several hundred survivors. Zero in the top ten is consistent with it;
  the audit says nothing about ranks 11-405.

## 4. Assumptions the verdicts rest on [A]

* The removal thresholds (20% flag fractions, 2 x background, SAP depth
  below 30% of a > 5-sigma corrected depth, 50% top-event share, SNR 7,
  TLS SDE 9) and the preprocessing (default quality mask plus QLP's
  low-precision flag, isolated single-cadence dips, binned points deeper
  than 3 x the candidate depth) are this audit's choices, stated in
  `docs/AUDIT.md` and applied identically to all twelve.
* Neighbour dilution uses Gaia RP (else G) flux ratios and f/(1+f) as the
  largest depth a totally eclipsed neighbour could produce; aperture
  membership is approximated by separation in pixels.
* The Gaia RV noise expectation is 4 x the per-epoch error (quoted error
  times the square root of the number of transits).

## 5. Still open

1. **A pipeline-level SAP check.** The dominant false-positive class in the
   top ten (dips that exist only in the PDC-corrected or QLP-detrended flux
   at PDC gaps and scattered-light ramps) is invisible to the survey as
   built. The per-event rules of the audit should run inside the survey's
   whole-stitch re-measurement (`docs/AUDIT.md` section 6, change 1).
2. **Star-level gates and Gaia astrometry in the ranking** (change 2), and
   a per-event ephemeris test in place of the local-BLS stitch SNR (change 3).
3. **QLP low-precision cadences and multi-cadence garbage** reached the
   survey's stitched data through the survey's own mask only partly; the
   audit's first TLS pass on ranks 1, 2 and 5 was dominated by them until the
   flag (2^12 for sectors 1-55, 2^30 from sector 56) and a deep clip were
   applied. TLS itself will fit sub-cadence "transits" of arbitrary depth to
   such points; any TLS use needs the same preprocessing.
4. **One SAP-visible single dip remains unexplained**: TIC 290350156, BTJD
   4111.88 (sector 101, QLP), 5.8-7.7 ppt, 2.4 h, mid-sector, unflagged.
   Its 13.2-d period is excluded; as a single event it is not a candidate.
5. **TIC 167304394** is a real 22.78-d eclipsing binary in an equal
   Gaia pair, absent from the TESS EB catalog (sectors 1-26) and every SPOC
   TCE list. A human may report it to an EB catalog; it is not a CTOI.
6. **P4 open items not exercised because nothing reached SUBMIT**: the
   uniform-posterior TRICERATOPS re-runs, the whole-stitch fits, and the
   density-prior rule for the packets. The audit's `fit` sub-command
   implements the prior rule (adopt the catalog density when imposing it
   costs less than delta chi2 9) for a future SUBMIT; the survey's own
   `transit_fit.py` still has the gap described in `HANDOFF_P4.md` item 1.
7. **The audit code is a script, not a tested module.** It has no unit
   tests; its rules are documented in `docs/AUDIT.md` and every intermediate
   number is in `data/survey/p5/`. Porting the event rules into
   `src/tesshunter` with tests is the first step of a second pass.

## Files

* `scripts/audit_p5.py`, `docs/AUDIT.md`, `HANDOFF_P5.md`, `.gitignore`.
* `data/survey/p5/`: `tls/*.json`, `events/*_{survey,packet,tls}.json`,
  `neighbours/*.json`, `crossmatch_p5.json`, `audit_summary.json`,
  `run_*.sh`, `*.log`. Git-ignored: `data/survey/p5/lc/`,
  `data/survey/p5/tls/*.npz`, `data/cache/audit_lightkurve/`.
