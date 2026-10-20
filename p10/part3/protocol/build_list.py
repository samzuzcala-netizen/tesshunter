"""Reproduce the original 531 and correct input cuts without TCE selection."""
import csv
from pathlib import Path
import re
import time
import numpy as np
import pandas as pd
from common import REPO, ROOT, read, write, sha, utc, environment


def domain_mask(pool):
    return ((pool.Teff < 3600) & (pool.rad < 0.45) & pool.Tmag.between(12.5, 14.0)
        & (pool.gallat.abs() >= 20) & (pool.n_sectors_200s >= 3)
        & (pool.n_sectors_2min_in_search < pool.n_sectors_200s / 2))


def original_list(pool):
    return pool[domain_mask(pool) & pool.xmatch_status.eq("REJECT")
                & pool.xmatch_tic_sources.eq("spoc_tce")].copy()


def sectors(value):
    if value is None or str(value).lower() in ("", "nan"):
        return set()
    return {int(x) for x in str(value).split(",")}


def corrected_inventory(tics, directory, sector_min=56, sector_max=105):
    tics = np.array(sorted(set(int(t) for t in tics)), dtype=np.int64)
    found = {}
    inventory = {int(t): [] for t in tics}
    for path in sorted(Path(directory).glob("*.npy")):
        match = re.fullmatch(r"s(\d+)\.npy", path.name)
        if not match or not sector_min <= int(match[1]) <= sector_max:
            continue
        sector = int(match[1])
        if sector in found:
            raise ValueError(f"Duplicate MIT sector {sector}")
        values = np.load(path, allow_pickle=False)
        if values.ndim != 1 or (len(values)>1 and not np.all(values[1:] >= values[:-1])):
            raise ValueError(f"Malformed or unsorted MIT list {path}")
        if not len(values):
            raise ValueError(f"Empty MIT list cannot establish absence: {path}")
        status = path.with_suffix(".status")
        if status.exists() and status.read_text().strip() != "ok":
            raise ValueError(f"MIT list status not ok: {path}")
        found[sector] = dict(path=str(path), sha256=sha(path), n_ids=len(values))
        for tic in tics[np.isin(tics, values)]:
            inventory[int(tic)].append(sector)
    if set(found) != set(range(sector_min, sector_max+1)):
        raise ValueError(f"Missing MIT lists: {sorted(set(range(sector_min,sector_max+1))-set(found))}")
    return inventory, found


def apply_input_cuts(original, inventory):
    rows = []
    for _, row in original.sort_values("tic_id").iterrows():
        tic = int(row.tic_id)
        ffi = sorted(s for s in sectors(row.sectors_200s) if 56 <= s <= 105)
        twomin = sorted(set(inventory[tic]) & set(ffi))
        gaia = str(row.gaia_dwarf_check).lower() == "pass"
        minority = len(twomin) < len(ffi)/2
        reason = "gaia" if not gaia else "ffi_majority" if not minority else None
        rows.append(dict(tic_id=tic, Tmag=float(row.Tmag), Teff=float(row.Teff),
            radius_rsun=float(row.rad), gaia_pass=gaia,
            pool_200s_sectors=sorted(sectors(row.sectors_200s)),
            delivered_ffi_sectors=ffi, corrected_twomin_sectors=inventory[tic],
            corrected_twomin_in_search=twomin, n_corrected_twomin_in_search=len(twomin),
            pool_n_twomin_in_search=int(row.n_sectors_2min_in_search),
            ffi_majority_pass=minority, after_a_eligible=reason is None,
            usable_sector_cut="PENDING_PART_D" if reason is None else "NOT_REQUIRED",
            status="PENDING_PART_D" if reason is None else "INPUT_INELIGIBLE",
            exclusion_reason=reason))
    return rows


def main():
    environment()
    for name, digest in read(ROOT / "manifests/registration_seal.json")["hashes"].items():
        if sha(REPO/name) != digest:
            raise RuntimeError(f"Registration changed: {name}")
    start = time.perf_counter()
    pool_path = REPO / "data/survey/cache/p8/pool_after_xmatch.csv"
    pool = pd.read_csv(pool_path, low_memory=False)
    original = original_list(pool)
    if len(pool)!=117171 or int(domain_mask(pool).sum())!=11491 or len(original)!=531:
        raise ValueError("The registered source population was not reproduced")
    inventory, lists = corrected_inventory(original.tic_id, REPO/"data/survey/cache/twomin_lists")
    rows = apply_input_cuts(original, inventory)
    write(ROOT/"manifests/original_531.json", rows)
    write(ROOT/"manifests/twomin_inventory.json", dict(utc=utc(),
        files={str(s):dict(v,path=Path(v["path"]).relative_to(REPO).as_posix()) for s,v in lists.items()}))
    original.to_csv(ROOT/"manifests/original_531.csv", index=False, lineterminator="\n")
    selected = {r["tic_id"] for r in rows if r["after_a_eligible"]}
    target_rows = []
    for r in original.to_dict("records"):
        if int(r["tic_id"]) not in selected:
            continue
        target_rows.append(dict(tic_id=int(r["tic_id"]), ra_deg=r["ra"], dec_deg=r["dec"],
            tmag=r["Tmag"], teff_k=r["Teff"], radius_rsun=r["rad"], mass_msun=r["mass"],
            contamination_ratio_used=r["contratio"], n_sectors_200s=int(r["n_sectors_200s"])))
    # Stable identity order; no ephemeris or apparent-ease sorting.
    pd.DataFrame(target_rows).sort_values("tic_id").to_csv(ROOT/"manifests/targets_after_a.csv",index=False,lineterminator="\n")
    summary = dict(utc=utc(), pool_rows=len(pool), domain_rows=int(domain_mask(pool).sum()),
        original=len(rows), after_gaia=sum(r["gaia_pass"] for r in rows),
        after_corrected_ffi_majority=sum(r["after_a_eligible"] for r in rows),
        gaia_excluded=sum(r["exclusion_reason"]=="gaia" for r in rows),
        ffi_majority_excluded=sum(r["exclusion_reason"]=="ffi_majority" for r in rows),
        corrected_counts_changed=sum(r["n_corrected_twomin_in_search"]!=r["pool_n_twomin_in_search"] for r in rows),
        usable_sector_cut="PENDING_PART_D", twomin_files=len(lists),
        pool_sha256=sha(pool_path), source_sha256=sha(__file__), wall_seconds=time.perf_counter()-start)
    write(ROOT/"results/part_a.json", summary)
    exposure=read(ROOT/"manifests/exposure_ledger.json")
    exposure["stages"].append(dict(stage="A",utc=utc(),tics=sorted(int(t) for t in original.tic_id),
        content="stellar metadata and coverage lists; no flux or predictions"))
    write(ROOT/"manifests/exposure_ledger.json",exposure,replace=True)
    print(summary, flush=True)


if __name__ == "__main__":
    main()
