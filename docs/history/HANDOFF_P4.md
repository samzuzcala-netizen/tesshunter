# HANDOFF P4: the survey run and the candidate packets

Date: 2026-09-03. Branch `improve/recovery`. Environment as in `CTOI_PROMPTS.md`
(double-nested repo path, `tesshunter_venv` Python 3.13, lightkurve 2.6.0,
TRICERATOPS 1.1.0 with the celerite import shim from P3).

Session start state, measured [M]: `git status` clean on 4c6054e (the P3
commit); 12,028 files in `data/cache/lightkurve`, 0 zero-byte files, 285 GB
free; `pytest tests/ -q` 305 passed, 1 skipped, 184 s. The tree was healthy.

Evidence tags: [M] measured in this session, [A] adopted assumption,
[R] refuted or unavailable. The pipeline finds candidates; nothing in this
document is a detection, and nothing was submitted anywhere.

## Summary

| item | value |
|---|---|
| targets in `targets_v1.csv` | 819 |
| targets searched to status `ok` | 819 (0 errors, 0 timeouts, 0 retries, 3 time-budget stops) |
| accepted candidates (G1) | 6,378 on 814 stars (7.8 per star; P2 measured 7.9 on its 300-star sample) |
| after G2 (stitch SNR >= 9, epoch-consistent) | 910 |
| after G3 (>= 3 transits on the stitch) | 515 |
| after G4 (verdict not likely-FP) | 430 |
| after G5 (fit converged, dip >= 3 sigma) | 411 on 261 stars |
| after G6 (harmonics merged) | 405 unique signals |
| after G7 (fresh hard-stop cross-match, catalogs re-downloaded 2026-09-03) | 405 (0 REJECT, 0 FLAG) |
| expected from the P2 false-alarm tables for 819 stars at G2-G4 | 311 to 500 (measured 430) |
| expected REAL new signals, measured completeness curve, mid priors | 2.19 (P1 model: 5.00) |
| expensive steps (all-sector centroid, TRICERATOPS, packet) | top 30 by the frozen score, all 30 completed; FPP <= 0.5 on 8 of 30; final verdicts: likely false positive 19, ambiguous 7, promising 4 |
| packets | `docs/packets/survey_v1/` (30, one per top-30 candidate); case files `docs/case_files/` (top 10) |
| wall clock | prefetch 1.0 h (8 workers); search 819 stars at 12 then 18 workers, 17.8 CPU-hours, per-star median 54 s, p90 155 s, max 317 s |
| test suite at the end | 305 passed, 1 skipped, 101 s (after the `stellar.py` fix) |

Nothing in detection or vetting changed. One P3 module was patched for a
crash the run exposed (`stellar._parse_tic_row`, section "Crashes").

## 1. The frozen score

`docs/RANKING_SCORE.md` was written and committed (97d1d8b) before any
survey search ran; the only P3-code search executed before that commit was a
14-second smoke job on one star, used to confirm which fields the survey
output carries. Gates G0-G8 and the four-term score (S_snr from the
whole-stitch SNR between 9 and 50; S_ntr from the stitch transit count
between 3 and 10; S_fpp = 1 - FPP where TRICERATOPS ran, 0.5 otherwise;
S_rho from the profile delta chi2 and density ratio of the P3 fit) were not
changed after the run. Two things the run showed about the frozen rules, left
as they are and recorded here:

* G6 merges only 2:1 and 3:1 harmonics within 1%. Two stars carry two
  survivors each whose periods differ by 1.3% (TIC 141756992 at 78.27 and
  79.25 d, from the chunk and the stitch search) or by 16% (TIC 356976754 at
  11.79 and 13.63 d); these are the same signal or the same variable star and
  both rows were carried through the expensive stage.
* With S_fpp neutral, ties at 3.5 (S_snr, S_ntr and S_rho all saturated) are
  broken by stitch SNR, so the pre-FPP top is dominated by the deepest,
  highest-SNR signals, several of them grazing (b at the fit rail of 1.2,
  implied radii 25-40 R_Earth) and "ambiguous" rather than "promising". The
  design put FPP after the first ranking on purpose; the final table is
  where those sort out.

