"""Prompt 8 Part 3: settle the three rule decisions prompt 7 left open, by measurement.

One instrument for all three, run on three candidate sets:

* ``inj``  the RECOVERED prompt-8 injections (true planets by construction, constant depth by
           construction), under the ephemeris their Stage A record chose;
* ``p7``   the 405 prompt-6 candidates, under the ephemeris prompt 6 chose (the P7 option
           records are rerun with every variant; nothing is re-downloaded);
* ``adv``  the prompt-3 adversarial eclipsing binaries and blends (``data/adversarial/targets_v1.csv``)
           under their catalogued ephemerides.

For every candidate the script computes, from the same products: the event table on the
unmasked and on the transit-masked detrend, per-sector red-noise betas capped at 5 (caps 3
and 2 follow by re-clipping), the depth-consistency p-value under white errors and under
each cap, the six Stage A criteria at thresholds 1e-3, 1e-4 and 1e-5, and the secondary
gate under every variant (``secondary.apply_gate``) from one phase scan.

The masked variant uses the fixed event ephemeris above. A full Stage A run instead
detrends around the survey ephemeris before fitting TLS and choosing an event ephemeris.
Consequently, its stored decision need not equal this instrument's masked/cap5 decision;
the instrument isolates variants at one fixed ephemeris, without rerunning TLS.

PRE-REGISTERED DECISION RULES (written before the measurement; X is never changed):

  X = 90 percent.

  Decision 1 (the secondary gate).  Completeness = the fraction of recovered injections
  passing Stage A whose gate is not FAIL under the variant.  Kills = the fraction of the
  adversarial EBs and blends that p7.0's gate FAILs which the variant still FAILs.  Choose
  the variant with the highest completeness among those that retain at least X percent of
  the p7.0 kills; a tie goes to the variant retaining more kills, then to p7.0.  Variants:
  (a) bound (p7.0); (b) quiet_bound with N=2; (c) quiet_zero with N in {2, 3, 5};
  (d) quiet_bound_hold with N=2.

  Decisions 2 and 3 (depth consistency and the masked detrend, chosen together).
  Completeness = the fraction of recovered injections passing ALL SIX Stage A criteria
  under the variant (mask on/off x errors in {white, inflated cap 2, cap 3, cap 5} x
  threshold, with the threshold moved only for white errors: 1e-3, 1e-4, 1e-5).  Kills = the
  fraction of the reference kill set - the 18 prompt-6 candidates that failed only depth
  consistency plus the adversarial EBs and blends - that p7.0 (mask on, cap 5, 1e-3) FAILs
  on depth consistency which the variant still FAILs on depth consistency.  Choose the
  combination with the highest completeness among those retaining at least X percent of the
  p7.0 kills; a tie goes to the combination retaining more kills, then to p7.0.

  The secondary-gate and depth-consistency kill rates on the 405 are reported, never used
  in a rule (their truth is unknown).  No prompt-8 real candidate is used anywhere here.

Outputs: ``data/survey/p8/decisions/<set>/<key>.json`` per candidate, ``decisions_p8.json``
with the tables and the decisions, and the ``docs/RULES.md`` section text.
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
P6 = REPO / "data" / "survey" / "p6"
P7OPT = REPO / "data" / "survey" / "p7" / "options"
LC_ROOT = REPO / "data" / "survey" / "audit_lc"
INJ_ROOT = P8 / "inj_funnel"
DEC = P8 / "decisions"
ADV = REPO / "data" / "adversarial" / "targets_v1.csv"
PY = sys.executable
BTJD = 2457000.0

X_RETAIN = 0.90
CAPS = (2.0, 3.0, 5.0)
THRESHOLDS = (1e-3, 1e-4, 1e-5)
SEC_VARIANTS = ("bound", "quiet_bound", "quiet_zero_N2", "quiet_zero_N3", "quiet_zero_N5", "quiet_bound_hold")

from tesshunter import audit_rules as R                                            # noqa: E402
from tesshunter.audit_prep import clean_and_detrend, detrend_window_days, expected_t14_hours, prepare_series, transit_mask  # noqa: E402
from tesshunter.event_vet import event_table, sector_beta, stagea_criteria, summarise_events   # noqa: E402
from tesshunter.secondary import apply_gate, secondary_scan                         # noqa: E402


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _mask_fn(eph):
    return lambda tt: transit_mask(tt, eph["period"], eph["t0"], eph["duration"])


def measure(products: list[dict], eph: dict, survey_depth_ppt: float, window: float, rstar: float, mstar: float,
            teff: float, secondary_from: dict | None = None) -> dict:
    """Everything the three decisions need for one candidate, from one set of products."""
    ref_depth = (survey_depth_ppt or 1.0) / 1000.0
    cad = {int(p["sector"]): float(p["cadence_s"]) for p in products}
    out = {"ephemeris": eph, "survey_depth_ppt": survey_depth_ppt, "window_days": window, "by_mask": {}}
    for mask_on in (False, True):
        prep = prepare_series(products, window, R.BIN_MINUTES, ref_depth, mask_fn=(_mask_fn(eph) if mask_on else None))
        un = prep["unbinned"]
        t, f, s = un["time"], un["flux"], un["sector"]
        events = event_table(products, t, f, eph["period"], eph["t0"], eph["duration"], ref_depth)
        in_tr = transit_mask(t, eph["period"], eph["t0"], eph["duration"], n_durations=0.5)
        beta5 = sector_beta(t, f, s, in_tr, eph["duration"], cad, beta_max=5.0)
        block = {"n_unbinned": int(len(t)), "beta_by_sector_cap5": {str(k): round(v, 3) for k, v in beta5.items()},
                 "variants": {}}
        for errors in ("white",) + tuple(f"cap{int(c)}" for c in CAPS):
            if errors == "white":
                summ = summarise_events(events, eph, beta_by_sector=None)
            else:
                capv = float(errors[3:])
                beta = {k: min(v, capv) for k, v in beta5.items()}
                summ = summarise_events(events, eph, beta_by_sector=beta, gate_errors="inflated")
            dk = summ["det_kept"]
            v = {"n_kept": summ["n_kept"], "n_observed": summ["n_observed"], "kept_snr": dk.get("snr"),
                 "p_const": dk.get("p_const"), "p_const_white": dk.get("p_const_white", dk.get("p_const")),
                 "kept_depth_ppt": dk.get("weighted_mean_depth_ppt"), "criteria": {}}
            for thr in (THRESHOLDS if errors == "white" else (1e-3,)):
                c = stagea_criteria(dk, survey_depth_ppt, p_min=thr)
                v["criteria"][f"{thr:g}"] = {"all": c["all_passed"], "n_passed": c["n_criteria_passed"],
                                             "depth_consistent": c["criteria"]["depths_consistent_p_ge_1e-3"],
                                             "depth_window": c["criteria"]["depth_within_0.5_2x_survey"],
                                             "depth_over_survey": c["depth_over_survey_depth"]}
            block["variants"][errors] = v
        out["by_mask"]["masked" if mask_on else "unmasked"] = block
        if mask_on and secondary_from is None:
            # the scan on the masked series (the p7.0 series), SAP detrended alongside
            sap = clean_and_detrend(products, window, flux_key="sap_flux", err_key="sap_flux_err")
            sec = secondary_scan(t, f, eph["period"], eph["t0"], eph["duration"], rstar, mstar, teff,
                                 sap["time"], sap["flux"])
            out["secondary"] = {k: sec.get(k) for k in ("n_dips_above_5sigma", "variability_flag", "gate", "gate_by_mode",
                                                        "secondary_sigma_over_planet_bound", "secondary_sigma_over_zero",
                                                        "primary", "secondaries", "deepest_secondary_in_sap",
                                                        "planet_secondary_bound", "verdict")}
    if secondary_from is not None:
        out["secondary"] = secondary_from
    return out


def gate_variants_from(sec: dict) -> dict:
    """Every decision-1 variant's gate from a stored scan.

    Current scans already record every variant before rounding the displayed SAP
    depth and error. Use those decisions: reconstructing a near-threshold gate
    from the rounded values can change it. Only older scans need reconstruction.

    A prompt-7 record (``data/survey/p7/options``) predates the primary-shoulder split of
    prompt 8, so its ``secondaries`` are re-split here with the same rule, its deepest
    genuine secondary re-measured from the stored dips (the SAP re-measurement in the record
    is of the deepest stored dip, which may be a shoulder; where the deepest genuine secondary
    is a different dip the detrended depth is used and ``gate_measured_in`` says so).
    """
    recorded = (sec or {}).get("gate_by_mode")
    if recorded is not None:
        if any(recorded.get(v) not in ("PASS", "FAIL", "HOLD") for v in SEC_VARIANTS):
            raise ValueError("incomplete recorded secondary variants; exact gate decisions required")
        return {v: recorded[v] for v in SEC_VARIANTS}
    if not sec or sec.get("primary") is None or not sec.get("secondaries"):
        return {v: "PASS" for v in SEC_VARIANTS}
    from tesshunter.secondary import split_primary_shoulders
    prim = sec["primary"]
    dips = [prim] + list(sec["secondaries"])
    secs, shoulders = split_primary_shoulders(dips, prim, sec.get("box_width_days") or 0.0, sec.get("period_days") or 1.0)
    if not secs:
        return {v: "PASS" for v in SEC_VARIANTS}
    d = secs[0]
    sap = sec.get("deepest_secondary_in_sap")
    if sap and abs(float(sap.get("phase", -9)) - float(d["phase"])) < 1e-6:
        depth, err = sap["depth_ppt"], sap["err_ppt"]
    else:
        depth, err = d["depth_ppt"], d["err_ppt"]
    b = sec["planet_secondary_bound"]["max_planetary_secondary_ppt"]
    n = int(sec["n_dips_above_5sigma"]) - len(shoulders); var = bool(n > 5)
    return {"bound": apply_gate(depth, err, b, n, var, "bound", 2)["gate"],
            "quiet_bound": apply_gate(depth, err, b, n, var, "quiet_bound", 2)["gate"],
            "quiet_zero_N2": apply_gate(depth, err, b, n, var, "quiet_zero", 2)["gate"],
            "quiet_zero_N3": apply_gate(depth, err, b, n, var, "quiet_zero", 3)["gate"],
            "quiet_zero_N5": apply_gate(depth, err, b, n, var, "quiet_zero", 5)["gate"],
            "quiet_bound_hold": apply_gate(depth, err, b, n, var, "quiet_bound_hold", 2)["gate"]}


# ─────────────────────────────────────────────────────────────────────────────
# the three candidate sets
# ─────────────────────────────────────────────────────────────────────────────
def jobs_inj() -> list[dict]:
    import p8_completeness as C
    from analyze_completeness import _load_results
    jobs = C.recovered_jobs(_load_results(C.INJ_RUN))
    C.load_funnel_outcomes(jobs, rules="p7.0")
    return [injection_job(j) for j in jobs]


def injection_job(j: dict) -> dict:
    """One settled injection's instrument input; selecting rules still requires the full set."""
    import p8_completeness as C
    root = INJ_ROOT / j["job_id"]
    k = C.kkey(j["tic_id"], j["period_days"])
    ra = C.require_settled_record(root / "stageA" / f"{k}.json", "p7.0", "decision", ("PASS", "FAIL"))
    rs = C.require_settled_record(root / "secondary" / f"{k}.json", "p7.0", "gate", ("PASS", "FAIL", "HOLD"))
    prep = json.loads((root / "prep" / f"{k}.json").read_text(encoding="utf-8"))
    return {"set": "inj", "key": j["job_id"], "tic_id": j["tic_id"], "job": j,
            "eph": ra["per_ephemeris"][ra["chosen_ephemeris"]]["ephemeris"],
            "survey_depth_ppt": float(j["depth_ppt"]), "window": prep["wotan"]["window_days"],
            "rstar": prep["R_star"], "mstar": prep["M_star"], "teff": float(j["teff_k"] or 3300.0),
            "stageA_p7": ra["decision"], "secondary_from": rs["secondary"], "truth": "planet"}


