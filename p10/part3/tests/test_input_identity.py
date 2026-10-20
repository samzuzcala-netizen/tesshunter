import copy
import numpy as np
import pytest
from input_identity import compare,timing_status,choose_verified


def fixture():
    cols={'TIME':np.array([1.,np.nan,2.,3.]),'DET_FLUX':np.array([1.,2.,3.,4.]),
          'SAP_FLUX':np.array([5.,6.,7.,8.]),'QUALITY':np.array([0,0,0,1<<30])}
    raw={'time':cols['TIME'][[0,2,3]],'flux':cols['DET_FLUX'][[0,2,3]],
         'sap_flux':cols['SAP_FLUX'][[0,2,3]],'quality':cols['QUALITY'][[0,2,3]],'flux_err':np.full(3,np.nan)}
    meta={'sector':74,'author':'QLP','flux_column':'det_flux','cadence_s':200}
    source={'sector':74,'author':'QLP','version':'02','headers':{'TIMESYS':'TDB','TIMEREF':'SOLARSYSTEM','BJDREFI':2457000}}
    return raw,meta,(source,cols['TIME'],cols)


@pytest.mark.parametrize('field',['time','flux','sap_flux','quality'])
def test_each_required_array_change_is_rejected(field):
    raw,meta,source=fixture()
    assert compare(raw,meta,source)['all_required_exact']
    raw[field]=raw[field].copy();raw[field][0]+=1
    assert not compare(raw,meta,source)['all_required_exact']


def test_corrected_version_is_required_even_for_equal_arrays():
    raw,meta,source=fixture();configuration={'qlp_excluded_sectors':[80], 'qlp_correction_required_sectors':list(range(74,80))}
    checked=compare(raw,meta,source)
    assert checked['nonfinite_time_rows_removed']==1
    assert timing_status(meta,source[0],checked,configuration)=='CORRECTED_V02_SOURCE_VERIFIED'
    assert timing_status(meta,dict(source[0],version='01'),checked,configuration)=='CORRECTED_V02_REQUIRED'


def test_author_choice_and_window_are_not_changed_by_verification_failure():
    config={'sector_min':56,'sector_max':105,'qlp_excluded_sectors':[80]}
    def row(s,author,state='SOURCE_VERIFIED'):
        return {'metadata':{'sector':s,'author':author,'cadence_s':200},'timing_status':state,'n_quality_good':100}
    rows=[row(55,'SPOC'),row(56,'SPOC','SOURCE_UNVERIFIED'),row(56,'QLP'),row(80,'QLP'),row(105,'TESS-SPOC'),row(106,'SPOC')]
    assert [r['metadata']['sector'] for r in choose_verified(rows,config)]==[105]
