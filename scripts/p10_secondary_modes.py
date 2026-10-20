"""Prompt 10 Part 2a: the secondary-scan gate modes, measured (HANDOFF_P10.md section 0.2).

One scan per candidate evaluates the p8.0 ``bound`` gate and the three prompt-10 modes
(``empirical_bound``, ``recurrent_bound``, ``recurrent_bound_corr``) on identical inputs:

    inj     the recovered P8 injections that passed Stage A (planets by construction; every
            secondary FAIL is a false kill): the injection funnel roots under
            data/survey/p8/inj_funnel, the injection re-installed in every flux column
    adv     the prompt-3 adversarial eclipsing binaries and blends under their catalogued
            ephemerides (data/adversarial/targets_v1.csv), as the P8 instrument built them
    p8pass  the 189 P8 Stage A passers (170 secondary rejections plus 19 passers) from the
            P8 tree, read-only; the rejections are cross-tabulated with their EB screen review
    p6eb    TIC 233007823, the prompt-6 eccentric eclipsing binary (secondary at phase 0.605),
            which every eligible mode must FAIL
    dev     the P9 development hosts and the five audit-named hosts (rule 8), from the P9
            blind tree, read-only

Nothing under data/survey/p8, data/survey/p9 or p9 is written; records go to
data/survey/p10/secondary_modes/<set>/ and the tables to p10/results/secondary_modes.{json,md}.

PRE-REGISTERED DECISION RULE (HANDOFF_P10.md 0.2, Y = 90%): choose the mode with the lowest
injection false-kill rate FK among those that retain at least 90% of the p8.0 ``bound`` kills
on the adversarial EB and blend set and that FAIL TIC 233007823; an exact tie in FK goes to
the simpler mode (bound < empirical_bound < recurrent_bound < recurrent_bound_corr).  The
p8pass and dev sets are descriptive and never enter the rule.

Nothing here submits anything anywhere.  The pipeline finds candidates.
"""
from __future__ import annotations

import argparse
import csv
import glob
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
INJ_ROOT = P8 / "inj_funnel"
LC_ROOT = REPO / "data" / "survey" / "audit_lc"
P9 = REPO / "p9"
OUT = REPO / "data" / "survey" / "p10" / "secondary_modes"
RES = REPO / "p10" / "results"
LOGS = REPO / "p10" / "logs"
PY = sys.executable

SETS = ("inj", "adv", "p8pass", "p6eb", "dev")
MODES = ("bound", "empirical_bound", "recurrent_bound", "recurrent_bound_corr")
SIMPLER = {m: i for i, m in enumerate(MODES)}
Y_RETAIN = 0.90
P6_EB_TIC = 233007823
DEV_HOSTS = (335590096, 181804752, 161032923, 159579593, 377293776, 164828012, 271971130, 33153766, 167009792,
             237222864, 284441182, 33595516)

from tesshunter import audit_rules as R                                                     # noqa: E402
from tesshunter.audit_prep import clean_and_detrend, prepare_series, transit_mask          # noqa: E402
from tesshunter.secondary import GATE_MODES_P10, secondary_scan                              # noqa: E402


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def kkey(tic, period):
    return f"tic{int(tic)}_P{float(period):.4f}"


# ─────────────────────────────────────────────────────────────────────────────
# the jobs
# ─────────────────────────────────────────────────────────────────────────────
def jobs_inj() -> list[dict]:
    import p8_decisions as D
    out = []
    for j in D.jobs_inj():
        if j["stageA_p7"] != "PASS":
            continue
        key = kkey(j["tic_id"], j["job"]["period_days"])
        out.append({"set": "inj", "key": j["key"], "tic_id": j["tic_id"], "period": float(j["job"]["period_days"]),
                    "eph": j["eph"], "survey_depth_ppt": j["survey_depth_ppt"], "window": j["window"],
                    "rstar": j["rstar"], "mstar": j["mstar"], "teff": j["teff"], "truth": "planet",
                    "root": str(INJ_ROOT / j["key"]), "lc_root": str(LC_ROOT), "series_key": key,
                    "injection": j["job"], "reference_gate": (j.get("secondary_from") or {}).get("gate"),
                    "reference_source": "inj_funnel secondary record (p7.0 = p8.0 bound)"})
    return out


