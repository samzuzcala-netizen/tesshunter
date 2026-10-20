"""Part 2 planners: every jobs manifest of the calibration arms, written from closed receipts.

Actions (each writes ``p12/manifests/<phase>_jobs.json`` and prices it for STOP-6):
  inputs                    E_cal hosts, eligible and INPUT_INELIGIBLE injections (evaluator side)
  prepare <arm> <phase>     prepare_injections_p12 jobs (full spec for archival, the 2b spec for sml)
  search <arm> <phase>      blind survey_p10 searches over the injected arrays and the E_cal false-alarm arrays
  real436 <arm> <phase>     blind survey_p10 searches over the 436 TCE hosts' frozen arrays
  stage <A|S|B> <arm> <phase>  per-case runtimes from the locked search (A), then its closed receipts (S, B)
  c_sample <arm> <phase>    30 S-passing injections, 10 per expected-SNR bin, seed 20260908 over sorted job ids
  verify <arm> <phase>      verify_prepare for the E_cal false-alarm stars and the 436 on the SML arm
Workers never receive an injection parameter: search runtimes name frozen arrays only; stage
runtimes name the injected raw index by path and SHA-256. Retry passes are built by the
controller from ``retry_arguments`` / ``retry_result_path`` (a separate attempt-2 runtime).

Superseded 2026-09-23 (AMENDMENTS_P12.md): ``c_job`` parenthesises its runtime path (``Path / str + str`` raised
TypeError; found by the engineering dry run before first use).
"""
from p12_common import REPO, ROOT, DATA, read, write, sha, utc, append_jsonl
from part0_plan_p12 import source_snapshot
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

INJ_FULL = REPO / 'data/survey/injections_p8.csv'
INJ_2B = REPO / 'data/survey/p10/injections_2b.csv'
SAMPLE = REPO / 'data/survey/completeness_sample_p8.csv'
LABEL = {'archival': 'cal_archival', 'sml': 'cal_sml'}
STAR_KEYS = ('radius_rsun', 'mass_msun', 'teff_k', 'tmag', 'ra_deg', 'dec_deg')
PREGATE = dict(stitch_snr_min=7.1, stitch_n_transits_min=3)
HISTORICAL = ('scripts/revet_p6.py', 'scripts/audit_p5.py', 'p10/protocol/p10_funnel_calibration.py')


def _owner_free():
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Build manifests only between phases')


def _sources():
    result = dict(source_snapshot())
    for name in HISTORICAL:
        result[name] = sha(REPO / name)
    return result


def _csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))


def _stars():
    return {int(r['tic_id']): {k: float(r[k]) for k in STAR_KEYS} for r in _csv(REPO / 'data/survey/targets_p8.csv')}


def _write_jobs(phase, jobs):
    path = ROOT / f'manifests/{phase}_jobs.json'
    if path.exists():
        raise FileExistsError(path)
    write(path, jobs)
    from ledger_p12 import price_phase
    price_phase(phase, path)
    return path


