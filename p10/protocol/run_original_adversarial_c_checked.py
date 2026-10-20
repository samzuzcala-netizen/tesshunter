"""Continue original EB controls with a verified TLS empty-duration contract.

The frozen original controller and all scientific source/artifacts remain intact.
Only the parent-side validator is extended: a blind chi2 +inf must correspond
exactly to an empty installed TLS duration set, with exact saved normalization.
"""
from pathlib import Path
import argparse
import hashlib
import inspect
import json
import os

import run_original_adversarial_c as R
Q, np = R.Q, R.Q.np
CONTRACT = Q.ROOT / "p10/results/original_adversarial_c_validation_contract.json"
DIAGNOSIS = Q.ROOT / "p10/results/takeover_20260908/heartbeat_checks/20260911T162800Z/empty_duration_sentinel_diagnosis.json"
ORIGINAL_VALIDATE = R.validate_case


def check_arrays(arrays, oversampling, empty_mask=None):
    """Permit only proven +inf chi2; all downstream arrays must remain exact."""
    from transitleastsquares.stats import spectra
    names = {"periods", "power", "chi2", "SR", "power_raw"}
    Q.require(set(arrays) == names, "Incomplete raw spectrum")
    p = arrays["periods"]
    Q.require(p.ndim == 1 and len(p) > 0 and all(arrays[k].shape == p.shape for k in names), "Raw shapes differ")
    Q.require(all(np.isfinite(arrays[k]).all() for k in names - {"chi2"}), "Nonfinite normalized spectrum")
    chi2 = arrays["chi2"]
    Q.require(not np.isnan(chi2).any() and not np.isneginf(chi2).any()
              and np.isfinite(chi2).any() and np.all(chi2[np.isfinite(chi2)] > 0), "Invalid chi2")
    positive_inf = np.isposinf(chi2)
    if positive_inf.any():
        Q.require(empty_mask is not None and np.array_equal(positive_inf, empty_mask), "Unproved positive-infinity trials")
        Q.require(np.all(arrays["SR"][positive_inf] == 0), "Infinite chi2 must yield zero SR")
    sr, raw, power, _, sde = spectra(chi2, oversampling)
    Q.require(np.array_equal(sr, arrays["SR"]) and np.array_equal(raw, arrays["power_raw"])
              and np.array_equal(power, arrays["power"]) and np.isfinite(sde), "TLS normalization differs")
    return int(positive_inf.sum())


def prove_empty_durations(arrays, lc_path, tls):
    from transitleastsquares import transitleastsquares
    from transitleastsquares.validate import validate_args
    from transitleastsquares.grid import duration_grid, period_grid, T14
    from transitleastsquares.transit import get_cache
    inputs = tls["inputs"]
    with np.load(lc_path, allow_pickle=False) as lc:
        model = transitleastsquares(lc["time"], lc["flux"], lc["flux_err"], verbose=False)
    rs, ms = inputs["R_star"], inputs["M_star"]
    kw = dict(period_min=inputs["period_min"], period_max=inputs["period_max"],
              oversampling_factor=inputs["oversampling_factor"], duration_grid_step=1.1,
              use_threads=1, show_progress_bar=False, verbose=False, R_star=rs, M_star=ms,
              R_star_min=max(0.1, 0.5*rs), R_star_max=2*rs,
              M_star_min=max(0.08, 0.5*ms), M_star_max=2*ms, T0_fit_margin=0.01)
    model, _ = validate_args(model, kw)
    span = max(model.t) - min(model.t)
    expected = period_grid(R_star=model.R_star, M_star=model.M_star, time_span=span,
                           period_min=model.period_min, period_max=model.period_max,
                           oversampling_factor=model.oversampling_factor, n_transits_min=model.n_transits_min)
    periods = arrays["periods"]
    Q.require(np.array_equal(np.sort(expected), periods), "Saved original period grid differs")
    durations = duration_grid(periods, shortest=1/len(model.t), log_step=model.duration_grid_step)
    maxwidth = int(max(durations)*len(model.y))
    if maxwidth % 2: maxwidth += 1
    overview, _ = get_cache(durations=durations, maxwidth_in_samples=maxwidth,
        per=model.per, rp=model.rp, a=model.a, inc=model.inc, ecc=model.ecc, w=model.w,
        u=model.u, limb_dark=model.limb_dark, verbose=False)
    widths = np.unique(overview["width_in_samples"])
    empty = np.zeros(len(periods), dtype=bool)
    for j, period in enumerate(periods):
        duration_min = T14(R_s=model.R_star_min, M_s=model.M_star_min, P=period, small=True)
        duration_max = T14(R_s=model.R_star_max, M_s=model.M_star_max, P=period, small=False)
        naive = span / period
        correction = (naive + 1) / naive
        low = int(np.floor(duration_min*len(model.y)))
        high = int(np.ceil(duration_max*len(model.y)*correction))
        empty[j] = not np.any((widths >= low) & (widths <= high))
    return empty


