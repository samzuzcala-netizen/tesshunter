"""Exercise exact local staging and byte-preserving delivery in a tiny Git repo."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest


def load():
    protocol=Path(__file__).resolve().parents[1]/'protocol'
    old=sys.modules.get('common')
    try:
        spec=importlib.util.spec_from_file_location('common',protocol/'common.py')
        common=importlib.util.module_from_spec(spec);sys.modules['common']=common
        spec.loader.exec_module(common)
        spec=importlib.util.spec_from_file_location('p11_5_test_delivery',protocol/'local_delivery.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module
    finally:
        if old is None:sys.modules.pop('common',None)
        else:sys.modules['common']=old


@pytest.fixture
def repository(tmp_path,monkeypatch):
    d=load();repo=tmp_path/'repository';repo.mkdir()
    root=repo/'p11/p11_5'
    monkeypatch.setattr(d,'REPO',repo);monkeypatch.setattr(d,'ROOT',root)
    d.git('init','-q');d.git('config','user.name','P11.5 synthetic fixture')
    d.git('config','user.email','fixture@example.invalid');d.git('config','core.autocrlf','true')
    (repo/'base.txt').write_text('original user content\n',encoding='utf-8')
    d.git('add','base.txt');d.git('commit','-qm','Synthetic original history')
    before=d.git('rev-parse','HEAD').decode().strip()
    source='src/tesshunter/p11_5_fixture[1].py'
    files={source:b'answer = 42\n',
        'src/tesshunter/.gitattributes':b'.gitattributes -text\np11_5_*.py -text\n',
        'p11/p11_5/.gitattributes':b'* -text\n',
        'p11/p11_5/results/historical_integrity_final.json':b'{"all_pass": true}\n'}
    for relative,data in files.items():
        p=repo/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    d.write(root/'manifests/final_freeze.json',dict(all_p11_5_jobs_closed=True,
        source_and_evidence={p:d.sha(repo/p) for p in files}))
    return d,before,source


def test_literal_staging_preserves_unrelated_work_and_sealed_bytes(repository,tmp_path):
    d,before,source=repository
    unrelated=d.REPO/'unrelated user file.txt';unrelated.write_text('leave me alone\n',encoding='utf-8')
    d.commit()
    receipt=d.read(d.ROOT/'manifests/local_commit_receipt.json')
    assert receipt['head_before']==before and receipt['commit']!=before
    paths=set(d.git('diff-tree','--no-commit-id','--name-only','-r',receipt['commit']).decode().splitlines())
    assert paths==set(receipt['explicit_committed_paths']) and source in paths
    assert unrelated.read_text(encoding='utf-8')=='leave me alone\n'
    assert 'unrelated user file.txt' not in paths
    d.package(tmp_path/'outputs')
    copied=tmp_path/'outputs/P11_5/source/tesshunter/p11_5_fixture[1].py'
    assert copied.read_bytes()==(d.REPO/source).read_bytes()
    (d.REPO/source).write_bytes(b'answer = 42\r\n')
    with pytest.raises(ValueError,match='Committed bytes differ'):
        d.verify_committed_bytes(receipt['commit'],[source])


def test_preexisting_staged_user_work_is_preserved(repository):
    d,before,_=repository
    (d.REPO/'base.txt').write_text('user edit waiting for commit\n',encoding='utf-8')
    d.git('add','base.txt')
    staged_before=d.git('diff','--cached','--binary')
    with pytest.raises(RuntimeError,match='Existing staged work'):
        d.commit()
    assert d.git('rev-parse','HEAD').decode().strip()==before
    assert d.git('diff','--cached','--binary')==staged_before


def test_disk_floor_blocks_commit_before_staging(repository,monkeypatch):
    d,before,_=repository
    monkeypatch.setattr(d.shutil,'disk_usage',lambda _:SimpleNamespace(free=30000000000))
    with pytest.raises(RuntimeError,match='30 GB free-disk floor'):
        d.commit()
    assert d.git('rev-parse','HEAD').decode().strip()==before
    assert not d.git('diff','--cached','--name-only').strip()
    assert not (d.ROOT/'manifests/local_commit_receipt.json').exists()


def test_disk_floor_blocks_package_before_creating_output(repository,tmp_path,monkeypatch):
    d,_,_=repository
    d.commit()
    monkeypatch.setattr(d.shutil,'disk_usage',lambda _:SimpleNamespace(free=30050000000))
    destination=tmp_path/'not-created'/'outputs'
    with pytest.raises(RuntimeError,match='30 GB free-disk floor'):
        d.package(destination)
    assert not destination.parent.exists()
