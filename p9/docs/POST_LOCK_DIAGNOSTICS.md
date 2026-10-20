# Supplemental diagnosis from locked evidence

These analyses were added after some individual hosts had been locked and scored.
They are exploratory explanations of existing results. They are not changes to
the preregistered scientific gates, sample, match rule, truth manifest or manual
verdicts. Full versions include every applicable locked control; partial versions
are explicitly named and retained for the work history.

`search_audit.py` reads existing search logs for all positive search-match failures.
It locates local near-period candidates and records their gates, composite scores,
chosen competitors and exact log lines. A local period match does not prove that
an alternative full-stitch search would recover the planet.

`spectrum_audit.py` reads every saved blind C power array and reports quantiles,
extrema and each extreme bin's fraction of centered power variance. It archives
the installed TLS statistic implementation. No bin is removed, no replacement
SDE is calculated and no failed C candidate advances. The raw trial chi-square
arrays were not saved, limiting diagnosis of upstream numerical/statistical causes.

`ephemeris_audit.py` lists timing context for every positive. If a locked positive
fails the primary search match despite an accepted candidate within the registered
1% period window, it retrieves every available NASA PS timing row for that object.
The immutable post-lock CSV and receipt include publication and ExoFOP entries;
the original receipt's phrase "published PS rows" describes this complete archive
query and does not establish peer review of an ExoFOP row. No solution is selected
to replace the primary truth. Each timing solution is independently applied to
the same locked candidates and accepted A/C/D ephemerides with the unchanged
event-matching function. This executes no scientific stage and supplies no primary
recovery credit. The receipt records the host lock time preceding the source query.

For TOI-849 b, the archive default is the Polanski et al. (2024) solution. The
Armstrong et al. (2020) solution predicts the saved blind signal much more closely.
The [discovery paper](https://arxiv.org/abs/2003.10314), Table 1, independently
identifies a precise transit ephemeris; its arXiv v3 rounded/posterior values
differ slightly from the archive's indexed version. The computation uses the
exact archived PS row, preserved in the post-lock CSV, not a hand-entered hybrid.
Independent-error propagation omits epoch/period covariance and TTVs. This is a
one-control sensitivity to truth preparation, not a calibrated new scoring method.

`ephemeris_figures.py` plots the same saved blind prepared flux using the frozen
default, alternative published and already-locked fitted timing coordinates. It
changes only display coordinates and median display bins; it does not extract,
filter, inject, fit, or score a new signal.

`negative_audit.py` independently checks every negative's nominal timing and
registered aliases. An intentionally broad union of any candidate on the host,
plus operationally unavailable paths, supplies a possible-survival upper bound.
It never assigns a negative label to an unrelated candidate. Error columns omitted
from the original EB truth manifest are read only from the frozen raw catalogue
for this diagnostic; primary timing and outcome counts remain unchanged.

`duration_audit.py` was added after the final host locks and scores exposed
TOI-1450 A b's `C_signal_switch` category. It inventories every reported C duration
and checks each identity failure using the same saved C period and epoch with
alternative recorded A, native D seed, final D fit and published durations. The
very short reported C duration admits only 77 of 172 truth opportunities. Native
C itself passed, and the native physical-fit window already uses the wider of
survey and C durations. The existing final fit is checked for association only;
none of these substitutions changes primary scoring or supplies a rescued pass.
The first-termination category is an identity-test failure, not proof that a
different physical signal was selected. The upstream duration problem and a
replacement identity protocol remain uncalibrated.

`historical_caps.py` copies and hashes the original P8 B/C/D records and checks
which C survivors already had B HOLD ceilings. It does not revisit or overwrite
the historical decisions, nor establish whether a cap was astrophysically justified.

No gate variant, ephemeris-selection protocol, transplantation or spatial injection
was evaluated on an independent holdout. These diagnoses motivate future controlled
experiments; their retention benefits and negative-control costs remain unmeasured.
