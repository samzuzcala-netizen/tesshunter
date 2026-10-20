"""S1 phase planner (evaluator side): job lists ``D:/tesshunter_s1/jobs/<phase>_jobs.json`` and runtimes
``D:/tesshunter_s1/runtimes/s1_b<n>_<stage>/`` for ``controller_s1.py``.  Logic of ``k2/protocol/plan_k2.py``
(funnel_runtime, siblings_for, plan_d) and ``k1/protocol/plan_k1.py`` (star_block, collect) with S1 roots; the frozen
K2 configuration (``k2/protocol/config.json``) supplies the S mode, the C variant, the A1 scope and M1.

Every stage plans only the jobs whose result does not exist yet, so a smoke subset and the rest of its batch share
one run folder, one funnel label (``s1_b<n>``) and one receipt tree.

  refresh <label>                         snapshot-day list refresh (part5_k2.refresh logic) -> s1/survey
  download <phase> <batch> [--attempt k] [--first n] [--only-missing]
  search <phase> <batch> [--first n]
  collect <batch>
  funnel <phase> <A|S|B|C> <batch> [--first n] [--s-closed]
  neighbours <round> <batch> [--first n]  bulk SIMBAD + VSX (<round>_bulk) and per-star Gaia (<round>) jobs
  d <phase> <batch> [--first n]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from s1_common import (REPO, S1, S1_DATA, K1, K2, STORE, RUNS, RECEIPTS, FUNNEL, RUNTIMES, NEIGHBOURS, JOBS, TARGETS,
                       batch_frame, read, write, sha, utc)

FROZEN = read(K2 / "protocol" / "config.json")
S_MODE = FROZEN["s_mode"]                      # bound_alias
C_VARIANT = FROZEN["c_variant"]                # V3
A1_SCOPE = FROZEN["a1_scope"]                  # None
M1 = bool(FROZEN["m1"])                        # True
PRESET = FROZEN["preset"]                      # survey_k1
BUDGET = float(FROZEN["time_budget_s"])        # 8100
CATALOGUE = "20261015"                         # launch-day snapshot (D:/tesshunter_s1/catalogs/snap_20261015)
DEADLINES = {"download": 900, "search": BUDGET * 1.6 + 900, "A": 1800, "S": 600, "B": 600, "C": 14400, "D": 5400,
             "nb_bulk": 1800, "nb": 900}
FUNNEL_PINS = ["funnel_k2.py", "c_input_k2.py", "funnel_k1.py"]
D_PINS = ["stage_d_worker_k1.py", "stage_d_packets_k1.py", "stage_d_pixels_k1.py", "rules_k1.py", "funnel_k1.py"]
LIST_PIN = "s1/survey/targets_s1.csv"


def label(batch: int) -> str:
    return f"s1_b{int(batch)}"


def stars(batch: int, first: int | None = None) -> pd.DataFrame:
    df = batch_frame(batch)
    return df.head(first) if first else df


def write_jobs(phase: str, jobs: list) -> dict:
    write(JOBS / f"{phase}_jobs.json", jobs, replace=True)
    return {"phase": phase, "jobs": len(jobs)}


# ── download / search / collect ───────────────────────────────────────────────
def download_state(tic: int) -> str:
    """complete | incomplete | none, from the star's index.json (n_failed = 0 and >= 1 usable product = complete)."""
    p = STORE / f"tic{int(tic)}" / "index.json"
    if not p.exists():
        return "none"
    idx = read(p)
    if idx.get("n_failed", 1) == 0 and idx.get("n_products", 0) > 0:
        return "complete"
    return "no_products" if idx.get("n_failed", 1) == 0 else "incomplete"


def plan_download(phase, batch, attempt=1, first=None, only_missing=False, deadline=None):
    jobs = []
    for t in stars(batch, first).tic_id.astype("int64"):
        if only_missing and download_state(t) == "complete":
            continue
        rp = S1_DATA / "download_receipts" / phase / f"tic{t}.json"
        jobs.append({"job_id": f"dl_{t}", "arguments": ["download_s1.py", str(t), str(attempt), label(batch), "--receipt", str(rp)],
                     "result_path": str(rp), "deadline_s": deadline or DEADLINES["download"], "online": True,
                     "pins": ["download_k1.py", LIST_PIN]})
    return write_jobs(phase, jobs)


def open_phase_jobs(pattern: str) -> set:
    """Job ids of the open phases matching ``pattern`` (an owner file exists): never plan a job twice."""
    out = set()
    for owner in (S1 / "manifests").glob(f"owner_{pattern}.json"):
        phase = owner.stem[len("owner_"):]
        launch = S1_DATA / "controllers" / phase / "launch.json"
        if launch.exists():
            out |= {j["job_id"] for j in read(launch)["frozen_jobs"]}
    return out


