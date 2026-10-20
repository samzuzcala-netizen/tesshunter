# PROMPT 8: small stars, not more of the same

Run in a fresh session. Read first, in this order: `HANDOFF_P7.md`,
`HANDOFF_P6.md` sections 2 and 5, `docs/RULES.md`, `docs/AUDIT.md` section 6,
`docs/POPULATION.md` section 4, `docs/COMPLETENESS.md`, `HANDOFF_P4.md` (the
survey run and its MAST lessons), `HANDOFF_P2.md` (the survey engine and the
cadence rules). `CTOI_PROMPTS.md` holds prompts 1 to 5 and the shared rules;
this prompt follows the same rules and the same evidence discipline.

The pipeline finds candidates. Nothing in this prompt is a detection, a
discovery, or a confirmation. The agent never submits anything anywhere.

---------------------------------------------------------------------

## SHARED PREAMBLE (updated through prompt 7)

Environment facts, verified 2026-09-03:

- Repo: `C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter`
  (double-nested). Branch `improve/recovery`, HEAD `5fa0cdb` (prompt 7).
- Python: `C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe`
  (3.13, lightkurve 2.6.0, numpy 2.5.1, numba, batman, transitleastsquares
  1.32, wotan 1.10, TRICERATOPS with the hand-made celerite shim). The venv
  `python.exe` is a launcher plus a child interpreter: two processes per job
  with the same command line. Count and kill accordingly.
- Before anything imports tesshunter set
  `LIGHTKURVE_CACHE=<repo>\data\cache\lightkurve` and `PYTHONIOENCODING=utf-8`.
  `TESSHUNTER_OFFLINE=1` (set by `tests/conftest.py`) stops TIC queries.
- First action of every session: `git status`, count files under
  `data/cache/lightkurve`, run `pytest tests/ -q` (prompt 7 left 447 passed,
  1 skipped, about 3 minutes). Do not trust the previous handoff's claim
  that the tree is healthy. Measure it.
- Machine: 24 cores, about 229 GB free on C: at the time of writing. The disk
  has filled once before (prompt 3). Check free space before every bulk
  download and write the number in the handoff.

Binding gotchas, all learned the hard way (prompts 2 to 7):

1. The Bash tool truncates near 8 kB and heredocs break on Python triple
   quotes: write scripts to files and run the files. `taskkill` is blocked;
   use `Stop-Process`. Launch long jobs with `run_in_background`, not `nohup &`.
2. MAST: never issue per-sector lightkurve searches from many workers. One
   `search_lightcurve` or `search_targetpixelfile` per star, one
   `Tesscut.get_sectors` per star, then download per sector with at most
   4 workers. A worker can hang forever past the 300 s socket timeout: watch
   for a worker whose CPU time stops advancing, stop it, re-download that
   star alone.
3. QLP: sectors 56 and later have all-NaN `det_flux_err` (the ingest fills
   it); the low-precision bit is 2^12 in sectors 1 to 55 and 2^30 from 56 on
   (`audit_prep.product_bitmask` knows this).
4. Cadence: the flatten window is in cadences, so never stitch mixed
   cadences. `ffi.stitch_prepared` refuses products whose cadences differ by
   more than 1.5x. The survey's `target_cadence_minutes` bins finer products
   to a common cadence; a product it cannot bin is dropped, never mixed in.
5. TLS uses `multiprocessing.Pool` internally: run it only from a top-level
   subprocess slice, never inside a `ProcessPoolExecutor` worker. Use N
   slices x 1 thread. TLS fits sub-cadence dips of arbitrary depth to deep
   outliers: mask the low-precision bits, drop isolated single-cadence dips,
   clip binned points deeper than 3x the candidate depth, require SDE >= 9.
6. The wotan biweight absorbs part of every transit: a clean signal comes
   back at 0.5 to 0.9 of its survey depth (median 0.667 unmasked, 0.830
   masked, prompt 7). A depth ratio near 0.7 is normal, not evidence against.
