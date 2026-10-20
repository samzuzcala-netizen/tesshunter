"""K1 change 9: the K1 hard stop (pattern of p10/part3/protocol/catalog_adapter.py; nothing in src edited).

On the K1 catalogue snapshot (``k1/protocol/snapshot_k1.py``):
* REJECT: the star's TIC ID is a TOI, a CTOI (including the 1,173 RAVEN CTOIs of 2026-08-27), a
  NASA Exoplanet Archive host (ps or pscomppars), a TESS EB (Prsa et al. 2022) or a TESS Ten
  Thousand EB (Kostov et al. 2025, tables 3 and 4).
* FLAG ``known_object_within_21arcsec``: any of those objects, or a SPOC TCE host, lies within 21"
  (one TESS pixel) of the star (the star itself excluded).
* FLAG ``spoc_tce``: the star carries a SPOC TCE (and no REJECT source).  The TCE periods go into a
  sidecar that Stage D / the candidate list use as a VETO for matching periods, never a REJECT.
Vectorised over a whole pool; ``check(tic, ra, dec)`` for one star.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from k1_common import DATA

REJECT_SOURCES = ("toi", "ctoi", "nasa_ps", "nasa_pscomppars", "tess_eb", "ttt3", "ttt4")
FLAG_RADIUS_ARCSEC = 21.0
STATUS = ("REJECT", "FLAG", "CLEAN")


def _unit(ra, dec):
    ra = np.radians(np.asarray(ra, float)); dec = np.radians(np.asarray(dec, float))
    return np.column_stack([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)])


class K1Catalog:
    def __init__(self, snap_dir: Path):
        self.snap = Path(snap_dir)
        frames = {}
        for n in ("toi", "ctoi", "nasa_ps", "nasa_pscomppars", "tess_eb", "spoc_tce"):
            df = pd.read_csv(self.snap / n / f"{n}.normalized.csv", low_memory=False)
            df["tic_id"] = pd.to_numeric(df["tic_id"], errors="coerce")
            frames[n] = df
        for num in (3, 4):
            t = pd.read_csv(self.snap / "ttt" / f"ttt_table{num}.csv")
            frames[f"ttt{num}"] = pd.DataFrame({"source": f"ttt{num}", "tic_id": t["tic_id"], "ra": t["RAdeg"],
                                                "dec": t["DEdeg"], "label": "TTT-EB " + t["tic_id"].astype(str),
                                                "detail": "P=" + t["period_days"].astype(str) + "d"})
        self.frames = frames
        self.reject_tics = {n: set(frames[n]["tic_id"].dropna().astype("int64")) for n in REJECT_SOURCES}
        self.tce_tics = set(frames["spoc_tce"]["tic_id"].dropna().astype("int64"))
        allc = pd.concat([frames[n][["source", "tic_id", "ra", "dec", "label"]] for n in frames], ignore_index=True)
        allc = allc[np.isfinite(allc.ra.astype(float)) & np.isfinite(allc.dec.astype(float))]
        allc = allc.drop_duplicates(["source", "tic_id", "label"]).reset_index(drop=True)
        self.objects = allc
        from scipy.spatial import cKDTree
        self.tree = cKDTree(_unit(allc.ra, allc.dec))

    def tce_sidecar(self, tics) -> pd.DataFrame:
        tce = self.frames["spoc_tce"]
        sub = tce[tce.tic_id.isin(set(int(t) for t in tics))].copy()
        sub["tce_period_days"] = sub["detail"].astype(str).map(
            lambda s: float(m.group(1)) if (m := re.search(r"P=([0-9.eE+-]+)d", s)) else np.nan)
        sub["tce_snr"] = sub["detail"].astype(str).map(
            lambda s: float(m.group(1)) if (m := re.search(r"SNR=([0-9.eE+-]+)", s)) else np.nan)
        sub["tce_run"] = sub["label"].astype(str).str.extract(r"TCE (s\d+-s\d+)")[0]
        return sub[["tic_id", "tce_run", "label", "tce_period_days", "tce_snr"]].reset_index(drop=True)

    def check_many(self, pool: pd.DataFrame) -> pd.DataFrame:
        tics = pool["tic_id"].astype("int64").to_numpy()
        status = np.full(len(tics), "CLEAN", dtype=object)
        reasons = [[] for _ in tics]
        for n in REJECT_SOURCES:
            hit = np.isin(tics, np.fromiter(self.reject_tics[n], dtype=np.int64))
            for i in np.flatnonzero(hit):
                reasons[i].append(n)
        rej = np.array([bool(r) for r in reasons])
        status[rej] = "REJECT"
        tce = np.isin(tics, np.fromiter(self.tce_tics, dtype=np.int64))
        chord = 2.0 * np.sin(np.radians(FLAG_RADIUS_ARCSEC / 3600.0) / 2.0)
        hits = self.tree.query_ball_point(_unit(pool["ra"], pool["dec"]), r=chord)
        near = []
        obj_tic = self.objects.tic_id.to_numpy()
        obj_src = self.objects.source.to_numpy()
        for i, idx in enumerate(hits):
            others = [(obj_src[j], obj_tic[j]) for j in idx if not (np.isfinite(obj_tic[j]) and int(obj_tic[j]) == tics[i])]
            near.append(sorted({f"{s}:{int(t) if np.isfinite(t) else 'na'}" for s, t in others}))
        flags = []
        for i in range(len(tics)):
            f = []
            if tce[i]:
                f.append("spoc_tce")
            if near[i]:
                f.append("known_object_within_21arcsec")
            flags.append(f)
            if status[i] == "CLEAN" and f:
                status[i] = "FLAG"
        return pd.DataFrame({"xmatch_status": status, "xmatch_reject_sources": [";".join(r) for r in reasons],
                             "xmatch_flags": [";".join(f) for f in flags],
                             "xmatch_neighbours_21arcsec": [";".join(n[:10]) for n in near],
                             "spoc_tce": tce}, index=pool.index)

    def check(self, tic: int, ra: float, dec: float) -> dict:
        r = self.check_many(pd.DataFrame({"tic_id": [int(tic)], "ra": [float(ra)], "dec": [float(dec)]}))
        out = r.iloc[0].to_dict()
        out["tce_sidecar"] = self.tce_sidecar([tic]).to_dict(orient="records")
        return out


def load(label: str = "20261008") -> K1Catalog:
    return K1Catalog(DATA / "catalogs" / f"snap_{label}")


def tce_period_veto(period: float, sidecar_rows: list[dict], tol: float = 0.01) -> dict:
    """A candidate whose period is within 1% of a TCE period of the same star (at ratios 1, 2, 1/2)
    is vetoed (the star's own SPOC TCE; not new)."""
    for r in sidecar_rows:
        p = r.get("tce_period_days")
        if p is None or not np.isfinite(p) or p <= 0:
            continue
        for ratio in (1.0, 2.0, 0.5):
            if abs(period / (p * ratio) - 1.0) < tol:
                return {"veto": True, "tce_period_days": p, "ratio": ratio, "tce_run": r.get("tce_run")}
    return {"veto": False}


def crossmatch_record(cat: K1Catalog, tic: int, ra: float, dec: float) -> dict:
    """The hard-stop record in the shape the p10/p12 tiers read (K0 status, K5/H4 catalogue periods)."""
    tic = int(tic)
    r = cat.check(tic, ra, dec)
    matches = []
    for n, f in cat.frames.items():
        sub = f[f.tic_id == tic]
        for _, row in sub.iterrows():
            matches.append({"source": n, "label": str(row.get("label")), "detail": str(row.get("detail"))})
    neighbours = [x for x in str(r["xmatch_neighbours_21arcsec"]).split(";") if x]
    return {"tic_id": tic, "status": r["xmatch_status"], "tic_matches": matches[:50],
            "neighbour_matches": [{"source": x.split(":")[0], "tic_id": x.split(":")[1]} for x in neighbours],
            "catalog_stamp": f"k1:{cat.snap.name}", "flags": r["xmatch_flags"], "tce_sidecar": r["tce_sidecar"]}
