import pandas as pd

# ── Iterative planet detection ────────────────────────────────────────────────
# All thresholds (MAX_PLANETS, SNR_MIN, SNR_MIN_RESOLVED, MIN_EVENT_COMPLETENESS,
# MIN_COMPOSITE_SCORE, ARTIFACT_PERIODS, KNOWN_PERIODS) come from the config cell.
#
# Each pass:
#   1. Bin the working LC (lc_clean initially; masks accumulate each pass).
#   2. Run a broad BLS on the residual — TOP_N candidates.
#   3. GATE 1 — stop if even rank-1 SNR < SNR_MIN (pure-noise pass).
#   4. Iterate over ALL TOP_N candidates:
#      a. Skip known artifact periods (ARTIFACT_PERIODS).
#      b. Resolve aliases (half-period dip, alternating events,
#         event completeness, physical window overlap vs. prior planets).
#      c. GATES 2-4 — reject if resolved SNR / ev_comp / composite < thresholds.
#      d. Collect survivors in resolved_pool.
#   5. Stop if resolved_pool is empty (no real signal remains).
#      Otherwise pick the best candidate by composite score.
#   6. Accept the planet, mask it from the UNBINNED working LC (width_factor=7).
#   7. Post-mask SNR check + optional known-period diagnostic.
#
# Key: step 4 tries every top-N BLS peak, not just rank 1.  After masking, the
# strongest residual is often a junk/artifact signal while real planets sit at
# rank 5, 12, 20.  This is especially true for K2 where 1-day roll artifacts
# can dominate the residual even after a real transit has been masked.

# Backward-compatible fallbacks for new config variables
try:
    _artifact_periods = ARTIFACT_PERIODS
except NameError:
    _artifact_periods = [1.0]

try:
    _known_periods = KNOWN_PERIODS
except NameError:
    _known_periods = {}

try:
    _n_periods = N_PERIODS      # override BLS frequency-grid size (None = auto)
except NameError:
    _n_periods = None

_disp = ["harmonic_label", "trial_period", "period_days",
         "depth_ppt", "snr", "event_completeness",
         "alternating_flag", "overlap", "composite_score"]

found_planets = []
working_lc    = lc_clean

