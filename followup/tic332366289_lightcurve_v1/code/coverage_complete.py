import common as C
import numpy as np,pandas as pd
from ingest import load
from analyze import series_for
from astropy.time import Time
rows=[]
for s in C.SECTORS:
    series,_=series_for(s);base=series.get('SAP',series['PIX_SMALL']);t=base['t']
    for label,(P,T,d) in [('EA',C.EA),('EF',C.EF)]:
        for n in range(int(np.ceil((1950-T)/P)),int(np.floor((3620-T)/P))+1):
            tc=T+n*P;inside=(abs(t-tc)<=d/2)&base['good']&np.isfinite(base['y']);inrange=t[0]-d/2<=tc<=t[-1]+d/2
            rows.append(dict(sector=s,ephemeris=label,cycle=n,tc=tc,in_sector_time_range=inrange,n_good_in=int(sum(inside)),target_active=s not in [25,40,50,52]))
pd.DataFrame(rows).to_csv(C.WS/'results/all_cycle_sector_coverage.csv',index=False)
geo=C.json.loads((C.WS/'inputs/ccd_geometry.json').read_text())
inv=[]
for s in C.SECTORS:
    a=load(s,'pixel');g=next(r for r in geo if r['sector']==s);active=s not in [25,40,50,52]
    inv.append(dict(sector=s,first_btjd=float(a['time'].min()),last_btjd=float(a['time'].max()),cadence_s=float(a['cadence'])*86400,target_ccd_col=g['target_ccd'][0],target_ccd_row=g['target_ccd'][1],target_active=active,spoc_available=(C.BIG/'arrays'/f'spoc_{s}.npz').exists(),n_EA_epochs_in_range=sum(r['in_sector_time_range'] for r in rows if r['sector']==s and r['ephemeris']=='EA'),status='active science pixels' if active else 'off science array; cutout existence is not target coverage'))
pd.DataFrame(inv).to_csv(C.WS/'results/sector_coverage.csv',index=False)
start=Time('2026-10-01T00:00:00',scale='utc').tdb.jd-2457000
first=int(np.ceil((start-C.EF[1])/C.EF[0]));future=[]
for n in range(first,first+5):
    ea=C.EA[1]+n*C.EA[0];ef=C.EF[1]+n*C.EF[0];err=np.hypot(.0053882258523593385,n*.00018556567112793171);half=C.EA[2]/2+3*err+1/24
    future.append(dict(cycle=n,EA_BTJD=ea,EF_BTJD=ef,EF_formal_1sigma_min=err*1440,EA_approx_UTC=Time(ea+2457000,format='jd',scale='tdb').utc.isot,window_start_BTJD=min(ea,ef)-half,window_end_BTJD=max(ea,ef)+half,window_start_approx_UTC=Time(min(ea,ef)-half+2457000,format='jd',scale='tdb').utc.isot,window_end_approx_UTC=Time(max(ea,ef)+half+2457000,format='jd',scale='tdb').utc.isot,note='conditional 18.748-day hypothesis; UTC approximate, no observer barycentric correction; covariance and alias uncertainty not included'))
pd.DataFrame(future).to_csv(C.WS/'results/conditional_future_windows.csv',index=False)
print('Coverage complete; future windows',future)
