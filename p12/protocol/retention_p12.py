"""Part 2 real-signal leg: search-level recovery of INDEPENDENT present TCE families on the 436
(copy of P10.3 ``prepare_part_f_v1`` matching and ``retention_analysis_v1`` search table).

Matching: the P12 sidecar rows of the 436 hosts grouped by ``tce_families.families`` and matched to
the locked ``survey_p10`` predictions by ``part_f_math_v1.candidate_match`` (exact or 2, 3, 1/2, 1/3
within 1%, with the epoch check when the propagated uncertainty is small enough) — the P10.3 rule.
Presence (whether the TCE's signal is in the data) is the sealed P10.3 forced-fit presence of the
corresponding family (same TIC, anchor period within 1%); a family with no P10.3 counterpart is
UNMEASURED. The pure P10.3 functions are imported read-only by file path. Evaluator only: it opens
the sidecar after the prediction lock, as Part 2 permits for the 436.
"""
from p12_common import REPO, ROOT, DATA, read, write, sha, utc, append_jsonl
import argparse
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np


def _load(name):
    spec = importlib.util.spec_from_file_location(f'p10_3_{name}', REPO / f'p10/part3/protocol/{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = _load('part_f_math_v1')
TF = _load('tce_families')


def recovery_summary(rows, host_status):
    """``prepare_part_f_v1.recovery_summary`` (survey_p10, in-domain rows)."""
    considered = [r for r in rows if r['in_band']]
    if not considered:
        return dict(status='OUTSIDE_DOMAIN', recovered_candidate_ids=[], exact_candidate_ids=[], alias_candidate_ids=[])
    accepted = [m for r in considered for m in r['associations'] if m['recovered']]
    exact = sorted({m['candidate_id'] for m in accepted if m['exact']})
    alias = sorted({m['candidate_id'] for m in accepted if not m['exact']})
    status = ('RECOVERED_EXACT' if exact else 'RECOVERED_ALIAS' if alias else
              'OPERATIONAL_UNKNOWN' if host_status != 'COMPLETE' else 'NOT_RECOVERED')
    return dict(status=status, recovered_candidate_ids=sorted(set(exact + alias)), exact_candidate_ids=exact, alias_candidate_ids=alias)


def match(sidecar_rows, hosts, noises):
    """Families with per-stratum survey_p10 recovery; ``hosts[tic] = {'status', 'accepted'}``."""
    grouped = TF.families(sidecar_rows)
    out = []
    for family in grouped:
        tic = family['tic_id']
        noise, host = noises[tic], hosts[tic]
        records = []
        for row in family['rows']:
            associations = [m for c in host['accepted'] if (m := M.candidate_match(row, c, noise['midpoint_btjd'])) is not None]
            records.append(dict(row_id=M.row_id(row), independence=row['independence'], in_band=M.in_band(row),
                                likely_periodic=M.likely(row), expected_snr=M.expected_snr(row, noise), associations=associations))
        strata = {}
        for stratum in M.STRATA:
            subset = [r for r in records if stratum == 'UNION' or r['independence'] == stratum]
            if not subset:
                continue
            rep = M.representative([row for row, r in zip(family['rows'], records) if r in subset])
            strata[stratum] = dict(in_band=any(r['in_band'] for r in subset),
                                   likely_periodic_in_band=any(r['in_band'] and r['likely_periodic'] for r in subset),
                                   expected_snr=M.expected_snr(rep, noise), period=M.finite(rep.get('tce_period')),
                                   survey_p10=recovery_summary(subset, host['status']))
        out.append(dict(tic_id=tic, anchor_period=family['anchor_period'], strata=strata, n_rows=len(records)))
    return out


def presence_for(families, p10_matching, p10_forced):
    """Carry the sealed P10.3 forced-fit presence to a P12 family by TIC and anchor period (1%)."""
    old = {}
    for family in p10_matching['ephemeris_families']:
        old.setdefault(int(family['tic_id']), []).append((float(family['anchor_period_days']),
                                                         p10_forced['families'][family['family_id']]['presence']))
    for family in families:
        hits = [presence for period, presence in old.get(family['tic_id'], [])
                if abs(period / family['anchor_period'] - 1) < 0.01]
        family['presence'] = hits[0] if len(hits) == 1 else 'UNMEASURED' if not hits else 'AMBIGUOUS'
    return families


def state(summary):
    s = summary['status']
    return 'PASS' if s.startswith('RECOVERED_') else 'FAIL' if s == 'NOT_RECOVERED' else 'OUTSIDE_DOMAIN' if s == 'OUTSIDE_DOMAIN' else 'UNKNOWN'


def present_table(families, stratum='INDEPENDENT', seed=2026092001, draws=10000):
    rows = [f for f in families if stratum in f['strata'] and f['strata'][stratum]['in_band'] and f.get('presence') == 'PRESENT'
            and state(f['strata'][stratum]['survey_p10']) in ('PASS', 'FAIL')]
    recovered = [f for f in rows if state(f['strata'][stratum]['survey_p10']) == 'PASS']
    hosts = sorted({f['tic_id'] for f in rows})
    index = {h: i for i, h in enumerate(hosts)}
    n, d = np.zeros(len(hosts)), np.zeros(len(hosts))
    for f in rows:
        d[index[f['tic_id']]] += 1
    for f in recovered:
        n[index[f['tic_id']]] += 1
    ci = None
    if hosts:
        rng = np.random.Generator(np.random.PCG64(seed))
        w = rng.multinomial(len(hosts), np.full(len(hosts), 1 / len(hosts)), size=draws)
        num, den = w @ n, w @ d
        good = den > 0
        ci = np.percentile(num[good] / den[good], [2.5, 97.5]).tolist()
    return dict(stratum=stratum, present_families=len(rows), recovered=len(recovered),
                fraction=len(recovered) / len(rows) if rows else None, ci95=ci, hosts=len(hosts),
                per_host={str(h): dict(recovered=int(n[index[h]]), present=int(d[index[h]])) for h in hosts},
                bootstrap=dict(seed=seed, draws=draws, bit_generator='PCG64', unit='whole host'))


def _sidecar_rows(path, tics):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        return [r for r in csv.DictReader(stream) if int(r['ticid']) in tics]


def run(arm, lock_phase):
    lock = ROOT / f'manifests/{lock_phase}_predictions_lock.json'
    seal = read(lock.with_name(lock.stem + '_seal.json'))
    if sha(lock) != seal['sha256']:
        raise RuntimeError('Prediction lock changed')
    locked = read(lock)
    hosts = {}
    for job in locked['jobs']:
        tic = int(job['job_id'][3:])
        hosts[tic] = dict(status=job['status'], accepted=job['accepted'])
    noises = {tic: read(ROOT / f'results/native_noise/{arm}/tic{tic}.json') for tic in hosts}
    sidecar = read(ROOT / 'manifests/sidecar_p12.json')
    if sha(REPO / sidecar['path']) != sidecar['sha256']:
        raise RuntimeError('STOP-1: P12 sidecar differs from its seal')
    rows = _sidecar_rows(REPO / sidecar['path'], set(hosts))
    for tic in sorted(hosts):
        append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=tic, stage=f'Part 2 real-signal leg ({arm}): search-level sidecar match',
            path=sidecar['path'], reader='retention_p12.py', prompt_of_origin='P12', content='TCE rows matched to locked predictions by script'))
    families = presence_for(match(rows, hosts, noises), read(REPO / 'p10/part3/results/matching.json'),
                            read(REPO / 'p10/part3/results/forced_fits.json'))
    table = present_table(families)
    result = dict(utc=utc(), arm=arm, lock_phase=lock_phase, lock_sha256=sha(lock), sidecar_sha256=sidecar['sha256'],
                  hosts=len(hosts), host_unknowns=sum(1 for h in hosts.values() if h['status'] != 'COMPLETE'),
                  families=len(families), presence_counts={p: sum(1 for f in families if f['presence'] == p)
                                                           for p in sorted({f['presence'] for f in families})},
                  independent_present=table, family_records=families,
                  rule='P10.3: exact or 2, 3, 1/2, 1/3 within 1% with the epoch check; presence from the sealed P10.3 forced fits',
                  label='development-exposed, EB-contaminated real-signal instrument; search level')
    out = ROOT / f'results/part2/retention_{arm}.json'
    write(out, json.loads(json.dumps(result, default=float)), replace=out.exists())
    print(json.dumps(dict(arm=arm, present=table['present_families'], recovered=table['recovered'], ci95=table['ci95'])), flush=True)
    return result


def reproduce_p10_3():
    """156/377 from the sealed P10.3 predictions, sidecar and noise through this module's matcher."""
    predictions = read(REPO / 'p10/part3/manifests/predictions_survey_p10.json')
    hosts = {int(h['tic_id']): dict(status=h['status'], accepted=h['accepted']) for h in predictions['hosts']}
    noises = {tic: read(REPO / f'p10/part3/results/native_noise/tic{tic}.json') for tic in hosts}
    sidecar = read(REPO / 'p10/part3/manifests/sidecar.json')
    rows = _sidecar_rows(REPO / sidecar['path'], set(hosts))
    families = match(rows, hosts, noises)
    matching = read(REPO / 'p10/part3/results/matching.json')
    forced = read(REPO / 'p10/part3/results/forced_fits.json')
    for family, old in zip(families, matching['ephemeris_families']):
        family['presence'] = forced['families'][old['family_id']]['presence']
    return present_table(families)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('arm', choices=['archival', 'sml'])
    args = parser.parse_args(argv)
    run(args.arm, 'cal_a_real436' if args.arm == 'archival' else 'cal_b_real436')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
