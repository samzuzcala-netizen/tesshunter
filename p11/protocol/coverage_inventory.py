"""Per-target metadata inventory. Name avoids shadowing numba's coverage dependency."""
from collections import defaultdict, Counter
import csv
from common import REPO,P11,DATA,read,write,sha,utc


def main():
    paths=sorted((DATA/"acquisition").glob("mast_survey_*.json"))
    if len(paths)!=10:raise RuntimeError("All ten original-survey metadata batches are required")
    obs=defaultdict(list)
    for p in paths:
        data=read(p)
        if data["status"]!="COMPLETE":raise RuntimeError("Incomplete metadata")
        for r in data["data"]:obs[int(r["target_name"])].append(r)
    targets=list(csv.DictReader((REPO/"data/survey/targets_p8.csv").open(encoding="utf-8")))
    dev={int(r["tic_id"]) for r in read(P11/"manifests/development_hosts.json")}
    records=[]
    for row in targets:
        tic=int(row["tic_id"]); p=REPO/f"data/survey/audit_lc/tic{tic}/index.json"
        idx=read(p) if p.exists() else {"products":[]}
        cached={int(r["sector"]) for r in idx["products"] if "file" in r and 56<=int(r["sector"])<=104 and r.get("cadence_s",1e9)<=300}
        current=set(); valid_ffi=set(); valid_any=set(); two_min=set(); unknown=[]; newly_available=[]
        cached_pairs={(r.get("author"),r.get("sector")) for r in idx["products"] if "file" in r}
        for r in obs[tic]:
            s=int(r.get("sequence_number") or -1);author=r["provenance_name"];exp=float(r.get("t_exptime") or 1e9)
            if s<56 or s>104:continue
            if (author,s) not in cached_pairs:newly_available.append({k:r.get(k) for k in ("provenance_name","sequence_number","t_exptime","obs_id","t_obs_release","dataURL")})
            if not 100<=exp<=300:continue
            current.add(s)
            if author=="SPOC":two_min.add(s)
            if author=="QLP" and 99<=s<=104:continue
            valid_any.add(s)
            if author in ("QLP","TESS-SPOC"):valid_ffi.add(s)
        invpath=P11/f"results/input_inventory_v2/tic{tic}.json"
        inv=read(invpath) if invpath.exists() else None
        records.append(dict(tic_id=tic,tmag=float(row["tmag"]),development=tic in dev,
            cached_200s_or_harmonizable_sectors=sorted(cached),current_metadata_200s_or_harmonizable_sectors=sorted(current),
            added_sectors_at_current_metadata=sorted(current-cached),new_author_sector_records=newly_available,
            current_unaffected_native_FFI_sector_upper_bound=sorted(valid_ffi),
            current_unaffected_any_author_sector_upper_bound=sorted(valid_any),
            two_minute_sectors=sorted(two_min),
            passes_unaffected_metadata_coverage_upper_bound=len(valid_ffi)>=3 and len(two_min&valid_ffi)<len(valid_ffi)/2,
            audited_cached_sectors=inv["audited_selected_sectors"] if inv else None,
            provenance="MAST observation metadata is an availability upper bound, not proof of usable FITS/quality or of redelivery dates"))
    out=P11/"results/coverage";out.mkdir(parents=True,exist_ok=True)
    write(out/"per_target_inventory.json",records)
    with (out/"coverage_difference.csv").open("w",newline="",encoding="utf-8") as f:
        fields=["tic_id","tmag","development","cached_sectors","current_sectors","added_sectors","unaffected_native_FFI_sectors","audited_cached_sectors","metadata_coverage_upper_bound_pass"]
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for r in records:
            join=lambda value: ",".join(map(str,value or []))
            writer.writerow(dict(tic_id=r["tic_id"],tmag=r["tmag"],development=r["development"],
                cached_sectors=join(r["cached_200s_or_harmonizable_sectors"]),current_sectors=join(r["current_metadata_200s_or_harmonizable_sectors"]),
                added_sectors=join(r["added_sectors_at_current_metadata"]),unaffected_native_FFI_sectors=join(r["current_unaffected_native_FFI_sector_upper_bound"]),
                audited_cached_sectors=join(r["audited_cached_sectors"]),metadata_coverage_upper_bound_pass=r["passes_unaffected_metadata_coverage_upper_bound"] ))
    devrows=[r for r in records if r["development"]]
    injs=list(csv.DictReader((REPO/"data/survey/p10/injections_2b.csv").open(encoding="utf-8")))
    impossible={r["tic_id"] for r in devrows if len(r["current_unaffected_any_author_sector_upper_bound"])<3}
    missing_domain={r["tic_id"] for r in devrows if not r["passes_unaffected_metadata_coverage_upper_bound"]}
    summary=dict(utc=utc(),survey_targets=len(records),development_hosts=len(devrows),
        targets_with_added_metadata_sectors=sum(bool(r["added_sectors_at_current_metadata"]) for r in records),
        development_hosts_with_added_metadata_sectors=sum(bool(r["added_sectors_at_current_metadata"]) for r in devrows),
        development_hosts_failing_even_any_author_three_sector_upper_bound=sorted(impossible),
        development_hosts_failing_native_FFI_population_upper_bound=sorted(missing_domain),
        comparison_injections_on_hosts_failing_any_author_upper_bound=sum(int(r["tic_id"]) in impossible for r in injs),
        comparison_injections_on_hosts_failing_native_FFI_upper_bound=sum(int(r["tic_id"]) in missing_domain for r in injs),
        source_hashes={p.relative_to(REPO).as_posix():sha(p) for p in paths},
        caveats=["Existing corrected QLP 74-79 v02 records are allowed in the upper bound.","QLP 99-104 are excluded pending verified redelivery, regardless of the filename version.","Missing/incorrect MAST cadence metadata can require a FITS check; per-host product records are retained.","MAST release timestamps do not by themselves prove when an overwritten product was redelivered."])
    write(out/"summary.json",summary)
    print({k:v if not isinstance(v,list) else len(v) for k,v in summary.items() if k not in ('source_hashes','caveats')},flush=True)


if __name__=="__main__":main()
