"""P12 population metadata and extension ranking; no candidate-result reads."""
import argparse
from collections import Counter
import io
import json

import numpy as np
import pandas as pd

from p12_common import REPO, ROOT, read, write, sha, utc

DESIGN = dict(teff_max_k=3600., radius_max_rsun=.45, tmag_range=[12.5, 14.0],
              min_sectors_200s_with_lc=3, min_abs_galactic_latitude_deg=20.)
EXCLUDED = {80, 83, 85, 99, 100, 101, 102, 103, 104}


def _apply_cuts_origin(pool: pd.DataFrame, design: dict, tmag_hi: float, rad_max: float) -> tuple[pd.DataFrame, dict]:
    counts = {}
    s = pool
    counts["query_pool_abs_b"] = int(len(s))
    s = s[s["Teff"] < design["teff_max_k"]]; counts["teff_lt_3600"] = int(len(s))
    s = s[s["rad"] < rad_max]; counts[f"radius_lt_{rad_max:g}"] = int(len(s))
    lc = s["lumclass"].fillna("").astype(str).str.upper()
    s = s[(lc == "DWARF") | (lc == "")]; counts["lumclass_dwarf_or_missing"] = int(len(s))
    counts["lumclass_missing_kept"] = int((lc.loc[s.index] == "").sum())
    s = s[(s["Tmag"] >= design["tmag_range"][0]) & (s["Tmag"] < tmag_hi)]; counts[f"tmag_12.5_to_{tmag_hi:g}"] = int(len(s))
    counts["gaia_dwarf_check_reasons"] = s["gaia_dwarf_check"].value_counts().to_dict()
    s = s[s["gaia_dwarf_check"] == "pass"]; counts["gaia_dwarf_pass"] = int(len(s))
    s = s[s["n_sectors_200s"] >= design["min_sectors_200s_with_lc"]]; counts["ge_3_sectors_200s_with_lc"] = int(len(s))
    counts["zero_2min_sectors_in_search"] = int((s["n_sectors_2min_in_search"] == 0).sum())
    minority = s["n_sectors_2min_in_search"] < s["n_sectors_200s"] / 2.0
    counts["minority_2min_sectors_in_search"] = int(minority.sum())
    s = s[minority]; counts["ffi_only_minority"] = int(len(s))
    counts["xmatch_status"] = s["xmatch_status"].value_counts().to_dict()
    s = s[s["xmatch_status"] == "CLEAN"]; counts["hard_stop_clean"] = int(len(s))
    return s, counts


def apply_cuts(frame) -> pd.DataFrame:
    # The origin queried pool is already latitude-cut; enforce that prerequisite
    # for callers supplying standalone metadata frames, retaining all boundaries.
    pool = frame[frame["gallat"].abs() >= DESIGN["min_abs_galactic_latitude_deg"]]
    selected, counts = _apply_cuts_origin(pool, DESIGN, DESIGN["tmag_range"][1], DESIGN["radius_max_rsun"])
    selected = selected.copy()
    selected.attrs["cut_counts"] = counts
    return selected


def _csv(path, frame):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = frame.to_csv(index=False, lineterminator="\n")
    if path.exists():
        if path.read_text(encoding="utf-8") != body:
            raise RuntimeError(f"Refusing to replace a different population: {path.name}")
        return
    with path.open("x", encoding="utf-8", newline="") as stream:
        stream.write(body)


def _eligibility(population):
    stars = {}
    for row in population.itertuples():
        tic = int(row.tic_id)
        path = ROOT / f"results/native_noise/archival/tic{tic}.json"
        if path.exists():
            result = read(path)
            if int(result["tic_id"]) != tic or result["status"] not in {"INPUT_ELIGIBLE", "INPUT_INELIGIBLE"}:
                raise RuntimeError(f"Invalid preparation status for TIC {tic}")
            stars[str(tic)] = dict(status=result["status"], usable_sectors=result["usable_sectors"],
                reason=None if result["status"] == "INPUT_ELIGIBLE" else "sectors/finite-points/scatter",
                result_path=path.relative_to(REPO).as_posix(), result_sha256=sha(path), source_set=row.source_set)
        else:
            stars[str(tic)] = dict(status="OPERATIONAL_UNKNOWN", reason="preparation receipt absent", source_set=row.source_set)
    sample_path = REPO / "data/survey/completeness_sample_p8.csv"
    sample_ids = set(pd.read_csv(sample_path, usecols=["tic_id"]).tic_id.astype(int))
    eligible = {int(tic) for tic, record in stars.items() if record["status"] == "INPUT_ELIGIBLE"}
    injection_counts = {}
    # Read host IDs only. These tables are evaluator metadata, not worker inputs.
    for name, path in (("full", REPO / "data/survey/injections_p8.csv"),
                       ("2b", REPO / "data/survey/p10/injections_2b.csv")):
        ids = pd.read_csv(path, usecols=["tic_id"]).tic_id.astype(int)
        injection_counts[name] = dict(total=len(ids), eligible=int(ids.isin(eligible).sum()),
                                     calibration_hosts=int(ids[ids.isin(sample_ids)].nunique()),
                                     calibration_injections=int(ids.isin(sample_ids).sum()))
    counts = {source: dict(Counter(record["status"] for record in stars.values() if record["source_set"] == source))
              for source in ("p8_2000", "p10_436")}
    counts["calibration_300"] = dict(Counter(stars.get(str(tic), {"status": "REJECT_NOVELTY"})["status"] for tic in sample_ids))
    return dict(utc=utc(), per_star=stars, counts=counts, injections=injection_counts,
                complete=all(record["status"] != "OPERATIONAL_UNKNOWN" for record in stars.values()),
                n_eligible=len(eligible), n_unknown=sum(r["status"] == "OPERATIONAL_UNKNOWN" for r in stars.values()))


