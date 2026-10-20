"""K1 neighbour records for Stage B and D (copy of p12/protocol/neighbours_worker_p12.py, K1 roots).

Wraps the unchanged ``scripts/p8_neighbours.py``: bulk SIMBAD and VSX per target set (one query per
few hundred stars), then the per-star Gaia DR3 cone (``audit_p5.neighbours_step``).  Records go to
``D:/tesshunter_k1/neighbours/neighbours/tic<id>.json``.  A Gaia query that hangs is bounded by the
controller deadline; the Oct 4 ARI-mirror transport is installed when ``--ari-mirror`` is given.
CLI: ``neighbours_k1.py <simbad|vsx|TIC> --targets <csv> --label <set> --receipt <path>``.
Targets CSV columns: tic_id, ra_deg, dec_deg, tmag, teff_k, radius_rsun, mass_msun, tic_gaia_id.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path

from k1_common import REPO, DATA, environment, write, sha, utc

N = None


def module(targets: str, label: str):
    global N
    if N is None:
        sys.path.insert(0, str(REPO / "scripts"))
        import audit_p5 as A
        cache = DATA / "lightkurve_funnel"
        cache.mkdir(parents=True, exist_ok=True)
        A.AUDIT_CACHE = cache
        import p8_neighbours
        N = p8_neighbours
    N.OUT = DATA / "neighbours"
    N.LC_ROOT = DATA / "audit_lc"
    N.BULK = DATA / "neighbours_bulk" / label
    N.BULK.mkdir(parents=True, exist_ok=True)
    N.TARGETS = Path(targets)
    return N


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("kind")
    ap.add_argument("--targets", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--receipt", required=True)
    a = ap.parse_args(argv)
    environment(offline=False)
    started, timer = utc(), time.perf_counter()
    m = module(a.targets, a.label)
    rows = m.load_targets(a.targets)
    socket.setdefaulttimeout(300)
    if a.kind in ("simbad", "vsx"):
        values = getattr(m, "bulk_" + a.kind)(rows)
        ok = {int(r["tic_id"]) for r in rows} == set(values)
        result = dict(kind=a.kind, ok=ok, n_hosts=len(values), n_with_objects=sum(bool(v) for v in values.values()))
    else:
        tic = int(a.kind)
        for category in ("simbad", "vsx"):
            present = any(str(tic) in json.loads(p.read_text(encoding="utf-8")) for p in m.BULK.glob(category + "_*.json"))
            if not present:
                raise RuntimeError(f"Missing bulk {category} for TIC {tic}")
        result = m.one(tic, a.targets, False)
        result["record"] = str(DATA / "neighbours" / "neighbours" / f"tic{tic}.json")
    result.update(started_utc=started, completed_utc=utc(), wall_seconds=time.perf_counter() - timer, label=a.label,
                  source_sha256=sha(__file__), legacy_source_sha256=sha(REPO / "scripts/p8_neighbours.py"))
    write(Path(a.receipt), result, replace=True)
    print("neighbours", a.kind, result["ok"], flush=True)
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
