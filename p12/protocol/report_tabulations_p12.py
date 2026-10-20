"""Part 2d report-only tabulations (no rule depends on them; they feed Part 6b).

1. ``window_check.json``: the retention and 1-hour noise measurement of ``p11/protocol/noise_audit.py``
   (``noise`` and ``paired_depth`` copied) on the P11 audit hosts' selected corrected products and their
   recorded physical injections, prepared at biweight windows 0.75 (default), 1.0 and 1.5 d.
2. ``long_period_tabulation.json``: from ``p10/part3/results/matching.json`` and the sealed forced fits,
   survey_p10 recovery of INDEPENDENT present families with depth < 10 ppt and duration < 4.8 h per
   period bin, beside the arm-A injection recovery in the same bins.
3. ``s_mode_restatement.json``: per S mode, injection false kills and adversarial kills retained
   (``p10/results/secondary_modes.json``), and the 17.2% S false-kill rate (200 / 1,164) as a limit.
"""
from p12_common import REPO, ROOT, read, write, sha, utc
import csv
import json
import sys
from pathlib import Path

import numpy as np

PERIOD_BINS = [(0.5, 1), (1, 2), (2, 5), (5, 10), (10, 20), (20, 30.0001)]


def mad(x):
    x = np.asarray(x)
    x = x[np.isfinite(x)]
    return float(1.4826 * np.median(abs(x - np.median(x)))) if len(x) else None


def one_hour_scatter(t, f, sector):
    """Median over sectors of the 1-hour binned MAD scatter (noise_audit.noise, 1 h timescale)."""
    values = []
    for s in sorted(set(sector)):
        take = (sector == s) & np.isfinite(t) & np.isfinite(f)
        st, sf = t[take], f[take]
        if len(st) < 50:
            continue
        cadence = float(np.median(np.diff(st)))
        width = 1 / 24
        idx = np.floor((st - st.min()) / width).astype(int)
        counts = np.bincount(idx)
        means = np.bincount(idx, weights=sf) / np.maximum(counts, 1)
        good = counts >= 0.5 * width / cadence
        if good.sum() >= 8:
            values.append(mad(means[good]))
    return float(np.median(values)) if values else None


def paired_depth(t, uninj, injected, shape):
    good = np.isfinite(t) & np.isfinite(uninj) & np.isfinite(injected) & np.isfinite(shape)
    t, uninj, injected, shape = t[good], uninj[good], injected[good], shape[good]
    if np.count_nonzero(shape > 0) < 3 or np.ptp(shape) == 0:
        return None
    X = np.column_stack([np.ones(len(t)), shape])
    return float(np.linalg.lstsq(X, uninj - injected, rcond=None)[0][1])


def window_check():
    for path in (REPO / 'src',):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from tesshunter import survey_p8
    from tesshunter.survey import transit_model
    configuration = read(ROOT / 'protocol/config.json')['closing_sentence']
    windows = [configuration['default_window_days']] + list(configuration['window_days'])
    hosts = sorted(int(p.stem[3:]) for p in (REPO / 'p11/results/noise_v2').glob('tic*.json'))
    rows = []
    for tic in hosts:
        audit = read(REPO / f'p11/results/noise_v2/tic{tic}.json')
        inventory = read(REPO / f'p11/results/input_inventory_v2/tic{tic}.json')
        products = [p for p in survey_p8.load_audit_products(tic, sector_min=56, sector_max=104)
                    if p['sector'] in inventory['audited_selected_sectors']]
        if not products:
            rows.append(dict(tic_id=tic, status='NO_PRODUCTS')); continue
        param = dict(audit['physical_injection_parameters'])
        raw_injected, _ = survey_p8.inject_products(products, **param, supersample=7)
        uninj, _ = survey_p8.harmonise_cadence(products, 200 / 60)
        inj, _ = survey_p8.harmonise_cadence(raw_injected, 200 / 60)
        row = dict(tic_id=tic, status='MEASURED', windows={})
        for w in windows:
            base = survey_p8.prepare_search_input(uninj, w)
            test = survey_p8.prepare_search_input(inj, w)
            common, i, j = np.intersect1d(base['time'], test['time'], return_indices=True)
            shape = 1 - transit_model(common, **param, exp_time_days=200 / 86400, supersample=7)
            row['windows'][str(w)] = dict(retention=paired_depth(common, base['flux'][i], test['flux'][j], shape),
                                          one_hour_scatter=one_hour_scatter(base['time'], base['flux'], base['sector']))
        rows.append(row)
    measured = [r for r in rows if r['status'] == 'MEASURED']
    summary = {}
    for w in windows:
        ret = [r['windows'][str(w)]['retention'] for r in measured if r['windows'][str(w)]['retention'] is not None]
        ratio = [r['windows'][str(w)]['one_hour_scatter'] / r['windows'][str(windows[0])]['one_hour_scatter'] for r in measured
                 if r['windows'][str(w)]['one_hour_scatter'] and r['windows'][str(windows[0])]['one_hour_scatter']]
        summary[str(w)] = dict(n=len(ret), median_retention=float(np.median(ret)) if ret else None,
                               median_one_hour_noise_ratio_vs_default=float(np.median(ratio)) if ratio else None)
    reference = configuration['window_retention_reference']
    condition = any((summary[str(w)]['median_retention'] or 0) >= reference + configuration['window_retention_gain_min'] and
                    (summary[str(w)]['median_one_hour_noise_ratio_vs_default'] or 99) <= configuration['window_noise_ratio_max']
                    for w in configuration['window_days'])
    return dict(utc=utc(), hosts=len(hosts), measured=len(measured), windows=windows, summary=summary, rows=rows,
                closing_sentence_item_2_holds=condition, reference_retention=reference,
                label='report-only; P11 audit hosts, selected corrected products, recorded physical injections')


