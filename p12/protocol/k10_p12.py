"""Part 1c: K10 calibration on saved records and its admission (written before it ran).

Variants (``rules_p12.k10``): K10e = n_excluded / n_observed > 0.5 (not measurable when
n_observed < 4); K10s = SAP kept depth < 0.5 x corrected kept depth, the difference above 3x
the quadrature sum of their errors, kept events in >= 2 sectors (not measurable when a depth
or an error is missing). Sets (seen records, every read ledgered): (a) the four P8 reviewer
artefact KILLs and the two HOLDs of ``data/survey/p8/review_p8.json``; (b) the P8 Stage A
passers (descriptive); (c) the Stage A PASS records of the sealed P10 2d injections; (d) the
Stage A records of the 12 P9 rows of ``tier_rederivation.csv`` associated with a named planet.
Admission: a variant is eligible when it fires on <= 2.0% of (c) (fired / all records of the
set) and on none of (d). K10 is the OR of eligible variants, re-checked against both bars
(drop K10s, then K10e, until it passes). K10 is a KILL when the OR fires on
tic144277542_P12.9812 and on >= 3 of the 4 artefact KILLs; otherwise it is flag F10.
"""
from p12_common import REPO, ROOT, read, write, sha, utc, append_jsonl
import rules_p12
from rules_p12 import k10, k10_or, K10_VARIANTS
from stats_p12 import rate
import argparse
import json
from pathlib import Path

ARTEFACT_KILLS = ('tic230120862_P16.7959', 'tic80256158_P10.8184', 'tic144277542_P12.9812', 'tic155895971_P13.1279')
HOLDS = ('tic154566869_P8.9053', 'tic404927114_P27.5436')
P9_NAMED = ('tic231702397_P5.0783', 'tic335590096_P1.5228', 'tic102734241_P10.9047', 'tic243641947_P2.5929',
            'tic271971130_P19.2884', 'tic389900760_P5.8005', 'tic259168516_P4.8025', 'tic181804752_P4.9893',
            'tic178709444_P3.4721', 'tic161032923_P3.9644', 'tic284441182_P2.5272', 'tic377293776_P2.0439')
KEY_RECORD = 'tic144277542_P12.9812'


def _tic(key):
    return int(key.split('_P')[0][3:])


def sets():
    p8 = REPO / 'data/survey/p8/stageA'
    review = read(REPO / 'data/survey/p8/review_p8.json')
    if set(review) != set(ARTEFACT_KILLS) | set(HOLDS):
        raise RuntimeError('P8 review keys differ from the registered set (a)')
    a = [(key, p8 / f'{key}.json', 'P8') for key in ARTEFACT_KILLS + HOLDS]
    b = [(path.stem, path, 'P8') for path in sorted(p8.glob('*.json')) if read(path).get('decision') == 'PASS']
    c = []
    for path in sorted((REPO / 'data/survey/p10/part2d/calibration/inj_funnel').glob('*/stageA/*.json')):
        if read(path).get('decision') == 'PASS':
            c.append((path.parent.parent.name + '/' + path.stem, path, 'P10 2d'))
    d = [(key, REPO / f'p9/results/blind/tic{_tic(key)}/stageA/{key}.json', 'P9') for key in P9_NAMED]
    return dict(a=a, b=b, c=c, d=d)


def calibrate():
    configuration = read(ROOT / 'protocol/config.json')
    c10 = configuration['k10']
    groups = sets()
    values = {}
    for name, rows in groups.items():
        values[name] = []
        for label, path, origin in rows:
            record = read(path)
            values[name].append((label, k10(record, configuration)))
            append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=_tic(label.split('/')[-1]),
                stage=f'Part 1c K10 calibration set ({name}), seen Stage A record', path=path.relative_to(REPO).as_posix(),
                reader='k10_p12.py calibrate', prompt_of_origin=origin, content='chosen-ephemeris event counts and kept depths only'))
    table = {}
    for variant in K10_VARIANTS:
        table[variant] = {}
        for name, rows in values.items():
            fired = sum(1 for _, v in rows if v[variant]['fired'])
            unmeasurable = sum(1 for _, v in rows if v[variant]['fired'] is None)
            table[variant][name] = dict(rate(fired, len(rows)), not_measurable=unmeasurable,
                                        fired_labels=[label for label, v in rows if v[variant]['fired']] if name in ('a', 'd') else None)
    eligible = [v for v in K10_VARIANTS if table[v]['c']['fraction'] is not None
                and table[v]['c']['fraction'] <= c10['injection_fire_fraction_max'] and table[v]['d']['k'] == 0]

    def or_rates(variants):
        out = {}
        for name, rows in values.items():
            fired = sum(1 for _, v in rows if k10_or(v, variants))
            out[name] = dict(rate(fired, len(rows)), fired_labels=[label for label, v in rows if k10_or(v, variants)] if name in ('a', 'd') else None)
        return out

    chosen, history = list(eligible), []
    while chosen:
        rates = or_rates(chosen)
        passes = rates['c']['fraction'] <= c10['injection_fire_fraction_max'] and rates['d']['k'] == 0
        history.append(dict(variants=list(chosen), c=rates['c'], d=rates['d'], passes=passes))
        if passes:
            break
        chosen.remove('K10s' if 'K10s' in chosen else 'K10e')
    or_a = {label: k10_or(v, chosen) for label, v in values['a']} if chosen else {}
    fires_key = bool(or_a.get(KEY_RECORD))
    artefact_hits = sum(1 for key in ARTEFACT_KILLS if or_a.get(key))
    word = 'K10_KILL' if chosen and fires_key and artefact_hits >= c10['artifact_fire_count_min'] else 'K10_FLAG'
    result = dict(utc=utc(), schema='p12-k10-calibration-v1', word=word, or_variants=chosen, eligible_variants=eligible,
                  or_recheck_history=history, fires_on_key_record=fires_key, artefact_kills_fired=artefact_hits,
                  artefact_kill_bar=c10['artifact_fire_count_min'], sets=dict(n={k: len(v) for k, v in values.items()},
                  definition=dict(a='4 P8 artefact KILLs + 2 HOLDs (review_p8.json)', b='P8 Stage A PASS (descriptive)',
                                  c='Stage A PASS of the sealed P10 2d injections', d='12 P9 named-planet rows')),
                  table=table, per_record_a={label: v for label, v in values['a']},
                  per_record_d={label: v for label, v in values['d']},
                  denominator='fired / all records of the set (a not-measurable record counts as not fired)',
                  bars=dict(injection_fire_fraction_max=c10['injection_fire_fraction_max'], truth_positive_fires_max=0),
                  source_sha256=sha(__file__), rules_sha256=sha(rules_p12.__file__),
                  label='calibration on seen records under a rule written before it ran')
    out = ROOT / 'results/part1/k10_calibration.json'
    write(out, json.loads(json.dumps(result, default=str)))
    print(json.dumps(dict(word=word, or_variants=chosen, eligible=eligible, n={k: len(v) for k, v in values.items()},
                          artefact_kills_fired=artefact_hits, fires_on_key_record=fires_key)), flush=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['calibrate'])
    parser.parse_args(argv)
    calibrate()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
