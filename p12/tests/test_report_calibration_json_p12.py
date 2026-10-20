"""The calibration report's strict-JSON writer (AMENDMENTS_P12.md, 2026-09-25): open bin edges stay numeric for the
Part 6 reader, other non-finite values become null, finite values are untouched."""
import json
import math
import sys

from report_calibration_json_p12 import finite, EDGE


def test_open_bin_edge_is_numeric_and_other_non_finite_values_are_null():
    result = dict(tables=dict(rotation=[dict(bin=[10.0, 1e9], n=2), dict(bin=[1e9, float('inf')], n=0)]),
                  levels=[dict(logistic=dict(snr50=12.5, snr90=float('inf'), snr90_16_84=[float('nan'), float('-inf')]))],
                  count=3, label='cal_archival')
    out = finite(json.loads(json.dumps(result, default=float)))
    json.dumps(out, allow_nan=False)
    assert out['tables']['rotation'][0]['bin'] == [10.0, 1e9]
    assert out['tables']['rotation'][1]['bin'] == [1e9, sys.float_info.max] and EDGE == sys.float_info.max
    assert f"{out['tables']['rotation'][1]['bin'][0]:g}-{out['tables']['rotation'][1]['bin'][1]:g}" == '1e+09-1.79769e+308'
    assert out['levels'][0]['logistic'] == dict(snr50=12.5, snr90=None, snr90_16_84=[None, None])
    assert out['count'] == 3 and out['label'] == 'cal_archival'


def test_negative_open_edge_keeps_its_sign():
    assert finite(dict(bin=[float('-inf'), 0.0])) == dict(bin=[-EDGE, 0.0]) and not math.isinf(-EDGE)
