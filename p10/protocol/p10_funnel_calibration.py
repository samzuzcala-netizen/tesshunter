"""Prompt 8: the funnel over the native-cadence survey's candidates.

Every candidate the ``survey_p8`` search accepts is collected from the run directory, a
cheap pre-gate from the search record itself is applied, and the survivors enter the
prompt-6/7 funnel under the prompt-8 rule set, in this order, nothing expensive before the
cheap gates:

    collect    run results -> ``candidates.csv`` (every accepted candidate) and
               ``survivors.csv`` (the pre-gate passers, ordered by whole-stitch SNR; the
               rank is an ordering, no verdict depends on it)
    stageA     the event rules and the six criteria at native cadence (``revet_p6.stagea_one``)
    secondary  the full-phase secondary scan on every Stage A passer and on a seeded 10% of
               the Stage A failures (so the handoff can say what the gate does on things
               Stage A already killed); a passer whose gate says FAIL does not enter Stage B
    stageB     the phase-independent window test, the long-period flag, the Gaia / VSX
               flags (from the prompt-8 neighbour records), the deep-event-host flag
    stageC     blind TLS on the Stage B survivors (top-level slices, the prompt-5 masks)
    stageD     the fresh hard stop, the all-transit fit, Gaia/SIMBAD/VSX, the packet fields
    funnel / census / csv / report   the counts and tables

The stages are ``revet_p6``'s, re-pointed at the prompt-8 tables and output root through
``revet_p6.set_population``; nothing under ``data/survey/p6`` or ``p7`` is touched.  The rule
set is ``--rules`` (``p8.0`` once Part 3 has decided it; ``p7.0`` and measurement variants
before that).  Each stage writes one JSON per candidate under ``data/survey/p8/stage<X>/``
and is idempotent: a settled record under the same rules version short-circuits.

The pre-gate [A]: ``stitch_epoch_consistent`` and ``stitch_snr >= 7.1`` and
``stitch_n_transits >= 3``.  The transit-count half is lossless with respect to the funnel
(Stage A needs three kept events, and kept <= observed <= transits); the SNR half is the
prompt-4 G2 threshold lowered from 9 to the SPOC release floor, and its cost is measured on
the recovered injections in Part 1e (``scripts/p8_completeness.py``).

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

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

OUT = REPO / "data/survey/p10/part2d/calibration/fa_funnel"
RUN = REPO / "data/survey/runs/p10_2b/e_fa"
LC_ROOT = REPO / "data" / "survey" / "audit_lc"
SURVIVORS = OUT / "survivors.csv"
CANDIDATES = OUT / "candidates.csv"
PACKETS = REPO / "data/survey/p10/part2d/calibration/packets"          # does not exist: no packet ephemeris
PY = sys.executable


def set_root(root) -> None:
    """Point every table and output at ``root`` (the real funnel is ``data/survey/p8``; the
    false-alarm funnel of Part 1e is ``data/survey/p8/fa_funnel``)."""
    global OUT, SURVIVORS, CANDIDATES
    OUT = Path(root) if Path(root).is_absolute() else REPO / root
    SURVIVORS = OUT / "survivors.csv"
    CANDIDATES = OUT / "candidates.csv"
    V.set_population(out_root=OUT, survivors_csv=SURVIVORS, candidates_csv=CANDIDATES, packets_dir=PACKETS)
    V.LC_ROOT = LC_ROOT
    import audit_p5 as A
    from tesshunter.survey import get_config
    A.set_input_config(get_config("survey_p10"))

PREGATE = {"stitch_snr_min": 7.1, "stitch_n_transits_min": 3, "stitch_epoch_consistent": True}
INJECT_ARGS: list[str] = []
SECONDARY_FAIL_SAMPLE_FRACTION = 0.10
SECONDARY_FAIL_SAMPLE_SEED = 20260904

import revet_p6 as V                                    # noqa: E402
from tesshunter import audit_rules as R                 # noqa: E402
from tesshunter.audit_prep import clean_and_detrend     # noqa: E402
from tesshunter.secondary import secondary_scan         # noqa: E402

# P10 calibration records explicitly name the frozen preset. The original
# writer still supplies its unchanged ingest metadata and atomic serialization.
# Older rule sets and their cache identities are untouched.
import audit_p5 as _audit
if not hasattr(_audit, "_p10_calibration_original_jdump"):
    _audit._p10_calibration_original_jdump = _audit.jdump
    def _p10_named_jdump(path, obj):
        if isinstance(obj, dict) and obj.get("rules_version") == "p10.0":
            obj = dict(obj, survey_preset="survey_p10")
        return _audit._p10_calibration_original_jdump(path, obj)
    _audit.jdump = _p10_named_jdump

set_root(OUT)


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rules_by_name(name: str):
    if name in ("p6.2", "p7.0"):
        return {"p6.2": R.LEGACY_RULES, "p7.0": R.DEFAULT_RULES}[name]
    if name == "p8.0":
        if R.P8_RULES is None:
            raise SystemExit("p8.0 is not decided yet (audit_rules.P8_RULES is None): Part 3 first")
        return R.P8_RULES
    if name == "p10.0":
        return R.P10_RULES
    raise SystemExit(f"unknown rule set {name}")


def set_rules(name: str) -> None:
    V.set_rules(rules_by_name(name))


# ─────────────────────────────────────────────────────────────────────────────
# collect
# ─────────────────────────────────────────────────────────────────────────────
CAND_COLS = ["tic_id", "planet_num", "search", "period_days", "epoch_btjd", "duration_days", "depth_ppt",
             "snr", "n_transits", "stitch_snr", "stitch_n_transits", "stitch_epoch_consistent", "stitch_period_days",
             "stitch_depth_ppt", "verdict", "n_flags_high", "n_flags_medium", "flags_high",
             "n_units", "baseline_days", "n_cadences", "tmag", "teff_k", "radius_rsun", "mass_msun",
             "ra_deg", "dec_deg", "rotation_peak_period_days", "rotation_semi_amplitude_ppt",
             "rotation_scatter_ppt", "prep_mad_ppt", "budget_stop", "pregate_snr", "pregate_transits",
             "pregate_epoch", "passes_pregate"]


def collect(run_dir: Path, targets_csv: Path) -> dict:
    stars = {int(r["tic_id"]): r for r in csv.DictReader(open(targets_csv, newline="", encoding="utf-8"))}
    rows, n_ok, n_other, statuses = [], 0, 0, {}
    for p in sorted((run_dir / "results").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        statuses[d.get("status")] = statuses.get(d.get("status"), 0) + 1
        if d.get("status") != "ok" or not d.get("result"):
            n_other += 1
            continue
        n_ok += 1
        tic = int(d["tic_id"])
        st = stars.get(tic, {})
        res = d["result"]
        rot = d.get("rotation_proxy") or {}
        cnt = d.get("prepare_counters") or {}
        vet = {v["planet_num"]: v for v in (res.get("vetting") or [])}
        budget = any("would not fit" in n for n in (res.get("notes") or []))
        for q in res.get("planets") or []:
            v = vet.get(q["planet_num"], {})
            snr_ok = (q.get("stitch_snr") or 0.0) >= PREGATE["stitch_snr_min"]
            ntr_ok = int(q.get("stitch_n_transits") or 0) >= PREGATE["stitch_n_transits_min"]
            eph_ok = bool(q.get("stitch_epoch_consistent"))
            rows.append({
                "tic_id": tic, "planet_num": q["planet_num"], "search": q.get("search"),
                "period_days": q["period_days"], "epoch_btjd": q["epoch_btjd"], "duration_days": q["duration_days"],
                "depth_ppt": q["depth_ppt"], "snr": q["snr"], "n_transits": q.get("n_transits_observed"),
                "stitch_snr": q.get("stitch_snr"), "stitch_n_transits": q.get("stitch_n_transits"),
                "stitch_epoch_consistent": q.get("stitch_epoch_consistent"),
                "stitch_period_days": q.get("stitch_period_days"), "stitch_depth_ppt": q.get("stitch_depth_ppt"),
                "verdict": q.get("verdict"), "n_flags_high": len(v.get("flags_high") or []),
                "n_flags_medium": len(v.get("flags_medium") or []), "flags_high": "|".join(v.get("flags_high") or []),
                "n_units": d.get("n_units"), "baseline_days": round(float(d.get("baseline_days") or 0), 2),
                "n_cadences": d.get("n_cadences_raw"),
                "tmag": st.get("tmag"), "teff_k": st.get("teff_k"), "radius_rsun": st.get("radius_rsun"),
                "mass_msun": st.get("mass_msun"), "ra_deg": st.get("ra_deg"), "dec_deg": st.get("dec_deg"),
                "rotation_peak_period_days": rot.get("peak_period_days"),
                "rotation_semi_amplitude_ppt": rot.get("semi_amplitude_ppt"),
                "rotation_scatter_ppt": rot.get("scatter_ppt"), "prep_mad_ppt": cnt.get("mad_ppt"),
                "budget_stop": budget, "pregate_snr": snr_ok, "pregate_transits": ntr_ok, "pregate_epoch": eph_ok,
                "passes_pregate": bool(snr_ok and ntr_ok and eph_ok),
            })
    OUT.mkdir(parents=True, exist_ok=True)
    with open(CANDIDATES, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAND_COLS)
        w.writeheader()
        w.writerows(rows)
    surv = [r for r in rows if r["passes_pregate"]]
    surv.sort(key=lambda r: -float(r["stitch_snr"] or 0.0))
    with open(SURVIVORS, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["rank"] + CAND_COLS)
        w.writeheader()
        for i, r in enumerate(surv, 1):
            w.writerow({"rank": i, **r})
    summary = {"generated_utc": utc(), "run_dir": str(run_dir), "n_result_files": n_ok + n_other,
               "statuses": statuses, "n_stars_ok": n_ok, "n_targets": len(stars),
               "n_accepted_candidates": len(rows), "n_stars_with_candidates": len({r["tic_id"] for r in rows}),
               "pregate": PREGATE, "n_fail_snr": sum(not r["pregate_snr"] for r in rows),
               "n_fail_transits": sum(not r["pregate_transits"] for r in rows),
               "n_fail_epoch": sum(not r["pregate_epoch"] for r in rows),
               "n_pass_pregate": len(surv), "n_stars_pass_pregate": len({r["tic_id"] for r in surv}),
               "n_budget_stops": sum(1 for r in rows if r["budget_stop"]) and len({r["tic_id"] for r in rows if r["budget_stop"]})}
    summary["config"] = "survey_p10"
    (OUT / "collect_p10.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# the secondary stage
# ─────────────────────────────────────────────────────────────────────────────
def secondary_jobs() -> list[dict]:
    """Stage A passers, plus a seeded 10% of the Stage A failures."""
    js = V.jobs()
    dec = {}
    for p in (OUT / "stageA").glob("*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        dec[r["key"]] = r.get("decision")
    return select_secondary_jobs(js, dec)


def select_secondary_jobs(js: list[dict], dec: dict) -> list[dict]:
    """Use the same seeded failure sample for execution and completeness validation."""
    passers = [j for j in js if dec.get(V.kkey(j["tic_id"], j["period"])) == "PASS"]
    failures = [j for j in js if dec.get(V.kkey(j["tic_id"], j["period"])) == "FAIL"]
    rng = np.random.default_rng(SECONDARY_FAIL_SAMPLE_SEED)
    n = int(round(SECONDARY_FAIL_SAMPLE_FRACTION * len(failures)))
    idx = sorted(rng.choice(len(failures), size=min(n, len(failures)), replace=False)) if failures and n else []
    sample = [dict(failures[i], stageA_sample=True) for i in idx]
    return [dict(j, stageA_sample=False) for j in passers] + sample


def secondary_one(job: dict, force: bool = False) -> dict:
    import audit_p5 as A
    A.set_roots(OUT, LC_ROOT)
    tic, period = job["tic_id"], job["period"]
    k = V.kkey(tic, period)
    out_path = OUT / "secondary" / f"{k}.json"
    if out_path.exists() and not force:
        r = A.jload(out_path)
        if A.cache_matches(r) and r.get("gate") in ("PASS", "FAIL", "HOLD"):
            return r
    t0 = time.perf_counter()
    rs = V.RULE_SET
    rec = {"key": k, "tic_id": tic, "rank": job["rank"], "survey_period": period,
           "survey_depth_ppt": job["depth_ppt"], "generated_utc": utc(), "rules_version": V.RULES,
           "stageA_sample": bool(job.get("stageA_sample")),
           "thresholds": R.thresholds(rs)["secondary"]}
    try:
        sa = A.jload(OUT / "stageA" / f"{k}.json")
        eph = sa["per_ephemeris"][sa["chosen_ephemeris"]]["ephemeris"]
        prep_meta = A.jload(OUT / "prep" / f"{k}.json")
        products = A.choose_per_sector(A.load_products(tic))
        st = A.stellar_from_cache(tic)
        teff = float(st["teff"]) if st.get("teff") else float(_survivor_teff(tic) or 5500.0)
        z = np.load(OUT / "tls" / f"{k}_lc.npz")
        t_un, f_un = z["time_unbinned"], z["flux_unbinned"]
        sap = clean_and_detrend(products, prep_meta["wotan"]["window_days"], flux_key="sap_flux", err_key="sap_flux_err")
        p10 = getattr(rs, "verdict_tiers", "p8") == "p10"
        sec = secondary_scan(t_un, f_un, eph["period"], eph["t0"], eph["duration"],
                             prep_meta["R_star"], prep_meta["M_star"], teff, sap["time"], sap["flux"],
                             gate_mode=rs.secondary_gate, quiet_max_dips=rs.secondary_quiet_max_dips,
                             # [P10] the prompt-10 measurements and modes; off under every earlier set
                             t_sap_sector=sap["sector"] if p10 else None, p10_modes=p10)
        sec["teff_K"] = teff
        sec["sap_products_used"] = int(sum(1 for p in sap["per_product"] if not p["dropped"]))
        rec.update({"secondary": sec, "gate": sec["gate"], "variability_flag": sec["variability_flag"],
                    "stageA_decision": sa["decision"], "chosen_ephemeris": sa["chosen_ephemeris"],
                    "reason": sec.get("verdict")})
    except Exception as exc:
        rec.update({"gate": "ERROR", "reason": f"{type(exc).__name__}: {exc}"[:400]})
    rec["seconds"] = round(time.perf_counter() - t0, 1)
    A.jdump(out_path, rec)
    return rec


def _survivor_teff(tic: int):
    for r in csv.DictReader(open(SURVIVORS, newline="", encoding="utf-8")):
        if int(r["tic_id"]) == tic:
            try:
                return float(r["teff_k"])
            except (TypeError, ValueError):
                return None
    return None




# ─────────────────────────────────────────────────────────────────────────────
# eligibility (the funnel order) and the slice runners
# ─────────────────────────────────────────────────────────────────────────────
def decisions(stage: str) -> dict:
    out = {}
    d = OUT / ("secondary" if stage == "S" else f"stage{stage}")
    for p in d.glob("*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        out[r["key"]] = r.get("gate") if stage == "S" else r.get("decision")
    return out


def eligible(stage: str) -> list[dict]:
    js = V.jobs()
    if stage == "A":
        return js
    if stage == "S":
        return secondary_jobs()
    if stage == "B":
        a, s = decisions("A"), decisions("S")
        return [j for j in js if a.get(V.kkey(j["tic_id"], j["period"])) == "PASS"
                and s.get(V.kkey(j["tic_id"], j["period"])) in ("PASS", "HOLD")]
    prev = {"C": "B", "D": "C"}[stage]
    d = decisions(prev)
    return [j for j in js if d.get(V.kkey(j["tic_id"], j["period"])) == "PASS"]


STAGE_FN = {"A": V.stagea_one, "S": secondary_one, "B": V.stageb_one, "C": V.stagec_one}
STAGE_DIR = {"A": "stageA", "S": "secondary", "B": "stageB", "C": "stageC"}


def run_slice(stage: str, index: int, nslices: int, threads: int, oversampling: int, force: bool,
              queue: Path | None = None, max_jobs: int | None = None) -> None:
    if max_jobs is not None and queue is None:
        raise ValueError("A bounded worker requires a shared queue")
    if stage == "B" and OUT.resolve() == (REPO / "data/survey/p8").resolve():
        from p8_neighbour_depths import ensure_context
        ensure_context(check_only=True)
    from p8_worker_qos import configure_current_worker
    configure_current_worker()
    js = eligible(stage)
    mine = js[index::nslices]
    fn = STAGE_FN[stage]
    if queue is None:
        work = iter(mine)
        print(f"slice {index}/{nslices}: {len(mine)} of {len(js)} candidates, stage {stage}, rules {V.RULES}", flush=True)
    else:
        from p8_work_queue import claims
        by_key = {V.kkey(j["tic_id"], j["period"]): j for j in js}
        work = (by_key[key] for key in claims(queue, limit=max_jobs))
        print(f"worker {index}/{nslices}: shared queue of {len(js)} candidates, stage {stage}, rules {V.RULES}", flush=True)
        if max_jobs is not None:
            print(f"worker {index}: stop after at most {max_jobs} claims", flush=True)
    t0 = time.perf_counter()
    for i, job in enumerate(work, 1):
        kw = {"force": force}
        if stage == "A":
            kw["threads"] = threads
        elif stage == "C":
            kw["threads"] = threads; kw["oversampling"] = oversampling
        r = fn(job, **kw)
        el = time.perf_counter() - t0
        dec = r.get("decision") or r.get("gate")
        progress = f"{index}:{i}/{len(mine)}" if queue is None else f"{index}:{i} shared"
        eta = f" eta {(el / i) * (len(mine) - i) / 60:.1f} min" if queue is None else ""
        print(f"[{progress}] rank {job['rank']:>4} {r['key']:<28} {dec:<5} {r.get('seconds', 0):>6.1f} s | "
              f"{str(r.get('reason', ''))[:140]} | elapsed {el / 60:.1f} min{eta}",
              flush=True)
    print(f"slice {index} DONE in {(time.perf_counter() - t0) / 60:.1f} min", flush=True)


def run_stage(stage: str, nslices: int, threads: int, oversampling: int, force: bool, rules: str,
              shared_queue: bool = False) -> None:
    from p8_stage_wait import wait_for_existing_workers
    wait_for_existing_workers(stage, REPO, OUT)
    if stage == "B" and OUT.resolve() == (REPO / "data/survey/p8").resolve():
        from p8_neighbour_depths import ensure_context
        print("P8 Gaia depth context:", ensure_context(), flush=True)
    js = eligible(stage)
    (OUT / STAGE_DIR[stage]).mkdir(parents=True, exist_ok=True)
    logdir = OUT / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    queue = None
    if shared_queue:
        from p8_work_queue import create_queue
        queue = logdir / f"{stage}_queue_{os.getpid()}_{time.time_ns()}.sqlite"
        create_queue(queue, [V.kkey(j["tic_id"], j["period"]) for j in js])
    print(f"stage {stage}: {len(js)} candidates on {len({j['tic_id'] for j in js})} stars, "
          f"{nslices} slices x {threads} threads, rules {rules}", flush=True)
    procs = []
    for i in range(nslices):
        log = open(logdir / f"stage{stage}_slice{i}.log", "w", encoding="utf-8")
        cmd = [PY, str(Path(__file__).resolve()), "--rules", rules, "--root", str(OUT), *INJECT_ARGS, "slice", "--stage", stage,
               "--index", str(i), "--nslices", str(nslices), "--threads", str(threads),
               "--oversampling", str(oversampling)]
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
        raise SystemExit(f"stage {stage}: failed slices {codes}; rerun to resume")
    if stage in ("A", "B", "C"):
        V.write_stage_csv(stage)
    else:
        write_secondary_csv()


def write_secondary_csv() -> Path:
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((OUT / "secondary").glob("*.json"))]
    path = OUT / "secondary.csv"
    cols = ["rank", "key", "tic_id", "survey_period", "survey_depth_ppt", "stageA_decision", "stageA_sample", "gate",
            "variability_flag", "n_dips", "primary_depth_ppt", "primary_sigma", "second_phase", "second_depth_ppt",
            "second_sigma", "sap_depth_ppt", "sap_err_ppt", "sigma_over_bound", "bound_ppt", "reason", "seconds"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in sorted(recs, key=lambda r: r.get("rank", 0)):
            s = r.get("secondary") or {}
            prim = s.get("primary") or {}
            secs = s.get("secondaries") or []
            sap = s.get("deepest_secondary_in_sap") or {}
            w.writerow({"rank": r.get("rank"), "key": r["key"], "tic_id": r["tic_id"], "survey_period": r["survey_period"],
                        "survey_depth_ppt": r["survey_depth_ppt"], "stageA_decision": r.get("stageA_decision"),
                        "stageA_sample": r.get("stageA_sample"), "gate": r.get("gate"),
                        "variability_flag": s.get("variability_flag"), "n_dips": s.get("n_dips_above_5sigma"),
                        "primary_depth_ppt": prim.get("depth_ppt"), "primary_sigma": prim.get("sigma"),
                        "second_phase": secs[0]["phase"] if secs else None,
                        "second_depth_ppt": secs[0]["depth_ppt"] if secs else None,
                        "second_sigma": secs[0]["sigma"] if secs else None,
                        "sap_depth_ppt": sap.get("depth_ppt"), "sap_err_ppt": sap.get("err_ppt"),
                        "sigma_over_bound": s.get("secondary_sigma_over_planet_bound"),
                        "bound_ppt": (s.get("planet_secondary_bound") or {}).get("max_planetary_secondary_ppt"),
                        "reason": str(r.get("reason", ""))[:200], "seconds": r.get("seconds")})
    return path


# ─────────────────────────────────────────────────────────────────────────────
# funnel
# ─────────────────────────────────────────────────────────────────────────────
def funnel() -> dict:
    coll = json.loads((OUT / "collect_p10.json").read_text(encoding="utf-8")) if (OUT / "collect_p10.json").exists() else {}
    a, s, b, c = decisions("A"), decisions("S"), decisions("B"), decisions("C")
    d = {}
    for p in (OUT / "stageD").glob("*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        d[r["key"]] = r.get("verdict") or r.get("provisional_verdict")
    js = V.jobs()
    keys = [V.kkey(j["tic_id"], j["period"]) for j in js]
    a_pass = [k for k in keys if a.get(k) == "PASS"]
    s_on_pass = {k: s.get(k) for k in a_pass}
    out = {"generated_utc": utc(), "rules_version": V.RULES, "pregate": PREGATE,
           "n_accepted_candidates": coll.get("n_accepted_candidates"),
           "n_stars_searched_ok": coll.get("n_stars_ok"),
           "n_pass_pregate": len(js), "n_stars_pass_pregate": len({j["tic_id"] for j in js}),
           "stageA": {"n_in": len(js), "PASS": len(a_pass), "FAIL": sum(v == "FAIL" for v in a.values()),
                      "ERROR": sum(v == "ERROR" for v in a.values()), "missing": sum(k not in a for k in keys)},
           "secondary": {"n_in_passers": len(a_pass),
                         "passers_PASS": sum(v == "PASS" for v in s_on_pass.values()),
                         "passers_FAIL": sum(v == "FAIL" for v in s_on_pass.values()),
                         "passers_HOLD": sum(v == "HOLD" for v in s_on_pass.values()),
                         "passers_missing": sum(v is None for v in s_on_pass.values()),
                         "stageA_failure_sample_n": sum(1 for k, v in s.items() if k not in a_pass),
                         "stageA_failure_sample_gate": {g: sum(1 for k, v in s.items() if k not in a_pass and v == g)
                                                        for g in ("PASS", "FAIL", "HOLD", "ERROR")}},
           "stageB": {"n_in": len(eligible("B")), "PASS": sum(v == "PASS" for v in b.values()),
                      "FAIL": sum(v == "FAIL" for v in b.values()), "ERROR": sum(v == "ERROR" for v in b.values())},
           "stageC": {"n_in": len(eligible("C")), "PASS": sum(v == "PASS" for v in c.values()),
                      "FAIL": sum(v == "FAIL" for v in c.values()), "ERROR": sum(v == "ERROR" for v in c.values())},
           "stageD": {"n_in": len(eligible("D")), "verdicts": {vv: sum(1 for v in d.values() if v == vv)
                                                                 for vv in sorted(set(d.values()))}}}
    out["config"] = "survey_p10"
    (OUT / "funnel_p10.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rules", default="p10.0", help="p8.0 (once decided), p7.0, p6.2")
    ap.add_argument("--root", default=str(OUT), help="output root and table directory (default data/survey/p8)")
    ap.add_argument("--inject", default=None,
                    help="JSON file with an injection model (inj_period, inj_t0, inj_rp_rs, inj_b, inj_a_rs, inj_u1, inj_u2): "
                         "installed into audit_p5.load_products in this process and every slice (the Part 4 exercise on a "
                         "recovered injection); never used on a real candidate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--run", default=str(RUN))
    c.add_argument("--targets", default=str(REPO / "data" / "survey" / "targets_p8.csv"))
    for st in ("stageA", "secondary", "stageB", "stageC"):
        s = sub.add_parser(st)
        s.add_argument("--slices", type=int, default=12)
        s.add_argument("--threads", type=int, default=1)
        s.add_argument("--oversampling", type=int, default=V.C_OVERSAMPLING_DEFAULT)
        s.add_argument("--force", action="store_true")
        s.add_argument("--shared-queue", action="store_true")
    sl = sub.add_parser("slice")
    sl.add_argument("--stage", required=True, choices=["A", "S", "B", "C"])
    sl.add_argument("--index", type=int, required=True); sl.add_argument("--nslices", type=int, required=True)
    sl.add_argument("--threads", type=int, default=1)
    sl.add_argument("--oversampling", type=int, default=V.C_OVERSAMPLING_DEFAULT)
    sl.add_argument("--force", action="store_true")
    sl.add_argument("--queue", type=Path)
    sl.add_argument("--max-jobs", type=int, help="Stop after this many shared-queue claims; other workers retain the remaining jobs")
    sd = sub.add_parser("stageD")
    sd.add_argument("--force", action="store_true")
    sd.add_argument("--no-refresh", action="store_true")
    sub.add_parser("funnel")
    sub.add_parser("census")
    cs = sub.add_parser("csv"); cs.add_argument("--stage", required=True, choices=["A", "S", "B", "C", "D"])
    el = sub.add_parser("eligible"); el.add_argument("--stage", required=True, choices=["A", "S", "B", "C", "D"])
    vd = sub.add_parser("verdict")
    vd.add_argument("--tic", type=int, required=True); vd.add_argument("--period", type=float, required=True)
    vd.add_argument("--verdict", required=True, choices=["SUBMIT", "HOLD", "KILL"])
    vd.add_argument("--reason", required=True)
    vd.add_argument("--note", default=None)
    args = ap.parse_args(argv)
    set_root(args.root)
    set_rules(args.rules)
    if args.inject:
        import p10_completeness_calibration as C
        C.install_injection(json.loads(Path(args.inject).read_text(encoding="utf-8")))
        INJECT_ARGS.extend(["--inject", args.inject])
    if args.cmd == "collect":
        collect(Path(args.run), Path(args.targets))
    elif args.cmd in ("stageA", "secondary", "stageB", "stageC"):
        run_stage({"stageA": "A", "secondary": "S", "stageB": "B", "stageC": "C"}[args.cmd],
                  args.slices, args.threads, args.oversampling, args.force, args.rules, args.shared_queue)
    elif args.cmd == "slice":
        run_slice(args.stage, args.index, args.nslices, args.threads, args.oversampling, args.force, args.queue, args.max_jobs)
    elif args.cmd == "stageD":
        V.eligible = lambda stage: eligible(stage)          # the P8 funnel order
        if not args.no_refresh and OUT.resolve() == (REPO / "data/survey/p8").resolve():
            from p8_catalogs import refetch_tce_versions
            with refetch_tce_versions(OUT / "catalog_refetch_p8.json"):
                V.staged(force=args.force, refresh=True)
        else:
            V.staged(force=args.force, refresh=not args.no_refresh)
    elif args.cmd == "funnel":
        funnel()
    elif args.cmd == "census":
        V.census()
    elif args.cmd == "csv":
        print(write_secondary_csv() if args.stage == "S" else V.write_stage_csv(args.stage))
    elif args.cmd == "eligible":
        for j in eligible(args.stage):
            print(j["rank"], j["tic_id"], j["period"])
    elif args.cmd == "verdict":
        print(json.dumps(V.stamp_verdict(args.tic, args.period, args.verdict, args.reason, args.note), indent=1))


if __name__ == "__main__":
    main()
