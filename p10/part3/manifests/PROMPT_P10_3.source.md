# PROMPT 10.3: the 531 stars, real-data retention in the P8 domain

**Execution prompt for a new session. Dated 2026-09-14.** Execute P10 Part 3
as a standalone, bounded experiment. It was pre-registered in
`HANDOFF_P10.md` section 0.6 and `PROMPT_P10.md` Part 3 but never reached,
because P10 stopped at Part 2d. This prompt carries that registration
forward, adds a measured funnel-retention extension (Part G), and closes
with tables, not candidates.

The pipeline finds candidates. Nothing in this run is a detection, a
discovery, a confirmation, or a submission. Nothing is pushed. No verdict
tier is computed and no packet is written. Never write "discovered",
"planet found", or "confirmed".

Evidence tags: [M] measured in this run, [Pn] taken from prompt n,
[A] adopted before measurement, [I] interpretation. Assumptions go in their
own section of every report, never in the results.

Final state is exactly one of:

- **RETENTION_MEASURED**: Parts A to G complete on the full registered list;
  the interpretation rule of Part H did not fire.
- **RETENTION_MEASURED_CALIBRATION_OPTIMISTIC**: Parts A to G complete; the
  Part H rule fired; the five autopsies are written; the bounded `p10.1`
  iteration is either executed or costed as a next step (Part H says which).
- **INPUT_LIMITED**: a stop rule in Part I fired before the paired search
  completed. Deliver every completed measurement and the exact reason.

---------------------------------------------------------------------

## 1. Start from the existing evidence

Repository:
`C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter`
(double-nested). Branch `improve/recovery`. Recorded HEAD at writing:
`a9c9aa30` ("Complete bounded P11.5 paired development experiment",
2026-09-14 09:11 EDT). Verify the current state; do not reset to that
commit; do not discard later user work.

Interpreter: `C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe`.
`python` is not on PATH. The venv `python.exe` is a launcher plus a child
interpreter: two processes per job with the same command line. Before
anything imports tesshunter set
`LIGHTKURVE_CACHE=<repo>\data\cache\lightkurve` and `PYTHONIOENCODING=utf-8`.
`TESSHUNTER_OFFLINE=1` (set by `tests/conftest.py`) stops TIC queries in tests.

First actions of the session, in order, with the numbers written into the
handoff: `git status`; `pytest tests p11/tests p11/p11_5/tests -q` (the
P11.5 close was 891 passed, 1 skipped); confirm no live science owner
(`Get-CimInstance Win32_Process` filtered on `tesshunter` and `p11_5`,
expect none); free space on `C:` and `D:`.

Read, in this order:

- `docs/AUDIT_P10.md`; `p10/results/part2d_calibration_20260912/STOP_RULE_1.md`
  and `COMPLETENESS_P10.md`; `docs/RULES.md` section 9 (the frozen `p10.0`
  rule set and `survey_p10`).
- `HANDOFF_P10.md` section 0.6 (the Part 3 registration, binding here) and
  section 0.11 (disclosed amendments); `PROMPT_P10.md` Part 3 and the shared
  preamble gotchas 1 to 16 (gotchas 1 to 9 are in `PROMPT_P8.md`).
- `docs/incumbent_checks_p8/INCUMBENT_CHECKS_P8_DOMAIN.md` sections 4.5 and
  6 (where the 531 come from) and `incumbent_checks.py` (the domain filter).
- `p11/p11_5/DECISION_P11_5.md`, `SEARCH_ALTERNATIVES_P11_5.md`,
  `C_LOCAL_P11_5.md` (the latest measured state of the funnel).
- `p9/protocol/PIPELINE_MAP.md`; `p9/protocol/AMENDMENTS.md` section 5 (the
  corrected two-minute inventory, gotcha 15).
- `scripts/p8_download.py`, `scripts/p8_neighbours.py`, `scripts/run_survey.py`,
  `scripts/p8_funnel.py`, `scripts/audit_p5.py` (`forced` subcommand),
  `p10/protocol/p10_funnel_calibration.py`, `src/tesshunter/catalog_crossmatch.py`
  (`_parse_spoc_tce`, `hard_stop`), `src/tesshunter/verdict_tiers.py` (`k0_hard_stop`, F7).

Established facts, starting evidence and not results to regenerate:

