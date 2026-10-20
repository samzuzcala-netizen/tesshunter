"""Part 3 freeze entry point (AMENDMENTS_P12.md, "Freeze receipt: scalar amended constants (2026-09-26)").

``freeze_p12.build`` failed at its first run before writing anything: it records the amended constants as
``list(v)`` for every value, and ``rules_p12.AMENDED`` holds one tuple (``TIER_DENSITY_RATIO_RANGE``) and one scalar
(``TIER_ODD_EVEN_SIGMA`` 3.5), so ``list(3.5)`` raised TypeError. This is that ``build`` unchanged except that the
constants are recorded as ``rules_p12.install_hash`` already records them (a tuple as a list, a scalar as itself).
``MANIFESTS``, ``TABLES`` and ``preset`` are imported from ``freeze_p12``. It is a new file, not a supersession, because
the frozen stage runtimes pin every existing ``p12/protocol/*.py`` (Part 4 neg_fa_C builds its C runtimes from the arm
A base runtimes).
"""
from p12_common import REPO, ROOT, read, write, sha, utc
from freeze_p12 import MANIFESTS, TABLES, preset
import argparse
import json


def amended(constants):
    return {k: list(v) if isinstance(v, tuple) else v for k, v in constants.items()}


def build():
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Freeze requires no owner')
    out = ROOT / 'manifests/freeze_p12_0.json'
    if out.exists():
        raise FileExistsError('The freeze is immutable')
    if read(ROOT / 'manifests/freeze_readiness.json')['status'] != 'READY':
        raise RuntimeError('Freeze readiness is not READY')
    from register_p12 import verify
    registration = verify()
    import rules_p12
    install = rules_p12.install()
    decision = read(ROOT / 'results/part2/photometry_decision.json')
    k10 = read(ROOT / 'results/part1/k10_calibration.json')
    configuration = read(ROOT / 'protocol/config.json')
    ledger = ROOT / 'manifests/exposure_ledger.jsonl'
    rows = sum(1 for line in ledger.open(encoding='utf-8') if line.strip())
    python = sorted((ROOT / 'protocol').glob('*.py')) + sorted((ROOT / 'heldout').glob('*.py'))
    receipt = dict(utc=utc(), schema='p12-freeze-v1', rules_version='p12.0', base_rules='p10.0',
        photometry=dict(word=decision['decision'], reason=decision.get('reason'), table_sha256=sha(ROOT / 'results/part2/photometry_decision.json'),
                        median_wall_ratio=decision.get('median_wall_ratio')),
        preset=preset(), rules=dict(install_hash=install['install_hash'], rules_p12_sha256=sha(ROOT / 'protocol/rules_p12.py'),
                                    amended_constants=amended(rules_p12.AMENDED), k10_word=k10['word'],
                                    k10_variants=k10['or_variants'], amendments_sha256=sha(ROOT / 'protocol/AMENDMENTS_P12.md')),
        population_tier=read(ROOT / 'manifests/decision_point_1.json')['tier'],
        sector_policy=dict(path=configuration['sector_policy_path'], sha256=sha(REPO / configuration['sector_policy_path'])),
        seeds=configuration['seeds'],
        manifests={name: sha(ROOT / name) for name in MANIFESTS if (ROOT / name).exists()},
        tables={name: sha(ROOT / name) for name in TABLES if (ROOT / name).exists()},
        phase_sequence_sha256=sha(ROOT / 'manifests/phase_sequence.json'),
        exposure_ledger=dict(rows=rows, sha256=sha(ledger)),
        registration=registration,
        source_hashes={p.relative_to(REPO).as_posix(): sha(p) for p in python},
        from_here='no threshold, preset, policy, catalogue or population changes; controller_p12 verifies this receipt before '
                  'every neg_*, bar_* and final_* phase (a mismatch is STOP-1)',
        entry_point='p12/protocol/freeze_build_p12.py (freeze_p12.build with scalar amended constants)')
    receipt['source_hashes']['p12/protocol/config.json'] = sha(ROOT / 'protocol/config.json')
    write(out, receipt)
    from register_p12 import add
    link = add([out.relative_to(REPO).as_posix()], 'Part 3 freeze of p12.0')
    print(json.dumps(dict(freeze_sha256=sha(out), sources=len(receipt['source_hashes']), link=link['link'],
                          photometry=receipt['photometry']['word'], k10=k10['word'])), flush=True)
    return receipt


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    build()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
