# tesshunter recovery-improvement report

Date: 2026-08-06. Starting point: commit `4fcf906` (the state described by
`BENCHMARK_REPORT.md`). Scoring is the FROZEN `tesshunter_benchmark/score.py`,
unmodified.

## Summary

| | dev (24 planets) | | holdout (6 planets) | |
|---|---|---|---|---|
| | before | after | before | after |
| **Recovered** | 15 | **17** | 3 | **4** |
| Alias | 3 | 2 | 0 | 0 |
| **Missed** | 6 | **5** | 3 | **2** |
| **False positives** | 14 | **12** | 6 | 7 |
| Recovered mislabeled FP | 1 | **0** | 1 | 1 |
| Mean depth error | 25.9% | **13.0%** | 33.1% | **10.9%** |
| **Paired depth error** | 25.9% | **8.8%** | 33.1% | **13.7%** |
| Worst target wall clock | 2088 s | **1178 s** | — | 1719 s |

Dev: every tier in the frozen priority order improved and no planet moved
backwards. Holdout: recovered up, missed down, and depth error down on every
paired planet, at the cost of one extra false positive. Suite 124 → 177, all
green. Public API additive-only. No crashes, no timeouts.

Two planets were newly recovered on the dev set (TOI-270 b, upgraded from a 2×
alias; TOI-700 b, the shallowest target in the set at 460 ppm) and one on the
holdout (GJ 357 b).

Sections 1, 2 and 4 are the parts worth reading if you only read some of this:
three of the brief's leads were refuted by measurement, one of my own
hypotheses was refuted by my own probe, and seven known weaknesses survive.

## 0. The environment described in the brief did not exist on this machine

This has to come first, because every number below depends on it.

The brief describes a working setup at `C:\Users\samzu\...` with Python 3.14,
every dependency installed, and a ~1.5 GB light-curve cache. What was actually
present:

| Brief | Reality | Action |
|---|---|---|
| `C:\Users\samzu\...` | `C:\Users\seanj\...`, plus one extra directory level | Re-pointed `targets.py` (env-var overridable) |
| Repo healthy, 124 tests | **`src/` and `tests/` deleted from the working tree** | Restored from git `4fcf906` (working tree held deletions only, nothing was overwritten) |
| Python 3.14 with all deps | Python 3.13.3 / 3.12, **zero** scientific packages | Created a venv at `C:\Users\seanj\Downloads\tesshunter_venv` |
| Cache ~1.5 GB, 919 FITS | **Empty** — one file, the ExoFOP CSV | Re-downloaded from MAST |

Dependencies were installed into a disposable venv rather than the user's
global Python. Versions: lightkurve 2.6.0 (the version the brief names),
astropy 8.0.1, numpy 2.5.1, scipy 1.18.0, pandas 2.3.3, Python 3.13.3.

**Because of this, the brief's own validity condition — "your comparisons are
only valid if you run on the same machine with the same cache" — could not be
met by assumption and had to be established by measurement.** It was:

- `pytest tests/ -q` → **124 passed**, exactly as specified.
- A full 10-target run of the *unmodified* code (`--mode current_local`)
  reproduces the frozen reference **exactly**: recovered 15, alias 3, missed 6,
  FP 14, mislabels 1, and mean depth error identical to 1e-12
  (0.25945726312591677 in both).
- Per-target spot checks are bit-identical to the stored reference in period,
  depth, SNR and transit count.

So the reconstruction is not merely functional, it is numerically faithful, and
deltas measured here are directly comparable to the published standings.
`results/current_local/` is retained as the on-machine baseline and as the
evidence for this claim.

### Harness changes (no scoring logic touched)

`score.py` restricts `--mode` to `{baseline, fixed}` via argparse choices, so a
new mode cannot be scored by invoking it. Rather than edit the frozen scorer,
`score_any.py` imports it and calls its `score_target()` unchanged.
Equivalence is proved, not asserted: `score_any.py --verify` re-scores both
immutable reference runs through the wrapper and diffs against
`fixed_scores.json` / `baseline_scores.json` — both **IDENTICAL**.

