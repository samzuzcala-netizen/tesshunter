"""Display every registered joint policy after locked development evaluation."""
from common import *
environment()
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle


def render(result,destination,*,layout_fixture=False):
    destination=Path(destination)
    outputs=[destination.with_suffix('.png'),destination.with_suffix('.svg')]
    if any(p.exists() for p in outputs):raise FileExistsError('Figure outputs are immutable')
    policies=result['policies'];lookup={(p['S'],p['D'],p['E']):p for p in policies}
    ss=('S0','S1','S2');ds=(25,36,49,64,81,100);es=(6,10)
    if set(lookup)!={(s,d,e) for s in ss for d in ds for e in es}:
        raise ValueError('The figure requires the complete registered 36-policy grid')
    values=[p['low']['gain_pp'] for p in policies if p['low']['gain_pp'] is not None]
    limit=max(5.,max((abs(v) for v in values),default=0.))
    norm=TwoSlopeNorm(vmin=-limit,vcenter=0,vmax=limit)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.hashsalt':'p11.5-development'})
    fig,axes=plt.subplots(1,2,figsize=(13.2,6.6))
    fig.subplots_adjust(left=.15,right=.90,top=.66,bottom=.30,wspace=.11)
    title='SYNTHETIC LAYOUT FIXTURE' if layout_fixture else 'P11.5 paired development'
    fig.text(.075,.94,title,fontsize=20,fontweight='bold')
    fig.text(.075,.885,f"{result['n_hosts']} D_core hosts  |  {result['n_injections']} fixed injections  |  "
        f"{result['n_hosts']} uninjected series  |  Selected search: {result['selected_search']}",fontsize=11)
    low=result['search_low']
    search=(f"{low['proposed']}/{low['n']} versus {low['baseline']}/{low['n']}; "
        f"{low['gain_pp']:+.2f} pp (95% paired host interval {low['ci95_pp'][0]:+.2f} to {low['ci95_pp'][1]:+.2f})"
        if low.get('n') else 'No injections in the registered low-SNR bin; gain unidentified')
    fig.text(.075,.83,'R1 versus R0 after pre-gate / A / bound S, expected SNR [7,15):',fontsize=10)
    fig.text(.075,.792,search,fontsize=11)
    fig.text(.075,.728,'Actual selected pre-gate / A / S / B / C recovery minus the same-input U10 upper-bound comparator',fontsize=10)
    image=None
    for axis,e in zip(axes,es):
        grid=np.array([[np.nan if lookup[(s,d,e)]['low']['gain_pp'] is None
            else lookup[(s,d,e)]['low']['gain_pp'] for d in ds] for s in ss])
        image=axis.imshow(grid,cmap='RdBu',norm=norm,aspect='auto')
        axis.set_xticks(range(len(ds)),[str(d) for d in ds])
        axis.set_xlabel('Primary and residual D threshold',labelpad=9)
        axis.set_yticks(range(len(ss)),['S0: bound','S1: recurrent','S2: flag'] if e==6 else ['','',''])
        axis.set_title(f'E threshold = {e}',pad=10,fontsize=12)
        axis.tick_params(length=0,pad=7)
        for spine in axis.spines.values():spine.set_visible(False)
        for i,s in enumerate(ss):
            for j,d in enumerate(ds):
                p=lookup[(s,d,e)];value=p['low']['gain_pp']
                text='n/a' if value is None else f'{value:+.1f}'
                colour='white' if value is not None and abs(value)>limit*.62 else '#17212b'
                axis.text(j,i,text,ha='center',va='center',fontsize=12,fontweight='bold',color=colour)
                axis.add_patch(Rectangle((j-.5,i-.5),1,1,fill=False,edgecolor='white',linewidth=1))
                if p['eligible']:
                    axis.add_patch(Rectangle((j-.45,i-.44),.9,.88,fill=False,edgecolor='#127a3e',linewidth=3))
    cax=fig.add_axes([.925,.30,.012,.36])
    fig.colorbar(image,cax=cax,label='Low-SNR gain (percentage points)')
    eligible=sum(p['eligible'] for p in policies)
    fig.text(.075,.195,f'Eligible joint policies: {eligible} / 36. Green outlines mark policies meeting every registered development criterion.',fontsize=10)
    fig.text(.075,.15,'Tiles show point estimates. Exact counts and 95% paired host intervals are in the accompanying result tables.',fontsize=9.5)
    fig.text(.075,.105,'U10: unchanged true-period pre-gate / A / bound S, before B and C. Y: actual selected route with unambiguous C PASS.',fontsize=9.5)
    fig.text(.075,.062,'Operational unknowns follow the registered recovery/workload treatment. This figure supports development inference only.',fontsize=9.5)
    destination.parent.mkdir(parents=True,exist_ok=True)
    try:
        for path in outputs:fig.savefig(path,dpi=150,facecolor='white')
    finally:plt.close(fig)
    return outputs


def main():
    source=ROOT/'results/development_evaluation.json'
    result=read(source)
    if result['final_C_stage']!='C_v2':raise ValueError('Figure requires the corrected C evaluation')
    outputs=render(result,ROOT/'results/development_overview')
    write(ROOT/'results/development_overview.json',dict(utc=utc(),evaluation_sha256=sha(source),
        figure_source_sha256=sha(Path(__file__)),
        figures={p.relative_to(REPO).as_posix():sha(p) for p in outputs},
        all_registered_policies_shown=True,threshold_selection_from_figure=False))
    print('Development figures written',*[p.name for p in outputs])


if __name__=='__main__':main()
