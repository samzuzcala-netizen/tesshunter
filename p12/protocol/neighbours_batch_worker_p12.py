"""P10.3 neighbour batch loop retaining every per-star P12 receipt (superseded 2026-09-23: the batch
file may name ``targets`` and ``label``, passed to the worker; AMENDMENTS_P12.md)."""
from p12_common import REPO,ROOT,read,write,sha,utc,environment
import sys,time
import neighbours_worker_p12 as worker


def main(path):
    batch=read(path);start=time.perf_counter();failures=[]
    for tic in batch['tics']:
        try:worker.main(str(tic),*((batch.get('targets'),batch.get('label')) if batch.get('targets') or batch.get('label') else ()))
        except (Exception,SystemExit) as exc:
            failures.append(dict(tic_id=tic,error=f'{type(exc).__name__}: {exc}'))
    result=dict(utc=utc(),batch_id=batch['batch_id'],stars=len(batch['tics']),failures=failures,label=batch.get('label'),
        wall_seconds=time.perf_counter()-start,source_sha256=sha(__file__))
    write(ROOT/f'results/neighbour_batches/{batch["batch_id"]}.json',result)
    if failures:raise SystemExit(2)
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('path');parser.add_argument('--online',action='store_true');args=parser.parse_args()
    if not args.online:raise RuntimeError('Neighbour acquisition requires explicit --online')
    environment(offline=False);main(args.path)
