"""Prompt 6: re-vet all 405 P4 survivors under the audit rules of prompt 5.

Stages, each writing one JSON per candidate under ``data/survey/p6/stage<X>/`` and one CSV
with the decision and a one-line reason for every candidate that entered the stage:

    stageA  events under the survey (and packet, and forced-TLS) ephemerides; removal rules
            exactly as ``docs/AUDIT.md`` section 1 step 3; kept-event statistics.
    stageB  star-level: the phase-independent deepest-window test (kills), the Gaia DR3 cone
            and the deep-event-host check (flag only, capping the verdict at HOLD).
    stageC  blind TLS 0.5-110 d on the Stage B survivors.
    stageD  the full prompt-5 audit of every Stage C PASS.

    census  the artefact census over all 405 Stage A records.
    funnel  405 -> A -> B -> C -> D counts into ``funnel_p6.json``.

Every threshold is named once in ``tesshunter.audit_rules`` and copied into every record,
which also carries ``rules_version`` so that a mixed-vintage directory is detectable.  Since
prompt 7 the rules themselves live in the package - ``tesshunter.audit_prep``,
``tesshunter.event_vet``, ``tesshunter.star_vet``, ``tesshunter.secondary`` - and
``scripts/audit_p5.py`` drives them; this script slices the population and decides.

The rule set is ``audit_rules.LEGACY_RULES`` (``p6.2``) by default, exactly what prompt 6 ran,
so the 405 Stage A records reproduce; ``--rules p7.0`` selects the prompt-7 set.

Nothing here submits anything anywhere.  The pipeline finds candidates.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

OUT_ROOT = REPO / "data" / "survey" / "p6"
LC_ROOT = REPO / "data" / "survey" / "audit_lc"
# The candidate tables.  Prompt-4 by default (so prompts 6 and 7 reproduce); prompt 8's driver
# points them at its own tables with ``set_population``.
SURVIVORS_CSV = REPO / "data" / "survey" / "p4" / "survivors.csv"
CANDIDATES_CSV = REPO / "data" / "survey" / "p4" / "candidates.csv"
PY = sys.executable


def set_population(out_root=None, survivors_csv=None, candidates_csv=None, packets_dir=None) -> None:
    """Re-point the driver at another population (prompt 8): its output root, its survivor and
    accepted-candidate tables, and the packet directory ``audit_p5`` reads fits from."""
    global OUT_ROOT, SURVIVORS_CSV, CANDIDATES_CSV
    if out_root is not None:
        OUT_ROOT = Path(out_root)
    if survivors_csv is not None:
        SURVIVORS_CSV = Path(survivors_csv)
    if candidates_csv is not None:
        CANDIDATES_CSV = Path(candidates_csv)
    import audit_p5 as A
    A.set_population(survivors_csv=survivors_csv, packets_dir=packets_dir)

# -- thresholds: named once in tesshunter.audit_rules, re-exported here so the module constants
#    the prompt-6 drivers and reports refer to keep working ------------------
sys.path.insert(0, str(REPO / "src"))
from tesshunter import audit_rules as R                       # noqa: E402
from tesshunter.event_vet import ARTEFACT_CLASSES, classes_of  # noqa: E402
from tesshunter.event_vet import stagea_criteria as _stagea_criteria  # noqa: E402
from tesshunter.star_vet import (                             # noqa: E402
    deep_event_hosts,
    deepest_window,
    gaia_flag_digest,
    long_period_window_test,
    phase_independent_test,
)

RULES = R.LEGACY_RULES.version
RULE_SET = R.LEGACY_RULES
# Stage A
A_MIN_KEPT = R.A_MIN_KEPT
A_MIN_SNR = R.A_MIN_SNR
A_MAX_TOP_SHARE = R.A_MAX_TOP_SHARE
A_MIN_SNR_WO_TOP = R.A_MIN_SNR_WO_TOP
A_DEPTH_LO = R.A_DEPTH_LO
A_DEPTH_HI = R.A_DEPTH_HI
A_P_CONST = R.A_P_CONST
# Stage B
B_MAX_CADENCE_S = R.B_MAX_CADENCE_S
B_MIN_SPAN_PERIODS = R.B_MIN_SPAN_PERIODS
B_DEPTH_FRAC = R.B_DEPTH_FRAC
B_NOISE_FRAC = R.B_NOISE_FRAC
B_WINDOW_FILL = R.B_WINDOW_FILL
B_RUWE = R.B_RUWE
B_IPD_MULTI_PEAK = R.B_IPD_MULTI_PEAK
B_AEN_SIG = R.B_AEN_SIG
B_DEEP_PPT = R.B_DEEP_PPT
B_DEEP_RATIO = R.B_DEEP_RATIO
# Stage C
C_SDE = R.C_SDE
C_TOL = R.C_TOL
C_ALIAS_P_CONST = R.C_ALIAS_P_CONST
C_OVERSAMPLING_DEFAULT = R.C_OVERSAMPLING_DEFAULT
C_OVERSAMPLING_MANY = R.C_OVERSAMPLING_MANY
C_MANY_STARS = R.C_MANY_STARS

THRESHOLDS = {
    "stageA": {"min_kept_events": A_MIN_KEPT, "min_kept_event_snr": A_MIN_SNR,
               "max_top_event_share_of_snr2": A_MAX_TOP_SHARE, "min_snr_without_top_event": A_MIN_SNR_WO_TOP,
               "kept_depth_over_survey_depth": [A_DEPTH_LO, A_DEPTH_HI], "min_p_const": A_P_CONST,
               "flux": "wotan-detrended corrected flux (det_kept); sap_kept recorded alongside",
               "ephemeris_choice": "the ephemeris passing the most criteria, ties broken by kept-event SNR"},
    "stageB": {"max_cadence_s": B_MAX_CADENCE_S, "min_span_periods": B_MIN_SPAN_PERIODS,
               "window_depth_fraction": B_DEPTH_FRAC, "window_noise_fraction": B_NOISE_FRAC,
               "window_fill_fraction": B_WINDOW_FILL, "window_length": "expected_t14_hours (central transit)",
               "ruwe": B_RUWE, "ipd_frac_multi_peak_pct": B_IPD_MULTI_PEAK, "aen_sig": B_AEN_SIG,
               "deep_event_ppt": B_DEEP_PPT, "deep_event_ratio": B_DEEP_RATIO},
    "stageC": {"sde": C_SDE, "period_tolerance": C_TOL, "alias_min_p_const": C_ALIAS_P_CONST,
               "oversampling_default": C_OVERSAMPLING_DEFAULT, "oversampling_if_many": C_OVERSAMPLING_MANY,
               "many_stars": C_MANY_STARS},
}


def set_rules(rules) -> None:
    """Select the rule set for this driver and for ``audit_p5``."""
    global RULES, RULE_SET
    if isinstance(rules, str):
        rules = {"p6.2": R.LEGACY_RULES, "p7.0": R.DEFAULT_RULES, "p8.0": R.P8_RULES}[rules]
        if rules is None:
            raise SystemExit("p8.0 is not decided yet (audit_rules.P8_RULES is None)")
    RULE_SET = rules
    RULES = rules.version
    THRESHOLDS["stageA"] = dict(THRESHOLDS["stageA"], min_p_const=rules.depth_consistency_p_min)
    import audit_p5 as A
    A.set_rules(rules)


# The artefact classes and `classes_of` are tesshunter.event_vet's (imported above): a removal
# reason string is mapped back to the rule that wrote it, so the census never re-runs a rule.


# ── the population ───────────────────────────────────────────────────────────
def survivors() -> list[dict]:
    rows = list(csv.DictReader(open(SURVIVORS_CSV, newline="", encoding="utf-8")))
    return sorted(rows, key=lambda r: int(r["rank"]))


def jobs() -> list[dict]:
    """One job per survivor: the identity, the survey ephemeris and the survey depth."""
    out = []
    for r in survivors():
        out.append({"rank": int(r["rank"]), "tic_id": int(r["tic_id"]), "planet_num": int(r["planet_num"]),
                    "period": float(r["period_days"]), "epoch_btjd": float(r["epoch_btjd"]),
                    "duration_days": float(r["duration_days"]), "depth_ppt": float(r["depth_ppt"]),
                    "stitch_snr": float(r["stitch_snr"]), "stitch_n_transits": int(float(r["stitch_n_transits"])),
                    "n_units": int(float(r["n_units"])), "tmag": float(r["tmag"]),
                    "radius_rsun": r["radius_rsun"], "mass_msun": r["mass_msun"],
                    "ra_deg": float(r["ra_deg"]), "dec_deg": float(r["dec_deg"])})
    return out


def kkey(tic: int, period: float) -> str:
    return f"tic{int(tic)}_P{float(period):.4f}"


def have_lc(tic: int) -> bool:
    return (LC_ROOT / f"tic{tic}" / "index.json").exists()


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def accepted_rows(tic: int) -> list[dict]:
    """Every accepted candidate row of this star (``candidates.csv``)."""
    return [r for r in csv.DictReader(open(CANDIDATES_CSV, newline="", encoding="utf-8"))
            if int(r["tic_id"]) == tic]


def deep_candidates(tic: int, depth_ppt: float, period: float) -> dict:
    """Stage B (iii), from ``tesshunter.star_vet.deep_event_hosts``: accepted candidates on this
    star deep enough to be a binary host."""
    return deep_event_hosts(accepted_rows(tic), depth_ppt, period)


# ─────────────────────────────────────────────────────────────────────────────
# Stage A: events under every available ephemeris
# ─────────────────────────────────────────────────────────────────────────────
def stagea_criteria(dk: dict, survey_depth_ppt: float) -> dict:
    """The six Stage A criteria, from ``tesshunter.event_vet.stagea_criteria``."""
    return _stagea_criteria(dk, survey_depth_ppt, p_min=RULE_SET.depth_consistency_p_min)


def compact_events(rec: dict) -> list[dict]:
    """The per-event table kept in the Stage A record: every observed epoch and why it went."""
    out = []
    for e in rec["events"]:
        if not e.get("observed"):
            out.append({"n": e["n"], "tc_btjd": e["tc_btjd"], "observed": False,
                        "reason": e.get("reason", "not observed")})
            continue
        out.append({"n": e["n"], "tc_btjd": e["tc_btjd"], "sector": e["sector"], "author": e["author"],
                    "cadence_s": e["cadence_s"], "observed": True, "coverage": e["coverage_in_transit"],
                    "det_depth_ppt": e["det_depth_ppt"], "det_depth_err_ppt": e["det_depth_err_ppt"],
                    "sap_depth_ppt": e["sap_depth_ppt"], "sap_depth_err_ppt": e["sap_depth_err_ppt"],
                    "edge_distance_days": e["edge_distance_days"], "pdc_gap_distance_days": e.get("pdc_gap_distance_days"),
                    "desat": e["desat_within_one_duration"], "q_frac": e["frac_in_transit_quality_flagged"],
                    "straylight_frac": e.get("frac_straylight_flagged_within_one_duration"),
                    "ramp_over_depth": e["baseline_change_across_event_over_depth"],
                    "bkg_over_sector_median": e.get("bkg_in_over_sector_median"),
                    "excluded": e["excluded"], "exclusion_reasons": e["exclusion_reasons"],
                    "artefact_classes": classes_of(e["exclusion_reasons"])})
    return out


def strongest_event(rec: dict) -> dict:
    """The observed event carrying the most (depth/error)^2 in the detrended flux, and its fate.

    "Carried by" an artefact class, in the census, means this event was removed by that rule.
    """
    best, best_w = None, -np.inf
    for e in rec["events"]:
        if not e.get("observed") or e.get("det_depth_ppt") is None or not e.get("det_depth_err_ppt"):
            continue
        d, s = e["det_depth_ppt"], e["det_depth_err_ppt"]
        w = (d / s) ** 2 * (1 if d > 0 else -1)
        if w > best_w:
            best, best_w = e, w
    if best is None:
        return {"found": False}
    return {"found": True, "n": best["n"], "tc_btjd": best["tc_btjd"], "sector": best["sector"],
            "author": best["author"], "det_depth_ppt": best["det_depth_ppt"],
            "det_depth_err_ppt": best["det_depth_err_ppt"], "sap_depth_ppt": best["sap_depth_ppt"],
            "snr2": round(float(best_w), 1), "excluded": best["excluded"],
            "exclusion_reasons": best["exclusion_reasons"], "artefact_classes": classes_of(best["exclusion_reasons"])}


def forced_usable(fo: dict) -> bool:
    """A narrow TLS that fits no transit at all returns a degenerate result (null period / T0 /
    counts).  Such a run yields no ephemeris, so the candidate is examined under the survey (and
    packet) ephemerides only, and the record says so."""
    f = (fo or {}).get("forced") or {}
    return all(f.get(k) is not None for k in ("period", "T0_btjd", "duration_days"))


def stagea_one(job: dict, threads: int = 1, force: bool = False) -> dict:
    import audit_p5 as A
    A.set_roots(OUT_ROOT, LC_ROOT)
    tic, period = job["tic_id"], job["period"]
    k = kkey(tic, period)
    out_path = OUT_ROOT / "stageA" / f"{k}.json"
    if out_path.exists() and not force:
        r = A.jload(out_path)
        # a cached ERROR is retried on a re-run; only settled decisions short-circuit
        if A.cache_matches(r) and r.get("decision") in ("PASS", "FAIL"):
            return r
    t0 = time.perf_counter()
    rec: dict = {"key": k, "tic_id": tic, "planet_num": job["planet_num"], "rank": job["rank"],
                 "generated_utc": utc(), "rules_version": RULES, "thresholds": THRESHOLDS["stageA"],
                 "survey": {kk: job[kk] for kk in ("period", "epoch_btjd", "duration_days", "depth_ppt",
                                                   "stitch_snr", "stitch_n_transits", "n_units", "tmag")}}
    if not have_lc(tic):
        # Stage 0 has not reached this star yet: nothing is written, so a re-run picks it up.
        rec.update({"decision": "SKIP", "reason": "no light curves in the store for this star", "seconds": 0.0})
        return rec
    try:
        prep = A.prepare_step(tic, period)
        fo = A.forced_step(tic, period, threads=threads)
        tls_ok = forced_usable(fo)
        has_packet = bool(A._packet_fit(tic, period))
        sources = ["survey"] + (["tls"] if tls_ok else []) + (["packet"] if has_packet else [])
        per: dict = {}
        for src in sources:
            r = A.events_step(tic, period, source=src)
            s = r["summary"]
            crit = stagea_criteria(s["det_kept"], job["depth_ppt"])
            per[src] = {"ephemeris": s["ephemeris"], "n_predicted_in_span": s["n_predicted_in_span"],
                        "n_observed": s["n_observed"], "n_excluded": s["n_excluded"], "n_kept": s["n_kept"],
                        "det_all": s["det_all"], "det_kept": s["det_kept"], "sap_kept": s["sap_kept"],
                        "audit_flags": s["flags"], **crit,
                        "strongest_event": strongest_event(r), "events": compact_events(r)}
        chosen = max(sources, key=lambda sc: (per[sc]["n_criteria_passed"], per[sc]["kept_snr"] or -1e9))
        ch = per[chosen]
        rec.update({
            "prepare": {kk: prep[kk] for kk in ("n_unbinned", "n_binned", "baseline_days", "wotan",
                                                "n_isolated_clipped", "n_isolated_bins_clipped",
                                                "deep_clip_threshold_ppt", "n_deep_clipped",
                                                "R_star", "M_star", "expected_t14_hours_b0")},
            "forced_tls": {kk: fo["forced"].get(kk) for kk in ("period", "T0_btjd", "duration_days", "depth",
                                                              "SDE", "distinct_transit_count",
                                                              "odd_even_mismatch")},
            "ephemerides_examined": sources, "has_p4_packet": has_packet,
            "forced_tls_usable": tls_ok,
            "per_ephemeris": per, "chosen_ephemeris": chosen,
            "criteria": ch["criteria"], "n_criteria_passed": ch["n_criteria_passed"],
            "decision": "PASS" if ch["all_passed"] else "FAIL",
            "deep_event_host": deep_candidates(tic, job["depth_ppt"], period),
        })
        failed = [c for c, ok in ch["criteria"].items() if not ok]
        rec["reason"] = (f"{chosen} ephemeris, {ch['n_kept']} kept events, SNR {ch['kept_snr']}, "
                         f"top share {ch['top_event_share']}, SNR w/o top {ch['snr_without_top']}, "
                         f"depth {ch['kept_depth_ppt']} ppt = {ch['depth_over_survey_depth']}x survey, "
                         f"p_const {None if ch['p_const'] is None else f'{ch['p_const']:.2g}'}"
                         + (f"; fails {', '.join(failed)}" if failed else "; all six criteria pass"))
    except Exception as exc:
        rec.update({"decision": "ERROR", "reason": f"{type(exc).__name__}: {exc}"[:400]})
    rec["seconds"] = round(time.perf_counter() - t0, 1)
    A.jdump(out_path, rec)
    return rec


# ─────────────────────────────────────────────────────────────────────────────
# Stage B: star-level tests on the Stage A survivors
# ─────────────────────────────────────────────────────────────────────────────
def sector_series(A, tic: int, period: float) -> list[dict]:
    """The prepared per-sector detrended series, in sector order, for the window test."""
    z = np.load(OUT_ROOT / "tls" / f"{kkey(tic, period)}_lc.npz")
    t_, f_, sec = z["time_unbinned"], z["flux_unbinned"], z["sector_unbinned"]
    prods = {int(p["sector"]): p for p in A.choose_per_sector(A.load_products(tic))}
    out = []
    for s in sorted({int(x) for x in sec}):
        p = prods.get(s, {})
        m = sec == s
        out.append({"sector": s, "author": p.get("author"), "cadence_s": float(p.get("cadence_s", 1e9)),
                    "time": t_[m], "flux": f_[m]})
    return out


def phase_independent(A, tic: int, period: float, depth_ppt: float, t14_hours: float,
                      survey_duration_days: float | None = None) -> dict:
    """Stage B (i), from ``tesshunter.star_vet.phase_independent_test``.  A sector of <= 10-min
    cadence spanning >= 1.5 periods must contain a transit at some phase; if its deepest
    transit-length window is shallower than depth/3 while its window noise is below depth/5, the
    period is excluded in that sector.  One such sector kills."""
    return phase_independent_test(sector_series(A, tic, period), period, depth_ppt, t14_hours,
                                  survey_duration_days, exact=RULE_SET.exact_t14_record)


def gaia_flags(nb: dict, depth_ppt: float) -> dict:
    """Stage B (ii), from ``tesshunter.star_vet.gaia_flag_digest``.  Flags only: a flagged
    candidate can reach HOLD at most, never SUBMIT."""
    return gaia_flag_digest(nb, depth_ppt)


def stageb_one(job: dict, force: bool = False) -> dict:
    import audit_p5 as A
    A.set_roots(OUT_ROOT, LC_ROOT)
    tic, period = job["tic_id"], job["period"]
    k = kkey(tic, period)
    out_path = OUT_ROOT / "stageB" / f"{k}.json"
    if out_path.exists() and not force:
        r = A.jload(out_path)
        # a cached ERROR is retried on a re-run; only settled decisions short-circuit
        if A.cache_matches(r) and r.get("decision") in ("PASS", "FAIL"):
            return r
    t0 = time.perf_counter()
    rec = {"key": k, "tic_id": tic, "rank": job["rank"], "survey_period": period,
           "survey_depth_ppt": job["depth_ppt"], "generated_utc": utc(), "rules_version": RULES,
           "thresholds": THRESHOLDS["stageB"]}
    try:
        sp = A.stellar_for(tic, period)
        rec["phase_independent"] = phase_independent(A, tic, period, job["depth_ppt"],
                                                     sp["expected_t14_hours_b0"], job.get("duration_days"))
        rec["gaia"] = gaia_flags(A.neighbours_step(tic), job["depth_ppt"])
        rec["deep_event_host"] = deep_candidates(tic, job["depth_ppt"], period)
        pi = rec["phase_independent"]
        flags = list(rec["gaia"]["flags"])
        if rec["deep_event_host"]["flag"]:
            d = rec["deep_event_host"]
            flags.append(f"same star carries {d['n_deep']} accepted candidate(s) up to {d['deepest_ppt']} ppt "
                         f"(>= {d['threshold_ppt']} ppt): possible binary host")
        rec["flags"] = flags
        if pi["excluded"]:
            rec["decision"] = "FAIL"
            s = [r for r in pi["sectors"] if r.get("excludes_period")][0]
            rec["reason"] = (f"period excluded by sector {s['sector']} ({s['author']}, {s['cadence_s']:.0f} s, "
                             f"{s['span_periods']:.2f} periods): {s['why']}")
            rec["max_verdict"] = "KILL"
        else:
            rec["decision"] = "PASS"
            rec["max_verdict"] = "HOLD" if flags else "SUBMIT"
            rec["reason"] = (f"{pi['n_sectors_tested']} sector(s) could test the period phase-independently, "
                             f"none excludes it; " + (f"{len(flags)} star-level flag(s): " + "; ".join(flags)
                                                      if flags else "no star-level flags"))
    except Exception as exc:
        rec.update({"decision": "ERROR", "reason": f"{type(exc).__name__}: {exc}"[:400], "max_verdict": "KILL"})
    rec["seconds"] = round(time.perf_counter() - t0, 1)
    A.jdump(out_path, rec)
    return rec


# ─────────────────────────────────────────────────────────────────────────────
# Stage C: blind TLS
# ─────────────────────────────────────────────────────────────────────────────
def alias_depths_consistent(blind: dict) -> dict:
    """A 2:1 or 1:2 alias passes only if TLS's per-transit depths at that period are consistent."""
    dd = blind.get("transit_depths") or []
    ee = blind.get("transit_depths_uncertainties") or []
    pairs = [(a, b) for a, b in zip(dd, ee) if a is not None and b is not None and b > 0]
    n = len(pairs)
    if n < 3:
        return {"n": int(n), "p_const": None, "consistent": False, "why": "fewer than 3 usable per-transit depths"}
    d = 1.0 - np.array([a for a, _ in pairs], dtype=float)
    e = np.array([b for _, b in pairs], dtype=float)
    w = 1.0 / e ** 2
    mean = float(np.sum(w * d) / np.sum(w))
    chi2 = float(np.sum(((d - mean) / e) ** 2))
    dof = n - 1
    from scipy import stats as sst
    p = float(sst.chi2.sf(chi2, dof))
    return {"n": int(n), "weighted_mean_depth_ppt": round(1000 * mean, 3), "chi2": round(chi2, 1), "dof": dof,
            "p_const": p, "odd_even_mismatch": blind.get("odd_even_mismatch"),
            "consistent": bool(p >= C_ALIAS_P_CONST),
            "why": f"per-transit depths about their mean: chi2 {chi2:.1f}/{dof} dof, p {p:.2g}"}