def long_period():
    matching = read(REPO / 'p10/part3/results/matching.json')
    forced = read(REPO / 'p10/part3/results/forced_fits.json')
    rows = []
    for family in matching['ephemeris_families']:
        stratum = family['strata'].get('INDEPENDENT')
        if not stratum or not stratum['in_band'] or forced['families'][family['family_id']]['presence'] != 'PRESENT':
            continue
        rep = stratum['representative']
        depth_ppt = float(rep.get('tce_depth') or 0) / 1000
        duration_h = float(rep.get('tce_duration') or 0)
        if not (depth_ppt < 10 and duration_h < 4.8):
            continue
        status = stratum['presets']['survey_p10']['status']
        rows.append(dict(period=float(rep['tce_period']), recovered=status.startswith('RECOVERED_'), known=status != 'OPERATIONAL_UNKNOWN'))
    outcomes_path = ROOT / 'results/part2/injection_outcomes_archival.csv'
    with outcomes_path.open(newline='', encoding='utf-8') as stream:
        injections = list(csv.DictReader(stream))
    table = []
    for lo, hi in PERIOD_BINS:
        fam = [r for r in rows if lo <= r['period'] < hi and r['known']]
        inj = [r for r in injections if lo <= float(r['period']) < hi]
        table.append(dict(bin=[lo, min(hi, 30)], families=len(fam), families_recovered=sum(r['recovered'] for r in fam),
                          family_fraction=(sum(r['recovered'] for r in fam) / len(fam)) if fam else None, injections=len(inj),
                          injection_fraction=(sum(r['status'] == 'recovered' for r in inj) / len(inj)) if inj else None))
    configuration = read(ROOT / 'protocol/config.json')['closing_sentence']
    above = [t for t in table if t['bin'][0] >= configuration['long_period_days_min']]
    n_above = sum(t['families'] for t in above)
    deficit = [100 * ((t['injection_fraction'] or 0) - (t['family_fraction'] or 0)) for t in above if t['families']]
    condition = bool(n_above >= configuration['long_period_min_families'] and deficit and min(deficit) >= configuration['long_period_deficit_pp_min'])
    return dict(utc=utc(), selection='INDEPENDENT present in-band families, depth < 10 ppt, duration < 4.8 h (P10.3 matching and forced fits)',
                table=table, families_above_5_d=n_above, deficits_pp_above_5_d=deficit, closing_sentence_item_3_holds=condition,
                injection_source=outcomes_path.relative_to(REPO).as_posix(), injection_source_sha256=sha(outcomes_path))


def s_modes():
    modes = read(REPO / 'p10/results/secondary_modes.json')
    rate = read(ROOT / 'protocol/config.json')['tabulations']['s_false_kill_rate']
    return dict(utc=utc(), table=modes['decision']['table'], injections=modes['injections'], adversarial=modes['adversarial'],
                p12_mode='bound (P10 2a; P11.5: all 36 joint S x C policies lost planets)',
                s_false_kill_rate=dict(numerator=rate[0], denominator=rate[1], fraction=rate[0] / rate[1],
                                       source='p10/results/part2d_calibration_20260912/stop_rule_1_decision.json'),
                limit='The bound S gate falsely kills about one injected planet in six that reach it; the completeness statement carries this limit.',
                sources={'p10/results/secondary_modes.json': sha(REPO / 'p10/results/secondary_modes.json')})


def main(argv):
    out = ROOT / 'results/part2'
    for name, function in (('window_check', window_check), ('long_period_tabulation', long_period), ('s_mode_restatement', s_modes)):
        write(out / f'{name}.json', json.loads(json.dumps(function(), default=float)), replace=False)
    print(json.dumps(dict(written=['window_check', 'long_period_tabulation', 's_mode_restatement'])), flush=True)
    return 0
