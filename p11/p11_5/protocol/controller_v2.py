"""Bounded generic owner with durable interruption records and Windows I/O retry."""
from common import *
environment()
import argparse,subprocess,time,sys,shutil,traceback
import psutil
from record_io import write,resume

def run(manifest,workers,timeout):
    manifest=Path(manifest);jobs=read(manifest);phase=manifest.stem
    receipt=ROOT/'results/controllers'/phase;lock=ROOT/'manifests/controller_owner.json'
    if lock.exists():raise RuntimeError('Existing controller ownership requires review')
    receipt.mkdir(parents=True,exist_ok=False)
    owner=psutil.Process();started=time.time()
    identity=dict(pid=owner.pid,create_time=owner.create_time(),command=owner.cmdline(),
        manifest=str(manifest),manifest_sha256=sha(manifest))
    sources={'p11/p11_5/protocol/'+p for p in ('controller_v2.py','common.py','record_io.py','owned_worker.py','cpu_allocation.py')}
    for job in jobs:
        sources.update(job.get('source_paths',[]))
        if job['command'][0].endswith('.py'):sources.add(job['command'][0])
    hashes={p:sha(REPO/p) for p in sorted(sources)}
    write(receipt/'source_freeze.json',dict(utc=utc(),hashes=hashes))
    write(lock,identity);event('science_start',phase=phase,**identity)
    active={};done=[];queue=list(jobs);failure=None;failure_traceback=None;serial=0

    def kill_owned(slot):
        process=slot['process']
        if process.poll() is not None:return
        try:
            parent=psutil.Process(process.pid)
            if parent.create_time()!=slot['create_time']:raise RuntimeError('PID ownership changed before cleanup')
            for child in parent.children(recursive=True):
                try:child.kill()
                except psutil.NoSuchProcess:pass
            parent.kill()
        except psutil.NoSuchProcess:pass

    def seal(jid,slot,status,reason=None):
        finished=time.time();slot['log'].close()
        row=dict(job_id=jid,exit_code=slot['process'].poll(),status=status,reason=reason,
            started_unix=slot['start'],finished_unix=finished,wall_seconds=finished-slot['start'],
            measured_process_tree_cpu_seconds=slot['cpu'],peak_tree_rss_bytes=slot['peak'],
            command=slot['job']['command'],actual_command=slot['process'].args,
            pid=slot['process'].pid,create_time=slot['create_time'],sampling_access_failures=slot['sampling_access_failures'])
        write(receipt/(jid+'.json'),row);done.append(row)
        if status!='COMPLETE':event('case_operational_failure',phase=phase,job_id=jid,status=status,wall_seconds=row['wall_seconds'])

    try:
        while queue or active:
            events=[json.loads(s) for s in (ROOT/'manifests/events.jsonl').read_text().splitlines()]
            previous=sum(e.get('wall_seconds',0) for e in events if e['event']=='science_end')
            if .920809591111111+(previous+time.time()-started)/3600>=48:raise RuntimeError('Cumulative queue cap')
            if shutil.disk_usage(REPO).free<30000000000:raise RuntimeError('Disk headroom')
            while queue and len(active)<workers:
                if psutil.virtual_memory().available<2500000000 and active:break
                for path,expected in hashes.items():
                    if sha(REPO/path)!=expected:raise RuntimeError('Worker source changed: '+path)
                job=queue.pop(0);jid=job['job_id'];log=(receipt/(jid+'.log')).open('w',encoding='utf-8')
                command=[sys.executable,'p11/p11_5/protocol/owned_worker.py',*job['command']]
                child=subprocess.Popen(command,cwd=REPO,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                active[jid]=dict(process=child,job=job,log=log,start=time.time(),
                    create_time=psutil.Process(child.pid).create_time(),cpu=0.,peak=0,sampling_access_failures=0)
            for jid,slot in list(active.items()):
                child=slot['process'];now=time.time()
                try:
                    parent=psutil.Process(child.pid)
                    if parent.create_time()!=slot['create_time']:raise RuntimeError('PID ownership changed')
                    tree=[parent]+parent.children(recursive=True)
                    slot['cpu']=max(slot['cpu'],sum(sum(c.cpu_times()[:2]) for c in tree))
                    slot['peak']=max(slot['peak'],sum(c.memory_info().rss for c in tree))
                except psutil.NoSuchProcess:pass
                except psutil.AccessDenied:slot['sampling_access_failures']+=1
                timed_out=now-slot['start']>timeout
                if timed_out and child.poll() is None:kill_owned(slot)
                code=child.poll()
                if code is None:continue
                seal(jid,slot,'TIMEOUT' if timed_out else 'COMPLETE' if code==0 else 'INPUT_ERROR')
                del active[jid]
            serial+=1
            write(receipt/'progress.json',dict(completed=len(done),total=len(jobs),pending=len(queue),utc=utc(),
                elapsed_seconds=time.time()-started,workers=workers,
                active=[dict(job_id=jid,stage='C_v2' if s['job']['command'][0].endswith('c_v2_worker.py') else 'input',
                    pid=s['process'].pid,create_time=s['create_time'],elapsed_seconds=time.time()-s['start'],
                    cpu_seconds=s['cpu'],peak_rss=s['peak']) for jid,s in active.items()]),replace=True)
            if serial%60==0:resume(f'Active phase {phase}: {len(done)}/{len(jobs)} attempts complete, {len(active)} active, {len(queue)} pending. Owner PID {owner.pid}, created {owner.create_time()}. Fixed {timeout:g}-second deadline; at most {workers} single-thread workers. Original P10/P11 queues remain closed. No aggregate efficacy is read by this controller.')
            time.sleep(1)
    except BaseException as exc:
        failure=repr(exc);failure_traceback=traceback.format_exc();raise
    finally:
        for jid,slot in active.items():kill_owned(slot);seal(jid,slot,'INTERRUPTED',failure)
        write(receipt/'closed.json',dict(identity=identity,utc=utc(),wall_seconds=time.time()-started,
            completed=len(done),pending=queue,failures=[r for r in done if r['status']!='COMPLETE'],
            failure=failure,failure_traceback=failure_traceback,workers=workers,timeout_seconds=timeout,
            source_hashes_verified_at_end=all(sha(REPO/p)==h for p,h in hashes.items())))
        event('science_end',phase=phase,wall_seconds=time.time()-started,completed=len(done),total=len(jobs),**identity)
        if lock.exists() and read(lock)==identity:lock.unlink()
    print(phase,'closed',len(done),'/',len(jobs),'failed',sum(r['status']!='COMPLETE' for r in done),flush=True)
    if any(r['status']!='COMPLETE' for r in done):raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('manifest');parser.add_argument('--workers',type=int,default=1)
    parser.add_argument('--timeout',type=float,required=True);args=parser.parse_args()
    assert 1<=args.workers<=24;run(args.manifest,args.workers,args.timeout)
