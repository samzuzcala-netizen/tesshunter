"""P11.5 versioned copy of the P10 detector, with a side-effect-only pool observer.

Original source is sealed at P11 commit 3cf65ea0. The only behavioral addition
captures the complete all-gate-passing pool before ordinary selection. Observer
wall time is measured separately and excluded from the ordinary budget clock;
it remains fully charged to R1 deployable and actual experiment cost.
"""
from .pipeline import (lk, np, pd, time, Optional, StellarParams, preprocessing,
    bls_search, logger, pick_survivor, MAX_VETO_PASSES, PASS_COST_SAFETY,
    MIN_WORKING_CADENCES, MAX_MASK_REMOVAL_FRACTION, RINGING_PERIOD_TOL,
    GATE7_MIN_RP_RS, MIN_CADENCES_PER_DURATION, _n_finite_cadences,
    _is_artifact_period, _ringing_neighbour, _duration_is_railed, _box_rp_rs,
    _anchor_plausibility)

def _detect_planets(
    lc_clean: lk.LightCurve,
    *,
    period_min: float,
    period_max: float,
    duration_min: float,
    duration_max: float,
    max_planets: int,
    bin_minutes: float,
    top_n: int,
    n_periods: Optional[int],
    snr_min: float,
    snr_min_resolved: float,
    min_event_completeness: float,
    min_composite_score: float,
    min_transits: int,
    mask_width_factor: float,
    artifact_periods: list[float],
    known_periods: dict[str, float],
    notes: list[str],
    time_budget_s: Optional[float] = None,
    grid_cap: Optional[int] = None,
    local_grid_cap: Optional[int] = None,
    stellar: Optional[StellarParams] = None,
    rank_by: str = "composite",
    observer=None,
) -> tuple[list[dict], pd.DataFrame]:
    """Iterative detection loop ported from ``scripts/_cell_loop_src.py``.

    Each pass: bin the working LC, broad BLS (artifact periods suppressed),
    gate 1 on rank-1 raw SNR, then per-candidate alias resolution with the
    2% artifact skip applied both before and after resolution, gates 2–4
    (resolved SNR / event completeness / composite score), the NEW gate 5
    (``n_transits_observed >= min_transits``, defect B4), acceptance of the
    best survivor by composite score, transit masking with
    ``width_factor=mask_width_factor``, and a post-mask residual check.

    Robustness additions over the notebook loop: the loop stops cleanly when
    the working light curve drops below ``MIN_WORKING_CADENCES`` finite
    cadences or the BLS fails/returns empty, and a mask that would remove
    more than ``MAX_MASK_REMOVAL_FRACTION`` of cadences stops the loop after
    the planet is accepted instead of emptying the light curve.

    Returns
    -------
    (found_planets, first_pass_candidates) — accepted planet dicts and the
    raw BLS candidate table from the first pass (for reporting).
    """
    found_planets: list[dict] = []
    first_pass_candidates = pd.DataFrame()
    working_lc = lc_clean

    # A pass that finds only vetoed signals still MASKS the strongest of them
    # and continues, so a veto can never starve the search (see the empty-pool
    # branch below). Those passes do not produce a planet, so the loop needs
    # headroom beyond max_planets; MAX_VETO_PASSES bounds the extra work.
    observer_seconds = 0.0
    detect_t0 = time.perf_counter()
    worst_pass_s = 0.0
    pass_start: Optional[float] = None

    for _idx in range(max_planets + MAX_VETO_PASSES):
        if len(found_planets) >= max_planets:
            break

        # Cost of the pass that just finished, whichever way it exited.
        now = time.perf_counter() - observer_seconds
        if pass_start is not None:
            worst_pass_s = max(worst_pass_s, now - pass_start)
        pass_start = now

        # ── Wall-clock guard ──────────────────────────────────────────────────
        # A pass budget is a COUNT and says nothing about runtime, while callers
        # run under a hard per-target timeout. Overrunning it is far worse than
        # stopping early: the benchmark harness records `planets: []` for a
        # target that timed out, so a single overrun converts every recovered
        # planet on that target into a miss. Passes cost near-constant time
        # (masking removes only a few percent of cadences), so the slowest
        # completed pass predicts the next one.
        if time_budget_s is not None and worst_pass_s > 0.0:
            elapsed = now - detect_t0
            if elapsed + PASS_COST_SAFETY * worst_pass_s > time_budget_s:
                msg = (
                    f"Detection stopped before pass {_idx + 1}: another pass "
                    f"(~{PASS_COST_SAFETY * worst_pass_s:.0f} s) would not fit the "
                    f"{time_budget_s:.0f} s detection budget ({elapsed:.0f} s used)"
                )
                logger.warning(msg)
                notes.append(msg)
                break

        planet_num = len(found_planets) + 1
        logger.info("Detection pass %d (planet %d)", _idx + 1, planet_num)

        # ── Robustness: never BLS a (nearly) empty light curve ────────────────
        n_finite = _n_finite_cadences(working_lc)
        if n_finite < MIN_WORKING_CADENCES:
            msg = (
                f"Detection stopped before pass {planet_num}: only {n_finite} "
                f"finite cadences remain (< {MIN_WORKING_CADENCES})"
            )
            logger.warning(msg)
            notes.append(msg)
            break

        working_binned = preprocessing.bin_lightcurve(
            working_lc, bin_minutes=bin_minutes
        )

        # Binned cadence for gate 7: it decides whether the duration grid's
        # lower bound is resolvable at all on this data.
        _bt = np.asarray(working_binned.time.value, dtype=float)
        _bt = _bt[np.isfinite(_bt)]
        binned_cadence_days = (
            float(np.median(np.diff(np.sort(_bt)))) if _bt.size > 1 else 0.0
        )

        # ── Broad BLS (artifact periods suppressed before peak extraction) ────
        try:
            _, _, raw_cands = bls_search.run_bls(
                working_binned,
                period_min=period_min,
                period_max=period_max,
                duration_min=duration_min,
                duration_max=duration_max,
                top_n=top_n,
                suppress_periods=artifact_periods or None,
                n_periods=n_periods,
                n_max=grid_cap,
            )
        except Exception as exc:
            msg = f"Detection stopped at pass {planet_num}: BLS failed ({exc})"
            logger.warning(msg)
            notes.append(msg)
            break

        # Capture the genuine FIRST pass. planet_num is now len(found_planets)+1,
        # which stays 1 across veto passes, so it can no longer serve as the
        # "first pass" test without silently overwriting this table.
        if _idx == 0:
            first_pass_candidates = raw_cands.copy()

        if raw_cands.empty:
            logger.info("No BLS candidates returned — stopping.")
            break

        top = raw_cands.iloc[0]
        logger.info(
            "Broad BLS top: %.4f d  depth %.3f ppt  SNR %.1f  (%d candidates)",
            top["period_days"], top["depth_ppt"], top["snr"], len(raw_cands),
        )

        # Gate 1: fast exit when even rank-1 is clearly below threshold
        if float(top["snr"]) < snr_min:
            logger.info(
                "STOP (gate 1): top SNR %.1f < %.1f", top["snr"], snr_min
            )
            break

        # ── Try every top-N candidate; collect survivors ──────────────────────
        existing_df = pd.DataFrame(found_planets) if found_planets else None
        resolved_pool: list[tuple[pd.Series, int]] = []
        vetoed_pool: list[tuple[pd.Series, int, str]] = []

        logger.info("Resolving %d BLS candidate(s)...", len(raw_cands))
        for _, raw_cand in raw_cands.iterrows():
            p = float(raw_cand["period_days"])

            # Skip known instrument / sampling artifact periods
            if _is_artifact_period(p, artifact_periods):
                logger.info("[%.4f d]  artifact period — skip", p)
                continue

            try:
                resolved, _trial_table = bls_search.resolve_aliases_for_candidate(
                    working_binned,
                    raw_cand,
                    existing_candidates=existing_df,
                    period_min=period_min,
                    period_max=period_max,
                    duration_min=duration_min,
                    duration_max=duration_max,
                    local_n_max=local_grid_cap,
                )
            except Exception as exc:
                logger.warning(
                    "[%.4f d]  alias resolution failed (%s) — skip", p, exc
                )
                continue

            ev_comp = float(resolved.get("event_completeness", float("nan")))
            comp_score = float(resolved.get("composite_score", resolved["snr"]))
            r_p = float(resolved["period_days"])

            # Also skip if alias resolution chose an artifact period
            if _is_artifact_period(r_p, artifact_periods):
                logger.info(
                    "[%.4f d -> %.4f d]  resolved to artifact — skip", p, r_p
                )
                continue

            if float(resolved["snr"]) < snr_min_resolved:
                logger.info(
                    "[%.4f d -> %.4f d]  SNR %.1f < %.1f  (gate 2)",
                    p, r_p, resolved["snr"], snr_min_resolved,
                )
                continue
            if not (ev_comp >= min_event_completeness):   # NaN-safe
                logger.info(
                    "[%.4f d -> %.4f d]  ev_comp %.2f < %.2f  (gate 3)",
                    p, r_p, ev_comp, min_event_completeness,
                )
                continue
            if comp_score < min_composite_score:
                logger.info(
                    "[%.4f d -> %.4f d]  composite %.2f < %.2f  (gate 4)",
                    p, r_p, comp_score, min_composite_score,
                )
                continue

            # Gate 5 (NEW, defect B4): require enough observed transit epochs.
            # Read n_transits_observed from the resolved row; recompute at the
            # resolved ephemeris when the row does not carry an honest count.
            n_obs = int(resolved.get("n_transits_observed", 0) or 0)
            if n_obs <= 0:
                n_obs = bls_search._count_observed_transits(
                    np.asarray(working_binned.time.value, dtype=float),
                    float(resolved["epoch_btjd"]),
                    r_p,
                    float(resolved["duration_days"]),
                )
            if n_obs < min_transits:
                logger.info(
                    "[%.4f d -> %.4f d]  n_transits_observed %d < %d  (gate 5"
                    "%s)",
                    p, r_p, n_obs, min_transits,
                    "; single event" if n_obs <= 1 else "",
                )
                continue

            # ── Vetoes (gates 6 and 7) ────────────────────────────────────────
            # Applied AFTER the quality gates so only genuinely strong signals
            # can be vetoed — a veto must never be spent on noise. A vetoed
            # candidate is a real feature of the light curve (residual ringing
            # or an unresolvable-duration systematic); it is not reported as a
            # planet, but it is still eligible to be MASKED so the search can
            # keep going. See the empty-pool branch below.

            # Gate 6: ratio-1 neighbourhood veto. Masking an accepted planet
            # leaves correlated residual power a few percent away in period,
            # which a later pass re-detects as a new planet. Nothing else
            # carries accepted periods forward: suppress_periods gets only the
            # static artifact list, and the composite's `overlap` term is
            # epoch-based, so ringing at a drifting epoch produces no overlap.
            # HARMONICS ARE NOT SUPPRESSED — see RINGING_PERIOD_TOL.
            near = _ringing_neighbour(r_p, found_planets)
            if near is not None:
                logger.info(
                    "[%.4f d -> %.4f d]  within %.1f%% of accepted planet %d "
                    "(%.4f d) — residual ringing, vetoed  (gate 6)",
                    p, r_p, 100.0 * RINGING_PERIOD_TOL,
                    near["planet_num"], near["period_days"],
                )
                vetoed_pool.append((resolved, n_obs, "ringing"))
                continue

            # Gate 7: a duration pinned on an unresolvable grid floor. When
            # duration_min is below ~2 binned cadences no transit that short
            # can be measured at all, so a best fit landing exactly there is
            # the optimiser against a rail — characteristically a sharp
            # single-bin residual fitted as an absurdly deep box.
            if _duration_is_railed(
                float(resolved["duration_days"]), duration_min, binned_cadence_days
            ):
                # Second condition (prompt 3, part C3): the railed box must
                # also be too deep to be a planet. A shallow railed fit is
                # kept and left to vetting.
                rp_rs_box = _box_rp_rs(float(resolved["depth_ppt"]))
                if rp_rs_box > GATE7_MIN_RP_RS:
                    logger.info(
                        "[%.4f d -> %.4f d]  duration pinned at the unresolvable "
                        "grid floor %.5f d (< %.1f binned cadences of %.5f d) and "
                        "box depth implies Rp/R* %.3f > %.2f — vetoed  (gate 7)",
                        p, r_p, duration_min, MIN_CADENCES_PER_DURATION,
                        binned_cadence_days, rp_rs_box, GATE7_MIN_RP_RS,
                    )
                    vetoed_pool.append((resolved, n_obs, "railed duration"))
                    continue
                logger.info(
                    "[%.4f d -> %.4f d]  duration railed at %.5f d but box depth "
                    "implies Rp/R* %.3f <= %.2f — kept  (gate 7 second condition)",
                    p, r_p, duration_min, rp_rs_box, GATE7_MIN_RP_RS,
                )

            logger.info(
                "[%.4f d -> %.4f d]  SNR %.1f  ev_comp %.2f  composite %.2f  "
                "n_transits %d  PASS",
                p, r_p, resolved["snr"], ev_comp, comp_score, n_obs,
            )
            resolved_pool.append((resolved, n_obs))

        if not resolved_pool:
            if not vetoed_pool:
                logger.info("No candidate survived quality gates — stopping.")
                break
            # Every survivor was vetoed. Mask the strongest of them and carry
            # on: the signal is real (it passed every quality gate) and simply
            # is not a planet, so removing it is what lets a later pass reach
            # the planets hiding underneath. Without this, a target whose
            # top-N list is dominated by systematics loses the whole search —
            # on TRAPPIST-1 that cost 6 of 7 accepted candidates.
            v_res, _v_obs, v_why = max(
                vetoed_pool,
                key=lambda rv: float(rv[0].get("composite_score", rv[0]["snr"])),
            )
            v_p = float(v_res["period_days"])
            n_before = len(working_lc)
            masked_lc = preprocessing.mask_transits(
                working_lc, period=v_p, epoch=float(v_res["epoch_btjd"]),
                duration=float(v_res["duration_days"]),
                width_factor=mask_width_factor,
            )
            frac_removed = 1.0 - len(masked_lc) / max(n_before, 1)
            if frac_removed > MAX_MASK_REMOVAL_FRACTION:
                msg = (
                    f"Detection stopped: masking the vetoed {v_why} signal at "
                    f"P={v_p:.4f} d would remove {100.0 * frac_removed:.0f}% of cadences"
                )
                logger.warning(msg)
                notes.append(msg)
                break
            msg = (
                f"Vetoed {v_why} signal at P={v_p:.4f} d "
                f"(depth {float(v_res['depth_ppt']):.3f} ppt, SNR "
                f"{float(v_res['snr']):.1f}) masked but NOT reported as a planet"
            )
            logger.info(msg)
            notes.append(msg)
            working_lc = masked_lc
            continue

        # ── Pick best survivor by composite score (or resolved SNR, prompt 10) ─
        if observer is not None:
            callback_start = time.perf_counter()
            observer(lc_clean, working_lc, resolved_pool, _idx + 1)
            observer_seconds += time.perf_counter() - callback_start
        resolved, n_obs = pick_survivor(resolved_pool, rank_by)
        ev_comp = float(resolved.get("event_completeness", float("nan")))
        comp_score = float(resolved.get("composite_score", resolved["snr"]))
        r_p = float(resolved["period_days"])

        logger.info(
            "Accepted planet %d: [%s]  P = %.6f d  depth %.3f ppt  SNR %.1f  "
            "ev_comp %.2f  composite %.2f  n_transits %d",
            planet_num, resolved.get("harmonic_label", "P"), r_p,
            resolved["depth_ppt"], resolved["snr"], ev_comp, comp_score, n_obs,
        )

        found_planets.append({
            "planet_num":          planet_num,
            "period_days":         r_p,
            "epoch_btjd":          float(resolved["epoch_btjd"]),
            "duration_days":       float(resolved["duration_days"]),
            "depth_ppt":           float(resolved["depth_ppt"]),
            "power":               float(resolved.get("power", 0.0)),
            "snr":                 float(resolved["snr"]),
            "sde":                 float(resolved.get("sde", 0.0)),
            "event_completeness":  ev_comp,
            "n_transits_observed": int(n_obs),
            "single_event":        bool(n_obs <= 1),
            "harmonic_label":      str(resolved.get("harmonic_label", "P")),
            "odd_even_retest":     bool(resolved.get("odd_even_retest", False)),
            "carves_exclusion_zone": True,
        })

        # Gate 6 anchor plausibility (prompt 3, part C2): decide now, from a
        # cheap fit on the working curve, whether this candidate may veto
        # later neighbours as its ringing.
        carve, gate_fit = _anchor_plausibility(working_binned, found_planets[-1], stellar)
        found_planets[-1]["carves_exclusion_zone"] = bool(carve)
        found_planets[-1]["gate_fit"] = gate_fit
        if not carve:
            msg = (
                f"Planet {planet_num} at P={r_p:.4f} d does not carve a gate-6 exclusion "
                f"zone: {gate_fit.get('reason', '')}"
            )
            logger.info(msg)
            notes.append(msg)

        # ── Mask and verify ───────────────────────────────────────────────────
        n_before = len(working_lc)
        masked_lc = preprocessing.mask_transits(
            working_lc,
            period=r_p,
            epoch=float(resolved["epoch_btjd"]),
            duration=float(resolved["duration_days"]),
            width_factor=mask_width_factor,
        )
        frac_removed = 1.0 - len(masked_lc) / max(n_before, 1)
        if frac_removed > MAX_MASK_REMOVAL_FRACTION:
            msg = (
                f"Detection stopped after planet {planet_num}: masking "
                f"P={r_p:.4f} d (width_factor={mask_width_factor:g}) would "
                f"remove {100.0 * frac_removed:.0f}% of cadences"
            )
            logger.warning(msg)
            notes.append(msg)
            break
        working_lc = masked_lc

        # ── Post-mask check + known-period diagnostic (non-fatal) ─────────────
        try:
            if _n_finite_cadences(working_lc) >= MIN_WORKING_CADENCES:
                check_binned = preprocessing.bin_lightcurve(
                    working_lc, bin_minutes=bin_minutes
                )
                _, _, chk = bls_search.run_bls(
                    check_binned,
                    period_min=r_p * 0.98,
                    period_max=r_p * 1.02,
                    duration_min=duration_min,
                    duration_max=duration_max,
                    top_n=3,
                    n_max=local_grid_cap,
                )
                if chk.empty:
                    logger.info(
                        "Post-mask check (%.4f d): signal gone.", r_p
                    )
                else:
                    psnr = float(chk.iloc[0]["snr"])
                    logger.info(
                        "Post-mask check (%.4f d): SNR = %.1f%s",
                        r_p, psnr,
                        "  WARNING: still elevated — check width_factor"
                        if psnr > 5 else "  OK",
                    )
                for name, kp in known_periods.items():
                    _, _, local = bls_search.run_bls(
                        check_binned,
                        period_min=kp * 0.98,
                        period_max=kp * 1.02,
                        duration_min=duration_min,
                        duration_max=duration_max,
                        top_n=3,
                        n_max=local_grid_cap,
                    )
                    if local.empty:
                        logger.info("  %s (%.4f d): no signal", name, kp)
                    else:
                        b = local.iloc[0]
                        logger.info(
                            "  %s (%.4f d): P=%.4f d  depth=%.3f ppt  SNR=%.1f",
                            name, kp, b["period_days"], b["depth_ppt"], b["snr"],
                        )
        except Exception as exc:
            logger.debug("Post-mask check failed (non-fatal): %s", exc)

    logger.info(
        "Detection complete — %d candidate(s) found", len(found_planets)
    )
    return found_planets, first_pass_candidates


# ---------------------------------------------------------------------------
# Public API