- P10 stopped by Stop Rule 1: after-A/S SNR50 18.26 [17.69, 18.96] against
  the required 14.0; whole pre-gated funnel 952/2,100 injections. Search-only
  SNR50 under `survey_p10` is 11.58 [11.31, 11.88]; under `survey_p8` it is
  13.15 [12.86, 13.46] [P10]. The bound secondary gate rejects 200/1,164 =
  17.2% of injected planets that pass Stage A [P10].
- P11.5 measured on 120 hosts that the unchanged pre-gate/A/S route keeps
  108 of the 151 injections the search recovers (28% early-funnel loss, zero
  reverse cases); an R1 reservoir gains +2.75 pp at 2.06x the candidate load;
  every physical-chi-squared C_local policy loses real planets [P11.5].
  Nothing in this prompt retunes any of that. `survey_p10`, bound S,
  strongest-peak C(a) with conditional robust fallback, and the one-cadence
  floor remain the frozen `p10.0` choices.
- The hard stop REJECTED 531 domain stars for a bare SPOC threshold-crossing
  event and no other reason. Median Tmag 13.31 against 13.59 for the CLEAN
  domain; median 15 sectors at 200 s against 4; 355 would rank inside the
  top 2,000; modelled 5.1 funnel-grade planets [incumbent check, 2026-09-07].
  QLP has alerted zero TOIs in the domain; the domain is effectively
  unsearched to TessHunter's depth [incumbent check].
- Read-only profile of the 531 and their TCEs, 2026-09-14 [M, this prompt's
  author; reproduce it in Part A]: the pool filter of Part A reproduces
  exactly 531; Gaia dwarf check passes 473 of them; 2,809 TCE rows on the
  531 stars (median 2 per star, maximum 64); 1,669 distinct periods at 1%;
  635 rows with model SNR >= 12 and >= 3 transits on 155 stars; 362 of those
  inside 0.5 to 30 d on 108 stars; 433 of 2,809 have a period error small
  enough for an epoch check over the gap to the sector-56 window. The raw
  `sectors` field shows both multi-sector runs (`s0001-s0036`, `s0014-s0041`)
  and single-sector runs inside the search window (`s0055`, `s0060`,
  `s0086`). The last point matters: a TCE from a run inside sectors 56 and
  later is not independent data. Part B stratifies on it.
- P11's input audit: QLP sectors 80, 83, 85 carry unresolved timing
  discrepancies (166 to 206 s median offsets in sector 80) and QLP 99 to 104
  await corrected redelivery [P11]. The frozen P11/P11.5 policy excluded
  those QLP sectors. Part D applies the same exclusion here, because a
  recovered-period test with timing-defective sectors is not a clean
  retention measurement.
- Storage on 2026-09-14 [M]: `C:` 36.8 GB free of 931; `D:` 928.9 GB free.
  Pure regenerable caches on `C:`: `data/cache/lightkurve/tesscut` 20 GB,
  `data/cache/stitched` 3.6 GB. Sealed P11.5 evidence
  `data/survey/p11/p11_5/c_models_v2` 12 GB is not a cache and is not moved.
  The audit store `data/survey/audit_lc` holds 2,291 stars; sample star
  directories are 2 to 13 MB for sectors 27 and later.
- Budget: the P11/P11.5 cumulative cap of 48 scientific queue-hours has
  16.02 charged [P11.5]. This run charges against the same cap: at most
  **31.98 queue-hours** of union scientific-job intervals, failures and
  stalls included. Downloads count toward the 15 GB cumulative acquisition
  cap of which 85,401,427 bytes are used.

---------------------------------------------------------------------

## 2. What this run measures, and why it is the right next measurement

Every sensitivity number the project owns comes from injections. P9 tried
to measure real-planet retention and found zero strict-overlap hosts in the
P8 domain. The 531 stars are the only in-domain set with an independent
prior ephemeris per star, and they are the brightest and best-observed
stars in the domain. A TCE period recovered blind in sectors 56 and later,
on an independent pipeline, on FFI data, is strong evidence of a real
periodic signal, and a miss with the signal demonstrably present in those
data is a measured sensitivity loss in exactly the domain P8 targets.

The measurement has three layers, each reported separately:

1. **Search retention** (Part F): does the blind search, under the frozen
   `survey_p10` and the P8 `survey_p8` preset paired on the same stitched
   inputs, recover the TCE period?
