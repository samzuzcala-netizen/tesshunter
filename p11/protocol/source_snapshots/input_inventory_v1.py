"""Read-only raw/FITS provenance and independent timing audit for all 300 hosts.

No search, candidate matching, transit-based clock correction or historical write.
"""
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re
import sys
import time
from common import REPO, P11, DATA, utc, sha, read, write, append_event, science_environment

science_environment()
import numpy as np
from astropy.io import fits
import psutil

AUTHORS = {"SPOC":0, "TESS-SPOC":1, "QLP":2}
HEADERS = ["ORIGIN", "CREATOR", "PROCVER", "FILEVER", "VERSION", "DATE", "DATE-OBS", "DATE-END",
           "TICID", "SECTOR", "CAMERA", "CCD", "TIMESYS", "TIMEREF", "BJDREFI", "BJDREFF", "TIMEUNIT",
           "TIMEDEL", "TIMEPIXR", "TSTART", "TSTOP", "TIERRELA", "TIERABSO", "EXPOSURE", "FRAMETIM",
           "NUM_FRM", "READNOIS", "GAIN", "FLFRCSAP", "CROWDSAP", "TESSMAG", "RA_OBJ", "DEC_OBJ"]


def scalar(x):
    if x is None or isinstance(x, (str, bool, int)):
        return x
    try:
        value = float(x)
        return value if np.isfinite(value) else None
    except (TypeError, ValueError):
        return str(x)


def candidate_files():
    result = defaultdict(list)
    base = REPO / "data/cache/audit_lightkurve"
    for p in base.rglob("*.fits"):
        if not (p.name.endswith("_lc.fits") or p.name.endswith("_llc.fits")):
            continue
        m = re.search(r"(?<!\d)(\d{16})(?!\d)", p.name)
        if m:
            result[int(m.group(1))].append(p)
    return result


def source_info(path):
    with fits.open(path, memmap=False) as hdus:
        data = hdus[1].data
        h0, h1 = hdus[0].header, hdus[1].header
        headers = {k:scalar(h1.get(k, h0.get(k))) for k in HEADERS}
        name = path.name.lower()
        author = "QLP" if "hlsp_qlp" in name else "TESS-SPOC" if "hlsp_tess-spoc" in name else "SPOC"
        columns = {c.name: dict(unit=c.unit, format=c.format) for c in hdus[1].columns}
        t = np.asarray(data["TIME"], dtype=float)
        ref = float(headers.get("BJDREFI") or 0) + float(headers.get("BJDREFF") or 0)
        btjd = t + (ref - 2457000) if ref else t.copy()
        arrays = {k:np.asarray(data[k]).copy() for k in data.names}
        aperture = None
        for hdu in hdus[2:]:
            if hdu.name == "APERTURE" and hdu.data is not None:
                aperture = dict(shape=list(hdu.data.shape), selected_pixels=int(np.count_nonzero(hdu.data & 2)),
                                collected_pixels=int(np.count_nonzero(hdu.data)))
        return dict(path=path.relative_to(REPO).as_posix(), sha256=sha(path), bytes=path.stat().st_size,
                    sector=int(headers["SECTOR"] or -1), author=author, headers=headers,
                    columns=columns, aperture=aperture, product_version=(re.search(r"_v([^_]+)_",path.name).group(1) if re.search(r"_v([^_]+)_",path.name) else headers.get("PROCVER"))), btjd, arrays


def equal(a,b):
    return a.shape == b.shape and bool(np.array_equal(a,b,equal_nan=True))


