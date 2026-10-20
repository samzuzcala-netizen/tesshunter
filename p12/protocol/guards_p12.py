"""Part F integrity guard shared by its planner, worker and controller."""
from p12_common import REPO, ROOT, sha, utc, read
from pathlib import Path
import json
import os


class IntegrityFailure(RuntimeError):
    pass


def require_hash(path, expected, label):
    path = Path(path)
    if isinstance(expected, dict):
        expected = expected.get('sha256')
    if not path.is_file() or sha(path) != expected:
        raise IntegrityFailure(f'{label} hash changed: {path}')


def signal_integrity_failure(error, context):
    path = ROOT/'results/active_integrity_failure.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x', encoding='utf-8') as stream:
            json.dump(dict(utc=utc(),error=str(error),context=context,
                           action='Stop owned scientific queue; preserve unknowns'), stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        pass


def assert_no_integrity_failure(root=None):
    root = ROOT if root is None else root
    if (root/'results/active_integrity_failure.json').exists():
        raise IntegrityFailure('INTEGRITY_FAILURE: durable worker integrity receipt present')


def verify_freeze(phase):
    if not phase.startswith(('neg_', 'bar_', 'final_')):
        return None
    path = ROOT / 'manifests/freeze_p12_0.json'
    if not path.is_file():
        raise IntegrityFailure('STOP-1: freeze_p12_0.json required for ' + phase)
    receipt = read(path)
    hashes = receipt.get('source_hashes', receipt.get('hashes'))
    if not isinstance(hashes, dict) or not hashes:
        raise IntegrityFailure('STOP-1: freeze has no source hashes')
    for name, expected in hashes.items():
        source = REPO / name
        if not source.resolve().is_relative_to(REPO.resolve()):
            raise IntegrityFailure('STOP-1: freeze path outside repository')
        require_hash(source, expected, 'Frozen source')
    actual_python = {p.relative_to(REPO).as_posix() for p in (ROOT / 'protocol').glob('*.py')}
    sealed_python = {name for name in hashes if name.startswith(ROOT.relative_to(REPO).as_posix() + '/protocol/') and name.endswith('.py')}
    if actual_python != sealed_python:
        raise IntegrityFailure('STOP-1: Python source membership changed since freeze')
    return dict(freeze_sha256=sha(path), source_hashes_verified=len(hashes))
