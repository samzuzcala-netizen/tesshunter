"""P12 Stage D worker: events under every ephemeris, neighbours, the frozen hard stop,
the Stage-C-seeded all-transit fit, TRICERATOPS, TESScut centroids, difference images
and fixed apertures, the verdict tiers under the requested rule sets, and a packet.

Origins: ``scripts/revet_p6.py`` ``staged_one`` (called unchanged), ``scripts/p8_stage_d_packets.py``
(copied as ``stage_d_packets_p12``), the P8 pixel methods (``stage_d_pixels_p12``) and the P9
runner's D adapter pattern (roots, stellar and neighbour inputs patched in memory).

Routes and sources:
  * ``product_source`` ``p8_store`` (the products and p8.0 records P8 used) is allowed only in
    ``plumbing_d`` and its 1d re-run ``plumbing_d_rerun``; every other phase reads products through ``policy_products_p12`` under
    ``survey_p10`` and p10.0 stage rules.
  * ``redact_catalogue`` is allowed only in ``neg_*`` phases (4a).
  * Under p10.0 stage rules ``audit_p5.fit_step`` seeds from the survey ephemeris; the physical
    fit must use the signal Stage C accepted (a validated alias sits outside the fit's 0.1%
    bounds), so the worker seeds it from the Stage C blind ephemeris exactly as
    ``audit_p5._p8_fit_input`` does for p8.0, and installs that seed as ``A._p8_fit_input``
    for the downstream consistency checks. A Stage C ``UNRESOLVED`` case (H6) is seeded from the
    survey ephemeris and its fit reads the Stage A forced narrow-TLS record.
A measurement that fails is recorded and leaves its record absent, so H3 holds; the job is
COMPLETE when a verdict was stamped, OPERATIONAL_UNKNOWN otherwise.

Superseded 2026-09-23 (AMENDMENTS_P12.md): a phase or packet path containing "ttt" is written under the
registered worker alias "tenk", because blind_io_p12 denies any "ttt" path component to a worker.
Superseded 2026-09-23 (AMENDMENTS_P12.md, 4c): ``product_source`` ``heldout`` (only ``neg_p9_*`` and
``bar_p9_*``) reads the P9 held-out inputs through the harness's own selection (``p12/heldout/common.py``
``install_products``) with the harness's frozen source snapshot first on the import path and the
Lightkurve / TESScut cache under ``data/survey/p12/heldout/lightkurve``; route ``ephemeris_assisted``
(only ``bar_p9_*``) seeds the fit from the survivor row the evaluator wrote at the truth ephemeris (no
Stage C record exists; the Stage A forced narrow-TLS record supplies the cadence map and depth seed).
"""
from p12_common import REPO, ROOT, DATA, environment, read, write, sha, utc, redirect_audit_cache
import copy
import csv
import hashlib
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

from blind_io_p12 import install as install_guard, summary as guard_summary

RUNTIME_FIELDS = {'candidate_id', 'key', 'tic_id', 'period', 'depth_ppt', 'phase', 'root', 'route', 'redact_catalogue',
                  'product_source', 'arm', 'rules', 'crossmatch_star', 'tce_association', 'star', 'neighbours_reference',
                  'packet_subtree', 'population_tier', 'n_draws', 'source_hashes', 'review_reference', 'job'}


def refuse(runtime):
    phase = runtime['phase']
    if runtime.get('redact_catalogue') and not phase.startswith('neg_'):
        raise RuntimeError('--redact-catalogue is registered only for neg_* phases (4a)')
    if runtime.get('product_source') == 'p8_store' and phase not in ('plumbing_d', 'plumbing_d_rerun'):
        raise RuntimeError('--product-source p8_store is registered only for plumbing_d (1d)')
    if runtime.get('product_source') == 'heldout' and not phase.startswith(('neg_p9_', 'bar_p9_')):
        raise RuntimeError('--product-source heldout is registered only for the P9 held-out phases (4c)')
    if runtime.get('product_source') not in ('p8_store', 'policy', 'heldout'):
        raise RuntimeError('Unregistered product source')
    if runtime.get('route') not in ('normal', 'forced_negatives', 'ephemeris_assisted'):
        raise RuntimeError('Unregistered route')
    if runtime.get('route') == 'ephemeris_assisted' and not phase.startswith('bar_p9_'):
        raise RuntimeError('The ephemeris-assisted route is registered only for bar_p9_* (4c, LB3)')
    for rules in runtime['rules']:
        if rules not in ('p10.0', 'p12.0'):
            raise RuntimeError('Unregistered rule set')


