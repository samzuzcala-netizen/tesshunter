# K2 Part 2: Stage A cross-product depth consistency (rule A1)

Dated 2026-10-15 (UTC). Prompt K2, Part 2. Tags: [M] measured, [A] adopted/registered, [I] interpretation.
Nothing here is a detection.

**Sources:**

* `k2/results/a1.json`;
* `k2/manifests/ra_a1_selection.json`;
* receipts `D:/tesshunter_k2/funnel_receipts/ra_a1/{A,S,B}/`.

**Rules:** `k2/protocol/RULES_K2.md` section 3.

## 1. Outcome [A]

**A1 is not adopted.** Neither scope meets criterion (i) (+3 pp injection retention through A at expected SNR
>= 20). Stage A stays K1's.

| scope | (i) retention through A, 498 injections | (ii) A-level FA per star | (iii) DEV adversarial A-pass rate | qualifies |
|---|---|---|---|---|
| K1 | 433 (86.9%) | 0.088 (22 / 250) | 45 / 136 = 33.1% (22 of 35 hosts) | - |
| A1a `author` | 434 (87.1%): **+0.2 pp** | 0.088: ratio 1.00 | 48 / 136 = 35.3%: +2.2 pp (23 hosts) | **no** (i) |
| A1b `author_exposure` | 443 (89.0%): **+2.0 pp** | 0.092: ratio 1.05 | 51 / 136 = 37.5%: +4.4 pp (23 hosts) | **no** (i) |

[M] Final after the 2-job retry (CVZ timeouts, 7,200-s deadline, both complete): the numbers above are
unchanged.

## 2. What ran [M]

* **R-A:** 3,799 pre-gate candidates.
  * Injection searches with expected SNR >= 20: 2,747.
  * FA hosts: 673.
  * DEV hosts: 379.
* **Re-run scope** (monotonicity, RULES_K2 3.2): 1,035 K1 A-FAIL candidates with at least one depth-failing
  ephemeris, plus 20 K1 A-PASS candidates for the determinism check.
* **Wall:** 2.2 h at 16 workers, plus a 0.8-h retry. 1,053 completed first time; 2 timed out at 1,800 s on CVZ
  hosts and completed on the 7,200-s retry. 0 unknowns.
* **Determinism [M]:** every completed re-run reproduces its K1 decision and its per-ephemeris `p_const` exactly
  (1,055 / 1,055). The 20 K1 PASS candidates pass.
* **New A passers** (either scope): 24.
  * All 24 went to S; 15 pass S under `bound_alias` (1 on an FA host, which stops at S as in K1).
  * B ran on the other 14: 13 PASS, 1 FAIL.

## 3. Why A1 rescues so little [M/I]

Of the depth-failing ephemerides among the re-runs:

* about half have all their kept events in ONE product family, and still fail. For those, A1a is the K1 test.
* where both families are present, the within-family chi-square usually still fails (p < 1e-3).

[I] So the high-SNR depth scatter that K1's Stage A rejects is mostly sector-to-sector scatter within a
pipeline: apertures and crowding corrections change by sector. It is not a TESS-SPOC vs QLP offset.

* Splitting further by exposure class (A1b) passes the within-family test more often.
* But the family means then often differ by more than 25% and more than 3 sigma.
* A1b's gain (+9 injections) is real but below the registered +3 pp bar.

K1 attributed 5 of its 26 G1 losses to this criterion. A fix would need per-sector depth normalisation (a dilution
or aperture model) or a relative tolerance on the event scatter, not a product-family split.
