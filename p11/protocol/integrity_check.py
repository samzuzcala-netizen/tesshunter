"""Verify all registered historical hashes, P10's complete seal and P11 source inputs."""
import json
import subprocess
import time
from common import REPO,P11,read,write,sha,utc


def main():
    started=utc();timer=time.perf_counter();bad=[]
    original=read(P11/'manifests/entry_source_and_evidence_hashes.json')
    for name,digest in original.items():
        if not (REPO/name).is_file() or sha(REPO/name)!=digest:bad.append(name)
    seal_path=REPO/'p10/results/part2d_calibration_20260912/full_calibration_closed_seal_20260912.json'
    seal=read(seal_path)
    for entry in seal['files']:
        path=REPO/entry['path']
        if not path.is_file() or path.stat().st_size!=entry['bytes'] or sha(path)!=entry['sha256']:bad.append(entry['path'])
    raw={}
    for path in (P11/'results/input_inventory_v2').glob('tic*.json'):
        for r in read(path)['records']:
            if 'raw_path' not in r:continue
            raw[r['raw_path']]=r['raw_sha256']
            for source in r['source_matches']:raw[source['path']]=source['sha256']
    for name,digest in raw.items():
        if sha(REPO/name)!=digest:bad.append(name)
    write(P11/'results/historical_integrity.json',dict(started_utc=started,completed_utc=utc(),wall_seconds=time.perf_counter()-timer,
        registered_source_evidence_index_files=len(original),P10_full_calibration_files=len(seal['files']),
        raw_and_source_FITS_files=len(raw),mismatches=bad,status='PASS' if not bad else 'FAIL',
        P10_seal_sha256=sha(seal_path),source_sha256=sha(__file__),
        tracked_diff=subprocess.check_output(['git','diff','--name-only'],cwd=REPO,text=True).splitlines()))
    print('integrity',len(original),len(seal['files']),len(raw),'mismatches',len(bad),flush=True)
    if bad:raise SystemExit(1)


if __name__=='__main__':main()
