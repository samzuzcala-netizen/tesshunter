"""A transient progress-file reader must not abort unrelated science jobs."""
import importlib.util
from pathlib import Path
import sys
import pytest

def module():
    root=Path(__file__).resolve().parents[1]/'protocol';sys.path.insert(0,str(root))
    def load(name,path):
        spec=importlib.util.spec_from_file_location(name,path)
        value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
    common=load('p11_5_record_io_common_test',root/'common.py')
    previous=sys.modules.get('common');sys.modules['common']=common
    try:return load('p11_5_record_io_test',root/'record_io.py')
    finally:
        if previous is None:sys.modules.pop('common',None)
        else:sys.modules['common']=previous

def test_transient_permission_failure_retries_same_record_without_restarting_job(monkeypatch):
    value=module();attempts=[];events=[]
    monkeypatch.setattr(value.time,'sleep',lambda seconds:None)
    monkeypatch.setattr(value.base,'event',lambda *a,**k:events.append((a,k)))
    def operation(path,body,replace):
        attempts.append((path,body,replace))
        if len(attempts)<3:raise PermissionError('reader temporarily holds target')
        return 'written'
    assert value.transient_call(operation,'progress',{'completed':98},replace=True)=='written'
    assert attempts==[('progress',{'completed':98},True)]*3
    assert events[0][1]['attempts']==2

def test_nonsharing_errors_are_not_hidden():
    value=module()
    def operation():raise ValueError('scientific identity changed')
    with pytest.raises(ValueError,match='identity'):value.transient_call(operation)

def test_persistent_access_failure_has_a_finite_retry_deadline(monkeypatch):
    value=module();clock=[0.];calls=[]
    def now():clock[0]+=11.;return clock[0]
    monkeypatch.setattr(value.time,'monotonic',now)
    def operation():calls.append(1);raise PermissionError('persistent access failure')
    with pytest.raises(PermissionError,match='persistent'):value.transient_call(operation)
    assert len(calls)==1
