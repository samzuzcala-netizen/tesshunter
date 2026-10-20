import pytest
import guards_p12 as guards
from p12_common import write, sha


@pytest.fixture
def guards_root(tmp_path,monkeypatch):
    root=tmp_path/'p12';(root/'manifests').mkdir(parents=True)
    monkeypatch.setattr(guards,'REPO',tmp_path);monkeypatch.setattr(guards,'ROOT',root)
    return tmp_path,root


@pytest.mark.parametrize('phase',['neg_ttt','bar_endpoint','final_search'])
def test_freeze_required(guards_root,phase):
    with pytest.raises(guards.IntegrityFailure,match='freeze'):
        guards.verify_freeze(phase)


def test_freeze_hash_refusal(guards_root):
    repo,root=guards_root
    source=root/'worker.py';source.write_text('old')
    write(root/'manifests/freeze_p12_0.json',{'source_hashes':{'p12/worker.py':sha(source)}})
    assert guards.verify_freeze('final_search')['source_hashes_verified']==1
    source.write_text('changed')
    with pytest.raises(guards.IntegrityFailure,match='hash changed'):
        guards.verify_freeze('final_search')
    assert guards.verify_freeze('verify_core') is None


def test_durable_integrity_failure(guards_root):
    repo,root=guards_root
    guards.signal_integrity_failure('fixture mismatch',{'phase':'dummy'})
    with pytest.raises(guards.IntegrityFailure):
        guards.assert_no_integrity_failure()