def jobs_p7() -> list[dict]:
    surv = {(int(r["tic_id"]), round(float(r["period_days"]), 4)): r
            for r in csv.DictReader(open(REPO / "data" / "survey" / "p4" / "survivors.csv", newline="", encoding="utf-8"))}
    out = []
    for p in sorted(P7OPT.glob("*.json")):
        r7 = json.loads(p.read_text(encoding="utf-8"))
        if r7.get("status") != "OK":
            continue
        k = r7["key"]
        tic, per = r7["tic_id"], r7["survey_period"]
        ra = json.loads((P6 / "stageA" / f"{k}.json").read_text(encoding="utf-8"))
        prep = json.loads((P6 / "prep" / f"{k}.json").read_text(encoding="utf-8"))
        st = REPO / "data" / "cache" / "tic" / f"tic{tic}.json"
        teff = None
        if st.exists():
            teff = json.loads(st.read_text(encoding="utf-8")).get("teff")
        row = surv.get((int(tic), round(float(per), 4)), {})
        if teff is None:
            teff = float(row.get("teff_k") or 5500.0)
        only_depth = (ra.get("n_criteria_passed") == 5 and not ra["criteria"]["depths_consistent_p_ge_1e-3"])
        out.append({"set": "p7", "key": k, "tic_id": tic, "rank": r7["rank"],
                    "eph": ra["per_ephemeris"][ra["chosen_ephemeris"]]["ephemeris"],
                    "survey_depth_ppt": float(r7["survey_depth_ppt"]), "window": prep["wotan"]["window_days"],
                    "rstar": prep["R_star"], "mstar": prep["M_star"], "teff": float(teff),
                    "stageA_p6": ra["decision"], "only_depth_consistency_fail_p6": bool(only_depth),
                    "secondary_from": r7.get("secondary"), "truth": "unknown"})
    return out


