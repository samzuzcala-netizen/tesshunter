import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
import numpy as np
from recipe import measure,box_overlap,aliases
from ingest import match_time,aperture_map,net_flux
def test_time_alignment_not_index():
    t=np.arange(10.)/432;t2=t+.0002
    j,ok,dt=match_time(t2,t,.001)
    assert ok.all() and np.array_equal(j,np.arange(10))
    j,ok,dt=match_time(t2[2:],t,.001)
    assert np.array_equal(j,np.arange(2,10))
def test_alignment_reject_duplicates():
    import pytest
    with pytest.raises(ValueError):match_time(np.array([.0001,.0002]),np.arange(4.)*.01,.005)
def test_optimal_aperture_mapping():
    ap=np.zeros((4,5),int);ap[1,2]=2;ap[2,3]=3
    m=aperture_map(ap,[100,200],(21,21),[95,197])
    assert m[4,7] and m[5,8] and m.sum()==2
def test_background_sign():
    cube=np.full((5,3,3),20.);cube[:,1,1]+=10;cube[2,1,1]-=2
    mask=np.zeros((3,3),bool);mask[1,1]=True
    net=net_flux(cube,mask,np.full(5,20.))
    assert np.array_equal(net,[10,10,8,10,10])
def test_depth_injection_mixed_cadences_separate():
    for cadence in [200/86400,600/86400,1800/86400]:
        t=np.arange(-.5,.5,cadence);base=500*(1+.08*t)
        q=box_overlap(t,0,.0928318,cadence);y=base*(1-.0065*q)
        r=measure(t,y,np.ones(len(t),bool),0,.0928318,cadence)
        assert r['valid'] and abs(r['depth']-6.5)<1e-8
def test_guard_and_event_masks():
    t=np.arange(-.5,.5,200/86400);r=measure(t,np.ones(len(t)),np.ones(len(t),bool),0,.0928318,200/86400,details=True)
    assert not np.any(r['in_mask']&r['out_mask'])
    assert np.min(abs(r['t'][r['out_mask']]))>=.0928318/2+1/24
def test_gap_not_bridged():
    t=np.arange(-.5,.5,200/86400);good=~((t>.13)&(t<.16))
    assert 'gap' in measure(t,np.ones(len(t)),good,0,.0928318,200/86400)['reason']
def test_momentum_not_bridged():
    t=np.arange(-.5,.5,200/86400)
    assert 'momentum' in measure(t,np.ones(len(t)),np.ones(len(t),bool),0,.0928318,200/86400,dumps=np.array([.2]))['reason']
def test_alias_enumeration():
    p=18.748084871649127;n,period=aliases(0,33*p)
    assert n[0]==7 and n[-1]==618 and np.min(abs(period-p))<1e-12
    assert np.all((period>=1)&(period<=100))
def test_long_cadence_partial_exposure():
    q=box_overlap(np.array([-.05,0,.05]),0,.08,.02)
    assert np.allclose(q,[0,1,0],atol=1e-10)
    assert np.allclose(box_overlap(np.array([-.04,.04]),0,.08,.02),.5)
def test_actual_detector_geometry():
    import common as C,json
    geo=json.loads((C.WS/'inputs/ccd_geometry.json').read_text())
    off=[]
    for r in geo:
        col,row=r['target_ccd']
        if not (45<=col<=2092 and 1<=row<=2048):off.append(r['sector'])
    assert sorted(off)==[25,40,50,52]
    # The conclusion does not depend on the one-based vs zero-based convention.
    assert sorted(r['sector'] for r in geo if not (44<=r['target_ccd'][0]<=2091 and 0<=r['target_ccd'][1]<=2047))==off
def test_qdata_time_and_aperture_reality():
    import common as C,json
    from ingest import load
    for sec in [24,26,51,53,57,77,78,79,80,84]:
        a=load(sec);p=load(sec,'pixel')
        j,ok,dt=match_time(p['original_time'],a['time'],float(a['cadence'])/2)
        assert ok.all() and np.allclose(p['time'],a['time'][j])
        assert p['opt_mask'].sum()==np.sum((a['aperture']&2)!=0)
if __name__=='__main__':
    import pytest,common as C,sys,io,contextlib
    stream=io.StringIO()
    with contextlib.redirect_stdout(stream):code=pytest.main([__file__,'-q','-p','no:cacheprovider'])
    text=stream.getvalue();print(text);(C.WS/'logs/tests.txt').write_text(text,encoding='utf-8');sys.exit(code)
