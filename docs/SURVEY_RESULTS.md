# Survey results: `targets_v1.csv` through the P3 pipeline (prompt 4)

Generated 2026-09-03 10:22 UTC by `scripts/write_survey_results.py` from `data/survey/p4/`. Ranking rules: `docs/RANKING_SCORE.md` (frozen before the run, commit 97d1d8b). The pipeline finds candidates; nothing in this document is a detection, and nothing has been submitted anywhere.

## 1. What ran

* Population: 819 stars of `data/survey/targets_v1.csv` (stratum 3, Tmag 10.5-13.5 dwarfs, QLP and TESS-SPOC light curves, hard-stop clean at build time).
* Search: preset `survey_v1` (chunked plan, 1-100 d, 30-minute bins, 600 s budget per star), the P3 characterisation and vetting stack inside every sub-search, whole-stitch re-measurement of every candidate.
* Job status: ok 819 of 819 results; 0 target(s) without a result file.
* Retried jobs: 0; not-ok after retry: 0 (listed in section 7).
* Wall clock per star (whole worker): median 54 s, 90th percentile 155 s, max 317 s; search stage median 54 s; characterisation (fits) median 6.4 s; total CPU 17.8 h.
* Units (sectors) per star: median 12, max 45; products used by author: QLP 5053, SPOC 1957, TESS-SPOC 9607; stars by author set: qlp 73, qlp;spoc 26, qlp;spoc;tess-spoc 191, qlp;tess-spoc 349, spoc 4, spoc;tess-spoc 112, tess-spoc 64.
* Provenance events recorded by the download layer: 300 (offline_cache_mode 200; `offline_cache_mode` is the P2 rebuild of the 300 completeness-sample stars from the local FITS cache, not a download fallback); searches that hit the time budget: 3 (TIC 141827391, 167247580, 167307093).
* SPOC 2-minute products, where a star has them, are binned to 30 minutes and take precedence over TESS-SPOC and QLP in the same sector (the P2 ingestion rule); the counts above are products, not sectors.
* Prefetch (download + stitch, 8 workers): {'ok': 819}; download per new star median 40 s, p90 89 s, max 150 s (n = 519).

## 2. Signals and gates

| gate | rule (`docs/RANKING_SCORE.md`) | rows after | stars |
|---|---|---:|---:|
| G0 | job finished ok | 819 | 819 |
| G1 | accepted candidates | 6378 | 814 |
| G2 | stitch SNR >= 9 and epoch-consistent | 910 | |
| G3 | >= 3 transits on the stitch | 515 | |
| G4 | verdict not likely-FP | 430 | |
| G5 | fit converged and sees the dip (>= 3 sigma) | 411 | 261 |
| G6 | one row per signal (harmonics merged) | 405 | |
| G7 | fresh hard-stop cross-match (REJECT removed) | 405 | 261 |

Cross-match at survivor time: 405 candidate rows checked, 0 REJECT (known object under the same TIC), 0 FLAG (known object within 21 arcsec under another TIC; kept, noted). Catalog stamp: `ctoi=2026-09-03:f6964541;nasa_ps=2026-09-03:85f3c196;nasa_pscomppars=2026-09-03:4843e49c;spoc_tce=2026-09-03:e580dde7;tess_eb=2026-09-03:43555226;toi=2026-09-03:4704bb7c` (rows per source: ctoi 5,137, nasa_ps 39,278, nasa_pscomppars 6,057, spoc_tce 342,918, tess_eb 4,584, toi 8,148).

Of the 6378 accepted candidates, 851 have only two transits on the stitch. Candidates failing a gate, by first failed gate: G2 5468, G3 395, G4 85, G5 19.

Light-curve verdicts of all accepted candidates: promising planet candidate 4070, ambiguous / manual vetting required 1846, likely false positive 462.

## 3. How many of these are expected to be noise