def plan_search(phase, batch, first=None):
    from plan_k1 import star_block
    run = RUNS / label(batch)
    busy = open_phase_jobs("*")
    jobs, skipped = [], {}
    for _, r in stars(batch, first).iterrows():
        tic = int(r.tic_id)
        job_id = f"s1_{tic}"
        state = download_state(tic)
        if state != "complete":
            skipped[state] = skipped.get(state, 0) + 1
            continue
        if (run / "results" / f"{job_id}.json").exists():
            skipped["searched"] = skipped.get("searched", 0) + 1
            continue
        if job_id in busy:
            skipped["in_open_phase"] = skipped.get("in_open_phase", 0) + 1
            continue
        rt = {"job_id": job_id, "tic_id": tic, "preset": PRESET, "star": star_block(r), "lc_root": str(STORE),
              "cache_dir": str(S1_DATA / "stitched" / "clean"), "run_dir": str(run),
              "overrides": {"time_budget_s": BUDGET}, "use": label(batch)}
        path = RUNTIMES / f"{label(batch)}_search" / f"{job_id}.json"
        write(path, rt, replace=True)
        jobs.append({"job_id": job_id, "arguments": ["search_s1.py", str(path)],
                     "result_path": str(run / "receipts" / f"{job_id}.json"), "deadline_s": DEADLINES["search"],
                     "online": False, "pins": ["search_worker_k1.py", "download_k1.py", LIST_PIN]})
    out = write_jobs(phase, jobs)
    out["skipped"] = skipped
    return out


def collect(batch):
    import plan_k1
    if plan_k1.RUNS.resolve() != RUNS.resolve():
        raise RuntimeError("plan_k1 does not point at the S1 runs")
    return plan_k1.collect(label(batch))


# ── funnel A / S / B / C ──────────────────────────────────────────────────────
def receipts(lab: str, stage: str) -> dict:
    out = {}
    for p in (RECEIPTS / lab / stage).glob("*.json"):
        r = read(p)
        out[r["candidate_id"]] = r
    return out


def funnel_runtime(cands, search_rt, cid, lab, *, siblings=None):
    """plan_k2.funnel_runtime with S1 roots: one case root per candidate for A/S/B/C, the S1 neighbour record."""
    r = cands[cands.candidate_id == cid].iloc[0]
    allc = cands[cands.job_id == r.job_id]
    clean = lambda x: {k: (None if (isinstance(v, float) and not np.isfinite(v)) else v) for k, v in x.items()  # noqa: E731
                       if k not in ("job_id", "candidate_id", "passes_pregate")}
    root = str(FUNNEL / lab / cid)
    return {"candidate_id": cid, "tic_id": int(r.tic_id), "candidate": clean(r.to_dict()),
            "all_candidates": [clean(x) for x in allc.to_dict(orient="records")], "star": search_rt["star"],
            "lc_root": search_rt["lc_root"], "root": root, "preset": search_rt["preset"], "s_mode": S_MODE,
            "ramp_variant": False, "label": lab, "use": search_rt.get("use"), "tls_threads": 4,
            "neighbours_path": str(NEIGHBOURS / f"tic{int(r.tic_id)}.json"), "k2_c_variant": C_VARIANT,
            "k2_siblings": siblings or [], "k2_a1_scope": A1_SCOPE,
            # the A/S/B case root itself: funnel_k2 copies only into a root that does not exist yet, so C runs on the
            # prepared series and records of its own A/S/B case root (as the fresh-set fr_k1 C jobs did)
            "k2_copy_from": root}


