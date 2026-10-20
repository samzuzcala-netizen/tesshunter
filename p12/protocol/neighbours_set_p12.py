"""One job per target set: the unchanged P8 neighbour acquisition (bulk SIMBAD, bulk VSX, then the per-star
Gaia cone and assembly) through ``neighbours_worker_p12`` with the set's own label and target list.

Used for the Part 4 negative sets, the E1 extension and any final-search star without a neighbour table
(5e ``final_neighbours``). Receipts: ``results/neighbour_receipts/<label>/{simbad,vsx,<tic>}.json`` and
``results/neighbour_sets/<label>.json``; tables ``DATA/neighbours/tic<id>.json``.
"""
from p12_common import REPO, ROOT, DATA, environment, read, write, sha, utc
import argparse
import csv
import json
import time


def run(label, targets):
    import neighbours_worker_p12 as worker
    started, timer = utc(), time.perf_counter()
    with (REPO / targets).open(newline='', encoding='utf-8-sig') as stream:
        tics = [int(r['tic_id']) for r in csv.DictReader(stream)]
    bulk, failures, stars = {}, [], []
    for kind in ('simbad', 'vsx'):
        bulk[kind] = worker.main(kind, targets, label)
    for tic in tics:
        existing = DATA / f'neighbours/tic{tic}.json'
        try:
            result = worker.main(str(tic), targets, label)
            stars.append(dict(tic_id=tic, ok=result['ok'], preexisting=existing.exists()))
        except (Exception, SystemExit) as exc:
            failures.append(dict(tic_id=tic, error=f'{type(exc).__name__}: {exc}'[:300]))
    receipt = dict(utc=utc(), started_utc=started, label=label, targets=targets, targets_sha256=sha(REPO / targets),
                   stars=len(tics), ok=sum(1 for s in stars if s['ok']), failures=failures,
                   bulk={k: dict(n_hosts=v['n_hosts'], n_with_objects=v['n_with_objects']) for k, v in bulk.items()},
                   wall_seconds=time.perf_counter() - timer, source_sha256=sha(__file__))
    write(ROOT / f'results/neighbour_sets/{label}.json', receipt, replace=(ROOT / f'results/neighbour_sets/{label}.json').exists())
    print(json.dumps(dict(label=label, stars=len(tics), ok=receipt['ok'], failures=len(failures))), flush=True)
    return 0 if not failures and receipt['ok'] == len(tics) else 2


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('label'); parser.add_argument('targets'); parser.add_argument('--online', action='store_true')
    args = parser.parse_args(argv)
    if not args.online:
        raise RuntimeError('Neighbour acquisition requires explicit --online')
    environment(offline=False)
    return run(args.label, args.targets)


if __name__ == '__main__':
    raise SystemExit(main())
