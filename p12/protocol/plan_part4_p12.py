"""Part 4 planners for the independent negative sets (4a, 4b, LB1c) and the natural false-alarm set (4d).

Sets: ``ttt`` (``ttt_negatives.csv``, phases ``neg_ttt_*``, LB1a/LB1b) and ``ttta`` (``ttt_adjacent_negatives.csv``,
phases ``neg_ttta_*``, LB1c, reported only). Every path a worker reads or writes uses the registered alias
"tenk" for "ttt" (blind_io_p12 denies any "ttt" path component to a worker). Forced route (4a): search ->
pre-gate -> A -> S and B recorded -> C on every A passer whatever S and B decided -> D on every C passer and
UNRESOLVED case, redacted (K0 status, K5 catalogue clause, H4 recorded and excluded). No worker opens the TTT
ephemerides; the evaluator scores after the prediction lock. Natural set (4d): the E_cal false-alarm stars' A
passers of Part 2's frozen arm, C forced, D not redacted.
Actions: inputs <set>; download <set> <phase>; verify <set> <phase>; neighbours <set> <phase>; search <set> <phase>;
stage <A|S|B> <set> <phase> <search_phase>; c <set> <phase> <search_phase>; d <set> <phase> <c_phase>;
fa_c <phase>; fa_d <phase> <c_phase>.
"""
from p12_common import REPO, ROOT, DATA, read, write, sha, utc, append_jsonl
import argparse
import csv
import json
from pathlib import Path

import plan_part2_p12 as P2

SETS = {'ttt': dict(manifest='manifests/ttt_negatives.csv', alias='tenk', tier='negative_ttt_domain'),
        'ttta': dict(manifest='manifests/ttt_adjacent_negatives.csv', alias='tenka', tier='negative_ttt_adjacent')}
STAR_MAP = dict(radius_rsun='rad', mass_msun='mass', teff_k='Teff', tmag='Tmag', ra_deg='ra', dec_deg='dec')


def _alias(text):
    return text.replace('ttt', 'tenk')


def _stars(name):
    rows = P2._csv(ROOT / SETS[name]['manifest'])
    out = {}
    for r in rows:
        star = {}
        for key, column in STAR_MAP.items():
            try:
                star[key] = float(r[column])
            except (TypeError, ValueError):
                star[key] = None
        out[int(r['tic_id'])] = star
    return out


def inputs(name):
    """``p12/manifests/part4/<alias>_targets.csv`` in the P8 target columns (neighbours, D, stellar inputs)."""
    P2._owner_free()
    stars = _stars(name)
    path = ROOT / f"manifests/part4/{SETS[name]['alias']}_targets.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['tic_id', *STAR_MAP], lineterminator='\n')
        writer.writeheader()
        for tic in sorted(stars):
            writer.writerow(dict(tic_id=tic, **{k: ('' if v is None else v) for k, v in stars[tic].items()}))
    missing = sorted(t for t, s in stars.items() if any(v is None for v in s.values()))
    write(ROOT / f"manifests/part4/{SETS[name]['alias']}_inputs.json", dict(utc=utc(), set=name, stars=len(stars),
          targets=path.relative_to(REPO).as_posix(), targets_sha256=sha(path), stellar_parameters_missing=missing),
          replace=(ROOT / f"manifests/part4/{SETS[name]['alias']}_inputs.json").exists())
    return path


def _tics(name):
    return sorted(_stars(name))


def download(name, phase):
    P2._owner_free()
    from build_batches_p12 import job
    jobs = []
    for tic in _tics(name):
        index = REPO / f'data/survey/audit_lc/tic{tic}/index.json'
        if index.exists() and read(index).get('n_failed', 0) == 0:
            continue
        jobs.append(job(tic, 1, index.exists()))
    return P2._write_jobs(phase, jobs)


def verify(name, phase):
    P2._owner_free()
    import build_input_jobs_p12 as B
    sources = P2._sources()
    jobs = []
    todo = [t for t in _tics(name) if not (ROOT / f'results/native_noise/archival/tic{t}.json').exists()]
    missing = [t for t in todo if not (ROOT / f'manifests/input_jobs/tic{t}.json').exists()]
    if missing:
        # One walk of the product caches for every star (build_input_jobs_p12 walks both caches per call).
        B.build(missing, output=ROOT / f'manifests/part4/{SETS[name]["alias"]}_input_job_rows.json')
    for tic in todo:
        job_path = ROOT / f'manifests/input_jobs/tic{tic}.json'
        jobs.append(dict(job_id=f'tic{tic}', arguments=['p12/protocol/verify_prepare_p12.py', str(tic)], attempt=1,
                         result_path=f'p12/results/native_noise/archival/tic{tic}.json',
                         source_hashes=dict(sources, **{job_path.relative_to(REPO).as_posix(): sha(job_path)})))
    return P2._write_jobs(phase, jobs)