Also added: `compare_any.py` (arbitrary A/B plus the required paired-depth
analysis; it reproduces `BENCHMARK_REPORT.md`'s 15.7% → 21.7% paired figure
exactly), `simulate_vetoes.py`, `build_holdout_targets.py`, `run_holdout.sh`,
and diagnostic probes. `orchestrate.py` gained arbitrary `--mode`, a
`--concurrency` override, and process-scoped sleep inhibition (the brief flags
mid-run sleep as a silent corrupter; this sets no persistent power setting).

Concurrency was raised from 3 to 5. Each target is single-threaded (~0.8 core)
and the machine has 24 cores, so this cuts wall-clock without slowing any
individual target. The per-target 2400 s timeout is unchanged and no target
timed out.

## 1. Leads from the brief that the evidence REFUTED

Three of the brief's candidate directions were checked against the stored data
before building, and were not implemented because the data says they are wrong.
Recording them matters as much as the changes that shipped.

### 1.1 The absurd-depth / implied-radius veto removes zero false positives

The brief proposes vetoing candidates whose fitted depth implies a companion
far larger than the star, and calls it "likely the single safest FP reduction
available". Computed over all 14 FPs and all 18 true detections
(Rp/Rs = sqrt(depth), radius = Rp/Rs x R_star):

- largest **false positive** implied radius: **0.54 R_Jup** (HD 63433)
- largest **true detection**: **1.24 R_Jup** (WASP-18 b), then 0.97 (WASP-126 b)

The ordering is inverted: any radius threshold deletes real hot Jupiters before
it touches a single FP. Moreover the veto **already exists** and is already
tighter than the brief proposes (`vetting.py`: `RADIUS_HARD_VETO_RJUP = 2.5`,
`RADIUS_HIGH_RISK_RJUP = 1.5`) — it simply never fires.

TRAPPIST-1's "physically absurd 1.5–9.6% depths" are not absurd as radii: on a
0.121 R_sun star, 9.6% implies 0.37 R_Jup, an ordinary planet. The absurdity
lives in Rp/Rs, not in radius. Reformulated as `Rp/Rs > 0.20` it would remove 3
FPs — real, but far from the headline win, and it was superseded by the
duration-rail veto which removes the same TRAPPIST-1 candidates for a
better-founded reason.

### 1.2 Harmonic suppression would delete currently-recovered planets

The brief proposes suppressing periods near accepted periods "and their
low-order harmonics". Real planetary systems are resonant; in this dev set
alone:

| system | pair | ratio |
|---|---|---|
| TOI-270 | d/c | **2.010** |
| L 98-59 | d/c | **2.019** |
| TRAPPIST-1 | g/e | **2.025** |
| TRAPPIST-1 | g/d | 3.050 |
| HD 63433 | c/b | 2.890 |

Suppressing low-order harmonics would veto TOI-270 d and L 98-59 d, both
currently recovered. Only the ratio-1 half of the lead was implemented, and the
shipped code carries an explicit comment and a parametrised regression test
covering these six ratios so the harmonic half is not re-added later.

### 1.3 The period-grid cap is a red herring

Forensics found the 20000-frequency cap is not causal for any miss, alias, FP
or depth error: achieved period precision is ~20x inside the scorer's 2%
tolerance on the coarsest grid and ~250x inside it after local refinement. No
work was spent raising it. (The brief's "34k–62k frequencies" figure is also
wrong against the logs — requests span 28,703 to 887,048.)

## 2. A hypothesis of my own that I tested and abandoned

I suspected `alternating_event_consistency` was misfiring on shallow, low-SNR
planets and forcing 2P through the resolver's Priority-2 path. A first probe
appeared to confirm it at a ~37% false-alarm rate at every noise level.

That was a bug in **my probe**, not in the code: I passed the ephemeris epoch
in the wrong time frame (the synthetic helper stores time as BTJD + 2457000),
so it sampled random phases and I was measuring how often a scale-invariant
ratio test fires on pure noise. The noise-independence was the tell — a genuine
noise-driven false alarm rate would rise with noise.

Corrected, the measured false-alarm rate on a strictly periodic injection is
**0.0%** at per-transit SNR 12.3, 4.1 and 2.1, and 2.5% at SNR 1.0. The
function is sound and was left untouched. The real mechanism is in section 3.2.

## 3. Dev-benchmark result

`results/current_local/` (unmodified code, this machine) vs
`results/improved_final/`, both scored by the frozen scorer over the same 24
in-range planets.

