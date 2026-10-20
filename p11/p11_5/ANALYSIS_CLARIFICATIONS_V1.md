# Evaluation clarifications before aggregate scoring

Recorded during the six-host downstream timing pilot, before development size selection, recovery matching, historical C measurements or aggregate efficacy inspection. These clarify the implementation of the registered selection and unknown rules; they introduce no new search, C model or thresholds.

- Protection of each exact original adversarial identity requires a measured isolated S/C rejection and a rejection in the ordered A/S/B/C route. An operationally unknown ordered route is not protected. An earlier measured A or B failure alone cannot hide failure of isolated S/C protection. These historical controls are explicitly conditioned on registered candidate ephemerides, rather than newly selected by blind survey search.
- The tie rule's forwarded-control count uses unique exact measurement identities in the union of the 40 original S controls and the distinct 41-record EB C collection. Unknowns count as forwarded; overlap does not count twice. Injection controls are not contamination negatives. Every original collection row remains in the output.
- Sensitivity diagnostics use fixed half-open expected-SNR, physical-period and radius bins declared in `protocol/sensitivity_tables.py`. All included injections remain in the overall denominator, including expected SNR zero. Aliases are reported separately and never count as true-period recoveries.
- SNR50/SNR90 are point diagnostics from the historical two-parameter logistic family in log expected SNR. Non-finite, non-increasing, single-class and extrapolated crossings are marked. Required recovery uncertainty uses the registered 10,000 paired whole-host bootstrap, not independent injection resampling. The historical P10 stop is unchanged.

The live timing workers do not import the evaluator or this document. Their sealed scientific sources remain unchanged.
