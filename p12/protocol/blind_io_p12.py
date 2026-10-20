"""Durable Python open-event log and fail-closed P12 truth guards."""
import atexit
import json,os,sys,threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / 'data/survey/p12'


def _canonical(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(os.fsdecode(path))))


def is_protected(path, protected_paths=()):
    path = _canonical(path)
    lowered = [part.casefold() for part in Path(path).parts]
    basename = Path(path).name.casefold()
    if 'ttt_downloads' in lowered:
        return True
    if basename == 'spoc_tce.ephemerides.csv':
        return True
    if basename.startswith('injections_') or basename in ('final_truth.csv', 'truth.csv', 'truth.json'):
        return True
    if any('ttt' in part or 'tess_ten_thousand' in part or 'tess-ten-thousand' in part
           for part in lowered) and Path(path).suffix.casefold() in ('.csv', '.fits', '.fit', '.ecsv', '.vot', '.xml', '.parquet', '.json', '.jsonl'):
        return True
    for root in [REPO / 'p9/truth', *protected_paths]:
        boundary = _canonical(root)
        if path == boundary or path.startswith(boundary + os.sep):
            return True
    for index in range(len(lowered) - 2):
        if lowered[index:index + 3] == ['data', 'survey', 'p12'] and 'truth' in lowered[index + 3:-1]:
            return True
    data = _canonical(DATA)
    if path.startswith(data + os.sep) and 'truth' in [part.casefold() for part in Path(os.path.relpath(path, data)).parts[:-1]]:
        return True
    if 'calibration' in path.casefold() and ('truth' in lowered or 'truth' in basename or basename.startswith('injections_')):
        return True
    return False


class SidecarAccessError(RuntimeError):pass


def install(log_path,protected_path=None,*,protected_paths=()):
    log_path=Path(log_path);log_path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(log_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    forbidden=tuple(protected_paths)+(() if protected_path is None else (protected_path,))
    state={'opened':set(),'denied':[],'events':0,'fd':fd}
    local=threading.local()
    def audit(event,args):
        if event!='open' or getattr(local,'inside',False):return
        if not args or isinstance(args[0],int):return
        local.inside=True
        try:
            path=_canonical(args[0])
            denied=is_protected(path,forbidden)
            if path not in state['opened'] or denied:
                row={'path':path,'mode':str(args[1]) if len(args)>1 else None,'denied':denied}
                os.write(fd,(json.dumps(row)+'\n').encode());state['events']+=1;state['opened'].add(path)
            if denied:
                state['denied'].append(path);os.fsync(fd)
                raise SidecarAccessError('Protected truth access forbidden in a blind worker')
        finally:local.inside=False
    sys.addaudithook(audit)
    def fatal_denial():
        if state['denied']:
            os.fsync(fd)
            os._exit(86)
    atexit.register(fatal_denial)
    return state


def summary(state):
    os.fsync(state['fd'])
    if state['denied']:
        raise SidecarAccessError('A denied truth read invalidated this worker')
    return dict(python_open_events=state['events'],unique_paths=len(state['opened']),
                sidecar_open_attempts=list(state['denied']),sidecar_opened=False,
                protected_open_attempts=list(state['denied']),protected_opened=False,
                scope='CPython open audit events; includes standard Python/NumPy file reads, not an OS-wide kernel file trace')
