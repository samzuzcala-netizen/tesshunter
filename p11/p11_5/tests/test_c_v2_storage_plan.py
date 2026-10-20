"""Storage batching retains the complete ordered cohort and guards resources."""
import importlib.util
from pathlib import Path
import sys
import pytest


def load():
    protocol=Path(__file__).resolve().parents[1]/'protocol'
    names=('common','resource_ledger');old={n:sys.modules.get(n) for n in names}
    try:
        for name in names:
            spec=importlib.util.spec_from_file_location(name,protocol/(name+'.py'))
            module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
        spec=importlib.util.spec_from_file_location('storage_plan',protocol/'c_v2_storage_plan.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    finally:
        for name,value in old.items():
            if value is None:sys.modules.pop(name,None)
            else:sys.modules[name]=value


def item(name,size):return dict(job={'job_id':name},predicted_npz_bytes=size)


def test_every_case_and_original_order_survive_storage_partition():
    m=load();items=[item(str(i),x) for i,x in enumerate([4,6,7,2,5,5])]
    groups=m.split_batches(items,10)
    assert [x for group in groups for x in group]==items
    assert all(sum(x['predicted_npz_bytes'] for x in group)<=10 for group in groups)
    assert [len(group) for group in groups]==[2,2,2]


def test_oversized_model_and_duplicate_ids_are_refused():
    m=load()
    with pytest.raises(ValueError,match='does not fit'):m.split_batches([item('one',11)],10)
    with pytest.raises(ValueError,match='Duplicate'):m.split_batches([item('same',1),item('same',2)],10)


def test_packing_allocation_respects_actual_disk_and_memory():
    m=load();sizes=[100000000]*24
    assert m.packing_workers(sizes,35000000000,20000000000,512*1024**2)==24
    assert m.packing_workers(sizes,31000000000,20000000000,512*1024**2)==4
    with pytest.raises(RuntimeError,match='headroom'):
        m.packing_workers(sizes,30000000000,20000000000,512*1024**2)


def test_bounds_include_a_full_extra_wave_and_zero_work_costs_zero():
    m=load()
    assert m.queue_bound(24,600)==1200/3600
    assert m.queue_bound(25,600)==1800/3600
    assert m.queue_bound(0,600)==0
