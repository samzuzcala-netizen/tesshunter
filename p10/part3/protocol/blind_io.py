"""Durable Python open-event log and a fail-closed ephemeris sidecar guard."""
import json,os,sys,threading
from pathlib import Path


class SidecarAccessError(RuntimeError):pass


def install(log_path,protected_path):
    log_path=Path(log_path);log_path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(log_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    forbidden=os.path.normcase(os.path.abspath(protected_path))
    state={'opened':set(),'denied':[],'events':0,'fd':fd}
    local=threading.local()
    def audit(event,args):
        if event!='open' or getattr(local,'inside',False):return
        if not args or isinstance(args[0],int):return
        local.inside=True
        try:
            raw=os.fsdecode(args[0]);path=os.path.normcase(os.path.abspath(raw))
            denied=path==forbidden or Path(path).name.casefold()=='spoc_tce.ephemerides.csv'
            if path not in state['opened'] or denied:
                row={'path':path,'mode':str(args[1]) if len(args)>1 else None,'denied':denied}
                os.write(fd,(json.dumps(row)+'\n').encode());state['events']+=1;state['opened'].add(path)
            if denied:
                state['denied'].append(path);os.fsync(fd)
                raise SidecarAccessError('Ephemeris sidecar access forbidden in a blind worker')
        finally:local.inside=False
    sys.addaudithook(audit)
    return state


def summary(state):
    os.fsync(state['fd'])
    return dict(python_open_events=state['events'],unique_paths=len(state['opened']),
                sidecar_open_attempts=list(state['denied']),sidecar_opened=False,
                scope='CPython open audit events; includes standard Python/NumPy file reads, not an OS-wide kernel file trace')
