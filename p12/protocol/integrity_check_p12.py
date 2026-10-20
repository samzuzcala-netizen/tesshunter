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
from p12_common import REPO, ROOT, read, write, sha, utc, environment, initialize


def run_original(source, function, output):
    output = Path(output)
    if not output.resolve().is_relative_to((ROOT / 'results').resolve()):
        raise RuntimeError('Historical verifier output must be isolated under P12 results')
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


def verify_mapping(mapping, repo=None):
    repo = REPO if repo is None else Path(repo)
    if not isinstance(mapping, dict):
        raise TypeError('Seal must be a mapping')
    if isinstance(mapping.get('files'), (dict, list)):
        mapping = mapping['files']
    elif 'hashes' in mapping:
        mapping = mapping['hashes']
    elif 'source_and_evidence' in mapping:
        mapping = mapping['source_and_evidence']
    elif isinstance(mapping.get('path'), str) and isinstance(mapping.get('sha256'), str):
        mapping = {mapping['path']: mapping['sha256']}
    if isinstance(mapping, list):
        mapping = {row['path']: row for row in mapping}
    if not isinstance(mapping, dict):
        raise TypeError('Unsupported documented seal serialization')
    mismatches = []; total = 0
    for name, record in mapping.items():
        expected = record.get('sha256') if isinstance(record, dict) else record
        if not isinstance(expected, str) or len(expected) != 64:
            raise ValueError('Invalid sealed SHA-256: ' + name)
        path = repo / name
        if not path.is_file():
            mismatches.append(dict(path=name, reason='missing')); continue
        total += path.stat().st_size
        actual = sha(path)
        if actual != expected or (isinstance(record, dict) and 'bytes' in record and path.stat().st_size != record['bytes']):
            mismatches.append(dict(path=name, expected=expected, actual=actual))
    return dict(files=len(mapping), bytes=total, mismatches=mismatches, status='FAIL' if mismatches else 'PASS')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["entry", "final"])
    args = parser.parse_args(argv)
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
        ("p10/part3/manifests/final_data_seal.json", "files"),
        ("p10/part3/manifests/final_source_seal.json", "files"),
    ):
        seal = read(REPO / manifest)
        outside = seal.get('outside_input_data_seal')
        if outside:
            actual = sha(REPO / outside)
            if actual != seal.get('outside_input_data_seal_sha256'):
                mismatches.append(dict(path=outside, expected=seal.get('outside_input_data_seal_sha256'), actual=actual))
        checked = verify_mapping(seal)
        count += checked['files']; total += checked['bytes']
        mismatches.extend(checked['mismatches'])
    nested = {}
    for filename in ('p10_p11.json', 'p11_historical.json'):
        if (out / filename).is_file():
            record = read(out / filename)
            nested[filename] = {k: v for k, v in record.items() if k in (
                'registered_source_evidence_index_files', 'P10_full_calibration_files',
                'raw_and_source_FITS_files', 'status', 'all_pass', 'mismatches')}
            for field in ('frozen_evidence_checks', 'effective_historical_source_checks'):
                if field in record:
                    nested[filename][field + '_count'] = len(record[field])
                    nested[filename][field + '_mismatches'] = [name for name, row in record[field].items() if not row['match']]
    result = dict(started_utc=started, completed_utc=utc(),
        wall_seconds=time.perf_counter()-timer, directly_rehashed_seal_files=count,
        directly_rehashed_seal_bytes=total, nested_historical_verifiers=nested,
        count_scope='Direct P11.5 and P10.3 final seals; nested historical counts reported separately, with overlap not deduplicated',
        mismatches=mismatches, verifier_errors=errors,
        historical_receipts_rewritten=False, status="FAIL" if errors or mismatches else "PASS")
    write(out / "summary.json", result)
    print(result, flush=True)
    if errors or mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