7. Gate 7 arms when `duration_min` is shorter than two binned cadences.
8. On a variable star a box scan finds ppt dips at many phases. A dip away
   from phase 0 is a secondary only when the scan is otherwise quiet.
9. Every stage that can take more than a few minutes gets a checkpoint and a
   `--resume`. This desktop has had unexplained process-tree kills.

Rules for this prompt, unchanged from the shared rules:

1. Commit at the end on `improve/recovery` with a message naming prompt 8.
   Do not push unless told. Interim commits at the end of each part are
   encouraged; this prompt is long.
2. Write `HANDOFF_P8.md`: what shipped, what was measured (with sample
   sizes), what was refuted, what is still open. Evidence tags on every
   number: [M] measured this prompt, [Pn] taken from prompt n, [A] adopted.
   Assumptions in their own section, not in the results.
3. Never write "discovered", "planet found", or "confirmed".
4. The agent never submits to ExoFOP, MAST, or any external service.
5. If a lead is refuted by measurement, say so and do not build it.
6. Decision rules are written down before the measurement that they judge,
   and are not tuned after seeing the real candidates.

---------------------------------------------------------------------

## Why this prompt exists

Seven prompts have measured the pipeline from every side. The picture is
consistent and it says the population, not the pipeline, is what to change:

- Sensitivity is the weakness. Recovery of injected transits crosses 50% only
  at matched-filter SNR 26.5 and 90% at 97.6, on 30-minute bins [P2]. The
  measured-curve expectation for the 819 G/K dwarfs was 2.19 new signals [P4],
  not the 5.0 the adopted efficiencies promised [P1].
- False-positive control is now the strength. 405 survivors were re-vetted
  under the audit rules and every one was killed on evidence [P6]; 302 of 405
  were carried by an event a removal rule takes away [P6]; the rules
  reproduce bit for bit in the package with 142 tests [P7]; the full-phase
  secondary scan found the 52-sigma feature at phase 0.605 that two earlier
  passes were blind to [P6, P7].
- Depth scales with 1/R*^2. A 2 Earth-radius planet is 0.34 ppt on a Sun and
  3.7 ppt on a 0.30 R_sun M dwarf. That moves it from far below this
  pipeline's floor to above it. Small planets are also about twice as
  common per star around M dwarfs [A: Dressing & Charbonneau 2015 against
  Kunimoto & Matthews 2020, both already transcribed in
  `tesshunter.occurrence_grids`].

One change of population buys more yield than any further pipeline work.
This prompt makes that change and measures, before searching, whether it
buys enough to be worth the search.

---------------------------------------------------------------------

## The population, defined

Every cut below is a definition. Where a cut depends on a measurement (light
curve coverage, incumbent coverage), the measurement is made in Part 1 and
the cut is applied to it; nothing is assumed about coverage.

- **Stars**: TIC Teff below 3600 K and TIC radius below 0.45 R_sun, TIC
  luminosity class dwarf where the TIC gives one. Confirm dwarf status from
  the TIC's own Gaia columns (parallax, G, BP-RP): absolute G consistent with
  a main-sequence M dwarf. Drop stars the check fails and count them; TIC
  Teff and radius at these magnitudes are less reliable than at Tmag 12
  [P1, docs/POPULATION.md section 6].
- **Brightness**: Tmag 12.5 to 14.0. Extend the ceiling toward 14.5 only if
  Part 1 measures that QLP or TESS-SPOC light curves exist at sector 56 and
  later for a comparable fraction of stars in 14.0 to 14.5 as in 13.5 to
  14.0. The pipeline does not ingest TGLC; do not add a reader for it in
  this prompt.