def legacy(runtime, root):
    """The configured audit/revet modules for this case root."""
    if runtime['product_source'] == 'heldout':
        return _heldout_legacy(runtime, root)
    for path in (REPO / 'src', REPO / 'scripts', REPO / 'p10/protocol'):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    import audit_p5 as A
    redirect_audit_cache(A)
    if runtime['product_source'] == 'p8_store':
        import p8_funnel as F
        F.PACKETS = DATA / 'funnel/empty_packets'
        F.PACKETS.mkdir(parents=True, exist_ok=True)
        F.set_root(root)
        F.set_rules('p8.0')
        A.set_roots(root, REPO / 'data/survey/audit_lc')
    else:
        import p10_funnel_calibration as F
        from rules_p12 import configure_early_funnel
        F.LC_ROOT = REPO / 'data/survey/audit_lc'
        F.PACKETS = DATA / 'funnel/empty_packets'
        F.PACKETS.mkdir(parents=True, exist_ok=True)
        F.set_root(root)
        configure_early_funnel(F, 'p12.0')
        A.set_roots(root, REPO / 'data/survey/audit_lc')
    redirect_audit_cache(A)
    import revet_p6 as V
    return A, V, F


def _heldout_legacy(runtime, root):
    """4c: the harness's frozen snapshot first, P9 inputs read-only, the P12 held-out cache."""
    heldout = REPO / 'p12/heldout'
    if str(heldout) not in sys.path:
        sys.path.insert(0, str(heldout))
    import common as H
    H.frozen_imports()
    import audit_p5 as A
    import p10_funnel_calibration as F
    H.base_first()
    from rules_p12 import configure_early_funnel
    F.LC_ROOT = H.P9 / 'inputs/raw'
    F.PACKETS = H.H / 'work/empty_packets'
    F.PACKETS.mkdir(parents=True, exist_ok=True)
    F.set_root(root)
    configure_early_funnel(F, 'p12.0')
    A.set_roots(root, H.P9 / 'inputs/raw')
    A.AUDIT_CACHE = H.CACHE
    H.CACHE.mkdir(parents=True, exist_ok=True)
    os.environ['LIGHTKURVE_CACHE'] = str(H.CACHE)
    import revet_p6 as V
    return A, V, F


def _patch_inputs(A, runtime, root):
    tic = int(runtime['tic_id'])
    star = runtime['star']
    stellar = {'radius': star['radius_rsun'], 'mass': star['mass_msun'], 'teff': star['teff_k'],
               'tmag': star['tmag'], 'ra': star['ra_deg'], 'dec': star['dec_deg']}
    A.stellar_from_cache = lambda requested: stellar if int(requested) == tic else {}
    nb_ref = runtime['neighbours_reference']
    source = REPO / nb_ref['path']
    if sha(source) != nb_ref['sha256']:
        raise RuntimeError('Neighbour table changed')
    target = root / 'neighbours' / f'tic{tic}.json'
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    def neighbours(t, force=False):
        if int(t) != tic:
            raise RuntimeError('Neighbour lookup for another star')
        nb = copy.deepcopy(read(target))
        depths = [float(r['depth_ppt']) for r in csv.DictReader((root / 'survivors.csv').open(encoding='utf-8'))]
        g = nb.get('gaia') or {}
        if g.get('error') or not g.get('target'):
            raise RuntimeError('Gaia neighbour record unavailable: ' + str(g.get('error')))
        for n in g.get('neighbours', []):
            d = n.get('max_observed_depth_ppt_total_eclipse')
            n['can_produce_candidate_depths_total_eclipse'] = [d >= v for v in depths] if d is not None else None
            n['can_produce_candidate_depths_50pct_eclipse'] = [d / 2 >= v for v in depths] if d is not None else None
        nb['candidate_depths_ppt'] = depths
        A.jdump(target, nb)
        return nb
    A.neighbours_step = neighbours