def jobs_adv() -> list[dict]:
    import p8_decisions as D
    out = []
    for j in D.jobs_adv():
        ref = D.DEC / "adv" / f"{j['key']}.json"
        rg = read(ref).get("gate_variants", {}).get("bound") if ref.exists() else None
        out.append({"set": "adv", "key": j["key"], "tic_id": j["tic_id"], "period": j["eph"]["period"], "eph": j["eph"],
                    "survey_depth_ppt": j["survey_depth_ppt"], "window": j["window"], "rstar": j["rstar"],
                    "mstar": j["mstar"], "teff": j["teff"], "truth": j["cls"], "name": j["name"],
                    "root": str(P8), "lc_root": str(LC_ROOT), "series_key": None, "injection": None,
                    "reference_gate": rg, "reference_source": "data/survey/p8/decisions/adv (p8.0 instrument)"})
    return out


def _reviews() -> dict:
    out = {}
    for p in sorted(glob.glob(str(P8 / "eb_screen" / "review_ready_batch*.json"))):
        for rec in read(p).get("records", []):
            out.setdefault(rec["key"], {"visual_review": rec.get("visual_review"), "assessment": rec.get("assessment"),
                                        "catalogue_match": rec.get("catalogue_match"), "source": os.path.basename(p)})
    return out


def review_class(text: str | None) -> str:
    """A coarse keyword class of the free-text EB screen review, descriptive only."""
    s = (text or "").lower()
    if any(w in s for w in ("modulation", "sinusoid", "rotation", "rotational", "spot")):
        return "modulation"
    if any(w in s for w in ("eclipse", "detached", "secondary", "binary", "contact")):
        return "eclipse_like"
    if any(w in s for w in ("ramp", "systematic", "gap", "background", "scattered", "artefact", "artifact", "step")):
        return "systematics"
    return "other"


def jobs_p8pass() -> list[dict]:
    import audit_p5 as A
    A.set_roots(P8, LC_ROOT)
    reviews = _reviews()
    out = []
    for p in sorted((P8 / "secondary").glob("tic*.json")):
        s = read(p)
        if s.get("stageA_decision") != "PASS" or s.get("stageA_sample"):
            continue
        key, tic, period = s["key"], int(s["tic_id"]), float(s["survey_period"])
        a = read(P8 / "stageA" / f"{key}.json")
        prep = read(P8 / "prep" / f"{key}.json")
        st = A.stellar_from_cache(tic)
        teff = float(st["teff"]) if st.get("teff") else float(s.get("secondary", {}).get("teff_K") or 3300.0)
        rv = reviews.get(key)
        out.append({"set": "p8pass", "key": key, "tic_id": tic, "period": period,
                    "eph": a["per_ephemeris"][a["chosen_ephemeris"]]["ephemeris"],
                    "survey_depth_ppt": float(s["survey_depth_ppt"]), "window": prep["wotan"]["window_days"],
                    "rstar": prep["R_star"], "mstar": prep["M_star"], "teff": teff, "truth": "unknown",
                    "root": str(P8), "lc_root": str(LC_ROOT), "series_key": key, "injection": None,
                    "reference_gate": s.get("gate"), "reference_source": "data/survey/p8/secondary (p8.0)",
                    "review": rv, "review_class": review_class((rv or {}).get("visual_review")) if rv else None})
    return out


def jobs_p6eb() -> list[dict]:
    import p8_decisions as D
    out = []
    for j in D.jobs_p7():
        if int(j["tic_id"]) != P6_EB_TIC:
            continue
        out.append({"set": "p6eb", "key": j["key"], "tic_id": j["tic_id"], "period": j["eph"]["period"], "eph": j["eph"],
                    "survey_depth_ppt": j["survey_depth_ppt"], "window": j["window"], "rstar": j["rstar"],
                    "mstar": j["mstar"], "teff": j["teff"], "truth": "eccentric_EB", "root": str(P8),
                    "lc_root": str(LC_ROOT), "series_key": None, "injection": None,
                    "reference_gate": (j.get("secondary_from") or {}).get("gate"),
                    "reference_source": "data/survey/p7/options (p7.0 scan)"})
    return out


