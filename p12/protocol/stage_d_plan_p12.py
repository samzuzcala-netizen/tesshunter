"""Part 1d: the Stage D plumbing test on six seen P8 candidates.

Copies the P8 D inputs of the four artefact KILLs, TIC 154566869 and TIC 404927114
(``data/survey/p8/{stageA,secondary,stageB,stageC,neighbours}``, plus the ``tls``
records Stage C wrote and D reads, the P8 reviewer's ``pixel_followup`` record that
K9 reads, and each key's rows of ``survivors.csv`` and ``candidates.csv``) into
``data/survey/p12/plumbing_p8/<key>/`` with a receipt, then writes
``p12/manifests/plumbing_d_jobs.json`` (``stage_d_worker_p12.py --product-source p8_store``,
100,000 TRICERATOPS draws, stamped under p10.0 and p12.0, packets under
``docs/packets/audit_p12/plumbing_p8/``). Every copied record is a ledgered seen P8 record.

Superseded 2026-09-23 (AMENDMENTS_P12.md, 1d): ``check`` reads the registered measurement updates of
``p12/manifests/plumbing_expectation_updates.json``. 1d allows an expectation to change only for a live
measurement, recorded with both values; each update names the key, the rule set, the original
expectation, the observed outcome and the measurement that moved it, and it applies only while the
observed outcome equals the recorded one, so an update can never absorb a later or different change.
``resume --phase plumbing_d_rerun --keys K...`` re-runs, once, the named keys after a defect is fixed (1d: fix once and
re-run; a second failure is STOP-3): the same runtimes with the phase ``plumbing_d_rerun``, so the re-run writes its own
receipt (``results/funnel/plumbing_d_rerun/D/``) and the first receipt stays; ``check`` requires that phase CLOSED and
reads the re-run receipt for those keys.
"""
from p12_common import REPO, ROOT, DATA, read, write, sha, utc, append_jsonl
from part0_plan_p12 import source_snapshot
import argparse
import csv
import json
import shutil
from pathlib import Path

P8 = REPO / 'data/survey/p8'
KEYS = ('tic230120862_P16.7959', 'tic80256158_P10.8184', 'tic144277542_P12.9812', 'tic155895971_P13.1279',
        'tic154566869_P8.9053', 'tic404927114_P27.5436')
EXPECTED = {  # PROMPT_P12.md 1d, from p10/results/tier_rederivation.csv
    'tic230120862_P16.7959': {'p10.0': ('KILL', 'K9', ['K9', 'H1', 'H2']), 'p12.0': ('KILL', 'K9')},
    'tic80256158_P10.8184': {'p10.0': ('KILL', 'K8', ['K8', 'K9']), 'p12.0': ('KILL', 'K8')},
    'tic154566869_P8.9053': {'p10.0': ('KILL', 'K8', ['K8', 'H1']), 'p12.0': ('KILL', 'K8')},
    'tic155895971_P13.1279': {'p10.0': ('KILL', 'K8', ['K8', 'K9']), 'p12.0': ('KILL', 'K8')},
    'tic404927114_P27.5436': {'p10.0': ('HOLD', 'H3', None), 'p12.0': ('HOLD', 'H3')},
    'tic144277542_P12.9812': {'p10.0': ('SUBMIT', None, None), 'p12.0': ('HOLD', 'H5', 'or KILL K10 if admitted and firing')},
}
WORKER = 'p12/protocol/stage_d_worker_p12.py'
HISTORICAL = ('scripts/audit_p5.py', 'scripts/revet_p6.py', 'scripts/p8_funnel.py', 'scripts/survivor_packets.py',
              'scripts/p8_eb_difference_image.py', 'scripts/p8_eb_aperture.py', 'src/tesshunter/verdict_tiers.py',
              'src/tesshunter/audit_rules.py', 'src/tesshunter/fpp.py', 'src/tesshunter/centroid.py',
              'src/tesshunter/packet.py', 'src/tesshunter/secondary.py', 'src/tesshunter/event_vet.py')


def _copy(source, destination, rows):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha(destination) != sha(source):
            raise RuntimeError('Existing plumbing copy differs: ' + destination.as_posix())
    else:
        shutil.copyfile(source, destination)
    rows.append(dict(source=source.relative_to(REPO).as_posix(), destination=destination.relative_to(REPO).as_posix(),
                     sha256=sha(destination), source_sha256=sha(source)))


def _table(path, predicate):
    with path.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, [row for row in reader if predicate(row)]