def _fit_seed(A, root, key, tic, period, route='normal'):
    """The Stage C accepted ephemeris, as ``audit_p5._p8_fit_input`` builds it for p8.0."""
    import numpy as np
    if route == 'ephemeris_assisted':
        forced = read(root / 'tls' / f'{key}_forced.json')['forced']
        survey = ORIGINAL_EPHEMERIS(tic, period)
        return {'version': 'p12-eph-assisted-1', 'stage_c_sha256': None,
                'ephemeris': dict(survey, source='survivor row at the truth ephemeris (ephemeris-assisted, LB3)'),
                'depth_flux': float(forced['depth'])}
    path = root / 'stageC' / f'{key}.json'
    raw = path.read_bytes()
    rec = json.loads(raw)
    if not A.cache_matches(rec):
        raise ValueError(f'{key}: Stage C record does not match the stage rules / input configuration')
    survey = ORIGINAL_EPHEMERIS(tic, period)
    if rec.get('decision') == 'PASS':
        blind = rec['blind']
        p, t0, duration, depth = (float(blind[n]) for n in ('period', 'T0_btjd', 'duration_days', 'depth'))
        if not np.all(np.isfinite([p, t0, duration, depth])) or not (0 < duration < p and 0 < depth < 1):
            raise ValueError(f'{key}: invalid accepted Stage C fit ephemeris')
        return {'version': 1, 'stage_c_sha256': hashlib.sha256(raw).hexdigest(),
                'ephemeris': {'period': p, 't0': t0, 'duration': max(survey['duration'], duration),
                              'source': 'stageC.blind', 'ref_depth_ppt': survey['ref_depth_ppt']}, 'depth_flux': depth}
    if rec.get('decision') == 'UNRESOLVED':
        forced = read(root / 'tls' / f'{key}_forced.json')['forced']
        return {'version': 'p12-unresolved-1', 'stage_c_sha256': hashlib.sha256(raw).hexdigest(),
                'ephemeris': dict(survey, source='survey (Stage C UNRESOLVED after its retry; H6)'),
                'depth_flux': float(forced['depth'])}
    raise ValueError(f'{key}: Stage C {rec.get("decision")} is not eligible for D')


ORIGINAL_EPHEMERIS = None


def _install_fit_seed(A, root, key, tic, period, route='normal'):
    """Seed ``fit_step`` from Stage C under p10.0 stage rules (no-op for the p8.0 plumbing)."""
    global ORIGINAL_EPHEMERIS
    if A.RULES_VERSION == 'p8.0':
        return None
    ORIGINAL_EPHEMERIS = A._ephemeris
    original_fit = A.fit_step
    seed = _fit_seed(A, root, key, tic, period, route)
    tls_path = root / 'tls' / f'{key}.json'
    substitute = None
    if not tls_path.exists() and seed['version'] in ('p12-unresolved-1', 'p12-eph-assisted-1'):
        forced = read(root / 'tls' / f'{key}_forced.json')
        substitute = dict(forced, d_side_substitute=('Stage C UNRESOLVED' if seed['version'] == 'p12-unresolved-1' else
                                                     'Ephemeris-assisted (no Stage C)') + ': no blind TLS record exists; the Stage A '
                                                    'forced narrow-TLS record supplies the cadence map and depth seed of the fit')
        A.jdump(tls_path, substitute)

    def seeded(t, p, source='survey'):
        if source == 'survey' and int(t) == tic and abs(float(p) / period - 1) < 1e-12:
            return dict(seed['ephemeris'])
        return ORIGINAL_EPHEMERIS(t, p, source)

    def fit_step(t, p, force=False, max_iter=2000):
        if int(t) != tic or abs(float(p) / period - 1) > 1e-12:
            return original_fit(t, p, force=force, max_iter=max_iter)
        out = root / 'fit' / f'{key}.json'
        if out.exists() and not force:
            cached = read(out)
            if A.cache_matches(cached) and cached.get('fit_input') == seed:
                return cached
        A._ephemeris = seeded
        try:
            result = original_fit(t, p, force=True, max_iter=max_iter)
        finally:
            A._ephemeris = ORIGINAL_EPHEMERIS
        result['fit_input'] = seed
        A.jdump(out, result)
        return result

    A.fit_step = fit_step
    A._p8_fit_input = lambda t, p: _fit_seed(A, root, key, tic, float(p), route)
    return dict(seed=seed, tls_substitute=bool(substitute))