def jobs_adv() -> list[dict]:
    out = []
    for r in csv.DictReader(open(ADV, newline="", encoding="utf-8")):
        if r["cls"] not in ("eb", "blend"):
            continue
        tic = int(r["tic_id"])
        if not (LC_ROOT / f"tic{tic}" / "index.json").exists():
            continue
        st = REPO / "data" / "cache" / "tic" / f"tic{tic}.json"
        s = json.loads(st.read_text(encoding="utf-8")) if st.exists() else {}
        rstar = float(s.get("radius") or 1.0); mstar = float(s.get("mass") or rstar); teff = float(s.get("teff") or 5500.0)
        per = float(r["period_known"]); t0 = float(r["epoch_known_bjd"]) - BTJD
        dur = float(r["duration_h_known"]) / 24.0 if r.get("duration_h_known") not in ("", None) else 0.1
        depth = float(r["depth_ppm_known"]) / 1000.0
        t14 = expected_t14_hours(per, rstar, mstar)
        out.append({"set": "adv", "key": f"{r['cls']}_tic{tic}", "tic_id": tic, "cls": r["cls"], "name": r["name"],
                    "eph": {"period": per, "t0": t0, "duration": max(dur, 0.02), "source": "catalog", "ref_depth_ppt": depth},
                    "survey_depth_ppt": depth, "window": detrend_window_days(t14), "rstar": rstar, "mstar": mstar,
                    "teff": teff, "secondary_from": None, "truth": r["cls"]})
    return out


