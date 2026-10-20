"""P9 checkpoint/manifest operations. Sampling changes never read recovery truth."""
from common import *
import argparse, csv, shutil, time
import numpy as np
import pandas as pd

def pilot_timing():
    ids=read(P9/'manifests/pilot_ids.json');costs=[];c_costs=[];missing=[]
    for tic in ids:
        path=P9/'results/operations'/f'search_tic{tic}.json'
        if not path.exists():missing.append(str(path));continue
        t=read(path)['attempts'][-1]['wall_seconds']
        root=P9/'results/blind'/f'tic{tic}'
        for r in csv.DictReader((root/'survivors.csv').open(encoding='utf-8')):
            key=f'tic{tic}_P{float(r["period_days"]):.4f}'
            a=P9/'results/operations'/f'A_{key}.json'
            if not a.exists():missing.append(str(a));continue
            t+=read(a)['attempts'][-1]['wall_seconds']
            b=root/'stageB'/f'{key}.json'
            if b.exists() and read(b).get('decision')=='PASS':
                c=P9/'results/operations'/f'C_{key}.json'
                if c.exists():c_costs.append(dict(key=key,seconds=read(c)['attempts'][-1]['wall_seconds']))
                else:missing.append(str(c))
        costs.append(dict(tic_id=tic,search_plus_A_seconds=t))
    return dict(utc=utc(),hosts=costs,median_search_plus_A_seconds=float(np.median([c['search_plus_A_seconds'] for c in costs])),
      C_jobs=c_costs,missing=missing)

def freeze_final():
    timing=pilot_timing()
    if timing['missing']:raise RuntimeError('Pilot timing incomplete: '+str(timing['missing']))
    reduced=timing['median_search_plus_A_seconds']>1800 or any(c['seconds']>7200 for c in timing['C_jobs'])
    pr=pd.read_csv(P9/'truth/selection_priority.csv')
    quotas={'p8_proxy':1000,'small_long':3 if reduced else 6,'small_short':3 if reduced else 6,
      'other_radius':2 if reduced else 3,'EB_detached':4 if reduced else 6,'EB_contact':4 if reduced else 6,'uncertain':4}
    selected=pr[[r.priority<=quotas.get(r.stratum,0) for r in pr.itertuples()]].copy()
    blend=pd.read_csv(P9/'truth/blend_truth.csv')
    add=pd.DataFrame([dict(tic_id=int(r.tic_id),stratum='blend',priority=i+1,order_hash=r.order_hash,
      split='development' if int(__import__('hashlib').sha256(f'{SEED}:split:{int(r.tic_id)}'.encode()).hexdigest()[:8],16)%4==0 else 'holdout') for i,r in enumerate(blend.itertuples())])
    selected=pd.concat([selected,add],ignore_index=True)
    selected.to_csv(P9/'truth/final_selection.csv',index=False)
    ids=list(selected.tic_id.astype(int));write(P9/'manifests/final_ids.json',ids)
    write(P9/'protocol/final_sampling_lock.json',dict(utc=utc(),rule_reduced=reduced,quotas=quotas,n_hosts=len(ids),
      pilot_timing=timing,selection_sha256=sha(P9/'truth/final_selection.csv'),
      protocol_sha256=sha(P9/'protocol/PREREGISTRATION.md'),amendments_sha256=sha(P9/'protocol/AMENDMENTS.md'),
      code_sha256={p.name:sha(p) for p in P9.glob('*.py')}))
    print('frozen final hosts',len(ids),'reduced',reduced,'median search+A',timing['median_search_plus_A_seconds'],flush=True)

def archive_pilot():
    import psutil
    ids=read(P9/'manifests/pilot_ids.json')
    # Refuse to move a directory a native stage can still be reading/writing.
    active=[]
    for p in psutil.process_iter(['pid','cmdline']):
        cmd=' '.join(p.info.get('cmdline') or [])
        if 'runner.py' in cmd and (' stage ' in cmd or ' search ' in cmd):active.append(cmd)
    if active:raise RuntimeError('Active scientific workers: '+str(active))
    dest=P9/'results/timing_pilot';dest.mkdir(parents=True,exist_ok=True)
    for tic in ids:
        source=P9/'results/blind'/f'tic{tic}';target=dest/f'tic{tic}'
        assert source.resolve().is_relative_to((P9/'results').resolve()) and target.resolve().is_relative_to((P9/'results').resolve())
        if source.exists() and not target.exists():shutil.move(str(source),str(target))
    opdest=dest/'operations';opdest.mkdir(exist_ok=True)
    for p in (P9/'results/operations').glob('*.json'):
        if any(f'tic{tic}' in p.name for tic in ids):shutil.move(str(p),str(opdest/p.name))
    stellar={str(t):read(P9/'inputs/stellar'/f'tic{t}.json') for t in ids}
    write(dest/'stellar_snapshot.json',stellar)
    write(dest/'input_snapshot.json',{str(p.relative_to(P9)):sha(p) for t in ids for folder in ['raw','stellar','stellar_aux','neighbours']
      for p in ((P9/'inputs'/folder/f'tic{t}').glob('*') if folder=='raw' else [P9/'inputs'/folder/f'tic{t}.json']) if p.is_file()})
    write(dest/'manifest.json',dict(utc=utc(),role='timing pilot; primary requires search trace replay',
      sha256={str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file()}))
    print('pilot preserved',len(ids),'hosts',flush=True)

