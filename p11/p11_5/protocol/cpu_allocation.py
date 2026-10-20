"""Apply the already verified 24-CPU allocation and explicit execution QoS."""
import ctypes,ctypes.wintypes as w
import psutil

CPUS=[0,2,4,6,8,10,12,14]+list(range(16,32))

class POWER(ctypes.Structure):
    _fields_=[('Version',w.ULONG),('ControlMask',w.ULONG),('StateMask',w.ULONG)]

def apply_current(cpus=None):
    process=psutil.Process()
    cpus=cpus if cpus is not None else CPUS if psutil.cpu_count()==32 else process.cpu_affinity()[:24]
    if len(cpus)>24:raise ValueError('CPU allocation exceeds the registered cap')
    process.cpu_affinity(cpus)
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.GetCurrentProcess.restype=w.HANDLE;handle=k.GetCurrentProcess()
    for name in ('GetProcessInformation','SetProcessInformation'):
        function=getattr(k,name);function.argtypes=[w.HANDLE,ctypes.c_int,w.LPVOID,w.DWORD];function.restype=w.BOOL
    before=POWER(1,0,0)
    if not k.GetProcessInformation(handle,4,ctypes.byref(before),ctypes.sizeof(before)):raise ctypes.WinError(ctypes.get_last_error())
    desired=POWER(1,before.ControlMask|1,before.StateMask&~1)
    if not k.SetProcessInformation(handle,4,ctypes.byref(desired),ctypes.sizeof(desired)):raise ctypes.WinError(ctypes.get_last_error())
    return dict(pid=process.pid,create_time=process.create_time(),affinity=cpus,
        previous_control=before.ControlMask,previous_state=before.StateMask,
        applied_control=desired.ControlMask,applied_state=desired.StateMask)