2. **Early-funnel retention** (Part G): of the recovered TCE signals, how
   many survive pre-gate, Stage A, the bound secondary gate and Stage B
   under `p10.0`? This is the number P11.5 could only measure on injections.
3. **Calibration check** (Part H): is the injection SNR50 optimistic in this
   domain? The pre-registered rule of section 0.6 decides.

Three populations are always reported with exact counts: the original 531,
the input-eligible subset after Part A and Part D, and the evaluated subset
(Part E). Input exclusions are `INPUT_INELIGIBLE`, never misses.

Most TCEs are systematics or eclipsing binaries. "Absent in these data" is
separated from "present and missed" by the forced box fit in Part F, and a
TCE absent from the sector-56 data is not a pipeline miss. Recovery of an
eclipsing binary's period is still a valid search-retention event; the
funnel's rejection of it in Part G is reported as what it is, a measured
rejection of a periodic signal that is not a planet candidate, not a loss.

---------------------------------------------------------------------

## 3. Register before measuring

Create `p10/part3/` with `protocol/`, `manifests/`, `results/`, `logs/`,
`work/`; new scientific arrays under `data/survey/p10/part3/`. Every file
covered by the P10, P11 and P11.5 seals stays byte-identical; verify with
the existing read-only integrity checks (`p11/protocol/integrity_check.py`,
`p11/p11_5/protocol/integrity.py historical`) at the start and the end.
Never run a sealed-path historical writer.

Before any blind search runs, write and hash:

- `p10/part3/PREREGISTRATION_P10_3.md`: this prompt's rules restated with
  the exact thresholds; an amendment table listing every difference from
  `HANDOFF_P10.md` section 0.6 and why (expected: the standalone budget,
  the QLP sector exclusions, the independence strata, Part G, the C cap,
  the conditional `p10.1` iteration).
- `p10/part3/protocol/config.json`: thresholds, presets, deadlines, worker
  counts, seeds, sector policy, the nested evaluation order.
- Manifests: the 531 identities with every cut outcome; the TCE ephemeris
  sidecar hash; product identities and hashes after Part D; the exposure
  ledger (which stars were opened at which stage); source and config hashes.
- Seeds: NumPy PCG64 `2026091401` for any host bootstrap, `2026091402` for
  engineering-only synthetic tests. Host ordering for nested subsets is
  SHA256 of `20260914:p10_3:development:<integer TIC>` within the strata
  of Part E.

The search never reads the sidecar. The run manifest asserts it (list the
files each worker process opened; the sidecar path must be absent). TCE
ephemerides are opened only by Part F's matching and forced-fit code, after
the blind results are locked (hashed prediction manifest per preset).

Take one entry compatibility measurement (full regression) and one at the
end. Add focused tests for every new code path named below.

---------------------------------------------------------------------

## Part A: the list

Reproduce, in `p10/part3/protocol/build_list.py`, exactly the incumbent
check's domain filter on `data/survey/cache/p8/pool_after_xmatch.csv`
(117,171 rows):

```
Teff < 3600 and rad < 0.45 and 12.5 <= Tmag <= 14.0 and |gallat| >= 20
and n_sectors_200s >= 3 and n_sectors_2min_in_search < n_sectors_200s / 2
```

then `xmatch_status == REJECT` and `xmatch_tic_sources` exactly `spoc_tce`.
Expected 11,491 domain stars and 531 bare-TCE rejects [incumbent check;
reproduced 2026-09-14]. Report the count after each of the following, and
keep all 531 identities in the manifest with their outcome:

1. `gaia_dwarf_check == pass` (expected 473). Stars failing it are
   `INPUT_INELIGIBLE(gaia)`; they stay in the accounting.
2. The FFI-majority rule from the **corrected** two-minute inventory
   (gotcha 15: MIT two-minute lists are `sNNN.npy` under
   `data/survey/cache/target_lists`; use the corrected parser logic of
   `p9/protocol/AMENDMENTS.md` section 5, intersecting two-minute sectors
   with delivered FFI sectors). The pool's `n_sectors_2min_in_search` was
   built by the P8 builder and may be wrong for the same reason P9's was.
   Recompute it; stars with two-minute sectors not in strict minority are
   `INPUT_INELIGIBLE(ffi_majority)`.
3. The verified-usable-sector count after Part D (at least 3 usable
   sectors at 200 s under the sector policy of Part D).