def timing_pair(left, right):
    la, ra = left[2], right[2]
    lt, rt = left[1], right[1]
    method = None
    if "CADENCENO" in la and "CADENCENO" in ra:
        _, ix, jx = np.intersect1d(la["CADENCENO"],ra["CADENCENO"],return_indices=True)
        method = "exact CADENCENO join; no flux used"
    else:
        return dict(status="UNMEASURED",reason="No common cadence identifier; no flux-based alignment attempted")
    finite = np.isfinite(lt[ix]) & np.isfinite(rt[jx])
    diffs = (lt[ix[finite]] - rt[jx[finite]]) * 86400
    if len(diffs) == 0:
        return dict(status="UNMEASURED",reason="No finite shared cadence times",method=method)
    return dict(status="MEASURED", method=method, n_shared=int(len(diffs)),
                median_seconds=float(np.median(diffs)), min_seconds=float(np.min(diffs)), max_seconds=float(np.max(diffs)),
                p95_abs_seconds=float(np.quantile(abs(diffs),0.95)),
                left=left[0]["path"], right=right[0]["path"],
                left_time_reference=left[0]["headers"],right_time_reference=right[0]["headers"])


def inventory_host(row, paths):
    tic = int(row["tic_id"])
    rawdir = REPO / f"data/survey/audit_lc/tic{tic}"
    idx = read(rawdir/"index.json")
    sources, errors = [], []
    for path in sorted(paths):
        try:
            sources.append(source_info(path))
        except Exception as exc:
            errors.append(dict(path=str(path),error=repr(exc)))
    records, best = [], {}
    for p in idx["products"]:
        if "file" not in p:
            records.append(dict(metadata=p, status="DOWNLOAD_ERROR"))
            continue
        path = rawdir / p["file"]
        with np.load(path, allow_pickle=False) as z:
            t = np.asarray(z["time"], dtype=float)
            flux = np.asarray(z["flux"], dtype=float)
            error = np.asarray(z["flux_err"], dtype=float)
            quality = np.asarray(z["quality"])
            sap = np.asarray(z["sap_flux"],dtype=float)
            nearby = [s for s in sources if s[0]["sector"] == p["sector"] and s[0]["author"] == p["author"]]
            exact = [s for s in nearby if equal(t,s[1])]
            src = exact[0] if exact else None
            checks = dict(time_exact_source=src is not None)
            if src:
                column = p["flux_column"].upper()
                checks["flux_exact_source"] = column in src[2] and equal(flux, np.asarray(src[2][column],dtype=float))
                checks["quality_exact_source"] = "QUALITY" in src[2] and equal(quality,src[2]["QUALITY"])
                checks["SAP_exact_source"] = "SAP_FLUX" in src[2] and equal(sap,np.asarray(src[2]["SAP_FLUX"],dtype=float))
                checks["BJD_TDB_SOLARSYSTEM"] = src[0]["headers"]["TIMESYS"] == "TDB" and src[0]["headers"]["TIMEREF"] == "SOLARSYSTEM" and src[0]["headers"]["BJDREFI"] == 2457000
            mask = 17087 | ((1<<30) if p["author"] == "QLP" and p["sector"] >= 56 else 0)
            good = np.isfinite(t)&np.isfinite(flux)&(flux>0)&((quality & mask)==0)
            timing = "SOURCE_UNVERIFIED" if not src or not all(checks.values()) else "UNAFFECTED_SOURCE_VERIFIED"
            if p["author"] == "QLP" and 99 <= p["sector"] <= 104:
                timing = "QLP_99_104_REDELIVERY_PENDING_EXCLUDE"
            if p["author"] == "QLP" and 74 <= p["sector"] <= 79:
                timing = "QLP_74_79_CORRECTED_SOURCE_VERIFIED" if src and src[0]["product_version"] in ("02","2","2.0") and all(checks.values()) else "QLP_74_79_CORRECTED_COMPARISON_REQUIRED"
            record = dict(metadata=p, raw_path=path.relative_to(REPO).as_posix(),raw_sha256=sha(path),
                          index_sha256=sha(rawdir/"index.json"),downloaded_utc=idx.get("downloaded_utc"),
                          source_matches=[s[0] for s in exact],available_source_versions=[s[0] for s in nearby],
                          checks=checks,timing_status=timing, n_quality_good=int(good.sum()),
                          quality_mask=mask, finite_error_fraction=float(np.isfinite(error).mean()),
                          positive_error_fraction=float((np.isfinite(error)&(error>0)).mean()),
                          product_era="QLP_TGLC_s94_onward" if p["author"] == "QLP" and p["sector"] >= 94 else "QLP_pre94" if p["author"] == "QLP" else p["author"])
            records.append(record)
            if p["sector"] >=56 and p["sector"] <=104 and p["author"] in AUTHORS:
                sector=p["sector"]
                if sector not in best or AUTHORS[p["author"]]<AUTHORS[best[sector]["metadata"]["author"]]:
                    best[sector]=record
    comparisons=[]
    for s in sources:
        if s[0]["author"] != "QLP" or s[0]["sector"]<56:
            continue
        for other in sources:
            if other[0]["author"] == "TESS-SPOC" and other[0]["sector"] == s[0]["sector"]:
                comparisons.append(timing_pair(s,other))
    # Prefer the same P10 author wherever valid; record alternative source candidates without substituting them.
    original=[r for r in best.values() if r["metadata"]["cadence_s"]<=300]
    usable=[r for r in original if r["n_quality_good"]>=50 and r["timing_status"] in ("UNAFFECTED_SOURCE_VERIFIED","QLP_74_79_CORRECTED_SOURCE_VERIFIED")]
    return dict(tic_id=tic,metadata=row,utc=utc(),records=records,source_read_errors=errors,timestamp_comparisons=comparisons,
                original_selected_sectors=sorted(r["metadata"]["sector"] for r in original),
                audited_selected_sectors=sorted(r["metadata"]["sector"] for r in usable),
                meets_three_sector_rule=len(usable)>=3,selected_npoints=sum(r["n_quality_good"] for r in usable))


