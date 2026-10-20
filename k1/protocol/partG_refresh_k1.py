"""K1 Part G1-G2: delivery-day catalogue refresh of the frozen survey list, then the freeze.

The survey list (``k1/survey/targets_k1.csv``: 7,000 K + 3,000 eM, ranked, eM slice flagged) is checked against
the delivery-day snapshot (``snapshot_k1.py catalogs --label <label>``) with the K1 hard stop
(``catalog_adapter_k1``).  Stars now REJECTed (a TOI or CTOI gained since Part A, or any other hard-stop
source) are dropped and recorded; each class is refilled from ``reserve_k1.csv`` in rank order, skipping any
reserve star that is REJECTed, already listed, or touched by calibration (``k1/manifests/exposure_ledger.csv``).
Survey blindness check: no survey-list star may appear in the exposure ledger (STOP-E).
Writes the refreshed ``targets_k1.csv`` (the pre-refresh list kept as ``targets_k1_prerefresh.csv``), the reserve
minus promoted stars, the SPOC TCE period sidecar (``tce_sidecar_k1.csv``) and
``k1/manifests/target_refresh_<label>.json``.  Only catalogue metadata is read; no light curve.
"""
from __future__ import annotations

import json
import shutil
import sys

import pandas as pd

from k1_common import ROOT, write, sha, utc
import catalog_adapter_k1 as CA

N_K, N_EM = 7000, 3000


def main(label: str) -> dict:
    sv = ROOT / "survey"
    tg = pd.read_csv(sv / "targets_k1.csv", low_memory=False)
    rs = pd.read_csv(sv / "reserve_k1.csv", low_memory=False)
    led = pd.read_csv(ROOT / "manifests" / "exposure_ledger.csv", dtype=str)              # appended by several writers
    ledger = set(pd.to_numeric(led.tic_id, errors="coerce").dropna().astype("int64"))       # (repeated header rows)
    exposed = sorted(int(t) for t in set(tg.tic_id.astype("int64")) & ledger)
    if exposed:
        raise SystemExit(f"STOP-E: survey-list stars in the exposure ledger: {exposed[:10]}")
    cat = CA.load(label)
    chk = cat.check_many(tg)
    drop = tg[chk.xmatch_status == "REJECT"].assign(reason=chk.xmatch_reject_sources[chk.xmatch_status == "REJECT"])
    keep = tg[chk.xmatch_status != "REJECT"].copy()
    is_em = lambda df: df.k1_type.eq("M_early") if "k1_type" in df else df.k1_class.eq("eM")  # noqa: E731
    need = {"eM": N_EM - int(is_em(keep).sum()), "K": N_K - int((~is_em(keep)).sum())}
    rs = rs.sort_values("rank")
    rchk = cat.check_many(rs)
    cand = rs[(rchk.xmatch_status != "REJECT") & ~rs.tic_id.astype("int64").isin(ledger)
              & ~rs.tic_id.isin(keep.tic_id)]
    add = pd.concat([cand[is_em(cand)].head(max(0, need["eM"])), cand[~is_em(cand)].head(max(0, need["K"]))])
    new = pd.concat([keep, add], ignore_index=True)
    # rank is within slice; the list is the K block (rank order) then the eM block (rank order)
    new = new.assign(_o=new.slice.ne("K").astype(int)).sort_values(["_o", "rank"]).drop(columns="_o").reset_index(drop=True)
    shutil.copyfile(sv / "targets_k1.csv", sv / "targets_k1_prerefresh.csv")
    new.to_csv(sv / "targets_k1.csv", index=False)
    rs[~rs.tic_id.isin(add.tic_id)].to_csv(sv / "reserve_k1.csv", index=False)
    side = cat.tce_sidecar(new.tic_id.astype("int64"))
    side.to_csv(sv / "tce_sidecar_k1.csv", index=False)
    fchk = cat.check_many(new)
    man = {"utc": utc(), "snapshot": label, "n_before": int(len(tg)), "dropped": drop[["tic_id", "rank", "reason"]].to_dict(orient="records"),
           "dropped_by_reason": drop.reason.value_counts().to_dict(), "added": add[["tic_id", "rank"]].to_dict(orient="records"),
           "n_after": int(len(new)), "n_eM": int(is_em(new).sum()), "n_K": int((~is_em(new)).sum()),
           "status_after": fchk.xmatch_status.value_counts().to_dict(), "spoc_tce_flagged": int(fchk.spoc_tce.sum()),
           "exposure_ledger_overlap": exposed, "targets_sha256": sha(sv / "targets_k1.csv"),
           "prerefresh_sha256": sha(sv / "targets_k1_prerefresh.csv"), "tce_sidecar_sha256": sha(sv / "tce_sidecar_k1.csv")}
    write(ROOT / "manifests" / f"target_refresh_{label}.json", man, replace=True)
    return man


if __name__ == "__main__":
    m = main(sys.argv[1] if len(sys.argv) > 1 else "20261014")
    print(json.dumps({k: v for k, v in m.items() if k not in ("dropped", "added")}, indent=1, default=str))
    print("dropped", m["dropped"][:20])
