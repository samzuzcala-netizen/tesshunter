"""Prompt 6 Stage 0: download every survivor star into the shared audit light-curve store.

One ``search_lightcurve`` per star (the ``download`` sub-command of ``audit_p5``), at most
four worker processes, stars ordered by their best P4 rank so the funnel can start early.
Stars whose ``index.json`` already exists (the twelve audited in prompt 5) are skipped.
"""
from __future__ import annotations

import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

OUT = REPO / "data" / "survey" / "p6"


def star_order() -> list[int]:
    rows = list(csv.DictReader(open(REPO / "data" / "survey" / "p4" / "survivors.csv", newline="", encoding="utf-8")))
    best: dict[int, int] = {}
    for r in rows:
        tic, rank = int(r["tic_id"]), int(r["rank"])
        if tic not in best or rank < best[tic]:
            best[tic] = rank
    return [t for t, _ in sorted(best.items(), key=lambda kv: kv[1])]


def one(tic: int) -> dict:
    import audit_p5 as A
    t0 = time.perf_counter()
    try:
        idx = A.download(tic)
        return {"tic_id": tic, "n_products": idx["n_products"], "n_failed": idx["n_failed"],
                "seconds": round(time.perf_counter() - t0, 1), "ok": True}
    except Exception as exc:                                   # network / MAST failure: retried by a re-run
        return {"tic_id": tic, "error": f"{type(exc).__name__}: {exc}"[:300],
                "seconds": round(time.perf_counter() - t0, 1), "ok": False}


def main() -> None:
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    tics = star_order()
    done = [t for t in tics if (REPO / "data" / "survey" / "audit_lc" / f"tic{t}" / "index.json").exists()]
    todo = [t for t in tics if t not in set(done)]
    print(f"{len(tics)} survivor stars, {len(done)} already in the store, {len(todo)} to download, "
          f"{workers} workers", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    results, t0 = [], time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(one, t): t for t in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            results.append(r)
            el = time.perf_counter() - t0
            print(f"[{i}/{len(todo)}] TIC {r['tic_id']}: "
                  + (f"{r['n_products']} products ({r['n_failed']} failed)" if r["ok"] else r["error"])
                  + f" in {r['seconds']} s | elapsed {el / 60:.1f} min, eta {(el / i) * (len(todo) - i) / 60:.1f} min",
                  flush=True)
            (OUT / "download_p6.json").write_text(json.dumps(
                {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "workers": workers,
                 "n_stars_total": len(tics), "n_preexisting": len(done), "n_attempted": len(todo),
                 "n_ok": sum(r["ok"] for r in results), "n_error": sum(not r["ok"] for r in results),
                 "elapsed_min": round(el / 60, 1), "results": sorted(results, key=lambda r: r["tic_id"])},
                indent=1), encoding="utf-8")
    print(f"DONE: {sum(r['ok'] for r in results)} ok, {sum(not r['ok'] for r in results)} errors, "
          f"{(time.perf_counter() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
