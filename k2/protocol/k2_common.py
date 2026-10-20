"""K2 paths and helpers (prompt K2).

K2 reuses K1's workers.  A K2 job runs them with ``K1_DATA`` pointed at the K2 data root (the controller sets it),
so their receipts, runs, caches and packets land under ``D:/tesshunter_k2``; K1's store, case roots and receipts
are read through the explicit ``K1_*`` paths below.  Evaluator-side K2 code imports this module, never the
workers' implicit ``k1_common.DATA``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
K1 = REPO / "k1"
K2 = REPO / "k2"
for _p in (K2 / "protocol", K1 / "protocol", REPO / "src", REPO / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

K1_DATA = Path(r"D:\tesshunter_k1")
K2_DATA = Path(os.environ.get("K2_DATA", r"D:\tesshunter_k2"))
K1_STORE = K1_DATA / "audit_lc"
K2_STORE = K2_DATA / "audit_lc"
K1_RUNS, K2_RUNS = K1_DATA / "runs", K2_DATA / "runs"
K1_RECEIPTS, K2_RECEIPTS = K1_DATA / "funnel_receipts", K2_DATA / "funnel_receipts"
K1_FUNNEL, K2_FUNNEL = K1_DATA / "funnel", K2_DATA / "funnel"
K1_RUNTIMES, K2_RUNTIMES = K1_DATA / "runtimes", K2_DATA / "runtimes"
K1_NEIGHBOURS = K1_DATA / "neighbours" / "neighbours"
K2_NEIGHBOURS = K2_DATA / "neighbours" / "neighbours"
CONTROLLERS = K2_DATA / "controllers"
JOBS = K2_DATA / "jobs"
K1_TRUTH, K2_TRUTH = K1 / "truth", K2 / "truth"
PY = Path(r"C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe")

from k1_common import sha, sha_text, read, write, utc, safe, append_jsonl  # noqa: E402,F401


#: Operational (2026-10-15, K-D; k2/manifests/relocation_lightkurve_cache.json): this lightkurve ignores
#: LIGHTKURVE_CACHE, so downloads without an explicit download_dir (Stage D's FPP TESScut cutouts) went to the home
#: cache on C:.  XDG_CACHE_HOME with an existing <dir>/lightkurve folder redirects them to D:.  No effect on results.
XDG_CACHE = K2_DATA / "xdg_cache"


def worker_env(offline: bool = True) -> dict:
    """The environment of a K2 job: K1's worker environment with ``K1_DATA`` = the K2 data root and lightkurve's
    default cache on D: (``XDG_CACHE_HOME``)."""
    import k1_common
    env = k1_common.environment(offline=offline)
    (XDG_CACHE / "lightkurve").mkdir(parents=True, exist_ok=True)
    return dict(env, K1_DATA=str(K2_DATA), K2_DATA=str(K2_DATA), XDG_CACHE_HOME=str(XDG_CACHE))


def assert_worker_root() -> None:
    """A K2 worker must run with K1_DATA pointed at the K2 root (so nothing is written into K1's data)."""
    if Path(os.environ.get("K1_DATA", "")).resolve() != K2_DATA.resolve():
        raise RuntimeError("K2 worker started without K1_DATA = the K2 data root")


def guard_truth(path) -> None:
    p = Path(path).resolve()
    for t in (K1_TRUTH, K2_TRUTH):
        if p.is_relative_to(t.resolve()):
            raise RuntimeError("Worker input under a truth folder")


def ledger(tic: int, use: str, stage: str, note: str = "") -> None:
    """K2 exposure ledger (every star K2 touches for the first time: the fresh set)."""
    path = K2 / "manifests" / "exposure_ledger_k2.csv"
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        if new:
            stream.write("utc,tic_id,use,stage,note\n")
        stream.write(f"{utc()},{int(tic)},{use},{stage},{note.replace(',', ';')}\n")
