"""Record source provenance without importing any scientific module."""
import difflib
from pathlib import Path
from p12_common import REPO, ROOT, read, write, sha, utc


def build() -> dict:
    interfaces = read(ROOT / 'manifests/interfaces_p12.json')
    rows = []
    for entry in interfaces['modules']:
        path = ROOT / 'protocol' / entry['module']
        if not path.is_file():
            rows.append(dict(module=entry['module'], status='open', origin=entry['origin']))
            continue
        source = REPO / entry['origin'] if entry['origin'] else None
        old = source.read_text(encoding='utf-8-sig') if source and source.is_file() else ''
        new = path.read_text(encoding='utf-8-sig')
        rows.append(dict(module=entry['module'], status='written', origin=entry['origin'],
                         origin_sha256=sha(source) if source and source.is_file() else None,
                         p12_sha256=sha(path), permitted_diff=entry['permitted_diff'],
                         diff=''.join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                   fromfile=entry['origin'] or '(new)', tofile=path.relative_to(REPO).as_posix()))))
    return dict(utc=utc(), source='PROMPT_P12.md Part 0c', modules=rows,
                meaning='Complete textual diffs for lead review; not a scientific equivalence assertion')


def main() -> None:
    write(ROOT / 'manifests/protocol_provenance.json', build(), replace=True)


if __name__ == '__main__':
    main()
