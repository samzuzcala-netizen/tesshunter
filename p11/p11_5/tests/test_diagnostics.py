from pathlib import Path
import sys,importlib.util

def isolated_module(name):
    root=Path(__file__).resolve().parents[1]/'protocol'
    sys.path.insert(0,str(root))
    def load(module_name,path):
        spec=importlib.util.spec_from_file_location(module_name,path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module
    common=load('p11_5_common_diagnostic_test',root/'common.py')
    # Historical P11 also calls its protocol module common. Production workers
    # are separate processes; tests must keep the two module namespaces apart.
    previous=sys.modules.get('common');sys.modules['common']=common
    try:return load('p11_5_'+name+'_test',root/(name+'.py'))
    finally:
        if previous is None:sys.modules.pop('common',None)
        else:sys.modules['common']=previous

def test_scientific_time_union_counts_overlap_once_and_keeps_stalls():
    assert isolated_module('resource_ledger').union([(5,10),(0,7),(20,30),(30,40)])==[[0,10],[20,40]]

def test_diagnostic_cannot_invent_finite_threshold_with_no_recoveries():
    rows=[dict(snr_expected=x,y=False) for x in (0,1,10,100)]
    fit=isolated_module('sensitivity_tables').logistic_point(rows,'y')
    assert fit['status']=='UNIDENTIFIED' and fit['n']==3

def test_model_storage_preserves_exact_container_and_array_values(tmp_path):
    import numpy as np
    module=isolated_module('model_storage')
    source=tmp_path/'model.npz';values=np.arange(1000,dtype=np.float64)/7
    np.savez_compressed(source,model=values,flat=np.ones(1000))
    original=module.sha(source);packed=tmp_path/'model.npz.xz'
    receipt=module.pack_container(source,packed)
    assert receipt['original_container_bytes_identical']
    assert module.decompressed_sha(packed)==original
    source.unlink()
    with module.open_model(source) as arrays:
        assert np.array_equal(arrays['model'],values)
        assert np.array_equal(arrays['flat'],np.ones(1000))

def test_model_storage_rejects_path_escape_before_filesystem_access():
    import pytest
    with pytest.raises(ValueError,match='identity'):
        isolated_module('model_storage').pack_one('../historical')

def test_final_C_path_never_falls_back_to_uncorrected_measurement():
    module=isolated_module('final_c')
    assert module.stage_path('fixture','C').parent.name=='C_v2'
    assert module.stage_path('fixture','A').parent.name=='A'
