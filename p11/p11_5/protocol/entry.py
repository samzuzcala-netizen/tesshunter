"""Read-only historical verification and an explicit compatibility reuse proof."""
from common import *
import importlib.metadata
import shutil
import subprocess
import sys
import psutil

def main():
    environment()
    old = read(REPO / 'p11/results/final/entry.json')
    versions = {name: importlib.metadata.version(name) for name in old['versions']}
    historical = read(REPO / 'p11/manifests/final_freeze.json')['source_and_evidence']
    checks = {name: sha(REPO/name) == item['sha256'] for name, item in historical.items()}
    original = read(REPO / 'p11/manifests/entry_source_and_evidence_hashes.json')
    # P11 added its own files, while every effective historical worker source is unchanged.
    source = {name: expected for name, expected in original.items()
              if name.startswith(('src/', 'scripts/', 'tests/'))}
    source_checks = {name: sha(REPO/name) == expected for name, expected in source.items()}
    assert checks and source_checks and all(checks.values()) and all(source_checks.values())
    assert versions == old['versions'] and sys.version == old['python']
    (ROOT/'manifests').mkdir(parents=True, exist_ok=True)
    status = subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'], cwd=REPO)
    (ROOT/'manifests/entry_git_status.txt').write_bytes(status)
    owners = [p.info for p in psutil.process_iter(['pid','ppid','name','create_time','cmdline'])
              if 'python' in (p.info['name'] or '').lower()]
    receipt = dict(utc=utc(), head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        interpreter=sys.executable, python=sys.version, versions=versions,
        compatibility='REUSE_RECENT_793_PASS_1_SKIP',
        prior_receipt='p11/results/final/entry.json', prior_receipt_sha256=sha(REPO/'p11/results/final/entry.json'),
        historical_freeze_checks=checks, effective_source_checks=source_checks,
        environment=dict(os.environ), owners=owners, disk=shutil.disk_usage(REPO)._asdict(),
        memory=psutil.virtual_memory()._asdict(), cumulative_prior_queue_hours=0.920809591111111,
        cumulative_prior_acquired_bytes=81827574)
    receipt['environment']={k:os.environ[k] for k in ('TESSHUNTER_OFFLINE','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS','LIGHTKURVE_CACHE')}
    write(ROOT/'results/entry.json', receipt)
    event('entry', prior_queue_hours=0.920809591111111, prior_acquired_bytes=81827574,
          source_checks=len(source_checks), historical_checks=len(checks))
    print({k:receipt[k] for k in ('head','compatibility','disk')})

if __name__=='__main__': main()
