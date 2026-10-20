"""Explicit public metadata acquisition, isolated from all historical caches."""
import argparse
import csv
import json
import shutil
import time
from common import REPO, P11, DATA, utc, sha, read, write, append_event
import requests

ROOT=DATA/"acquisition"


def fetch(url,path,request=None):
    ROOT.mkdir(parents=True,exist_ok=True)
    ledger=ROOT/"acquisition.jsonl"
    existing=[json.loads(s) for s in ledger.read_text().splitlines()] if ledger.exists() else []
    used=sum(r.get("bytes",0) for r in existing)
    if used>=15000000000 or shutil.disk_usage(REPO).free<30000000000:
        raise RuntimeError("Acquisition cap or disk headroom")
    start=time.perf_counter()
    session=requests.Session()
    session.headers.update({"User-Agent":"tesshunter P11 input metadata audit"})
    response=None
    try:
        response=session.post(url,data={"request":json.dumps(request)},timeout=(15,45)) if request else session.get(url,timeout=(15,45))
        body=response.content
        if used+len(body)>15000000000 or shutil.disk_usage(REPO).free-len(body)<30000000000:
            raise RuntimeError("Acquisition cap/headroom would be exceeded")
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():raise RuntimeError("Refuse to overwrite acquisition")
        path.write_bytes(body)
        receipt=dict(url=url,request=request,status_code=response.status_code,bytes=len(body),path=path.relative_to(REPO).as_posix(),sha256=sha(path),wall_seconds=time.perf_counter()-start,response_headers=dict(response.headers))
        append_event(ledger,receipt)
        return response
    except Exception as exc:
        append_event(ledger,dict(url=url,request=request,error=repr(exc),bytes=0,wall_seconds=time.perf_counter()-start))
        raise


def mast_request(ids):
    return dict(service="Mast.Caom.Filtered",params=dict(columns="*",filters=[
        dict(paramName="target_name",values=[str(int(t)) for t in ids]),
        dict(paramName="provenance_name",values=["QLP","TESS-SPOC","SPOC"]),
        dict(paramName="dataproduct_type",values=["timeseries"])]),format="json",pagesize=50000,page=1)


def main(mode):
    if mode=="notices":
        for label,url in [("mast_qlp","https://archive.stsci.edu/hlsp/qlp"),("mit_qlp","https://tess.mit.edu/qlp/"),("tls_faq","https://transitleastsquares.readthedocs.io/en/latest/FAQ.html")]:
            path=ROOT/f"{label}.html"
            if not path.exists():
                r=fetch(url,path);print(label,r.status_code,len(r.content),flush=True)
        return
    rows=list(csv.DictReader((REPO/"data/survey/targets_p8.csv").open(encoding="utf-8")))
    ids=[int(r["tic_id"]) for r in rows]
    batches=[[5655186]] if mode=="pilot" else [ids[i:i+200] for i in range(0,len(ids),200)]
    for i,batch in enumerate(batches):
        path=ROOT/f"mast_{mode}_{i:03d}.json"
        if path.exists():
            result=read(path)
        else:
            result=fetch("https://mast.stsci.edu/api/v0/invoke",path,mast_request(batch)).json()
        print(mode,i,"status",result.get("status"),"rows",len(result.get("data",[])),"paging",result.get("paging"),flush=True)
        if mode=="pilot" and result.get("data"):
            print({k:v for k,v in result['data'][0].items() if k in ('target_name','sequence_number','provenance_name','t_exptime','obs_id','obs_collection','t_min','t_max')},flush=True)
        if result.get("status")!="COMPLETE":raise RuntimeError("MAST metadata query incomplete: "+str(result)[:300])
        paging=result.get("paging",{})
        if paging.get("pagesFiltered",1)>1:raise RuntimeError("MAST metadata pagination must be completed before inventory")


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("mode",choices=["notices","pilot","survey"])
    main(parser.parse_args().mode)