- **Sky**: |b| >= 20 deg, as in prompt 1 (crowding and contamination).
- **Sectors**: at least three sectors at 200-second FFI cadence, which means
  sector 56 onward, each with a QLP or TESS-SPOC light curve. Sectors 27 to
  55 (600 s) and 1 to 26 (1800 s) are recorded per star but do not count
  toward the three. Whether the 600-second sectors enter the search at all
  is a measured decision in Part 1, not a preference.
- **FFI-only**: SPOC 2-minute products in at most a minority of the sectors
  that enter the search. Report the population size at zero 2-minute sectors
  and at "minority" so the trade is visible. SPOC searches its 2-minute
  targets thoroughly and its TCEs are already in the hard stop; the thin
  incumbent coverage is on FFI-only stars.
- **Hard stop**: CLEAN under the prompt-1 cross-match with freshly
  downloaded catalogs (all six sources, TIC ID match rejects, 21-arcsec
  neighbour match flags, FLAG stars excluded from the target list).
- **Size**: 1,000 to 2,000 stars. If more qualify, rank by each star's own
  expected-new-signal score under the Part 1 yield model, as prompt 1 did,
  and cut at 2,000. If fewer than 1,000 qualify, relax in this order and
  write down what was relaxed: the Tmag ceiling (only where coverage is
  measured, above); the radius cut to 0.50 R_sun. Do not relax the three
  sector minimum or the Teff cut.

Why the cadence cut is not cosmetic: the phase-independent window test that
made two top-10 candidates falsifiable in minutes needs sectors at 600 s or
finer [P5, P6], and it has power only below about 17 d because a sector spans
25 d [P6]. At native 200 s cadence the search runs on the data the vetting
runs on, not on 30-minute bins of it.

---------------------------------------------------------------------

## Part 1: build the population, measure the expectation, decide whether to search

### 1a. Population build

`scripts/build_survey_population.py` samples 240 tiles of 0.75 deg
(420 deg^2, 1/65 of the |b| >= 20 sky) [P1]. That sample held 2,450 faint M
dwarfs at Tmag 13.5 to 15 with 4 or more sectors [P1]; the cuts above are
narrower in Teff, radius and Tmag and stricter on cadence, so 240 tiles will
not deliver 1,000 stars. Do not scale the tiles up blindly. Build the pool
by a direct TIC query on the cuts (Teff, radius, Tmag, |b|) over the whole
sky in declination or RA strips with a reproducible script
(`scripts/build_p8_population.py` or a new stage of the existing builder,
your choice; one command, seeded, cached per strip). Reuse without change:

- the vendored tess-point for sectors observed per star (cap at the last
  sector with public data on the build date; record it);
- the `products` stage's streamed QLP and TESS-SPOC per-sector target lists
  (already cached under `data/survey/cache/products` for sectors 1 to 105;
  refresh and extend to whatever is public now);
- the hard stop in `tesshunter.catalog_crossmatch` with its 7-day cache and
  version stamp; a fetch failure fails the run loudly.

For the 2-minute check use a bulk method (per-sector 2-minute target lists,
or one bulk MAST observations query over the whole TIC list), never one
search per star. State the source.

Output `data/survey/targets_p8.csv` with the prompt-1 columns plus: sectors
at 200 s, sectors at 600 s, sectors with SPOC 2-minute data, the Gaia-based
dwarf check result, and the catalog version stamp. Write
`docs/POPULATION_P8.md` from the JSON the script writes, as prompt 1 did.

### 1b. Gaia for every star, up front

Prompt 7 could evaluate the Gaia penalty for 36 of 405 candidates because
Gaia was queried only for stars that reached Stage B [P7]. Run the 1-arcmin
Gaia DR3 cone (`audit_p5._gaia_cone` and the neighbour record it feeds) for
every star in `targets_p8.csv` before the search, cached per star in the
layout `star_vet.gaia_flag_digest` and `ranking.gaia_penalty_flags` already
consume, so no rule code changes. Use a single asynchronous TAP job with an
uploaded table if the per-star cones would exceed an hour; at most two Gaia
jobs in flight. Record RUWE, `ipd_frac_multi_peak`,
`astrometric_excess_noise_sig`, `non_single_star`, `phot_variable_flag`, and
every neighbour within 3 px bright enough to make a 1 ppt dip if totally
eclipsed. SIMBAD and VSX within 1 arcmin for every star as well; they are
cheap and prompt 5 and 6 killed three candidates with them.