def plan_funnel(phase, stage, batch, first=None, s_closed=False):
    import plan_k2 as PK
    lab = label(batch)
    run = RUNS / lab
    cands = pd.read_csv(run / "candidates.csv")
    if first:
        keep = {f"s1_{int(t)}" for t in stars(batch, first).tic_id}
        cands = cands[cands.job_id.isin(keep)]
    srt = {read(p)["job_id"]: read(p) for p in (RUNTIMES / f"{lab}_search").glob("*.json")}
    rec = {st: receipts(lab, st) for st in ("A", "S", "B", "C")}
    ok = lambda st, c: (rec[st].get(c) or {}).get("status") == "COMPLETE" and (rec[st].get(c) or {}).get("decision") == "PASS"  # noqa: E731
    gate = lambda c: ((rec["S"].get(c) or {}).get("gate_by_mode") or {}).get(S_MODE)  # noqa: E731
    if stage == "C" and not s_closed:
        a_pass = [c for c in cands.candidate_id if ok("A", c)]
        missing = [c for c in a_pass if c not in rec["S"]]
        if missing:
            raise SystemExit(f"C planned before every S job closed: {len(missing)} A passes without an S receipt "
                             f"({missing[:5]}); rerun with --s-closed once the S retry has closed")
    busy = open_phase_jobs("*")
    rts, skipped = [], {"done": 0, "no_neighbours": 0, "in_open_phase": 0}
    for r in cands.itertuples():
        cid = r.candidate_id
        if cid in rec[stage]:
            skipped["done"] += 1
            continue
        if f"{stage}_{lab}_{cid}" in busy:
            skipped["in_open_phase"] += 1
            continue
        if stage == "A" and not r.passes_pregate:
            continue
        if stage == "S" and not ok("A", cid):
            continue
        if stage == "B":
            if not (ok("A", cid) and gate(cid) in ("PASS", "HOLD")):
                continue
            if not (NEIGHBOURS / f"tic{int(r.tic_id)}.json").exists():
                skipped["no_neighbours"] += 1
                continue
        if stage == "C" and not ok("B", cid):
            continue
        sib = PK.siblings_for(cid, cands, rec["S"], rec["A"]) if (stage == "C" and M1) else []
        rts.append(funnel_runtime(cands, srt[r.job_id], cid, lab, siblings=sib))
    jobs = []
    for rt in rts:
        path = RUNTIMES / f"{lab}_{stage}" / f"{rt['candidate_id']}.json"
        write(path, rt, replace=True)
        jobs.append({"job_id": f"{stage}_{lab}_{rt['candidate_id']}", "arguments": ["funnel_k2.py", stage, str(path)],
                     "result_path": str(RECEIPTS / lab / stage / f"{rt['candidate_id']}.json"),
                     "deadline_s": DEADLINES[stage], "online": False, "pins": FUNNEL_PINS})
    out = write_jobs(phase, jobs)
    out.update(skipped=skipped, with_siblings=sum(bool(rt["k2_siblings"]) for rt in rts))
    return out


# ── neighbours (stars with a bound_alias S PASS/HOLD) ─────────────────────────
def plan_neighbours(round_, batch, first=None):
    lab = label(batch)
    a, s = receipts(lab, "A"), receipts(lab, "S")
    want = sorted({int(r["tic_id"]) for c, r in s.items()
                   if (r.get("gate_by_mode") or {}).get(S_MODE) in ("PASS", "HOLD")
                   and (a.get(c) or {}).get("decision") == "PASS"})
    if first:
        allowed = set(stars(batch, first).tic_id.astype("int64"))
        want = [t for t in want if t in allowed]
    want = [t for t in want if not (NEIGHBOURS / f"tic{t}.json").exists()]
    tg = pd.read_csv(TARGETS, low_memory=False, dtype={"GAIA": str})
    sub = tg[tg.tic_id.isin(want)]
    form = pd.DataFrame({"tic_id": sub.tic_id, "ra_deg": sub.ra, "dec_deg": sub.dec, "tmag": sub.Tmag, "teff_k": sub.Teff,
                         "radius_rsun": sub.rad, "mass_msun": sub["mass"].fillna(sub.rad), "tic_gaia_id": sub.GAIA})
    targets = S1_DATA / "hosts" / f"neighbours_{round_}.csv"
    targets.parent.mkdir(parents=True, exist_ok=True)
    form.to_csv(targets, index=False)
    rec = S1_DATA / "neighbour_receipts" / round_
    bulk = [{"job_id": f"nb_{round_}_{k}", "arguments": ["neighbours_k1.py", k, "--targets", str(targets), "--label", round_,
                                                         "--receipt", str(rec / f"{k}.json")],
             "result_path": str(rec / f"{k}.json"), "deadline_s": DEADLINES["nb_bulk"], "online": True,
             "pins": ["neighbours_k1.py"]} for k in ("simbad", "vsx")] if want else []
    per = [{"job_id": f"nb_{t}", "arguments": ["neighbours_k1.py", str(t), "--targets", str(targets), "--label", round_,
                                                "--receipt", str(rec / f"tic{t}.json")],
            "result_path": str(rec / f"tic{t}.json"), "deadline_s": DEADLINES["nb"], "online": True,
            "pins": ["neighbours_k1.py"]} for t in want]
    write_jobs(f"{round_}_bulk", bulk)
    write_jobs(round_, per)
    return {"bulk_phase": f"{round_}_bulk", "phase": round_, "stars": len(want), "targets": str(targets)}