Do not select or drop stars by TCE content, brightness, or apparent ease.

---------------------------------------------------------------------

## Part B: the TCE ephemeris sidecar and the independence strata

`catalog_crossmatch._parse_spoc_tce` keeps only a label and a
`P=...d SNR=...` detail string. Extend the parser to also write
`data/cache/catalogs/spoc_tce/spoc_tce.ephemerides.csv` from the raw
`data/cache/catalogs/spoc_tce/raw/*_dvr-tcestats.csv` files (132 files,
342,918 rows; header names verified 2026-09-14): `tceid`, `ticid`,
`tce_plnt_num`, `sectors`, `tce_period`, `tce_period_err`, `tce_time0bt`,
`tce_time0bt_err`, `tce_duration`, `tce_duration_err`, `tce_depth`,
`tce_depth_err`, `tce_model_snr`, `tce_num_transits`, `tce_ntoi`, plus the
source filename. Take the names from the header; do not guess them.
Requirements, each with a test:

- The normalised crossmatch table `spoc_tce.normalized.csv` and every
  crossmatch digest stay byte-identical (compare hashes before and after).
- The sidecar carries every TCE row for every TIC in the pool, not only the
  531, so the extension is not truth-guided.
- Duplicate ephemerides across runs (same star, period within 1%) are kept
  as rows; Part F deduplicates at match time and reports both counts.

Independence strata [A]: for each TCE, parse `sectors` into first and last
sector. Stratum **INDEPENDENT** when the last sector <= 55 (the TCE data
precede the search window entirely). Stratum **OVERLAPPING** when any run
sector >= 56. Report every Part F and Part G table for both strata and for
the union; the Part H rule uses INDEPENDENT only. A recovered OVERLAPPING
TCE is "same epoch, different pipeline and cadence": useful, weaker.

---------------------------------------------------------------------

## Part C: the population rule `hard_stop_p10`

Implement `hard_stop_p10` in `catalog_crossmatch` as registered in section
0.6: a TIC match in `spoc_tce` with no other source is FLAG-with-ephemeris,
not REJECT; TOI, CTOI, NASA archive and TESS-EB REJECTs are unchanged; the
21-arcsec neighbour FLAG is unchanged; stars with a promoted TOI or CTOI
remain REJECT for novelty. `hard_stop` (the P8 rule) is not edited; the new
rule is a separate named function selected by configuration. Tests: the
531 all become FLAG under the new rule and stay REJECT under the old; the
P8 2,000 are unchanged under both; the crossmatch fixtures in
`scripts/build_crossmatch_fixtures.py` still pass.

`verdict_tiers.k0_hard_stop` and flag F7 are not exercised in this run
(no verdicts), but the FLAG record must carry the ephemeris fields so a
future Part 5 can read them. Document the interface.

---------------------------------------------------------------------

## Part D: storage, sector policy and acquisition

**Sector policy [A, from P11]:** products from sectors 56 to 105 under the
existing author preference SPOC, TESS-SPOC, QLP; exclude QLP sectors 80, 83,
85 and 99 to 104 unless the corrected redelivery is verified against the
official notices with source-level timestamp evidence (no transit-based
clock check ever). Corrected QLP 74 to 79 require the saved corrected-v02
comparison. Record the notice snapshot hash. No rolling latest-sector
expansion: freeze one sector set before downloading.

**Storage [A]:** keep at least 25 GB free on `C:` at every point. Before
downloading, estimate size with `scripts/p8_download.py 4 --targets <list>
--first 50` and forecast the full acquisition from the per-star bytes
(expect 10 to 20 MB per star at a median of 15 sectors plus the 600-s era,
5 to 11 GB total; the stitched cache adds about 0.5 MB per star). If the
forecast breaches the floor, relocate the regenerable TESScut cache
(`data/cache/lightkurve/tesscut`, 20 GB) to `D:\tesshunter_cache\lightkurve\tesscut`
and leave a directory junction (`mklink /J`) at the original path, after
recording file count and total bytes before and after. Relocation of a
regenerable cache is reversible and is not deletion; record it in the
handoff. Never delete historical data. Never touch sealed P10, P11 or
P11.5 evidence to make room.

