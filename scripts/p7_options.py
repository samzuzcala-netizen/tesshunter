"""Prompt 7, Part B: measure each of the four new options over all 405 survivors.

Report-only.  Nothing here produces a SUBMIT / HOLD / KILL verdict for any
candidate, nothing runs a blind TLS, nothing runs the survey and nothing is
submitted anywhere.  What it produces is, per option, how many Stage A passers
and failers change status, which way, and why - counts, not verdicts.

The four options (``tesshunter.audit_rules.RuleSet``):

1. ``secondary_scan``            the full-phase secondary scan and its gate
2. ``inflated_depth_consistency`` per-sector red-noise beta on the event errors
3. ``transit_masked_detrend``     the biweight fitted with the transits masked
4. ``long_period_window_test``    the long-period equivalent of Stage B (i)

Each candidate is measured under the ephemeris prompt 6 chose for it, so the
comparison is like for like; the prepared arrays and the forced-TLS ephemerides
come from ``data/survey/p6/`` and are not recomputed except where an option
changes them (option 3 re-runs the detrend).

    py scripts/p7_options.py run     [--slices 16]     one JSON per candidate
    py scripts/p7_options.py tables                    the aggregate tables

Writes ``data/survey/p7/options/<key>.json`` and ``data/survey/p7/options_p7.json``.
"""
from __future__ import annotations

import argparse
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

from tesshunter import audit_rules as R                                  # noqa: E402
from tesshunter.audit_prep import (                                      # noqa: E402
    clean_and_detrend,
    prepare_series,
    transit_mask,
)
from tesshunter.event_vet import (                                       # noqa: E402
    classes_of,
    event_table,
    sector_beta,
    stagea_criteria,
    summarise_events,
)
from tesshunter.secondary import secondary_scan                          # noqa: E402
from tesshunter.star_vet import long_period_window_test                  # noqa: E402

