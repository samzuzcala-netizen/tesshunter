import json
import sys
from types import SimpleNamespace
import numpy as np
import pytest
import input_identity_p12 as I
import policy_products_p12 as P
from p12_common import read,write
from B_fixtures import roots,product,identity


def test_excluded_qlp_and_failed_preferred_never_returned(monkeypatch,tmp_path):
    repo,root,_=roots(monkeypatch,tmp_path,I,P)
    metadata=[];sources=[]
    for sector,author in [(56,'QLP'),(80,'QLP'),(57,'SPOC'),(57,'QLP'),(74,'QLP')]:
        m,s=product(repo,1,sector,author=author);metadata.append(m);sources.append(s)
    value=identity(repo,root,1,metadata,sources)
    value['records'][2]['timing_status']='SOURCE_UNVERIFIED'
    value['selected_sectors']=[56]
    write(root/'manifests/input_identity/tic1.json',value,replace=True)
    got=P.load_policy_products(1)
    assert [(p['sector'],p['author']) for p in got]==[(56,'QLP')]


def test_policy_refuses_changed_raw_and_changed_selection(monkeypatch,tmp_path):
    repo,root,_=roots(monkeypatch,tmp_path,I,P);m,s=product(repo,1,56)
    value=identity(repo,root,1,[m],[s]);value['selected_sectors']=[80]
    write(root/'manifests/input_identity/tic1.json',value,replace=True)
    with pytest.raises(RuntimeError,match='Selected sectors'):P.load_policy_products(1)
    value['selected_sectors']=[56];write(root/'manifests/input_identity/tic1.json',value,replace=True)
    with (repo/value['records'][0]['raw_path']).open('ab') as f:f.write(b'changed')
    with pytest.raises(RuntimeError,match='Raw product hash'):P.load_policy_products(1)


def test_install_both_exactly_one_star_and_restore(monkeypatch,tmp_path):
    from tesshunter import survey_p8
    old=survey_p8.load_audit_products;old_a=lambda tic: []
    fake=SimpleNamespace(load_products=old_a,AUDIT_CACHE=None)
    monkeypatch.setitem(sys.modules,'audit_p5',fake)
    calls=[]
    monkeypatch.setattr(P,'redirect_audit_cache',lambda a:calls.append(a))
    monkeypatch.setattr(P,'load_policy_products',lambda tic,arm:[dict(tic=tic,arm=arm)])
    restore=P.install(123,'sml')
    try:
        assert calls==[fake]
        assert survey_p8.load_audit_products(123)==fake.load_products(123)==[dict(tic=123,arm='sml')]
        with pytest.raises(RuntimeError,match='different star'):fake.load_products(124)
    finally:restore()
    assert survey_p8.load_audit_products is old
    assert fake.load_products is old_a
