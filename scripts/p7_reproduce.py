"""Prompt 7, Part A acceptance test: the ported rules reproduce the P5 and P6 records exactly.

The rules of prompts 5 and 6 now live in ``tesshunter.audit_prep``,
``tesshunter.event_vet``, ``tesshunter.star_vet`` and ``tesshunter.audit_rules``;
``scripts/audit_p5.py`` and ``scripts/revet_p6.py`` are wrappers over them.  This
script re-derives every prompt-6 record **through those wrappers** and diffs it
field by field against what is on disk.  Nothing under ``data/survey/p6/`` is
written: the reproduction runs in ``data/survey/p7/reproduce/``, whose
``tls/*_lc.npz``, ``tls/*_forced.json``, ``prep/*.json`` and ``neighbours/*.json``
are hard links to the prompt-6 files, so the ephemerides and the prepared arrays
are the ones prompt 6 used and only the rules are re-run.

Sub-commands::

    prep     [--slices N]   recompute the detrend/bin/clip of all 405 in memory and compare the
                            counters and every array with data/survey/p6/prep + tls/*_lc.npz
    stageA   [--slices N]   re-run Stage A for all 405 and diff every field against p6/stageA
    stageB                  re-run Stage B for the 7 records that entered it
    stageC                  re-run the FORCED TLS of the 6 Stage C candidates (not the blind
                            search) and diff it; replay the Stage C decision on the stored blind
    all      [--slices N]   all four, into data/survey/p7/reproduce_p7.json
    slice    --part ... internal: one worker

Tolerance: strings, booleans, integers and decisions must be equal exactly.  A
float pair counts as equal when ``|a - b| <= 1e-12 * max(1, |b|)``; the largest
relative difference actually seen is reported, and every field that is not equal
is listed.  Timestamps, wall-clock seconds and absolute paths are excluded by
name (``generated_utc``, ``seconds``, ``timing_s``, ``prepare_generated_utc``,
``lc_npz``, ``downloaded_utc``, ``verdict_stamped_utc``).

Nothing here submits anything anywhere.  The pipeline finds candidates.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

P6 = REPO / "data" / "survey" / "p6"
LC_ROOT = REPO / "data" / "survey" / "audit_lc"
SCRATCH = REPO / "data" / "survey" / "p7" / "reproduce"
SCRATCH_TLS = REPO / "data" / "survey" / "p7" / "reproduce_tls"
OUT_JSON = REPO / "data" / "survey" / "p7" / "reproduce_p7.json"
PY = sys.executable

#: a float pair is equal when |a - b| <= RTOL * max(1, |b|).
RTOL = 1e-12
#: fields whose value is a timestamp, a wall-clock measurement or an absolute path.
IGNORE_KEYS = {"generated_utc", "seconds", "timing_s", "prepare_generated_utc", "lc_npz",
               "downloaded_utc", "verdict_stamped_utc", "verdict_utc"}


# ─────────────────────────────────────────────────────────────────────────────
# the diff engine
# ─────────────────────────────────────────────────────────────────────────────
def diff(new, old, path: str = "", out: list | None = None, worst: list | None = None) -> list:
    """Every field of ``new`` that differs from ``old``, as ``(path, new, old)``."""
    out = [] if out is None else out
    worst = [0.0] if worst is None else worst
    if isinstance(old, dict) and isinstance(new, dict):
        for k in sorted(set(old) | set(new)):
            if k in IGNORE_KEYS:
                continue
            if k not in old:
                out.append((f"{path}.{k}", new[k], "<absent>"))
            elif k not in new:
                out.append((f"{path}.{k}", "<absent>", old[k]))
            else:
                diff(new[k], old[k], f"{path}.{k}", out, worst)
        return out
    if isinstance(old, list) and isinstance(new, list):
        if len(old) != len(new):
            out.append((f"{path}[len]", len(new), len(old)))
            return out
        for i, (a, b) in enumerate(zip(new, old)):
            diff(a, b, f"{path}[{i}]", out, worst)
        return out
    if isinstance(old, bool) or isinstance(new, bool):
        if bool(old) != bool(new):
            out.append((path, new, old))
        return out
    if isinstance(old, (int, float)) and isinstance(new, (int, float)):
        if old != old and new != new:            # NaN == NaN for this purpose
            return out
        tol = RTOL * max(1.0, abs(float(old)))
        d = abs(float(new) - float(old))
        if d > 0:
            worst[0] = max(worst[0], d / max(1.0, abs(float(old))))
        if d > tol:
            out.append((path, new, old))
        return out
    if old != new:
        out.append((path, new, old))
    return out


def diff_records(new: dict, old: dict) -> dict:
    worst = [0.0]
    d = diff(new, old, "", None, worst)
    return {"n_differences": len(d), "worst_relative": worst[0],
            "differences": [{"field": p, "new": _short(a), "stored": _short(b)} for p, a, b in d[:40]]}


def _short(v):
    s = v if isinstance(v, (int, float, bool)) or v is None else str(v)
    return s if not isinstance(s, str) or len(s) <= 200 else s[:200] + "..."


# ─────────────────────────────────────────────────────────────────────────────
# the scratch root: hard links so the prompt-6 inputs are byte-identical
# ─────────────────────────────────────────────────────────────────────────────
def link(src: Path, dst: Path) -> None:
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
    except FileExistsError:
        pass                        # another slice got there first
    except OSError:
        shutil.copy2(src, dst)


def build_scratch(with_forced: bool = True, root: Path = SCRATCH) -> Path:
    """Hard-link the prompt-6 inputs the rules read into a scratch output root."""
    for sub in ("tls", "events", "prep", "neighbours", "stageA", "stageB", "stageC", "fit", "crossmatch"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    n = 0
    for p in (P6 / "tls").glob("*_lc.npz"):
        link(p, root / "tls" / p.name); n += 1
    if with_forced:
        for p in (P6 / "tls").glob("*_forced.json"):
            link(p, root / "tls" / p.name); n += 1
        for p in (P6 / "prep").glob("*.json"):
            link(p, root / "prep" / p.name); n += 1
    for p in (P6 / "neighbours").glob("*.json"):
        link(p, root / "neighbours" / p.name); n += 1
    return root


def _load_driver(root: Path):
    import audit_p5 as A
    import revet_p6 as V
    V.OUT_ROOT = root
    V.LC_ROOT = LC_ROOT
    V.set_rules("p6.2")
    A.set_roots(root, LC_ROOT)
    return A, V


# ─────────────────────────────────────────────────────────────────────────────
# part 1: prepare (detrend, bin, clip) over all 405
# ─────────────────────────────────────────────────────────────────────────────
def reproduce_prep(jobs_: list[dict]) -> list[dict]:
    import audit_p5 as A
    from tesshunter.audit_prep import prepare_series
    A.set_roots(P6, LC_ROOT)
    rows = []
    for job in jobs_:
        tic, period = job["tic_id"], job["period"]
        k = A.key(tic, period)
        meta_p = P6 / "prep" / f"{k}.json"
        npz_p = P6 / "tls" / f"{k}_lc.npz"
        if not meta_p.exists():
            rows.append({"key": k, "status": "MISSING_PREP"}); continue
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        products = A.choose_per_sector(A.load_products(tic))
        row = A.survivor_row(tic, period)
        ref_depth = (float(row.get("depth_ppt")) / 1000.0) if row.get("depth_ppt") else 0.0
        prep = prepare_series(products, meta["wotan"]["window_days"], meta["bin_minutes"], ref_depth)
        cnt, det = prep["counters"], prep["unbinned"]
        new_meta = {kk: cnt[kk] for kk in ("n_unbinned", "n_binned", "n_isolated_clipped",
                                           "n_isolated_bins_clipped", "deep_clip_threshold_ppt",
                                           "n_deep_clipped")}
        new_meta["per_product"] = det["per_product"]
        old_meta = {kk: meta[kk] for kk in new_meta if kk in meta}
        d = diff_records(new_meta, old_meta)
        arr = {"status": "OK", "arrays_identical": True, "max_abs_array_diff": 0.0}
        if npz_p.exists():
            z = np.load(npz_p)
            for name, a in (("time", prep["binned"]["time"]), ("flux", prep["binned"]["flux"]),
                            ("flux_err", prep["binned"]["flux_err"]),
                            ("time_unbinned", det["time"]), ("flux_unbinned", det["flux"]),
                            ("sector_unbinned", det["sector"]), ("trend_unbinned", det["trend"])):
                o = z[name]
                if o.shape != a.shape:
                    arr["arrays_identical"] = False
                    arr.setdefault("shape_mismatch", []).append(f"{name}: {o.shape} vs {a.shape}")
                    continue
                if not np.array_equal(o, a):
                    arr["arrays_identical"] = False
                    md = float(np.nanmax(np.abs(o - a))) if o.size else 0.0
                    arr["max_abs_array_diff"] = max(arr["max_abs_array_diff"], md)
                    arr.setdefault("arrays_differing", []).append(name)
            z.close()
        else:
            arr["status"] = "NO_NPZ"
        rows.append({"key": k, "rank": job["rank"], **arr, **d})
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# part 2/3/4: the stages, re-run through the wrappers
# ─────────────────────────────────────────────────────────────────────────────
def reproduce_stage(stage: str, jobs_: list[dict], root: Path) -> list[dict]:
    A, V = _load_driver(root)
    fn = {"A": V.stagea_one, "B": V.stageb_one}[stage]
    rows = []
    for job in jobs_:
        k = V.kkey(job["tic_id"], job["period"])
        stored_p = P6 / f"stage{stage}" / f"{k}.json"
        if not stored_p.exists():
            rows.append({"key": k, "status": "MISSING_STORED"}); continue
        stored = json.loads(stored_p.read_text(encoding="utf-8"))
        kw = {"force": True}
        if stage == "A":
            kw["threads"] = 1
        new = fn(job, **kw)
        rows.append({"key": k, "rank": job.get("rank"), "status": "OK",
                     "decision_new": new.get("decision"), "decision_stored": stored.get("decision"),
                     "decision_same": new.get("decision") == stored.get("decision"),
                     **diff_records(new, stored)})
    return rows


def reproduce_stagec() -> dict:
    """Re-run the forced (narrow) TLS of every Stage C candidate and diff it, and replay the
    Stage C decision on the stored blind-search block.  The blind search itself (29 CPU-minutes
    in prompt 6) is not repeated: it is an input here, not a rule."""
    root = build_scratch(with_forced=False, root=SCRATCH_TLS)
    A, V = _load_driver(root)
    rows = []
    for p in sorted((P6 / "stageC").glob("*.json")):
        stored = json.loads(p.read_text(encoding="utf-8"))
        tic, period = stored["tic_id"], stored["survey_period"]
        k = V.kkey(tic, period)
        # (a) the forced narrow TLS, re-run
        t0 = time.perf_counter()
        new_forced = A.forced_step(tic, period, threads=8, force=True)
        stored_forced = json.loads((P6 / "tls" / f"{k}_forced.json").read_text(encoding="utf-8"))
        dforced = diff_records(new_forced["forced"], stored_forced["forced"])
        # (b) the Stage C decision, replayed on the stored blind block
        b = stored["blind"]
        m, strong = b["match"], b["SDE"] >= V.C_SDE
        same = bool(m["same_period_1pct"])
        alias21 = bool(m["alias_1pct"] and m["closest_alias"] in ("2:1", "1:2") and not same)
        if same and strong:
            dec = "PASS"
        elif alias21 and strong:
            dec = "PASS" if V.alias_depths_consistent(b)["consistent"] else "FAIL"
        else:
            dec = "FAIL"
        rows.append({"key": k, "rank": stored.get("rank"), "status": "OK",
                     "forced_tls": dforced, "forced_seconds": round(time.perf_counter() - t0, 1),
                     "decision_new": dec, "decision_stored": stored["decision"],
                     "decision_same": dec == stored["decision"]})
    return {"n": len(rows), "rows": rows}


# ─────────────────────────────────────────────────────────────────────────────
# slicing
# ─────────────────────────────────────────────────────────────────────────────
def run_slices(part: str, nslices: int) -> list[dict]:
    if part in ("stageA", "stageB"):
        build_scratch()             # once, in the parent, so the slices do not race on the links
    if nslices <= 1:
        return _run_part(part, 0, 1)
    logdir = REPO / "data" / "survey" / "p7" / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    procs = []
    for i in range(nslices):
        log = open(logdir / f"reproduce_{part}_slice{i}.log", "w", encoding="utf-8")
        cmd = [PY, str(Path(__file__).resolve()), "slice", "--part", part,
               "--index", str(i), "--nslices", str(nslices)]
        procs.append((i, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=str(REPO)), log))
    codes = []
    for i, pr, log in procs:
        codes.append((i, pr.wait()))
        log.close()
    bad = [c for c in codes if c[1] != 0]
    if bad:
        raise SystemExit(f"slices failed: {bad} (see {logdir})")
    rows = []
    for i in range(nslices):
        f = REPO / "data" / "survey" / "p7" / "slices" / f"{part}_{i}.json"
        rows.extend(json.loads(f.read_text(encoding="utf-8")))
    return rows


def _run_part(part: str, index: int, nslices: int) -> list[dict]:
    import revet_p6 as V
    js = V.jobs()[index::nslices]
    if part == "prep":
        return reproduce_prep(js)
    if part == "stageA":
        return reproduce_stage("A", js, build_scratch())
    if part == "stageB":
        keys = {json.loads(p.read_text(encoding="utf-8"))["key"] for p in (P6 / "stageB").glob("*.json")}
        js = [j for j in js if V.kkey(j["tic_id"], j["period"]) in keys]
        return reproduce_stage("B", js, build_scratch())
    raise SystemExit(f"unknown part {part}")


def summarise(part: str, rows: list[dict]) -> dict:
    ndiff = sum(r.get("n_differences", 0) for r in rows)
    bad = [r for r in rows if r.get("n_differences", 0) or r.get("decision_same") is False
           or r.get("arrays_identical") is False or r.get("status") not in ("OK", None)]
    worst = max((r.get("worst_relative", 0.0) for r in rows), default=0.0)
    worst_arr = max((r.get("max_abs_array_diff", 0.0) for r in rows), default=0.0)
    return {"part": part, "n_records": len(rows), "n_field_differences": ndiff,
            "n_records_with_a_difference": len(bad),
            "n_decision_differences": sum(1 for r in rows if r.get("decision_same") is False),
            "worst_relative_difference": worst, "worst_absolute_array_difference": worst_arr,
            "tolerance": {"relative": RTOL, "ignored_keys": sorted(IGNORE_KEYS)},
            "offenders": bad[:20]}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("prep", "stageA", "stageB", "all"):
        s = sub.add_parser(c)
        s.add_argument("--slices", type=int, default=8)
        s.add_argument("--out", type=Path, default=OUT_JSON, help="summary path; P8 can retain the historical P7 summary")
    sub.add_parser("stageC").add_argument("--out", type=Path, default=OUT_JSON)
    sl = sub.add_parser("slice")
    sl.add_argument("--part", required=True, choices=["prep", "stageA", "stageB"])
    sl.add_argument("--index", type=int, required=True)
    sl.add_argument("--nslices", type=int, required=True)
    args = ap.parse_args(argv)

    if args.cmd == "slice":
        rows = _run_part(args.part, args.index, args.nslices)
        d = REPO / "data" / "survey" / "p7" / "slices"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{args.part}_{args.index}.json").write_text(json.dumps(rows, indent=1, default=str),
                                                          encoding="utf-8")
        print(f"slice {args.index}/{args.nslices} {args.part}: {len(rows)} records", flush=True)
        return

    parts = ["prep", "stageA", "stageB", "stageC"] if args.cmd == "all" else [args.cmd]
    res = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "what": "prompt-7 Part A acceptance: the ported rules re-derive the prompt-6 records",
           "rules_version_reproduced": "p6.2", "parts": {}}
    for part in parts:
        t0 = time.perf_counter()
        if part == "stageC":
            r = reproduce_stagec()
            nd = sum(x["forced_tls"]["n_differences"] for x in r["rows"])
            res["parts"]["stageC"] = {
                "part": "stageC", "n_records": r["n"], "n_field_differences": nd,
                "n_decision_differences": sum(1 for x in r["rows"] if not x["decision_same"]),
                "worst_relative_difference": max((x["forced_tls"]["worst_relative"] for x in r["rows"]),
                                                 default=0.0),
                "note": "the forced narrow TLS was re-run; the blind search is an input, not a rule",
                "rows": r["rows"]}
        else:
            rows = run_slices(part, getattr(args, "slices", 8))
            res["parts"][part] = summarise(part, rows)
        s = res["parts"][part]
        print(f"{part}: {s['n_records']} records, {s.get('n_field_differences')} field differences, "
              f"{s.get('n_decision_differences')} decision differences, worst relative "
              f"{s.get('worst_relative_difference'):.3e}, {(time.perf_counter() - t0) / 60:.1f} min",
              flush=True)
    output = args.out if args.out.is_absolute() else REPO / args.out
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    total_d = sum(v.get("n_field_differences", 0) for v in res["parts"].values())
    total_dec = sum(v.get("n_decision_differences", 0) for v in res["parts"].values())
    print(f"\nwrote {output}\nTOTAL: {total_d} field differences, {total_dec} decision differences "
          f"across {sum(v['n_records'] for v in res['parts'].values())} records")


if __name__ == "__main__":
    main()
