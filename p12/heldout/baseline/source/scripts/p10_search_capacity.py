"""Prompt 10 Part 2b: search capacity and ranking, measured (HANDOFF_P10.md section 0.3).

Variants (``tesshunter.survey.PRESETS``; ingestion identical, so every variant reads the same
stitched cache): (a) survey_p8, (b) survey_p10_budget (2,700 s), (c) survey_p10_slots (6 per
subsearch, 24 merged, top 16), (d) survey_p10_rank ((c) ranked by resolved SNR), (e)
survey_p10_both ((d) at 2,700 s).  Every run records the BLS / alias traces and a
per-partition ``budget_exhausted`` flag (``record_traces``).

    subset    the injections with snr_expected in [6, 30) from the P8 outcomes; the
              pre-registered wall projection decides whether they are subsampled to 600
              (seed 20260908); the FA stars are never subsampled
    run       run_survey.py for the variants given, injections then the 300 FA stars
    metrics   R_7_15 and R_15_30 (P8 injection match; the P9 event-match rule as a second
              column), FA_pre, FA_S where measured, median wall, the budget-exhaustion
              fraction, and every injection lost to ranking with the competing score
    decide    the pre-registered rule, and which of (d) / (e) the better of (b) / (c) selects

PRE-REGISTERED DECISION RULE (HANDOFF_P10.md 0.3): choose the variant with the highest
R_7_15 among those with FA_pre <= 1.5 x FA_pre(a) and median wall <= 3 x median wall(a); if
no eligible variant improves R_7_15 by at least 5 percentage points over (a), keep survey_p8's
search fields for survey_p10 and write that search capacity is not where the loss is; ties
in R_7_15 go to the cheaper variant.  The fourth variant is (e) if R_7_15(b) > R_7_15(c),
else (d).

Nothing here submits anything anywhere.  The pipeline finds candidates.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data" / "cache" / "lightkurve"))
os.environ.setdefault("TESSHUNTER_OFFLINE", "1")

P8 = REPO / "data" / "survey" / "p8"
RUNS = REPO / "data" / "survey" / "runs" / "p10_2b"
RES = REPO / "p10" / "results"
LOGS = REPO / "p10" / "logs"
SUBSET = REPO / "data" / "survey" / "p10" / "injections_2b.csv"
FA_SAMPLE = REPO / "data" / "survey" / "completeness_sample_p8.csv"
PY = sys.executable

VARIANTS = {"a": "survey_p8", "b": "survey_p10_budget", "c": "survey_p10_slots", "d": "survey_p10_rank", "e": "survey_p10_both"}
SEED = 20260908
WORKERS = 24
#: [A, 0.3] the projection's per-job wall by variant: the P8 mean 240 s, three times that
#: for the 2,700-s budget, 1.5 times for the doubled slots.
PROJECTION_S = {"a": 240.0, "b": 720.0, "c": 360.0}
MAX_PROJECTED_HOURS = 16.0
SUBSAMPLE_TO = 600
BINS = {"R_7_15": (7.0, 15.0), "R_15_30": (15.0, 30.0)}
BAND = (6.0, 30.0)
FA_PRE_FACTOR, WALL_FACTOR, MIN_GAIN_PP = 1.5, 3.0, 5.0
PREGATE = {"snr": 7.1, "n_transits": 3}


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def outcomes():
    return list(csv.DictReader((P8 / "injection_outcomes_p8.csv").open(newline="", encoding="utf-8")))


# ─────────────────────────────────────────────────────────────────────────────
# the subset and the projection
# ─────────────────────────────────────────────────────────────────────────────
def make_subset() -> dict:
    rows = outcomes()
    band = sorted(r["job_id"] for r in rows if BAND[0] <= float(r["snr_expected"]) < BAND[1])
    n_all = len(band)
    projected_h = (n_all + 300) * sum(PROJECTION_S.values()) / WORKERS / 3600.0
    subsampled = projected_h > MAX_PROJECTED_HOURS
    selected = band
    if subsampled:
        rng = np.random.default_rng(SEED)
        selected = sorted(rng.choice(band, size=SUBSAMPLE_TO, replace=False).tolist())
    spec = list(csv.DictReader((REPO / "data" / "survey" / "injections_p8.csv").open(newline="", encoding="utf-8")))
    keep = set(selected)
    SUBSET.parent.mkdir(parents=True, exist_ok=True)
    with SUBSET.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(spec[0].keys()))
        w.writeheader()
        for r in spec:
            if r["job_id"] in keep:
                w.writerow(r)
    snr = {r["job_id"]: float(r["snr_expected"]) for r in rows}
    info = {"generated_utc": utc(), "band": list(BAND), "n_in_band": n_all, "projection_hours_three_variants": round(projected_h, 2),
            "projection_rule": f"(N_inj + 300) x {sum(PROJECTION_S.values()):.0f} s / {WORKERS} workers; subsample to {SUBSAMPLE_TO} if > {MAX_PROJECTED_HOURS} h",
            "subsampled": subsampled, "seed": SEED, "n_selected": len(selected),
            "projection_hours_selected": round((len(selected) + 300) * sum(PROJECTION_S.values()) / WORKERS / 3600.0, 2),
            "per_bin_selected": {k: sum(1 for j in selected if lo <= snr[j] < hi) for k, (lo, hi) in BINS.items()},
            "per_bin_in_band": {k: sum(1 for j in band if lo <= snr[j] < hi) for k, (lo, hi) in BINS.items()},
            "subset_csv": str(SUBSET.relative_to(REPO))}
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "search_capacity_subset.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")
    return info


# ─────────────────────────────────────────────────────────────────────────────
# the runs
# ─────────────────────────────────────────────────────────────────────────────
def timeout_for(preset: str) -> float:
    from tesshunter.survey import get_config
    return 1500.0 if get_config(preset).time_budget_s <= 900.0 else 4500.0


def run_variant(v: str, kinds=("inj", "fa"), workers: int = WORKERS) -> dict:
    preset = VARIANTS[v]
    LOGS.mkdir(parents=True, exist_ok=True)
    out = {}
    for kind in kinds:
        run_dir = RUNS / f"{v}_{kind}"
        cmd = [PY, str(REPO / "scripts" / "run_survey.py"), "--config", preset, "--overrides", json.dumps({"record_traces": True}),
               "--out", str(run_dir), "--concurrency", str(workers), "--timeout", str(timeout_for(preset)), "--resume", "--no-download"]
        cmd += ["--injections", str(SUBSET)] if kind == "inj" else ["--sample", str(FA_SAMPLE)]
        t0 = time.perf_counter()
        with (LOGS / f"search_capacity_{v}_{kind}.log").open("a", encoding="utf-8") as log:
            log.write(f"\n=== {utc()} {' '.join(cmd)}\n")
            log.flush()
            code = subprocess.run(cmd, cwd=str(REPO), stdout=log, stderr=subprocess.STDOUT).returncode
        out[kind] = {"preset": preset, "run_dir": str(run_dir.relative_to(REPO)), "exit": code, "wall_h": round((time.perf_counter() - t0) / 3600, 3)}
        print(v, kind, out[kind], flush=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# the metrics
# ─────────────────────────────────────────────────────────────────────────────
def load_results(run_dir: Path) -> list[dict]:
    return [read(p) for p in sorted((run_dir / "results").glob("*.json"))]


_TIMES: dict = {}


def star_times(tic: int) -> np.ndarray:
    """The star's cadence times (sectors >= 56, harmonised to 200 s) for the P9 event match."""
    if tic not in _TIMES:
        from tesshunter.survey_p8 import harmonise_cadence, load_audit_products
        prods, _ = harmonise_cadence(load_audit_products(tic, REPO / "data" / "survey" / "audit_lc", sector_min=56), 200 / 60)
        _TIMES[tic] = np.sort(np.concatenate([p["time"][np.isfinite(p["time"]) & np.isfinite(p["flux"])] for p in prods]))
    return _TIMES[tic]


