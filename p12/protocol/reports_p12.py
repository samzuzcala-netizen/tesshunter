"""Report dispatcher: ``reports_p12.py <kind> [args]`` runs ``report_<kind>_p12.main(args)``.

Each report kind is its own sealed module (chained into the registration before the phase that
runs it), so adding a later part's report never rewrites an earlier sealed report.
"""
from p12_common import ROOT
import importlib
import sys

KINDS = ('calibration', 'tabulations', 'ttt', 'p9_blind', 'p9_assisted', 'specificity', 'extension', 'natural_load',
         'completeness', 'audit', 'handoff')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in KINDS:
        raise SystemExit('usage: reports_p12.py {' + ','.join(KINDS) + '} [args]')
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Reports run only between phases')
    module = importlib.import_module(f'report_{argv[0]}_p12')
    return module.main(argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
