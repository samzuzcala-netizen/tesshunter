"""Part 1d (after plumbing): re-score the 35 saved records of ``p10/results/tier_rederivation.csv``
under p12.0 (copy of ``scripts/p10_tier_rederivation.py``; nothing re-measured, nothing
under ``data/survey/p8`` or ``p9`` written). Exactly the flips of 1b plus the K10 outcome are
expected; any other flip is listed for diagnosis. The p10.0 re-evaluation with the overlay
loaded must reproduce the sealed ``tier_rederivation.json`` evaluations exactly.
Label: "re-scoring of seen records under pre-registered rules, not a validation".
"""
from p12_common import REPO, ROOT, read, write, sha, utc, append_jsonl
import argparse
import csv
import json
import sys
from pathlib import Path

LABEL = 're-scoring of seen records under pre-registered rules, not a validation'
EXPECTED_FLIPS = {
    'tic178709444_P3.4721': ('KILL', 'SUBMIT', 'A1: K8 density-ratio guard (0.5, 2.0) -> (0.5, 2.5)'),
    'tic231702397_P5.0783': ('KILL', 'SUBMIT', 'A2: K6 odd/even 3.0 -> 3.5 sigma'),
    'tic144277542_P12.9812': ('SUBMIT', 'HOLD', 'A3: H5 one-sector K9b hold (or KILL K10 if admitted and firing)'),
}


def _historical():
    for path in (REPO / 'src', REPO / 'scripts'):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    import p10_tier_rederivation as H
    return H


def rescore():
    import rules_p12
    H = _historical()
    from tesshunter import verdict_tiers as T
    install = rules_p12.install()
    admission = rules_p12.k10_admission()
    sealed = read(REPO / 'p10/results/tier_rederivation.json')
    with (REPO / 'p10/results/tier_rederivation.csv').open(newline='', encoding='utf-8') as stream:
        sealed_rows = list(csv.DictReader(stream))
    rows, evaluations, reproduction = [], {}, {}
    for old in sealed_rows:
        key, tic, period = old['key'], int(old['tic_id']), float(old['period_days'])
        base = dict(set=old['set'], key=key, tic_id=tic, period_days=period, association=old['association'],
                    p10_verdict=old['p10_verdict'], p10_deciding=old['deciding_condition'])
        if old['p10_verdict'] == 'not permitted':
            rows.append(dict(base, p12_verdict='not permitted', p12_deciding=old['deciding_condition'], flip=False,
                             expected_flip=key in EXPECTED_FLIPS, note='never reached D under p8.0; not re-scored'))
            continue
        if old['set'] == 'P8':
            root = REPO / 'data/survey/p8'
            b = read(root / 'stageB' / f'{key}.json')
            inputs = T.load_inputs(root, key, tic, period, float(b['survey_depth_ppt']), candidates_csv=root / 'candidates.csv')
        else:
            root = REPO / f'p9/results/blind/tic{tic}'
            b = read(root / 'stageB' / f'{key}.json')
            inputs = T.load_inputs(root, key, tic, period, float(b['survey_depth_ppt']), candidates_csv=root / 'candidates.csv')
        append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=tic, stage='Part 1 re-scoring of a seen record',
            path=root.relative_to(REPO).as_posix(), reader='tier_rederivation_p12.py', prompt_of_origin=old['set'],
            content='saved stage, fit, expensive and pixel records of this key'))
        p10 = rules_p12.evaluate(inputs, 'p10.0')
        reproduction[key] = json.dumps(json.loads(json.dumps(p10, default=str)), sort_keys=True) == \
            json.dumps(sealed['evaluations'][key], sort_keys=True)
        ev = rules_p12.evaluate(inputs, 'p12.0', k10_word=admission['word'], k10_variants=admission['variants'])
        evaluations[key] = ev
        fired = [n for n in ev['k_order'] + ev['h_order'] if ev['conditions'][n]['fired']]
        flip = ev['verdict'] != p10['verdict']
        rows.append(dict(base, p12_verdict=ev['verdict'], p12_deciding=ev['deciding_condition'] or '', flip=flip,
                         expected_flip=key in EXPECTED_FLIPS, p12_fired=' '.join(fired),
                         p12_not_measurable=' '.join(ev['not_measurable']),
                         candidate_tier=(ev.get('candidate_tier') or {}).get('candidate_tier'),
                         k10_or_fired=ev['flags']['F10']['or_fired'], k10_word=admission['word'],
                         density_ratio=ev['conditions']['K8'].get('density_ratio'), odd_even_sigma=ev['conditions']['K6'].get('sigma'),
                         h5=ev['conditions']['H5']['fired'], note=''))
    unlisted = [r['key'] for r in rows if r['flip'] and not r['expected_flip']]
    missing = [k for k in EXPECTED_FLIPS if not any(r['key'] == k and r['flip'] for r in rows)]
    out = Path(REPO / 'p12/results/part1')
    out.mkdir(parents=True, exist_ok=True)
    cols = sorted({c for r in rows for c in r}, key=lambda c: list(rows[0]).index(c) if c in rows[0] else 99)
    with (out / 'tier_rederivation_p12.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=cols, lineterminator='\n')
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, '') for c in cols})
    payload = dict(utc=utc(), label=LABEL, rules_version='p12.0', install=install, k10=admission,
                   expected_flips=EXPECTED_FLIPS, unlisted_flips=unlisted, expected_flips_missing=missing,
                   p10_reproduces_sealed_evaluations=reproduction, all_p10_reproduced=all(reproduction.values()),
                   rows=rows, evaluations=evaluations, source_sha256=sha(__file__))
    write(out / 'tier_rederivation_p12.json', json.loads(json.dumps(payload, default=str)), replace=(out / 'tier_rederivation_p12.json').exists())
    print(json.dumps(dict(rows=len(rows), flips=[r['key'] for r in rows if r['flip']], unlisted=unlisted,
                          missing=missing, p10_reproduced=all(reproduction.values()))), flush=True)
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='p12/results/part1')
    args = parser.parse_args(argv)
    if Path(args.out).as_posix().rstrip('/') != 'p12/results/part1':
        raise ValueError('Registered output is p12/results/part1')
    rescore()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
