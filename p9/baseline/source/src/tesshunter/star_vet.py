"""Star-level tests: the phase-independent window test, deep-event hosts, Gaia flags.

Ported out of ``scripts/revet_p6.py`` unchanged (Stage B).  Pure: arrays and
already-fetched records in, dicts out.  Nothing here queries Gaia, SIMBAD or
VSX — ``gaia_flag_digest`` reads a neighbours record that was cached earlier.

The prompt-7 addition is ``long_period_window_test``: at periods where no
sector spans 1.5 periods the deepest-window test has no power at all (a TESS
sector spans about 25 d, so only P below roughly 17 d can be tested), and five
of the seven prompt-6 Stage B candidates had zero testable sectors.  The
long-period test asks a different question of the same data — in how many of
the sectors that predicted a transit did every observed epoch get removed by
the event rules — and flags, never kills.
"""
from __future__ import annotations

import math

import numpy as np

from .audit_rules import (
    B_AEN_SIG,
    B_DEEP_PPT,
    B_DEEP_RATIO,
    B_DEPTH_FRAC,
    B_IPD_MULTI_PEAK,
    B_MAX_CADENCE_S,
    B_MIN_SPAN_PERIODS,
    B_NOISE_FRAC,
    B_RUWE,
    B_RV_NOISE_MULTIPLE,
    B_WINDOW_FILL,
    LONGP_MAX_SPAN_PERIODS,
    LONGP_REMOVED_SECTOR_FRACTION,
)

__all__ = ["deepest_window", "phase_independent_test", "long_period_window_test",
           "deep_event_hosts", "gaia_flag_digest"]


def deepest_window(ts: np.ndarray, fs: np.ndarray, win_days: float, cad_days: float) -> dict | None:
    """Deepest transit-length running window of a detrended sector, and the
    noise of a window mean.  ``None`` when no window holds enough cadences."""
    n = len(ts)
    if n < 20:
        return None
    idx = np.arange(n)
    j = np.searchsorted(ts, ts + win_days, side="right")
    cnt = j - idx
    csum = np.concatenate(([0.0], np.cumsum(fs)))
    expected = max(1.0, win_days / cad_days)
    ok = cnt >= B_WINDOW_FILL * expected
    if not ok.any():
        return None
    means = np.full(n, np.nan)
    means[ok] = (csum[j[ok]] - csum[idx[ok]]) / cnt[ok]
    depths = 1.0 - means
    i = int(np.nanargmax(depths))
    resid = fs - np.nanmedian(fs)
    sig_pt = float(1.4826 * np.nanmedian(np.abs(resid - np.nanmedian(resid))))
    n_typ = float(np.median(cnt[ok]))
    return {"deepest_depth_ppt": round(1000 * float(depths[i]), 3),
            "deepest_at_btjd": round(float(ts[i]), 4),
            "n_in_deepest_window": int(cnt[i]), "n_windows_tested": int(ok.sum()),
            "point_scatter_ppt": round(1000 * sig_pt, 3),
            "median_points_per_window": round(n_typ, 1),
            "window_noise_ppt": round(1000 * sig_pt / math.sqrt(max(n_typ, 1.0)), 4),
            "expected_points_per_window": round(expected, 1)}