def plan():
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Build manifests only between phases')
    hard = read(ROOT / 'manifests/hard_stop_p12.json')['per_star']
    targets = {int(r['tic_id']): r for r in csv.DictReader((REPO / 'data/survey/targets_p8.csv').open(encoding='utf-8-sig'))}
    copies, jobs = [], []
    sources = dict(source_snapshot())
    for name in HISTORICAL:
        sources[name] = sha(REPO / name)
    for key in KEYS:
        tic = int(key.split('_P')[0][3:])
        root = DATA / 'plumbing_p8' / key
        for folder in ('stageA', 'secondary', 'stageB', 'stageC', 'pixel_followup'):
            _copy(P8 / folder / f'{key}.json', root / folder / f'{key}.json', copies)
        for path in sorted((P8 / 'tls').glob(key + '*')):
            _copy(path, root / 'tls' / path.name, copies)
        _copy(P8 / 'neighbours' / f'tic{tic}.json', DATA / 'plumbing_p8/neighbour_tables' / f'tic{tic}.json', copies)
        for table, predicate in (('survivors.csv', lambda r: r['tic_id'] == str(tic) and f"tic{tic}_P{float(r['period_days']):.4f}" == key),
                                 ('candidates.csv', lambda r: r['tic_id'] == str(tic))):
            fields, rows = _table(P8 / table, predicate)
            if table == 'survivors.csv' and len(rows) != 1:
                raise RuntimeError(f'{key}: expected one survivor row')
            out = root / table
            if not out.exists():
                with out.open('x', newline='', encoding='utf-8') as stream:
                    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
                    writer.writeheader(); writer.writerows(rows)
            copies.append(dict(source=(P8 / table).relative_to(REPO).as_posix(), destination=out.relative_to(REPO).as_posix(),
                               sha256=sha(out), rows=len(rows), selection=f'rows of TIC {tic}' + (' at this key' if table == 'survivors.csv' else '')))
            if table == 'survivors.csv':
                survivor = rows[0]
        star = targets[tic]
        nb = DATA / 'plumbing_p8/neighbour_tables' / f'tic{tic}.json'
        runtime = dict(candidate_id=key, key=key, tic_id=tic, period=float(survivor['period_days']),
                       depth_ppt=float(survivor['depth_ppt']), phase='plumbing_d', root=root.relative_to(REPO).as_posix(),
                       route='normal', redact_catalogue=False, product_source='p8_store', arm='archival', rules=['p10.0', 'p12.0'],
                       crossmatch_star=hard[str(tic)], tce_association=None,
                       star={k: float(star[k]) for k in ('radius_rsun', 'mass_msun', 'teff_k', 'tmag', 'ra_deg', 'dec_deg')},
                       neighbours_reference=dict(path=nb.relative_to(REPO).as_posix(), sha256=sha(nb)),
                       packet_subtree='plumbing_p8', population_tier='core', n_draws=100000, source_hashes=sources,
                       review_reference=dict(path=(root / 'pixel_followup' / f'{key}.json').relative_to(REPO).as_posix(),
                                             source='P8 pixel review (HANDOFF_P8.md); KILL read as the K9 artefact decision'),
                       job=dict(rank=int(survivor['rank']), tic_id=tic, period=float(survivor['period_days']),
                                depth_ppt=float(survivor['depth_ppt'])))
        path = ROOT / 'manifests/plumbing_d_runtime' / f'{key}.json'
        if not path.exists():
            write(path, runtime)
        elif read(path) != runtime:
            raise RuntimeError('Existing plumbing runtime differs: ' + key)
        jobs.append(dict(job_id=key, attempt=1, arguments=[WORKER, path.relative_to(REPO).as_posix(), sha(path)],
                         result_path=f'p12/results/funnel/plumbing_d/D/{key}.json',
                         source_hashes=dict(sources, **{path.relative_to(REPO).as_posix(): sha(path)})))
        for row in copies:
            if f'tic{tic}' in row['source']:
                append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=tic, stage='Part 1d plumbing input copy (seen P8 record)',
                    path=row['source'], reader='stage_d_plan_p12.py plumbing', prompt_of_origin='P8', content='copied by script; not displayed'))
    write(ROOT / 'manifests/plumbing_p8_copy.json', dict(utc=utc(), keys=list(KEYS), files=copies,
          note='The prompt names stageA, secondary, stageB, stageC and neighbours; the tls records (Stage C output read by D), '
               'the P8 reviewer pixel_followup record (the K9 review) and the key rows of survivors.csv / candidates.csv are copied '
               'too because D reads them; nothing else of P8 is copied.', expected=EXPECTED), replace=(ROOT / 'manifests/plumbing_p8_copy.json').exists())
    write(ROOT / 'manifests/plumbing_d_jobs.json', jobs, replace=(ROOT / 'manifests/plumbing_d_jobs.json').exists())
    from ledger_p12 import price_phase
    price_phase('plumbing_d', ROOT / 'manifests/plumbing_d_jobs.json')
    print(json.dumps(dict(jobs=len(jobs), files_copied=len(copies))), flush=True)
    return jobs