for _idx in range(MAX_PLANETS):
    planet_num = _idx + 1
    print(f"\n{'='*62}")
    print(f"  Detection pass {planet_num}")
    print(f"{'='*62}")

    working_binned = preprocessing.bin_lightcurve(working_lc, bin_minutes=BIN_MINUTES)

    # ── Broad BLS ─────────────────────────────────────────────────────────
    # suppress_periods zeros out artifact-period power before peak extraction,
    # preventing artifacts from (a) consuming candidate slots and (b) triggering
    # harmonic masking that would erase real signals at nearby periods.
    _, _, raw_cands = bls_search.run_bls(
        working_binned,
        period_min       = PERIOD_MIN,
        period_max       = PERIOD_MAX,
        duration_min     = DURATION_MIN,
        duration_max     = DURATION_MAX,
        top_n            = TOP_N,
        suppress_periods = _artifact_periods,
        n_periods        = _n_periods,
    )

    if raw_cands.empty:
        print("No BLS candidates returned — stopping.")
        break

    top = raw_cands.iloc[0]
    print(f"Broad BLS top:  {top['period_days']:.4f} d  "
          f"depth {top['depth_ppt']:.3f} ppt  SNR {top['snr']:.1f}  "
          f"({len(raw_cands)} candidates)")

    # Gate 1: fast exit when even rank-1 is clearly below threshold
    if top["snr"] < SNR_MIN:
        print(f"  STOP (gate 1): top SNR {top['snr']:.1f} < {SNR_MIN}")
        break

    # ── Try every top-N candidate; collect survivors ───────────────────────
    existing_df   = pd.DataFrame(found_planets) if found_planets else None
    resolved_pool: list[tuple] = []  # (resolved_series, trial_table_df)

    print(f"\nResolving {len(raw_cands)} BLS candidate(s)...")
    for _, raw_cand in raw_cands.iterrows():
        p = raw_cand["period_days"]

        # Skip known instrument / sampling artifact periods
        if any(abs(p / bad - 1.0) < 0.02 for bad in _artifact_periods):
            print(f"  [{p:.4f} d]  artifact period -- skip")
            continue

        resolved, trial_table = bls_search.resolve_aliases_for_candidate(
            working_binned,
            raw_cand,
            existing_candidates = existing_df,
            period_min   = PERIOD_MIN,
            period_max   = PERIOD_MAX,
            duration_min = DURATION_MIN,
            duration_max = DURATION_MAX,
        )

        ev_comp    = resolved.get("event_completeness", float("nan"))
        comp_score = resolved.get("composite_score", resolved["snr"])
        r_p        = resolved["period_days"]

        # Also skip if alias resolution chose an artifact period
        # (e.g. raw=2.010 d -> resolver picks P/2=1.005 d)
        if any(abs(r_p / bad - 1.0) < 0.02 for bad in _artifact_periods):
            print(f"  [{p:.4f} d -> {r_p:.4f} d]  resolved to artifact -- skip")
            continue

        if resolved["snr"] < SNR_MIN_RESOLVED:
            print(f"  [{p:.4f} d -> {r_p:.4f} d]  "
                  f"SNR {resolved['snr']:.1f} < {SNR_MIN_RESOLVED}  (gate 2)")
            continue
        if not (ev_comp >= MIN_EVENT_COMPLETENESS):   # NaN-safe
            print(f"  [{p:.4f} d -> {r_p:.4f} d]  "
                  f"ev_comp {ev_comp:.2f} < {MIN_EVENT_COMPLETENESS}  (gate 3)")
            continue
        if comp_score < MIN_COMPOSITE_SCORE:
            print(f"  [{p:.4f} d -> {r_p:.4f} d]  "
                  f"composite {comp_score:.2f} < {MIN_COMPOSITE_SCORE}  (gate 4)")
            continue

        print(f"  [{p:.4f} d -> {r_p:.4f} d]  "
              f"SNR {resolved['snr']:.1f}  ev_comp {ev_comp:.2f}  "
              f"composite {comp_score:.2f}  PASS")
        resolved_pool.append((resolved, trial_table))

    if not resolved_pool:
        print("\nNo candidate survived quality gates -- stopping.")
        break

    # ── Pick best survivor by composite score ─────────────────────────────
    resolved, best_trial = max(
        resolved_pool,
        key=lambda rt: rt[0].get("composite_score", rt[0]["snr"]),
    )
    ev_comp    = resolved.get("event_completeness", float("nan"))
    comp_score = resolved.get("composite_score", resolved["snr"])

    print(f"\nAlias trial table (best candidate):")
    if not best_trial.empty:
        print(best_trial[_disp].to_string(index=False))

    print(f"\nAccepted planet {planet_num}: [{resolved['harmonic_label']}]  "
          f"P = {resolved['period_days']:.6f} d  "
          f"depth {resolved['depth_ppt']:.3f} ppt  "
          f"SNR {resolved['snr']:.1f}  "
          f"ev_comp {ev_comp:.2f}  "
          f"composite {comp_score:.2f}")

    found_planets.append({
        "planet_num":         planet_num,
        "period_days":        resolved["period_days"],
        "epoch_btjd":         resolved["epoch_btjd"],
        "duration_days":      resolved["duration_days"],
        "depth_ppt":          resolved["depth_ppt"],
        "power":              resolved.get("power", 0.0),
        "snr":                resolved["snr"],
        "event_completeness": ev_comp,
        "harmonic_label":     resolved.get("harmonic_label", "P"),
    })

    # ── Mask and verify ───────────────────────────────────────────────────
    working_lc = preprocessing.mask_transits(
        working_lc,
        period       = resolved["period_days"],
        epoch        = resolved["epoch_btjd"],
        duration     = resolved["duration_days"],
        width_factor = 7.0,
    )
    check_binned = preprocessing.bin_lightcurve(working_lc, bin_minutes=BIN_MINUTES)
    _, _, chk = bls_search.run_bls(
        check_binned,
        period_min   = resolved["period_days"] * 0.98,
        period_max   = resolved["period_days"] * 1.02,
        duration_min = DURATION_MIN,
        duration_max = DURATION_MAX,
        top_n = 3,
    )
    if chk.empty:
        print(f"Post-mask check ({resolved['period_days']:.4f} d): signal gone.")
    else:
        psnr = chk.iloc[0]["snr"]
        flag = "  WARNING: still elevated -- check width_factor" if psnr > 5 else "  OK"
        print(f"Post-mask check ({resolved['period_days']:.4f} d): SNR = {psnr:.1f}{flag}")

    # ── Known-period diagnostic ────────────────────────────────────────────
    if _known_periods:
        print(f"\nKnown-period diagnostic "
              f"(residual after planet {planet_num} masked):")
        for _name, _p in _known_periods.items():
            _, _, _local = bls_search.run_bls(
                check_binned,
                period_min   = _p * 0.98,
                period_max   = _p * 1.02,
                duration_min = DURATION_MIN,
                duration_max = DURATION_MAX,
                top_n = 3,
            )
            if _local.empty:
                print(f"  {_name} ({_p:.4f} d): no signal")
            else:
                _b = _local.iloc[0]
                print(f"  {_name} ({_p:.4f} d): "
                      f"P={_b['period_days']:.4f} d  "
                      f"depth={_b['depth_ppt']:.3f} ppt  "
                      f"SNR={_b['snr']:.1f}")

# ── Summary table ─────────────────────────────────────────────────────────────
print(f"\n{'='*62}")
print(f"Detection complete -- {len(found_planets)} candidate(s) found")
print(f"{'='*62}")
planets_df = pd.DataFrame(found_planets)
if not planets_df.empty:
    _sumcols = ["planet_num", "period_days", "depth_ppt",
                "snr", "event_completeness", "harmonic_label"]
    print(planets_df[_sumcols].to_string(index=False))

# Downstream aliases
best    = planets_df.iloc[0] if not planets_df.empty else None
planet2 = planets_df.iloc[1] if len(planets_df) > 1 else None
