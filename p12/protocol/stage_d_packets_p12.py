"""Stage D measurements (TESScut centroids, TRICERATOPS) and packets, copied from
``scripts/p8_stage_d_packets.py`` with P12 roots.

The origin's ``setup`` calls ``p8_funnel.set_root`` (survey_p8 ingestion, gotcha 14)
and its packets land under ``docs/packets/audit_<root>``; this copy takes the
already configured ``audit_p5`` module from the worker, writes the expensive record
under the case root and the packet under ``docs/packets/audit_p12/<subtree>/<key>/``.
``measure`` is ``measure_one`` without the rank and resume branches; the fit check
compares against the worker's seeded fit input (``A._p8_fit_input``, installed by
``stage_d_worker_p12``). Nothing here submits anything.

Superseded 2026-09-23 (AMENDMENTS_P12.md, 4c LB3): on the ``ephemeris_assisted`` route no secondary, Stage B or
Stage C record exists (the leg runs Stage A, recorded and not gating, then the fit and D), so ``measurement_inputs``
requires only the Stage A record, the fit seeded at the truth ephemeris, the forced-TLS substitute record, the
light curve Stage A prepared and the neighbour table; the S, B and C conditions stay not measurable in the tiers.
The ``normal`` and ``forced_negatives`` routes are unchanged.
"""
from p12_common import REPO, sha, utc
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

CTOI_NOTE_LIMIT = ('The field\'s validation bar (resolved source, localised repeated dimming, low FPP) is out of reach for '
                   'TESS FFI photometry alone at Tmag 13.5; this is a candidate for follow-up, not a validated planet.')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def uniform_fpp(fp):
    """The P4 diagnostic: blank labels and equal top probabilities."""
    tops = (fp.get('top_scenarios') or [])[:3]
    vals = [t.get('prob') for t in tops]
    return bool(len(vals) >= 2 and all(v is not None and np.isfinite(v) for v in vals)
                and max(vals) - min(vals) < 1e-6 and all(not str(t.get('scenario') or '') for t in tops))


