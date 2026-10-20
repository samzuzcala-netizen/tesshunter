"""Sector time spans (BTJD) measured from product time ranges already in the repo's audit store.

Used ONLY to pre-select known planets by predicted transit count before any download; the binding
check is always the realised data (an epoch is observed only when the downloaded usable products
cover it, RULES_K1 1.3).  Sectors with no measured product are interpolated (27.4-d cadence).
"""
import json
from pathlib import Path

import numpy as np

from k1_common import REPO, ROOT

CACHE = ROOT / "protocol" / "data" / "sector_spans.json"


def build(stores=(REPO / "data/survey/audit_lc",)) -> dict:
    spans = {}
    for store in stores:
        for idx in Path(store).glob("tic*/index.json"):
            try:
                d = json.loads(idx.read_text(encoding="utf-8"))
            except Exception:
                continue
            for p in d.get("products", []):
                if "t_start" not in p:
                    continue
                s = int(p["sector"])
                lo, hi = spans.get(s, (np.inf, -np.inf))
                spans[s] = (min(lo, float(p["t_start"])), max(hi, float(p["t_end"])))
    known = sorted(spans)
    out = {}
    for s in range(1, 111):
        if s in spans:
            out[s] = {"t_start": spans[s][0], "t_end": spans[s][1], "source": "measured"}
        else:
            ref = min(known, key=lambda k: abs(k - s))
            shift = (s - ref) * 27.4
            out[s] = {"t_start": spans[ref][0] + shift, "t_end": spans[ref][1] + shift, "source": f"interpolated_from_s{ref}"}
    CACHE.write_text(json.dumps({str(k): v for k, v in out.items()}, indent=1))
    return out


def load() -> dict:
    if not CACHE.exists():
        return build()
    return {int(k): v for k, v in json.loads(CACHE.read_text()).items()}


def predicted_transits(period, t0, t14_days, sectors, spans=None, coverage=0.5) -> int:
    """Epochs whose window lies inside a usable sector span (gaps inside sectors ignored)."""
    spans = spans or load()
    n = 0
    for s in sectors:
        sp = spans.get(int(s))
        if not sp:
            continue
        a, b = sp["t_start"], sp["t_end"]
        k0, k1 = int(np.ceil((a - t0) / period)), int(np.floor((b - t0) / period))
        for k in range(k0, k1 + 1):
            tc = t0 + k * period
            if a + coverage * t14_days / 2 <= tc <= b - coverage * t14_days / 2:
                n += 1
    return n