**Acquisition:** `scripts/p8_download.py 4 --targets <list>` into the shared
audit store (gotcha 2 governs every MAST call: one `search_lightcurve` per
star, at most four workers, watch for a worker whose CPU time stops
advancing past the 300-s socket timeout, stop it and rerun that star).
Then `scripts/p8_neighbours.py bulk` and `stars` for Gaia, SIMBAD and VSX
(bulk SIMBAD, 100 coordinates per query). Then the per-star noise record in
the `noise_p8` pattern (`scripts/p8_expected_yield.py --noise-only` or its
function `star_noise`, restricted to sectors 56 and later under the sector
policy), which Part F needs for expected SNR. Verify every product's TIME,
flux and quality identity against its FITS source as P11 did; truncated
FITS from MAST outages are deleted and re-downloaded, never used.

Report: products per star, usable sectors per star after the policy, and
the third Part A count.

---------------------------------------------------------------------

## Part E: timing pilot, evaluation size, and the paired blind search

**Pilot first.** Six stars, two per native-point-count tercile of the
eligible list, chosen by the timing hash (`20260914:p10_3:timing:<TIC>`),
run under `survey_p10` and `survey_p8` with `record_traces` on, at the
production worker layout. Record wall and CPU per job, and Stage A time per
pre-gate survivor. Forecast the full run from the observed distribution
and the P10 injection tails (search median 444 s, p90 1,284 s, maximum
1,682 s under `survey_p10`; Stage A median 100 s, p90 517 s; C 0.5 to 3.4 h
per run) with a 25% margin, never from a median multiplied out.

**Nested evaluation order [A].** Stratify the eligible list by Tmag band
[12.5, 13), [13, 13.5), [13.5, 14] crossed with usable-sector count 3 to 5,
6 to 10, over 10; order within strata by the development hash; weighted
deficit round-robin gives one fixed nested order. Registered levels: all
eligible, 400, 300, 200. Choose the largest level whose forecast for Parts
E, F and G (with the C cap of Part G) fits the remaining budget after Part
D, before any blind result is read. Freeze it once. Every selected star
carries all its TCEs.

**The paired search.** For the selected stars run, paired on the same
stitched cache (identical ingestion key, gotcha 11):

1. `survey_p10` (the frozen preset, 2,700 s detector budget) on every
   selected star, `--resume`, `record_traces` on so ranking witnesses and
   per-partition `budget_exhausted` flags exist for the autopsies.
2. `survey_p8` on the same stars if the forecast fits after item 1;
   otherwise on the largest registered nested subset that fits, declared
   before launch. The paired `survey_p8` versus `survey_p10` difference on
   real signals is the one measurement of the Part 2b change that
   injections cannot give; it is the first thing cut, and its cut is
   reported as such.

Operational rules: one owning controller per phase with recorded PID,
creation time and command; 24 active cores at most; single-thread BLAS
(`OMP_NUM_THREADS=1` and friends); per-job deadline 3,600 s for a search,
one attempt, a timed-out star is `OPERATIONAL_UNKNOWN` and never retried to
obtain a result; a MAST hang is a worker stall, not a scientific outcome.
An exhausted detector budget returns status `ok` (gotcha 11): read the
flag. Do not launch a second controller on this machine while one is
alive. Checkpoint per star (the run directory is the checkpoint) and
commit at phase boundaries.

Lock each preset's prediction manifest (every accepted candidate with
period, epoch, duration, depth, stitch SNR, partition and budget flags,
hashed) before Part F opens the sidecar.

---------------------------------------------------------------------

## Part F: matching and the forced fits

Matching rule [A, section 0.6 verbatim]: a TCE is recovered when an
accepted signal's period is within 1% of the TCE period or of the TCE
period times a `_match` alias ratio (2, 3, 1/2, 1/3; aliases reported,
never credited as exact). The epoch is checked only where
`sigma_P x N_cycles < T14 / 2`, with `N_cycles` counted from the TCE epoch
to the midpoint of the star's sector-56-and-later data; then the propagated
epoch must agree within `T14 / 2` modulo the period. Otherwise the match is
period-only, stated per TCE. Within a star, deduplicate TCEs whose periods
agree within 1% into one ephemeris family; report families and raw rows.

