"""Presentation-only redraw from saved arrays; no fits or scientific outcome changes."""
from pathlib import Path
import os, sys
REPO=Path(r'C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter')
sys.path.insert(0,str(REPO/'p10/part3/protocol'))
from common import ROOT,read,sha,write,utc,environment
environment()
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

fid='tic29002055_family000007'
r=read(ROOT/f'results/autopsies/{fid}.json')
noise=read(ROOT/'results/native_noise/tic29002055.json')
assert sha(REPO/noise['prepared_path'])==noise['prepared_sha256']
events_path=next((REPO/r['diagnostic_root']/'events').glob('*.json'))
events=read(events_path)
finite_events=[e for e in events['events'] if e.get('observed') and isinstance(e.get('det_depth_ppt'),(int,float)) and np.isfinite(e['det_depth_ppt'])]
assert not finite_events
with np.load(REPO/noise['prepared_path'],allow_pickle=False) as z:
    t,f=z['time'],z['flux']
good=np.isfinite(t)&np.isfinite(f);t,f=t[good],f[good]
row=r['representative'];p=float(row['tce_period']);epoch=float(row['tce_time0bt']);d=float(row['tce_duration'])/24
fig,axes=plt.subplots(1,3,figsize=(15,4),layout='constrained')
step=max(1,len(t)//12000)
axes[0].scatter(t[::step],1000*(f[::step]-1),s=1,alpha=.35)
axes[0].set(xlabel='BTJD',ylabel='Prepared flux (ppt)',title='Frozen native search input')
phase=(t-epoch+p/2)%p-p/2;mask=abs(phase)<2*d
edges=np.linspace(-2*d,2*d,61)
n,_=np.histogram(phase[mask],edges);s,_=np.histogram(phase[mask],edges,weights=f[mask]);ok=n>0
axes[1].plot((edges[1:]+edges[:-1])[ok]*12,(s[ok]/n[ok]-1)*1000,'.-')
axes[1].axvspan(-d*12,d*12,color='grey',alpha=.15)
axes[1].set(xlabel='Hours from nominal TCE epoch',ylabel='Binned flux (ppt)',title='TCE-informed fold; diagnostic only')
axes[2].set_axis_off()
axes[2].text(.5,.58,'No finite detrended\nevent-depth measurements',ha='center',va='center',fontsize=13,transform=axes[2].transAxes)
axes[2].text(.5,.31,'12 observed opportunities\n5 excluded; 7 kept opportunities\n0 finite kept depth measurements',ha='center',va='center',fontsize=10,transform=axes[2].transAxes)
fig.suptitle('TIC 29002055 · nominal-ephemeris diagnostic · original outcomes unchanged',fontsize=11)
out=ROOT/f'results/autopsies/{fid}_display_v2.png';assert not out.exists()
fig.savefig(out,dpi=150);plt.close(fig)
write(ROOT/'results/autopsy_display_v2.json',dict(utc=utc(),purpose='Presentation-only redraw; annotate empty measurement panel',
    original_plot=r['figure_path'],original_plot_sha256=sha(REPO/r['figure_path']),display_plot=out.relative_to(REPO).as_posix(),display_sha256=sha(out),
    input_hashes={noise['prepared_path']:noise['prepared_sha256'],events_path.relative_to(REPO).as_posix():sha(events_path)},scientific_reexecution=False))
print(out)
