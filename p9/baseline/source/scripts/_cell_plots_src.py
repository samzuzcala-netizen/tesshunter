# Periodogram, raw, and cleaned plots don't depend on any detected candidate.
# Folded and zoom plots require 'best' (Planet 1); skip them when nothing was found.
plot_paths = plotting.all_diagnostic_plots(
    lc_raw, lc_clean, bls_result, candidates, TARGET_LABEL
)

if best is not None:
    plot_paths["folded"] = plotting.plot_folded_lightcurve(
        lc_clean,
        best["period_days"], best["epoch_btjd"], best["duration_days"],
        TARGET_LABEL,
    )
    plot_paths["zoom"] = plotting.plot_transit_zoom(
        lc_clean,
        best["epoch_btjd"], best["duration_days"], best["period_days"],
        TARGET_LABEL,
    )
else:
    print("No accepted candidates — skipping folded and zoom plots.")

print("Plots saved:")
for k, p in plot_paths.items():
    print(f"  {k}: {p}")