def stagec_one(job: dict, threads: int = 20, oversampling: int = C_OVERSAMPLING_DEFAULT, force: bool = False) -> dict:
    import audit_p5 as A
    A.set_roots(OUT_ROOT, LC_ROOT)
    tic, period = job["tic_id"], job["period"]
    k = kkey(tic, period)
    out_path = OUT_ROOT / "stageC" / f"{k}.json"
    if out_path.exists() and not force:
        r = A.jload(out_path)
        # a cached ERROR is retried on a re-run; only settled decisions short-circuit
        if A.cache_matches(r) and r.get("decision") in ("PASS", "FAIL"):
            return r
    t0 = time.perf_counter()
    rec = {"key": k, "tic_id": tic, "rank": job["rank"], "survey_period": period,
           "survey_depth_ppt": job["depth_ppt"], "generated_utc": utc(), "rules_version": RULES,
           "thresholds": dict(THRESHOLDS["stageC"], oversampling_used=oversampling)}
    try:
        r = A.tls_step(tic, period, threads, oversampling, 0.5, 110.0, 30.0, None, force=force)
        b = r["blind"]
        rec["blind"] = {kk: b.get(kk) for kk in ("period", "T0_btjd", "duration_days", "depth", "SDE", "snr",
                                                  "FAP", "distinct_transit_count", "odd_even_mismatch",
                                                  "SDE_at_survey_period_max_1pct", "SDE_rank_of_survey_period",
                                                  "match")}
        rec["peaks"] = b["peaks"][:5]
        rec["audit_verdict_tls"] = r["verdict_tls"]
        rec["inputs"] = {kk: r["inputs"][kk] for kk in ("n_binned", "baseline_days", "n_isolated_clipped",
                                                        "n_isolated_bins_clipped", "n_deep_clipped",
                                                        "deep_clip_threshold_ppt", "oversampling_factor")}
        m, strong = b["match"], b["SDE"] >= C_SDE
        same = bool(m["same_period_1pct"])
        alias21 = bool(m["alias_1pct"] and m["closest_alias"] in ("2:1", "1:2") and not same)
        if same and strong:
            rec["decision"] = "PASS"
            rec["reason"] = f"strongest peak {b['period']:.5f} d is within 1% of the survey period at SDE {b['SDE']:.1f}"
        elif alias21 and strong:
            cons = alias_depths_consistent(b)
            rec["alias_depth_consistency"] = cons
            rec["decision"] = "PASS" if cons["consistent"] else "FAIL"
            rec["reason"] = (f"strongest peak {b['period']:.5f} d is an exact {m['closest_alias']} alias at "
                             f"SDE {b['SDE']:.1f}; {cons['why']} -> "
                             f"{'consistent' if cons['consistent'] else 'inconsistent'}")
        else:
            rec["decision"] = "FAIL"
            rec["reason"] = (f"strongest peak {b['period']:.5f} d (SDE {b['SDE']:.1f}, alias {m['closest_alias']} "
                             f"at {m['closest_alias_frac']:.3f}); SDE within 1% of the survey period "
                             f"{b['SDE_at_survey_period_max_1pct']}")
        rec["timing_s"] = r["timing_s"]
    except Exception as exc:
        rec.update({"decision": "ERROR", "reason": f"{type(exc).__name__}: {exc}"[:400]})
    rec["seconds"] = round(time.perf_counter() - t0, 1)
    A.jdump(out_path, rec)
    return rec