def inputs():
    _owner_free()
    eligibility = read(ROOT / 'manifests/eligibility_p12.json')['per_star']
    hosts = [r for r in _csv(SAMPLE)]
    e_cal = [r for r in hosts if eligibility.get(str(int(r['tic_id'])), {}).get('status') == 'INPUT_ELIGIBLE']
    e_ids = {int(r['tic_id']) for r in e_cal}
    out = {}
    for name, spec in (('full', INJ_FULL), ('2b', INJ_2B)):
        rows = _csv(spec)
        out[name] = dict(spec=spec.relative_to(REPO).as_posix(), spec_sha256=sha(spec), total=len(rows),
                         eligible_job_ids=sorted(r['job_id'] for r in rows if int(r['tic_id']) in e_ids),
                         input_ineligible_job_ids=sorted(r['job_id'] for r in rows if int(r['tic_id']) not in e_ids))
    stars = _stars()
    path = ROOT / 'manifests/part2/e_cal_hosts.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['tic_id', *STAR_KEYS], lineterminator='\n')
        writer.writeheader()
        for tic in sorted(e_ids):
            writer.writerow(dict(tic_id=tic, **stars[tic]))
    targets = ROOT / 'manifests/part2/sml_inventory_targets.csv'
    core = [int(r['tic_id']) for r in _csv(ROOT / 'manifests/targets_p12_core.csv')
            if eligibility.get(str(int(r['tic_id'])), {}).get('status') == 'INPUT_ELIGIBLE']
    with targets.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['tic_id'], lineterminator='\n')
        writer.writeheader()
        for tic in sorted(set(core) | e_ids):
            writer.writerow(dict(tic_id=tic))
    cal_targets = ROOT / 'manifests/part2/sml_cal_targets.csv'
    tce = {int(r['tic_id']) for r in _csv(REPO / 'p10/part3/manifests/targets_evaluated.csv')}
    with cal_targets.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['tic_id'], lineterminator='\n')
        writer.writeheader()
        for tic in sorted(e_ids | tce):
            writer.writerow(dict(tic_id=tic))
    receipt = dict(utc=utc(), e_cal_hosts=len(e_ids), calibration_hosts=len(hosts), injections=out,
                   sml_cal_targets=cal_targets.relative_to(REPO).as_posix(), sml_cal_targets_sha256=sha(cal_targets),
                   e_cal_path=path.relative_to(REPO).as_posix(), e_cal_sha256=sha(path),
                   sml_inventory_targets=targets.relative_to(REPO).as_posix(), sml_inventory_targets_sha256=sha(targets),
                   rule='an injection on an input-ineligible host is INPUT_INELIGIBLE, reported in its own row, never a miss')
    write(ROOT / 'manifests/part2/inputs.json', receipt, replace=(ROOT / 'manifests/part2/inputs.json').exists())
    print(json.dumps(dict(e_cal=len(e_ids), full=len(out['full']['eligible_job_ids']), two_b=len(out['2b']['eligible_job_ids']))), flush=True)
    return receipt


def prepare(arm, phase, spec_name):
    _owner_free()
    receipt = read(ROOT / 'manifests/part2/inputs.json')
    spec = receipt['injections'][spec_name]
    sources = _sources()
    jobs = []
    for jid in spec['eligible_job_ids']:
        jobs.append(dict(job_id=jid, attempt=1, arguments=['p12/protocol/prepare_injections_p12.py', '--arm', arm,
                                                           '--spec', spec['spec'], '--job-id', jid],
                         result_path=f'p12/results/preparation/{arm}/{jid}.json', source_hashes=sources))
    return _write_jobs(phase, jobs)


def _search_job(tic, jid, star, prepared, run, sources, runtime_folder):
    runtime = dict(tic_id=int(tic), preset='survey_p10', job_id=jid, star=star, prepared_path=prepared['prepared_path'],
                   prepared_sha256=prepared['prepared_sha256'], provenance_sha256=prepared['provenance_sha256'],
                   ingest_key=prepared['ingest_key'], source_hashes=sources, run=run)
    # The search I/O log is exclusive per runtime file name (blind_search_worker_p12 names it by the stem), and the
    # same star is searched in several phases (arm A and B false-alarm hosts, the 436, the pilot, the final search),
    # so every runtime name carries its phase.
    path = ROOT / f'manifests/runtime/{runtime_folder}/{runtime_folder}__{jid}.json'
    write(path, runtime, replace=False)
    retry = dict(runtime, run=run + '_a2')
    retry_path = ROOT / f'manifests/runtime/{runtime_folder}/{runtime_folder}__{jid}_a2.json'
    write(retry_path, retry, replace=False)
    rel = lambda p: p.relative_to(REPO).as_posix()
    receipts = lambda r: 'p12/results/search_receipts/' + Path(r).relative_to('data/survey/p12').as_posix() + f'/{jid}.json'
    return dict(job_id=jid, attempt=1, arguments=['p12/protocol/blind_search_worker_p12.py', rel(path), sha(path)],
                result_path=receipts(run), source_hashes=dict(sources, **{rel(path): sha(path)}),
                retry_arguments=['p12/protocol/blind_search_worker_p12.py', rel(retry_path), sha(retry_path)],
                retry_result_path=receipts(run + '_a2'))


def _host_prepared(arm, tic):
    record = read(ROOT / f'results/native_noise/{arm}/tic{int(tic)}.json')
    if record['status'] != 'INPUT_ELIGIBLE':
        raise RuntimeError(f'TIC {tic} is not input-eligible on the {arm} arm')
    return dict(prepared_path=record['prepared_path'], prepared_sha256=record['prepared_sha256'],
                provenance_sha256=record['provenance_sha256'], ingest_key=record['ingest_key'])


