"""FU3 replay worker: one frozen-preset search (survey.run_job) on one replay store copy.

The parent sets K1_DATA = K2_DATA = the replay data root, XDG_CACHE_HOME, TESSHUNTER_OFFLINE=1 and single-thread
BLAS.  Identical call to search_worker_k1.main (survey.run_job(job, cache_dir, allow_download=False) with
record_traces and the 8,100-s budget), minus the K1/S1 list guards that do not apply to replay copies.
CLI: s08_worker.py <job.json>
"""
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter")
for p in (REPO / "src", REPO / "scripts", REPO / "k1" / "protocol", REPO / "k2" / "protocol"):
    sys.path.insert(0, str(p))
replay = Path(os.environ["K1_DATA"])
assert "tess_fu3_cache" in str(replay), "replay worker must run on the FU3 replay root"
import k1_common  # noqa: E402
k1_common.environment(offline=True)
from tesshunter import survey  # noqa: E402


def main(job_path):
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    out = Path(job["out_dir"])
    res_path = out / "results" / f"{job['job_id']}.json"
    if res_path.exists():
        print("exists", res_path)
        return 0
    trace = out / "traces" / f"{job['job_id']}.jsonl"
    trace.parent.mkdir(parents=True, exist_ok=True)
    j = dict(job_id=job["job_id"], tic_id=int(job["tic_id"]), star=job["star"], config="survey_k1",
             overrides={"record_traces": True, "time_budget_s": 8100.0}, trace_path=str(trace),
             lc_root=job["lc_root"])
    t0, c0 = time.perf_counter(), time.process_time()
    res = survey.run_job(j, cache_dir=Path(job["cache_dir"]), allow_download=False)
    res_path.parent.mkdir(parents=True, exist_ok=True)
    k1_common.write(res_path, k1_common.safe(res), replace=True)
    planets = (res.get("result") or {}).get("planets") or []
    rec = dict(job_id=job["job_id"], tic_id=int(job["tic_id"]), status=res.get("status"), error=res.get("error"),
               wall_seconds=time.perf_counter() - t0, cpu_seconds=time.process_time() - c0, n_accepted=len(planets),
               n_pre_gate=int(sum((p.get("stitch_snr") or 0) >= 7.1 and int(p.get("stitch_n_transits") or 0) >= 3
                                  and bool(p.get("stitch_epoch_consistent")) for p in planets)),
               budget_exhausted_partitions=sum(bool(s.get("budget_exhausted")) for s in res.get("searches", [])),
               n_units=res.get("n_units"), completed_utc=k1_common.utc())
    k1_common.write(out / "receipts" / f"{job['job_id']}.json", rec, replace=True)
    print("search", job["job_id"], rec["status"], round(rec["wall_seconds"], 1), rec["n_accepted"], rec["n_pre_gate"], flush=True)
    return 0 if rec["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
