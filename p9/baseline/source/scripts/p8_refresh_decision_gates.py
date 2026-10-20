"""Refresh derived P8 gate fields from stored scans, without remeasuring any light curve."""
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'src'), str(REPO / 'scripts')]
import audit_p5 as A
import p8_decisions as D


def other_fields(record):
    return hashlib.sha256(json.dumps({k: v for k, v in record.items() if k != 'gate_variants'},
                                     sort_keys=True).encode()).hexdigest()


def main():
    report = {'generated_utc': D.utc(), 'scope': 'Derived gate fields only; original scans and all other fields retained',
              'n_checked': {}, 'changes': [], 'non_gate_field_differences': 0}
    for name in ('inj', 'p7', 'adv'):
        report['n_checked'][name] = 0
        for path in sorted((D.DEC / name).glob('*.json')):
            record = json.loads(path.read_text(encoding='utf-8'))
            if record.get('status') != 'OK':
                raise ValueError(f'unsettled instrument record: {path}')
            report['n_checked'][name] += 1
            gates = D.gate_variants_from(record.get('secondary'))
            if gates == record.get('gate_variants'):
                continue
            original = other_fields(record)
            report['changes'].append({'set': name, 'key': record['key'],
                                      'before': record['gate_variants'], 'after': gates})
            record['gate_variants'] = gates
            A.jdump(path, record)
            assert other_fields(json.loads(path.read_text(encoding='utf-8'))) == original
    target = D.P8 / 'decision_gate_refresh_p8.json'
    target.write_text(json.dumps(report, indent=1), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