JOBS = {"inj": jobs_inj, "p7": jobs_p7, "adv": jobs_adv}


def one(job: dict, force: bool = False) -> dict:
    import audit_p5 as A
    from tesshunter.survey import get_config
    A.set_input_config(get_config("survey_p8") if job["set"] == "inj" else None)
    if job["set"] != "inj" and hasattr(A, "_load_products_uninjected"):
        A.load_products = A._load_products_uninjected
    A.set_roots(P8, LC_ROOT)
    out_path = DEC / job["set"] / f"{job['key']}.json"
    if out_path.exists() and not force:
        r = json.loads(out_path.read_text(encoding="utf-8"))
        if r.get("status") == "OK" and r.get("input_config") == A.input_config():
            gates = gate_variants_from(r.get("secondary"))
            if gates != r.get("gate_variants"):
                r["gate_variants"] = gates
                A.jdump(out_path, r)
            return r
    t0 = time.perf_counter()
    rec = {k: v for k, v in job.items() if k not in ("secondary_from", "job")}
    rec.update({"generated_utc": utc(), "x_retain": X_RETAIN})
    try:
        if job["set"] == "inj":
            import p8_completeness as C
            C.install_injection(job["job"])
        products = A.choose_per_sector(A.load_products(job["tic_id"]))
        m = measure(products, job["eph"], job["survey_depth_ppt"], job["window"], job["rstar"], job["mstar"], job["teff"],
                    secondary_from=job.get("secondary_from"))
        m["gate_variants"] = gate_variants_from(m.get("secondary"))
        rec.update(m)
        if A.input_config() is not None:
            rec["input_config"] = A.input_config()
        rec["status"] = "OK"
    except Exception as exc:
        rec.update({"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"[:400]})
    rec["seconds"] = round(time.perf_counter() - t0, 1)
    A.jdump(out_path, rec)
    return rec