## 2. The run [M]

* **Prefetch** (`scripts/run_survey.py --prefetch`, 8 workers, all 819
  stars, 3,592 s): 519 stars needed MAST; download median 40 s, 90th
  percentile 89 s, max 150 s per star; every product of every survey author
  (TESS-SPOC 9,607, QLP 5,053, SPOC 1,957 products over the population; SPOC
  2-minute products are binned to 30 minutes and take precedence in their
  sector per the P2 rule). 0 failures.
* **Search** (`data/survey/runs/survey_v1`): phase 1 on the 324 stars already
  in the stitched cache at 12 workers while the prefetch ran; phase 2 on the
  other 495 at 12 workers; the phase-2 orchestrator was then killed on
  purpose and the whole list resumed at 18 workers (`--resume`: 290 to run,
  529 skipped, orphaned workers terminated from their pid files). Every
  job returned `ok` on its first attempt. Units per star median 12, max 45;
  three searches hit the 600 s detection budget (TIC 141827391, 167247580,
  167307093; 41-42 units each, 7-9 candidates each).
* **Per-target log**: `data/survey/p4/per_target_log.csv` (timing by stage,
  cache hit, products by author, sectors used, candidates, budget stop,
  provenance events). The 300 "fallback events" in the run summary are all
  `offline_cache_mode` notes inherited from the P2 rebuild of the 300
  completeness-sample stars; no download fallback occurred.
* **Socket timeout**: `scripts/survey_worker.py` now sets a 300 s default
  socket timeout (the P3 MAST-hang lesson); no job needed it.

## 3. Gates and expectations [M]

Full tables in `docs/SURVEY_RESULTS.md`. The count after G2-G4 (430) sits
inside the 311-500 range the P2 false-alarm run predicts for 819 stars, and
below the 500 that uses the same transit-count definition as G3, which is
the expected direction: the P3 fit-based flags were not in the P2 run. The
P2 sample is 300 of these 819 stars, so this is a consistency check, not an
independent prediction.

Candidates failing a gate, by first failed gate: G2 5,468 (85% of all
accepted candidates fail the whole-stitch re-measurement), G3 395, G4 85,
G5 19. Of the 6,378 accepted candidates 851 have only two transits on the
stitch. Survivor population: periods median 58 d (quartiles 21-81 d, the
long-period stitch search contributes 193 of 405), stitch SNR median 13.5
(90th percentile 34), transits median 6, depth median 3.8 ppt, implied
radius median 4.9 R_Earth (90th percentile 23); 214 "promising", 191
"ambiguous"; 51 have S_rho = 0 (a/R* inconsistent), 354 have S_rho = 1.

**Expected real signals** (`scripts/p4_expected_yield.py`,
`data/survey/p4/expected_yield_p4.json`): the P1 per-star, per-cell yield
model re-evaluated with the P2 measured recovery step function (0% below
SNR 7.1, 6% at 7.1-9, 14% at 9-12, 37% at 12-20, 64% at 20-50, 89% above)
in place of the adopted 0.8 / 0.7 / 0.4 efficiencies gives 3.32 / 2.19 /
1.12 new signals at low / mid / high prior completeness against P1's 7.13 /
5.00 / 2.88 (the script reproduces P1's 5.00 with P1's own functions first).
By class at mid priors: A 0.23, B 1.76, C 0.20. Caveat [A]: P1's SNR is a
photon-plus-floor model SNR and P2's axis is the matched-filter SNR on the
pipeline's own binned, detrended data; same symbol, different quantity.

## 4. The expensive stage [M]

