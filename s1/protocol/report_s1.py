"""S1 batch report (prompt S1 section 5; evaluator side, read-only on the data): ``s1/results/BATCH_<n>.md`` and
``s1/results/batch_<n>.json``.

Counts every stage of batch ``n`` from the receipts (label ``s1_b<n>``), the phase closures (``s1_b<n>_*``), the
partition-limited fraction of the search, the Stage C wall distribution, the disk accounting (``s1/work/disk_s1.py``),
the queue-hours against the plan, and the SUBMIT / HOLD candidate table (TIC, slice, period, depth, SNR, tier, deciding
condition, TCE flag, packet, "pixel coverage incomplete" when a Stage D centroid sector has source ``none``).  Labels
are candidates for the user's review, never detections.
CLI: ``report_s1.py <batch> [--first n] [--title "..."]``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from s1_common import S1, S1_DATA, RUNS, RECEIPTS, RUNTIMES, FUNNEL, CONTROLLERS, batch_frame, read, utc

PLAN_QH_PER_BATCH = 120.0
CPU_STAGES = ("search", "A", "C")
#: S-P as decided by the user before batch 1 (s1/manifests/decision_prelaunch.json): pause when the partition-limited
#: fraction exceeds the sector-matched expectation (K1/K2 rate per n_units bin) by more than 10 pp.
_SP = read(S1 / "manifests" / "decision_prelaunch.json")["s_p_rule"]
SP_BINS = ((0, 8, 0.000), (8, 13, 0.000), (13, 20, 0.034), (20, 30, 0.402), (30, 37, 0.586), (37, 10**6, 0.473))
SP_MARGIN = 0.10
if [round(b["rate"], 3) for b in _SP["bins"]] != [r for _, _, r in SP_BINS]:
    raise RuntimeError("S-P table differs from s1/manifests/decision_prelaunch.json")


def sp_rate(n_units: int) -> float:
    return next(r for lo, hi, r in SP_BINS if lo <= int(n_units) < hi)


def receipts(lab, stage):
    out = {}
    for p in (RECEIPTS / lab / stage).glob("*.json"):
        r = read(p)
        out[r["candidate_id"]] = r
    return out


def phases(batch):
    rows = []
    for d in sorted(CONTROLLERS.glob(f"s1_b{batch}_*")):
        c = read(d / "closure.json") if (d / "closure.json").exists() else None
        p = read(d / "progress.json") if (d / "progress.json").exists() else {}
        src = c or p
        rows.append({"phase": d.name, "status": src.get("status"), "total": src.get("total"), "complete": src.get("complete"),
                     "unknowns": src.get("unknowns"), "wall_hours": round(float(src.get("wall_hours") or 0), 2),
                     "job_wall_hours": round(float((c or {}).get("job_wall_hours") or 0), 2), "retry_of": (c or {}).get("retry_of")})
    return pd.DataFrame(rows)


def stage_of(phase):
    for key, st in (("_dl", "download"), ("_search", "search"), ("_nb", "neighbours"), ("_A", "A"), ("_S", "S"),
                    ("_B", "B"), ("_C", "C"), ("_D", "D")):
        if key in phase:
            return st
    return "other"


def pixel_gap(case_root: str, key: str):
    p = Path(case_root) / "expensive" / f"{key}.json"
    if not p.exists():
        return None
    per = ((read(p).get("centroid") or {}).get("per_sector")) or []
    none = [s.get("sector") for s in per if s.get("source") == "none"]
    return {"n_sectors": len(per), "none": none}


def build(batch, first=None, title=None):
    import catalog_adapter_k1 as CA
    lab = f"s1_b{batch}"
    stars = batch_frame(batch)
    if first:
        stars = stars.head(first)
    tics = set(stars.tic_id.astype("int64"))
    slice_of = dict(zip(stars.tic_id.astype("int64"), stars.slice))
    jobs = {f"s1_{t}" for t in tics}
    run = RUNS / lab
    sr = [read(p) for p in (run / "receipts").glob("*.json")] if (run / "receipts").exists() else []
    sr = [r for r in sr if r["job_id"] in jobs]
    cands = pd.read_csv(run / "candidates.csv") if (run / "candidates.csv").exists() else pd.DataFrame(columns=["job_id"])
    cands = cands[cands.job_id.isin(jobs)]
    rec = {st: {c: r for c, r in receipts(lab, st).items() if c.rsplit("_p", 1)[0] in jobs} for st in "ASBCD"}
    dec = lambda st, v: sum((r.get("status") == "COMPLETE" and r.get("decision") == v) for r in rec[st].values())  # noqa: E731
    unk = lambda st: sum(r.get("status") != "COMPLETE" for r in rec[st].values())  # noqa: E731
    gate = [((r.get("gate_by_mode") or {}).get("bound_alias")) for r in rec["S"].values() if r.get("status") == "COMPLETE"]
    dv = [((r.get("verdicts") or {}).get("k1.0") or {}).get("verdict") for r in rec["D"].values() if r.get("status") == "COMPLETE"]
    # download states
    from plan_s1 import download_state
    dstate = pd.Series([download_state(t) for t in tics]).value_counts().to_dict()
    counts = {"stars": len(tics), "download": dstate,
              "searched_complete": sum(r["status"] == "COMPLETE" for r in sr),
              "search_unknown": sum(r["status"] != "COMPLETE" for r in sr),
              "accepted_candidates": int(len(cands)), "pregate": int(cands.passes_pregate.sum()) if len(cands) else 0,
              "A_jobs": len(rec["A"]), "A_pass": dec("A", "PASS"), "A_unknown": unk("A"),
              "S_jobs": len(rec["S"]), "S_bound_alias": {k: gate.count(k) for k in ("PASS", "HOLD", "FAIL")}, "S_unknown": unk("S"),
              "B_jobs": len(rec["B"]), "B_pass": dec("B", "PASS"), "B_unknown": unk("B"),
              "C_jobs": len(rec["C"]), "C_pass": dec("C", "PASS"), "C_unknown": unk("C"),
              "D_jobs": len(rec["D"]), "D": {k: dv.count(k) for k in ("SUBMIT", "HOLD", "KILL")}, "D_unknown": unk("D")}
    part = [r.get("budget_exhausted_partitions", 0) > 0 for r in sr if r["status"] == "COMPLETE"]
    sp_exp = [sp_rate(r.get("n_units") or 0) for r in sr if r["status"] == "COMPLETE"]
    walls = {"search_s": [r["wall_seconds"] for r in sr if r["status"] == "COMPLETE"],
             "C_s": [r["wall_seconds"] for r in rec["C"].values() if r.get("wall_seconds") is not None]}
    cw = np.array(walls["C_s"]) if walls["C_s"] else np.array([])
    cdist = ({"n": int(cw.size), "min": float(cw.min()), "median": float(np.median(cw)), "p90": float(np.percentile(cw, 90)),
              "max": float(cw.max()), "over_4h": int((cw > 14400).sum()), "over_4h_frac": float((cw > 14400).mean())}
             if cw.size else {"n": 0})
    ph = phases(batch)
    if len(ph):
        ph["stage"] = ph.phase.map(stage_of)
    qh = ph.groupby("stage").wall_hours.sum().round(2).to_dict() if len(ph) else {}
    # candidates
    cat = CA.load("20261015")
    rows = []
    for cid, r in sorted(rec["D"].items()):
        v = ((r.get("verdicts") or {}).get("k1.0")) or {}
        if v.get("verdict") not in ("SUBMIT", "HOLD"):
            continue
        drt = read(RUNTIMES / f"{lab}_D" / f"{cid}.json")
        c = cands[cands.candidate_id == cid].iloc[0] if (cands.candidate_id == cid).any() else None
        tce = drt.get("tce_sidecar") or []
        veto = CA.tce_period_veto(float(drt["period"]), tce) if tce else {"veto": False}
        gap = pixel_gap(drt["root"], drt["key"])
        rows.append({"candidate_id": cid, "tic_id": int(r["tic_id"]), "slice": slice_of.get(int(r["tic_id"])),
                     "verdict": v["verdict"], "tier": v.get("candidate_tier"), "deciding_condition": v.get("deciding_condition"),
                     "not_measurable": ",".join(v.get("not_measurable") or []),
                     "period_d": round(float(drt["period"]), 5), "depth_ppt": round(float(drt["depth_ppt"]), 3),
                     "stitch_snr": round(float(c.stitch_snr), 1) if c is not None else None,
                     "hard_stop": (drt.get("crossmatch_star") or {}).get("status"),
                     "tce": (f"{len(tce)} TCE" + (f", period veto (x{veto['ratio']})" if veto.get("veto") else "")) if tce else "none",
                     "pixel_coverage_incomplete": bool(gap and gap["none"]),
                     "pixel_none_sectors": ",".join(str(s) for s in (gap or {}).get("none", [])),
                     "packet": r.get("packet")})
    kills = pd.Series([((r.get("verdicts") or {}).get("k1.0") or {}).get("deciding_condition") for r in rec["D"].values()
                       if ((r.get("verdicts") or {}).get("k1.0") or {}).get("verdict") == "KILL"]).value_counts().to_dict()
    sh = counts["D"]["SUBMIT"] + counts["D"]["HOLD"]
    out = {"utc": utc(), "batch": batch, "first": first, "title": title, "counts": counts,
           "partition_limited_fraction": float(np.mean(part)) if part else None, "partition_limited_n": int(sum(part)),
           "sp_expected": float(np.mean(sp_exp)) if sp_exp else None,
           "sp_fires": bool(part and np.mean(part) > np.mean(sp_exp) + SP_MARGIN),
           "search_wall_s": {"median": float(np.median(walls["search_s"])) if walls["search_s"] else None,
                             "max": float(max(walls["search_s"])) if walls["search_s"] else None},
           "stage_c_walls": cdist, "kill_by_condition": kills,
           "submit_hold_per_1000": 1000.0 * sh / max(counts["searched_complete"], 1),
           "eM_submit_hold": sum(1 for r in rows if r["slice"] == "eM_slice"),
           "phase_wall_hours_by_stage": qh, "phases": ph.to_dict(orient="records") if len(ph) else [],
           "candidates": rows}
    return out


def markdown(res, disk=None):
    c = res["counts"]
    L = [f"# BATCH_{res['batch']}{(' - ' + res['title']) if res['title'] else ''}", "",
         f"Generated {res['utc'][:16]}Z by `s1/protocol/report_s1.py`.  Tags: [M] measured, [I] interpretation.  "
         "SUBMIT / HOLD are candidates for the user's review, not detections; nothing was uploaded or submitted.", "",
         "## Stars and unknowns [M]", "",
         f"* stars: {c['stars']}; download states: {c['download']}",
         f"* searched (COMPLETE): {c['searched_complete']}; search unknowns: {c['search_unknown']}",
         f"* partition-limited fraction: {res['partition_limited_fraction'] if res['partition_limited_fraction'] is None else round(100 * res['partition_limited_fraction'], 1)}% "
         f"({res['partition_limited_n']} stars); sector-matched expectation "
         f"{'n/a' if res['sp_expected'] is None else round(100 * res['sp_expected'], 1)}%; S-P (expectation + 10 pp, user decision "
         f"2026-10-16) {'**FIRES**' if res['sp_fires'] else 'not triggered'}", "",
         "| phase | stage | status | complete / total | unknowns | wall h |", "|---|---|---|---|---|---|"]
    for p in res["phases"]:
        L.append(f"| {p['phase']} | {p.get('stage')} | {p['status']} | {p['complete']} / {p['total']} | {p['unknowns']} | {p['wall_hours']} |")
    L += ["", "## Funnel counts [M]", "",
          "| stage | jobs | pass | unknown |", "|---|---|---|---|",
          f"| search -> accepted / pre-gate | {c['searched_complete']} | {c['accepted_candidates']} accepted, {c['pregate']} pre-gate | {c['search_unknown']} |",
          f"| A | {c['A_jobs']} | {c['A_pass']} | {c['A_unknown']} |",
          f"| S (bound_alias) | {c['S_jobs']} | PASS {c['S_bound_alias']['PASS']}, HOLD {c['S_bound_alias']['HOLD']} | {c['S_unknown']} |",
          f"| B | {c['B_jobs']} | {c['B_pass']} | {c['B_unknown']} |",
          f"| C | {c['C_jobs']} | {c['C_pass']} | {c['C_unknown']} |",
          f"| D | {c['D_jobs']} | SUBMIT {c['D']['SUBMIT']}, HOLD {c['D']['HOLD']}, KILL {c['D']['KILL']} | {c['D_unknown']} |", "",
          f"* SUBMIT + HOLD per 1,000 searched stars: {res['submit_hold_per_1000']:.1f} (S-L at 30); in the eM slice: {res['eM_submit_hold']}",
          f"* KILL by deciding condition: {res['kill_by_condition'] or 'none'}", "",
          "## Stage C walls [M]", "", f"{res['stage_c_walls']}", "",
          "## Cost [M]", "", f"Phase wall hours by stage (overlapping network phases counted separately): {res['phase_wall_hours_by_stage']}",
          f"(plan ~{PLAN_QH_PER_BATCH:.0f} queue-hours per batch, ~601 in total)."]
    if disk:
        L += ["", "## Disk [M]", "", f"GB by category: {disk['gb']}", "", f"Rates: {disk['rates']}"]
        if disk.get("projection"):
            L += ["", f"Projection: {disk['projection']}"]
    L += ["", "## SUBMIT / HOLD candidates", ""]
    if res["candidates"]:
        L += ["| TIC | slice | verdict | tier | deciding | period d | depth ppt | stitch SNR | hard stop | TCE | pixel coverage | packet |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in res["candidates"]:
            pc = f"**incomplete** (none: {r['pixel_none_sectors']})" if r["pixel_coverage_incomplete"] else "complete"
            L.append(f"| {r['tic_id']} | {r['slice']} | {r['verdict']} | {r['tier']} | {r['deciding_condition']} | {r['period_d']} | "
                     f"{r['depth_ppt']} | {r['stitch_snr']} | {r['hard_stop']} | {r['tce']} | {pc} | `{r['packet']}` |")
    else:
        L.append("None.")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("batch", type=int)
    ap.add_argument("--first", type=int)
    ap.add_argument("--title")
    ap.add_argument("--disk-json")
    ap.add_argument("--name")
    a = ap.parse_args()
    res = build(a.batch, a.first, a.title)
    disk = json.loads(Path(a.disk_json).read_text()) if a.disk_json else None
    name = a.name or f"BATCH_{a.batch}"
    (S1 / "results").mkdir(parents=True, exist_ok=True)
    (S1 / "results" / f"{name}.md").write_text(markdown(res, disk), encoding="utf-8", newline="\n")
    (S1 / "results" / f"{name.lower()}.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in res.items() if k not in ("phases", "candidates")}, indent=1, default=str))
