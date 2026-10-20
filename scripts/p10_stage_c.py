"""Prompt 10 Part 2c: Stage C, measured (HANDOFF_P10.md section 0.4).

    sde        (i) the installed SDE and SDE_robust side by side on every saved C spectrum (the
               19 P8 and 18 P9 records, plus every prompt-10 spectrum with raw arrays), the
               concentration statistic, how many trigger the fallback, and which decisions the
               fallback would change
    repro-hip  reproduce HIP 97166 b's C run from the P9 locked inputs with the raw chi2 / SR /
               power_raw arrays saved, then diagnose the extreme trial near 0.594628 d
    peaks      (ii) the significant_peak rule evaluated statically on the 37 saved spectra:
               which records decide without a residual run and which need one
    run        (ii) / (iii) run Stage C for named records in a prompt-10 workspace under a
               rule set (p8.0 for the strongest rule alone; p10.0-partial with
               significant_peak and the fallback for both decisions in one run) at native or
               600-s cadence; TLS at 8 threads, one job at a time
    cadence    (iii) the 600-s reruns of the 37 saved records (or a seeded 12) under p8.0, and
               the agreement table against the native decisions
    injc       (iii) the seeded injection-C sample (20 per snr_expected bin, or 10) run under
               p10.0-partial so the strongest rule (a) and significant_peak (b) come from one
               TLS run each
    adv        the 18 adversarial eclipsing binaries under the same rules at 600 s
    tables     every table and the decisions for the handoff

Workspaces: data/survey/p10/stage_c/<set>/<key>/ (survivors.csv, candidates.csv, prep/, tls/,
stageC/); nothing under data/survey/p8, data/survey/p9 or p9 is written.  Tables:
p10/results/stage_c_*.json and stage_c.md.

Nothing here submits anything anywhere.  The pipeline finds candidates.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
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
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

P8 = REPO / "data" / "survey" / "p8"
P9 = REPO / "p9"
LC_ROOT = REPO / "data" / "survey" / "audit_lc"
OUT = REPO / "data" / "survey" / "p10" / "stage_c"
RES = REPO / "p10" / "results"
LOGS = REPO / "p10" / "logs"
SEED = 20260908
HIP_KEY, HIP_TIC = "tic237222864_P10.2888", 237222864
TOI1470C_KEY, TOI1470_TIC = "tic284441182_P18.0890", 284441182
INJ_BINS = {"7_12": (7.0, 12.0), "12_20": (12.0, 20.0), "20_50": (20.0, 50.0)}
CAND_COLS = ["tic_id", "planet_num", "search", "period_days", "epoch_btjd", "duration_days", "depth_ppt", "snr",
             "n_transits", "stitch_snr", "stitch_n_transits", "stitch_epoch_consistent", "stitch_period_days",
             "stitch_depth_ppt", "verdict", "n_flags_high", "n_flags_medium", "flags_high", "n_units", "baseline_days",
             "n_cadences", "tmag", "teff_k", "radius_rsun", "mass_msun", "ra_deg", "dec_deg", "rotation_peak_period_days",
             "rotation_semi_amplitude_ppt", "rotation_scatter_ppt", "prep_mad_ppt", "budget_stop", "pregate_snr",
             "pregate_transits", "pregate_epoch", "passes_pregate"]

from tesshunter import audit_rules as R                      # noqa: E402
from tesshunter import stage_c as SC                         # noqa: E402


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def kkey(tic, period):
    return f"tic{int(tic)}_P{float(period):.4f}"


# ─────────────────────────────────────────────────────────────────────────────
# the 37 saved C records
# ─────────────────────────────────────────────────────────────────────────────
def saved_c_records() -> list[dict]:
    out = []
    for p in sorted((P8 / "stageC").glob("tic*.json")):
        c = read(p)
        out.append({"set": "p8", "key": c["key"], "tic_id": int(c["tic_id"]), "period": float(c["survey_period"]),
                    "depth_ppt": float(c["survey_depth_ppt"]), "decision": c.get("decision"), "record": str(p.relative_to(REPO)),
                    "spectrum": str((P8 / "tls" / f"{c['key']}_spectrum.npz").relative_to(REPO)), "source_root": str(P8),
                    "lc_root": str(LC_ROOT), "stellar": "cache", "truth": "P8 candidate (D verdict recorded)" if c.get("decision") == "PASS" else "P8 candidate",
                    "blind": c.get("blind"), "peaks": c.get("peaks")})
    for tic in read(P9 / "manifests" / "final_ids.json"):
        root = P9 / "results" / "blind" / f"tic{tic}"
        for p in sorted((root / "stageC").glob("tic*.json")):
            c = read(p)
            out.append({"set": "p9", "key": c["key"], "tic_id": int(tic), "period": float(c["survey_period"]),
                        "depth_ppt": float(c["survey_depth_ppt"]), "decision": c.get("decision"), "record": str(p.relative_to(REPO)),
                        "spectrum": str((root / "tls" / f"{c['key']}_spectrum.npz").relative_to(REPO)), "source_root": str(root),
                        "lc_root": str(P9 / "inputs" / "raw"), "stellar": "p9", "truth": "P9 host", "blind": c.get("blind"), "peaks": c.get("peaks")})
    return out


def p9_labels() -> dict:
    """Blind key -> the P9 post-lock truth association and label (from the scored signals and
    the candidate ledger), for the withdrawal check and the tables."""
    labels = {}
    led = P9 / "results" / "candidate_ledger.csv"
    if led.exists():
        for r in csv.DictReader(led.open(newline="", encoding="utf-8")):
            k = r.get("key") or r.get("candidate_key") or ""
            if k:
                labels[k] = {c: r.get(c) for c in r if c != "key"}
    return labels


# ─────────────────────────────────────────────────────────────────────────────
# (i) SDE and SDE_robust on the saved spectra
# ─────────────────────────────────────────────────────────────────────────────
def cmd_sde() -> dict:
    labels = p9_labels()
    rows = []
    for rec in saved_c_records():
        z = np.load(REPO / rec["spectrum"])
        p, w = z["periods"], z["power"]
        i = int(np.nanargmax(w))
        fb = SC.sde_fallback(w, i)
        row = {k: rec[k] for k in ("set", "key", "tic_id", "period", "decision", "truth")}
        row.update({"n_trials": int(len(w)), "installed_SDE": float(w[i]), "strongest_period": float(p[i]),
                    "concentration": fb["concentration"], "concentration_period": float(p[fb["concentration_index"]]) if fb["concentration_index"] is not None else None,
                    "concentration_value": fb.get("concentration_value"), "sde_robust_at_strongest": fb["sde_robust_at_peak"],
                    "sde_robust_max": fb["sde_robust_max"], "triggered": fb["triggered"], "passes_on_robust": fb["passes_on_robust"],
                    "has_power_raw": "power_raw" in z.files, "spectrum_used": "power (installed SDE spectrum; power_raw not saved by p8.0)"})
        # what the fallback would change: only a record whose installed SDE < 9 at the strongest peak,
        # whose strongest peak is the survey period (or a depth-consistent 2:1 alias), can flip
        blind = rec.get("blind") or {}
        same = bool((blind.get("match") or {}).get("same_period_1pct"))
        row["would_flip_to_pass"] = bool(fb["triggered"] and fb["passes_on_robust"] and float(w[i]) < R.C_SDE and same)
        row["label"] = labels.get(rec["key"])
        rows.append(row)
    n_trig = sum(r["triggered"] for r in rows)
    flips = [r for r in rows if r["would_flip_to_pass"]]
    res = {"generated_utc": utc(), "n_spectra": len(rows), "n_triggered": n_trig, "trigger": R.C_CONCENTRATION_TRIGGER,
           "rows": rows, "flips_to_pass": [r["key"] for r in flips],
           "rule": "threshold stays 9 on the installed SDE; SDE_robust consulted only when one ordinate carries > 0.5 of the "
                   "centred variance; then PASS if SDE_robust >= 9 at the installed strongest peak",
           "withdrawal": "the fallback is withdrawn if any P8 or P9 negative control or adversarial-EB C decision flips FAIL to PASS"}
    write(RES / "stage_c_sde.json", res)
    return res


# ─────────────────────────────────────────────────────────────────────────────
# workspaces and C runs
# ─────────────────────────────────────────────────────────────────────────────
def workspace(set_name: str, key: str, source_root: Path, tic: int) -> Path:
    """A prompt-10 root for one record: the source root's survivors.csv and candidates.csv rows
    of this star (the driver reads its ephemeris and depth from them), nothing else."""
    ws = OUT / set_name / key
    ws.mkdir(parents=True, exist_ok=True)
    for name in ("survivors.csv", "candidates.csv"):
        src = Path(source_root) / name
        dst = ws / name
        if dst.exists():
            continue
        if src.exists():
            with src.open(newline="", encoding="utf-8") as fh:
                rd = csv.DictReader(fh)
                rows = [r for r in rd if int(r["tic_id"]) == int(tic)]
                cols = rd.fieldnames
            with dst.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=cols)
                w.writeheader()
                for r in rows:
                    w.writerow(r)
    for sub in ("prep", "tls", "stageC", "stageA", "events"):
        (ws / sub).mkdir(exist_ok=True)
    return ws


def configure(ws: Path, lc_root: Path, stellar: str, rules, cadence: str, injection: dict | None = None):
    import audit_p5 as A
    import revet_p6 as V
    from tesshunter.survey import get_config
    cfg = get_config("survey_p8") if cadence == "native" else get_config("survey_p8", bin_minutes=10.0)
    A.set_input_config(cfg)
    if hasattr(A, "_load_products_uninjected"):
        A.load_products = A._load_products_uninjected
    V.set_population(out_root=ws, survivors_csv=ws / "survivors.csv", candidates_csv=ws / "candidates.csv",
                     packets_dir=ws / "empty_packets")
    (ws / "empty_packets").mkdir(exist_ok=True)
    V.LC_ROOT = Path(lc_root)
    A.set_roots(ws, Path(lc_root))
    V.set_rules(rules)
    if not hasattr(A, "_stellar_from_cache_before_p10"):
        A._stellar_from_cache_before_p10 = A.stellar_from_cache
    A.stellar_from_cache = A._stellar_from_cache_before_p10
    if stellar == "p9":
        A.stellar_from_cache = lambda t: read(P9 / "inputs" / "stellar" / f"tic{int(t)}.json")
    if injection is not None:
        import p8_completeness as C
        C.install_injection(injection)
    return A, V, cfg


def rules_for(name: str):
    if name == "p8.0":
        return R.P8_RULES
    if name == "p10c":
        return R.P10_RULES.with_options(stagec_peak_rule="significant_peak", stagec_sde_robust_fallback=True,
                                        duration_floor_cadence=True)
    return R.NAMED_RULES[name]


def run_c(set_name: str, rec: dict, rules_name: str, cadence: str, threads: int = 8, force: bool = False,
          injection: dict | None = None, tag: str | None = None) -> dict:
    """Stage C on one record in a prompt-10 workspace.  ``rec`` carries key, tic_id, period,
    depth_ppt, source_root, lc_root, stellar."""
    tag = tag or f"{rules_name}_{cadence}"
    ws = workspace(f"{set_name}/{tag}", rec.get("workspace_id", rec["key"]), Path(rec["source_root"]), rec["tic_id"])
    A, V, cfg = configure(ws, Path(rec["lc_root"]), rec["stellar"], rules_for(rules_name), cadence, injection)
    path = ws / "stageC" / f"{rec['key']}.json"
    if path.exists() and not force:
        cached = read(path)
        if cached.get("decision") in ("PASS", "FAIL"):
            meta = cached.get("p10") or {}
            if (cached.get("rules_version") != rules_for(rules_name).version or meta.get("input_config") != A.input_config()
                    or meta.get("cadence") != cadence or meta.get("rules") != rules_name
                    or cached.get("survey_period") != rec["period"] or cached.get("survey_depth_ppt") != rec["depth_ppt"]):
                raise RuntimeError("Existing C record has different inputs; use a new reviewed workspace")
            if rules_name != "p8.0" and cached.get("stagec_implementation") != SC.IMPLEMENTATION:
                raise RuntimeError("Inherited experimental C decision must be preserved; use a new corrected workspace")
            return cached  # Reading a completed run must never replace its measured wall.
    job = {"tic_id": rec["tic_id"], "period": rec["period"], "depth_ppt": rec["depth_ppt"], "rank": 0}
    t0 = time.perf_counter()
    r = V.stagec_one(job, threads=threads, oversampling=3, force=force)
    # Preserve the driver-added input_config and normalized fields in the saved
    # record; the object returned by stagec_one predates audit_p5.jdump's copy.
    r = A.jload(path)
    r["p10"] = {"set": set_name, "tag": tag, "rules": rules_name, "cadence": cadence, "workspace": str(ws.relative_to(REPO)),
                "input_config": A.input_config(), "wall_s": round(time.perf_counter() - t0, 1), "generated_utc": utc()}
    r["p10"].update({k: rec[k] for k in ("job_id", "candidate_id", "bin", "snr_expected") if k in rec})
    write(path, r)
    return r


def cmd_run(set_name: str, keys: list[str], rules_name: str, cadence: str, threads: int, force: bool) -> None:
    recs = {r["key"]: r for r in saved_c_records() if r["set"] == set_name} if set_name in ("p8", "p9") else {}
    if set_name == "adv":
        recs = {r["key"]: r for r in adv_records()}
    for k in keys:
        rec = recs[k]
        r = run_c(set_name, rec, rules_name, cadence, threads, force)
        print(set_name, k, rules_name, cadence, r.get("decision"), r.get("decision_strongest"), r["p10"]["wall_s"], "s",
              str(r.get("reason", ""))[:160], flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# HIP 97166 b: reproduce with the arrays and diagnose the extreme trial
# ─────────────────────────────────────────────────────────────────────────────
def cmd_repro_hip(threads: int = 8, force: bool = False) -> dict:
    rec = next(r for r in saved_c_records() if r["key"] == HIP_KEY)
    r = run_c("p9", rec, "p8.0", "native", threads, force, tag="repro_hip")
    return diagnose_hip(r)


def diagnose_hip(c_record: dict | None = None) -> dict:
    ws = OUT / "p9" / "repro_hip" / HIP_KEY
    z = np.load(ws / "tls" / f"{HIP_KEY}_spectrum.npz")
    p, w = z["periods"], z["power"]
    out = {"generated_utc": utc(), "workspace": str(ws.relative_to(REPO)), "n_trials": int(len(p)), "arrays_saved": z.files,
           "c_decision": (c_record or {}).get("decision"), "installed_SDE": (c_record or {}).get("blind", {}).get("SDE")}
    saved = np.load(REPO / "p9" / "results" / "blind" / f"tic{HIP_TIC}" / "tls" / f"{HIP_KEY}_spectrum.npz")
    out["reproduction"] = {"n_trials_saved": int(len(saved["periods"])), "same_grid": bool(len(saved["periods"]) == len(p) and np.allclose(saved["periods"], p)),
                           "max_abs_power_difference": float(np.nanmax(np.abs(saved["power"] - w))) if len(saved["periods"]) == len(p) else None}
    i_min = int(np.nanargmin(w))
    conc = SC.concentration(w)
    out["extreme_trial"] = {"index": i_min, "period": float(p[i_min]), "power": float(w[i_min]), "concentration_fraction": conc["fraction"],
                            "saved_p9_extreme_period": 0.594628, "saved_p9_extreme_power": float(np.nanmin(saved["power"]))}
    if "chi2" in z.files:
        chi2, SR, praw = z["chi2"], z["SR"], z["power_raw"]
        good = np.isfinite(chi2)
        med = float(np.median(chi2[good]))
        out["extreme_trial"].update({"chi2": float(chi2[i_min]), "chi2_min": float(np.nanmin(chi2)), "chi2_median": med,
                                     "chi2_excess_over_median_fraction": float(chi2[i_min] / med - 1.0), "SR": float(SR[i_min]),
                                     "SR_mean": float(np.nanmean(SR)), "SR_std": float(np.nanstd(SR)), "power_raw": float(praw[i_min]),
                                     "n_nonfinite_chi2": int((~good).sum()), "chi2_finite_max": float(np.nanmax(chi2))})
        # the flat model's chi-square on the same series, for scale
        zl = np.load(ws / "tls" / f"{HIP_KEY}_lc.npz")
        tb, fb, eb = zl["time"], zl["flux"], zl["flux_err"]
        chi2_flat = float(np.sum(((fb - 1.0) / eb) ** 2))
        out["extreme_trial"]["chi2_flat_model"] = chi2_flat
        out["extreme_trial"]["chi2_over_flat"] = float(chi2[i_min] / chi2_flat)
        # which points: fold at the extreme period and find the box (over the TLS duration range) whose
        # in-box residual sum is most extreme in either direction
        P = float(p[i_min])
        ph = ((tb - tb.min()) / P) % 1.0
        best = None
        for dur in [0.02 * 1.1 ** k for k in range(int(np.log(0.5 / 0.02) / np.log(1.1)) + 1)]:
            if dur > P / 2:
                break
            width = dur / P
            for centre in np.arange(0, 1, max(width / 4, 1e-3)):
                d = np.abs(((ph - centre + 0.5) % 1.0) - 0.5)
                inb = d < width / 2
                if inb.sum() < 3:
                    continue
                s = float(np.sum((fb[inb] - 1.0) / eb[inb] ** 2))
                q = float(np.sum(((fb[inb] - 1.0) / eb[inb]) ** 2))
                for name, val in (("deepest", -s), ("brightest", s), ("largest_chi2", q)):
                    if best is None or val > best.get(name, (-np.inf,))[0]:
                        best = best or {}
                        best[name] = (val, centre, dur, int(inb.sum()), np.flatnonzero(inb)[:12].tolist())
        if best:
            out["extreme_trial"]["boxes"] = {name: {"statistic": v[0], "phase": v[1], "duration_days": v[2], "n_in": v[3],
                                                    "first_indices": v[4], "times": tb[v[4]].tolist(), "fluxes": fb[v[4]].tolist(),
                                                    "errors": eb[v[4]].tolist()} for name, v in best.items()}
    write(RES / "stage_c_hip97166.json", out)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# (ii) the significant_peak rule statically on the saved spectra
# ─────────────────────────────────────────────────────────────────────────────
def cmd_peaks() -> dict:
    rows = []
    for rec in saved_c_records():
        z = np.load(REPO / rec["spectrum"])
        p, w = z["periods"], z["power"]
        b = rec["blind"] or {}
        local = SC.local_peak(p, w, rec["period"])
        strongest = {"period": b.get("period"), "SDE": b.get("SDE")}
        m = b.get("match") or {}
        adc = None
        if m.get("alias_1pct") and m.get("closest_alias") in ("2:1", "1:2") and not m.get("same_period_1pct"):
            import revet_p6 as V
            src = read(REPO / rec["record"])
            adc = (src.get("alias_depth_consistency") or {}).get("consistent")
        # the strongest peak's own transit count is known; other stronger peaks need a narrow run
        transits = {f"{float(b['period']):.6f}": b.get("distinct_transit_count")} if b.get("period") else {}
        sp = SC.significant_peak(rec["period"], strongest, rec["peaks"] or [], local, stronger_transits=transits,
                                 alias_depths_consistent=adc)
        rows.append({k: rec[k] for k in ("set", "key", "tic_id", "period", "decision", "truth")} | {
            "installed_SDE": strongest["SDE"], "strongest_period": strongest["period"], "strongest_transits": b.get("distinct_transit_count"),
            "local": local, "static_decision": sp["decision"], "static_reason": sp["reason"],
            "stronger": sp["stronger"], "needs_residual": sp["decision"] == "NEEDS_RESIDUAL"})
    res = {"generated_utc": utc(), "n": len(rows), "rows": rows,
           "counts": {d: sum(1 for r in rows if r["static_decision"] == d) for d in ("PASS", "FAIL", "NEEDS_RESIDUAL")},
           "changes_static": [r["key"] for r in rows if r["static_decision"] in ("PASS", "FAIL") and r["static_decision"] != r["decision"]]}
    write(RES / "stage_c_peaks_static.json", res)
    return res


# ─────────────────────────────────────────────────────────────────────────────
# (iii) the 600-s cadence decision and the injection-C sample
# ─────────────────────────────────────────────────────────────────────────────
def cadence_sample(records: list[dict], n: int = 12) -> list[dict]:
    rng = np.random.default_rng(SEED)
    passes = sorted([r for r in records if r["decision"] == "PASS"], key=lambda r: r["key"])
    fails = sorted([r for r in records if r["decision"] == "FAIL"], key=lambda r: r["key"])
    pick = list(rng.choice(len(passes), size=min(n // 2, len(passes)), replace=False)) + [0] * 0
    chosen = [passes[i] for i in sorted(pick)]
    pick_f = rng.choice(len(fails), size=min(n // 2, len(fails)), replace=False)
    chosen += [fails[i] for i in sorted(pick_f)]
    return chosen


def cmd_cadence(threads: int, limit_to_seeded: bool, keys: list[str] | None, force: bool) -> None:
    recs = saved_c_records()
    if keys:
        recs = [r for r in recs if r["key"] in keys]
    elif limit_to_seeded:
        recs = cadence_sample(recs, 12)
    for rec in recs:
        r = run_c(rec["set"], rec, "p8.0", "600s", threads, force, tag="cadence_600s")
        print("cadence", rec["set"], rec["key"], "native", rec["decision"], "600s", r.get("decision"), r["p10"]["wall_s"], "s", flush=True)


def cadence_table() -> dict:
    rows = []
    for rec in saved_c_records():
        p = OUT / rec["set"] / "cadence_600s" / rec["key"] / "stageC" / f"{rec['key']}.json"
        if not p.exists():
            continue
        r = read(p)
        rows.append({"set": rec["set"], "key": rec["key"], "native": rec["decision"], "s600": r.get("decision"),
                     "agree": rec["decision"] == r.get("decision"), "native_SDE": (rec["blind"] or {}).get("SDE"),
                     "s600_SDE": (r.get("blind") or {}).get("SDE"), "native_strongest": (rec["blind"] or {}).get("period"),
                     "s600_strongest": (r.get("blind") or {}).get("period"), "s600_reason": str(r.get("reason", ""))[:200],
                     "wall_s": r["p10"]["wall_s"], "native_wall_s": (read(REPO / rec["record"]).get("timing_s") or {}).get("tls_blind")})
    n = len(rows)
    agree = sum(1 for r in rows if r["agree"])
    need = 35 if n >= 37 else 11
    res = {"generated_utc": utc(), "n": n, "agree": agree, "disagree": [r for r in rows if not r["agree"]], "rows": rows,
           "rule": f"at least {need} of {n if n in (37, 12) else 'N'} agree and every disagreement explained -> injection C at 600 s; else native with 30",
           "decision_600s": bool(n and agree >= (35 if n >= 37 else 11))}
    write(RES / "stage_c_cadence.json", res)
    return res


def injection_sample(n_per_bin: int = 20) -> list[dict]:
    """Recovered injections that passed the secondary scan (p8.0), 20 per snr_expected bin, seeded."""
    rows = list(csv.DictReader((P8 / "injection_outcomes_p8.csv").open(newline="", encoding="utf-8")))
    ok = [r for r in rows if r["status"] == "recovered" and r["through_funnel"] == "True"]
    rng = np.random.default_rng(SEED)
    out = []
    for name, (lo, hi) in INJ_BINS.items():
        pool = sorted([r for r in ok if lo <= float(r["snr_expected"]) < hi], key=lambda r: r["job_id"])
        pick = rng.choice(len(pool), size=min(n_per_bin, len(pool)), replace=False)
        for i in sorted(pick):
            out.append(dict(pool[i], bin=name))
    return out


def injection_record(job_row: dict) -> tuple[dict, dict]:
    """The C-run record and the injection model of one sampled injection (from its funnel root)."""
    import p8_completeness as C
    from analyze_completeness import _load_results
    recs = _load_results(C.INJ_RUN)
    jobs = {j["job_id"]: j for j in C.recovered_jobs(recs)}
    j = jobs[job_row["job_id"]]
    root = C.INJ_ROOT / j["job_id"]
    rec = {"key": kkey(j["tic_id"], j["period_days"]), "tic_id": int(j["tic_id"]), "period": float(j["period_days"]),
           "depth_ppt": float(j["depth_ppt"]), "source_root": str(root), "lc_root": str(LC_ROOT), "stellar": "cache",
           "job_id": j["job_id"], "snr_expected": float(job_row["snr_expected"]), "bin": job_row["bin"]}
    return rec, j


def cmd_injc(threads: int, cadence: str, n_per_bin: int, force: bool, limit: int | None) -> None:
    frozen = read(RES / "stage_c_injection_sample.json")
    if frozen["seed"] != SEED or frozen["cadence"] != cadence or frozen["n_per_bin"] != n_per_bin:
        raise RuntimeError("Use the frozen injection-C sample and cadence; do not redraw it")
    sample = frozen["jobs"]
    for i, row in enumerate(sample[:limit] if limit else sample):
        rec, j = injection_record(row)
        r = run_c("inj", rec, "p10c", cadence, threads, force, injection=j, tag=f"injc_corrected_{cadence}")
        print(f"injc [{i + 1}/{len(sample)}] {rec['job_id']} bin {rec['bin']} (a) {r.get('decision_strongest')} (b) {r.get('decision')} "
              f"{r['p10']['wall_s']} s | {str(r.get('reason', ''))[:120]}", flush=True)


def adv_records() -> list[dict]:
    """All audited survey candidates; catalogue values remain audit-only labels."""
    import hashlib
    inventory = read(RES / "stage_c_adversarial_input_inventory.json")
    if inventory["n_hosts"] != 18 or inventory["n_survey_candidates"] != 41 or not all(inventory["checks"].values()):
        raise RuntimeError("The complete audited adversarial candidate inventory is required")
    out = []
    for row in inventory["rows"]:
        source = REPO / row["source"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != row["source_sha256"]:
            raise RuntimeError("Adversarial search input changed: " + row["candidate_id"])
        s = row["survey"]
        out.append({"key": row["key"], "candidate_id": row["candidate_id"], "workspace_id": row["candidate_id"],
                    "tic_id": row["tic_id"], "period": s["period_days"], "depth_ppt": s["depth_ppt"],
                    "source_root": str(OUT / "adv_survey_tables" / row["candidate_id"]),
                    "lc_root": str(LC_ROOT), "stellar": "cache", "survey": s, "source": row["source"],
                    "name": row["name"]})
    return out


def adv_tables():
    """A separate input root per original survey candidate, including rounded-key collisions."""
    recs = adv_records()
    import io
    for r in recs:
        data = read(REPO / r["source"])
        candidate = next(p for p in data["planets"] if p["planet_num"] == r["survey"]["planet_num"])
        if any(candidate[k] != v for k, v in r["survey"].items()):
            raise RuntimeError("Survey candidate differs from audited input")
        row = {k: candidate[k] for k in CAND_COLS if k in candidate}
        row.update(tic_id=r["tic_id"], stitch_snr=candidate.get("stitch_snr", candidate["snr"]),
                   stitch_n_transits=candidate.get("stitch_n_transits", candidate.get("n_transits", 0)))
        text = io.StringIO(newline=""); writer = csv.DictWriter(text, fieldnames=CAND_COLS)
        writer.writeheader(); writer.writerow(row)
        root = Path(r["source_root"]); root.mkdir(parents=True, exist_ok=True)
        for name in ("survivors.csv", "candidates.csv"):
            path = root / name; content = text.getvalue().encode("utf-8")
            if path.exists():
                if path.read_bytes() != content:
                    raise RuntimeError("Existing adversarial C input differs; preserve and review")
            else:
                with path.open("xb") as stream:
                    stream.write(content)
    return recs


def cmd_adv(threads: int, cadence: str, force: bool, limit: int | None) -> None:
    recs = adv_tables()
    for rec in (recs[:limit] if limit else recs):
        r = run_c("adv", rec, "p10c", cadence, threads, force, tag=f"adv_corrected_{cadence}")
        print("adv", rec["key"], rec["name"], "(a)", r.get("decision_strongest"), "(b)", r.get("decision"), r["p10"]["wall_s"], "s",
              str(r.get("reason", ""))[:140], flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# tables
# ─────────────────────────────────────────────────────────────────────────────
def collect(set_name: str, tag: str) -> list[dict]:
    out = []
    for p in sorted((OUT / set_name / tag).glob("*/stageC/*.json")):
        out.append(read(p))
    return out


def cmd_tables() -> dict:
    res = {"generated_utc": utc()}
    if (RES / "stage_c_sde.json").exists():
        res["sde"] = read(RES / "stage_c_sde.json")
    if (RES / "stage_c_hip97166.json").exists():
        res["hip97166"] = read(RES / "stage_c_hip97166.json")
    if (RES / "stage_c_peaks_static.json").exists():
        res["peaks_static"] = read(RES / "stage_c_peaks_static.json")
    res["cadence"] = cadence_table()
    # significant_peak runs on the saved records
    runs = {"p8": collect("p8", "p10c_native") + collect("p8", "p10c_600s"), "p9": collect("p9", "p10c_native") + collect("p9", "p10c_600s"),
            "adv": collect("adv", "adv_600s") + collect("adv", "adv_native")}
    res["significant_peak_runs"] = {s: [{"key": r["key"], "cadence": r["p10"]["cadence"], "strongest_rule": r.get("decision_strongest"),
                                         "significant_peak": r.get("decision"), "reason": str(r.get("reason", ""))[:200],
                                         "robust_fallback": bool(r.get("strong_via_robust")), "wall_s": r["p10"]["wall_s"]} for r in rs]
                                    for s, rs in runs.items()}
    inj = collect("inj", "injc_600s") + collect("inj", "injc_native")
    by_bin = {}
    for r in inj:
        b = r["p10"].get("bin")
        d = by_bin.setdefault(b, {"n": 0, "a_pass": 0, "b_pass": 0})
        d["n"] += 1
        d["a_pass"] += int(r.get("decision_strongest") == "PASS")
        d["b_pass"] += int(r.get("decision") == "PASS")
    res["injection_c"] = {"n": len(inj), "per_bin": by_bin,
                          "rows": [{"job_id": r["p10"].get("job_id"), "bin": r["p10"].get("bin"), "snr_expected": r["p10"].get("snr_expected"),
                                    "a": r.get("decision_strongest"), "b": r.get("decision"), "SDE": (r.get("blind") or {}).get("SDE"),
                                    "wall_s": r["p10"]["wall_s"]} for r in inj]}
    write(RES / "stage_c_tables.json", res)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sde")
    rh = sub.add_parser("repro-hip"); rh.add_argument("--threads", type=int, default=8); rh.add_argument("--force", action="store_true")
    sub.add_parser("diagnose-hip")
    sub.add_parser("peaks")
    rn = sub.add_parser("run"); rn.add_argument("--set", required=True, choices=["p8", "p9", "adv"]); rn.add_argument("--keys", required=True)
    rn.add_argument("--rules", default="p10c"); rn.add_argument("--cadence", default="native", choices=["native", "600s"])
    rn.add_argument("--threads", type=int, default=8); rn.add_argument("--force", action="store_true")
    cd = sub.add_parser("cadence"); cd.add_argument("--threads", type=int, default=8); cd.add_argument("--seeded-12", action="store_true")
    cd.add_argument("--keys", default=None); cd.add_argument("--force", action="store_true")
    ij = sub.add_parser("injc"); ij.add_argument("--threads", type=int, default=8); ij.add_argument("--cadence", default="600s", choices=["native", "600s"])
    ij.add_argument("--per-bin", type=int, default=20); ij.add_argument("--force", action="store_true"); ij.add_argument("--limit", type=int)
    ad = sub.add_parser("adv"); ad.add_argument("--threads", type=int, default=8); ad.add_argument("--cadence", default="600s", choices=["native", "600s"])
    ad.add_argument("--force", action="store_true"); ad.add_argument("--limit", type=int)
    sub.add_parser("tables")
    args = ap.parse_args(argv)
    if args.cmd == "sde":
        r = cmd_sde(); print(json.dumps({k: r[k] for k in ("n_spectra", "n_triggered", "flips_to_pass")}, indent=1))
        for row in r["rows"]:
            print(f"{row['set']} {row['key']:<26} C {row['decision']:<4} SDE {row['installed_SDE']:7.2f} robust {row['sde_robust_at_strongest']!s:>8} "
                  f"conc {row['concentration']:.4f} trig {row['triggered']} flip {row['would_flip_to_pass']}")
    elif args.cmd == "repro-hip":
        print(json.dumps(cmd_repro_hip(args.threads, args.force)["extreme_trial"], indent=1, default=str))
    elif args.cmd == "diagnose-hip":
        print(json.dumps(diagnose_hip()["extreme_trial"], indent=1, default=str))
    elif args.cmd == "peaks":
        r = cmd_peaks(); print(json.dumps({k: r[k] for k in ("n", "counts", "changes_static")}, indent=1))
        for row in r["rows"]:
            print(f"{row['set']} {row['key']:<26} C {row['decision']:<4} static {row['static_decision']:<14} {row['static_reason'][:120]}")
    elif args.cmd == "run":
        cmd_run(args.set, args.keys.split(","), args.rules, args.cadence, args.threads, args.force)
    elif args.cmd == "cadence":
        cmd_cadence(args.threads, args.seeded_12, args.keys.split(",") if args.keys else None, args.force)
        print(json.dumps({k: v for k, v in cadence_table().items() if k in ("n", "agree", "decision_600s")}, indent=1))
    elif args.cmd == "injc":
        cmd_injc(args.threads, args.cadence, args.per_bin, args.force, args.limit)
    elif args.cmd == "adv":
        cmd_adv(args.threads, args.cadence, args.force, args.limit)
    elif args.cmd == "tables":
        r = cmd_tables(); print(json.dumps({k: r[k] for k in r if k in ("cadence", "injection_c")}, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
