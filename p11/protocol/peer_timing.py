"""Validate same cadence timing after the exact P10 quality masks, no flux alignment."""
import re
import time
from collections import defaultdict
import numpy as np
from astropy.io import fits
from common import REPO,P11,DATA,read,write,utc,sha,append_event


def pair(left,right):
    with fits.open(REPO/left,memmap=False) as l, fits.open(REPO/right,memmap=False) as r:
        ld,rd=l[1].data,r[1].data
        _,i,j=np.intersect1d(ld['CADENCENO'],rd['CADENCENO'],return_indices=True)
        mask=np.isfinite(ld['TIME'][i])&np.isfinite(rd['TIME'][j])&((ld['QUALITY'][i]&(17087|(1<<30)))==0)&((rd['QUALITY'][j]&17087)==0)
        i,j=i[mask],j[mask];delta=(ld['TIME'][i]-rd['TIME'][j])*86400
        sector=int(re.search(r'_s(\d{4})-',left).group(1))
        t=ld['TIME'][i]
        median=float(np.median(delta)) if len(delta) else None
        return dict(sector=sector,left=left,right=right,n_quality_kept_shared=len(delta),
            median_seconds=median,min_seconds=float(np.min(delta)) if len(delta) else None,max_seconds=float(np.max(delta)) if len(delta) else None,
            p95_absolute_seconds=float(np.quantile(abs(delta),0.95)) if len(delta) else None,
            n_abs_above_10_seconds=int(np.sum(abs(delta)>10)),n_abs_above_half_native_cadence=int(np.sum(abs(delta)>100)),
            methods='exact CADENCENO; finite TIME; QLP 17087|2^30 and TESS-SPOC 17087 quality masks; identical BJD-TDB reference; no fitted offset',
            sample_extremes=[dict(cadenceno=int(ld['CADENCENO'][i[k]]),QLP_BTJD=float(t[k]),TESS_SPOC_BTJD=float(rd['TIME'][j[k]]),delta_seconds=float(delta[k])) for k in ([int(np.argmin(delta)),int(np.argmax(delta))] if len(delta) else [])])


def main():
    timer=time.perf_counter();started=utc();rows=[]
    for path in (P11/'results/input_inventory_v2').glob('tic*.json'):
        d=read(path)
        for rec in d['timestamp_comparisons']:
            if rec['status']=='MEASURED':rows.append(dict(tic_id=d['tic_id'],**pair(rec['left'],rec['right'])))
    by=defaultdict(list)
    for r in rows:by[r['sector']].append(r)
    sectors={str(s):dict(n_pairs=len(rs),pairs_above_10_seconds=sum(r['n_abs_above_10_seconds']>0 for r in rs),
               pairs_above_half_cadence=sum(r['n_abs_above_half_native_cadence']>0 for r in rs),
               median_offset_range_seconds=[min(r['median_seconds'] for r in rs if r['median_seconds'] is not None),max(r['median_seconds'] for r in rs if r['median_seconds'] is not None)]) for s,rs in by.items()}
    write(P11/'results/peer_timing_quality_filtered.json',dict(utc=utc(),source_sha256=sha(__file__),rows=rows,sectors=sectors,
        diagnostic_thresholds='10 seconds and half of a 200-second cadence describe discrepancy sizes, not hypothesis tests or astrophysical gates',
        interpretation='Source-copy equality verifies ingestion only. Discrepant QLP timing is unresolved; these numbers never authorize a transit-optimized correction.'))
    append_event(P11/'manifests/queue_intervals.jsonl',dict(event='interval',phase='audit_peer_timing',started_utc=started,ended_utc=utc(),wall_seconds=time.perf_counter()-timer))
    print({k:v for k,v in sectors.items() if v['pairs_above_10_seconds']},flush=True)


if __name__=='__main__':main()
