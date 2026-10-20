"""P11.5 bounded alternative reservoir and exact shared-trajectory receipts.

This module never consults injection truth. The ordinary P10 candidate list is
preserved; extras have separate identities, masks, confirmation and accounting.
"""
from contextlib import contextmanager
from functools import partial
from pathlib import Path
import hashlib
import json
import time
import numpy as np
from . import pipeline, survey
from .p11_5_detector import _detect_planets

VERSION = 'p11.5-r1-v1'

def array_key(*arrays, config=None):
    h=hashlib.sha256()
    for array in arrays:
        a=np.ascontiguousarray(array)
        h.update(str(a.dtype).encode());h.update(str(a.shape).encode());h.update(a.tobytes())
    h.update(json.dumps(config,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    return h.hexdigest()

def ephemeris_equal(a,b,baseline):
    """Period AND epoch identity; no rational-alias family collapse."""
    pa,pb=float(a['period_days']),float(b['period_days'])
    if not np.isfinite([pa,pb]).all() or min(pa,pb)<=0:return False
    if abs(pa-pb)/min(pa,pb)>.001:return False
    duration=min(float(a['duration_days']),float(b['duration_days']))
    if not np.isfinite(duration) or duration<=0:return False
    epoch=abs((float(a['epoch_btjd'])-float(b['epoch_btjd'])+.5*pb)%pb-.5*pb)
    drift=abs(pa-pb)*max(0.,float(baseline))/min(pa,pb)
    return epoch+drift<=.5*duration

def rank_pool(pool):
    # Python stable sort reproduces max()'s first-in-pool SNR tie behavior.
    return sorted(pool,key=lambda q:-float(q['snr']))

def pass_extras(pool,baseline):
    if not pool:return []
    ranked=rank_pool(pool);kept=[ranked[0]]
    for row in ranked[1:]:
        if not any(ephemeris_equal(row,q,baseline) for q in kept):kept.append(row)
        if len(kept)==3:break
    return kept[1:]

def reservoir(pools, originals, baseline, cap=12):
    all_extras=[]
    for pool in pools:
        for row in pass_extras(pool['passing'],baseline):
            all_extras.append(dict(row,snapshot_id=pool['snapshot_id'],
                search=pool['partition'],detection_pass=pool['detection_pass'],origin='R1_EXTRA'))
    distinct=[];duplicates=[]
    for row in rank_pool(all_extras):
        if any(ephemeris_equal(row,q,baseline) for q in originals+distinct):duplicates.append(row)
        else:distinct.append(row)
    kept=distinct[:cap]
    for i,row in enumerate(kept,len(originals)+1):row['planet_num']=i
    return kept,dict(proposed=len(all_extras),duplicates=len(duplicates),
                     distinct=len(distinct),retained=len(kept),truncated=distinct[cap:])

def replay(pools, originals, baseline, expected_input_key, expected_config_key):
    """A complete immutable pool is replayable only on its exact arrays/config."""
    for p in pools:
        if p.get('complete') is not True:raise ValueError('Incomplete resolved pool')
        if p.get('input_key')!=expected_input_key or p.get('config_key')!=expected_config_key:
            raise ValueError('Replay input/config mismatch')
        if not p.get('snapshot_id') or not p.get('snapshot_array_key'):
            raise ValueError('Missing reconstructable mask identity')
    return reservoir(pools,originals,baseline)

class PoolRecorder:
    def __init__(self,root,input_key,config_key):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=False)
        self.input_key=input_key;self.config_key=config_key
        self.pools=[];self.seconds=0.;self.cpu_seconds=0.;self.partition=-1
        self.base=None;self.base_key=None;self.masks={}

    def start_partition(self,label):
        self.partition=label;self.base=None;self.base_key=None

    def __call__(self,clean,working,pool,pass_index):
        start=time.perf_counter();cpu=time.process_time()
        ca=[np.asarray(clean.time.value),np.asarray(clean.flux.value),np.asarray(clean.flux_err.value)]
        wa=[np.asarray(working.time.value),np.asarray(working.flux.value),np.asarray(working.flux_err.value)]
        if self.base is None:
            self.base=ca;self.base_key=array_key(*ca)
            np.savez_compressed(self.root/f'{self.partition}_base.npz',time=ca[0],flux=ca[1],flux_err=ca[2])
        index=np.searchsorted(ca[0],wa[0])
        if any(not np.array_equal(a[index],b,equal_nan=True) for a,b in zip(ca,wa)):
            raise ValueError('Working snapshot is not an exact mask of detector input')
        mask=np.zeros(len(ca[0]),dtype=bool);mask[index]=True
        sid=f'{self.partition}_pass{pass_index}'
        self.masks[sid]=np.packbits(mask)
        passing=[]
        for row,n_obs in pool:
            q={k:(v.item() if isinstance(v,np.generic) else v) for k,v in row.to_dict().items()}
            q['n_transits_observed']=int(n_obs)
            passing.append(q)
        self.pools.append(dict(complete=True,partition=self.partition,detection_pass=pass_index,
            input_key=self.input_key,config_key=self.config_key,snapshot_id=sid,
            base_array_key=self.base_key,base_points=len(ca[0]),snapshot_array_key=array_key(*wa),
            snapshot_points=len(wa[0]),passing=passing))
        self.seconds+=time.perf_counter()-start;self.cpu_seconds+=time.process_time()-cpu

    def close(self):
        np.savez_compressed(self.root/'masks.npz',**self.masks)

    def restore(self,pool):
        with np.load(self.root/f'{pool["partition"]}_base.npz',allow_pickle=False) as z:
            arrays=[z[k] for k in ('time','flux','flux_err')]
        if array_key(*arrays)!=pool['base_array_key']:raise ValueError('Changed base array')
        with np.load(self.root/'masks.npz',allow_pickle=False) as z:
            mask=np.unpackbits(z[pool['snapshot_id']],count=pool['base_points']).astype(bool)
        result=[a[mask] for a in arrays]
        if array_key(*result)!=pool['snapshot_array_key']:raise ValueError('Changed snapshot')
        return result

@contextmanager
def capture_pools(recorder):
    """Worker-local reversible adapter; historical source and presets unchanged."""
    old_detect=pipeline._detect_planets;old_search=pipeline.search_light_curve
    def search(lc,*args,**kwargs):
        label=kwargs['target_label'].split()[-1]
        recorder.start_partition(label)
        return old_search(lc,*args,**kwargs)
    pipeline._detect_planets=partial(_detect_planets,observer=recorder)
    pipeline.search_light_curve=search
    try:yield
    finally:
        pipeline._detect_planets=old_detect;pipeline.search_light_curve=old_search

def confirm_extras(lc,extras,cfg):
    # Every extra is actually remeasured on the whole original stitch. The old
    # stitch shortcut is not applied to a hypothesis found on a masked snapshot.
    for q in extras:q['origin_partition']=q['search'];q['search']='R1_confirmation'
    result=survey.confirm_on_stitch(lc,extras,cfg,do_flatten=False)
    for q in extras:q['search']=q['origin_partition']
    return result
