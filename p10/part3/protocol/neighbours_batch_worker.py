"""Amortize imports over a fixed identity batch, retaining every per-star receipt."""
from common import REPO,ROOT,read,write,sha,utc
import sys,time
import neighbours_worker as worker
worker.N.TARGETS=ROOT/'manifests/targets_neighbours.csv'
one=worker.main


def main(path):
    batch=read(path);start=time.perf_counter();failures=[]
    for tic in batch['tics']:
        try:one(str(tic))
        except (Exception,SystemExit) as exc:
            failures.append(dict(tic_id=tic,error=f'{type(exc).__name__}: {exc}'))
            print('neighbour input unknown',tic,type(exc).__name__,flush=True)
    result=dict(utc=utc(),batch_id=batch['batch_id'],stars=len(batch['tics']),failures=failures,
                wall_seconds=time.perf_counter()-start,source_sha256=sha(__file__))
    write(ROOT/f'results/neighbour_batches/{batch["batch_id"]}.json',result)
    if failures:raise SystemExit(2)


if __name__=='__main__':main(__import__('pathlib').Path(sys.argv[1]))
