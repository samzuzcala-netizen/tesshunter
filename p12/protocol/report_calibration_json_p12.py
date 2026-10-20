"""Part 2a step 6 / 2c entry point for ``COMPLETENESS_ARM_{A,B}.{md,json}`` (AMENDMENTS_P12.md, "Calibration report
JSON: non-finite values (2026-09-25)").

``report_calibration_p12.main`` builds the registered result and then fails in the strict JSON writer: the rotation
table's last bin is ``[1e9, inf)`` (``ROT_EDGES``), and strict JSON has no infinity. This entry point runs the same
``build`` and ``markdown`` unchanged and writes the JSON with every non-finite float made representable: an open bin
edge becomes the largest finite double (the Part 6 reader formats edges as numbers), any other non-finite value
becomes null (every reader prints null as n/a). The markdown is written from the unconverted result, as before.
It is a new file rather than a supersession because the frozen stage runtimes pin every existing
``p12/protocol/*.py`` (Part 4 neg_fa_C builds its C runtimes from the arm A base runtimes).
"""
from p12_common import ROOT, write
from report_calibration_p12 import build, markdown, ARM_NAME
import json
import math
import sys

EDGE = sys.float_info.max


def finite(value, edge=False):
    """Strict-JSON copy: +-inf in a ``bin`` edge list becomes +-EDGE; every other non-finite float becomes None."""
    if isinstance(value, float) and not math.isfinite(value):
        return math.copysign(EDGE, value) if edge and not math.isnan(value) else None
    if isinstance(value, dict):
        return {k: finite(v, edge=(k == 'bin')) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite(v, edge) for v in value]
    return value


def main(argv):
    arm = argv[0]
    result = build(arm)
    name = f'COMPLETENESS_ARM_{ARM_NAME[arm]}'
    write(ROOT / f'results/part2/{name}.json', finite(json.loads(json.dumps(result, default=float))), replace=False)
    (ROOT / f'results/part2/{name}.md').write_text(markdown(result), encoding='utf-8')
    print(json.dumps(dict(arm=arm, n=result['n_injections'], whole=result['levels'][-1]['through'])), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
