"""P12 destination copy of build_sidecar; preserve the origin parser/schema."""
import argparse
import time

import pandas as pd

from p12_common import REPO, ROOT, DATA, write, sha, utc, append_jsonl
from catalog_adapter_p12 import install, EPHEMERIS_COLUMNS


def catalog_evidence_hashes():
    # Hashing reads bytes only. Never load historical sidecar rows into this process.
    root = REPO / "data/cache/catalogs"
    return {p.relative_to(REPO).as_posix(): sha(p) for p in sorted(root.rglob("*")) if p.is_file()}


def build() -> dict:
    started = time.perf_counter()
    cx = install()
    cx.CATALOG_CACHE_DIR = DATA / "catalogs"
    before = catalog_evidence_hashes()
    pool = pd.read_csv(REPO / "data/survey/cache/p8/pool_after_xmatch.csv", low_memory=False)
    paths = sorted((DATA / "catalogs/spoc_tce/raw").glob("*_dvr-tcestats.csv"))
    source_hashes = {p.relative_to(REPO).as_posix(): sha(p) for p in paths}
    sidecar = DATA / "catalogs/spoc_tce/spoc_tce.ephemerides.csv"
    normalized = cx._parse_spoc_tce(((p.name, p.read_bytes()) for p in paths),
        ephemerides_path=sidecar, pool_tics=pool.tic_id)
    frame = pd.read_csv(sidecar, dtype={"tceid": str})
    receipt = dict(utc=utc(), path=sidecar.relative_to(REPO).as_posix(),
        sha256=sha(sidecar), bytes=sidecar.stat().st_size, rows=len(frame),
        pool_tics=len(pool), raw_files=len(paths), raw_rows=normalized.attrs["p10_3_raw_rows"],
        columns=list(frame.columns), source_hashes=source_hashes,
        units=dict(tce_period="days", tce_time0bt="BTJD", tce_duration="hours", tce_depth="ppm"),
        source_sha256=sha(__file__), wall_seconds=time.perf_counter() - started)
    for tic in sorted(frame.ticid.unique()):
        append_jsonl(ROOT / "manifests/exposure_ledger.jsonl", dict(utc=utc(), star=int(tic),
            stage="0d sidecar build", path=sidecar.relative_to(REPO).as_posix(),
            reader="build_sidecar_p12.py", prompt_of_origin="P12",
            content="catalogue ephemeris rows; no search predictions"))
    after = catalog_evidence_hashes()
    if before != after:
        raise RuntimeError("STOP-1: historical catalogue bytes changed while building P12 sidecar")
    receipt["historical_catalogue_hashes_unchanged"] = True
    write(ROOT / "manifests/sidecar_p12.json", receipt)
    return receipt


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    receipt = build()
    print(f"P12 sidecar: {receipt['rows']} rows; historical catalogue hashes unchanged", flush=True)


if __name__ == "__main__":
    main()