def search(arm, phase):
    _owner_free()
    receipt = read(ROOT / 'manifests/part2/inputs.json')
    stars = _stars()
    sources = _sources()
    run = f'data/survey/p12/calibration/{arm}/runs/survey_p10'
    jobs = []
    spec = receipt['injections']['full' if arm == 'archival' else '2b']
    for jid in spec['eligible_job_ids']:
        prep_path = ROOT / f'results/preparation/{arm}/{jid}.json'
        if not prep_path.exists() or read(prep_path).get('status') != 'COMPLETE':
            continue  # an unprepared injection is an operational unknown of the preparation phase
        prep = read(prep_path)
        prepared = dict(prepared_path=prep['prepared_path'], prepared_sha256=prep['prepared_sha256'],
                        provenance_sha256=prep['provenance_sha256'], ingest_key=prep['ingest_key'])
        jobs.append(_search_job(prep['tic_id'], jid, stars[int(prep['tic_id'])], prepared, run, sources, phase))
    for row in _csv(ROOT / 'manifests/part2/e_cal_hosts.csv'):
        tic = int(row['tic_id'])
        jobs.append(_search_job(tic, f'tic{tic}', stars[tic], _host_prepared(arm, tic), run, sources, phase))
    return _write_jobs(phase, jobs)


def real436(arm, phase):
    _owner_free()
    targets = {int(r['tic_id']): r for r in _csv(REPO / 'p10/part3/manifests/targets_evaluated.csv')}
    sources = _sources()
    run = f'data/survey/p12/real436/{arm}/runs/survey_p10'
    jobs = [_search_job(tic, f'tic{tic}', {k: float(targets[tic][k]) for k in STAR_KEYS}, _host_prepared(arm, tic), run, sources, phase)
            for tic in sorted(targets)]
    return _write_jobs(phase, jobs)


def collect_rows(result, star):
    """The P10 ``collect`` row of every accepted candidate (copied field for field)."""
    tic = int(result['tic_id'])
    res = result['result']
    rot = result.get('rotation_proxy') or {}
    cnt = result.get('prepare_counters') or {}
    vet = {v['planet_num']: v for v in (res.get('vetting') or [])}
    budget = any('would not fit' in n for n in (res.get('notes') or []))
    rows = []
    for q in res.get('planets') or []:
        v = vet.get(q['planet_num'], {})
        snr_ok = (q.get('stitch_snr') or 0.0) >= PREGATE['stitch_snr_min']
        ntr_ok = int(q.get('stitch_n_transits') or 0) >= PREGATE['stitch_n_transits_min']
        eph_ok = bool(q.get('stitch_epoch_consistent'))
        rows.append({'tic_id': tic, 'planet_num': q['planet_num'], 'search': q.get('search'), 'period_days': q['period_days'],
                     'epoch_btjd': q['epoch_btjd'], 'duration_days': q['duration_days'], 'depth_ppt': q['depth_ppt'],
                     'snr': q['snr'], 'n_transits': q.get('n_transits_observed'), 'stitch_snr': q.get('stitch_snr'),
                     'stitch_n_transits': q.get('stitch_n_transits'), 'stitch_epoch_consistent': q.get('stitch_epoch_consistent'),
                     'stitch_period_days': q.get('stitch_period_days'), 'stitch_depth_ppt': q.get('stitch_depth_ppt'),
                     'verdict': q.get('verdict'), 'n_flags_high': len(v.get('flags_high') or []),
                     'n_flags_medium': len(v.get('flags_medium') or []), 'flags_high': '|'.join(v.get('flags_high') or []),
                     'n_units': result.get('n_units'), 'baseline_days': round(float(result.get('baseline_days') or 0), 2),
                     'n_cadences': result.get('n_cadences_raw'), 'tmag': star.get('tmag'), 'teff_k': star.get('teff_k'),
                     'radius_rsun': star.get('radius_rsun'), 'mass_msun': star.get('mass_msun'), 'ra_deg': star.get('ra_deg'),
                     'dec_deg': star.get('dec_deg'), 'rotation_peak_period_days': rot.get('peak_period_days'),
                     'rotation_semi_amplitude_ppt': rot.get('semi_amplitude_ppt'), 'rotation_scatter_ppt': rot.get('scatter_ppt'),
                     'prep_mad_ppt': cnt.get('mad_ppt'), 'budget_stop': budget, 'pregate_snr': snr_ok, 'pregate_transits': ntr_ok,
                     'pregate_epoch': eph_ok, 'passes_pregate': bool(snr_ok and ntr_ok and eph_ok)})
    return rows