def neighbours(name, phase):
    P2._owner_free()
    alias = SETS[name]['alias']
    targets = f'p12/manifests/part4/{alias}_targets.csv'
    jobs = [dict(job_id=f'neighbours_{alias}', attempt=1, arguments=['p12/protocol/neighbours_set_p12.py', alias, targets, '--online'],
                 result_path=f'p12/results/neighbour_sets/{alias}.json', source_hashes=P2._sources(), stars=len(_tics(name)))]
    return P2._write_jobs(phase, jobs)


def search(name, phase):
    P2._owner_free()
    alias = SETS[name]['alias']
    stars = _stars(name)
    sources = P2._sources()
    run = f'data/survey/p12/negatives/{alias}/runs/survey_p10'
    jobs = []
    for tic in sorted(stars):
        noise = ROOT / f'results/native_noise/archival/tic{tic}.json'
        if not noise.exists() or read(noise)['status'] != 'INPUT_ELIGIBLE':
            continue  # < 3 usable sectors: leaves N (4b); recorded by the evaluator
        # Set-prefixed job ids: the LB1a star is also in LB1c, and the search I/O log is exclusive per runtime stem.
        jobs.append(P2._search_job(tic, f'{alias}_tic{tic}', stars[tic], P2._host_prepared('archival', tic), run, sources, _alias(phase)))
    return P2._write_jobs(phase, jobs)


def _neighbour_ref(tic):
    path = DATA / f'neighbours/tic{tic}.json'
    return dict(path=path.relative_to(REPO).as_posix(), sha256=sha(path)) if path.exists() else None


def cases(name, search_phase):
    alias = SETS[name]['alias']
    label = f'neg_{alias}'
    manifest = ROOT / f'manifests/part4/{label}_cases.json'
    if manifest.exists():
        return read(manifest)
    locked = P2._locked(search_phase)
    stars = _stars(name)
    sources = P2._sources()
    rows, counts = [], dict(stars_complete=0, unknown=0, accepted=0, pregate=0)
    for job in locked['jobs']:
        if job['status'] != 'COMPLETE':
            counts['unknown'] += 1
            continue
        counts['stars_complete'] += 1
        result = read(REPO / job['result_path'])
        tic = int(result['tic_id'])
        collected = P2.collect_rows(result, stars[tic])
        counts['accepted'] += len(collected)
        for row in collected:
            if not row['passes_pregate']:
                continue
            counts['pregate'] += 1
            cid = f"tic{tic}_p{int(row['planet_num']):02d}"
            base = P2._case_runtime(label, name, cid, tic, row, collected, stars[tic], dict(kind='policy', arm='archival'),
                                    _neighbour_ref(tic), sources, route='forced_negatives', population_tier=SETS[name]['tier'])
            rows.append(dict(candidate_id=cid, tic_id=tic, kind='negative', runtime=base.relative_to(REPO).as_posix(),
                             runtime_sha256=sha(base), pregate=True))
    result = dict(utc=utc(), label=label, set=name, search_phase=search_phase, counts=counts, cases=rows,
                  lock_sha256=sha(ROOT / f'manifests/{search_phase}_predictions_lock.json'))
    write(manifest, result)
    return result


def stage(stage_name, name, phase, search_phase):
    """Forced route: A on every pre-gate passer; S and B recorded on every A passer."""
    P2._owner_free()
    collected = cases(name, search_phase)
    label = collected['label']
    jobs = []
    for row in collected['cases']:
        a, _ = P2._receipt(label, 'A', row['candidate_id'])
        if stage_name == 'A' or P2._decision(a) == 'PASS':
            jobs.append(P2._stage_job(stage_name, label, row))
    return P2._write_jobs(phase, jobs)


def c(name, phase, search_phase):
    P2._owner_free()
    collected = cases(name, search_phase)
    label = collected['label']
    jobs = [P2.c_job(label, row, 'forced_negatives') for row in collected['cases']
            if P2._decision(P2._receipt(label, 'A', row['candidate_id'])[0]) == 'PASS']
    return P2._write_jobs(phase, jobs)


def d_runtime(phase, label, row, redact, route, packet_subtree, population_tier, sources, tce_association=None):
    """A Stage D runtime (stage_d_worker_p12 fields) for one case of a closed C phase."""
    from crossmatch_p12 import crossmatch_step
    base = read(REPO / row['runtime'] if 'runtime' in row else REPO / row['base_runtime'])
    tic, cand = int(base['tic_id']), base['candidate']
    key = f"tic{tic}_P{float(cand['period_days']):.4f}"
    star = base['star']
    xm = crossmatch_step(dict(tic_id=tic, ra_deg=star['ra_deg'], dec_deg=star['dec_deg'], period=float(cand['period_days'])))
    nb = base['neighbours_reference'] or _neighbour_ref(tic)
    runtime = dict(candidate_id=base['candidate_id'], key=key, tic_id=tic, period=float(cand['period_days']),
                   depth_ppt=float(cand['depth_ppt']), phase=phase, root=base['root'], route=route, redact_catalogue=redact,
                   product_source='policy', arm=base['products'].get('arm', 'archival'), rules=['p12.0'], crossmatch_star=xm,
                   tce_association=tce_association, star=star, neighbours_reference=nb, packet_subtree=packet_subtree,
                   population_tier=population_tier, n_draws=100000, source_hashes=sources, review_reference=None,
                   job=dict(rank=int(cand.get('rank') or 0), tic_id=tic, period=float(cand['period_days']),
                            depth_ppt=float(cand['depth_ppt'])))
    return runtime


