"""Inspect or set Windows execution QoS for explicitly named P8 worker processes.

HighQoS opts a computation into normal performance scheduling; it does not raise
process priority, alter processor affinity, change the system power plan or restart work.
The caller must verify that each PID belongs to this run before using --apply.
See https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-setprocessinformation
"""
import argparse
import ctypes
from ctypes import wintypes
import json
import os

_configured = False


def configure_current_worker():
    """Ask Windows to schedule this compute worker for performance, once per process."""
    global _configured
    if _configured or os.name != "nt":
        return
    _configured = True
    try:
        result = process_qos(os.getpid(), apply=True)
        print(f"Windows compute-worker QoS: {json.dumps(result)}", flush=True)
    except OSError as exc:
        # Older Windows versions need not support this scheduling hint.
        print(f"Windows compute-worker QoS unavailable; keeping system scheduling: {exc}", flush=True)


class PowerThrottlingState(ctypes.Structure):
    _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]


def process_qos(pid, apply=False):
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    for name in ("GetProcessInformation", "SetProcessInformation"):
        fn = getattr(api, name)
        fn.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        fn.restype = wintypes.BOOL
    handle = api.OpenProcess(0x1000 | (0x0200 if apply else 0), False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        state = PowerThrottlingState(1, 0, 0)
        if not api.GetProcessInformation(handle, 4, ctypes.byref(state), ctypes.sizeof(state)):
            raise ctypes.WinError(ctypes.get_last_error())
        result = {"pid": pid, "before": {"control_mask": state.ControlMask, "state_mask": state.StateMask}}
        if apply:
            state.ControlMask |= 1  # PROCESS_POWER_THROTTLING_EXECUTION_SPEED
            state.StateMask &= ~1   # explicit HighQoS; retain the other mechanisms
            if not api.SetProcessInformation(handle, 4, ctypes.byref(state), ctypes.sizeof(state)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not api.GetProcessInformation(handle, 4, ctypes.byref(state), ctypes.sizeof(state)):
                raise ctypes.WinError(ctypes.get_last_error())
            result["after"] = {"control_mask": state.ControlMask, "state_mask": state.StateMask}
        return result
    finally:
        api.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pids", nargs="+", type=int)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Windows only")
    print(json.dumps([process_qos(pid, args.apply) for pid in args.pids], indent=1))


if __name__ == "__main__":
    main()