### 1c. Raw products for every star

The prompt-6 funnel needs the raw per-product arrays (SAP, corrected flux,
quality, per product per sector) that `scripts/p6_download.py` fetched for
261 stars into `data/survey/audit_lc/` [P6]. Fetch the same for every P8
star, all sectors at 200 s (and 600 s if 1d admits them), with the download
discipline of gotcha 2. Estimate the size from the first 50 stars and check
disk before continuing. These arrays feed both the search preprocessing and
the event rules, so the search and the vetting see identical inputs.

### 1d. Search configuration at native cadence

Add a `SurveyConfig` preset (`survey_p8`) rather than overriding `survey_v1`
on the command line, so the ingest key and every record name it. Fields to
set and justify: `target_cadence_minutes` and `bin_minutes` at the native
200 s (no binning), `period_min` 0.5 d, `period_max` 30 d for the band the
yield model counts (a second, long-period pass to the baseline is allowed
only after the short band is done and is reported separately),
`duration_min` and `duration_max` for M-dwarf transits (a central transit at
0.5 d on a 0.3 R_sun star is under an hour), the chunked plan unchanged.
Preprocessing is the prompt-6 recipe in `tesshunter.audit_prep`
(`prepare_series`: quality and low-precision masks, per-product biweight,
upward clip for flares, deep-outlier clip), applied to the corrected flux
with the SAP array carried alongside. Wire it in as a preprocessing option
of the survey search, not as a replacement of the survey module; the
`survey_v1` path must still reproduce prompt 4 (one smoke test on
TIC 100196477 against its stored record).

M dwarfs bring flares and fast rotation. The upward clip handles the first;
for the second, measure a rotation proxy per star from the light curve
itself (Lomb-Scargle peak period and amplitude on the corrected flux) and
store it in the star record. If a rotation-aware biweight window (shorter
than 3x T14 on fast rotators) is needed, decide it on the injection set in
1e, not on real candidates.

### 1e. Completeness and false-alarm budget at native cadence, through the whole funnel

Prompt 2 measured completeness of the search alone. The expectation this
prompt needs is completeness of the search followed by the gates, because a
signal the funnel kills is not a candidate. Measure both.

- Sample 300 stars at random (seeded) from `targets_p8.csv`;
  `scripts/make_injection_spec.py --targets data/survey/targets_p8.csv`
  with `--rp-min`/`--rp-max` set to cover 1 to 4 Earth radii on these stars
  and a new `--period-bins` option (the bins are hardcoded to 1 to 40 d
  today) set to four log bins over 0.5 to 30 d, at least 2,000 injections.
  Batman with Claret limb darkening by Teff, as before.
- Inject into every flux column of every product, SAP and corrected alike,
  before any preprocessing. This matters: the "dip absent in SAP" rule
  removed 164 events in prompt 6 and would kill any injection made only in
  the corrected flux.
- Run the search (`scripts/run_survey.py --config survey_p8 --injections
  ...`), then run every recovered injection through Stage A of the funnel
  and the secondary scan under `p7.0`. Report recovery by expected SNR
  (matched-filter SNR on the star's own un-injected prepared curve, the
  prompt-2 definition), by period, by radius, by Tmag, and by the rotation
  proxy. Report SNR50 and SNR90 for search-only and for search-plus-gates.
- False alarms: the same 300 stars with no injection, through the search and
  the same gates. Report candidates per star at each stage. This is the
  false-alarm budget for the population.
