import pandas as pd

try:
    _planets = planets_df
except NameError:
    _planets = pd.DataFrame()

# ── Branch on whether the detection loop accepted any candidates ───────────────
# Do NOT fall back to the raw BLS rank-1 candidate when the loop found nothing.
# That would vet a noise peak as if it were a real planet.

if _planets.empty:
    print("Detection loop found no accepted candidates.")
    print("Skipping vetting — there is nothing to vet.")
    best = None
    vet  = None

else:
    best = _planets.iloc[0]

    # Vet Planet 1 in full.  For multi-planet systems, per-planet vetting can
    # be added by looping over _planets rows and calling run_vetting() for each.
    vet = vetting.run_vetting(
        lc_clean,
        period_days         = best["period_days"],
        epoch_btjd          = best["epoch_btjd"],
        duration_days       = best["duration_days"],
        depth_ppt           = best["depth_ppt"],
        n_sectors           = len(sectors),
        stellar_radius_rsun = stellar_radius,
        is_known_toi        = xmatch["is_known_toi"],
    )

    print(f"Planet 1 vetting  P = {best['period_days']:.6f} d")
    print(f"VERDICT           : {vet.verdict}")
    print("\nVetting notes:")
    for n in vet.notes:
        print(f"  {n}")

    _sumcols = [c for c in
                ["planet_num", "period_days", "depth_ppt",
                 "snr", "event_completeness", "harmonic_label"]
                if c in _planets.columns]
    if len(_planets) > 1:
        print("\nAll detected candidates:")
        print(_planets[_sumcols].to_string(index=False))
