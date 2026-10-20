"""K1 Part E freeze: ``k1/protocol/config.json`` (every parameter) and ``k1/manifests/freeze_k1.json``
(source hashes of every K1 protocol file and every touched ``src`` module, the registration, amendments,
decisions and seeds).  Input: ``k1/results/decisions_E.json`` written by the E1-E4 evaluation.
After this, any change is a dated amendment with a reason.

CLI: ``freeze_k1.py`` (refuses to overwrite an existing freeze unless ``--amendment <file>`` is given).
"""
from __future__ import annotations

import argparse
import dataclasses
import glob
import json
import sys
from pathlib import Path

from k1_common import REPO, ROOT, environment, read, write, sha, utc

TOUCHED_SRC = ["bls_search.py", "survey.py", "survey_p8.py", "pipeline.py", "event_vet.py", "star_vet.py",
               "secondary.py", "k1_rules.py", "audit_rules.py"]
WORKERS = {"download": 4, "search": 24, "A": 16, "S": 16, "B": 16, "C": 6, "C_tls_threads": 4, "D": 6}


def build_config(dec: dict) -> dict:
    environment(offline=True)
    from tesshunter import survey, k1_rules, event_vet, star_vet, bls_search
    import sector_policy_k1 as SP
    preset = dec["E1"]["preset"]
    cfg = survey.get_config(preset, time_budget_s=float(dec["E4"]["budget_s"]))
    return {
        "preset": preset, "search_config": json.loads(json.dumps(dataclasses.asdict(cfg), default=str)),
        "time_budget_s": float(dec["E4"]["budget_s"]),
        "s_mode": dec["E2"]["mode"], "sap_ramp_variant": bool(dec["E3"]["adopt"]),
        "pregate": {"stitch_snr_min": 7.1, "stitch_n_transits_min": 3, "stitch_epoch_consistent": True},
        "early_funnel_rules": "p10.0 (A/S/B/C, as P12) with K1 swaps: native-cadence choice per sector, "
                              "coarsest-in-transit-cadence TLS duration floor, B per-window cadence rule, S mode above",
        "tiers": "k1.0 (p12.0 + K8 density-only at P > 10 d -> HOLD)",
        "hard_stop": "K1Catalog: REJECT TOI/CTOI/NASA/TESS-EB/TTT; FLAG SPOC TCE (sidecar period veto) and <= 21 arcsec",
        "k1_rules": {k: getattr(k1_rules, k) for k in dir(k1_rules) if k.isupper()},
        "event_vet.SAP_RAMP_NOISE_MULTIPLE": (k1_rules.K1_SAP_RAMP_NOISE_MULTIPLE if dec["E3"]["adopt"] else None),
        "star_vet.B_CADENCE_RULE": "per_window",
        "bls_search.EVENT_COMPLETENESS": "mean_err",
        "sector_policy": {"sector_max": 98, "excluded": "99-104 and 105+", "qlp_tess_spoc_only": [80, 83, 85],
                          "qlp_v02_required": sorted(SP.QLP_V02_REQUIRED), "prefer": "TESS-SPOC (through s85) over QLP"},
        "workers": WORKERS, "seeds": dec.get("seeds"), "decisions": dec,
        "event_vet.EVENT_DEPTH_TEMPLATE": k1_rules.K1_EVENT_DEPTH_TEMPLATE,
        "operations": {"search_phases_power_throttling": "windows_default (as calibrated: E-cores only)",
                       "other_phases_power_throttling": "opted_out (controller_k1.unthrottle)",
                       "retry": "one retry per phase; TIMEOUT jobs get 4x their deadline (controller_k1.RETRY_TIMEOUT_FACTOR)",
                       "deadlines_s": {"search": "budget x 1.6 + 900", "A": 1800, "S": 600, "B": 600,
                                       "C": "14400 (57600 for samples with 30-40-sector hosts)", "D": 5400}},
        "defaults_untouched": {"event_vet.SAP_RAMP_NOISE_MULTIPLE": event_vet.SAP_RAMP_NOISE_MULTIPLE,
                               "star_vet.B_CADENCE_RULE": star_vet.B_CADENCE_RULE,
                               "bls_search.DEFAULT_N_DURATIONS": bls_search.DEFAULT_N_DURATIONS},
    }


def hashes() -> dict:
    files = sorted(glob.glob(str(ROOT / "protocol" / "*.py")) + glob.glob(str(ROOT / "protocol" / "*.ps1"))
                   + glob.glob(str(ROOT / "protocol" / "*.md")) + glob.glob(str(ROOT / "protocol" / "data" / "*")))
    out = {str(Path(f).relative_to(REPO)).replace("\\", "/"): sha(f) for f in files}
    for m in TOUCHED_SRC:
        p = REPO / "src" / "tesshunter" / m
        out[f"src/tesshunter/{m}"] = sha(p)
    for s in ("build_k1_population.py",):
        out[f"scripts/{s}"] = sha(REPO / "scripts" / s)
    return out


def main(amendment=None):
    cfg_path, frz_path = ROOT / "protocol" / "config.json", ROOT / "manifests" / "freeze_k1.json"
    if frz_path.exists() and not amendment:
        raise SystemExit("freeze exists; changes need --amendment <file>")
    dec = read(ROOT / "results" / "decisions_E.json")
    cfg = build_config(dec)
    write(cfg_path, cfg, replace=True)
    frz = {"utc": utc(), "config_sha256": sha(cfg_path), "registration": read(ROOT / "manifests" / "registration.json"),
           "rules_sha256": sha(ROOT / "protocol" / "RULES_K1.md"), "sources": hashes(), "decisions": dec,
           "amendment": amendment, "python": sys.version}
    if frz_path.exists():
        prev = frz_path.with_name(f"freeze_k1_superseded_{utc().replace(':', '')[:15]}.json")
        frz_path.replace(prev)
        frz["supersedes"] = str(prev)
    write(frz_path, frz)
    print(json.dumps({"config": str(cfg_path), "config_sha256": frz["config_sha256"], "n_sources": len(frz["sources"])}, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--amendment")
    main(ap.parse_args().amendment)
