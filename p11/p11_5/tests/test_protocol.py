import importlib.util
from pathlib import Path
import sys
import pytest

def worker():
    root=Path(__file__).resolve().parents[1]/'protocol'
    sys.path.insert(0,str(root))
    common_spec=importlib.util.spec_from_file_location('p11_5_common_worker_test',root/'common.py')
    common=importlib.util.module_from_spec(common_spec);common_spec.loader.exec_module(common)
    spec=importlib.util.spec_from_file_location('p11_5_funnel_worker_test',root/'funnel_worker.py')
    module=importlib.util.module_from_spec(spec)
    previous=sys.modules.get('common');sys.modules['common']=common
    try:spec.loader.exec_module(module)
    finally:
        if previous is None:sys.modules.pop('common',None)
        else:sys.modules['common']=previous
    return module

@pytest.mark.parametrize('nested',[{'candidate':{'inj_period':3.}}, {'all_candidates':[{'truth':'planet'}]}, {'star':{'injection_model':{'period':3.}}}])
def test_funnel_rejects_nested_evaluator_truth_before_any_input_io(nested):
    with pytest.raises(ValueError,match='truth'):worker().setup(nested)