def core() -> dict:
    p8 = pd.read_csv(REPO / "data/survey/targets_p8.csv").assign(source_set="p8_2000")
    evaluated = pd.read_csv(REPO / "p10/part3/manifests/targets_evaluated.csv").assign(source_set="p10_436")
    all_stars = pd.concat([p8, evaluated], ignore_index=True)
    if all_stars.tic_id.duplicated().any():
        raise RuntimeError("Core populations overlap")
    hard_stop = read(ROOT / "manifests/hard_stop_p12.json")["per_star"]
    statuses, ephemeris, associations = [], [], []
    for tic in all_stars.tic_id:
        record = hard_stop[str(int(tic))]
        status = record.get("hard_stop_p12", record.get("status"))
        status = "REJECT_NOVELTY" if status == "REJECT" else status
        if status not in {"REJECT_NOVELTY", "FLAG", "CLEAN"}:
            raise RuntimeError(f"Unresolved catalogue status for TIC {tic}")
        statuses.append(status)
        ephemeris.append(record.get("f7", {}).get("ephemeris", ""))
        associations.append(json.dumps(record.get("f7", {}).get("associations", []), allow_nan=False, sort_keys=True))
    all_stars = all_stars.assign(hard_stop_p12=statuses, f7_ephemeris=ephemeris, f7_associations=associations)
    selected = all_stars[all_stars.hard_stop_p12 != "REJECT_NOVELTY"].sort_values("tic_id").reset_index(drop=True)
    path = ROOT / "manifests/targets_p12_core.csv"
    _csv(path, selected)
    receipt = dict(utc=utc(), path=path.relative_to(REPO).as_posix(), sha256=sha(path), rows=len(selected),
        rejected_novelty=int((all_stars.hard_stop_p12 == "REJECT_NOVELTY").sum()),
        source_counts={str(k): int(v) for k, v in selected.source_set.value_counts().items()})
    # A core can be frozen before preparation. Aggregate eligibility only once
    # its verification receipts exist; missing ones remain operational unknowns.
    if any((ROOT / f"results/native_noise/archival/tic{int(tic)}.json").exists() for tic in selected.tic_id):
        eligibility = _eligibility(selected)
        write(ROOT / "manifests/eligibility_p12.json", eligibility, replace=True)
        receipt["eligibility"] = {key: eligibility[key] for key in ("counts", "complete", "n_eligible", "n_unknown")}
    return receipt


def _sectors(value):
    if value is None or (isinstance(value, float) and np.isnan(value)) or str(value).strip() == "":
        return []
    return [int(s) for s in str(value).split(",") if s.strip()]


def _rank_extension(frame):
    result = frame.copy()
    result["n_pol"] = result.sectors_200s.map(lambda values: len({s for s in _sectors(values) if 56 <= s <= 105 and s not in EXCLUDED}))
    result["sigma_Tmag_ppt"] = np.exp(-8.878 + .810 * result.Tmag)
    result["M"] = np.sqrt(result.n_pol) / (result.sigma_Tmag_ppt * result.rad ** 2)
    if not np.isfinite(result.M).all():
        raise RuntimeError("Nonfinite extension ranking metric")
    result = result.sort_values(["M", "tic_id"], ascending=[False, True], kind="stable").reset_index(drop=True)
    result["rank"] = np.arange(1, len(result) + 1)
    return result


def extension() -> dict:
    pool = pd.read_csv(REPO / "data/survey/cache/p8/pool_after_xmatch.csv", low_memory=False)
    original_p8 = set(pd.read_csv(REPO / "data/survey/targets_p8.csv", usecols=["tic_id"]).tic_id.astype(int))
    original_tce = set(pd.read_csv(REPO / "p10/part3/manifests/original_531.csv", usecols=["tic_id"]).tic_id.astype(int))
    selected = apply_cuts(pool)
    ranked = _rank_extension(selected[~selected.tic_id.isin(original_p8 | original_tce)])
    paths = {}
    for tier, table in (("E1", ranked.head(1000)), ("E2", ranked)):
        path = ROOT / f"manifests/targets_ext_{tier}.csv"
        _csv(path, table)
        paths[tier] = dict(path=path.relative_to(REPO).as_posix(), sha256=sha(path), rows=len(table))
    return dict(utc=utc(), tiers=paths, cut_counts=selected.attrs.get("cut_counts", {}),
                metric="sqrt(n_pol)/(exp(-8.878+0.810*Tmag)*rad**2)", tie_break="tic_id ascending")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["core", "extension"])
    args = parser.parse_args(argv)
    print(json.dumps(core() if args.mode == "core" else extension(), allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
