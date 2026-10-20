"""Prompt K1 thresholds (k1/protocol/RULES_K1.md), named once.

Kept out of :mod:`tesshunter.audit_rules`, whose source P12 pins (``p12/tests/test_rules_p12.py``
``test_historical_rule_sources_unchanged``).  Every value here is read only when a K1 switch or mode is
on; the prompt-5 to prompt-12 rule sets never import them.
"""
from __future__ import annotations

# change 11: the alias-aware S mode ``bound_alias`` (tesshunter.secondary)
#: an off-phase dip is in the alias family when it lies within this phase of the primary's phase + 0.5
#: (or 1.5 box widths in phase, whichever is larger) ...
SEC_ALIAS_PHASE_TOL = 0.02
#: ... its detrended depth agrees with the primary's within this many combined sigma ...
SEC_ALIAS_CONSISTENCY_SIGMA = 2.0
#: ... and its best box width (the most significant of these multiples of the candidate duration) lies
#: within one step of the primary's.
SEC_ALIAS_WIDTH_FACTORS = (0.5, 0.75, 1.0, 1.5, 2.0)

# change 12: the noise-relative SAP ramp (tesshunter.event_vet.SAP_RAMP_NOISE_MULTIPLE, Rule E3 variant)
K1_SAP_RAMP_NOISE_MULTIPLE = 3.0

# exposure-aware Stage B (tesshunter.star_vet.B_CADENCE_RULE = "per_window"): a coarser sector also tests
# a period when its cadence puts at least this many cadences in the T14 window
B_MIN_CADENCES_PER_WINDOW = 4

# amendment 2 (k1/protocol/AMENDMENT_K1_20261008_2.md): exposure-aware Stage A per-event depth
# (tesshunter.event_vet.EVENT_DEPTH_TEMPLATE); on in every K1 funnel, both arms
K1_EVENT_DEPTH_TEMPLATE = "exposure_ld"