| Metric | before | after | delta |
|---|---|---|---|
| **Recovered** | 15 | **17** | **+2** |
| Alias (partial credit) | 3 | 2 | −1 |
| **Missed** | 6 | **5** | **−1** |
| **False positives** | 14 | **12** | **−2** |
| **Recovered mislabeled FP** | 1 | **0** | **−1** |
| Mean depth error | 25.9% (n=15) | **13.0%** (n=17) | −12.9pp |
| **Paired depth error** (recovered in both, n=15) | 25.9% | **8.8%** | **−17.1pp** |
| Worst target wall clock | 2088 s | **1178 s** | 1222 s of headroom |
| Crashes / timeouts | 0 | 0 | — |

Every tier in the frozen priority order improved, and no planet moved
backwards. The two status changes are both upgrades:

- **TOI-270 b**: `alias:2P` → **recovered** (3.36008 d against a true 3.36017 d,
  0.003% error). TOI-270 now returns all three planets with zero false
  positives, where before it returned two plus an alias plus a duplicate FP.
- **TOI-700 b**: `missed` → **recovered**. The shallowest planet in the set
  (460 ppm). It was never a sensitivity failure: two ringing false positives
  were consuming the target's detection slots.

Per-planet detail is in section 3.1; depth detail in 3.2.

### 3.1 Per-planet

| Target | Planet | True P (d) | before | after | depth err before | depth err after |
|---|---|---|---|---|---|---|
| WASP-18 | b | 0.94145 | recovered | recovered | 22.0% | **8.1%** |
| WASP-126 | b | 3.28879 | recovered | recovered | 7.6% | **0.5%** |
| LHS 3844 | b | 0.46293 | recovered | recovered | 16.5% | **3.5%** |
| TOI-270 | b | 3.36017 | alias:2P | **recovered** | – | 4.1% |
| | c | 5.66048 | recovered | recovered | 0.6% | 12.3% |
| | d | 11.37970 | recovered | recovered | 18.6% | **5.0%** |
| L 98-59 | b | 2.25311 | recovered | recovered | 21.8% | **8.4%** |
| | c | 3.69068 | recovered | recovered | 4.2% | 4.9% |
| | d | 7.45073 | recovered | recovered | 4.8% | 6.6% |
| Pi Mensae | c | 6.26783 | recovered | recovered | 57.5% | **7.0%** |
| HD 63433 | b | 7.10793 | missed | missed | – | – |
| | c | 20.54382 | recovered | recovered | 101.2% | **30.8%** |
| TOI-700 | b | 9.97727 | missed | **recovered** | – | 85.1% |
| | c | 16.05111 | recovered | recovered | 3.8% | **1.9%** |
| HD 108236 | b | 3.79589 | alias:3P | alias:3P | – | – |
| | c | 6.20362 | recovered | recovered | 46.5% | **1.0%** |
| | d | 14.17589 | recovered | recovered | 54.3% | **1.2%** |
| | e | 19.59016 | recovered | recovered | 21.6% | **5.4%** |
| TRAPPIST-1 | b | 1.51087 | recovered | recovered | 8.2% | 35.5% |
| | c | 2.42182 | alias:3P | alias:3P | – | – |
| | d, e, f, g | | missed | missed | – | – |

### 3.2 Depth: what moved and what did not

Paired over the 15 planets recovered by both runs, **25.9% → 8.8%**, improving
11 of 15. The four largest errors in the old run all collapse:

| planet | before | after |
|---|---|---|
| HD 63433 c | 101.2% | 30.8% |
| Pi Mensae c | 57.5% | 7.0% |
| HD 108236 d | 54.3% | 1.2% |
| HD 108236 c | 46.5% | 1.0% |

Two planets got worse and the reason is understood, not mysterious: **TRAPPIST-1
b (8.2% → 35.5%)** and **TOI-270 c (0.6% → 12.3%)**. Both had accurate BLS box
depths already, and the new estimator measures the transit CORE — the
limb-darkened flat bottom — which is genuinely deeper than the
duration-averaged value catalogues report. This is a real systematic and is
listed in section 4 as the ceiling on the depth metric. The signed errors
across all 17 recovered planets are mixed (9 negative, 8 positive), so a global
retune of the core window would push the negative half further negative; it was
not done.

