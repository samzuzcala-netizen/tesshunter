"""Part 5 planners: the E1 extension (5a), the final search (5b), collect and the funnel (5c to 5e).

Actions (each writes ``p12/manifests/<phase>_jobs.json`` and prices it for STOP-6):
  e1_targets                          ``manifests/part5/e1_targets.csv`` in the P8 star columns (TIC v8 fields)
  download_pilot <phase>              the first 50 E1 stars by ascending TIC (``build_batches_p12.job``)
  download_batch <phase> <n>          batch n (1-based) of 100 of the remaining E1 stars, ascending TIC
  pilot_rates <phase>                 per-star bytes and wall of the pilot, into ``manifests/part5/e1_pilot_rates.json``
  neighbours <phase>                  the E1 neighbour tables (``neighbours_set_p12.py`` label ``e1``)
  verify <phase>                      ``verify_prepare_p12.py`` for every downloaded E1 star
  ext_sample                          300 eligible E1 stars by SHA-256 of ``20260920:ext_cal:<TIC>``, then the 600
                                      injections (``make_injection_spec_p12.py``, 2 per star, seed 20260920, 1-4 Re,
                                      0.5-30 d in four log bins)
  ext_prepare / ext_search <phase>    preparation and the survey_p10 search (injected arrays + the 300 uninjected)
  ext_stage <A|S> <phase>             A on every recovered injection and false-alarm pre-gate passer; S on A passers
  final_search <phase>                every eligible core star and (E1) every eligible extension star
  collect <phase>                     the locked search into ``DATA/final/funnel/{candidates,survivors}.csv`` and
                                      ``collect_p12.json``, one runtime per pre-gate passer
  stage <A|S|B> <phase>               A on every pre-gate passer; S on A passers plus a seeded 10% of A failures
                                      (seed 20260920); B on S PASS or HOLD
  c <phase>                           C on every B passer, ordered by ``ranking.score_v2`` for scheduling only
  neighbours_final <phase>            ``final_neighbours``: stars with a C PASS or UNRESOLVED case and no table
  d <phase>                           D on every C PASS and UNRESOLVED case (p12.0, F7 from the sidecar after the lock)
  novelty <phase>                     the TOI / CTOI novelty re-check job (``novelty_p12.py``)
Every final-population record opened here is a planning read of identity and decision only, ledgered.
"""
from p12_common import REPO, ROOT, DATA, read, write, sha, utc, append_jsonl, host_hash
import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

import plan_part2_p12 as P2

E1 = ROOT / 'manifests/targets_ext_E1.csv'
E1_STARS = ROOT / 'manifests/part5/e1_targets.csv'
STAR_MAP = dict(radius_rsun='rad', mass_msun='mass', teff_k='Teff', tmag='Tmag', ra_deg='ra', dec_deg='dec')
LABEL = 'final'
EXT_LABEL = 'ext_cal'
PILOT = 50
BATCH = 100
S_FAIL_FRACTION, S_FAIL_SEED = 0.10, 20260920


def _tier():
    return read(ROOT / 'manifests/decision_point_1.json')['tier']


def _e1_rows():
    return {int(r['tic_id']): r for r in P2._csv(E1)}


def e1_targets():
    P2._owner_free()
    rows = _e1_rows()
    E1_STARS.parent.mkdir(parents=True, exist_ok=True)
    with E1_STARS.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['tic_id', *STAR_MAP], lineterminator='\n')
        writer.writeheader()
        for tic in sorted(rows):
            writer.writerow(dict(tic_id=tic, **{k: rows[tic][c] for k, c in STAR_MAP.items()}))
    return E1_STARS


def _e1_stars():
    out = {}
    for r in P2._csv(E1_STARS):
        star = {}
        for key in STAR_MAP:
            try:
                star[key] = float(r[key])
            except (TypeError, ValueError):
                star[key] = None
        out[int(r['tic_id'])] = star
    return out


def _download_order():
    from build_batches_p12 import job
    tics = sorted(_e1_rows())
    pending = []
    for tic in tics:
        index = REPO / f'data/survey/audit_lc/tic{tic}/index.json'
        if index.exists() and read(index).get('n_failed', 0) == 0:
            continue
        pending.append(tic)
    return tics, pending, job


