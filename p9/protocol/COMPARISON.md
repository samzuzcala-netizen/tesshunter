# P9 comparison specification, before external outcome scoring

The P8 analytic experiment used `survey_p8` and p7.0. The archived rules show
that its search/pre/A/secondary scientific choices equal the frozen p8.0 choices;
p8.0 additionally records exact Stage B window values. P8's published recovery
rule differs from P9's multi-event alignment rule. Re-score the saved P8 accepted
signals with the P9 primary match and candidate-choice rule. Reuse A/S only for the
same saved candidate and recheck its accepted A ephemeris. A missing or different
candidate's downstream record is uncalibrated, not a manufactured success/failure.
Keep both original and rescored counts. Do not edit historical records.
The rules are not nested: some old recoveries can fail the multi-event rule and
some previously uncredited signals can match P9's duration-based center tolerance.
Those newly credited signals have no historical A/S calibration. Keep them in the
comparison frame and report bounds for their missing downstream results.

For each external planet with a finite expected model SNR, test injection matches
using period ratio <=1.5, radius ratio <=1.5, expected SNR ratio <=2, Tmag difference
<=0.5, Teff difference <=300 K, stellar-radius difference <=0.1 Rsun, sector-count
ratio <=2, same product-majority group, and SPOC sector-fraction difference <=0.25.
These are descriptive calipers, not an assumption that discovery selection vanishes.
Report each caliper's support and the intersection. Require >=5 independent
injection hosts per external planet. A matched inferential estimate further requires
>=5 external hosts in each used period (below/above 10 d) x SNR (below/above 20)
x product cell, and >=10 external hosts overall. Otherwise report unsupported
comparison and the reason; do not drop product/cadence conditions to obtain a result.

When supported, external signals have equal weight, each one's matching injection
signals share its weight, and uncertainty resamples whole external and injection
hosts. Report host ESS and weight concentration. Report SNR/radius/period-only
tables as unmatched descriptive tables, never an analytic-optimism estimate.

There is no validated transplant or spatial injection in this experiment. Original
P8 light-curve injections have unchanged pixels and cannot calibrate localization.
The real-control experiment, with separate target-pixel review, supplies the only
measured late-gate observations. No new analytic transit is added to an unremoved
real transit to pretend it is a paired recovery experiment.

Yield retains the registered late-retention scenarios. With unsupported P8 overlap,
no external completeness point estimate is transported to the P8 population.
Conditional Poisson zero probabilities are labelled scenarios, and neither the
three incumbent-search assumptions nor alternative occurrence normalizations are
represented as posterior samples. Lower/upper late-yield bounds are zero and the
historical early-S yield. Search/pre/A/S historical expectations can be displayed
from their already calibrated model; B/C/D/HOLD remain uncalibrated where unsupported.