TOI-700 b's 85.1% depth error is honest and worth stating plainly: it is
credited as recovered on period alone (9.977 d), but its fitted duration is
0.0135 d against a catalogue T14 near 0.094 d, so the depth is meaningless.
A recovery, but a poor characterisation.

### 3.3 What shipped, per change

Seven commits. Deltas are attributed by the method named in each row; the
frozen scorer is used throughout.

| # | Commit | Change | Attribution method | Measured effect |
|---|---|---|---|---|
| 1 | `bd6c09a` | Gates 6+7: ratio-1 ringing veto, railed-duration veto | replay of stored candidate lists through the frozen scorer (`simulate_vetoes.py`), each gate in isolation and combined | FP 14 → 10 (each alone), 14 → 7 (combined), everything else bit-identical |
| 2 | `fbb16d7` | Alias resolver descends a winning trial to its fundamental | full benchmark | **inert as first written** — geometric test scored 0.452 against a 0.50 threshold |
| 3 | `4c61906` | Depth re-measurement at accepted ephemerides (Stage 4.5) | full benchmark | paired depth 27.2% → 7.1% |
| 4 | `dbc59d5` | Radius-aware secondary-eclipse exemption | frozen scorer | mislabels 1 → 0 |
| 5 | `886e1b8` | Vetoed signals masked not fatal; descent uses absolute event counts | full benchmark | **recovered 15 → 17, missed 6 → 5**; FP 9 → 12 (see below) |
| 6 | `68ffc87` `97321c4` | Adversarial-review fixes: baseline contamination, sibling transits, EB fail-safe | full benchmark + targeted real-data probe | net depth 13.0%; HD 63433 c preserved at 30.8% |
| 7 | `57118e5` | Detection loop bounded by wall clock, not pass count | measured pass costs vs the 2400 s timeout | worst target 2088 s → 1178 s; removes a latent timeout failure |

Two rows deserve their honest reading:

**Commit 2 did nothing on its own.** The alias descent as first written never
fired. Rather than lower the threshold to rescue one target — which would be
tuning against the dev truth table — the trial table was dumped and the real
mechanism found (section 3.4). The fix landed in commit 5.

**Commit 5 is a trade, and the commit-1 headline of "FP 14 → 7" describes a
paper simulation, not a run.** The simulation could not model freed detection
slots refilling. Measured end to end, the mask-and-continue behaviour buys
**+2 recovered and −1 missed** at a cost of **+3 false positives** relative to
the intermediate run that lacked it (`results/improved` scored 15/2/7/9;
`results/improved_v2` scored 17/2/5/12). Under the frozen priority order —
recovered above missed above FP — that trade is correct, and the final result
is still −2 FP against the baseline. But it is a trade and is stated as one.

### 3.4 The alias mechanism, since it is the most interesting finding

`event_completeness` is a **fraction**, so it structurally rewards a fold for
examining fewer epochs. Dumping the resolver's trial table for TOI-270 b:

| trial | period (d) | SNR | ev_comp | n_covered | n_dip | composite |
|---|---|---|---|---|---|---|
| **P** | 3.359656 | **11.77** | 0.600 | 15 | **9** | 7.062 |
| **2P** | 6.721913 | 9.34 | **1.000** | 6 | 6 | **9.342** ← won |
| 3P | 10.080843 | 8.23 | 0.833 | 6 | 5 | 6.862 |

The true period predicts 15 transit epochs and confirms 9; the 2× harmonic
predicts 6 and trivially confirms all 6, scoring a perfect 1.000. Multiplied
into `snr × ev_comp × (1 − overlap)` that overturns an SNR of 11.77 at the
truth with 9.34 at the harmonic. The score was actively biased toward the
harmonic.

The fix uses the **absolute** count `n_dip`, already computed and previously
unused for this: a true fundamental explains strictly more transit events
(9 vs 6), while a spurious sub-harmonic merely redistributes the same events
across alternating epochs and finds no more. That asymmetry is what makes the
rule safe rather than a tuned threshold.

## 3.5 Holdout: the improvements generalise

Five targets never used during development, built mechanically by
`build_holdout_targets.py` from the mission's table plus cached ExoFOP truth
(rows with TFOPWG disposition CP or KP — that column IS present, so the
"all TOI rows" fallback was not needed). Six in-range planets, two out-of-range
scoring as bonus only. Both code versions were run once each, in one session,
on the same pre-warmed light curves, with only the source differing.