def p9_match(rec: dict) -> dict:
    """The P9 registered event match (period within 1%, >= 3 one-to-one matched observed
    centres covering >= 50% of both truth and found opportunities), imported read-only."""
    sys.path.insert(0, str(REPO / "p9"))
    import scoring as p9scoring
    model = rec.get("injection_model") or {}
    inj = rec.get("injection") or {}
    truth = {"period": float(inj["period"]), "epoch_btjd": float(model["t0"]), "duration_hours": 24.0 * float(model.get("t14_days") or 0.0)}
    times = star_times(int(rec["tic_id"]))
    best = None
    for p in ((rec.get("result") or {}).get("planets") or []):
        m = p9scoring.match_signal(times, truth, {"period": p["period_days"], "t0": p["epoch_btjd"], "duration": p["duration_days"]}, 1)
        if m["matched"] and (best is None or m["matched_events"] > best["matched_events"]):
            best = dict(m, period_days=p["period_days"], planet_num=p.get("planet_num"))
    return {"matched": best is not None, "best": best}


def gates_pass(res: dict, cfg) -> bool:
    try:
        return (float(res.get("snr", 0)) >= cfg.snr_min_resolved and float(res.get("event_completeness", float("nan"))) >= cfg.min_event_completeness
                and float(res.get("composite_score", res.get("snr", 0))) >= cfg.min_composite_score
                and int(res.get("n_transits_observed", 0) or 0) >= cfg.min_transits)
    except (TypeError, ValueError):
        return False