def load_contract():
    R.load_manifest()
    contract = Q.read(CONTRACT)
    Q.require(contract["original_adversarial_manifest_sha256"] == Q.sha(R.MANIFEST), "EB manifest changed")
    Q.verify_hashes(contract["source_sha256"])
    Q.verify_hashes(contract["evidence_sha256"])
    return contract


def validate_case(item):
    load_contract()
    try:
        return ORIGINAL_VALIDATE(item)
    except RuntimeError as exc:
        # The frozen original validator has already completed all metadata,
        # native-input, candidate, timing and duration-floor assertions here.
        if not str(exc).startswith("Incomplete/nonfinite raw spectrum: "):
            raise
    rec = item["record"]; key = rec["key"]; ws = Q.ROOT / item["workspace"]
    result = Q.read(ws / "stageC" / (key + ".json")); meta = result["p10"]
    tls = Q.read(ws / "tls" / (key + ".json")); prep = Q.read(ws / "prep" / (key + ".json"))
    manifest = R.load_manifest()
    Q.require(item["set"] == "adv" and result["input_config"] == manifest["input_config"]
              and meta["input_profile"] == R.PROFILE, "Original-input EB profile differs")
    host = manifest["hosts"][str(rec["tic_id"])]
    Q.require(sorted(p["sector"] for p in prep["per_product"]) == sorted(host["units_used"])
              and all(p["author"] == "SPOC" for p in prep["per_product"]), "Original sectors differ")
    spectra = sorted((ws / "tls").glob("*_spectrum.npz"))
    proofs = []
    for path in spectra:
        with np.load(path, allow_pickle=False) as z:
            arrays = {k:z[k] for k in z.files}
        empty = None
        if "chi2" in arrays and np.isposinf(arrays["chi2"]).any():
            Q.require(path.name == key + "_spectrum.npz", "Unreviewed nonfinite residual/narrow spectrum")
            empty = prove_empty_durations(arrays, ws / "tls" / (key + "_lc.npz"), tls)
        count = check_arrays(arrays, tls["inputs"]["oversampling_factor"], empty)
        if count:
            proofs.append(dict(path=str(path.relative_to(Q.ROOT)), positive_infinity_trials=count,
                               exact_empty_duration_mask=True, exact_TLS_normalization=True,
                               empty_duration_mask_sha256=hashlib.sha256(empty.tobytes()).hexdigest()))
    Q.require(proofs, "Finite-contract exception did not contain a proven sentinel")
    replay = R.M.replay_saved_decisions(Q, item)
    files = sorted(p for p in ws.rglob("*") if p.is_file())
    return dict(id=item["id"], set=item["set"], workspace=item["workspace"], key=key,
        a_installed=result["decision_strongest_installed"], a_with_fallback=result["decision_strongest"],
        b_installed=result["decision_significant_installed"], b_with_fallback=result["decision"],
        fallback=result["spectrum_fallback"], wall_s=meta["wall_s"], n_spectra=len(spectra),
        bin=rec.get("bin"), snr_expected=rec.get("snr_expected"),
        checks={k:True for k in ("settled_paired_decisions", "frozen_rule_options", "exact_candidate",
                "native_input_config", "raw_arrays_saved", "duration_floor_at_consumers", "original_injected_arrays_if_applicable")},
        artifact_sha256={str(p.relative_to(Q.ROOT)):Q.sha(p) for p in files},
        numerical_replay=replay, input_profile=R.PROFILE, replay_helper_sha256=Q.sha(Path(R.M.__file__)),
        raw_sentinel_proofs=proofs, validator_contract_sha256=Q.sha(CONTRACT))