- The 600-second decision: if 1a admits sectors 27 to 55, rerun a 100-star
  subset of the injections at a 600 s common cadence with those sectors
  included and compare recovery with the 200 s-only run on the same
  injections. Decide before Part 2 and write the numbers down.

### 1f. The expectation, and the stop rule

Replace the prompt-1 adopted efficiencies and the prompt-4 step function
with this prompt's measured recovery curve, using `tesshunter.survey_yield`
and the pattern of `scripts/p4_expected_yield.py`. The per-star SNR of each
occurrence cell comes from the star's own measured noise on its prepared
native-cadence curve, not from the photon model. Occurrence: the DC15 grid
for Teff <= 4000 K, already transcribed, with the adopted 4 to 20 Earth-radii
rate of 0.01 per star [P1]. As a sensitivity, not the central model, report
the yield under a mid-to-late M dwarf rate from the literature if you can
cite one (state the source and the transcription). Prior completeness for
FFI-only stars at these magnitudes is adopted; use the prompt-1 faint
M-dwarf priors and report high, mid and low.

Write the expected number of new signals through the funnel, the expected
number of funnel-passing false alarms, and their ratio, in
`docs/POPULATION_P8.md` and `HANDOFF_P8.md`.

**Stop rule, fixed now:** if the mid-prior expectation through the funnel is
below 3.0, stop. Write the handoff with the population, the completeness
map, the false-alarm budget and the expectation, commit, and report that
the search is not worth running on this population. That is a cheaper
null than a search. If the expectation is 3.0 or more, proceed to Part 2.
Report the high-prior number next to it either way; if the high-prior
expectation is below 1.0, say so in the first line of the handoff.

---------------------------------------------------------------------

## Part 2: search at native cadence

Run `scripts/run_survey.py --config survey_p8 --targets
data/survey/targets_p8.csv --out data/survey/runs/survey_p8` at 12 to 16
concurrency with `--resume`, after a `--prefetch` pass that builds the
stitched cache (the prompt-4 pattern: prefetch at 8 workers, search the
cached stars while the prefetch finishes, then `--resume` on the full list
for retries). Log per-star timing, products used, sectors used, and every
fallback. Any star that errors is retried once, then listed.

Every candidate the search accepts goes into the funnel in this order, with
nothing expensive before the cheap gates:

1. Stage A event rules and the six criteria at native cadence
   (`scripts/revet_p6.py --rules <version> stageA`), on the raw arrays from
   1c. Prompt 6 ran this at 17 s per candidate at 30-minute bins; expect
   more at 200 s and measure it.
2. The full-phase secondary scan (`tesshunter.secondary`, about 10 s per
   candidate [P7]) on every Stage A passer, and on a random 10% of Stage A
   failures so the handoff can say what the gate does on things Stage A
   already killed.
3. Stage B: the phase-independent window test (now with power on most of
   the band, since every star has 200 s sectors and P < 30 d), the
   long-period flag, the Gaia and VSX flags from 1b, the deep-event host
   flag. Record the Stage B `t14_hours` unrounded; prompt 7 found the
   rounded field makes a Stage B record non-replayable [P7, finding 7]. Fix
   that here since Stage B records will be produced in volume.
4. Stage C: blind TLS on survivors only, top-level slices, the prompt-5
   masks and SDE >= 9.

Which rule version the funnel runs under is decided in Part 3. Part 2's
search may run while Part 3 is measured, but **no real P8 candidate enters
step 1 until Part 3 has committed `p8.0`**. Do not look at the real
candidate list while Part 3 is being measured.

---------------------------------------------------------------------

## Part 3: settle the three rule decisions prompt 7 left open, by measurement

Prompt 7 implemented four options as `p7.0` and refused to defend three of
the choices [P7, section 6]. This part decides them with one instrument
and pre-registered decision rules. The instrument is the same for all three:

- **Funnel completeness**: the fraction of recovered P8 injections (Part 1e,
  true planets by construction, constant depth by construction) that pass
  the gate under each variant.
- **Retained kills**: the fraction of the prompt-6 candidates the gate killed
  under `p7.0` that it still kills under the variant, using the 405 records
  already in `data/survey/p7/options/` (rerun with the variant; do not
  re-download), and the kill rate on the prompt-3 adversarial EB and blend
  lists (`data/adversarial/targets_v1.csv`, 18 EBs and 22 blends, light curves
  cached).

Write the decision rule for each decision in `HANDOFF_P8.md` before running
the measurement, in this form: "choose the variant with the highest funnel
completeness among those that retain at least X% of the p7.0 kills on EBs
and blends", with X stated. Do not change X after the numbers are in. No P8
real candidate is used in any of these measurements.

**Decision 1: the secondary gate and the quiet-scan requirement.** Under
`p7.0` the gate fails 156 of the 234 candidates that reach it, 78 of them
variability-flagged and 41 with quiet scans of at most two dips; at these
periods the planetary bound is 1e-3 ppt, so the gate reduces to "the SAP
depth at the deepest off-phase dip is more than 3 sigma from zero" [P7,
finding 1]. Variants to measure: (a) `p7.0` as is; (b) fail only when the
scan is quiet (at most 2 dips) and the off-phase dip is more than 3 sigma
above the bound; (c) 3 sigma above zero and at most N dips, N in {2, 3, 5};
(d) (b) with the variability flag demoting to HOLD instead of passing.
Recompute the planetary bound per star from each star's own a/R* and Teff;
on a 3400 K star at 10 d the equilibrium temperature is near 360 K and the
bound is smaller still than on the G/K sample, so the gate collapses even
more completely to "3 sigma from zero" here. That is why the decision
matters more on this population, and why the G/K numbers must not be
carried over.

**Decision 2: depth consistency on white errors with beta reported, or on
inflated errors.** A per-sector beta clipped at 5 turned p = 1.2e-24 into
p = 0.97 [P7, finding 2]. Injections have constant depth by construction,
so the white-error p-value on recovered injections should be uniform if the
errors are right; its fraction below 1e-3 is the white gate's false-kill
rate, and the same for the inflated gate. Retained kills: the 18 prompt-6
candidates that failed only depth consistency (EBs and spotted stars) and
the adversarial EBs. Variants: white errors with beta reported (the gate on
white); inflated errors; white errors with the threshold moved; inflated
with the cap at 2 or 3 instead of 5. Whatever is chosen, both p-values stay
on every record.

**Decision 3: the masked detrend and the inflation together.** Under `p7.0`
depth consistency is gained by 13 and lost by 42, net worse, because the
masked detrend recovers more depth and so makes depth variation more
significant [P7, finding 3]. Measure the four combinations (mask on/off x
inflation on/off) with the same instrument; the winning combination of
decisions 2 and 3 is chosen together, not stacked.

Ship the result as `RuleSet` `p8.0` in `tesshunter.audit_rules`
(`p7.0` and `p6.2` untouched, so prompts 5 to 7 still reproduce; run
`scripts/p7_reproduce.py all --slices 16` once after the change and quote
its 0/0/0.0 line), with tests for each new threshold fired and just-not-fired
in the pattern of `tests/test_event_vet.py` and `tests/test_secondary.py`,
and a section in `docs/RULES.md` with the measured tables. Then, and only
then, the real P8 candidates enter Part 2 step 1 under `--rules p8.0`.

---------------------------------------------------------------------

## Part 4: verdicts, and the code that has never run

Order Stage C survivors by `ranking.score_v2` with the Gaia term now real
for every star (state how many rows have a Gaia record; it should be all).
No verdict depends on rank.