def download_pilot(phase):
    P2._owner_free()
    tics, pending, job = _download_order()
    chosen = tics[:PILOT]
    jobs = [job(t, 1, (REPO / f'data/survey/audit_lc/tic{t}/index.json').exists()) for t in chosen if t in set(pending)]
    write(ROOT / 'manifests/part5/e1_download_plan.json', dict(utc=utc(), stars=len(tics), pilot=chosen, batch_size=BATCH,
          n_batches=int(np.ceil((len(tics) - PILOT) / BATCH)), order='ascending TIC identity'),
          replace=(ROOT / 'manifests/part5/e1_download_plan.json').exists())
    return P2._write_jobs(phase, jobs)


def download_batch(phase, n):
    P2._owner_free()
    tics, pending, job = _download_order()
    rest = tics[PILOT:]
    n = int(n)
    chosen = rest[(n - 1) * BATCH:n * BATCH]
    jobs = [job(t, 1, (REPO / f'data/survey/audit_lc/tic{t}/index.json').exists()) for t in chosen if t in set(pending)]
    path = ROOT / f'manifests/{phase}_jobs.json'
    if path.exists():
        raise FileExistsError(path)
    write(path, jobs)
    # 5a: the pilot's per-star queue-s replaces the 12.9-s unit when higher.
    rates = ROOT / 'manifests/part5/e1_pilot_rates.json'
    measured = read(rates)['queue_s_per_star'] if rates.exists() else None
    from ledger_p12 import price_phase
    price_phase(phase, path, unit_override=dict(download_queue_seconds=max(12.9, measured or 0)))
    return path


def pilot_rates(phase):
    """Per-star bytes and wall of the pilot; 5a: they replace the forecast's if higher."""
    closure = read(ROOT / f'results/controllers/{phase}/closure.json')
    walls, sizes = [], []
    for path in sorted((ROOT / f'results/controllers/{phase}/attempts').glob('*.json')):
        attempt = read(path)
        walls.append(float(attempt.get('wall_seconds') or 0))
        tic = int(attempt['job_id'][3:])
        folder = REPO / f'data/survey/audit_lc/tic{tic}'
        sizes.append(sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()) if folder.exists() else 0)
    result = dict(utc=utc(), phase=phase, stars=len(walls), wall_per_star_s=float(np.mean(walls)) if walls else None,
                  queue_s_per_star=float(closure['queue_hours']) * 3600 / max(len(walls), 1),
                  bytes_per_star=float(np.mean(sizes)) if sizes else None, forecast_queue_s_per_star=12.9,
                  forecast_bytes_per_star=48e6)
    result['replaces_forecast'] = bool((result['queue_s_per_star'] or 0) > 12.9 or (result['bytes_per_star'] or 0) > 48e6)
    write(ROOT / 'manifests/part5/e1_pilot_rates.json', result, replace=(ROOT / 'manifests/part5/e1_pilot_rates.json').exists())
    print(json.dumps(result), flush=True)
    return result


def neighbours(phase):
    P2._owner_free()
    targets = E1_STARS.relative_to(REPO).as_posix()
    jobs = [dict(job_id='neighbours_e1', attempt=1, arguments=['p12/protocol/neighbours_set_p12.py', 'e1', targets, '--online'],
                 result_path='p12/results/neighbour_sets/e1.json', source_hashes=P2._sources(), stars=len(_e1_rows()))]
    return P2._write_jobs(phase, jobs)


def verify(phase):
    P2._owner_free()
    import build_input_jobs_p12 as B
    sources = P2._sources()
    jobs = []
    # A star whose acquisition failed after its retry has no index: it is not verified and stays UNKNOWN.
    todo = [t for t in sorted(_e1_rows()) if not (ROOT / f'results/native_noise/archival/tic{t}.json').exists()
            and (REPO / f'data/survey/audit_lc/tic{t}/index.json').exists()]
    missing = [t for t in todo if not (ROOT / f'manifests/input_jobs/tic{t}.json').exists()]
    if missing:
        B.build(missing, output=ROOT / 'manifests/part5/e1_input_job_rows.json')
    for tic in todo:
        job_path = ROOT / f'manifests/input_jobs/tic{tic}.json'
        jobs.append(dict(job_id=f'tic{tic}', arguments=['p12/protocol/verify_prepare_p12.py', str(tic)], attempt=1,
                         result_path=f'p12/results/native_noise/archival/tic{tic}.json',
                         source_hashes=dict(sources, **{job_path.relative_to(REPO).as_posix(): sha(job_path)})))
    return P2._write_jobs(phase, jobs)