def jobs_dev() -> list[dict]:
    out = []
    for tic in DEV_HOSTS:
        root = P9 / "results" / "blind" / f"tic{tic}"
        st_path = P9 / "inputs" / "stellar" / f"tic{tic}.json"
        st = read(st_path) if st_path.exists() else {}
        for p in sorted((root / "secondary").glob("tic*.json")):
            s = read(p)
            key, period = s["key"], float(s["survey_period"])
            a = read(root / "stageA" / f"{key}.json")
            prep = read(root / "prep" / f"{key}.json")
            out.append({"set": "dev", "key": key, "tic_id": int(tic), "period": period,
                        "eph": a["per_ephemeris"][a["chosen_ephemeris"]]["ephemeris"],
                        "survey_depth_ppt": float(s["survey_depth_ppt"]), "window": prep["wotan"]["window_days"],
                        "rstar": prep["R_star"], "mstar": prep["M_star"],
                        "teff": float(st.get("teff") or s.get("secondary", {}).get("teff_K") or 3300.0),
                        "truth": "P9 development host", "root": str(root), "lc_root": str(P9 / "inputs" / "raw"),
                        "series_key": key, "injection": None, "reference_gate": s.get("gate"),
                        "reference_source": "p9/results/blind secondary record (p8.0)"})
    return out


JOBS = {"inj": jobs_inj, "adv": jobs_adv, "p8pass": jobs_p8pass, "p6eb": jobs_p6eb, "dev": jobs_dev}


# ─────────────────────────────────────────────────────────────────────────────
# one candidate
# ─────────────────────────────────────────────────────────────────────────────
def one(job: dict, force: bool = False) -> dict:
    import audit_p5 as A
    from tesshunter.survey import get_config
    out_path = OUT / job["set"] / f"{job['key']}.json"
    if out_path.exists() and not force:
        r = read(out_path)
        if r.get("status") == "OK":
            return r
    t_start = time.perf_counter()
    rec = {k: v for k, v in job.items() if k not in ("injection",)}
    rec.update({"generated_utc": utc(), "y_retain": Y_RETAIN})
    try:
        A.set_input_config(get_config("survey_p8") if job["set"] in ("inj", "p8pass", "dev") else None)
        if hasattr(A, "_load_products_uninjected"):
            A.load_products = A._load_products_uninjected
        A.set_roots(job["root"], job["lc_root"])
        if job.get("injection"):
            import p8_completeness as C
            C.install_injection(job["injection"])
        products = A.choose_per_sector(A.load_products(job["tic_id"]))
        eph, window = job["eph"], job["window"]
        if job.get("series_key"):
            with np.load(Path(job["root"]) / "tls" / f"{job['series_key']}_lc.npz") as z:
                t, f = z["time_unbinned"], z["flux_unbinned"]
            rec["series"] = f"{job['root']}/tls/{job['series_key']}_lc.npz"
        else:
            ref_depth = (job["survey_depth_ppt"] or 1.0) / 1000.0
            prep = prepare_series(products, window, R.BIN_MINUTES, ref_depth,
                                  mask_fn=lambda tt: transit_mask(tt, eph["period"], eph["t0"], eph["duration"]))
            t, f = prep["unbinned"]["time"], prep["unbinned"]["flux"]
            rec["series"] = "prepare_series (transit-masked, the p7.0/p8.0 recipe) on the products"
        sap = clean_and_detrend(products, window, flux_key="sap_flux", err_key="sap_flux_err")
        sec = secondary_scan(t, f, eph["period"], eph["t0"], eph["duration"], job["rstar"], job["mstar"], job["teff"],
                             sap["time"], sap["flux"], gate_mode="bound", quiet_max_dips=2,
                             t_sap_sector=sap["sector"], p10_modes=True)
        rec.update({"gate_bound": sec["gate"], "gate_by_mode": sec.get("gate_by_mode"),
                    "gate_by_mode_p10": sec.get("gate_by_mode_p10"),
                    "gates": {"bound": sec["gate"], **{m: sec["gate_by_mode_p10"][m] for m in GATE_MODES_P10}},
                    "n_dips_above_5sigma": sec.get("n_dips_above_5sigma"), "variability_flag": sec.get("variability_flag"),
                    "primary": sec.get("primary"), "deepest_secondary": (sec.get("secondaries") or [None])[0],
                    "deepest_secondary_in_sap": sec.get("deepest_secondary_in_sap"),
                    "planet_secondary_bound_ppt": (sec.get("planet_secondary_bound") or {}).get("max_planetary_secondary_ppt"),
                    "secondary_sigma_over_planet_bound": sec.get("secondary_sigma_over_planet_bound"),
                    "p10": sec.get("p10"), "verdict": sec.get("verdict"),
                    "n_points": sec.get("n_points"), "sap_products_used": int(sum(1 for p in sap["per_product"] if not p["dropped"])),
                    "reference_gate_agrees": (job.get("reference_gate") is None) or (job["reference_gate"] == sec["gate"]),
                    "status": "OK"})
    except Exception as exc:
        rec.update({"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"[:400]})
    rec["seconds"] = round(time.perf_counter() - t_start, 1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(rec, indent=1, default=str, allow_nan=True), encoding="utf-8")
    os.replace(tmp, out_path)
    return rec