def _locked(phase):
    lock = ROOT / f'manifests/{phase}_predictions_lock.json'
    seal = read(lock.with_name(lock.stem + '_seal.json'))
    if sha(lock) != seal['sha256']:
        raise RuntimeError('Prediction lock changed')
    return read(lock)


def _matched_planet(truth_path, prediction):
    """The accepted candidate the scorer credited (evaluator side, after the lock)."""
    for path in (REPO / 'src', REPO / 'scripts'):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from analyze_completeness import classify
    truth = read(truth_path)
    planets = [p.get('raw_candidate', p) for p in prediction['accepted']]
    outcome = classify(dict(status='ok', injection=truth.get('injection') or truth, injection_model=truth['injection_model'],
                            result=dict(planets=planets)))
    if outcome['status'] != 'recovered':
        return None
    return next(p for p in planets if abs(float(p['period_days']) / outcome['matched_period'] - 1) < 1e-9)


def _case_runtime(label, instrument, cid, tic, candidate, all_candidates, star, products, neighbours, sources, route='normal',
                  population_tier='core'):
    root = f'data/survey/p12/funnel/{label}/cases/{cid}'
    runtime = dict(candidate_id=cid, tic_id=int(tic), candidate=candidate, all_candidates=all_candidates, star=star,
                   products=products, neighbours_reference=neighbours, label=label, instrument=instrument, route=route,
                   root=root, source_hashes=sources, attempt=1, population_tier=population_tier)
    base = ROOT / f'manifests/runtime/{label}/{cid}.json'
    write(base, runtime, replace=False)
    write(base.with_name(f'{cid}_a2.json'), dict(runtime, attempt=2), replace=False)
    return base


def _neighbours(tic):
    path = REPO / f'data/survey/p8/neighbours/tic{int(tic)}.json'
    return dict(path=path.relative_to(REPO).as_posix(), sha256=sha(path)) if path.exists() else None


def cases(arm, search_phase):
    """Collect: every recovered injection and every false-alarm pre-gate passer becomes a case."""
    label = LABEL[arm]
    manifest = ROOT / f'manifests/part2/{label}_cases.json'
    if manifest.exists():
        return read(manifest)
    locked = _locked(search_phase)
    stars = _stars()
    sources = _sources()
    rows, counts = [], dict(injections=0, recovered=0, false_alarm_accepted=0, false_alarm_pregate=0, unknown=0)
    for job in locked['jobs']:
        jid = job['job_id']
        if job['status'] != 'COMPLETE':
            counts['unknown'] += 1
            continue
        result = read(REPO / job['result_path'])
        tic = int(result['tic_id'])
        star = stars[tic]
        collected = collect_rows(result, star)
        if jid.startswith('tic'):
            counts['false_alarm_accepted'] += len(collected)
            for row in collected:
                if not row['passes_pregate']:
                    continue
                counts['false_alarm_pregate'] += 1
                cid = f"fa_tic{tic}_p{int(row['planet_num']):02d}"
                base = _case_runtime(label, 'false_alarm', cid, tic, row, collected, star,
                                     dict(kind='policy', arm=arm), _neighbours(tic), sources)
                rows.append(dict(candidate_id=cid, tic_id=tic, kind='false_alarm', runtime=base.relative_to(REPO).as_posix(),
                                 runtime_sha256=sha(base), pregate=True))
            continue
        counts['injections'] += 1
        prep = read(ROOT / f'results/preparation/{arm}/{jid}.json')
        matched = _matched_planet(REPO / prep['truth_path'], job)
        append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=tic, stage=f'Part 2 collect: injection truth match ({jid})',
            path=prep['truth_path'], reader='plan_part2_p12.py cases', prompt_of_origin='P12', content='evaluator-side match after the prediction lock'))
        if matched is None:
            continue
        counts['recovered'] += 1
        row = next(r for r in collected if int(r['planet_num']) == int(matched['planet_num']))
        base = _case_runtime(label, 'injection', jid, tic, row, [row], star,
                             dict(kind='injected', index=prep['raw_index_path'], index_sha256=prep['raw_index_sha256']),
                             _neighbours(tic), sources)
        rows.append(dict(candidate_id=jid, tic_id=tic, kind='injection', runtime=base.relative_to(REPO).as_posix(),
                         runtime_sha256=sha(base), pregate=bool(row['passes_pregate'])))
    result = dict(utc=utc(), label=label, arm=arm, search_phase=search_phase, counts=counts, cases=rows,
                  lock_sha256=sha(ROOT / f'manifests/{search_phase}_predictions_lock.json'))
    write(manifest, result)
    return result