def _eligible(tic, arm='archival'):
    path = ROOT / f'results/native_noise/{arm}/tic{int(tic)}.json'
    return path.exists() and read(path)['status'] == 'INPUT_ELIGIBLE'


def ext_sample():
    """5a: 300 eligible extension stars by SHA-256 of 20260920:ext_cal:<TIC>, then the 600-injection spec."""
    P2._owner_free()
    stars = _e1_stars()
    eligible = sorted((t for t in stars if _eligible(t)), key=lambda t: hashlib.sha256(f'20260920:ext_cal:{t}'.encode()).hexdigest())
    chosen = eligible[:300]
    folder = ROOT / 'manifests/part5'
    sample = folder / 'ext_cal_sample.csv'
    with sample.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['tic_id', *STAR_MAP, 'contamination_ratio_used'], lineterminator='\n')
        writer.writeheader()
        for tic in chosen:
            writer.writerow(dict(tic_id=tic, **stars[tic], contamination_ratio_used=''))
    hosts = folder / 'ext_cal_hosts.csv'
    with hosts.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['tic_id', *STAR_MAP], lineterminator='\n')
        writer.writeheader()
        for tic in sorted(chosen):
            writer.writerow(dict(tic_id=tic, **stars[tic]))
    spec = DATA / 'calibration/ext/truth/injections_ext_cal.csv'
    spec.parent.mkdir(parents=True, exist_ok=True)
    if not spec.exists():
        subprocess.run([sys.executable, 'p12/protocol/make_injection_spec_p12.py', '--sample', str(sample), '--n-stars', str(len(chosen)),
                        '--per-star', '2', '--seed', '20260920', '--rp-earth-min', '1', '--rp-earth-max', '4',
                        '--period-bins', '0.5,30,4', '--sample-out', str(folder / 'ext_cal_sample_out.csv'), '--spec-out', str(spec)],
                       cwd=REPO, check=True)
    rows = P2._csv(spec)
    receipt = dict(utc=utc(), eligible_extension_stars=len(eligible), chosen=len(chosen), order='SHA-256 of 20260920:ext_cal:<TIC>',
                   sample=sample.relative_to(REPO).as_posix(), sample_sha256=sha(sample), spec=spec.relative_to(REPO).as_posix(),
                   spec_sha256=sha(spec), injections=len(rows), eligible_job_ids=sorted(r['job_id'] for r in rows))
    write(folder / 'ext_cal_inputs.json', receipt, replace=(folder / 'ext_cal_inputs.json').exists())
    print(json.dumps(dict(chosen=len(chosen), injections=len(rows))), flush=True)
    return receipt


def ext_prepare(phase):
    P2._owner_free()
    receipt = read(ROOT / 'manifests/part5/ext_cal_inputs.json')
    sources = P2._sources()
    jobs = [dict(job_id=jid, attempt=1, arguments=['p12/protocol/prepare_injections_p12.py', '--arm', 'archival', '--spec', receipt['spec'],
                 '--job-id', jid], result_path=f'p12/results/preparation/archival/{jid}.json', source_hashes=sources)
            for jid in receipt['eligible_job_ids']]
    return P2._write_jobs(phase, jobs)


def ext_search(phase):
    P2._owner_free()
    receipt = read(ROOT / 'manifests/part5/ext_cal_inputs.json')
    stars = _e1_stars()
    sources = P2._sources()
    run = 'data/survey/p12/calibration/ext/runs/survey_p10'
    jobs = []
    for jid in receipt['eligible_job_ids']:
        prep_path = ROOT / f'results/preparation/archival/{jid}.json'
        if not prep_path.exists() or read(prep_path).get('status') != 'COMPLETE':
            continue
        prep = read(prep_path)
        prepared = {k: prep[k] for k in ('prepared_path', 'prepared_sha256', 'provenance_sha256', 'ingest_key')}
        jobs.append(P2._search_job(prep['tic_id'], jid, stars[int(prep['tic_id'])], prepared, run, sources, phase))
    for row in P2._csv(ROOT / 'manifests/part5/ext_cal_hosts.csv'):
        tic = int(row['tic_id'])
        jobs.append(P2._search_job(tic, f'extfa_tic{tic}', stars[tic], P2._host_prepared('archival', tic), run, sources, phase))
    return P2._write_jobs(phase, jobs)