Before any real candidate reaches it, exercise the untested path end to
end on something that is not a P8 candidate: `audit_p5.fit_step`,
`write_ctoi_fields` and `revet_p6.py verdict`, on one recovered P8
injection and on the prompt-3 demonstration target (TOI-270 c,
`docs/packets/toi270_c_demo`). Prompts 5, 6 and 7 all left these as
unexercised code [P7, section 6]. Fix what breaks, with a test. The
prompt-5 fit rule applies: adopt the density prior when the data cannot
reject it; report the grazing-rail problem if it recurs.

Stage D for every Stage C survivor: fresh hard stop (re-download all six
catalogs; new TOIs appear weekly and M dwarfs are a TOI-rich population),
the physical fit with all transits, TRICERATOPS with the cached Gaia
neighbours (binned fold by default, `fpp_uniform` flagged as in prompt 4),
centroid from TESScut (FFI-only stars have no pipeline TPFs [P4]), the
packet, and `ctoi_fields.json`. Then `docs/AUDIT_P8.md` with, per survivor,
SUBMIT, HOLD (what would change it) or KILL (why), and the ordered submit
list with the two-sentence ExoFOP note for each. A clean null is a
legitimate outcome and is reported plainly.

Expectations to carry in, so they are recognised and not mistaken for
findings: flares (the upward clip), fast rotation (the biweight and the
rotation proxy), and noisier QLP photometry at Tmag 13 to 14 with the
artefact classes of the prompt-6 census (PDC-made dips in 232
sector/camera/CCD combinations, cameras 3 and 4 carrying 73%, 291 of 467 in
sectors 56 and later [P6]). Add a census of the P8 candidates in the same
eight classes so the two populations can be compared.

Uncatalogued eclipsing binaries the funnel kills are still worth a line in
the handoff and, if clean, an EB report in the pattern of
`docs/eb_reports/` (prompts 5 and 6 found two).

---------------------------------------------------------------------

## Acceptance

- `data/survey/targets_p8.csv` and `docs/POPULATION_P8.md` exist and are
  reproducible from one seeded command; every cut's count is in the memo,
  including the Gaia dwarf check, the 2-minute check at zero and minority,
  and the coverage measurement that set the Tmag ceiling.
- A Gaia, SIMBAD and VSX record exists for every star in the list.
- Completeness and false-alarm budget at native cadence exist with sample
  sizes, search-only and through the gates, with SNR50 and SNR90 for both.
- The expectation through the funnel is written with high, mid and low
  priors, and the stop rule was applied as written. If the run stopped, the
  handoff says so in the first line.
- If the search ran: every star ran or the handoff lists which did not and
  why; the funnel counts are in a table (candidates, Stage A, secondary,
  B, C, D); the artefact census exists.
- `p8.0` exists with tests, its three decisions each have a pre-registered
  rule and a measured table, `p7_reproduce.py` still reports 0/0/0.0, and
  `p6.2` and `p7.0` records are unchanged.
- `fit_step`, `write_ctoi_fields` and `verdict` have each run to completion
  at least once, on a non-candidate, with a test.
- Suite green. Commit on `improve/recovery` naming prompt 8. Write
  `HANDOFF_P8.md`.

The human then reads `docs/AUDIT_P8.md` if it exists, opens every packet,
and submits only the SUBMIT verdicts, by hand, on exofop.ipac.caltech.edu.

---------------------------------------------------------------------

## Budget and sequencing

Rough wall-clock, so the session can be planned and split if needed; all
[A] until measured: population build and coverage stages 1 to 3 h (TIC
strips, target lists, hard stop); Gaia and neighbour records 1 to 2 h;
raw product downloads for 1,000 to 2,000 stars at 4 workers several hours
(run in the background while 1d and the injection spec are built);
injections plus false-alarm run 2 to 4 h at 16 concurrency; the search 1 to
3 h; the Part 3 measurements 1 to 2 h; Stage D minutes per survivor. If the
session must be split, split at a part boundary, commit, and leave a
"resume here" line at the top of `HANDOFF_P8.md`.
