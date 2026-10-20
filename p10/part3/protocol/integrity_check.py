"""Run historical checks with receipt writes redirected; verify P11.5 seals too.

The original verifier source is executed unchanged. Only its output writer is
substituted, before main/historical is called. Never invoke a historical writer
against a sealed directory.
"""
import argparse
import importlib.util
import sys
import time
from pathlib import Path
from common import REPO, ROOT, read, write, sha, utc, environment, initialize


def run_original(source, function, output):
    old_common = sys.modules.pop("common", None)
    directory = REPO / source
    sys.path.insert(0, str(directory.parent))
    try:
        spec = importlib.util.spec_from_file_location("historical_verifier", directory)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        expected = ("p11/results/historical_integrity.json" if function == "main"
                    else "p11/p11_5/results/historical_integrity_final.json")

        def isolated_writer(path, value, **kwargs):
            if Path(path).resolve() != (REPO / expected).resolve():
                raise RuntimeError(f"Unexpected historical write: {path}")
            write(output, dict(value, receipt_redirected_from=expected))

        module.write = isolated_writer
        getattr(module, function)()
    finally:
        sys.path.pop(0)
        sys.modules.pop("common", None)
        if old_common is not None:
            sys.modules["common"] = old_common


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["entry", "final"])
    args = parser.parse_args()
    environment()
    initialize()
    out = ROOT / "results" / f"integrity_{args.phase}"
    out.mkdir(parents=True, exist_ok=False)
    started = utc()
    timer = time.perf_counter()
    errors = []
    for source, function, filename in (
        ("p11/protocol/integrity_check.py", "main", "p10_p11.json"),
        ("p11/p11_5/protocol/integrity.py", "historical", "p11_historical.json"),
    ):
        try:
            run_original(source, function, out / filename)
        except BaseException as exc:
            errors.append(dict(source=source, error=f"{type(exc).__name__}: {exc}"))
    mismatches = []
    count = 0
    total = 0
    for manifest, field in (
        ("p11/p11_5/manifests/final_freeze.json", "source_and_evidence"),
        ("p11/p11_5/manifests/scientific_data_final.json", "hashes"),
    ):
        for name, digest in read(REPO / manifest)[field].items():
            path = REPO / name
            count += 1
            if not path.is_file():
                mismatches.append(dict(path=name, reason="missing"))
                continue
            total += path.stat().st_size
            actual = sha(path)
            if actual != digest:
                mismatches.append(dict(path=name, expected=digest, actual=actual))
    result = dict(started_utc=started, completed_utc=utc(),
        wall_seconds=time.perf_counter()-timer, p11_5_files=count,
        p11_5_bytes=total, mismatches=mismatches, verifier_errors=errors,
        historical_receipts_rewritten=False, status="FAIL" if errors or mismatches else "PASS")
    write(out / "summary.json", result)
    print(result, flush=True)
    if errors or mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