# ── Stage D (real hard stop, launch snapshot) ─────────────────────────────────
def plan_d(phase, batch, first=None, n_draws=100000):
    import catalog_adapter_k1 as CA
    lab = label(batch)
    cat = CA.load(CATALOGUE)
    if cat.snap.resolve() != (S1_DATA / "catalogs" / f"snap_{CATALOGUE}").resolve():
        raise RuntimeError("catalogue adapter does not point at the S1 launch snapshot")
    allowed = {f"s1_{int(t)}" for t in stars(batch, first).tic_id} if first else None
    done = receipts(lab, "D")
    busy = open_phase_jobs("*")      # never plan a D job that an open phase still holds (2026-10-18 D2/D3 incident)
    jobs = []
    for cid, rec in sorted(receipts(lab, "C").items()):
        if rec.get("decision") != "PASS" or rec.get("status") != "COMPLETE" or cid in done:
            continue
        if f"D_{lab}_{cid}" in busy:
            continue
        if allowed is not None and cid.rsplit("_p", 1)[0] not in allowed:
            continue
        crt = read(RUNTIMES / f"{lab}_C" / f"{cid}.json")
        cand = crt["candidate"]
        tic, period = int(crt["tic_id"]), float(cand["period_days"])
        st = crt["star"]
        xm = CA.crossmatch_record(cat, tic, st["ra_deg"], st["dec_deg"])
        rt = {"candidate_id": cid, "key": f"tic{tic}_P{period:.4f}", "tic_id": tic, "period": period,
              "depth_ppt": float(cand["depth_ppt"]), "root": crt["root"], "lc_root": crt["lc_root"],
              # the C runtime's own S mode (the rules stamp p10.0 vs p10.0-partial must match the case root)
              "preset": crt["preset"], "s_mode": crt.get("s_mode") or S_MODE, "crossmatch_star": xm,
              "tce_sidecar": xm.get("tce_sidecar"), "star": st, "neighbours_path": crt["neighbours_path"],
              "n_draws": int(n_draws), "label": lab, "use": crt.get("use"), "redact_catalogue": False,
              "job": {"rank": 0, "tic_id": tic, "period": period, "depth_ppt": float(cand["depth_ppt"])},
              "candidate": cand, "all_candidates": crt["all_candidates"], "ramp_variant": False}
        path = RUNTIMES / f"{lab}_D" / f"{cid}.json"
        write(path, rt, replace=True)
        jobs.append({"job_id": f"D_{lab}_{cid}", "arguments": ["stage_d_worker_k1.py", str(path)],
                     "result_path": str(RECEIPTS / lab / "D" / f"{cid}.json"), "deadline_s": DEADLINES["D"],
                     "online": True, "pins": D_PINS})
    return write_jobs(phase, jobs)


