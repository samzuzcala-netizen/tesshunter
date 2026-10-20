"""Turn the injection run and the no-injection (false-alarm) run into
``docs/COMPLETENESS.md``, a figure, and ``data/survey/completeness_v1.json``.

Recovery rule (fixed before the run was examined):

* ``recovered`` — an accepted candidate whose period is within 1% of the
  injected period AND whose transit windows overlap the injected ones
  (epoch difference modulo the period smaller than the larger of the two
  durations). ``recovered_clean`` additionally requires the automated
  verdict not to be "likely false positive".
* ``alias`` — the same epoch test at a period ratio within 1% of 2, 3, 1/2
  or 1/3 (partial credit, reported separately, never counted as recovered).
* ``missed`` — everything else, including a job that errored or timed out
  (those are counted and listed; they are misses of the pipeline as run).

Expected SNR per injection is measured on the star itself: the un-injected
cached curve is preprocessed exactly as the search does (flatten, 30-minute
bins), the robust per-bin scatter is 1.4826 x MAD, and the matched-filter
SNR is sqrt(sum_i delta_i^2) / sigma over the binned cadences the injected
model depresses (delta_i = 1 - model_i). It accounts for the real gaps, the
real noise and the real detrending, not a photon model.

SNR50 / SNR90 come from a two-parameter logistic in ln(SNR) fitted by
maximum likelihood; their 16/84 percentile intervals from 1000 bootstrap
resamples of the injections.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

PERIOD_BINS = [(1.0, 2.5), (2.5, 6.3), (6.3, 16.0), (16.0, 40.0)]
RP_BINS = [(0.01, 0.02), (0.02, 0.04), (0.04, 0.07), (0.07, 0.12)]
SNR_BINS = [(0, 5), (5, 7.1), (7.1, 9), (9, 12), (12, 20), (20, 50), (50, 1e9)]
VERDICT_FP = "likely false positive"


def _rel(path: Path) -> str:
    """Repo-relative posix path when inside the repo, else the absolute path."""
    try:
        return Path(path).resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _load_results(run_dir: Path) -> list[dict]:
    out = []
    for p in sorted((run_dir / "results").glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            out.append({"job_id": p.stem, "status": "corrupt"})
    return out


def _epoch_match(t0_inj: float, t0_found: float, period: float, tol_days: float) -> bool:
    d = (t0_found - t0_inj + 0.5 * period) % period - 0.5 * period
    return abs(d) <= tol_days


def classify(rec: dict) -> dict:
    """Recovery status of one injection job."""
    inj = rec.get("injection") or {}
    model = rec.get("injection_model") or {}
    res = rec.get("result") or {}
    planets = res.get("planets") or []
    p_inj = float(inj.get("period", np.nan))
    t0_inj = float(model.get("t0", np.nan))
    t14 = float(model.get("t14_days", 0.0) or 0.0)
    status = {"status": "missed", "matched_period": None, "matched_snr": None,
              "matched_verdict": None, "matched_rank": None, "clean": False, "ratio": None,
              "matched_stitch_snr": None, "matched_stitch_consistent": None, "matched_n_transits": None}
    if rec.get("status") != "ok" or not np.isfinite(p_inj):
        status["status"] = "job_" + str(rec.get("status"))
        return status
    best = None
    for p in planets:
        pf = float(p["period_days"])
        for ratio in (1.0, 2.0, 3.0, 0.5, 1.0 / 3.0):
            if abs(pf / (p_inj * ratio) - 1.0) < 0.01:
                base = min(pf, p_inj)
                tol = max(t14, float(p.get("duration_days", 0.0)), 0.02)
                if _epoch_match(t0_inj, float(p["epoch_btjd"]), base, tol):
                    cand = (0 if ratio == 1.0 else 1, -float(p.get("snr", 0.0)), ratio, p)
                    if best is None or cand[:2] < best[:2]:
                        best = cand
                break
    if best is None:
        return status
    _, _, ratio, p = best
    status["status"] = "recovered" if ratio == 1.0 else "alias"
    status["ratio"] = ratio
    status["matched_period"] = float(p["period_days"])
    status["matched_snr"] = float(p.get("snr", np.nan))
    status["matched_verdict"] = p.get("verdict")
    status["matched_rank"] = int(p.get("planet_num", 0))
    status["clean"] = bool(ratio == 1.0 and p.get("verdict") != VERDICT_FP)
    status["matched_stitch_snr"] = p.get("stitch_snr")
    status["matched_stitch_consistent"] = p.get("stitch_epoch_consistent")
    status["matched_n_transits"] = p.get("n_transits_observed")
    return status


def expected_snr_table(inj_recs: list[dict], sample_cfg_name: str, cache_dir: Path | None,
                       scratch: Path) -> dict[str, dict]:
    """Matched-filter expected SNR per injection from the un-injected star."""
    from tesshunter import preprocessing, survey

    cfg = survey.get_config(sample_cfg_name)
    by_tic: dict[int, list[dict]] = {}
    for r in inj_recs:
        if r.get("status") != "ok":
            continue
        by_tic.setdefault(int(r["tic_id"]), []).append(r)
    scratch.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict] = {}
    t_start = time.perf_counter()
    for i, (tic, recs) in enumerate(sorted(by_tic.items())):
        star_file = scratch / f"tic{tic}_noise.npz"
        if star_file.exists():
            with np.load(star_file) as z:
                bt, sigma = z["bt"], float(z["sigma"])
        else:
            lc, _prov, _info = survey.get_stitched(tic, cfg, cache_dir=cache_dir, allow_download=False)
            clean, _rec = preprocessing.preprocess(
                lc, sigma=cfg.sigma_clip, do_flatten=True, window_days=cfg.window_days,
                max_transit_duration_days=cfg.duration_max,
            )
            binned = preprocessing.bin_lightcurve(clean, bin_minutes=cfg.bin_minutes)
            bt = np.asarray(binned.time.value, dtype=float)
            bf = np.asarray(binned.flux.value, dtype=float)
            ok = np.isfinite(bf)
            resid = bf[ok] - np.nanmedian(bf[ok])
            sigma = float(1.4826 * np.median(np.abs(resid)))
            np.savez(star_file, bt=bt, sigma=sigma)
        for r in recs:
            m = r["injection_model"]
            model = survey.transit_model(
                bt, period=m["period"], t0=m["t0"], rp_rs=m["rp_rs"], b=m["b"], a_rs=m["a_rs"],
                u=(m["u1"], m["u2"]), exp_time_days=cfg.bin_minutes / 1440.0,
            )
            delta = 1.0 - model
            in_tr = delta > 0
            n_in = int(in_tr.sum())
            snr_mf = float(np.sqrt(np.sum(delta[in_tr] ** 2)) / sigma) if n_in and sigma > 0 else 0.0
            depth_mean = float(delta[in_tr].mean()) if n_in else 0.0
            snr_box = float(depth_mean * np.sqrt(n_in) / sigma) if n_in and sigma > 0 else 0.0
            n_tr = int(np.unique(np.round((bt[in_tr] - m["t0"]) / m["period"])).size) if n_in else 0
            out[r["job_id"]] = {"sigma_bin": sigma, "n_in_bins": n_in, "snr_expected": snr_mf,
                                "snr_box": snr_box, "n_transits_binned": n_tr,
                                "depth_mean_bin_ppm": depth_mean * 1e6}
        if (i + 1) % 25 == 0:
            print(f"  expected SNR: {i + 1}/{len(by_tic)} stars ({time.perf_counter() - t_start:.0f} s)", flush=True)
    return out


def logistic_fit(snr: np.ndarray, rec: np.ndarray, n_boot: int = 1000, seed: int = 1) -> dict:
    """MLE logistic in ln(SNR); SNR50/SNR90 with bootstrap intervals."""
    from scipy.optimize import minimize

    x = np.log(np.clip(snr, 1e-3, None))
    y = rec.astype(float)

    def nll(theta, x, y):
        a, b = theta
        z = a + b * x
        return float(np.sum(np.logaddexp(0.0, -z) * y + np.logaddexp(0.0, z) * (1.0 - y)))

    def fit(x, y):
        best = None
        for a0, b0 in ((-4.0, 2.0), (-2.0, 1.0), (-8.0, 4.0)):
            r = minimize(nll, np.array([a0, b0]), args=(x, y), method="Nelder-Mead",
                         options={"xatol": 1e-6, "fatol": 1e-8, "maxiter": 4000})
            if best is None or r.fun < best.fun:
                best = r
        a, b = best.x
        s50 = float(np.exp(-a / b)) if b > 0 else float("nan")
        s90 = float(np.exp((np.log(9.0) - a) / b)) if b > 0 else float("nan")
        return a, b, s50, s90

    a, b, s50, s90 = fit(x, y)
    rng = np.random.default_rng(seed)
    boots = []
    n = x.size
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        try:
            boots.append(fit(x[idx], y[idx])[2:])
        except Exception:
            continue
    boots = np.array(boots) if boots else np.full((1, 2), np.nan)
    return {"a": float(a), "b": float(b), "snr50": s50, "snr90": s90,
            "snr50_16_84": [float(np.nanpercentile(boots[:, 0], 16)), float(np.nanpercentile(boots[:, 0], 84))],
            "snr90_16_84": [float(np.nanpercentile(boots[:, 1], 16)), float(np.nanpercentile(boots[:, 1], 84))],
            "n": int(n), "n_boot": int(len(boots))}


def _binned_rate(x, ok, bins, log=False):
    rows = []
    for lo, hi in bins:
        m = (x >= lo) & (x < hi)
        n = int(m.sum())
        k = int(ok[m].sum())
        rows.append({"lo": lo, "hi": hi, "n": n, "k": k, "frac": (k / n) if n else float("nan")})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inj-run", required=True)
    ap.add_argument("--fa-run", required=True)
    ap.add_argument("--prefetch-run", default=None)
    ap.add_argument("--sample", default=str(REPO / "data" / "survey" / "completeness_sample_v1.csv"))
    ap.add_argument("--population", default=str(REPO / "data" / "survey" / "targets_v1.csv"))
    ap.add_argument("--config", default="survey_v1")
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--out-md", default=str(REPO / "docs" / "COMPLETENESS.md"))
    ap.add_argument("--out-json", default=str(REPO / "data" / "survey" / "completeness_v1.json"))
    ap.add_argument("--out-fig", default=str(REPO / "docs" / "figures" / "completeness_v1.png"))
    ap.add_argument("--scratch", default=str(REPO / "data" / "survey" / "cache" / "noise"))
    args = ap.parse_args()

    inj_run, fa_run = Path(args.inj_run), Path(args.fa_run)
    inj = _load_results(inj_run)
    fa = _load_results(fa_run)
    with open(args.sample, newline="", encoding="utf-8") as fh:
        sample = list(csv.DictReader(fh))
    with open(args.population, newline="", encoding="utf-8") as fh:
        n_population = sum(1 for _ in csv.DictReader(fh))
    cache_dir = Path(args.cache_dir) if args.cache_dir else None

    # ── injections ──
    print(f"injection jobs: {len(inj)}; computing expected SNR ...", flush=True)
    snr_tab = expected_snr_table(inj, args.config, cache_dir, Path(args.scratch))
    rows = []
    for r in inj:
        c = classify(r)
        m = r.get("injection_model") or {}
        i = r.get("injection") or {}
        s = snr_tab.get(r["job_id"], {})
        rows.append({
            "job_id": r["job_id"], "tic_id": r.get("tic_id"), "job_status": r.get("status"),
            "period": i.get("period"), "rp_rs": i.get("rp_rs"), "b": i.get("b"),
            "depth_model_ppm": m.get("depth_mean_in_transit_ppm"), "t14_days": m.get("t14_days"),
            "n_transits_with_data": m.get("n_transits_with_data"),
            "snr_expected": s.get("snr_expected"), "snr_box": s.get("snr_box"),
            "n_in_bins": s.get("n_in_bins"), "sigma_bin": s.get("sigma_bin"),
            "n_transits_binned": s.get("n_transits_binned"),
            "search_s": (r.get("timings") or {}).get("search"),
            "budget_stop": any("would not fit" in n for n in ((r.get("result") or {}).get("notes") or [])),
            **{f"rec_{k}": v for k, v in c.items()},
        })
    inj_csv = inj_run / "injection_outcomes.csv"
    if rows:
        keys = []
        for r in rows:
            for k in r:
                if k not in keys:
                    keys.append(k)
        with open(inj_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)

    ok_rows = [r for r in rows if r["job_status"] == "ok"]
    n_inj = len(rows)
    n_ok = len(ok_rows)
    status_counts = {}
    for r in rows:
        status_counts[r["rec_status"]] = status_counts.get(r["rec_status"], 0) + 1
    n_rec = status_counts.get("recovered", 0)
    n_clean = sum(1 for r in rows if r["rec_clean"])
    n_alias = status_counts.get("alias", 0)

    P = np.array([r["period"] for r in ok_rows], dtype=float)
    RP = np.array([r["rp_rs"] for r in ok_rows], dtype=float)
    B = np.array([r["b"] for r in ok_rows], dtype=float)
    SNR = np.array([r["snr_expected"] if r["snr_expected"] is not None else np.nan for r in ok_rows], dtype=float)
    NTR = np.array([r["n_transits_with_data"] or 0 for r in ok_rows], dtype=float)
    REC = np.array([r["rec_status"] == "recovered" for r in ok_rows])
    CLEAN = np.array([bool(r["rec_clean"]) for r in ok_rows])

    finite = np.isfinite(SNR) & (SNR > 0)
    fit_all = logistic_fit(SNR[finite], REC[finite])
    fit_clean = logistic_fit(SNR[finite], CLEAN[finite])
    ge3 = finite & (NTR >= 3)
    fit_ge3 = logistic_fit(SNR[ge3], REC[ge3]) if ge3.sum() > 20 else None
    by_ntr = _binned_rate(NTR, REC, [(0, 2), (2, 3), (3, 6), (6, 20), (20, 1e9)])

    SSNR = np.array([r["rec_matched_stitch_snr"] if r.get("rec_matched_stitch_snr") is not None else np.nan for r in ok_rows], dtype=float)
    SCONS = np.array([bool(r.get("rec_matched_stitch_consistent")) for r in ok_rows])
    conf_fits = {}
    for thr in (7.1, 9.0, 12.0):
        REC_T = REC & np.isfinite(SSNR) & (SSNR >= thr) & SCONS
        conf_fits[str(thr)] = {"n_recovered": int(REC_T.sum()),
                               "logistic": logistic_fit(SNR[finite], REC_T[finite]) if finite.sum() > 20 else None}
    by_period = _binned_rate(P, REC, PERIOD_BINS)
    by_rp = _binned_rate(RP, REC, RP_BINS)
    by_snr = _binned_rate(np.where(finite, SNR, -1), REC, SNR_BINS)
    by_b = _binned_rate(B, REC, [(0, 0.3), (0.3, 0.6), (0.6, 0.9)])
    map_pr = []
    for lo, hi in PERIOD_BINS:
        row = []
        for rlo, rhi in RP_BINS:
            m = (P >= lo) & (P < hi) & (RP >= rlo) & (RP < rhi)
            n = int(m.sum())
            k = int(REC[m].sum())
            row.append({"n": n, "k": k, "frac": (k / n) if n else float("nan")})
        map_pr.append(row)
    map_ps = []
    for lo, hi in PERIOD_BINS:
        row = []
        for slo, shi in SNR_BINS:
            m = (P >= lo) & (P < hi) & finite & (SNR >= slo) & (SNR < shi)
            n = int(m.sum())
            k = int(REC[m].sum())
            row.append({"n": n, "k": k, "frac": (k / n) if n else float("nan")})
        map_ps.append(row)

    # ── false alarms ──
    fa_ok = [r for r in fa if r.get("status") == "ok"]
    fa_cands = []
    for r in fa_ok:
        for p in ((r.get("result") or {}).get("planets") or []):
            fa_cands.append({"tic_id": r["tic_id"], "period": p["period_days"], "snr": p["snr"],
                             "depth_ppt": p["depth_ppt"], "duration_days": p["duration_days"],
                             "n_transits": p.get("n_transits_observed"), "verdict": p.get("verdict"),
                             "planet_num": p.get("planet_num"), "search": p.get("search"),
                             "stitch_snr": p.get("stitch_snr"), "stitch_n_transits": p.get("stitch_n_transits"),
                             "stitch_epoch_consistent": p.get("stitch_epoch_consistent")})
    n_fa_stars = len(fa_ok)
    fa_snr = np.array([c["snr"] for c in fa_cands], dtype=float)
    fa_nonfp = np.array([c["verdict"] != VERDICT_FP for c in fa_cands])
    fa_ntr = np.array([int(c.get("n_transits") or 0) for c in fa_cands], dtype=int)
    fa_by_ntr = {}
    for label, m in (("2 transits", fa_ntr == 2), (">=3 transits", fa_ntr >= 3)):
        fa_by_ntr[label] = {"n": int(m.sum()), "snr_ge9": int((m & (fa_snr >= 9)).sum()),
                            "snr_ge9_not_fp": int((m & (fa_snr >= 9) & fa_nonfp).sum()),
                            "per_star": float(m.sum() / n_fa_stars) if n_fa_stars else float("nan"),
                            "per_star_snr_ge9_not_fp": float((m & (fa_snr >= 9) & fa_nonfp).sum() / n_fa_stars) if n_fa_stars else float("nan")}
    fa_thresholds = {}
    for thr in (5.0, 7.1, 9.0, 12.0, 20.0):
        n_all = int((fa_snr >= thr).sum())
        n_nonfp = int(((fa_snr >= thr) & fa_nonfp).sum())
        fa_thresholds[str(thr)] = {"n_candidates": n_all, "n_not_fp_verdict": n_nonfp,
                                   "per_star": n_all / n_fa_stars if n_fa_stars else float("nan"),
                                   "per_star_not_fp": n_nonfp / n_fa_stars if n_fa_stars else float("nan"),
                                   "expected_in_population": (n_all / n_fa_stars * n_population) if n_fa_stars else float("nan"),
                                   "expected_in_population_not_fp": (n_nonfp / n_fa_stars * n_population) if n_fa_stars else float("nan")}
    stars_with_cand = len({c["tic_id"] for c in fa_cands})
    fa_ssnr = np.array([float(c["stitch_snr"]) if c.get("stitch_snr") is not None else np.nan for c in fa_cands], dtype=float)
    fa_scons = np.array([bool(c.get("stitch_epoch_consistent")) for c in fa_cands])
    fa_stitch_thresholds = {}
    for thr in (7.1, 9.0, 12.0, 20.0):
        m = np.isfinite(fa_ssnr) & (fa_ssnr >= thr) & fa_scons
        n_all = int(m.sum())
        n_nonfp = int((m & fa_nonfp).sum())
        n_ge3 = int((m & fa_nonfp & (fa_ntr >= 3)).sum())
        fa_stitch_thresholds[str(thr)] = {"n_candidates": n_all, "n_not_fp": n_nonfp, "n_not_fp_ge3_transits": n_ge3,
                                          "per_star_not_fp": n_nonfp / n_fa_stars if n_fa_stars else float("nan"),
                                          "expected_in_population_not_fp": (n_nonfp / n_fa_stars * n_population) if n_fa_stars else float("nan"),
                                          "per_star_not_fp_ge3": n_ge3 / n_fa_stars if n_fa_stars else float("nan"),
                                          "expected_in_population_not_fp_ge3": (n_ge3 / n_fa_stars * n_population) if n_fa_stars else float("nan")}
    fa_period_bins = _binned_rate(np.array([c["period"] for c in fa_cands] or [0.0]),
                                  np.ones(max(len(fa_cands), 1), dtype=bool),
                                  [(1, 2.5), (2.5, 6.3), (6.3, 16), (16, 40), (40, 100)])
    fa_search = np.array([(r.get("timings") or {}).get("search") or np.nan for r in fa_ok], dtype=float)
    fa_wall = np.array([r.get("wall_s") or np.nan for r in fa_ok], dtype=float)
    fa_budget = sum(1 for r in fa_ok if any("would not fit" in n for n in ((r.get("result") or {}).get("notes") or [])))
    fa_status = {}
    for r in fa:
        fa_status[r.get("status")] = fa_status.get(r.get("status"), 0) + 1
    fa_csv = fa_run / "false_alarm_candidates.csv"
    if fa_cands:
        with open(fa_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(fa_cands[0].keys()))
            w.writeheader()
            w.writerows(fa_cands)

    prefetch = None
    if args.prefetch_run:
        pre = _load_results(Path(args.prefetch_run))
        dl = np.array([(r.get("cache") or {}).get("download_s") or np.nan for r in pre if r.get("status") == "ok"], dtype=float)
        prefetch = {"n": int(np.isfinite(dl).sum()), "download_s_median": float(np.nanmedian(dl)) if dl.size else None,
                    "download_s_p90": float(np.nanpercentile(dl, 90)) if dl.size else None,
                    "download_s_max": float(np.nanmax(dl)) if dl.size else None}

    summary = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config": args.config, "sample_size_stars": len(sample), "population_size": n_population,
        "injections": {"n_total": n_inj, "n_ok": n_ok, "status_counts": status_counts,
                       "n_recovered": n_rec, "n_recovered_clean_verdict": n_clean, "n_alias": n_alias,
                       "frac_recovered_of_ok": (n_rec / n_ok) if n_ok else None,
                       "logistic_all": fit_all, "logistic_clean_verdict": fit_clean, "logistic_ge3_transits": fit_ge3,
                       "by_n_transits_in_data": by_ntr, "recovered_with_stitch_snr_at_least": conf_fits,
                       "by_period": by_period, "by_rp_rs": by_rp, "by_snr": by_snr, "by_b": by_b,
                       "map_period_x_rp": map_pr, "map_period_x_snr": map_ps,
                       "period_bins": PERIOD_BINS, "rp_bins": RP_BINS, "snr_bins": SNR_BINS,
                       "budget_stops": int(sum(1 for r in ok_rows if r["budget_stop"])),
                       "search_s_median": float(np.nanmedian([r["search_s"] for r in ok_rows if r["search_s"]])) if ok_rows else None},
        "false_alarms": {"n_stars_searched": n_fa_stars, "job_status_counts": fa_status,
                         "n_candidates": len(fa_cands), "n_stars_with_candidate": stars_with_cand,
                         "candidates_per_star": (len(fa_cands) / n_fa_stars) if n_fa_stars else None,
                         "by_snr_threshold": fa_thresholds, "by_period": fa_period_bins,
                         "by_n_transits": fa_by_ntr, "by_stitch_snr_threshold": fa_stitch_thresholds,
                         "budget_stops": int(fa_budget),
                         "search_s_median": float(np.nanmedian(fa_search)) if fa_search.size else None,
                         "search_s_p90": float(np.nanpercentile(fa_search, 90)) if fa_search.size else None,
                         "search_s_max": float(np.nanmax(fa_search)) if fa_search.size else None,
                         "wall_s_median": float(np.nanmedian(fa_wall)) if fa_wall.size else None,
                         "wall_s_p90": float(np.nanpercentile(fa_wall, 90)) if fa_wall.size else None,
                         "wall_s_max": float(np.nanmax(fa_wall)) if fa_wall.size else None},
        "prefetch": prefetch,
    }
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(summary, indent=1, default=float), encoding="utf-8")

    # ── figure ──
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
        ax = axes[0]
        grid = np.array([[c["frac"] for c in row] for row in map_pr])
        im = ax.imshow(grid, origin="lower", vmin=0, vmax=1, cmap="viridis", aspect="auto")
        ax.set_xticks(range(len(RP_BINS)))
        ax.set_xticklabels([f"{lo:g}-{hi:g}" for lo, hi in RP_BINS])
        ax.set_yticks(range(len(PERIOD_BINS)))
        ax.set_yticklabels([f"{lo:g}-{hi:g}" for lo, hi in PERIOD_BINS])
        ax.set_xlabel("Rp/R*")
        ax.set_ylabel("period (d)")
        ax.set_title(f"recovered fraction, {n_ok} injections on {len(sample)} stars")
        for i, row in enumerate(map_pr):
            for j, c in enumerate(row):
                ax.text(j, i, f"{c['k']}/{c['n']}", ha="center", va="center", color="w", fontsize=8)
        fig.colorbar(im, ax=ax)

        ax = axes[1]
        grid = np.array([[c["frac"] for c in row] for row in map_ps])
        im = ax.imshow(grid, origin="lower", vmin=0, vmax=1, cmap="viridis", aspect="auto")
        ax.set_xticks(range(len(SNR_BINS)))
        ax.set_xticklabels([f"{lo:g}-{hi:g}" if hi < 1e8 else f">{lo:g}" for lo, hi in SNR_BINS], rotation=45)
        ax.set_yticks(range(len(PERIOD_BINS)))
        ax.set_yticklabels([f"{lo:g}-{hi:g}" for lo, hi in PERIOD_BINS])
        ax.set_xlabel("expected SNR (matched filter, measured noise)")
        ax.set_ylabel("period (d)")
        ax.set_title("recovered fraction by period and SNR")
        for i, row in enumerate(map_ps):
            for j, c in enumerate(row):
                ax.text(j, i, f"{c['k']}/{c['n']}", ha="center", va="center", color="w", fontsize=7)
        fig.colorbar(im, ax=ax)

        ax = axes[2]
        s = SNR[finite]
        r = REC[finite]
        edges = np.exp(np.linspace(np.log(max(s.min(), 0.5)), np.log(s.max()), 14))
        cen, frac, err = [], [], []
        for lo, hi in zip(edges[:-1], edges[1:]):
            m = (s >= lo) & (s < hi)
            if m.sum() >= 5:
                cen.append(np.sqrt(lo * hi))
                frac.append(r[m].mean())
                err.append(np.sqrt(r[m].mean() * (1 - r[m].mean()) / m.sum()))
        ax.errorbar(cen, frac, yerr=err, fmt="o", color="k", label="binned injections")
        xs = np.exp(np.linspace(np.log(0.5), np.log(max(s.max(), 100)), 200))
        ax.plot(xs, 1 / (1 + np.exp(-(fit_all["a"] + fit_all["b"] * np.log(xs)))), "-", color="C0",
                label=f"logistic: SNR50={fit_all['snr50']:.1f}, SNR90={fit_all['snr90']:.1f}")
        ax.axvline(fit_all["snr50"], color="C0", ls=":")
        ax.axvline(fit_all["snr90"], color="C0", ls="--")
        ax.set_xscale("log")
        ax.set_xlabel("expected SNR")
        ax.set_ylabel("recovered fraction")
        ax.set_ylim(-0.02, 1.02)
        ax.legend(loc="lower right", fontsize=8)
        ax.set_title("completeness vs SNR")
        fig.tight_layout()
        Path(args.out_fig).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.out_fig, dpi=130)
        print(f"wrote {args.out_fig}")
    except Exception as exc:  # pragma: no cover
        print(f"figure failed: {exc}")

    # ── markdown ──
    def pct(x):
        return "n/a" if x is None or not np.isfinite(x) else f"{100 * x:.0f}%"

    L = []
    L.append("# Completeness and false-alarm rate of the survey search")
    L.append("")
    L.append(f"Generated by `scripts/analyze_completeness.py` on {summary['generated_utc']} from "
             f"`{_rel(inj_run)}` and `{_rel(fa_run)}`. Config preset `{args.config}` "
             f"(every field in `data/survey/completeness_v1.json`). The pipeline finds candidates; "
             f"nothing here is a detection.")
    L.append("")
    L.append("## 1. What was measured")
    L.append("")
    L.append(f"* Sample: {len(sample)} stars drawn at random (seed in `completeness_sample_v1.csv`) from the "
             f"{n_population}-star primary population `targets_v1.csv`.")
    L.append(f"* Injections: {n_inj} batman transits (quadratic limb darkening by Teff, a/R* from the TIC mass and "
             f"radius) multiplied into the cached stitched curves BEFORE detrending; period log-uniform 1-40 d in "
             f"four equally populated log bins, Rp/R* log-uniform {RP_BINS[0][0]}-{RP_BINS[-1][1]}, impact parameter "
             f"uniform 0-0.9, random phase. Every injection ran through the full search with the survey config.")
    L.append(f"* False alarms: the same {n_fa_stars} stars searched with no injection.")
    L.append("* Recovery rule (fixed before the run): accepted candidate with period within 1% of the injected "
             "period and overlapping transit windows. Period ratios of 2, 3, 1/2, 1/3 are `alias` (reported, not credited).")
    L.append("* Expected SNR: matched-filter SNR of the injected model on the star's own detrended, 30-minute-binned, "
             "un-injected curve (sigma = 1.4826 x MAD per bin), so gaps, noise and detrending are the real ones.")
    L.append("")
    L.append("## 2. Injection outcomes")
    L.append("")
    L.append(f"| outcome | n | share of {n_ok} completed jobs |")
    L.append("|---|---:|---:|")
    for k in ("recovered", "alias", "missed"):
        v = status_counts.get(k, 0)
        L.append(f"| {k} | {v} | {pct(v / n_ok) if n_ok else 'n/a'} |")
    others = {k: v for k, v in status_counts.items() if k not in ("recovered", "alias", "missed")}
    for k, v in others.items():
        L.append(f"| {k} | {v} | (job did not complete; counted as missed) |")
    L.append(f"| recovered with a verdict other than \"likely false positive\" | {n_clean} | {pct(n_clean / n_ok) if n_ok else 'n/a'} |")
    L.append("")
    L.append(f"Jobs that hit the detection time budget: {summary['injections']['budget_stops']} of {n_ok}. "
             f"Median search time per injection job: {summary['injections']['search_s_median']:.0f} s."
             if summary['injections']['search_s_median'] else "")
    L.append("")
    L.append("### SNR at which recovery crosses 50% and 90%")
    L.append("")
    L.append("| definition | n | SNR50 (16-84%) | SNR90 (16-84%) |")
    L.append("|---|---:|---|---|")
    for name, f in (("recovered (any verdict)", fit_all), ("recovered, verdict not FP", fit_clean),
                    ("recovered, injections with >= 3 transits in data", fit_ge3)):
        if f is None:
            continue
        L.append(f"| {name} | {f['n']} | {f['snr50']:.1f} ({f['snr50_16_84'][0]:.1f}-{f['snr50_16_84'][1]:.1f}) | "
                 f"{f['snr90']:.1f} ({f['snr90_16_84'][0]:.1f}-{f['snr90_16_84'][1]:.1f}) |")
    L.append("")
    L.append("### Recovery when the candidate must also pass the whole-stitch re-measurement")
    L.append("")
    L.append("Chunk candidates are re-measured on the full stitched curve (`stitch_snr`, epoch within one duration). "
             "Requiring a stitch SNR above a threshold is the lever against chunk-local false alarms; its cost:")
    L.append("")
    L.append("| stitch SNR >= | recovered (of " + str(n_ok) + ") | SNR50 | SNR90 |")
    L.append("|---|---:|---:|---:|")
    for thr, v in conf_fits.items():
        f = v["logistic"]
        L.append(f"| {thr} | {v['n_recovered']} | {f['snr50']:.1f} | {f['snr90']:.1f} |" if f else f"| {thr} | {v['n_recovered']} | n/a | n/a |")
    L.append("")
    L.append("### Recovered fraction by period, radius ratio, impact parameter and expected SNR")
    L.append("")
    L.append("| period (d) | n | recovered | fraction |")
    L.append("|---|---:|---:|---:|")
    for r in by_period:
        L.append(f"| {r['lo']:g}-{r['hi']:g} | {r['n']} | {r['k']} | {pct(r['frac'])} |")
    L.append("")
    L.append("| Rp/R* | n | recovered | fraction |")
    L.append("|---|---:|---:|---:|")
    for r in by_rp:
        L.append(f"| {r['lo']:g}-{r['hi']:g} | {r['n']} | {r['k']} | {pct(r['frac'])} |")
    L.append("")
    L.append("| impact parameter | n | recovered | fraction |")
    L.append("|---|---:|---:|---:|")
    for r in by_b:
        L.append(f"| {r['lo']:g}-{r['hi']:g} | {r['n']} | {r['k']} | {pct(r['frac'])} |")
    L.append("")
    L.append("| transits of the injection with data | n | recovered | fraction |")
    L.append("|---|---:|---:|---:|")
    for r in by_ntr:
        lab = f"{int(r['lo'])}-{int(r['hi']) - 1}" if r['hi'] < 1e8 else f">= {int(r['lo'])}"
        L.append(f"| {lab} | {r['n']} | {r['k']} | {pct(r['frac'])} |")
    L.append("")
    L.append("| expected SNR | n | recovered | fraction |")
    L.append("|---|---:|---:|---:|")
    for r in by_snr:
        lab = f"{r['lo']:g}-{r['hi']:g}" if r['hi'] < 1e8 else f">= {r['lo']:g}"
        L.append(f"| {lab} | {r['n']} | {r['k']} | {pct(r['frac'])} |")
    L.append("")
    L.append("### Completeness map (period x Rp/R*), recovered/injected")
    L.append("")
    L.append("| period \\ Rp/R* | " + " | ".join(f"{lo:g}-{hi:g}" for lo, hi in RP_BINS) + " |")
    L.append("|---|" + "---:|" * len(RP_BINS))
    for (lo, hi), row in zip(PERIOD_BINS, map_pr):
        L.append(f"| {lo:g}-{hi:g} | " + " | ".join(f"{c['k']}/{c['n']} ({pct(c['frac'])})" for c in row) + " |")
    L.append("")
    L.append("### Completeness map (period x expected SNR), recovered/injected")
    L.append("")
    L.append("| period \\ SNR | " + " | ".join((f"{lo:g}-{hi:g}" if hi < 1e8 else f">= {lo:g}") for lo, hi in SNR_BINS) + " |")
    L.append("|---|" + "---:|" * len(SNR_BINS))
    for (lo, hi), row in zip(PERIOD_BINS, map_ps):
        L.append(f"| {lo:g}-{hi:g} | " + " | ".join(f"{c['k']}/{c['n']} ({pct(c['frac'])})" for c in row) + " |")
    L.append("")
    L.append(f"Figure: `{_rel(args.out_fig)}`.")
    L.append("")
    L.append("## 3. False-alarm rate (no injection)")
    L.append("")
    L.append(f"{n_fa_stars} stars searched (job status counts: {fa_status}); {len(fa_cands)} accepted candidates on "
             f"{stars_with_cand} stars, {summary['false_alarms']['candidates_per_star']:.2f} per star; "
             f"{fa_budget} searches hit the detection time budget.")
    L.append("")
    L.append("| SNR threshold | candidates | per star | expected in the "
             f"{n_population}-star population | of which verdict not FP | per star | expected in population |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for thr, v in fa_thresholds.items():
        L.append(f"| >= {thr} | {v['n_candidates']} | {v['per_star']:.3f} | {v['expected_in_population']:.1f} | "
                 f"{v['n_not_fp_verdict']} | {v['per_star_not_fp']:.3f} | {v['expected_in_population_not_fp']:.1f} |")
    L.append("")
    L.append("| stitch SNR >= (epoch-consistent) | candidates | verdict not FP | per star | expected in population | not FP and >= 3 transits | per star | expected in population |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for thr, v in fa_stitch_thresholds.items():
        L.append(f"| {thr} | {v['n_candidates']} | {v['n_not_fp']} | {v['per_star_not_fp']:.3f} | {v['expected_in_population_not_fp']:.1f} | "
                 f"{v['n_not_fp_ge3_transits']} | {v['per_star_not_fp_ge3']:.3f} | {v['expected_in_population_not_fp_ge3']:.1f} |")
    L.append("")
    L.append("| candidates by transit count | n | SNR >= 9 | SNR >= 9 and verdict not FP | per star (SNR >= 9, not FP) | expected in population |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for lab, v in fa_by_ntr.items():
        L.append(f"| {lab} | {v['n']} | {v['snr_ge9']} | {v['snr_ge9_not_fp']} | {v['per_star_snr_ge9_not_fp']:.3f} | {v['per_star_snr_ge9_not_fp'] * n_population:.1f} |")
    L.append("")
    L.append("| candidate period (d) | n |")
    L.append("|---|---:|")
    for r in fa_period_bins:
        L.append(f"| {r['lo']:g}-{r['hi']:g} | {r['n'] if fa_cands else 0} |")
    L.append("")
    L.append(f"Candidate list: `{_rel(fa_csv)}`. A real signal in the sample would appear "
             "here too; the hard stop guarantees only that no catalogued object is present.")
    L.append("")
    L.append("## 4. Wall clock on the same stars")
    L.append("")
    fa_ = summary["false_alarms"]
    L.append(f"Search stage (cached stitched curve, no download), {n_fa_stars} stars: median "
             f"{fa_['search_s_median']:.0f} s, 90th percentile {fa_['search_s_p90']:.0f} s, max {fa_['search_s_max']:.0f} s. "
             f"Whole worker process including Python start-up and cache load: median {fa_['wall_s_median']:.0f} s, "
             f"90th percentile {fa_['wall_s_p90']:.0f} s, max {fa_['wall_s_max']:.0f} s."
             if fa_['search_s_median'] else "No timing available.")
    if prefetch and prefetch["download_s_median"] is not None:
        L.append(f"MAST search plus download of every survey-author product, {prefetch['n']} stars: median "
                 f"{prefetch['download_s_median']:.0f} s, 90th percentile {prefetch['download_s_p90']:.0f} s, "
                 f"max {prefetch['download_s_max']:.0f} s (run once; the stitched cache serves every later search).")
    L.append("")
    L.append("## 5. How to read these numbers")
    L.append("")
    L.append("* Completeness is measured only inside the injected grid (1-40 d, Rp/R* 0.01-0.12, b < 0.9) on this "
             "sample; the survey searches to 100 d, and nothing here says what happens between 40 and 100 d.")
    L.append("* The SNR axis is the matched-filter SNR on this pipeline's own detrended, binned data, which is "
             "the quantity the packet quotes. It is not the SNR a different detrending would give.")
    L.append("* `alias` recoveries would be caught by a human looking at the folded curve at 2P or P/2; they are "
             "not credited because the automated ranking would carry the wrong period.")
    L.append("* Injections into stars that already carry a real or systematic signal compete with it for the "
             "detection slots; that competition is part of the measured completeness by design.")
    L.append("")
    Path(args.out_md).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {args.out_md} and {args.out_json}")
    print(json.dumps({"recovered": n_rec, "alias": n_alias, "n_ok": n_ok, "snr50": fit_all["snr50"],
                      "snr90": fit_all["snr90"], "fa_per_star": summary["false_alarms"]["candidates_per_star"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
