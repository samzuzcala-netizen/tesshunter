"""Single durable owner of bounded, source-sealed subprocess science phases."""
from common import *
environment()
import argparse
import subprocess
import time
import sys
import shutil
import psutil

def run(manifest,workers,timeout):
    manifest=Path(manifest);jobs=read(manifest)
    phase=manifest.stem;receipt=ROOT/'results/controllers'/phase
    receipt.mkdir(parents=True,exist_ok=False)
    lock=ROOT/'manifests/controller_owner.json'
    if lock.exists():raise RuntimeError('Existing controller ownership requires review')
    owner=psutil.Process();started=time.time()
    identity=dict(pid=owner.pid,create_time=owner.create_time(),command=owner.cmdline(),manifest=str(manifest),manifest_sha256=sha(manifest))
    sources=set()
    for job in jobs:
        sources.update(job.get('source_paths',[]))
        if job['command'][0].endswith('.py'):sources.add(job['command'][0])
    source_hashes={p:sha(REPO/p) for p in sorted(sources)}
    write(receipt/'source_freeze.json',dict(utc=utc(),hashes=source_hashes))
    write(lock,identity)
    event('science_start',phase=phase,**identity)
    active={};done=[];queue=list(jobs)
    try:
        while queue or active:
            # Current phase is bounded against the cumulative cap, counting prior
            # phase intervals even when their worker results were errors.
            events=[json.loads(s) for s in (ROOT/'manifests/events.jsonl').read_text().splitlines()]
            previous=sum(e.get('wall_seconds',0) for e in events if e['event']=='science_end')
            if .920809591111111+(previous+time.time()-started)/3600>=48:raise RuntimeError('Cumulative queue cap')
            if shutil.disk_usage(REPO).free<30000000000:raise RuntimeError('Disk headroom')
            while queue and len(active)<workers:
                for path,expected in source_hashes.items():
                    if sha(REPO/path)!=expected:raise RuntimeError('Worker source changed: '+path)
                job=queue.pop(0);jid=job['job_id'];log=(receipt/(jid+'.log')).open('w',encoding='utf-8')
                command=[sys.executable,*job['command']]
                child=subprocess.Popen(command,cwd=REPO,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                active[jid]=dict(process=child,job=job,log=log,start=time.time(),create_time=psutil.Process(child.pid).create_time(),cpu=0.,peak=0)
            for jid,slot in list(active.items()):
                p=slot['process'];now=time.time()
                try:
                    proc=psutil.Process(p.pid)
                    if proc.create_time()!=slot['create_time']:raise RuntimeError('PID ownership changed')
                    tree=[proc]+proc.children(recursive=True)
                    slot['cpu']=max(slot['cpu'],sum(sum(c.cpu_times()[:2]) for c in tree))
                    slot['peak']=max(slot['peak'],sum(c.memory_info().rss for c in tree))
                except psutil.NoSuchProcess:pass
                timed_out=now-slot['start']>timeout
                if timed_out and p.poll() is None:
                    proc=psutil.Process(p.pid)
                    assert proc.create_time()==slot['create_time']
                    for child in proc.children(recursive=True):child.kill()
                    proc.kill()
                code=p.poll()
                if code is None:continue
                slot['log'].close()
                row=dict(job_id=jid,exit_code=code,status='TIMEOUT' if timed_out else 'COMPLETE' if code==0 else 'INPUT_ERROR',
                    started_unix=slot['start'],finished_unix=now,wall_seconds=now-slot['start'],
                    measured_process_tree_cpu_seconds=slot['cpu'],peak_tree_rss_bytes=slot['peak'],command=slot['job']['command'],
                    pid=p.pid,create_time=slot['create_time'])
                write(receipt/(jid+'.json'),row);done.append(row);del active[jid]
            write(receipt/'progress.json',dict(completed=len(done),total=len(jobs),active=[dict(job_id=k,pid=v['process'].pid,
                create_time=v['create_time'],elapsed_seconds=time.time()-v['start'],cpu_seconds=v['cpu'],peak_rss=v['peak']) for k,v in active.items()],
                pending=len(queue),utc=utc()),replace=True)
            time.sleep(1)
        write(receipt/'closed.json',dict(identity=identity,utc=utc(),wall_seconds=time.time()-started,completed=len(done),
            failures=[r for r in done if r['status']!='COMPLETE'],workers=workers,timeout_seconds=timeout))
    finally:
        for slot in active.values():
            p=slot['process']
            if p.poll() is None:
                proc=psutil.Process(p.pid)
                if proc.create_time()==slot['create_time']:
                    for child in proc.children(recursive=True):child.kill()
                    proc.kill()
            slot['log'].close()
        event('science_end',phase=phase,wall_seconds=time.time()-started,completed=len(done),total=len(jobs),**identity)
        if lock.exists() and read(lock)==identity:lock.unlink()
    print(phase,'closed',len(done),'/',len(jobs),'failed',sum(r['status']!='COMPLETE' for r in done),flush=True)
    if any(r['status']!='COMPLETE' for r in done):raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('--workers',type=int,default=1);p.add_argument('--timeout',type=float,required=True)
    a=p.parse_args();assert 1<=a.workers<=24;run(a.manifest,a.workers,a.timeout)
