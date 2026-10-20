"""Versioned bounded launcher with an explicit durable controller log."""
from common import *
environment()
import sys,subprocess
from cpu_allocation import apply_current

def main():
    if len(sys.argv)<3:raise ValueError('Use allocation_name controller.py [arguments]')
    receipt=apply_current();name=sys.argv[1];command=[sys.executable,*sys.argv[2:]]
    log=ROOT/f'results/controller_{name}_stdout.log'
    if log.exists():raise FileExistsError(log)
    write(ROOT/f'manifests/allocation_{name}.json',dict(utc=utc(),**receipt,command=command,
        maximum_simultaneous_cpu_cores=len(receipt['affinity']),
        inheritance='Affinity is inherited; the owned worker explicitly sets its own execution-speed QoS before running the unchanged payload.',
        stdout_log=log.relative_to(REPO).as_posix(),
        thread_environment={k:os.environ[k] for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS')}))
    with log.open('w',encoding='utf-8') as stream:
        result=subprocess.run(command,cwd=REPO,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    print('Controller launcher closed',name,'exit',result.returncode,'log',log,flush=True)
    raise SystemExit(result.returncode)

if __name__=='__main__':main()
