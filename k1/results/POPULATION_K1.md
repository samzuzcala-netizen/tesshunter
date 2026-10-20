# POPULATION_K1 — Part A: the K and early-M target pool and the drawn lists

Tags: **[M]** measured in this run; **[R]** from the review (`NEXT_POPULATION_REVIEW_2026-10-07.md`);
**[A]** registered before measurement (`k1/protocol/RULES_K1.md`); **[I]** interpretation.
Machine-readable: `k1/results/population_report.json`, `population_k1.json`, `population_count_decomposition.json`,
`rank_reproduction.json`.  Builder: `scripts/build_k1_population.py` (stage caches in `D:\tesshunter_k1\pop`).
Nothing here is a detection.

## A1-A2. Query and coverage [M]

* TIC all-sky query, Teff 3500-5400 K, Tmag 9.5-13.6, R 0.35-1.15 R☉, objType STAR, in 5° declination
  strips split until each query returned < 50,000 rows: **1,295,195 unique stars** in 46 accepted strips
  (16 strips split once; none needed a second split).  Two strip queries hung on MAST (24 min, then 7 min);
  each is now bounded at 420 s in a daemon thread and retried.  Strip CSVs keep the exact 19-digit Gaia
  DR2 ids (a first concatenation parsed them as float64; caught when DR3 RUWE matched only ~35% of ids;
  rebuilt from the cached strips, lists unchanged: same stars, order and E_new).
* Product availability: the cached QLP / TESS-SPOC target lists (sectors 1-105; TESS-SPOC lists exist only
  through sector 85) and the MIT 2-minute lists (1-110 after the Part 0 refresh added 106-110).
* Sector coverage for the ranking's novelty term: the vendored tess-point, chunks of 2,000 stars.

## A3. Cuts, in the registered order [M]

| step | cut | all | class K | class eM |
|---|---|---:|---:|---:|
| 0 | query envelope (all sky) | 1,295,195 | — | — |
| 1 | class (K: 3900-5300 K, 0.55-1.0 R☉; eM: 3600-3899 K, 0.40-0.70 R☉), log g ≥ 4.3 where given, not GIANT | 991,596 | 904,697 | 86,899 |
| 2 | Tmag 10.0-13.5 | 878,299 | 802,431 | 75,868 |
| 3 | \|b\| ≥ 20°, > 10° from the LMC, > 4° from the SMC | 528,669 | 481,257 | 47,412 |
| 4 | TIC `contratio` measured and ≤ 0.10 | 267,071 | 227,876 | 39,195 |
| 5 | Gaia main-sequence check (change 2) | 251,566 | 215,867 | 35,699 |
| 6 | K1 hard stop: not REJECT (change 9) | 250,597 | 215,029 | 35,568 |
| 7 | FFI rule: n_2min_in_search < n_usable / 2 | 225,765 | 194,804 | 30,961 |
| 8 | n_usable ≥ 5 | **70,059** | **60,915** | **9,144** |

Sanity ranges [R]: class K after step 8 expected ~83,000 (STOP-A outside 40,000-170,000); eM expected
10,000-30,000 (STOP-A outside 5,000-60,000).  **Both inside: STOP-A does not fire** [M].

Step 5 reasons among class K after step 4 [M]: no TIC parallax 11,372; no Gaia photometry 347; overluminous
(> 1 mag above the Pecaut & Mamajek dwarf sequence, evolved) 226; parallax/error < 5: 54; colour outside
BP-RP 0.85-2.50: 8; underluminous (> 1 mag below): 2.  Step 6 rejects among class K: CTOI 314 (incl. RAVEN),
TOI 208, TOI+NASA PS 89, TESS EB 63, NASA PS 45, TESS Ten Thousand 43, other combinations the rest.

**Why class K is 60,915 and not ~83,000** [M, `population_count_decomposition.json`]: on the same stars
(steps 1-6 passed, strict-minority 2-min rule) the count with ≥ 5 list sectors in **1-105** is 80,116 — the
review's basis (it counted ≥ 5 sectors in 1-105).  The registered usable-sector rule excludes sectors
99-105 (QLP timing error / not released): 61,592; and QLP 80/83/85 without TESS-SPOC: 60,915.  The Gaia
check removes ~3,400 more K stars (64,358 without it).  The review's strictly-FFI-only rule (no 2-min
sector at all) would give 54,656.  The remaining difference to 83,000 is the review's 1/64 tile model
(×63.7 scaling) [I].

## A4-A5. Ranking (change 7) [M]

