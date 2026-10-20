"""Amendment A1.2: TGLC light curves (Han & Brandt) for every FU3 sector <= 55 with a predicted event.

Files are fetched from MAST's deterministic HLSP path (the documented sector target lists are streamed only when
the path returns 404, bounded to 300 s).  These are D-alt reductions of the same FFI photons, not new epochs.
Outputs: D:/tess_fu3_cache/tglc/*.fits, results/s05_tglc_receipts.json
"""
import time

import requests
from astropy.io import fits

from fu3_common import *

OUT = CACHE / "tglc"
OUT.mkdir(parents=True, exist_ok=True)
GAIA = {270573718: "4792202879700135040", 262843927: "4673750877131752832", 193718989: "1346023547769345792"}
# sectors with discovery-era events (from s02) and camera/ccd from the S1 store index
from reductions import store_products  # noqa: E402


def url_for(gaia, s, cam, ccd):
    g = gaia.zfill(21)
    parts = "/".join(g[i:i + 4] for i in range(0, 16, 4))
    fn = f"hlsp_tglc_tess_ffi_gaiaid-{gaia}-s{s:04d}-cam{cam}-ccd{ccd}_tess_v1_llc.fits"
    return f"https://archive.stsci.edu/hlsps/tglc/s{s:04d}/cam{cam}-ccd{ccd}/{parts}/{fn}", fn


def stream_list(s, gaia, tic):
    url = f"https://archive.stsci.edu/hlsps/tglc/target_lists/s{s:04d}.csv"
    rec = dict(url=url, start_utc=utc(), stop_rule="first match or 300 s")
    t0 = time.monotonic()
    try:
        with requests.get(url, stream=True, timeout=(20, 60)) as r:
            rec["status"] = r.status_code
            lines = r.iter_lines()
            rec["header"] = next(lines).decode()
            n = 0
            for line in lines:
                n += 1
                if gaia.encode() in line or str(tic).encode() in line:
                    rec["match"] = line.decode()
                    break
                if time.monotonic() - t0 > 300:
                    rec["timeout_stop"] = True
                    break
            else:
                rec["complete_scan"] = True
            rec["scanned_lines"] = n
    except Exception as exc:   # noqa: BLE001
        rec["error"] = repr(exc)
    rec["elapsed_s"] = time.monotonic() - t0
    return rec


def main():
    receipts = []
    for tic in TICS:
        ev = read(RES / f"s02_events_{tic}.json")
        secs = sorted({r["sector"] for r in ev["events"] if r["reduction"] == "pdc_raw" and r["sector"] <= 55})
        prods = {int(p["sector"]): p for p in store_products(tic)}
        for s in secs:
            p = prods.get(s)
            if not p:
                continue
            url, fn = url_for(GAIA[tic], s, p["camera"], p["ccd"])
            dest = OUT / fn
            rec = dict(tic=tic, sector=s, camera=p["camera"], ccd=p["ccd"], url=url, file=str(dest), utc=utc())
            if dest.exists() and dest.read_bytes()[:6] == b"SIMPLE":
                rec.update(status="CACHED", bytes=dest.stat().st_size, sha256=sha256(dest))
            else:
                try:
                    r = requests.get(url, timeout=(20, 120))
                    rec.update(status=r.status_code, bytes=len(r.content))
                    if r.status_code == 200 and r.content[:6] == b"SIMPLE":
                        dest.write_bytes(r.content)
                        rec["sha256"] = sha256(dest)
                    elif r.status_code == 404:
                        rec["target_list_scan"] = stream_list(s, GAIA[tic], tic)
                except Exception as exc:   # noqa: BLE001
                    rec.update(status="ERROR", error=repr(exc))
            if dest.exists():
                with fits.open(dest) as h:
                    rec["columns"] = h[1].columns.names
                    hd = h[0].header
                    rec["header"] = {k: str(hd.get(k)) for k in ("TICID", "GAIADR3", "SECTOR", "CAMERA", "CCD", "TESSMAG",
                                                                 "RA_OBJ", "DEC_OBJ", "VERSION") if k in hd}
                    h1 = h[1].header
                    rec["header1"] = {k: str(h1.get(k)) for k in ("TIMEREF", "TIMESYS", "TIMEUNIT", "BJDREFI", "BJDREFF",
                                                                  "TIMEDEL", "XPTIME", "EXPOSURE") if k in h1}
            receipts.append(rec)
            log("s05", f"TGLC {tic} s{s}: {rec.get('status')} {rec.get('bytes')}")
            save(RES / "s05_tglc_receipts.json", receipts)


if __name__ == "__main__":
    main()
