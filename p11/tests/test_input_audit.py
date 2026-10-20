import importlib.util
from pathlib import Path
import sys

import numpy as np
from astropy.io import fits

PROTO=Path(__file__).resolve().parents[1]/'protocol'
sys.path.insert(0,str(PROTO))
import noise_audit as noise
import input_inventory as inventory
import instrument_noise
import analyze_audit


def test_depth_retention_separates_normalization_from_lost_depth():
    t=np.arange(200,dtype=float)
    shape=np.zeros(200);shape[20:30]=0.008;shape[120:130]=0.008
    uninj=1+0.0001*np.sin(t)
    result=noise.paired_depth(t,uninj,uninj-0.93*shape+0.001,shape)
    assert result['status']=='MEASURED'
    assert abs(result['retained_depth_fraction']-0.93)<1e-10
    assert abs(result['renormalization_offset']+0.001)<1e-10


def test_noise_model_uses_sky_aperture_and_read_counts_in_electrons():
    # 100 source e, 50 sky e, 4 pixels, 3 reads and 2 e/read -> variance 198 e^2.
    assert np.isclose(instrument_noise.count_noise(100,50,4,3,2),np.sqrt(198)/100)
    assert instrument_noise.count_noise(100,50,4,3,2)>instrument_noise.count_noise(100,0,0,0,0)


def test_queue_budget_counts_union_including_overlapping_and_failed_attempts():
    merged=analyze_audit.merge_intervals([(10,20),(0,15),(25,30),(26,27)])
    assert merged==[[0,20],[25,30]]
    assert sum(b-a for a,b in merged)==25


def test_absent_transits_are_unknown_not_perfect_retention():
    r=noise.paired_depth(np.arange(100),np.ones(100),np.ones(100),np.zeros(100))
    assert r['status']=='UNMEASURED'
    assert 'retained_depth_fraction' not in r


def test_actual_preparation_preserves_resolved_injection_on_synthetic_array():
    # Exercise the real detrending import path as well as the actual estimator.
    rng=np.random.default_rng(72);t=np.arange(6000)*200/86400
    flux=1+0.001*np.sin(2*np.pi*t/4)+rng.normal(0,0.0002,len(t))
    product=dict(time=t,flux=flux,flux_err=np.full(len(t),0.0002),sap_flux=flux,
        sap_flux_err=np.full(len(t),0.0002),sap_bkg=np.zeros(len(t)),quality=np.zeros(len(t),dtype=np.int64),
        sector=70,author='TESS-SPOC',cadence_s=200)
    params=dict(period=3.0,t0=0.7,rp_rs=0.06,b=0.3,a_rs=15,u=(0.3,0.2))
    injected,_=noise.survey_p8.inject_products([product],**params,supersample=7)
    plain=noise.survey_p8.prepare_search_input([product],0.75)
    altered=noise.survey_p8.prepare_search_input(injected,0.75)
    common,i,j=np.intersect1d(plain['time'],altered['time'],return_indices=True)
    shape=1-noise.transit_model(common,**params,exp_time_days=200/86400,supersample=7)
    result=noise.paired_depth(common,plain['flux'][i],altered['flux'][j],shape)
    assert result['status']=='MEASURED'
    assert 0.8<result['retained_depth_fraction']<1.1


def test_white_noise_time_bins_and_gaps_have_physical_occupancy():
    rng=np.random.default_rng(71)
    t=np.arange(30*432)*200/86400
    f=1+rng.normal(0,0.004,len(t))
    keep=(t<10)|(t>15)
    r=noise.noise(t[keep],f[keep],np.ones(keep.sum(),dtype=int))[0]
    assert 0.8<r['duty_cycle']<0.85
    assert 3.6<r['point_scatter_ppt']<4.4
    assert 0.7<r['timescales']['1']['red_noise_inflation']<1.3
    assert r['timescales']['4']['n_bins']<30*6


def test_fits_provenance_exactly_reproduces_reader_nan_time_filter(tmp_path,monkeypatch):
    monkeypatch.setattr(inventory,'REPO',tmp_path)
    raw=tmp_path/'data/survey/audit_lc/tic123';raw.mkdir(parents=True)
    t=np.array([3000.,np.nan,3000.004,3000.006]);flux=np.array([1.,2.,1.01,0.99]);q=np.zeros(4,dtype=np.int32)
    cols=[fits.Column(name='TIME',array=t,format='D'),fits.Column(name='PDCSAP_FLUX',array=flux,format='D'),
          fits.Column(name='SAP_FLUX',array=flux,format='D'),fits.Column(name='QUALITY',array=q,format='J')]
    primary=fits.PrimaryHDU()
    for k,v in dict(SECTOR=70,TICID=123,TIMESYS='TDB',TIMEREF='SOLARSYSTEM',BJDREFI=2457000).items():primary.header[k]=v
    path=tmp_path/'hlsp_tess-spoc_0000000000000123-s0070_v1_lc.fits'
    fits.HDUList([primary,fits.BinTableHDU.from_columns(cols)]).writeto(path)
    valid=np.isfinite(t)
    np.savez(raw/'s070_TESSSPOC.npz',time=t[valid],flux=flux[valid],flux_err=np.ones(3)*0.01,
             sap_flux=flux[valid],sap_flux_err=np.ones(3)*0.01,sap_bkg=np.ones(3),quality=q[valid])
    inventory.write(raw/'index.json',{'products':[dict(file='s070_TESSSPOC.npz',author='TESS-SPOC',sector=70,cadence_s=200,flux_column='pdcsap_flux')]})
    out=inventory.inventory_host({'tic_id':123},[path])
    record=out['records'][0]
    assert all(record['checks'].values())
    assert record['source_rows_removed_for_nonfinite_time']==1
    assert record['timing_status']=='UNAFFECTED_SOURCE_VERIFIED'
    with np.load(raw/'s070_TESSSPOC.npz') as z:changed={k:z[k] for k in z.files}
    changed['time']=changed['time']+1/86400
    np.savez(raw/'s070_TESSSPOC.npz',**changed)
    assert inventory.inventory_host({'tic_id':123},[path])['records'][0]['timing_status']=='SOURCE_UNVERIFIED'
