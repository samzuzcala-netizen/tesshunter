# K1 launch plan (frozen package; DO NOT LAUNCH: final state NOT_READY)

Dated 2026-10-14 (UTC). Prompt K1, Part G4. Tags: [M] measured, [R] review, [A] adopted, [I] interpretation.

**Status.** K1 ended **NOT_READY**: G1 is 29/55 = 52.7% against a 60% bar (`k1/results/VALIDATION_K1.md`). This
plan is the frozen package such a launch would use once a later prompt resolves G1, or once the user decides to
launch on the G2 evidence (K1 non-inferior to, and ahead of, P12: +9.1 pp). Nothing here launches anything.

## 1. Frozen inputs

| input | value |
|---|---|
| targets | `k1/survey/targets_k1.csv`: 7,000 K (ranks 1-7,000) + 3,000 eM (`slice = eM_slice`, ranks 1-3,000) by E_new. sha256 5768d330...8ae8, unchanged by the 2026-10-14 TOI/CTOI refresh (0 dropped). |
| SPOC TCE veto | `k1/survey/tce_sidecar_k1.csv`; 48 targets flagged |
| configuration | `k1/protocol/config.json` + `k1/manifests/freeze_k1.json` (re-frozen under amendment 7). survey_k1, all usable sectors 1-98, 8,100 s search budget, S `bound_alias`, legacy SAP-ramp rule, k1.0 tiers, amendments 1-7. |
| hashes together | `k1/manifests/launch_package_k1.json` |

## 2. Batches (rank order; the eM slice inside the first two batches)

| batch | stars | content |
|---|---|---|
| 1 | 2,000 | eM ranks 1-1,500 + K ranks 1-500 |
| 2 | 2,000 | eM ranks 1,501-3,000 + K ranks 501-1,000 |
| 3 | 2,000 | K ranks 1,001-3,000 |
| 4 | 2,000 | K ranks 3,001-5,000 |
| 5 | 2,000 | K ranks 5,001-7,000 |

After batch 2, apply the eM decision rule (section 6).

## 3. Stage order, workers and deadlines

1. **Download.** 4 MAST workers, one search per star. Bounded calls; the QLP 74-79 v02 requirement; usable
   sectors only.
2. **Search.** `search_worker_k1.py`, survey_k1, 8,100 s budget, 24 workers, with Windows' default scheduling
   (the condition the calibration was measured under). Deadline 13,860 s.
3. **Pre-gate.** stitch SNR >= 7.1, >= 3 stitch transits, epoch-consistent.
4. **Stage A** (legacy ramp, exposure-aware depth). 28 workers (opted out of power throttling), deadline
   1,800 s, scaled 4x on its one retry. [I] Add an n_usable-scaled deadline for >= 30-sector stars.
5. **Stage S**, `bound_alias`: 16 workers.
6. **Stage B**: 16 workers.
7. **Stage C** (blind TLS 0.5-110 d): 8 workers x 4 TLS threads; deadline 57,600 s (30-40-sector stars take
   8-15 h).
8. **Stage D**: 6 workers, online, with the K1 hard stop:
   * REJECT on TOI/CTOI/NASA/TESS-EB/TTT;
   * FLAG within 21";
   * SPOC TCE sidecar as a period veto.

Each phase runs under `controller_k1.py`, with one retry pass for unknowns.

## 4. Supervision

* One detached controller per phase.
* An early check ~10 minutes after each launch, then one check-in every 60 minutes (`checkin_k1.py`).
* No polling.
* The routine is disabled at the end of the survey.

## 5. Price and storage

**Price.** Priced from measured job walls by usable-sector count (`k1/results/survey_price.json`; 1.5x margin):

| stage | queue-hours |
|---|---|
| search | 345 |
| A | 117 |
| S | 0.4 |
| B | 0.2 |
| C | 809 |
| D | 104 |
| **total** | **~1,376 (~57 days)** |

* That is ~275 queue-hours per batch, with batches 1-2 cheaper: eM stars have fewer sectors on average.
* [I] Stage C on >= 20-sector stars dominates the cost.
* [M] 34% of the list has >= 30 usable sectors.

**Storage on D:.** [M] Per-star use measured in Parts D-F:

| item | rate | survey total |
|---|---|---|
| light-curve store | ~1.3 MB per star | ~13 GB |
| search records | ~1.9 MB per star | ~19 GB |
| funnel case folders | ~2 MB per A candidate | ~55 GB |
| Stage D pixel cutouts | ~0.2 GB per D candidate | ~200 GB |
| **total** | | **~290-390 GB** |

D: has 616 GB free (floor 100 GB). C: is at ~36 GB (floor 25 GB); nothing K1 writes goes to C:.

## 6. Expected outcomes

**Expected new planets** (`k1/results/yield_partG.json`; Part D through-C curve x50 14.4, w 2.4, cmax 0.79;
range from the C-sample Wilson bounds):

| slice | expected | range |
|---|---|---|
| 7,000 K (TOI-calibrated occurrence) | **7.0** | 4.5-8.6 |
| 3,000 eM, TOI-calibrated | **1.9** | 1.1-2.5 |
| 3,000 eM, published DC15 | **6.5** | 3.8-8.8 |

[R] The review's own curve on the same list gives 7.1 / 2.3 / 7.9.

**eM rule restated** (>= 5 real new candidates: eM leads the next batch; <= 2: stay with K; 3-4: extend the
slice):

* the TOI-calibrated expectation (1.9) gives "stay with K";
* the published expectation (6.5) gives "eM leads".

[I] Batches 1-2 measure which applies.

**SUBMIT + HOLD labels per 1,000 stars, [I] about 5-15** (assumptions labelled):

* natural false alarms through S: 0.088 per star ([M], 250 FA hosts);
* Stage C pass fraction for natural false alarms: unmeasured; P12's ~16% is assumed;
* real signals: ~0.7-1 new planets per 1,000 K stars, plus known-planet hosts that pass the hard stop.

[R] The M-dwarf rate was 4-5 per 1,000.

## 7. Stop rules for the survey itself

| rule | trigger | action |
|---|---|---|
| S-D | C: < 25 GB or D: < 100 GB | pause (relocate caches behind a junction with a receipt) |
| S-F | a phase's unknowns > 10% after its retry, or a MAST/archive outage > 6 h | pause; unknowns stay unknown |
| S-P | a batch's partition-limited fraction > 25% (calibration: 9-14%) | pause and report |
| S-C | more than 5% of a batch's Stage C jobs exceed 16 h | pause and report the cost |
| S-L | more than 30 SUBMIT + HOLD per 1,000 stars in a batch (about 2x the upper expectation) | pause: a false-alarm blow-up |
| S-N | always | nothing is uploaded, posted or sent; nobody is contacted; no ExoFOP / TFOP / VSX submission. Labels are candidates for the user's review, never detections. |