UPDATES = ROOT / 'manifests/plumbing_expectation_updates.json'


def _expectations():
    """EXPECTED with the registered live-measurement updates applied (1d), and the updates themselves."""
    expected = {key: dict(value) for key, value in EXPECTED.items()}
    updates = read(UPDATES)['updates'] if UPDATES.exists() else []
    for row in updates:
        if row.get('cause_class') != 'LIVE_MEASUREMENT':
            raise RuntimeError('1d permits an expectation update only for a live measurement')
        original = tuple(row['original'][:2]) if row['original'] else None
        current = EXPECTED[row['key']][row['rules']]
        if original != tuple(current[:2]):
            raise RuntimeError('Expectation update does not start from the registered expectation')
        expected[row['key']][row['rules']] = (row['observed']['verdict'], row['observed']['deciding'],
                                              row['observed'].get('fired') if row['rules'] == 'p10.0' else None)
    return expected, updates


def check():
    """The judged table ``p12/results/part1/plumbing_d.json``: each record against 1d.

    A difference is listed with both values; whether a live measurement caused it (a new FPP
    draw, a centroid, the fixed-aperture record that now exists for 404927114) is the lead's
    diagnosis, recorded in AMENDMENTS_P12.md; any other difference is a defect (fix once)."""
    closure = read(ROOT / 'results/controllers/plumbing_d/closure.json')
    resumes = [ROOT / f'results/controllers/{name}/closure.json' for name in ('plumbing_d_resume_2', 'plumbing_d_resume')]
    rerun_closure = ROOT / 'results/controllers/plumbing_d_rerun/closure.json'
    rerun_keys = set()
    if rerun_closure.exists():
        closed = read(rerun_closure)
        if closed.get('status') != 'CLOSED' or not closed.get('all_owned_workers_closed'):
            raise RuntimeError('plumbing_d_rerun did not close cleanly')
        rerun_keys = {j['job_id'] for j in read(ROOT / 'results/controllers/plumbing_d_rerun/launch.json')['frozen_jobs']}
    resume_path = next((r for r in resumes if r.exists() and read(r).get('status') == 'CLOSED'), resumes[0])
    if closure['status'] != 'CLOSED' or not closure['all_owned_workers_closed']:
        # STOP-6 (2026-09-23, a pricing defect) interrupted plumbing_d; the user continued it and the
        # reconciled remainder ran as plumbing_d_resume (recover_p12.py; CONTINUE_plumbing_d).
        recovery = read(ROOT / 'manifests/recovery_plumbing_d.json')
        resumed = read(resume_path) if resume_path.exists() else {}
        if (recovery.get('status') != 'RECONCILED' or not (ROOT / 'manifests/CONTINUE_plumbing_d').exists()
                or resumed.get('status') != 'CLOSED' or not resumed.get('all_owned_workers_closed')):
            raise RuntimeError('plumbing_d is neither closed nor reconciled and resumed')
    k10 = read(ROOT / 'results/part1/k10_calibration.json')
    expectations, updates = _expectations()
    rows, differences = [], []
    for key in KEYS:
        receipt_path = ROOT / f"results/funnel/{'plumbing_d_rerun' if key in rerun_keys else 'plumbing_d'}/D/{key}.json"
        receipt = read(receipt_path) if receipt_path.exists() else {}
        record = read(REPO / receipt['stage_d_record']) if receipt.get('stage_d_record') else {}
        tiers = record.get('tiers_by_rules') or {}
        row = dict(key=key, status=receipt.get('status'), errors=receipt.get('errors'), packet=receipt.get('packet'))
        for rules in ('p10.0', 'p12.0'):
            t = tiers.get(rules) or {}
            order = t.get('k_order', []) + t.get('h_order', []) or [n for n in (t.get('conditions') or {})]
            fired = [n for n in order if ((t.get('conditions') or {}).get(n) or {}).get('fired')]
            expected = expectations[key][rules]
            got = (t.get('verdict'), t.get('deciding_condition'))
            ok = got == expected[:2]
            if rules == 'p12.0' and key == 'tic144277542_P12.9812' and k10['word'] == 'K10_KILL':
                ok = ok or got == ('KILL', 'K10')
            update = next((u for u in updates if u['key'] == key and u['rules'] == rules), None)
            if update and sorted(fired) != sorted(update['observed'].get('fired') or []):
                ok = False  # an update applies only to the outcome it recorded
            # The fired set is registered for the p10.0 KILLs (1d); elsewhere the verdict and deciding condition.
            listed = expected[2] if rules == 'p10.0' and isinstance(expected[2], list) else None
            fired_ok = listed is None or sorted(fired) == sorted(listed)
            row[rules] = dict(verdict=got[0], deciding=got[1], fired=fired, expected=list(expected[:2]),
                              expected_fired=expected[2] if rules == 'p10.0' else None, match=bool(ok and fired_ok),
                              not_measurable=t.get('not_measurable'),
                              candidate_tier=(t.get('candidate_tier') or {}).get('candidate_tier'))
            if not (ok and fired_ok):
                differences.append(dict(key=key, rules=rules, got=dict(verdict=got[0], deciding=got[1], fired=fired),
                                        expected=dict(verdict=expected[0], deciding=expected[1],
                                                      fired=expected[2] if rules == 'p10.0' else None)))
        row['ctoi_fields_complete'] = bool(receipt.get('packet')) and all(
            k in read(REPO / receipt['packet'] / 'ctoi_fields.json') for k in ('tiers', 'validation_status', 'candidate_tier'))
        rows.append(row)
    status = 'MATCH' if not differences and all(r['status'] == 'COMPLETE' and r['ctoi_fields_complete'] for r in rows) else 'DIFFERENCES_REQUIRE_DIAGNOSIS'
    write(ROOT / 'results/part1/plumbing_d.json', dict(utc=utc(), status=status, rows=rows, differences=differences,
          k10_word=k10['word'], expectations=EXPECTED, expectation_updates=updates,
          updates_sha256=sha(UPDATES) if UPDATES.exists() else None, rule='PROMPT_P12.md 1d: a live-measurement difference is recorded with '
          'both values and the expectation updated in AMENDMENTS_P12.md; any other difference is a defect, fixed once; a second failure is STOP-3'),
          replace=(ROOT / 'results/part1/plumbing_d.json').exists())
    print(json.dumps(dict(status=status, differences=len(differences))), flush=True)
    return 0 if status == 'MATCH' else 3


