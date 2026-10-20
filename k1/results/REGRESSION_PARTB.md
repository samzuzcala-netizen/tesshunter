# Part B8 — regression proof (P12 reproducibility first)

Tags: [M] measured in this run.  Machine-readable: `k1/results/b8_replay.json`,
`k1/results/preset_identity_partB.json`, `k1/logs/tests_baseline/`, `k1/logs/tests_partB/`.

1. **Test suites [M]** — same counts as the Section 1 baseline on the final Part B src:
   | suite | baseline | after Part B |
   |---|---|---|
   | `tests/` | 786 passed, 1 skipped | 786 passed, 1 skipped |
   | `p11/tests` | 7 | 7 |
   | `p11/p11_5/tests` | 98 | 98 |
   | `p12/tests` | 248 (isolated runner) | 248 (plain pytest; the isolated runner refuses while other K1 phases run python) |
   | `k1/tests` (new, changes 2-14) | — | 55 passed |
   | `scripts/p8_smoke_v1.py` | 0 differences | 0 differences |
   Two P12/P11.5 frozen-source guards caught first drafts and shaped the final layout: `p12/tests/test_rules_p12.py`
   pins `audit_rules.py` (K1 thresholds moved to the new `src/tesshunter/k1_rules.py`; `audit_rules.py` is byte-identical
   to `aee65172b`), and `p11/p11_5/tests/test_search.py` pins `pipeline._detect_planets` to its versioned copy (the K1
   gate-7 change is a context manager, `pipeline.ExposureAwareGate7`, entered by `survey.run_job` only for K1 presets;
   `_detect_planets` is unchanged).
2. **Preset identity [M]** — every pre-K1 preset (`survey_v1`, `survey_p8`, `survey_p8_600s`, `survey_p10*`) has the
   same `to_dict()`, ingest key and search kwargs as at `aee65172b` (`k1/work/check_preset_identity.py`).
3. **Stored-case replay [M]** — 12 P12 `final` candidates replayed (frozen `survey_p10` search on the stored prepared
   input, then Stage A, Stage S, and Stage B where a repaired B record exists) into `D:\tesshunter_k1\b8_replay`:
   **11 reproduce field-for-field** (timestamps and wall/CPU seconds excepted): tic31851521_p09, tic312091108_p07,
   tic165530589_p03, tic181233766_p02, tic219755626_p01, tic165530589_p07, tic99769004_p02, tic160272538_p04,
   tic234503605_p05, tic431479577_p04, tic261654470_p06 (Stage B also compared on 4 of them).  tic25080724_p02: Stage A and
   S identical; its search record differs only inside budget-limited partitions, where the number of detection passes
   that fit the wall budget depends on machine load (stored ~260 s per pass under P12's 24 workers, replay ~167 s).
   A first replay pass run without P12's single-thread environment differed at ~1e-13 in BLS power (BLAS reduction
   order); K1 workers now use the same single-thread settings (`k1_common.environment`).
4. **No edits** under `p9/`, `p10/`, `p11/`, `p12/`, `scripts/audit_p5.py`, `scripts/revet_p6.py` or any existing
   script; the six `.~lock.*#` deletions under `p12/results/funnel/` predate K1 and are not staged.
