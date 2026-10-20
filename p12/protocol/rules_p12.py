"""P12 endpoint overlay: p12.0 = p10.0 plus the Part 1b amendments A1 to A7.

Nothing under ``src/`` is edited. ``install()`` registers ``"p12.0"`` in
``audit_rules.NAMED_RULES`` in memory (Stages A, S, B and C are p10.0 under
p12.0). ``evaluate(inputs, rules)`` calls ``verdict_tiers.evaluate`` untouched for
``p10.0``; for ``p12.0`` a context manager sets the amended constants in the
``audit_rules`` namespace that the tier functions read at call time (each
identifier asserted first), evaluates, restores, then applies K10 (a KILL only
if admitted by 1c, else flag F10), H5, H6, F10 and ``candidate_tier``. With
``redact_catalogue=True`` (negative sets only) the hard-stop status is passed as
``KNOWN_STATUS_REDACTED`` and the catalogue clause of K5 and H4 are computed,
recorded and excluded.
"""
from p12_common import REPO, ROOT, read, sha
import contextlib
import copy
import hashlib
import json
import math
import sys

RULES_VERSION = 'p12.0'
BASE_RULES = 'p10.0'
#: A1 (audit_rules line 361) and A2 (line 333); equal to config.json "tiers".
AMENDED = {'TIER_DENSITY_RATIO_RANGE': (0.5, 2.5), 'TIER_ODD_EVEN_SIGMA': 3.5}
K10_VARIANTS = ('K10e', 'K10s')
H_EXTRA = ('H5', 'H6')
CONDITION_NAMES = {
    'K10': 'light-curve artefact test (K10e excluded-event fraction; K10s SAP depth absent), admitted by Part 1c',
    'H5': 'the K9b fixed-aperture disagreement holds in exactly one measurable sector',
    'H6': 'Stage C UNRESOLVED after its one recorded retry',
}


def _modules():
    src = str(REPO / 'src')
    if src not in sys.path:
        sys.path.insert(0, src)
    from tesshunter import audit_rules as R
    from tesshunter import verdict_tiers as T
    return R, T


def _check_config():
    tiers = read(ROOT / 'protocol/config.json')['tiers']
    if tuple(tiers['density_ratio_range']) != AMENDED['TIER_DENSITY_RATIO_RANGE'] or \
            float(tiers['odd_even_sigma']) != AMENDED['TIER_ODD_EVEN_SIGMA']:
        raise RuntimeError('rules_p12 amended constants differ from config.json tiers')
    return tiers


