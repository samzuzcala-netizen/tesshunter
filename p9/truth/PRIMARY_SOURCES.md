# External label provenance and limitations

The frozen NASA Planetary Systems default rows supply the positive catalogue
labels and parameter references. Transit flag=1 and controversy flag=0 were
required. Statistical validation is a probabilistic external label, not infallible
ground truth. The execution side never receives these references or labels.
The original reference HTML is retained per signal in `final_truth.csv`.
The [NASA PS column documentation](https://exoplanetarchive.ipac.caltech.edu/docs/API_PS_columns.html)
explains the default solution and timing/parameter fields. A default row is not the
same as mixing every available best measurement from PSCompPars. Explicit ExoFOP
fallbacks for missing duration/epoch/depth are recorded by field.

Primary discovery/validation publications were checked on 2026-09-08. The catalogue
selected the controls before this supplementary bibliography audit. This audit did
not replace controls or change any ephemeris. The sources below support the nature
of the external labels; their methods do not constitute a new P9 validation.

| Controls | Primary source | External evidence and relevant limitation |
|---|---|---|
| Kepler-504, 607, 622, 629, 922, 994, 995, 1076, 1328 b | [Morton et al. 2016](https://arxiv.org/abs/1605.02825) | Statistical validation using vespa; not every confirmed catalogue entry has an RV mass. |
| Kepler-195 b, 196 b, 262 b/c | [Rowe et al. 2014](https://arxiv.org/abs/1402.6534) | Multiplicity-based statistical validation; unresolved dilution can affect derived radii. |
| Kepler-560 b | [NASA reference/solution history](https://exoplanetarchive.ipac.caltech.edu/overview/Kepler-560), [Morton et al. 2016](https://arxiv.org/abs/1605.02825) | NASA lists Mann et al. 2017 as discovery reference and also a Morton validation solution. Stellar multiplicity and TTV notes matter. The Mann ADS abstract was unavailable to the web reader; no claim of a new full-paper revalidation. |
| TOI-4860 b | [Triaud et al. 2023](https://arxiv.org/abs/2308.02253), [Almenara et al. 2023](https://arxiv.org/abs/2308.01454) | Multicolour transit observations and independent RV evidence. Published mass estimates differ; P9 does not feed either planet mass into execution. |
| TOI-6002 b | [Ghachoui et al. 2024](https://arxiv.org/abs/2408.00709) | TESS and ground-based validation of small M-dwarf planets. |
| TOI-5716 b | [Gomez Barrientos et al. 2026](https://arxiv.org/abs/2512.11971) | Statistical validation using TESS, multicolour photometry, imaging and spectroscopy; announced in 2025, journal publication in 2026. |
| LP 791-18 b/c | [Crossfield et al. 2019](https://arxiv.org/abs/1906.09267) | Two transiting planets with ground-based timing refinement; each is scored separately. Other system planets are not silently added without frame eligibility. |
| TOI-3235 b | [Hobson et al. 2023](https://arxiv.org/abs/2302.10008) | ESPRESSO RV confirmation and multiple ground-based transit data sets. |
| TOI-849 b | [Armstrong et al. 2020](https://arxiv.org/abs/2003.10314) | Measured mass and transiting radius establish the planetary object; unusual density is not a P9 gate. |
| HIP 97166 b | [MacDougall et al. 2021](https://arxiv.org/abs/2110.05628) | RV confirmation, high impact parameter and eccentricity; the outer nontransiting RV planet does not count as a transit recovery target. |
| TOI-1680 b | [Ghachoui et al. 2023](https://arxiv.org/abs/2307.05368) | Multicolour transits and high-resolution imaging; described as an inactive late M dwarf. |
| TOI-1080 b | [Gómez Maqueo Chew et al. 2026](https://arxiv.org/abs/2603.00385) | TESS/ground-based validation, with an RV mass upper bound rather than a mass detection. |
| TOI-762 A b | [Hartman et al. 2024](https://arxiv.org/abs/2407.07187) | RV-confirmed planet; a resolved stellar companion is a real source-localization complication. |
| TOI-1450 A b | [Brady et al. 2024](https://arxiv.org/abs/2405.10400) | Transiting Earth-mass planet in the HUMDRUM RV survey. |
| TOI-1470 b/c | [González-Álvarez et al. 2023](https://arxiv.org/abs/2306.08516) | Two sub-Neptunes; detecting one does not establish recovery of the other. |
| TOI-715 b | [Dransfield et al. 2024](https://arxiv.org/abs/2305.06206) | Ground-based validation of the 19.29-day signal; other proposed signals on this host do not inherit its positive label. |
| TOI-2120 b | [Hori et al. 2024](https://arxiv.org/abs/2405.12637) | Ground-based/statistical validation with RV upper bounds; possible eccentricity limits a circular diagnostic-SNR template. |
| TOI-122 b | [Waalkes et al. 2021](https://arxiv.org/abs/2010.15905) | Discovery and validation of the 5.08-day transiting sub-Neptune around an inactive M dwarf; announced in 2020. |

The 12 binary controls come from the independently curated
[MAST TESS Eclipsing Binary catalogue](https://archive.stsci.edu/hlsp/tess-ebs),
described by [Prša et al. 2022](https://arxiv.org/abs/2110.13382).
The catalogue's morphology coefficient supplies approximate low/high-morphology
subgroups; it is not a definitive spectroscopic binary classification. Its
`bjd0` is the reference primary-eclipse BTJD (also documented in the
[VizieR catalogue](https://vizier.cfa.harvard.edu/viz-bin/VizieR?-source=J%2FApJS%2F258%2F16%2Ftess-ebs)).
Do not add `prim_pos_pf` again. The label identifies a binary signal associated
with the light curve, without asserting that the named TIC is its physical source.

The four blend controls use the frozen
[ExoFOP TOI bulk table](https://exofop.ipac.caltech.edu/tess/download_toi.php?sort=toi&output=csv)
and explicit TFOP comments confirming or retiring the signal as a nearby eclipsing
binary. `blend_truth.csv` contains each exact comment and original parameter row.
These are follow-up catalogue labels, not dispositions inferred from P9 outcomes.
Four ordinary TOI PCs remain uncertain and are tabulated separately. The CTOI
catalogue was snapshotted and participates in ordinary exclusion checks, but no
CTOI-only signal was added to the independent-label sample.

No independently attributable instrumental-signal or variable-only negative sample
was secured by this protocol. Those subtypes are uncalibrated. Rejected P8 signals
and speculative FP comments are not substituted as independent negative labels.