| Metric | before | after | delta |
|---|---|---|---|
| **Recovered** (of 6) | 3 | **4** | **+1** |
| **Missed** | 3 | **2** | **−1** |
| False positives | 6 | 7 | **+1 (worse)** |
| Recovered mislabeled FP | 1 | 1 | 0 |
| Mean depth error | 33.1% (n=3) | **10.9%** (n=4) | −22.3pp |
| **Paired depth error** (n=3) | 33.1% | **13.7%** | **−19.4pp, improved 3 of 3** |
| Worst target wall clock | — | 1719 s | inside the 2400 s timeout |

| Target | Planet | True P (d) | before | after | depth err before | depth err after |
|---|---|---|---|---|---|---|
| WASP-121 | b | 1.27492 | recovered | recovered | 29.0% | **14.9%** |
| GJ 357 | b | 3.93060 | missed | **recovered** | – | 2.2% |
| TOI-125 | b | 4.65172 | recovered | recovered | 15.6% | **0.0%** |
| | c | 9.15494 | recovered | recovered | 54.7% | **26.3%** |
| HD 21749 | c | 7.78979 | missed | missed | – | – |
| AU Mic | b | 8.45368 | missed | missed | – | – |

The direction of every dev-set gain reproduces on unseen targets: recovered up,
missed down, depth error down on **every** paired planet. This is the main
anti-overfitting result.

**The +1 false positive is a real regression and is not explained away.** The
seven are listed in `compare_any.py --a holdout_current --b holdout_improved`;
two belong to AU Mic, whose top candidate is an 18,029 ppm activity signal at
SNR 273 — the brief predicted AU Mic would be brutal and it was. HD 21749 c and
AU Mic b remain missed by both versions.

### Holdout process disclosure

The holdout was run **twice for the pre-improvement baseline and once for the
improved code**, and the reason is a defect of mine, not a tuning loop. The
first baseline run produced 0 planets and 0 s wall time on all five targets:
I had added `time_budget_s=` to `run_target_fixed.py` unconditionally, and the
pre-improvement `search_target` has no such parameter, so every target died on
`TypeError` and was recorded as an empty result. The harness now introspects
the signature and passes version-dependent kwargs only when accepted, which is
what a before/after harness must do. The baseline was then re-run once.

**No improved-code holdout result was ever re-run, and nothing from the holdout
fed back into any threshold or design decision.** The failed baseline contained
no information about the improved code.

## 4. Known weaknesses, disclosed

Six independent adversary agents attacked each change with synthetic probes,
and a separate adjudicator sorted reproduced defects from theory. Three
findings were fixed (commits 6 and 7). The rest are real and are recorded here
rather than patched.

1. **Gate 6's exclusion zone can be anchored on a false positive.** The veto
   tests period proximity only, and detection cannot consult a verdict because
   vetting runs afterwards. Reproduced: a 120 ppt eclipsing binary accepted
   first causes a real, independent SNR-100 planet 3.87% away to be vetoed as
   its "ringing", and the pipeline then reports that planet at half its true
   period. On the dev set two currently-missed planets sit inside live
   exclusion zones anchored on false positives — TRAPPIST-1 e at 3.47% of an
   accepted candidate, g at 4.61%. Gate 6 will be the binding constraint on any
   future TRAPPIST-1 work.
   *An epoch-overlap refinement was built and then rejected on measurement:
   real ringing has essentially no epoch overlap either (TOI-700's two genuine
   ringing FPs score 0.043; the TOI-270 duplicate scores 0.000, sitting at
   anti-phase), so the refinement would have disabled the veto entirely and
   given back the TOI-700 b recovery.*
2. **Gate 7 can veto a genuinely ultra-short-duration planet.** Reproduced: a
   single box transit with T14 = 0.011 d against `duration_min = 0.01` and
   10-minute bins is deleted (gate on → 0 planets; gate off → recovered at
   SNR 84.8). The gate fires on fitted duration alone, with no depth, SNR or
   period condition. It is also entry-point dependent: the benchmark's
   `duration_min` arms it, while `config.py`'s 0.02 d disarms it entirely.
