# P10-routed original P8 yield engine. The original numerical yield, geometry,
# limb darkening, occurrence, contamination and impact-grid functions are retained.
# Claimed fraction 0.03 is explicit for every detectability class. Legacy P8
# diagnostic fields are named as such and never decide P10 Stop Rule 1.
"""Prompt 8 Part 1f: the expectation through the funnel, and the stop rule.

Replaces the prompt-1 adopted efficiencies and the prompt-4 step function with this prompt's
measured recovery curve (``data/survey/p8/completeness_p8.json``): per star and per occurrence
cell, the matched-filter SNR of the cell's planet is computed on the star's OWN prepared
native-cadence series (its measured per-cadence scatter and its actual cadence count), not
from a photon model, and the through-funnel recovery curve gives P_detect.

    expected new signals = sum_stars sum_cells rate(cell) x P_transit x P_detect(SNR) x (1 - prior)

* occurrence: the Dressing & Charbonneau 2015 grid (Teff <= 4000 K) already transcribed in
  ``tesshunter.occurrence_grids``, clipped to the search band 0.5-30 d, with the adopted
  4-20 Earth-radius rate of 0.01 per star [P1];
* sensitivity (not the central model): Hardegree-Ullman et al. 2019, AJ 158, 75
  (arXiv:1905.05900), 1.19 (+0.70 / -0.49) planets per star at 0.5-2.5 Earth radii and 0.5-10 d
  for M3V-M5V, applied as a rescaling of the DC15 cells inside that box;
* P_detect: the logistic fit in ln SNR of the through-funnel recovery of the prompt-8
  injections (search + pre-gate + Stage A + secondary gate), the central curve; the
  search-only curve is reported for comparison;
* prior completeness: the prompt-1 faint M-dwarf priors, high / mid / low, with the
  prompt-1 detectability classes evaluated from the same measured noise;
* the impact parameter is averaged over b in {0, 0.3, 0.6, 0.85}, and the in-transit cadence
  count is the phase-averaged expectation (T14 / P x the star's cadence count).

Stop rule, fixed before the measurement: if the mid-prior expectation through the funnel is
below 3.0 the search does not run.  The high-prior number is reported next to it; if it is
below 1.0 the handoff says so in its first line.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data" / "cache" / "lightkurve"))

P8 = REPO / "p10/results/part2d_calibration_20260912/yield_model"
TARGETS = REPO / "data" / "survey" / "targets_p8.csv"
COMPLETENESS = REPO / "data/survey/p10/part2d/calibration/completeness_p10.json"
CONFIG = "survey_p10"

STOP_RULE = {"mid_prior_min_expected_through_funnel": 3.0, "high_prior_warn_below": 1.0,
             "fixed": "PROMPT_P8.md Part 1f, before any measurement"}
B_GRID = [0.0, 0.3, 0.6, 0.85]
HU19 = {"citation": "Hardegree-Ullman, Cushing, Muirhead & Christiansen 2019, AJ 158, 75 (arXiv:1905.05900)",
        "url": "https://arxiv.org/abs/1905.05900",
        "rate_per_star": 1.19, "err_plus": 0.70, "err_minus": 0.49, "rp_earth": [0.5, 2.5], "period_days": [0.5, 10.0],
        "spectral_types": "M3V-M5V (overall); M3V 0.86, M4V 1.36, M5V 3.07",
        "transcription": "abstract, verified 2026-09-05; overall M3V-M5V rate and its asymmetric errors",
        "shape_assumption": "rescale the DC15-supported portion of 0.5-2.5 Re x 0.5-10 d, including partial cells uniformly in log P and log R; DC15 starts at 1 Re, so the HU19 total is assigned to 1-2.5 Re. This is a sensitivity proxy, not a transcription of a radius-period distribution."}
R_EARTH_RSUN = 0.009168


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def star_noise(tic: int, cfg) -> dict | None:
    """Per-cadence scatter, cadence count and span of the prepared native-cadence series."""
    from tesshunter import survey_p8
    try:
        lc, prov, _ = survey_p8.get_prepared(tic, cfg)
    except Exception:
        return None
    f = np.asarray(lc.flux.value, dtype=float)
    t = np.asarray(lc.time.value, dtype=float)
    ok = np.isfinite(f)
    if ok.sum() < 100:
        return None
    resid = f[ok] - np.nanmedian(f[ok])
    sigma = float(1.4826 * np.median(np.abs(resid)))
    cad = float(np.nanmedian(np.diff(np.sort(t[ok]))))
    sectors = np.asarray(lc.meta.get("TESSHUNTER_SECTOR", []))
    n_sec = len(prov.get("units_used", []))
    return {"sigma": sigma, "n_cad": int(ok.sum()), "cadence_days": cad, "span_days": float(t[ok].max() - t[ok].min()),
            "data_days": float(ok.sum() * cad), "n_sectors": n_sec, "rot": prov.get("rotation_proxy")}


def cached_star_noise(tic: int, cfg) -> tuple[int, dict | None]:
    root = P8 / "noise_p10"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"tic{tic}_{cfg.ingest_key()}.json"
    if path.exists():
        return tic, json.loads(path.read_text(encoding="utf-8"))
    raise RuntimeError(f"Missing preverified P10 noise copy for TIC {tic}; no original cache is written or inferred")


def measure_population_noise(rows: list[dict], cfg, workers: int = 4) -> dict[int, dict]:
    """Checkpoint per star; building the prepared curves involves no search or network request."""
    by_tic = {}
    pending = [int(r["tic_id"]) for r in rows]
    started = time.perf_counter()
    for attempt in range(2):
        with ProcessPoolExecutor(max_workers=workers) as pool:
            tasks = {pool.submit(cached_star_noise, tic, cfg): tic for tic in pending}
            failed = []
            for future in as_completed(tasks):
                tic = tasks[future]
                try:
                    _, noise = future.result()
                except Exception as exc:
                    print(f"noise TIC {tic}: {type(exc).__name__}: {exc}", flush=True)
                    noise = None
                if noise is None:
                    failed.append(tic)
                else:
                    by_tic[tic] = noise
                if len(by_tic) % 100 == 0:
                    print(f"noise {len(by_tic)}/{len(rows)} stars, {(time.perf_counter() - started) / 60:.1f} min", flush=True)
        pending = failed
        if not pending:
            break
    summary = {"generated_utc": utc(), "config": cfg.to_dict(), "n_targets": len(rows),
               "n_measured": len(by_tic), "failed_after_retry": pending,
               "seconds": time.perf_counter() - started}
    (P8 / "noise_summary_p10.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    if pending:
        raise RuntimeError(f"noise unavailable after retry for {len(pending)} targets: {pending}; no stop decision made")
    return by_tic


def box_fraction(cell: dict) -> float:
    """Fraction of a DC15 cell inside the HU19 box, using the adopted log-uniform cell shape."""
    fraction = 1.0
    for prefix, bounds in (("p", HU19["period_days"]), ("r", HU19["rp_earth"])):
        lo, hi = cell[f"{prefix}_lo"], cell[f"{prefix}_hi"]
        a, b = max(lo, bounds[0]), min(hi, bounds[1])
        if b <= a:
            return 0.0
        fraction *= math.log(b / a) / math.log(hi / lo)
    return fraction


def remaining_fraction(classes: dict, prior: dict, level: str) -> float:
    """Apply incumbent-search priors to this cell's classes before summing detected yield."""
    total = sum(classes.values())
    if total <= 0:
        return 1.0 - prior["B"][level]
    return sum(classes[k] * (1.0 - prior[k][level]) for k in classes) / total