# -----------------------------------------------------------------------------
# Stage D: the full prompt-5 audit of every Stage C PASS
# -----------------------------------------------------------------------------
def staged_one(job: dict, xm: dict, force: bool = False) -> dict:
    """Events under all three ephemerides, Gaia/SIMBAD/VSX, the hard stop and the all-transit fit.

    The verdict written here is PROVISIONAL: it is what the rules alone say.  The final
    SUBMIT / HOLD / KILL is stamped by the ``verdict`` sub-command after the P4 survivor row,
    packet and case file have been read, and is the one that reaches ``docs/REVET.md``.
    """
    import audit_p5 as A
    A.set_roots(OUT_ROOT, LC_ROOT)
    tic, period = job["tic_id"], job["period"]
    k = kkey(tic, period)
    out_path = OUT_ROOT / "stageD" / f"{k}.json"
    if out_path.exists() and not force:
        r = A.jload(out_path)
        if A.cache_matches(r) and r.get("verdict"):
            return r
    t0 = time.perf_counter()
    rec = {"key": k, "tic_id": tic, "rank": job["rank"], "survey_period": period,
           "survey_depth_ppt": job["depth_ppt"], "generated_utc": utc(), "rules_version": RULES}
    try:
        # 1. every event under every ephemeris we have
        has_packet = bool(A._packet_fit(tic, period))
        tls_ok = forced_usable(A.forced_step(tic, period))
        sources = ["survey"] + (["tls"] if tls_ok else []) + (["packet"] if has_packet else [])
        ev = {}
        for src in sources:
            r = A.events_step(tic, period, source=src, force=force)
            ev[src] = {kk: r["summary"][kk] for kk in ("ephemeris", "n_observed", "n_excluded", "n_kept",
                                                        "det_all", "det_kept", "sap_kept", "flags")}
            ev[src]["events"] = compact_events(r)
        rec["events"] = ev
        rec["has_p4_packet"] = has_packet
        rec["forced_tls_usable"] = tls_ok
        # 2. the sky: Gaia DR3, SIMBAD, VSX
        nb = A.neighbours_step(tic)
        rec["neighbours_summary"] = nb.get("summary")
        rec["gaia"] = gaia_flags(nb, job["depth_ppt"])
        rec["simbad"] = (nb.get("simbad") or {}).get("objects", [])[:10]
        rec["vsx"] = (nb.get("vsx") or {}).get("objects", [])[:10]
        # 3. the hard stop, catalogs refreshed in this session
        rec["crossmatch"] = {"catalog_stamp": xm.get("catalog_stamp"),
                             "star": (xm.get("per_star", {}) or {}).get(str(tic), {})}
        # 4. the all-transit fit (untested code in prompt 5: recorded, never allowed to abort the audit)
        try:
            fit = A.fit_step(tic, period, force=force)
            rec["fit"] = {"adopted": fit["adopted"], "density_prior_adopted": fit["density_prior_adopted"],
                          "delta_chi2_prior_minus_free": fit["delta_chi2_prior_minus_free"],
                          "delta_chi2_vs_flat": fit["adopted"].get("delta_chi2_vs_flat"),
                          "beta_red_noise": fit["data"]["beta_red_noise"], "odd_even": fit["odd_even"],
                          "stellar": fit["stellar"], "uncertainty_issues": fit.get("uncertainty_issues", [])}
            rec["ctoi_fields_path"] = None
        except Exception as exc:
            rec["fit"] = {"error": f"{type(exc).__name__}: {exc}"[:400]}
        # 5. stage records carried forward
        for st in ("A", "B", "C"):
            f = OUT_ROOT / f"stage{st}" / f"{k}.json"
            if f.exists():
                r = A.jload(f)
                rec[f"stage{st}"] = {"decision": r.get("decision"), "reason": r.get("reason"),
                                     "max_verdict": r.get("max_verdict")}
        # 6. what the rules alone say
        rec["provisional_verdict"], rec["provisional_reason"] = provisional_verdict(rec)
        rec["verdict"] = None
        rec["reason"] = "awaiting the human-read verdict (revet_p6.py verdict ...)"
    except Exception as exc:
        rec.update({"verdict": "ERROR", "reason": f"{type(exc).__name__}: {exc}"[:400]})
    rec["seconds"] = round(time.perf_counter() - t0, 1)
    A.jdump(out_path, rec)
    return rec


