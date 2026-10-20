# PROMPT 12: freeze the best justified configuration, measure the launch bar, run one final search, state what the pipeline cannot find

**Execution prompt for a fresh session (Claude or Codex). Written 2026-09-22 from evidence verified on 2026-09-16 and 2026-09-20.** Self-contained: every path, threshold, seed, stop rule, deliverable and final state is inside it. Bring the TessHunter pipeline to the configuration `p12.0` the sealed evidence can justify, measure a launch bar on material no P12 rule was tuned on, run one final search of the core population under `p12.0` frozen before any real candidate of that population is opened, and deliver a candidate list, a completeness statement, a specificity statement and an audit the user can act on.

The pipeline produces candidates. Nothing in this run is a detection, a discovery, a confirmation or a submission; never write "discovered", "found" or "confirmed" for anything the pipeline produces (catalogue planets used as labels are "truth positives"). The agent never submits, never pushes, never deletes historical data. Evidence tags on every number in every report: `[M]` measured in this run, `[Pn]` inherited from prompt n, `[A]` adopted before measurement, `[I]` interpretation. Assumptions live in section 9 and in their own section of every report, never inside results. Every run ends in exactly one final state of section 8.

**First session (binding): execute Part 0 as the bounded engineering sprint of section 10 (one lead, three subagents, four hours, a durable handoff). Read section 10 before Part 0. Every later session resumes from `RESUME_P12.md` and `HANDOFF_P12.md`.**

---------------------------------------------------------------------

## 0. Shared preamble

### 0a. Environment facts (re-measure each in Part 0 and record it in `HANDOFF_P12.md`)

- Repository `C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter` (double-nested), branch `improve/recovery`, HEAD `863c01be5`, tracked tree clean. Untracked: in the root `PROMPT_P10_3.md`, `PROMPT_P12_DESIGN_BRIEF.md`, `P12_DESIGN_RATIONALE.md` and this file; under data about 2,540 `data/survey/p10/fa_2b/*/tls/*_lc.npz`, `data/survey/p10/part3/`, `data/survey/p11/p11_5/`, `data/survey/p10/part2d/injection_search/{manifest.json,progress.jsonl,summary.csv}`, some `p10/logs/*.log`, `p10/results/takeover_20260908/{corrected_c_control_queue,original_adversarial_c_queue}.json`, `p11/p11_5/manifests/local_commit_receipt.json` and `p11/p11_5/results/controllers/development_complete/progress.json.tmp` and one file under `data/survey/p10/stage_c/adv/adv_corrected_native/eb_tic135085261_candidate1/` (git status re-read 2026-09-22). Never reset, discard, delete or commit them; do not edit `.gitignore`.
- Interpreter `C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe` (Python 3.13.3), written `PY`; `python` is not on PATH. The venv `python.exe` is a launcher plus a child: two processes per job with the same command line; identity is pid + create_time + cmdline; kill children first (`controller_v4.py` `terminate_owned`).
- Before anything imports `tesshunter`: `LIGHTKURVE_CACHE=<repo>\data\cache\lightkurve`, `PYTHONIOENCODING=utf-8`; workers also `PYTHONDONTWRITEBYTECODE=1` and every BLAS, numexpr and numba thread count 1 (`p10/part3/protocol/common.py` `environment()`); `TESSHUNTER_OFFLINE=1` for tests and offline workers. `scripts/audit_p5.py` line 117 sets `LIGHTKURVE_CACHE` to `data/cache/audit_lightkurve` (on `C:`) at import and `scripts/p8_stage_d_packets.py` line 180 passes it to `run_fpp`: every P12 module importing `audit_p5` resets it and `audit_p5.AUDIT_CACHE` to a `D:` path after the import (Part 0b).
- Machine (2026-09-20): 32 logical / 24 physical cores, 63.8 GB RAM; `C:` 55.4 GB free (46.1 GB on 2026-09-16); `D:` 906.3 GB free. Measured layouts (`p10/part3/protocol/config.json`; `p11/p11_5/protocol/cpu_allocation.py`): 24 single-thread workers on CPUs `[0,2,...,14] + 16..31`; 4 download; 2 neighbour; 8 verify; Stage C 3 jobs x 8 TLS threads. C beside a 24-worker phase, or more than 24 active cores, is unmeasured: never.
- Junctions: `data/cache/stitched` -> `D:\tesshunter_cache\stitched` (6,658 files, 3.76 GB); `data/cache/lightkurve/tesscut` -> `D:\tesshunter_cache\lightkurve\tesscut` (324 files, 21.0 GB); receipts `p10/part3/manifests/cache_relocation_{stitched,tesscut}.json`. Count through junctions with PowerShell or `os.walk` (Git Bash `find` reports 0).
- `C:` holds `data/cache/audit_lightkurve` 68.7 GB (80,093 files), `data/survey/audit_lc` 13.2 GB (82,807 files), `.git` 10.4 GB (23,921 loose objects). Floor 25 GB free; abort a phase at floor + 1 GB; warn within 3 GB (`config.json` budget; `checkin.py` line 31).
- Git, repo-local: `maintenance.auto=false`, `gc.auto=0`, `gc.autoDetach=false`; keep them.
- Codex automations `prompt-10-3-hourly-check-in` and `continue-local-p10-execution` (`C:\Users\seanj\.codex\automations\<id>\automation.toml`) are `PAUSED` and stay so. No `controller_owner.json` under `p10/part3/manifests` or `p11/p11_5/manifests`; no python process alive.
- Tests (`p10/part3/results/final_regression_isolated.json`): `PY -m pytest tests p11/tests p11/p11_5/tests -q` 891 passed, 1 skipped, 270.5 s; `PY -m pytest p10/part3/tests -q` 116 passed, 8.0 s; separate processes. `PY p9/verify.py` last gave 397 checks with only `baseline_git_HEAD_unchanged` failing (`HANDOFF_P10.md` lines 1416 to 1418); it rewrites `p9/results/verification.json`, a sealed path, so P12 never runs it (gotcha 14): the same 397 checks run through the copy `p9_verify_p12.py`, which writes only under `p12/logs/`.
- Catalogue stamp `data/survey/catalog_versions_p8.json` (2026-09-04); TOI snapshot 2026-09-08 (`docs/incumbent_checks_p8/toi_fetch_stamp.txt`). No qualifying sector release for the 2,000 between 2026-09-05 and 2026-09-12 (`p11/INPUT_AUDIT.md`).
- Population pins (SHA-256): `data/survey/cache/p8/pool_after_xmatch.csv` `09fa6982494b7c9510f87b9a66e13c02fe8653039cc9b1ac98d8053f5056dbe3`; `data/survey/targets_p8.csv` `80f4267f26f4c0d0fe642dbffa2206d7df5aae573a2a85cf13539bead0394a1a`; `data/survey/targets_p8.meta.json` `d7290585dd741067841b01639252f1f0438e21742492d05590ec9819b3559761`.

### 0b. Numbered gotchas (from `PROMPT_P8.md` 1 to 9, `PROMPT_P10.md` 10 to 16, the P10.3, P11 and P11.5 records and the memory file; all bind)

1. The Bash tool truncates near 8 kB and heredocs break on Python triple quotes: write every script to a file and run it. A stdin script cannot spawn a `ProcessPool`. Controller launches go in a `.cmd` under `p12/work/`, started detached; CMD launchers test `if %errorlevel% neq 0`, never `if errorlevel 1`.
2. `taskkill` is blocked: `Stop-Process` or psutil after an identity match; never an indiscriminate python kill.
3. MAST: one `search_lightcurve` and one `Tesscut.get_sectors` per star, at most 4 download workers, never per-sector searches from many workers (P4 stalled TESScut). Hangs outlive `socket.setdefaulttimeout(300)` (26% of pilot stars hung at 1,800 s): every download runs under a 600 s controller deadline (0 unknowns on 436 stars, `p10/part3/ACQUISITION_CLOSEOUT_20260914.md`); a stalled worker is stopped alone and recorded; one recorded transport-class retry pass (`p10/part3/AMENDMENTS_D1_D4_20260914.md` D2, D3). Cutouts under `CUTOUT_TIMEOUT_S = 240` (`scripts/survivor_packets.py` line 49).
4. Truncated FITS after an outage (P8.5: 1,005 stars failed in minutes, 2 truncated): a store is complete only when every `index.json` has `n_failed 0` and every product passes the TIME, flux and quality identity check; a corrupt product directory is re-downloaded with `force=True`; sealed files are never deleted.
5. QLP: sectors >= 56 ship all-NaN `det_flux_err` (filled with the robust scatter); low-precision bit 2^12 before sector 56, 2^30 from 56; `sap_flux_err` NaN everywhere; QLP from sector 94 is TGLC photometry; TESS-SPOC has no alternative aperture. QLP 80, 83, 85, 99 to 104 are excluded and 74 to 79 need the corrected-v02 comparison (`p10/part3/manifests/sector_policy_effective.json`).
6. Never stitch mixed cadences (`harmonise_cadence` bins finer products by >= 1.5x, drops coarser). Science sectors 56 to 105.
7. TLS uses `multiprocessing.Pool`: Stage C only as a top-level subprocess, never inside a pool worker (`WinError 5`). Floor every TLS duration at one cadence before a rule, keep the raw value; save `chi2`, `SR`, `power_raw`. C at native cadence only: 600-s input flipped 15 of 18 decisions (`p10/results/stage_c_cadence_validation.md`).
8. The biweight absorbs part of every transit (retention 0.935 on a 1.3-h transit).
9. The search is wall-budget sensitive (identical inputs gave 6 then 8 signals, P9): paired comparisons run on identical prepared inputs, same machine, same part, and read `survey.budget_exhausted()`, not the status. `survey_p10` differs from `survey_p8` (slots 6/24/16, `rank_by="snr"`, 2,700 s; `src/tesshunter/survey.py` lines 230 to 237): no `survey_p8` result supports a `survey_p10` claim.
10. Timeouts and rc != 0 are operational unknowns, never rejections or misses, kept in every denominator; a retry is a separate manifest at attempt 2, only where this prompt says so.
11. Windows file replacement raises `PermissionError` under load (the P11.5 owner died replacing `progress.json`): temp plus `os.replace` with bounded retries, append-only receipts; a suspended process is not a checkpoint; never resume a recycled pid.
12. Git auto-maintenance ran despite a command-line `gc.auto=0` and left 8.34 and 2.25 GB temporary packs (`p10/part3/MAIN_REVIEW_20260914.md` s.1, s.6): commit only with `git -c maintenance.auto=false -c gc.auto=0 -c gc.autoDetach=false`, never with a controller alive, never repack with an owner alive; retry a failed `git add` once.
13. Unqualified `common` imports collide across test suites: P12's module is `p12_common.py`; the P12 suite runs in its own process.
14. Historical writers write into sealed paths (`p9/verify.py`, `p11/protocol/integrity_check.py`, `p10/part3/protocol/integrity_check.py` which refuses to run twice into its output, `scripts/build_p8_population.py`, `p8_neighbours.py`, `p8_write_audit.py`, `p8_funnel.py set_root` which hard-codes `survey_p8` ingestion, `p8_stage_d_packets.py`): none runs against its historical destination; P12 uses versioned copies under `p12/protocol/`.
15. `scripts/run_survey.py --resume` treats `no_data` as final: P12 never uses it; search only a complete store.
16. Per-sector fixed-aperture depths carry 0.33 to 4.42 ppt errors at Tmag 13 to 14 (`HANDOFF_P8.md` lines 147, 155); a zero-error centroid entry is a missing measurement; missing pixel evidence is never "no contamination"; K7b and K9b need 16 clean sky pixels.
17. `hard_stop_p10` FLAG is not wired into D: `k0_hard_stop` reads only `status` (`src/tesshunter/verdict_tiers.py` lines 109 to 114) and `audit_p5.crossmatch_step` calls `cat.check` (`scripts/audit_p5.py` lines 975 to 995), so a bare-TCE star reaching D historically is REJECTED; `catalog_adapter.hard_stop_p10` raises `ValueError` for a bare TCE without a sidecar row (`p10/part3/protocol/catalog_adapter.py` line 108). Part 1 wires a versioned copy that returns FLAG with `ephemeris: none` instead.
18. Truth is opened only after a prediction lock; the P9 truth file is used as frozen (`HANDOFF_P10.md` 0.7).
19. Injections are credited on the exact period (1%); real TCE families also on 2, 3, 1/2, 1/3 aliases: never compare the two instruments as one rule.
20. Unexplained process-tree kills have happened (`HANDOFF_P10.md` line 34): durable per-case receipts, one owning controller, a commit at the end of every part.
21. `p11/manifests/entry_source_and_evidence_hashes.json` hashes every `src/tesshunter/*.py` and the integrity check re-executes it: P12 edits nothing under `src/` or `scripts/`; every rule change is a module under `p12/protocol/` installed at worker start (the `catalog_adapter.install()` pattern).
22. `survey_p8.load_audit_products` (lines 59 to 99) applies only the author preference and `sector_min`, not the QLP exclusions or the corrected-v02 rule; the frozen policy is applied only by `verify_prepare_star.py` (`input_identity.choose_verified`). Every P12 worker reads products through `policy_products_p12.py` (Part 0c); a worker calling `get_prepared` unpatched searches the pre-P11 sector set, the input of the P10 2d calibration.
23. `blind_search_worker.py` searches a frozen prepared `.npz` and has no injection field (lines 19 to 30): injected series are built on the evaluator side, as P11.5 did (`p11/p11_5/protocol/prepare.py`), saved as frozen arrays, searched blind and scored afterwards.

### 0c. Shared rules

1. Commit at the end of every part on `improve/recovery`: `git -c maintenance.auto=false -c gc.auto=0 -c gc.autoDetach=false add p12 HANDOFF_P12.md docs/AUDIT_P12.md docs/packets/audit_p12 RESUME_P12.md`, then commit "prompt 12 part N: <one line>"; never with an owner alive; never push; never add a historical path, a cache or `data/survey/p12/` (hashed into committed seals instead).
2. `HANDOFF_P12.md` is the record: what shipped, what was measured (sample sizes, unknowns), what was refuted, what is open, a "resume here" line while live, tags on every number, assumptions apart.
3. The user submits, by hand, after final delivery; the agent never submits to any external service.
4. Rules before measurement: every threshold is fixed in `p12/PREREGISTRATION_P12.md` and `p12/protocol/config.json`, hashed in `p12/manifests/registration_seal.json`, before the measurement it judges (section 2f names each judged table). A threshold may change only before its table exists, recorded in `p12/protocol/AMENDMENTS_P12.md`. A change that fails its bar is not adopted and not retried with a lower bar.
5. Development boundary: no per-candidate record of the final population (`p12/manifests/targets_p12_core.csv`) is opened before the freeze receipt of Part 3. Before it, final-population stars enter only as stage counts of the 300 false-alarm stars and as search-level matching of the 436 TCE hosts to the sidecar, both by script in Part 2. After it, Part 4 opens by script the false-alarm stars' A passers and Part 5 opens everything. Sealed P8, P9 and P10 records seen by earlier prompts may be read by script for Part 1 and Part 2d; the 25 unexposed P9 hosts of Part 4c are never read before Part 4. Every per-candidate read is a row of `p12/manifests/exposure_ledger.jsonl` (UTC, star, stage, path, reader, prompt of origin).
6. Sealed evidence stays byte-identical: `data/survey/{p2_runs,p4,p5,p6,p7,p8,p10,p11}/`, existing `data/survey/runs/*`, `data/survey/targets_*.csv`, `injections_*.csv`, `completeness_*`, `population_p8.json`, `p9/` (including `p9/results/verification.json`, which P12 never rewrites), `p10/`, `p11/`, `docs/AUDIT_*.md`, `docs/RULES.md`, `docs/COMPLETENESS*.md`, `docs/packets/audit_p8/`, `HANDOFF_*.md`, `PROMPT_P8.md`, `PROMPT_P10.md`, `PROMPT_P10_3.md`, `src/`, `scripts/`, `data/cache/catalogs/` (never refreshed in place). Integrity is checked at entry and at the end (Part 0c, Part 6e).
7. New work lives in `p12/{protocol,manifests,results,logs,work,tests,heldout}` (tracked), `data/survey/p12/` (untracked, a junction to `D:\tesshunter_data\survey_p12`, hashed in the seals), `docs/packets/audit_p12/`, `HANDOFF_P12.md`, `docs/AUDIT_P12.md`, `RESUME_P12.md`. Shared stores writable with receipts: `data/survey/audit_lc/` and `data/cache/audit_lightkurve/` (new stars only; an existing `index.json` is never rewritten without `--force`), `data/cache/stitched/` and `data/cache/lightkurve/tesscut/` (regenerable).
8. Long phases run detached under one owning controller; the session never polls; the hourly routine of section 6.2 supervises and pauses only at the three decision points of 6.3 and at a stop rule.
9. Forecasts use the unit costs of section 6.1 with margin 1.25 (`config.json` `forecast_margin`); a pilot's measured cost may raise a forecast and never lowers it.

