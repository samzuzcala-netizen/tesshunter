"""P11 FITS inventory pattern and P10.3 identity-only job manifests."""
from p12_common import REPO, ROOT, DATA, read, write, sha, utc
from pathlib import Path
import argparse
import csv
import os
import re


def build(tics, *, output=None):
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Build manifests only between phases')
    ids = sorted({int(t) for t in tics})
    lookup = {tic: set() for tic in ids}
    for cache in (REPO/'data/cache/audit_lightkurve/mastDownload',DATA/'lightkurve'):
        for base, dirs, files in os.walk(cache):
            for name in files:
                if not name.endswith(('_lc.fits', '_llc.fits')):
                    continue
                match = re.search(r'(?<!\d)(\d{16})(?!\d)', name)
                if match and int(match[1]) in lookup:
                    lookup[int(match[1])].add((Path(base) / name).relative_to(REPO).as_posix())
    configuration = read(ROOT / 'protocol/config.json')
    policy_path = REPO / configuration['sector_policy_path']
    if sha(policy_path) != configuration['sector_policy_sha256']:
        raise RuntimeError('Frozen sector policy changed')
    notice = read(policy_path)['notice_snapshot']
    if sha(REPO / notice['path']) != notice['sha256']:
        raise RuntimeError('Frozen timing notice changed')
    sources = sorted({p.relative_to(REPO).as_posix() for p in (ROOT/'protocol').glob('*.py')} |
        {p.relative_to(REPO).as_posix() for p in (REPO/'src/tesshunter').glob('*.py')} |
        {'p12/protocol/config.json'})
    hashes = {name: sha(REPO / name) for name in sources}
    jobs = []
    for tic in ids:
        index_path = REPO / f'data/survey/audit_lc/tic{tic}/index.json'
        job_path = ROOT / f'manifests/input_jobs/tic{tic}.json'
        write(job_path, dict(tic_id=tic, source_paths=sorted(lookup[tic]),
            source_hashes={name: sha(REPO / name) for name in sorted(lookup[tic])},
            index_sha256=sha(index_path) if index_path.exists() else None,
            notice_snapshot_sha256=notice['sha256']))
        jobs.append(dict(job_id=f'tic{tic}', arguments=['p12/protocol/verify_prepare_p12.py', str(tic)],
            attempt=1, result_path=f'p12/results/native_noise/archival/tic{tic}.json',
            source_hashes=dict(hashes, **{job_path.relative_to(REPO).as_posix(): sha(job_path)})))
    write(output or ROOT / 'manifests/verify_core_jobs.json', jobs)
    return jobs


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--targets', default=str(ROOT / 'manifests/targets_p12_core.csv'))
    args = parser.parse_args(argv)
    with open(args.targets, newline='', encoding='utf-8-sig') as stream:
        jobs = build([row['tic_id'] for row in csv.DictReader(stream)])
    print('verification jobs', len(jobs), flush=True)
    return 0


if __name__ == '__main__':
    main()