def provisional_verdict(rec: dict) -> tuple[str, str]:
    """What the rules alone say before the P4 material is read."""
    xm = ((rec.get("crossmatch") or {}).get("star") or {}).get("status")
    flags = (rec.get("gaia") or {}).get("flags") or []
    stb = (rec.get("stageB") or {}).get("max_verdict")
    if xm and xm != "CLEAN":
        return "KILL", f"hard stop: the star is not clean ({xm})"
    fit = rec.get("fit") or {}
    if fit.get("error"):
        return "HOLD", f"the all-transit fit did not run ({fit['error'][:120]}); a fit is needed before any submission"
    dchi2 = (fit.get("adopted") or {}).get("delta_chi2_vs_flat")
    if dchi2 is not None and dchi2 < 25:
        return "KILL", f"the all-transit fit improves on a flat line by only delta chi2 {dchi2:.1f}"
    if fit.get("uncertainty_issues"):
        return "HOLD", "all-transit fit needs uncertainty assessment: " + "; ".join(fit["uncertainty_issues"])
    if flags or stb == "HOLD":
        return "HOLD", "Stage B star-level flags stand: " + ("; ".join(flags) if flags else "see the Stage B record")
    return "SUBMIT", "every stage passed and no star-level flag stands"


def staged(force: bool = False, refresh: bool = True) -> None:
    import audit_p5 as A
    A.set_roots(OUT_ROOT, LC_ROOT)
    js = eligible("D")
    (OUT_ROOT / "stageD").mkdir(parents=True, exist_ok=True)
    if not js:
        print("no Stage C PASS: Stage D is empty, nothing to audit and nothing to submit", flush=True)
        (OUT_ROOT / "stageD_empty.json").write_text(json.dumps(
            {"generated_utc": utc(), "rules_version": RULES, "n_stage_c_pass": 0,
             "statement": "No candidate reached Stage D; the ordered list to submit is empty."}, indent=1),
            encoding="utf-8")
        return
    tics = sorted({j["tic_id"] for j in js})
    print(f"Stage D: {len(js)} candidates on {len(tics)} stars; refreshing the hard-stop catalogs", flush=True)
    xm = A.crossmatch_step(tics, refresh=refresh)
    for job in js:
        r = staged_one(job, xm, force=force)
        print(f"rank {job['rank']:>3} {r['key']:<28} provisional {r.get('provisional_verdict')} "
              f"| {r.get('provisional_reason', '')[:160]} | {r['seconds']} s", flush=True)
    write_stage_csv("D")


