"""One source-sealed owner for blind per-series search -> candidate A/S/B/C jobs.

Readiness uses measured pipeline statuses only, never injection truth. Completed
work is reused by immutable identity, with its original deployable cost intact.
"""
from common import *
environment()
import argparse,sys,subprocess,time,shutil
import psutil
from candidates import extract,sources

DEADLINES={'search':3600,'A':1200,'S':300,'B':300,'C':600}

def run(name,series_path,candidate_path,workers,stages):
    start=time.time();owner=psutil.Process();lock=ROOT/'manifests/controller_owner.json'
    if lock.exists():raise RuntimeError('Existing scientific owner requires review')
    root=ROOT/f'results/controllers/{name}';root.mkdir(parents=True,exist_ok=False)
    immutable=sources()
    for p in ('candidates.py','flow_controller.py','search_worker.py'):
        immutable['p11/p11_5/protocol/'+p]=sha(ROOT/'protocol'/p)
    write(root/'source_freeze.json',dict(utc=utc(),hashes=immutable))
    identity=dict(pid=owner.pid,create_time=owner.create_time(),command=owner.cmdline(),phase=name)
    write(lock,identity);event('science_start',**identity)
    queue=[];known=set();active={};completed=[];reused=[];serial=0

    def enqueue(stage,key,command):
        tag=stage+'_'+key
        if tag not in known:
            known.add(tag);queue.append(dict(job_id=tag,stage=stage,key=key,command=command))

    def candidate(stage,cid):
        if stage not in stages:return
        path=ROOT/f'results/funnel/{stage}/{cid}.json'
        if path.exists():
            reused.append(dict(stage=stage,candidate_id=cid,result_sha256=sha(path)));advance(stage,cid);return
        enqueue(stage,cid,['p11/p11_5/protocol/funnel_worker.py',stage,f'p11/p11_5/manifests/runtime_funnel/{cid}.json'])

    def advance(stage,key):
        if stage=='search':
            path=ROOT/f'results/search/{key}.json'
            if not path.exists():return
            ids=extract([key])
            for cid in ids:candidate('A',cid)
            return
        path=ROOT/f'results/funnel/{stage}/{key}.json'
        if not path.exists():return
        record=read(path);runtime=read(ROOT/f'manifests/runtime_funnel/{key}.json')
        measured=record.get('measurement',{})
        if stage=='A':
            if record['status']=='COMPLETE' and (measured.get('decision')=='PASS' or runtime.get('engineering_label') and measured.get('chosen_ephemeris')):
                candidate('S',key)
        elif stage=='S':candidate('B',key)
        elif stage=='B':candidate('C',key)

    def charge_prior():
        events=[json.loads(s) for s in (ROOT/'manifests/events.jsonl').read_text().splitlines()]
        return .920809591111111+sum(e.get('wall_seconds',0) for e in events if e['event']=='science_end')/3600

    def acquired():
        count=81827574+sum(read(p).get('bytes',0) for p in (ROOT/'results/acquisition').glob('*.json'))
        for path in (ROOT/'results/network').glob('*.jsonl'):
            lines=path.read_text().splitlines()
            if lines:
                try:count+=json.loads(lines[-1])['cumulative_response_body_bytes']
                except json.JSONDecodeError:
                    if len(lines)>1:count+=json.loads(lines[-2])['cumulative_response_body_bytes']
        return count

    def seal_case(jid,slot,status,code,reason=None):
        now=time.time();row=dict(job_id=jid,stage=slot['job']['stage'],key=slot['job']['key'],status=status,exit_code=code,
            reason=reason,started_unix=slot['start'],finished_unix=now,wall_seconds=now-slot['start'],
            measured_process_tree_cpu_seconds=slot['cpu'],peak_tree_rss_bytes=slot['peak'],
            command=slot['job']['command'],pid=slot['process'].pid,create_time=slot['create_time'])
        write(root/(jid+'.json'),row);completed.append(row)
        if status in ('TIMEOUT','INPUT_ERROR','INTERRUPTED'):
            event('case_operational_failure',phase=name,job_id=jid,status=status,wall_seconds=row['wall_seconds'])
        return row

    failure=None
    try:
        if series_path:
            series=read(series_path)
            for item in series:
                jid=item['job_id'] if isinstance(item,dict) else item
                path=ROOT/f'results/search/{jid}.json'
                if path.exists():
                    reused.append(dict(stage='search',series_id=jid,result_sha256=sha(path)));advance('search',jid)
                else:enqueue('search',jid,['p11/p11_5/protocol/search_worker.py',f'p11/p11_5/manifests/runtime_search/{jid}.json'])
        if candidate_path:
            for item in read(candidate_path):
                runtime=read(REPO/item['command'][-1]);candidate('A',runtime['candidate_id'])
        while queue or active:
            if charge_prior()+(time.time()-start)/3600>=48:raise RuntimeError('Cumulative 48-hour cap')
            if shutil.disk_usage(REPO).free<30000000000:raise RuntimeError('Disk headroom')
            if acquired()>15000000000:raise RuntimeError('Acquisition cap')
            while queue and len(active)<workers:
                if psutil.virtual_memory().available<2500000000 and active:break
                for path,expected in immutable.items():
                    if sha(REPO/path)!=expected:raise RuntimeError('Loaded source changed: '+path)
                job=queue.pop(0);jid=job['job_id'];log=(root/(jid+'.log')).open('w',encoding='utf-8')
                child=subprocess.Popen([sys.executable,*job['command']],cwd=REPO,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                active[jid]=dict(job=job,process=child,log=log,start=time.time(),create_time=psutil.Process(child.pid).create_time(),cpu=0.,peak=0)
            for jid,slot in list(active.items()):
                p=slot['process'];now=time.time()
                try:
                    proc=psutil.Process(p.pid)
                    if proc.create_time()!=slot['create_time']:raise RuntimeError('PID identity changed')
                    tree=[proc]+proc.children(recursive=True)
                    slot['cpu']=max(slot['cpu'],sum(sum(c.cpu_times()[:2]) for c in tree))
                    slot['peak']=max(slot['peak'],sum(c.memory_info().rss for c in tree))
                except psutil.NoSuchProcess:pass
                timed_out=now-slot['start']>DEADLINES[slot['job']['stage']]
                if timed_out and p.poll() is None:
                    proc=psutil.Process(p.pid);assert proc.create_time()==slot['create_time']
                    for child in proc.children(recursive=True):child.kill()
                    proc.kill()
                code=p.poll()
                if code is None:continue
                slot['log'].close()
                seal_case(jid,slot,'TIMEOUT' if timed_out else 'COMPLETE' if code==0 else 'INPUT_ERROR',code)
                del active[jid];advance(slot['job']['stage'],slot['job']['key'])
            serial+=1
            write(root/'progress.json',dict(utc=utc(),completed=len(completed),pending=len(queue),reused=len(reused),
                active=[dict(job_id=jid,stage=s['job']['stage'],pid=s['process'].pid,create_time=s['create_time'],elapsed_seconds=time.time()-s['start'],
                             cpu_seconds=s['cpu'],peak_rss=s['peak']) for jid,s in active.items()],
                elapsed_seconds=time.time()-start,workers=workers),replace=True)
            if serial%60==0:
                resume(f'Active phase {name}: {len(completed)} new cases complete, {len(active)} active, {len(queue)} pending, {len(reused)} immutable prior results reused. Current owner PID {owner.pid}, created {owner.create_time()}. Stage deadlines: {DEADLINES}. No aggregate efficacy in controller. Original P10/P11 queues remain closed. Scientific charged hours including prior/current: {charge_prior()+(time.time()-start)/3600:.4f}.')
            time.sleep(1)
    except BaseException as exc:
        failure=repr(exc);raise
    finally:
        for jid,slot in active.items():
            p=slot['process']
            if p.poll() is None:
                proc=psutil.Process(p.pid)
                if proc.create_time()==slot['create_time']:
                    for child in proc.children(recursive=True):child.kill()
                    proc.kill()
            slot['log'].close();seal_case(jid,slot,'INTERRUPTED',p.poll(),failure)
        write(root/'closed.json',dict(utc=utc(),identity=identity,completed=len(completed),pending=queue,
            reused=reused,failures=[r for r in completed if r['status']!='COMPLETE'],failure=failure,wall_seconds=time.time()-start,
            source_hashes_verified_at_end=all(sha(REPO/p)==h for p,h in immutable.items())))
        event('science_end',wall_seconds=time.time()-start,completed=len(completed),**identity)
        if lock.exists() and read(lock)==identity:lock.unlink()
    print('flow closed',name,len(completed),'failures',sum(r['status']!='COMPLETE' for r in completed),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--series');p.add_argument('--candidates');p.add_argument('--workers',type=int,default=1);p.add_argument('--stages',default='ASBC')
    a=p.parse_args();assert 1<=a.workers<=24;run(a.name,a.series,a.candidates,a.workers,a.stages)
