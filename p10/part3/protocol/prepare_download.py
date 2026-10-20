"""Freeze the identity-only first-50 acquisition sample and storage preflight."""
import csv
import shutil
from common import REPO, ROOT, read, write, sha, utc


def main():
    targets=list(csv.DictReader((ROOT/"manifests/targets_after_a.csv").open()))
    if (ROOT/"manifests/controller_owner.json").exists():raise RuntimeError("Owner exists")
    free=shutil.disk_usage(REPO).free
    if free<28000000000:raise RuntimeError("Storage preflight requires relocation")
    source=read(REPO/"p11/p11_5/results/acquisition/mast_qlp.html.json")
    if sha(REPO/source["path"])!=source["sha256"]:raise RuntimeError("QLP notice snapshot changed")
    write(ROOT/"manifests/sector_policy.json",dict(utc=utc(),sectors=list(range(56,106)),
        excluded_qlp=[80,83,85,99,100,101,102,103,104],exceptions_sought=False,
        notice_snapshot=source,corrected_74_79="Require per-product corrected-v02 source TIME comparison",
        acquisition_27_55="P8 downloader retains this cache superset; excluded from scientific inputs"))
    existing=[]
    for row in targets:
        tic=int(row["tic_id"]);path=REPO/f"data/survey/audit_lc/tic{tic}/index.json"
        if path.exists():existing.append(dict(tic_id=tic,index_sha256=sha(path)))
    selected=targets[:50]
    jobs=[dict(job_id=f"tic{r['tic_id']}",arguments=["p10/part3/protocol/download_star.py",r["tic_id"]],
        result_path=f"p10/part3/results/download/tic{r['tic_id']}.json") for r in selected]
    write(ROOT/"manifests/download_pilot_jobs.json",jobs)
    write(ROOT/"manifests/download_pilot_preflight.json",dict(utc=utc(),eligible_after_a=len(targets),
        existing_audit_indices=existing,pilot_tics=[int(r["tic_id"]) for r in selected],
        selection="First 50 in ascending TIC identity order; no TCE content used",
        c_free_bytes=free,d_free_bytes=shutil.disk_usage("D:/").free,
        forecast_minutes=45,forecast_basis="Conservative engineering allocation for first-50 metadata and product downloads; full acquisition forecast waits for measured sample",
        command="p8_download.one in four top-level workers; isolated controller/logs, frozen upper-sector/exclusion filter and HTTP body-byte cap",
        source_sha256=sha(__file__)))
    # Attribute the already completed small data-census computations conservatively.
    ledger=read(ROOT/"manifests/resource_ledger.json")
    for result_path,phase in [("results/part_a.json","A_list"),("results/hard_stop_p10.json","BC_sidecar_population")]:
        result=read(ROOT/result_path)
        seconds=result["wall_seconds"]
        ledger["intervals"].append(dict(phase=phase,end=result["utc"],hours=seconds/3600,
            accounting="Measured non-overlapping program wall; conservative scientific charge"))
        ledger["new_queue_hours"]+=seconds/3600
    write(ROOT/"manifests/resource_ledger.json",ledger,replace=True)
    print(dict(after_a=len(targets),existing_indices=len(existing),sample=50,c_free_bytes=free,
        new_queue_hours=ledger["new_queue_hours"]),flush=True)


if __name__=="__main__":main()