def install_hash():
    """Identity of the overlay: this file plus the configuration blocks it reads."""
    configuration = read(ROOT / 'protocol/config.json')
    body = json.dumps(dict(source=sha(__file__), tiers=configuration['tiers'], k10=configuration['k10'],
                           amended={k: list(v) if isinstance(v, tuple) else v for k, v in AMENDED.items()}),
                      sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()


def configure_early_funnel(module, version='p10.0'):
    """A, S, B and C run p10.0 under both p10.0 and p12.0 (Part 2a: "A, S, B equal p10.0")."""
    if version not in ('p10.0', 'p12.0'):
        raise RuntimeError('Unregistered rule set ' + str(version))
    module.set_rules('p10.0')
    return module.V.RULE_SET


def install():
    R, T = _modules()
    _check_config()
    if 'p12.0' in R.NAMED_RULES and R.NAMED_RULES['p12.0'] is not R.P10_RULES:
        raise RuntimeError('A different p12.0 is registered')
    R.NAMED_RULES['p12.0'] = R.P10_RULES
    for name in AMENDED:
        if not hasattr(R, name):
            raise RuntimeError('audit_rules lacks ' + name)
    return dict(rules_version=RULES_VERSION, base_rules=BASE_RULES, install_hash=install_hash())


@contextlib.contextmanager
def amended():
    R, T = _modules()
    _check_config()
    saved = {}
    for name, value in AMENDED.items():
        if not hasattr(R, name):
            raise RuntimeError('audit_rules lacks ' + name)
        if name in vars(T) and vars(T)[name] is not getattr(R, name):
            raise RuntimeError('verdict_tiers holds its own copy of ' + name)
        saved[name] = getattr(R, name)
    try:
        for name, value in AMENDED.items():
            setattr(R, name, value)
        yield R, T
    finally:
        for name, value in saved.items():
            setattr(R, name, value)


def _f(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _cond(fired, detail, **values):
    return dict(fired=fired, measurable=fired is not None, detail=detail, **values)


def _chosen(stagea):
    if not stagea:
        return None
    per = stagea.get('per_ephemeris') or {}
    return per.get(stagea.get('chosen_ephemeris')) if per else None


def k10(stagea, configuration=None):
    """K10e and K10s from the Stage A record's chosen ephemeris (Part 1c)."""
    c = (configuration or read(ROOT / 'protocol/config.json'))['k10']
    chosen = _chosen(stagea)
    if chosen is None:
        none = _cond(None, 'Stage A chosen ephemeris unavailable')
        return {'K10e': none, 'K10s': dict(none)}
    n_obs, n_exc = chosen.get('n_observed'), chosen.get('n_excluded')
    if not isinstance(n_obs, int) or not isinstance(n_exc, int) or n_obs < c['n_observed_min']:
        e = _cond(None, f"n_observed {n_obs} < {c['n_observed_min']}: not measurable", n_observed=n_obs, n_excluded=n_exc)
    else:
        fraction = n_exc / n_obs
        e = _cond(bool(fraction > c['excluded_event_fraction_min_strict']),
                  f"n_excluded / n_observed = {n_exc}/{n_obs} = {fraction:.3f} (> {c['excluded_event_fraction_min_strict']} fires)",
                  n_observed=n_obs, n_excluded=n_exc, fraction=fraction)
    det, sap = chosen.get('det_kept') or {}, chosen.get('sap_kept') or {}
    d, ed = _f(det.get('weighted_mean_depth_ppt')), _f(det.get('err_ppt'))
    s, es = _f(sap.get('weighted_mean_depth_ppt')), _f(sap.get('err_ppt'))
    sectors = sorted({int(ev['sector']) for ev in chosen.get('events') or []
                      if ev.get('observed') and not ev.get('excluded') and ev.get('sector') is not None})
    if None in (d, ed, s, es):
        k = _cond(None, 'a kept depth or its error is missing: not measurable', det_ppt=d, det_err_ppt=ed, sap_ppt=s, sap_err_ppt=es)
    else:
        quad = math.sqrt(ed ** 2 + es ** 2)
        shallow = s < c['sap_to_det_depth_ratio_max_strict'] * d
        significant = (d - s) > c['depth_difference_sigma_min'] * quad
        spread = len(sectors) >= c['kept_sectors_min']
        k = _cond(bool(shallow and significant and spread),
                  f"SAP {s:.3f} +/- {es:.3f} ppt vs corrected {d:.3f} +/- {ed:.3f} ppt; SAP < 0.5x {shallow}; "
                  f"difference > 3 sigma {significant}; kept events in {len(sectors)} sector(s)",
                  det_ppt=d, det_err_ppt=ed, sap_ppt=s, sap_err_ppt=es, quadrature_err_ppt=quad,
                  kept_sectors=sectors, sap_below_half=shallow, difference_significant=significant, kept_sectors_ge_2=spread)
    return {'K10e': e, 'K10s': k}


def k10_or(values, variants):
    """The OR of the admitted variants: fired if any fires, None if none is measurable."""
    rows = [values[v] for v in variants]
    if not rows:
        return None
    if any(r['fired'] for r in rows):
        return True
    if all(r['fired'] is None for r in rows):
        return None
    return False


def k10_admission():
    path = ROOT / 'results/part1/k10_calibration.json'
    if not path.is_file():
        raise RuntimeError('K10 admission not yet measured (Part 1c)')
    record = read(path)
    return dict(word=record['word'], variants=list(record['or_variants']), calibration_sha256=sha(path))


def h5(conditions):
    k9 = conditions.get('K9') or {}
    rows = k9.get('disagreement') or []
    measured = [r for r in rows if r.get('fired') is not None]
    if not measured:
        return _cond(None, 'no K9b-measurable sector')
    n = sum(1 for r in measured if r['fired'])
    return _cond(n == 1, f'K9b disagreement in {n} of {len(measured)} measurable sector(s)', n_disagreeing=n,
                 n_measurable=len(measured), sectors=[r.get('sector') for r in measured if r['fired']])


def h6(stagec):
    if not stagec:
        return _cond(None, 'Stage C record unavailable')
    decision = stagec.get('decision')
    return _cond(decision == 'UNRESOLVED', f'Stage C {decision}', decision=decision,
                 attempts=stagec.get('attempts'), deadlines_s=stagec.get('deadlines_s'))


def centroid_support(expensive, neighbours, d_ref_ppt, configuration=None):
    """A6's centroid route: per sector informative / target_consistent_unlocalised / offset."""
    c = (configuration or read(ROOT / 'protocol/config.json'))['tiers']
    sigma, radius_max = float(c['centroid_sigma']), float(c['centroid_radius_max_pixels'])
    depth = (d_ref_ppt or 0) / 1000.0
    capable = []
    for n in (((neighbours or {}).get('gaia') or {}).get('neighbours') or []):
        dmag, sep = _f(n.get('delta_mag')), _f(n.get('sep_px'))
        if dmag is None or sep is None:
            continue
        ratio = 10 ** (-0.4 * dmag)
        if depth > 0 and ratio >= depth:
            capable.append(dict(source_id=n.get('source_id'), sep_px=sep, delta_mag=dmag, flux_ratio=ratio))
    rows = []
    for s in (((expensive or {}).get('centroid') or {}).get('per_sector') or []):
        err, tot = _f(s.get('shift_err_px')), _f(s.get('total_shift_px'))
        usable = (s.get('available') and (s.get('n_in') or 0) >= 3 and (s.get('n_out') or 0) >= 10
                  and err is not None and err > 0 and tot is not None)
        if not usable:
            rows.append(dict(sector=s.get('sector'), status='not_measurable')); continue
        r3 = sigma * err
        consistent = tot <= r3
        small = r3 <= radius_max
        # Conservative containment (no direction in the neighbour table): a neighbour is
        # excluded only when it lies beyond the region's farthest point from the target.
        inside = [n for n in capable if n['sep_px'] - tot <= r3]
        status = ('offset' if not consistent else
                  'informative' if small and not inside else 'target_consistent_unlocalised')
        rows.append(dict(sector=s.get('sector'), status=status, total_shift_px=tot, shift_err_px=err,
                         radius_3sigma_px=r3, radius_ok=small, capable_neighbours_in_region=[n['source_id'] for n in inside]))
    return dict(per_sector=rows, capable_neighbours=capable, depth_fraction=depth,
                n_informative=sum(1 for r in rows if r['status'] == 'informative'))


def candidate_tier(ev, inputs, configuration=None):
    c = (configuration or read(ROOT / 'protocol/config.json'))['tiers']
    f5 = ev['flags']['F5']
    by_f5 = f5.get('localisation') == 'on_target_consistent' and (f5.get('n_sectors_measurable') or 0) >= c['minimum_pixel_sectors']
    cen = centroid_support(inputs.get('expensive'), inputs.get('neighbours'), ev['reference_depth']['depth_ppt'], configuration)
    by_centroid = cen['n_informative'] >= c['minimum_pixel_sectors']
    tier = 2 if (by_f5 or by_centroid) else 1
    return dict(candidate_tier=tier, label='pixel-supported candidate' if tier == 2 else 'CTOI-grade candidate',
                route=[name for name, ok in (('F5_on_target_consistent', by_f5), ('informative_centroid', by_centroid)) if ok],
                centroid=cen)


def _redact(inputs, T):
    period, depth = float(inputs['period']), float(inputs.get('depth_ppt') or 0.0)
    nb = inputs.get('neighbours') or {}
    vsx = nb['vsx'].get('objects') or [] if isinstance(nb.get('vsx'), dict) and 'objects' in nb['vsx'] else None
    record = dict(k0_status=(inputs.get('crossmatch_star') or {}).get('status'),
                  k5_with_catalogue=T.k5_alias(period, depth, inputs.get('candidates'), inputs.get('catalogue_periods')),
                  h4_with_catalogue=T.h4_vsx(vsx, period), excluded=['K0', 'K5 catalogue clause', 'H4'])
    out = dict(inputs)
    out['crossmatch_star'] = dict(inputs.get('crossmatch_star') or {}, status='KNOWN_STATUS_REDACTED')
    out['catalogue_periods'] = None
    if nb:
        out['neighbours'] = copy.deepcopy(nb)
        out['neighbours']['vsx'] = None
    return out, record


def evaluate(inputs, rules='p12.0', *, redact_catalogue=False, k10_word=None, k10_variants=None):
    R, T = _modules()
    redaction = None
    if redact_catalogue:
        inputs, redaction = _redact(inputs, T)
    if rules == 'p10.0':
        ev = T.evaluate(inputs)
        if redaction:
            ev['redaction'] = redaction
        return ev
    if rules != 'p12.0':
        raise ValueError('Unregistered rule set ' + str(rules))
    configuration = read(ROOT / 'protocol/config.json')
    with amended() as (Ra, Ta):
        ev = Ta.evaluate(inputs)
        ev['thresholds'] = Ra.tier_thresholds()
    if k10_word is None:
        admission = k10_admission()
        k10_word, k10_variants = admission['word'], admission['variants']
    if k10_word not in ('K10_KILL', 'K10_FLAG'):
        raise ValueError('Unknown K10 word')
    values = k10(inputs.get('stageA'), configuration)
    or_fired = k10_or(values, list(k10_variants or []))
    conditions = ev['conditions']
    k_order = list(T.K_ORDER)
    if k10_word == 'K10_KILL':
        conditions['K10'] = _cond(or_fired, f"K10 (KILL, OR of {list(k10_variants)}): " +
                                  '; '.join(f"{v} {values[v]['detail']}" for v in k10_variants), variants=list(k10_variants))
        k_order.append('K10')
    conditions['H5'] = h5(conditions)
    conditions['H6'] = h6(inputs.get('stageC'))
    h_order = list(T.H_ORDER) + list(H_EXTRA)
    verdict, deciding = 'SUBMIT', None
    for name in k_order:
        if conditions[name]['fired']:
            verdict, deciding = 'KILL', name
            break
    if verdict == 'SUBMIT':
        for name in h_order:
            if conditions[name]['fired']:
                verdict, deciding = 'HOLD', name
                break
    ev['flags']['F10'] = dict(word=k10_word, or_variants=list(k10_variants or []), or_fired=or_fired,
                              K10e=values['K10e'], K10s=values['K10s'], deciding=k10_word == 'K10_KILL')
    ev.update(rules_version=RULES_VERSION, base_rules=BASE_RULES, verdict=verdict, deciding_condition=deciding,
              deciding_detail=None if deciding is None else conditions[deciding]['detail'],
              not_measurable=[n for n in k_order + h_order if conditions[n]['fired'] is None],
              k_order=k_order, h_order=h_order, install_hash=install_hash(),
              amended_constants={k: list(v) if isinstance(v, tuple) else v for k, v in AMENDED.items()},
              candidate_tier=None, validation_status=ev['flags'].get('F9'))
    if verdict == 'SUBMIT':
        ev['candidate_tier'] = candidate_tier(ev, inputs, configuration)
    if redaction:
        ev['redaction'] = redaction
    return ev


def summarise(ev):
    fired = [n for n in ev.get('k_order', []) + ev.get('h_order', []) if (ev['conditions'].get(n) or {}).get('fired')]
    tier = (ev.get('candidate_tier') or {}).get('candidate_tier')
    return (f"{ev['verdict']}{' tier ' + str(tier) if tier else ''} ({ev['deciding_condition'] or 'no condition'}): "
            f"fired {fired or 'none'}; not measurable {ev['not_measurable'] or 'none'}")