def stamp_verdict(tic: int, period: float, verdict: str, reason: str, note: str | None = None) -> dict:
    """The final verdict, stamped after the P4 survivor row, packet and case file were read.

    A SUBMIT also writes ``ctoi_fields.json`` under ``docs/packets/audit_p6/``; the human fills
    the ExoFOP tag and submits by hand.  Nothing here submits anything anywhere.
    """
    import audit_p5 as A
    A.set_roots(OUT_ROOT, LC_ROOT)
    k = kkey(tic, period)
    path = OUT_ROOT / "stageD" / f"{k}.json"
    rec = A.jload(path)
    rec["verdict"] = verdict
    rec["reason"] = reason
    rec["verdict_stamped_utc"] = utc()
    if verdict == "SUBMIT":
        p = A.write_ctoi_fields(tic, period, note or reason)
        rec["ctoi_fields_path"] = str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p)
    A.jdump(path, rec)
    print(f"{k}: {verdict} | {reason}")
    if rec.get("ctoi_fields_path"):
        print("ctoi fields ->", rec["ctoi_fields_path"])
    write_stage_csv("D")
    return rec


# ─────────────────────────────────────────────────────────────────────────────
# slice runners (one top-level subprocess per slice, so TLS may make its own pool)
# ─────────────────────────────────────────────────────────────────────────────
STAGE_FN = {"A": stagea_one, "B": stageb_one, "C": stagec_one}


def eligible(stage: str) -> list[dict]:
    """The jobs that enter a stage: all 405 for A, the previous stage's PASSes after that."""
    js = jobs()
    if stage == "A":
        return js
    prev = {"B": "A", "C": "B", "D": "C"}[stage]
    ok = set()
    for p in (OUT_ROOT / f"stage{prev}").glob("*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        if r.get("decision") == "PASS":
            ok.add(r["key"])
    return [j for j in js if kkey(j["tic_id"], j["period"]) in ok]


def run_slice(stage: str, index: int, nslices: int, threads: int, oversampling: int, force: bool) -> None:
    js = eligible(stage)
    mine = js[index::nslices]
    fn = STAGE_FN[stage]
    print(f"slice {index}/{nslices}: {len(mine)} of {len(js)} candidates, stage {stage}, threads {threads}", flush=True)
    t0 = time.perf_counter()
    for i, job in enumerate(mine, 1):
        kw = {"force": force}
        if stage == "A":
            kw["threads"] = threads
        elif stage == "C":
            kw["threads"] = threads; kw["oversampling"] = oversampling
        r = fn(job, **kw)
        el = time.perf_counter() - t0
        print(f"[{index}:{i}/{len(mine)}] rank {job['rank']:>3} {r['key']:<28} {r['decision']:<5} "
              f"{r.get('seconds', 0):>6.1f} s | {r.get('reason', '')[:150]} | elapsed {el / 60:.1f} min "
              f"eta {(el / i) * (len(mine) - i) / 60:.1f} min", flush=True)
    print(f"slice {index} DONE in {(time.perf_counter() - t0) / 60:.1f} min", flush=True)


def run_stage(stage: str, nslices: int, threads: int, oversampling: int, force: bool) -> None:
    js = eligible(stage)
    (OUT_ROOT / f"stage{stage}").mkdir(parents=True, exist_ok=True)
    logdir = OUT_ROOT / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    print(f"stage {stage}: {len(js)} candidates on {len({j['tic_id'] for j in js})} stars, "
          f"{nslices} slices x {threads} TLS threads", flush=True)
    procs = []
    for i in range(nslices):
        log = open(logdir / f"stage{stage}_slice{i}.log", "w", encoding="utf-8")
        cmd = [PY, str(Path(__file__).resolve()), "--rules", RULES, "slice", "--stage", stage,
               "--index", str(i), "--nslices", str(nslices), "--threads", str(threads),
               "--oversampling", str(oversampling)]
        if force:
            cmd.append("--force")
        procs.append((i, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=str(REPO)), log))
    codes = []
    for i, pr, log in procs:
        codes.append((i, pr.wait()))
        log.close()
    print("slice exit codes:", codes, flush=True)
    write_stage_csv(stage)


# ─────────────────────────────────────────────────────────────────────────────
# CSVs and the funnel
# ─────────────────────────────────────────────────────────────────────────────
def write_stage_csv(stage: str) -> Path:
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((OUT_ROOT / f"stage{stage}").glob("*.json"))]
    recs.sort(key=lambda r: r.get("rank", 9999))
    path = OUT_ROOT / f"stage{stage}.csv"
    if stage == "A":
        cols = ["rank", "tic_id", "key", "survey_period_days", "survey_depth_ppt", "chosen_ephemeris",
                "n_observed", "n_excluded", "n_kept", "kept_snr", "top_event_share", "snr_without_top",
                "kept_depth_ppt", "depth_over_survey_depth", "p_const", "n_criteria_passed",
                "strongest_event_excluded", "strongest_event_classes", "decision", "reason"]
        rows = []
        for r in recs:
            ch = (r.get("per_ephemeris") or {}).get(r.get("chosen_ephemeris"), {})
            se = ch.get("strongest_event", {})
            rows.append({"rank": r.get("rank"), "tic_id": r["tic_id"], "key": r["key"],
                         "survey_period_days": r["survey"]["period"], "survey_depth_ppt": round(r["survey"]["depth_ppt"], 3),
                         "chosen_ephemeris": r.get("chosen_ephemeris"), "n_observed": ch.get("n_observed"),
                         "n_excluded": ch.get("n_excluded"), "n_kept": ch.get("n_kept"),
                         "kept_snr": ch.get("kept_snr"), "top_event_share": ch.get("top_event_share"),
                         "snr_without_top": ch.get("snr_without_top"), "kept_depth_ppt": ch.get("kept_depth_ppt"),
                         "depth_over_survey_depth": ch.get("depth_over_survey_depth"), "p_const": ch.get("p_const"),
                         "n_criteria_passed": r.get("n_criteria_passed"),
                         "strongest_event_excluded": se.get("excluded"),
                         "strongest_event_classes": "|".join(se.get("artefact_classes") or []),
                         "decision": r["decision"], "reason": r.get("reason", "")})
    elif stage == "B":
        cols = ["rank", "tic_id", "key", "survey_period_days", "survey_depth_ppt", "n_sectors_tested",
                "n_sectors_excluding", "excluding_sectors", "median_deepest_window_ppt",
                "median_deepest_window_ppt_at_survey_duration", "min_margin_over_threshold",
                "survey_duration_over_t14", "ruwe", "ipd_frac_multi_peak",
                "n_neighbours_could_produce_depth", "n_deep_candidates_on_star", "n_flags", "flags",
                "max_verdict", "decision", "reason"]
        rows = []
        for r in recs:
            pi = r.get("phase_independent", {}) or {}
            g = r.get("gaia", {}) or {}
            rows.append({"rank": r.get("rank"), "tic_id": r["tic_id"], "key": r["key"],
                         "survey_period_days": r["survey_period"], "survey_depth_ppt": round(r["survey_depth_ppt"], 3),
                         "n_sectors_tested": pi.get("n_sectors_tested"), "n_sectors_excluding": pi.get("n_sectors_excluding"),
                         "excluding_sectors": "|".join(str(x) for x in (pi.get("excluding_sectors") or [])),
                         "median_deepest_window_ppt": pi.get("median_deepest_window_ppt"),
                         "median_deepest_window_ppt_at_survey_duration":
                             pi.get("median_deepest_window_ppt_at_survey_duration"),
                         "min_margin_over_threshold": pi.get("min_margin_over_threshold"),
                         "survey_duration_over_t14": pi.get("survey_duration_over_t14"),
                         "ruwe": g.get("ruwe"), "ipd_frac_multi_peak": g.get("ipd_frac_multi_peak"),
                         "n_neighbours_could_produce_depth": g.get("n_neighbours_could_produce_depth_within_3px"),
                         "n_deep_candidates_on_star": (r.get("deep_event_host") or {}).get("n_deep"),
                         "n_flags": len(r.get("flags") or []), "flags": " | ".join(r.get("flags") or []),
                         "max_verdict": r.get("max_verdict"), "decision": r["decision"], "reason": r.get("reason", "")})
    elif stage == "C":
        cols = ["rank", "tic_id", "key", "survey_period_days", "survey_depth_ppt", "blind_period_days", "blind_SDE",
                "blind_depth_ppt", "n_transits", "SDE_at_survey_period", "SDE_rank_of_survey_period",
                "closest_alias", "oversampling", "decision", "reason"]
        rows = []
        for r in recs:
            b = r.get("blind", {}) or {}
            m = b.get("match", {}) or {}
            rows.append({"rank": r.get("rank"), "tic_id": r["tic_id"], "key": r["key"],
                         "survey_period_days": r["survey_period"], "survey_depth_ppt": round(r["survey_depth_ppt"], 3),
                         "blind_period_days": None if b.get("period") is None else round(b["period"], 5),
                         "blind_SDE": None if b.get("SDE") is None else round(b["SDE"], 2),
                         "blind_depth_ppt": None if b.get("depth") is None else round(1000 * (1 - b["depth"]), 3),
                         "n_transits": b.get("distinct_transit_count"),
                         "SDE_at_survey_period": b.get("SDE_at_survey_period_max_1pct"),
                         "SDE_rank_of_survey_period": b.get("SDE_rank_of_survey_period"),
                         "closest_alias": m.get("closest_alias"),
                         "oversampling": (r.get("thresholds") or {}).get("oversampling_used"),
                         "decision": r["decision"], "reason": r.get("reason", "")})
    else:
        cols = ["rank", "tic_id", "key", "survey_period_days", "provisional_verdict", "verdict",
                "ctoi_fields_path", "reason"]
        rows = [{"rank": r.get("rank"), "tic_id": r["tic_id"], "key": r["key"],
                 "survey_period_days": r.get("survey_period"),
                 "provisional_verdict": r.get("provisional_verdict"), "verdict": r.get("verdict"),
                 "ctoi_fields_path": r.get("ctoi_fields_path"),
                 "reason": r.get("reason", "")} for r in recs]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    n_pass = sum(1 for r in recs if r.get("decision") == "PASS")
    print(f"wrote {path} : {len(rows)} rows, {n_pass} PASS", flush=True)
    return path