def main(runtime_path, expected_sha256):
    # Stage D is an online phase (catalogue, Gaia, TESScut, TRICERATOPS); set before any science import.
    environment(offline=False)
    runtime_path = Path(runtime_path)
    if not runtime_path.is_absolute():
        runtime_path = REPO / runtime_path
    # One guard log per phase runtime folder (manifests/<phase>_runtime/<cid>.json), so a retry phase never collides.
    guard = install_guard(ROOT / f'results/stage_d_io/{runtime_path.parent.name}/{runtime_path.stem}.jsonl')
    if sha(runtime_path) != expected_sha256:
        raise RuntimeError('Frozen runtime changed')
    runtime = read(runtime_path)
    if set(runtime) != RUNTIME_FIELDS or runtime['candidate_id'] != runtime_path.stem:
        raise RuntimeError('Unregistered runtime fields/identity')
    refuse(runtime)
    for name, digest in runtime['source_hashes'].items():
        if sha(REPO / name) != digest:
            raise RuntimeError('Frozen D input/source changed: ' + name)
    phase, cid, key = runtime['phase'], runtime['candidate_id'], runtime['key']
    tic, period = int(runtime['tic_id']), float(runtime['period'])
    # blind_io_p12 protects every path component containing "ttt" (the TESS Ten Thousand table), so a
    # neg_ttt* worker writes under the registered alias "tenk" (config negatives.worker_path_alias).
    label = phase.replace('ttt', 'tenk')
    destination = ROOT / f'results/funnel/{label}/D/{cid}.json'
    if destination.exists():
        raise FileExistsError(destination)
    root = REPO / runtime['root']
    started, timer = utc(), time.perf_counter()
    A, V, F = legacy(runtime, root)
    restore = None
    if runtime['product_source'] == 'policy':
        import policy_products_p12
        restore = policy_products_p12.install(tic, runtime['arm'])
    elif runtime['product_source'] == 'heldout':
        import common as H
        restore = H.install_products(tic)
    steps, errors = {}, {}
    try:
        _patch_inputs(A, runtime, root)
        seed = _install_fit_seed(A, root, key, tic, period, runtime['route'])
        job = dict(runtime['job'], tic_id=tic, period=period, depth_ppt=runtime['depth_ppt'], key=key)
        xm = dict(catalog_stamp=(runtime['crossmatch_star'] or {}).get('catalog_stamp'),
                  per_star={str(tic): runtime['crossmatch_star'] or {}})
        A.jdump(root / f'crossmatch_{root.name}.json', xm)
        clock = time.perf_counter()
        staged = V.staged_one(job, xm, force=True)
        steps['staged'] = round(time.perf_counter() - clock, 1)
        if staged.get('verdict') == 'ERROR':
            errors['staged'] = staged.get('reason')
        extra = fit = arrays = None
        if not errors and not (staged.get('fit') or {}).get('error'):
            import stage_d_packets_p12 as D
            clock = time.perf_counter()
            try:
                extra, fit, arrays = D.measure(A, V, root, job, runtime['n_draws'], runtime['route'])
            except Exception as exc:
                errors['measure'] = f'{type(exc).__name__}: {exc}'[:400]
            steps['measure'] = round(time.perf_counter() - clock, 1)
        if extra is not None:
            import stage_d_pixels_p12 as P
            clock = time.perf_counter()
            try:
                used = sorted(s['sector'] for s in (extra.get('centroid') or {}).get('per_sector', []) if s.get('source') == 'TESScut')
                if used:
                    nb = read(root / 'neighbours' / f'tic{tic}.json')
                    gaia_path = root / 'pixels' / f'tic{tic}_gaia_positions.json'
                    gaia = P.gaia_positions(nb['ra'], nb['dec'], gaia_path)
                    a = fit['adopted']
                    eph = dict(period=a['period'], t0=a['t0_btjd'], duration=a['t14_hours'] / 24, source='P12 physical fit')
                    cache = Path(A.AUDIT_CACHE) / 'tesscut'
                    # The records the difference image depends on; the ephemeris-assisted route has no Stage C record.
                    pinned = [root / 'fit' / f'{key}.json', root / 'stageC' / f'{key}.json', gaia_path]
                    diff = P.difference(root, key, eph, used, gaia, nb, cache,
                                        [q for q in pinned if runtime['route'] != 'ephemeris_assisted' or q.exists()])
                    P.aperture(root, key, eph, diff, nb, cache)
                else:
                    errors['pixels'] = 'no TESScut sector in the centroid record'
            except Exception as exc:
                errors['pixels'] = f'{type(exc).__name__}: {exc}'[:400]
            steps['pixels'] = round(time.perf_counter() - clock, 1)
        from tesshunter import verdict_tiers as T
        import rules_p12
        install = rules_p12.install()
        inputs = T.load_inputs(root, key, tic, period, runtime['depth_ppt'], candidates_csv=root / 'candidates.csv')
        inputs['crossmatch_star'] = runtime['crossmatch_star'] or {}
        inputs['catalogue_periods'] = T.catalogue_periods_from(inputs['neighbours'], inputs['crossmatch_star'])
        inputs['tce_association'] = runtime['tce_association']
        tiers = {}
        for rules in runtime['rules']:
            tiers[rules] = rules_p12.evaluate(inputs, rules, redact_catalogue=bool(runtime['redact_catalogue']))
        record = read(root / 'stageD' / f'{key}.json')
        record.update(tiers_by_rules=tiers, tiers=tiers.get('p12.0') or tiers[runtime['rules'][0]],
                      provisional_verdict=(tiers.get('p12.0') or tiers[runtime['rules'][0]])['verdict'],
                      d_errors=errors, fit_seed=seed, population_tier=runtime['population_tier'],
                      p12_install=install, redacted=bool(runtime['redact_catalogue']))
        A.jdump(root / 'stageD' / f'{key}.json', record)
        packet = None
        final = tiers.get('p12.0') or tiers[runtime['rules'][0]]
        if fit is not None and arrays is not None and (final['verdict'] in ('SUBMIT', 'HOLD') or phase in ('plumbing_d', 'plumbing_d_rerun')):
            import stage_d_packets_p12 as D
            if 'ttt' in runtime['packet_subtree']:
                raise RuntimeError('A worker packet subtree must use the registered alias (no "ttt")')
            packets_dir = REPO / 'docs/packets/audit_p12' / runtime['packet_subtree']
            packet = D.build_packet(A, root, job, fit, arrays, extra, tiers, packets_dir,
                                    dict(population_tier=runtime['population_tier'], phase=phase,
                                         redacted_catalogue=bool(runtime['redact_catalogue'])))
        status = 'COMPLETE'
    except Exception as exc:
        errors['worker'] = f'{type(exc).__name__}: {exc}'[:400]
        errors['traceback'] = traceback.format_exc()[-3000:]
        tiers, packet, status = {}, None, 'OPERATIONAL_UNKNOWN'
    finally:
        if restore:
            restore()
    receipt = dict(candidate_id=cid, key=key, tic_id=tic, stage='D', phase=phase, status=status, started_utc=started,
                   completed_utc=utc(), wall_seconds=time.perf_counter() - timer, steps_seconds=steps, errors=errors,
                   verdicts={r: dict(verdict=t['verdict'], deciding_condition=t['deciding_condition'],
                                     candidate_tier=(t.get('candidate_tier') or {}).get('candidate_tier'),
                                     not_measurable=t['not_measurable'])
                             for r, t in tiers.items()},
                   stage_d_record=(root / 'stageD' / f'{key}.json').relative_to(REPO).as_posix() if tiers else None,
                   packet=packet.relative_to(REPO).as_posix() if packet else None, runtime_sha256=sha(runtime_path),
                   redacted=bool(runtime['redact_catalogue']), product_source=runtime['product_source'],
                   io=guard_summary(guard))
    write(destination, json.loads(json.dumps(receipt, default=str)))
    print('D', status, round(receipt['wall_seconds'], 1), flush=True)
    return 0 if status == 'COMPLETE' else 2


if __name__ == '__main__':
    raise SystemExit(main(*sys.argv[1:]))