P6 = REPO / "data" / "survey" / "p6"
LC_ROOT = REPO / "data" / "survey" / "audit_lc"
OUT = REPO / "data" / "survey" / "p7" / "options"
SUMMARY = REPO / "data" / "survey" / "p7" / "options_p7.json"
PY = sys.executable
DEFAULT_TEFF = 5500.0        # [A] where the TIC has no effective temperature


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def one(job: dict, force: bool = False) -> dict:
    import audit_p5 as A
    A.set_roots(P6, LC_ROOT)
    tic, period = job["tic_id"], job["period"]
    k = A.key(tic, period)
    out_path = OUT / f"{k}.json"
    if out_path.exists() and not force:
        r = json.loads(out_path.read_text(encoding="utf-8"))
        if r.get("rules_version") == R.DEFAULT_RULES.version:
            return r
    t_start = time.perf_counter()
    rec = {"key": k, "tic_id": tic, "rank": job["rank"], "survey_period": period,
           "survey_depth_ppt": job["depth_ppt"], "generated_utc": utc(),
           "rules_version": R.DEFAULT_RULES.version, "thresholds": R.thresholds(R.DEFAULT_RULES),
           "report_only": "no verdict is produced for any candidate by this script"}
    try:
        stored = json.loads((P6 / "stageA" / f"{k}.json").read_text(encoding="utf-8"))
        rec["p6"] = {"decision": stored["decision"], "chosen_ephemeris": stored["chosen_ephemeris"],
                     "criteria": stored["criteria"], "n_criteria_passed": stored["n_criteria_passed"]}
        per6 = stored["per_ephemeris"]
        chosen = stored["chosen_ephemeris"]
        eph = per6[chosen]["ephemeris"]
        products = A.choose_per_sector(A.load_products(tic))
        prep_meta = json.loads((P6 / "prep" / f"{k}.json").read_text(encoding="utf-8"))
        window = prep_meta["wotan"]["window_days"]
        st = A.stellar_from_cache(tic)
        rstar, mstar = prep_meta["R_star"], prep_meta["M_star"]
        teff = float(st["teff"]) if st.get("teff") else DEFAULT_TEFF
        z = np.load(P6 / "tls" / f"{k}_lc.npz")
        t_un, f_un, s_un = z["time_unbinned"], z["flux_unbinned"], z["sector_unbinned"]
        cad = {int(p["sector"]): float(p["cadence_s"]) for p in products}
        ref_depth = (eph["ref_depth_ppt"] or 1.0) / 1000.0

        # ── option 1: the full-phase secondary scan ──────────────────────────
        t0s = time.perf_counter()
        sap_det = clean_and_detrend(products, window, flux_key="sap_flux", err_key="sap_flux_err")
        sec = secondary_scan(t_un, f_un, eph["period"], eph["t0"], eph["duration"],
                             rstar, mstar, teff, sap_det["time"], sap_det["flux"])
        sec["seconds"] = round(time.perf_counter() - t0s, 1)
        sec["sap_products_used"] = int(sum(1 for p in sap_det["per_product"] if not p["dropped"]))
        sec["teff_K"] = teff
        rec["secondary"] = sec

        # ── the p6 event table under the chosen ephemeris (the baseline) ─────
        events6 = event_table(products, t_un, f_un, eph["period"], eph["t0"], eph["duration"], ref_depth)
        summ6 = summarise_events(events6, eph)
        crit6 = stagea_criteria(summ6["det_kept"], job["depth_ppt"])

        # ── option 2: red-noise-inflated depth consistency ───────────────────
        in_tr = transit_mask(t_un, eph["period"], eph["t0"], eph["duration"], n_durations=0.5)
        beta = sector_beta(t_un, f_un, s_un, in_tr, eph["duration"], cad)
        summ_beta = summarise_events(events6, eph, beta_by_sector=beta)
        crit_beta = stagea_criteria(summ_beta["det_kept"], job["depth_ppt"])
        rec["inflated_depth_consistency"] = {
            "beta_by_sector": {str(kk): round(v, 3) for kk, v in sorted(beta.items())},
            "beta_median": round(float(np.median(list(beta.values()))), 3) if beta else None,
            "beta_max": round(float(max(beta.values())), 3) if beta else None,
            "p_const_white": summ_beta["det_kept"].get("p_const_white"),
            "p_const_inflated": summ_beta["det_kept"].get("p_const_inflated"),
            "snr_white": summ_beta["det_kept"].get("snr_white"),
            "snr_inflated": summ_beta["det_kept"].get("snr_inflated"),
            "criteria": crit_beta["criteria"], "n_criteria_passed": crit_beta["n_criteria_passed"],
            "all_passed": crit_beta["all_passed"],
            "depth_consistency_now_passes": bool(
                crit_beta["criteria"]["depths_consistent_p_ge_1e-3"]
                and not crit6["criteria"]["depths_consistent_p_ge_1e-3"]),
        }

        # ── option 3: the transit-masked detrend ────────────────────────────
        t0m = time.perf_counter()
        masked = prepare_series(products, window, prep_meta["bin_minutes"],
                                (job["depth_ppt"] / 1000.0),
                                mask_fn=lambda tt: transit_mask(tt, eph["period"], eph["t0"],
                                                               eph["duration"]))
        mdet = masked["unbinned"]
        events_m = event_table(products, mdet["time"], mdet["flux"], eph["period"], eph["t0"],
                               eph["duration"], ref_depth)
        summ_m = summarise_events(events_m, eph)
        crit_m = stagea_criteria(summ_m["det_kept"], job["depth_ppt"])
        d6 = summ6["det_kept"].get("weighted_mean_depth_ppt")
        dm = summ_m["det_kept"].get("weighted_mean_depth_ppt")
        rec["transit_masked_detrend"] = {
            "n_cadences_masked_from_trend": masked["counters"]["n_masked_from_trend"],
            "n_unbinned_unmasked": int(len(t_un)), "n_unbinned_masked": masked["counters"]["n_unbinned"],
            "kept_depth_ppt_unmasked": d6, "kept_depth_ppt_masked": dm,
            "depth_over_survey_unmasked": crit6["depth_over_survey_depth"],
            "depth_over_survey_masked": crit_m["depth_over_survey_depth"],
            "masked_over_unmasked": (round(dm / d6, 3) if (d6 and dm and abs(d6) > 1e-9) else None),
            "kept_snr_unmasked": summ6["det_kept"].get("snr"),
            "kept_snr_masked": summ_m["det_kept"].get("snr"),
            "n_kept_unmasked": summ6["n_kept"], "n_kept_masked": summ_m["n_kept"],
            "criteria": crit_m["criteria"], "n_criteria_passed": crit_m["n_criteria_passed"],
            "all_passed": crit_m["all_passed"], "seconds": round(time.perf_counter() - t0m, 1),
        }

        # ── option 4: the long-period window test ───────────────────────────
        spans = {}
        for s in np.unique(s_un):
            m = s_un == s
            spans[int(s)] = float(t_un[m].max() - t_un[m].min())
        for e in events6:
            if e.get("observed"):
                e["artefact_classes"] = classes_of(e["exclusion_reasons"])
        rec["long_period_window_test"] = long_period_window_test(events6, spans, eph["period"])

        # ── all four together: what the p7.0 rule set decides ───────────────
        beta_m = sector_beta(mdet["time"], mdet["flux"], mdet["sector"],
                             transit_mask(mdet["time"], eph["period"], eph["t0"], eph["duration"],
                                          n_durations=0.5),
                             eph["duration"], cad)
        summ_all = summarise_events(events_m, eph, beta_by_sector=beta_m)
        crit_all = stagea_criteria(summ_all["det_kept"], job["depth_ppt"])
        gate = sec["gate"]
        rec["combined_p7"] = {
            "criteria": crit_all["criteria"], "n_criteria_passed": crit_all["n_criteria_passed"],
            "stageA_all_passed": crit_all["all_passed"],
            "secondary_gate": gate, "variability_flag": sec["variability_flag"],
            "long_period_flag": rec["long_period_window_test"]["flag"],
            "decision": ("FAIL" if (not crit_all["all_passed"] or gate == "FAIL") else "PASS"),
            "kept_snr": crit_all["kept_snr"], "kept_depth_ppt": crit_all["kept_depth_ppt"],
            "depth_over_survey_depth": crit_all["depth_over_survey_depth"],
            "p_const": crit_all["p_const"],
        }
        rec["p6"]["kept_snr"] = crit6["kept_snr"]
        rec["p6"]["kept_depth_ppt"] = crit6["kept_depth_ppt"]
        rec["p6"]["depth_over_survey_depth"] = crit6["depth_over_survey_depth"]
        rec["p6"]["p_const"] = crit6["p_const"]
        rec["status"] = "OK"
    except Exception as exc:                       # a failure is recorded, never silent
        rec["status"] = "ERROR"
        rec["error"] = f"{type(exc).__name__}: {exc}"[:400]
    rec["seconds"] = round(time.perf_counter() - t_start, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
    return rec


def run_slice(index: int, nslices: int, force: bool) -> None:
    import revet_p6 as V
    js = V.jobs()[index::nslices]
    t0 = time.perf_counter()
    for i, job in enumerate(js, 1):
        r = one(job, force=force)
        el = time.perf_counter() - t0
        c = r.get("combined_p7") or {}
        print(f"[{index}:{i}/{len(js)}] rank {job['rank']:>3} {r['key']:<28} {r.get('status')} "
              f"p6 {(r.get('p6') or {}).get('decision')} -> p7 {c.get('decision')} "
              f"| sec gate {c.get('secondary_gate')} dips {(r.get('secondary') or {}).get('n_dips_above_5sigma')} "
              f"| {r['seconds']}s | elapsed {el / 60:.1f} min eta {(el / i) * (len(js) - i) / 60:.1f} min",
              flush=True)


def run(nslices: int, force: bool) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    logdir = REPO / "data" / "survey" / "p7" / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    procs = []
    for i in range(nslices):
        log = open(logdir / f"options_slice{i}.log", "w", encoding="utf-8")
        cmd = [PY, str(Path(__file__).resolve()), "slice", "--index", str(i), "--nslices", str(nslices)]
        if force:
            cmd.append("--force")
        procs.append((i, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=str(REPO)), log))
    codes = []
    for i, pr, log in procs:
        codes.append((i, pr.wait()))
        log.close()
    print("slice exit codes:", codes, flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# the aggregate tables
# ─────────────────────────────────────────────────────────────────────────────
def _pct(xs: list[float]) -> dict:
    if not xs:
        return {}
    a = np.array(xs, dtype=float)
    a = a[np.isfinite(a)]
    if not a.size:
        return {}
    return {"n": int(a.size), "min": round(float(a.min()), 3),
            "p10": round(float(np.percentile(a, 10)), 3), "p25": round(float(np.percentile(a, 25)), 3),
            "median": round(float(np.median(a)), 3), "p75": round(float(np.percentile(a, 75)), 3),
            "p90": round(float(np.percentile(a, 90)), 3), "max": round(float(a.max()), 3),
            "mean": round(float(a.mean()), 3)}


def tables() -> dict:
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(OUT.glob("*.json"))]
    ok = [r for r in recs if r.get("status") == "OK"]
    res = {"generated_utc": utc(), "rules_version": R.DEFAULT_RULES.version,
           "population": {"n_records": len(recs), "n_ok": len(ok),
                          "n_error": len(recs) - len(ok),
                          "errors": [{"key": r["key"], "error": r.get("error")}
                                     for r in recs if r.get("status") != "OK"][:20]},
           "report_only": ("counts of status changes under each option; no candidate is given a "
                           "SUBMIT / HOLD / KILL verdict anywhere in this file")}
    p6pass = [r for r in ok if r["p6"]["decision"] == "PASS"]
    p6fail = [r for r in ok if r["p6"]["decision"] == "FAIL"]
    res["population"]["n_p6_pass"] = len(p6pass)
    res["population"]["n_p6_fail"] = len(p6fail)

    # ---- option 1: the secondary scan -------------------------------------
    sec = [r["secondary"] for r in ok]
    gate_fail = [r for r in ok if r["secondary"]["gate"] == "FAIL"]
    res["option_1_secondary_scan"] = {
        "what": "full-phase scan for dips above 5 sigma outside the primary; the gate is on the "
                "SAP depth of the deepest one against the period-aware planetary bound",
        "n_scanned": len(sec),
        "n_dips_distribution": _pct([s["n_dips_above_5sigma"] for s in sec]),
        "n_with_no_primary": sum(1 for s in sec if s.get("primary") is None),
        "n_clean_scan": sum(1 for s in sec if s.get("verdict", "").startswith("CLEAN")),
        "n_with_at_least_one_secondary": sum(1 for s in sec if s.get("secondaries")),
        "n_variability_flag": sum(1 for s in sec if s.get("variability_flag")),
        "n_gate_fail": len(gate_fail),
        "gate_fail_from_p6_pass": sorted(r["key"] for r in gate_fail if r["p6"]["decision"] == "PASS"),
        "n_gate_fail_from_p6_pass": sum(1 for r in gate_fail if r["p6"]["decision"] == "PASS"),
        "n_gate_fail_from_p6_fail": sum(1 for r in gate_fail if r["p6"]["decision"] == "FAIL"),
        "secondary_over_bound_distribution": _pct(
            [s["secondary_over_planet_bound"] for s in sec if s.get("secondary_over_planet_bound")]),
        "gate_measured_in": {v: sum(1 for s in sec if s.get("gate_measured_in") == v)
                             for v in ("sap", "detrended")},
        "p6_pass_rows": [{"key": r["key"], "rank": r["rank"],
                          "n_dips": r["secondary"]["n_dips_above_5sigma"],
                          "deepest_other_phase": (r["secondary"]["secondaries"] or [{}])[0].get("phase"),
                          "deepest_other_sigma": (r["secondary"]["secondaries"] or [{}])[0].get("sigma"),
                          "sap_depth_ppt": (r["secondary"].get("deepest_secondary_in_sap") or {}).get("depth_ppt"),
                          "over_planet_bound": r["secondary"].get("secondary_over_planet_bound"),
                          "sigma_over_bound": r["secondary"].get("secondary_sigma_over_planet_bound"),
                          "gate": r["secondary"]["gate"], "verdict": r["secondary"]["verdict"][:160]}
                         for r in sorted(p6pass, key=lambda r: r["rank"])],
    }

    # ---- option 2: the inflated depth consistency -------------------------
    inf = [r["inflated_depth_consistency"] for r in ok]
    now_pass = [r for r in ok if r["inflated_depth_consistency"]["depth_consistency_now_passes"]]
    res["option_2_inflated_depth_consistency"] = {
        "what": "per-sector red-noise beta multiplies each event's error before the chi-square; "
                "the gate uses the inflated p-value, the white one stays on the record",
        "beta_median_distribution": _pct([i["beta_median"] for i in inf if i["beta_median"]]),
        "beta_max_distribution": _pct([i["beta_max"] for i in inf if i["beta_max"]]),
        "n_beta_at_the_cap": sum(1 for i in inf if (i["beta_max"] or 0) >= R.BETA_MAX),
        "n_depth_consistency_changed_to_pass": len(now_pass),
        "n_of_those_that_then_pass_all_six": sum(1 for r in now_pass
                                                 if r["inflated_depth_consistency"]["all_passed"]),
        "n_stageA_pass_under_this_option_alone": sum(
            1 for r in ok if r["inflated_depth_consistency"]["all_passed"]),
        "changed_to_pass_all_six": sorted(
            {"key": r["key"], "rank": r["rank"], "p6_decision": r["p6"]["decision"],
             "p_white": r["inflated_depth_consistency"]["p_const_white"],
             "p_inflated": r["inflated_depth_consistency"]["p_const_inflated"],
             "beta_median": r["inflated_depth_consistency"]["beta_median"]}.__str__()
            for r in ok if r["inflated_depth_consistency"]["all_passed"]
            and r["p6"]["decision"] == "FAIL")[:40],
        "n_p6_pass_that_still_pass": sum(1 for r in p6pass
                                         if r["inflated_depth_consistency"]["all_passed"]),
    }

    # ---- option 3: the transit-masked detrend -----------------------------
    tm = [r["transit_masked_detrend"] for r in ok]
    res["option_3_transit_masked_detrend"] = {
        "what": "the biweight is fitted with one duration either side of every predicted mid-time "
                "masked out of the trend; the depth is then measured on the same events",
        "depth_over_survey_unmasked": _pct([t["depth_over_survey_unmasked"] for t in tm
                                            if t["depth_over_survey_unmasked"] is not None]),
        "depth_over_survey_masked": _pct([t["depth_over_survey_masked"] for t in tm
                                          if t["depth_over_survey_masked"] is not None]),
        "masked_over_unmasked": _pct([t["masked_over_unmasked"] for t in tm
                                      if t["masked_over_unmasked"] is not None]),
        "n_depth_ratio_increased": sum(1 for t in tm if (t["masked_over_unmasked"] or 0) > 1.0),
        "n_depth_ratio_decreased": sum(1 for t in tm if t["masked_over_unmasked"] is not None
                                       and t["masked_over_unmasked"] < 1.0),
        "n_stageA_pass_under_this_option_alone": sum(1 for t in tm if t["all_passed"]),
        "n_p6_pass_that_still_pass": sum(1 for r in p6pass if r["transit_masked_detrend"]["all_passed"]),
        "n_depth_criterion_gained": sum(
            1 for r in ok if r["transit_masked_detrend"]["criteria"]["depth_within_0.5_2x_survey"]
            and not r["p6"]["criteria"]["depth_within_0.5_2x_survey"]),
        "n_depth_criterion_lost": sum(
            1 for r in ok if not r["transit_masked_detrend"]["criteria"]["depth_within_0.5_2x_survey"]
            and r["p6"]["criteria"]["depth_within_0.5_2x_survey"]),
        "on_the_p6_passers": [{"key": r["key"], "rank": r["rank"],
                               "unmasked": r["transit_masked_detrend"]["depth_over_survey_unmasked"],
                               "masked": r["transit_masked_detrend"]["depth_over_survey_masked"],
                               "ratio": r["transit_masked_detrend"]["masked_over_unmasked"]}
                              for r in sorted(p6pass, key=lambda r: r["rank"])],
    }

    # ---- option 4: the long-period window test ----------------------------
    lp = [r["long_period_window_test"] for r in ok]
    applies = [x for x in lp if x["applies"]]
    res["option_4_long_period_window_test"] = {
        "what": "where no sector spans 1.5 periods, count the sectors in which every observed "
                "predicted epoch was removed; more than half flags, never kills",
        "n_applies": len(applies), "n_does_not_apply": len(lp) - len(applies),
        "n_flagged": sum(1 for x in lp if x["flag"]),
        "fraction_removed_distribution": _pct([x["fraction_of_sectors_fully_removed"] for x in applies
                                               if x["fraction_of_sectors_fully_removed"] is not None]),
        "n_flagged_among_p6_pass": sum(1 for r in p6pass if r["long_period_window_test"]["flag"]),
        "n_flagged_among_p6_fail": sum(1 for r in p6fail if r["long_period_window_test"]["flag"]),
        "p6_pass_rows": [{"key": r["key"], "rank": r["rank"],
                          "applies": r["long_period_window_test"]["applies"],
                          "sectors": r["long_period_window_test"]["n_sectors_with_an_observed_epoch"],
                          "fully_removed": r["long_period_window_test"]["n_sectors_with_every_observed_epoch_removed"],
                          "flag": r["long_period_window_test"]["flag"]}
                         for r in sorted(p6pass, key=lambda r: r["rank"])],
    }

    # ---- all four together -------------------------------------------------
    changed = [r for r in ok if r["combined_p7"]["decision"] != r["p6"]["decision"]]
    res["combined_p7_0"] = {
        "what": "all four options on: the Stage A criteria on the masked detrend with inflated "
                "errors, plus the secondary gate.  The long-period test flags but never decides.",
        "n_p6_pass": len(p6pass), "n_p6_fail": len(p6fail),
        "n_p7_pass": sum(1 for r in ok if r["combined_p7"]["decision"] == "PASS"),
        "n_changed": len(changed),
        "pass_to_fail": [{"key": r["key"], "rank": r["rank"],
                          "why": ("secondary gate" if r["combined_p7"]["secondary_gate"] == "FAIL"
                                  else "Stage A criteria: " + ", ".join(
                                      c for c, v in r["combined_p7"]["criteria"].items() if not v))}
                         for r in changed if r["p6"]["decision"] == "PASS"],
        "fail_to_pass": [{"key": r["key"], "rank": r["rank"],
                          "p6_failed": [c for c, v in r["p6"]["criteria"].items() if not v],
                          "p7_kept_snr": r["combined_p7"]["kept_snr"],
                          "p7_depth_over_survey": r["combined_p7"]["depth_over_survey_depth"],
                          "p7_p_const": r["combined_p7"]["p_const"]}
                         for r in changed if r["p6"]["decision"] == "FAIL"],
        "n_flagged_only": sum(1 for r in ok if r["combined_p7"]["decision"] == r["p6"]["decision"]
                              and (r["combined_p7"]["variability_flag"]
                                   or r["combined_p7"]["long_period_flag"])),
    }
    # per-criterion movement, all 405
    crit_moves = {}
    for c in ("kept_events_ge_3", "kept_snr_ge_7", "top_share_le_50pct", "snr_without_top_ge_5",
              "depth_within_0.5_2x_survey", "depths_consistent_p_ge_1e-3"):
        gained = sum(1 for r in ok if r["combined_p7"]["criteria"][c] and not r["p6"]["criteria"][c])
        lost = sum(1 for r in ok if not r["combined_p7"]["criteria"][c] and r["p6"]["criteria"][c])
        crit_moves[c] = {"gained_under_p7": gained, "lost_under_p7": lost,
                         "failing_under_p6": sum(1 for r in ok if not r["p6"]["criteria"][c]),
                         "failing_under_p7": sum(1 for r in ok if not r["combined_p7"]["criteria"][c])}
    res["combined_p7_0"]["per_criterion"] = crit_moves
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "option_1_secondary_scan"}, indent=1,
                     default=str)[:6000])
    print(f"\nwrote {SUMMARY}")
    return res


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--slices", type=int, default=16)
    r.add_argument("--force", action="store_true")
    s = sub.add_parser("slice")
    s.add_argument("--index", type=int, required=True)
    s.add_argument("--nslices", type=int, required=True)
    s.add_argument("--force", action="store_true")
    o = sub.add_parser("one")
    o.add_argument("--tic", type=int, required=True)
    o.add_argument("--period", type=float, required=True)
    o.add_argument("--force", action="store_true")
    sub.add_parser("tables")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        run(a.slices, a.force)
        tables()
    elif a.cmd == "slice":
        run_slice(a.index, a.nslices, a.force)
    elif a.cmd == "one":
        import revet_p6 as V
        job = next(j for j in V.jobs() if j["tic_id"] == a.tic and abs(j["period"] / a.period - 1) < 1e-6)
        print(json.dumps(one(job, force=a.force), indent=1, default=str)[:8000])
    elif a.cmd == "tables":
        tables()


if __name__ == "__main__":
    main()