def all_jobs(sets: list[str], limit: int | None = None) -> list[dict]:
    jobs = []
    for s in sets:
        js = JOBS[s]()
        jobs.extend(js[:limit] if limit else js)
    return jobs


def run_slice(sets: list[str], index: int, nslices: int, force: bool, limit: int | None) -> None:
    try:
        from p8_worker_qos import configure_current_worker
        configure_current_worker()
    except Exception:
        pass
    jobs = all_jobs(sets, limit)
    mine = jobs[index::nslices]
    print(f"slice {index}/{nslices}: {len(mine)} of {len(jobs)} candidates ({sets})", flush=True)
    t0 = time.perf_counter()
    for i, j in enumerate(mine, 1):
        r = one(j, force)
        el = time.perf_counter() - t0
        print(f"[{index}:{i}/{len(mine)}] {j['set']:<6} {j['key']:<28} {r['status']} {r.get('seconds', 0):>6.1f} s "
              f"{json.dumps(r.get('gates')) if r.get('gates') else r.get('error', '')[:100]} | elapsed {el / 60:.1f} min "
              f"eta {(el / i) * (len(mine) - i) / 60:.1f} min", flush=True)


def run(sets: list[str], nslices: int, force: bool, limit: int | None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    procs = []
    for i in range(nslices):
        log = open(LOGS / f"secondary_modes_{'_'.join(sets)}_slice{i}.log", "w", encoding="utf-8")
        cmd = [PY, str(Path(__file__).resolve()), "slice", "--sets", ",".join(sets), "--index", str(i), "--nslices", str(nslices)]
        if force:
            cmd.append("--force")
        if limit:
            cmd += ["--limit", str(limit)]
        procs.append((i, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=str(REPO)), log))
    codes = [(i, pr.wait()) for i, pr, log in procs]
    for _, _, log in procs:
        log.close()
    print("slice exit codes:", codes, flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# the tables and the decision
# ─────────────────────────────────────────────────────────────────────────────
def load_set(name: str) -> list[dict]:
    return [read(p) for p in sorted((OUT / name).glob("*.json"))]


def frac(xs) -> float | None:
    xs = list(xs)
    return (sum(1 for x in xs if x) / len(xs)) if xs else None


def tables() -> dict:
    sets = {s: load_set(s) for s in SETS}
    ok = {s: [r for r in rs if r.get("status") == "OK"] for s, rs in sets.items()}
    res = {"generated_utc": utc(), "y_retain": Y_RETAIN, "modes": list(MODES),
           "n": {s: {"records": len(sets[s]), "ok": len(ok[s]), "error": len(sets[s]) - len(ok[s])} for s in SETS},
           "errors": {s: [{"key": r["key"], "error": r.get("error")} for r in sets[s] if r.get("status") != "OK"][:20] for s in SETS}}
    inj, adv, p8p, p6, dev = (ok[s] for s in SETS)
    # reference agreement: the rescanned bound gate must equal the saved p8.0 decision
    res["reference_agreement"] = {s: {"n_with_reference": sum(1 for r in ok[s] if r.get("reference_gate") is not None),
                                      "n_disagree": sum(1 for r in ok[s] if r.get("reference_gate") is not None and r["reference_gate"] != r["gate_bound"]),
                                      "disagreements": [{"key": r["key"], "saved": r["reference_gate"], "rescanned": r["gate_bound"]}
                                                        for r in ok[s] if r.get("reference_gate") is not None and r["reference_gate"] != r["gate_bound"]][:30]}
                                  for s in SETS}
    # FK: injection false-kill rate per mode
    res["injections"] = {"n": len(inj), "per_mode": {}}
    for m in MODES:
        kills = [r for r in inj if r["gates"][m] == "FAIL"]
        res["injections"]["per_mode"][m] = {"n_fail": len(kills), "false_kill_rate": frac(r["gates"][m] == "FAIL" for r in inj)}
    res["injections"]["legacy_variants"] = {v: sum(1 for r in inj if (r.get("gate_by_mode") or {}).get(v) == "FAIL")
                                            for v in ("quiet_bound", "quiet_zero", "quiet_bound_hold")}
    # KR: retained kills on the adversarial set
    ref_kills = [r for r in adv if r["gates"]["bound"] == "FAIL"]
    res["adversarial"] = {"n": len(adv), "n_eb": sum(r["truth"] == "eb" for r in adv), "n_blend": sum(r["truth"] == "blend" for r in adv),
                          "n_bound_kills": len(ref_kills), "per_mode": {}}
    for m in MODES:
        res["adversarial"]["per_mode"][m] = {
            "kills_retained": sum(1 for r in ref_kills if r["gates"][m] == "FAIL"),
            "retention": frac(r["gates"][m] == "FAIL" for r in ref_kills),
            "eb_killed": sum(1 for r in adv if r["truth"] == "eb" and r["gates"][m] == "FAIL"),
            "blend_killed": sum(1 for r in adv if r["truth"] == "blend" and r["gates"][m] == "FAIL"),
            "lost_kills": [r["key"] for r in ref_kills if r["gates"][m] != "FAIL"]}
    # TIC 233007823
    res["p6_eccentric_eb"] = [{"key": r["key"], "gates": r["gates"], "reference_gate": r.get("reference_gate"),
                               "deepest_secondary_in_sap": r.get("deepest_secondary_in_sap"),
                               "p10_summary": _p10_summary(r)} for r in p6]
    # the P8 A passers, descriptive
    rej = [r for r in p8p if r["reference_gate"] == "FAIL"]
    pas = [r for r in p8p if r["reference_gate"] == "PASS"]
    res["p8_stage_a_passers"] = {"n": len(p8p), "n_rejections": len(rej), "n_passers": len(pas),
                                 "rejections_pass_per_mode": {m: sum(1 for r in rej if r["gates"][m] == "PASS") for m in MODES},
                                 "passers_fail_per_mode": {m: sum(1 for r in pas if r["gates"][m] == "FAIL") for m in MODES},
                                 "cross_tab_review_class": {}, "cross_tab_assessment": {}, "cross_tab_catalogue_match": {}}
    for r in rej:
        cls = r.get("review_class") or "unreviewed"
        row = res["p8_stage_a_passers"]["cross_tab_review_class"].setdefault(cls, {"n": 0, **{m: 0 for m in MODES}})
        row["n"] += 1
        for m in MODES:
            row[m] += int(r["gates"][m] == "PASS")
        asmt = ((r.get("review") or {}).get("assessment") or "unreviewed")[:60]
        row = res["p8_stage_a_passers"]["cross_tab_assessment"].setdefault(asmt, {"n": 0, **{m: 0 for m in MODES}})
        row["n"] += 1
        for m in MODES:
            row[m] += int(r["gates"][m] == "PASS")
        cm = "catalogue_match" if (r.get("review") or {}).get("catalogue_match") else "no_catalogue_match"
        row = res["p8_stage_a_passers"]["cross_tab_catalogue_match"].setdefault(cm, {"n": 0, **{m: 0 for m in MODES}})
        row["n"] += 1
        for m in MODES:
            row[m] += int(r["gates"][m] == "PASS")
    res["p8_stage_a_passers"]["note"] = ("counts are rejections that would PASS under each mode; the review class is a keyword "
                                         "class of the free-text EB screen review (modulation / eclipse_like / systematics / other), descriptive only")
    # the development hosts, descriptive
    res["development_hosts"] = [{"key": r["key"], "tic_id": r["tic_id"], "gates": r["gates"], "reference_gate": r.get("reference_gate"),
                                 "p10_summary": _p10_summary(r)} for r in dev]
    # the decision
    p6_fail = {m: all(r["gates"][m] == "FAIL" for r in p6) and bool(p6) for m in MODES}
    table = []
    for m in MODES:
        kr = res["adversarial"]["per_mode"][m]["retention"]
        fk = res["injections"]["per_mode"][m]["false_kill_rate"]
        table.append({"mode": m, "false_kill_rate": fk, "n_false_kills": res["injections"]["per_mode"][m]["n_fail"],
                      "kill_retention": kr, "kills_retained": res["adversarial"]["per_mode"][m]["kills_retained"],
                      "tic233007823_fail": p6_fail[m],
                      "eligible": (kr is not None and kr >= Y_RETAIN and p6_fail[m] and fk is not None)})
    elig = [t for t in table if t["eligible"]]
    chosen = sorted(elig, key=lambda t: (t["false_kill_rate"], SIMPLER[t["mode"]]))[0]["mode"] if elig else None
    res["decision"] = {"rule": ("lowest injection false-kill rate among modes retaining >= 90% of the p8.0 bound kills on the "
                                "adversarial EB and blend set and failing TIC 233007823; an exact tie in FK goes to the simpler mode "
                                "(bound < empirical_bound < recurrent_bound < recurrent_bound_corr)"),
                       "table": table, "chosen": chosen,
                       "complete": all(res["n"][s]["error"] == 0 for s in SETS) and len(inj) > 0 and len(adv) > 0 and len(p6) > 0}
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "secondary_modes.json").write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8")
    (RES / "secondary_modes.md").write_text(markdown(res), encoding="utf-8")
    return res


