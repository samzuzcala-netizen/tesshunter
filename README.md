# tesshunter

**A search for small transiting planets around M and K dwarfs in NASA TESS full-frame-image photometry, with a
pre-registered, calibrated vetting funnel and deep archival follow-up of the survivors.**

[Project page](https://samzuzcala-netizen.github.io/tesshunter/) · [Candidates](CANDIDATES.md) · [Reports](reports/) ·
[Pipeline guide](docs/PIPELINE_GUIDE.md)

> Every signal here is a **planet candidate**, not a confirmed or validated planet. Candidates were first identified
> by this project on the dates listed in [CANDIDATES.md](CANDIDATES.md); this repository is their first public record.

## At a glance

| | |
|---|---|
| Light-curve searches | **≈10,800 star searches** across seven survey runs (P4 819, P8 2,000, P12 2,788, October 2026 sweeps 300 + 1,998 + 931, S1 batch 1 2,000) |
| Calibration | Thousands of injection–recovery trials (e.g. 2,100 in P10, 1,687 in P12) and a retention test on 436 real TESS planet-candidate hosts |
| Vetting funnel | Pre-gate → Stage A (per-event consistency) → S (aliases, stellar signals) → B → C (blind 0.5–110 d re-search) → D (dossier: fit, Gaia scene, centroids, TRICERATOPS false-positive probability) |
| Output | **6 new planet candidates** from S1 batch 1 (not TOIs or CTOIs as of 2026-10-19), plus earlier leads such as an ultra-short-period (0.71 d) candidate around an M dwarf |
| Follow-up | Three candidates taken through a reproducible archival follow-up: 11+ independent re-reductions, injection-calibrated difference-image localisation, ZTF photometry, Gaia RV mass limits, MCMC radii, a replay of the discovery search, and a colour–magnitude binarity test |
| Engineering | Python package (~20,000 lines), **624 automated tests**, frozen protocols with hashed input/output manifests, CPU budgets and stop rules, resumable multi-process orchestration |

## The candidates

The six new candidates from S1 batch 1 (period P, mid-transit epoch T0 in BJD_TDB, depth, size):

| TIC | P (d) | T0 (BJD_TDB) | Depth (ppm) | ~Rp (R⊕) | Pipeline verdict | Follow-up status |
|---|---|---|---|---|---|---|
| 382098683 | 4.351685 | 2458329.13902 | 416 | 1.3 | SUBMIT | Archival constraints report |
| 188830138 | 1.181024 | 2458764.89089 | 347 | 1.4 | SUBMIT | Archival constraints report |
| 116046773 | 5.650272 | 2458987.88262 | 866 | 2.3 | SUBMIT | Deep vetting + continuation |
| 201247574 | 16.560576 | 2458333.60991 | 1,559 | 2.4 | HOLD | Archival constraints report |
| 262843927 | 24.108929 | 2458332.78771 | 1,245 | 2.0 | HOLD | FU3: top tier; likely unresolved companion |
| 270573718 | 41.383701 | 2458334.90375 | 2,058 | 2.1 | HOLD | FU3: second tier; timing offsets unresolved |

Full table with uncertainties, discovery dates and the other leads: [CANDIDATES.md](CANDIDATES.md) ·
[candidates.csv](candidates.csv).

## How it works

1. **Targets.** M and K dwarfs from the TESS Input Catalog, ranked by expected yield, cross-matched against Gaia DR3
   and against every existing TOI/CTOI.
2. **Light curves.** TESS-SPOC and QLP full-frame-image products (and SPOC 2-min where present), stitched per
   cadence family, detrended, quality-masked.
3. **Search.** Box/transit least-squares over 0.5–50 d with a fixed CPU budget per star; candidates must show at
   least three epoch-consistent transits at stitched S/N ≥ 7.1.
4. **Vetting funnel.** Each stage has frozen, written rules (`docs/RULES.md`, `p12/`, `k1/`, `k2/`). Stage A refits
   every individual event; S tests aliases and stellar variability; C re-searches blind; D assembles a dossier
   (physical fit, odd/even and secondary checks, Gaia scene, pixel centroids, TRICERATOPS).
5. **Calibration.** Every configuration change is judged by injection–recovery on real light curves and by
   retention of known planets, against pre-declared decision rules, including when the answer was "no gain".
6. **Follow-up.** [followup/fu3_three_candidates](followup/fu3_three_candidates) is a complete, reproducible
   archival follow-up (protocol frozen before new data were examined, amendments recorded, 13 unit tests, a
   PDF report).

## Repository map

| Path | Contents |
|---|---|
| `src/tesshunter/` | The pipeline package |
| `tests/` | 624 tests (`pytest tests`) |
| `scripts/` | Command-line drivers for surveys, vetting and reports |
| `p9/` … `p12/`, `k1/`, `k2/`, `s1/` | Research phases: protocols, decision records and code (run outputs omitted) |
| `docs/` | Rules, audits, completeness studies, case files; `docs/history/` holds phase handoffs |
| `followup/` | Candidate follow-ups, including the FU3 toolkit and report |
| `reports/` | PDF reports on the batch-1 candidates |

Large run outputs (light curves, per-star search results, multi-GB manifests) are not included.

## Running it

```bash
pip install -e ".[dev]"
pytest tests
```

The pipeline downloads public TESS data from MAST. Paths in some research scripts point at the author's machine
and data drives; they document what was run rather than being turnkey.

## Credits and licence

By Samuel Zachary Edwards. Uses public data from NASA's TESS mission (MAST), ESA Gaia, ZTF and other archives cited in the
reports. TIC 193718989 was also detected by this
survey but was first posted publicly by [eumemic/exoplanets](https://github.com/eumemic/exoplanets) on 2026-10-08,
so it is not claimed here.

Code: MIT licence ([LICENSE](LICENSE)). Candidate lists, reports and figures: CC BY 4.0. If you use these
candidates, please cite this repository ([CITATION.cff](CITATION.cff)).
