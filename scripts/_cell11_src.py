# ── Step 3b: Alias-aware period resolution ───────────────────────────────────
# resolve_aliases_for_candidate() tests P/6, P/5, P/4, P/3, P/2, P, 2P, 3P, 4P.
# For each trial it:
#   1. Runs a local BLS refinement (±5% window).
#   2. Measures event completeness: fraction of covered windows with a real dip.
#      (A half-period alias scores ~0.5 here; the true period scores ~1.0.)
#   3. Measures alternating-event consistency: if odd/even events differ
#      greatly, the detected period is probably half the true period → prefer 2P.
#   4. Scores as  SNR × event_completeness × (1 − overlap).
#
# Selection priority:
#   1. Phase-0.5 alias flag (check_half_period_alias) fires → select P/2.
#   2. Alternating-event flag fires at input P → select 2P.
#   3. Otherwise → highest composite score (NOT shortest period).

resolved, trial_table = bls_search.resolve_aliases_for_candidate(
    lc_binned,
    candidates.iloc[0],
    existing_candidates = None,       # no prior planets yet
    period_min   = PERIOD_MIN,
    period_max   = PERIOD_MAX,
    duration_min = DURATION_MIN,
    duration_max = DURATION_MAX,
)

_disp = ["harmonic_label", "trial_period", "period_days",
         "depth_ppt", "snr", "event_completeness",
         "alternating_flag", "overlap", "composite_score"]
print("Harmonic / alias trial table:")
if not trial_table.empty:
    print(trial_table[_disp].to_string(index=False))
else:
    print("  (no harmonic trials in range)")

print(f"\nSelected: [{resolved['harmonic_label']}]  "
      f"P = {resolved['period_days']:.6f} d  "
      f"depth {resolved['depth_ppt']:.3f} ppt  "
      f"SNR {resolved['snr']:.1f}  "
      f"ev_comp {resolved.get('event_completeness', float('nan')):.2f}")

# 'best' is the resolved planet 1 — passed to all downstream cells.
best = resolved
