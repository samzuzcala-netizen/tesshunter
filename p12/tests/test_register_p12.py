import pytest
import register_p12 as register
from p12_common import write,sha


def setup(tmp_path,monkeypatch):
    root=tmp_path/'p12';(root/'protocol').mkdir(parents=True);(root/'manifests').mkdir()
    for name in ('PROMPT_P12.md','p12/PREREGISTRATION_P12.md','p12/protocol/config.json','p12/protocol/a.py'):
        (tmp_path/name).write_text('{}' if name.endswith('.json') else 'fixture')
    write(root/'results/integrity_entry/summary.json',{'status':'PASS'})
    write(root/'manifests/resource_ledger.json',{'existing':True})
    monkeypatch.setattr(register,'REPO',tmp_path);monkeypatch.setattr(register,'ROOT',root)
    return root


def test_registration_roundtrip_preserves_existing_ledger(tmp_path,monkeypatch):
    root=setup(tmp_path,monkeypatch);prior=sha(root/'manifests/resource_ledger.json')
    result=register.register()
    assert register.verify()['status']=='PASS'
    assert 'PROMPT_P12.md' in result['hashes'] and 'p12/protocol/a.py' in result['hashes']
    assert sha(root/'manifests/resource_ledger.json')==prior
    with pytest.raises(FileExistsError):register.register()


@pytest.mark.parametrize('change',['prompt','python','membership'])
def test_registration_tamper_refused(tmp_path,monkeypatch,change):
    root=setup(tmp_path,monkeypatch);register.register()
    path={'prompt':tmp_path/'PROMPT_P12.md','python':root/'protocol/a.py','membership':root/'protocol/new.py'}[change]
    path.write_text('changed')
    with pytest.raises(RuntimeError,match='registration mismatch'):
        register.verify()


def test_chain_addition_seals_a_later_module(tmp_path,monkeypatch):
    root=setup(tmp_path,monkeypatch);register.register()
    later=root/'protocol/later.py';later.write_text('later module')
    with pytest.raises(RuntimeError,match='membership'):register.verify()
    result=register.add(['p12/protocol/later.py'],'part 2 module')
    assert register.verify()['chain_links']==1 and result['files']==1
    later.write_text('tampered')
    with pytest.raises(RuntimeError,match='registration mismatch'):register.verify()


def test_chain_refuses_frozen_and_unrecorded_supersession(tmp_path,monkeypatch):
    root=setup(tmp_path,monkeypatch);register.register()
    with pytest.raises(ValueError,match='Frozen'):register.add(['p12/protocol/config.json'],'no')
    (root/'protocol/a.py').write_text('fixed module')
    with pytest.raises(ValueError,match='supersession'):register.add(['p12/protocol/a.py'],'fix')
    register.add(['p12/protocol/a.py'],'fix',amendment='AMENDMENTS_P12.md fixture',supersede=True)
    assert register.verify()['status']=='PASS'


def test_chain_link_order_is_verified(tmp_path,monkeypatch):
    root=setup(tmp_path,monkeypatch);register.register()
    (root/'protocol/b.py').write_text('b');register.add(['p12/protocol/b.py'],'first')
    (root/'protocol/c.py').write_text('c');register.add(['p12/protocol/c.py'],'second')
    first=sorted((root/'manifests/registration_chain').glob('0001_*.json'))[0]
    body=first.read_text().replace('"first"','"edited"');first.write_text(body)
    with pytest.raises(RuntimeError,match='predecessor'):register.verify()


def test_effective_hashes_carry_a_supersession(tmp_path,monkeypatch):
    root=setup(tmp_path,monkeypatch);register.register()
    (root/'protocol/a.py').write_text('fixed');register.add(['p12/protocol/a.py'],'fix',amendment='x',supersede=True)
    hashes,python,problems,_=register.effective()
    assert not problems and hashes['p12/protocol/a.py']==sha(root/'protocol/a.py')
    assert read_seal(root)['hashes']['p12/protocol/a.py']!=hashes['p12/protocol/a.py']


def read_seal(root):
    import json
    return json.loads((root/'manifests/registration_seal.json').read_text())
