"""Verify the delivered bundle without requiring the original Git/P8 checkout."""
from pathlib import Path
import hashlib, json

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    manifest=json.loads((ROOT/'BUNDLE_MANIFEST.json').read_text(encoding='utf-8'))
    bad=[]
    for rel,expected in manifest['files_sha256'].items():
        path=(ROOT/rel).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or digest(path)!=expected:bad.append(rel)
    lock_count=0
    for lp in (ROOT/'p9/results/locks').glob('tic*.json'):
        lock=json.loads(lp.read_text(encoding='utf-8'));blind=ROOT/'p9/results/blind'/lp.stem
        actual={str(p.relative_to(ROOT/'p9')):digest(p) for p in blind.rglob('*') if p.is_file()}
        # Original Windows receipts retain backslashes; accept platform path syntax.
        normalize=lambda d:{k.replace('\\','/'):v for k,v in d.items()}
        if normalize(actual)!=normalize(lock['sha256']):bad.append('exact blind-host lock: '+lp.stem)
        lock_count+=1
    for path in (ROOT/'p9/results/blind').glob('*/final/*.json'):
        if json.loads(path.read_text(encoding='utf-8')).get('actual_submission_eligible') is not False:
            bad.append('actual submission flag: '+str(path.relative_to(ROOT)))
    print(json.dumps(dict(status='FAIL' if bad else 'PASS',files_checked=len(manifest['files_sha256']),
      locked_hosts=lock_count,mismatches=bad),indent=2))
    if bad:raise SystemExit(1)


if __name__=='__main__':main()
