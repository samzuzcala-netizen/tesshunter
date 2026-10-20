"""Part 4c ephemeris-assisted leg (LB3): the amended endpoint on the unexposed P9 truth positives.

After the blind leg's lock (``neg_p9_search_predictions_lock.json``) and its scoring:
  plan   (evaluator) one survivor row per positive holdout signal at the truth period, epoch and
         duration (``p9/truth/final_truth.csv`` ``period``, ``epoch_btjd``, ``duration_hours``; depth from
         ``depth_ppm``, else the Stage A measurement at that ephemeris), in the harness root
         ``p12/heldout/results/assisted/<key>/`` (one root per signal); the frozen hard stop on the P12 snapshot, not
         redacted; one ``bar_p9_eph`` job per signal
  run    (worker, ``bar_p9_eph``, 2 workers, 5,400 s) Stage A (recorded, not gating), then the
         all-transit fit and Stage D under p12.0 through ``stage_d_worker_p12`` (``--product-source
         heldout``, route ``ephemeris_assisted``, no redaction)
  score  (evaluator) per signal: fit convergence, verdict and every K and H condition; LB3 = signals
         with K6, K8 or K10 fired / n_fit (every condition is evaluated, so a signal counts whatever
         condition decided its verdict), decisive when n_fit >= 5. Label: "ephemeris-assisted, not a
         funnel retention".
"""
from p12_common import REPO, ROOT, DATA, read, write, sha, utc, append_jsonl
import argparse
import csv
import json
import math
import sys
from pathlib import Path

HELDOUT = REPO / 'p12/heldout'
ASSISTED = HELDOUT / 'results/assisted'
TRUTH = REPO / 'p9/truth/final_truth.csv'
PHASE = 'bar_p9_eph'
LB3_CONDITIONS = ('K6', 'K8', 'K10')
COLUMNS = ['rank', 'tic_id', 'planet_num', 'search', 'period_days', 'epoch_btjd', 'duration_days', 'depth_ppt', 'snr',
           'n_transits', 'stitch_snr', 'stitch_n_transits', 'stitch_epoch_consistent', 'stitch_period_days',
           'stitch_depth_ppt', 'verdict', 'n_flags_high', 'n_flags_medium', 'flags_high', 'n_units', 'baseline_days',
           'n_cadences', 'tmag', 'teff_k', 'radius_rsun', 'mass_msun', 'ra_deg', 'dec_deg', 'rotation_peak_period_days',
           'rotation_semi_amplitude_ppt', 'rotation_scatter_ppt', 'prep_mad_ppt', 'budget_stop', 'pregate_snr',
           'pregate_transits', 'pregate_epoch', 'passes_pregate']


def _harness():
    if str(HELDOUT) not in sys.path:
        sys.path.insert(0, str(HELDOUT))
    import runner
    return runner


def _key(tic, period):
    return f'tic{int(tic)}_P{float(period):.4f}'


def signals():
    """Positive holdout truth rows of the registered hosts (evaluator side, after the blind lock)."""
    import pandas as pd
    lock = ROOT / 'manifests/neg_p9_search_predictions_lock.json'
    if not lock.exists():
        raise RuntimeError('The ephemeris-assisted leg opens only after the blind leg lock (4c)')
    hosts = read(ROOT / 'manifests/heldout_hosts.json')
    truth = pd.read_csv(TRUTH)
    rows = [r for r in truth.to_dict('records') if int(r['tic_id']) in set(hosts['positives'])
            and r.get('split') == 'holdout' and r.get('label') == 'positive']
    append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=None, stage='Part 4c LB3: truth ephemerides of the positive holdout signals',
        path=TRUTH.relative_to(REPO).as_posix(), reader='ephemeris_assisted_p12.py plan', prompt_of_origin='P9 (held-out truth)',
        content=f'{len(rows)} truth rows read after the blind lock; period, epoch, duration, depth written as survivor rows'))
    return rows


