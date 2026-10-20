"""Prompt 8 Part 1e: completeness and the false-alarm budget at native cadence, through the funnel.

Prompt 2 measured completeness of the search alone.  The expectation prompt 8 needs is
completeness of the search followed by the gates, because a signal the funnel kills is not
a candidate.  Both are measured here.

    python scripts/p8_completeness.py funnel --slices 16        # Stage A + secondary on every recovered injection
    python scripts/p8_completeness.py analyze                    # tables -> completeness_p8.json, docs/COMPLETENESS_P8.md

Inputs: the injection run (``data/survey/runs/inj_p8``, one job per row of
``data/survey/injections_p8.csv``), the false-alarm run (``data/survey/runs/fa_p8``, the same
300 stars with no injection) and its funnel (``scripts/p8_funnel.py --root data/survey/p8/fa_funnel``).

The injection funnel: every RECOVERED injection (period within 1% and overlapping transit
windows; aliases are reported, never credited) becomes one candidate under its own root
``data/survey/p8/inj_funnel/<job_id>/``, the store's products are re-injected in memory
(``flux`` and ``sap_flux`` alike, exactly as the search saw them) before ``audit_p5`` reads
them, and Stage A and the secondary scan run under the rule set given by ``--rules``.  The
pre-gate of the real funnel is recorded per injection, not applied, so its cost is visible.

Expected SNR: the matched-filter SNR of the injected model on the star's own UN-injected
prepared native-cadence series (the prompt-2 definition, sigma = 1.4826 x MAD per cadence).

Nothing here is a detection.  The agent never submits anything anywhere.
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

P8 = REPO / "data" / "survey" / "p8"
INJ_RUN = REPO / "data" / "survey" / "runs" / "inj_p8"
FA_RUN = REPO / "data" / "survey" / "runs" / "fa_p8"
INJ_ROOT = P8 / "inj_funnel"
FA_ROOT = P8 / "fa_funnel"
SPEC = REPO / "data" / "survey" / "injections_p8.csv"
SAMPLE = REPO / "data" / "survey" / "completeness_sample_p8.csv"
PY = sys.executable
CONFIG = "survey_p8"

from analyze_completeness import _binned_rate, _load_results, classify, logistic_fit   # noqa: E402

PERIOD_BINS_LOG = None      # filled from the spec's period_bin column
SNR_BINS = [(0, 5), (5, 7.1), (7.1, 9), (9, 12), (12, 20), (20, 50), (50, 1e9)]
RP_BINS = [(1.0, 1.41), (1.41, 2.0), (2.0, 2.83), (2.83, 4.0)]
TMAG_BINS = [(12.5, 13.0), (13.0, 13.5), (13.5, 14.0), (14.0, 14.5)]
ROT_EXTREME = 1e9  # existing upper reporting boundary; never a search or vetting gate
ROT_BINS = [(0.0, 0.5), (0.5, 1.0), (1.0, 3.0), (3.0, 10.0), (10.0, ROT_EXTREME),
            (ROT_EXTREME, np.inf)]  # include extreme raw-photometry proxies explicitly


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def kkey(tic: int, period: float) -> str:
    return f"tic{int(tic)}_P{float(period):.4f}"


# ─────────────────────────────────────────────────────────────────────────────
# expected SNR on the un-injected prepared curve
# ─────────────────────────────────────────────────────────────────────────────
def expected_snr(recs: list[dict], cache_dir: Path | None = None,
                 checkpoint_path: Path | None = None) -> dict[str, dict]:
    from tesshunter import survey, survey_p8

    cfg = survey.get_config(CONFIG)
    out: dict[str, dict] = (json.loads(checkpoint_path.read_text(encoding="utf-8"))
                            if checkpoint_path is not None and checkpoint_path.exists() else {})
    by_tic: dict[int, list[dict]] = {}
    for r in recs:
        if r.get("status") == "ok" and r.get("injection_model"):
            by_tic.setdefault(int(r["tic_id"]), []).append(r)
    for tic, rs in sorted(by_tic.items()):
        if all("snr_expected" in out.get(r["job_id"], {}) for r in rs):
            continue
        try:
            lc, prov, _ = survey_p8.get_prepared(tic, cfg, cache_dir=cache_dir)
        except Exception as exc:
            for r in rs:
                out[r["job_id"]] = {"error": str(exc)[:200]}
            continue
        t = np.asarray(lc.time.value, dtype=float)
        f = np.asarray(lc.flux.value, dtype=float)
        ok = np.isfinite(f)
        resid = f[ok] - np.nanmedian(f[ok])
        sigma = float(1.4826 * np.median(np.abs(resid)))
        cad = float(np.nanmedian(np.diff(np.sort(t[ok])))) if ok.sum() > 1 else 200.0 / 86400.0
        for r in rs:
            m = r["injection_model"]
            model = survey.transit_model(t[ok], period=m["period"], t0=m["t0"], rp_rs=m["rp_rs"], b=m["b"],
                                         a_rs=m["a_rs"], u=(m["u1"], m["u2"]), exp_time_days=cad)
            delta = 1.0 - model
            in_tr = delta > 0
            n_in = int(in_tr.sum())
            snr_mf = float(np.sqrt(np.sum(delta[in_tr] ** 2)) / sigma) if n_in and sigma > 0 else 0.0
            n_tr = int(np.unique(np.round((t[ok][in_tr] - m["t0"]) / m["period"])).size) if n_in else 0
            out[r["job_id"]] = {"sigma_cadence_ppt": 1000 * sigma, "n_in_transit_cadences": n_in,
                                "snr_expected": snr_mf, "n_transits_in_prepared": n_tr,
                                "depth_max_ppt": 1000 * float(delta.max()) if n_in else 0.0,
                                "rotation_proxy": prov.get("rotation_proxy")}
        if checkpoint_path is not None:
            tmp = checkpoint_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
            tmp.replace(checkpoint_path)
        print(f"expected SNR: {sum('snr_expected' in v for v in out.values())}/{sum(map(len, by_tic.values()))} injections", flush=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# the injection funnel
# ─────────────────────────────────────────────────────────────────────────────
CAND_COLS = ["rank", "tic_id", "planet_num", "search", "period_days", "epoch_btjd", "duration_days", "depth_ppt",
             "snr", "n_transits", "stitch_snr", "stitch_n_transits", "stitch_epoch_consistent", "verdict",
             "n_units", "tmag", "teff_k", "radius_rsun", "mass_msun", "ra_deg", "dec_deg", "job_id",
             "inj_period", "inj_t0", "inj_rp_rs", "inj_b", "inj_a_rs", "inj_u1", "inj_u2", "inj_rp_earth",
             "pregate_pass"]


def recovered_jobs(recs: list[dict]) -> list[dict]:
    """One funnel job per recovered injection (aliases and misses excluded)."""
    spec = {r["job_id"]: r for r in csv.DictReader(open(SPEC, newline="", encoding="utf-8"))}
    sample = {int(r["tic_id"]): r for r in csv.DictReader(open(SAMPLE, newline="", encoding="utf-8"))}
    jobs = []
    for r in recs:
        c = classify(r)
        if c["status"] != "recovered":
            continue
        planets = (r.get("result") or {}).get("planets") or []
        p = next(q for q in planets if abs(float(q["period_days"]) / c["matched_period"] - 1) < 1e-9)
        m = r["injection_model"]
        st = sample.get(int(r["tic_id"]), {})
        sp = spec.get(r["job_id"], {})
        pre = bool(p.get("stitch_epoch_consistent")) and (p.get("stitch_snr") or 0) >= 7.1 \
            and int(p.get("stitch_n_transits") or 0) >= 3
        jobs.append({"rank": 0, "tic_id": int(r["tic_id"]), "planet_num": p["planet_num"], "search": p.get("search"),
                     "period_days": p["period_days"], "epoch_btjd": p["epoch_btjd"], "duration_days": p["duration_days"],
                     "depth_ppt": p["depth_ppt"], "snr": p["snr"], "n_transits": p.get("n_transits_observed"),
                     "stitch_snr": p.get("stitch_snr"), "stitch_n_transits": p.get("stitch_n_transits"),
                     "stitch_epoch_consistent": p.get("stitch_epoch_consistent"), "verdict": p.get("verdict"),
                     "n_units": r.get("n_units"), "tmag": st.get("tmag"), "teff_k": st.get("teff_k"),
                     "radius_rsun": st.get("radius_rsun"), "mass_msun": st.get("mass_msun"),
                     "ra_deg": st.get("ra_deg"), "dec_deg": st.get("dec_deg"), "job_id": r["job_id"],
                     "inj_period": m["period"], "inj_t0": m["t0"], "inj_rp_rs": m["rp_rs"], "inj_b": m["b"],
                     "inj_a_rs": m["a_rs"], "inj_u1": m["u1"], "inj_u2": m["u2"], "inj_rp_earth": sp.get("rp_earth", ""),
                     "pregate_pass": pre})
    jobs.sort(key=lambda j: -float(j["snr"]))
    for i, j in enumerate(jobs, 1):
        j["rank"] = i
    return jobs


def write_job_root(job: dict) -> Path:
    root = INJ_ROOT / job["job_id"]
    root.mkdir(parents=True, exist_ok=True)
    for name in ("survivors.csv", "candidates.csv"):
        with open(root / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=CAND_COLS)
            w.writeheader()
            w.writerow({k: job.get(k) for k in CAND_COLS})
    return root


def install_injection(job: dict) -> None:
    """Make ``audit_p5.load_products`` return the star's products with this injection in
    every flux column, exactly as the search saw them."""
    import audit_p5 as A
    from tesshunter.survey_p8 import inject_products
    orig = A.__dict__.get("_load_products_uninjected") or A.load_products
    A._load_products_uninjected = orig

    def injected(tic: int) -> list[dict]:
        # Match the completed search exactly: select/harmonise products, then inject
        # at the exposure of the common-cadence product, before detrending or clipping.
        prods = A.choose_per_sector(orig(tic))
        prods = [dict(p, cadence_s=float(p.get("cadence_s") or 200.0)) for p in prods]
        out, _ = inject_products(prods, period=float(job["inj_period"]), t0=float(job["inj_t0"]),
                                 rp_rs=float(job["inj_rp_rs"]), b=float(job["inj_b"]), a_rs=float(job["inj_a_rs"]),
                                 u=(float(job["inj_u1"]), float(job["inj_u2"])))
        return out
    A.load_products = injected


def run_slice(index: int, nslices: int, rules: str, force: bool, queue: Path | None = None) -> None:
    from p8_worker_qos import configure_current_worker
    configure_current_worker()
    import p8_funnel as F
    recs = _load_results(INJ_RUN)
    jobs = recovered_jobs(recs)
    mine = jobs[index::nslices]
    if queue is None:
        work = iter(mine)
        print(f"slice {index}/{nslices}: {len(mine)} of {len(jobs)} recovered injections, rules {rules}", flush=True)
    else:
        from p8_work_queue import claims
        by_key = {j["job_id"]: j for j in jobs}
        work = (by_key[key] for key in claims(queue))
        print(f"worker {index}/{nslices}: shared queue of {len(jobs)} recovered injections, rules {rules}", flush=True)
    t0 = time.perf_counter()
    for i, job in enumerate(work, 1):
        root = write_job_root(job)
        F.set_root(root)
        F.set_rules(rules)
        install_injection(job)
        j = {"rank": job["rank"], "tic_id": job["tic_id"], "planet_num": job["planet_num"],
             "period": float(job["period_days"]), "epoch_btjd": float(job["epoch_btjd"]),
             "duration_days": float(job["duration_days"]), "depth_ppt": float(job["depth_ppt"]),
             "stitch_snr": float(job["stitch_snr"] or 0), "stitch_n_transits": int(job["stitch_n_transits"] or 0),
             "n_units": int(job["n_units"] or 0), "tmag": float(job["tmag"] or 0),
             "radius_rsun": job["radius_rsun"], "mass_msun": job["mass_msun"],
             "ra_deg": float(job["ra_deg"] or 0), "dec_deg": float(job["dec_deg"] or 0)}
        (root / "stageA").mkdir(exist_ok=True)
        (root / "secondary").mkdir(exist_ok=True)
        ra = F.V.stagea_one(j, threads=1, force=force)
        rs = F.secondary_one(dict(j, stageA_sample=(ra.get("decision") != "PASS")), force=force) \
            if ra.get("decision") in ("PASS", "FAIL") else {"gate": "SKIP", "seconds": 0}
        el = time.perf_counter() - t0
        progress = f"{index}:{i}/{len(mine)}" if queue is None else f"{index}:{i} shared"
        eta = f" eta {(el / i) * (len(mine) - i) / 60:.1f} min" if queue is None else ""
        print(f"[{progress}] {job['job_id']:<22} A {ra.get('decision'):<5} S {rs.get('gate'):<5} "
              f"{ra.get('seconds', 0):>6.1f}+{rs.get('seconds', 0):>5.1f} s | {str(ra.get('reason', ''))[:110]} | "
              f"elapsed {el / 60:.1f} min{eta}", flush=True)
    print(f"slice {index} DONE in {(time.perf_counter() - t0) / 60:.1f} min", flush=True)


def run_funnel(nslices: int, rules: str, force: bool, shared_queue: bool = False) -> None:
    INJ_ROOT.mkdir(parents=True, exist_ok=True)
    logdir = P8 / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    queue = None
    if shared_queue:
        from p8_work_queue import create_queue
        queue = logdir / f"injection_queue_{os.getpid()}_{time.time_ns()}.sqlite"
        create_queue(queue, [j["job_id"] for j in recovered_jobs(_load_results(INJ_RUN))])
    procs = []
    for i in range(nslices):
        log = open(logdir / f"inj_funnel_slice{i}.log", "w", encoding="utf-8")
        cmd = [PY, str(Path(__file__).resolve()), "slice", "--index", str(i), "--nslices", str(nslices), "--rules", rules]
        if force:
            cmd.append("--force")
        if queue is not None:
            cmd.extend(["--queue", str(queue)])
        procs.append((i, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=str(REPO)), log))
    codes = []
    for i, pr, log in procs:
        codes.append((i, pr.wait()))
        log.close()
    print("slice exit codes:", codes, flush=True)
    if any(code != 0 for _, code in codes):
        raise SystemExit(f"injection funnel: failed slices {codes}; rerun to resume")


# ─────────────────────────────────────────────────────────────────────────────
# analysis
# ─────────────────────────────────────────────────────────────────────────────
def require_settled_record(path: Path, rules: str, field: str, settled: tuple[str, ...]) -> dict:
    """Unfinished or stale vetting must never be counted as a missed injection or zero false alarms."""
    from audit_p5 import input_config_for
    from tesshunter.survey import get_config
    r = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if (r.get("rules_version") != rules or r.get("input_config") != input_config_for(get_config(CONFIG))
            or r.get(field) not in settled):
        raise ValueError(f"incomplete/stale {field} record: {path}; resume its funnel before analyzing")
    return r


def load_funnel_outcomes(jobs: list[dict], rules: str | None = None) -> dict[str, dict]:
    out = {}
    for j in jobs:
        root = INJ_ROOT / j["job_id"]
        k = kkey(j["tic_id"], j["period_days"])
        a = root / "stageA" / f"{k}.json"
        s = root / "secondary" / f"{k}.json"
        ra = json.loads(a.read_text(encoding="utf-8")) if a.exists() else {}
        rs = json.loads(s.read_text(encoding="utf-8")) if s.exists() else {}
        if rules is not None:
            ra = require_settled_record(a, rules, "decision", ("PASS", "FAIL"))
            rs = require_settled_record(s, rules, "gate", ("PASS", "FAIL", "HOLD"))
        out[j["job_id"]] = {"stageA": ra.get("decision"), "stageA_criteria": ra.get("criteria"),
                            "stageA_n_passed": ra.get("n_criteria_passed"), "chosen_ephemeris": ra.get("chosen_ephemeris"),
                            "kept_snr": (ra.get("per_ephemeris", {}).get(ra.get("chosen_ephemeris"), {}) or {}).get("kept_snr"),
                            "n_kept": (ra.get("per_ephemeris", {}).get(ra.get("chosen_ephemeris"), {}) or {}).get("n_kept"),
                            "depth_over_survey": (ra.get("per_ephemeris", {}).get(ra.get("chosen_ephemeris"), {}) or {}).get("depth_over_survey_depth"),
                            "secondary_gate": rs.get("gate"), "secondary_n_dips": (rs.get("secondary") or {}).get("n_dips_above_5sigma"),
                            "secondary_variability": rs.get("variability_flag"),
                            "gate_by_mode": (rs.get("secondary") or {}).get("gate_by_mode"),
                            "p_const_white": ((ra.get("per_ephemeris", {}).get(ra.get("chosen_ephemeris"), {}) or {}).get("det_kept") or {}).get("p_const_white"),
                            "p_const_inflated": ((ra.get("per_ephemeris", {}).get(ra.get("chosen_ephemeris"), {}) or {}).get("det_kept") or {}).get("p_const_inflated"),
                            "p_const": ((ra.get("per_ephemeris", {}).get(ra.get("chosen_ephemeris"), {}) or {}).get("det_kept") or {}).get("p_const"),
                            "stageA_seconds": ra.get("seconds"), "secondary_seconds": rs.get("seconds")}
    return out


def fa_funnel_counts(n_stars: int, rules: str | None = None) -> dict:
    """Candidates per star at each stage of the false-alarm funnel."""
    from p8_funnel import select_secondary_jobs
    coll = FA_ROOT / "collect_p8.json"
    if not coll.exists():
        return {"available": False}
    c = json.loads(coll.read_text(encoding="utf-8"))
    rows = sorted(csv.DictReader(open(FA_ROOT / "survivors.csv", newline="", encoding="utf-8")),
                  key=lambda r: int(r["rank"]))
    jobs = [{"tic_id": int(r["tic_id"]), "period": float(r["period_days"])} for r in rows]
    expected = {kkey(j["tic_id"], j["period"]) for j in jobs}
    if len(expected) != len(rows) or len(rows) != c["n_pass_pregate"]:
        raise ValueError("false-alarm pre-gate table does not match the collected population")
    dec = {}
    a_records = {}
    for st in ("stageA", "secondary"):
        d = FA_ROOT / st
        dec[st] = {}
        for p in d.glob("*.json") if d.exists() else []:
            r = json.loads(p.read_text(encoding="utf-8"))
            if r["key"] not in expected:
                continue
            dec[st][r["key"]] = r.get("decision") or r.get("gate")
            if st == "stageA":
                a_records[r["key"]] = r
    a_pass = [k for k, v in dec["stageA"].items() if v == "PASS"]
    secondary_jobs = select_secondary_jobs(jobs, dec["stageA"])
    sampled_failures = [kkey(j["tic_id"], j["period"]) for j in secondary_jobs if j["stageA_sample"]]
    if rules is not None:
        if c.get("n_stars_ok") != n_stars:
            raise ValueError("false-alarm search is incomplete")
        for row in rows:
            key = kkey(int(row["tic_id"]), float(row["period_days"]))
            require_settled_record(FA_ROOT / "stageA" / f"{key}.json", rules, "decision", ("PASS", "FAIL"))
        for key in a_pass + sampled_failures:
            require_settled_record(FA_ROOT / "secondary" / f"{key}.json", rules, "gate", ("PASS", "FAIL", "HOLD"))
    s_pass = [k for k in a_pass if dec["secondary"].get(k) in ("PASS", "HOLD")]
    criteria_failures = {}
    for record in a_records.values():
        for criterion, passed in (record.get("criteria") or {}).items():
            if not passed:
                criteria_failures[criterion] = criteria_failures.get(criterion, 0) + 1
    return {"available": True, "n_stars": n_stars, "n_stars_ok": c.get("n_stars_ok"),
            "accepted": c.get("n_accepted_candidates"), "accepted_per_star": c.get("n_accepted_candidates", 0) / max(n_stars, 1),
            "pregate": c.get("n_pass_pregate"), "pregate_per_star": c.get("n_pass_pregate", 0) / max(n_stars, 1),
            "stageA_done": len(dec["stageA"]), "stageA_pass": len(a_pass), "stageA_pass_per_star": len(a_pass) / max(n_stars, 1),
            "stageA_pass_and_secondary": len(s_pass), "stageA_pass_and_secondary_per_star": len(s_pass) / max(n_stars, 1),
            "stageA_criteria_fail_counts": criteria_failures,
            "stageA_failure_sample_n": len(sampled_failures),
            "stageA_failure_sample_gate": {gate: sum(dec["secondary"].get(k) == gate for k in sampled_failures)
                                           for gate in ("PASS", "FAIL", "HOLD")}}


def analyze(rules: str) -> dict:
    recs = _load_results(INJ_RUN)
    spec = {r["job_id"]: r for r in csv.DictReader(open(SPEC, newline="", encoding="utf-8"))}
    sample = list(csv.DictReader(open(SAMPLE, newline="", encoding="utf-8")))
    n_stars = len(sample)
    if len(recs) != len(spec) or any(r.get("status") != "ok" for r in recs):
        raise ValueError("injection search is incomplete; resume it before analyzing")
    jobs = recovered_jobs(recs)
    fun = load_funnel_outcomes(jobs, rules=rules)
    fa_counts = fa_funnel_counts(n_stars, rules=rules)
    cache = P8 / "expected_snr_p8.json"
    if cache.exists():
        esnr = json.loads(cache.read_text(encoding="utf-8"))
    else:
        esnr = expected_snr(recs, checkpoint_path=cache)
        cache.write_text(json.dumps(esnr, indent=1, default=float), encoding="utf-8")
    if any(not np.isfinite(esnr.get(r["job_id"], {}).get("snr_expected", np.nan)) for r in recs):
        raise ValueError("expected SNR is missing for an injection; resume the snr command")
    by_job = {j["job_id"]: j for j in jobs}
    rows = []
    for r in recs:
        c = classify(r)
        s = spec.get(r["job_id"], {})
        e = esnr.get(r["job_id"], {})
        j = by_job.get(r["job_id"])
        f = fun.get(r["job_id"], {})
        rec = {"job_id": r["job_id"], "tic_id": r.get("tic_id"), "status": c["status"], "ratio": c["ratio"],
               "period": float(s.get("period", np.nan)), "period_bin": int(s.get("period_bin", -1)),
               "rp_earth": float(s.get("rp_earth") or np.nan), "rp_rs": float(s.get("rp_rs", np.nan)),
               "b": float(s.get("b", np.nan)), "tmag": float(s.get("tmag") or np.nan),
               "snr_expected": e.get("snr_expected", np.nan), "n_transits_expected": e.get("n_transits_in_prepared"),
               "rot_amp_ppt": ((e.get("rotation_proxy") or {}).get("semi_amplitude_ppt")),
               "rot_period": ((e.get("rotation_proxy") or {}).get("peak_period_days")),
               "matched_snr": c["matched_snr"], "matched_stitch_snr": c["matched_stitch_snr"],
               "pregate": (j or {}).get("pregate_pass"), "stageA": f.get("stageA"), "secondary_gate": f.get("secondary_gate"),
               "kept_snr": f.get("kept_snr"), "n_kept": f.get("n_kept"), "depth_over_survey": f.get("depth_over_survey"),
               "stageA_criteria": f.get("stageA_criteria"), "gate_by_mode": f.get("gate_by_mode"),
               "p_const_white": f.get("p_const_white"), "p_const_inflated": f.get("p_const_inflated"),
               "wall_s": r.get("wall_s"), "job_status": r.get("status")}
        rec["recovered"] = c["status"] == "recovered"
        rec["through_pregate"] = bool(rec["recovered"] and rec["pregate"])
        rec["through_stageA"] = bool(rec["recovered"] and f.get("stageA") == "PASS")
        rec["through_funnel"] = bool(rec["through_stageA"] and f.get("secondary_gate") in ("PASS", "HOLD"))
        rec["through_funnel_pregated"] = bool(rec["through_funnel"] and rec["pregate"])
        rows.append(rec)
    n = len(rows)
    ok = np.array([r["job_status"] == "ok" for r in rows])
    snr = np.array([r["snr_expected"] if r["snr_expected"] == r["snr_expected"] else np.nan for r in rows], dtype=float)
    valid = ok & np.isfinite(snr)
    levels = {"search_only": "recovered", "search_and_pregate": "through_pregate", "search_and_stageA": "through_stageA",
              "search_and_stageA_and_secondary": "through_funnel", "full_funnel_with_pregate": "through_funnel_pregated"}
    res = {"generated_utc": utc(), "rules_version": rules, "config": CONFIG, "n_injections": n, "n_jobs_ok": int(ok.sum()),
           "n_stars": n_stars, "job_statuses": {}, "outcomes": {}, "levels": {}, "by_period_bin": {}, "by_rp_earth": {},
           "by_tmag": {}, "by_rotation_amplitude": {}, "by_snr": {}, "stageA_criteria_failures_on_recovered": {},
           "secondary_gate_by_mode_on_stageA_pass": {}, "depth_consistency_on_recovered": {},
           "map_period_x_snr": {}, "timing": {}}
    for r in rows:
        res["job_statuses"][r["job_status"]] = res["job_statuses"].get(r["job_status"], 0) + 1
        res["outcomes"][r["status"]] = res["outcomes"].get(r["status"], 0) + 1
    for name, key in levels.items():
        y = np.array([bool(r[key]) for r in rows])
        lvl = {"n": int(valid.sum()), "n_through": int(y[valid].sum()), "fraction": float(y[valid].mean()) if valid.any() else None}
        if valid.sum() > 20 and y[valid].sum() > 5:
            lvl["logistic"] = logistic_fit(snr[valid], y[valid])
        lvl["by_snr"] = _binned_rate(snr[valid], y[valid], SNR_BINS)
        res["levels"][name] = lvl
    rec_y = np.array([r["recovered"] for r in rows]); fun_y = np.array([r["through_funnel"] for r in rows])
    full_y = np.array([r["through_funnel_pregated"] for r in rows])

    def bin_counts(mask):
        return {"n": int(mask.sum()), "recovered": int(rec_y[mask].sum()),
                "through_funnel": int(fun_y[mask].sum()), "through_funnel_pregated": int(full_y[mask].sum())}

    pb = np.array([r["period_bin"] for r in rows]); per = np.array([r["period"] for r in rows])
    for b in sorted(set(pb.tolist())):
        m = valid & (pb == b)
        res["by_period_bin"][str(b)] = {"period_range": [float(np.nanmin(per[m])), float(np.nanmax(per[m]))] if m.any() else None,
                                        **bin_counts(m)}
    rp = np.array([r["rp_earth"] for r in rows], dtype=float)
    res["by_rp_earth"] = {f"{lo}-{hi}": bin_counts(valid & (rp >= lo) & (rp < hi)) for lo, hi in RP_BINS}
    tm = np.array([r["tmag"] for r in rows], dtype=float)
    res["by_tmag"] = {f"{lo}-{hi}": bin_counts(valid & (tm >= lo) & (tm < hi)) for lo, hi in TMAG_BINS}
    ra = np.array([r["rot_amp_ppt"] if r["rot_amp_ppt"] is not None else np.nan for r in rows], dtype=float)
    res["by_rotation_amplitude"] = {f"{lo}-{hi}": bin_counts(valid & (ra >= lo) & (ra < hi)) for lo, hi in ROT_BINS}
    extreme = valid & np.isfinite(ra) & (ra >= ROT_EXTREME)
    res["rotation_proxy_quality"] = {
        "n_missing_or_nonfinite": int((valid & ~np.isfinite(ra)).sum()),
        "extreme_reporting_boundary_ppt": ROT_EXTREME,
        "n_extreme_injections": int(extreme.sum()),
        "extreme_tic_ids": sorted({rows[i]["tic_id"] for i in np.flatnonzero(extreme)}),
        "note": "Extreme raw-photometry proxies are reported separately; this is not a physical rotation measurement or an exclusion gate.",
    }
    # period x SNR map
    for b in sorted(set(pb.tolist())):
        res["map_period_x_snr"][str(b)] = {"search": _binned_rate(snr[valid & (pb == b)], rec_y[valid & (pb == b)], SNR_BINS),
                                           "funnel": _binned_rate(snr[valid & (pb == b)], fun_y[valid & (pb == b)], SNR_BINS),
                                           "funnel_pregated": _binned_rate(snr[valid & (pb == b)], full_y[valid & (pb == b)], SNR_BINS)}
    # Stage A criteria failures among recovered
    crit_fail = {}
    n_rec_a = 0
    for r in rows:
        if r["recovered"] and r["stageA_criteria"]:
            n_rec_a += 1
            for k, v in r["stageA_criteria"].items():
                if not v:
                    crit_fail[k] = crit_fail.get(k, 0) + 1
    res["stageA_criteria_failures_on_recovered"] = {"n_with_stageA_record": n_rec_a, "failing": crit_fail,
                                                    "stageA_decisions": {d: sum(1 for r in rows if r["recovered"] and r["stageA"] == d)
                                                                         for d in ("PASS", "FAIL", "ERROR", None)}}
    # secondary gate by mode on Stage A passers (the decision-1 instrument, planets by construction)
    gbm = {}
    n_gbm = 0
    for r in rows:
        if r["through_stageA"] and r["gate_by_mode"]:
            n_gbm += 1
            for m, g in r["gate_by_mode"].items():
                gbm.setdefault(m, {})[g] = gbm.setdefault(m, {}).get(g, 0) + 1
    res["secondary_gate_by_mode_on_stageA_pass"] = {"n": n_gbm, "by_mode": gbm}
    # depth consistency p-values on recovered (decision 2): fraction below 1e-3 = false-kill rate
    pw = np.array([r["p_const_white"] if r["p_const_white"] is not None else np.nan for r in rows if r["recovered"]], dtype=float)
    pi = np.array([r["p_const_inflated"] if r["p_const_inflated"] is not None else np.nan for r in rows if r["recovered"]], dtype=float)
    for name, arr in (("white", pw), ("inflated", pi)):
        a = arr[np.isfinite(arr)]
        if a.size:
            res["depth_consistency_on_recovered"][name] = {
                "n": int(a.size), "frac_below_1e-3": float(np.mean(a < 1e-3)), "frac_below_1e-2": float(np.mean(a < 1e-2)),
                "frac_below_0.05": float(np.mean(a < 0.05)), "quantiles_p10_p50_p90": [float(x) for x in np.percentile(a, [10, 50, 90])],
                "ks_uniform_p": float(__import__("scipy.stats").stats.kstest(a, "uniform").pvalue)}
    walls = np.array([r["wall_s"] or 0 for r in rows if r["job_status"] == "ok"], dtype=float)
    a_s = np.array([fun[j["job_id"]]["stageA_seconds"] or 0 for j in jobs if fun.get(j["job_id"], {}).get("stageA_seconds")], dtype=float)
    s_s = np.array([fun[j["job_id"]]["secondary_seconds"] or 0 for j in jobs if fun.get(j["job_id"], {}).get("secondary_seconds")], dtype=float)
    res["timing"] = {"search_wall_s_median_p90_max": [float(np.median(walls)), float(np.percentile(walls, 90)), float(walls.max())] if walls.size else None,
                     "stageA_s_median_p90": [float(np.median(a_s)), float(np.percentile(a_s, 90))] if a_s.size else None,
                     "secondary_s_median_p90": [float(np.median(s_s)), float(np.percentile(s_s, 90))] if s_s.size else None,
                     "n_budget_stops": int(sum(1 for r in recs if any("would not fit" in n for n in ((r.get("result") or {}).get("notes") or []))))}
    res["false_alarms"] = fa_counts
    (P8 / "completeness_p8.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    with open(P8 / "injection_outcomes_p8.csv", "w", newline="", encoding="utf-8") as fh:
        cols = [k for k in rows[0].keys() if k not in ("stageA_criteria", "gate_by_mode")]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({k: res[k] for k in ("n_injections", "n_jobs_ok", "outcomes", "job_statuses")}, indent=1))
    for name, lvl in res["levels"].items():
        lg = lvl.get("logistic") or {}
        print(f"{name:<36} {lvl['n_through']:>5}/{lvl['n']:<5} {100 * (lvl['fraction'] or 0):5.1f}%  SNR50 {lg.get('snr50', float('nan')):6.1f}  SNR90 {lg.get('snr90', float('nan')):6.1f}")
    print("false alarms:", json.dumps(res["false_alarms"], indent=1))
    return res


def _pct(k, n):
    return f"{k}/{n} ({100.0 * k / n:.0f}%)" if n else "0/0"


def report(res: dict) -> str:
    """``docs/COMPLETENESS_P8.md`` from ``completeness_p8.json``."""
    L = []
    a = L.append
    a("# Completeness and the false-alarm budget at native cadence, through the funnel\n")
    a(f"Generated {res['generated_utc']} by `scripts/p8_completeness.py analyze` from `data/survey/runs/inj_p8`, "
      f"`data/survey/runs/fa_p8` and the injection funnel under `data/survey/p8/inj_funnel/` (rules {res['rules_version']}, "
      f"config `{res['config']}`). Every number is [M]. The pipeline finds candidates; nothing here is a detection.\n")
    a("## 1. What was measured\n")
    a(f"* Sample: {res['n_stars']} stars drawn at random (seed 20260904) from the 2,000-star `targets_p8.csv`; "
      f"{res['n_injections']:,} batman injections (7 per star; period log-uniform in four equal-log bins over 0.5-30 d, "
      "radius log-uniform 1-4 Earth radii converted to Rp/R* per star, impact parameter uniform 0-0.9, quadratic limb "
      "darkening by Teff). Products are selected and brought to the common exposure first, then the model is "
      "multiplied into SAP and corrected flux before detrending and clipping, matching the completed search. "
      f"Jobs by status: {res['job_statuses']}; outcomes: {res['outcomes']}.")
    a("* Recovery rule (fixed before the run, the prompt-2 rule): an accepted candidate with period within 1% of the "
      "injected period and overlapping transit windows; ratios 2, 3, 1/2, 1/3 are `alias` (reported, never credited).")
    a("* Expected SNR: the matched-filter SNR of the injected model on the star's own UN-injected prepared "
      "native-cadence series (sigma = 1.4826 x MAD per cadence).")
    a("* Through the gates: every recovered injection went through Stage A of the funnel (the prompt-6 event rules "
      "and six criteria at native cadence) and the full-phase secondary scan, with the products re-injected in memory; "
      "the real funnel's pre-gate (epoch-consistent, stitch SNR >= 7.1, >= 3 transits) is applied in the central "
      "whole-funnel curve and reported separately to show its losses.\n")
    a("Here, through-funnel completeness ends after the pre-gate, Stage A and secondary scan, as specified in Part 1e. "
      "The later Stage B, blind TLS and Stage D checks are not calibrated by this injection run; their losses can "
      "only reduce the number reaching a final verdict.\n")
    a("## 2. Recovery at each level\n")
    a("| level | through / injected | fraction | SNR50 (16-84%) | SNR90 (16-84%) |")
    a("|---|---:|---:|---|---|")
    labels = {"search_only": "search only", "search_and_pregate": "search + pre-gate", "search_and_stageA": "search + Stage A",
              "search_and_stageA_and_secondary": "search + Stage A + secondary gate",
              "full_funnel_with_pregate": "the whole funnel (pre-gate, Stage A, secondary gate)"}
    f = lambda v: "n/a" if v is None else f"{v:.1f}"          # noqa: E731
    for k, lab in labels.items():
        x = res["levels"][k]
        lg = x.get("logistic") or {}
        s50 = lg.get("snr50_16_84") or [None, None]; s90 = lg.get("snr90_16_84") or [None, None]
        a(f"| {lab} | {x['n_through']:,} / {x['n']:,} | {100 * (x['fraction'] or 0):.1f}% | {f(lg.get('snr50'))} ({f(s50[0])}-{f(s50[1])}) | "
          f"{f(lg.get('snr90'))} ({f(s90[0])}-{f(s90[1])}) |")
    a("\n### By expected SNR\n")
    a("| expected SNR | n | search only | whole funnel |")
    a("|---|---:|---:|---:|")
    so, ff_ = res["levels"]["search_only"]["by_snr"], res["levels"]["full_funnel_with_pregate"]["by_snr"]
    for r1, r2 in zip(so, ff_):
        a(f"| {r1['lo']:g}-{r1['hi']:g} | {r1['n']} | {_pct(r1['k'], r1['n'])} | {_pct(r2['k'], r2['n'])} |")
    a("\n### By period bin, radius, Tmag and the rotation proxy\n")
    a("Every fraction uses all injected signals in the bin as its denominator. The last column is the central whole-funnel outcome.\n")
    a("| bin | n | recovered | search + A + secondary | search + pre-gate + A + secondary |")
    a("|---|---:|---:|---:|---:|")
    def bin_row(label, counts):
        a(f"| {label} | {counts['n']} | {_pct(counts['recovered'], counts['n'])} | "
          f"{_pct(counts['through_funnel'], counts['n'])} | {_pct(counts['through_funnel_pregated'], counts['n'])} |")
    for b, d in res["by_period_bin"].items():
        pr = d["period_range"]
        bin_row(f"period {pr[0]:.2f}-{pr[1]:.2f} d", d)
    for k, d in res["by_rp_earth"].items():
        bin_row(f"radius {k} R_earth", d)
    for k, d in res["by_tmag"].items():
        bin_row(f"Tmag {k}", d)
    for k, d in res["by_rotation_amplitude"].items():
        bin_row(f"rotation semi-amplitude {k} ppt", d)
    rq = res.get("rotation_proxy_quality")
    if rq:
        a(f"\nRotation-proxy accounting: {rq['n_missing_or_nonfinite']} missing/nonfinite; "
          f"{rq['n_extreme_injections']} injections on TICs {rq['extreme_tic_ids']} are in the explicit "
          f">= {rq['extreme_reporting_boundary_ppt']:g} ppt bin. {rq['note']}")
    for key, label in (("search", "search only"), ("funnel_pregated", "search + pre-gate + A + secondary")):
        a(f"\n### Period x expected SNR ({label})\n")
        a("| period bin \\ SNR | " + " | ".join(f"{r['lo']:g}-{r['hi']:g}" for r in so) + " |")
        a("|---|" + "---:|" * len(so))
        for b, d in res["map_period_x_snr"].items():
            pr = res["by_period_bin"][b]["period_range"]
            a(f"| {pr[0]:.2f}-{pr[1]:.2f} d | " + " | ".join(_pct(r["k"], r["n"]) for r in d[key]) + " |")
    a("\n## 3. What the funnel does to a real signal\n")
    sa = res["stageA_criteria_failures_on_recovered"]
    a(f"Of the recovered injections, {sa['n_with_stageA_record']} have a Stage A record; decisions {sa['stageA_decisions']}. "
      f"Criteria failing (a candidate can fail several): {sa['failing']}.")
    sg = res["secondary_gate_by_mode_on_stageA_pass"]
    a(f"Secondary gate on the {sg['n']} Stage A passers, by variant (planets by construction): {sg['by_mode']}.")
    dc = res["depth_consistency_on_recovered"]
    if dc:
        a("\nDepth-consistency p-values on the recovered injections (constant input depth; uniformity is the ideal error-model benchmark):\n")
        a("| errors | n | below 1e-3 (false-kill rate) | below 1e-2 | below 0.05 | p10 / p50 / p90 | KS uniform p |")
        a("|---|---:|---:|---:|---:|---|---:|")
        for k, d in dc.items():
            q = d["quantiles_p10_p50_p90"]
            a(f"| {k} | {d['n']} | {100 * d['frac_below_1e-3']:.1f}% | {100 * d['frac_below_1e-2']:.1f}% | {100 * d['frac_below_0.05']:.1f}% | "
              f"{q[0]:.3f} / {q[1]:.3f} / {q[2]:.3f} | {d['ks_uniform_p']:.2g} |")
    a("\n## 4. False alarms (the same stars, no injection)\n")
    fa = res.get("false_alarms") or {}
    if fa.get("available"):
        a("| stage | candidates | per star |")
        a("|---|---:|---:|")
        a(f"| accepted by the search | {fa['accepted']:,} | {fa['accepted_per_star']:.2f} |")
        a(f"| past the pre-gate | {fa['pregate']:,} | {fa['pregate_per_star']:.3f} |")
        a(f"| past Stage A | {fa['stageA_pass']:,} | {fa['stageA_pass_per_star']:.4f} |")
        a(f"| past the secondary gate | {fa['stageA_pass_and_secondary']:,} | {fa['stageA_pass_and_secondary_per_star']:.4f} |")
        a(f"\nStage A records: {fa['stageA_done']} of {fa['pregate']} pre-gate passers; {fa['n_stars_ok']} of {fa['n_stars']} stars searched ok.")
        a(f"The seeded sample of {fa['stageA_failure_sample_n']} Stage A failures has secondary gates "
          f"{fa['stageA_failure_sample_gate']}; these are diagnostic and do not enter the passing false-alarm budget.")
        a(f"Stage A criterion failures (a candidate can fail several): {fa['stageA_criteria_fail_counts']}.")
    else:
        a("The false-alarm funnel has not been run.")
    a("\n## 5. Wall clock\n")
    t = res["timing"]
    a(f"Search per injection job (cached products, no download): median / p90 / max {t['search_wall_s_median_p90_max']} s; "
      f"{t['n_budget_stops']} jobs hit the detection budget. Stage A per candidate median / p90 {t['stageA_s_median_p90']} s; "
      f"secondary scan {t['secondary_s_median_p90']} s.")
    a("\n## 6. Statistical assumptions [A]\n")
    a("The SNR curves use the prompt-2 two-parameter logistic model and 1,000 resamples of individual injections "
      "for the 16-84% intervals. Injections on the same star share its noise; these intervals do not model that "
      "within-star dependence or population-model uncertainty. SNR50 and SNR90 are fitted curve crossings, "
      "which can lie beyond the sampled SNR range.")
    a("The p-value distribution is conditional on recovery, ephemeris estimation and event removal. Its "
      "departure from uniformity is a diagnostic of the combined process, not an isolated test of the error bars. "
      "The measured fraction killed is still the calibration loss for those recovered injections. "
      "The rotation proxy is a sinusoidal fit to corrected photometry and can be dominated by extreme flux outliers.")
    return "\n".join(L) + "\n"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("funnel"); f.add_argument("--slices", type=int, default=16); f.add_argument("--rules", default="p7.0")
    f.add_argument("--force", action="store_true")
    f.add_argument("--shared-queue", action="store_true", help="let idle top-level workers claim the next injection")
    s = sub.add_parser("slice"); s.add_argument("--index", type=int, required=True); s.add_argument("--nslices", type=int, required=True)
    s.add_argument("--rules", default="p7.0"); s.add_argument("--force", action="store_true")
    s.add_argument("--queue", type=Path)
    a = sub.add_parser("analyze"); a.add_argument("--rules", default="p7.0")
    sub.add_parser("report")
    sub.add_parser("jobs")
    sub.add_parser("snr")
    args = ap.parse_args(argv)
    if args.cmd == "funnel":
        run_funnel(args.slices, args.rules, args.force, args.shared_queue)
    elif args.cmd == "slice":
        run_slice(args.index, args.nslices, args.rules, args.force, args.queue)
    elif args.cmd == "analyze":
        res = analyze(args.rules)
        (REPO / "docs" / "COMPLETENESS_P8.md").write_text(report(res), encoding="utf-8")
        print("wrote docs/COMPLETENESS_P8.md")
    elif args.cmd == "report":
        res = json.loads((P8 / "completeness_p8.json").read_text(encoding="utf-8"))
        (REPO / "docs" / "COMPLETENESS_P8.md").write_text(report(res), encoding="utf-8")
        print("wrote docs/COMPLETENESS_P8.md")
    elif args.cmd == "jobs":
        js = recovered_jobs(_load_results(INJ_RUN))
        print(len(js), "recovered injections;", sum(j["pregate_pass"] for j in js), "pass the pre-gate")
    elif args.cmd == "snr":
        expected_snr(_load_results(INJ_RUN), checkpoint_path=P8 / "expected_snr_p8.json")


if __name__ == "__main__":
    main()
