"""P10.3 acquisition worker, version 2: amendments D1 to D3 of MAIN_REVIEW_20260914.md.

``download_star.py`` (version 1) stays byte-identical; this file replaces it for every
acquisition launched after the pilot. Differences, all registered in
``AMENDMENTS_D1_D4_20260914.md`` before any launch:

  D1  the sector floor is ``config["sector_min"]`` (56), applied both to the search-result
      filter and to ``audit_p5.download(sector_min=...)``; the P8 sector 27 to 55 superset is
      no longer downloaded.
  D2  the 600-second deadline is a controller argument, not a worker change.
  D3  an explicit attempt number and ``--force`` re-index for the retry pass; receipts go to
      ``results/download_v2/tic<id>_a<attempt>.json`` and metadata to
      ``results/acquisition_metadata_v2/tic<id>_a<attempt>.csv`` so version-1 receipts are
      never overwritten; corrupt or partial cached FITS files left by a killed download are
      detected, removed and recorded before the download starts (a truncated FITS is never
      read as data).

Written by the user's Claude session on 2026-09-14 while no controller was alive.
"""
from common import REPO, ROOT, environment, read, write, sha, utc
environment(offline=False)
import sys
import time
import numpy as np
import psutil
sys.path.insert(0, str(REPO / "scripts"))
import p8_download as D
import audit_p5 as A
import lightkurve as lk
from astropy.io import fits
from acquisition_meter import install as install_meter, accounting

POLICY = ("P10.3 acquisition 56-105 (D1); excluded QLP sectors removed before download; "
          "corrupt cached FITS removed before download (D3)")
AMENDMENT = "D1-D3, p10/part3/AMENDMENTS_D1_D4_20260914.md"


def allowed_download_rows(result, configuration):
    lo = int(configuration["sector_min"]); hi = int(configuration["sector_max"])
    excluded = set(int(s) for s in configuration["qlp_excluded_sectors"])
    indices = []
    for i in range(len(result)):
        mission = str(result.mission[i]); author = str(result.author[i])
        sector = int(mission.split()[-1]) if "Sector" in mission else -1
        if not lo <= sector <= hi:
            continue
        if author == "QLP" and sector in excluded:
            continue
        indices.append(i)
    return indices


def remove_corrupt_cached_fits(tic):
    """Open every cached FITS for this star; delete the ones astropy cannot read to the data table."""
    removed = []
    root = A.AUDIT_CACHE / "mastDownload"
    if not root.exists():
        return removed
    for product_dir in root.glob(f"*/*{tic:016d}*"):
        for path in product_dir.glob("*.fits"):
            try:
                with fits.open(path, memmap=False) as handle:
                    _ = handle[1].data.shape
            except Exception as exc:
                removed.append(dict(file=str(path.relative_to(REPO)), bytes=path.stat().st_size,
                                    error=type(exc).__name__))
                path.unlink()
    return removed


def main():
    tic = int(sys.argv[1])
    attempt = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 1
    force = "--force" in sys.argv
    start = time.perf_counter(); started = utc()
    install_meter()
    configuration = read(ROOT / "protocol/config.json")
    removed = remove_corrupt_cached_fits(tic)
    search = lk.search_lightcurve
    calls = 0

    def frozen_search(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise RuntimeError("More than one lightcurve search for a star")
        result = search(*args, **kwargs)
        destination = ROOT / f"results/acquisition_metadata_v2/tic{tic}_a{attempt}.csv"
        destination.parent.mkdir(parents=True, exist_ok=True)
        result.table.write(destination, format="ascii.csv", overwrite=False)
        return result[allowed_download_rows(result, configuration)]

    lk.search_lightcurve = frozen_search
    D.OUT = ROOT / "results/acquisition"
    index_path = D.STORE / f"tic{tic}/index.json"
    previous_index = sha(index_path) if index_path.exists() else None
    t0 = time.perf_counter()
    try:
        idx = A.download(tic, force=force, sector_min=int(configuration["sector_min"]))
        size = sum((D.STORE / f"tic{tic}" / p["file"]).stat().st_size for p in idx["products"] if "file" in p)
        result = {"tic_id": tic, "n_products": idx["n_products"], "n_failed": idx["n_failed"],
                  "bytes": int(size), "seconds": round(time.perf_counter() - t0, 1), "ok": True}
    except Exception as exc:
        result = {"tic_id": tic, "error": f"{type(exc).__name__}: {exc}"[:300],
                  "seconds": round(time.perf_counter() - t0, 1), "ok": False}
    result.update(started_utc=started, completed_utc=utc(), wall_seconds=time.perf_counter() - start,
                  cpu_seconds=time.process_time(), pid=psutil.Process().pid, search_lightcurve_calls=calls,
                  attempt=attempt, force=force, corrupt_cached_fits_removed=removed,
                  previous_index_sha256=previous_index, source_sha256=sha(__file__),
                  policy=POLICY, amendment=AMENDMENT, sector_min=int(configuration["sector_min"]))
    if result["ok"]:
        result["index_sha256"] = sha(index_path)
    meter = accounting()
    result["http_body_bytes"] = meter["workers"].get(str(psutil.Process().pid), 0)
    write(ROOT / f"results/download_v2/tic{tic}_a{attempt}.json", result)
    print(result, flush=True)
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