def register():
    R.load_manifest(); Q.closed_prior_queues()
    Q.require(not R.LOCK.exists() and not CONTRACT.exists(), "Existing owner/contract requires review")
    diagnosis = Q.read(DIAGNOSIS)
    Q.require(diagnosis["exact_empty_duration_mask_matches"] and diagnosis["installed_normalization_arrays_and_scalar_exact"]
              and diagnosis["paired_replay"]["paired_decisions_reproduced"], "Sentinel diagnosis incomplete")
    source = {str(Path(__file__).relative_to(Q.ROOT)): Q.sha(Path(__file__)), **diagnosis["source_sha256"]}
    Q.write_new(CONTRACT, dict(utc=Q.utc(), original_adversarial_manifest_sha256=Q.sha(R.MANIFEST),
        source_sha256=source, evidence_sha256={str(DIAGNOSIS.relative_to(Q.ROOT)): Q.sha(DIAGNOSIS)},
        scope="Parent validation only. Accept blind chi2 +inf only when every such trial has no admitted installed TLS duration and all saved finite normalization arrays/scalars and paired decisions reproduce exactly. No raw array, source, threshold, sample or stellar input changes."))
    load_contract()


def recover_saved():
    load_contract(); Q.closed_prior_queues()
    Q.require(not R.LOCK.exists(), "Live corrected owner")
    state = Q.read(R.STATE)
    Q.require(state["status"] == "stopped_review_required", "Queue is not stopped for review")
    item = next(i for i in R.load_manifest()["items"] if i["id"] == state["active_id"])
    path = R.RECEIPTS / (item["id"] + ".json")
    Q.require(not path.exists(), "Completion receipt already exists")
    archive = Q.read(DIAGNOSIS.parent / "raw_array_diagnosis.json")
    for row in archive["archived"]:
        Q.require(Q.sha(Q.ROOT / row["source"]) == row["sha256"]
                  and Q.sha(Q.ROOT / row["archive"]) == row["sha256"], "Stopped evidence changed")
    fresh = validate_case(item)
    Q.write_new(path, dict(fresh, utc=Q.utc(), log=state["log"], log_sha256=Q.sha(Q.ROOT / state["log"]),
                           recovered_existing_case_without_TLS=True))
    print(json.dumps(dict(recovered_id=item["id"], original_wall_s=fresh["wall_s"], full_TLS_runs=0)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("register", "recover-saved", "inspect", "run", "validate", "measure"))
    parser.add_argument("--id"); parser.add_argument("--stage-c-source")
    args = parser.parse_args(); os.chdir(Q.ROOT)
    if args.command == "register": register(); return
    load_contract()
    R.validate_case = validate_case
    if args.command == "recover-saved": recover_saved()
    elif args.command == "run":
        Q.require(args.stage_c_source and Path(args.stage_c_source).resolve() == R.SOURCE.resolve(), "Explicit frozen Stage C source required")
        R.run_queue()
    elif args.command == "validate":
        Q.require(args.id, "Completed ID required"); R.validate(args.id)
    elif args.command == "measure": R.measure()
    else:
        print(json.dumps(dict(utc=Q.utc(), state=Q.read(R.STATE), lock=Q.read(R.LOCK) if R.LOCK.exists() else None,
            owners=Q.owners(), completed_receipts=len(list(R.RECEIPTS.glob("*.json"))),
            validator_contract_sha256=Q.sha(CONTRACT)), indent=2))


if __name__ == "__main__":
    main()
