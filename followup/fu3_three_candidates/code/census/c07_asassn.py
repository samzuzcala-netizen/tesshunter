"""Census task 9: ASAS-SN Sky Patrol v2 light curves via the documented Python client (pip package `skypatrol`,
module `pyasassn`), installed only in D:\\tess_fu3_cache\\venv_census.  Run with that venv's python.

The client's own download path (`cone_search(download=True)`) uses a multiprocessing pool and an internal retry
loop of up to 5 rounds over all block servers; to respect the census rule of at most 2 retries and to keep every
request in-process (receipt hook), this script uses the client for initialisation and the cone search, and then
repeats the client's documented request sequence itself (POST lookup_cone with download=True, then GET get_block
for each 1000-target block on the advertised block servers, one retry at most).  No login is involved.
Light curves are saved as CSV, not interpreted.
"""
from __future__ import annotations

import io
import json
from base64 import encodebytes

import census_common as C
from census_common import TARGETS, log, save_json, tag

import requests

SCRIPT = "c07_asassn"
OUTDIR = C.OUT / "asassn_skypatrol"


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    import pyasassn
    from pyasassn import client as pc
    res = {"script": SCRIPT, "utc": C.utc(), "client_version": None, "init": {}, "targets": {}}
    try:
        from pyasassn.version import __version__ as v
        res["client_version"] = v
    except Exception:  # noqa: BLE001
        res["client_version"] = "unknown"
    with tag("asassn_client_init") as rc:
        try:
            cl = pc.SkyPatrolClient(verbose=False)
            res["init"] = {"ok": True, "block_servers": list(cl.block_servers),
                           "catalogs": list(cl.catalogs.catalog_names()) if hasattr(cl.catalogs, "catalog_names") else None}
        except Exception as e:  # noqa: BLE001
            cl = None
            res["init"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    res["init"]["receipts"] = [r["receipt"] for r in rc]
    msg_raw = [r["raw"] for r in rc if r.get("raw") and "get_current_message" in (r.get("url") or "")]
    if msg_raw:
        res["init"]["server_message"] = open(msg_raw[0], encoding="utf-8", errors="replace").read()
    log(SCRIPT, f"init: {res['init'].get('ok')} {res['init'].get('error', '')} servers={res['init'].get('block_servers')}")
    lc_service_up = bool(cl is not None and cl.block_servers)
    res["init"]["light_curve_service_available"] = lc_service_up
    if cl is None:
        save_json(C.PARTS / "c07_asassn.json", res)
        return
    for tic, t in TARGETS.items():
        rec = {"cone_radius_arcsec": 15.0, "catalog": "master_list"}
        ra, dec = C.pos_at_epoch(tic, 2016.0)   # Gaia-epoch position; 15" cone absorbs the 2000-2026 motion
        radius = 15.0 / 3600.0
        cols = ["asas_sn_id", "ra_deg", "dec_deg", "catalog_sources"]
        with tag(f"asassn_cone_{tic}") as rc:
            try:
                idx = cl.cone_search(ra, dec, radius=radius, units="deg", catalog="master_list", cols=cols,
                                     download=False)
                rec["index"] = json.loads(idx.to_json(orient="records")) if idx is not None else []
                rec["cone_error"] = None
            except Exception as e:  # noqa: BLE001
                rec["index"], rec["cone_error"] = None, f"{type(e).__name__}: {e}"
        rec["cone_receipts"] = [r["receipt"] for r in rc]
        log(SCRIPT, f"{tic} cone: n={None if rec['index'] is None else len(rec['index'])} err={rec['cone_error']}")
        if rec["index"]:
            for r in rec["index"]:
                r["sep_arcsec_from_2016pos"] = round(C.sep_arcsec(ra, dec, float(r["ra_deg"]), float(r["dec_deg"])), 2)
        if rec["index"] and not lc_service_up:
            rec["light_curves"] = ("not requested: get_block_servers returned an empty list (light-curve service "
                                   "unavailable; see init.server_message)")
            res["targets"][tic] = rec
            continue
        if rec["index"]:
            # same request sequence as cone_search(download=True), done in-process
            url = f"http://asassn-lb01.ifa.hawaii.edu:9006/lookup_cone/radius{radius}_ra{ra}_dec{dec}"
            with tag(f"asassn_cone_download_{tic}") as rc2:
                try:
                    resp = requests.post(url, json={"catalog": "master_list", "cols": cols, "format": "arrow",
                                                    "download": True}, timeout=(30, 120))
                    ok = bool(resp)
                except Exception as e:  # noqa: BLE001
                    ok, resp = False, None
                    rec["download_prep_error"] = f"{type(e).__name__}: {e}"
            rec["download_prep_receipts"] = [r["receipt"] for r in rc2]
            if ok:
                query_id = (f"conectr-{radius}_conera-{ra}_conedec-{dec}|catalog-master_list|cols-" + "/".join(cols))
                query_hash = encodebytes(bytes(query_id, encoding="utf-8")).decode()
                n_chunks = (len(rec["index"]) + 999) // 1000
                frames = []
                rec["blocks"] = []
                for bi in range(n_chunks):
                    got = None
                    for attempt in range(2):   # one retry at most, on the next block server
                        srv = cl.block_servers[(bi + attempt) % len(cl.block_servers)]
                        burl = (f"http://{srv}:9006/get_block/query_hash-{query_hash}-block_idx-{bi}-"
                                f"catalog-master_list")
                        with tag(f"asassn_block_{tic}_{bi}_{attempt}") as rc3:
                            try:
                                br = requests.get(burl, timeout=(30, 120))
                                got = pc._deserialize(br.content) if br else None
                                err = None if br else f"HTTP {br.status_code}"
                            except Exception as e:  # noqa: BLE001
                                got, err = None, f"{type(e).__name__}: {e}"
                        rec["blocks"].append({"block": bi, "attempt": attempt, "server": srv, "error": err,
                                              "receipts": [r["receipt"] for r in rc3]})
                        if got is not None:
                            frames.append(got)
                            break
                if frames:
                    import pandas as pd
                    data = pd.concat(frames)
                    p = OUTDIR / f"asassn_skypatrol_tic{tic}.csv"
                    C._check_write(p)
                    data.to_csv(p, index=False)
                    rec["saved_csv"] = str(p)
                    rec["sha256"] = C.sha256_file(p)
                    rec["columns"] = list(data.columns)
                    summ = {}
                    for sid, g in data.groupby("asas_sn_id"):
                        d = {}
                        fcol = "phot_filter" if "phot_filter" in g.columns else None
                        tcol = "jd" if "jd" in g.columns else None
                        for fv, gg in (g.groupby(fcol) if fcol else [("all", g)]):
                            d[str(fv)] = {"n": int(len(gg)),
                                          "t_min": float(gg[tcol].min()) if tcol else None,
                                          "t_max": float(gg[tcol].max()) if tcol else None,
                                          "n_quality_G": int((gg["quality"] == "G").sum()) if "quality" in gg.columns else None}
                        summ[str(sid)] = d
                    rec["summary"] = summ
            log(SCRIPT, f"{tic}: blocks={rec.get('blocks')} saved={rec.get('saved_csv')} summary={rec.get('summary')}")
        res["targets"][tic] = rec
    save_json(C.PARTS / "c07_asassn.json", res)


if __name__ == "__main__":
    main()
