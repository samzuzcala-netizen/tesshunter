import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'protocol'))
from close_forced_fits_v1 import validate_family
from part_f_guards_v1 import IntegrityFailure

def fixture():
    job=dict(job_id='f1',arguments=['worker','runtime','digest'])
    attempt=dict(job_id='f1',attempt=1,status='COMPLETE')
    runtime=dict(family_id='f1',tic_id=42,representative_row_id='r1',method_registration_sha256='method')
    result=dict(family_id='f1',tic_id=42,representative_row_id='r1',runtime_sha256='digest',
        scientific_attempt=1,method_registration_sha256='method',status='COMPLETE',presence='PRESENT')
    return job,attempt,runtime,result

def test_complete_and_unknown_are_distinct():
    args=fixture();assert validate_family(*args)['presence']=='PRESENT'
    args[1]['status']='TIMEOUT'
    assert validate_family(*args)['presence']=='OPERATIONAL_UNKNOWN'
    assert validate_family(*args[:3],None)['presence']=='OPERATIONAL_UNKNOWN'

@pytest.mark.parametrize('field,value',[('runtime_sha256','wrong'),('family_id','f2'),('scientific_attempt',2),
    ('method_registration_sha256','wrong'),('tic_id',99),('representative_row_id','r2')])
def test_corrupt_result_identity_refused(field,value):
    args=fixture();args[3][field]=value
    with pytest.raises(IntegrityFailure):validate_family(*args)

def test_complete_without_measurement_is_integrity_error():
    args=fixture()
    with pytest.raises(IntegrityFailure):validate_family(*args[:3],None)
