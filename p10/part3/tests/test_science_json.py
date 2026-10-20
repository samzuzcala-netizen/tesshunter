import json
import numpy as np
from science_json import safe


def test_numpy_and_nonfinite_diagnostics_are_saved_without_changing_finite_values():
    value={'period':np.float64(2.123),'count':np.int64(4),'diagnostic':np.nan,'vector':np.array([1.,np.inf])}
    result=json.loads(json.dumps(safe(value),allow_nan=False))
    assert result=={'period':2.123,'count':4,'diagnostic':None,'vector':[1.,None]}
