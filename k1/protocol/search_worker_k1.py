"""K1 search worker (change 6): one preset search on one host's frozen store, traces on.

Adapted by copy from ``p12/protocol/blind_search_worker_p12.py``.  Asserts the preset is
``survey_k1`` or ``survey_k1_s56``; refuses survey-list stars (STOP-E) and any input under
``k1/truth``; never sees injection parameters (injected hosts are read from their own store copy).
Runtime JSON fields: job_id, tic_id, preset, star, lc_root, cache_dir, run_dir, overrides.
CLI: ``search_worker_k1.py <runtime.json>``.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from k1_common import ROOT, TRUTH, environment, read, write, sha, utc, safe

environment(offline=True)

PRESETS = ("survey_k1", "survey_k1_s56")
ALLOWED = {"job_id", "tic_id", "preset", "star", "lc_root", "cache_dir", "run_dir", "overrides", "use"}
ALLOWED_OVERRIDES = {"time_budget_s"}


def main(runtime_path: str) -> int:
    runtime_path = Path(runtime_path)
    rt = read(runtime_path)
    if set(rt) - ALLOWED:
        raise RuntimeError("Unregistered runtime fields: " + ",".join(sorted(set(rt) - ALLOWED)))
    if rt["preset"] not in PRESETS:
        raise RuntimeError("Unregistered preset " + str(rt["preset"]))
    if set(rt.get("overrides") or {}) - ALLOWED_OVERRIDES:
        raise RuntimeError("Unregistered override")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", rt["job_id"]):
        raise RuntimeError("Unsafe job id")
    lc_root = Path(rt["lc_root"]).resolve()
    if lc_root.is_relative_to(TRUTH.resolve()):
        raise RuntimeError("Worker input under k1/truth")
    for key in rt.get("star", {}):
        if key.startswith("inj") or key in ("truth", "injection", "period", "t0"):
            raise RuntimeError("Truth-like field in star block")
    import download_k1
    if int(rt["tic_id"]) in download_k1.survey_tics():
        raise RuntimeError("STOP-E: survey-list star")
    from tesshunter import survey
    run = Path(rt["run_dir"])
    result_path = run / "results" / f"{rt['job_id']}.json"
    if result_path.exists():
        raise FileExistsError(result_path)
    trace = run / "traces" / f"{rt['job_id']}.jsonl"
    trace.parent.mkdir(parents=True, exist_ok=True)
    started, timer, cpu = utc(), time.perf_counter(), time.process_time()
    job = dict(job_id=rt["job_id"], tic_id=int(rt["tic_id"]), star=rt["star"], config=rt["preset"],
               overrides={"record_traces": True, **(rt.get("overrides") or {})}, trace_path=str(trace),
               lc_root=str(lc_root))
    result = survey.run_job(job, cache_dir=Path(rt["cache_dir"]), allow_download=False)
    write(result_path, safe(result))
    planets = (result.get("result") or {}).get("planets") or []
    pregate = sum((p.get("stitch_snr") or 0) >= 7.1 and (p.get("stitch_n_transits") or 0) >= 3
                  and bool(p.get("stitch_epoch_consistent")) for p in planets)
    receipt = dict(job_id=rt["job_id"], tic_id=int(rt["tic_id"]), preset=rt["preset"], use=rt.get("use"),
                   status="COMPLETE" if result["status"] == "ok" else "OPERATIONAL_UNKNOWN",
                   result_status=result["status"], error=(result.get("error") or "")[:500] or None,
                   started_utc=started, completed_utc=utc(), wall_seconds=time.perf_counter() - timer,
                   cpu_seconds=time.process_time() - cpu, n_cad=result.get("n_cadences_raw"),
                   n_units=result.get("n_units"), baseline_days=result.get("baseline_days"),
                   n_accepted=len(planets), n_pre_gate=int(pregate),
                   budget_s=(result.get("config") or {}).get("time_budget_s"),
                   partitions=[dict(label=s.get("label"), budget_s=s.get("budget_s"), n_cadences=s.get("n_cadences"),
                                    period_min=s.get("period_min"), period_max=s.get("period_max"),
                                    budget_exhausted=bool(s.get("budget_exhausted")),
                                    search_seconds=sum(float(v) for v in (s.get("timings") or {}).values()))
                               for s in result.get("searches", [])],
                   budget_exhausted_partitions=sum(bool(s.get("budget_exhausted")) for s in result.get("searches", [])),
                   result_path=str(result_path), result_sha256=sha(result_path), runtime_sha256=sha(runtime_path))
    write(run / "receipts" / f"{rt['job_id']}.json", receipt)
    print("search", rt["preset"], rt["tic_id"], receipt["status"], round(receipt["wall_seconds"], 1), flush=True)
    return 0 if receipt["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
