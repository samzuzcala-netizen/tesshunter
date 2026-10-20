"""Per-part HANDOFF sections from receipts only (0c.2), prepended before each part's commit.

For every phase of the part in ``phase_sequence.json``: a controller phase's closure (jobs,
unknowns, queue-hours, status); an evaluator's registered outputs (path, SHA-256 and their
top-level scalar fields). No per-candidate record is opened; judged tables are summarised by
their scalar headline fields only.
"""
from p12_common import REPO, ROOT, read, sha, utc
import argparse
import json
from pathlib import Path

HEADLINE_TYPES = (str, int, float, bool, type(None))


def _headline(path):
    try:
        value = read(path)
    except Exception:
        return {}
    if not isinstance(value, dict):
        return {'entries': len(value) if isinstance(value, list) else None}
    return {k: v for k, v in value.items() if isinstance(v, HEADLINE_TYPES) and k not in ('utc',)
            and not (isinstance(v, str) and len(v) > 160)}


def section(part):
    sequence = read(ROOT / 'manifests/phase_sequence.json')
    rows = [p for p in sequence['phases'] if p['part'] == part]
    lines = [f'# PART {part} CLOSED ({utc()}) [M]', '']
    for p in rows:
        name = p['name']
        closure_path = ROOT / 'results/controllers' / name / 'closure.json'
        if p['kind'] == 'controller':
            if closure_path.exists():
                c = read(closure_path)
                lines.append(f"- `{name}` (controller): {c['status']}, {c['completed']} of {c['total']} jobs, {c['unknowns']} "
                             f"operational unknowns, {c['queue_hours']:.3f} queue-h [M].")
            else:
                lines.append(f'- `{name}` (controller): not run (condition not met or skipped) [M].')
        elif p['kind'] in ('evaluator', 'gate'):
            transition = [t for t in (ROOT / 'results').glob('transition_after_*.json') if read(t).get('phase') == name]
            done = any(read(t).get('status') == 'COMPLETE' for t in transition)
            lines.append(f"- `{name}` ({p['kind']}, `{p.get('script')}` {' '.join(p.get('args', []))}): "
                         f"{'complete' if done else 'not run'} [M].")
            for rel in [p.get('judged_table'), p.get('output')]:
                if rel and (REPO / rel).exists():
                    heads = _headline(REPO / rel)
                    lines.append(f"  - `{rel}` (SHA-256 `{sha(REPO / rel)[:16]}…`): " +
                                 '; '.join(f'{k} = {json.dumps(v)}' for k, v in list(heads.items())[:12]))
        elif p['kind'] == 'commit':
            lines.append(f"- `{name}`: commit \"{p.get('message')}\" follows this section.")
    ledger = ROOT / 'manifests/resource_ledger.json'
    if ledger.exists():
        lines += ['', f"Cumulative new queue-hours: {read(ledger).get('new_queue_hours', 0):.3f} [M]."]
    lines += ['', 'Resume here: the next phase of the registered sequence (`continuation_p12.py`).', '', '---', '']
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('part', type=int)
    args = parser.parse_args(argv)
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Owner remains')
    lines = section(args.part)
    handoff = REPO / 'HANDOFF_P12.md'
    handoff.write_text('\n'.join(lines) + '\n' + handoff.read_text(encoding='utf-8'), encoding='utf-8')
    with (REPO / 'RESUME_P12.md').open('a', encoding='utf-8') as stream:
        stream.write(f'\n{utc()} [M]: part {args.part} closed; handoff section written; commit follows.\n')
    print(json.dumps(dict(part=args.part, lines=len(lines))), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
