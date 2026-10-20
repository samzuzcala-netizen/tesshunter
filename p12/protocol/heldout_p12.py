"""Part 4c evaluator entry for the held-out harness (continuation actions run from ``p12/protocol`` only).

``heldout_p12.py prepare`` runs ``p12/heldout/prepare.py all`` in its own process: the host manifest, the
per-host input selection and execution table, the frozen snapshot and its seal, then the prepared arrays.
"""
from p12_common import REPO, ROOT, PY, environment
import subprocess
import sys


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv != ['prepare']:
        raise SystemExit('usage: heldout_p12.py prepare')
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Held-out preparation runs only between phases')
    return subprocess.run([str(PY), 'p12/heldout/prepare.py', 'all'], cwd=REPO, env=environment(), check=True).returncode


if __name__ == '__main__':
    raise SystemExit(main())
