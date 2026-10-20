"""P9-pattern post-lock diagnostics; no search, TLS, forced-fit retry or primary-score change."""
from common import REPO,ROOT,DATA,read,write,sha,utc,environment
environment()
import sys,csv,json,time,re,traceback
from collections import Counter
import numpy as np
from funnel_worker import legacy
from part_f_math_v1 import finite,RATIOS
from part_f_guards_v1 import require_hash,IntegrityFailure,signal_integrity_failure,assert_no_integrity_failure
from science_json import safe

def period_kind(period,target):
    if finite(period) is None or period<=0:return None
    distance,_,label=min((abs(period/(target*ratio)-1),i,label) for i,(ratio,label) in enumerate(RATIOS))
    return label if distance<.01 else None

def trace_census(lines,target):
    counts=Counter();near=[];competition=[]
    for number,text in enumerate(lines,1):
        row=json.loads(text);counts[row.get('event')]+=1
        if row.get('event')!='broad_bls':continue
        candidates=row.get('candidates',[])
        matching=[q for q in candidates if period_kind(q.get('period_days'),target)]
        for q in matching:near.append(dict(line=number,partition=row.get('partition'),pass_number=row.get('pass'),
            alias=period_kind(q['period_days'],target),**{k:q.get(k) for k in ('period_days','epoch_btjd','duration_days','snr','peak_rank')}))
        if matching and candidates and not period_kind(candidates[0].get('period_days'),target):
            competition.append(dict(line=number,partition=row.get('partition'),pass_number=row.get('pass'),
                leading_period=candidates[0]['period_days'],leading_snr=candidates[0].get('snr'),near_ranks=[q.get('peak_rank') for q in matching]))
    return dict(events=dict(counts),near_trial_count=len(near),near_trials=near,broad_rank_competition=competition,
        interpretation='BLS rank witnesses alone do not show internal gate passage or establish a globally matching ephemeris.')

def log_census(text,target):
    partition='unassigned';iteration=0;passes={};stops=[]
    for number,line in enumerate(text.splitlines(),1):
        m=re.search(r'search_light_curve: TIC \d+ (chunk\d+|stitch)',line)
        if m:partition=m.group(1);iteration=0
        m=re.search(r'Detection pass (\d+) \(planet (\d+)\)',line)
        if m:
            iteration=int(m.group(1));passes[(partition,iteration)]=dict(partition=partition,pass_number=iteration,near_trials=[],chosen=None)
        row=passes.get((partition,iteration))
        if row is not None:
            m=re.search(r'\[([\d.]+) d -> ([\d.]+) d\]\s+(.*)',line)
            if m and (period_kind(float(m.group(1)),target) or period_kind(float(m.group(2)),target)):
                tail=m.group(3);comp=re.search(r'composite ([\d.]+)',tail);snr=re.search(r'SNR ([\d.]+)',tail)
                row['near_trials'].append(dict(line=number,raw_period=float(m.group(1)),resolved_period=float(m.group(2)),
                    resolved_alias=period_kind(float(m.group(2)),target),internal_gates_passed=tail.rstrip().endswith('PASS'),
                    composite=float(comp.group(1)) if comp else None,snr=float(snr.group(1)) if snr else None,message=tail))
            m=re.search(r'Accepted planet (\d+): \[([^]]*)\]\s+P = ([\d.]+) d.*composite ([\d.]+)',line)
            if m:row['chosen']=dict(line=number,period=float(m.group(3)),composite=float(m.group(4)),planet_num=int(m.group(1)))
        if any(token in line.lower() for token in ('budget exhausted','budget exceeded','time budget','would remove','finite cadences remain')):
            stops.append(dict(line=number,message=line))
    informative=[r for r in passes.values() if r['near_trials']]
    witnesses=[r for r in informative if r['chosen'] and not period_kind(r['chosen']['period'],target) and
        any(t['internal_gates_passed'] and t['resolved_alias'] for t in r['near_trials'])]
    return dict(detection_passes=len(passes),informative_passes=informative,selection_witnesses=witnesses,stop_messages=stops,
        interpretation='Local period-compatible gate survivors lost recorded selection; this is not a measured alternative recovery.')

