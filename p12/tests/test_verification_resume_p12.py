import pytest
from verification_resume_p12 import archive_partial


def test_partial_archive_preserves_bytes_and_refuses_overwrite(tmp_path):
    root=tmp_path/'p12';source=root/'prepared/case';source.mkdir(parents=True)
    body=b'partial preparation fixture';(source/'native.npz').write_bytes(body)
    destination=root/'interrupted/case'
    receipt=archive_partial(source,destination,root)
    assert receipt['files']==1 and (destination/'native.npz').read_bytes()==body and not source.exists()
    source.mkdir();(source/'native.npz').write_bytes(b'new attempt')
    with pytest.raises(FileExistsError):archive_partial(source,destination,root)
    assert (source/'native.npz').read_bytes()==b'new attempt'
    assert (destination/'native.npz').read_bytes()==body


def test_partial_archive_rejects_escape_before_moving(tmp_path):
    root=tmp_path/'p12';root.mkdir();source=root/'case.json';source.write_bytes(b'fixture')
    with pytest.raises(RuntimeError,match='escapes'):
        archive_partial(source,tmp_path/'outside.json',root)
    assert source.read_bytes()==b'fixture' and not (tmp_path/'outside.json').exists()
