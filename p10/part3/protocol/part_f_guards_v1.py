"""Part F integrity guard shared by its planner, worker and controller."""
from common import ROOT, sha, utc
import json
import os


class IntegrityFailure(RuntimeError):
    pass


def require_hash(path, expected, label):
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