def reuse_pilot():
    """Reuse downstream measurements only after identical full blind signal lists."""
    old=P9/'results/timing_pilot';stars=read(old/'stellar_snapshot.json');out=[]
    for p,h in read(old/'input_snapshot.json').items():
        if sha(P9/p)!=h:raise RuntimeError('Pilot cache inputs changed: '+p)
    for tic in read(P9/'manifests/pilot_ids.json'):
        prev=old/f'tic{tic}';now=P9/'results/blind'/f'tic{tic}'
        oldsearch=prev/'search/results'/f'tic{tic}.json';newsearch=now/'search/results'/f'tic{tic}.json'
        if not newsearch.exists():continue
        a,b=read(oldsearch),read(newsearch)
        same=all(a.get('result',{}).get(k)==b.get('result',{}).get(k) for k in ['planets','vetting'])
        same=bool(same and read(P9/'inputs/stellar'/f'tic{tic}.json')==stars[str(tic)])
        rec=dict(tic_id=tic,validated_identical_candidate_and_vetting_lists=same,
          old_search_sha256=sha(oldsearch),new_search_sha256=sha(newsearch),copied={})
        if same:
            for folder in ['stageA','secondary','stageB','stageC','stageD','events','tls','prep','neighbours','fit','expensive','eb_screen']:
                if (prev/folder).exists():
                    shutil.copytree(prev/folder,now/folder,dirs_exist_ok=True)
                    for p in (now/folder).rglob('*'):
                        if p.is_file():rec['copied'][str(p.relative_to(now))]=sha(p)
            cp=prev/f'crossmatch_tic{tic}.json'
            if cp.exists():shutil.copy2(cp,now/cp.name)
            for p in (old/'operations').glob('*.json'):
                if f'tic{tic}_P' in p.name:
                    op=read(p);op['reuse_validation']=dict(old_search_sha256=sha(oldsearch),new_search_sha256=sha(newsearch))
                    write(P9/'results/operations'/p.name,op)
        out.append(rec)
    write(P9/'results/pilot_cache_reuse.json',out)
    print('validated downstream reuse',sum(r['validated_identical_candidate_and_vetting_lists'] for r in out),'of',len(out),flush=True)

def lock_settled():
    ids=read(P9/'manifests/final_ids.json');locked=[];pending={}
    def settled_operation(token):
        path=P9/'results/operations'/f'{token}.json'
        if not path.exists():return False
        record=read(path)
        return record.get('status')=='complete' or (record.get('status') in ('error','timeout') and len(record.get('attempts',[]))>=2)
    for tic in ids:
        root=P9/'results/blind'/f'tic{tic}';why=[]
        sr=root/'search/results'/f'tic{tic}.json'
        op=P9/'results/operations'/f'search_tic{tic}.json'
        if not settled_operation(f'search_tic{tic}'):why.append('search operation not settled')
        if not sr.exists() and not settled_operation(f'search_tic{tic}'):why.append('search absent')
        elif sr.exists() and read(sr).get('status')=='ok' and op.exists() and read(op).get('status')=='complete':
            for r in csv.DictReader((root/'survivors.csv').open(encoding='utf-8')):
                key=f'tic{tic}_P{float(r["period_days"]):.4f}'
                for folder,field,allowed in [('stageA','decision',{'PASS'}),('secondary','gate',{'PASS','HOLD'}),
                  ('stageB','decision',{'PASS'}),('stageC','decision',{'PASS'})]:
                    p=root/folder/f'{key}.json'
                    stage={'stageA':'A','secondary':'S','stageB':'B','stageC':'C'}[folder]
                    if not settled_operation(f'{stage}_{key}'):
                        why.append('operation:'+stage+':'+key);break
                    if not p.exists():break  # Exhausted operational failure is settled, not scientific rejection.
                    if read(p).get(field) not in allowed:break
                else:
                    if not settled_operation(f'D_{key}'):why.append('operation:D:'+key)
                    if not (root/'final'/f'{key}.json').exists():why.append('final:'+key)
        if why:pending[str(tic)]=why;continue
        lp=P9/'results/locks'/f'tic{tic}.json'
        hashes={str(p.relative_to(P9)):sha(p) for p in root.rglob('*') if p.is_file()}
        if lp.exists():
            if read(lp)['sha256']!=hashes:raise RuntimeError('Previously locked output changed '+str(tic))
        else:write(lp,dict(utc=utc(),tic_id=tic,sha256=hashes,manual_blinding='unblinded investigating session',external_submission=False))
        locked.append(tic)
    write(P9/'results/lock_status.json',dict(utc=utc(),locked=locked,pending=pending))
    print('locked',len(locked),'pending',len(pending),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('cmd',choices=['timing','freeze','archive','reuse','lock']);a=p.parse_args()
    if a.cmd=='timing':print(pilot_timing())
    elif a.cmd=='freeze':freeze_final()
    elif a.cmd=='archive':archive_pilot()
    elif a.cmd=='reuse':reuse_pilot()
    else:lock_settled()
