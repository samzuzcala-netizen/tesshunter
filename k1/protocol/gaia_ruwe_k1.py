"""Gaia DR3 RUWE for the K1 survey and reserve lists (flag ruwe_gt_1p4; never a cut).

The TIC v8.2 ``GAIA`` column is a DR2 source_id.  DR3 RUWE comes from ``gaiadr3.dr2_neighbourhood``
(the DR2 -> DR3 match, best angular distance) joined to ``gaiadr3.gaia_source``, queried in chunks of
2,000 ids, each call bounded in a daemon thread (gotcha 8): ESA's TAP first, the ARI Heidelberg mirror
(the Oct 4 transport repair) when ESA fails or exceeds the bound.  Writes
``D:/tesshunter_k1/pop/gaia_ruwe.csv`` and a receipt; unknowns stay unknown.
"""
from __future__ import annotations

import io
import json
import threading
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from k1_common import ROOT, DATA, write, utc

ENDPOINTS = (("esa", "https://gea.esac.esa.int/tap-server/tap/sync"),
             ("ari", "https://gaia.ari.uni-heidelberg.de/tap/sync"))


def _sync(url, adql, timeout=300):
    data = urllib.parse.urlencode({"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": adql}).encode()
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "tesshunter K1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return pd.read_csv(io.BytesIO(r.read()))


def bounded(url, adql, limit=420):
    box = {}

    def run():
        try:
            box["df"] = _sync(url, adql)
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc
    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(limit)
    if th.is_alive():
        raise TimeoutError(f"{url} exceeded {limit} s")
    if "error" in box:
        raise box["error"]
    return box["df"]


def query_chunk(ids):
    lst = ",".join(str(int(i)) for i in ids)
    adql = ("SELECT n.dr2_source_id, n.dr3_source_id, n.angular_distance, g.ruwe FROM gaiadr3.dr2_neighbourhood AS n "
            f"JOIN gaiadr3.gaia_source AS g ON g.source_id = n.dr3_source_id WHERE n.dr2_source_id IN ({lst})")
    errors = []
    for name, url in ENDPOINTS:
        for attempt in range(2):
            try:
                df = bounded(url, adql)
                df.columns = [c.lower() for c in df.columns]
                df = df.sort_values("angular_distance").drop_duplicates("dr2_source_id")
                return df, name, errors
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{name} attempt {attempt + 1}: {type(exc).__name__}: {str(exc)[:120]}")
                time.sleep(5 * (attempt + 1))
    return None, None, errors


def main():
    survey = pd.read_csv(ROOT / "survey" / "targets_k1.csv", usecols=["tic_id", "GAIA"])
    reserve = pd.read_csv(ROOT / "survey" / "reserve_k1.csv", usecols=["tic_id", "GAIA"])
    stars = pd.concat([survey, reserve]).drop_duplicates("tic_id")
    stars["GAIA"] = pd.to_numeric(stars["GAIA"], errors="coerce")
    ids = stars["GAIA"].dropna().astype("int64").unique()
    frames, log = [], []
    for a in range(0, len(ids), 2000):
        df, endpoint, errors = query_chunk(ids[a:a + 2000])
        log.append({"chunk": a // 2000, "n": int(min(2000, len(ids) - a)), "endpoint": endpoint, "errors": errors,
                    "rows": None if df is None else int(len(df))})
        if df is not None:
            frames.append(df)
        print(log[-1], flush=True)
    res = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["dr2_source_id", "ruwe"])
    out = stars.merge(res.rename(columns={"dr2_source_id": "GAIA"}), on="GAIA", how="left")
    out.to_csv(DATA / "pop" / "gaia_ruwe.csv", index=False)
    receipt = {"utc": utc(), "n_stars": int(len(stars)), "n_with_dr2_id": int(stars.GAIA.notna().sum()),
               "n_with_ruwe": int(out.ruwe.notna().sum()), "n_ruwe_gt_1p4": int((out.ruwe > 1.4).sum()),
               "chunks": log}
    write(ROOT / "manifests" / "gaia_ruwe_receipt.json", receipt, replace=True)
    print(json.dumps({k: v for k, v in receipt.items() if k != "chunks"}))


if __name__ == "__main__":
    main()
