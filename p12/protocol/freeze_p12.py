"""Part 3: the freeze of ``p12.0``, written before any Part 4 or Part 5 job and before any
per-candidate record of the final population is opened.

``freeze_p12_0.json`` carries: population, eligibility and E1 manifest hashes; the photometry word
and its table's hash; the ``survey_p10`` preset (the resolved dataclass fields and the survey.py
hash); the rules overlay hash, the amendment table and the K10 word; the sector policy, catalogue
snapshot and sidecar hashes; seeds; completeness-table hashes; the negative-set and held-out
manifests; every ``p12/protocol/*.py`` and ``p12/heldout/*.py`` hash (``source_hashes``, verified by ``guards_p12.verify_freeze``
before every ``neg_*``, ``bar_*`` and ``final_*`` phase); an exposure-ledger snapshot. The receipt is
appended to the registration seal as an immutable chain link.
"""
from p12_common import REPO, ROOT, DATA, read, write, sha, utc
import argparse
import dataclasses
import json
import sys
from pathlib import Path

MANIFESTS = ('manifests/targets_p12_core.csv', 'manifests/eligibility_p12.json', 'manifests/targets_ext_E1.csv',
             'manifests/targets_ext_E2.csv', 'manifests/decision_point_1.json', 'manifests/hard_stop_p12.json',
             'manifests/catalog_versions_p12.json', 'manifests/sidecar_p12.json', 'manifests/ttt_negatives.csv',
             'manifests/ttt_adjacent_negatives.csv', 'manifests/ttt_adjacent_selection.json', 'manifests/sector_probe.json',
             'protocol/config.json', 'protocol/AMENDMENTS_P12.md', 'PREREGISTRATION_P12.md', 'results/part1/k10_calibration.json',
             'results/part1/tier_rederivation_p12.json', 'results/part1/plumbing_d.json', 'results/part2/photometry_decision.json')
TABLES = ('results/part2/COMPLETENESS_ARM_A.json', 'results/part2/COMPLETENESS_ARM_B.json', 'results/part2/retention_archival.json',
          'results/part2/retention_sml.json', 'results/part2/window_check.json', 'results/part2/long_period_tabulation.json',
          'results/part2/s_mode_restatement.json', 'results/part2/injection_outcomes_archival.csv',
          'results/part2/injection_outcomes_sml.csv')


def preset():
    if str(REPO / 'src') not in sys.path:
        sys.path.insert(0, str(REPO / 'src'))
    from tesshunter import survey
    cfg = survey.get_config('survey_p10')
    fields = {k: (v if isinstance(v, (int, float, str, bool, type(None))) else repr(v)) for k, v in dataclasses.asdict(cfg).items()}
    return dict(name='survey_p10', fields=fields, ingest_key=cfg.ingest_key(), survey_py_sha256=sha(REPO / 'src/tesshunter/survey.py'),
                lines='src/tesshunter/survey.py lines 207 to 237 (survey_p8, then the survey_p10 replacements)')


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
                                    amended_constants={k: list(v) for k, v in rules_p12.AMENDED.items()}, k10_word=k10['word'],
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
                  'every neg_*, bar_* and final_* phase (a mismatch is STOP-1)')
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