def resume(phase='plumbing_d_resume', only_incomplete=False, keys=None):
    """The reconciled plumbing jobs (``recover_p12.py plumbing_d``) as ``plumbing_d_resume``: the same
    runtimes copied under ``plumbing_d_resume_runtime/`` (the I/O guard log is per runtime folder), the
    same receipts, sources re-pinned to the current (chain-verified) tree."""
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Build manifests only between phases')
    if not (ROOT / 'manifests/CONTINUE_plumbing_d').exists():
        raise RuntimeError('Resumption requires the user decision CONTINUE_plumbing_d')
    recovery = read(ROOT / 'manifests/recovery_plumbing_d.json')
    if recovery['status'] != 'RECONCILED':
        raise RuntimeError('plumbing_d is not reconciled')
    sources = dict(source_snapshot())
    for name in HISTORICAL:
        sources[name] = sha(REPO / name)
    jobs = []
    for job in read(REPO / recovery['resume_manifest']):
        receipt = REPO / job['result_path']
        if only_incomplete and receipt.exists() and read(receipt).get('status') == 'COMPLETE':
            continue
        if keys is not None and job['job_id'] not in keys:
            continue
        original = REPO / job['arguments'][1]
        runtime = dict(read(original), source_hashes=sources)
        if phase == 'plumbing_d_rerun':
            runtime['phase'] = phase
            job = dict(job, result_path=f"p12/results/funnel/{phase}/D/{job['job_id']}.json")
        path = ROOT / f'manifests/{phase}_runtime' / original.name
        write(path, runtime)
        jobs.append(dict(job_id=job['job_id'], attempt=1, arguments=[WORKER, path.relative_to(REPO).as_posix(), sha(path)],
                         result_path=job['result_path'], source_hashes=dict(sources, **{path.relative_to(REPO).as_posix(): sha(path)}),
                         recovery_of='plumbing_d', original_runtime_sha256=sha(original)))
    out = ROOT / f'manifests/{phase}_jobs.json'
    write(out, jobs)
    from ledger_p12 import price_phase
    price_phase(phase, out)
    print(json.dumps(dict(resume_jobs=len(jobs))), flush=True)
    return jobs


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['plumbing', 'check', 'resume'])
    parser.add_argument('--phase', default='plumbing_d_resume')
    parser.add_argument('--only-incomplete', action='store_true')
    parser.add_argument('--keys', nargs='*')
    args = parser.parse_args(argv)
    if args.action == 'plumbing':
        plan()
        return 0
    if args.action == 'resume':
        resume(args.phase, args.only_incomplete, set(args.keys) if args.keys else None)
        return 0
    return check()


if __name__ == '__main__':
    raise SystemExit(main())
