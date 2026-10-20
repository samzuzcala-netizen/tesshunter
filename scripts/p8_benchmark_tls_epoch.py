"""Re-run representative stored forced TLS fits with the equivalent epoch ordering path."""
import argparse
import importlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "scripts")]
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data/cache/lightkurve"))
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fa", action="store_true", help="benchmark two long-period records from the 300-star control sample")
    parser.add_argument("--epoch-only", action="store_true", help="paired timing of the two epoch scans on control-sample arrays")
    args = parser.parse_args()
    import audit_p5 as A
    from p7_reproduce import diff_records
    from tesshunter.tls_epoch import final_T0_fit
    if args.epoch_only:
        return benchmark_epochs(A, final_T0_fit)
    tls_main = importlib.import_module("transitleastsquares.main")
    tls_main.final_T0_fit = final_T0_fit
    examples = ["inj00378_tic154567574", "inj01068_tic237929888", "inj01614_tic348843860"]
    paths = [next((REPO / "data/survey/p8/inj_funnel" / job / "tls").glob("*_forced.json")) for job in examples]
    output = REPO / "data/survey/p8/tls_epoch_benchmark_p8.json"
    if args.fa:
        paths = []
        for path in sorted((REPO / "data/survey/p8/fa_funnel/tls").glob("*_forced.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("input_config") and record["inputs"]["n_binned"] > 70000 and record["survey_period"] > 20:
                paths.append(path)
            if len(paths) == 2:
                break
        output = REPO / "data/survey/p8/tls_epoch_benchmark_fa_p8.json"
    results = []
    for path in paths:
        old = json.loads(path.read_text(encoding="utf-8"))
        inputs = old["inputs"]
        with np.load(path.with_name(path.name.replace("_forced.json", "_lc.npz"))) as z:
            t, f, e = z["time"], z["flux"], z["flux_err"]
        start = time.perf_counter()
        fit = A.run_tls(t, f, e, inputs["period_min"], inputs["period_max"],
                        inputs["R_star"], inputs["M_star"], inputs["oversampling_factor"], 1)
        seconds = time.perf_counter() - start
        new = A._tls_summary(fit)
        record = {"source": str(path.relative_to(REPO)), "n_cadences": len(t), "period": old["survey_period"],
                  "stored_wall_seconds": old["timing_s"]["tls_forced"], "new_wall_seconds": seconds,
                  "exactly_equal": new == old["forced"], "comparison": diff_records(new, old["forced"])}
        results.append(record)
        print(json.dumps(record), flush=True)
        output.write_text(json.dumps(results, indent=1), encoding="utf-8")
        if not record["exactly_equal"]:
            raise SystemExit("optimized TLS differs from the stored result; do not use it in the funnel")


def benchmark_epochs(A, replacement):
    from transitleastsquares.stats import final_T0_fit as original
    paths = sorted((REPO / "data/survey/p8/fa_funnel/tls").glob("*_forced.json"))
    path = next(p for p in paths if json.loads(p.read_text())["inputs"]["n_binned"] > 190000)
    old = json.loads(path.read_text(encoding="utf-8"))
    with np.load(path.with_name(path.name.replace("_forced.json", "_lc.npz"))) as z:
        t, y, dy = z["time"], z["flux"], z["flux_err"]
    results = []
    # Synthetic template, actual control-sample arrays. This isolates time spent in
    # the epoch scan; the separate full TLS benchmarks verify the scientific output.
    for index, stride in enumerate((2, 1)):
        tt, yy, ee = t[::stride], y[::stride], dy[::stride]
        duration = max(20, round(len(yy) * 0.08 / old["survey_period"]))
        arguments = dict(signal=1 - 0.1 * np.sin(np.linspace(0, np.pi, duration)) ** 2,
                         depth=0.99, t=tt, y=yy, dy=ee, period=old["survey_period"],
                         T0_fit_margin=0.01, show_progress_bar=False, verbose=False)
        row = {"source": str(path.relative_to(REPO)), "n_cadences": len(yy), "template_samples": duration,
               "template": "synthetic sin-squared; timing isolation only", "T0_fit_margin": 0.01}
        functions = [("upstream", original), ("equivalent", replacement)]
        if index:
            functions.reverse()
        for name, function in functions:
            wall, cpu = time.perf_counter(), time.process_time()
            epoch = function(**arguments)
            row[name] = {"epoch": float(epoch), "wall_seconds": time.perf_counter() - wall,
                         "cpu_seconds": time.process_time() - cpu}
            print(json.dumps({"n_cadences": len(yy), "method": name, **row[name]}), flush=True)
        row["exactly_equal"] = row["upstream"]["epoch"] == row["equivalent"]["epoch"]
        results.append(row)
        A.jdump(REPO / "data/survey/p8/tls_epoch_paired_timing_p8.json", results)
        if not row["exactly_equal"]:
            raise SystemExit("epoch timing comparison differs")


if __name__ == "__main__":
    main()