def _receipt(label, stage, cid):
    for folder in (f'{stage}_a2', stage):
        path = ROOT / f'results/funnel/{label}/{folder}/{cid}.json'
        if path.exists():
            return read(path), path
    return None, None


def _decision(receipt):
    if not receipt or receipt.get('status') != 'COMPLETE':
        return 'OPERATIONAL_UNKNOWN'
    m = receipt.get('measurement') or {}
    d = m.get('decision', m.get('gate'))
    return d if d in ('PASS', 'FAIL', 'HOLD') else 'OPERATIONAL_UNKNOWN'


def _stage_job(stage, label, row):
    base = REPO / row['runtime']
    retry = base.with_name(base.stem + '_a2.json')
    rel = lambda p: p.relative_to(REPO).as_posix()
    runtime = read(base)
    return dict(job_id=row['candidate_id'], attempt=1, arguments=['p12/protocol/funnel_stage_p12.py', stage, rel(base), sha(base)],
                result_path=f"p12/results/funnel/{label}/{stage}/{row['candidate_id']}.json",
                source_hashes=dict(runtime['source_hashes'], **{rel(base): sha(base), rel(retry): sha(retry)}),
                retry_arguments=['p12/protocol/funnel_stage_p12.py', stage, rel(retry), sha(retry)],
                retry_result_path=f"p12/results/funnel/{label}/{stage}_a2/{row['candidate_id']}.json")


def stage(stage_name, arm, phase, search_phase):
    _owner_free()
    label = LABEL[arm]
    collected = cases(arm, search_phase)
    jobs = []
    for row in collected['cases']:
        a, _ = _receipt(label, 'A', row['candidate_id'])
        s, _ = _receipt(label, 'S', row['candidate_id'])
        if stage_name == 'A':
            eligible = True
        elif stage_name == 'S':
            eligible = _decision(a) == 'PASS'
        else:
            eligible = row['kind'] == 'false_alarm' and _decision(a) == 'PASS' and _decision(s) in ('PASS', 'HOLD')
        if eligible:
            jobs.append(_stage_job(stage_name, label, row))
    return _write_jobs(phase, jobs)


def c_sample(arm, phase, search_phase, outcomes_csv):
    """30 S-passing injections, 10 per expected-SNR bin [7,12), [12,20), [20,50), seed 20260908 over sorted job ids."""
    _owner_free()
    configuration = read(ROOT / 'protocol/config.json')['part2']
    label = LABEL[arm]
    collected = cases(arm, search_phase)
    outcomes = {r['job_id']: r for r in _csv(outcomes_csv)}
    passers = []
    for row in collected['cases']:
        if row['kind'] != 'injection':
            continue
        a, _ = _receipt(label, 'A', row['candidate_id'])
        s, _ = _receipt(label, 'S', row['candidate_id'])
        if _decision(a) == 'PASS' and _decision(s) in ('PASS', 'HOLD'):
            passers.append(dict(row, snr_expected=float(outcomes[row['candidate_id']]['snr_expected'])))
    chosen, bins = sample_bins(passers, configuration['c_sample_bins'], configuration['c_sample_per_bin'],
                               configuration['c_sample_seed'])
    write(ROOT / f'manifests/part2/{phase}_sample.json', dict(utc=utc(), bins=bins, seed=configuration['c_sample_seed'],
          design=configuration['c_sample_order'], n=len(chosen)))
    jobs = [c_job(label, row, 'injection_sample') for row in chosen]
    return _write_jobs(phase, jobs)