def run_slice(sets: list[str], index: int, nslices: int, force: bool) -> None:
    from p8_worker_qos import configure_current_worker
    configure_current_worker()
    jobs = [j for s in sets for j in JOBS[s]()]
    mine = jobs[index::nslices]
    print(f"slice {index}/{nslices}: {len(mine)} of {len(jobs)} candidates ({sets})", flush=True)
    t0 = time.perf_counter()
    for i, j in enumerate(mine, 1):
        r = one(j, force)
        el = time.perf_counter() - t0
        print(f"[{index}:{i}/{len(mine)}] {j['set']} {j['key']:<26} {r['status']} {r.get('seconds', 0):>6.1f} s "
              f"{r.get('error', '')[:80]} | elapsed {el / 60:.1f} min eta {(el / i) * (len(mine) - i) / 60:.1f} min", flush=True)


def run(sets: list[str], nslices: int, force: bool) -> None:
    DEC.mkdir(parents=True, exist_ok=True)
    logdir = P8 / "logs"; logdir.mkdir(parents=True, exist_ok=True)
    procs = []
    for i in range(nslices):
        log = open(logdir / f"decisions_{'_'.join(sets)}_slice{i}.log", "w", encoding="utf-8")
        cmd = [PY, str(Path(__file__).resolve()), "slice", "--sets", ",".join(sets), "--index", str(i), "--nslices", str(nslices)]
        if force:
            cmd.append("--force")
        procs.append((i, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=str(REPO)), log))
    codes = [(i, pr.wait()) for i, pr, log in procs]
    for _, _, log in procs:
        log.close()
    print("slice exit codes:", codes, flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# the tables and the decisions
# ─────────────────────────────────────────────────────────────────────────────
def load_set(name: str) -> list[dict]:
    d = DEC / name
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))] if d.exists() else []


def d23_variants() -> list[tuple[str, str, str]]:
    v = []
    for mask in ("unmasked", "masked"):
        for errors in ("white",) + tuple(f"cap{int(c)}" for c in CAPS):
            for thr in (THRESHOLDS if errors == "white" else (1e-3,)):
                v.append((mask, errors, f"{thr:g}"))
    return v


def d23_pass(rec: dict, mask: str, errors: str, thr: str, what: str = "all") -> bool | None:
    try:
        return bool(rec["by_mask"][mask]["variants"][errors]["criteria"][thr][what])
    except KeyError:
        return None


def frac(xs) -> float | None:
    xs = [x for x in xs if x is not None]
    return (sum(xs) / len(xs)) if xs else None


