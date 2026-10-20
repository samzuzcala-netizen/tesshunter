"""P12 registration, copied from P10.3 register.py; immutable rule/source seal.

Chain additions (resumed session, 2026-09-23): after the base seal, a later
source file (a module needed by a later part, the freeze receipt) is sealed by
an immutable, hash-linked addition under ``manifests/registration_chain/``.
The prompt, the preregistration and the configuration are never superseded; a
sealed module may be superseded only with a recorded reason and amendment, and
only while no owner is alive. ``verify`` folds the chain in order.
"""
from p12_common import REPO, ROOT, initialize, read, write, sha, utc
import argparse
import json

FROZEN = ('PROMPT_P12.md', 'p12/PREREGISTRATION_P12.md', 'p12/protocol/config.json')


def _sources():
    return [REPO / 'PROMPT_P12.md', ROOT / 'PREREGISTRATION_P12.md',
            ROOT / 'protocol/config.json', *sorted((ROOT / 'protocol').glob('*.py'))]


def register():
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Registration requires no owner')
    if read(ROOT / 'results/integrity_entry/summary.json')['status'] != 'PASS':
        raise RuntimeError('STOP-1: entry integrity has not passed')
    names = _sources()
    if not all(path.is_file() for path in names):
        raise RuntimeError('Prompt, preregistration, config and P12 source must exist')
    destination = ROOT / 'manifests/registration_seal.json'
    if destination.exists():
        raise FileExistsError('Registration is immutable; use a documented chain addition')
    snapshot = ROOT / 'manifests/PROMPT_P12.source.md'
    with snapshot.open('xb') as stream:
        stream.write((REPO / 'PROMPT_P12.md').read_bytes())
    receipt = dict(utc=utc(), schema='p12-registration-v1',
        hashes={p.relative_to(REPO).as_posix(): sha(p) for p in [*names, snapshot]},
        python_files=[p.relative_to(REPO).as_posix() for p in names if p.suffix == '.py'],
        before_part1_measurements=True, prompt_snapshot_sha256=sha(snapshot),
        immutable=True, chain_additions=[], chain_directory='p12/manifests/registration_chain')
    write(destination, receipt)
    # Part 0 already owns its resource/exposure receipts; registration preserves them.
    return receipt


def _links():
    folder = ROOT / 'manifests/registration_chain'
    return sorted(folder.glob('[0-9][0-9][0-9][0-9]_*.json')) if folder.is_dir() else []


def effective():
    """The sealed hash map and Python membership after folding every chain link."""
    seal_path = ROOT / 'manifests/registration_seal.json'
    seal = read(seal_path)
    hashes = {name: (value.get('sha256') if isinstance(value, dict) else value) for name, value in seal['hashes'].items()}
    python = set(seal['python_files'])
    previous = sha(seal_path)
    problems = []
    for index, path in enumerate(_links(), 1):
        link = read(path)
        if link.get('index') != index or not path.name.startswith(f'{index:04d}_'):
            problems.append(f'chain link out of order: {path.name}')
        if link.get('previous_sha256') != previous:
            problems.append(f'chain link does not follow its predecessor: {path.name}')
        for name in link.get('hashes', {}):
            if name in FROZEN:
                problems.append(f'chain link supersedes a frozen file: {name}')
            if name in hashes and name not in link.get('superseded', {}):
                problems.append(f'chain link rewrites a sealed file without supersession: {name}')
        hashes.update(link.get('hashes', {}))
        python.update(link.get('python_files_added', []))
        previous = sha(path)
    return hashes, python, problems, previous


def add(paths, reason, *, amendment=None, supersede=False):
    """Seal later files by an immutable, hash-linked chain addition."""
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Chain addition requires no owner')
    if not reason or not str(reason).strip():
        raise ValueError('A chain addition needs a reason')
    hashes, python, problems, previous = effective()
    if problems:
        raise RuntimeError('STOP-1 registration chain invalid: ' + '; '.join(problems))
    rows, superseded, added_python = {}, {}, []
    for raw in paths:
        path = (REPO / raw).resolve()
        if not path.is_file() or not path.is_relative_to(ROOT.resolve()):
            raise ValueError(f'Chain additions seal existing files under p12/ only: {raw}')
        name = path.relative_to(REPO.resolve()).as_posix()
        if name in FROZEN:
            raise ValueError(f'Frozen registration file cannot be superseded: {name}')
        if name in hashes:
            if not supersede or not amendment:
                raise ValueError(f'Already sealed; supersession needs supersede=True and an amendment: {name}')
            superseded[name] = hashes[name]
        rows[name] = sha(path)
        if name.startswith('p12/protocol/') and name.endswith('.py') and name not in python:
            added_python.append(name)
    folder = ROOT / 'manifests/registration_chain'
    index = len(_links()) + 1
    slug = ''.join(ch if ch.isalnum() else '_' for ch in str(reason).lower())[:40].strip('_') or 'addition'
    link = dict(utc=utc(), schema='p12-registration-chain-v1', index=index, previous_sha256=previous,
        reason=reason, amendment=amendment, hashes=rows, superseded=superseded,
        python_files_added=sorted(added_python), immutable=True)
    destination = folder / f'{index:04d}_{slug}.json'
    write(destination, link)
    return dict(link=destination.relative_to(REPO).as_posix(), sha256=sha(destination), files=len(rows))


def verify():
    path = ROOT / 'manifests/registration_seal.json'
    hashes, python, problems, _ = effective()
    mismatches = list(problems)
    for name, digest in hashes.items():
        source = REPO / name
        if not source.is_file() or sha(source) != digest:
            mismatches.append(name)
    current = {p.relative_to(REPO).as_posix() for p in (ROOT / 'protocol').glob('*.py')}
    if current != python:
        mismatches.append('P12 Python source membership changed')
    if mismatches:
        raise RuntimeError('STOP-1 registration mismatch: ' + ', '.join(mismatches))
    return dict(status='PASS', registration_sha256=sha(path), files_verified=len(hashes), chain_links=len(_links()))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', nargs='?', choices=('register', 'verify', 'add'), default='register')
    parser.add_argument('paths', nargs='*')
    parser.add_argument('--reason')
    parser.add_argument('--amendment')
    parser.add_argument('--supersede', action='store_true')
    args = parser.parse_args(argv)
    if args.action == 'verify':
        result = verify()
    elif args.action == 'add':
        result = add(args.paths, args.reason, amendment=args.amendment, supersede=args.supersede)
    else:
        result = register()
    print(json.dumps(result), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