3. **The depth estimator measures the limb-darkened flat bottom**, not the
   duration-averaged depth catalogues report. This is now the floor on the
   depth metric and it cost TRAPPIST-1 b and TOI-270 c (section 3.2).
4. **The secondary-eclipse exemption still de-escalates a genuine eclipsing
   binary** at high SNR ("likely false positive" → "ambiguous"). The flaw is
   astrophysical and cannot be fixed with a better radius cut: everything from
   ~0.3 M_Jup to the hydrogen-burning limit is 1.0–1.2 R_Jup, so radius cannot
   identify the population the exemption targets. The design was changed to
   fail safe — the flag is always raised, so such a system lands on "ambiguous"
   and is never cleared as "promising" — but the correct discriminant is
   period-aware (the secondary an irradiated planet can produce at the observed
   a/R*), not a fixed ratio plus a radius cut.
5. **The alias resolver halves the period of an eclipsing binary** whose
   secondary is 30–50% of the primary. Measured across three seeds, this
   happens at both `SUBHARMONIC_DIP_RATIO = 0.30` and 0.50, because the
   composite argmax picks P/2 on its own — so raising the constant would fix
   nothing and would risk the TOI-270 b recovery. The frozen scorer does not
   measure this, since it is a wrong ephemeris on a false-positive-class object.
6. **The depth pass accepts any positive measurement**, so on a candidate with
   no real depth at the accepted ephemeris it can ship a positively-selected
   noise draw while the `snr` on the same row still reflects the discarded BLS
   depth. Visible in the shipped run: TRAPPIST-1 planet 1 carries
   `depth_ppt_bls = 52.396` against `depth_ppt = 0.685` with `snr = 34.5`.
   This affects false positives, not recoveries.
7. **`preprocessing.bin_lightcurve` silently returns the UNBINNED curve** when
   `flux_err` is absent or non-positive. Real SPOC products always carry
   errors, so the benchmark is unaffected, but it silently disarms gate 7 and
   multiplies BLS cost ~5x for any caller that builds a light curve without
   them.

## 5. Remaining work

1. **Gate 6 needs a plausibility-aware anchor.** The right signal is not epoch
   overlap (measured, refuted). A candidate whose depth implies a
   non-planetary companion should not be allowed to carve an exclusion zone.
2. **Gate 7 needs a second condition.** Railed duration alone is not sufficient
   evidence; combining it with an implied `Rp/Rs > 0.2` would still remove the
   three catastrophic TRAPPIST-1 candidates while sparing a real short transit.
3. **HD 63433 b and TOI-700 b characterisation.** Both are limited by duration
   mis-fits rather than sensitivity.
4. **TRAPPIST-1 d/e/f/g remain out of reach** and are now additionally
   constrained by gate 6 (weakness 1).
5. **A period-aware secondary-eclipse test** would replace weakness 4 properly.
6. **The holdout's +1 false positive** was not diagnosed; TOI-125 and HD 21749
   each contribute two shallow (142–845 ppm) candidates worth a look.

## 6. Reproducing this

```bash
# environment (the venv is disposable; nothing was installed globally)
C:/Users/seanj/Downloads/tesshunter_venv/Scripts/python.exe -m pytest tests/ -q -p no:cacheprovider

# prove the scoring wrapper is the frozen scorer
cd tesshunter_benchmark && python score_any.py --verify

# dev benchmark
python orchestrate.py --mode <name> --concurrency 5
python score_any.py --mode <name>
python compare_any.py --a current_local --b <name>

# holdout (checks out each commit in turn; refuses a dirty tree)
bash run_holdout.sh
```

Result sets on disk, none of the reference sets touched:

| directory | what it is |
|---|---|
| `results/current_local/` | unmodified code on this machine — the equivalence proof |
| `results/improved/` | first improved run (regressed TRAPPIST-1) |
| `results/improved_v2/` | after the mask-and-continue fix |
| `results/improved_v3/` | after the first contamination guard (depth regressed) |
| `results/improved_final/` | **the final result** |
| `results/holdout_current/`, `results/holdout_improved/` | holdout, one run each |

`results/baseline/`, `results/fixed/`, `results/fixed_prewindowfix/`,
`baseline_scores.json` and `fixed_scores.json` are untouched, as is `score.py`.