def plan():
    if (ROOT / 'manifests/controller_owner.json').exists():
        raise RuntimeError('Plan only between phases')
    from crossmatch_p12 import crossmatch_step
    runner = _harness()
    stars = runner.execution_rows()
    by_host = {}
    for r in signals():
        by_host.setdefault(int(r['tic_id']), []).append(r)
    seal = read(ROOT / 'manifests/heldout_source_seal.json')
    sources = dict(seal['files'])
    sources['p12/manifests/heldout_source_seal.json'] = sha(ROOT / 'manifests/heldout_source_seal.json')
    sources['p12/protocol/ephemeris_assisted_p12.py'] = sha(ROOT / 'protocol/ephemeris_assisted_p12.py')
    jobs, table = [], []
    for tic, rows in sorted(by_host.items()):
        star = stars[tic]
        for i, r in enumerate(sorted(rows, key=lambda x: float(x['period'])), 1):
            # One root per signal, so two signals of one host never share a working file.
            root = ASSISTED / _key(tic, r['period'])
            root.mkdir(parents=True, exist_ok=True)
            survivors = []
            depth_ppm = r.get('depth_ppm')
            depth = float(depth_ppm) / 1000 if depth_ppm not in (None, '') and math.isfinite(float(depth_ppm)) else None
            row = {c: '' for c in COLUMNS}
            row.update(rank=1, tic_id=tic, planet_num=i, search='truth_ephemeris', period_days=float(r['period']),
                       epoch_btjd=float(r['epoch_btjd']), duration_days=float(r['duration_hours']) / 24,
                       depth_ppt='nan' if depth is None else depth, verdict='ephemeris_assisted', tmag=star['tmag'],
                       teff_k=star['teff_k'], radius_rsun=star['radius_rsun'], mass_msun=star['mass_msun'],
                       ra_deg=star['ra_deg'], dec_deg=star['dec_deg'], passes_pregate=True)
            survivors.append(row)
            key = _key(tic, r['period'])
            xm = crossmatch_step(dict(tic_id=tic, ra_deg=float(star['ra_deg']), dec_deg=float(star['dec_deg']), period=float(r['period'])))
            spec = dict(truth_id=r['truth_id'], tic_id=tic, key=key, depth_source='depth_ppm' if depth is not None else 'Stage A at the truth ephemeris',
                        crossmatch_star=xm)
            spec_path = ROOT / f'manifests/runtime/{PHASE}/{key}.json'
            write(spec_path, spec)
            rel = spec_path.relative_to(REPO).as_posix()
            jobs.append(dict(job_id=key, attempt=1, arguments=['p12/protocol/ephemeris_assisted_p12.py', 'run', rel, sha(spec_path)],
                             result_path=f'p12/results/funnel/{PHASE}/D/{key}.json', source_hashes=dict(sources, **{rel: sha(spec_path)})))
            table.append(dict(truth_id=r['truth_id'], tic_id=tic, key=key, period=float(r['period']), depth_source=spec['depth_source']))
            for name in ('survivors.csv', 'candidates.csv'):
                with (root / name).open('w', newline='', encoding='utf-8') as stream:
                    writer = csv.DictWriter(stream, fieldnames=COLUMNS if name == 'survivors.csv' else COLUMNS[1:], lineterminator='\n')
                    writer.writeheader()
                    for row in survivors:
                        writer.writerow(row if name == 'survivors.csv' else {k: v for k, v in row.items() if k != 'rank'})
    out = ROOT / f'manifests/{PHASE}_jobs.json'
    if out.exists():
        raise FileExistsError(out)
    write(out, jobs)
    write(ROOT / f'manifests/{PHASE}_signals.json', dict(utc=utc(), signals=table, n=len(table),
          label='ephemeris-assisted, not a funnel retention'))
    from ledger_p12 import price_phase
    price_phase(PHASE, out)
    print(json.dumps(dict(signals=len(table), hosts=len(by_host))), flush=True)
    return out