def figure(path,runtime,noise,events):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    require_hash(REPO/noise['prepared_path'],noise['prepared_sha256'],'Autopsy native plot input')
    with np.load(REPO/noise['prepared_path'],allow_pickle=False) as z:t,f=z['time'],z['flux']
    good=np.isfinite(t)&np.isfinite(f);t,f=t[good],f[good]
    row=runtime['representative'];p=float(row['tce_period']);epoch=float(row['tce_time0bt']);d=float(row['tce_duration'])/24
    fig,axes=plt.subplots(1,3,figsize=(15,4),layout='constrained')
    step=max(1,len(t)//12000);axes[0].scatter(t[::step],1000*(f[::step]-1),s=1,alpha=.35)
    axes[0].set(xlabel='BTJD',ylabel='Prepared flux (ppt)',title='Frozen native search input')
    phase=(t-epoch+p/2)%p-p/2;mask=abs(phase)<2*d
    edges=np.linspace(-2*d,2*d,61);n,_=np.histogram(phase[mask],edges);s,_=np.histogram(phase[mask],edges,weights=f[mask]);ok=n>0
    axes[1].plot((edges[1:]+edges[:-1])[ok]*12,(s[ok]/n[ok]-1)*1000,'.-')
    axes[1].axvspan(-d*12,d*12,color='grey',alpha=.15)
    axes[1].set(xlabel='Hours from nominal TCE epoch',ylabel='Binned flux (ppt)',title='TCE-informed fold; diagnostic only')
    for excluded,color,label in [(False,'#24724a','Kept'),(True,'#ad3c36','Removed')]:
        rows=[e for e in events['events'] if e.get('observed') and bool(e.get('excluded'))==excluded and finite(e.get('det_depth_ppt')) is not None and finite(e.get('det_depth_err_ppt')) is not None]
        axes[2].errorbar([e['tc_btjd'] for e in rows],[e['det_depth_ppt'] for e in rows],
            yerr=[e['det_depth_err_ppt'] for e in rows],fmt='.',ms=3,alpha=.6,color=color,label=label)
    axes[2].legend(fontsize=8);axes[2].set(xlabel='Event BTJD',ylabel='Event depth (ppt)',title='Counterfactual event removal')
    fig.suptitle(f"TIC {runtime['tic_id']} · {runtime['family_id']} · no primary-score change",fontsize=11)
    path.parent.mkdir(parents=True,exist_ok=True);fig.savefig(path,dpi=150);plt.close(fig)

def main(runtime_name,expected):
    assert_no_integrity_failure();require_hash(REPO/runtime_name,expected,'Autopsy runtime')
    runtime=read(REPO/runtime_name);fid=runtime['family_id'];tic=runtime['tic_id']
    out=ROOT/f'results/autopsies/{fid}.json';assert not out.exists()
    started,timer=utc(),time.perf_counter()
    try:
        for path,digest in runtime['source_hashes'].items():require_hash(REPO/path,digest,'Autopsy source')
        for path,digest in runtime['input_hashes'].items():require_hash(REPO/path,digest,'Autopsy input')
        root=DATA/f'autopsies_v1/{fid}';root.mkdir(parents=True,exist_ok=False)
        row=runtime['representative'];star=runtime['star'];noise=read(REPO/runtime['noise_path'])
        p=float(row['tce_period']);duration=max(float(row['tce_duration'])/24,noise['cadence_days'])
        candidate=dict(rank=1,tic_id=tic,planet_num=1,period_days=p,epoch_btjd=float(row['tce_time0bt']),
            duration_days=duration,depth_ppt=float(row['tce_depth'])/1000,stitch_snr=0,stitch_n_transits=0,
            n_units=len(runtime['raw_products']),**star)
        for name in ('survivors.csv','candidates.csv'):
            with (root/name).open('x',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=list(candidate));w.writeheader();w.writerow(candidate)
        F=legacy(root);import audit_p5 as A
        A.set_roots(root,REPO/'data/survey/audit_lc')
        if A.OUT!=root:raise IntegrityFailure('Autopsy audit output root differs')
        def products(requested):
            if int(requested)!=tic:raise IntegrityFailure('Unexpected autopsy host')
            data=[]
            for product in runtime['raw_products']:
                require_hash(REPO/product['raw_path'],product['raw_sha256'],'Autopsy raw array')
                with np.load(REPO/product['raw_path'],allow_pickle=False) as z:record={k:np.asarray(z[k]) for k in z.files}
                record.update(product['metadata']);data.append(record)
            return data
        A.load_products=products
        A.stellar_from_cache=lambda requested:dict(radius=star['radius_rsun'],mass=star['mass_msun'],teff=star['teff_k'],tmag=star['tmag'],ra=star['ra_deg'],dec=star['dec_deg']) if int(requested)==tic else {}
        prep=A.prepare_step(tic,p)
        events=A.events_step(tic,p,source='survey')
        from tesshunter.event_vet import classes_of
        removal=Counter(c for e in events['events'] if e.get('observed') for c in classes_of(e.get('exclusion_reasons') or []))
        search={}
        for preset,paths in runtime['search_paths'].items():
            trace=trace_census((REPO/paths['trace_path']).read_text(encoding='utf-8-sig').splitlines(),p)
            log=log_census((REPO/paths['log_path']).read_text(encoding='utf-8',errors='replace'),p)
            search[preset]=dict(trace=trace,log=log,accepted_associations=runtime['accepted_associations'][preset],
                budget_flags=runtime['budget_flags'][preset],accepted_candidates=runtime['accepted_candidates'][preset])
        image_path=ROOT/f'results/autopsies/{fid}.png';figure(image_path,runtime,noise,events)
        result=dict(status='COMPLETE',family_id=fid,tic_id=tic,expected_snr=runtime['expected_snr'],
            representative=row,primary_forced_fit=runtime['primary_forced_fit'],primary_epoch_rule=runtime['primary_epoch_rule'],
            first_termination='SEARCH_MATCHING',search=search,preparation=prep,event_summary=events['summary'],
            event_removal_counts=dict(removal),counterfactual_A_criteria=F.V.stagea_criteria(events['summary']['det_kept'],float(row['tce_depth'])/1000),
            frozen_native_preparation_counters=noise['prepare_counters'],rotation_proxy=noise['rotation_proxy'],
            figure_path=image_path.relative_to(REPO).as_posix(),diagnostic_root=root.relative_to(REPO).as_posix(),
            input_hashes=runtime['input_hashes'],interpretation='Nominal INDEPENDENT TCE-ephemeris event audit is counterfactual, especially when epoch is uncheckable. It is not an actual Stage A rejection. No search/TLS/Part F fit rerun or primary recovery change.')
    except IntegrityFailure as error:signal_integrity_failure(error,dict(phase='autopsies',family_id=fid));raise
    except Exception as error:
        result=dict(status='OPERATIONAL_UNKNOWN',family_id=fid,tic_id=tic,error=f'{type(error).__name__}: {error}',traceback=traceback.format_exc())
    result.update(started_utc=started,completed_utc=utc(),wall_seconds=time.perf_counter()-timer,runtime_sha256=expected)
    write(out,safe(result));print(fid,result['status'],flush=True)
    if result['status']!='COMPLETE':raise SystemExit(2)

if __name__=='__main__':
    try:main(sys.argv[1],sys.argv[2])
    except IntegrityFailure as error:signal_integrity_failure(error,dict(phase='autopsies',runtime=sys.argv[1]));raise
