# K2 launch plan (frozen package; DO NOT LAUNCH without the user)

Dated 2026-10-15 (UTC). Prompt K2, Part 5. Tags: [M] measured, [R] review / K1, [A] adopted, [I] interpretation.

**Status.** K2 ended **NOT_READY**: on the fresh confirmatory set G1 is 38/64 = 59.4% against the 60% bar, one planet short (Wilson 47-71%). G2 (+10.9 pp over P12) and G3 (0/70 SUBMIT) pass (`k2/results/VALIDATION_K2.md`). This is the frozen package a launch would use once a later prompt resolves G1, or once the user decides to launch on the evidence.

Nothing here launches anything. This updates `k1/survey/LAUNCH_PLAN_K1.md`. Changed: the Stage C input (V3),
sibling masking (M1), Stage C workers and deadlines, the price and the expected yield. Everything else is K1's.

## 1. Frozen inputs

| input | value |
|---|---|
| targets | `k2/survey/targets_k2.csv`: the same 7,000 K + 3,000 eM in the same order as `k1/survey/targets_k1.csv` (sha256 5768d330...). The 2026-10-15 TOI/CTOI re-snapshot dropped 0 and added 0. |
| SPOC TCE veto | `k2/survey/tce_sidecar_k2.csv`; 48 targets flagged |
| configuration | `k2/protocol/config.json` + `k2/manifests/freeze_k2.json` (sha d47da619...): K1's frozen configuration (survey_k1, usable sectors 1-98, 8,100 s search budget, S `bound_alias`, legacy SAP ramp, k1.0 tiers, K1 amendments 1-7) **plus** Stage C input V3 (30-min bins, propagated errors; AMENDMENT_K2_20261014_1; TLS oversampling 2 on baselines > 1,000 d) **plus** M1 sibling masking. Stage A unchanged (A1 not adopted). |
| catalogue snapshot | `D:/tesshunter_k2/catalogs/snap_20261015` (`k2/manifests/catalog_snapshot_20261015.json`) |

## 2. Batches

As K1 (rank order, the eM slice inside the first two batches):

| batch | stars | content |
|---|---|---|
| 1 | 2,000 | eM ranks 1-1,500 + K ranks 1-500 |
| 2 | 2,000 | eM ranks 1,501-3,000 + K ranks 501-1,000 |
| 3 | 2,000 | K ranks 1,001-3,000 |
| 4 | 2,000 | K ranks 3,001-5,000 |
| 5 | 2,000 | K ranks 5,001-7,000 |

The eM decision rule (section 6) applies after batch 2.

## 3. Stage order, workers and deadlines

1. **Download.** As K1: 4 workers, one search per star, usable sectors only, QLP 74-79 v02.
   * [M] Concurrent appends from 4 download workers lost 13 of 208 exposure-ledger rows in K2. Give the ledger a
     file lock, or one writer, before launching.
2. **Search.** As K1: `search_worker_k1.py`, survey_k1, 8,100 s, 24 workers, Windows-default scheduling, deadline
   13,860 s.
3. **Pre-gate.** As K1.
4. **Stage A.** As K1, deadline 1,800 s with a 4x retry. [M] CVZ hosts still time out at 1,800 s (4 of 1,905 A
   jobs in K2; all completed on the retry).
5. **Stage S** (`bound_alias`) and **Stage B**: as K1.
6. **Stage C: changed.**
   * `funnel_k2.py C` with `k2_c_variant = V3`. The M1 siblings come from the same search's S receipts (stitch
     SNR higher, `bound_alias` PASS/HOLD, not an alias), so **all of a star's S jobs must finish before its C jobs
     are planned**.
   * Case roots copied from the A/S/B case root (`k2_copy_from`).
   * Workers: 8 x 4 TLS threads.
   * [M] Under clean conditions V3 jobs took 48 s to 22 min (median 18 min on >= 30-sector hosts). With the
     machine oversubscribed, up to 1.7 h.
   * A 4-h deadline covers every K2 C job under the amended input (367). Keep 57,600 s on the retry.
7. **Stage D.** As K1: 6 workers, online, K1 hard stop, the K2 snapshot.
   * [M] Stage D is TESScut-bound: about 1 min per sector cutout, 20-40 min per multi-sector candidate. Keep one
     shared TESScut cache for the whole survey.
   * When a Stage C record's S mode differs from the D runtime's, D refuses the job (rules stamp p10.0 vs
     p10.0-partial). Plan D with the C runtime's S mode.

Each phase runs under `controller_k2.py` with one retry pass for unknowns.

## 4. Supervision

* One detached controller per phase, plus the background waiter `k2/work/wait_k2.sh <max_min> <phases>`. The
  waiter wakes the session on a closure or after 60 minutes; `checkin_k2.py` runs at each wake.
* [M] Session cron check-ins did not fire in K2, so they are not the supervision mechanism.
* No polling. Never edit a pinned source while a phase runs.

## 5. Price and storage

**Price** (`k2/results/survey_price_k2_final.json`; K1's method with V3 Stage C unit costs; 1.5x margin):

| stage | K1 | K2 |
|---|---|---|
| search | 345 | 345 |
| A | 117 | 117 |
| S + B | 0.6 | 0.6 |
| C | 809 | **34** (61 with the oversubscribed HELD-OUT / fresh walls) |
| D | 104 | 104 |
| **total** | **~1,376 qh (~57 days)** | **~601 qh (~25 days)**; 628 sensitivity |

* [I] The search (345 qh) is now the largest item, then A and D. The next cost lever is the search budget or
  grid, with its own paired recall check.
* **Storage:** as K1 (~290-390 GB on D:, mostly Stage D cutouts). [M] D: had ~597 GB free on 2026-10-15; C: ~35
  GB (floor 25 GB).

## 6. Expected outcomes

**Expected new planets** (`k2/results/yield_k2.json`; K2 through-C curve x50 13.9, w 2.35, cmax 0.79; ranges
from the C-sample Wilson bounds):

| slice | K2 | K1 |
|---|---|---|
| 7,000 K (TOI-calibrated) | **7.3** (4.8-8.8) | 7.0 (4.5-8.6) |
| 3,000 eM, TOI-calibrated | **2.0** (1.2-2.7) | 1.9 (1.1-2.5) |
| 3,000 eM, published DC15 | **7.0** (4.2-9.3) | 6.5 (3.8-8.8) |

**eM rule**, unchanged from K1:

* >= 5 real new candidates: eM leads the next batch;
* <= 2: stay with K;
* 3-4: extend the slice.

The TOI-calibrated expectation (2.0) says stay with K; the published one (7.0) says eM leads. Batches 1-2 decide.

**SUBMIT + HOLD per 1,000 stars:** [I] about 5-15, as K1 (the C pass fraction of natural false alarms is still
unmeasured).

## 7. Stop rules for the survey itself

As K1 (S-D, S-F, S-P, S-L, S-N), except S-C: pause if more than 5% of a batch's Stage C jobs exceed 4 h (V3 jobs
take minutes; a long job now signals a problem).