def ext_cases(search_phase):
    """As plan_part2_p12.cases, on the extension calibration (label ext_cal)."""
    manifest = ROOT / f'manifests/part5/{EXT_LABEL}_cases.json'
    if manifest.exists():
        return read(manifest)
    locked = P2._locked(search_phase)
    stars = _e1_stars()
    sources = P2._sources()
    rows, counts = [], dict(injections=0, recovered=0, false_alarm_accepted=0, false_alarm_pregate=0, unknown=0)
    for job in locked['jobs']:
        jid = job['job_id']
        if job['status'] != 'COMPLETE':
            counts['unknown'] += 1
            continue
        result = read(REPO / job['result_path'])
        tic = int(result['tic_id'])
        star = stars[tic]
        collected = P2.collect_rows(result, star)
        if jid.startswith('extfa_'):
            counts['false_alarm_accepted'] += len(collected)
            for row in collected:
                if not row['passes_pregate']:
                    continue
                counts['false_alarm_pregate'] += 1
                cid = f"fa_tic{tic}_p{int(row['planet_num']):02d}"
                base = P2._case_runtime(EXT_LABEL, 'false_alarm', cid, tic, row, collected, star, dict(kind='policy', arm='archival'),
                                        None, sources, population_tier='E1')
                rows.append(dict(candidate_id=cid, tic_id=tic, kind='false_alarm', runtime=base.relative_to(REPO).as_posix(),
                                 runtime_sha256=sha(base), pregate=True))
            continue
        counts['injections'] += 1
        prep = read(ROOT / f'results/preparation/archival/{jid}.json')
        matched = P2._matched_planet(REPO / prep['truth_path'], job)
        append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=tic, stage=f'Part 5a collect: extension injection truth match ({jid})',
            path=prep['truth_path'], reader='plan_part5_p12.py ext_cases', prompt_of_origin='P12', content='evaluator-side match after the prediction lock'))
        if matched is None:
            continue
        counts['recovered'] += 1
        row = next(r for r in collected if int(r['planet_num']) == int(matched['planet_num']))
        base = P2._case_runtime(EXT_LABEL, 'injection', jid, tic, row, [row], star,
                                dict(kind='injected', index=prep['raw_index_path'], index_sha256=prep['raw_index_sha256']), None, sources,
                                population_tier='E1')
        rows.append(dict(candidate_id=jid, tic_id=tic, kind='injection', runtime=base.relative_to(REPO).as_posix(),
                         runtime_sha256=sha(base), pregate=bool(row['passes_pregate'])))
    result = dict(utc=utc(), label=EXT_LABEL, search_phase=search_phase, counts=counts, cases=rows,
                  lock_sha256=sha(ROOT / f'manifests/{search_phase}_predictions_lock.json'))
    write(manifest, result)
    return result


def ext_stage(stage_name, phase, search_phase):
    P2._owner_free()
    collected = ext_cases(search_phase)
    jobs = []
    for row in collected['cases']:
        a, _ = P2._receipt(EXT_LABEL, 'A', row['candidate_id'])
        if stage_name == 'A' or P2._decision(a) == 'PASS':
            jobs.append(P2._stage_job(stage_name, EXT_LABEL, row))
    return P2._write_jobs(phase, jobs)


def _population():
    """(tic, tier) of every eligible final-population star: core, then E1 when chosen."""
    eligibility = read(ROOT / 'manifests/eligibility_p12.json')['per_star']
    core = sorted(int(t) for t, e in eligibility.items() if e.get('status') == 'INPUT_ELIGIBLE')
    out = [(t, 'core') for t in core]
    if _tier() in ('E1', 'E2'):
        out += [(t, 'E1') for t in sorted(_e1_rows()) if _eligible(t) and t not in set(core)]
    return out


def _final_stars():
    stars = P2._stars()
    if E1_STARS.exists():
        for tic, star in _e1_stars().items():
            stars.setdefault(tic, star)
    return stars


