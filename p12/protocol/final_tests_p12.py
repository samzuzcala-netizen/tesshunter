"""Part 6e.3 gate: the three suites, each alone, through ``run_tests_p12.py`` (verdicts and counts only).

``tests p11/tests p11/p11_5/tests`` (891 passed, 1 skipped, as at entry), ``p10/part3/tests`` (118, the ruled
0a count) and ``p12/tests`` (every test passes). Receipts under ``p12/results/final_tests/<suite>/``; the gate
receipt ``p12/results/gates/final_tests.json``; exit 1 when any suite differs.
"""
from p12_common import REPO, ROOT, PY, environment, read, write, sha, utc
import json
import subprocess

SUITES = (('compatibility', ['tests', 'p11/tests', 'p11/p11_5/tests'], dict(passed=891, skipped=1, failed=0, errors=0)),
          ('p10_part3', ['p10/part3/tests'], dict(passed=118, failed=0, errors=0)),
          ('p12', ['p12/tests'], dict(failed=0, errors=0)))


def main():
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Tests run alone with no owner')
    rows, ok = [], True
    for name, targets, expected in SUITES:
        output = f'p12/results/final_tests/{name}'
        code = subprocess.run([str(PY), 'p12/protocol/run_tests_p12.py', '--output', output, *targets], cwd=REPO,
                              env=environment(), timeout=3600).returncode
        receipt = read(REPO / output / 'receipt.json')
        match = all(receipt.get(k) == v for k, v in expected.items()) and (name != 'p12' or receipt.get('passed', 0) > 0)
        ok = ok and match
        rows.append(dict(suite=name, targets=targets, exit_code=code, expected=expected,
                         observed={k: receipt.get(k) for k in ('passed', 'failed', 'skipped', 'errors')}, match=match,
                         receipt_sha256=sha(REPO / output / 'receipt.json')))
    result = dict(utc=utc(), gate='final_tests', passed=ok, suites=rows, source_sha256=sha(__file__))
    write(ROOT / 'results/gates/final_tests.json', result, replace=(ROOT / 'results/gates/final_tests.json').exists())
    print(json.dumps(dict(passed=ok, suites={r['suite']: r['observed'] for r in rows})), flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