---------------------------------------------------------------------

## 1. Reading list, in this order

Items 1 to 8 before Part 0; each later item before the part that uses it.

1. `PROMPT_P10_3.md` and `p10/part3/PREREGISTRATION_P10_3.md`: the house style and the controller, routine, receipt and seal patterns P12 reuses.
2. `p10/part3/{DECISION,SEARCH_RETENTION,FUNNEL_RETENTION,CALIBRATION_CHECK,AUTOPSIES}_P10_3.md`: real-signal retention on the 436 (156/377 INDEPENDENT present families), the natural load per host (9.93 / 2.53 / 0.672 / 0.067 / 0.011), the 29 B survivors, what is unmeasured.
3. `docs/RULES.md` sections 1, 2, 6, 8, 9: the `p10.0` rule set, S modes, the 2b rule, the C rule, the tiers. `p12.0` is `p10.0` plus Part 1's amendments.
4. `p10/results/part2d_calibration_20260912/{COMPLETENESS_P10.md, STOP_RULE_1.md, stop_rule_1_decision.json}`: the injection instrument (2,100 injections on 300 stars) and its level table (search 1,240, pre-gate 1,184, A 1,164, S 964, whole funnel 952), FA rates 11.65 / 2.363 / 0.150 / 0.0067 per star; generated 2026-09-12T15:20Z on the pre-P11 sector set.
5. `p11/INPUT_AUDIT.md`, `p11/p11_5/INPUT_POLICY_P11_5.md`, `p11/p11_5/DECISION_P11_5.md`: why QLP 80, 83, 85, 99 to 104 are excluded (sector 80 offsets 166 to 206 s), that 59 of the 300 calibration hosts keep fewer than three sectors under the policy (235 hosts and 484 of the 600 2b injections under the full P11.5 policy), and the R1 result.
6. `p11/results/noise_summary/summary.json`, `p11/protocol/noise_audit.py` lines 90 to 110: the small-aperture measurement and how `DET_FLUX_SML` is read from the cached FITS.
7. `p11/p11_5/protocol/{inputs,prepare,search_worker,funnel_worker,score_common}.py`: the policy-applied, evaluator-side injected preparation Part 2 copies.
8. `p10/part3/protocol/` (the modules of the 0c table) and `p10/part3/manifests/{supervision_policy_v3,checkin_schedule,sector_policy_effective,cache_relocation_tesscut}.json`.
9. `p10/results/tier_rederivation.{csv,json}`, `src/tesshunter/verdict_tiers.py`, `src/tesshunter/audit_rules.py` lines 327 to 380, `tests/test_p10_tiers.py`, `HANDOFF_P8.md` lines 138 to 160, `data/survey/p8/review_p8.json`: the K, H, F conditions, the `TIER_*` identifiers, the three endpoint risks (TOI-762 A b killed by K8 at density ratio 2.094; TOI-122 b by K6 at 3.10 sigma; TIC 144277542 SUBMIT with K9b disagreeing in 1 of 3 sectors) and what the P8 reviewer recorded for the four artefact KILLs ("background/correction artifact", sky-tracking aperture depths).
10. `docs/AUDIT_P9.md`, `p9/truth/final_truth.csv`, `p9/runner.py`, `p9/common.py`, `p10/protocol/p9_scoring_adapter.py`, `p9/results/runtime_by_stage_and_label.csv`, `HANDOFF_P10.md` 0.0, 0.7, 0.11, 2.2 (lines 1249 to 1480): the held-out harness, truth, cost and exposure.
11. `docs/incumbent_checks_p8/INCUMBENT_CHECKS_P8_DOMAIN.md`, `docs/POPULATION_P8.md`, `p10/part3/results/{part_d,hard_stop_p10}.json`: the population and the noise relation used to rank an extension.
12. `scripts/p8_stage_d_packets.py`, `scripts/audit_p5.py`, `src/tesshunter/{packet,fpp,event_vet}.py`, `docs/packets/audit_p8/tic144277542_P12.9812/`: the Stage D path, never run live under `p10.0`.
13. `p10/part3/results/controllers/*/closure.json`, `p10/part3/{ACQUISITION_CLOSEOUT,AMENDMENTS_D1_D4,MAIN_REVIEW}_20260914.md`, `data/survey/p8/funnel_timing_p8.json`: the unit costs of 6.1 and the failure modes behind the gotchas.
14. `PROMPT_P8.md` gotchas 1 to 9, `PROMPT_P10.md` gotchas 10 to 16, and `C:\Users\seanj\.claude\projects\C--Users-seanj--claude\memory\project_tesshunter.md` if readable (the repository wins where they differ).