def ranking_loss(rec: dict, cfg, trace_path: Path) -> dict | None:
    """For a missed injection: did a trial at the injected period pass every internal gate in
    some pass and lose the pass to a higher-scoring candidate?  Returns the witness."""
    if not trace_path.exists():
        return {"trace": "missing"}
    p_inj = float((rec.get("injection") or {}).get("period", np.nan))
    events = [json.loads(l) for l in trace_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_pass: dict = {}
    for e in events:
        if e["event"] == "alias":
            by_pass.setdefault((e["partition"], e["pass"]), []).append(e["resolved"])
    key = (lambda r: float(r["snr"])) if cfg.rank_by == "snr" else (lambda r: float(r.get("composite_score", r["snr"])))
    witnesses = []
    for (part, k), trials in by_pass.items():
        passing = [t for t in trials if gates_pass(t, cfg)]
        mine = [t for t in passing if abs(float(t["period_days"]) / p_inj - 1) < 0.01]
        if not mine or not passing:
            continue
        winner = max(passing, key=key)
        if abs(float(winner["period_days"]) / p_inj - 1) < 0.01:
            continue
        witnesses.append({"partition": part, "pass": k, "injection_score": key(mine[0]), "injection_snr": float(mine[0]["snr"]),
                          "competing_period": float(winner["period_days"]), "competing_score": key(winner), "competing_snr": float(winner["snr"]),
                          "n_passing_trials": len(passing)})
    slots = {s["label"]: {"n_planets": len(s.get("planets") or []), "max_planets": cfg.max_planets, "budget_exhausted": s.get("budget_exhausted")}
             for s in rec.get("searches") or []}
    return {"trace": "read", "lost_to_ranking": bool(witnesses), "witnesses": witnesses, "partitions": slots}


def metrics(v: str) -> dict:
    from analyze_completeness import classify
    from tesshunter.survey import get_config
    cfg = get_config(VARIANTS[v])
    snr = {r["job_id"]: float(r["snr_expected"]) for r in outcomes()}
    inj_dir, fa_dir = RUNS / f"{v}_inj", RUNS / f"{v}_fa"
    inj = load_results(inj_dir) if inj_dir.exists() else []
    fa = load_results(fa_dir) if fa_dir.exists() else []
    out = {"variant": v, "preset": VARIANTS[v], "config": cfg.to_dict(), "n_inj_results": len(inj), "n_fa_results": len(fa),
           "inj_status": {}, "fa_status": {}}
    for r in inj:
        out["inj_status"][r.get("status")] = out["inj_status"].get(r.get("status"), 0) + 1
    for r in fa:
        out["fa_status"][r.get("status")] = out["fa_status"].get(r.get("status"), 0) + 1
    rows = []
    for r in inj:
        c = classify(r)
        m9 = p9_match(r) if r.get("status") == "ok" else {"matched": False, "best": None}
        row = {"job_id": r["job_id"], "tic_id": r["tic_id"], "snr_expected": snr.get(r["job_id"]), "status": c["status"],
               "recovered_p8": c["status"] == "recovered", "matched_p9": m9["matched"], "wall_s": r.get("wall_s"),
               "budget_exhausted_any": any(s.get("budget_exhausted") for s in r.get("searches") or []),
               "n_partitions": len(r.get("searches") or []),
               "n_partitions_exhausted": sum(1 for s in r.get("searches") or [] if s.get("budget_exhausted"))}
        if not row["recovered_p8"] and r.get("status") == "ok":
            row["ranking"] = ranking_loss(r, cfg, inj_dir / "traces" / f"{r['job_id']}.jsonl")
        rows.append(row)
    out["injections"] = rows
    for name, (lo, hi) in BINS.items():
        sel = [x for x in rows if x["snr_expected"] is not None and lo <= x["snr_expected"] < hi and x["status"] != "job_error"]
        out[name] = {"n": len(sel), "recovered_p8": sum(x["recovered_p8"] for x in sel),
                     "rate_p8": (sum(x["recovered_p8"] for x in sel) / len(sel)) if sel else None,
                     "matched_p9": sum(x["matched_p9"] for x in sel), "rate_p9": (sum(x["matched_p9"] for x in sel) / len(sel)) if sel else None}
    lost = [x for x in rows if (x.get("ranking") or {}).get("lost_to_ranking")]
    out["ranking_losses"] = {"n": len(lost), "n_missed_with_trace": sum(1 for x in rows if (x.get("ranking") or {}).get("trace") == "read"),
                             "witnesses": [{"job_id": x["job_id"], "snr_expected": x["snr_expected"], **w} for x in lost for w in x["ranking"]["witnesses"]]}
    # false alarms
    pre = []
    for r in fa:
        planets = (r.get("result") or {}).get("planets") or [] if r.get("status") == "ok" else []
        n_pre = sum(1 for p in planets if p.get("stitch_epoch_consistent") and float(p.get("stitch_snr") or 0) >= PREGATE["snr"]
                    and int(p.get("stitch_n_transits") or 0) >= PREGATE["n_transits"])
        pre.append({"tic_id": r["tic_id"], "n_accepted": len(planets), "n_pregate": n_pre, "wall_s": r.get("wall_s"),
                    "n_partitions": len(r.get("searches") or []), "n_partitions_exhausted": sum(1 for s in r.get("searches") or [] if s.get("budget_exhausted"))})
    n_fa_ok = sum(1 for r in fa if r.get("status") == "ok")
    out["false_alarms"] = {"n_stars": len(fa), "n_ok": n_fa_ok, "accepted_per_star": (sum(x["n_accepted"] for x in pre) / n_fa_ok) if n_fa_ok else None,
                           "FA_pre": (sum(x["n_pregate"] for x in pre) / n_fa_ok) if n_fa_ok else None, "n_pregate_total": sum(x["n_pregate"] for x in pre),
                           "FA_S": None, "FA_S_note": "A + secondary on the pre-gate passers; measured separately (funnel) where run"}
    walls_all = [float(x["wall_s"]) for x in rows + pre if x.get("wall_s") is not None]
    walls_fa = [float(x["wall_s"]) for x in pre if x.get("wall_s") is not None]
    parts = sum(x["n_partitions"] for x in rows + pre)
    exh = sum(x["n_partitions_exhausted"] for x in rows + pre)
    out["wall"] = {"median_s_all": float(np.median(walls_all)) if walls_all else None, "median_s_fa": float(np.median(walls_fa)) if walls_fa else None,
                   "p90_s_all": float(np.percentile(walls_all, 90)) if walls_all else None, "sum_job_hours": round(sum(walls_all) / 3600, 2),
                   "budget_exhausted_partition_fraction": (exh / parts) if parts else None, "n_partitions": parts,
                   "jobs_with_any_exhaustion_fraction": (sum(1 for x in rows + pre if x["n_partitions_exhausted"]) / len(rows + pre)) if rows + pre else None}
    return out


def all_metrics(variants) -> dict:
    RES.mkdir(parents=True, exist_ok=True)
    res = {"generated_utc": utc(), "subset": read(RES / "search_capacity_subset.json") if (RES / "search_capacity_subset.json").exists() else None,
           "variants": {v: metrics(v) for v in variants}}
    (RES / "search_capacity_metrics.json").write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8")
    return res


def decide(res: dict) -> dict:
    vs = res["variants"]
    a = vs.get("a")
    if a is None or a["R_7_15"]["rate_p8"] is None or a["false_alarms"]["FA_pre"] is None:
        return {"complete": False, "reason": "variant (a) not measured"}
    fa_cap = FA_PRE_FACTOR * a["false_alarms"]["FA_pre"]
    wall_cap = WALL_FACTOR * a["wall"]["median_s_all"]
    table = []
    for v, m in vs.items():
        r = m["R_7_15"]["rate_p8"]
        fa_pre = m["false_alarms"]["FA_pre"]
        wall = m["wall"]["median_s_all"]
        complete = (r is not None and fa_pre is not None and wall is not None and m["n_inj_results"] > 0 and m["n_fa_results"] > 0)
        elig = complete and fa_pre <= fa_cap and wall <= wall_cap
        table.append({"variant": v, "preset": m["preset"], "R_7_15": r, "R_7_15_p9": m["R_7_15"]["rate_p9"], "R_15_30": m["R_15_30"]["rate_p8"],
                      "FA_pre": fa_pre, "median_wall_s": wall, "budget_exhausted_fraction": m["wall"]["budget_exhausted_partition_fraction"],
                      "gain_pp_over_a": None if r is None else round(100 * (r - a["R_7_15"]["rate_p8"]), 2),
                      "complete": complete, "eligible": elig})
    elig = [t for t in table if t["eligible"]]
    best = sorted(elig, key=lambda t: (-t["R_7_15"], t["median_wall_s"]))[0] if elig else None
    improved = best is not None and best["gain_pp_over_a"] >= MIN_GAIN_PP
    chosen = best["variant"] if improved else "a"
    fourth = None
    if "b" in vs and "c" in vs and vs["b"]["R_7_15"]["rate_p8"] is not None and vs["c"]["R_7_15"]["rate_p8"] is not None:
        fourth = "e" if vs["b"]["R_7_15"]["rate_p8"] > vs["c"]["R_7_15"]["rate_p8"] else "d"
    dec = {"rule": ("highest R_7_15 among variants with FA_pre <= 1.5 x FA_pre(a) and median wall <= 3 x median wall(a); "
                    "keep survey_p8 unless the best eligible variant improves R_7_15 by >= 5 percentage points; ties to the cheaper variant"),
           "fa_pre_cap": fa_cap, "wall_cap_s": wall_cap, "table": table, "best_eligible": None if best is None else best["variant"],
           "improves_by_5pp": improved, "chosen": chosen, "chosen_preset": VARIANTS[chosen],
           "fourth_variant": fourth, "fourth_variant_rule": "(e) if R_7_15(b) > R_7_15(c) else (d)",
           "search_capacity_is_not_where_the_loss_is": (not improved)}
    res["decision"] = dec
    (RES / "search_capacity_metrics.json").write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8")
    (RES / "search_capacity.md").write_text(markdown(res), encoding="utf-8")
    return dec


def markdown(res: dict) -> str:
    a = ["# Part 2b: search capacity and ranking, measured [M]\n", f"Generated {res['generated_utc']}.\n"]
    s = res.get("subset") or {}
    a.append(f"Injections with snr_expected in [6, 30): {s.get('n_in_band')}; projection for three variants {s.get('projection_hours_three_variants')} h "
             f"({s.get('projection_rule')}); subsampled: {s.get('subsampled')}; selected {s.get('n_selected')} (seed {s.get('seed')}); "
             f"per bin selected {s.get('per_bin_selected')}; FA stars 300, never subsampled.\n")
    a.append("| variant | preset | R_7_15 (P8 match) | R_7_15 (P9 event match) | R_15_30 | FA_pre | median wall (s) | budget-exhausted partitions | gain (pp) | eligible |")
    a.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    dec = res.get("decision") or {}
    for t in dec.get("table", []):
        m = res["variants"][t["variant"]]
        a.append(f"| {t['variant']} | {t['preset']} | {m['R_7_15']['recovered_p8']}/{m['R_7_15']['n']} ({100 * (t['R_7_15'] or 0):.1f}%) | "
                 f"{m['R_7_15']['matched_p9']}/{m['R_7_15']['n']} ({100 * (t['R_7_15_p9'] or 0):.1f}%) | "
                 f"{m['R_15_30']['recovered_p8']}/{m['R_15_30']['n']} ({100 * (t['R_15_30'] or 0):.1f}%) | "
                 f"{m['false_alarms']['n_pregate_total']}/{m['false_alarms']['n_ok']} = {t['FA_pre'] if t['FA_pre'] is None else round(t['FA_pre'], 3)} | "
                 f"{None if t['median_wall_s'] is None else round(t['median_wall_s'], 1)} | "
                 f"{None if t['budget_exhausted_fraction'] is None else round(t['budget_exhausted_fraction'], 3)} | {t['gain_pp_over_a']} | {'yes' if t['eligible'] else 'no'} |")
    a.append("")
    if dec:
        a.append(f"**Decision ({dec['rule']}): `{dec['chosen_preset']}` (best eligible {dec['best_eligible']}, improves by >= 5 pp: {dec['improves_by_5pp']}); "
                 f"fourth variant by the (b)/(c) rule: {dec['fourth_variant']}.**\n")
    for v, m in res["variants"].items():
        rl = m["ranking_losses"]
        a.append(f"Variant {v}: {rl['n']} injections lost to ranking among {rl['n_missed_with_trace']} misses with a trace; "
                 f"jobs with any exhausted partition {m['wall']['jobs_with_any_exhaustion_fraction']}; injection statuses {m['inj_status']}, FA statuses {m['fa_status']}.")
        for w in rl["witnesses"][:12]:
            a.append(f"  - {w['job_id']} (snr_expected {w['snr_expected']:.1f}): {w['partition']} pass {w['pass']}, injection score {w['injection_score']:.2f} "
                     f"(SNR {w['injection_snr']:.1f}) lost to P = {w['competing_period']:.4f} d at score {w['competing_score']:.2f} (SNR {w['competing_snr']:.1f})")
    return "\n".join(a) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("subset")
    r = sub.add_parser("run"); r.add_argument("--variants", default="a,b,c"); r.add_argument("--kinds", default="inj,fa"); r.add_argument("--workers", type=int, default=WORKERS)
    m = sub.add_parser("metrics"); m.add_argument("--variants", default="a,b,c")
    d = sub.add_parser("decide"); d.add_argument("--variants", default="a,b,c")
    args = ap.parse_args(argv)
    if args.cmd == "subset":
        print(json.dumps(make_subset(), indent=1))
    elif args.cmd == "run":
        for v in args.variants.split(","):
            run_variant(v, tuple(args.kinds.split(",")), args.workers)
    elif args.cmd == "metrics":
        res = all_metrics(args.variants.split(","))
        print(json.dumps({v: {k: res["variants"][v][k] for k in ("R_7_15", "R_15_30", "false_alarms", "wall")} for v in res["variants"]}, indent=1, default=str))
    elif args.cmd == "decide":
        res = all_metrics(args.variants.split(","))
        print(json.dumps(decide(res), indent=1, default=str))
        print((RES / "search_capacity.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
