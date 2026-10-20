"""Registered mechanical gates of phase_sequence.json; each writes one receipt.

A gate decides nothing scientific: it checks that receipts required by the prompt
exist and agree, or applies a threshold that the preregistration and config.json
fixed before the table it reads existed.
"""
from p12_common import REPO, ROOT, read, write, sha, utc
import argparse
import json
import os
from pathlib import Path


def relocation():
    """PROMPT_P12.md 0b / 5a: both audit stores on D: behind junctions, with receipts."""
    rows, problems = [], []
    for name, rel in (('audit_lightkurve', 'data/cache/audit_lightkurve'), ('audit_lc', 'data/survey/audit_lc')):
        receipt_path = ROOT / f'manifests/cache_relocation_{name}.json'
        if not receipt_path.is_file():
            problems.append(f'{name}: receipt missing'); continue
        r = read(receipt_path)
        path = REPO / rel
        target = os.readlink(path) if os.path.isjunction(path) else None
        ok = (target is not None and Path(target.replace('\\\\?\\', '')).drive.casefold() == 'd:'
              and r['files_before'] == r['files_after'] == r['files_destination']
              and r['bytes_before'] == r['bytes_after'] == r['bytes_destination']
              and r['sample']['size'] == min(1000, r['files_before']) and r['sample']['all_equal_after'] is True
              and r['sample']['seed'] == 2026092002)
        if not ok:
            problems.append(f'{name}: junction or receipt check failed')
        rows.append(dict(store=name, receipt=receipt_path.relative_to(REPO).as_posix(), receipt_sha256=sha(receipt_path),
                         junction_target=target, files=r['files_after'], bytes=r['bytes_after'], ok=ok))
    return dict(gate='relocation', passed=not problems, stores=rows, problems=problems)


GATES = dict(relocation=relocation)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('gate', choices=sorted(GATES))
    args = parser.parse_args(argv)
    result = dict(GATES[args.gate](), utc=utc(), source_sha256=sha(__file__))
    out = ROOT / f'results/gates/{args.gate}.json'
    if out.exists():
        result['previous_receipt_sha256'] = sha(out)
    write(out, result, replace=out.exists())
    print(json.dumps({k: result[k] for k in ('gate', 'passed', 'problems')}), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