def _d_jobs(phase, label, closure, redact, route, packet_subtree, tier):
    from stage_d_plan_p12 import WORKER, HISTORICAL
    sources = P2._sources()
    for name in HISTORICAL:
        sources[name] = sha(REPO / name)
    jobs = []
    runtime_folder = _alias(f'{phase}_runtime')
    for row in closure['rows']:
        if row['decision'] not in ('PASS', 'UNRESOLVED'):
            continue
        base_path = ROOT / f"manifests/runtime/{row['label']}/{row['candidate_id']}.json"
        runtime = d_runtime(phase, label, dict(runtime=base_path.relative_to(REPO).as_posix()), redact, route, packet_subtree, tier, sources)
        path = ROOT / f'manifests/{runtime_folder}/{row["candidate_id"]}.json'
        write(path, runtime)
        # The one recorded retry pass runs under its own phase name, so its receipt and I/O log never meet attempt 1's.
        retry_path = ROOT / f'manifests/{_alias(phase + "_retry_runtime")}/{row["candidate_id"]}.json'
        write(retry_path, dict(runtime, phase=phase + '_retry'))
        rel, retry_rel = path.relative_to(REPO).as_posix(), retry_path.relative_to(REPO).as_posix()
        jobs.append(dict(job_id=row['candidate_id'], attempt=1, arguments=[WORKER, rel, sha(path)],
                         result_path=f"p12/results/funnel/{_alias(phase)}/D/{row['candidate_id']}.json",
                         retry_arguments=[WORKER, retry_rel, sha(retry_path)],
                         retry_result_path=f"p12/results/funnel/{_alias(phase + '_retry')}/D/{row['candidate_id']}.json",
                         source_hashes=dict(sources, **{rel: sha(path), retry_rel: sha(retry_path)})))
        append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=runtime['tic_id'],
            stage=f'Part 4 D planning ({phase}): case identity and C decision only', path=rel, reader='plan_part4_p12.py',
            prompt_of_origin='P12', content='candidate ephemeris passed to the D worker; not displayed'))
    return P2._write_jobs(phase, jobs)


def d(name, phase, c_phase):
    P2._owner_free()
    alias = SETS[name]['alias']
    closure = read(ROOT / f'results/funnel/neg_{alias}/C_closure_{c_phase}.json')
    return _d_jobs(phase, f'neg_{alias}', closure, True, 'forced_negatives', f'neg_{alias}', SETS[name]['tier'])


def fa_c(phase):
    """4d: C on every A passer of the E_cal false-alarm stars from Part 2's frozen arm."""
    P2._owner_free()
    arm = 'archival' if read(ROOT / 'results/part2/photometry_decision.json')['decision'] != 'ADOPT_SML' else 'sml'
    label = P2.LABEL[arm]
    collected = read(ROOT / f'manifests/part2/{label}_cases.json')
    jobs = [P2.c_job(label, row, 'forced_negatives') for row in collected['cases']
            if row['kind'] == 'false_alarm' and P2._decision(P2._receipt(label, 'A', row['candidate_id'])[0]) == 'PASS']
    for job in jobs:
        append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=None, stage=f'Part 4d natural-load C planning ({phase})',
            path=job['arguments'][1], reader='plan_part4_p12.py fa_c', prompt_of_origin='P12',
            content='A PASS decision of an E_cal false-alarm case (after the freeze), not displayed'))
    return P2._write_jobs(phase, jobs)


def fa_d(phase, c_phase):
    P2._owner_free()
    arm = 'archival' if read(ROOT / 'results/part2/photometry_decision.json')['decision'] != 'ADOPT_SML' else 'sml'
    label = P2.LABEL[arm]
    closure = read(ROOT / f'results/funnel/{label}/C_closure_{c_phase}.json')
    return _d_jobs(phase, label, closure, False, 'forced_negatives', 'neg_fa', 'core_natural_load')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['inputs', 'download', 'verify', 'neighbours', 'search', 'stage', 'c', 'd', 'fa_c', 'fa_d'])
    parser.add_argument('args', nargs='*')
    a = parser.parse_args(argv)
    functions = dict(inputs=inputs, download=download, verify=verify, neighbours=neighbours, search=search, stage=stage,
                     c=c, d=d, fa_c=fa_c, fa_d=fa_d)
    functions[a.action](*a.args)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
