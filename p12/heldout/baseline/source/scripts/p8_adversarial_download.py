"""Prompt 8 Part 3: the prompt-3 adversarial eclipsing binaries and blends into the audit store.

``audit_p5.download`` (one ``search_lightcurve`` per star, every SPOC 2-min / TESS-SPOC / QLP
product) for the 18 EBs and 22 blends of ``data/adversarial/targets_v1.csv``, two workers, so
the event rules and the secondary scan can run on them under every rule variant.
"""
from __future__ import annotations

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


def one(tic: int) -> dict:
    import audit_p5 as A
    t0 = time.perf_counter()
    try:
        idx = A.download(tic)
        return {"tic_id": tic, "n_products": idx["n_products"], "n_failed": idx["n_failed"], "ok": True,
                "seconds": round(time.perf_counter() - t0, 1)}
    except Exception as exc:
        return {"tic_id": tic, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:200],
                "seconds": round(time.perf_counter() - t0, 1)}


def main() -> None:
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    rows = [r for r in csv.DictReader(open(REPO / "data" / "adversarial" / "targets_v1.csv", newline="", encoding="utf-8"))
            if r["cls"] in ("eb", "blend")]
    tics = [int(r["tic_id"]) for r in rows]
    res = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(one, t): t for t in tics}
        for f in as_completed(futs):
            r = f.result()
            res.append(r)
            print(r, flush=True)
    (OUT / "adversarial_download.json").write_text(json.dumps(
        {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n": len(res),
         "n_ok": sum(r["ok"] for r in res), "results": sorted(res, key=lambda r: r["tic_id"])}, indent=1), encoding="utf-8")
    print("DONE", sum(r["ok"] for r in res), "ok of", len(res), flush=True)


if __name__ == "__main__":
    main()
