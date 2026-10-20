"""Readable pages from saved native fixed-aperture arrays; no new extraction."""
from common import *
import argparse
import numpy as np


def run(tic,key):
    if (P9/'results/locks'/f'tic{tic}.json').exists():raise RuntimeError('Host already locked')
    root=P9/'results/blind'/f'tic{tic}'
    meta=root/'eb_screen'/f'{key}_target_aperture.json';arrays=meta.with_suffix('.npz');m=read(meta)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder=root/'eb_screen/aperture_pages';folder.mkdir(exist_ok=True);pages=[]
    with np.load(arrays) as z:
        for start in range(0,len(m['sectors']),3):
            sectors=m['sectors'][start:start+3]
            fig,axes=plt.subplots(len(sectors),2,figsize=(11,3.1*len(sectors)),squeeze=False,layout='constrained')
            for row,s in enumerate(sectors):
                sec=s['sector']
                if s.get('status','complete')!='complete':
                    for ax in axes[row]:
                        ax.axis('off');ax.text(.5,.5,f'Sector {sec}: native extraction unavailable\n{s.get("error")}\n{s.get("n_background_pixels")} clean sky pixels; 16 required\nNo replacement measurement',ha='center',va='center',transform=ax.transAxes,fontsize=10)
                    continue
                time=z[f's{sec}_time'];flux=z[f's{sec}_flux'];background=z[f's{sec}_background']
                p,t0=m['ephemeris']['period'],m['ephemeris']['t0'];phase=((time-t0)/p+.25)%1-.25
                for ax,y,label in [(axes[row,0],(flux-1)*1000,'Target aperture (ppt)'),(axes[row,1],background,'Local background (electrons/s/pixel)')]:
                    # Same draw/bin/limit rules as aperture_review.py.
                    draw=np.linspace(0,len(time)-1,min(12000,len(time)),dtype=int)
                    ax.scatter(phase[draw],y[draw],s=1,alpha=.12,color='#426681')
                    bins=np.minimum(((phase+.25)*200).astype(int),199)
                    b=np.array([(j/200-.25+.0025,np.median(y[bins==j])) for j in range(200) if np.any(bins==j)])
                    ax.plot(b[:,0],b[:,1],color='#b94328',lw=1.1);lo,hi=np.quantile(y,[.002,.998]);pad=(hi-lo)*.1
                    ax.set(xlim=(-.25,.75),ylim=(lo-pad,hi+pad),xlabel='Phase at blind fitted ephemeris',ylabel=label,title=f'Sector {sec}');ax.grid(alpha=.15)
            page=start//3+1;path=folder/f'{key}_{page:02d}.png'
            fig.suptitle(f'{key}: saved native target-aperture/background arrays, page {page}',fontsize=11)
            fig.savefig(path,dpi=140);plt.close(fig)
            pages.append(dict(path=str(path.relative_to(P9)),sectors=[s['sector'] for s in sectors],sha256=sha(path)))
    write(folder/f'{key}.json',dict(utc=utc(),key=key,pages=pages,scope='Presentation of saved arrays and availability; no extraction or gate change',
      sources={str(p.relative_to(P9)):sha(p) for p in [meta,arrays]},script_sha256=sha(Path(__file__))))
    print('Aperture review pages',key,len(pages),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tic',type=int,required=True);p.add_argument('--key',required=True);a=p.parse_args();run(a.tic,a.key)
