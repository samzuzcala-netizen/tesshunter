"""Build the pool-wide sidecar and record the A/B/C census without searching."""
from collections import Counter
import json
import math
import time
import pandas as pd
from common import REPO, ROOT, read, write, sha, utc
from catalog_adapter import install, EPHEMERIS_COLUMNS
from tce_families import counts, families


def catalog_evidence_hashes():
    paths = set()
    for path in (REPO/"data/cache/catalogs").rglob("*"):
        if path.is_file() and "raw" not in path.parts and path.suffix in (".csv",".json") and "ephemerides" not in path.name:
            paths.add(path)
    for path in (REPO/"data/survey").rglob("*.json"):
        if "crossmatch" in path.name.lower():
            paths.add(path)
    paths.add(REPO/"data/survey/cache/p8/pool_after_xmatch.csv")
    return {p.relative_to(REPO).as_posix():sha(p) for p in sorted(paths)}


def main():
    started=time.perf_counter()
    cx=install()
    before=catalog_evidence_hashes()
    write(ROOT/"manifests/crossmatch_before.json",before)
    pool=pd.read_csv(REPO/"data/survey/cache/p8/pool_after_xmatch.csv",low_memory=False)
    paths=sorted((REPO/"data/cache/catalogs/spoc_tce/raw").glob("*_dvr-tcestats.csv"))
    source=ROOT/"manifests/spoc_raw_files.json"
    write(source, {p.relative_to(REPO).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in paths})
    sidecar=REPO/"data/cache/catalogs/spoc_tce/spoc_tce.ephemerides.csv"
    normalized=cx._parse_spoc_tce(((p.name,p.read_bytes()) for p in paths),
        ephemerides_path=sidecar,pool_tics=pool.tic_id)
    frame=pd.read_csv(sidecar,dtype={"tceid":str})
    original=read(ROOT/"manifests/original_531.json")
    original_ids={r["tic_id"] for r in original}
    eligible_ids={r["tic_id"] for r in original if r["after_a_eligible"]}
    # JSON-safe values; retain missing errors as null rather than silently zero.
    safe=json.loads(frame.to_json(orient="records",double_precision=15))
    selected=[r for r in safe if int(r["ticid"]) in original_ids]
    eligible=[r for r in selected if int(r["ticid"]) in eligible_ids]
    write(ROOT/"manifests/sidecar.json",dict(utc=utc(),path=sidecar.relative_to(REPO).as_posix(),
        sha256=sha(sidecar),bytes=sidecar.stat().st_size,rows=len(frame),
        pool_tics=len(pool),raw_files=len(paths),raw_rows=normalized.attrs["p10_3_raw_rows"],
        columns=list(frame.columns), source_manifest_sha256=sha(source),
        units=dict(tce_period="days",tce_time0bt="BTJD",tce_duration="hours",tce_depth="ppm")))
    write(ROOT/"results/tce_census.json",dict(utc=utc(),original_531=counts(selected),
        after_a=counts(eligible),stage="B; after-A power upper bound, not STOP-1 decision",
        row_median=float(pd.Series(Counter(int(r["ticid"]) for r in selected)).median()),
        row_max=max(Counter(int(r["ticid"]) for r in selected).values()),
        source_sha256=sha(__file__)))
    cat=cx.KnownObjectCatalog.load(offline=True,allow_stale=True)
    lookup={int(t):[] for t in frame.ticid.unique()}
    for row in safe:
        lookup[int(row["ticid"])].append(row)
    identity_rows=[]
    target_lookup=pool.set_index("tic_id")
    for tic in sorted(original_ids):
        metadata=target_lookup.loc[tic]
        old=cx.hard_stop(tic,metadata.ra,metadata.dec,catalog=cat,resolve_neighbours=False)
        new=cx.hard_stop_p10(tic,metadata.ra,metadata.dec,catalog=cat,resolve_neighbours=False,ephemerides=lookup[tic])
        identity_rows.append(dict(tic_id=tic,old=old.status,new=new.status,record=new.to_dict()))
    if any(r["old"]!="REJECT" or r["new"]!="FLAG" for r in identity_rows):
        raise RuntimeError("531 population rule compatibility failed")
    original_p8=pd.read_csv(REPO/"data/survey/targets_p8.csv")
    compatibility=[]
    for r in original_p8.itertuples():
        old=cx.hard_stop(r.tic_id,r.ra_deg,r.dec_deg,catalog=cat,resolve_neighbours=False)
        new=cx.hard_stop_p10(r.tic_id,r.ra_deg,r.dec_deg,catalog=cat,resolve_neighbours=False,ephemerides=lookup.get(r.tic_id,[]))
        compatibility.append(dict(tic_id=int(r.tic_id),unchanged=old.to_dict()==new.to_dict(),status=old.status))
    if not all(r["unchanged"] for r in compatibility):
        raise RuntimeError("P8 population changed under new rule")
    after=catalog_evidence_hashes()
    if before!=after:
        raise RuntimeError("STOP-4: Crossmatch evidence changed")
    write(ROOT/"results/hard_stop_p10.json",dict(utc=utc(),original=identity_rows,p8=compatibility,
        original_flag_count=531,p8_unchanged_count=len(compatibility),
        normalized_and_digests_unchanged=True,crossmatch_hashes_after=after,
        sealed_source_unchanged=sha(REPO/"src/tesshunter/catalog_crossmatch.py"),
        adapter_source_sha256=sha(ROOT/"protocol/catalog_adapter.py"),
        wall_seconds=time.perf_counter()-started))
    exposure=read(ROOT/"manifests/exposure_ledger.json")
    exposure["stages"].append(dict(stage="B/C",utc=utc(),tics=sorted(original_ids),
        content="catalogue ephemeris census and population rule; no search predictions or forced fits"))
    write(ROOT/"manifests/exposure_ledger.json",exposure,replace=True)
    print(json.dumps(read(ROOT/"results/tce_census.json"),indent=2),flush=True)
    print("hard_stop_p10: 531 FLAG; 2000 P8 unchanged; catalogue hashes unchanged",flush=True)


if __name__=="__main__":
    main()
