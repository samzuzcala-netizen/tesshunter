"""Isolated, metered invocation of unchanged P8 bulk and per-star neighbours."""
from common import REPO,ROOT,DATA,environment,write,sha,utc
environment(offline=False)
import sys,time,socket
from acquisition_meter import install,accounting
install()
sys.path.insert(0,str(REPO/'scripts'))
import p8_neighbours as N
N.OUT=DATA;N.LC_ROOT=REPO/'data/survey/audit_lc';N.BULK=DATA/'neighbours_bulk'
N.TARGETS=ROOT/'manifests/targets_after_a.csv'


def main(kind):
    started=utc();timer=time.perf_counter();cpu=time.process_time()
    rows=N.load_targets(str(N.TARGETS));socket.setdefaulttimeout(300)
    if kind in ('simbad','vsx'):
        values=getattr(N,'bulk_'+kind)(rows)
        if {int(r['tic_id']) for r in rows}!=set(values):raise RuntimeError('Bulk neighbour target coverage mismatch')
        result=dict(kind=kind,ok=True,n_hosts=len(values),n_with_objects=sum(bool(v) for v in values.values()))
    else:
        tic=int(kind)
        # Require all bulk data before per-star assembly; prevent accidental individual SIMBAD/VSX queries.
        import json
        for category in ('simbad','vsx'):
            found=any(str(tic) in json.loads(p.read_text(encoding='utf-8')) for p in N.BULK.glob(category+'_*.json'))
            if not found:raise RuntimeError(f'Missing bulk {category} for TIC {tic}')
        result=N.one(tic,str(N.TARGETS),False)
    meter=accounting()
    result.update(started_utc=started,completed_utc=utc(),wall_seconds=time.perf_counter()-timer,
                  cpu_seconds=time.process_time()-cpu,source_sha256=sha(__file__),
                  legacy_source_sha256=sha(REPO/'scripts/p8_neighbours.py'),
                  measured_http_body_bytes=meter['workers'].get(str(__import__('os').getpid()),0))
    write(ROOT/f'results/neighbour_receipts/{kind}.json',result)
    print(kind,'COMPLETE' if result['ok'] else 'OPERATIONAL_UNKNOWN',flush=True)
    if not result['ok']:raise SystemExit(2)


if __name__=='__main__':main(sys.argv[1])