def phase_independent_test(sectors: list[dict], period: float, depth_ppt: float,
                           t14_hours: float, survey_duration_days: float | None = None,
                           exact: bool = False) -> dict:
    """Stage B (i).

    A sector of <= 10-min cadence spanning >= 1.5 periods must contain a
    transit at some phase; if its deepest transit-length window is shallower
    than depth/3 while its window noise is below depth/5, the period is
    excluded in that sector.  One such sector kills.

    ``sectors`` is a list of ``{"sector", "author", "cadence_s", "time",
    "flux"}`` in the order they should be reported (the caller sorts).
    """
    win = t14_hours / 24.0
    win_survey = float(survey_duration_days) if survey_duration_days else None
    # ``exact`` (prompt 8): store the window unrounded so the record replays from
    # its own fields (prompt-7 finding 7); the rounded form is the p6.2/p7.0 record.
    res = {"t14_hours": (float(t14_hours) if exact else round(t14_hours, 3)),
           "window_days": (float(win) if exact else round(win, 5)),
           "depth_ppt": round(depth_ppt, 3),
           "depth_threshold_ppt": round(B_DEPTH_FRAC * depth_ppt, 3),
           "noise_threshold_ppt": round(B_NOISE_FRAC * depth_ppt, 3),
           "survey_duration_days": win_survey,
           "survey_duration_over_t14": None if not win_survey else round(win_survey / win, 3),
           "diagnostic": ("the decision uses the central-transit duration T14 as the window, as specified; "
                          "deepest_depth_ppt_at_survey_duration repeats the measurement with the survey's own "
                          "box duration and is recorded ONLY so that window dilution is visible, never used"),
           "sectors": []}
    for sd in sectors:
        s = int(sd["sector"])
        cad = float(sd.get("cadence_s", 1e9))
        ts, fs = np.asarray(sd["time"]), np.asarray(sd["flux"])
        span = float(ts.max() - ts.min()) if ts.size else 0.0
        row = {"sector": s, "author": sd.get("author"), "cadence_s": cad, "span_days": round(span, 2),
               "n_points": int(ts.size), "span_periods": round(span / period, 3)}
        if cad > B_MAX_CADENCE_S:
            row["tested"] = False
            row["why"] = f"cadence {cad:.0f} s > {B_MAX_CADENCE_S:.0f} s"
        elif span < B_MIN_SPAN_PERIODS * period:
            row["tested"] = False
            row["why"] = f"spans {span / period:.2f} periods < {B_MIN_SPAN_PERIODS}"
        else:
            w = deepest_window(ts, fs, win, cad / 86400.0)
            if w is None:
                row["tested"] = False
                row["why"] = "no window with enough cadences"
            else:
                row.update(w)
                if win_survey and abs(win_survey - win) / win > 0.05:
                    w2 = deepest_window(ts, fs, win_survey, cad / 86400.0)
                    row["deepest_depth_ppt_at_survey_duration"] = None if w2 is None else w2["deepest_depth_ppt"]
                    row["window_noise_ppt_at_survey_duration"] = None if w2 is None else w2["window_noise_ppt"]
                row["margin_over_threshold"] = round(w["deepest_depth_ppt"] / max(B_DEPTH_FRAC * depth_ppt, 1e-9), 3)
                shallow = w["deepest_depth_ppt"] < B_DEPTH_FRAC * depth_ppt
                sensitive = w["window_noise_ppt"] < B_NOISE_FRAC * depth_ppt
                row["tested"] = True
                row["excludes_period"] = bool(shallow and sensitive)
                row["why"] = (f"deepest window {w['deepest_depth_ppt']:.2f} ppt "
                              f"{'<' if shallow else '>='} {B_DEPTH_FRAC * depth_ppt:.2f} ppt; noise "
                              f"{w['window_noise_ppt']:.3f} ppt {'<' if sensitive else '>='} "
                              f"{B_NOISE_FRAC * depth_ppt:.2f} ppt")
        res["sectors"].append(row)
    tested = [r for r in res["sectors"] if r.get("tested")]
    excl = [r for r in tested if r.get("excludes_period")]
    deepest = [r["deepest_depth_ppt"] for r in tested if r.get("deepest_depth_ppt") is not None]
    alt = [r["deepest_depth_ppt_at_survey_duration"] for r in tested
           if r.get("deepest_depth_ppt_at_survey_duration") is not None]
    res.update({"n_sectors": len(res["sectors"]), "n_sectors_tested": len(tested),
                "n_sectors_excluding": len(excl), "excluding_sectors": [r["sector"] for r in excl],
                "median_deepest_window_ppt": None if not deepest else round(float(np.median(deepest)), 3),
                "median_deepest_window_ppt_at_survey_duration":
                    None if not alt else round(float(np.median(alt)), 3),
                "min_margin_over_threshold": None if not tested else min(
                    (r["margin_over_threshold"] for r in tested if r.get("margin_over_threshold") is not None),
                    default=None),
                "excluded": bool(excl)})
    return res


