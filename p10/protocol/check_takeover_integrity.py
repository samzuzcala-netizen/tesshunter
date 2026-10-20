"""Check frozen registration, read-only baselines and documented source changes."""
from pathlib import Path
import hashlib
import json
import subprocess
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parents[2]
RECEIPTS = REPO / "p10/results/takeover_20260908"
INHERITED_HEAD = "dd9457b00cba1e8290aa53ae9467be8f9cc137c7"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def frozen(data):
    return data.split(b"## 0. Pre-registered decision rules", 1)[1].split(b"## 1. Part 0: housekeeping", 1)[0]

def main():
    before = subprocess.check_output(["git", "show", INHERITED_HEAD + ":HANDOFF_P10.md"], cwd=REPO)
    after = (REPO / "HANDOFF_P10.md").read_bytes()
    checks = {"section_0_byte_identical": frozen(before) == frozen(after)}
    hashes = json.loads((RECEIPTS / "inherited_source_hashes.json").read_text(encoding="utf-8-sig"))
    changed = [r["path"] for r in hashes
               if r["path"].startswith(("src/", "scripts/", "configs/"))
               or r["path"] in ("pyproject.toml", "requirements.txt", "PROMPT_P10.md")]
    changed = [p for p in changed if sha((REPO/p).read_bytes()) != next(r["sha256"] for r in hashes if r["path"] == p)]
    corrections_path = RECEIPTS / "stage_c_source_corrections_20260910.json"
    if corrections_path.exists():
        corrections = json.loads(corrections_path.read_bytes())
        documented = {r["path"]: r for r in corrections["source_changes"]}
        original = {r["path"]: r["sha256"] for r in hashes}
        checks["scientific_source_matches_documented_corrections"] = (
            set(changed) == set(documented) and all(
                r["inherited_sha256"] == original[p] and r["corrected_sha256"] == sha((REPO/p).read_bytes())
                for p, r in documented.items()))
    else:
        checks["inherited_scientific_source_unchanged"] = not changed
    checks["p8_baseline_ancestor"] = subprocess.run(["git","merge-base","--is-ancestor","fbc68571","HEAD"],cwd=REPO).returncode == 0
    checks["no_tracked_p8_p9_edits"] = not subprocess.check_output(
        ["git","diff",INHERITED_HEAD,"--","p9","data/survey/p8","data/survey/p9"],cwd=REPO)
    checks["verification_receipt_restored"] = sha((REPO/"p9/results/verification.json").read_bytes()) == (
        RECEIPTS/"verification_original_sha256.txt").read_text(encoding="utf-8-sig").strip().lower()
    receipt = {"utc": datetime.now(timezone.utc).isoformat(), "inherited_head": INHERITED_HEAD,
               "checks": checks, "inherited_scientific_source_unchanged": not changed,
               "source_corrections_receipt": str(corrections_path.relative_to(REPO)) if corrections_path.exists() else None,
               "changed_scientific_paths": changed, "section_0_sha256": sha(frozen(before))}
    out = RECEIPTS / "takeover_integrity.json"
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0 if all(checks.values()) else 1

if __name__ == "__main__":
    raise SystemExit(main())