def measurement_inputs(A, root, key, tic, period, route):
    """Stale or non-native inputs are refused before any network call."""
    root = Path(root)
    folders = ('stageA', 'fit', 'tls') if route == 'ephemeris_assisted' else ('stageA', 'secondary', 'stageB', 'stageC', 'fit', 'tls')
    paths = [root / folder / f'{key}.json' for folder in folders]
    paths += [root / 'neighbours' / f'tic{tic}.json', root / 'tls' / f'{key}_lc.npz']
    for path in paths[:len(folders)]:
        if not A.cache_matches(read(path)):
            raise ValueError(f'{path.name}: stale input for this rule set / input configuration')
    required = [('stageA', 'decision', {'PASS'}), ('stageC', 'decision', {'PASS', 'UNRESOLVED'})]
    if route == 'ephemeris_assisted':
        required = []  # Stage A is recorded, not gating (4c)
    if route == 'normal':
        required += [('secondary', 'gate', {'PASS', 'HOLD'}), ('stageB', 'decision', {'PASS'})]
    for folder, field, allowed in required:
        if read(root / folder / f'{key}.json').get(field) not in allowed:
            raise ValueError(f'{key}: {folder} not eligible for D on the {route} route')
    fit = read(root / 'fit' / f'{key}.json')
    if fit.get('fit_input') != A._p8_fit_input(tic, period):
        raise ValueError(f'{key}: the physical fit is not seeded by the accepted Stage C ephemeris')
    adopted = fit['adopted']
    needed = [adopted.get(k) for k in ('period', 't0_btjd', 'rp_rs', 'a_rs', 'b', 't14_hours', 'depth_max_ppt')]
    if any(v is None or not np.isfinite(v) for v in needed):
        raise ValueError(f'{key}: physical fit is incomplete')
    tls = read(root / 'tls' / f'{key}.json')
    for p in tls['inputs']['products']:
        if int(p['sector']) < 56 or abs(float(p['cadence_s']) - 200) > 1:
            raise ValueError(f'{key}: expected only sectors >= 56 at harmonised 200 s')
    with np.load(root / 'tls' / f'{key}_lc.npz') as z:
        arrays = {k: z[k] for k in ('time_unbinned', 'flux_unbinned', 'sector_unbinned')}
    hashes = {_rel(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    return fit, arrays, hashes


def measure(A, V, root, job, n_draws, route):
    """Centroids on every selected sector (TESScut only) and TRICERATOPS at the fit ephemeris."""
    from tesshunter.fpp import run_fpp
    from survivor_packets import centroid_all_sectors
    root = Path(root)
    key, tic, period = job['key'], int(job['tic_id']), float(job['period'])
    fit, arrays, hashes = measurement_inputs(A, root, key, tic, period, route)
    fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode('utf-8')).hexdigest()
    out_path = root / 'expensive' / f'{key}.json'
    a = fit['adopted']
    nb = read(root / 'neighbours' / f'tic{tic}.json')
    sectors = sorted(int(s) for s in np.unique(arrays['sector_unbinned']))
    rec = dict(key=key, tic_id=tic, rules_version=A.RULES_VERSION, source_sha256=hashes, input_fingerprint=fingerprint,
               n_draws=n_draws, status='running', timings={},
               ephemeris_source=('P12 all-transit physical fit (seeded at the truth ephemeris; ephemeris-assisted)' if route == 'ephemeris_assisted'
                                 else 'P12 all-transit physical fit (Stage C seeded)'),
               cadence_s=200.0, period=a['period'], t0_btjd=a['t0_btjd'], duration_days=a['t14_hours'] / 24,
               gaia_context=V.gaia_flags(nb, a['depth_max_ppt']), gaia_neighbours=nb['gaia'],
               gaia_usage='Cached neighbour table for the resolved-neighbour assessment; TRICERATOPS uses its TIC scene and its own wider Gaia field population.')
    start = time.perf_counter()
    for name in ('centroid', 'fpp'):
        part = time.perf_counter()
        try:
            if name == 'centroid':
                rec[name] = centroid_all_sectors(tic, nb['ra'], nb['dec'], sectors, a['period'], a['t0_btjd'],
                                                 a['t14_hours'] / 24, len(sectors), tesscut_only=True)
            else:
                fp = run_fpp(tic, sectors[:3], arrays['time_unbinned'], arrays['flux_unbinned'], None,
                             period=a['period'], t0=a['t0_btjd'], duration=a['t14_hours'] / 24,
                             depth_frac=a['depth_max_ppt'] / 1000, exp_time_days=200 / 86400, tmag=nb.get('tmag'),
                             aperture='circular', author='QLP', n_draws=n_draws, red_noise_beta=fit['data']['beta_red_noise'],
                             ra=nb['ra'], dec=nb['dec'], cache_dir=root / 'expensive/fpp_cache',
                             lightkurve_cache_dir=os.environ.get('LIGHTKURVE_CACHE'), fold_mode='binned',
                             input_fingerprint=fingerprint, force=True)
                rec[name] = fp.to_dict()
        except Exception as exc:
            rec[name] = {'available': False, 'error': f'{type(exc).__name__}: {exc}'[:400]}
        rec['timings'][name] = {'wall_seconds': round(time.perf_counter() - part, 1)}
        A.jdump(out_path, rec)
    rec['fpp_uniform'] = uniform_fpp(rec['fpp'])
    rec['status'] = 'complete' if all((rec.get(k) or {}).get('available') for k in ('centroid', 'fpp')) else 'incomplete'
    rec['timings']['total_seconds'] = round(time.perf_counter() - start, 1)
    A.jdump(out_path, rec)
    return rec, fit, arrays


def ctoi_fields(A, root, key, tic, fit, note, tiers, extra_fields):
    """ExoFOP candidate fields (``CTOI_FORM_FIELDS``); the user fills tag, candidate_name, paper_url."""
    from tesshunter.packet import CTOI_FORM_FIELDS
    root = Path(root)
    a = fit['adopted']
    ev_path = next((root / 'events' / f'{key}_{s}.json' for s in ('tls', 'survey') if (root / 'events' / f'{key}_{s}.json').exists()), None)
    ev = read(ev_path)['summary'] if ev_path else {}
    form = dict(target=f'TIC {tic}', tic_id=tic, discovery_source='TESS', period_days=a['period'], period_err_days=a['period_err'],
                epoch_bjd=a['epoch_bjd'], epoch_err_days=a['t0_err'], depth_ppm=round(1000 * a['depth_max_ppt'], 1),
                depth_err_ppm=None if a['depth_err_ppt'] is None else round(1000 * a['depth_err_ppt'], 1),
                duration_hours=a['t14_hours'], duration_err_hours=a['t14_err_hours'], disposition='PC',
                tag=None, candidate_name=None, paper_url=None, notes=note)
    form = {k: form.get(k) for k in CTOI_FORM_FIELDS}
    data = dict(form_fields=form, left_for_the_user=['tag', 'candidate_name', 'paper_url'],
                supplementary=dict(rp_rs=a['rp_rs'], rp_rs_err=a['rp_rs_err'], rp_rearth=a['rp_rearth'],
                    rp_rearth_err=a['rp_rearth_err'], a_rs=a['a_rs'], a_rs_err=a['a_rs_err'], impact_parameter=a['b'],
                    impact_parameter_err=a['b_err'], inclination_deg=a['inc_deg'],
                    depth_duration_averaged_ppm=round(1000 * a['depth_avg_ppt'], 1),
                    density_prior_adopted=fit['density_prior_adopted'], delta_chi2_prior_minus_free=fit['delta_chi2_prior_minus_free'],
                    beta_red_noise=fit['data']['beta_red_noise'], n_transits_in_fit=a['n_transits'], odd_even=fit['odd_even'],
                    events={k: ev.get(k) for k in ('n_observed', 'n_excluded', 'n_kept')}, stellar=fit['stellar'],
                    limb_darkening=fit['limb_darkening']),
                provenance=dict(generated_utc=utc(), rules_version=tiers.get('rules_version'), fit_rules_version=fit.get('rules_version'),
                                audit_files=[_rel(root / 'fit' / f'{key}.json'), _rel(ev_path) if ev_path else None]),
                tiers=dict(rules_version=tiers.get('rules_version'), verdict=tiers.get('verdict'),
                           deciding_condition=tiers.get('deciding_condition'), deciding_detail=tiers.get('deciding_detail'),
                           not_measurable=tiers.get('not_measurable'),
                           conditions={k: {kk: vv for kk, vv in v.items() if kk in ('fired', 'measurable', 'detail')}
                                       for k, v in (tiers.get('conditions') or {}).items()}),
                flags=tiers.get('flags'), validation_status=(tiers.get('flags') or {}).get('F9'),
                candidate_tier=(tiers.get('candidate_tier') or {}).get('candidate_tier'),
                external_submission_performed=False, **extra_fields)
    return data


def build_packet(A, root, job, fit, arrays, extra, tiers_by_rules, packets_dir, extra_fields):
    """A packet carries the measurements whatever the verdict; the p12.0 tier record decides."""
    root = Path(root)
    key, tic = job['key'], int(job['tic_id'])
    out = Path(packets_dir) / key
    out.mkdir(parents=True, exist_ok=True)
    records = {folder: read(root / folder / f'{key}.json') for folder in ('stageA', 'secondary', 'stageB', 'stageC', 'stageD')
               if (root / folder / f'{key}.json').exists()}
    nb = read(root / 'neighbours' / f'tic{tic}.json')
    for name, data in {**records, 'fit': fit, 'expensive': extra, 'neighbours': nb, 'job': job,
                       **{f'tiers_{r.replace(".", "_")}': t for r, t in tiers_by_rules.items()}}.items():
        A.jdump(out / f'{name}.json', data)
    tiers = tiers_by_rules.get('p12.0') or next(iter(tiers_by_rules.values()))
    verdict = tiers['verdict']
    tier = (tiers.get('candidate_tier') or {}).get('candidate_tier')
    a = fit['adopted']
    sectors = sorted(int(s) for s in np.unique(arrays['sector_unbinned']))
    note = (f"TessHunter P12 candidate: P = {a['period']:.6f} d, T0 = {a['epoch_bjd']:.5f} BJD, depth {1000 * a['depth_max_ppt']:.0f} ppm, "
            f"duration {a['t14_hours']:.2f} h, TESS sectors {sectors[0]}-{sectors[-1]} ({len(sectors)}), preset survey_p10, "
            f"rules {tiers.get('rules_version')}. Verdict {verdict}" + (f" tier {tier}" if tier else '') +
            f"; not claimed: a validated planet or a resolved source. {CTOI_NOTE_LIMIT}")
    fields = ctoi_fields(A, root, key, tic, fit, note, tiers, extra_fields)
    A.jdump(out / 'ctoi_fields.json', fields)
    figure(out / 'summary.png', job, fit, arrays, records, extra, tiers)
    cen, fp = extra.get('centroid') or {}, extra.get('fpp') or {}
    lines = [f"# TIC {tic}: P12 candidate review ({key})", '',
             f"**{verdict}**" + (f" (candidate tier {tier}: {(tiers.get('candidate_tier') or {}).get('label')})" if tier else '')
             + f" under {tiers.get('rules_version')}: {tiers.get('deciding_condition') or 'no condition'}; "
             + str(tiers.get('deciding_detail') or 'every measured condition passes'), '',
             'This is a candidate packet. No external submission has been made; the user decides.', '',
             '![Diagnostics](summary.png)', '', '| Measurement | Value |', '|---|---|',
             f"| Period | {a['period']:.9f} +/- {a.get('period_err')} d |",
             f"| Epoch | {a['epoch_bjd']:.9f} +/- {a.get('t0_err')} BJD |",
             f"| Radius | {a['rp_rearth']} +/- {a.get('rp_rearth_err')} Earth radii |",
             f"| T14 | {a['t14_hours']} +/- {a.get('t14_err_hours')} h |",
             f"| Impact parameter | {a['b']:.5f} +/- {a.get('b_err')} |",
             f"| Density prior / grazing | {fit['density_prior_adopted']} / {a['grazing']} |",
             f"| Transits / beta | {a['n_transits']} / {fit['data']['beta_red_noise']} |",
             f"| FPP / NFPP | {fp.get('fpp')} / {fp.get('nfpp')} |",
             f"| fpp_uniform | {extra.get('fpp_uniform')} |",
             f"| Centroid | {cen.get('note') or cen.get('error')} |", '',
             f"ExoFOP note draft: {note}", '', CTOI_NOTE_LIMIT, '']
    for rules, t in tiers_by_rules.items():
        lines += tier_lines(t, rules)
    (out / 'packet.md').write_text('\n'.join(lines), encoding='utf-8')
    return out


def tier_lines(t, rules):
    from tesshunter.verdict_tiers import CONDITION_NAMES
    from rules_p12 import CONDITION_NAMES as EXTRA
    names = {**CONDITION_NAMES, **EXTRA}
    c = t.get('conditions') or {}
    order = t.get('k_order', []) + t.get('h_order', []) or list(c)
    lines = [f'## {rules} verdict tiers', '', f"**{t.get('verdict')}** on {t.get('deciding_condition') or 'no condition'}", '',
             '| Condition | Fired | Detail |', '|---|---|---|']
    for n in order:
        v = c.get(n) or {}
        f = v.get('fired')
        lines.append(f"| {n}: {names.get(n, '')} | {'not measurable' if f is None else ('yes' if f else 'no')} | {str(v.get('detail', ''))[:220]} |")
    flags = t.get('flags') or {}
    lines += ['', '### Flags', '']
    for n in sorted(flags, key=lambda x: int(x[1:]) if x[1:].isdigit() else 99):
        v = flags[n]
        lines.append(f"- **{n}**: {(v if isinstance(v, str) else json.dumps(v, default=str))[:900]}")
    lines.append('')
    return lines


def figure(path, job, fit, arrays, records, extra, tiers):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from tesshunter.survey import transit_model
    t, f = arrays['time_unbinned'], arrays['flux_unbinned']
    a = fit['adopted']
    p, t0, dur = a['period'], a['t0_btjd'], a['t14_hours'] / 24
    phase = (t - t0 + p / 2) % p - p / 2
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5), constrained_layout=True)
    stride = max(1, len(t) // 16000)
    axes[0, 0].scatter(t[::stride], 1000 * (f[::stride] - 1), s=1, alpha=.5)
    axes[0, 0].set(xlabel='Time (BTJD)', ylabel='Relative flux (ppt)', title='Prepared native-cadence series')
    near = abs(phase) < 2 * dur
    axes[0, 1].scatter(phase[near] * 24, 1000 * (f[near] - 1), s=2, alpha=.12)
    grid = np.linspace(-2 * dur, 2 * dur, 700)
    ld = fit['limb_darkening']
    model = transit_model(grid, period=p, t0=0, rp_rs=a['rp_rs'], b=a['b'], a_rs=a['a_rs'], u=(ld['u1'], ld['u2']), exp_time_days=200 / 86400)
    axes[0, 1].plot(grid * 24, 1000 * (model - 1), color='crimson', lw=2)
    axes[0, 1].set(xlabel='Time from transit (h)', ylabel='Relative flux (ppt)', title='All-transit physical fit')
    stagea = records.get('stageA') or {}
    events = ((stagea.get('per_ephemeris') or {}).get(stagea.get('chosen_ephemeris')) or {}).get('events') or []
    for excluded, label, color in ((False, 'Kept', 'tab:blue'), (True, 'Removed', 'tab:orange')):
        es = [e for e in events if e.get('observed') and bool(e.get('excluded')) == excluded
              and e.get('det_depth_ppt') is not None and e.get('det_depth_err_ppt') is not None]
        axes[1, 0].errorbar([e['tc_btjd'] for e in es], [e['det_depth_ppt'] for e in es],
                            yerr=[e['det_depth_err_ppt'] for e in es], fmt='.', ms=4, alpha=.7, label=label, color=color)
    axes[1, 0].legend()
    axes[1, 0].set(xlabel='Event time (BTJD)', ylabel='Depth (ppt)', title='Stage A event measurements')
    cen = extra.get('centroid') or {}
    cs = [c for c in cen.get('per_sector', []) if c.get('available') and c.get('shift_err_px')]
    if cs:
        axes[1, 1].errorbar([c['sector'] for c in cs], [c['total_shift_px'] for c in cs], yerr=[c['shift_err_px'] for c in cs], fmt='o', ms=4)
    else:
        axes[1, 1].text(.5, .5, 'Centroid unavailable; see record', transform=axes[1, 1].transAxes, ha='center')
    axes[1, 1].set(xlabel='TESS sector', ylabel='Centroid shift (pixels)', title='TESScut centroid by sector')
    fig.suptitle(f"TIC {job['tic_id']} | P = {p:.7f} d | {tiers.get('rules_version')} {tiers.get('verdict')}", fontsize=15)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _rel(path):
    path = Path(path)
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return str(path)