def ld_shape_factor(rp_rs: float, a_rs: float, b: float, u: tuple[float, float]) -> tuple[float, float]:
    """(T14 in days, sqrt(<delta^2>_in-transit) / (rp_rs^2)) for a limb-darkened model, so that the
    matched-filter SNR = rp_rs^2 x factor x sqrt(N_in) / sigma, on a fine grid over one transit."""
    from tesshunter.survey import transit_duration_days, transit_model
    t14 = transit_duration_days(1.0, a_rs, b, rp_rs)          # period 1 d: T14 in days for a/R* given at P=1
    if t14 <= 0:
        return 0.0, 0.0
    tt = np.linspace(-0.5 * t14, 0.5 * t14, 401)
    m = transit_model(tt, period=1.0, t0=0.0, rp_rs=rp_rs, b=b, a_rs=a_rs, u=u, exp_time_days=None)
    d = 1.0 - m
    return t14, float(np.sqrt(np.mean(d ** 2)) / rp_rs ** 2)


def logistic(snr: np.ndarray, a: float, b: float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(a + b * np.log(np.clip(snr, 1e-3, None)))))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--targets", default=str(TARGETS))
    ap.add_argument("--completeness", default=str(COMPLETENESS))
    ap.add_argument("--out", default=str(P8 / "expected_yield_p10_engine.json"))
    ap.add_argument("--noise-only", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)
    from tesshunter import occurrence_grids as og, survey, survey_yield as sy
    from tesshunter.survey import a_over_rs, limb_darkening_for_teff

    cfg = survey.get_config(CONFIG)
    rows = list(csv.DictReader(open(args.targets, newline="", encoding="utf-8")))
    noise_by_tic = measure_population_noise(rows, cfg, args.workers)
    if args.noise_only:
        return
    comp = json.loads(Path(args.completeness).read_text(encoding="utf-8"))
    curves = {name: comp["levels"][name].get("logistic") for name in comp["levels"]}
    central_curve = curves["full_funnel_with_pregate"]
    search_curve = curves["search_only"]
    if not central_curve or not search_curve:
        raise SystemExit("the completeness file has no logistic fit for the central level")
    cells = sy.occurrence_cells("m", sy.CENTRAL_MODEL["m"], cfg.period_max, p_min=cfg.period_min)
    # the HU19 rescaling of the cells inside its box
    in_box = [c for c in cells if box_fraction(c) > 0]
    dc15_box = sum(c["rate"] * box_fraction(c) for c in in_box)
    hu_scale = HU19["rate_per_star"] / dc15_box if dc15_box > 0 else 1.0
    fills = sy.contamination_fills(pd.Series(
        [float(r["contamination_ratio"]) for r in rows if r.get("contamination_ratio") not in ("", None, "nan")],
        dtype=float,
    ))
    fill = fills["measured_median"]
    prior = {cls: {level: 0.03 for level in ("low", "mid", "high")} for cls in ("A", "B", "C")}
    d = sy.DETECTION
    per_star, n_no_noise = [], 0
    t0 = time.perf_counter()
    for i, r in enumerate(rows):
        tic = int(r["tic_id"])
        noise = noise_by_tic[tic]
        if noise is None:
            n_no_noise += 1
            per_star.append({"tic_id": tic, "available": False})
            continue
        rstar = float(r["radius_rsun"]); mstar = float(r["mass_msun"]) if r.get("mass_msun") not in ("", "nan") else rstar
        teff = float(r["teff_k"]) if r.get("teff_k") not in ("", "nan") else 3300.0
        contam = float(r["contamination_ratio"]) if r.get("contamination_ratio") not in ("", "nan") else fill
        u = limb_darkening_for_teff(teff)
        sig, ncad, cad, span = noise["sigma"], noise["n_cad"], noise["cadence_days"], noise["span_days"]
        n_sec = max(noise["n_sectors"], 1)
        tot = {k: 0.0 for k in ("funnel", "search", "A", "B", "C", "funnel_hu19")}
        new = {level + suffix: 0.0 for level in ("low", "mid", "high") for suffix in ("", "_hu19", "_search_only")}
        cell_rows = []
        for c in cells:
            if c["rate"] <= 0:
                continue
            pmid = float(np.sqrt(c["p_lo"] * c["p_hi"]))
            rp_rs = c["r_rep"] * R_EARTH_RSUN / max(rstar, 0.05)
            a_rs = a_over_rs(pmid, mstar, rstar)
            pgeo = float(np.clip((1.0 + rp_rs) / a_rs, 0, 1))
            hu = 1.0 + (hu_scale - 1.0) * box_fraction(c)
            pdet_f, pdet_s, pa, pb_, pc_ = 0.0, 0.0, 0.0, 0.0, 0.0
            for b in B_GRID:
                if b >= 1.0 + rp_rs:
                    continue
                t14, fac = ld_shape_factor(rp_rs, a_rs, b, u)
                t14 *= pmid                              # T14 scales with P at fixed a/R*
                if t14 <= 0:
                    continue
                n_in = (t14 / pmid) * ncad               # phase-averaged in-transit cadences over the whole series
                depth_eff = rp_rs ** 2 / (1.0 + contam)
                snr = depth_eff * fac * math.sqrt(max(n_in, 0.0)) / sig
                n_tr = noise["data_days"] / pmid
                pd_f = float(logistic(np.array([snr]), central_curve["a"], central_curve["b"])[0])
                pd_s = float(logistic(np.array([snr]), search_curve["a"], search_curve["b"])[0])
                pdet_f += pd_f / len(B_GRID)
                pdet_s += pd_s / len(B_GRID)
                # prompt-1 classes on the measured noise: A single-sector SNR >= 9 with >= 2 transits per sector
                n_in_sec = n_in / n_sec
                snr_sec = depth_eff * fac * math.sqrt(max(n_in_sec, 0.0)) / sig
                n_tr_sec = d["sector_days"] * d["duty_cycle"] / pmid
                a_ = sy._ramp(snr_sec, d["single_sector_snr_for_prior_search"]) if n_tr_sec >= d["min_transits"] else 0.0
                s9 = sy._ramp(snr, d["class_b_snr"]) if n_tr >= d["min_transits"] else 0.0
                s7 = sy._ramp(snr, d["snr_threshold"]) if n_tr >= d["min_transits"] else 0.0
                pa += float(a_) / len(B_GRID); pb_ += float(max(s9 - a_, 0.0)) / len(B_GRID); pc_ += float(max(s7 - s9, 0.0)) / len(B_GRID)
                classes = {"A": float(a_), "B": float(max(s9 - a_, 0.0)), "C": float(max(s7 - s9, 0.0))}
                for level in ("low", "mid", "high"):
                    weight = c["rate"] * pgeo * remaining_fraction(classes, prior, level) / len(B_GRID)
                    new[level] += weight * pd_f
                    new[level + "_hu19"] += weight * pd_f * hu
                    new[level + "_search_only"] += weight * pd_s
            tot["funnel"] += c["rate"] * pgeo * pdet_f
            tot["funnel_hu19"] += c["rate"] * hu * pgeo * pdet_f
            tot["search"] += c["rate"] * pgeo * pdet_s
            tot["A"] += c["rate"] * pgeo * pa; tot["B"] += c["rate"] * pgeo * pb_; tot["C"] += c["rate"] * pgeo * pc_
            cell_rows.append({"cell": c["label"], "pgeo": pgeo, "pdet_funnel": pdet_f, "pdet_search": pdet_s})
        per_star.append({"tic_id": tic, "available": True, "sigma_ppt": 1000 * sig, "n_cadences": ncad, "n_sectors": n_sec,
                         "span_days": span, "detectable_through_funnel": tot["funnel"], "detectable_search_only": tot["search"],
                         "class_A": tot["A"], "class_B": tot["B"], "class_C": tot["C"], "new": new,
                         "rotation_amp_ppt": (noise["rot"] or {}).get("semi_amplitude_ppt")})
        if (i + 1) % 200 == 0:
            print(f"{i + 1}/{len(rows)} stars in {(time.perf_counter() - t0) / 60:.1f} min", flush=True)
    avail = [p for p in per_star if p["available"]]
    n_av = len(avail)
    sums = {}
    for key in ("low", "mid", "high", "low_hu19", "mid_hu19", "high_hu19", "low_search_only", "mid_search_only", "high_search_only"):
        sums[key] = float(sum(p["new"][key] for p in avail))
    detect = {"funnel": float(sum(p["detectable_through_funnel"] for p in avail)),
              "search_only": float(sum(p["detectable_search_only"] for p in avail)),
              "class_A": float(sum(p["class_A"] for p in avail)), "class_B": float(sum(p["class_B"] for p in avail)),
              "class_C": float(sum(p["class_C"] for p in avail))}
    fa = comp.get("false_alarms") or {}
    fa_per_star = fa.get("stageA_pass_and_secondary_per_star")
    fa_expected = (fa_per_star * n_av) if fa_per_star is not None else None
    stop = sums["mid"] < STOP_RULE["mid_prior_min_expected_through_funnel"]
    out = {"generated_utc": utc(), "config": CONFIG, "n_targets": len(rows), "n_stars_with_prepared_curve": n_av,
           "n_stars_without": n_no_noise, "p8_legacy_yield_check_not_p10_stop_rule": STOP_RULE,
           "calibration": {"source": str(Path(args.completeness).resolve()), "generated_utc": comp["generated_utc"],
                           "rules_version": comp["rules_version"], "n_injections": comp["n_injections"],
                           "n_stars": comp["n_stars"], "stages": ["search", "pre-gate", "Stage A", "secondary"]},
           "recovery_curves": {"central_through_funnel": central_curve, "search_only": search_curve,
                               "all_levels": curves},
           "occurrence": {"model": sy.CENTRAL_MODEL["m"], "period_band_days": [cfg.period_min, cfg.period_max],
                          "n_cells": len(cells), "adopted_giants": og.DC15_M_GIANTS_ADOPTED,
                          "sensitivity_hu19": dict(HU19, dc15_rate_in_box=dc15_box, scale_applied=hu_scale, n_cells_in_box=len(in_box))},
           "prior_completeness": prior, "prior_application": "per occurrence cell and impact parameter, before summing detected yield",
           "impact_parameter_grid": B_GRID, "contamination_fill": fill,
           "model_assumptions": [
               "The SNR-marginal logistic calibration is applied to each occurrence cell and each star.",
               "Occurrence cells use representative radius and geometric-midpoint period; phase-averaged transit coverage uses the measured cadence count.",
               "Impact parameters have equal weights on the recorded grid; the SNR shape calculation uses an instantaneous limb-darkened model.",
               "The 1-4 Earth-radius injection calibration is extrapolated in SNR to the adopted giant-planet component.",
               "Uninjected control passers are treated as the false-alarm budget and extrapolated at a constant rate per star.",
               "Later Stage B, blind TLS and Stage D losses are uncalibrated and can only reduce the final candidate yield."],
           "detectable_planets_total": detect,
           "expected_new_signals": {"through_funnel": {"low": sums["low"], "mid": sums["mid"], "high": sums["high"]},
                                    "through_funnel_hu19": {"low": sums["low_hu19"], "mid": sums["mid_hu19"], "high": sums["high_hu19"]},
                                    "search_only": {"low": sums["low_search_only"], "mid": sums["mid_search_only"], "high": sums["high_search_only"]}},
           "expected_funnel_passing_false_alarms": fa_expected, "false_alarm_budget": fa,
           "signal_to_false_alarm_ratio_mid": (sums["mid"] / fa_expected) if fa_expected else None,
           "p8_legacy_yield_diagnostic_not_p10_decision": {"stop": bool(stop), "mid_prior_expectation": sums["mid"], "high_prior_expectation": sums["high"],
                        "high_prior_below_1": bool(sums["high"] < STOP_RULE["high_prior_warn_below"]),
                        "statement": ("STOP: the mid-prior expectation through the funnel is below 3.0; the search is not worth "
                                      "running on this population" if stop else
                                      "PROCEED: the mid-prior expectation through the funnel is 3.0 or more")},
           "per_star_quantiles": {"sigma_ppt": [float(x) for x in np.percentile([p["sigma_ppt"] for p in avail], [10, 50, 90])] if avail else None,
                                  "new_mid": [float(x) for x in np.percentile([p["new"]["mid"] for p in avail], [10, 50, 90])] if avail else None},
           "per_star": per_star}
    Path(args.out).write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("n_targets", "n_stars_with_prepared_curve", "detectable_planets_total",
                                          "expected_new_signals", "expected_funnel_passing_false_alarms",
                                          "signal_to_false_alarm_ratio_mid", "p8_legacy_yield_diagnostic_not_p10_decision")}, indent=1))


if __name__ == "__main__":
    main()