`P12_DESIGN_RATIONALE.md` is context, not instructions. A prior draft of this prompt (2026-09-16, 90,797 bytes) and the 2026-09-22 synthesis draft (108,246 bytes, kept outside the tree as `..\P12_SYNTHESIS_DRAFT_20260922\`) are superseded; this file amends the synthesis as section 11 records, and the prompt you execute is the file whose SHA-256 Part 1a seals. No search or funnel worker ever opens a TCE sidecar, `p9/truth/`, the TESS Ten Thousand table or a calibration truth file; the opened-file assertions check this.

---------------------------------------------------------------------

## 2. Objective and the definition of "best conceivable state"

### 2a. What the user sees when P12 ends (written first)

`docs/AUDIT_P12.md`, page one, in this order:

1. The final state (section 8) and the launch-bar table (3b): each clause's number, N, Wilson 95% interval, decisive flag, outcome; if the bar was not met, the failing clause and its consequence on lines 2 and 3.
2. The candidate list: tier 2 "pixel-supported candidates", then tier 1 "CTOI-grade candidates", each by `ranking.score_v2` descending (order never changes a verdict): TIC, period, epoch, depth, duration, radius, tier, deciding condition, F7 association, F5 status, `score_v2`, packet path.
3. The HOLD list ("not for submission") with conditions, and the UNRESOLVED and UNKNOWN counts.
4. Per candidate: the two-sentence ExoFOP note (ephemeris, depth, duration, sectors, preset and rules version; then the tier and what is not claimed), F1 to F10, and: "The field's validation bar (resolved source, localised repeated dimming, low FPP) is out of reach for TESS FFI photometry alone at Tmag 13.5; this is a candidate for follow-up, not a validated planet." Next-transit windows only while the propagated timing error is below half the duration.
5. The completeness statement (Part 6a) in short form, with one sentence per period and radius class giving the measured recovery rate and its last measured stage (injections through S, C on the 30-injection sample; D measured only on the 12 ephemeris-assisted P9 hosts), so the completeness claim stays narrower than the candidate list it accompanies.
6. The specificity statement: survival of independent negatives at B, C and D with N, Wilson bounds and what N can and cannot detect.
7. The cost ledger: queue-hours per part, GB downloaded, disk on `C:` and `D:`, calendar days, check-ins.
8. Next steps for the user: open each packet under `docs/packets/audit_p12/<key>/`, fill `tag`, `candidate_name`, `paper_url` in `ctoi_fields.json`, and enter the CTOI form by hand if they choose; then the closing sentence of Part 6b, "The registered P12 work on these inputs is complete; these measurements bound what it can find, and the specific experiments that could move those bounds are X."

A clean null is stated in one sentence beside the completeness statement. Where the expected candidate count and the trustworthiness of the list pull apart, this prompt chooses the list.

### 2b. The definition [binding]

The best conceivable state is the configuration `p12.0` = (population, photometry input, search preset, funnel rules, endpoint tiers) that wins every pre-registered paired instrument it is entered into, frozen in `p12/manifests/freeze_p12_0.json` (Part 3) before the launch bar is measured, with every component either (a) inherited from a prompt that settled it by measurement (2d) or (b) decided in P12 by a rule written here before its measurement. Every candidate change is one experiment with one instrument, one admission threshold, one cost forecast and a fixed place in the order, cheapest and most decisive first (Part 1 on saved records, then Part 2). A change that fails its bar is not adopted and not retried with a lower bar. The launch bar is measured on material not exposed to any P12 rule decision; the final search runs whether or not it is met and the final state names which; its candidate list is produced under `p12.0` frozen before the first real candidate of the final population is opened.

### 2c. The seven questions of the design brief

| question | rule | evidence |
|---|---|---|
| Which stars | Core = the 2,000 P8 stars (`data/survey/targets_p8.csv`) + the 436 input-eligible bare-TCE stars (`p10/part3/manifests/targets_evaluated.csv`) under `hard_stop_p10` (bare TCE = FLAG with F7), re-checked on the P12 catalogue snapshot (0d), then filtered by the frozen input policy: fewer than 3 usable sectors = `INPUT_INELIGIBLE(sectors)`, listed, never searched (about 1,570 to 1,610 of the 2,000 stay [I, from 235 to 241 of 300]; 436 of 436). Extension tiers E1 (top 1,000 of the 7,989 unselected qualified CLEAN stars by an observable sensitivity metric) and E2 (all 7,989) only if the user picks one at decision point 1, each with its own calibration. The yield model decides nothing and appears once as a labelled model row. | calibration, noise, neighbours and products exist on exactly these stars; the 436 are the best-observed (median 15 sectors against 4, `INCUMBENT_CHECKS_P8_DOMAIN.md` s.4.5); the model never predicted an observed count (2e) |
| Which photometry | Archival corrected flux (SPOC and TESS-SPOC `pdcsap_flux`, QLP `det_flux`, preference SPOC > TESS-SPOC > QLP, biweight 0.75 d) under the frozen sector policy. One candidate: QLP `DET_FLUX_SML` on QLP-selected sectors (Part 2). No pixel extractor; no SAP test. | 1-h noise ratio 0.639 [0.627, 0.648] on 53 of 60 hosts, retention 0.939 against 0.935 (`p11/results/noise_summary/summary.json`); SAP parity 0.988 cannot reach 5 pp; no pixel code exists and 2,000 stars of cutouts need 1.6 to 2.0 TB |
| Which search | `survey_p10` frozen (0.5 to 30 d, durations 0.02 to 0.20 d, slots 6/24/16, `rank_by="snr"`, 2,700 s; `survey.py` lines 230 to 237). No search change is tested (2e). "Better, not different" = the 2b rule plus no loss on the 377 INDEPENDENT real families, applied to the photometry change. | +9.28 pp R_7_15 on injections (`p10/results/search_capacity_final.md`); +4.78 pp [+1.53, +8.15] on real families (`SEARCH_RETENTION_P10_3.md`) |
| Which vetting | `p10.0` route: pre-gate (stitch SNR >= 7.1, >= 3 transits, epoch-consistent) -> A -> bound S -> B (flags) -> C (TLS native, SDE >= 9, robust fallback, cadence floor) -> D. C on every B passer, no cap: 12,240 s, one recorded retry at 36,000 s, then UNRESOLVED (never a rejection); D on every C passer and every UNRESOLVED case (capped at HOLD by H6). Specificity of B, C, D measured in Part 4 on three independent negative sets with C and D forced. | retention 1,240 -> 1,184 -> 1,164 -> 964 (`stop_rule_1_decision.json`); bound S the only mode keeping >= 90% of adversarial kills (`p10/results/secondary_modes.md`); B/C/D specificity unmeasured (P9: 1 of 16 negatives reached C) |
| The endpoint | `p10.0` tiers + Part 1b: K8 guard (0.5, 2.0) -> (0.5, 2.5); K6 3.0 -> 3.5 sigma; H5 (one-sector K9b hold); H6 (C unresolved); K10 light-curve artefact test (a KILL only if its bar is met, else flag F10); K0 through `hard_stop_p10`; two tiers. Every SUBMIT carries F1 to F10 and the non-claim of 2a item 4. | TOI-762 A b and TOI-122 b killed, TIC 144277542 SUBMIT (`tier_rederivation.csv` keys `tic178709444_P3.4721`, `tic231702397_P5.0783`, `tic144277542_P12.9812`); F5 not measurable on 17 of 22 |
| Launch bar | Section 3b; if not met the search still runs and the state is `FINAL_SEARCH_DELIVERED_BAR_NOT_MET`. | `HANDOFF_P10.md` 0.7 stop rules 2 and 3, rewritten |
| The output | Section 2a. | `src/tesshunter/packet.py` `CTOI_FORM_FIELDS` |

### 2d. Reused because a measurement settled it

`survey_p10` over `survey_p8` [P10, P10.3]; bound S [P10 2a; P11.5: all 36 joint S x C policies lost planets]; strongest-peak C with robust fallback at native cadence [P10 2c]; Stage A's six criteria and error model [P8]; B as flags [P8; one kill in the project's history, `docs/REVET.md` s.5]; the pre-gate [P8]; the 2,100-injection instrument, the 2b subset (600, seed 20260908) and the 2b rule [P8, P10]; the paired whole-host bootstrap [P10.3]; `hard_stop_p10` and the sidecar [P10.3: 531 FLAG]; the frozen sector policy [P11, P10.3 D1]; the P10.3 controller and routine (34 check-ins over 29.0 h, zero controller failures) and the unit costs of 6.1.

### 2e. Overridden or dropped, with the deciding measurement

| item | status | measurement |
|---|---|---|
| Bare SPOC TCE = REJECT [P1] | overridden by `hard_stop_p10` | 0 promoted TOIs among 531 [P10.3] |
| Yield model as selector or forecast | dropped; one model row | predicted 5.00 / 2.19 / 11.67 / 21.09, observed 0 / 0 / 0 / not run (`HANDOFF_P1.md`; `HANDOFF_P4.md` s.3; `stop_rule_1_decision.json`) |
| Reuse of P8 search results | overridden: all re-searched | presets differ (`survey.py` 230 to 237) |
| P10 2d calibration as the completeness statement | overridden: re-measured under the frozen policy (Part 2) | 2d ran before the P11 input audit; 59 of its 300 hosts keep < 3 sectors under the policy (`p11/INPUT_AUDIT.md`) |
| K8 guard, K6 threshold | amended (Part 1), validated in Part 4 | two truth positives killed on the seen set, each flip isolated |
| R1 reservoir [P11.5] | dropped | +2.75 pp [0.00, +6.25] after pre/A/S against its registered 3.0 pp gain clause, 2.06x pre-gate load (`DECISION_P11_5.md`; `p11/protocol/PROMPT_P11.txt` line 94); a failed change is not retried |
| Larger detector budget | dropped | +0/291 in [7,15) (`search_capacity_final.md`) |
| Long-period pass, `duration_max` 0.3 d, slot removal | dropped; Part 2d reports whether a planet-like mechanism exists | no measurement; > 5 d real losses are EB-deep (`AUTOPSIES_P10_3.md`); the largest central transit in the domain is 3.64 h |
| S as a flag or a joint S x D test | dropped | softer modes keep at most 21 of 26 adversarial kills against 24 needed (`secondary_modes.md`; `C_LOCAL_P11_5.md`); no D-level EB tier; 365 to 1,637 extra C runs |
| C_v2 / C_local | dropped | worse rejector and retainer (`C_LOCAL_P11_5.md`) |
| C cap | dropped | a budget device; P10.3's cap left 23 of 29 B survivors unrun |
| Stop rule 1 as a go/no-go | dropped; SNR50 reported | `STOP_RULE_1.md` |
| Stop rule 3 "0 of 18" | rewritten as LB3 with a denominator guard | the 12 unexposed positive hosts were P9 search-stage failures (`docs/AUDIT_P9.md` line 159) |
| P11 photometry bar (>= 15% noise, >= 95% retention) | dropped | the default product itself retains 0.935 |
| Sectors beyond 105 | probed, not acquired (0f) | every calibration is on 56 to 105 |

### 2f. The judged tables ("the measurement being seen")

Part 1: `p12/results/part1/{k10_calibration.json, tier_rederivation_p12.csv, plumbing_d.json}`. Part 2: `p12/results/part2/photometry_decision.json`. Part 4: `p12/results/part4/{ttt_table,p9_negatives_table,p9_positives_table,fa_natural_table,launch_bar}.json`. Part 5: `data/survey/p12/final/funnel/collect_p12.json`. Once a judged table exists its rule text is frozen.

### 2g. The forecast at a glance (derivation in 6.1)

Core, archival photometry: **225 to 244 queue-hours with the 1.25 margin** (180 to 195 base); **261 to 281** if the small aperture is adopted at a wall ratio of 1, **up to 381 to 401** at the wall clause's ceiling of 3 (6.1); plus a Stage C retry tail of up to 63 queue-hours (73 with the small aperture) reported separately. Calendar at the P10.3 duty (0.553): **17 to 21 days** archival or small aperture at ratio 1, up to 30 at ratio 3, up to 36 with the whole tail; 9.4 to 11.7 days at full duty. These are conditional planning figures: 0e's counts, the pilot and the Part 2 wall ratio replace them in `forecast_p12.json`, and no calendar date is promised. Downloads 72 to 115 GB (mostly TESScut cubes for D), all on `D:`; about 165 to 210 GB on `D:`; under 3 GB net on `C:`. E1 adds 49 to 61 queue-hours and 48 GB; E2 adds 271 to 369 queue-hours, up to 383 GB, and an 82 GB relocation of the audit stores to `D:`.

---------------------------------------------------------------------

## 3. Definition of done

### 3a. Done means all of these exist and are committed

1. `p12/manifests/freeze_p12_0.json` (Part 3), written before any Part 4 or Part 5 job and before any per-candidate record of the final population was opened.
2. The launch-bar table in `p12/results/part4/launch_bar.json` and on page one of `docs/AUDIT_P12.md`.
3. `p12/results/candidates_p12.csv` (every eligible star, every accepted signal, last stage, verdict or UNRESOLVED or UNKNOWN, tier, deciding condition, F1 to F10) and a packet per SUBMIT and HOLD under `docs/packets/audit_p12/<key>/` whose `ctoi_fields.json` carries `tiers`, `validation_status` and `candidate_tier`.
4. `p12/results/COMPLETENESS_P12.md`, `p12/results/SPECIFICITY_P12.md`, the cost ledger `p12/manifests/resource_ledger.json`.
5. `HANDOFF_P12.md`, `docs/AUDIT_P12.md`, the seals, the integrity receipts (entry and final, 0 mismatches), the exposure ledger, the routine's `DISABLED_VERIFIED` receipt, and the final state on line 1 of both documents.

### 3b. The launch bar [A, pre-registered]

Measured in Part 4, after the freeze and before the final search's C stage opens, on material no P12 rule decision was exposed to. The Part 1 checks on seen records are preconditions, not clauses; the photometry decision's own rows are never bar material.

A negative is **SUBMIT-equivalent** when a candidate on it matching the binary's catalogue period family (exact or 2, 3, 1/2, 1/3 within 1%, the P9 negative rule, scored after the prediction lock) ends SUBMIT (tier 1 or 2) under `p12.0` with the redaction of 4a. **End to end** = under the final search's route (S and B gate). **At D** = under the forced route of 4a, over the negatives that reach D.

| clause | instrument (Part) | measured number | threshold | decisive when |
|---|---|---|---|---|
| LB1a in-domain negatives, end to end | TESS Ten Thousand binaries under the domain cuts (4b); N1 = stars searched COMPLETE (target 30) | SUBMIT-equivalent / N1 | <= 1 of N1 (`HANDOFF_P10.md` 0.7 stop rule 2) | N1 >= 20; **`bar_met` requires this clause decisive** |
| LB1b in-domain negatives at D | same set, forced route | SUBMIT-equivalent / N1_D | <= 1 of N1_D | N1_D >= 5 |
| LB2a P9 negatives, end to end | the 13 unexposed P9 negatives (4c) | SUBMIT-equivalent / 13 | <= 1 of 13 | always |
| LB2b P9 negatives at D | same set, forced route | SUBMIT-equivalent / N2_D | <= 1 of N2_D | N2_D >= 5 |
| LB3 endpoint on unexposed truth positives | the 12 unexposed P9 positive hosts (13 signals), ephemeris-assisted A to D at the truth ephemeris after the blind leg's lock (4c) | signals KILLed by K6, K8 or K10 / n_fit (D transit fit converged) | <= 1 of n_fit | n_fit >= 5 |
| LB4 completeness no-regression | injections outside the 2b subset on hosts eligible under the frozen policy, through search, pre-gate, A, S on the frozen input (Part 2) | whole-funnel recovery under `p12.0` / recovery of the same job ids in `data/survey/p10/part2d/calibration/injection_outcomes_p10.csv` (column `through_funnel_pregated`) | >= 0.90 | always (about 1,150 injections [I]) |

`bar_met` = LB1a decisive AND every decisive clause holds. A clause that is not decisive is printed NOT MEASURED with its N and outcome and never counts as a pass.

What N can detect (printed beside the table): the Wilson 95% upper bound is 11.4% on 0 of 30, 16.7% on 1 of 30, 22.8% on 0 of 13, 43.4% on 0 of 5. The bar detects a gross specificity failure (one binary in ten passing) and cannot detect a 3% false-SUBMIT rate; the CTOI-grade tier carries that limit.

Expectations written now: LB1b and LB2b may be NOT MEASURED (15 of 16 P9 negatives never reached C, `docs/AUDIT_P9.md`); the blind positive leg is expected to bring 0 to 2 of 13 signals to D (they were P9 search-stage failures, 15 of 17 misses below model SNR 7.1, `docs/AUDIT_P9.md` line 159), which is why LB3 uses the ephemeris-assisted leg; if n_fit < 5 too, amendments A1 and A2 stay validated only by the re-scoring of seen records, and page one says so. LB4 compares the frozen policy with the pre-P11 sector set on the same job ids across dates: a no-regression clause, not an absolute bar; `budget_exhausted` is reported per job in both runs.

### 3c. If the bar is not met

Part 5 runs anyway under the frozen `p12.0` (binding). Lines 1 to 3 of `docs/AUDIT_P12.md` give the failing or non-decisive clause, its number, and: "The candidates below were produced under rules whose pre-registered launch bar was not met (clause <id>: <number>); submission is not recommended until <the measurement named from the failing table> exists." The state is `FINAL_SEARCH_DELIVERED_BAR_NOT_MET`; every SUBMIT's F9 text names the clause. No rule changes and no iteration runs after the bar is seen: a retuned rule would need a fresh unexposed set, which the records do not contain; the handoff names the set a later prompt would need.

### 3d. What the final search delivers regardless

The candidate, HOLD, UNRESOLVED and UNKNOWN lists, every stage record, every D verdict with numeric conditions, every packet, the natural-load table, the completeness and specificity statements, the cost ledger and the seals. A bar failure changes the label, not the list. A run stopped before the final search writes the same documents for the completed parts, with the stop on page one and "no final search was run" in the list section. A run stopped after the search closed but before Parts 5 and 6 completed writes them for what closed, labelled partial, under `STOPPED_AFTER_FINAL_SEARCH_INCOMPLETE` (section 8).

---------------------------------------------------------------------

## 4. The numbered parts

Order (the first session executes Part 0 as the sprint of section 10): Part 0 (preflight, workspace, copies, catalogue snapshot, population, pilot, forecast; ends at decision point 1) -> Part 1 (registration, endpoint amendments on saved records) -> Part 2 (calibration under the frozen input policy and the one photometry test) -> Part 3 (freeze) -> Part 4 (independent specificity, held-out endpoint, launch bar) -> Part 5 (final search) -> Part 6 (completeness, audit, seals, shutdown).

Command convention: `controller_p12.py --phase cal_a_search --workers 24 --deadline 3600` means `C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe p12/protocol/controller_p12.py --phase cal_a_search --workers 24 --deadline 3600` run from the repository root with the environment of 0a (`TESSHUNTER_OFFLINE=1` except in download, catalogue, probe, neighbour and Stage D phases). A `--phase` without `--jobs` uses `p12/manifests/<phase>_jobs.json`. Controller launches go through a `.cmd` under `p12/work/`, detached; every other script is a file run by `PY`.

## Part 0: preflight, workspace, protocol, catalogue snapshot, population, pilot, approval

Purpose: measure the entry state, build the workspace and every module without touching a historical writer, freeze the catalogue snapshot, population and input eligibility, fetch the independent negative set, time the search, and put the whole forecast before the user. Nothing is decided scientifically and nothing is opened at candidate level.

### 0a. Entry measurements (into `p12/logs/entry_preflight.json` and `HANDOFF_P12.md`)

```
cd C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter
set LIGHTKURVE_CACHE=%CD%\data\cache\lightkurve
set PYTHONIOENCODING=utf-8
set TESSHUNTER_OFFLINE=1
git status --short
git log -1 --format=%H
git config --get maintenance.auto
git config --get gc.auto
git config --get gc.autoDetach
git count-objects -vH
C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe -m pytest tests p11/tests p11/p11_5/tests -q
C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe -m pytest p10/part3/tests -q
C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe -c "import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('p9/results/verification.json').read_bytes()).hexdigest())"
```

Expected: HEAD `863c01be5`; `false / 0 / false`; 891 passed 1 skipped; 118 passed (corrected 2026-09-22, AMENDMENTS_P12.md); the SHA-256 of `p9/results/verification.json` recorded in `entry_preflight.json` (it must be unchanged at the final integrity check). The 397 P9 checks run in 0c through `p9_verify_p12.py`, never through `p9/verify.py` (gotcha 14). Also record by PowerShell: `Get-PSDrive C,D`; `Get-Process python* -ErrorAction SilentlyContinue` (none); both automation TOMLs `PAUSED`; no historical `controller_owner.json`; the three population pins of 0a. Anything else is STOP-3 unless it is a listed untracked file. The integrity check runs in 0c through the P12 copy (the original refuses to run twice into its output).

### 0b. Workspace, the `D:` junction, the cache redirect

Create `p12/{protocol,manifests,results,logs,work,tests,heldout}`, then `D:\tesshunter_data\survey_p12\` and `mklink /J data\survey\p12 D:\tesshunter_data\survey_p12`, receipt `p12/manifests/data_relocation_p12.json`. Every P12 prepared array, run, funnel case, calibration arm, catalogue snapshot, SML store and held-out record lives there. Every P12 module that imports `scripts/audit_p5.py` sets `os.environ["LIGHTKURVE_CACHE"]` and `audit_p5.AUDIT_CACHE` to `data/survey/p12/lightkurve/` after the import; its test asserts the cube directory's realpath is on `D:`. The TESS Ten Thousand products (about 1.4 GB) go into the shared stores on `C:` with receipts.

If the user picks an extension tier, before its first download relocate `data/cache/audit_lightkurve` (68.7 GB) and `data/survey/audit_lc` (13.2 GB) to `D:\tesshunter_cache\{audit_lightkurve,audit_lc}` behind junctions with the receipt pattern of `p10/part3/manifests/cache_relocation_tesscut.json` (PowerShell counts and bytes before and after, SHA-256 of 1,000 files sampled with seed 2026092002). Paths are unchanged through a junction, so sealed `source_paths` still resolve.

### 0c. Protocol copies and new modules (tests under `p12/tests/`, suite run alone: `PY -m pytest p12/tests -q`)

Copy, never edit, originals from `p10/part3/protocol/` unless stated; each copy changes only what its row says; `diff_origins_p12.py` writes every diff and both hashes to `p12/manifests/protocol_provenance.json`. Then run `integrity_check_p12.py entry` (63,168 files, 305 to 473 s, 0 mismatches) and `p9_verify_p12.py entry` (397 checks, only `baseline_git_HEAD_unchanged` failing).

| module | origin | change | test |
|---|---|---|---|
| `p12_common.py`, `config.json` | `common.py`, `config.json` | `ROOT=REPO/'p12'`, `DATA=REPO/'data/survey/p12'`; deadlines download 600, search 3,600, A 1,200, S 300, B 300, C 12,240, C retry 36,000, D 5,400, cutout 240 s; workers download 4, neighbours 2, verify 8, search/A/S/B 24, C 3 x 8 threads, D 2; oversampling 3; floors 25e9 (`C:`) and 50e9 (`D:`) bytes; margin 1.25; seeds (1a); sector policy from `p10/part3/manifests/sector_policy_effective.json`; supervision early 10, interval 60, detached above 30 minutes; no queue cap | roots on `D:`; keys present |
| `controller_p12.py`, `guards_p12.py` | `controller_v4.py`, `part_f_guards_v1.py` | P12 roots; jobs path under `p12/manifests/`; `D:` floor; phases `neg_*`, `bar_*`, `final_*` refuse to launch unless `freeze_p12_0.json` exists and its source hashes match; `--retry-of <phase> --deadline S` builds an attempt-2 manifest from that phase's TIMEOUT and OPERATIONAL_UNKNOWN receipts | exclusive owner; TIMEOUT with no orphan; freeze refusal; retry manifest |
| `checkin_p12.py`, `continuation_p12.py`, `final_shutdown_p12.py`, `recover_p12.py` | `checkin.py`, `continuation_next.py`, `final_shutdown_v1.py`, `p11/p11_5/protocol/recover_controller_interruption.py` | the contract and phase sequence of 6.2; the shutdown of 6.4; reconciliation from receipts (STOP-5) | trigger table; sequence order; synthetic tree; synthetic interrupted phase |
| `integrity_check_p12.py`, `register_p12.py` | `integrity_check.py`, `register.py` | outputs under `p12/results/integrity_<phase>/`; also re-hashes the files of `p10/part3/manifests/final_{data,source}_seal.json` (format `p10/part3/results/final_seal_format_note.json`); seals this prompt, the preregistration, the config and every `p12/protocol/*.py` | 0 mismatches at entry; seal round-trip |
| `p9_verify_p12.py` | `p9/verify.py` | output path only: `p12/logs/p9_verification_<phase>.json` for `entry` and `final`; reads `p9/` and never writes under it | 397 checks with only `baseline_git_HEAD_unchanged` failing; the SHA-256 of `p9/results/verification.json` unchanged after the run |
| `blind_io_p12.py` | `blind_io.py` | guarded paths: both sidecars, `p9/truth/`, the TTT table, `data/survey/p12/**/truth/` | an open fails the job |
| `policy_products_p12.py` | new | `load_policy_products(tic, arm)` loads the verified policy-selected raw arrays named in `p12/manifests/input_identity/tic<id>.json` by path and SHA-256; `arm="sml"` swaps `flux` for `DET_FLUX_SML` on the sectors of 2b's rule; `install(tic, arm)` patches `survey_p8.load_audit_products` and `audit_p5.load_products` for that star | no excluded QLP product is ever returned; swaps only named sectors |
| `build_input_jobs_p12.py`, `verify_prepare_p12.py`, `input_identity_p12.py` | pattern of `p10/part3/manifests/input_jobs/*.json` and `p11/protocol/input_inventory.py`; `verify_prepare_star.py`, `input_identity.py` | per star the cached FITS `source_paths` under `data/cache/audit_lightkurve/mastDownload/`, `index_sha256` and the P10.3 notice-snapshot hash; identity records and `data/survey/p12/prepared/<arm>/tic<id>/native200.npz`; eligibility by the unchanged rule (>= 3 sectors of >= 50 points, >= 100 finite points, finite scatter) | the 436 reproduce their P10.3 status and prepared SHA-256 |
| `download_star_p12.py`, `build_batches_p12.py`, `neighbours_worker_p12.py`, `neighbours_batch_worker_p12.py` | `_v2` and neighbour originals | P12 receipts and batches | corrupt FITS re-downloaded with `force=True` |
| `blind_search_worker_p12.py`, `lock_predictions_p12.py` | `blind_search_worker.py`, `lock_predictions.py` | runtime adds `run` (output directory); `survey_p10` only; guards from `blind_io_p12` | hash refusal; guarded open fails |
| `prepare_injections_p12.py`, `score_injections_p12.py` | `p11/p11_5/protocol/prepare.py`, `score_common.py`, and the recovery rule and tables of `p10/protocol/p10_completeness_calibration.py` | evaluator side: per injection on an eligible host, `load_policy_products` -> `harmonise_cadence` -> `survey_p8.inject_products` (SAP and corrected flux) -> `build_prepared`; writes `data/survey/p12/calibration/<arm>/{prepared,injected_raw,truth}/`; scoring after closure: recovered (period within 1%, overlapping windows), alias (2, 3, 1/2, 1/3, never credited), missed, expected SNR on the uninjected array, in the columns of `injection_outcomes_p10.csv` | injected array differs only in-transit; on 5 injections whose host the policy leaves unchanged, the array equals `survey_p8.get_prepared(..., injection=row)` to 1e-12 (so LB4 compares like with like); 20 sealed 2d rows re-scored identically |
| `funnel_plan_p12.py`, `funnel_worker_p12.py`, `stage_c_plan_p12.py`, `stage_c_worker_p12.py`, `close_stage_c_p12.py` | `full_funnel_plan.py` (its `survey_p10`-keyed collect, never `scripts/p8_funnel.py collect`), `funnel_worker.py`, the `stage_c_*_v1.py` trio | products through `policy_products_p12` or the injected raw arrays; rules through `rules_p12`; C receipts carry `deadline_s` and `attempt`; a second TIMEOUT closes `UNRESOLVED` | a sealed P10.3 A record replays byte-identically under `p10.0` |
| `stage_d_worker_p12.py`, `stage_d_packets_p12.py`, `crossmatch_p12.py`, `catalog_adapter_p12.py` | `scripts/p8_stage_d_packets.py`, `audit_p5.crossmatch_step`, `catalog_adapter.py` | packets under `docs/packets/audit_p12/<subtree>/`; tiers through `rules_p12`; crossmatch on the 0d snapshot with `refresh=False`; `hard_stop_p10` returns FLAG with `ephemeris: none` instead of raising; `f7` block (run, planet number, period, model SNR, alias ratio within 1%); the 0b cache redirect; `--redact-catalogue` (4a) and `--product-source p8_store` (1d) only in the phases that name them | bare TCE FLAG and not K0; TOI REJECT and K0; P8 star CLEAN; cube path on `D:` |
| `catalog_snapshot_p12.py`, `build_sidecar_p12.py` | the `KnownObjectCatalog.load(refresh=True)` call, `build_sidecar.py` | sets `catalog_crossmatch.CATALOG_CACHE_DIR` to `data/survey/p12/catalogs/` first, so `data/cache/catalogs/` is never written | its hashes unchanged after a run |
| `rules_p12.py`, `k10_p12.py`, `tier_rederivation_p12.py`, `sml_p12.py` | new; `scripts/p10_tier_rederivation.py`; reading pattern of `p11/protocol/noise_audit.py` lines 94 to 106 | Parts 1b, 1c, 1d, 2b | Part 1; two FITS fixtures |
| `fetch_ttt_p12.py`, `sector_probe_p12.py`, `targets_p12.py` | new; `latest_public_sector()` and `apply_cuts` of `scripts/build_p8_population.py` (lines 239 to 254, 528 to 547) by copy | 0e, 0f | cuts on a fixture; hash order; relaxation order |
| `retention_p12.py`, `tce_families_p12.py`, `compare_arms_p12.py` | `retention_analysis_v1.py`, `tce_families.py`, `p10/protocol/compare_{injection,false_alarm}_variants.py` | evaluator only; paired whole-host bootstrap, 10,000 draws, seed 2026092001 | 156/377 from sealed P10.3 results; e's 146/291 and 709/300 from sealed 2b rows |
| `heldout/`; `freeze_p12.py`, `launch_bar_p12.py`, `candidate_list_p12.py`, `seals_p12.py`, `reports_p12.py`, `ledger_p12.py` | 4c; new, `final_evidence_seals_v1.py`, `final_reports_v1.py` | Parts 3 to 6 | 4c; smoke tests |

### 0d. Catalogue snapshot and hard stop (one network step)

`catalog_snapshot_p12.py` (600 s deadline per source, one retry): hash `data/cache/catalogs/*` before and after (unchanged, else STOP-1); load the six sources with `refresh=True` into `data/survey/p12/catalogs/`; write `p12/manifests/catalog_versions_p12.json` in the `data/survey/catalog_versions_p8.json` format. A source that still fails is taken read-only from its 2026-09-04 copy and page one says which. `build_sidecar_p12.py` builds the P12 sidecar. Then `hard_stop_p10` through the adapter copy over the 2,436: a new TOI, CTOI, NASA or TESS-EB match makes a star `REJECT_NOVELTY` (listed, removed); a P8 star with a new bare SPOC TCE becomes FLAG with F7; `p12/manifests/hard_stop_p12.json` gives the counts against `p10/part3/results/hard_stop_p10.json` (531 FLAG, 2,000 CLEAN). This snapshot serves every later part unchanged.

### 0e. Population, eligibility, extension ranking

`targets_p12.py core` writes `p12/manifests/targets_p12_core.csv` (2,000 rows of `targets_p8.csv` and 436 of `targets_evaluated.csv`, with `hard_stop_p12`, F7 columns, `source_set`, minus 0d rejects). `build_input_jobs_p12.py`, then `verify_prepare_p12.py` under `controller_p12.py --phase verify_core --workers 8 --deadline 600` (1.54 queue-s per star: 1.0 h). `p12/manifests/eligibility_p12.json`: per star `INPUT_ELIGIBLE` or `INPUT_INELIGIBLE(sectors)`, and counts for the 2,000, the 436, and the 300 calibration hosts (`data/survey/completeness_sample_p8.csv`) with their injections in the full set and in the 2b subset. Measured counts replace every count in the forecast.

`targets_p12.py extension` ranks the 7,989 unselected qualified CLEAN stars (the pool after `apply_cuts`, minus the 2,000 and the 531) by `M = sqrt(n_pol) / (sigma_Tmag x rad^2)`, where `n_pol` counts `sectors_200s` in 56 to 105 outside 80, 83, 85, 99 to 104, `sigma_Tmag = exp(-8.878 + 0.810 Tmag)` ppt (`INCUMBENT_CHECKS_P8_DOMAIN.md` "Noise model") and `rad` is the TIC radius [A: SNR of a fixed-radius planet scales as depth over noise times the square root of the transit count, depth as rad^-2; no occurrence term], ties by TIC; writes `targets_ext_E1.csv` (ranks 1 to 1,000) and `targets_ext_E2.csv`.

### 0f. Sector probe and the independent negative set

`sector_probe_p12.py` reproduces `latest_public_sector()` (one QLP and one TESS-SPOC list fetch, no per-star call) into `p12/manifests/sector_probe.json`; the count of core stars with a product above sector 105 is reported as untested input.

`fetch_ttt_p12.py` fetches the TESS Ten Thousand table (Kostov et al. 2025, arXiv:2506.05631) by bounded attempts, each recorded (URL, UTC, bytes, SHA-256) in `p12/manifests/ttt_fetch.json`: (1) one `astroquery.vizier` query by title and author (600 s); (2) the e-print `https://arxiv.org/e-print/2506.05631` unpacked for a machine-readable table (600 s); (3) fallback `data/cache/catalogs/tess_eb/` read-only, labelled "fallback TESS-EB". The agent never asks which table to use. Selection [`HANDOFF_P10.md` 0.7 4e]: join by TIC to the pool; Teff < 3600 K, radius < 0.45, 12.5 <= Tmag <= 14.0, |b| >= 20, `n_sectors_200s` >= 3 with a QLP or TESS-SPOC light curve, FFI-majority (`n_sectors_2min_in_search < n_sectors_200s / 2`); stars absent from the pool fail; core stars excluded; if fewer than 20 qualify, relax Teff to < 4000 K, then Tmag to 12.0 to 14.5, in that order, recorded. Order by SHA-256 of `20260908:ttt:<integer TIC>` (the P9 method, `p9/data_prepare.py` line 8); the first 30 TICs go to `p12/manifests/ttt_negatives.csv`, their ephemerides to the guarded `data/survey/p12/negatives/truth/ttt_ephemerides.json`.

### 0g. Timing pilot

Twenty-four eligible P8 stars, eight per Tmag band ([12.5,13), [13,13.5), [13.5,14]), lowest SHA-256 of `20260920:p12:timing:<integer TIC>` per band: `pilot_search` (24 workers, 3,600 s: the production width, so contention is measured), then `pilot_A` on their pre-gate passers (24 workers, 1,200 s). Read only walls, CPU and counts; the results are never opened or reused (ledger row "timing only"). Units are converted before any comparison: the pilot's search unit is the mean COMPLETE job wall divided by 24, queue-seconds per star at 24 workers (the definition behind 31.9 = 3.811 h / 430 stars), and its A unit is the mean COMPLETE A job wall divided by 24 (behind 15.5); each replaces its 6.1 value only if higher. A raw job wall (about 900 s) is never compared with a queue unit. `forecast_p12.json` records the raw walls, the converted units and which value each line used.

### 0h. Forecast and decision point 1

`ledger_p12.py forecast` writes `p12/manifests/forecast_p12.json` (the tables of 6.1 with 0e's counts and the pilot) and renders it at the top of `HANDOFF_P12.md` under "DECISION POINT 1" with the entry, 0d, 0e and 0f results, the three decision points and the recommendation (core only: the extension has no calibration and 5,157 of its 7,989 stars are at Tmag 13.5 to 14, counted from the pool, where whole-funnel recovery is 41%, `COMPLETENESS_P10.md` s.2). Commit "prompt 12 part 0". The routine pauses until the user writes `p12/manifests/decision_point_1.json` (`{"tier": "core" | "E1" | "E2", "approved_utc": ...}`).

Forecast: about 3.1 queue-h (tests, integrity, snapshot 0.2 h, verify 1.0 h, pilot 0.5 h), 3.9 with margin; about 6 h of engineering (the first session's sprint of section 10 covers as much of it as four hours allow); under 1 GB downloaded. Auto-advance: none.

---------------------------------------------------------------------

## Part 1: registration, the endpoint amendments, K10, the K0 wiring, the Stage D plumbing test

Purpose: write and seal every rule; implement the endpoint amendments as an installable overlay; calibrate the light-curve artefact test on saved records; prove the Stage D path end to end on six seen P8 candidates. No record of the final population or of the 25 unexposed P9 hosts is opened.

### 1a. Registration [A]

Write `p12/PREREGISTRATION_P12.md` (every rule of sections 2, 3 and 5 and Parts 1 to 6 with exact thresholds; an amendment table against `HANDOFF_P10.md` 0.7 and 0.8 and `PROMPT_P10_3.md`: uncapped C with one retry and UNRESOLVED; D on UNRESOLVED under H6; the frozen-policy recalibration; stop rule 3 rewritten as LB3; the two tiers; A1 to A7; the forced route and redaction for negatives; the extension tiers) and `config.json`, then `register_p12.py` writes `p12/manifests/registration_seal.json`. Seeds: NumPy PCG64 `20260920` for any new draw (without replacement over sorted keys); `2026092001` for every paired host bootstrap (10,000 draws, percentile 95% intervals); `2026092002` for fixtures and relocation samples; the sealed 20260902 (P8 injections), 20260904 (the 300 calibration stars) and 20260908 (the 2b subset, the C injection sample of `scripts/p10_stage_c.py` line 57, the TTT order) reused. Ordering hashes are `sha256("<seed>:<purpose>:<integer TIC>")` ascending.

### 1b. The rule overlay `rules_p12.py` and the amendments [A]

`install()` registers `"p12.0"` in `audit_rules.NAMED_RULES` in memory. `evaluate(inputs, rules, redact_catalogue=False)`: for `p10.0` it calls `verdict_tiers.evaluate` untouched; for `p12.0` a context manager sets the amended constants in every namespace `verdict_tiers` reads them from (assert each identifier exists first), evaluates, restores, then applies K10, H5, H6, F10 and `candidate_tier`. With `redact_catalogue=True` (negative sets only) the crossmatch status is passed as `KNOWN_STATUS_REDACTED` (treated as unavailable by `k0_hard_stop`, `verdict_tiers.py` lines 109 to 114) and the catalogue clause of K5 and H4 are computed, recorded and excluded. Receipts record `rules_p12.install_hash`. Nothing under `src/` is edited.

| id | change | `p10.0` -> `p12.0` | expected effect on the seen records of `p10/results/tier_rederivation.csv` | reason |
|---|---|---|---|---|
| A1 | `TIER_DENSITY_RATIO_RANGE` (`audit_rules.py` line 361) | (0.5, 2.0) -> (0.5, 2.5) | `tic178709444_P3.4721` (TOI-762 A b, ratio 2.094, dchi2 39.14) KILL -> SUBMIT-equivalent; nothing else (other K8 fires have ratios 0.093 to 0.173 or a radius above the limit, as `tic41422753_P2.4708` at 24.07 Re) | a truth positive killed 0.094 above an unlabelled guard; 2.5 is the smallest half-unit step clearing it |
| A2 | `TIER_ODD_EVEN_SIGMA` (line 333) | 3.0 -> 3.5 | `tic231702397_P5.0783` (TOI-122 b, 3.10 sigma, 16 odd / 14 even) KILL -> SUBMIT-equivalent; nothing else (next-largest K6 on a SUBMIT 1.65) | smallest half-sigma step clearing a truth positive |
| A3 | new HOLD H5 | none -> holds when the K9b disagreement holds in exactly one measurable sector and no KILL fired (`TIER_MIN_SECTORS`, line 348, shared with K7, unchanged) | `tic144277542_P12.9812` SUBMIT -> HOLD H5 (K9b disagrees in 1 of 3 sectors) unless K10 kills it; nothing else | K9 kills only on two disagreeing sectors (`HANDOFF_P10.md` 0.11 item 4) and K9a is vacuous on background-dominated apertures (item 6); one sector cannot kill at 0.33 to 4.42 ppt per-sector errors but can withhold submission; the P8 reviewer killed this record on pixel evidence (`HANDOFF_P8.md` line 155) |
| A4 | new K10 (1c) | none -> a KILL after K9 if admitted, else flag F10 on every D record | set by 1c | K9 needs pixels 17 of 22 seen records lack |
| A5 | new HOLD H6 | none -> a C outcome UNRESOLVED after the retry gets D and a verdict of at most HOLD | none (every seen D record passed C) | every D measurement without a SUBMIT that skipped C |
| A6 | `candidate_tier` (SUBMITs only) | none -> tier 2 when `F5_localisation` is `on_target_consistent` in >= 2 measurable sectors, or the TESScut centroid is informative in >= 2 sectors: within 3 sigma of the target, non-zero errors, 3-sigma radius <= 1 pixel, and the 3-sigma region excludes every capable neighbour (a star of the neighbour table whose flux ratio to the target, 10^(-0.4 x dTmag), is at least the fitted depth: the 100% eclipse bound); a centroid consistent with the target that fails the radius or neighbour condition is recorded `target_consistent_unlocalised` and does not count; else tier 1 | reported, no verdict change | the absence of pixel evidence becomes a label; a centroid that cannot separate the target from a capable neighbour is not pixel support |
| A7 | K0 wiring | `crossmatch_step` + `cat.check` (bare TCE REJECT) -> `crossmatch_p12.py` + `hard_stop_p10` (FLAG with F7) | the 436 can reach a verdict; the 2,000 unchanged | gotcha 17 |

Tests (`p12/tests/test_rules_p12.py`): the 22 seen records under `p10.0` with the overlay loaded reproduce `tier_rederivation.json` byte for byte; each amended constant fires and just-not-fires; H5 and H6 fire on synthetic inputs; A6's centroid route refuses a synthetic centroid with a 2-pixel 3-sigma radius and one whose region contains a capable neighbour; the D worker refuses `--redact-catalogue` outside `neg_*` phases; historical source hashes unchanged.

### 1c. K10: definition, calibration, admission [A, written before the calibration runs]

K10 reads only the Stage A record's chosen ephemeris (`per_ephemeris[chosen_ephemeris]`, fields of `src/tesshunter/event_vet.py` lines 150 to 200). Variants:
- K10e: `n_excluded / n_observed > 0.5` (the condition behind Stage A's audit flag "more than half of the observed events coincide with dumps/edges/ramps"); not measurable when `n_observed < 4`.
- K10s: `sap_kept.weighted_mean_depth_ppt < 0.5 x det_kept.weighted_mean_depth_ppt`, the difference above 3 x the quadrature sum of their `err_ppt`, kept events in >= 2 sectors; not measurable when a depth or error is missing.

Calibration sets (seen records, ledgered): (a) the four P8 reviewer artefact KILLs of `data/survey/p8/review_p8.json` (`tic230120862_P16.7959`, `tic80256158_P10.8184`, `tic144277542_P12.9812`, `tic155895971_P13.1279`) and the two HOLDs; (b) the 189 P8 A passers (`data/survey/p8/stageA/`), descriptive; (c) the 1,164 A PASS records of the sealed P10 2d injections (`data/survey/p10/part2d/calibration/inj_funnel/<job_id>/`; injections entered SAP and corrected flux alike); (d) the A records of the 12 P9 rows of `tier_rederivation.csv` associated with a named planet (`p9/results/blind/tic<id>/stageA/`; uncertain TOIs, TIC 33595516 and 41422753 excluded).

Admission: a variant is eligible when it fires on <= 2.0% of (c) (below the 2.6% depth-consistency false-kill rate, `COMPLETENESS_P10.md` s.3) and on none of (d). K10 is the OR of eligible variants, re-checked against both bars (drop K10s, then K10e, until it passes). K10 is a KILL when the OR fires on `tic144277542_P12.9812` and on >= 3 of the 4 artefact KILLs; otherwise it is flag F10 (values recorded on every D record, never deciding). `k10_p12.py calibrate` writes `p12/results/part1/k10_calibration.json` (per variant and set: fired, not measurable, n, Wilson interval) and `K10_KILL` or `K10_FLAG`.

Expectation written now: a read-only design-time look at the six P8 A records measured `n_excluded / n_observed` = 8/11 on 144277542 and at most 0.5 on the other five, and the SAP condition met only on 230120862 (0.806 against 1.894 ppt); K10e fired on 18 of the 189 P8 A passers. The 3-of-4 bar is therefore not expected to be met, K10 is expected to be a flag, and the 144277542 class to be held by H5. The rule stands whatever the calibration shows.

### 1d. The Stage D plumbing test (precondition)

Copy the six P8 D inputs (`data/survey/p8/{stageA,secondary,stageB,stageC,neighbours}` for the four KILLs, `tic154566869_P8.9053` and `tic404927114_P27.5436`) into `data/survey/p12/plumbing_p8/` with a receipt. `controller_p12.py --phase plumbing_d --workers 2 --deadline 5400` runs `stage_d_worker_p12.py --product-source p8_store` (the products P8 used; refused in `bar_*`, `neg_*`, `final_*`), 100,000 TRICERATOPS draws, cutouts re-fetched to `D:`, packets under `docs/packets/audit_p12/plumbing_p8/`; each record is stamped under `p10.0` and `p12.0`.

Expected under `p10.0` (verdict and `fired` set from the CSV): 230120862 KILL K9 (K9 H1 H2); 80256158 KILL K8 (K8 K9); 154566869 KILL K8 (K8 H1); 155895971 KILL K8 (K8 K9); 404927114 HOLD H3; 144277542 SUBMIT. Under `p12.0`: the same except 144277542 HOLD H5 (or KILL K10 if admitted and firing). Every `ctoi_fields.json` carries `tiers`, `validation_status`, `candidate_tier`. A difference caused by a live measurement (a new FPP draw, a centroid, the fixed-aperture photometry that now writes a record for 404927114, `HANDOFF_P10.md` 0.11 item 7) is recorded with both values and the expectation is updated in `AMENDMENTS_P12.md` only for measurements, never rule constants. Any other difference is a defect: fix once and re-run; a second failure is STOP-3.

Then `tier_rederivation_p12.py --out p12/results/part1` re-scores the 35 saved records under `p12.0`: exactly the flips of 1b plus the K10 outcome. An unlisted flip is diagnosed: a correct consequence of a registered definition is added to the amendment table as a correction before Part 2 (the rule does not change); an implementation error is fixed. Label: "re-scoring of seen records under pre-registered rules, not a validation".

Outputs: the preregistration and seal, the overlay and D modules with tests, `p12/results/part1/{k10_calibration.json, tier_rederivation_p12.csv, plumbing_d.json}`, six packets. Commit "prompt 12 part 1". Forecast: calibration and re-scoring 0.2 h; plumbing about 1 h (6 x up to 15 min at 2 workers, about 50 cutouts at 19 s, 4.8 GB on `D:`); 1.2 queue-h, 1.5 with margin; about 4 h of engineering. Auto-advance: into Part 2 when the tests and both checks pass and `decision_point_1.json` exists.

---------------------------------------------------------------------

## Part 2: the calibration under the frozen input policy, and the one photometry test

Purpose: (i) re-measure the injection instrument under the frozen sector policy, because the P10 2d calibration used sectors the final search excludes; (ii) run the one admitted photometry hypothesis, the QLP small aperture, on the 2b instrument and the 436-host real-signal instrument, paired against (i) in the same part on the same machine; (iii) three free report-only tabulations. Outcomes are tables written by evaluator scripts; no per-candidate record of the final population is opened.

Inputs: `data/survey/injections_p8.csv` (2,100 rows on the 300 stars of `data/survey/completeness_sample_p8.csv`), `data/survey/p10/injections_2b.csv` (600 rows, expected SNR [6,30)). `E_cal` = the calibration hosts eligible under the policy (0e); an injection on an ineligible host is `INPUT_INELIGIBLE`, reported in its own row, never a miss.

### 2a. Arm A: archival photometry under the frozen policy

1. `prepare_injections_p12.py --arm archival --spec data/survey/injections_p8.csv` under `cal_a_prepare` (8 workers, 1,200 s); the uninjected false-alarm arrays are the 0e arrays of `E_cal`, reused by hash.
2. `cal_a_search` (24 workers, 3,600 s): `blind_search_worker_p12.py`, `survey_p10`, over every injected and false-alarm array; `score_injections_p12.py archival`.
3. Funnel under `p12.0` (A, S, B equal `p10.0`): pre-gate recorded on every recovered injection; `cal_a_A` (1,200 s) on every recovered injection (from its injected raw arrays) and every false-alarm pre-gate passer; `cal_a_S` (300 s) on every A passer; `cal_a_B` on the false-alarm S passers; one recorded retry pass per phase.
4. `cal_a_C` (3 x 8 threads, 12,240 s, then `--retry-of cal_a_C --deadline 36000`) on 30 S-passing injections, 10 per expected-SNR bin [7,12), [12,20), [20,50), seed 20260908 over sorted job ids (the design of `scripts/p10_stage_c.py` `injection_sample`; P10: 24/30).
5. `cal_a_real436` (24 workers, 3,600 s): the 436 from their 0e arrays (a test asserts they equal the P10.3 prepared arrays by SHA-256); `retention_p12.py` matches to the P12 sidecar by the P10.3 rule (exact or 2, 3, 1/2, 1/3, epoch check) and counts INDEPENDENT present families (P10.3: 156/377).
6. `reports_p12.py calibration archival` writes `p12/results/part2/COMPLETENESS_ARM_A.{md,json}` in the tables of `COMPLETENESS_P10.md` (level table with SNR50 and SNR90; recovery by expected SNR, period, radius, Tmag, rotation; FA per star per stage; C retention), each with an alias-credited row and the policy-loss row.

### 2b. Mixed-aperture rule, inventory, gate [A, before the inventory runs]

`sml_p12.py inventory` over `E_cal` and every eligible core star: per policy-selected product the author; for QLP whether `DET_FLUX_SML` exists in the cached FITS (`memmap=False`), its finite fraction relative to `DET_FLUX`, and the generation (TGLC from sector 94); `p12/manifests/sml_inventory.json`.

Rule: a sector uses `DET_FLUX_SML` in place of `det_flux` if and only if the selected product is QLP, the column exists and its finite fraction is >= 0.9 of `det_flux`'s; all other sectors are unchanged and the author preference is untouched; the NaN error column is filled by the existing robust-scatter rule; injections enter the swapped column like the default.

Gate: arm B runs only if >= 100 hosts of `E_cal` have >= 1 SML-usable sector and SML-usable sectors are >= 15% of the selected sector products on `E_cal` [A: below either, a 5 pp paired gain needs a within-host effect larger than any in the records; P8 used QLP for 9,023 of 20,924 arrays, `data/survey/p8/run_summary_p8.json`]. If it fails, `photometry_decision.json` records `KEEP_ARCHIVAL (NOT_TESTABLE)` with the counts.

### 2c. Arm B: the small aperture

1. `sml_p12.py store` writes `data/survey/p12/sml/raw/tic<id>/` for `E_cal` and the 436 (byte-identical except `flux` on SML sectors; hashes in `p12/manifests/sml_store_index.json`; test: differs only there).
2. `prepare_injections_p12.py --arm sml --spec data/survey/p10/injections_2b.csv` (`cal_b_prepare`); `verify_prepare_p12.py --arm sml` for the `E_cal` false-alarm stars and the 436.
3. `cal_b_search`, `cal_b_real436`, `score_injections_p12.py sml`, `retention_p12.py sml`, `cal_b_A`, `cal_b_S` as in 2a.
4. `compare_arms_p12.py archival sml --out p12/results/part2/photometry_decision.json`, paired on identical job and host ids, arm A's 2b rows as baseline.

| clause, all required | metric | threshold | precedent |
|---|---|---|---|
| search gain | R_7_15: 2b injections on `E_cal` in expected SNR [7,15), recovered search-only, exact credit | B - A >= +5.0 pp | 2b rule, `docs/RULES.md` 9.3 |
| funnel gain | the same, recovered and through pre-gate, A, S | B - A >= +3.0 pp | P11 gain clause, `p11/protocol/PROMPT_P11.txt` line 94; an aperture change can move A's depth-consistency test (77 of 92 real A losses, `FUNNEL_RETENTION_P10_3.md`) |
| strong signals | R_15_30 | B >= A - 2.0 pp | no strong-signal loss |
| false alarms | pre-gate passers on the `E_cal` false-alarm stars | B <= 1.5 x A | 2b rule |
| false alarms through S | S passers, count | B <= 3 x max(A, 2) | three-fold, floored at P10's 2 (`COMPLETENESS_P10.md` s.4) |
| real signals | INDEPENDENT present families recovered on the 436 | B - A >= 0 (paired bootstrap interval reported) | no loss on real signals; flux-level injections cannot see dilution |
| wall | median job wall | B <= 3 x A | 2b rule |
| pair completeness | unknowns after the retry pass | <= 5% per arm; an unknown is a miss in B and a recovery in A | an incomplete pair cannot clear a bar |

The judged word is `ADOPT_SML` or `KEEP_ARCHIVAL`. On `ADOPT_SML`, `cal_b_full_*` phases run the remaining injections of `injections_p8.csv` on `E_cal` and the 30-injection C sample on the SML input, `COMPLETENESS_ARM_B.{md,json}` is written, and `sml_p12.py store` plus `verify_prepare_p12.py --arm sml` build the SML inputs of every eligible core star for Part 5; arm A stays the archival comparison.

### 2d. Report-only tabulations (no rule depends on them; they feed Part 6b)

1. `window_check.json`: the retention and 1-hour noise measurement of `p11/protocol/noise_audit.py` on the 60 saved arrays of `data/survey/p11/audit_prepared_v2/` at `audit_window_days` 1.0 and 1.5 (default 0.75).
2. `long_period_tabulation.json`: from `p10/part3/results/matching.json`, recovery of INDEPENDENT present families with depth < 10 ppt and duration < 4.8 h per period bin, beside injection recovery in the same bins.
3. `s_mode_restatement.json`: per S mode, injection false kills and adversarial kills retained (`p10/results/secondary_modes.json`, `C_LOCAL_P11_5.md`); the 17.2% S false-kill rate (200/1,164, `stop_rule_1_decision.json`) enters the completeness statement as a limit.

Forecast (6.1): prepare 1.0 h; arm A search up to 2,400 x 31.7 queue-s = 21.1 h; A up to 1,893 x 15.5 s = 8.2 h; S and B 0.4 h; C 10.8 h; real leg 3.8 h; SML store and preparation 1.0 h; arm B search 900 x 31.7 s = 7.9 h, real leg 3.8 h, A 5.5 h, S 0.1 h; tabulations 0.2 h. Base 63.8 queue-h, 79.8 with margin (counts shrink to `E_cal`); C retry tail up to 10 queue-h (10% of the 30 C jobs at up to 10 h, 3 concurrent), separate. `ADOPT_SML` adds 29.5 h base (1,500 x 31.7 s = 13.2 h, A 4.3 h, C 10.8 h, preparation 1.2 h), 36.9 with margin, and its own C retry tail of up to 10 queue-h. Disk on `D:` 22 to 39 GB. Auto-advance: every phase (6.2); the decision is mechanical. Commit "prompt 12 part 2".

---------------------------------------------------------------------

## Part 3: the freeze

`freeze_p12.py` writes `p12/manifests/freeze_p12_0.json`: population, eligibility and (if chosen) extension manifest hashes; the photometry word and its table's hash; the `survey_p10` preset hash (`survey.py` lines 207 to 237); `rules_p12.py` hash, the amendment table, the K10 word; sector policy, catalogue snapshot and sidecar hashes; seeds; completeness-table hashes; every `p12/protocol/*.py` hash; an exposure-ledger snapshot. `register_p12.py` appends it to the registration seal. Tests: `rules_p12.install()` reproduces the frozen constants; the receipt round-trips. From here no threshold, preset, policy, catalogue or population changes; `controller_p12.py` checks the receipt before every `neg_*`, `bar_*`, `final_*` phase (a mismatch is STOP-1). Commit "prompt 12 part 3: freeze". Minutes; auto-advance.

---------------------------------------------------------------------

## Part 4: independent specificity, the held-out endpoint, the launch bar

Purpose: under the frozen `p12.0` and before the final search's C stage opens, measure how often B, C and D pass an independent negative, what the amended endpoint does to planets it has never seen, and whether the frozen input lost recovery: the launch bar of 3b. Nothing here changes a rule; a failure is a label. Every phase is named `neg_*` or `bar_*`.

### 4a. Rules for the negative sets [A]

- Forced route: search -> pre-gate -> A -> S and B recorded -> C on every A passer whatever S and B decided -> D on every C passer and UNRESOLVED case. End-to-end outcomes come from the recorded S and B decisions; at-D outcomes from the forced route. Reason: on P9 only 1 of 16 negatives reached C; a stage never exercised is not measured.
- Redaction (TTT and P9 negatives): `stage_d_worker_p12.py --redact-catalogue` (1b), because these are known binaries by construction and the question is whether the light-curve, fit and pixel conditions catch them. The natural set of 4d is not redacted.
- Blinding: no worker opens the TTT ephemerides or `p9/truth/`; `lock_predictions_p12.py` locks predictions at search closure; the evaluator then matches with the P9 negative rule.
- Every negative reaching D gets a one-paragraph autopsy in `SPECIFICITY_P12.md` (conditions fired, not measurable, F5, K10 values).

### 4b. Set (i): TESS Ten Thousand binaries (LB1)

The 30 stars of `ttt_negatives.csv`: `neg_ttt_download` (`build_batches_p12.py plan`, `download_star_p12.py`, 4 workers, 600 s, one transport-class retry pass, gotcha 4 checks); `neg_ttt_verify` under the frozen policy (a star with < 3 usable sectors leaves N1); `neg_ttt_neighbours` (2 workers, 900 s); `neg_ttt_search` (24, 3,600 s); `neg_ttt_A` (1,200 s); `neg_ttt_S`, `neg_ttt_B` (300 s); `neg_ttt_C` (3 x 8, 12,240 s) and its retry at 36,000 s; `neg_ttt_D` (2 workers, 5,400 s, redacted, packets under `docs/packets/audit_p12/neg_ttt/`); evaluator scoring into `p12/results/part4/ttt_table.json` (per stage reached and killed by condition, Wilson intervals, LB1a, LB1b).

### 4c. Set (iii) and the positives: the P9 held-out hosts (LB2, LB3)

Hosts (split `holdout` of `p9/truth/final_truth.csv`; `HANDOFF_P10.md` 0.0 and 2.2), written with the exposing document of every excluded host to `p12/manifests/heldout_hosts.json` before any run:
- 12 positive hosts, 13 signals: TIC 239275865, 122063843, 298074836, 164778883, 158983792, 120315006, 48448415, 122673489 (two signals), 164832454, 399955825, 298837729, 120254625.
- 13 negatives: TIC 149473467, 151826930, 379783522, 287669537, 349059354, 269238622, 279462605, 172421004, 80025900, 265489698, 229804573, 207174531 (TESS-EB) and 157568289 (TOI-645.01, blend); development negatives 33153766 and 167009792 and the re-scored 41422753 excluded.

Harness `p12/heldout/`: copies of `p9/{runner,common,dispatch,prepare,scoring,metrics}.py` and `p10/protocol/p9_scoring_adapter.py` with exactly these edits, each tested: (1) `BASE = p12/heldout/baseline/source`, a hashed snapshot of `src/` and `scripts/` at HEAD plus the P12 overlay (`p12/manifests/heldout_source_seal.json`); (2) preset and rules from the freeze (`survey_p10`, `p12.0`) in place of `F.set_rules('p8.0')` and `config='survey_p8'` (`p9/runner.py` lines 30, 85); (3) `--route negatives|normal` replacing the requirements table (lines 161 to 163); (4) the P12 deadlines in place of line 165, with the C retry; (5) outputs under `p12/heldout/{results,logs,work}`, Lightkurve cache `data/survey/p12/heldout/lightkurve/`; (6) inputs read-only from `p9/inputs/raw` with the harness's own selection, recorded per host (2-minute SPOC hosts outside the domain; they keep these inputs even if Part 2 adopted the small aperture, stated on page one); (7) scoring through the adapter copy (event match, candidate choice, nested credit, alias family for negatives, cadence floor); (8) `batch` replaced by `plan --stage <X> --route <R>`, which writes `p12/manifests/neg_p9_<X>_jobs.json` with one `runner.py stage --tic --stage --key` job per case so the P12 controller owns every job. `p9/` is never written.

Blind leg: for each stage search, A, S, B, C, D: `runner.py plan`, then `controller_p12.py --phase neg_p9_<X>` (P9 layout as ceiling: 4 search and A workers, 2 C x 8 threads, 2 D); negatives forced and redacted, positives on the normal route; lock, then truth; `p9_negatives_table.json` (LB2a, LB2b) and the blind rows of `p9_positives_table.json` (n_D).

Ephemeris-assisted leg (LB3), after the blind lock: `ephemeris_assisted_p12.py` writes one survivor row per positive signal at the truth period, epoch and duration (`final_truth.csv` `period`, `epoch_btjd`, `duration_hours`; depth from `depth_ppm`, else the A measurement at that ephemeris), runs A (recorded, not gating), the all-transit fit and D under `p12.0` without redaction (`bar_p9_eph`, 2 workers, 5,400 s), and records per signal the fit convergence, verdict and every K and H condition. Label: "ephemeris-assisted, not a funnel retention".

### 4d. Set (ii): natural load of the false-alarm stars (reported, not a bar clause)

The A passers of the `E_cal` false-alarm stars from Part 2's frozen arm (45 on the P10 2d inputs, `COMPLETENESS_P10.md` s.4): `neg_fa_C` (C on every A passer, retry at 36,000 s) and `neg_fa_D` (not redacted). Reported per stage with N and Wilson intervals in the stop-rule-2 form as a natural rate: these are unlabelled final-population stars, so a SUBMIT here is a candidate, listed with the flag `opened_in_part4`; its star's Part 5 verdict is the one delivered. Nothing in 4d changes a rule.

### 4e. The launch bar and the specificity statement

`launch_bar_p12.py` computes LB4 (Part 2's per-injection table of the frozen arm against `injection_outcomes_p10.csv`, same job ids, non-2b injections on `E_cal`) and writes `p12/results/part4/launch_bar.json` (number, N, Wilson interval, threshold, decisive flag, outcome per clause; `bar_met`). `reports_p12.py specificity` writes `p12/results/SPECIFICITY_P12.md`: per set and stage, survivors with Wilson intervals, the autopsies, the 4d rows, and two zero-compute labelled rows (set (i) S kills against SPOC DV secondary statistics in the P12 sidecar where a TCE exists; the P8 170 and P10.3 24 S rejections against TESS-EB and VSX in the snapshot). The routine records `bar_met` in `HANDOFF_P12.md` and advances either way. Commit "prompt 12 part 4".

Forecast (6.1): TTT acquisition 0.15 h (0.8 GB HTTP, 1.4 GB disk), neighbours 0.14 h, search 0.27 h, A about 0.4 h, C forced on up to 30 A passers 10.8 h, D up to 30 x 7.5 queue-min 3.8 h, cutouts 0.3 h and up to 24 GB; natural set C 45 x 0.36 h = 16.2 h, D about 18 candidates 2.3 h, cutouts 0.3 h and 14 GB; P9 hosts about 8 h (P9 spent 99,915 process-s on 48 hosts, 28,800 of them A timeouts, `p9/results/runtime_by_stage_and_label.csv`; scaled to 25 hosts with the `survey_p10` search at 2.54x) plus the ephemeris-assisted leg 1.6 h and cutouts 13 GB. Base 44.6 queue-h, 55.8 with margin; C retry tail up to 30 h, separate. Auto-advance: every phase; pauses only for a stop rule.

---------------------------------------------------------------------

## Part 5: the final search

Purpose: one search of the approved population under frozen `p12.0`; C on every B passer; D on every C passer and UNRESOLVED case; verdicts, packets, the list and the natural-load table. Every phase is `final_*`; every worker verifies the freeze hashes.

### 5a. Inputs

The eligible stars of `targets_p12_core.csv` with their frozen arrays (`data/survey/p12/prepared/archival/` or `.../sml/` per the Part 2 word). The 436, including the 29 P10.3 B survivors, are searched and verdicted like every star and carry F7 ("SPOC TCE <run> pn <n> at P = ..., an association, not a confirmation"). Guarded paths in any worker's opened files are STOP-1.

If E1 or E2 was chosen, first: relocate the audit stores (0b); acquire in batches of 100 (`final_ext_download_NN`, ascending TIC, 4 workers, 600 s, one retry pass, every `index.json` checked), starting with a 50-star pilot whose per-star bytes and wall replace the forecast's if higher; neighbours; `verify_prepare_p12.py`; then the extension calibration: 300 eligible extension stars by SHA-256 of `20260920:ext_cal:<integer TIC>`, 600 injections from a P12 copy of `scripts/make_injection_spec.py` (2 per star, seed 20260920, 1 to 4 Re, 0.5 to 30 d) plus the same 300 as false-alarm stars, through search, pre-gate, A, S (`final_ext_cal_*`; `COMPLETENESS_EXT.{md,json}`). No admission rule: the extension is searched and the statement says what the pipeline can find there. Extension stars carry `population_tier`.

### 5b. Search

`final_search` (24 workers, 3,600 s), results under `data/survey/p12/final/runs/survey_p10/`; one attempt, then exactly one recorded retry pass (`--retry-of final_search`); a star still unknown is UNKNOWN in every table. At closure `lock_predictions_p12.py` writes `p12/manifests/final_predictions_lock.json` (every accepted signal with period, epoch, duration, depth, stitch SNR, partition, budget flags) before 5e opens the sidecar.

### 5c. Collect, pre-gate, A, S, B

`funnel_plan_p12.py collect` writes `data/survey/p12/final/funnel/{candidates.csv, survivors.csv, collect_p12.json}` and one runtime per candidate. `final_A` (1,200 s) on every pre-gate passer, one retry pass; `final_S` (300 s) on every A passer and a seeded 10% of A failures (seed 20260920) for the natural-load table; `final_B` (300 s) on every S passer (PASS or HOLD).

### 5d. Stage C on every B passer

No cap; `stage_c_plan_p12.py` orders by `ranking.score_v2` for scheduling only; `final_C` (3 x 8 TLS threads, oversampling 3, native cadence, spectra saved, 12,240 s), then `--retry-of final_C --deadline 36000`; still unresolved = `UNRESOLVED` with both receipts, never a rejection. C never runs beside another phase.

### 5e. Stage D on every C passer and UNRESOLVED case

`final_D` (2 workers, 5,400 s), `stage_d_worker_p12.py --rules p12.0`: crossmatch on the frozen snapshot (`hard_stop_p10`, F7 from the P12 sidecar, opened here after the lock); the all-transit fit with the density prior; TRICERATOPS at 100,000 draws; TESScut centroids for every selected sector (one `get_sectors` per star, 240 s per cutout, at most 4 download threads, cubes on `D:`) and the star's neighbour table for A6 (P8's for the 2,000; for any star without one, `final_neighbours`, 2 workers, 900 s, minutes in total, runs before `final_D`); difference images and fixed apertures where >= 16 clean sky pixels exist; tiers with every K and H numeric, K10 or F10, H5, H6, F1 to F10, `candidate_tier`, `validation_status`; a packet per SUBMIT and HOLD under `docs/packets/audit_p12/<key>/`. A D measurement that did not run is H3, re-run once in `final_D_retry`, then delivered as HOLD H3 with the reason.

### 5f. The list, the natural load, the novelty re-check

`candidate_list_p12.py` writes `p12/results/candidates_p12.csv`: every accepted signal, last stage, stage decisions, verdict (SUBMIT tier 1 or 2, HOLD, KILL with condition, UNRESOLVED, UNKNOWN, `REJECT_NOVELTY`, `INPUT_INELIGIBLE`), `score_v2`, F1 to F10, F7, `population_tier`, `opened_in_part4`, packet path. `p12/results/natural_load_p12.json`: per-star counts at every stage for the 2,000-origin stars and the 436 apart, against the P10 false-alarm rates (11.65 / 2.363 / 0.150 / 0.0067) and the P10.3 rates (9.93 / 2.53 / 0.672 / 0.067 / 0.011). Then `catalog_snapshot_p12.py novelty` (TOI and CTOI only, 600 s, into `data/survey/p12/catalogs/final_check/`): a SUBMIT or HOLD star alerted since 0d is flagged `ALERTED_SINCE_SNAPSHOT`; no verdict changes. Commit "prompt 12 part 5".

Forecast (6.1; up to 2,436 core stars, archival): search 21.6 h plus a 5% retry pass 1.1 h; A 2,000 x 2.363 + 436 x 2.532 = 5,830 jobs x 15.5 s = 25.1 h plus 0.3 h; S about 1,100 jobs 0.4 h; B minutes; C 43 to 69 jobs x 0.36 h = 15.5 to 24.8 h (43 = the P10 false-alarm S rate on the 2,000 plus the P10.3 rate on the 436; 69 = three times the false-alarm rate on the 2,000, above the 1.4 times P8 measured: 19 B passers on 2,000 stars, `docs/AUDIT_P8.md`); D on 14 to 57 candidates (C pass fraction 32% to 83%, P8 6/19 and P10.3 5/6) x 7.5 queue-min = 1.7 to 7.1 h, cutouts 0.2 to 0.8 h and 14 to 57 GB on `D:`. Base 66.0 to 81.3 queue-h, 82.5 to 101.6 with margin; C retry tail 17 to 23 h, separate (10% of C jobs at up to 10 h, 3 concurrent); with `ADOPT_SML` the search and A lines scale by the measured wall ratio (6.1, at most 3). Records about 36 GB on `D:` (P10.3's funnel for 436 hosts: 6.5 GiB). Auto-advance: every phase; pauses only for a stop rule.

---------------------------------------------------------------------

## Part 6: completeness, audit, seals, shutdown

### 6a. `p12/results/COMPLETENESS_P12.md` (required in every final state)

1. Injection recovery under `p12.0` on the frozen input (arm A or B), through the search and through the frozen funnel (pre-gate, A, S; C on the 30-injection sample), by radius (1.0 to 1.41, 1.41 to 2.0, 2.0 to 2.83, 2.83 to 4.0 Re), period (0.50 to 1.39, 1.39 to 3.87, 3.88 to 10.76, 10.80 to 29.96 d), Tmag (12.5 to 13, 13 to 13.5, 13.5 to 14) and rotation amplitude, with bootstrap intervals, exact and alias-credited rows, the policy-loss row, and SNR50 and SNR90 per stage beside P10's. Scope, stated in the table header and in every summary that quotes it: injection completeness is measured through S, with C on the 30-injection sample; no injection runs through D; D-level behaviour on planets is measured only by LB3 on the 12 ephemeris-assisted P9 hosts; the delivered list is end to end, and its D-level completeness is not calibrated by injections.
2. Real-signal retention on the 436, labelled development-exposed and EB-contaminated: Part 2's search-level recovery [M]; the P10.3 funnel tables (156/377; 174 -> 131 -> 37 -> 13 -> 13) [P10.3]; the Part 5 results on the same hosts re-matched after the lock through C and D [M, "same hosts, final search"].
3. False-alarm and independent-negative rates per stage: Part 2 false alarms per star; Part 5 natural load; Part 4 negative survival with Wilson intervals.
4. One sentence per period class and per radius class: "At P in [a, b] d the frozen pipeline recovers X% [lo, hi] of injected planets of r1 to r2 Re on stars of Tmag 12.5 to 14 with at least 3 policy sectors through the funnel to S (n injections on m stars); below expected SNR Y (the through-S 10% recovery point) the pipeline recovers fewer than one such planet in ten on these inputs." Then the stated limits: the S gate's 17.2% false kill, the flux-level photometry test, the untested pixel lever, sectors above 105 (probe count), stars removed by the input policy.
5. The extension's own table, if one ran.
6. The yield model, one row: "model (DC15, claimed fraction 0.03, never validated by an observed count)": 21.09 through S on the 2,000 (`stop_rule_1_decision.json`) beside the observed count; no forecast of the candidate count.
7. The assumptions section.

### 6b. The closing sentence, chosen by rule [A]

"The registered P12 work on these inputs is complete; these measurements bound what it can find, and the specific experiments that could move those bounds are X", X listing every item whose condition holds (the sentence never claims that no further work could help; it names what the measurements point to): (1) through-S recovery at 1.0 to 1.41 Re below 15% (P10: 10%) -> "pixel-level photometry, the only untested input change with a measured noise lever"; (2) the 2d window check shows retention at 1.0 or 1.5 d above 0.935 by >= 0.02 with a 1-hour noise ratio <= 1.05 -> "a detrending-window test on the 2b instrument (about 20 queue-hours)"; (3) the long-period tabulation shows >= 30 planet-like families above 5 d recovered >= 15 pp below the injection bin -> "a long-period search variant"; (4) LB3 NOT MEASURED -> "an unexposed in-domain truth-positive set, which the records do not contain"; (5) if none, "new sectors beyond 105" with the probe count.

### 6c. `docs/AUDIT_P12.md`

Page one as 2a. Then: the funnel table (accepted, pre-gate, A, S, B, C pass / fail / UNRESOLVED, D verdicts, UNKNOWN) beside P8's (13,252 / 3,688 / 189 / 19 / 19 / 6; 0 SUBMIT, 2 HOLD, 4 KILL; `docs/AUDIT_P8.md`) and P10.3's; the ledger of the 29 P10.3 B survivors and every P8 B passer with a P12 record; S-rejected A passers listed "S-rejected, not verdicted"; the photometry, K10, re-scoring and plumbing tables; the Part 4 tables with each host's exposure; the artefact census of kept events beside P8's; unknowns by stage; the next-step list with each item's measurement and cost.

### 6d. `HANDOFF_P12.md`

Final state on line 1; the "resume here" line removed; what shipped, what was measured (sample sizes, unknowns), what was refuted, what is open; the three decision points and the user's choices; entry and exit environment numbers; the exposure-ledger summary; assumptions.

### 6e. Seals, integrity, tests, shutdown

1. `seals_p12.py`: SHA-256 of every file under `p12/` and `data/survey/p12/` into `p12/manifests/{source_seal_final,data_seal_final}.json`; sources re-verified against the freeze (a mismatch is STOP-1).
2. `integrity_check_p12.py final` (0 mismatches).
3. `PY -m pytest tests p11/tests p11/p11_5/tests -q`, `PY -m pytest p10/part3/tests -q`, `PY -m pytest p12/tests -q`, each alone (891 / 116 / all); `PY p12/protocol/p9_verify_p12.py final` (397 checks, only `baseline_git_HEAD_unchanged` failing; `p9/results/verification.json` untouched, its hash equal to the entry value).
4. `ledger_p12.py final`: queue-hours per phase and part, union queue-hours, job-wall hours, bytes, disk before and after, calendar days, check-ins, into `resource_ledger.json`.
5. `final_shutdown_p12.py` (6.4).
6. The final state on line 1 of both documents; commit "prompt 12 part 6: final delivery", no owner alive, no push; the last message to the user is decision point 3 (state, candidates per tier, launch-bar numbers with denominators, total cost, closing sentence).

Forecast: about 1.0 queue-h, 1.25 with margin. Auto-advance: 6a to 6e; stops at decision point 3.

---------------------------------------------------------------------

## 5. Stop rules [A]

A stop never converts an operational unknown into a miss or a rejection. Every stop writes `p12/manifests/stop_<id>_<utc>.json` (trigger, measurement, phase, owner state, what exists), closes every owned job by identity, pauses the routine at decision point 2, and leads to the state named.

| id | trigger | measurement | final state it leads to |
|---|---|---|---|
| STOP-1 integrity | a historical seal hash differs (`integrity_check_p12.py` at entry or final, the guard check in every controller loop); `data/cache/catalogs/` changed by the snapshot step; a guarded path (a sidecar, `p9/truth/`, the TTT table, a calibration truth file) appears in a worker's opened-file list; a live source hash differs from `freeze_p12_0.json` after Part 3 | the mismatch list, the file name, or the hash pair | before Part 5's search closes: `STOPPED_BEFORE_FINAL_SEARCH`, unless the human restores byte identity (tracked files from git; a changed untracked sealed file cannot be restored and ends the run) and the check re-passes, in which case the run resumes with the incident on page one; after the search closes: a delivered state only if byte identity is restored, the check re-passes and every condition of that state (section 8) is met by the end of Part 6, with the incident on page one; otherwise `STOPPED_AFTER_FINAL_SEARCH_INCOMPLETE` |
| STOP-2 storage | free space on `C:` would fall below 25 GB + 1 GB and no permitted relocation (regenerable caches only, receipted, behind junctions) restores it; or `D:` falls below 50 GB free | the controller's free-byte reading | as STOP-1's timing: `STOPPED_BEFORE_FINAL_SEARCH` before the search closes; after it, a delivered state only if the run resumes and completes Parts 5 and 6, otherwise `STOPPED_AFTER_FINAL_SEARCH_INCOMPLETE` with the phase that stopped named |
| STOP-3 entry or engineering | Part 0a's expectations not met (other than the listed untracked files); a Part 1 expectation check (plumbing or re-scoring) still fails after one fix; a copied module's test still fails after one fix | the differing number or the failing test | `STOPPED_BEFORE_FINAL_SEARCH` |
| STOP-4 user stop | `p12/manifests/USER_STOP` exists, or the user says stop in chat | the file or the message | as STOP-2 |
| STOP-5 owner loss | a controller owner is gone without a closure receipt and its receipts cannot be reconciled by the logic of `p11/p11_5/protocol/recover_controller_interruption.py` (copied as `recover_p12.py`); or a launch meets a recycled owner file | the owner receipt and pid identity | pause; the human chooses restore-and-resume (the phase restarts from its receipts under a new owner) or stop (as STOP-2) |
| STOP-6 overrun | a phase's queue-hours exceed twice its forecast with margin before it closes | `progress.json` against `forecast_p12.json` | pause; the user writes `p12/manifests/CONTINUE_<phase>` or `USER_STOP`; no rule changes |
| STOP-7 broken phase | more than 5% of a phase's jobs are operational unknowns after its one recorded retry pass, outside Stage C (whose timeouts become UNRESOLVED by rule) | the closure receipt | pause; the human decides a repair (a registered amendment, never a threshold) or stop (as STOP-2) |

Not stops (recorded, reported, auto-advanced): a launch-bar clause failing or not decisive (the search runs; the label changes); K10 entering as a flag; the small-aperture gate failing or the arm not adopted; the TTT fetch falling back to TESS-EB or yielding N1 < 20 (then LB1a is not decisive and the bar cannot be met, stated on page one); a development pair with more than 5% unknowns (the variant cannot be adopted, 2c); a SUBMIT in the natural-load set (a candidate, flagged); final-search unknowns of 5% or less after the retry pass (delivered as UNKNOWN, counted in every denominator); Stage C timeouts (retry, then UNRESOLVED).

---------------------------------------------------------------------

## 6. Resources, ownership and supervision

### 6.1 Unit costs and the total forecast

| unit | value | source |
|---|---|---|
| `survey_p10` search, 24 workers | 31.9 queue-s per star (3.811 h / 430); job wall 887 / 1,217 / 1,444 s median / p90 / max; injection jobs 760 s mean (31.7 queue-s) | `p10/part3/results/controllers/search_survey_p10/closure.json`; `p10/results/search_capacity_final.json` |
| Stage A, 24 workers | 15.5 queue-s per job; 364 / 714 / 1,202 s; 2 of 1,087 timeouts at 1,200 s | `.../controllers/funnel_A/closure.json` |
| load per star | pre-gate 2.363, A 0.150, S 0.0067 (false-alarm stars); 2.532, 0.672, 0.067 (TCE hosts); P8: 19 B passers on 2,000 | `COMPLETENESS_P10.md` s.4; `FUNNEL_RETENTION_P10_3.md`; `docs/AUDIT_P8.md` |
| S, B | 1.3 and 0.45 queue-s per job | `.../funnel_S`, `.../funnel_B` closures |
| C, 3 x 8 TLS threads | 0.36 queue-h per job (3,454 / 6,879 / 7,740 s); P8 median 6,581 s, max 30,426 s; P10 corrected controls max 22,708 s | `.../funnel_C/closure.json`; `HANDOFF_P8.md` line 123; `p10/results/stage_c_corrected_control_measurements.json` |
| D per candidate | 47 to 868 s (P4, median about 6 min); P9 median 247 s, max 724 s; planning 7.5 queue-min at 2 workers | `HANDOFF_P4.md` line 129; `p9/results/blind/*/expensive/` |
| TESScut cutout, sector >= 56 | about 100 MB, 19 s; 240 s limit | `data/survey/p8/expensive/`; `scripts/survivor_packets.py` line 49 |
| acquisition, 4 workers, 600 s | 12.9 queue-s per star (0.31 to 0.46 queue-h per 100; 0.63 at the pilot-era rate); 26.4 MB HTTP, 48 MB disk per star | `p10/part3/ACQUISITION_CLOSEOUT_20260914.md` |
| verify and prepare, 8 workers | 9.2 / 12.3 / 15.4 s per star | `.../verify_prepare_full/closure.json` |
| neighbours | 16.5 min per 2,000 stars bulk, 2 workers | `HANDOFF_P8_5.md` line 54 |
| tests; integrity | 270 + 8 s; 305 to 473 s | `final_regression_isolated.json`; `integrity_{entry,final}/summary.json` |
| duty; margin | 16.16 queue-h in 29.2 h calendar (0.553); 1.25 | `p10/part3/manifests/resource_ledger.json`; `config.json` |

| part | base queue-h | with margin | C retry tail (separate) | download | disk `D:` | disk `C:` |
|---|---:|---:|---:|---|---|---|
| 0 | 3.1 | 3.9 | 0 | < 1 GB | 18 GB | < 0.5 GB |
| 1 | 1.2 | 1.5 | 0 | 4.8 GB | 5 GB | < 0.1 GB |
| 2 | 63.8 | 79.8 | up to 10 | 0 | 22 to 39 GB | 0 |
| 2 if `ADOPT_SML` | + 29.5 | + 36.9 | + up to 10 | 0 | + 10 GB | 0 |
| 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| 4 | 44.6 | 55.8 | up to 30 | 0.8 GB + about 51 GB TESScut | about 55 GB | 1.4 GB |
| 5 (up to 2,436 stars) | 66.0 to 81.3 | 82.5 to 101.6 | 17 to 23 | 14 to 57 GB | 50 to 93 GB | < 1 GB |
| 6 | 1.0 | 1.25 | 0 | < 0.1 GB | 0 | < 0.5 GB |
| **total, archival** | **180 to 195** | **225 to 244** | **up to 63** | **72 to 115 GB** | **about 165 to 210 GB** | **under 3 GB** |
| **total, `ADOPT_SML`, wall ratio 1** | **209 to 224** | **261 to 281** | **up to 73** | same | + 10 GB | same |
| **total, `ADOPT_SML`, wall ratio 3 (ceiling)** | **305 to 320** | **381 to 401** | **up to 73** | same | + 10 GB | same |

With `ADOPT_SML` the Part 5 search and A lines (22.7 h and 25.4 h base) scale by arm B's measured median wall ratio, at most 3 under the wall clause of 2c: the ratio-1 row assumes the small aperture costs no more per job and is not an upper bound; the ratio-3 row is the registered ceiling (+96 queue-h base, +120 with margin). When Part 2 closes, `ledger_p12.py forecast --after-part2` re-renders `forecast_p12.json` with the measured ratio, and STOP-6 reads the re-rendered forecast, so an adopted slower arm is priced rather than tripped as an overrun. Calendar at 0.553 duty: 17 to 18 days archival; 20 to 21 with the small aperture at ratio 1, up to 30 at ratio 3, up to 36 with the whole retry tail; at full duty 9.4 to 10.2 days archival and 10.9 to 11.7 at ratio 1. Every figure here is a conditional planning estimate that 0e's counts, the pilot and the Part 2 ratio replace; no calendar date is promised. CPU-hours [I]: at most 24 per queue-hour, about 5,400 to 6,700. Counts are upper bounds on 2,436 stars and 300 hosts; 0e's measured counts replace them in `forecast_p12.json`.

| extension (base -> margin) | acquisition | calibration | verify, neighbours | search | A | C (1x to 3x the false-alarm rate) | D | total | bytes |
|---|---|---|---|---|---|---|---|---|---|
| E1, 1,000 stars | 3.1 to 6.3 h + 0.2 h pilot | 13.1 h | 0.5 h | 8.9 h | 10.2 h | 7 to 20 jobs, 2.5 to 7.2 h | 0.3 to 2.1 h | 39 to 49 -> **49 to 61** | 26 GB HTTP, 48 GB `D:` |
| E2, 7,989 stars | 24.8 to 50 h + 0.2 h pilot | 13.1 h | 4.5 h | 70.8 h | 81.1 h | 54 to 161 jobs, 19 to 58 h | 2.1 to 16.7 h | 217 to 295 -> **271 to 369** | 40 to 211 GB HTTP (the pilot decides), up to 383 GB `D:`, plus 82 GB relocated |

### 6.2 The controller and the check-in routine

Controller: `controller_p12.py --phase <name> [--jobs <path>] --workers N --deadline S [--retry-of <phase>]`. Exclusive owner receipt `p12/manifests/controller_owner.json` (`open("x")`; pid, create_time, cmdline, phase). Preflight: no owner, no python process, `C:` above floor + 1 GB, `D:` above 50 GB, worker and import hashes equal to the jobs manifest's, and the freeze receipt for `neg_*`, `bar_*`, `final_*`. One attempt per job; `attempts/<job_id>.json` (COMPLETE, TIMEOUT, OPERATIONAL_UNKNOWN or INTERRUPTED_UNKNOWN, wall, CPU, result hash); `launch.json` and `closure.json` with source hashes re-verified; `progress.json` every 3 s by temp plus `os.replace` (10 bounded retries) to `p12/results/controllers/<phase>/` and `p12/progress.json`; closure appends to `resource_ledger.json`. Workers via `subprocess.Popen(..., CREATE_NO_WINDOW)` with `p12_common.environment()` and affinity through `p11/p11_5/protocol/cpu_allocation.py` (imported read-only); kill by identity, children first; phases over 30 minutes launch hidden through a PowerShell launcher recorded in `p12/manifests/<phase>_launcher.json`; never edit worker-loaded source while an owner is alive.

Registered sequence: `p12/manifests/phase_sequence.json` (written in Part 0) lists every phase named in Parts 0 to 6 in the order the parts give them (Part 4: 4b, then 4c blind and ephemeris-assisted legs, then 4d), each part ending with its commit; the conditional branches of Part 2 (gate, `ADOPT_SML`) and Part 5 (extension) are keyed to their decision files; the routine pauses after `pilot_A` (decision point 1) and after the Part 6 commit (decision point 3).

The check-in routine is one command, `C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe p12/protocol/checkin_p12.py` from the repository root, then the action its printed word requires; the firing agent reads nothing else. The script is bounded: it reads `p12/progress.json`, the owner receipt and pid identity, the last 50 log lines, free bytes on `C:` and `D:`, and each active worker's CPU against the previous check; it opens no per-case result, re-reads no prompt, recomputes nothing, writes nothing under `data/survey/p12`; it appends a row to `p12/logs/checkins.jsonl` and a dated line to `RESUME_P12.md`, and prints exactly one of:
- `SLEEP`: healthy and open; do nothing. (A worker whose CPU did not advance since the last check is first stopped alone by identity and recorded; that is the script's only process action.)
- `ADVANCE <phase>`: the phase closed `CLOSED` with all owned workers closed; run `continuation_p12.py --launch`, which runs the next preflight, launches, commits at a part boundary (no owner alive) and schedules the early check.
- `PAUSE <reason>`: message the user and do nothing else. Reasons: decision point 1 or 3; any stop rule; an unreconcilable `OWNER_GONE_WITHOUT_CLOSURE`; `STORAGE_WITHIN_3GB`; a worker stalled at two consecutive checks.

Cadence: after each launch of a phase forecast over 30 minutes, one check at 10 minutes, then every 60 minutes, and a shortened final interval when the progress rate puts closure inside the hour; never more often; the session never sleep-polls. Firing:
- Codex: `C:\Users\seanj\.codex\automations\prompt-12-hourly-check-in\automation.toml` with `rrule = "FREQ=MINUTELY;INTERVAL=60"`, `status = "ACTIVE"`, the P12 thread pinned, and a prompt saying only: run the command; on `SLEEP` do nothing; on `ADVANCE` run `continuation_p12.py --launch`; on `PAUSE` message the user with the reason. Early and final checks are one-off firings of the same command (or the interval set to 10 and back to 60, each change recorded).
- Claude: a scheduled task in the session's scheduling facility (every 60 minutes, or cron `0 * * * *`) whose whole instruction is the same command and contract, plus one-off tasks for the early and final checks.
- Record facility, id, prompt SHA-256, interval and every firing in `p12/manifests/checkin_schedule.json`. With no scheduling facility, launch the phase and end the session with `RESUME_P12.md` naming the running phase and telling the next session to run the check-in command first; never a sleep loop. The historical automations stay `PAUSED`.

### 6.3 Human decision points (three)

1. **Launch approval after Part 0** (0h): the user sees the forecast, the eligibility and hard-stop counts, N1 and its fetch path, and picks the population tier. A person is needed because the extension trades 49 to 369 queue-hours and up to 465 GB against stars with no calibration, which no measurement prices, and because this is the user's one chance to decline before the machine is committed for weeks.
2. **Any stop rule** (section 5): a person is needed because a stop means the registered plan no longer describes the machine's state (a changed seal, a full disk, a lost owner, a broken or overrunning phase) and the remedy may touch sealed evidence or cost.
3. **Final delivery** (6e): a person is needed because only the user decides whether a candidate is submitted, and the completeness statement is the user's basis for closing the project on these inputs.

Everything else auto-advances: the K10 admission, the photometry gate and decision, the freeze, every negative set, the launch-bar outcome, the retry passes, the extension calibration, the novelty re-check.

### 6.4 Shutdown and verification

At the end or at any stop: close every owned job by identity; `final_shutdown_p12.py` disables the routine (Codex `status = "PAUSED"`; Claude task deleted or paused, listing saved), re-reads its configuration by id (disabled, prompt SHA unchanged), asserts every closure `CLOSED` with `all_owned_workers_closed`, no owner receipt, no python science process, the historical automations `PAUSED`, and writes `p12/manifests/final_supervision_disabled.json` (`status: DISABLED_VERIFIED`, check-in count, first and last firing). Never leave a routine armed over an idle machine.

---------------------------------------------------------------------

## 7. Deliverables (every file the executing agent writes)

Tracked unless stated; committed at the end of the part that writes them.

| path | content |
|---|---|
| `p12/PREREGISTRATION_P12.md`, `p12/protocol/{config.json, AMENDMENTS_P12.md, INTERFACES_P12.md}` | every rule and threshold, the amendment table, seeds; configuration; dated clarifications that never change a threshold; the module interfaces and lane ownership of section 10 |
| `p12/protocol/*.py`, `p12/heldout/`, `p12/tests/` | the modules of 0c and 4c with their tests; diffs and hashes in `p12/manifests/protocol_provenance.json` |
| `p12/manifests/` | `registration_seal.json`; relocation receipts; `catalog_hashes_{before,after}.json`, `catalog_versions_p12.json`, `hard_stop_p12.json`; `targets_p12_core.csv`, `eligibility_p12.json`, `input_jobs/`, `input_identity/`, `targets_ext_E{1,2}.csv`; `sector_probe.json`, `ttt_fetch.json`, `ttt_negatives.csv`; `forecast_p12.json`, `decision_point_1.json`; `sml_inventory.json`, `sml_store_index.json`; `freeze_p12_0.json`; `heldout_hosts.json`, `heldout_source_seal.json`; every prediction lock; `phase_sequence.json`; every `<phase>_jobs.json` and `<phase>_launcher.json`; `exposure_ledger.jsonl`; `resource_ledger.json`; `checkin_schedule.json`; `final_supervision_disabled.json`; `{source,data}_seal_final.json`; any `stop_*.json`, `USER_STOP`, `CONTINUE_<phase>` |
| `p12/results/` | controller receipts per phase; `integrity_{entry,final}/`; `part1/{k10_calibration.json, tier_rederivation_p12.csv, plumbing_d.json}`; `part2/{COMPLETENESS_ARM_A, COMPLETENESS_ARM_B if run}.{md,json}`, `photometry_decision.json`, `window_check.json`, `long_period_tabulation.json`, `s_mode_restatement.json`; `part4/{ttt_table, p9_negatives_table, p9_positives_table, fa_natural_table, launch_bar}.json`; `SPECIFICITY_P12.md`; `COMPLETENESS_EXT.*` if run; `candidates_p12.csv`; `natural_load_p12.json`; `COMPLETENESS_P12.md` |
| `p12/logs/` | `entry_preflight.json`, `sprint_clock.json`, `p9_verification_{entry,final}.json`, controller logs, `checkins.jsonl`, `last_checkin.json` |
| `RESUME_P12.md`, `HANDOFF_P12.md` (root); `docs/AUDIT_P12.md` | the routine's lines; the handoff (6d); the audit (6c, page one as 2a) |
| `docs/packets/audit_p12/<key>/` | per SUBMIT and HOLD: `packet.md`, `ctoi_fields.json` (`CTOI_FORM_FIELDS` with `tag`, `candidate_name`, `paper_url` left for the user, plus `tiers`, F1 to F10, `validation_status`, `candidate_tier`, `population_tier`, `external_submission_performed: false`), figures, stage JSONs; subtrees `plumbing_p8/`, `neg_ttt/`, `neg_p9/`, `neg_fa/` |
| `data/survey/p12/` (untracked, on `D:`, hashed in the seals) | catalogue snapshot and sidecar, prepared arrays, calibration arms with guarded truth files, SML store, runs, funnel cases, held-out data, D records, Lightkurve and TESScut cubes |

---------------------------------------------------------------------

## 8. Final-state vocabulary (exactly one; every run ends in one of these)

| state | conditions | deliverables required |
|---|---|---|
| `FINAL_SEARCH_DELIVERED_BAR_MET` | `freeze_p12_0.json` predates every `neg_*`, `bar_*`, `final_*` launch receipt; `bar_met = true`; `final_search` closed over every eligible star (UNKNOWNs listed); every B passer carries C PASS, FAIL or UNRESOLVED; every C passer and UNRESOLVED case a D verdict or HOLD H3; integrity entry and final at 0 mismatches; routine `DISABLED_VERIFIED` | everything in section 7; the list may be empty (a clean null, stated beside the completeness and specificity statements) |
| `FINAL_SEARCH_DELIVERED_BAR_NOT_MET` | the same, except `bar_met = false`; the failing or non-decisive clause, its number and consequence, and the 3c sentence are lines 1 to 3 of `docs/AUDIT_P12.md`; every SUBMIT's F9 names the clause | everything in section 7 |
| `STOPPED_AFTER_FINAL_SEARCH_INCOMPLETE` | `final_search` closed over every eligible star (UNKNOWNs listed), but a stop rule fired, the user stopped, or the final integrity check did not reach 0 mismatches before every condition of a delivered state was met; the receipt names the trigger and the last closed phase; every owned job closed; routine `DISABLED_VERIFIED` | everything in section 7 that exists, plus an "unfinished work" block on page one of `docs/AUDIT_P12.md` and `HANDOFF_P12.md`: B passers without a C outcome, C passers and UNRESOLVED cases without a D verdict, SUBMITs and HOLDs without a packet, the integrity status, the launch-bar table as measured; `candidates_p12.csv` labelled `partial` in its header with each star's last closed stage; `COMPLETENESS_P12.md` and `SPECIFICITY_P12.md` from what was measured, with a line per missing item; the cost ledger; the resume point |
| `STOPPED_BEFORE_FINAL_SEARCH` | a stop rule fired, or the user declined at decision point 1, before `final_search` closed; the receipt names the trigger and the last closed phase; every owned job closed; routine `DISABLED_VERIFIED` | `HANDOFF_P12.md` and `docs/AUDIT_P12.md` for the completed parts with the stop on page one and "no final search was run"; `COMPLETENESS_P12.md` from whatever Part 2 measured (or the P10 2d tables labelled "pre-P11 sector set, not the frozen input") with a line per missing item; `SPECIFICITY_P12.md` if Part 4 closed; seals of what exists; the cost ledger; the resume point |

No other state may be claimed; a non-decisive clause is a line inside a delivered state, not a state. "Discovered", "found" and "confirmed" appear in no deliverable about anything the pipeline produced.

---------------------------------------------------------------------

## 9. Assumptions [A]

1. P10.3's unit costs (430 hosts, median 16 sectors) bound the costs on the P8 stars (median 8); the injection-host mean of 760 s agrees; the pilot can only raise the forecast.
2. The false-alarm rates measured on the pre-P11 sector set forecast the natural load under the frozen policy within the margin; Part 2 re-measures them.
3. C's median of 0.36 queue-h (6 jobs) against P8's 1.83 h; the 10% retry share is an adopted allowance, reported as a separate tail.
4. Stage D costs 3 to 15 minutes per candidate and MAST serves TESScut at about 19 s per cutout; Part 1 re-measures both.
5. The eligible fraction of the 2,000 is close to the calibration hosts' 235 to 241 of 300; Part 0e measures it.
6. `DET_FLUX_SML` exists on most QLP products of sectors 56 to 93 as one aperture family; TGLC-era products may lack it; the gate decides. Flux-level injections suffice for the recovery comparison, not for dilution or throughput, hence the real-signal clause and the stated limit.
7. The TESS Ten Thousand table is obtainable and at least 20 binaries meet the cuts after the relaxations; if only the TESS-EB fallback works, N1 is probably below 20 (6 TESS-EB matches in the domain, `INCUMBENT_CHECKS_P8_DOMAIN.md`), LB1a is not decisive and the bar cannot be met, as page one then says.
8. The 25 P9 hosts are unexposed to every P12 rule decision; their pre-D outcomes were seen by P9 and P10 (disclosed); they are 2-minute hosts outside the domain, many Kepler planets, so they test the tier rules, not the domain's sensitivity, and fewer than 5 ephemeris-assisted fits may converge.
9. The C and D outcomes of the false-alarm stars' A passers are unexposed to any rule decision (the stars entered Part 2 only as counts).
10. Redacting K0, K5's catalogue clause and H4 makes known binaries a fair test of the light-curve, fit and pixel conditions.
11. K10s is fair on injections (both streams injected), and K10e's injection fire rate is an adequate proxy for its cost on real planets.
12. The 436, though development-exposed, are a valid search-level instrument; F7 is an association, not a confirmation.
13. Sectors 56 to 105 with the QLP exclusions are the right input; later sectors are counted, not searched.
14. The field's validation bar is out of reach for TESS FFI photometry alone at Tmag 13.5 (F5 not measurable on 17 of 22 seen records), so tier 1 is an honest CTOI-grade label and tier 2 the ceiling.
15. The six catalogue sources are fetchable; a failing one falls back read-only to its 2026-09-04 copy (0d).
16. The machine stays as measured with no competing process; the scheduling facility fires within minutes (P10.3: 34 firings over 29.0 h); commits under the three `-c` flags do not trigger auto-maintenance.

## 10. First session: the bounded Part 0 engineering sprint [binding for the first session]

The user's instruction, verbatim: "Execute a bounded Part 0 engineering sprint using one lead and three subagents. Complete the required entry checks first, then define shared interfaces and assign disjoint files across controller/recovery, input preparation, and catalogue/population work. The lead owns shared configuration, manifests, seals, integration and commits. Preserve every scientific rule, exposure restriction and stop rule in PROMPT_P12.md. Do not run later-part measurements or launch live workers while their source is being edited. Prioritize tested implementations and integration over scaffolding. Reserve the final 90 minutes of this four-hour window for integration, verification and a durable handoff; do not relax checks to meet the deadline."

How it binds to this prompt:

### 10a. Scope and clock

- The sprint is Part 0 and nothing else: 0a, 0b and 0c in full, then 0d, 0e, 0f, 0g and 0h in that order as far as tested, integrated work reaches. No job of `cal_*`, `plumbing_d`, `neg_*`, `bar_*` or `final_*` is launched; no per-candidate record is opened (0c.5); no sealed path is written (0c.6); no rule, threshold, exposure restriction or stop rule of this prompt changes.
- T0 is the UTC of the first command of 0a, written to `p12/logs/sprint_clock.json` with the deadlines below. Engineering ends at T0 + 150 minutes. From T0 + 150 to T0 + 240 the lead does only integration, verification and the handoff (10c to 10e). A task that cannot close (tests green, integrated) by T0 + 150 is not started; one still open at T0 + 150 is stopped and recorded as open.
- Every check of 0a, every test of 0c, the integrity check and the P9 verification keep their expected values. A check that fails is diagnosed and fixed once; if it still fails it is reported open in the handoff and STOP-3 applies as written (the sprint then ends in the handoff with the stop on page one). No expectation is edited to pass, no test is skipped or weakened, no deadline of `config.json` is shortened to fit the window.

### 10b. Order and lanes

1. The lead, alone, before any subagent starts: 0a (read-only entry measurements against the expected values; `p12/logs/entry_preflight.json`); 0b (the directories, the `D:` junction and its receipt, the cache-redirect rule); `p12/protocol/config.json` and `p12_common.py` (the shared configuration, 0c row 1); `diff_origins_p12.py`; a smoke test so `PY -m pytest p12/tests -q` runs; and `p12/protocol/INTERFACES_P12.md`: for every module of the 0c table its lane, its public functions with signatures and return types, the receipts it writes and their formats, the origin file and the permitted diff, and the test that proves it. Interfaces are frozen for the sprint once written; a change goes through the lead and is logged in the same file.
2. Three subagents in parallel, one lane each, disjoint files, the same working tree, no git worktrees, no branches, no commits, no controller launches, no network, no detached process:
   - Lane A, controller and recovery: `controller_p12.py`, `guards_p12.py`, `checkin_p12.py`, `continuation_p12.py`, `final_shutdown_p12.py`, `recover_p12.py`, `blind_io_p12.py`, `integrity_check_p12.py`, `register_p12.py`, `p9_verify_p12.py`, `ledger_p12.py` (the forecast rendering of 0h and the `--after-part2` re-render of 6.1), with the tests their 0c rows name (exclusive owner; TIMEOUT with no orphan; freeze refusal; retry manifest; trigger table; sequence order; synthetic tree; synthetic interrupted phase; a guarded open fails the job; seal round-trip). The controller is exercised on a synthetic job tree with a dummy worker under `p12/tests/`; no science worker is launched.
   - Lane B, input preparation: `policy_products_p12.py`, `build_input_jobs_p12.py`, `verify_prepare_p12.py`, `input_identity_p12.py`, `download_star_p12.py`, `build_batches_p12.py`, `neighbours_worker_p12.py`, `neighbours_batch_worker_p12.py`, `blind_search_worker_p12.py`, `lock_predictions_p12.py`, `prepare_injections_p12.py`, `score_injections_p12.py`, `sml_p12.py` (inventory and store only), with the tests their rows name (no excluded QLP product is ever returned; the swap touches only named sectors; 5 of the 436, chosen by the 0c hash rule, reproduce their P10.3 status and prepared SHA-256; the injected array differs only in-transit; the 1e-12 equality on 5 unchanged hosts; 20 sealed 2d rows re-scored identically; hash refusal; corrupt FITS re-downloaded with `force=True` on a fixture).
   - Lane C, catalogue and population: `catalog_snapshot_p12.py`, `build_sidecar_p12.py`, `crossmatch_p12.py`, `catalog_adapter_p12.py`, `targets_p12.py`, `fetch_ttt_p12.py`, `sector_probe_p12.py`, with the tests their rows name (`data/cache/catalogs/` hashes unchanged after a run, on a fixture; bare TCE FLAG and not K0; TOI REJECT and K0; a P8 star CLEAN; cuts on a fixture; hash order; relaxation order). Lane C writes code and fixtures only; the live 0d snapshot, the 0e run and the 0f fetches are launched by the lead in 10c.
   - Outside the sprint unless every lane above is integrated with green tests before T0 + 150: `funnel_plan_p12.py`, `funnel_worker_p12.py`, `stage_c_plan_p12.py`, `stage_c_worker_p12.py`, `close_stage_c_p12.py`, `stage_d_worker_p12.py`, `stage_d_packets_p12.py`, `rules_p12.py`, `k10_p12.py`, `tier_rederivation_p12.py`, `retention_p12.py`, `tce_families_p12.py`, `compare_arms_p12.py`, `p12/heldout/`, `freeze_p12.py`, `launch_bar_p12.py`, `candidate_list_p12.py`, `seals_p12.py`, `reports_p12.py`. They serve Parts 1 to 6 and are listed as open in the handoff with their 0c rows.
   - A subagent edits only the files of its lane and their tests. A change it needs in `p12_common.py`, `config.json` or another lane's interface is a written request to the lead, who makes it and records it in `INTERFACES_P12.md`. A subagent may read the sealed evidence its tests need by script (0c.5 permits sealed P8, P9 and P10 records) and never opens `p9/truth/`, a sidecar, the TTT table or a calibration truth file (gotcha 18; the `blind_io_p12` guards apply to its tests too). A subagent never runs `git`, never launches a controller phase, never writes under `data/survey/`, `p9/`, `p10/`, `p11/`, `src/`, `scripts/` or `docs/`, and never starts a process that outlives its task.
3. The lead, while the lanes work: `INTERFACES_P12.md`, `p12/manifests/phase_sequence.json`, the receipt formats, review of each lane's diff against its 0c row as it lands, `p12/manifests/protocol_provenance.json` from `diff_origins_p12.py`. The lead edits no lane file while its subagent is active.

### 10c. Integration (from T0 + 150 at the latest)

1. The lead runs `PY -m pytest p12/tests -q` alone, then the historical suites in separate processes (891 passed 1 skipped; 116 passed), then `integrity_check_p12.py entry` (0 mismatches) and `p9_verify_p12.py entry` (397 checks, one expected failure). A failing test is fixed by the lead once; otherwise its module is marked open and its test stays failing in the record, never deleted or skipped.
2. Only with green tests and 0 mismatches, and only when no source the launched workers load is being edited by anyone, the live Part 0 steps run in order, each closing before the next starts, as far as the clock allows: 0d (the snapshot, one network step, 600 s per source); 0e `verify_core` (about 1.0 queue-h at 8 workers, 1.25 h with margin: launch only if it can close by T0 + 215); 0f (the probe and the TTT fetch); 0g (the pilot at 24 workers: launch only if it can close by T0 + 215); 0h (the forecast and `decision_point_1` rendering). A step that cannot close in time is not launched and the handoff says so. Launched phases run detached under `controller_p12.py` as 0c.8 requires; the lead reads `checkin_p12.py` between its own integration steps, never in a sleep loop. A phase still open at T0 + 225 is stopped by identity (`terminate_owned`), `recover_p12.py` reconciles its receipts, and the handoff names it as the resume point; nothing runs past the session.
3. `diff_origins_p12.py`, then the sprint commit (10d).

### 10d. Commits

One commit by the lead at the end of the sprint, under the three `-c` flags of 0c.1, with no owner alive, adding `p12/`, `HANDOFF_P12.md` and `RESUME_P12.md` and nothing historical: "prompt 12 part 0: engineering sprint <UTC>", or "prompt 12 part 0" if 0h closed and Part 0 is complete. Never push.

### 10e. The durable handoff (written before T0 + 240, whatever the state)

`HANDOFF_P12.md` opens with "SPRINT HANDOFF <UTC>": T0 and the deadlines; the 0a entry table with expected and observed values; per module of the 0c table its status (`done and tested` with the test names and count, `written, tests failing` with which, `open`) and the SHA-256 of every file under `p12/protocol/` and `p12/tests/`; which live Part 0 steps closed, with their receipts (0d hashes, 0e counts, 0f N1 and the probe count, 0g raw walls and converted units, 0h forecast), and which did not; the open items per lane in priority order; every expectation not met and what was done about it; `git status --short` after the commit. `RESUME_P12.md` holds one line: "resume here: <the first unfinished item of Part 0>; no owner alive; no routine armed". The sprint arms no scheduling routine; decision point 1 is reached only if 0h closed, and the next session arms the routine of 6.2 when it launches Part 1.

### 10f. The subagent brief

The lead gives each subagent exactly this, with its lane's file list and 0c rows appended: "You are implementing lane <X> of `PROMPT_P12.md` Part 0c in the TessHunter repository at `C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter`. Read `PROMPT_P12.md` sections 0a, 0b, 0c, Part 0 and section 10, and `p12/protocol/INTERFACES_P12.md`. Copy, never edit, the origin modules your rows name; change only what each row says; write the tests each row names under `p12/tests/`; run only `PY -m pytest p12/tests/<your test files> -q` with the environment of 0a and `TESSHUNTER_OFFLINE=1`. Edit only the files in your list. Do not run git, do not launch any controller phase, do not write under `data/survey/`, `p9/`, `p10/`, `p11/`, `src/`, `scripts/` or `docs/`, do not open `p9/truth/`, any sidecar, the TESS Ten Thousand table or any truth file, do not start a detached process, do not edit `p12_common.py` or `config.json` (ask the lead). Stop at <T0 + 150 UTC> and report: files written, tests and their results, what is unfinished, any interface change you need."

---------------------------------------------------------------------

## 11. Amendment log (2026-09-22, after the synthesis; corrections of this prompt's own text, not new measurements)

1. The historical P9 verifier is no longer run against its sealed destination at entry or closeout; `p9_verify_p12.py` writes under `p12/logs/`, so gotcha 14 and 0c.6 hold without exception.
2. The timing pilot converts job walls to queue-seconds per star at 24 workers before comparing with 6.1, and runs at the production width (24 stars, 24 workers).
3. Part 2's Stage C retry tail is counted (up to 10 queue-h per arm); the tail totals are 63 archival and 73 with the small aperture.
4. The `ADOPT_SML` forecast states its wall-ratio ceiling (305 to 320 base, 381 to 401 with margin at ratio 3) and is re-rendered after Part 2 so that STOP-6 prices an adopted slower arm.
5. A fourth final state, `STOPPED_AFTER_FINAL_SEARCH_INCOMPLETE`, covers a stop after the search closes and before Parts 5 and 6 complete.
6. The completeness sentence states the recovery rate below the 10% point instead of "not findable", the completeness scope (through S; D only on the LB3 hosts) is stated wherever it is quoted, and the closing sentence of 6b names the next experiments instead of "no further pipeline work is worth doing".
7. A6's centroid route to tier 2 requires an informative centroid (3-sigma radius <= 1 pixel, every capable neighbour excluded); a target-consistent but unlocalised centroid is recorded and does not count.
8. Section 10 adds the first session's bounded engineering sprint. It changes no scientific rule, exposure restriction or stop rule.
9. The untracked-file list of 0a includes five paths that `git status` showed on 2026-09-22 and the synthesis omitted, so 0a's expectation does not stop the sprint at entry.

`P12_DESIGN_RATIONALE.md` predates these amendments; where its forecast or wording differs from this file, this file governs.

End of `PROMPT_P12.md`. Finish the feasible measurement rather than stopping because a branch disappointed; keep the registered rules; deliver a list whose every number carries its instrument and its limit.