# ── launch-day list refresh (k2/protocol/part5_k2.refresh logic) ──────────────
def refresh(snap_label: str) -> dict:
    import catalog_adapter_k1 as CA
    sv2, sv1 = K2 / "survey", S1 / "survey"
    sv1.mkdir(parents=True, exist_ok=True)
    tg = pd.read_csv(sv2 / "targets_k2.csv", low_memory=False, dtype={"GAIA": str})
    rs = pd.read_csv(sv2 / "reserve_k2.csv", low_memory=False, dtype={"GAIA": str})
    ledger = set()
    for p in (K1 / "manifests" / "exposure_ledger.csv", K2 / "manifests" / "exposure_ledger_k2.csv"):
        led = pd.read_csv(p, dtype=str)
        ledger |= set(pd.to_numeric(led.tic_id, errors="coerce").dropna().astype("int64"))
    exposed = sorted(int(t) for t in set(tg.tic_id.astype("int64")) & ledger)
    if exposed:
        raise SystemExit(f"survey-list stars in a preparation exposure ledger: {exposed[:10]}")
    cat = CA.K1Catalog(S1_DATA / "catalogs" / f"snap_{snap_label}")
    chk = cat.check_many(tg)
    drop = tg[chk.xmatch_status == "REJECT"].assign(reason=chk.xmatch_reject_sources[chk.xmatch_status == "REJECT"])
    keep = tg[chk.xmatch_status != "REJECT"].copy()
    is_em = lambda df: df.k1_type.eq("M_early") if "k1_type" in df else df.k1_class.eq("eM")  # noqa: E731
    need = {"eM": 3000 - int(is_em(keep).sum()), "K": 7000 - int((~is_em(keep)).sum())}
    rs = rs.sort_values("rank")
    rchk = cat.check_many(rs)
    cand = rs[(rchk.xmatch_status != "REJECT") & ~rs.tic_id.astype("int64").isin(ledger) & ~rs.tic_id.isin(keep.tic_id)]
    add = pd.concat([cand[is_em(cand)].head(max(0, need["eM"])), cand[~is_em(cand)].head(max(0, need["K"]))])
    # operational: the reserve carries no ``slice`` column; a refilled star takes its own slice (K2's refresh never
    # added a star, so its sort never met this case)
    add = add.assign(slice=np.where(is_em(add), "eM_slice", "K"))
    new = pd.concat([keep, add], ignore_index=True)
    new = new.assign(_o=new.slice.ne("K").astype(int)).sort_values(["_o", "rank"]).drop(columns="_o").reset_index(drop=True)
    new.to_csv(sv1 / "targets_s1.csv", index=False)
    rs[~rs.tic_id.isin(add.tic_id)].to_csv(sv1 / "reserve_s1.csv", index=False)
    side = cat.tce_sidecar(new.tic_id.astype("int64"))
    side.to_csv(sv1 / "tce_sidecar_s1.csv", index=False)
    fchk = cat.check_many(new)
    same = bool(len(new) == len(tg) and (new.tic_id.values == tg.tic_id.values).all())
    if same and add.empty:
        # unchanged list: keep the frozen K2 files byte for byte (pandas re-writes a few floats at the 17th digit)
        import shutil
        shutil.copyfile(sv2 / "targets_k2.csv", sv1 / "targets_s1.csv")
        shutil.copyfile(sv2 / "reserve_k2.csv", sv1 / "reserve_s1.csv")
    man = {"utc": utc(), "snapshot": snap_label, "base_list": "k2/survey/targets_k2.csv", "n_before": int(len(tg)),
           "dropped": drop[["tic_id", "slice", "rank", "reason"]].to_dict(orient="records"),
           "dropped_by_reason": drop.reason.value_counts().to_dict(),
           "added": add[["tic_id", "slice", "rank"]].to_dict(orient="records"),
           "n_after": int(len(new)), "n_eM": int(is_em(new).sum()), "n_K": int((~is_em(new)).sum()),
           "identical_to_k2_frozen_list": same, "status_after": fchk.xmatch_status.value_counts().to_dict(),
           "spoc_tce_flagged": int(fchk.spoc_tce.sum()), "preparation_ledger_overlap": exposed,
           "targets_sha256": sha(sv1 / "targets_s1.csv"), "k2_targets_sha256": sha(sv2 / "targets_k2.csv"),
           "tce_sidecar_sha256": sha(sv1 / "tce_sidecar_s1.csv"), "tce_sidecar_rows": int(len(side))}
    write(S1 / "manifests" / f"target_refresh_{snap_label}.json", man, replace=True)
    return man


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refresh"); r.add_argument("label")
    d = sub.add_parser("download"); d.add_argument("phase"); d.add_argument("batch", type=int)
    d.add_argument("--attempt", type=int, default=1); d.add_argument("--first", type=int); d.add_argument("--only-missing", action="store_true")
    d.add_argument("--deadline", type=float)
    s = sub.add_parser("search"); s.add_argument("phase"); s.add_argument("batch", type=int); s.add_argument("--first", type=int)
    c = sub.add_parser("collect"); c.add_argument("batch", type=int)
    f = sub.add_parser("funnel"); f.add_argument("phase"); f.add_argument("stage", choices=["A", "S", "B", "C"])
    f.add_argument("batch", type=int); f.add_argument("--first", type=int); f.add_argument("--s-closed", action="store_true")
    n = sub.add_parser("neighbours"); n.add_argument("round"); n.add_argument("batch", type=int); n.add_argument("--first", type=int)
    dd = sub.add_parser("d"); dd.add_argument("phase"); dd.add_argument("batch", type=int); dd.add_argument("--first", type=int)
    a = ap.parse_args()
    if a.cmd == "refresh":
        out = refresh(a.label)
        out = {k: v for k, v in out.items() if k not in ("dropped", "added")} | {"n_dropped": len(out["dropped"]), "n_added": len(out["added"])}
    elif a.cmd == "download":
        out = plan_download(a.phase, a.batch, a.attempt, a.first, a.only_missing, a.deadline)
    elif a.cmd == "search":
        out = plan_search(a.phase, a.batch, a.first)
    elif a.cmd == "collect":
        out = collect(a.batch)
    elif a.cmd == "funnel":
        out = plan_funnel(a.phase, a.stage, a.batch, a.first, a.s_closed)
    elif a.cmd == "neighbours":
        out = plan_neighbours(a.round, a.batch, a.first)
    else:
        out = plan_d(a.phase, a.batch, a.first)
    print(json.dumps(out, indent=1, default=str))