def load_stage(stage: str) -> list[dict]:
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((OUT_ROOT / f"stage{stage}").glob("*.json"))]
    recs.sort(key=lambda r: r.get("rank", 9999))
    return recs


def funnel() -> dict:
    js = jobs()
    out = {"generated_utc": utc(), "rules_version": RULES, "thresholds": THRESHOLDS,
           "population": {"n_survivors": len(js), "n_stars": len({j["tic_id"] for j in js})}, "stages": {}}
    prev_n = len(js)
    for stage in ("A", "B", "C", "D"):
        recs = load_stage(stage)
        if not recs:
            out["stages"][stage] = {"n_entered": prev_n, "n_records": 0}
            continue
        dec = {}
        for r in recs:
            dec[r.get("decision") or r.get("verdict")] = dec.get(r.get("decision") or r.get("verdict"), 0) + 1
        n_pass = sum(1 for r in recs if r.get("decision") == "PASS")
        out["stages"][stage] = {"n_entered": prev_n, "n_records": len(recs), "decisions": dec,
                                "n_pass": n_pass, "n_stars": len({r["tic_id"] for r in recs})}
        prev_n = n_pass
    A_ = load_stage("A")
    out["completeness"] = {
        "stageA_records": len(A_), "stageA_expected": len(js),
        "stageA_all_same_rules": all(r.get("rules_version") == RULES for r in A_),
        "stageA_errors": [r["key"] for r in A_ if r.get("decision") == "ERROR"],
    }
    (OUT_ROOT / f"funnel_{OUT_ROOT.name}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out["stages"], indent=1))
    print(json.dumps(out["completeness"], indent=1))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# the artefact census over all 405 Stage A records
# ─────────────────────────────────────────────────────────────────────────────
def camera_ccd_map() -> dict:
    m = {}
    for idx in LC_ROOT.glob("tic*/index.json"):
        d = json.loads(idx.read_text(encoding="utf-8"))
        for p in d["products"]:
            if "file" in p:
                m.setdefault((d["tic_id"], p["sector"]), []).append((p["author"], p.get("camera"), p.get("ccd")))
    return m


def census() -> dict:
    recs = load_stage("A")
    cam = camera_ccd_map()
    res = {"generated_utc": utc(), "rules_version": RULES, "n_candidates": len(recs),
           "definition": ("a candidate is CARRIED BY an artefact class when its strongest observed event "
                          "(the largest (depth/error)^2 in the detrended corrected flux) was removed by that "
                          "rule; counted under the chosen ephemeris and, separately, under the survey ephemeris"),
           "artefact_classes": ARTEFACT_CLASSES}
    for tag, which in (("chosen", None), ("survey", "survey")):
        carried = {k: [] for k in ARTEFACT_CLASSES}
        carried_any, no_strongest, strongest_kept = [], [], []
        per_event = {k: 0 for k in ARTEFACT_CLASSES}
        n_events_obs = n_events_excl = 0
        pdc_sectors: dict = {}
        for r in recs:
            per = r.get("per_ephemeris") or {}
            src = which or r.get("chosen_ephemeris")
            ch = per.get(src)
            if not ch:
                continue
            se = ch.get("strongest_event") or {}
            if not se.get("found"):
                no_strongest.append(r["key"])
            elif not se.get("excluded"):
                strongest_kept.append(r["key"])
            else:
                carried_any.append(r["key"])
                for c in se.get("artefact_classes") or []:
                    carried[c].append(r["key"])
            for e in ch.get("events") or []:
                if not e.get("observed"):
                    continue
                n_events_obs += 1
                if e.get("excluded"):
                    n_events_excl += 1
                cl = e.get("artefact_classes") or []
                for c in cl:
                    per_event[c] += 1
                if "dip_absent_in_sap" in cl or "pdc_gap" in cl:
                    for author, camera, ccd in cam.get((r["tic_id"], e.get("sector")), [(e.get("author"), None, None)]):
                        if author != e.get("author"):
                            continue
                        kk = f"s{e['sector']:03d}_cam{camera}_ccd{ccd}_{author}"
                        d = pdc_sectors.setdefault(kk, {"sector": e["sector"], "camera": camera, "ccd": ccd,
                                                        "author": author, "n_events": 0, "tics": [],
                                                        "classes": {}})
                        d["n_events"] += 1
                        if r["tic_id"] not in d["tics"]:
                            d["tics"].append(r["tic_id"])
                        for c in cl:
                            d["classes"][c] = d["classes"].get(c, 0) + 1
        res[tag] = {
            "n_candidates_with_a_measurable_strongest_event": len(recs) - len(no_strongest),
            "n_strongest_event_kept": len(strongest_kept),
            "n_carried_by_an_artefact_class": len(carried_any),
            "carried_by": {k: len(v) for k, v in carried.items()},
            "carried_by_keys": {k: v for k, v in carried.items() if v},
            "events": {"n_observed": n_events_obs, "n_excluded": n_events_excl,
                       "n_excluded_per_class": per_event},
            "pdc_made_dips_by_sector_camera_ccd": dict(sorted(pdc_sectors.items(),
                                                              key=lambda kv: -kv[1]["n_events"])),
        }
    # binary-host eclipses: a deep accepted candidate on the star, and deep points actually clipped
    deep_host, deep_and_clipped = [], []
    for r in recs:
        d = r.get("deep_event_host") or {}
        nclip = (r.get("prepare") or {}).get("n_deep_clipped") or 0
        if d.get("flag"):
            deep_host.append(r["key"])
            if nclip > 0:
                deep_and_clipped.append(r["key"])
    res["binary_host_eclipses"] = {
        "definition": ("the star carries another accepted candidate at >= 30 ppt or >= 5 x this candidate's "
                       "depth (candidates.csv); 'with deep points clipped' additionally means the whole-baseline "
                       "prepare step removed binned points deeper than 3 x the candidate depth, i.e. the deep "
                       "events are present in this candidate's own search data"),
        "n_with_deep_accepted_candidate": len(deep_host),
        "n_with_deep_accepted_candidate_and_deep_points_clipped": len(deep_and_clipped),
        "keys_with_deep_points_clipped": deep_and_clipped,
    }
    # per star: how many of its survivors an artefact class explains
    per_star: dict = {}
    for r in recs:
        per = r.get("per_ephemeris") or {}
        ch = per.get(r.get("chosen_ephemeris")) or {}
        se = ch.get("strongest_event") or {}
        d = per_star.setdefault(r["tic_id"], {"n_survivors": 0, "n_carried": 0, "classes": {}})
        d["n_survivors"] += 1
        if se.get("found") and se.get("excluded"):
            d["n_carried"] += 1
            for c in se.get("artefact_classes") or []:
                d["classes"][c] = d["classes"].get(c, 0) + 1
    hist: dict = {}
    for tic, d in per_star.items():
        kk = f"{d['n_carried']}/{d['n_survivors']}"
        hist[kk] = hist.get(kk, 0) + 1
    res["per_star"] = {"n_stars": len(per_star),
                       "n_stars_all_survivors_carried": sum(1 for d in per_star.values()
                                                            if d["n_carried"] == d["n_survivors"]),
                       "n_stars_none_carried": sum(1 for d in per_star.values() if d["n_carried"] == 0),
                       "carried_over_survivors_histogram": dict(sorted(hist.items())),
                       "stars": {str(k): v for k, v in sorted(per_star.items(), key=lambda kv: -kv[1]["n_carried"])}}
    (OUT_ROOT / f"census_{OUT_ROOT.name}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({"chosen": res["chosen"]["carried_by"], "survey": res["survey"]["carried_by"],
                      "n_carried_chosen": res["chosen"]["n_carried_by_an_artefact_class"],
                      "n_carried_survey": res["survey"]["n_carried_by_an_artefact_class"],
                      "binary": res["binary_host_eclipses"]["n_with_deep_accepted_candidate"],
                      "per_star": {k: v for k, v in res["per_star"].items() if k != "stars"}}, indent=1))
    return res


