"""Download 21x21-pixel TESScut FFI cutouts for every discovery-era (sector <= 98) sector with a predicted event,
plus the TIC 262843927 sectors 31 and 88 (failure diagnosis).  D-orig/D-alt photons only (no sector > 98 here).
Outputs: D:/tess_fu3_cache/cutouts/<tic>_s<sector>.fits, results/s07a_cutout_receipts.json
"""
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor

from astropy.coordinates import SkyCoord
import astropy.units as u
from astroquery.mast import Tesscut

from fu3_common import *

OUT = CACHE / "cutouts"
OUT.mkdir(parents=True, exist_ok=True)
COORD = {270573718: (86.722905, -52.816629), 262843927: (52.573211, -63.501800), 193718989: (267.554464, 42.109629)}
SIZE = 21


def jobs():
    js = []
    for tic in TICS:
        ev = read(RES / f"s02_events_{tic}.json")
        secs = sorted({r["sector"] for r in ev["events"] if r["reduction"] == "pdc_raw" and r["sector"] <= 98})
        if tic == 262843927:
            secs = sorted(set(secs) | {31, 88})
        js += [(tic, s) for s in secs]
    return js


def fetch(job):
    tic, s = job
    dest = OUT / f"{tic}_s{s}.fits"
    rec = dict(tic=tic, sector=s, size=SIZE, dest=str(dest), start_utc=utc())
    if dest.exists() and dest.read_bytes()[:6] == b"SIMPLE":
        rec.update(status="CACHED", bytes=dest.stat().st_size, sha256=sha256(dest))
        return rec
    tmp = Path(tempfile.mkdtemp(dir=str(OUT)))
    try:
        c = SkyCoord(*COORD[tic], unit="deg")
        tab = Tesscut.download_cutouts(coordinates=c, size=SIZE, sector=s, path=str(tmp))
        files = list(tmp.glob("*.fits"))
        if not files:
            rec.update(status="NO_FILE", table=str(tab)[:300])
        else:
            shutil.move(str(files[0]), dest)
            rec.update(status="OK", source_name=files[0].name, bytes=dest.stat().st_size, sha256=sha256(dest))
    except Exception as exc:   # noqa: BLE001
        rec.update(status="ERROR", error=repr(exc)[:500])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    rec["end_utc"] = utc()
    log("s07a", f"{tic} s{s}: {rec['status']} {rec.get('bytes')}")
    return rec


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=3) as ex:
        recs = list(ex.map(fetch, jobs()))
    save(RES / "s07a_cutout_receipts.json", recs)
