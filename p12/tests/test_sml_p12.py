import numpy as np
import pytest
import input_identity_p12 as I
import policy_products_p12 as P
import sml_p12 as S
from p12_common import read,write,sha
from B_fixtures import roots,product,identity


def test_mixed_aperture_two_qlp_fits_and_spoc_only_flux_changes(monkeypatch,tmp_path):
    repo,root,_=roots(monkeypatch,tmp_path,I,P,S)
    metadata=[];sources=[]
    for sector,author,fraction in [(56,'QLP',.9),(94,'QLP',.898),(57,'SPOC',1.)]:
        m,s=product(repo,1,sector,author=author,finite_ratio=fraction);metadata.append(m);sources.append(s)
    identity(repo,root,1,metadata,sources)
    inv=S.inventory([1]);assert inv['n_sml']==1
    assert next(r for r in inv['products'] if r['sector']==94)['generation']=='QLP_TGLC_s94_onward'
    result=S.store([1]);assert result['n_sml']==1
    before=P.load_policy_products(1);after=P.load_policy_products(1,'sml')
    for old,new in zip(before,after):
        for key in old:
            if isinstance(old[key],np.ndarray):
                equal=np.array_equal(old[key],new[key],equal_nan=True)
                assert equal == (key!='flux' or old['sector']!=56)
    unchanged=[r for r in result['products'] if not r['uses_sml']]
    assert all(r['raw_sha256']==r['original_raw_sha256'] for r in unchanged)


def test_missing_column_stays_archival(monkeypatch,tmp_path):
    repo,root,_=roots(monkeypatch,tmp_path,I,P,S)
    meta,source=product(repo,1,56,sml=False);identity(repo,root,1,[meta],[source])
    assert S.inventory([1])['n_sml']==0
    result=S.store([1]);assert result['products'][0]['raw_sha256']==result['products'][0]['original_raw_sha256']


def test_sml_tampering_other_arrays_refused(monkeypatch,tmp_path):
    repo,root,_=roots(monkeypatch,tmp_path,I,P,S)
    meta,source=product(repo,1,56);identity(repo,root,1,[meta],[source]);result=S.store([1])
    path=repo/result['products'][0]['raw_path']
    with np.load(path) as z:arrays={k:z[k] for k in z.files}
    arrays['sap_flux']=arrays['sap_flux']+1
    np.savez_compressed(path,**arrays);result['products'][0]['raw_sha256']=sha(path)
    write(root/'manifests/sml_store_index.json',result,replace=True)
    with pytest.raises(RuntimeError,match='unpermitted array'):P.load_policy_products(1,'sml')


def test_store_reuses_verified_bytes_and_extends_index(monkeypatch,tmp_path):
    repo,root,_=roots(monkeypatch,tmp_path,I,P,S)
    meta,source=product(repo,1,56);identity(repo,root,1,[meta],[source])
    first=S.store([1]);first_hash=sha(root/'manifests/sml_store_index.json')
    assert S.store([1])==first
    assert sha(root/'manifests/sml_store_index.json')==first_hash
    meta,source=product(repo,2,57);identity(repo,root,2,[meta],[source])
    second=S.store([1,2])
    assert second['n_products']==2 and second['previous_index_sha256']==first_hash
    assert second['previous_index']==first
    assert second['products'][0]['raw_sha256']==first['products'][0]['raw_sha256']