Expected SNR under P8 conditions [A]:
`SNR = (depth / sigma) x sqrt(n_cad x T14 / P)` with the TCE depth and
duration, the star's measured sector-56-and-later per-cadence sigma from
Part D, and `n_cad` the usable cadences. Report recovery by TCE model SNR
bin (< 9, 9 to 12, 12 to 20, >= 20), by expected SNR bin (0 to 7, 7 to 10,
10 to 15, 15 to 20, 20 to 30, >= 30), by period band (0.5 to 1, 1 to 2,
2 to 5, 5 to 10, 10 to 20, 20 to 30, > 30 d), by independence stratum, and
by preset. TCEs with period outside 0.5 to 30 d are outside the search
domain and reported separately, never as misses.

Forced fits, only after both prediction manifests are locked: every TCE
family on every evaluated star gets a forced box fit at its period in the
sector-56-and-later prepared data (`scripts/audit_p5.py forced --tic --period`,
or the narrow-TLS equivalent it wraps, with the one-cadence duration floor,
gotcha 12). The signal is **present** when the forced depth is at least
3 sigma at the TCE period (epoch fixed when checkable, else the best
phase), **absent** otherwise. Report the 2x2 of recovered/missed against
present/absent per stratum. "Present and missed" is the retention loss;
"absent" is not a pipeline miss.

Deliver `p10/part3/results/matching.json`, `forced_fits.json`, and the
tables in `SEARCH_RETENTION_P10_3.md`, with 10,000 paired whole-host
bootstrap intervals (seed `2026091401`) on every fraction.

---------------------------------------------------------------------

## Part G: early-funnel retention on the real signals

Run the `p10.0` funnel on the `survey_p10` run's accepted candidates
through `scripts/p8_funnel.py` (or `p10/protocol/p10_funnel_calibration.py`,
whichever carries the `p10.0` route; state which and hash it) with
`--root data/survey/p10/part3/funnel` so nothing under `data/survey/p8`
is written:

- `collect`, the pre-gate, `stageA`, `secondary` (bound), `stageB` on
  **every** accepted candidate, not only the TCE matches. Stage A at
  1,200 s per candidate, S and B at 300 s, one attempt each; timeouts are
  `OPERATIONAL_UNKNOWN`. This also measures the natural candidate load of
  these brighter, longer-baseline stars, which Part 5 would need.
- Stage C (blind TLS, `p10.0` strongest-peak with conditional fallback,
  top-level slices, gotcha 10) only on TCE-matched, likely-periodic
  (model SNR >= 12, >= 3 transits) Stage B survivors, in descending
  expected-SNR order, up to a cap `N_C` fixed before any C launch from the
  measured remaining budget using the 3.4 h tail per run and at most three
  concurrent runs. Report the cap and what it excluded. Unmatched B
  survivors do not enter C here; they are listed with their stage records
  for a future Part 5.
- No Stage D, no verdict tiers, no packets, no `ctoi_fields.json`. A signal
  that ends Part G carried is reported as "carried, unverdicted, F7
  association: SPOC TCE <run> pn <n> at P = ..., not promoted".

Report for the TCE-matched present signals: the sequential retention
`search -> pre-gate -> A -> S -> B (-> C where run)`, per stratum, per
expected-SNR bin, with the A criterion and S mode that removed each loss,
paired against the P10 injection funnel at the same expected SNR. Report
the natural load: accepted, pre-gate, A, S, B counts per star, against
P10's 11.65 / 2.36 / 0.150 / 0.0067 per control star. Every sequential
count also reports its operational unknowns.

---------------------------------------------------------------------

## Part H: the interpretation rule and the bounded iteration

Rule [A, section 0.6 verbatim]: the likely-periodic subset is TCEs with
model SNR >= 12 and at least 3 transits in their DV run, restricted here to
the INDEPENDENT stratum, inside 0.5 to 30 d, forced fit **present**. Fit
the recovery-versus-expected-SNR logistic for that subset under each
preset and compare its SNR50 with the search-only injection SNR50 of the
same preset (`survey_p10` 11.58; `survey_p8` 13.15 [P10]). If the
in-domain SNR50 exceeds the injection SNR50 by more than 30%, the injection
calibration is optimistic in this domain: say so, and autopsy the five
highest-expected-SNR misses whose forced fit shows the signal present
(event removal census, ranking witness from the traces, alias check,
budget flag, the P9 autopsy pattern). Report the subset size and the
bootstrap interval on SNR50; if the subset has fewer than 40 members, the
SNR50 is reported as a diagnostic and the rule is recorded as "not
powered", not as passed.

