"""Constrain the owner and its descendants to at most 24 logical CPUs."""
from common import *
environment()
import sys,subprocess,psutil

def main():
    if len(sys.argv)<3:raise ValueError('Use bounded_launch.py allocation_name controller.py [arguments]')
    process=psutil.Process();cpus=process.cpu_affinity()[:24]
    process.cpu_affinity(cpus)
    name=sys.argv[1];command=[sys.executable,*sys.argv[2:]]
    write(ROOT/f'manifests/allocation_{name}.json',dict(utc=utc(),logical_cpus=cpus,maximum_simultaneous_cpu_cores=len(cpus),
        launcher_pid=process.pid,launcher_create_time=process.create_time(),command=command,
        inheritance='Windows process affinity is inherited by the owner and all spawned workers. The launcher waits; the scientific owner records its own identity and intervals.',
        thread_environment={k:os.environ[k] for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS')}))
    result=subprocess.run(command,cwd=REPO,creationflags=subprocess.CREATE_NO_WINDOW)
    raise SystemExit(result.returncode)

if __name__=='__main__':main()
