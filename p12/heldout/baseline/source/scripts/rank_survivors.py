"""Prompt 4, step 2: automated gates and the FROZEN ranking score.

The rules are written down in ``docs/RANKING_SCORE.md`` (dated before the
survey run) and implemented here without any free parameter. Usage::

    python scripts/rank_survivors.py --run data/survey/runs/survey_v1 --out data/survey/p4
    python scripts/rank_survivors.py --run ... --out ... --expensive data/survey/p4/expensive

Outputs under ``--out``:

* ``candidates.csv``   every accepted candidate of every finished job, one
                       row each, with every gate decision;
* ``survivors.csv``    rows passing G2-G6 (and G7 when cross-match results
                       are supplied), ranked by the frozen score;
* ``gate_counts.json`` counts after each gate;
* ``run_summary.json`` targets searched, status counts, timing quantiles,
                       products and sectors used, fallback events, errors.

With ``--expensive`` the per-candidate JSON files written by
``scripts/survivor_packets.py`` (fresh cross-match, TRICERATOPS, centroid,
contamination, final verdict) are merged in: G7 is applied and S_fpp uses
the measured FPP for the rows that have one. Nothing here submits anything.

``--score v2`` (prompt 7) is a SEPARATE mode.  It does not re-run the survey and
does not touch ``survivors.csv`` or any other frozen artefact: it reads the
frozen survivor list together with the prompt-6 audit records and the prompt-7
option records, scores every survivor with ``tesshunter.ranking.score_v2``
(``docs/RANKING_SCORE.md`` section 5) and writes ``survivors_score_v2.csv`` and
``score_v2.json`` beside them.  The frozen score stays exactly as it was.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent

VERDICT_FP = "likely false positive"

# ── frozen constants (docs/RANKING_SCORE.md) ─────────────────────────────────
SNR_GATE = 9.0            # G2 and the zero of S_snr
SNR_SATURATE = 50.0       # S_snr = 1 (measured completeness 89% above 50)
NTR_GATE = 3              # G3 and the zero of S_ntr
NTR_SATURATE = 10         # S_ntr = 1
DIP_SIGMA_MIN = 3.0       # G5 (transit_fit.FIT_MIN_DEPTH_SIGMA)
DCHI2_GATE = 9.0          # profile delta chi2 below which the catalog density is not rejected
RATIO_LIMIT = 3.0         # density ratio limit of the a/R* flag
HARMONIC_RATIOS = (2.0, 3.0)
HARMONIC_TOL = 0.01
FPP_NEUTRAL = 0.5
FPP_MAX_FOR_PACKET = 0.5  # G8 (fpp.FPP_MAX_FOR_PACKET)
TOP_N_EXPENSIVE = 30


def _f(v, default=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _s(v):
    return "" if v is None else str(v)


# ── score ─────────────────────────────────────────────────────────────────────

def s_snr(stitch_snr) -> float:
    x = _f(stitch_snr, 0.0)
    if x is None or x <= 0:
        return 0.0
    return float(np.clip(math.log(x / SNR_GATE) / math.log(SNR_SATURATE / SNR_GATE), 0.0, 1.0))


def s_ntr(n) -> float:
    x = _f(n, 0.0) or 0.0
    return float(np.clip((x - NTR_GATE) / (NTR_SATURATE - NTR_GATE), 0.0, 1.0))


def s_fpp(fpp) -> float:
    x = _f(fpp)
    if x is None:
        return FPP_NEUTRAL
    return float(np.clip(1.0 - x, 0.0, 1.0))


def s_rho(fit: dict) -> float:
    if not fit or not fit.get("success"):
        return 0.5
    if bool(fit.get("a_rs_inconsistent")):
        return 0.0
    if _f(fit.get("rho_star_cat_cgs")) is None:
        return 0.5
    d = _f(fit.get("density_dchi2_eff"))
    if d is None:
        d = _f(fit.get("density_dchi2"))
    if d is None:
        return 0.5
    if d < DCHI2_GATE:
        return 1.0
    ratio = _f(fit.get("density_ratio"))
    if ratio is None or ratio <= 0:
        return 0.5
    return float(np.clip(1.0 - abs(math.log(ratio)) / math.log(RATIO_LIMIT), 0.0, 1.0))


def score_row(row: dict, fit: dict, fpp=None) -> dict:
    a, b, c, d = s_snr(row.get("stitch_snr")), s_ntr(row.get("stitch_n_transits")), s_fpp(fpp), s_rho(fit)
    return {"s_snr": round(a, 4), "s_ntr": round(b, 4), "s_fpp": round(c, 4), "s_rho": round(d, 4),
            "score": round(a + b + c + d, 4)}


# ── rows ──────────────────────────────────────────────────────────────────────

def load_results(run_dir: Path) -> list[dict]:
    recs = []
    for p in sorted((run_dir / "results").glob("*.json")):
        try:
            recs.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception as exc:
            recs.append({"job_id": p.stem, "status": "corrupt", "error": str(exc)})
    return recs


def candidate_rows(rec: dict, target: dict | None) -> list[dict]:
    res = rec.get("result") or {}
    planets = res.get("planets") or []
    vet_by = {int(v.get("planet_num", 0)): v for v in (res.get("vetting") or [])}
    prov = res.get("provenance") or {}
    tic = int(rec.get("tic_id"))
    rows = []
    for p in planets:
        num = int(p.get("planet_num", 0))
        vet = vet_by.get(num, {})
        vr = vet.get("result") or {}
        fit = p.get("fit") or {}
        d_err = _f(fit.get("depth_err_white")) or _f(fit.get("depth_err"))
        dip_sigma = (_f(fit.get("depth_ppt"), 0.0) / d_err) if (fit.get("success") and d_err and d_err > 0) else None
        verdict = _s(p.get("verdict") or vet.get("verdict"))
        row = {
            "tic_id": tic, "planet_num": num, "search": p.get("search"),
            "period_days": _f(p.get("period_days")), "epoch_btjd": _f(p.get("epoch_btjd")),
            "duration_days": _f(p.get("duration_days")),
            "depth_ppt": _f(p.get("depth_ppt")), "depth_source": p.get("depth_source"),
            "snr": _f(p.get("snr")), "n_transits": _f(p.get("n_transits_observed")),
            "stitch_snr": _f(p.get("stitch_snr")), "stitch_n_transits": _f(p.get("stitch_n_transits")),
            "stitch_epoch_consistent": bool(p.get("stitch_epoch_consistent")),
            "stitch_period_days": _f(p.get("stitch_period_days")),
            "verdict": verdict,
            "n_flags_high": len(vet.get("flags_high") or []), "n_flags_medium": len(vet.get("flags_medium") or []),
            "flags_high": " | ".join(vet.get("flags_high") or [])[:300],
            "fit_success": bool(fit.get("success")),
            "fit_depth_ppt": _f(fit.get("depth_ppt")), "fit_depth_err": _f(fit.get("depth_err")),
            "fit_dip_sigma": None if dip_sigma is None else round(dip_sigma, 2),
            "fit_no_dip": bool(vr.get("fit_no_dip")),
            "rp_rs": _f(fit.get("rp_rs")), "rp_rs_err": _f(fit.get("rp_rs_err")),
            "rp_rearth": _f(fit.get("rp_rearth")), "rp_rearth_err": _f(fit.get("rp_rearth_err")),
            "a_rs": _f(fit.get("a_rs")), "a_rs_star": _f(fit.get("a_rs_star")),
            "impact_b": _f(fit.get("b")), "fit_duration_days": _f(fit.get("duration_days")),
            "density_ratio": _f(fit.get("density_ratio")), "density_dchi2_eff": _f(fit.get("density_dchi2_eff")),
            "a_rs_inconsistent": bool(fit.get("a_rs_inconsistent")), "grazing": bool(fit.get("grazing")),
            "density_prior_adopted": bool(fit.get("density_prior_adopted")),
            "beta_red_noise": _f(fit.get("beta_red_noise")),
            "odd_even_fit_sigma": _f((fit.get("odd_even") or {}).get("delta_sigma")),
            "secondary_is_stellar": bool(vr.get("secondary_is_stellar")),
            "n_units": len(prov.get("units_used") or []), "baseline_days": _f(rec.get("baseline_days")),
            "n_cadences": _f(rec.get("n_cadences_raw")),
            "tmag": _f((target or {}).get("tmag")), "teff_k": _f((target or {}).get("teff_k")),
            "radius_rsun": _f((target or {}).get("radius_rsun")), "mass_msun": _f((target or {}).get("mass_msun")),
            "ra_deg": _f((target or {}).get("ra_deg")), "dec_deg": _f((target or {}).get("dec_deg")),
        }
        # gates
        row["G2_stitch"] = bool(row["stitch_snr"] is not None and row["stitch_snr"] >= SNR_GATE
                                and row["stitch_epoch_consistent"])
        row["G3_transits"] = bool((row["stitch_n_transits"] or 0) >= NTR_GATE)
        row["G4_verdict"] = bool(VERDICT_FP not in verdict.lower())
        row["G5_fit"] = bool(row["fit_success"] and dip_sigma is not None and dip_sigma >= DIP_SIGMA_MIN)
        row["passes_G2_G5"] = bool(row["G2_stitch"] and row["G3_transits"] and row["G4_verdict"] and row["G5_fit"])
        row["first_failed_gate"] = next((g for g, ok in (("G2", row["G2_stitch"]), ("G3", row["G3_transits"]),
                                                          ("G4", row["G4_verdict"]), ("G5", row["G5_fit"])) if not ok), "")
        row.update(score_row(row, fit))
        row["_fit"] = fit
        rows.append(row)
    return rows


def dedupe_harmonics(df: pd.DataFrame) -> pd.DataFrame:
    """G6: within a star, rows whose periods are in a 2:1 or 3:1 ratio (1%) are one signal."""
    df = df.copy()
    df["G6_harmonic_of"] = ""
    df["G6_unique"] = True
    for tic, sub in df.groupby("tic_id"):
        sub = sub.sort_values(["score", "stitch_snr"], ascending=[False, False])
        kept: list[tuple[int, float]] = []
        for idx, r in sub.iterrows():
            P = float(r["period_days"])
            dup = None
            for kidx, kP in kept:
                for ratio in HARMONIC_RATIOS:
                    if abs(P / (kP * ratio) - 1.0) <= HARMONIC_TOL or abs(P * ratio / kP - 1.0) <= HARMONIC_TOL:
                        dup = kidx
                        break
                if dup is not None:
                    break
            if dup is None:
                kept.append((idx, P))
            else:
                df.at[idx, "G6_unique"] = False
                df.at[idx, "G6_harmonic_of"] = f"planet {int(df.at[dup, 'planet_num'])} P={df.at[dup, 'period_days']:.5f}"
    return df


def load_expensive(exp_dir: Path | None) -> dict:
    out = {}
    if not exp_dir or not exp_dir.exists():
        return out
    for p in sorted(exp_dir.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        out[(int(d["tic_id"]), round(float(d["period_days"]), 4))] = d
    return out


def rank(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["score", "stitch_snr", "tic_id", "period_days"],
                        ascending=[False, False, True, True]).reset_index(drop=True)
    df.insert(0, "rank", np.arange(1, len(df) + 1))
    return df


# ── run summary ───────────────────────────────────────────────────────────────

def _quantiles(x: list[float]) -> dict:
    if not x:
        return {}
    a = np.asarray(x, float)
    return {"n": int(a.size), "median": round(float(np.median(a)), 1), "p90": round(float(np.percentile(a, 90)), 1),
            "max": round(float(a.max()), 1), "mean": round(float(a.mean()), 1), "sum_hours": round(float(a.sum()) / 3600, 2)}


def summarize_run(recs: list[dict], targets: dict, prefetch_recs: list[dict] | None) -> dict:
    status = {}
    walls, search_s, detect_s, preprocess_s, fit_s = [], [], [], [], []
    products_by_author, units_hist, fallback, errors, retried, budget_stops = {}, [], [], [], [], []
    n_cand = 0
    for r in recs:
        st = r.get("status", "missing")
        status[st] = status.get(st, 0) + 1
        if int(r.get("attempts", 1) or 1) > 1:
            retried.append({"tic_id": r.get("tic_id"), "attempts": r.get("attempts"), "status": st})
        if st in ("error", "timeout", "corrupt", "no_data"):
            errors.append({"tic_id": r.get("tic_id"), "status": st, "attempts": r.get("attempts"),
                           "error": (r.get("error") or "").splitlines()[0][:200] if r.get("error") else ""})
        if st != "ok":
            continue
        walls.append(_f(r.get("wall_s"), 0.0))
        tm = r.get("timings") or {}
        search_s.append(_f(tm.get("search"), 0.0))
        rt = (r.get("result") or {}).get("timings") or {}
        detect_s.append(_f(rt.get("detect"), 0.0))
        preprocess_s.append(_f(rt.get("preprocess"), 0.0))
        fit_s.append(_f(rt.get("remeasure"), 0.0))
        prov = (r.get("result") or {}).get("provenance") or {}
        for p in prov.get("products") or []:
            a = str(p.get("author") or "?")
            products_by_author[a] = products_by_author.get(a, 0) + 1
        units_hist.append(len(prov.get("units_used") or []))
        for ev in prov.get("fallback_events") or []:
            fallback.append({"tic_id": r.get("tic_id"), **{k: str(v)[:160] for k, v in (ev or {}).items()}})
        for n in (r.get("result") or {}).get("notes") or []:
            if "would not fit" in n:
                budget_stops.append(r.get("tic_id"))
                break
        n_cand += len((r.get("result") or {}).get("planets") or [])
    per_star_authors = {}
    for r in recs:
        if r.get("status") != "ok":
            continue
        prov = (r.get("result") or {}).get("provenance") or {}
        key = ";".join(sorted({str(p.get("author") or "?").lower() for p in (prov.get("products") or [])}))
        per_star_authors[key] = per_star_authors.get(key, 0) + 1
    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_targets_in_list": len(targets), "n_results": len(recs), "status_counts": status,
        "n_accepted_candidates": n_cand,
        "wall_s": _quantiles(walls), "search_s": _quantiles(search_s), "detect_s": _quantiles(detect_s),
        "preprocess_s": _quantiles(preprocess_s), "characterise_s": _quantiles(fit_s),
        "units_per_star": _quantiles([float(u) for u in units_hist]),
        "products_by_author": products_by_author, "stars_by_author_set": per_star_authors,
        "n_fallback_events": len(fallback), "fallback_events": fallback[:200],
        "budget_stops": sorted(set(budget_stops)), "n_budget_stops": len(set(budget_stops)),
        "retried_jobs": retried, "not_ok_jobs": errors,
        "missing_from_results": sorted(set(targets) - {int(r.get("tic_id")) for r in recs if r.get("tic_id") is not None}),
    }
    if prefetch_recs:
        dl = [_f((r.get("cache") or {}).get("download_s"), 0.0) for r in prefetch_recs
              if r.get("status") == "ok" and not (r.get("cache") or {}).get("cache_hit")]
        out["prefetch"] = {"n_results": len(prefetch_recs),
                           "status_counts": {k: sum(1 for r in prefetch_recs if r.get("status") == k)
                                             for k in {r.get("status") for r in prefetch_recs}},
                           "download_s_new_stars": _quantiles(dl),
                           "not_ok": [{"tic_id": r.get("tic_id"), "status": r.get("status"),
                                       "error": (r.get("error") or "")[:200]} for r in prefetch_recs
                                      if r.get("status") != "ok"]}
    return out


def per_target_rows(recs: list[dict], prefetch_recs: list[dict] | None) -> list[dict]:
    """One row per target: timing, products, sectors, fallback events, errors."""
    pre = {int(r["tic_id"]): r for r in (prefetch_recs or []) if r.get("tic_id") is not None}
    rows = []
    for r in recs:
        tic = r.get("tic_id")
        res = r.get("result") or {}
        prov = res.get("provenance") or {}
        tm = r.get("timings") or {}
        rt = res.get("timings") or {}
        cache = r.get("cache") or {}
        pr = pre.get(int(tic)) if tic is not None else None
        pcache = (pr or {}).get("cache") or {}
        authors = {}
        for p in prov.get("products") or []:
            a = str(p.get("author") or "?").lower()
            authors[a] = authors.get(a, 0) + 1
        units = [str(u) for u in (prov.get("units_used") or [])]
        rows.append({
            "tic_id": tic, "status": r.get("status"), "attempts": r.get("attempts"),
            "wall_s": round(_f(r.get("wall_s"), 0.0) or 0.0, 1), "search_s": round(_f(tm.get("search"), 0.0) or 0.0, 1),
            "preprocess_s": round(_f(rt.get("preprocess"), 0.0) or 0.0, 1), "detect_s": round(_f(rt.get("detect"), 0.0) or 0.0, 1),
            "characterise_s": round(_f(rt.get("remeasure"), 0.0) or 0.0, 1), "confirm_s": round(_f(tm.get("confirm"), 0.0) or 0.0, 1),
            "cache_hit": cache.get("cache_hit"),
            "download_s": round(_f(cache.get("download_s"), 0.0) or _f(pcache.get("download_s"), 0.0) or 0.0, 1),
            "stitch_s": round(_f(cache.get("stitch_s"), 0.0) or _f(pcache.get("stitch_s"), 0.0) or 0.0, 1),
            "n_units": len(units), "units_used": ",".join(units), "n_products": prov.get("n_products_downloaded"),
            "products_by_author": ";".join(f"{k}:{v}" for k, v in sorted(authors.items())),
            "n_cadences": r.get("n_cadences_raw"), "baseline_days": round(_f(r.get("baseline_days"), 0.0) or 0.0, 1),
            "n_searches": res.get("n_searches"), "n_candidates": len(res.get("planets") or []),
            "budget_stop": any("would not fit" in n for n in (res.get("notes") or [])),
            "n_fallback_events": len(prov.get("fallback_events") or []),
            "fallback_events": " | ".join(f"{e.get('event')}: {str(e.get('detail'))[:80]}" for e in (prov.get("fallback_events") or []))[:300],
            "error": (r.get("error") or "").splitlines()[0][:200] if r.get("error") else "",
        })
    return rows


# -- the v2 score (prompt 7): a separate mode, the frozen score untouched -----

def rank_v2(out_dir: Path, p6: Path, p7: Path) -> dict:
    """Score every frozen survivor with the v2 rule and write the ordered list.

    Inputs, all already on disk: the frozen survivor rows, the prompt-6 Stage A
    record of each candidate (kept-event SNR, the per-event table, the
    deep-event-host block), the cached Gaia neighbours record of its star, and
    the prompt-7 option record (the secondary gate).  Nothing is recomputed and
    nothing is downloaded.  No verdict is produced for any candidate.
    """
    sys.path.insert(0, str(REPO / "src"))
    from tesshunter.ranking import score_v2
    from tesshunter.star_vet import gaia_flag_digest

    survivors = list(csv.DictReader(open(REPO / "data" / "survey" / "p4" / "survivors.csv",
                                         newline="", encoding="utf-8")))
    rows, missing = [], {"stageA": 0, "options": 0, "neighbours": 0}
    for r in survivors:
        tic, period = int(r["tic_id"]), float(r["period_days"])
        key = f"tic{tic}_P{period:.4f}"
        a_path = p6 / "stageA" / f"{key}.json"
        if not a_path.exists():
            missing["stageA"] += 1
            continue
        a = json.loads(a_path.read_text(encoding="utf-8"))
        ch = (a.get("per_ephemeris") or {}).get(a.get("chosen_ephemeris")) or {}
        # Gaia was queried only for the stars that reached Stage B, and prompt 7 queries
        # nothing: where there is no cached record the star simply incurs no Gaia penalty,
        # and the row says so, so the restriction is visible rather than silent.
        nb_path = p6 / "neighbours" / f"tic{tic}.json"
        if not nb_path.exists():
            nb_path = REPO / "data" / "survey" / "p5" / "neighbours" / f"tic{tic}.json"
        gaia_available = nb_path.exists()
        if gaia_available:
            gaia = gaia_flag_digest(json.loads(nb_path.read_text(encoding="utf-8")),
                                    float(r["depth_ppt"]))
        else:
            gaia, missing["neighbours"] = {}, missing["neighbours"] + 1
        o_path = p7 / "options" / f"{key}.json"
        gate = None
        if o_path.exists():
            gate = ((json.loads(o_path.read_text(encoding="utf-8")).get("secondary")) or {}).get("gate")
        else:
            missing["options"] += 1
        s = score_v2(ch.get("kept_snr"), ch.get("events") or [], gaia,
                     a.get("deep_event_host"), gate)
        rows.append({
            "frozen_rank": int(r["rank"]), "tic_id": tic, "period_days": period,
            "depth_ppt": round(float(r["depth_ppt"]), 3), "frozen_score": float(r["score"]),
            "chosen_ephemeris": a.get("chosen_ephemeris"), "stageA_decision": a.get("decision"),
            "score_v2": s["score_v2"], "S_snr2": s["S_snr2"], "S_sectors": s["S_sectors"],
            "kept_snr": s["kept_snr"],
            "n_sectors_showing_the_dip": s["n_sectors_showing_the_dip"],
            "n_sectors_with_kept_events": s["n_sectors_with_kept_events"],
            "gaia_record_available": gaia_available, "penalty_gaia": s["penalty_gaia"],
            "gaia_penalty_flags": " | ".join(s["gaia_penalty_flags"]),
            "penalty_deep_host": s["penalty_deep_host"], "deep_event_host": s["deep_event_host"],
            "secondary_gate": s["secondary_gate"],
            "zeroed_by_secondary_gate": s["zeroed_by_secondary_gate"],
        })
    df = pd.DataFrame(rows).sort_values(["score_v2", "kept_snr", "tic_id", "period_days"],
                                        ascending=[False, False, True, True])
    df.insert(0, "rank_v2", range(1, len(df) + 1))
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "survivors_score_v2.csv", index=False)
    rho = None
    if len(df) > 2:
        from scipy import stats as sst
        rr = sst.spearmanr(df["frozen_rank"], df["rank_v2"])
        rho = {"spearman_rho": round(float(rr.statistic), 4), "p_value": float(rr.pvalue)}
    res = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "what": "the prompt-7 v2 survivor score; the frozen P4 score and survivors.csv untouched",
           "n_scored": len(df), "missing_inputs": missing, "frozen_rank_vs_v2_rank": rho,
           "n_zeroed_by_secondary_gate": int(df["zeroed_by_secondary_gate"].sum()),
           "n_with_a_cached_gaia_record": int(df["gaia_record_available"].sum()),
           "gaia_note": ("Gaia DR3 was queried in prompts 5 and 6 only for the stars that reached "
                         "Stage B, and prompt 7 queries nothing; a candidate without a cached "
                         "record incurs no Gaia penalty and its row says so"),
           "n_with_a_gaia_penalty": int((df["penalty_gaia"] > 0).sum()),
           "n_with_a_gaia_penalty_among_those_with_a_record": int(
               ((df["penalty_gaia"] > 0) & df["gaia_record_available"]).sum()),
           "n_with_a_deep_host_penalty": int((df["penalty_deep_host"] > 0).sum()),
           "n_score_zero": int((df["score_v2"] == 0).sum()),
           "score_v2_quantiles": {k: round(float(df["score_v2"].quantile(q)), 4)
                                  for k, q in (("p10", .1), ("median", .5), ("p90", .9), ("max", 1.0))},
           "top_20": df.head(20).to_dict("records"),
           "stageA_pass_rows": df[df["stageA_decision"] == "PASS"].to_dict("records")}
    (out_dir / "score_v2.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(f"scored {len(df)} survivors; frozen rank vs v2 rank {rho}; "
          f"{res['n_zeroed_by_secondary_gate']} zeroed by the secondary gate")
    print(df.head(15).to_string(index=False))
    print(f"wrote {out_dir / 'survivors_score_v2.csv'} and {out_dir / 'score_v2.json'}")
    return res


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default=str(REPO / "data" / "survey" / "runs" / "survey_v1"))
    ap.add_argument("--prefetch-run", default=str(REPO / "data" / "survey" / "runs" / "p4_prefetch"))
    ap.add_argument("--targets", default=str(REPO / "data" / "survey" / "targets_v1.csv"))
    ap.add_argument("--out", default=str(REPO / "data" / "survey" / "p4"))
    ap.add_argument("--expensive", default=None, help="directory of per-candidate JSON from survivor_packets.py")
    ap.add_argument("--score", choices=["frozen", "v2"], default="frozen",
                    help="frozen: the P4 score, re-derived from the run (the default). "
                         "v2: score the frozen survivor list with the prompt-7 rule from the "
                         "prompt-6 audit records; writes survivors_score_v2.csv and touches "
                         "no frozen artefact")
    ap.add_argument("--p6-root", default=str(REPO / "data" / "survey" / "p6"))
    ap.add_argument("--p7-root", default=str(REPO / "data" / "survey" / "p7"))
    args = ap.parse_args()

    if args.score == "v2":
        rank_v2(Path(args.out), Path(args.p6_root), Path(args.p7_root))
        return 0

    run_dir, out_dir = Path(args.run), Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    targets = {int(r["tic_id"]): r for r in csv.DictReader(open(args.targets, newline="", encoding="utf-8"))}
    recs = load_results(run_dir)
    pre_dir = Path(args.prefetch_run)
    prefetch_recs = load_results(pre_dir) if (pre_dir / "results").exists() else None

    rows = []
    for r in recs:
        if r.get("status") != "ok":
            continue
        rows.extend(candidate_rows(r, targets.get(int(r["tic_id"]))))
    fits = {(int(r["tic_id"]), int(r["planet_num"])): r.pop("_fit") for r in rows}
    df = pd.DataFrame(rows)
    gate_counts = {
        "G0_jobs_ok": int(sum(1 for r in recs if r.get("status") == "ok")),
        "G1_accepted_candidates": int(len(df)),
        "stars_with_candidates": int(df["tic_id"].nunique()) if len(df) else 0,
    }
    if len(df):
        g2 = df["G2_stitch"]
        g3 = g2 & df["G3_transits"]
        g4 = g3 & df["G4_verdict"]
        g5 = g4 & df["G5_fit"]
        gate_counts.update({
            "G2_stitch_snr9_consistent": int(g2.sum()), "G3_three_transits": int(g3.sum()),
            "G4_verdict_not_fp": int(g4.sum()), "G5_fit_sees_dip": int(g5.sum()),
            "stars_after_G5": int(df.loc[g5, "tic_id"].nunique()),
            "candidates_2_transits_stitch": int((df["stitch_n_transits"] < 3).sum()),
        })
        surv = df[g5].copy()
        surv = dedupe_harmonics(surv)
        gate_counts["G6_unique_signals"] = int(surv["G6_unique"].sum())
        surv = surv[surv["G6_unique"]].copy()
    else:
        surv = df.copy()

    # expensive-step merge (G7 cross-match, measured FPP, final verdict).
    # The frozen rule (docs/RANKING_SCORE.md, S_fpp): the expensive set is the
    # top TOP_N_EXPENSIVE of the PRE-FPP ranking; only those rows are
    # re-scored with their measured FPP. A candidate outside that set that
    # received the expensive steps anyway (a rerun after the first FPP merge
    # selected from the post-FPP order) is reported with `extra_expensive`
    # and keeps S_fpp = 0.5 in the score.
    exp = load_expensive(Path(args.expensive)) if args.expensive else {}
    frozen_set: set = set()
    if len(surv):
        pre = surv.sort_values(["score", "stitch_snr", "tic_id", "period_days"],
                               ascending=[False, False, True, True]).head(TOP_N_EXPENSIVE)
        frozen_set = {(int(r.tic_id), round(float(r.period_days), 4)) for r in pre.itertuples()}
    if len(surv):
        for col in ("xmatch_status", "xmatch_summary", "catalog_stamp", "fpp", "nfpp", "fpp_error",
                    "fpp_uniform", "fpp_top_scenario", "extra_expensive",
                    "centroid_shift_px", "centroid_sigma", "centroid_flagged", "centroid_n_sectors",
                    "contamination_flagged", "verdict_final", "packet_dir", "expensive_done"):
            surv[col] = None
        surv["G7_crossmatch"] = True
        surv["G8_fpp_packet"] = None
        for idx, r in surv.iterrows():
            e = exp.get((int(r["tic_id"]), round(float(r["period_days"]), 4)))
            if not e:
                continue
            xm = e.get("crossmatch") or {}
            fp = e.get("fpp") or {}
            cen = e.get("centroid") or {}
            con = e.get("contamination") or {}
            surv.at[idx, "expensive_done"] = bool(e.get("started_utc")) and e.get("status") == "ok"
            surv.at[idx, "xmatch_status"] = xm.get("status")
            surv.at[idx, "xmatch_summary"] = (xm.get("summary") or "")[:200]
            surv.at[idx, "catalog_stamp"] = xm.get("catalog_stamp")
            surv.at[idx, "G7_crossmatch"] = xm.get("status") != "REJECT" if xm.get("status") else True
            if fp.get("available"):
                surv.at[idx, "fpp"] = _f(fp.get("fpp"))
                surv.at[idx, "nfpp"] = _f(fp.get("nfpp"))
                fppv = _f(fp.get("fpp"))
                surv.at[idx, "G8_fpp_packet"] = bool(fppv is not None and fppv <= FPP_MAX_FOR_PACKET)
                # A uniform posterior (every scenario at 1/n, blank scenario
                # names) means every likelihood was zero or NaN: the FPP is
                # then an artefact of the input, not a measurement. Reported,
                # not used to change the frozen score.
                tops = fp.get("top_scenarios") or []
                probs = [_f(t.get("prob")) for t in tops[:3] if isinstance(t, dict)]
                surv.at[idx, "fpp_uniform"] = bool(
                    len(probs) >= 2 and all(p is not None for p in probs)
                    and max(probs) - min(probs) < 1e-6
                    and all(not str(t.get("scenario") or "") for t in tops[:3]))
                surv.at[idx, "fpp_top_scenario"] = (f"{tops[0].get('scenario')} {tops[0].get('prob'):.3f}"
                                                    if tops and tops[0].get("scenario") else "")
            else:
                surv.at[idx, "fpp_error"] = (fp.get("error") or "not run")[:160]
            if cen.get("available"):
                surv.at[idx, "centroid_shift_px"] = _f(cen.get("total_shift_px"))
                surv.at[idx, "centroid_sigma"] = _f(cen.get("sigma"))
                surv.at[idx, "centroid_flagged"] = bool(cen.get("flagged"))
                surv.at[idx, "centroid_n_sectors"] = cen.get("n_sectors_used")
            if con.get("available"):
                surv.at[idx, "contamination_flagged"] = bool(con.get("flagged"))
            surv.at[idx, "verdict_final"] = e.get("verdict_final")
            surv.at[idx, "packet_dir"] = e.get("packet_dir")
            in_frozen = (int(r["tic_id"]), round(float(r["period_days"]), 4)) in frozen_set
            surv.at[idx, "extra_expensive"] = bool(e.get("started_utc")) and not in_frozen
            sc = score_row(r.to_dict(), fits.get((int(r["tic_id"]), int(r["planet_num"])), {}),
                           fpp=(fp.get("fpp") if (fp.get("available") and in_frozen) else None))
            for k, v in sc.items():
                surv.at[idx, k] = v
        n_rej = int((~surv["G7_crossmatch"]).sum())
        gate_counts["G7_crossmatch_rejected"] = n_rej
        gate_counts["G7_crossmatch_flagged"] = int((surv["xmatch_status"] == "FLAG").sum())
        gate_counts["G7_crossmatch_checked"] = int(surv["xmatch_status"].notna().sum())
        rejected = surv[~surv["G7_crossmatch"]].copy()
        surv = surv[surv["G7_crossmatch"]].copy()
        surv = rank(surv)
        gate_counts["survivors_ranked"] = int(len(surv))
        gate_counts["survivor_stars"] = int(surv["tic_id"].nunique())
        if exp:
            frozen_rows = surv[surv["extra_expensive"] != True]
            gate_counts["fpp_computed"] = int(surv["fpp"].notna().sum())
            gate_counts["fpp_computed_in_frozen_top30"] = int(frozen_rows["fpp"].notna().sum())
            gate_counts["extra_expensive_outside_frozen_top30"] = int((surv["extra_expensive"] == True).sum())
            gate_counts["G8_fpp_le_0.5"] = int((frozen_rows["G8_fpp_packet"] == True).sum())
            gate_counts["G8_fpp_gt_0.5"] = int((frozen_rows["G8_fpp_packet"] == False).sum())
        if len(rejected):
            rejected.to_csv(out_dir / "crossmatch_rejected.csv", index=False)
    else:
        gate_counts["survivors_ranked"] = 0

    df.drop(columns=[c for c in df.columns if c.startswith("_")], errors="ignore").to_csv(
        out_dir / "candidates.csv", index=False)
    surv.to_csv(out_dir / "survivors.csv", index=False)
    (out_dir / "gate_counts.json").write_text(json.dumps(gate_counts, indent=1), encoding="utf-8")
    summary = summarize_run(recs, targets, prefetch_recs)
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    pd.DataFrame(per_target_rows(recs, prefetch_recs)).to_csv(out_dir / "per_target_log.csv", index=False)
    print(json.dumps(gate_counts, indent=1))
    print(f"status: {summary['status_counts']}  wall median {summary['wall_s'].get('median')} s  "
          f"p90 {summary['wall_s'].get('p90')} s  max {summary['wall_s'].get('max')} s")
    print(f"wrote {out_dir / 'candidates.csv'}, {out_dir / 'survivors.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
