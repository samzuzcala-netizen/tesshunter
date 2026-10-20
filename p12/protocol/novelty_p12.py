"""Part 5f: the novelty re-check (``final_novelty``, one controller job, TOI and CTOI only, 600 s per source).

Each source is fetched by ``catalog_snapshot_p12.py --source`` in its own bounded process into
``data/survey/p12/catalogs/final_check/``; then every SUBMIT or HOLD star of ``candidates_p12.csv`` whose TIC
appears in the fresh TOI or CTOI table but not in the 0d snapshot is flagged ``ALERTED_SINCE_SNAPSHOT``.
No verdict changes. A source that fails leaves its rows ``NOT_RECHECKED``, never a novelty claim.
Output ``p12/results/novelty_p12.json``.
"""
from p12_common import REPO, ROOT, DATA, PY, environment, read, write, sha, utc
import csv
import json
import subprocess
import sys
import time

SOURCES = ('toi', 'ctoi')
DEADLINE_S = 600
FINAL = DATA / 'catalogs/final_check'


def _tics(path):
    with path.open(newline='', encoding='utf-8-sig') as stream:
        return {int(r['tic_id']): r.get('label') for r in csv.DictReader(stream) if r.get('tic_id', '').isdigit()}


def fetch(source):
    environment(offline=False)
    sys.path.insert(0, str(REPO / 'src'))
    from tesshunter import catalog_crossmatch as cx
    destination = FINAL / source
    if destination.exists():
        raise FileExistsError(destination)
    cx.CATALOG_CACHE_DIR = destination
    catalog = cx.KnownObjectCatalog.load(sources=[source], refresh=True, allow_stale=False, offline=False)
    write(ROOT / f'results/novelty/{source}.json', dict(utc=utc(), source=source, catalog=catalog.manifest(),
          destination=destination.relative_to(REPO).as_posix()))
    return 0


def run():
    attempts = {}
    for source in SOURCES:
        started = time.perf_counter()
        log = ROOT / f'logs/novelty_{source}.log'
        with log.open('w', encoding='utf-8') as stream:
            try:
                code = subprocess.run([str(PY), __file__, '--fetch', source], cwd=REPO, env=environment(offline=False),
                                      stdout=stream, stderr=subprocess.STDOUT, timeout=DEADLINE_S).returncode
                status = 'COMPLETE' if code == 0 else 'OPERATIONAL_UNKNOWN'
            except subprocess.TimeoutExpired:
                status = 'TIMEOUT'
        attempts[source] = dict(status=status, wall_seconds=round(time.perf_counter() - started, 1), log=log.relative_to(REPO).as_posix())
    candidates = []
    with (ROOT / 'results/candidates_p12.csv').open(newline='', encoding='utf-8') as stream:
        for r in csv.DictReader(stream):
            if r['verdict'].startswith(('SUBMIT', 'HOLD')):
                candidates.append(r)
    flagged = []
    for source in SOURCES:
        before = _tics(DATA / f'catalogs/{source}/{source}.normalized.csv')
        fresh_path = FINAL / source / source / f'{source}.normalized.csv'
        if not fresh_path.exists():
            fresh_path = FINAL / source / f'{source}.normalized.csv'
        fresh = _tics(fresh_path) if attempts[source]['status'] == 'COMPLETE' and fresh_path.exists() else None
        for r in candidates:
            tic = int(r['tic_id'])
            if fresh is None:
                flagged.append(dict(tic_id=tic, key=r['key'], source=source, flag='NOT_RECHECKED'))
            elif tic in fresh and tic not in before:
                flagged.append(dict(tic_id=tic, key=r['key'], source=source, flag='ALERTED_SINCE_SNAPSHOT', label=fresh[tic]))
    result = dict(utc=utc(), sources=attempts, candidates_checked=len(candidates), flags=flagged,
                  alerted=sorted({f['tic_id'] for f in flagged if f['flag'] == 'ALERTED_SINCE_SNAPSHOT'}),
                  rule='a SUBMIT or HOLD star alerted since 0d is flagged ALERTED_SINCE_SNAPSHOT; no verdict changes',
                  candidates_sha256=sha(ROOT / 'results/candidates_p12.csv'))
    write(ROOT / 'results/novelty_p12.json', result, replace=(ROOT / 'results/novelty_p12.json').exists())
    print(json.dumps(dict(checked=len(candidates), alerted=len(result['alerted']), sources={k: v['status'] for k, v in attempts.items()})), flush=True)
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ['--fetch']:
        return fetch(argv[1])
    if argv != ['--online']:
        raise SystemExit('usage: novelty_p12.py --online')
    return run()


if __name__ == '__main__':
    raise SystemExit(main())