def final_search(phase):
    P2._owner_free()
    arm = 'sml' if read(ROOT / 'results/part2/photometry_decision.json')['decision'] == 'ADOPT_SML' else 'archival'
    stars = _final_stars()
    sources = P2._sources()
    run = 'data/survey/p12/final/runs/survey_p10'
    jobs = [P2._search_job(tic, f'tic{tic}', stars[tic], P2._host_prepared(arm if tier == 'core' else 'archival', tic), run, sources, phase)
            for tic, tier in _population()]
    write(ROOT / 'manifests/part5/final_population.json', dict(utc=utc(), arm=arm, stars=len(jobs),
          by_tier={t: sum(1 for _, x in _population() if x == t) for t in ('core', 'E1')}),
          replace=(ROOT / 'manifests/part5/final_population.json').exists())
    return P2._write_jobs(phase, jobs)


def collect(search_phase='final_search'):
    """5c: the locked search into the final funnel tables and one runtime per pre-gate passer."""
    P2._owner_free()
    manifest = ROOT / 'manifests/part5/final_cases.json'
    if manifest.exists():
        return read(manifest)
    lock = read(ROOT / 'manifests/final_predictions_lock.json')
    seal = read(ROOT / 'manifests/final_predictions_lock_seal.json')
    if sha(ROOT / 'manifests/final_predictions_lock.json') != seal['sha256']:
        raise RuntimeError('Final prediction lock changed')
    arm = 'sml' if read(ROOT / 'results/part2/photometry_decision.json')['decision'] == 'ADOPT_SML' else 'archival'
    tiers = dict(_population())
    stars = _final_stars()
    sources = P2._sources()
    folder = DATA / 'final/funnel'
    folder.mkdir(parents=True, exist_ok=True)
    candidates, cases, counts = [], [], dict(stars_complete=0, unknown=0, accepted=0, pregate=0)
    for job in lock['jobs']:
        if job['status'] != 'COMPLETE':
            counts['unknown'] += 1
            continue
        counts['stars_complete'] += 1
        result = read(REPO / job['result_path'])
        tic = int(result['tic_id'])
        rows = P2.collect_rows(result, stars[tic])
        counts['accepted'] += len(rows)
        candidates += rows
        for row in rows:
            if not row['passes_pregate']:
                continue
            counts['pregate'] += 1
            cid = f"tic{tic}_p{int(row['planet_num']):02d}"
            base = P2._case_runtime(LABEL, 'final', cid, tic, row, rows, stars[tic],
                                    dict(kind='policy', arm=arm if tiers.get(tic) == 'core' else 'archival'),
                                    P2._neighbours(tic), sources, population_tier=tiers.get(tic, 'core'))
            cases.append(dict(candidate_id=cid, tic_id=tic, kind='final', runtime=base.relative_to(REPO).as_posix(),
                              runtime_sha256=sha(base), pregate=True, stitch_snr=row.get('stitch_snr')))
    fields = list(candidates[0].keys()) if candidates else ['tic_id']
    with (folder / 'candidates.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(candidates)
    survivors = sorted((r for r in candidates if r['passes_pregate']), key=lambda r: -float(r['stitch_snr'] or 0))
    with (folder / 'survivors.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['rank', *fields], lineterminator='\n')
        writer.writeheader()
        for i, r in enumerate(survivors, 1):
            writer.writerow(dict(rank=i, **r))
    summary = dict(utc=utc(), counts=counts, arm=arm, lock_sha256=seal['sha256'], candidates_csv_sha256=sha(folder / 'candidates.csv'),
                   survivors_csv_sha256=sha(folder / 'survivors.csv'), pregate=P2.PREGATE)
    write(folder / 'collect_p12.json', summary, replace=(folder / 'collect_p12.json').exists())
    write(manifest, dict(summary, cases=cases))
    print(json.dumps(counts), flush=True)
    return read(manifest)


def _ledger(phase, n):
    append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=None, stage=f'Part 5 planning ({phase})',
        path='p12/results/funnel/final', reader='plan_part5_p12.py', prompt_of_origin='P12',
        content=f'{n} final-population stage decisions read by the planner (identity and decision only; not displayed)'))


