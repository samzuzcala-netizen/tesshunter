"""One-shot health/QoS check of the existing owner; never launches science.

Windows does not inherit the explicit execution-speed QoS setting into new
Python children here. Apply the documented setting to new owned processes at
supervised health checks, retaining the existing 24-CPU affinity and deadlines.
"""
from common import *
import ctypes,ctypes.wintypes as w,psutil,collections,shutil

class POWER(ctypes.Structure):
    _fields_=[('Version',w.ULONG),('ControlMask',w.ULONG),('StateMask',w.ULONG)]

def main():
    lock=ROOT/'manifests/controller_owner.json'
    if not lock.exists():print(json.dumps(dict(owner_closed=True)));return
    identity=read(lock);owner=psutil.Process(identity['pid'])
    if owner.create_time()!=identity['create_time'] or owner.cmdline()!=identity['command']:raise ValueError('Owner identity changed')
    cpus=owner.cpu_affinity()
    if len(cpus)>24:raise ValueError('Owner allocation exceeds cap')
    psutil.Process().cpu_affinity(cpus)
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
                    log=ROOT/'manifests/allocation_qos_events.jsonl'
                    with log.open('a',encoding='utf-8') as out:out.write(json.dumps(change)+'\n');out.flush();os.fsync(out.fileno())
                    changed.append(change)
                checked+=1
            finally:k.CloseHandle(handle)
        except psutil.NoSuchProcess:continue
    phase=identity.get('phase') or Path(identity['manifest']).stem
    progress=read(ROOT/f'results/controllers/{phase}/progress.json')
    now=dict(phase=phase,pid=owner.pid,create_time=owner.create_time(),
        elapsed_seconds=progress.get('elapsed_seconds',0),
        active_cpu={a['job_id']:a.get('cpu_seconds',0) for a in progress['active']})
    previous_path=ROOT/'work/health_previous.json'
    previous=read(previous_path) if previous_path.exists() else None
    cpu_progress=None
    if previous and all(previous.get(k)==now[k] for k in ('phase','pid','create_time')):
        common_jobs=set(previous['active_cpu'])&set(now['active_cpu'])
        cpu_progress=dict(wall_interval_seconds=now['elapsed_seconds']-previous['elapsed_seconds'],
            continuing_jobs=len(common_jobs),
            accumulated_cpu_seconds=sum(max(0,now['active_cpu'][j]-previous['active_cpu'][j]) for j in common_jobs),
            completed_job_tails_included=False)
    write(previous_path,now,replace=True)
    terminal=collections.Counter()
    for path in (ROOT/f'results/controllers/{phase}').glob('*.json'):
        attempt=read(path)
        if 'job_id' not in attempt or 'status' not in attempt:continue
        status=attempt['status'];command=attempt.get('command',[]);record=None
        if command and command[0].endswith('funnel_worker.py'):
            runtime=read(REPO/command[-1]);record=ROOT/f"results/funnel/{command[1]}/{runtime['candidate_id']}.json"
        elif command and command[0].endswith('c_v2_worker.py'):
            handoff=read(REPO/command[-1]);record=ROOT/f"results/funnel/C_v2/{handoff['candidate_id']}.json"
        if record is not None and record.exists():
            measured_status=read(record).get('status')
            if measured_status in ('INPUT_ERROR','TIMEOUT'):status=measured_status
        terminal[status]+=1
    print(json.dumps(dict(utc=utc(),phase=phase,completed=progress['completed'],pending=progress['pending'],
        active_stages=dict(collections.Counter(a.get('stage','input') for a in progress['active'])),
        terminal_operational_statuses=dict(terminal),
        continuing_job_cpu_progress=cpu_progress,
        elapsed_hours=progress.get('elapsed_seconds',0)/3600,owned_python_processes_checked=checked,new_QoS_corrections=len(changed),
        free_disk_GB=shutil.disk_usage(REPO).free/1e9,available_memory_GB=psutil.virtual_memory().available/1e9)))

if __name__=='__main__':main()
