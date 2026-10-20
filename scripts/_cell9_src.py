lc_binned = preprocessing.bin_lightcurve(lc_clean, bin_minutes=BIN_MINUTES)
print(f"Binned: {len(lc_clean)} cadences -> {len(lc_binned)} cadences (binned)")

# Broad BLS search — no assumptions about what period to expect
bls_model, bls_result, candidates = bls_search.run_bls(
    lc_binned,
    period_min=PERIOD_MIN,
    period_max=PERIOD_MAX,
    duration_min=DURATION_MIN,
    duration_max=DURATION_MAX,
    top_n=TOP_N,
)

# score = SNR x completeness (penalises periods whose transits fall in sector gaps)
print(candidates[["peak_rank","period_days","depth_ppt","duration_days","snr","score"]].to_string(index=False))