If one mechanism explains at least three of the five, one bounded
iteration of Part 2 is permitted for that mechanism, exactly as registered:
re-measure on the 2,100 injections, re-freeze as `p10.1`, rerun Part E for
the changed preset. It is authorized in this run **only** if the measured
remaining budget after Part G covers the P10-measured cost of the 2b
subset (600 injections plus 300 controls, 13.75 h at 24 workers [P10])
plus the Part E rerun, with a 25% margin. Otherwise write the iteration as
an exact costed next step in `DECISION_P10_3.md` and stop. Autopsies never
change a locked blind result.

---------------------------------------------------------------------

## Part I: stop rules [A]

- **STOP-1 (power):** after Part D, fewer than 60 INDEPENDENT likely-periodic
  in-band TCE families on eligible stars. Deliver Parts A to D and the
  count; final state INPUT_LIMITED.
- **STOP-2 (storage):** free space on `C:` would fall below 25 GB and the
  cache relocation of Part D cannot restore it. Deliver what is complete.
- **STOP-3 (budget):** the pilot forecast for the 200-star level, with
  `survey_p10` only and `N_C = 0`, exceeds the remaining queue-hours.
  Deliver the forecast and Parts A to D.
- **STOP-4 (integrity):** any sealed P10/P11/P11.5 hash changes, or the
  sidecar is found in a search worker's opened-file list. Stop, restore,
  report.

A stop never converts an unknown into a miss or a rejection.

---------------------------------------------------------------------

## 4. Resources, ownership, and what is forbidden

- Budget: union of active scientific-job intervals, cumulative with P11 and
  P11.5, at most 31.98 h new; downloads at most 15 GB cumulative; keep
  `C:` above 25 GB free. Reallocate prospectively from pilot evidence;
  never raise a cap because a result is disappointing.
- One owning controller at a time; verify PID, creation time and command
  before resuming after any interruption; the P11.5 pattern
  (`bounded_launch_v2.py`, `owned_worker.py`, `record_io.py` with bounded
  progress-write retries) is the known-good Windows layout; a progress
  file replace error is an operational event, not a scientific one.
- Never edit worker-loaded source while a controller is alive.
- Supervision of long phases runs on the hourly check-in routine of
  section 4a and on nothing else. The old P10 two-hour heartbeat stays
  paused; do not reuse its prompt or its schedule. Close every owned job
  and disable the routine at the endpoint.
- No Stage D, no verdicts, no packets, no CTOI fields, no external
  submission, no push. No full 2,000 or 2,531-star survey. No injection
  reruns except the conditional Part H iteration.
- The 531 are development-exposed from Part F onward. Record it in the
  exposure ledger; they can never be a holdout.
- Gotchas 1 to 16 of `PROMPT_P10.md` and `PROMPT_P8.md` bind: 8 kB Bash
  command limit and heredoc breakage (write scripts to files), stdin
  scripts cannot spawn a ProcessPool on Windows, `taskkill` is blocked
  (use `Stop-Process`), TLS only from top-level slices, QLP low-precision
  bits (2^12 before sector 56, 2^30 from 56), never stitch mixed cadences,
  gate 7 and `duration_min`, sub-cadence TLS durations floored at one
  cadence, one search per star and at most four download workers.

### 4a. Supervision cadence: the hourly check-in routine [A]

This rule exists to conserve session usage. A check every five minutes
over a ten-hour search is 120 wakeups that learn nothing a single hourly
read would not. Long phases are supervised by a scheduled check-in, never
by polling.