def long_period_window_test(events: list[dict], sector_spans: dict, period: float) -> dict:
    """Prompt-7 option 4: the long-period equivalent of the window test.

    Applies where **no** sector spans ``LONGP_MAX_SPAN_PERIODS`` periods, i.e.
    exactly where Stage B (i) has no power.  For every sector in which at least
    one predicted epoch was actually observed, ask whether the event rules
    removed all of them.  A candidate whose predicted-and-observed epochs are
    removed in more than half of those sectors is FLAGGED, never killed.

    ``sector_spans`` maps sector -> baseline span in days (used only to decide
    whether the test applies and to report it).
    """
    spans = {int(k): float(v) for k, v in (sector_spans or {}).items()}
    max_span_periods = max((v / period for v in spans.values()), default=0.0)
    applies = bool(max_span_periods < LONGP_MAX_SPAN_PERIODS)
    per_sector: dict[int, dict] = {}
    for e in events:
        if not e.get("observed"):
            continue
        s = int(e.get("sector", -1))
        d = per_sector.setdefault(s, {"sector": s, "n_observed": 0, "n_removed": 0, "epochs": []})
        d["n_observed"] += 1
        if e.get("excluded"):
            d["n_removed"] += 1
        d["epochs"].append({"n": e["n"], "tc_btjd": e["tc_btjd"], "excluded": bool(e.get("excluded")),
                            "classes": e.get("artefact_classes") or []})
    for d in per_sector.values():
        d["all_removed"] = bool(d["n_observed"] > 0 and d["n_removed"] == d["n_observed"])
    n_sectors = len(per_sector)
    n_all_removed = sum(1 for d in per_sector.values() if d["all_removed"])
    frac = (n_all_removed / n_sectors) if n_sectors else None
    return {
        "applies": applies,
        "why_applies": (f"no sector spans {LONGP_MAX_SPAN_PERIODS} periods "
                        f"(deepest {max_span_periods:.2f}), so Stage B (i) has no power here"
                        if applies else
                        f"a sector spans {max_span_periods:.2f} periods, so Stage B (i) can test the period"),
        "max_sector_span_periods": round(max_span_periods, 3),
        "n_sectors_with_an_observed_epoch": n_sectors,
        "n_sectors_with_every_observed_epoch_removed": n_all_removed,
        "fraction_of_sectors_fully_removed": None if frac is None else round(frac, 3),
        "threshold_fraction": LONGP_REMOVED_SECTOR_FRACTION,
        "flag": bool(applies and frac is not None and frac > LONGP_REMOVED_SECTOR_FRACTION),
        "per_sector": [per_sector[s] for s in sorted(per_sector)],
    }


def deep_event_hosts(rows: list[dict], depth_ppt: float, period: float) -> dict:
    """Stage B (iii): accepted candidates on this star deep enough to be a binary host.

    ``rows`` are the accepted-candidate rows of this star (``candidates.csv``),
    each with ``period_days``, ``depth_ppt`` and optionally ``verdict``/``snr``.
    """
    thr = min(B_DEEP_PPT, B_DEEP_RATIO * depth_ppt)   # "depth >= 30 ppt OR >= 5 x the candidate depth"
    deep = []
    for r in rows:
        try:
            d = float(r["depth_ppt"])
        except (TypeError, ValueError, KeyError):
            continue
        if d >= B_DEEP_PPT or d >= B_DEEP_RATIO * depth_ppt:
            deep.append({"period_days": round(float(r["period_days"]), 5), "depth_ppt": round(d, 2),
                         "verdict": r.get("verdict"), "snr": r.get("snr"),
                         "same_candidate": bool(abs(float(r["period_days"]) / period - 1) < 0.01)})
    deep = [d for d in deep if not d["same_candidate"]]
    deep.sort(key=lambda d: -d["depth_ppt"])
    return {"n_accepted_on_star": len(rows), "threshold_ppt": round(thr, 2),
            "n_deep": len(deep), "deepest_ppt": deep[0]["depth_ppt"] if deep else None,
            "examples": deep[:5], "flag": bool(deep)}


