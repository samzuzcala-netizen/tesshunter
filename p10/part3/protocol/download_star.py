"""Run the original P8 downloader once per star with isolated receipts and bounds."""
from common import REPO, ROOT, environment, read, write, sha, utc
environment(offline=False)
import sys
import time
import traceback
import numpy as np
import psutil
sys.path.insert(0,str(REPO/"scripts"))
import p8_download as D
import audit_p5 as A
import lightkurve as lk
from acquisition_meter import install as install_meter, accounting


def allowed_download_rows(result,configuration):
    indices=[]
    for i in range(len(result)):
        mission=str(result.mission[i]);author=str(result.author[i])
        sector=int(mission.split()[-1]) if "Sector" in mission else -1
        if not 27<=sector<=configuration["sector_max"]:continue
        if author=="QLP" and sector in configuration["qlp_excluded_sectors"]:continue
        indices.append(i)
    return indices


def main():
    tic=int(sys.argv[1]);start=time.perf_counter();started=utc()
    install_meter()
    configuration=read(ROOT/"protocol/config.json")
    search=lk.search_lightcurve
    calls=0
    def frozen_search(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls>1:raise RuntimeError("More than one lightcurve search for a star")
        result=search(*args,**kwargs)
        destination=ROOT/f"results/acquisition_metadata/tic{tic}.csv"
        destination.parent.mkdir(parents=True,exist_ok=True)
        result.table.write(destination,format="ascii.csv",overwrite=False)
        return result[allowed_download_rows(result,configuration)]
    lk.search_lightcurve=frozen_search
    D.OUT=ROOT/"results/acquisition"
    # D.one -> A.download preserves the original array conversion and checkpoint.
    # Source FITS stay in A.AUDIT_CACHE; no historical index is forced or rewritten.
    result=D.one(tic)
    result.update(started_utc=started,completed_utc=utc(),wall_seconds=time.perf_counter()-start,
        cpu_seconds=time.process_time(),pid=os_pid(),search_lightcurve_calls=calls,
        source_sha256=sha(__file__),policy="P8 acquisition >=27; maximum105; excluded QLP removed before download")
    if result["ok"]:
        result["index_sha256"]=sha(D.STORE/f"tic{tic}/index.json")
    meter=accounting()
    result["http_body_bytes"]=meter["workers"].get(str(os_pid()),0)
    write(ROOT/f"results/download/tic{tic}.json",result)
    print(result,flush=True)
    if not result["ok"]:raise SystemExit(2)


def os_pid():
    return psutil.Process().pid


if __name__=="__main__":main()