`scripts/survivor_packets.py --expensive --top 30 --workers 4` on the 30
highest pre-FPP scores (27 stars; 879 sector-units between them). Per
candidate: the fresh cross-match again, a re-search for the refit (the
+/-5% whole-stitch window with the composite-score gate off, else an exact
reproduction of the survey's own sub-search), the centroid on EVERY sector
with pixel data (SPOC 2-minute TPF, else TESS-SPOC TPF, else a 21-pixel
TESScut cutout; 23 of 30 combined measurements flagged), the TIC
contamination check, TRICERATOPS (100,000 draws, binned fold, first three
sectors with a cutout, Tmag-sized circular aperture because none of these
stars has a SPOC aperture in its survey sectors), the final verdict through
`apply_pixel_checks`, and the packet.

* 30 of 30 completed (wall per candidate 47 s to 868 s, median about 6 min;
  the whole stage 2.1 h at 4 workers after a false start, section 5). The
  30th, TIC 201232256 at 12.148 d (pre-FPP rank 13), hung three times inside
  the download of one of its five TESS-SPOC target pixel files (80 min, 45
  min and 25 min with 8-9 CPU-seconds used each time; the two plan lookups
  for the star take 1 s and 9 s), and completed in 403 s once the centroid
  was taken from TESScut cutouts only (`--tesscut-only`, 8 of 8 sectors):
  FPP 0.974, final verdict likely false positive, final rank 59.
* Refit scope: the narrow window recovered 12 of 30, the exact reproduction
  the other 18 (`refit_scope` per candidate). For chunk-found candidates the
  packet fit therefore covers the events of that chunk (3-4 transits), not
  all stitch transits; stated in each case file.
* FPP: 8 of 30 at or below 0.5 (packet gate G8 passed), 22 above. SEVEN of
  the 30 TRICERATOPS runs returned a uniform posterior (every scenario at
  1/n with blank scenario names: FPP = 1 - 3/n, i.e. 0.80, 0.83, 0.86, 0.90
  or 0.91), which means every scenario likelihood was zero or NaN; those
  FPPs are artefacts of the input, flagged `fpp_uniform` in
  `survivors.csv` and named in `docs/SURVEY_RESULTS.md`. The frozen score
  used them as returned (the rule says "when TRICERATOPS returned a value")
  and was not changed. Six of the seven are deep or degenerate signals
  (59-126 ppt eclipses, or grazing rail fits); the seventh (TIC 284191194,
  73.7 d, 2.7 ppt, final verdict "promising") is the one to re-run with a
  sub-sampled fold in prompt 5.
* Final verdicts of the 30: likely false positive 19, ambiguous 7,
  promising 4 (TIC 212261364 at 8.954 d, TIC 334678787 at 46.206 d, and two
  outside the top 10 with uniform-posterior FPPs above the packet gate: TIC
  284191194 at 73.719 d and TIC 38696123 at 67.970 d).
* Final top 10 (S_fpp from the measured FPP; the same ten as the pre-FPP
  top 10 except that ranks 2-10 reshuffled): 233211748 (65.0 d, score 4.00,
  ambiguous on a 27-sigma centroid), 212261364 (8.95 d, 3.99, promising but
  on an eclipsing-binary host), 160619045 (91.7 d, 3.93, ambiguous),
  334678787 (46.2 d, 3.62, promising, every check clean), 290350156
  (13.2 d, 3.48, ambiguous on a 6-sigma centroid), then five "likely false
  positive": 21124154, 356976754, 246937997, 167304394, 233200485. Case
  files for all ten in `docs/case_files/`.
* One candidate OUTSIDE the frozen top 30 also received the expensive steps:
  the rerun for the 30th candidate selected "top 30" from the survivors
  table after the first FPP merge, in which 21 high-FPP rows had dropped
  and TIC 200658220 at 26.091 d (pre-FPP rank 20) had moved in. Per the
  frozen rule its FPP does not enter its score (`extra_expensive` column;
  `rank_survivors.py` now selects the expensive set from the pre-FPP order
  explicitly), so it stays at rank 19 with S_fpp = 0.5. Its measurements are
  worth prompt 5's attention: a 78.6-ppt (7.9%), flat-bottomed, central
  (b = 0.00) event with Rp/R* 0.258 on a Tmag 13.1 star (Rp = 13.5 R_Earth,
  1.2 R_Jup), 7 events at 26.09 d, no flags, FPP 4e-15, NFPP 1e-37, centroid
  3.7 sigma over 10 sectors, density ratio 2.4 (fit denser than the
  catalog), light-curve and final verdict "promising". A companion of that
  size on a small star is a giant planet, a brown dwarf or a late-M star;
  the light curve cannot tell them apart and one radial-velocity epoch can.
* Star-level context the frozen gates do not test: 9 of the 27 top-30
  stars carry a deep (>= 30 ppt) eclipse candidate on the same star
  (`data/survey/p4/top30_star_context.csv`); two of the top ten
  (212261364, 233200485) are shallow "candidates" on stars with 73-85 ppt
  eclipses that no catalog lists, and their high whole-stitch SNRs (120,
  124) are the deep eclipses folding into the +/-1% local BLS window, not
  coherent shallow transits (the refits give SNR 17.5 with 2 events and 7.1
  with 4 events).

## 5. Crashes and fixes forced by the run

* `stellar._parse_tic_row` (P3): a masked GAIA id in the TIC row of TIC
  167304394 raised `numpy.ma.MaskError`, which the parser's
  `except (TypeError, ValueError)` did not catch, so the whole TIC lookup
  failed for that star. Fixed to catch any exception per field. Non-fatal in
  the survey (the lookup is optional there) but it crashed the survivor
  stage's fallback path.
* `scripts/survivor_packets.py` (new, P4): blank CSV cells for a missing TIC
  mass reached `StellarParams.from_survey_row` as `''`; normalised. And the
  first design of the whole-stitch refit (a +/-2% period window through
  `search_light_curve`) returned nothing for the rank-7 candidate (an SNR-57
  stitch signal at 83.8 d): a narrow periodogram has no baseline for the SDE
  term of the composite score, so gate 4 rejected the peak. The refit now
  uses +/-5% with `min_composite_score=0` and, when that still returns
  nothing (it did for that candidate even so), reproduces the ORIGINAL
  sub-search exactly (same mask, period range, settings), which is
  deterministic and recovered the candidate at its survey period. The
  attempt sequence is recorded per candidate (`refit_attempts`).
* Process accounting on Windows: the venv `python.exe` is a launcher that
  spawns the real interpreter as a child with the same command line, so
  every worker shows as two processes; a process listing that matches on
  `run_survey.py` sees the launcher and the interpreter, not two
  orchestrators. Launching a long job from the Bash tool with `nohup ... &`
  worked but its log appeared late; the tool's own background mode is the
  cleaner way.

## 6. What was refuted or changed by measurement

* The P1 yield of 5.0 expected new signals for this population is refuted
  by the measured completeness curve: 2.2 at mid priors (section 3). This
  was anticipated by P2 and is now the number the packets are read against.
* The rank-7 narrow-window refit (section 5): the "cheap targeted re-search"
  design does not survive the pipeline's own acceptance gates for every
  survivor; the exact reproduction of the original sub-search is the
  reliable fallback.

## 7. Assumptions the results rest on [A]

* The gates and score of `docs/RANKING_SCORE.md`, including the neutral
  S_fpp = 0.5 for rows without a TRICERATOPS value and the S_rho = 0.5 for
  fits without a catalog density.
* The P2 false-alarm and completeness tables transfer from the 300-star
  sample to the whole 819-star list (the sample is a random draw from it).
* The measured-curve yield uses P1's occurrence, noise and prior-completeness
  inputs unchanged; only the efficiency is replaced.
* TRICERATOPS settings as in P3 (100,000 draws, binned fold, circular
  Tmag-sized aperture on FFI stars, first three sectors with a TESScut
  cutout); the centroid combination over sectors is inverse-variance
  weighted as in the P0 module, with its known false-flag rate on bright
  stars (P3 Part E).

## 8. Still open

1. **The P3 fit takes neither the density flag nor the density prior when
   beta is large.** The flag uses the beta-discounted profile delta chi2
   (`density_dchi2_eff`, threshold 9) but the prior is adopted only when the
   RAW delta chi2 is below 9; with beta at its cap of 5 a raw 57 becomes an
   effective 2.3, so nothing is applied and the free solution on the grazing
   rail is reported (b = 1.2, Rp/R* 0.26 +/- 39, T14 27 +/- 198 h on TIC
   233211748; the same on 160619045, 21124154, 246937997). The packet's
   `ctoi_fields.json` then carries those numbers. Not changed here (no
   vetting change without a crash); prompt 5 should adopt the prior whenever
   the flag is not raised, or quote the box, before any submission.
2. **No star-level gate.** A shallow candidate on a star with a hard-vetoed
   deep eclipse passes every frozen gate and its whole-stitch SNR is
   inflated by the eclipses (section 4). The P2 open item "objects the hard
   stop cannot see" is real in this population: at least 9 of the 27 top-30
   stars host an uncatalogued eclipsing binary or a similar deep signal. A
   second pass should mask accepted deep events before the shallow search
   and re-measure, and should carry a "same star has a deep FP" column into
   the ranking.
3. **G6 merges only exact 2:1 and 3:1 harmonics within 1%**; near-duplicate
   periods 1.3% apart and aliases such as 1.905:1 (TIC 167304394's 22.78 and
   11.96 d) went through as separate survivors. Frozen for this run.
4. **TRICERATOPS uniform posteriors** on 7 of 30 (section 4): the binned
   fold hands TRICERATOPS 150 points with a per-point error from the
   out-of-transit scatter; on 59-126 ppt eclipses and on degenerate fits
   every scenario likelihood underflows. Prompt 5 should re-run those with
   `fold_mode="subsample"` and read the scenario table, and the wrapper
   should report a uniform posterior as `available=False`.
5. **The centroid module flags 23 of 30** at 4-27 sigma on shifts of
   0.003-0.017 px (0.1-0.4 arcsec). P3 measured 3-8 sigma on known planets
   and 4-15 sigma on real blends; the survey's flags sit in and above both
   ranges, so the flag separates nothing here on its own. The per-sector
   values are kept in each candidate's JSON (`centroid.per_sector`) for a
   proper difference-image analysis in prompt 5.
6. **A TESS-SPOC target pixel file download that never returns.** TIC
   201232256's centroid stage hung three times in `SearchResult.download()`
   of one of its five TESS-SPOC TPFs, with the socket timeout and the
   per-cutout time limit both in place (neither covers a pipeline-TPF
   download that trickles). Worked around with `--tesscut-only` for that
   candidate (section 4); the general fix is the same thread-with-deadline
   wrapper around every MAST download, not just the cutouts.
7. **MAST etiquette.** Per-sector `search_targetpixelfile` / `search_tesscut`
   calls from 8 workers stalled the TESScut service for everyone (a
   `get_sectors` call took 276 s during the flood, 0.5 s after it). The
   survivor script now makes two lookups per star and downloads with at most
   4 workers; no per-sector MAST query should ever be issued in a loop again.
8. **The chunk-found candidates' packets fit only their chunk's events**
   (section 4). The all-transit fit on the stitch for TIC 334678787 (13
   events) and 290350156 (9) is the first thing prompt 5 should produce.
9. **The expected-yield recomputation uses P1's photon-model SNR as the
   argument of P2's matched-filter recovery curve**; the two are different
   quantities (section 3). A cleaner number needs the matched-filter SNR of
   each model planet on each star's own detrended curve, which the P2
   machinery can compute.
10. **`docs/SURVEY_RESULTS.md` section 3 compares against a sample of the
    same population** (300 of the 819 stars), not an independent one.

## Files

* `docs/RANKING_SCORE.md`, `docs/SURVEY_RESULTS.md`, `docs/case_files/`
  (top 10), `docs/packets/survey_v1/` (top 30).
* `scripts/rank_survivors.py`, `scripts/survivor_packets.py`,
  `scripts/p4_expected_yield.py`, `scripts/write_survey_results.py`;
  `scripts/survey_worker.py` (socket timeout); `src/tesshunter/stellar.py`
  (masked-element fix).
* `data/survey/p4/`: `candidates.csv` (every accepted candidate with gate
  decisions), `survivors.csv` (ranked), `crossmatch_rejected.csv` (none),
  `gate_counts.json`, `run_summary.json`, `per_target_log.csv`,
  `expected_yield_p4.json`, `catalog_versions_p4.json`, `expensive/` (one
  JSON per survivor: cross-match; plus centroid, contamination, TRICERATOPS,
  refit and packet for the top 30).
* `data/survey/runs/p4_prefetch/`, `data/survey/runs/survey_v1/` (one result
  JSON per star, orchestrator logs, `summary.csv`; git-ignored).
