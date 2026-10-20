import pandas as pd

# ── Step 0: Pre-mask already-found planets (b, c, d, e) ──────────────────────
# Strategy A — kernel still has planets_df from the previous run:
#   uses those exact epochs/durations (most accurate).
# Strategy B — kernel was restarted:
#   runs a quick BLS in a tight window around each known period to resolve
#   the epoch, then masks.  Falls back to FOUND_PLANETS literature values.

_to_mask = []

try:
    if planets_df is not None and not planets_df.empty:
        for _, _r in planets_df.iterrows():
            _to_mask.append({
                "name":          f"planet {int(_r['planet_num'])}",
                "period_days":   float(_r["period_days"]),
                "epoch_btjd":    float(_r["epoch_btjd"]),
                "duration_days": float(_r["duration_days"]),
            })
        print(f"Using planets_df from previous run — pre-masking "
              f"{len(_to_mask)} planet(s).")
except NameError:
    pass

if not _to_mask:
    print("planets_df not in namespace — resolving epochs from FOUND_PLANETS via BLS...")
    _binned_tmp = preprocessing.bin_lightcurve(lc_clean, bin_minutes=BIN_MINUTES)
    for _fp in FOUND_PLANETS:
        _p = _fp["period_days"]
        _, _, _c = bls_search.run_bls(
            _binned_tmp,
            period_min   = _p * 0.97,
            period_max   = _p * 1.03,
            duration_min = DURATION_MIN,
            duration_max = DURATION_MAX,
            top_n        = 1,
            n_periods    = 500,
        )
        if not _c.empty:
            _epoch = float(_c.iloc[0]["epoch_btjd"])
            _dur   = float(_c.iloc[0]["duration_days"])
            print(f"  {_fp['name']}: P={_c.iloc[0]['period_days']:.4f} d  "
                  f"epoch={_epoch:.4f}  dur={_dur:.4f}  [BLS-resolved]")
        elif _fp["epoch_btjd"] is not None:
            _epoch = _fp["epoch_btjd"]
            _dur   = _fp["duration_days"]
            print(f"  {_fp['name']}: BLS found nothing — using config epoch {_epoch:.4f}")
        else:
            print(f"  {_fp['name']}: BLS found nothing and no epoch set — "
                  f"skipping mask (transit may still be in the LC).")
            continue
        _to_mask.append({
            "name":          _fp["name"],
            "period_days":   _p,
            "epoch_btjd":    _epoch,
            "duration_days": _dur,
        })

# Apply the masks
working_lc = lc_clean
_masked_names = []
for _m in _to_mask:
    working_lc = preprocessing.mask_transits(
        working_lc,
        period       = _m["period_days"],
        epoch        = _m["epoch_btjd"],
        duration     = _m["duration_days"],
        width_factor = 7.0,
    )
    _masked_names.append(_m["name"])

print(f"\nPre-mask done.  Masked: {_masked_names}")
print(f"Cadences remaining: {len(working_lc)}  "
      f"(removed {len(lc_clean) - len(working_lc)})")
print(f"\nNow searching {PERIOD_MIN:.1f}–{PERIOD_MAX:.1f} d for f / g / h ...\n")

# ── Backward-compatible config fallbacks ──────────────────────────────────────
try:
    _artifact_periods = ARTIFACT_PERIODS
except NameError:
    _artifact_periods = [1.0]

try:
    _known_periods = KNOWN_PERIODS
except NameError:
    _known_periods = {}

try:
    _n_periods = N_PERIODS
except NameError:
    _n_periods = None

_disp = ["harmonic_label", "trial_period", "period_days",
         "depth_ppt", "snr", "event_completeness",
         "alternating_flag", "overlap", "composite_score"]

found_planets = []

# ── Iterative f / g / h detection ─────────────────────────────────────────────
for _idx in range(MAX_PLANETS):
    planet_num = _idx + 1
    print(f"\n{'='*62}")
    print(f"  Detection pass {planet_num}  "
          f"(searching {PERIOD_MIN:.1f}–{PERIOD_MAX:.1f} d)")
    print(f"{'='*62}")

    working_binned = preprocessing.bin_lightcurve(working_lc, bin_minutes=BIN_MINUTES)

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

    if top["snr"] < SNR_MIN:
        print(f"  STOP (gate 1): top SNR {top['snr']:.1f} < {SNR_MIN}")
        break

    existing_df   = pd.DataFrame(found_planets) if found_planets else None
    resolved_pool = []

    print(f"\nResolving {len(raw_cands)} BLS candidate(s)...")
    for _, raw_cand in raw_cands.iterrows():
        p = raw_cand["period_days"]

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

        if any(abs(r_p / bad - 1.0) < 0.02 for bad in _artifact_periods):
            print(f"  [{p:.4f} d -> {r_p:.4f} d]  resolved to artifact -- skip")
            continue

        if resolved["snr"] < SNR_MIN_RESOLVED:
            print(f"  [{p:.4f} d -> {r_p:.4f} d]  "
                  f"SNR {resolved['snr']:.1f} < {SNR_MIN_RESOLVED}  (gate 2)")
            continue
        if not (ev_comp >= MIN_EVENT_COMPLETENESS):
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
        print("\nNo candidate survived quality gates — stopping.")
        break

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

    # Mask this planet from the residual before the next pass
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
        top_n        = 3,
    )
    if chk.empty:
        print(f"Post-mask check ({resolved['period_days']:.4f} d): signal gone. OK")
    else:
        psnr = chk.iloc[0]["snr"]
        flag = "  WARNING: still elevated — check width_factor" if psnr > 5 else "  OK"
        print(f"Post-mask check ({resolved['period_days']:.4f} d): "
              f"residual SNR = {psnr:.1f}{flag}")

    # Known-period diagnostic — how strong are the remaining targets?
    if _known_periods:
        print(f"\nKnown-period diagnostic (residual after pass {planet_num}):")
        for _name, _p in _known_periods.items():
            _, _, _local = bls_search.run_bls(
                check_binned,
                period_min   = _p * 0.98,
                period_max   = _p * 1.02,
                duration_min = DURATION_MIN,
                duration_max = DURATION_MAX,
                top_n        = 3,
            )
            if _local.empty:
                print(f"  {_name} ({_p:.4f} d): no signal")
            else:
                _b = _local.iloc[0]
                print(f"  {_name} ({_p:.4f} d): "
                      f"P={_b['period_days']:.4f} d  "
                      f"depth={_b['depth_ppt']:.3f} ppt  "
                      f"SNR={_b['snr']:.1f}")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*62}")
print(f"f/g/h search complete — {len(found_planets)} candidate(s) accepted")
print(f"{'='*62}")
planets_df = pd.DataFrame(found_planets)
if not planets_df.empty:
    _sumcols = ["planet_num", "period_days", "depth_ppt",
                "snr", "event_completeness", "harmonic_label"]
    print(planets_df[_sumcols].to_string(index=False))
else:
    print("No candidates passed all gates.")
    print("Try inspecting phase folds at the known periods manually (see KNOWN_PERIODS).")

# Downstream aliases expected by later cells
best    = planets_df.iloc[0] if not planets_df.empty else None
planet2 = planets_df.iloc[1] if len(planets_df) > 1 else None