def tables() -> dict:
    inj, p7, adv = load_set("inj"), load_set("p7"), load_set("adv")
    for name, records, expected in (("inj", inj, jobs_inj()), ("p7", p7, jobs_p7()), ("adv", adv, jobs_adv())):
        validate_measurement_set(name, records, {j["key"] for j in expected})
    inj = [r for r in inj if r.get("status") == "OK"]; p7 = [r for r in p7 if r.get("status") == "OK"]
    adv = [r for r in adv if r.get("status") == "OK"]
    # Current scans retain exact decisions. Older scans need the primary-shoulder
    # reconstruction; no gate is rebuilt from rounded current display values.
    for r in inj + p7 + adv:
        r["gate_variants"] = gate_variants_from(r.get("secondary"))
        sec = r.get("secondary") or {}
        r["n_shoulder_dips"] = len(sec.get("primary_shoulder_dips") or []) if "primary_shoulder_dips" in sec else None
    res = {"generated_utc": utc(), "x_retain": X_RETAIN, "n": {"inj": len(inj), "p7": len(p7), "adv": len(adv),
                                                                "adv_eb": sum(r["cls"] == "eb" for r in adv),
                                                                "adv_blend": sum(r["cls"] == "blend" for r in adv)}}
    # ── decision 1 ──────────────────────────────────────────────────────────
    P7 = "masked"
    inj_a = [r for r in inj if d23_pass(r, P7, "cap5", "0.001")]            # Stage A passers under p7.0 rules
    adv_kill_ref = [r for r in adv if r["gate_variants"]["bound"] == "FAIL"]
    p7_kill_ref = [r for r in p7 if r["gate_variants"]["bound"] == "FAIL"]
    d1 = {"n_inj_stageA_pass": len(inj_a), "n_adv_p7_gate_kills": len(adv_kill_ref),
          "n_adv_eb_p7_kills": sum(r["cls"] == "eb" for r in adv_kill_ref),
          "n_adv_blend_p7_kills": sum(r["cls"] == "blend" for r in adv_kill_ref),
          "n_p7_gate_kills_405": len(p7_kill_ref), "variants": {}}
    for v in SEC_VARIANTS:
        comp = frac([r["gate_variants"][v] != "FAIL" for r in inj_a])
        held = sum(r["gate_variants"][v] == "HOLD" for r in inj_a)
        kills_adv = frac([r["gate_variants"][v] == "FAIL" for r in adv_kill_ref])
        kills_p7 = frac([r["gate_variants"][v] == "FAIL" for r in p7_kill_ref])
        d1["variants"][v] = {"completeness": comp, "n_inj_pass": sum(r["gate_variants"][v] != "FAIL" for r in inj_a),
                             "n_inj_hold": held, "retained_kills_adv": kills_adv,
                             "n_adv_kills": sum(r["gate_variants"][v] == "FAIL" for r in adv_kill_ref),
                             "adv_eb_killed": sum(r["gate_variants"][v] == "FAIL" for r in adv if r["cls"] == "eb"),
                             "adv_blend_killed": sum(r["gate_variants"][v] == "FAIL" for r in adv if r["cls"] == "blend"),
                             "retained_kills_405": kills_p7, "n_405_fail": sum(r["gate_variants"][v] == "FAIL" for r in p7),
                             "n_405_hold": sum(r["gate_variants"][v] == "HOLD" for r in p7),
                             "eligible": (kills_adv is None) or (kills_adv >= X_RETAIN)}
    elig = [(v, d) for v, d in d1["variants"].items() if d["eligible"] and d["completeness"] is not None]
    if elig:
        best = sorted(elig, key=lambda kv: (-(kv[1]["completeness"]), -(kv[1]["retained_kills_adv"] or 0), kv[0] != "bound"))[0][0]
    else:
        best = "bound"
    d1["decision"] = best
    d1["rule"] = ("highest completeness among variants retaining >= 90% of the p7.0 gate kills on the adversarial "
                  "EBs and blends; ties to more kills, then to p7.0")
    res["decision_1"] = d1
    # ── decisions 2 + 3 ─────────────────────────────────────────────────────
    ref = [r for r in p7 if r.get("only_depth_consistency_fail_p6")] + adv
    ref_kill = [r for r in ref if d23_pass(r, "masked", "cap5", "0.001", "depth_consistent") is False]
    ref_kill_p62 = [r for r in ref if d23_pass(r, "unmasked", "white", "0.001", "depth_consistent") is False]
    d23 = {"n_inj": len(inj), "n_reference": len(ref), "n_reference_18": sum(r.get("only_depth_consistency_fail_p6", False) for r in ref),
           "n_p7_depth_kills_in_reference": len(ref_kill), "n_p62_depth_kills_in_reference": len(ref_kill_p62), "variants": {}}
    for mask, errors, thr in d23_variants():
        name = f"{mask}|{errors}|{thr}"
        comp_all = frac([d23_pass(r, mask, errors, thr, "all") for r in inj])
        comp_dc = frac([d23_pass(r, mask, errors, thr, "depth_consistent") for r in inj])
        comp_dw = frac([d23_pass(r, mask, errors, thr, "depth_window") for r in inj])
        kills = frac([d23_pass(r, mask, errors, thr, "depth_consistent") is False for r in ref_kill])
        kills62 = frac([d23_pass(r, mask, errors, thr, "depth_consistent") is False for r in ref_kill_p62])
        d23["variants"][name] = {"mask": mask, "errors": errors, "threshold": thr,
                                 "completeness_all_six": comp_all, "completeness_depth_consistency": comp_dc,
                                 "completeness_depth_window": comp_dw,
                                 "n_inj_all_six": sum(bool(d23_pass(r, mask, errors, thr, "all")) for r in inj),
                                 "retained_kills_p7": kills, "retained_kills_p62": kills62,
                                 "n_405_depth_fail": sum(d23_pass(r, mask, errors, thr, "depth_consistent") is False for r in p7),
                                 "n_405_all_six": sum(bool(d23_pass(r, mask, errors, thr, "all")) for r in p7),
                                 "adv_eb_depth_fail": sum(d23_pass(r, mask, errors, thr, "depth_consistent") is False for r in adv if r["cls"] == "eb"),
                                 "adv_blend_depth_fail": sum(d23_pass(r, mask, errors, thr, "depth_consistent") is False for r in adv if r["cls"] == "blend"),
                                 "eligible": (kills is None) or (kills >= X_RETAIN)}
    elig = [(k, d) for k, d in d23["variants"].items() if d["eligible"] and d["completeness_all_six"] is not None]
    p7name = "masked|cap5|0.001"
    if elig:
        best = sorted(elig, key=lambda kv: (-(kv[1]["completeness_all_six"]), -(kv[1]["retained_kills_p7"] or 0), kv[0] != p7name))[0][0]
    else:
        best = p7name
    d23["decision"] = best
    d23["rule"] = ("highest all-six Stage A completeness among combinations retaining >= 90% of the p7.0 depth-consistency "
                   "kills on the reference set (the 18 + adversarial EBs and blends); ties to more kills, then to p7.0")
    res["decisions_2_3"] = d23
    # the white p-value distribution on the injections (uniform if the errors are right)
    for mask in ("unmasked", "masked"):
        for errors in ("white", "cap2", "cap3", "cap5"):
            ps = np.array([r["by_mask"][mask]["variants"][errors]["p_const"] for r in inj
                           if r["by_mask"][mask]["variants"][errors].get("p_const") is not None], dtype=float)
            if ps.size:
                from scipy import stats as sst
                res.setdefault("p_value_distribution_inj", {})[f"{mask}|{errors}"] = {
                    "n": int(ps.size), "frac_below_1e-3": float(np.mean(ps < 1e-3)), "frac_below_1e-2": float(np.mean(ps < 1e-2)),
                    "frac_below_0.05": float(np.mean(ps < 0.05)), "median": float(np.median(ps)),
                    "ks_uniform_p": float(sst.kstest(ps, "uniform").pvalue)}
    betas = [v for r in inj for v in r["by_mask"]["masked"]["beta_by_sector_cap5"].values()]
    if betas:
        res["beta_inj_masked_quantiles_p25_p50_p75_p90"] = [float(x) for x in np.percentile(betas, [25, 50, 75, 90])]
    (P8 / "decisions_p8.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    return res


def validate_measurement_set(name: str, records: list[dict], expected: set[str]) -> None:
    """A partial instrument must not select the rule set used on real candidates."""
    observed = {r["key"] for r in records if r.get("status") == "OK"}
    if not expected or observed != expected or len(records) != len(expected):
        raise ValueError(f"incomplete {name} decision instrument: {len(observed)}/{len(expected)} OK; resume measurement")
    if name == "inj":
        from audit_p5 import input_config_for
        from tesshunter.survey import get_config
        config = input_config_for(get_config("survey_p8"))
        if any(r.get("input_config") != config for r in records):
            raise ValueError("stale injection decision instrument: native-cadence records required")


def rules_section(res: dict) -> str:
    L = []
    a = L.append
    d1, d23 = res["decision_1"], res["decisions_2_3"]
    a("## 8. The prompt-8 decisions, measured (p8.0) **[P8]**\n")
    a(f"Instrument (`scripts/p8_decisions.py`): {res['n']['inj']} recovered prompt-8 injections (planets by construction), "
      f"the {res['n']['p7']} prompt-6 candidates under their prompt-6 ephemerides, and {res['n']['adv_eb']} adversarial "
      f"eclipsing binaries plus {res['n']['adv_blend']} blends under their catalogued ephemerides. X = {int(100 * res['x_retain'])}%, "
      "fixed before the measurement.\n")
    a("The variant instrument holds each event ephemeris fixed and uses it for the masked detrend. "
      "The injection ephemeris is the one selected by Stage A; the reference ephemerides are those stated above. "
      "This differs from a full Stage A run, which detrends around the survey ephemeris before fitting TLS. "
      "Thus the masked/cap5 column is a controlled variant measurement and need not exactly replay the stored "
      "Stage A decisions. The separate completeness calibration measures the actual full Stage A pipeline.\n")
    a("Current injection and adversarial scans supply their recorded gate variants, evaluated before the SAP "
      "display values were rounded. Their quiet-gate N counts the full phase-scan dip list, whereas the "
      "reported independent-dip count excludes primary shoulders; reconstructing gates from that count changes "
      "the implemented variants. Older prompt-7 scans lack variant decisions and use the documented "
      "shoulder reconstruction; the 405 are diagnostic only for Decision 1.\n")
    a(f"### Decision 1: the secondary gate ({d1['n_inj_stageA_pass']} Stage A-passing injections; p7.0 kills: "
      f"{d1['n_adv_p7_gate_kills']} of the adversarial set, {d1['n_p7_gate_kills_405']} of the 405)\n")
    a("| variant | injection completeness | injections held | adversarial kills retained | EBs killed | blends killed | 405 FAIL | 405 HOLD | eligible |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for v, d in d1["variants"].items():
        a(f"| {v} | {d['n_inj_pass']}/{d1['n_inj_stageA_pass']} ({100 * (d['completeness'] or 0):.1f}%) | {d['n_inj_hold']} | "
          f"{d['n_adv_kills']}/{d1['n_adv_p7_gate_kills']} ({100 * (d['retained_kills_adv'] or 0):.0f}%) | {d['adv_eb_killed']}/{res['n']['adv_eb']} | "
          f"{d['adv_blend_killed']}/{res['n']['adv_blend']} | {d['n_405_fail']} | {d['n_405_hold']} | {'yes' if d['eligible'] else 'no'} |")
    a(f"\n**Decision 1: `{d1['decision']}`** ({d1['rule']}).\n")
    a(f"### Decisions 2 and 3 together: depth consistency and the masked detrend ({d23['n_inj']} recovered injections; "
      f"reference kill set {d23['n_reference']} candidates, of which p7.0 fails {d23['n_p7_depth_kills_in_reference']} on depth consistency)\n")
    a("| detrend | errors | threshold | all six pass (injections) | depth-consistency pass | depth-window pass | p7.0 kills retained | p6.2 kills retained | 405 depth fail | 405 all six | eligible |")
    a("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for k, d in d23["variants"].items():
        a(f"| {d['mask']} | {d['errors']} | {d['threshold']} | {d['n_inj_all_six']}/{d23['n_inj']} ({100 * (d['completeness_all_six'] or 0):.1f}%) | "
          f"{100 * (d['completeness_depth_consistency'] or 0):.1f}% | {100 * (d['completeness_depth_window'] or 0):.1f}% | "
          f"{100 * (d['retained_kills_p7'] or 0):.0f}% | {100 * (d['retained_kills_p62'] or 0):.0f}% | {d['n_405_depth_fail']} | {d['n_405_all_six']} | "
          f"{'yes' if d['eligible'] else 'no'} |")
    a(f"\n**Decisions 2 and 3: `{d23['decision']}`** ({d23['rule']}).\n")
    pv = res.get("p_value_distribution_inj", {})
    if pv:
        a("Depth-consistency p-values on the recovered injections (constant injected depth). The uniform reference "
          "assumes the error model is correct; recovery selection, ephemeris estimation and event removal also "
          "condition this sample. The fractions below threshold are measured injection rejection rates, "
          "not unconditional nominal false-positive probabilities.\n")
        a("| detrend | errors | n | below 1e-3 | below 1e-2 | below 0.05 | median | KS uniform p |")
        a("|---|---|---:|---:|---:|---:|---:|---:|")
        for k, d in pv.items():
            m, e = k.split("|")
            a(f"| {m} | {e} | {d['n']} | {100 * d['frac_below_1e-3']:.1f}% | {100 * d['frac_below_1e-2']:.1f}% | {100 * d['frac_below_0.05']:.1f}% | {d['median']:.3f} | {d['ks_uniform_p']:.2g} |")
        a("")
    return "\n".join(L)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--sets", default="inj,p7,adv"); r.add_argument("--slices", type=int, default=16)
    r.add_argument("--force", action="store_true")
    s = sub.add_parser("slice"); s.add_argument("--sets", required=True); s.add_argument("--index", type=int, required=True)
    s.add_argument("--nslices", type=int, required=True); s.add_argument("--force", action="store_true")
    sub.add_parser("tables")
    j = sub.add_parser("jobs"); j.add_argument("--sets", default="inj,p7,adv")
    args = ap.parse_args(argv)
    if args.cmd == "run":
        run(args.sets.split(","), args.slices, args.force)
    elif args.cmd == "slice":
        run_slice(args.sets.split(","), args.index, args.nslices, args.force)
    elif args.cmd == "tables":
        res = tables()
        print(rules_section(res))
        print(json.dumps({"decision_1": res["decision_1"]["decision"], "decisions_2_3": res["decisions_2_3"]["decision"]}, indent=1))
    elif args.cmd == "jobs":
        for s_ in args.sets.split(","):
            print(s_, len(JOBS[s_]()))


if __name__ == "__main__":
    main()
