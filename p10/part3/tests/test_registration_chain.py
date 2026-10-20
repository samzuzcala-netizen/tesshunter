import shutil
import pytest
from common import REPO, ROOT, read
from registration_chain import verify


@pytest.mark.parametrize('changed', [
    'p10/part3/PREREGISTRATION_P10_3.md',
    'p10/part3/manifests/PREREGISTRATION_P10_3.original.md',
    'p10/part3/manifests/registration_seal.json',
    'p10/part3/protocol/config.json',
    'p10/part3/protocol/download_star_v2.py',
])
def test_amended_registration_detects_tampering(tmp_path, changed):
    chain=read(ROOT/'manifests/registration_amendments_D1_D4.json')
    files=set(read(ROOT/'manifests/registration_seal.json')['hashes'])
    files.update(chain['prelaunch_amendment_hashes'])
    files.update([chain['original_preregistration_snapshot'],chain['amendment_document'],
                  'p10/part3/manifests/registration_seal.json',
                  'p10/part3/manifests/registration_amendments_D1_D4.json'])
    for name in files:
        dest=tmp_path/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(REPO/name,dest)
    assert verify(tmp_path,tmp_path/'p10/part3')['effective_preregistration_verified']
    path=tmp_path/changed
    path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(RuntimeError):
        verify(tmp_path,tmp_path/'p10/part3')
