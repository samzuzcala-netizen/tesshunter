"""Prompt 8 Part 1c: raw per-product arrays for every P8 star into the shared audit store.

One ``search_lightcurve`` per star (``audit_p5.download`` with ``sector_min=27``: the
600-second and 200-second eras; sectors 1-26 are never searched under prompt 8), at most
four worker processes, the prompt-4/6 MAST discipline.  Stars whose ``index.json`` already
exists are skipped; a star whose index was built WITHOUT the sector cut (a prompt-5/6 star)
is kept as it is, since it holds a superset.

Checkpointing: the store itself is the checkpoint (one ``index.json`` per finished star), so
a killed run is resumed by running the script again.  A worker whose CPU time stops
advancing past the 300-s socket timeout is the known MAST hang: stop it and rerun.

    python scripts/p8_download.py [workers] [--targets data/survey/targets_p8.csv] [--first N]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

OUT = REPO / "data" / "survey" / "p8"
STORE = REPO / "data" / "survey" / "audit_lc"
SECTOR_MIN = 27


def one(tic: int) -> dict:
    import audit_p5 as A
    t0 = time.perf_counter()
    try:
        idx = A.download(tic, sector_min=SECTOR_MIN)
        size = sum((STORE / f"tic{tic}" / p["file"]).stat().st_size for p in idx["products"] if "file" in p)
        return {"tic_id": tic, "n_products": idx["n_products"], "n_failed": idx["n_failed"],
                "bytes": int(size), "seconds": round(time.perf_counter() - t0, 1), "ok": True}
    except Exception as exc:
        return {"tic_id": tic, "error": f"{type(exc).__name__}: {exc}"[:300],
                "seconds": round(time.perf_counter() - t0, 1), "ok": False}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("workers", nargs="?", type=int, default=4)
    ap.add_argument("--targets", default=str(REPO / "data" / "survey" / "targets_p8.csv"))
    ap.add_argument("--first", type=int, default=None, help="only the first N stars (the size estimate)")
    ap.add_argument("--tics", default=None, help="comma-separated subset")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.targets, newline="", encoding="utf-8")))
    tics = [int(r["tic_id"]) for r in rows]
    if a.tics:
        want = {int(x) for x in a.tics.split(",") if x.strip()}
        tics = [t for t in tics if t in want]
    if a.first:
        tics = tics[: a.first]
    done = [t for t in tics if (STORE / f"tic{t}" / "index.json").exists()]
    todo = [t for t in tics if t not in set(done)]
    print(f"{len(tics)} P8 stars, {len(done)} already in the store, {len(todo)} to download, "
          f"{a.workers} workers, sector_min {SECTOR_MIN}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    results, t0 = [], time.perf_counter()
    log_path = OUT / "download_p8.json"
    if log_path.exists():
        try:
            results = json.loads(log_path.read_text(encoding="utf-8")).get("results", [])
        except Exception:
            results = []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(one, t): t for t in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            results = [x for x in results if x["tic_id"] != r["tic_id"]] + [r]
            el = time.perf_counter() - t0
            print(f"[{i}/{len(todo)}] TIC {r['tic_id']}: "
                  + (f"{r['n_products']} products ({r['n_failed']} failed, {r['bytes'] / 1e6:.1f} MB)" if r["ok"] else r["error"])
                  + f" in {r['seconds']} s | elapsed {el / 60:.1f} min, eta {(el / i) * (len(todo) - i) / 60:.1f} min",
                  flush=True)
            if i % 10 == 0 or i == len(todo):
                ok = [x for x in results if x["ok"]]
                log_path.write_text(json.dumps(
                    {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "workers": a.workers,
                     "sector_min": SECTOR_MIN, "n_stars_total": len(tics), "n_preexisting": len(done),
                     "n_attempted": len(todo), "n_ok": len(ok), "n_error": sum(not x["ok"] for x in results),
                     "total_bytes_ok": int(sum(x.get("bytes", 0) for x in ok)),
                     "mean_bytes_per_star": (sum(x.get("bytes", 0) for x in ok) / len(ok)) if ok else None,
                     "elapsed_min": round(el / 60, 1), "results": sorted(results, key=lambda r: r["tic_id"])},
                    indent=1), encoding="utf-8")
    ok = [x for x in results if x["ok"]]
    print(f"DONE: {len(ok)} ok, {sum(not x['ok'] for x in results)} errors, "
          f"{sum(x.get('bytes', 0) for x in ok) / 1e9:.2f} GB, {(time.perf_counter() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