# -----------------------------------------------------------------------------
# report: the markdown tables of docs/REVET.md, generated from the records
# -----------------------------------------------------------------------------
def _fmt(v, nd=2):
    if v is None:
        return "-"
    if isinstance(v, float):
        if v != v:
            return "-"
        if abs(v) < 1e-3 and v != 0:
            return f"{v:.1e}"
        return f"{v:.{nd}f}"
    return str(v)


def report_tables() -> str:
    A_ = load_stage("A")
    B_ = load_stage("B")
    C_ = load_stage("C")
    D_ = load_stage("D")
    cen = json.loads((OUT_ROOT / f"census_{OUT_ROOT.name}.json").read_text(encoding="utf-8"))
    fun = json.loads((OUT_ROOT / f"funnel_{OUT_ROOT.name}.json").read_text(encoding="utf-8"))
    L = []
    w = L.append

    # ---- the funnel -------------------------------------------------------
    w("### Funnel\n")
    w("| stage | entered | records | PASS | stars in | stars out |")
    w("|---|---:|---:|---:|---:|---:|")
    for st, label in (("A", "A events"), ("B", "B star-level"), ("C", "C blind TLS"), ("D", "D full audit")):
        f = fun["stages"].get(st, {})
        recs = {"A": A_, "B": B_, "C": C_, "D": D_}[st]
        n_pass = sum(1 for r in recs if (r.get("decision") or r.get("verdict")) in ("PASS", "SUBMIT"))
        w(f"| {label} | {f.get('n_entered', 0)} | {f.get('n_records', 0)} | {n_pass} | "
          f"{len({r['tic_id'] for r in recs}) if recs else 0} | "
          f"{len({r['tic_id'] for r in recs if (r.get('decision') or r.get('verdict')) in ('PASS', 'SUBMIT')}) if recs else 0} |")

    # ---- Stage A failure modes -------------------------------------------
    w("\n### Stage A: which criterion each candidate fails\n")
    counts, npass_hist, chosen = {}, {}, {}
    for r in A_:
        for c, ok in (r.get("criteria") or {}).items():
            counts[c] = counts.get(c, 0) + (0 if ok else 1)
        npass_hist[r.get("n_criteria_passed")] = npass_hist.get(r.get("n_criteria_passed"), 0) + 1
        chosen[r.get("chosen_ephemeris")] = chosen.get(r.get("chosen_ephemeris"), 0) + 1
    w("| criterion | candidates failing it |")
    w("|---|---:|")
    labels = {"kept_events_ge_3": "fewer than 3 kept events",
              "kept_snr_ge_7": "kept-event SNR < 7",
              "top_share_le_50pct": "strongest kept event carries > 50% of the signal",
              "snr_without_top_ge_5": "SNR without the strongest kept event < 5",
              "depth_within_0.5_2x_survey": "kept depth outside 0.5-2 x the survey depth",
              "depths_consistent_p_ge_1e-3": "per-event depths inconsistent with a constant (p < 1e-3)"}
    for c, lab in labels.items():
        w(f"| {lab} | {counts.get(c, 0)} |")
    w(f"\nCriteria passed, out of six: " +
      ", ".join(f"{k} -> {v}" for k, v in sorted(npass_hist.items(), key=lambda kv: -(kv[0] or 0))) +
      ". Ephemeris that gave the candidate the most credit: " +
      ", ".join(f"{k} {v}" for k, v in sorted(chosen.items(), key=lambda kv: -kv[1])) + ".")

    # ---- Stage A near misses ---------------------------------------------
    near = [r for r in A_ if r.get("n_criteria_passed") == 5]
    w(f"\n### Stage A near misses: the {len(near)} candidates that fail exactly one criterion\n")
    w("Listed so that a reader can see what the single rule excluded; none of them entered Stage B." + "\n")
    w("| rank | TIC | P (d) | survey depth (ppt) | ephemeris | kept / observed | kept SNR | kept depth (ppt) | "
      "x survey | p(const) | the criterion it fails |")
    w("|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---|")
    for r in sorted(near, key=lambda r: r.get("rank", 9999)):
        ch = (r.get("per_ephemeris") or {}).get(r.get("chosen_ephemeris"), {})
        bad = [labels.get(c, c) for c, ok in (r.get("criteria") or {}).items() if not ok]
        w(f"| {r.get('rank')} | {r['tic_id']} | {r['survey']['period']:.4f} | {r['survey']['depth_ppt']:.2f} | "
          f"{r.get('chosen_ephemeris')} | {ch.get('n_kept')} / {ch.get('n_observed')} | "
          f"{_fmt(ch.get('kept_snr'))} | {_fmt(ch.get('kept_depth_ppt'), 3)} | "
          f"{_fmt(ch.get('depth_over_survey_depth'), 2)} | {_fmt(ch.get('p_const'))} | {'; '.join(bad)} |")

    # ---- the artefact census ---------------------------------------------
    for tag, title in (("chosen", "under the ephemeris that gives the candidate the most credit"),
                       ("survey", "under the survey ephemeris (the one the survey ranked on)")):
        c = cen[tag]
        w(f"\n### Artefact census, {title}\n")
        w(f"Candidates whose strongest observed event survives every removal rule: "
          f"{c['n_strongest_event_kept']} of {cen['n_candidates']}. "
          f"Carried by at least one artefact class: {c['n_carried_by_an_artefact_class']}. "
          f"Events: {c['events']['n_excluded']} of {c['events']['n_observed']} observed epochs removed.\n")
        w("| artefact class | candidates carried by it | events removed by it |")
        w("|---|---:|---:|")
        for k in ARTEFACT_CLASSES:
            w(f"| {k.replace('_', ' ')} | {c['carried_by'].get(k, 0)} | {c['events']['n_excluded_per_class'].get(k, 0)} |")

    # ---- the sectors that make PDC dips ----------------------------------
    w("\n### Sectors and camera/CCD that produce the PDC-made dips\n")
    w("Every (sector, camera, CCD, product) whose events were removed as a dip absent from SAP or as "
      "abutting a PDC gap, ordered by how many events it removed.\n")
    w("| sector | camera | CCD | product | events removed | stars | classes |")
    w("|---:|---:|---:|---|---:|---:|---|")
    for kk, d in list(cen["chosen"]["pdc_made_dips_by_sector_camera_ccd"].items())[:30]:
        w(f"| {d['sector']} | {d['camera']} | {d['ccd']} | {d['author']} | {d['n_events']} | {len(d['tics'])} | "
          f"{', '.join(f'{a} {b}' for a, b in sorted(d['classes'].items(), key=lambda kv: -kv[1]))} |")

    # ---- per star ---------------------------------------------------------
    ps = cen["per_star"]
    w(f"\n### How many survivors per star the artefact classes explain\n")
    w(f"{ps['n_stars']} stars. On {ps['n_stars_all_survivors_carried']} of them every survivor is carried by "
      f"an artefact class; on {ps['n_stars_none_carried']} none is.\n")
    w("| carried / survivors on the star | stars |")
    w("|---|---:|")
    for k, v in ps["carried_over_survivors_histogram"].items():
        w(f"| {k} | {v} |")

    # ---- binary hosts -----------------------------------------------------
    bh = cen["binary_host_eclipses"]
    w(f"\n### Deep events on the same star (binary hosts)\n")
    w(f"{bh['n_with_deep_accepted_candidate']} of {cen['n_candidates']} candidates sit on a star that carries "
      f"another accepted candidate at >= 30 ppt or >= 5 x this candidate's depth; on "
      f"{bh['n_with_deep_accepted_candidate_and_deep_points_clipped']} of them the whole-baseline preparation "
      f"actually removed binned points deeper than 3 x the candidate depth, i.e. the deep events are present "
      f"in this candidate's own search data.\n")

    # ---- Stage B ----------------------------------------------------------
    if B_:
        w("\n### Stage B: the star-level tests\n")
        w("The window of test (i) is the central-transit duration T14 at the candidate period, as specified. "
          "Where the survey's own box duration is shorter, a T14-long window averages over out-of-transit "
          "cadences and measures a shallower dip; the last two columns make that dilution visible. "
          "The decision uses the T14 column only.\n")
        w("| rank | TIC | P (d) | depth (ppt) | sectors tested | excluding | median deepest window (ppt) | "
          "same at the survey duration (ppt) | survey dur / T14 | min margin over threshold | RUWE | flags | decision |")
        w("|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---|")
        for r in B_:
            pi = r.get("phase_independent", {}) or {}
            g = r.get("gaia", {}) or {}
            w(f"| {r.get('rank')} | {r['tic_id']} | {r['survey_period']:.4f} | {r['survey_depth_ppt']:.2f} | "
              f"{pi.get('n_sectors_tested')} | {'|'.join(str(x) for x in (pi.get('excluding_sectors') or [])) or '-'} | "
              f"{_fmt(pi.get('median_deepest_window_ppt'))} | "
              f"{_fmt(pi.get('median_deepest_window_ppt_at_survey_duration'))} | "
              f"{_fmt(pi.get('survey_duration_over_t14'))} | {_fmt(pi.get('min_margin_over_threshold'))} | "
              f"{_fmt(g.get('ruwe'))} | {len(r.get('flags') or [])} | {r['decision']} |")
        bl = [r for r in B_ if r["decision"] == "FAIL"
              and (r.get("phase_independent") or {}).get("min_margin_over_threshold") is not None
              and 0.7 <= (r["phase_independent"]["min_margin_over_threshold"]) < 1.0]
        if bl:
            w(f"\n**Borderline exclusions.** {len(bl)} of the Stage B failures are excluded by a sector whose "
              f"deepest window is within 30% of the threshold, i.e. the kill turns on the window-dilution "
              f"factor above: " +
              "; ".join(f"TIC {r['tic_id']} P={r['survey_period']:.4f} d "
                        f"(margin {r['phase_independent']['min_margin_over_threshold']:.3f}, "
                        f"survey dur / T14 {_fmt(r['phase_independent'].get('survey_duration_over_t14'))})"
                        for r in bl) + ".")

    # ---- Stage C ----------------------------------------------------------
    if C_:
        w("\n### Stage C: blind Transit Least Squares, 0.5-110 d\n")
        w("| rank | TIC | survey P (d) | depth (ppt) | strongest blind peak (d) | SDE | depth there (ppt) | "
          "n transits | SDE within 1% of the survey P | rank of that period | verdict |")
        w("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
        for r in C_:
            b = r.get("blind", {}) or {}
            w(f"| {r.get('rank')} | {r['tic_id']} | {r['survey_period']:.4f} | {r['survey_depth_ppt']:.2f} | "
              f"{_fmt(b.get('period'), 5)} | {_fmt(b.get('SDE'), 1)} | "
              f"{_fmt(None if b.get('depth') is None else 1000 * (1 - b['depth']), 2)} | "
              f"{b.get('distinct_transit_count')} | {_fmt(b.get('SDE_at_survey_period_max_1pct'), 1)} | "
              f"{b.get('SDE_rank_of_survey_period') or '-'} | {r['decision']} |")

    # ---- Stage D ----------------------------------------------------------
    if D_:
        w("\n### Stage D: verdicts\n")
        w("| rank | TIC | P (d) | provisional | verdict | ctoi_fields.json | reason |")
        w("|---:|---:|---:|---|---|---|---|")
        for r in D_:
            w(f"| {r.get('rank')} | {r['tic_id']} | {r.get('survey_period', 0):.4f} | "
              f"{r.get('provisional_verdict') or '-'} | {r.get('verdict') or '-'} | "
              f"{r.get('ctoi_fields_path') or '-'} | {(r.get('reason') or '')[:200]} |")
    out = "\n".join(L) + "\n"
    (OUT_ROOT / "report_tables.md").write_text(out, encoding="utf-8")
    print(out)
    return out


# ─────────────────────────────────────────────────────────────────────────────
def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rules", choices=["p6.2", "p7.0"], default="p6.2",
                    help="rule set: p6.2 (the frozen prompt-6 rules, the default, so the 405 Stage A "
                         "records reproduce) or p7.0 (the same rules with the four prompt-7 options on)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for st in ("stageA", "stageB", "stageC"):
        s = sub.add_parser(st)
        s.add_argument("--slices", type=int, default=12)
        s.add_argument("--threads", type=int, default=1)
        s.add_argument("--oversampling", type=int, default=C_OVERSAMPLING_DEFAULT)
        s.add_argument("--force", action="store_true")
    sl = sub.add_parser("slice")
    sl.add_argument("--stage", required=True, choices=["A", "B", "C"])
    sl.add_argument("--index", type=int, required=True); sl.add_argument("--nslices", type=int, required=True)
    sl.add_argument("--threads", type=int, default=1)
    sl.add_argument("--oversampling", type=int, default=C_OVERSAMPLING_DEFAULT)
    sl.add_argument("--force", action="store_true")
    o = sub.add_parser("one")
    o.add_argument("--stage", required=True, choices=["A", "B", "C"])
    o.add_argument("--tic", type=int, required=True); o.add_argument("--period", type=float, required=True)
    o.add_argument("--threads", type=int, default=8)
    o.add_argument("--oversampling", type=int, default=C_OVERSAMPLING_DEFAULT)
    o.add_argument("--force", action="store_true")
    sd = sub.add_parser("stageD")
    sd.add_argument("--force", action="store_true")
    sd.add_argument("--no-refresh", action="store_true", help="do not re-download the hard-stop catalogs")
    vd = sub.add_parser("verdict")
    vd.add_argument("--tic", type=int, required=True); vd.add_argument("--period", type=float, required=True)
    vd.add_argument("--verdict", required=True, choices=["SUBMIT", "HOLD", "KILL"])
    vd.add_argument("--reason", required=True)
    vd.add_argument("--note", default=None, help="the two-sentence ExoFOP note, for a SUBMIT")
    cs = sub.add_parser("csv"); cs.add_argument("--stage", required=True, choices=["A", "B", "C", "D"])
    sub.add_parser("funnel")
    sub.add_parser("census")
    sub.add_parser("report")
    el = sub.add_parser("eligible"); el.add_argument("--stage", required=True, choices=["A", "B", "C", "D"])
    args = ap.parse_args(argv)
    set_rules(args.rules)

    if args.cmd in ("stageA", "stageB", "stageC"):
        run_stage(args.cmd[-1], args.slices, args.threads, args.oversampling, args.force)
    elif args.cmd == "slice":
        run_slice(args.stage, args.index, args.nslices, args.threads, args.oversampling, args.force)
    elif args.cmd == "one":
        job = next(j for j in jobs() if j["tic_id"] == args.tic and abs(j["period"] / args.period - 1) < 1e-6)
        kw = {"force": args.force}
        if args.stage == "A":
            kw["threads"] = args.threads
        elif args.stage == "C":
            kw["threads"] = args.threads; kw["oversampling"] = args.oversampling
        r = STAGE_FN[args.stage](job, **kw)
        print(json.dumps({k: v for k, v in r.items() if k not in ("per_ephemeris",)}, indent=1)[:6000])
        print("DECISION", r["decision"], "|", r.get("reason"))
    elif args.cmd == "stageD":
        staged(force=args.force, refresh=not args.no_refresh)
    elif args.cmd == "verdict":
        stamp_verdict(args.tic, args.period, args.verdict, args.reason, args.note)
    elif args.cmd == "csv":
        write_stage_csv(args.stage)
    elif args.cmd == "funnel":
        funnel()
    elif args.cmd == "census":
        census()
    elif args.cmd == "report":
        report_tables()
    elif args.cmd == "eligible":
        js = eligible(args.stage)
        print(f"{len(js)} candidates on {len({j['tic_id'] for j in js})} stars enter stage {args.stage}")
        for j in js[:60]:
            print(f"  rank {j['rank']:>3} TIC {j['tic_id']:>11} P={j['period']:.4f} depth={j['depth_ppt']:.2f} ppt")


if __name__ == "__main__":
    main()