E_new per star = Σ cells k(type, Rp class) × rate × P_geo × P_user(SNR(n_usable), N_tr(n_usable)) × (1 − P_inc),
KM2020 for class K (types K_late / K_early), DC15 for class eM (type M_early), the review's TOI-calibrated
radius-class factors, the Oct 3-4 completeness curve (max 0.65, SNR50 12.5, width 2.5, zero below 7.1,
≥ 3 transits), the repo noise model × measured Tmag ratio, and the review's SPOC/QLP novelty term
(`k1/protocol/rank_k1.py`, `yieldlib_k1.py` = the review's `yieldlib.py` byte for byte).  The survey ranking
uses periods 0.5-50 d (the K1 search range); the comparisons with the review use 0.5-30 d, as the review did.

**Reproduction check (A5)** on the review's own tile inputs (`k1/work/reproduce_review_yield.py`):
top-10,000 K, archival S1-98 = **8.95 vs 9.0** (ratio 0.994, within 10%); S56-98 policy 5.03 vs 5.0;
eM top-3,000 TOI-calibrated 2.38 vs 2.4, published 8.06 vs 8.1.

**On the K1 population** (model expectations, not detections):

| quantity | K1 [M] | review [R] | ratio |
|---|---:|---:|---:|
| top-10,000 K, usable sectors, P 0.5-30 d | 8.33 | 9.0 | 0.93 |
| top-10,000 K, sectors 56-98 only, P 0.5-30 d | 4.57 | 5.0 | 0.91 |
| top-3,000 eM, usable, TOI-calibrated (P 0.5-50 d) | 2.31 | 2.4 | 0.96 |
| top-3,000 eM, usable, published DC15 (P 0.5-50 d) | 7.89 | 8.1 | 0.97 |
| top-10,000 K, usable, P 0.5-50 d (the ranking basis) | 9.63 | — | — |
| top-7,000 K, usable, P 0.5-50 d (the survey slice) | 7.15 | — | — |

The top-10,000 E_new is within a factor 2 of the review (0.93): **STOP-A does not fire**.  The ~7% shortfall
is the usable-sector rule (sectors 99-105 and QLP 80/83/85 excluded, versus the review's archival tess-point
sectors 1-98 minus 80/83/85) and the Gaia check [I].  Composition of the top-10,000 K (P 0.5-50 d) [M]:
0.55 at 0.5-1.5 R⊕, 4.27 at 1.5-2.5, 3.05 at 2.5-4, 1.75 above 4 R⊕ (review: 0.7 / 4.2 / 2.6 / 1.8).
The model over-predicted the M-dwarf result by 1.5-3× [R]; treat these as upper-middle expectations.

## A6. Lists (drawn now; frozen at Part G)

* `k1/survey/targets_k1.csv`: top 7,000 K + top 3,000 eM by E_new (column `slice` = K / eM_slice),
  sha256 `5768d330...59ae8`.  **Never downloaded, searched or inspected in K1** (STOP-E guard in every worker).
* `k1/survey/reserve_k1.csv`: K ranks 7,001-17,000 + eM ranks 3,001-8,000, sha256 `0c20e1a8...a9536`.

## A7. Distributions [M]

| set | Tmag median (5-95%) | Teff median (5-95%) | n_usable median (5-95%) | contratio median (95%) | n_usable at 1800/600/200 s (medians) |
|---|---|---|---|---|---|
| all class K (60,915) | 12.51 (11.13-12.98) | 4863 (3988-5268) | 6 (5-38) | 0.011 (0.074) | 2 / 2 / 3 |
| all class eM (9,144) | 13.07 (11.96-13.47) | 3760 (3618-3886) | 6 (5-35) | 0.006 (0.066) | 2 / 2 / 3 |
| survey K (7,000) | 11.97 (10.80-12.82) | 4621 (3999-5254) | 19 (5-43) | 0.017 (0.076) | 6 / 5 / 8 |
| survey eM (3,000) | 12.56 (11.48-13.38) | 3755 (3617-3886) | 9 (5-40) | 0.010 (0.070) | 3 / 3 / 4 |

The ranking favours well-observed, brighter, cooler K dwarfs (median 19 usable sectors in the survey K slice,
of which 8 at 200 s).

Flags (recorded, never cuts) [M]: Gaia `possible_binary` (0.5-1.0 mag over the sequence) 3,212 of 70,059
(556 in the survey list); hard-stop FLAG 366 (survey 48), of which SPOC TCE 363 (survey 48; their TCE periods
are in the sidecar `D:\tesshunter_k1\pop\tce_sidecar_pool.csv` and act as a period veto) and a known object
within 21" 8 (survey 0); a strict minority of 2-min sectors 7,135 (survey 1,358; K1 uses their FFI products).
Gaia DR3 `ruwe_gt_1p4`: see the addendum below (queried for the survey and reserve lists).

### Addendum: Gaia DR3 RUWE (flag `ruwe_gt_1p4`, never a cut) [M]
`k1/protocol/gaia_ruwe_k1.py` (DR2 -> DR3 via `gaiadr3.dr2_neighbourhood`, ESA TAP, bounded calls;
receipt `k1/manifests/gaia_ruwe_receipt.json`, table `D:\tesshunter_k1\pop\gaia_ruwe.csv`): 24,999 of the
25,000 survey + reserve stars have a DR3 RUWE; **4,577 exceed 1.4**, of which **1,872 are in the survey list**
(1,400 K, 472 eM; 18.7%).  This is higher than the ~10% often quoted for field dwarfs [I: unexplained here;
unresolved companions push stars over the main-sequence colour/magnitude and the TIC radius, and brighter
binaries are over-represented at fixed Tmag].  The flag travels with each star into Stage B / D (Gaia flags
F2) and is a candidate-level caution, not a selection change.
