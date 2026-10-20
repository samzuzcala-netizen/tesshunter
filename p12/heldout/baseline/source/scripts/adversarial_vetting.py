"""Prompt 3, part E: the adversarial check of the vetting stack.

Runs the full search + characterisation + vetting + FPP stack on known
objects of three classes drawn from the cached catalogs:

* ``planet``: ExoFOP TOIs with TFOPWG disposition CP or KP;
* ``eb``: eclipsing binaries from the TESS EB catalog (Prsa et al. 2022);
* ``blend``: ExoFOP TOIs retired as FP whose comment names a nearby or
  background eclipsing binary (NEB / BEB / NPC).

Usage::

    python scripts/adversarial_vetting.py --build-list            # data/adversarial/targets_v1.csv
    python scripts/adversarial_vetting.py --run --workers 8       # data/adversarial/runs/v1/*.json
    python scripts/adversarial_vetting.py --summarize             # docs/ADVERSARIAL_VETTING.md

The search window brackets the known period by a factor 3.2 either side so
the alias resolver is tested on P/2 and 2P, and the candidate matching the
known period (ratio 1, or a harmonic) is the one vetted. Every run writes one
JSON per target; ``--run`` skips targets that already have a result unless
``--force``. Nothing here submits anything anywhere.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
             "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_var, "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

REPO = Path(__file__).resolve().parent.parent
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data" / "cache" / "lightkurve"))
sys.path.insert(0, str(REPO / "src"))

ADV_DIR = REPO / "data" / "adversarial"
TARGETS_CSV = ADV_DIR / "targets_v1.csv"
RUN_DIR = ADV_DIR / "runs" / "v1"
DOC_PATH = REPO / "docs" / "ADVERSARIAL_VETTING.md"

N_PLANET, N_EB, N_BLEND = 15, 15, 10
RESERVE = 3          # candidates listed per class beyond the quota, used when a target has no SPOC data
BLEND_RESERVE = 12   # blends were mostly found in FFI searches; many have no 2-min data at all
SEED = 20260902

HARMONIC_RATIOS = {1.0: "recovered", 2.0: "alias 2P", 0.5: "alias P/2", 3.0: "alias 3P", 1 / 3: "alias P/3"}


# ---------------------------------------------------------------------------
# Target list
# ---------------------------------------------------------------------------

def build_list() -> None:
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(SEED)
    toi = pd.read_csv(REPO / "data/cache/catalogs/toi/raw/exofop_toi.csv", low_memory=False)
    toi["tic"] = pd.to_numeric(toi["TIC ID"], errors="coerce")
    toi["period"] = pd.to_numeric(toi["Period (days)"], errors="coerce")
    toi["depth_ppm"] = pd.to_numeric(toi["Depth (ppm)"], errors="coerce")
    toi["tmag"] = pd.to_numeric(toi["TESS Mag"], errors="coerce")
    toi["snr"] = pd.to_numeric(toi["Planet SNR"], errors="coerce")
    toi["dur_h"] = pd.to_numeric(toi["Duration (hours)"], errors="coerce")
    toi["epoch"] = pd.to_numeric(toi["Epoch (BJD)"], errors="coerce")
    toi["n_sectors"] = toi["Sectors"].fillna("").astype(str).str.count(",") + 1

    rows = []

    # planets: TFOPWG disposition CP or KP, clear signal, bright enough for SPOC 2-min
    pl = toi[(toi["TFOPWG Disposition"].isin(["CP", "KP"])) & (toi["snr"] >= 15)
             & (toi["tmag"] <= 12.0) & (toi["period"].between(0.5, 20.0))
             & (toi["depth_ppm"].between(300, 30000))].copy()
    # one row per TIC (multi-planet systems keep the strongest signal)
    pl = pl.sort_values("snr", ascending=False).drop_duplicates("tic")
    pl = pl.sample(frac=1.0, random_state=int(rng.integers(1e9))).head(N_PLANET + RESERVE)
    for _, r in pl.iterrows():
        rows.append(dict(cls="planet", tic_id=int(r["tic"]), name=f"TOI-{r['TOI']}", period_known=r["period"],
                         epoch_known_bjd=r["epoch"], depth_ppm_known=r["depth_ppm"], duration_h_known=r["dur_h"],
                         tmag=r["tmag"], disposition=r["TFOPWG Disposition"], source="exofop_toi",
                         comment=str(r.get("Comments", ""))[:160]))

    # blends: retired FPs whose comment names a nearby / background EB
    fp = toi[toi["TFOPWG Disposition"] == "FP"].copy()
    c = fp["Comments"].fillna("").str.upper()
    fp = fp[c.str.contains("NEB|BEB|NPC|NEARBY EB|BACKGROUND EB|BLEND")]
    fp = fp[(fp["tmag"] <= 12.5) & (fp["period"].between(0.3, 20.0)) & (fp["depth_ppm"] >= 300)]
    fp = fp.drop_duplicates("tic").sample(frac=1.0, random_state=int(rng.integers(1e9))).head(N_BLEND + BLEND_RESERVE)
    for _, r in fp.iterrows():
        rows.append(dict(cls="blend", tic_id=int(r["tic"]), name=f"TOI-{r['TOI']}", period_known=r["period"],
                         epoch_known_bjd=r["epoch"], depth_ppm_known=r["depth_ppm"], duration_h_known=r["dur_h"],
                         tmag=r["tmag"], disposition="FP", source="exofop_toi",
                         comment=str(r.get("Comments", ""))[:160]))

    # eclipsing binaries: detached-ish, transit-like, bright, not already a TOI
    eb = pd.read_csv(REPO / "data/cache/catalogs/tess_eb/raw/hlsp_tess-ebs_s0001-s0026_v1.0_cat.csv")
    eb = eb[(eb["Tmag"] <= 11.5) & (eb["period"].between(0.5, 20.0)) & (eb["morph_coeff"] < 0.6)
            & (eb["prim_depth_pf"].between(0.005, 0.4))]
    eb = eb[~eb["tess_id"].isin(set(toi["tic"].dropna().astype(int)))]
    eb = eb.drop_duplicates("tess_id").sample(frac=1.0, random_state=int(rng.integers(1e9))).head(N_EB + RESERVE)
    for _, r in eb.iterrows():
        sec = r.get("sec_depth_pf")
        rows.append(dict(cls="eb", tic_id=int(r["tess_id"]), name=f"TESS-EB {int(r['tess_id'])}",
                         period_known=r["period"], epoch_known_bjd=r["bjd0"] + 2457000.0,
                         depth_ppm_known=float(r["prim_depth_pf"]) * 1e6, duration_h_known=None,
                         tmag=r["Tmag"], disposition="EB", source="tess_eb_prsa2022",
                         comment=f"morph={r['morph_coeff']:.2f} sec_depth={sec if sec == sec else 'nan'} sectors={r['sectors']}"))

    df = pd.DataFrame(rows)
    ADV_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TARGETS_CSV, index=False)
    print(df.groupby("cls").size().to_string())
    print(f"wrote {TARGETS_CSV}")


# ---------------------------------------------------------------------------
# One target
# ---------------------------------------------------------------------------

def _match_candidate(planets: list, p_known: float, tol: float = 0.01):
    best = None
    for p in planets:
        per = float(p["period_days"])
        for ratio, label in HARMONIC_RATIOS.items():
            if abs(per / (p_known * ratio) - 1.0) <= tol:
                cand = (0 if ratio == 1.0 else 1, -float(p.get("snr", 0)), p, label)
                if best is None or cand[:2] < best[:2]:
                    best = cand
    return (best[2], best[3]) if best else (None, "not detected")


def run_one(row: dict, budget_s: float, n_draws: int, do_fpp: bool, do_centroid: bool) -> dict:
    import logging
    import socket
    logging.basicConfig(level=logging.WARNING)
    socket.setdefaulttimeout(300.0)      # no MAST / Gaia call may hang a worker forever
    import numpy as np
    from tesshunter import fpp as fppmod
    from tesshunter.pipeline import search_target
    from tesshunter import stellar as stmod

    tic = int(row["tic_id"])
    p_known = float(row["period_known"])
    out = {"cls": row["cls"], "tic_id": tic, "name": row["name"], "period_known": p_known,
           "depth_ppm_known": row.get("depth_ppm_known"), "tmag": row.get("tmag"),
           "status": "ok", "error": None, "match": "not detected", "matched": None,
           "verdict": None, "fpp": None, "nfpp": None, "packet_eligible": None,
           "timings": {}, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    t0 = time.perf_counter()
    try:
        p_min = max(0.5, p_known / 3.2)
        p_max = min(40.0, p_known * 3.2)
        dur_max = 0.2 if p_known < 10 else 0.3
        common = dict(
            target=tic, mission="TESS", max_units=3,
            period_min=p_min, period_max=p_max, duration_min=0.01, duration_max=dur_max,
            max_planets=3, bin_minutes=10.0, top_n=20, n_periods=None, snr_min=5.0,
            snr_min_resolved=5.0, min_event_completeness=0.5, min_composite_score=3.0,
            min_transits=2, sigma_clip=4.0, mask_width_factor=7.0, artifact_periods=[],
            is_known_toi=False, max_results=12, generate_report=False, time_budget_s=budget_s,
        )
        # SPOC 2-minute first; when the star has none (most blend TOIs came
        # out of FFI searches) fall back to any author and cadence, which the
        # download layer resolves by its SPOC > TESS-SPOC > QLP priority.
        res = search_target(author="SPOC", exptime=120, **common)
        d = res.to_dict()
        out["data_source"] = "SPOC 120 s"
        if not (d.get("provenance") or {}).get("products"):
            res = search_target(author=None, exptime="auto", **common)
            d = res.to_dict()
            prods = (d.get("provenance") or {}).get("products") or []
            out["data_source"] = "fallback: " + ", ".join(
                sorted({f"{p.get('author')} {p.get('exptime', '')}".strip() for p in prods})) if prods else "none"
        data_author = None
        prods = (d.get("provenance") or {}).get("products") or []
        if prods:
            data_author = str(prods[0].get("author") or "")
        out["data_author"] = data_author
        out["timings"] = d["timings"]
        out["n_sectors"] = d.get("n_sectors")
        out["units_used"] = (d.get("provenance") or {}).get("units_used")
        out["n_planets"] = len(d["planets"])
        out["planets"] = [{k: p.get(k) for k in ("planet_num", "period_days", "epoch_btjd", "duration_days",
                                                   "depth_ppt", "snr", "harmonic_label", "verdict", "depth_source",
                                                   "carves_exclusion_zone", "odd_even_retest")}
                          for p in d["planets"]]
        out["stellar"] = d.get("stellar")
        out["notes"] = d.get("notes")
        if not d["planets"]:
            out["status"] = "no_candidates" if (d.get("provenance") or {}).get("products") else "no_data"
            if out["status"] == "no_data":
                out["error"] = "; ".join(d.get("notes") or [])[:300]
            out["timings"]["total"] = time.perf_counter() - t0
            return out
        cand, label = _match_candidate(d["planets"], p_known)
        out["match"] = label
        if cand is None:
            out["timings"]["total"] = time.perf_counter() - t0
            return out
        vet = next((v for v in d["vetting"] if v["planet_num"] == cand["planet_num"]), None)
        out["matched"] = {k: cand.get(k) for k in ("planet_num", "period_days", "epoch_btjd", "duration_days",
                                                    "depth_ppt", "depth_ppt_bls", "depth_ppt_flat", "snr",
                                                    "harmonic_label", "verdict", "depth_source",
                                                    "carves_exclusion_zone", "odd_even_retest", "rp_rs", "a_rs",
                                                    "impact_b", "rp_rearth", "a_rs_inconsistent")}
        out["matched"]["fit"] = cand.get("fit")
        out["matched"]["gate_fit"] = cand.get("gate_fit")
        out["vetting"] = vet
        out["verdict_lc_only"] = cand.get("verdict")
        out["verdict"] = cand.get("verdict")

        fpp_obj = None
        if do_fpp:
            t1 = time.perf_counter()
            fit = cand.get("fit") or {}
            depth_frac = float(cand["depth_ppt"]) / 1000.0
            sectors = [int(u) for u in (out["units_used"] or [])][:3]
            sp = stmod.StellarParams.from_dict(d["stellar"]) if d.get("stellar") else None
            tt = np.asarray(res.lc_clean.time.value, dtype=float)
            cad = float(np.median(np.diff(np.sort(tt)))) if tt.size > 1 else 2.0 / 1440.0
            fpp_obj = fppmod.run_fpp(
                tic, sectors, tt, np.asarray(res.lc_clean.flux.value, dtype=float),
                None, period=float(cand["period_days"]), t0=float(cand["epoch_btjd"]),
                duration=float(fit.get("duration_days") or cand["duration_days"]), depth_frac=depth_frac,
                exp_time_days=cad, tmag=(sp.tmag if sp else None), aperture="auto",
                author=(data_author or "SPOC"), n_draws=n_draws, red_noise_beta=fit.get("beta_red_noise"),
                ra=(sp.ra if sp else None), dec=(sp.dec if sp else None),
            )
            out["fpp_result"] = fpp_obj.to_dict()
            out["fpp"], out["nfpp"] = fpp_obj.fpp, fpp_obj.nfpp
            out["timings"]["fpp"] = time.perf_counter() - t1

        # Pixel-level checks (centroid on up to two TPF sectors, TIC
        # contamination, TRICERATOPS NFPP) folded into the verdict: these are
        # the tests that see a blend the light curve cannot.
        if do_centroid:
            from tesshunter.centroid import run_centroid_check
            from tesshunter.contamination import run_contamination_check
            from tesshunter.vetting import apply_pixel_checks, vetting_result_from_dict
            t1 = time.perf_counter()
            fit = cand.get("fit") or {}
            sectors_c = [int(u) for u in (out["units_used"] or [])][:2]
            cen = None
            try:
                cen = run_centroid_check(tic, "TESS", sectors_c, float(cand["period_days"]),
                                         float(cand["epoch_btjd"]),
                                         float(fit.get("duration_days") or cand["duration_days"]))
            except Exception as exc:
                out["centroid_error"] = str(exc)[:200]
            con = None
            spx = stmod.StellarParams.from_dict(d["stellar"]) if d.get("stellar") else None
            if spx is not None and spx.ra is not None:
                try:
                    con = run_contamination_check(spx.ra, spx.dec, spx.tmag or 10.0, float(cand["depth_ppt"]))
                except Exception as exc:
                    out["contamination_error"] = str(exc)[:200]
            out["centroid"] = ({k: v for k, v in cen.__dict__.items()} if cen is not None else None)
            out["contamination"] = ({k: v for k, v in con.__dict__.items() if not k.endswith("neighbours")}
                                    if con is not None else None)
            if vet is not None and vet.get("result"):
                vr = vetting_result_from_dict(vet["result"])
                new_verdict = apply_pixel_checks(vr, cen, con, fpp=fpp_obj)
                vet["flags_high"] = list(vr.high_risk_flags)
                vet["flags_medium"] = list(vr.medium_flags)
                vet["notes"] = list(vr.notes)
                vet["verdict"] = new_verdict
                out["verdict"] = new_verdict
            out["timings"]["pixel_checks"] = time.perf_counter() - t1

        verdict = str(out["verdict"] or "")
        out["packet_eligible"] = bool(
            "promising" in verdict.lower()
            and (out["fpp"] is None or out["fpp"] <= fppmod.FPP_MAX_FOR_PACKET)
        )
    except Exception as exc:
        out["status"] = "error"
        out["error"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}"
    out["timings"]["total"] = time.perf_counter() - t0
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _worker(args):
    row, budget_s, n_draws, do_fpp, do_centroid, out_path = args
    rec = run_one(row, budget_s, n_draws, do_fpp, do_centroid)
    tmp = Path(str(out_path) + ".tmp")
    tmp.write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
    tmp.replace(out_path)
    return rec["tic_id"], rec["cls"], rec["status"], rec["match"], rec["verdict"], rec["fpp"], rec["timings"].get("total")


def run(workers: int, budget_s: float, n_draws: int, do_fpp: bool, force: bool, only_cls: str | None,
        limit: int | None, do_centroid: bool = True) -> None:
    import pandas as pd
    df = pd.read_csv(TARGETS_CSV)
    if only_cls:
        df = df[df["cls"] == only_cls]
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    jobs = []
    for _, r in df.iterrows():
        out_path = RUN_DIR / f"{r['cls']}_tic{int(r['tic_id'])}.json"
        if out_path.exists() and not force:
            continue
        jobs.append((r.to_dict(), budget_s, n_draws, do_fpp, do_centroid, out_path))
    if limit:
        jobs = jobs[:limit]
    print(f"{len(jobs)} job(s) to run with {workers} worker(s)", flush=True)
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_worker, j) for j in jobs]
        for f in as_completed(futs):
            try:
                tic, cls, status, match, verdict, fppv, wall = f.result()
                print(f"  [{cls:6s}] TIC {tic:<11d} {status:13s} {match:14s} {str(verdict):40s} "
                      f"FPP={fppv if fppv is None else round(fppv, 4)} wall={wall:.0f}s  "
                      f"(elapsed {time.perf_counter() - t0:.0f}s)", flush=True)
            except Exception as exc:
                print("  worker crashed:", exc, flush=True)


def reapply() -> None:
    """Recompute every stored result's final verdict from its stored light-curve
    vetting result and its stored centroid / contamination / TRICERATOPS
    outputs, with the current flag rules. No search, no network."""
    from tesshunter.vetting import apply_pixel_checks, vetting_result_from_dict
    from tesshunter import fpp as fppmod
    n = 0
    for p in sorted(RUN_DIR.glob("*.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        vet = rec.get("vetting")
        if not vet or not vet.get("result") or not rec.get("matched"):
            continue
        vr = vetting_result_from_dict(vet["result"])
        # the demoted-SNR entry was a medium flag in earlier code; it is a note now
        vr.medium_flags[:] = [f for f in vr.medium_flags if not (f.startswith("elevated SNR") and "noted" in f)]
        new_verdict = apply_pixel_checks(vr, rec.get("centroid"), rec.get("contamination"),
                                         fpp=rec.get("fpp_result"))
        vet["flags_high"] = list(vr.high_risk_flags)
        vet["flags_medium"] = list(vr.medium_flags)
        vet["notes"] = list(vr.notes)
        vet["verdict"] = new_verdict
        rec["verdict"] = new_verdict
        rec["packet_eligible"] = bool("promising" in new_verdict.lower()
                                      and (rec.get("fpp") is None or rec["fpp"] <= fppmod.FPP_MAX_FOR_PACKET))
        p.write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
        n += 1
    print(f"re-applied the verdict rules to {n} result(s)")


def summarize() -> None:
    import pandas as pd
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RUN_DIR.glob("*.json"))]
    if not recs:
        print("no results")
        return
    df = pd.read_csv(TARGETS_CSV)
    quota = {"planet": N_PLANET, "eb": N_EB, "blend": N_BLEND}

    def bucket(r):
        if r["status"] == "no_data":
            return "no SPOC data"
        if r["status"] == "error":
            return "error"
        if r["match"] == "not detected":
            return "not detected"
        if r["match"] != "recovered":
            return "detected at a harmonic"
        v = (r["verdict"] or "").lower()
        if "false positive" in v:
            return "likely false positive"
        if "ambiguous" in v:
            return "ambiguous"
        if "promising" in v or "unverified" in v:
            return "promising"
        return "other"

    rows = []
    for r in recs:
        b = bucket(r)
        m = r.get("matched") or {}
        fit = m.get("fit") or {}
        cen = r.get("centroid") or {}
        con = r.get("contamination") or {}
        rows.append({"cls": r["cls"], "tic_id": r["tic_id"], "name": r["name"], "tmag": r.get("tmag"),
                     "P_known": r["period_known"], "P_found": m.get("period_days"), "match": r["match"],
                     "bucket": b, "verdict": r.get("verdict"), "verdict_lc_only": r.get("verdict_lc_only"),
                     "data": r.get("data_source"),
                     "centroid_px": cen.get("total_shift_px") if cen.get("available") else None,
                     "centroid_sigma": cen.get("sigma") if cen.get("available") else None,
                     "centroid_flag": cen.get("flagged") if cen.get("available") else None,
                     "contam_flag": con.get("flagged") if con.get("available") else None,
                     "snr": m.get("snr"),
                     "depth_ppt": m.get("depth_ppt"), "rp_rs": fit.get("rp_rs"),
                     "a_rs_ratio": fit.get("a_rs_ratio"), "a_rs_incons": fit.get("a_rs_inconsistent"),
                     "sec_stellar": ((r.get("vetting") or {}).get("result") or {}).get("secondary_is_stellar"),
                     "odd_even": ((r.get("vetting") or {}).get("result") or {}).get("odd_even_mismatch"),
                     "fpp": r.get("fpp"), "nfpp": r.get("nfpp"),
                     "fpp_block": (r.get("fpp") is not None and r["fpp"] > 0.5),
                     "packet": r.get("packet_eligible"),
                     "high": "; ".join((r.get("vetting") or {}).get("flags_high") or [])[:160],
                     "hard": "; ".join((r.get("vetting") or {}).get("flags_hard") or [])[:160],
                     "wall_s": (r.get("timings") or {}).get("total"), "error": (r.get("error") or "")[:120]})
    out = pd.DataFrame(rows)
    out.to_csv(ADV_DIR / "adversarial_results_v1.csv", index=False)

    order = ["promising", "ambiguous", "likely false positive", "detected at a harmonic", "not detected",
             "no SPOC data", "error"]
    cm = out.pivot_table(index="cls", columns="bucket", values="tic_id", aggfunc="count", fill_value=0)
    for c in order:
        if c not in cm.columns:
            cm[c] = 0
    cm = cm[order].reindex(["planet", "eb", "blend"]).fillna(0).astype(int)
    # FPP gate: of the promising ones, how many are blocked
    lines = ["# Adversarial vetting check (prompt 3, part E)", "",
             f"Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} from `{RUN_DIR.relative_to(REPO)}` "
             f"({len(recs)} results; target list `{TARGETS_CSV.relative_to(REPO)}`, seed {SEED}).", "",
             "Truth classes: `planet` = ExoFOP TOI with TFOPWG disposition CP/KP; `eb` = TESS EB catalog "
             "(Prsa et al. 2022, sectors 1-26); `blend` = ExoFOP TOI retired as FP with a nearby / background "
             "EB named in the comment. Each target was searched with SPOC 2-min data (up to 3 sectors) in a "
             "period window of 1/3.2 to 3.2 times the known period; the candidate matching the known period "
             "(or a harmonic) is the one vetted. Verdict buckets are the pipeline's automated verdict on that "
             "candidate; `promising` includes `unverified`.", "",
             "## Confusion matrix (automated verdict, before the FPP gate)", "",
             "| truth | " + " | ".join(order) + " | n |", "|---|" + "---:|" * (len(order) + 1)]
    for cls in ["planet", "eb", "blend"]:
        r = cm.loc[cls]
        lines.append(f"| {cls} | " + " | ".join(str(int(r[c])) for c in order) + f" | {int(r.sum())} |")
    lines += ["", "## With the TRICERATOPS gate (FPP <= 0.5 required for a packet)", "",
              "| truth | promising and FPP <= 0.5 (packet) | promising but FPP > 0.5 | FPP unavailable among promising |",
              "|---|---:|---:|---:|"]
    for cls in ["planet", "eb", "blend"]:
        sub = out[(out["cls"] == cls) & (out["bucket"] == "promising")]
        n_pk = int(((sub["fpp"].notna()) & (sub["fpp"] <= 0.5)).sum())
        n_bl = int(((sub["fpp"].notna()) & (sub["fpp"] > 0.5)).sum())
        n_na = int(sub["fpp"].isna().sum())
        lines.append(f"| {cls} | {n_pk} | {n_bl} | {n_na} |")
    lines += ["", "## Per-target results", ""]
    cols = ["cls", "name", "tic_id", "tmag", "data", "P_known", "P_found", "match", "bucket", "verdict_lc_only",
            "snr", "depth_ppt", "rp_rs", "a_rs_ratio", "a_rs_incons", "sec_stellar", "odd_even",
            "centroid_px", "centroid_sigma", "centroid_flag", "contam_flag", "fpp", "nfpp", "packet", "high", "hard"]
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "---|" * len(cols))
    for _, r in out.sort_values(["cls", "bucket"]).iterrows():
        def fmt(v):
            if v is None or (isinstance(v, float) and v != v):
                return ""
            if isinstance(v, float):
                return f"{v:.4g}"
            return str(v).replace("|", "/")
        lines.append("| " + " | ".join(fmt(r[c]) for c in cols) + " |")
    errs = out[out["error"] != ""]
    if len(errs):
        lines += ["", "## Errors / no data", ""]
        for _, r in errs.iterrows():
            lines.append(f"* {r['cls']} TIC {r['tic_id']}: {r['error']}")
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(cm.to_string())
    print(f"wrote {DOC_PATH}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-list", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--summarize", action="store_true")
    ap.add_argument("--reapply", action="store_true",
                    help="recompute stored verdicts with the current flag rules (no search, no network)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--budget", type=float, default=900.0)
    ap.add_argument("--n-draws", type=int, default=100_000)
    ap.add_argument("--no-fpp", action="store_true")
    ap.add_argument("--no-centroid", action="store_true", help="skip the centroid and contamination checks")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default=None, help="planet | eb | blend")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--redo-no-data", action="store_true",
                    help="delete results with status no_data / error before running, so they are retried")
    ap.add_argument("--redo-network-errors", action="store_true",
                    help="delete results whose TRICERATOPS or TPF step failed on a network error, so they are retried")
    args = ap.parse_args()
    if args.build_list:
        build_list()
    if args.redo_no_data or args.redo_network_errors:
        for p in RUN_DIR.glob("*.json"):
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
                st = rec.get("status")
            except Exception:
                rec, st = {}, "error"
            fe = (rec.get("fpp_result") or {}).get("error") or ""
            cen = rec.get("centroid") or {}
            cen_note = "" if cen.get("available") else (cen.get("note") or "")
            net = any(k in (fe + cen_note + (rec.get("centroid_error") or ""))
                      for k in ("Timeout", "Connection", "IncompleteRead", "No space", "HTTP"))
            if (args.redo_no_data and st in ("no_data", "error")) or (args.redo_network_errors and net):
                p.unlink()
                print("removed", p.name, st, (fe or cen_note)[:60])
    if args.run:
        run(args.workers, args.budget, args.n_draws, not args.no_fpp, args.force, args.only, args.limit,
            do_centroid=not args.no_centroid)
    if args.reapply:
        reapply()
    if args.summarize:
        summarize()
    return 0


if __name__ == "__main__":
    sys.exit(main())
