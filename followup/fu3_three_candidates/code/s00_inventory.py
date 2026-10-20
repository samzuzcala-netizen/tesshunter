"""Stage 0: inventory of every accessible input for the three targets, with SHA-256 hashes, the discovery
configuration, the product/sector/cadence provenance, and the recovered ephemerides.  Read-only on all inputs.

Outputs: manifests/input_manifest.csv, manifests/discovery_config.json, results/s00_provenance_<tic>.json,
results/s00_cited_vs_available.json
"""
import csv
import subprocess
import sys

from fu3_common import *

sys.path.insert(0, str(REPO / "src"))


def files_under(p: Path):
    if p.is_file():
        yield p
    elif p.is_dir():
        for q in sorted(p.rglob("*")):
            if q.is_file() and "__pycache__" not in q.parts:
                yield q


def categories(tic: int):
    t = str(tic)
    cats = {
        "survey_store_lightcurves": [S1 / "audit_lc" / f"tic{t}"],
        "survey_search_outputs": [S1 / "runs" / "s1_b1" / d / f"s1_{t}{ext}" for d, ext in
                                  (("results", ".json"), ("receipts", ".json"), ("traces", ".jsonl"))],
        "survey_funnel_case_roots": sorted((S1 / "funnel" / "s1_b1").glob(f"s1_{t}_p*")),
        "survey_funnel_receipts": sorted((S1 / "funnel_receipts" / "s1_b1").glob(f"*/s1_{t}_p*.json")),
        "survey_packet": [PACKET[tic]],
        "survey_neighbours": [S1 / "neighbours" / "neighbours" / f"tic{t}.json"],
        "survey_runtimes": sorted((S1 / "runtimes").glob(f"s1_b1_*/s1_{t}_*.json")),
        "survey_controller_records": sorted((S1 / "controllers").glob(f"s1_b1_*/*/*{t}*")),
        "survey_download_receipts": sorted((S1 / "download_receipts").glob(f"s1_b1_*/tic{t}.json")),
        "deep_analysis_files": sorted(p for p in DEEP.rglob(f"*{t}*") if p.is_file()),
        "continuation_files": sorted(p for p in CONT.rglob(f"*{t}*") if p.is_file()),
        "batch_review_files": [REVIEW / n for n in ("batch1_evidence.json", "batch1_rankings.json",
                                                   "candidate_judgments.json", "lightcurve_checks.json")],
    }
    return cats


SHARED = {
    "deep_analysis_shared": [DEEP / n for n in ("inputs.json", "assessments.json", "input_inventory.txt",
                                                "download_log.txt", "photometry_log.txt", "pixels_log.txt")]
                            + [DEEP / "output" / "pdf" / "TESS_batch1_deep_analysis.pdf"],
    "continuation_shared": [CONT / "README.txt", CONT / "output" / "pdf" / "TESS_seven_candidate_continuation.pdf"]
                           + [CONT / "analysis" / n for n in (
                               "test_matrix.json", "updated_assessments.json", "validation_checks.json",
                               "input_audit.json", "environment.json", "coverage_summary.json",
                               "archive_requests.json", "archive_followup_requests.json", "last_archive_requests.json",
                               "additional_cutouts_manifest.json", "additional_extraction_status.json")]
                           + sorted((CONT / "analysis" / "calibration").glob("*"))
                           + sorted(CONT.glob("*.py")) + sorted((CONT / "provenance").rglob("*")),
    "discovery_code_s1": sorted((REPO / "s1" / "protocol").glob("*.py")) + [REPO / "s1" / "survey" / "targets_s1.csv",
                                                                         REPO / "s1" / "results" / "BATCH_1.md",
                                                                         REPO / "s1" / "results" / "batch_1.json"],
    "discovery_code_k1_k2": sorted((REPO / "k1" / "protocol").glob("*.py")) + sorted((REPO / "k2" / "protocol").glob("*.py")),
    "discovery_code_src": sorted((REPO / "src" / "tesshunter").glob("*.py")) + sorted((REPO / "scripts").glob("*.py")),
}


def git(*args):
    try:
        return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as exc:   # noqa: BLE001
        return f"ERROR {exc}"


