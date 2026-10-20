from types import SimpleNamespace
import pytest
import input_identity_p12 as I
import download_star_p12 as D
import build_batches_p12 as B
from B_fixtures import roots,product,index
from p12_common import read,write,sha


def test_corrupt_fits_forces_redownload_and_preserves_historical_bytes(monkeypatch,tmp_path):
    repo,root,data=roots(monkeypatch,tmp_path,I,D)
    meta,valid=product(repo,1,56);idx=index(repo,1,[meta])
    corrupt=repo/'data/cache/audit_lightkurve/mastDownload/fixture/corrupt_0000000000000001_lc.fits'
    corrupt.write_bytes(b'SIMPLE = truncated FITS');before=sha(corrupt)
    calls=[]
    fake=SimpleNamespace(AUDIT_CACHE=None,LC_DIR=None)
    def download(tic,force,sector_min):
        calls.append((tic,force,sector_min));return read(idx)
    fake.download=download
    lk=SimpleNamespace(search_lightcurve=lambda *a,**k:pytest.fail('Fixture must not access network'))
    result=D._download_one(1,1,False,fake,lk)
    assert result['ok'] and result['force']
    assert calls==[(1,True,56)]
    assert sha(corrupt)==before
    assert result['corrupt_cached_fits_preserved'][0]['preserved']
    assert fake.AUDIT_CACHE.is_relative_to(data)


def test_product_identity_failure_is_operational_unknown(monkeypatch,tmp_path):
    repo,root,_=roots(monkeypatch,tmp_path,I,D)
    meta,valid=product(repo,1,56);idx=index(repo,1,[meta])
    valid.write_bytes(b'corrupt')
    fake=SimpleNamespace(download=lambda *a,**k:read(idx))
    lk=SimpleNamespace(search_lightcurve=lambda *a,**k:None)
    result=D._download_one(1,1,False,fake,lk)
    assert result['status']=='OPERATIONAL_UNKNOWN'
    assert not result['ok']


def test_sector_filter_and_explicit_network_gate():
    result=SimpleNamespace(mission=['TESS Sector 55','TESS Sector 56','TESS Sector 80','TESS Sector 80','TESS Sector 106'],
        author=['QLP','QLP','QLP','SPOC','SPOC'])
    class Search:
        mission=result.mission;author=result.author
        def __len__(self):return 5
    assert D.allowed_download_rows(Search(),dict(sector_min=56,sector_max=105,qlp_excluded_sectors=[80]))==[1,3]
    with pytest.raises(RuntimeError,match='explicit --online'):D.main(['1'])


@pytest.mark.parametrize('status,error,expected',[('TIMEOUT','',True),('OPERATIONAL_UNKNOWN','ConnectionError',True),('OPERATIONAL_UNKNOWN','ValueError: bad shape',False)])
def test_transport_retry_rule(status,error,expected):
    assert B.transport_class(status,error)==expected


def test_jobs_pin_sources_and_attempt_output():
    job=B.job(1,1)
    assert job['attempt']==1 and job['source_hashes']
    assert job['retry_result_path']!=job['result_path']
    assert '--online' in job['arguments']
    with pytest.raises(ValueError):B.job(1,3)
