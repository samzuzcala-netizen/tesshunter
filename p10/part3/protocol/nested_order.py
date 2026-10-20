"""Registered metadata-only nested order and point-count timing selection."""
from common import host_hash


def stratum(row):
    m=float(row['tmag']);s=int(row['n_usable_sectors'])
    if not 12.5<=m<=14 or s<3:raise ValueError('Host outside registered input strata')
    return f'{0 if m<13 else 1 if m<13.5 else 2}:{0 if s<=5 else 1 if s<=10 else 2}'


def order(rows):
    groups={}
    for r in rows:groups.setdefault(stratum(r),[]).append(r)
    for group in groups.values():group.sort(key=lambda r:(host_hash(r['tic_id']),int(r['tic_id'])))
    used={k:0 for k in groups};result=[];n=len(rows)
    for i in range(n):
        active=[k for k in groups if used[k]<len(groups[k])]
        key=min(active,key=lambda k:(-((i+1)*len(groups[k])-used[k]*n),k))
        result.append(dict(tic_id=int(groups[key][used[key]]['tic_id']),stratum=key));used[key]+=1
    return result


def timing_pilot(rows):
    ordered=sorted(rows,key=lambda r:(int(r['n_cad']),int(r['tic_id'])))
    n=len(rows);base,extra=divmod(n,3);start=0;selected=[]
    for i in range(3):
        size=base+(i<extra);part=ordered[start:start+size];start+=size
        if len(part)<2:raise ValueError('Fewer than two hosts in a timing tercile')
        chosen=sorted(part,key=lambda r:(host_hash(r['tic_id'],'timing'),int(r['tic_id'])))[:2]
        selected.extend(dict(tic_id=int(r['tic_id']),tercile=i,n_cad=int(r['n_cad'])) for r in chosen)
    return selected
