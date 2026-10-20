"""Display published-timing sensitivity using unchanged saved blind C flux."""
from common import *
import argparse
import numpy as np
import pandas as pd


def run(partial=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from scoring import verify_lock
    suffix='_partial' if partial else ''
    audit=read(P9/f'results/positive_ephemeris_audit{suffix}.json')
    truth=pd.read_csv(P9/'truth/final_truth.csv').set_index('truth_id');records=[]
    for row in audit['records']:
        alternatives=[r for r in row['alternative_solutions'] if r['diagnostic_existing_path']['search']]
        for i,alternative in enumerate(alternatives):
            tic=row['tic_id'];verify_lock(tic)
            candidate=next(c for c in alternative['candidate_matches'] if c['event_match']['matched']);key=candidate['key']
            root=P9/'results/blind'/f'tic{tic}';source=root/'tls'/f'{key}_lc.npz'
            fitpath=root/'fit'/f'{key}.json'
            if not source.exists() or not fitpath.exists():continue
            with np.load(source) as a:tt=a['time'];yy=(a['flux']-1)*1000
            fit=read(fitpath)['adopted'];nominal=truth.loc[row['truth_id']]
            panels=[('Frozen default truth',float(nominal.period),float(nominal.epoch_btjd)),
                ('Alternative published solution',alternative['period'],alternative['epoch_btjd']),
                ('Already-locked blind physical fit',fit['period'],fit['t0_btjd'])]
            fig,axes=plt.subplots(1,3,figsize=(13.2,4.3),sharex=True,sharey=True,layout='constrained')
            limits=np.quantile(yy[np.isfinite(yy)],[.01,.99]);span=max(1,float(limits[1]-limits[0]))
            for ax,(title,p,t0) in zip(axes,panels):
                x=((tt-t0+p/2)%p-p/2)*24
                ax.scatter(x,yy,s=2,c='#547991',alpha=.13,rasterized=True)
                bins=np.linspace(-4,4,81);indices=np.digitize(x,bins)
                med=[np.median(yy[indices==j]) if np.any(indices==j) else np.nan for j in range(1,len(bins))]
                ax.plot((bins[:-1]+bins[1:])/2,med,c='#A44635',lw=1.5,label='Display-bin median')
                ax.axvline(0,c='#555555',lw=.8,ls='--');ax.set(xlim=(-4,4),ylim=(limits[0]-.1*span,limits[1]+.1*span),
                    xlabel='Time from predicted transit center (h)',title=title+'\nP = '+f'{p:.8f}'+' d')
                ax.grid(alpha=.15)
            axes[0].set_ylabel('Saved blind prepared flux (ppt)');axes[2].legend(fontsize=8,loc='upper right')
            fig.suptitle(row['truth_id']+': same saved flux; changed display ephemeris only\nPost-lock diagnostic; no primary recovery credit',fontsize=12)
            target=P9/'figures'/f'ephemeris_{key}_{i+1}.png';fig.savefig(target,dpi=170);plt.close(fig)
            records.append(dict(truth_id=row['truth_id'],key=key,source_sha256={str(p.relative_to(P9)):sha(p) for p in [source,fitpath]},
                alternative_reference=alternative['reference'],output=str(target.relative_to(P9)),output_sha256=sha(target),
                transformation='Phase coordinates and display medians only; identical saved flux in all panels, no refit, no clipping of analysis data, fixed display range'))
    write(P9/f'results/ephemeris_figures{suffix}.json',dict(utc=utc(),script_sha256=sha(Path(__file__)),records=records))
    print('Ephemeris sensitivity figures',len(records),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');args=parser.parse_args();run(args.partial)