def main():
    started=utc(); timer=time.perf_counter(); process=psutil.Process()
    output=P11/"results/input_inventory"
    output.mkdir(parents=True,exist_ok=True)
    seal=read(P11/"protocol/registration_seal.json")
    for name,digest in seal["hashes"].items():
        if sha(REPO/name)!=digest:raise RuntimeError("Registration changed: "+name)
    append_event(P11/"manifests/queue_intervals.jsonl",dict(event="start",phase="audit_inventory",pid=process.pid,create_time=process.create_time(),source_sha256=sha(__file__)))
    lookup=candidate_files(); rows=read(P11/"manifests/development_hosts.json"); summaries=[]
    for i,row in enumerate(rows):
        tic=int(row["tic_id"]); path=output/f"tic{tic}.json"
        if path.exists():
            record=read(path)
        else:
            record=inventory_host(row,lookup[tic]);write(path,record)
        summaries.append({k:record[k] for k in ("tic_id","original_selected_sectors","audited_selected_sectors","meets_three_sector_rule","selected_npoints")})
        if i%20==19:
            write(output/"progress.json",dict(completed=i+1,total=len(rows),utc=utc(),wall_seconds=time.perf_counter()-timer))
            print("inventory",i+1,"/",len(rows),flush=True)
        if time.perf_counter()-timer>7200:
            raise RuntimeError("Audit inventory reached two-hour budget")
    all_records=[read(output/f"tic{int(r['tic_id'])}.json") for r in rows]
    timing=Counter(p["timing_status"] for r in all_records for p in r["records"] if "timing_status" in p)
    summary=dict(utc=utc(),n_hosts=len(rows),n_meets_three_sector_rule=sum(r["meets_three_sector_rule"] for r in summaries),
                 timing_status_counts=dict(timing),hosts=summaries,wall_seconds=time.perf_counter()-timer,
                 cpu_seconds=sum(process.cpu_times()[:2]),source_sha256=sha(__file__),
                 record_hashes={p.name:sha(p) for p in output.glob("tic*.json")})
    write(output/"summary.json",summary)
    append_event(P11/"manifests/queue_intervals.jsonl",dict(event="end",phase="audit_inventory",pid=process.pid,started_utc=started,wall_seconds=summary["wall_seconds"],cpu_seconds=summary["cpu_seconds"]))
    print(json.dumps({k:v for k,v in summary.items() if k not in ("hosts","record_hashes")}),flush=True)


if __name__=="__main__":main()