def gaia_flag_digest(neighbours: dict, depth_ppt: float) -> dict:
    """Stage B (ii): the Gaia / SIMBAD / VSX digest of a cached neighbours record.

    Flags only: a flagged candidate can reach HOLD at most, never SUBMIT.
    """
    g = neighbours.get("gaia", {}) or {}
    tg = g.get("target") or {}
    out = {"gaia_error": g.get("error"), "n_within_1arcmin": g.get("n_within_1arcmin"),
           "target_match": g.get("target_match"),
           "ruwe": tg.get("ruwe"), "ipd_frac_multi_peak": tg.get("ipd_frac_multi_peak"),
           "astrometric_excess_noise_sig": tg.get("astrometric_excess_noise_sig"),
           "phot_variable_flag": tg.get("phot_variable_flag"), "vari_class": tg.get("best_class_name"),
           "non_single_star": tg.get("non_single_star"), "duplicated_source": tg.get("duplicated_source"),
           "rv_amplitude_robust": tg.get("rv_amplitude_robust"), "rv_error": tg.get("radial_velocity_error"),
           "rv_n_transits": tg.get("rv_nb_transits"),
           "n_neighbours_could_produce_depth_within_3px":
               g.get("n_neighbours_that_could_produce_depth_total_eclipse_within_63arcsec"),
           "simbad_otypes": [o.get("otype") for o in (neighbours.get("simbad", {}) or {}).get("objects", [])[:5]],
           "n_vsx_within_1arcmin": (neighbours.get("vsx", {}) or {}).get("n_within_1arcmin"),
           "vsx_types": [o.get("Type") for o in (neighbours.get("vsx", {}) or {}).get("objects", [])[:5]]}
    # the Gaia RV amplitude only counts as evidence above its own noise expectation (P5's rule)
    rv, rve, rvn = out["rv_amplitude_robust"], out["rv_error"], out["rv_n_transits"]
    if rv is not None and rve and rvn:
        exp = B_RV_NOISE_MULTIPLE * float(rve) * math.sqrt(float(rvn))
        out["rv_expected_peak_to_peak"] = round(exp, 3)
        out["rv_above_noise_expectation"] = bool(float(rv) > exp)
    else:
        out["rv_expected_peak_to_peak"] = None
        out["rv_above_noise_expectation"] = None
    flags = []
    if out["ruwe"] is not None and out["ruwe"] > B_RUWE:
        flags.append(f"Gaia RUWE {out['ruwe']:.2f} > {B_RUWE}")
    if out["ipd_frac_multi_peak"] is not None and out["ipd_frac_multi_peak"] > B_IPD_MULTI_PEAK:
        flags.append(f"ipd_frac_multi_peak {out['ipd_frac_multi_peak']:.0f}% > {B_IPD_MULTI_PEAK:.0f}%")
    if out["astrometric_excess_noise_sig"] is not None and out["astrometric_excess_noise_sig"] > B_AEN_SIG:
        flags.append(f"astrometric_excess_noise_sig {out['astrometric_excess_noise_sig']:.1f} > {B_AEN_SIG}")
    if (out["non_single_star"] or 0):
        flags.append(f"Gaia non_single_star = {out['non_single_star']}")
    if str(out["phot_variable_flag"] or "").upper() == "VARIABLE":
        flags.append(f"Gaia phot_variable_flag VARIABLE ({out['vari_class'] or 'class -'})")
    if (out["n_neighbours_could_produce_depth_within_3px"] or 0) > 0:
        flags.append(f"{out['n_neighbours_could_produce_depth_within_3px']} neighbour(s) within 3 px "
                     f"bright enough to make the depth if totally eclipsed")
    if out["rv_above_noise_expectation"]:
        flags.append(f"Gaia RV amplitude {rv} > noise expectation {out['rv_expected_peak_to_peak']}")
    if (out["n_vsx_within_1arcmin"] or 0) > 0:
        flags.append(f"VSX entry within 1 arcmin ({', '.join(str(x) for x in out['vsx_types'] if x)})")
    out["flags"] = flags
    return out