def stage(stage_name, phase):
    P2._owner_free()
    collected = collect()
    jobs, a_fail = [], []
    for row in collected['cases']:
        a, _ = P2._receipt(LABEL, 'A', row['candidate_id'])
        s, _ = P2._receipt(LABEL, 'S', row['candidate_id'])
        if stage_name == 'A':
            jobs.append(P2._stage_job('A', LABEL, row))
        elif stage_name == 'S':
            if P2._decision(a) == 'PASS':
                jobs.append(P2._stage_job('S', LABEL, row))
            elif P2._decision(a) == 'FAIL':
                a_fail.append(row)
        elif P2._decision(a) == 'PASS' and P2._decision(s) in ('PASS', 'HOLD'):
            jobs.append(P2._stage_job('B', LABEL, row))
    if stage_name == 'S' and a_fail:
        # The natural-load table's seeded 10% of A failures (seed 20260920), as p10_funnel_calibration does.
        rng = np.random.default_rng(S_FAIL_SEED)
        pool = sorted(a_fail, key=lambda r: r['candidate_id'])
        pick = sorted(rng.choice(len(pool), size=int(round(S_FAIL_FRACTION * len(pool))), replace=False)) if pool else []
        for i in pick:
            jobs.append(dict(P2._stage_job('S', LABEL, pool[i]), diagnostic='A-failure sample (natural load)'))
    _ledger(phase, len(collected['cases']))
    return P2._write_jobs(phase, jobs)


def c(phase):
    P2._owner_free()
    collected = collect()
    passers = []
    for row in collected['cases']:
        b, _ = P2._receipt(LABEL, 'B', row['candidate_id'])
        if P2._decision(b) == 'PASS':
            passers.append(row)
    scores = {row['candidate_id']: _score_v2(row) for row in passers}
    order = sorted(passers, key=lambda r: (-scores[r['candidate_id']], r['candidate_id']))
    write(ROOT / f'manifests/part5/{phase}_order.json', dict(utc=utc(), order=[r['candidate_id'] for r in order], score_v2=scores,
          use='scheduling order only (5d); no decision depends on it; Gaia penalty not applied at scheduling'),
          replace=(ROOT / f'manifests/part5/{phase}_order.json').exists())
    jobs = [P2.c_job(LABEL, row, 'normal') for row in order]
    _ledger(phase, len(passers))
    return P2._write_jobs(phase, jobs)


def _score_v2(row):
    """``ranking.score_v2`` from the Stage A record (chosen ephemeris) and the S gate, as rank_survivors does."""
    if str(REPO / 'src') not in sys.path:
        sys.path.insert(0, str(REPO / 'src'))
    from tesshunter.ranking import score_v2
    runtime = read(REPO / row['runtime'])
    key = f"tic{int(runtime['tic_id'])}_P{float(runtime['candidate']['period_days']):.4f}"
    a_path = REPO / runtime['root'] / 'stageA' / f'{key}.json'
    s, _ = P2._receipt(LABEL, 'S', row['candidate_id'])
    try:
        a = read(a_path)
        ch = a['per_ephemeris'][a['chosen_ephemeris']]
        return float(score_v2(ch.get('kept_snr'), ch.get('events') or [], {}, a.get('deep_event_host'),
                              P2._decision(s))['score_v2'])
    except Exception:
        return float(row.get('stitch_snr') or 0) / 1000.0


def neighbours_final(phase):
    """final_neighbours: C PASS / UNRESOLVED stars without a neighbour table (E1 tables exist from 5a)."""
    P2._owner_free()
    closure = read(ROOT / f'results/funnel/{LABEL}/C_closure_final_C.json')
    tics = sorted({int(r['tic_id']) for r in closure['rows'] if r['decision'] in ('PASS', 'UNRESOLVED')
                   and not (DATA / f"neighbours/tic{int(r['tic_id'])}.json").exists()
                   and not (REPO / f"data/survey/p8/neighbours/tic{int(r['tic_id'])}.json").exists()})
    targets = ROOT / 'manifests/part5/final_neighbours_targets.csv'
    with targets.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['tic_id'], lineterminator='\n')
        writer.writeheader()
        for t in tics:
            writer.writerow(dict(tic_id=t))
    jobs = [dict(job_id='neighbours_final', attempt=1, arguments=['p12/protocol/neighbours_set_p12.py', 'final',
                 targets.relative_to(REPO).as_posix(), '--online'], result_path='p12/results/neighbour_sets/final.json',
                 source_hashes=P2._sources(), stars=len(tics))] if tics else []
    return P2._write_jobs(phase, jobs)


