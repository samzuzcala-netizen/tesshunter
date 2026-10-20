"""Part F paired comparison: P12's frozen pipeline from an isolated copy of aee65172b.

The copy (``D:/tesshunter_k1/p12_frozen``, ``git archive aee65172b src scripts p10/protocol p12/protocol``) is put
FIRST on ``sys.path``; nothing from the repo's (K1-modified) ``src`` is imported.  The search is the frozen
``survey_p10`` preset (sectors >= 56, products harmonised to 200 s, P12's search) on the host's K1-store
products, which hold only usable FFI products (sectors <= 98, QLP 80/83/85 excluded) -- the "sectors 56-98
inputs" of RULES_K1 G2.  The funnel is P12's p10.0 A / S / B / C exactly as ``funnel_stage_p12`` sets them up,
with K1 case roots and receipts.  The P12 worker environment (single-threaded numerics) is used.
CLI: ``p12_paired_worker_k1.py search <runtime>`` | ``p12_paired_worker_k1.py <A|S|B|C> <runtime>``.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import traceback
from pathlib import Path

FROZEN = Path(os.environ.get("K1_P12_FROZEN", r"D:\tesshunter_k1\p12_frozen"))
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
           "NUMBA_NUM_THREADS", "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_k] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["TESSHUNTER_OFFLINE"] = "1"
for _p in (FROZEN / "p10" / "protocol", FROZEN / "scripts", FROZEN / "src"):
    sys.path.insert(0, str(_p))
_here = Path(__file__).resolve().parent
sys.path.append(str(_here))           # k1_common only (stdlib-only helpers); appended, never ahead of the frozen copy
from k1_common import DATA, RECEIPTS, RUNS, read, write, utc, safe  # noqa: E402


def _assert_frozen(mod):
    path = Path(mod.__file__).resolve()
    if not path.is_relative_to(FROZEN.resolve()):
        raise RuntimeError(f"{mod.__name__} imported from {path}, not the frozen copy")


def search(rt):
    from tesshunter import survey
    _assert_frozen(survey)
    run = Path(rt["run_dir"])
    out = run / "results" / f"{rt['job_id']}.json"
    if out.exists():
        raise FileExistsError(out)
    t0, cpu = time.perf_counter(), time.process_time()
    res = survey.run_job(dict(job_id=rt["job_id"], tic_id=int(rt["tic_id"]), star=rt["star"], config="survey_p10",
                              overrides={"record_traces": True}, trace_path=str(run / "traces" / f"{rt['job_id']}.jsonl"),
                              lc_root=rt["lc_root"]), cache_dir=Path(rt["cache_dir"]), allow_download=False)
    write(out, safe(res))
    planets = (res.get("result") or {}).get("planets") or []
    rec = dict(job_id=rt["job_id"], tic_id=int(rt["tic_id"]), preset="survey_p10 (frozen aee65172b)",
               status="COMPLETE" if res["status"] == "ok" else "OPERATIONAL_UNKNOWN", wall_seconds=time.perf_counter() - t0,
               cpu_seconds=time.process_time() - cpu, n_accepted=len(planets), n_cad=res.get("n_cadences_raw"),
               n_pre_gate=sum((p.get("stitch_snr") or 0) >= 7.1 and (p.get("stitch_n_transits") or 0) >= 3
                              and bool(p.get("stitch_epoch_consistent")) for p in planets),
               budget_exhausted_partitions=sum(bool(s.get("budget_exhausted")) for s in res.get("searches", [])),
               survey_module=str(Path(survey.__file__).resolve()), completed_utc=utc())
    write(run / "receipts" / f"{rt['job_id']}.json", rec)
    return 0 if rec["status"] == "COMPLETE" else 2


def funnel(stage, rt):
    import p10_funnel_calibration as F
    import audit_p5 as A
    from tesshunter import survey
    for m in (F, A, survey):
        _assert_frozen(m)
    tic = int(rt["tic_id"])
    root = Path(rt["root"])
    root.mkdir(parents=True, exist_ok=True)
    cols = sorted(set(rt["candidate"]) | set(rt["star"]) | {"period_days", "tic_id", "rank"})
    cand = dict(rt["candidate"], **rt["star"], tic_id=tic)
    cand.setdefault("rank", 1)
    for name, rows in (("survivors.csv", [cand]), ("candidates.csv", rt["all_candidates"])):
        p = root / name
        if not p.exists():
            with p.open("x", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=sorted(set(cols) | {k for r in rows for k in r}), extrasaction="ignore")
                w.writeheader(); w.writerows(rows)
    F.LC_ROOT = Path(rt["lc_root"])
    F.PACKETS = DATA / "funnel_empty_packets"
    cache = DATA / "lightkurve_funnel"
    A.AUDIT_CACHE = cache
    os.environ["LIGHTKURVE_CACHE"] = str(cache)
    F.set_root(root)
    F.set_rules("p10.0")                                    # rules_p12.configure_early_funnel: A, S, B, C run p10.0
    A.set_input_config(survey.get_config("survey_p10"))
    A.set_roots(root, Path(rt["lc_root"]))
    st = rt["star"]
    stellar = {"radius": st["radius_rsun"], "mass": st["mass_msun"], "teff": st["teff_k"], "tmag": st["tmag"],
               "ra": st["ra_deg"], "dec": st["dec_deg"]}
    A.stellar_from_cache = lambda requested: stellar if int(requested) == tic else {}
    if stage == "B":
        tgt = root / "neighbours" / f"tic{tic}.json"
        tgt.parent.mkdir(parents=True, exist_ok=True)
        write(tgt, read(rt["neighbours_path"]), replace=True)
    job = F.V.jobs()[0]
    if stage == "A":
        return F.V.stagea_one(job, threads=1)
    if stage == "S":
        return F.secondary_one(job)
    if stage == "B":
        return F.V.stageb_one(job)
    return F.V.stagec_one(job, threads=int(rt.get("tls_threads") or 4), oversampling=3)


def main(kind, runtime_path):
    rt = read(runtime_path)
    if kind == "search":
        return search(rt)
    cid, label = rt["candidate_id"], rt["label"]
    dest = RECEIPTS / label / kind / f"{cid}.json"
    if dest.exists():
        raise FileExistsError(dest)
    t0 = time.perf_counter()
    try:
        m = funnel(kind, rt)
        decision = m.get("decision", m.get("gate", m.get("status")))
        rec = dict(candidate_id=cid, tic_id=int(rt["tic_id"]), stage=kind, label=label, decision=decision,
                   status="OPERATIONAL_UNKNOWN" if decision in ("ERROR", "SKIP", "INPUT_ERROR", "TIMEOUT") else "COMPLETE",
                   wall_seconds=time.perf_counter() - t0, measurement=m, pipeline="P12 frozen aee65172b")
        if kind == "S":
            sec = m.get("secondary") or {}
            rec["gate_by_mode"] = {"bound": m.get("gate")}
    except Exception as exc:
        rec = dict(candidate_id=cid, tic_id=int(rt["tic_id"]), stage=kind, label=label, status="OPERATIONAL_UNKNOWN",
                   error=f"{type(exc).__name__}: {exc}"[:500], traceback=traceback.format_exc()[-2500:],
                   wall_seconds=time.perf_counter() - t0)
    write(dest, safe(rec))
    print(kind, cid, rec["status"], rec.get("decision"), flush=True)
    return 0 if rec["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
