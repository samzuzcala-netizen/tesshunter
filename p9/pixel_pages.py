"""Paginate saved native scientific arrays for readable pre-lock pixel review."""
from common import *
import argparse
import numpy as np


def run(tic,key):
    if (P9/'results/locks'/f'tic{tic}.json').exists():raise RuntimeError('Host already locked')
    root=P9/'results/blind'/f'tic{tic}'
    meta=root/'eb_screen'/f'{key}_fit_difference.json';arrays=meta.with_suffix('.npz')
    m=read(meta)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import SymLogNorm
    pages=[];folder=root/'eb_screen/pages';folder.mkdir(exist_ok=True)
    with np.load(arrays) as z:
        for start in range(0,len(m['sectors']),3):
            sectors=m['sectors'][start:start+3]
            fig,axes=plt.subplots(len(sectors),3,figsize=(12.5,3.9*len(sectors)),squeeze=False,layout='constrained')
            for row,s in enumerate(sectors):
                sector=s['sector'];panels=[(z[f's{sector}_primary_reference'],'Local out-of-eclipse reference'),
                  (z[f's{sector}_primary_difference'],f'Primary difference: {len(s["primary_counts"])} events'),
                  (z[f's{sector}_secondary_difference'],f'Phase 0.5 difference: {len(s["secondary_counts"])} events')]
                for col,(values,title) in enumerate(panels):
                    ax=axes[row,col]
                    # These plotting normalizations/markers are exactly the native I.main choices.
                    if col==0:
                        norm=SymLogNorm(linthresh=max(float(np.nanpercentile(np.abs(values),25)),1),
                          vmin=float(np.nanmin(values)),vmax=float(np.nanmax(values)))
                        im=ax.imshow(values,origin='lower',cmap='gray_r',norm=norm)
                    else:
                        scale=max(float(np.nanpercentile(np.abs(values),99)),1e-9)
                        im=ax.imshow(values,origin='lower',cmap='RdBu_r',vmin=-scale,vmax=scale)
                    for pos in s['gaia_positions']:
                        label=pos['label']
                        if not label:continue
                        if label=='T':ax.scatter(pos['x'],pos['y'],marker='+',s=42,color='cyan',linewidths=.7)
                        else:ax.scatter(pos['x'],pos['y'],marker='o',s=14,facecolors='none',edgecolors='cyan',linewidths=.7)
                        ax.text(pos['x']+.2,pos['y']+.25,label,fontsize=7,color='#087f8c')
                    ax.set(title=f'Sector {sector}: {title}',xlabel='Cutout column (zero based)',ylabel='Cutout row (zero based)')
                    fig.colorbar(im,ax=ax,shrink=.75,label='electrons / s')
            page=start//3+1;path=folder/f'{key}_{page:02d}.png'
            fig.suptitle(f'{key}: native difference-array review, page {page}\nT = propagated Gaia target; red = dimming; maxima are not fitted source positions.',fontsize=12)
            fig.savefig(path,dpi=140);plt.close(fig)
            pages.append(dict(path=str(path.relative_to(P9)),sectors=[s['sector'] for s in sectors],sha256=sha(path)))
    write(folder/f'{key}.json',dict(utc=utc(),key=key,scope='Presentation of saved native arrays; no new measurement or scientific decision',
      sources={str(p.relative_to(P9)):sha(p) for p in [meta,arrays,BASE/'scripts/p8_eb_difference_image.py']},
      script_sha256=sha(Path(__file__)),pages=pages))
    print('Pixel review pages',key,len(pages),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tic',type=int,required=True);p.add_argument('--key',required=True);a=p.parse_args();run(a.tic,a.key)
