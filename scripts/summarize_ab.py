"""Summarise the ingestion A/B: for each variant, false-alarm candidates on
the no-injection run and recoveries on the injection run, plus timing.

Usage: python scripts/summarize_ab.py --runs data/survey/runs --prefix ab_
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

from analyze_completeness import VERDICT_FP, classify  # noqa: E402


def load(run: Path) -> list[dict]:
    out = []
    for p in sorted((run / "results").glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(REPO / "data" / "survey" / "runs"))
    ap.add_argument("--prefix", default="ab_")
    ap.add_argument("--min-transits", type=int, default=2)
    args = ap.parse_args()
    root = Path(args.runs)
    variants = sorted({p.name[len(args.prefix):].rsplit("_", 1)[0] for p in root.glob(f"{args.prefix}*_fa")})
    print(f"| variant | stars | FA cands (all) | SNR>=9 | SNR>=9 & not-FP verdict | SNR>=9 & >={args.min_transits + 1} transits | "
          f"depth>10 ppt | stars w/ cand | median wall s | p90 wall s | inj jobs | recovered | alias | clean rec |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for v in variants:
        fa = [r for r in load(root / f"{args.prefix}{v}_fa") if r.get("status") == "ok"]
        cands = [(r["tic_id"], p) for r in fa for p in ((r.get("result") or {}).get("planets") or [])]
        n_all = len(cands)
        n9 = sum(1 for _, p in cands if p["snr"] >= 9)
        n9nf = sum(1 for _, p in cands if p["snr"] >= 9 and p.get("verdict") != VERDICT_FP)
        n9t3 = sum(1 for _, p in cands if p["snr"] >= 9 and (p.get("n_transits_observed") or 0) >= args.min_transits + 1)
        deep = sum(1 for _, p in cands if p["depth_ppt"] > 10)
        stars = len({t for t, _ in cands})
        walls = np.array([r.get("wall_s") or np.nan for r in fa], dtype=float)
        inj = load(root / f"{args.prefix}{v}_inj")
        cls = [classify(r) for r in inj]
        n_rec = sum(1 for c in cls if c["status"] == "recovered")
        n_alias = sum(1 for c in cls if c["status"] == "alias")
        n_clean = sum(1 for c in cls if c["clean"])
        print(f"| {v} | {len(fa)} | {n_all} | {n9} | {n9nf} | {n9t3} | {deep} | {stars} | "
              f"{np.nanmedian(walls) if walls.size else float('nan'):.0f} | "
              f"{np.nanpercentile(walls, 90) if walls.size else float('nan'):.0f} | {len(inj)} | {n_rec} | {n_alias} | {n_clean} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
