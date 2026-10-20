"""Validate one immutable completed C control without TLS or partial retention.

Other cases may be running. This command requires the queue's completed receipt
and refuses the active case, checks original artifacts/logs and replays the four
decisions using the completed-only report helper. Repeated checks preserve the
first validation receipt byte-for-byte. No scientific workspace is written.
"""
from pathlib import Path
import argparse
import json

import run_corrected_c_controls as Q
import measure_completed_c_controls as M


def validate(identifier):
    manifest = Q.load_manifest()
    matches = [item for item in manifest["items"] if item["id"] == identifier]
    Q.require(len(matches) == 1, "Unknown frozen control identity: " + identifier)
    item = matches[0]
    receipt_path = Q.RECEIPTS / (identifier + ".json")
    Q.require(receipt_path.is_file(), "Control has no immutable completion receipt: " + identifier)
    if Q.STATE.exists():
        state = Q.read(Q.STATE)
        Q.require(state.get("active_id") != identifier, "Control still marked active; wait for its completed transition")
    saved, fresh = Q.read(receipt_path), Q.validate_case(item)
    Q.require(all(saved[k] == value for k, value in fresh.items()), "Completed receipt/artifacts changed")
    log = Q.ROOT / "p10/logs" / ("corrected_c_" + identifier + ".log")
    Q.require(Q.sha(log) == saved["log_sha256"], "Completed case log changed")
    replay = M.replay_saved_decisions(Q, item)
    ws, key = Q.ROOT / item["workspace"], item["record"]["key"]
    stage = Q.read(ws / "stageC" / (key + ".json"))
    with Q.np.load(ws / "tls" / (key + "_spectrum.npz"), allow_pickle=False) as arrays:
        spectrum = {"n_periods": len(arrays["periods"]),
                    "period_min": float(arrays["periods"].min()),
                    "period_max": float(arrays["periods"].max())}
    result = {"id": identifier, "manifest_sha256": Q.sha(Q.MANIFEST),
              "completed_receipt_sha256": Q.sha(receipt_path), "saved_receipt_unchanged": True,
              "fresh_validation": fresh, "numerical_replay": replay,
              "installed_strongest": stage["blind"], "significant_peak": stage["significant_peak"],
              "spectrum": spectrum, "helper_sha256": Q.sha(Path(M.__file__)),
              "validator_sha256": Q.sha(Path(__file__)),
              "scope": "One completed control only, preserving original wall and evidence. No new TLS, aggregate retention, adoption or later-stage outcome inspection."}
    # Confirm the read-only replay did not modify any original evidence.
    Q.verify_hashes(fresh["artifact_sha256"])
    Q.require(Q.sha(log) == saved["log_sha256"] and Q.sha(receipt_path) == result["completed_receipt_sha256"],
              "Evidence changed during validation")
    output = Q.STATE.parent / ("corrected_c_validation_" + identifier + ".json")
    reused = output.exists()
    if reused:
        original = Q.read(output)
        Q.require(all(original[k] == value for k, value in result.items()), "Existing validation differs; preserve it for review")
    else:
        Q.write_new(output, dict(utc=Q.utc(), **result))
    print(json.dumps({"receipt": str(output.relative_to(Q.ROOT)), "reused_without_rewrite": reused,
                      **{k: fresh[k] for k in ("id", *M.COLUMNS, "wall_s", "n_spectra", "bin", "snr_expected", "fallback")},
                      "spectrum": spectrum, "replay": replay, "local": stage["significant_peak"]["local"]}, indent=2))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", required=True)
    args = parser.parse_args()
    validate(args.id)


if __name__ == "__main__":
    main()
