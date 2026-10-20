from types import SimpleNamespace
import pytest
import neighbours_worker_p12 as N
import neighbours_batch_worker_p12 as B
from B_fixtures import roots
from p12_common import read,write


def test_bulk_coverage_and_p12_destinations(monkeypatch,tmp_path):
    repo,root,data=roots(monkeypatch,tmp_path,N)
    (repo/'scripts').mkdir();(repo/'scripts/p8_neighbours.py').write_text('fixture')
    fake=SimpleNamespace(load_targets=lambda p:[dict(tic_id='1')],bulk_simbad=lambda rows:{1:[]})
    monkeypatch.setattr(N,'N',fake)
    result=N.main('simbad')
    assert result['ok'] and result['n_hosts']==1
    assert fake.OUT==data and fake.BULK==data/'neighbours_bulk'
    assert (root/'results/neighbour_receipts/simbad.json').exists()
    fake.bulk_simbad=lambda rows:{}
    with pytest.raises(RuntimeError,match='coverage mismatch'):N.main('simbad')


def test_per_star_requires_both_bulk_sources(monkeypatch,tmp_path):
    repo,root,data=roots(monkeypatch,tmp_path,N)
    fake=SimpleNamespace(load_targets=lambda p:[dict(tic_id='1')],one=lambda *a:pytest.fail('must not call without bulk'))
    monkeypatch.setattr(N,'N',fake)
    with pytest.raises(RuntimeError,match='Missing bulk'):N.main('1')


def test_batch_retains_failure_receipt(monkeypatch,tmp_path):
    repo,root,_=roots(monkeypatch,tmp_path,B)
    path=root/'manifests/batch.json';write(path,dict(batch_id='fixture',tics=[1,2]))
    def one(tic):
        if tic=='2':raise RuntimeError('fixture transport error')
    monkeypatch.setattr(B.worker,'main',one)
    with pytest.raises(SystemExit):B.main(path)
    result=read(root/'results/neighbour_batches/fixture.json')
    assert result['stars']==2 and len(result['failures'])==1
