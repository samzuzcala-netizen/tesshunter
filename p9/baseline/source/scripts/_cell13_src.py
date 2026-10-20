import pandas as pd

# ── Mask planet-1 transits from the UNBINNED light curve, then re-bin ─────────
# width_factor=7.0 removes ±7 transit durations — aggressive enough to
# suppress both the primary signal and any correlated detrending residuals.
lc_masked = preprocessing.mask_transits(
    lc_clean,
    period       = best["period_days"],
    epoch        = best["epoch_btjd"],
    duration     = best["duration_days"],
    width_factor = 7.0,
)
lc_masked_binned = preprocessing.bin_lightcurve(lc_masked, bin_minutes=BIN_MINUTES)

print(f"Planet 1 ({best['period_days']:.4f} d) masked: "
      f"{len(lc_clean)} -> {len(lc_masked)} unbinned cadences")
print(f"After re-binning: {len(lc_masked_binned)} cadences")

# ── Diagnostic: did masking suppress planet 1? ───────────────────────────────
_, _, check_cands = bls_search.run_bls(
    lc_masked_binned,
    period_min   = best["period_days"] * 0.98,
    period_max   = best["period_days"] * 1.02,
    duration_min = DURATION_MIN,
    duration_max = DURATION_MAX,
    top_n = 3,
)
print("\nPost-mask check near planet-1 period (SNR should collapse):")
if check_cands.empty:
    print("  No signal found — masking successful.")
else:
    print(check_cands[["period_days", "depth_ppt", "snr"]].to_string(index=False))
    if check_cands.iloc[0]["snr"] > 5:
        print("  WARNING: SNR still high — consider increasing width_factor or "
              "re-checking period/epoch accuracy.")

# ── Blind BLS on the masked residual ─────────────────────────────────────────
_, result2, candidates2 = bls_search.run_bls(
    lc_masked_binned,
    period_min   = PERIOD_MIN,
    period_max   = PERIOD_MAX,
    duration_min = DURATION_MIN,
    duration_max = DURATION_MAX,
    top_n = TOP_N,
)

# ── Alias resolution for planet-2 candidate ───────────────────────────────────
# Pass planet 1 as existing_candidates so that trials whose transit windows
# physically overlap planet 1's windows are penalised.
# A period at ~2 × P1 is NOT penalised unless its transit windows actually
# coincide with planet 1's windows — independent planets at 2:1 resonance
# have uncorrelated epochs and therefore low physical overlap.
planet1_df = pd.DataFrame([{
    "period_days":   best["period_days"],
    "epoch_btjd":    best["epoch_btjd"],
    "duration_days": best["duration_days"],
}])

if candidates2.empty:
    print("No significant residual signal after masking planet 1.")
    planet2 = None
else:
    print("\nResidual BLS candidates (planet-1 masked):")
    print(candidates2[["peak_rank", "period_days", "depth_ppt",
                        "duration_days", "snr", "score"]].to_string(index=False))

    resolved2, trial_table2 = bls_search.resolve_aliases_for_candidate(
        lc_masked_binned,
        candidates2.iloc[0],
        existing_candidates = planet1_df,
        period_min   = PERIOD_MIN,
        period_max   = PERIOD_MAX,
        duration_min = DURATION_MIN,
        duration_max = DURATION_MAX,
    )

    _disp = ["harmonic_label", "trial_period", "period_days",
             "depth_ppt", "snr", "event_completeness",
             "alternating_flag", "overlap", "composite_score"]
    print("\nHarmonic / alias trial table (planet 2):")
    if not trial_table2.empty:
        print(trial_table2[_disp].to_string(index=False))
    else:
        print("  (no harmonic trials in range)")

    planet2 = resolved2
    print(f"\nResolved planet-2 candidate: [{planet2['harmonic_label']}]  "
          f"P = {planet2['period_days']:.6f} d  "
          f"depth {planet2['depth_ppt']:.3f} ppt  "
          f"SNR {planet2['snr']:.1f}  "
          f"ev_comp {planet2.get('event_completeness', float('nan')):.2f}")

# ── Summary ────────────────────────────────────────────────────────────────────
print("\nCandidates found so far:")
print(f"  Planet 1: {best['period_days']:.6f} d  "
      f"depth {best['depth_ppt']:.3f} ppt  SNR {best['snr']:.1f}")
if planet2 is not None:
    print(f"  Planet 2: {planet2['period_days']:.6f} d  "
          f"depth {planet2['depth_ppt']:.3f} ppt  SNR {planet2['snr']:.1f}")
else:
    print("  Planet 2: not found")
