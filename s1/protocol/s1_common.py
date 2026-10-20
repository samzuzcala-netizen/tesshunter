"""S1 paths and helpers (prompt S1: the K-dwarf survey on the frozen K2 package).

S1 runs K1's and K2's frozen workers unchanged.  This module points both data roots at ``D:/tesshunter_s1``
BEFORE ``k2_common`` (which reads ``K2_DATA`` at import) and ``k1_common`` (``K1_DATA``) are imported, so every
worker path, cache, receipt and packet lands under the S1 root: the K2 controller logic, ``k2_common.worker_env``
(``K1_DATA`` = ``K2_DATA`` = the S1 root, ``XDG_CACHE_HOME`` = ``D:/tesshunter_s1/xdg_cache``) and the K1/K2 workers
then need no edit.  Evaluator-side S1 code imports this module first.

Operational additions (no effect on any decision):
* ``ledger``: the S1 exposure ledger, appended under an exclusive lock (K2 lost 13 of 208 rows to concurrent appends
  from 4 download workers);
* ``survey_tics`` / ``batch_frame``: the S1 survey list and its 5 batches.
"""
from __future__ import annotations

import os
import random
import sys
import time
from pathlib import Path

S1_DATA = Path(r"D:\tesshunter_s1")
os.environ["K2_DATA"] = str(S1_DATA)
os.environ["K1_DATA"] = str(S1_DATA)

REPO = Path(__file__).resolve().parents[2]
S1 = REPO / "s1"
for _p in (REPO / "scripts", REPO / "src", REPO / "k1" / "protocol", REPO / "k2" / "protocol", S1 / "protocol"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import k2_common  # noqa: E402
from k2_common import (K1, K2, PY, CONTROLLERS, JOBS, worker_env, assert_worker_root, guard_truth,  # noqa: E402,F401
                       read, write, utc, sha, safe, append_jsonl)

if k2_common.K2_DATA.resolve() != S1_DATA.resolve():
    raise RuntimeError("k2_common was imported before s1_common set K2_DATA")

STORE = S1_DATA / "audit_lc"
RUNS = S1_DATA / "runs"
RECEIPTS = S1_DATA / "funnel_receipts"
FUNNEL = S1_DATA / "funnel"
RUNTIMES = S1_DATA / "runtimes"
NEIGHBOURS = S1_DATA / "neighbours" / "neighbours"
TARGETS = S1 / "survey" / "targets_s1.csv"
LEDGER = S1 / "manifests" / "exposure_ledger_s1.csv"

#: Batches (k2/survey/LAUNCH_PLAN_K2.md section 2) as literal rank ranges within each slice.  A star refilled from
#: the reserve carries its reserve rank (K 7001+, eM 3001+) and joins the last batch of its slice.
BATCHES = {1: (("eM_slice", 1, 1500), ("K", 1, 500)),
           2: (("eM_slice", 1501, 3000), ("K", 501, 1000)),
           3: (("K", 1001, 3000),),
           4: (("K", 3001, 5000),),
           5: (("K", 5001, 7000),)}
LAST_BATCH = {"eM_slice": 2, "K": 5}


def survey_tics() -> set[int]:
    import pandas as pd
    return set(pd.read_csv(TARGETS, usecols=["tic_id"]).tic_id.astype("int64"))


def batch_of(slice_: str, rank: int) -> int:
    for n, parts in BATCHES.items():
        for s, lo, hi in parts:
            if s == slice_ and lo <= rank <= hi:
                return n
    return LAST_BATCH[slice_]


def batch_frame(n: int):
    """The stars of batch ``n`` in rank order (ties: eM first, the larger part of batches 1-2)."""
    import pandas as pd
    tg = pd.read_csv(TARGETS, low_memory=False)
    tg["batch"] = [batch_of(s, int(r)) for s, r in zip(tg.slice, tg["rank"])]
    sub = tg[tg.batch == n].copy()
    sub["_o"] = sub.slice.ne("eM_slice").astype(int)
    return sub.sort_values(["rank", "_o"]).drop(columns="_o").reset_index(drop=True)


def ledger(tic: int, use: str, stage: str, note: str = "") -> None:
    """S1 exposure ledger (every survey star S1 downloads), appended under an exclusive lock directory."""
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    lock = LEDGER.with_name(LEDGER.name + ".lock")
    give_up = time.monotonic() + 300
    while True:
        try:
            os.mkdir(lock)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 600:      # a holder that died mid-append
                    os.rmdir(lock)
                    continue
            except OSError:
                pass
            if time.monotonic() > give_up:
                raise TimeoutError("exposure-ledger lock not acquired in 300 s")
            time.sleep(0.05 + 0.15 * random.random())
    try:
        new = not LEDGER.exists()
        with LEDGER.open("a", encoding="utf-8", newline="\n") as stream:
            if new:
                stream.write("utc,tic_id,use,stage,note\n")
            stream.write(f"{utc()},{int(tic)},{use},{stage},{note.replace(',', ';')}\n")
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.rmdir(lock)
