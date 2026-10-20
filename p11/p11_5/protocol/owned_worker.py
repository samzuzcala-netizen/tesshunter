"""Run an unchanged scientific payload after setting its own CPU/QoS state."""
from common import *
environment()
import sys,runpy,psutil
from cpu_allocation import apply_current

def main():
    identity=read(ROOT/'manifests/controller_owner.json');owner=psutil.Process(identity['pid'])
    if owner.create_time()!=identity['create_time'] or owner.cmdline()!=identity['command']:raise ValueError('Scientific owner identity changed')
    process=psutil.Process()
    if owner.pid not in {p.pid for p in process.parents()}:raise ValueError('Worker is not descended from the registered owner')
    receipt=apply_current(owner.cpu_affinity())
    receipt.update(utc=utc(),owner_pid=owner.pid,payload=sys.argv[1:])
    write(ROOT/f"manifests/worker_allocations/pid{process.pid}_{int(process.create_time()*1000)}.json",receipt)
    if len(sys.argv)<2:raise ValueError('Missing scientific payload')
    script=sys.argv[1];sys.argv=sys.argv[1:]
    runpy.run_path(script,run_name='__main__')

if __name__=='__main__':main()
