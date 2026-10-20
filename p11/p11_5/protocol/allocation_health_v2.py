"""Incremental one-shot owner health checks; no scientific work is launched."""
from common import *
environment()
import collections, ctypes, ctypes.wintypes as w, psutil, shutil, time
from datetime import datetime
from allocation_health import POWER
from cpu_allocation import apply_current
from record_io import write


def stat_key(path):
    if path is None:return None
    try:
        s=Path(path).stat();return [s.st_size,s.st_mtime_ns]
    except FileNotFoundError:return None


def terminal_snapshot(folder,previous):
    entries={};hits=misses=0
    for path in Path(folder).glob('*.json'):
        if path.name in ('progress.json','source_freeze.json','closed.json'):continue
        stamp=stat_key(path);old=previous.get(path.name)
        if old and old['receipt_stat']==stamp and stat_key(old.get('measurement_path'))==old.get('measurement_stat'):
            entries[path.name]=old;hits+=1;continue
        misses+=1;r=read(path)
        item=dict(receipt_stat=stamp,measurement_path=None,measurement_stat=None)
        if 'job_id' in r and 'status' in r:
            status=r['status'];command=r.get('command',[]);measurement=None
            if command and command[0].endswith('funnel_worker.py'):
                runtime=read(REPO/command[-1]);measurement=ROOT/f"results/funnel/{command[1]}/{runtime['candidate_id']}.json"
            elif command and command[0].endswith('c_v2_worker.py'):
                handoff=read(REPO/command[-1]);measurement=ROOT/f"results/funnel/C_v2/{handoff['candidate_id']}.json"
            if measurement is not None:
                item['measurement_path']=str(measurement)
                before=stat_key(measurement)
                if before is not None:
                    measured=read(measurement).get('status')
                    if measured in ('INPUT_ERROR','TIMEOUT'):status=measured
                    if before!=stat_key(measurement):raise RuntimeError('Operational measurement changed while reading')
                item['measurement_stat']=before
            item.update(job_id=r['job_id'],status=status)
        if stamp!=stat_key(path):raise RuntimeError('Attempt receipt changed while reading')
        entries[path.name]=item
    counts=collections.Counter(v['status'] for v in entries.values() if 'status' in v)
    return dict(entries=entries,counts=dict(counts),cache_hits=hits,cache_misses=misses)


def main():
    start=time.perf_counter();lock=ROOT/'manifests/controller_owner.json'
    if not lock.exists():print(json.dumps(dict(owner_closed=True)));return
    identity=read(lock);owner=psutil.Process(identity['pid'])
    if owner.create_time()!=identity['create_time'] or owner.cmdline()!=identity['command']:raise ValueError('Owner identity changed')
    cpus=owner.cpu_affinity()
    if len(cpus)>24:raise ValueError('Owner allocation exceeds cap')
    allocation=apply_current(cpus)
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
    for name in ('GetProcessInformation','SetProcessInformation'):
        function=getattr(k,name);function.argtypes=[w.HANDLE,ctypes.c_int,w.LPVOID,w.DWORD];function.restype=w.BOOL
    k.CloseHandle.argtypes=[w.HANDLE]
    changed=[];checked=0
    for process in [owner]+owner.children(recursive=True):
        try:
            if 'python' not in process.name().lower():continue
            if set(process.cpu_affinity())-set(cpus):raise ValueError('Child affinity outside owner allocation')
            handle=k.OpenProcess(0x1200,False,process.pid)
            if not handle:raise ctypes.WinError(ctypes.get_last_error())
            try:
                before=POWER(1,0,0)
                if not k.GetProcessInformation(handle,4,ctypes.byref(before),ctypes.sizeof(before)):raise ctypes.WinError(ctypes.get_last_error())
                if not before.ControlMask&1 or before.StateMask&1:
                    desired=POWER(1,before.ControlMask|1,before.StateMask&~1)
                    if not k.SetProcessInformation(handle,4,ctypes.byref(desired),ctypes.sizeof(desired)):raise ctypes.WinError(ctypes.get_last_error())
                    change=dict(utc=utc(),pid=process.pid,create_time=process.create_time(),owner_pid=owner.pid,
                        before_control=before.ControlMask,before_state=before.StateMask,after_control=desired.ControlMask,
                        after_state=desired.StateMask,affinity=process.cpu_affinity(),scientific_source_changed=False)
                    with (ROOT/'manifests/allocation_qos_events.jsonl').open('a',encoding='utf-8') as out:
                        out.write(json.dumps(change)+'\n');out.flush();os.fsync(out.fileno())
                    changed.append(change)
                checked+=1
            finally:k.CloseHandle(handle)
        except psutil.NoSuchProcess:continue
    phase=identity.get('phase') or Path(identity['manifest']).stem
    cache_path=ROOT/'work/terminal_health_cache_v2.json'
    cache_identity=dict(owner=identity,monitor_source_sha256=sha(Path(__file__)))
    cache=read(cache_path) if cache_path.exists() else {}
    old=cache.get('entries',{}) if cache.get('identity')==cache_identity else {}
    terminal=terminal_snapshot(ROOT/f'results/controllers/{phase}',old)
    write(cache_path,dict(identity=cache_identity,entries=terminal['entries']),replace=True)
    # Fetch progress after the historical-status scan so the live snapshot is fresh.
    progress=read(ROOT/f'results/controllers/{phase}/progress.json')
    now=dict(phase=phase,pid=owner.pid,create_time=owner.create_time(),elapsed_seconds=progress.get('elapsed_seconds',0),
        active_cpu={a['job_id']:a.get('cpu_seconds',0) for a in progress['active']})
    previous_path=ROOT/'work/health_previous.json';previous=read(previous_path) if previous_path.exists() else None
    cpu_progress=None
    if previous and all(previous.get(key)==now[key] for key in ('phase','pid','create_time')):
        common_jobs=set(previous['active_cpu'])&set(now['active_cpu'])
        cpu_progress=dict(wall_interval_seconds=now['elapsed_seconds']-previous['elapsed_seconds'],continuing_jobs=len(common_jobs),
            accumulated_cpu_seconds=sum(max(0,now['active_cpu'][j]-previous['active_cpu'][j]) for j in common_jobs),completed_job_tails_included=False)
    write(previous_path,now,replace=True)
    print(json.dumps(dict(utc=utc(),phase=phase,completed=progress['completed'],pending=progress['pending'],
        active_stages=dict(collections.Counter(a.get('stage','input') for a in progress['active'])),
        terminal_operational_statuses=terminal['counts'],continuing_job_cpu_progress=cpu_progress,
        elapsed_hours=progress.get('elapsed_seconds',0)/3600,owned_python_processes_checked=checked,new_QoS_corrections=len(changed),
        free_disk_GB=shutil.disk_usage(REPO).free/1e9,available_memory_GB=psutil.virtual_memory().available/1e9,
        monitoring_seconds=time.perf_counter()-start,terminal_cache_hits=terminal['cache_hits'],terminal_cache_misses=terminal['cache_misses'],
        progress_age_seconds=max(0,time.time()-datetime.fromisoformat(progress['utc']).timestamp()),monitor_allocation=allocation)))


if __name__=='__main__':main()
