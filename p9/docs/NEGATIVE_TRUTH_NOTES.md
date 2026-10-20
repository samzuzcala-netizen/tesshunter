# Negative truth: epoch definitions and scope

The frozen MAST EB catalogue supplies independently classified binary signals.
In Table 1 of the primary paper, `bjd0` is the primary-eclipse epoch in
BJD minus 2457000. P9 therefore does not add the fitted `prim_pos_pf` phase to
that epoch. Polyfit and two-Gaussian phase/width summaries can differ; they are
not a second required epoch offset. [Prša et al., Table 1](https://arxiv.org/pdf/2110.13382)

The catalogue release principally describes two-minute observations from the
first two TESS years. Its observing and discovery selection is distinct from
P8's cool, faint, FFI population. P9's later-sector measurements are external
tests of the retained labels/nominal ephemerides, not a claim that this catalogue
is a representative P8 negative population.
[MAST release description](https://archive.stsci.edu/hlsp/tess-ebs)

The preparation code copied nominal EB periods, primary epochs and duration/depth
summaries but omitted the available period/epoch error columns from the frozen
truth CSV. This omission is preserved and disclosed. The post-lock
[negative audit](../NEGATIVE_AUDIT.md) retrieves those errors from the unchanged
catalogue snapshot and propagates them over the selected observations as a
diagnostic. No primary score, eligibility decision or blind measurement changes.
The approximation omits covariance and real eclipse-timing variability.

An accepted near-period signal can fail the registered event rule even when a
binary is clearly present. For example, TIC 379783522's half-period candidate
matches 29 of 29 nominal primary opportunities but only 29 of 59 found
opportunities, below the fixed 50% threshold. Its actual native path terminates
at A. Other old ephemerides have appreciable propagated timing errors. The
post-lock audit reports both issues and a conservative all-candidate escape
bound without assigning the binary label to unrelated signals.

A separate future frame could examine the more recent independently vetted
FFI-based [TESS Ten Thousand catalogue](https://arxiv.org/abs/2506.05631), while
still imposing and verifying the intended stellar/product/coverage domain.
That catalogue was not substituted into the frozen P9 control sample after
outcomes became available.