def manifest():
    rows = []
    seen = set()
    groups = {f"tic{t}:{k}": v for t in TICS for k, v in categories(t).items()}
    groups.update({f"shared:{k}": v for k, v in SHARED.items()})
    for label, paths in groups.items():
        for p in paths:
            if not Path(p).exists():
                rows.append(dict(group=label, path=str(p), exists=False, bytes="", sha256="", mtime_utc=""))
                continue
            for f in files_under(Path(p)):
                key = (label, str(f))
                if key in seen:
                    continue
                seen.add(key)
                st = f.stat()
                rows.append(dict(group=label, path=str(f), exists=True, bytes=st.st_size, sha256=sha256(f),
                                 mtime_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(st.st_mtime))))
    out = MAN / "input_manifest.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    summary = {}
    for r in rows:
        g = summary.setdefault(r["group"], dict(files=0, bytes=0, missing=0))
        if r["exists"]:
            g["files"] += 1
            g["bytes"] += int(r["bytes"])
        else:
            g["missing"] += 1
    save(MAN / "input_manifest_summary.json", dict(generated_utc=utc(), groups=summary, n_rows=len(rows)))
    return summary


def discovery_config():
    from tesshunter import survey
    cfg = survey.PRESETS["survey_k1"].to_dict()
    s1run = {}
    for name in ("launch_s1_b1_search_a.json", "launch_s1_b1_search_b.json", "launch_s1_b1_search_c.json"):
        p = REPO / "s1" / "manifests" / name
        if p.exists():
            s1run[name] = read(p)
    rt = sorted((S1 / "runtimes").glob("s1_b1_search*/s1_270573718*.json"))
    out = dict(
        generated_utc=utc(), repo=str(REPO), branch=git("branch", "--show-current"), head=git("rev-parse", "HEAD"),
        head_subject=git("log", "-1", "--format=%s"), dirty_files=git("status", "--porcelain").splitlines()[:50],
        preset_survey_k1=cfg, s1_search_launch_manifests=s1run,
        example_search_runtime=(read(rt[0]) if rt else None),
        note="S1 runs the K1/K2 frozen search worker (search_worker_k1.py) with preset survey_k1; the period band is "
             "0.5-50 d, durations 0.02-0.35 d, sectors <= 98 at native mixed cadence, >= 3 transits.")
    save(MAN / "discovery_config.json", out)
    return out