def d(phase):
    P2._owner_free()
    from plan_part4_p12 import d_runtime, _neighbour_ref
    from stage_d_plan_p12 import WORKER, HISTORICAL
    closure = read(ROOT / f'results/funnel/{LABEL}/C_closure_final_C.json')
    sources = P2._sources()
    for name in HISTORICAL:
        sources[name] = sha(REPO / name)
    sidecar = _sidecar()
    jobs = []
    for row in closure['rows']:
        if row['decision'] not in ('PASS', 'UNRESOLVED'):
            continue
        base_path = ROOT / f"manifests/runtime/{LABEL}/{row['candidate_id']}.json"
        base = read(base_path)
        tce = sidecar(int(base['tic_id']), float(base['candidate']['period_days']))
        runtime = d_runtime(phase, LABEL, dict(runtime=base_path.relative_to(REPO).as_posix()), False, 'normal', row['candidate_id'],
                            base['population_tier'], sources, tce_association=tce)
        if runtime['neighbours_reference'] is None:
            runtime['neighbours_reference'] = _neighbour_ref(int(base['tic_id']))
        path = ROOT / f'manifests/{phase}_runtime/{row["candidate_id"]}.json'
        write(path, runtime)
        retry_path = ROOT / f'manifests/{phase}_retry_runtime/{row["candidate_id"]}.json'
        write(retry_path, dict(runtime, phase=phase + '_retry'))
        rel, retry_rel = path.relative_to(REPO).as_posix(), retry_path.relative_to(REPO).as_posix()
        jobs.append(dict(job_id=row['candidate_id'], attempt=1, arguments=[WORKER, rel, sha(path)],
                         result_path=f"p12/results/funnel/{phase}/D/{row['candidate_id']}.json",
                         retry_arguments=[WORKER, retry_rel, sha(retry_path)],
                         retry_result_path=f"p12/results/funnel/{phase}_retry/D/{row['candidate_id']}.json",
                         source_hashes=dict(sources, **{rel: sha(path), retry_rel: sha(retry_path)})))
    _ledger(phase, len(jobs))
    return P2._write_jobs(phase, jobs)


def _sidecar():
    """F7: the P12 SPOC-TCE sidecar, opened here (5e) after the final lock; an association, not a confirmation."""
    if not (ROOT / 'manifests/final_predictions_lock.json').exists():
        raise RuntimeError('The sidecar opens only after the final prediction lock (5e)')
    sidecar = read(ROOT / 'manifests/sidecar_p12.json')
    path = REPO / sidecar['path']
    rows = {}
    with path.open(newline='', encoding='utf-8-sig') as stream:
        for r in csv.DictReader(stream):
            try:
                rows.setdefault(int(r['ticid']), []).append(r)
            except (KeyError, ValueError):
                continue
    append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=None, stage='Part 5e: SPOC TCE sidecar opened for F7',
        path=sidecar['path'], reader='plan_part5_p12.py d', prompt_of_origin='P12', content='after the final prediction lock'))

    def association(tic, period):
        best = None
        for r in rows.get(tic, []):
            try:
                p = float(r.get('orbitalPeriodDays') or r.get('tce_period') or 'nan')
            except ValueError:
                continue
            for ratio in (1, 2, 0.5, 3, 1 / 3):
                if p > 0 and abs(period / (p * ratio) - 1) < 0.01:
                    text = f"SPOC TCE {r.get('run') or r.get('sectors') or ''} pn {r.get('tce_plnt_num') or r.get('planetNumber') or ''} at P = {p:.5f} d"
                    best = dict(ratio=ratio, period=p, text=text + ', an association, not a confirmation')
                    break
            if best:
                break
        return best
    return association


def novelty(phase):
    """final_novelty: one job, TOI and CTOI only (novelty_p12.py, 600 s per source)."""
    P2._owner_free()
    jobs = [dict(job_id='novelty', attempt=1, arguments=['p12/protocol/novelty_p12.py', '--online'],
                 result_path='p12/results/novelty_p12.json', source_hashes=P2._sources())]
    return P2._write_jobs(phase, jobs)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action')
    parser.add_argument('args', nargs='*')
    a = parser.parse_args(argv)
    functions = dict(e1_targets=e1_targets, download_pilot=download_pilot, download_batch=download_batch, pilot_rates=pilot_rates,
                     neighbours=neighbours, verify=verify, ext_sample=ext_sample, ext_prepare=ext_prepare, ext_search=ext_search,
                     ext_stage=ext_stage, final_search=final_search, collect=collect, stage=stage, c=c,
                     neighbours_final=neighbours_final, d=d, novelty=novelty)
    functions[a.action](*a.args)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
