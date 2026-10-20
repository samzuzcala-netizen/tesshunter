"""Run compatibility/behavioral tests without rewriting historical receipts."""
from common import *
environment()
import sys,subprocess,time,importlib.metadata

def main(name):
    folder=ROOT/'results'/name;folder.mkdir(parents=True,exist_ok=False)
    paths=[]
    for directory in ('src/tesshunter','tests','p11/tests','p11/p11_5/tests','p11/p11_5/protocol'):
        paths.extend(p for p in (REPO/directory).rglob('*.py') if '__pycache__' not in p.parts)
    hashes={p.relative_to(REPO).as_posix():sha(p) for p in sorted(set(paths))}
    write(folder/'source_freeze.json',dict(utc=utc(),hashes=hashes))
    command=[sys.executable,'-m','pytest','tests','p11/tests','p11/p11_5/tests','-q'];start=time.perf_counter()
    with (folder/'pytest.log').open('w',encoding='utf-8') as log:
        result=subprocess.run(command,cwd=REPO,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    changed=[p for p,h in hashes.items() if sha(REPO/p)!=h]
    write(folder/'receipt.json',dict(utc=utc(),command=command,exit_code=result.returncode,wall_seconds=time.perf_counter()-start,
        log_sha256=sha(folder/'pytest.log'),source_hashes_verified_at_end=not changed,changed=changed,
        python=sys.version,versions={k:importlib.metadata.version(k) for k in read(ROOT/'results/entry.json')['versions']}))
    print((folder/'pytest.log').read_text(encoding='utf-8')[-2000:])
    if result.returncode or changed:raise SystemExit(1)

if __name__=='__main__':main(sys.argv[1])