def sample_bins(passers, edges, per_bin, seed):
    """``scripts/p10_stage_c.py`` ``injection_sample``: one generator, bins in order, pools sorted by job id."""
    rng = np.random.default_rng(seed)
    chosen, bins = [], []
    for lo, hi in edges:
        pool = sorted([r for r in passers if lo <= r['snr_expected'] < hi], key=lambda r: r['candidate_id'])
        pick = rng.choice(len(pool), size=min(per_bin, len(pool)), replace=False) if pool else []
        selected = [pool[i] for i in sorted(pick)]
        chosen += selected
        bins.append(dict(bin=[lo, hi], pool=len(pool), selected=[r['candidate_id'] for r in selected]))
    return chosen, bins


def c_job(label, row, route):
    base = REPO / row['runtime']
    sources = dict(read(base)['source_hashes'])
    upstream = {}
    for stage_name in ('A', 'S', 'B'):
        _, path = _receipt(label, stage_name, row['candidate_id'])
        if path is not None:
            upstream[stage_name] = dict(path=path.relative_to(REPO).as_posix(), sha256=sha(path))
    rel = lambda p: p.relative_to(REPO).as_posix()
    runtimes = []
    for attempt, deadline in ((1, 12240), (2, 36000)):
        runtime = dict(candidate_id=row['candidate_id'], tic_id=int(row['tic_id']), base_runtime_path=rel(base),
                       base_runtime_sha256=sha(base), label=label, instrument=read(base)['instrument'], route=route,
                       upstream=upstream, threads=8, oversampling=3, deadline_s=deadline, attempt=attempt, source_hashes=sources)
        path = ROOT / (f'manifests/runtime/{label}_C/{row["candidate_id"]}' + ('' if attempt == 1 else '_a2') + '.json')
        write(path, runtime, replace=False)
        runtimes.append(path)
    first, second = runtimes
    return dict(job_id=row['candidate_id'], attempt=1, arguments=['p12/protocol/stage_c_worker_p12.py', rel(first), sha(first)],
                result_path=f"p12/results/funnel/{label}/C/{row['candidate_id']}.json",
                source_hashes=dict(sources, **{rel(first): sha(first), rel(second): sha(second), rel(base): sha(base)}),
                retry_arguments=['p12/protocol/stage_c_worker_p12.py', rel(second), sha(second)],
                retry_result_path=f"p12/results/funnel/{label}/C_a2/{row['candidate_id']}.json")


def verify_sml(phase):
    """verify_prepare --arm sml for the E_cal false-alarm stars and the 436 (Part 2c step 2)."""
    _owner_free()
    sources = _sources()
    tics = sorted({int(r['tic_id']) for r in _csv(ROOT / 'manifests/part2/e_cal_hosts.csv')} |
                  {int(r['tic_id']) for r in _csv(REPO / 'p10/part3/manifests/targets_evaluated.csv')})
    jobs = [dict(job_id=f'tic{t}', attempt=1, arguments=['p12/protocol/verify_prepare_p12.py', str(t), '--arm', 'sml'],
                 result_path=f'p12/results/native_noise/sml/tic{t}.json', source_hashes=sources) for t in tics]
    return _write_jobs(phase, jobs)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['inputs', 'prepare', 'search', 'real436', 'stage', 'c_sample', 'verify'])
    parser.add_argument('args', nargs='*')
    a = parser.parse_args(argv)
    if a.action == 'inputs':
        inputs()
    elif a.action == 'prepare':
        arm, phase = a.args
        prepare(arm, phase, 'full' if arm == 'archival' else '2b')
    elif a.action == 'search':
        search(*a.args)
    elif a.action == 'real436':
        real436(*a.args)
    elif a.action == 'stage':
        stage_name, arm, phase, search_phase = a.args
        stage(stage_name, arm, phase, search_phase)
    elif a.action == 'c_sample':
        arm, phase, search_phase = a.args
        c_sample(arm, phase, search_phase, ROOT / f'results/part2/injection_outcomes_{arm}.csv')
    else:
        verify_sml(*a.args)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