From `docs/COMPLETENESS.md` (the same search on 300 population stars with no injection, P2, before the P3 fit-based flags existed). The P2 verdict column was the P2 vetting stack; the measured column applies the same cut with the P3 verdict, so the two differ by exactly the P3 changes (fit-based flags, secondary bound, alias re-test):

| P2 threshold | per star (300 stars) | expected in 819 stars | measured here |
|---|---:|---:|---:|
| accepted candidates, any SNR | 7.92 | 6,489 | 6378 |
| stitch SNR >= 9, epoch-consistent, verdict not FP (G2 and G4) | 1.07 | 876 | 787 |
| ... and >= 3 transits in the chunk that found it (the memo's count) | 0.38 | 311 | 288 |
| ... and >= 3 transits on the whole stitch (the G3 quantity) | 0.61 | 500 | 430 |

Read: the P2 false-alarm run predicts that of order 300 to 500 candidates in this population pass G2-G4 from systematics and un-catalogued variability alone, and the measured counts sit inside or below that range. The P2 sample is 300 of these same 819 stars, so this is not an independent prediction: it says the rest of the population behaves like the sample. Every survivor below should therefore be read against that background: the ranking orders them, it does not make them real.

Expected number of REAL new signals in this population (`scripts/p4_expected_yield.py`, the P1 occurrence and noise model with the P2 measured recovery curve in place of the adopted efficiencies):

| prior completeness | P1 model (efficiencies 0.8/0.7/0.4) | measured curve |
|---|---:|---:|
| low | 7.13 | 3.32 |
| mid | 5.00 | 2.19 |
| high | 2.88 | 1.12 |

So at mid priors about 2.2 real new signals are expected among several hundred noise survivors; a null result for the top 10 is the likelier outcome and would be consistent with the model. Caveat: P1 SNR is a photon-plus-floor model scaled to QLP scatter; the P2 axis is the matched-filter SNR on the pipeline's own detrended 30-minute-binned data. Same symbol, different quantity; P2 judged the matched-filter one the more optimistic of the two.

## 4. Ranked survivors (top 30 of 405)

Score = S_snr + S_ntr + S_fpp + S_rho (each 0-1; `docs/RANKING_SCORE.md`). `stitch_snr` and transits are the whole-stitch re-measurement. Depth, Rp/R*, Rp, a/R* and b are the survey's limb-darkened fit on the chunk that found the signal (the packets refit on the whole stitch). FPP / NFPP are TRICERATOPS on the top 30 only (S_fpp = 0.5 where not computed). `final verdict` includes the centroid, contamination and NFPP checks. Full table with every column: `data/survey/p4/survivors.csv`.

| rank | TIC | P (d) | stitch SNR | transits | depth (ppt) | Rp/R* | Rp (Re) | b | rho ratio | dchi2 eff | FPP | NFPP | FPP uniform | centroid sigma | S_snr | S_ntr | S_fpp | S_rho | score | LC verdict | final verdict | xmatch | Tmag | units |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---|---|---|---:|---:|
| 1 | 233211748 | 65.0083 | 71.8 | 15 | 1.995 | 0.056 | 5.76 | 0.96 | 0.00 | 2.3 | 0.000 | 0.000 | no | 27.2 | 1.00 | 1.00 | 1.00 | 1.00 | 4.00 | promising planet candidate | ambiguous / manual vetting required | CLEAN | 11.2 | 38 |
| 2 | 212261364 | 8.9538 | 120.2 | 10 | 7.376 | 0.079 | 4.28 | 0.00 | 1.52 | -0.0 | 0.008 | 0.005 | no | 1.5 | 1.00 | 1.00 | 0.99 | 1.00 | 3.99 | promising planet candidate | promising planet candidate | CLEAN | 11.9 | 5 |
| 3 | 160619045 | 91.6642 | 44.4 | 11 | 4.256 | 0.281 | 24.14 | 1.20 | 0.01 | 0.7 | 0.000 | 0.000 | no | 13.9 | 0.93 | 1.00 | 1.00 | 1.00 | 3.93 | promising planet candidate | ambiguous / manual vetting required | CLEAN | 11.3 | 31 |
| 4 | 334678787 | 46.2063 | 26.2 | 13 | 6.491 | 0.081 | 6.99 | 0.76 | 0.18 | 0.2 | 0.000 | 0.000 | no | 1.2 | 0.62 | 1.00 | 1.00 | 1.00 | 3.62 | promising planet candidate | promising planet candidate | CLEAN | 10.7 | 34 |
| 5 | 290350156 | 13.2030 | 26.8 | 9 | 10.577 | 0.096 | 3.42 | 0.00 | 0.59 | 0.0 | 0.012 | 0.008 | no | 6.2 | 0.64 | 0.86 | 0.99 | 1.00 | 3.48 | promising planet candidate | ambiguous / manual vetting required | CLEAN | 12.2 | 6 |
| 6 | 21124154 | 89.2278 | 24.2 | 10 | 0.823 | 0.027 | 4.21 | 0.13 | 0.20 | 0.6 | 0.143 | 0.143 | no | 17.9 | 0.58 | 1.00 | 0.86 | 1.00 | 3.43 | promising planet candidate | likely false positive | CLEAN | 11.6 | 33 |
| 7 | 356976754 | 11.7890 | 33.6 | 67 | 3.970 | 0.275 | 29.70 | 1.20 | 0.37 | -0.0 | 0.458 | 0.000 | no | 4.0 | 0.77 | 1.00 | 0.54 | 1.00 | 3.31 | ambiguous / manual vetting required | likely false positive | CLEAN | 11.6 | 38 |
| 8 | 246937997 | 2.4571 | 22.8 | 53 | 12.414 | 0.255 | 22.93 | 1.09 | 0.01 | 7.6 | 0.249 | 0.126 | no | 6.5 | 0.54 | 1.00 | 0.75 | 1.00 | 3.29 | promising planet candidate | likely false positive | CLEAN | 11.7 | 6 |
| 9 | 167304394 | 22.7802 | 659.9 | 32 | 59.030 | 0.459 | 41.97 | 1.10 | 1.67 | 0.0 | 0.833 | 0.167 | yes | 16.7 | 1.00 | 1.00 | 0.17 | 1.00 | 3.17 | ambiguous / manual vetting required | likely false positive | CLEAN | 11.5 | 34 |
| 10 | 233200485 | 70.6808 | 124.1 | 13 | 1.548 | 0.038 | 4.01 | 0.68 | 2.75 | -1.0 | 0.900 | 0.500 | yes | 6.9 | 1.00 | 1.00 | 0.10 | 1.00 | 3.10 | promising planet candidate | likely false positive | CLEAN | 11.9 | 38 |
| 11 | 141756992 | 79.2531 | 56.8 | 13 | 2.345 | 0.258 | 15.90 | 1.20 | 0.00 | 4.9 | 0.909 | 0.545 | yes | 11.2 | 1.00 | 1.00 | 0.09 | 1.00 | 3.09 | promising planet candidate | likely false positive | CLEAN | 10.9 | 45 |
| 12 | 141756992 | 78.2667 | 55.9 | 13 | 7.405 | 0.079 | 4.86 | 0.00 | 0.34 | 0.0 | 0.909 | 0.545 | yes | 13.0 | 1.00 | 1.00 | 0.09 | 1.00 | 3.09 | ambiguous / manual vetting required | likely false positive | CLEAN | 10.9 | 45 |
| 13 | 219087933 | 10.5395 | 94.9 | 91 | 15.893 | 0.368 | 39.33 | 1.20 | 0.24 | 3.5 | 0.966 | 0.000 | no | 4.9 | 1.00 | 1.00 | 0.03 | 1.00 | 3.03 | ambiguous / manual vetting required | likely false positive | CLEAN | 11.8 | 41 |
| 14 | 284191194 | 73.7185 | 36.2 | 10 | 2.690 | 0.048 | 5.32 | 0.05 | 1.88 | -0.0 | 0.800 | 0.000 | yes | 1.4 | 0.81 | 1.00 | 0.20 | 1.00 | 3.01 | promising planet candidate | promising planet candidate | CLEAN | 11.1 | 30 |
| 15 | 366118831 | 28.1207 | 35.9 | 15 | 126.035 | 0.508 | 26.89 | 0.94 | 1.34 | 0.0 | 0.800 | 0.000 | yes | 5.8 | 0.81 | 1.00 | 0.20 | 1.00 | 3.01 | ambiguous / manual vetting required | likely false positive | CLEAN | 13.3 | 25 |
| 16 | 233007823 | 17.4683 | 59.1 | 47 | 3.417 | 0.270 | 31.07 | 1.20 | 0.13 | 6.9 | 1.000 | 1.000 | no | 5.8 | 1.00 | 1.00 | 0.00 | 1.00 | 3.00 | promising planet candidate | likely false positive | CLEAN | 11.6 | 39 |
| 17 | 382302559 | 83.8132 | 56.8 | 11 | 1.852 | 0.040 | 3.86 | 0.30 | 0.07 | 6.2 | 1.000 | 0.000 | no | 8.2 | 1.00 | 1.00 | 0.00 | 1.00 | 3.00 | promising planet candidate | ambiguous / manual vetting required | CLEAN | 12.1 | 44 |
| 18 | 290470328 | 7.4070 | 25.3 | 24 | 6.819 | 0.076 | 4.55 | 0.32 | 0.06 | 1.9 | 0.623 | 0.618 | no | 21.9 | 0.60 | 1.00 | 0.38 | 1.00 | 2.98 | promising planet candidate | likely false positive | CLEAN | 12.7 | 7 |
| 19 | 200658220 | 26.0912 | 41.9 | 7 | 78.776 | 0.258 | 13.47 | 0.00 | 2.40 | 0.0 | 0.000 | 0.000 | no | 3.7 | 0.90 | 0.57 | 0.50 | 1.00 | 2.97 | promising planet candidate | promising planet candidate | CLEAN | 13.1 | 10 |
| 20 | 201230005 | 8.0948 | 19.9 | 20 | 32.719 | 0.169 | 6.75 | 0.00 | 0.18 | -0.2 |  |  |  |  | 0.46 | 1.00 | 0.50 | 1.00 | 2.96 | promising planet candidate |  | CLEAN | 13.2 | 8 |
| 21 | 381979202 | 90.3809 | 19.1 | 11 | 6.336 | 0.074 | 7.92 | 0.00 | 0.21 | 0.6 |  |  |  |  | 0.44 | 1.00 | 0.50 | 1.00 | 2.94 | promising planet candidate |  | CLEAN | 11.6 | 41 |
| 22 | 357101526 | 63.5739 | 24.1 | 9 | 21.515 | 0.142 | 7.43 | 0.65 | 0.31 | 0.0 |  |  |  |  | 0.58 | 0.86 | 0.50 | 1.00 | 2.93 | promising planet candidate |  | CLEAN | 13.4 | 33 |
| 23 | 420899972 | 95.4973 | 89.7 | 6 | 5.526 | 0.288 | 31.33 | 1.20 | 0.00 | 1.3 |  |  |  |  | 1.00 | 0.43 | 0.50 | 1.00 | 2.93 | ambiguous / manual vetting required |  | CLEAN | 11.2 | 29 |
| 24 | 384888826 | 14.1538 | 57.9 | 6 | 2.386 | 0.053 | 4.07 | 0.89 | 0.00 | 1.6 |  |  |  |  | 1.00 | 0.43 | 0.50 | 1.00 | 2.93 | ambiguous / manual vetting required |  | CLEAN | 11.0 | 6 |
| 25 | 362104766 | 99.0881 | 53.6 | 6 | 6.333 | 0.085 | 11.46 | 0.87 | 0.91 | -0.0 |  |  |  |  | 1.00 | 0.43 | 0.50 | 1.00 | 2.93 | ambiguous / manual vetting required |  | CLEAN | 10.6 | 40 |
| 26 | 350297651 | 93.5468 | 18.7 | 13 | 2.961 | 0.052 | 6.95 | 0.52 | 65.24 | 0.7 |  |  |  |  | 0.43 | 1.00 | 0.50 | 1.00 | 2.93 | promising planet candidate |  | CLEAN | 11.2 | 45 |
| 27 | 38763320 | 74.8826 | 18.5 | 13 | 2.756 | 0.050 | 5.57 | 0.62 | 0.04 | 0.5 |  |  |  |  | 0.42 | 1.00 | 0.50 | 1.00 | 2.92 | promising planet candidate |  | CLEAN | 11.6 | 44 |
| 28 | 284190863 | 18.7036 | 18.3 | 25 | 1.215 | 0.032 | 2.58 | 0.26 | 1.07 | -0.0 |  |  |  |  | 0.41 | 1.00 | 0.50 | 1.00 | 2.91 | promising planet candidate |  | CLEAN | 11.1 | 24 |
| 29 | 38763320 | 55.5275 | 18.2 | 16 | 2.593 | 0.048 | 5.28 | 0.48 | 0.03 | 0.4 |  |  |  |  | 0.41 | 1.00 | 0.50 | 1.00 | 2.91 | ambiguous / manual vetting required |  | CLEAN | 11.6 | 44 |
| 30 | 350297651 | 65.5546 | 18.1 | 16 | 2.184 | 0.253 | 34.11 | 1.20 | 0.00 | 3.9 |  |  |  |  | 0.41 | 1.00 | 0.50 | 1.00 | 2.91 | ambiguous / manual vetting required |  | CLEAN | 11.2 | 45 |

## 5. The packet gate and what the expensive steps changed

* 1 candidate(s) OUTSIDE the frozen pre-FPP top 30 also received the expensive steps (a rerun after the first FPP merge selected from the post-FPP order); per the frozen rule their FPP is reported here but does not enter their score: TIC 200658220 at 26.091 d (final rank 19, FPP 0.000, NFPP 0.000, final verdict promising planet candidate).
* Expensive steps completed on 30 candidates: TRICERATOPS FPP <= 0.5 on 8, FPP > 0.5 on 22 (packet built but marked blocked, P3 rule), no FPP value on 0.
* Light-curve verdicts of those candidates: promising planet candidate 19, ambiguous / manual vetting required 11.
* Final verdicts after centroid, contamination and NFPP: likely false positive 19, ambiguous / manual vetting required 7, promising planet candidate 4.
* TRICERATOPS returned a UNIFORM scenario posterior (every scenario at 1/n, blank names) on 7 candidate(s): TIC 167304394 at 22.780 d (FPP 0.83), TIC 233200485 at 70.681 d (FPP 0.90), TIC 141756992 at 79.253 d (FPP 0.91), TIC 141756992 at 78.267 d (FPP 0.91), TIC 284191194 at 73.719 d (FPP 0.80), TIC 366118831 at 28.121 d (FPP 0.80), TIC 420900133 at 56.618 d (FPP 0.86). Those FPP values are an artefact of the input (every likelihood zero or NaN), not a measurement; the frozen score used them as returned and this column says so.
* Centroid flagged (P0 module, all sectors with pixel data): 23 of 30 with a measurement. P3 measured that this module's significance does not separate known planets from real blends on bright stars; it is reported, not decisive.
* Fresh cross-match on all 405 ranked survivors: CLEAN 405.

## 6. Packets and case files

Packets: `docs/packets/survey_v1/tic<TIC>_P<period>/` (packet.md, summary.png, ctoi_fields.json, fit.json, fpp.json, vetting.json, neighbours.csv, result.json) for every candidate in section 5. Case files for the top 10: `docs/case_files/`. Nothing is submitted by the pipeline; the human reads the audit (prompt 5) first.

## 7. Targets that did not complete

None: every target produced a result with status `ok`.

No download fallback event was recorded on any target (the only provenance events are the `offline_cache_mode` notes of the P2 rebuild, section 1).
