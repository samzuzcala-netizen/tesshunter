"""Post-lock plots of native C spectra for rejected confirmed-planet paths.

This presents saved evidence without rerunning TLS, masking another planet,
changing a match or advancing a failed candidate to D.
"""
from common import *
import argparse
import numpy as np


def run(partial=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    scores=read(P9/'results'/('scored_signals_partial.json' if partial else 'scored_signals.json'))
    records=[]
    for s in scores:
        if s['label']!='positive' or not s['first_termination'].startswith('C'):continue
        tic=int(s['tic_id']);key=s['candidate_key'];root=P9/'results/blind'/f'tic{tic}'
        lock=P9/'results/locks'/f'tic{tic}.json'
        if not lock.exists():raise RuntimeError('Truth-labelled plot requires host lock')
        cpath=root/'stageC'/f'{key}.json';sp=root/'tls'/f'{key}_spectrum.npz'
        if not cpath.exists() or not sp.exists():continue
        c=read(cpath);z=np.load(sp);period=z['periods'];power=z['power'];seed=c['survey_period'];b=c['blind']
        fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
        for ax in axes:
            ax.plot(period,power,color='#315F85',lw=.65)
            ax.axhline(c['thresholds']['sde'],color='#777777',ls='--',lw=1,label='C SDE threshold')
            ax.axvline(seed,color='#AE4B3D',lw=1.2,label='Blind survey candidate')
            ax.set(xlabel='Blind TLS trial period (days)',ylabel='TLS SDE');ax.grid(alpha=.15)
        axes[0].set(xscale='log',xlim=(.5,110),title=f'Strongest: {b["period"]:.5f} d, SDE {b["SDE"]:.2f}')
        axes[0].plot(b['period'],b['SDE'],'o',color='#315F85',ms=5)
        axes[0].legend(fontsize=8,loc='upper right')
        axes[1].set(xlim=(seed*.98,seed*1.02),title=f'Near survey period: SDE {b["SDE_at_survey_period_max_1pct"]:.2f}; rank {b["SDE_rank_of_survey_period"]}')
        visible=power[(period>=seed*.98)&(period<=seed*1.02)&np.isfinite(power)]
        if len(visible):
            low=min(0,float(visible.min()));high=max(float(visible.max()),float(c['thresholds']['sde']))
            pad=max(.5,.12*(high-low));axes[1].set_ylim(low-pad,high+pad)
        fig.suptitle(f'{s["truth_id"]}: locked C {c["decision"]}; saved blind spectrum, no recovery change',fontsize=12)
        out=P9/'figures'/f'C_{key}.png';out.parent.mkdir(exist_ok=True);fig.savefig(out,dpi=180);plt.close(fig)
        records.append(dict(truth_id=s['truth_id'],key=key,first_termination=s['first_termination'],
          source_sha256={str(p.relative_to(P9)):sha(p) for p in [cpath,sp,lock]},
          figure=str(out.relative_to(P9)),figure_sha256=sha(out)))
    write(P9/'results'/('failure_figure_receipt_partial.json' if partial else 'failure_figure_receipt.json'),
      dict(utc=utc(),script_sha256=sha(Path(__file__)),records=records,scope='Post-lock presentation only; native spectrum, unchanged decision'))
    print('C failure figures',len(records),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');a=p.parse_args();run(a.partial)