def first(d, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return default
    return d


def provenance(tic: int):
    pk = PACKET[tic]
    job = read(pk / "job.json")
    fit = read(pk / "fit.json")
    stA = read(pk / "stageA.json")
    stC = read(pk / "stageC.json")
    idx = read(S1 / "audit_lc" / f"tic{tic}" / "index.json")
    cand = sorted((S1 / "funnel" / "s1_b1").glob(f"s1_{tic}_p*"))
    ap_json = None
    for c in cand:
        for q in c.glob("eb_screen/*_target_aperture.json"):
            ap_json = read(q)
    products_on_mast = {}
    for r in idx.get("rows", []):
        products_on_mast.setdefault(f"{r['author']}|{int(r['exptime_s'])}", set()).add(int(r["sector"]))
    out = dict(
        tic=tic, packet=str(pk), job=job,
        ephemerides=dict(
            survey_period=fit.get("survey_period"),
            stageC_blind=dict(period=first(stC, "blind", "period"), t0_btjd=first(stC, "blind", "T0_btjd"),
                              duration_d=first(stC, "blind", "duration_days"), sde=first(stC, "blind", "SDE"),
                              peaks=stC.get("peaks")),
            stageA_event_ephemeris=first(stA, "event_ephemeris") or first(stA, "ephemeris"),
            fit_adopted=fit.get("adopted"), fit_free=fit.get("free_fit"), fit_prior=fit.get("prior_fit"),
            fit_data=fit.get("data"), fit_stellar=fit.get("stellar"), fit_limb_darkening=fit.get("limb_darkening"),
            delta_chi2_prior_minus_free=fit.get("delta_chi2_prior_minus_free"),
            note="fit_adopted.t0_err/period_err are marginal errors at the reference epoch t0 (cycle 0); no T0-P "
                 "covariance is stored by the packet. A conditional covariance is reconstructed from per-event "
                 "times in s03."),
        products_used=[{k: p.get(k) for k in ("sector", "author", "cadence_s", "native_cadence_s", "flux_column",
                                               "camera", "ccd", "n", "n_quality_nonzero", "version", "fits",
                                               "fits_sha256", "t_start", "t_end")} for p in idx.get("products", [])],
        products_listed_on_mast_at_download={k: sorted(v) for k, v in sorted(products_on_mast.items())},
        download_utc=idx.get("downloaded_utc"),
        stageA_chosen_ephemeris=stA.get("chosen_ephemeris"), stageA_decision=stA.get("decision"),
        stageA_reason=stA.get("reason"), stageA_prepare=stA.get("prepare"), stageA_survey=stA.get("survey"),
        stageA_ephemeris=first(stA, "per_ephemeris", stA.get("chosen_ephemeris"), "ephemeris"),
        stageA_event_records=[e for e in (first(stA, "per_ephemeris", stA.get("chosen_ephemeris"), "events") or [])
                              if e.get("observed")],
        stageA_n=dict((k, first(stA, "per_ephemeris", stA.get("chosen_ephemeris"), k)) for k in
                      ("n_predicted_in_span", "n_observed", "n_excluded", "n_kept", "kept_snr", "kept_depth_ppt",
                       "kept_depth_err_ppt", "p_const", "top_event_share", "snr_without_top")),
        target_aperture_product=(dict(method=ap_json.get("method"), k1_aperture=ap_json.get("k1_aperture"),
                                      ephemeris=ap_json.get("ephemeris"),
                                      sectors=[dict(sector=s.get("sector"), status=s.get("status"),
                                                    n_aperture_pixels=s.get("n_aperture_pixels"),
                                                    n_background_pixels=s.get("n_background_pixels"),
                                                    n_cadences=s.get("n_cadences"),
                                                    net=first(s, "measurements", "net"))
                                               for s in ap_json.get("sectors", [])]) if ap_json else None),
        funnel_candidate_ids=[c.name for c in cand],
    )
    save(RES / f"s00_provenance_{tic}.json", out)
    return out


def cited_vs_available():
    """Files the prior reports cite, checked against disk (available vs merely cited)."""
    checks = []
    for t in TICS:
        for suffix in ("recurrence", "models", "exact_alternatives", "joint_binary", "localization_controls",
                       "localization_jackknife", "fpp_sensitivity", "fpp_scene_audit", "ground_photometry",
                       "stellar_archival", "activity", "followup_checks", "corrected_calibrated",
                       "aperture_calibrated", "fresh_aperture_calibrated", "fresh_apertures_manifest",
                       "ps1_check"):
            p = CONT / "analysis" / f"{t}_{suffix}.json"
            checks.append(dict(tic=t, cited_by="continuation p.9-21 'analysis/<tic>_*.json'", file=str(p),
                               available=p.exists()))
    for name in ("download_manifest.json",):
        hits = list(DEEP.rglob(name))
        checks.append(dict(tic=None, cited_by="deep report ref [1]", file=name, available=bool(hits),
                           found=[str(h) for h in hits]))
    for name in ("reproduce.ps1", "make_figures.py", "validate_evidence.py", "localization_controls.py",
                 "fpp_sensitivity.py", "fpp_native_bins.py", "stellar_archival.py", "inspect_ps1.py"):
        p = CONT / name
        checks.append(dict(tic=None, cited_by="continuation p.25 file map", file=str(p), available=p.exists()))
    save(RES / "s00_cited_vs_available.json", checks)
    return checks


if __name__ == "__main__":
    log("s00", "inventory start")
    s = manifest()
    log("s00", f"manifest groups: {len(s)}")
    d = discovery_config()
    log("s00", f"discovery config head {d['head'][:12]} branch {d['branch']}")
    for t in TICS:
        p = provenance(t)
        log("s00", f"tic {t}: products {len(p['products_used'])}, stageA events {len(p['stageA_event_records'])}")
    c = cited_vs_available()
    log("s00", f"cited files missing: {[x['file'] for x in c if not x['available']]}")