def run(spec_path, expected):
    """Worker: A (recorded, not gating), then D through the P12 worker on the ephemeris-assisted route."""
    spec_path = REPO / spec_path
    if sha(spec_path) != expected:
        raise RuntimeError('Frozen ephemeris-assisted runtime changed')
    spec = read(spec_path)
    runner = _harness()
    tic, key = int(spec['tic_id']), spec['key']
    root, F, A, V = runner.setup(tic, root=ASSISTED / key)
    job = next(j for j in V.jobs() if V.kkey(tic, j['period']) == key)
    a = F.STAGE_FN['A'](job, threads=1)
    print('A', key, a.get('decision'), a.get('reason'), flush=True)
    if spec['depth_source'] != 'depth_ppm':
        chosen = (a.get('per_ephemeris') or {}).get(a.get('chosen_ephemeris') or 'survey') or {}
        depth = chosen.get('kept_depth_ppt')
        if depth is None:
            raise RuntimeError('No Stage A depth at the truth ephemeris')
        _set_depth(root, key, float(depth))
        job = next(j for j in V.jobs() if V.kkey(tic, j['period']) == key)
    runtime = runner.d_runtime(tic, key, 'ephemeris_assisted', job, root, PHASE, spec['crossmatch_star'], False, 'heldout_p9_positive_assisted')
    path = HELDOUT / f'work/d_runtime/{PHASE}/{key}.json'
    if path.exists():
        raise FileExistsError(path)
    write(path, runtime)
    import stage_d_worker_p12 as W
    return W.main(str(path), sha(path))


def _set_depth(root, key, depth):
    for name in ('survivors.csv', 'candidates.csv'):
        path = root / name
        with path.open(newline='', encoding='utf-8') as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        for r in rows:
            if _key(r['tic_id'], r['period_days']) == key:
                r['depth_ppt'] = depth
        with path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)


def score():
    signals_manifest = read(ROOT / f'manifests/{PHASE}_signals.json')
    rows, n_fit, killed = [], 0, 0
    for s in signals_manifest['signals']:
        receipt_path = ROOT / f'results/funnel/{PHASE}/D/{s["key"]}.json'
        record_path = ASSISTED / f'{s["key"]}/stageD/{s["key"]}.json'
        a_path = ASSISTED / f'{s["key"]}/stageA/{s["key"]}.json'
        receipt = read(receipt_path) if receipt_path.exists() else None
        record = read(record_path) if record_path.exists() else {}
        tiers = record.get('tiers') or {}
        fit = record.get('fit') or {}
        converged = bool(fit.get('adopted')) and not fit.get('error')
        fired = sorted(n for n, c in (tiers.get('conditions') or {}).items() if c.get('fired'))
        lb3 = converged and any(n in fired for n in LB3_CONDITIONS)
        n_fit += converged
        killed += lb3
        rows.append(dict(truth_id=s['truth_id'], tic_id=s['tic_id'], key=s['key'], status=(receipt or {}).get('status', 'OPERATIONAL_UNKNOWN'),
                         stage_A=(read(a_path).get('decision') if a_path.exists() else None), fit_converged=converged,
                         fit_error=fit.get('error'), verdict=tiers.get('verdict'), deciding_condition=tiers.get('deciding_condition'),
                         candidate_tier=(tiers.get('candidate_tier') or {}).get('candidate_tier'), fired=fired,
                         not_measurable=tiers.get('not_measurable'),
                         conditions={n: dict(fired=c.get('fired'), detail=c.get('detail')) for n, c in (tiers.get('conditions') or {}).items()},
                         lb3_counted=lb3))
    import stats_p12
    lb3 = dict(clause='LB3', number=killed, N=n_fit, wilson95=stats_p12.wilson(killed, n_fit) if n_fit else [None, None],
               threshold='<= 1 of n_fit', decisive=n_fit >= 5, holds=(killed <= 1) if n_fit >= 5 else None,
               conditions=list(LB3_CONDITIONS), label='ephemeris-assisted, not a funnel retention',
               reading='a signal counts when any of K6, K8, K10 fired on its record (every condition is evaluated), whatever condition decided the verdict')
    path = ROOT / 'results/part4/p9_positives_table.json'
    table = read(path) if path.exists() else {}
    table.update(ephemeris_assisted=dict(utc=utc(), rows=rows, n_signals=len(rows), n_fit=n_fit, LB3=lb3))
    write(path, json.loads(json.dumps(table, default=float)), replace=path.exists())
    print(json.dumps(dict(signals=len(rows), n_fit=n_fit, lb3=killed, decisive=lb3['decisive'])), flush=True)
    return table


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['plan', 'run', 'score'])
    parser.add_argument('args', nargs='*')
    a = parser.parse_args(argv)
    if a.action == 'plan':
        plan()
    elif a.action == 'run':
        return run(*a.args)
    else:
        score()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
