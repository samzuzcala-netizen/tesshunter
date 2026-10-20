"""Blind prediction extraction and stage scheduling, without evaluator truth."""
from common import *
environment()
import sys,subprocess,re

def sources():
    paths=list((REPO/'src/tesshunter').glob('*.py'))
    paths += [REPO/'scripts'/x for x in ('audit_p5.py','revet_p6.py','p8_funnel.py')]
    paths += [ROOT/'protocol'/x for x in ('common.py','funnel_worker.py')]
    return {p.relative_to(REPO).as_posix():sha(p) for p in sorted(paths)}

def catalogues():
    found={}
    lines=subprocess.check_output(['rg','--files','data/survey','-g','tic*.json'],cwd=REPO,text=True).splitlines()
    for line in sorted(lines,key=lambda v:(0 if '/p10/' in v.replace('\\','/') else 1 if '/p8/' in v.replace('\\','/') else 2,len(v),v)):
        p=Path(line)
        if p.parent.name!='neighbours' or 'p11_5' in line:continue
        m=re.fullmatch(r'tic(\d+)',p.stem)
        if m and int(m[1]) not in found:found[int(m[1])]=p
    return found

def extract(series_ids):
    source=sources();catalog=catalogues();written=[]
    hosts={r['tic_id']:r for r in read(ROOT/'manifests/hosts.json')}
    for jid in series_ids:
        path=ROOT/f'results/search/{jid}.json';record=read(path);tid=record['tic_id'];star=read(ROOT/f'manifests/runtime_search/{jid}.json')['star']
        h=hosts[tid];n_units=len(h['selected_sectors'])
        star=dict(star,**{k:h['original'][k] for k in ('ra_deg','dec_deg','tic_gaia_id','pmra_mas_yr','pmdec_mas_yr') if h['original'].get(k) not in (None,'')})
        raw=DATA/'raw' if jid==f'tic{tid}' else DATA/f'injected_raw/{jid}'
        idx=raw/f'tic{tid}/index.json'
        if not idx.exists():raise RuntimeError('Missing injected raw handoff: '+jid)
        ordinary=record['R0']['result']['planets'];extra=record['R1_extras']
        all_candidates=[dict(q,tic_id=tid) for q in ordinary+extra]
        predictions=[]
        for kind,pool in [('O',ordinary),('X',extra)]:
            for number,q in enumerate(pool,1):
                cid=f'{jid}__{kind}{number:02d}'
                pre=bool(q.get('stitch_epoch_consistent') and float(q.get('stitch_snr') or 0)>=7.1 and int(q.get('stitch_n_transits') or 0)>=3)
                predictions.append(dict(candidate_id=cid,methods=['R0','R1'] if kind=='O' else ['R1'],
                    ephemeris={k:q[k] for k in ('period_days','epoch_btjd','duration_days','depth_ppt')},
                    candidate=q,passes_pregate=pre))
                if not pre:continue
                job=dict(q,period=q['period_days'],planet_num=q.get('planet_num',number),rank=number,n_units=n_units,tmag=star['tmag'])
                ref=catalog.get(tid)
                runtime=dict(candidate_id=cid,series_id=jid,tic_id=tid,candidate=job,all_candidates=all_candidates,
                    star=star,raw_root=raw.relative_to(REPO).as_posix(),raw_index_sha256=sha(idx),input_key=record['input_key'],source_hashes=source,
                    catalogue_reference=None if ref is None else dict(path=ref.as_posix(),sha256=sha(REPO/ref)))
                runtime['raw_hashes']={Path(p['file']).relative_to(REPO).as_posix():sha(p['file']) for p in read(idx)['products']}
                stellar=REPO/f'data/cache/tic/tic{tid}.json'
                runtime['stellar_reference']=dict(path=stellar.relative_to(REPO).as_posix(),sha256=sha(stellar)) if stellar.exists() else None
                runtime_path=ROOT/f'manifests/runtime_funnel/{cid}.json'
                if runtime_path.exists():
                    if read(runtime_path)!=runtime:raise ValueError('Runtime candidate changed')
                else:write(runtime_path,runtime)
                written.append(cid)
        destination=ROOT/f'results/predictions/{jid}.json'
        out=dict(series_id=jid,tic_id=tid,search_result_sha256=sha(path),input_key=record['input_key'],predictions=predictions,truth_opened=False)
        if destination.exists():
            if read(destination)!=out:raise ValueError('Prediction changed')
        else:write(destination,out)
    return written

def schedule(stage,series_ids,name,*,engineering=False):
    jobs=[]
    for jid in series_ids:
        predictions=read(ROOT/f'results/predictions/{jid}.json')['predictions']
        for p in predictions:
            if not p['passes_pregate']:continue
            cid=p['candidate_id'];eligible=True
            if stage!='A':
                prior=ROOT/f'results/funnel/A/{cid}.json'
                if not prior.exists():eligible=False
                else:
                    a=read(prior);eligible=a['status']=='COMPLETE' and (a['measurement'].get('decision')=='PASS' or engineering)
            if not eligible or (ROOT/f'results/funnel/{stage}/{cid}.json').exists():continue
            runtime=ROOT/f'manifests/runtime_funnel/{cid}.json'
            jobs.append(dict(job_id=stage+'_'+cid,command=['p11/p11_5/protocol/funnel_worker.py',stage,runtime.relative_to(REPO).as_posix()],
                             source_paths=list(read(runtime)['source_hashes'])))
    write(ROOT/f'manifests/{name}.json',jobs)
    return len(jobs)

if __name__=='__main__':
    action=sys.argv[1];series=read(ROOT/f'manifests/{sys.argv[2]}.json')
    ids=[r['job_id'] if isinstance(r,dict) else r for r in series]
    if action=='extract':print('runtime candidates written',len(extract(ids)))
    else:print('stage jobs',schedule(action,ids,sys.argv[3]))
