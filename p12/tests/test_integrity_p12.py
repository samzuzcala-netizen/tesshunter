import ast
from pathlib import Path
import pytest
import integrity_check_p12 as integrity
import p9_verify_p12 as verifier
from p12_common import write,read,sha


@pytest.mark.parametrize('kind',['map','records','count_and_hashes','single','list'])
def test_documented_seal_serializations(tmp_path,kind):
    source=tmp_path/'fixture.dat';source.write_bytes(b'fixture bytes')
    digest=sha(source)
    variants={'map':{'files':{'fixture.dat':digest}},
              'records':{'hashes':{'fixture.dat':{'sha256':digest,'bytes':source.stat().st_size}}},
              'count_and_hashes':{'files':1,'hashes':{'fixture.dat':digest}},
              'single':{'path':'fixture.dat','sha256':digest},
              'list':{'files':[{'path':'fixture.dat','sha256':digest,'bytes':source.stat().st_size}]}}
    result=integrity.verify_mapping(variants[kind],tmp_path)
    assert result['files']==1 and result['status']=='PASS'
    source.write_bytes(b'changed')
    assert integrity.verify_mapping(variants[kind],tmp_path)['status']=='FAIL'


def test_original_writer_redirected_before_execution(tmp_path,monkeypatch):
    root=tmp_path/'p12';out=root/'results/integrity_entry/fixture.json'
    source=tmp_path/'p11/protocol/fixture.py';source.parent.mkdir(parents=True)
    source.write_text(
        'from pathlib import Path\n'
        'def write(path,value):\n raise AssertionError("historical writer called")\n'
        'def main():\n write(Path('+repr(str(tmp_path/'p11/results/historical_integrity.json'))+'),{"status":"PASS"})\n')
    monkeypatch.setattr(integrity,'REPO',tmp_path);monkeypatch.setattr(integrity,'ROOT',root)
    integrity.run_original('p11/protocol/fixture.py','main',out)
    assert read(out)['status']=='PASS'
    assert not (tmp_path/'p11/results').exists()
    with pytest.raises(RuntimeError,match='isolated'):
        integrity.run_original('p11/protocol/fixture.py','main',tmp_path/'p11/results/illegal.json')


def test_p9_check_body_unchanged_except_output_destination():
    repo=Path(__file__).resolve().parents[2]
    def body(path):
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        run=next(item for item in tree.body if isinstance(item,ast.FunctionDef) and item.name=='run')
        run.body=[item for item in run.body if not (isinstance(item,ast.Expr) and isinstance(item.value,ast.Call)
            and isinstance(item.value.func,ast.Name) and item.value.func.id in ('write','_p12_write'))]
        return ast.dump(run,include_attributes=False)
    assert body(repo/'p9/verify.py')==body(repo/'p12/protocol/p9_verify_p12.py')


def test_p9_output_only_adapter_fixture(tmp_path,monkeypatch):
    p9=tmp_path/'historical';sealed=p9/'results/verification.json'
    write(sealed,{'sealed':True});before=sha(sealed)
    root=tmp_path/'p12'
    monkeypatch.setattr(verifier,'P9',p9);monkeypatch.setattr(verifier,'P12_ROOT',root)
    def fake_run(partial):
        assert partial is False
        verifier._p12_write(verifier.VERIFICATION_OUTPUT,{'checks':{'fixture':True},'failures':[]})
    monkeypatch.setattr(verifier,'run',fake_run)
    verifier.main(['entry'])
    assert sha(sealed)==before
    assert read(root/'logs/p9_verification_entry.json')['checks']=={'fixture':True}
