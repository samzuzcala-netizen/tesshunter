"""Part 6e.1: the final seals.

SHA-256 of every file under ``p12/`` (``p12/manifests/source_seal_final.json``) and under ``data/survey/p12/``
(``p12/manifests/data_seal_final.json``, on ``D:`` behind the junction), then every source hash of
``freeze_p12_0.json`` re-verified (a mismatch is STOP-1). The two seal files and the working logs that change
while the seal runs (``p12/progress.json``, ``p12/logs/``) are listed by name without a hash.
"""
from p12_common import REPO, ROOT, DATA, read, write, sha, utc
import json
import os
import time

VOLATILE = ('p12/progress.json', 'p12/manifests/source_seal_final.json', 'p12/manifests/data_seal_final.json')


def _walk(root):
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__')
        for name in sorted(files):
            yield os.path.join(base, name)


def seal():
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Seals require no owner')
    from guards_p12 import verify_freeze
    freeze = verify_freeze('final_seals')
    timer = time.perf_counter()
    source, skipped = {}, []
    for path in _walk(ROOT):
        rel = os.path.relpath(path, REPO).replace(os.sep, '/')
        if rel in VOLATILE or rel.startswith('p12/logs/'):
            skipped.append(rel)
            continue
        source[rel] = sha(path)
    write(ROOT / 'manifests/source_seal_final.json', dict(utc=utc(), files=len(source), hashes=source, volatile_unhashed=skipped,
          freeze=freeze), replace=(ROOT / 'manifests/source_seal_final.json').exists())
    data, size = {}, 0
    for path in _walk(DATA):
        rel = os.path.relpath(path, REPO).replace(os.sep, '/')
        data[rel] = sha(path)
        size += os.path.getsize(path)
    write(ROOT / 'manifests/data_seal_final.json', dict(utc=utc(), files=len(data), bytes=size, root=str(DATA.resolve()), hashes=data),
          replace=(ROOT / 'manifests/data_seal_final.json').exists())
    print(json.dumps(dict(source_files=len(source), data_files=len(data), data_bytes=size,
                          wall_s=round(time.perf_counter() - timer, 1), freeze_sources_verified=freeze['source_hashes_verified'])), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(seal())