- Any phase whose forecast wall time exceeds 30 minutes (the download,
  each preset's search, Stage A, Stage C, the forced fits if batched) runs
  under a detached owning controller with durable per-case results and a
  `progress.json` the controller updates itself. The session does not sit
  in a wait loop watching it and does not sleep-poll.
- After launching such a phase, set exactly one recurring check-in at
  **60 minutes**, using whatever scheduling facility the session provides
  (a scheduled task, an adaptive heartbeat, or a fixed-interval loop). Two
  deliberate exceptions: one early check about 10 minutes after each
  launch, to catch an immediate crash or a mis-pointed path, and a
  shortened final interval when the forecast says the phase ends within
  the hour, so the next phase is not left idle. Otherwise never check more
  often than hourly, and never schedule extra wakeups for any other reason.
- A check-in is bounded and read-only against the science. It reads
  `progress.json`, the owner's PID and creation-time receipt, the last 50
  lines of the controller log, free space on `C:`, and the CPU
  accumulation of active workers against the previous check (the P11.5
  `allocation_health.py` pattern). It does not open per-case result files,
  does not re-read this prompt or the handoffs, and recomputes nothing. It
  writes one dated line to `RESUME_P10_3.md` (completed, pending, active,
  unknowns, disk, queue-hours) and one row to `p10/part3/logs/checkins.jsonl`.
- Triggers that end the sleep early and require action: the owner is gone
  without a closure receipt; an active worker's CPU has not advanced since
  the previous check (the MAST-hang or stall signature: stop that worker
  only, record it, let the controller continue); free space on `C:` within
  3 GB of the floor; a Part I stop rule; an error count rising between
  checks.
- When a check-in finds a phase closed cleanly, the routine may launch the
  next phase in the registered sequence (D download, D neighbours and
  noise, E pilot, E `survey_p10`, E `survey_p8`, G pre-gate and A, G S and
  B, F forced fits, G C) provided that phase's preflight passes (owner
  absent, disk, budget, hashes) and its decision is mechanical under the
  registered rules. It must **pause and hand back to a human-read session**
  at: the Part E level selection and the `survey_p8` cut decision, the
  `N_C` cap, the Part H rule outcome and any iteration, every Part I stop,
  and final delivery. Those decisions are written down before they are
  executed either way.
- Charge each check-in's own compute to engineering time, not to the
  scientific queue-hours. Record the schedule (interval, first and last
  firing, count) in the resource ledger. At the endpoint, or at any stop,
  disable the routine and verify it is disabled (the
  `automation_paused_verified.json` pattern from P10) before writing
  `DECISION_P10_3.md`. Never leave a routine armed over an idle machine.

---------------------------------------------------------------------

## 5. Delivery and final state

Under `p10/part3/`:

- `PREREGISTRATION_P10_3.md`, `protocol/config.json`, manifests (list with
  all cut outcomes, sidecar hash, product identities, exposure ledger,
  seeds, source and config hashes, prediction-manifest hashes per preset).
- `SEARCH_RETENTION_P10_3.md` (Part F tables, both presets, both strata,
  forced-fit 2x2, aliases, bootstrap intervals, budget-flag census).
- `FUNNEL_RETENTION_P10_3.md` (Part G sequential retention, per-loss
  attribution, natural load, C cap and what it excluded).
- `CALIBRATION_CHECK_P10_3.md` (Part H logistic fits, subset sizes, the
  rule outcome, the five autopsies if fired).
- `DECISION_P10_3.md`, `HANDOFF_P10_3.md`, `RESUME_P10_3.md`, resource
  ledger (queue-hours, bytes, disk before and after, cache relocation
  record, the check-in schedule and count), `logs/checkins.jsonl`, the
  routine's disabled-verified receipt, integrity receipts, final source
  and data seals.
- Tests for: the domain filter, the sidecar (byte-identical crossmatch),
  `hard_stop_p10`, the matching rule including the epoch-check condition,
  the expected-SNR formula, the forced-fit presence rule, the nested order,
  and the never-read-the-sidecar assertion.

`DECISION_P10_3.md` states, in this order: the final state; the three
population counts; search retention under each preset with intervals;
early-funnel retention with the losses attributed; the natural load; the
Part H outcome with subset size; operational unknowns by stage; cost in
queue-hours, bytes and disk; every criterion not met; and what remains
unmeasured (B/C specificity on these stars, D, every endpoint claim). It
also carries forward the unretuned endpoint risks: TOI-762 A b and
TOI-122 b are confirmed planets rejected by the `p10.0` tiers, and
TIC 144277542 changes from artefact KILL to SUBMIT under rescoring.

Commit only explicit `p10/part3/`, the sidecar and parser change, the
`hard_stop_p10` implementation and tests, locally on `improve/recovery`,
with a message naming prompt 10.3. Do not push. Do not repack. Do not
commit the audit store or stitched cache. End by stating what was
implemented, which populations were actually evaluated, the measured
retention at each layer, the calibration-rule outcome, the total cost, and
what a Part 5 rerun on the 2,000 plus these stars would need from here.

**Finish the feasible measurement rather than stopping because some
original stars lack coverage. Keep the registered rules; make the
population and evidence limits explicit; produce tables, not candidates.**
