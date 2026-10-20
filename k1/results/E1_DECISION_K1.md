# K1 rule E1 (cadence): registered outcome and its S-mode sensitivity

Dated 2026-10-10 (UTC). Prompt K1, Part D/E. Tags: [M] measured, [A] adopted/registered, [I] interpretation.
Inputs: Part D searches (1,000 injections, 250 FA hosts, both arms, 8,100 s), Stage A (legacy) and
Stage S (every mode, one scan) under the prediction lock `partD_S`. Source:
`k1/results/e1_partD.json` and the ledgers `k1/results/ledgers/injections_{k1,s56}_partD_S.csv`.

## E1 applied exactly as registered [A]

The pool is 259 injections with expected SNR 7-20 on the all-sector data, on 166 hosts. Retention is
measured through S under mode `bound`.

| condition | measured | required | holds |
|---|---|---|---|
| (a) R(k1) - R(s56) | +2.70 pp (18.5% vs 15.8%), host-bootstrap 95% [-2.56, +7.78] | >= 3 pp and lower bound > 0 | **no** |
| (b) pre-gate FA per star, k1 / s56 (250 FA hosts) | 2.692 / 2.212 = 1.22 | <= 1.5 | yes |
| (c) search wall, k1 / s56 (paired injection jobs) | 1.69 | <= 3 | yes |

**Outcome: `survey_k1_s56` is adopted.**

The bounded diagnostic does not apply. Of the 20 pool injections that s56 recovers and k1 does not,
2 are at P > 10 d and 4 are on partition-limited hosts, 4 of 20 in total, which is not "mainly".

* Discordant pairs: k1-only 27, s56-only 20.
* Four injections on one host have no s56 data and count as s56 non-recoveries.

## Why it failed: a written explanation, as the rule requires [M]

The all-sector arm leads at every stage up to and including A. It gives most of the lead back at S under
`bound`, and keeps it under the S modes that rescue off-phase features.

| stage / S mode (pool of 259) | k1 | s56 | k1 - s56 | host-bootstrap 95% |
|---|---|---|---|---|
| search | 36.3% | 25.9% | +10.4 pp | [+4.3, +16.7] |
| pre-gate | 32.8% | 22.0% | +10.8 pp | [+4.8, +16.6] |
| A | 31.3% | 20.5% | +10.8 pp | [+5.3, +16.4] |
| S `bound` (E1's registered mode) | 18.5% | 15.8% | +2.7 pp | [-2.4, +7.8] |
| S `empirical_bound` | 19.7% | 17.0% | +2.7 pp | [-2.6, +7.9] |
| S `recurrent_bound` | 25.1% | 18.1% | +6.9 pp | [+1.2, +12.8] |
| S `recurrent_bound_corr` | 25.1% | 18.1% | +6.9 pp | [+1.2, +12.8] |
| S `bound_alias` | 28.6% | 18.9% | +9.7 pp | [+3.9, +15.2] |

* [M] Under `bound`, S removes 41% of the k1 arm's A-passing pool injections (81 to 48). It removes
  23% of the s56 arm's (53 to 41).
* [M] The k1 kills are "SECONDARY ECLIPSE: a dip at phase x". The phases are arbitrary (0.15, 0.34,
  0.67, 0.76, 0.80, ...), so these are not secondaries of the injected planets.
* [I] With the older 1,800-s SAP sectors included, the off-phase scan finds more significant
  noise/systematics dips. `bound` has no rescue for a non-recurrent off-phase feature;
  `recurrent_bound` and `bound_alias` do.
* [M] At expected SNR 7-40 on the adopted (s56) arm, `bound_alias` leads S retention: 193 vs 167 of
  401 for `bound`. This is the leading mode for the C sample. E2's adversarial constraint (DEV
  pass-through at the end of D) is not yet measured.
* [M] FA through S per star (250 FA hosts) is identical in both arms:
  * `bound` 0.04;
  * `bound_alias` 0.088 (k1) and 0.08 (s56).

[I] The registered E1 fixes the S mode to `bound` before E2 chooses the mode the survey would use. If E2
selects `bound_alias` (or a recurrent mode), the survey would run with a mode under which the all-sector
arm recovers about 1.5x as many pool injections, yet E1 will have adopted s56. This sensitivity was not
anticipated at registration. Any change now would be a post-hoc amendment, made after seeing outcomes.

## Options for the user

1. **Keep E1 as registered** (`survey_k1_s56`). Part D continues on s56: the C sample is drawn from the
   s56 arm under `bound_alias` / `bound`.
2. **Amend (post-hoc, labelled as such).** Re-apply E1's three conditions under the S mode that E2
   selects, once the DEV adversarial pass-through is measured (after DEV D, about 6-8 h).
   * The C-sample arm waits for that.
   * If E2 selects `bound` or `empirical_bound`, the outcome is unchanged (s56).
   * If it selects `bound_alias`, the numbers above give survey_k1:
     * (a) +9.7 pp, lower bound +3.9;
     * (b) 1.22;
     * (c) 1.69.
