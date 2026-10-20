#!/usr/bin/env python
"""Cut recorded test fixtures and the acceptance ID lists from the live catalog cache.

Run once after ``KnownObjectCatalog.load()`` has populated ``data/cache/catalogs``::

    python scripts/build_crossmatch_fixtures.py

Writes ``tests/fixtures/catalogs/``: trimmed raw copies of every source
(acceptance rows plus a seeded random sample), a fake MAST index page for the
SPOC TCE files, and ``acceptance_ids.json`` holding 20 TOIs, 20 CTOIs (never
promoted), 10 TESS EBs, 10 TCE-only stars, 20 clean stars with real TIC
coordinates, and a few real "known object within 21 arcsec" flag cases.  Every
list is verified against the live catalog before it is written.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data" / "cache" / "lightkurve"))
warnings.simplefilter("ignore")

from tesshunter import catalog_crossmatch as cx  # noqa: E402

FIX = REPO / "tests" / "fixtures" / "catalogs"
SEED = 20260901

# Hand-picked, widely known TOI hosts (TIC ID -> name).  Only those present in
# the live TOI list are used; the list is topped up with seeded random TOIs.
FAMOUS_TOIS = {
    150428135: "TOI-700", 261136679: "Pi Men / TOI-144", 410153553: "LHS 3844 / TOI-136",
    259377017: "TOI-270", 100100827: "WASP-18 / TOI-185", 307210830: "L 98-59 / TOI-175",
    98796344: "LTT 1445A / TOI-455", 141527579: "TOI-1338", 231663901: "TOI-101",
    22221375: "TOI-125", 300038935: "TOI-431", 350153977: "TOI-178",
    441462736: "AU Mic / TOI-2221", 200723869: "TOI-1130", 445751830: "TOI-561",
    38846515: "WASP-62 / TOI-115", 425997655: "TOI-1136", 219195044: "TOI-1266",
    260004324: "TOI-1246", 29857954: "TOI-1695",
}


def main() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    (FIX / "spoc_tce").mkdir(exist_ok=True)
    cat = cx.KnownObjectCatalog.load(offline=True)
    if cat.any_stale():
        raise SystemExit("catalog cache is stale; refresh it first")
    T = cat.tables
    rng = np.random.default_rng(SEED)

    toi_set = set(T["toi"]["tic_id"])
    tois = [t for t in FAMOUS_TOIS if t in toi_set][:20]
    if len(tois) < 20:
        extra = rng.choice(sorted(toi_set - set(tois)), 40, replace=False)
        tois += [int(x) for x in extra][: 20 - len(tois)]
    print("TOIs picked:", len(tois), [FAMOUS_TOIS.get(t, "random") for t in tois])

    c = T["ctoi"]
    not_prom = c[~c["tic_id"].isin(toi_set) & (c["detail"].str.strip() == "promoted_to_TOI=")]
    ctois = [int(x) for x in rng.choice(np.unique(not_prom["tic_id"]), 20, replace=False)]

    eb = T["tess_eb"]
    eb_only = eb[~eb["tic_id"].isin(toi_set | set(c["tic_id"]))]
    ebs = [int(x) for x in rng.choice(np.unique(eb_only["tic_id"]), 10, replace=False)]

    others: set[int] = set()
    for n, df in T.items():
        if n != "spoc_tce":
            others |= set(df["tic_id"])
    tce = T["spoc_tce"]
    tce_only_ids = np.unique(tce.loc[~tce["tic_id"].isin(others), "tic_id"])
    tce_only = [int(x) for x in rng.choice(tce_only_ids, 10, replace=False)]
    print("TCE-only pool size:", len(tce_only_ids))

    # 20 clean stars from a real TIC cone query, verified CLEAN with real neighbours
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    from astroquery.mast import Catalogs

    cone = {"ra": 60.0, "dec": -55.0, "radius_deg": 0.4}
    centre = SkyCoord(ra=cone["ra"], dec=cone["dec"], unit="deg")
    tab = Catalogs.query_criteria(catalog="Tic", coordinates=centre, radius=cone["radius_deg"],
                                  Tmag=[10.5, 13.5], objType="STAR")
    allt = Catalogs.query_criteria(catalog="Tic", coordinates=centre, radius=cone["radius_deg"] + 0.05,
                                   Tmag=[-5, 17.0], objType="STAR")
    stars = tab.to_pandas()[["ID", "ra", "dec", "Tmag"]].rename(columns={"ID": "tic_id"})
    stars["tic_id"] = stars["tic_id"].astype("int64")
    neigh = allt.to_pandas()[["ID", "ra", "dec"]].rename(columns={"ID": "tic_id"})
    neigh["tic_id"] = neigh["tic_id"].astype("int64")
    res = cat.check_many(stars, neigh)
    clean_df = stars[res["xmatch_status"].to_numpy() == "CLEAN"]
    clean_df = clean_df.iloc[rng.permutation(len(clean_df))[:20]]
    clean = [{"tic_id": int(r.tic_id), "ra": float(r.ra), "dec": float(r.dec), "tmag": float(r.Tmag)}
             for r in clean_df.itertuples()]
    print("clean cone: total", len(stars), "clean", int((res["xmatch_status"] == "CLEAN").sum()),
          "picked", len(clean))

    def coords_of(src, t):
        df = T[src]
        r = df[df["tic_id"] == t].iloc[0]
        return float(r["ra"]), float(r["dec"])

    for src, ids in (("toi", tois), ("ctoi", ctois), ("tess_eb", ebs)):
        for t in ids:
            ra, dec = coords_of(src, t)
            r = cat.check(t, ra, dec)
            assert r.rejected and any(m["source"] == src for m in r.tic_matches), (src, t, r.summary())
    for t in tce_only:
        r = cat.check(t)
        assert r.rejected and {m["source"] for m in r.tic_matches} == {"spoc_tce"}, (t, r.summary())
    for s in clean:
        r = cat.check(s["tic_id"], s["ra"], s["dec"], neighbour_tics=[])
        assert r.status == "CLEAN", (s, r.summary())
    print("live verification of all 80 acceptance IDs OK")

    # real FLAG cases: an unknown TIC star within 21 arcsec of a TOI
    flag_cases = []
    known = cat.known_tics()
    toi_tab = T["toi"].dropna(subset=["ra", "dec"]).drop_duplicates("tic_id").head(400)
    for r in toi_tab.itertuples():
        try:
            nb = Catalogs.query_region(SkyCoord(ra=r.ra, dec=r.dec, unit="deg"),
                                       radius=21 * u.arcsec, catalog="Tic")
        except Exception:
            continue
        for row in nb:
            t = int(row["ID"])
            if t != int(r.tic_id) and t not in known:
                flag_cases.append({"tic_id": t, "ra": float(row["ra"]), "dec": float(row["dec"]),
                                   "near_known_tic": int(r.tic_id), "near_label": r.label})
                break
        if len(flag_cases) >= 3:
            break
    for fc in flag_cases:
        r = cat.check(fc["tic_id"], fc["ra"], fc["dec"], neighbour_tics=[(fc["near_known_tic"], 10.0)])
        assert r.flagged, (fc, r.summary())
    print("flag cases:", flag_cases)

    acc = {"catalog_stamp": cat.stamp(),
           "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "toi": tois, "toi_names": {str(t): FAMOUS_TOIS.get(t, "random") for t in tois},
           "ctoi": ctois, "tess_eb": ebs, "tce_only": tce_only, "clean": clean,
           "flag_cases": flag_cases, "clean_cone": cone}
    (FIX / "acceptance_ids.json").write_text(json.dumps(acc, indent=1))

    RAW = Path(cx.CATALOG_CACHE_DIR)

    def trim_csv(raw_path, out_path, tic_col_regex, keep_ids, n_random=30, comment="#"):
        text = raw_path.read_text(encoding="utf-8", errors="replace").splitlines()
        head = [ln for ln in text if ln.startswith(comment)] if comment else []
        body = [ln for ln in text if not (comment and ln.startswith(comment))]
        header, rows = body[0], body[1:]
        df = pd.read_csv(io.StringIO("\n".join([header] + rows)), low_memory=False,
                         dtype=str, keep_default_na=False)
        col = [c_ for c_ in df.columns if re.fullmatch(tic_col_regex, c_)][0]
        ids = df[col].str.extract(r"(\d+)", expand=False)
        keep = ids.isin([str(k) for k in keep_ids]).to_numpy()
        idx = np.flatnonzero(keep)
        rest = np.flatnonzero(~keep)
        pick = np.sort(np.concatenate([idx, rng.choice(rest, min(n_random, len(rest)), replace=False)]))
        lines = [rows[i] for i in pick]
        out_path.write_text("\n".join(head + [header] + lines) + "\n", encoding="utf-8")
        return len(lines)

    toi_keep = tois + [fc["near_known_tic"] for fc in flag_cases]   # flag cases need their TOI in the fixture
    print("toi rows", trim_csv(RAW / "toi/raw/exofop_toi.csv", FIX / "exofop_toi.csv", r"TIC ID", toi_keep, comment=None))
    print("ctoi rows", trim_csv(RAW / "ctoi/raw/exofop_ctoi.csv", FIX / "exofop_ctoi.csv", r"TIC ID", ctois, comment=None))
    print("ps rows", trim_csv(RAW / "nasa_ps/raw/nasa_ps.csv", FIX / "nasa_ps.csv", r"tic_id", tois[:5], comment=None))
    print("pscomppars rows", trim_csv(RAW / "nasa_pscomppars/raw/nasa_pscomppars.csv", FIX / "nasa_pscomppars.csv", r"tic_id", tois[:5], comment=None))
    print("eb rows", trim_csv(RAW / "tess_eb/raw/hlsp_tess-ebs_s0001-s0026_v1.0_cat.csv",
                              FIX / "hlsp_tess-ebs_s0001-s0026_v1.0_cat.csv", r"tess_id", ebs, comment=None))

    # SPOC TCE: the raw files that carry the TCE-only IDs (one per run), trimmed
    tce_rows = tce[tce["tic_id"].isin(tce_only)]
    runs = tce_rows["label"].str.extract(r"TCE (s\d{4}-s\d{4})", expand=False).unique()
    raw_files = sorted((RAW / "spoc_tce/raw").glob("*.csv"))
    chosen = []
    for run in runs:
        for f in raw_files:
            if run in f.name and f not in chosen:
                chosen.append(f)
                break
    covered = set()
    for f in chosen:
        body = f.read_text(encoding="utf-8", errors="replace")
        for t in tce_only:
            if re.search(rf"^0*{t}-\d\d,{t},", body, flags=re.M):
                covered.add(t)
    missing = set(tce_only) - covered
    assert not missing, f"tce_only ids not covered by chosen files: {missing}"
    names = []
    for f in chosen:
        out = FIX / "spoc_tce" / f.name.replace("new_versions__", "")
        n = trim_csv(f, out, r"ticid", tce_only, n_random=15, comment="#")
        names.append(out.name)
        print("tce fixture", out.name, "rows", n)
    # TCE host coordinates: every TIC ID in the trimmed TCE fixtures, from the live coordinate cache,
    # plus two recorded edge cases the tile-based neighbour list could never contain:
    #   * a real TCE host fainter than Tmag 17 (the tile queries stopped at 17);
    #   * a real TCE host recorded as 'boundary' (tests place a target 10 arcsec from it with an
    #     EMPTY neighbour table, i.e. the host lies outside the target's tile).
    coords = pd.read_csv(RAW / "spoc_tce" / "tic_coords.csv")
    coords["tic_id"] = coords["tic_id"].astype("int64")
    known_ids = cat.known_tics()
    faint = coords[(coords["tmag"] > 17.5) & coords["tic_id"].isin(tce_only_ids)].sort_values("tmag")
    faint_host = faint.iloc[0] if len(faint) else None
    bright_only = coords[coords["tic_id"].isin(tce_only_ids) & (coords["tmag"] < 12)]
    boundary_host = bright_only.iloc[len(bright_only) // 2] if len(bright_only) else None
    extra_ids = {int(h["tic_id"]) for h in (faint_host, boundary_host) if h is not None}
    edge = {"faint_tce_host": None if faint_host is None else
            {"tic_id": int(faint_host["tic_id"]), "ra": float(faint_host["ra"]), "dec": float(faint_host["dec"]),
             "tmag": float(faint_host["tmag"])},
            "boundary_tce_host": None if boundary_host is None else
            {"tic_id": int(boundary_host["tic_id"]), "ra": float(boundary_host["ra"]), "dec": float(boundary_host["dec"]),
             "tmag": float(boundary_host["tmag"])}}
    # the extra hosts must also appear in a TCE fixture file so the fixture catalog knows them as TCEs
    extra_rows = tce[tce["tic_id"].isin(extra_ids)]
    if len(extra_rows):
        runs_extra = extra_rows["label"].str.extract(r"TCE (s\d{4}-s\d{4})", expand=False).unique()
        for run in runs_extra:
            src = next((f for f in raw_files if run in f.name), None)
            if src is None:
                continue
            out = FIX / "spoc_tce" / src.name.replace("new_versions__", "")
            keep = sorted(set(tce_only) | {int(t) for t in extra_rows.loc[extra_rows["label"].str.contains(run), "tic_id"]})
            n = trim_csv(src, out, r"ticid", keep, n_random=15, comment="#")
            if out.name not in names:
                names.append(out.name)
            print("tce fixture (edge cases)", out.name, "rows", n)
    fixture_tce_ids = set()
    for nm in names:
        body = (FIX / "spoc_tce" / nm).read_text(encoding="utf-8")
        for line in body.splitlines():
            if line.startswith("#") or line.startswith("tceid"):
                continue
            try:
                fixture_tce_ids.add(int(line.split(",")[1]))
            except (IndexError, ValueError):
                pass
    fix_coords = coords[coords["tic_id"].isin(fixture_tce_ids | extra_ids)].copy()
    assert fixture_tce_ids <= set(fix_coords["tic_id"]), "every fixture TCE host needs a coordinate row"
    fix_coords.to_csv(FIX / "spoc_tce_tic_coords.csv", index=False)
    acc["tce_edge_cases"] = edge
    acc["tce_coords_provenance"] = json.loads((RAW / "spoc_tce" / "tic_coords.meta.json").read_text()).get("provenance")
    (FIX / "acceptance_ids.json").write_text(json.dumps(acc, indent=1))
    print("tce coordinate fixture rows:", len(fix_coords), "edge cases:", edge)
    idx_html = "<html><body>\n" + "\n".join(f'<a href="{nm}">{nm}</a>' for nm in names) + "\n</body></html>\n"
    (FIX / "spoc_tce_index.html").write_text(idx_html)
    (FIX / "spoc_tce_new_versions_index.html").write_text("<html><body>\n</body></html>\n")
    files = sorted(p for p in FIX.rglob("*") if p.is_file())
    print("fixture files:", [p.name for p in files])
    print("fixture bytes:", sum(p.stat().st_size for p in files))


if __name__ == "__main__":
    main()
