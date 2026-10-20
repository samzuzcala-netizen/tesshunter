"""Isolated invocation of unchanged P8 neighbours, with P12-only destinations.

Superseded 2026-09-23 (AMENDMENTS_P12.md): ``--targets`` and ``--label`` name the target set, so every
set (core, TTT negatives, TTT-adjacent negatives, E1) has its own bulk SIMBAD / VSX chunk cache
(``DATA/neighbours_bulk/<label>/``; the P8 chunk files are named by offset and would otherwise be
reused across sets) and its own receipt folder; per-star tables stay ``DATA/neighbours/tic<id>.json``.
The default (core, no label) keeps the original paths.
"""
from p12_common import REPO,ROOT,DATA,environment,write,sha,utc,redirect_audit_cache
import sys,time,socket
N=None
CORE='manifests/targets_p12_core.csv'  # under ROOT, resolved at call time


def _worker_module(targets=None,label=None):
    global N
    if N is None:
        sys.path.insert(0,str(REPO/'scripts'))
        import audit_p5 as A
        redirect_audit_cache(A)
        import p8_neighbours
        N=p8_neighbours
    N.OUT=DATA;N.LC_ROOT=REPO/'data/survey/audit_lc'
    N.BULK=DATA/'neighbours_bulk' if not label else DATA/'neighbours_bulk'/label
    N.TARGETS=ROOT/CORE if targets is None else REPO/targets
    return N


def main(kind,targets=None,label=None):
    started=utc();timer=time.perf_counter();cpu=time.process_time();module=_worker_module(targets,label)
    rows=module.load_targets(str(module.TARGETS));socket.setdefaulttimeout(300)
    if kind in ('simbad','vsx'):
        values=getattr(module,'bulk_'+kind)(rows)
        if {int(r['tic_id']) for r in rows}!=set(values):raise RuntimeError('Bulk neighbour target coverage mismatch')
        result=dict(kind=kind,ok=True,n_hosts=len(values),n_with_objects=sum(bool(v) for v in values.values()))
    else:
        tic=int(kind)
        import json
        for category in ('simbad','vsx'):
            present=any(str(tic) in json.loads(p.read_text(encoding='utf-8')) for p in module.BULK.glob(category+'_*.json'))
            if not present:raise RuntimeError(f'Missing bulk {category} for requested TIC')
        result=module.one(tic,str(module.TARGETS),False)
    result.update(started_utc=started,completed_utc=utc(),wall_seconds=time.perf_counter()-timer,label=label,
        targets=str(module.TARGETS.relative_to(REPO).as_posix()),
        cpu_seconds=time.process_time()-cpu,source_sha256=sha(__file__),legacy_source_sha256=sha(REPO/'scripts/p8_neighbours.py'))
    write(ROOT/('results/neighbour_receipts/'+(f'{label}/' if label else '')+f'{kind}.json'),result)
    if not result['ok']:raise SystemExit(2)
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('kind');parser.add_argument('--online',action='store_true')
    parser.add_argument('--targets');parser.add_argument('--label');args=parser.parse_args()
    if not args.online:raise RuntimeError('Neighbour acquisition requires explicit --online')
    environment(offline=False);main(args.kind,args.targets,args.label)