def _p10_summary(r: dict) -> dict:
    p = r.get("p10") or {}
    if not p.get("applicable"):
        return {"applicable": False}
    rec = p.get("recurrence") or {}
    return {"empirical_scatter_ppt": (p.get("empirical") or {}).get("scatter_ppt"), "sap_sigma": p.get("sap_sigma"),
            "n_covered_events": rec.get("n_covered_events"), "n_events_ge_sigma": rec.get("n_events_ge_sigma"),
            "per_event_recurs": rec.get("per_event_recurs"), "group_recurs": rec.get("group_recurs"), "recurs": rec.get("recurs"),
            "present_both": p.get("present_both")}


def markdown(res: dict) -> str:
    a = []
    a.append("# Part 2a: the secondary-scan modes, measured [M]\n")
    a.append(f"Generated {res['generated_utc']}. Records: " + ", ".join(f"{s} {res['n'][s]['ok']} OK / {res['n'][s]['error']} error" for s in SETS) + ".\n")
    ra = res["reference_agreement"]
    a.append("Rescanned `bound` gate against the saved p8.0 decision: " + "; ".join(f"{s} {ra[s]['n_disagree']} of {ra[s]['n_with_reference']} disagree" for s in SETS) + ".\n")
    a.append("| mode | injection false kills (FK) | adversarial kills retained (KR) | EBs killed | blends killed | TIC 233007823 | eligible |")
    a.append("|---|---:|---:|---:|---:|---|---|")
    n_inj, nk = res["injections"]["n"], res["adversarial"]["n_bound_kills"]
    for t in res["decision"]["table"]:
        pm = res["adversarial"]["per_mode"][t["mode"]]
        a.append(f"| {t['mode']} | {t['n_false_kills']}/{n_inj} ({100 * (t['false_kill_rate'] or 0):.1f}%) | "
                 f"{t['kills_retained']}/{nk} ({100 * (t['kill_retention'] or 0):.0f}%) | {pm['eb_killed']}/{res['adversarial']['n_eb']} | "
                 f"{pm['blend_killed']}/{res['adversarial']['n_blend']} | {'FAIL' if t['tic233007823_fail'] else 'PASS'} | {'yes' if t['eligible'] else 'no'} |")
    a.append("")
    a.append(f"**Decision (rule: {res['decision']['rule']}): `{res['decision']['chosen']}`.**\n")
    p8 = res["p8_stage_a_passers"]
    a.append(f"P8 Stage A passers (descriptive, never in the rule): {p8['n_rejections']} p8.0 rejections would PASS under "
             + ", ".join(f"{m}: {p8['rejections_pass_per_mode'][m]}" for m in MODES) + f"; the {p8['n_passers']} p8.0 passers would FAIL under "
             + ", ".join(f"{m}: {p8['passers_fail_per_mode'][m]}" for m in MODES) + ".\n")
    a.append("| review class of the rejection | n | pass under bound | empirical_bound | recurrent_bound | recurrent_bound_corr |")
    a.append("|---|---:|---:|---:|---:|---:|")
    for cls, row in sorted(p8["cross_tab_review_class"].items()):
        a.append(f"| {cls} | {row['n']} | {row['bound']} | {row['empirical_bound']} | {row['recurrent_bound']} | {row['recurrent_bound_corr']} |")
    a.append("")
    a.append("| P6 / development record | reference gate | bound | empirical_bound | recurrent_bound | recurrent_bound_corr | scatter (ppt) | SAP sigma | recurs |")
    a.append("|---|---|---|---|---|---|---:|---:|---|")
    for r in res["p6_eccentric_eb"] + res["development_hosts"]:
        s = r["p10_summary"]
        a.append(f"| {r['key']} | {r.get('reference_gate')} | " + " | ".join(r["gates"][m] for m in MODES) +
                 f" | {s.get('empirical_scatter_ppt')} | {s.get('sap_sigma')} | {s.get('recurs')} |")
    return "\n".join(a) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--sets", default=",".join(SETS)); r.add_argument("--slices", type=int, default=16)
    r.add_argument("--force", action="store_true"); r.add_argument("--limit", type=int)
    s = sub.add_parser("slice"); s.add_argument("--sets", required=True); s.add_argument("--index", type=int, required=True)
    s.add_argument("--nslices", type=int, required=True); s.add_argument("--force", action="store_true"); s.add_argument("--limit", type=int)
    j = sub.add_parser("jobs"); j.add_argument("--sets", default=",".join(SETS))
    sub.add_parser("tables")
    args = ap.parse_args(argv)
    if args.cmd == "run":
        run(args.sets.split(","), args.slices, args.force, args.limit)
        print(json.dumps(tables()["decision"], indent=1))
    elif args.cmd == "slice":
        run_slice(args.sets.split(","), args.index, args.nslices, args.force, args.limit)
    elif args.cmd == "jobs":
        for s_ in args.sets.split(","):
            js = JOBS[s_]()
            print(s_, len(js), [j["key"] for j in js[:3]])
    elif args.cmd == "tables":
        res = tables()
        print((RES / "secondary_modes.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
