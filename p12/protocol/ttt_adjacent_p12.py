"""LB1c adjacent-domain negatives (AMENDMENTS_P12.md, 2026-09-23; reported, never part of bar_met).

The P8 pool is an M-dwarf TIC query (Teff 2,000 to 3,600 K, radius <= 0.50), so a
pool join or the radius < 0.45 cut would reproduce the M-dwarf domain and N1.
LB1c therefore applies exactly the cuts the amendment enumerates to the TESS Ten
Thousand union already on disk:

  TIC Teff < 4500 K; 11.5 <= TIC Tmag <= 14.5; |b| >= 20 deg;
  >= 3 sectors_200s (sectors 56 to 105 with a QLP or TESS-SPOC light curve, the P8
  ``era_columns`` definition over the cached per-sector target lists);
  FFI-majority (``n_sectors_2min_in_search < n_sectors_200s / 2``, MIT 2-minute lists);
  core stars and E1 stars excluded.

Order: SHA-256 of ``20260908:ttt:<integer TIC>`` ascending; the first 30 go to
``p12/manifests/ttt_adjacent_negatives.csv`` and their ephemerides to the guarded
``data/survey/p12/negatives/truth/ttt_adjacent_ephemerides.json``.

``fetch`` (online, one bounded network step): TIC v8 columns for every union TIC by ID
list, in chunks, into ``data/survey/p12/negatives/adjacent/tic_union.csv``.
``select`` (offline): the cuts above; no ephemeris value is printed.
"""
from p12_common import REPO, ROOT, DATA, environment, read, write, sha, utc, append_jsonl
import argparse
import hashlib
import json
import time
import numpy as np
import pandas as pd

UNION = DATA / 'negatives/truth/ttt_journal_union_attempt5.csv'
OUT = DATA / 'negatives/adjacent'
LISTS = REPO / 'data/survey/cache/target_lists'
TWOMIN = REPO / 'data/survey/cache/twomin_lists'
TIC_COLUMNS = ["ID", "ra", "dec", "pmRA", "pmDEC", "Tmag", "e_Tmag", "Teff", "e_Teff", "logg", "rad", "e_rad",
               "mass", "e_mass", "lum", "lumclass", "contratio", "objType", "GAIA", "GAIAmag", "gaiabp",
               "gaiarp", "plx", "e_plx", "d", "e_d", "gallat", "gallong", "eclat", "eclong", "disposition",
               "Vmag", "Jmag", "Hmag", "Kmag", "numcont"]
CUTS = dict(teff_lt=4500.0, tmag_min=11.5, tmag_max=14.5, abs_b_min=20.0, min_sectors_200s=3,
            first_200s_sector=56, last_sector=105, ffi_majority='n_sectors_2min_in_search < n_sectors_200s / 2',
            excluded=['core (p12/manifests/targets_p12_core.csv)', 'E1 (p12/manifests/targets_ext_E1.csv)'],
            order='SHA-256(20260908:ttt:<integer TIC>) ascending', first=30)
CHUNK = 500


def _union_tics():
    frame = pd.read_csv(UNION, usecols=['tic_id'], low_memory=False)
    return sorted({int(t) for t in frame.tic_id})


def fetch():
    environment(offline=False)
    from astroquery.mast import Catalogs
    tics = _union_tics()
    OUT.mkdir(parents=True, exist_ok=True)
    frames, attempts = [], []
    started = time.perf_counter()
    for index in range(0, len(tics), CHUNK):
        ids = tics[index:index + CHUNK]
        last = None
        for attempt in range(1, 3):
            clock = time.perf_counter()
            try:
                table = Catalogs.query_criteria(catalog='Tic', ID=ids)
                df = table.to_pandas()
                df = df[[c for c in TIC_COLUMNS if c in df.columns]].rename(columns={'ID': 'tic_id'})
                df['tic_id'] = pd.to_numeric(df['tic_id']).astype('int64')
                frames.append(df)
                attempts.append(dict(chunk=index // CHUNK, attempt=attempt, status='COMPLETE', rows=len(df),
                                     requested=len(ids), seconds=round(time.perf_counter() - clock, 2)))
                last = None
                break
            except Exception as exc:
                last = f'{type(exc).__name__}: {exc}'[:300]
                attempts.append(dict(chunk=index // CHUNK, attempt=attempt, status='ERROR', error=last,
                                     seconds=round(time.perf_counter() - clock, 2)))
                time.sleep(15)
        if last is not None:
            write(ROOT / 'manifests/ttt_adjacent_fetch.json', dict(utc=utc(), status='OPERATIONAL_UNKNOWN',
                attempts=attempts, error=last), replace=True)
            raise RuntimeError('TIC chunk failed twice: ' + last)
    meta = pd.concat(frames, ignore_index=True).drop_duplicates('tic_id').sort_values('tic_id')
    path = OUT / 'tic_union.csv'
    with path.open('w', encoding='utf-8', newline='') as stream:
        meta.to_csv(stream, index=False, lineterminator='\n')
    receipt = dict(utc=utc(), status='COMPLETE', source='MAST Catalogs.query_criteria(catalog="Tic", ID=[...]) TIC v8',
        requested=len(tics), returned=int(len(meta)), missing=len(set(tics) - set(meta.tic_id.astype(int))),
        chunks=len(attempts), attempts=attempts, wall_seconds=round(time.perf_counter() - started, 1),
        path=path.relative_to(REPO).as_posix(), sha256=sha(path), union_sha256=sha(UNION))
    write(ROOT / 'manifests/ttt_adjacent_fetch.json', receipt, replace=True)
    for tic in tics:
        append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=int(tic),
            stage='0f LB1c TIC metadata fetch (TIC identifiers only from the union)', path=UNION.relative_to(REPO).as_posix(),
            reader='ttt_adjacent_p12.py fetch', prompt_of_origin='P12', content='TIC identifiers only; no ephemeris displayed'))
    print(json.dumps({k: receipt[k] for k in ('status', 'requested', 'returned', 'missing', 'wall_seconds')}), flush=True)
    return receipt


def _sectors(ids, name, pattern, first, last):
    have = {}
    for sector in range(first, last + 1):
        status = pattern.parent / (pattern.name.format(sector=sector).replace('.npy', '.status'))
        npy = pattern.parent / pattern.name.format(sector=sector)
        if not npy.exists() or not status.exists() or status.read_text().strip() != 'ok':
            continue
        listed = np.load(npy)
        for tic in ids[np.isin(ids, listed)]:
            have.setdefault(int(tic), []).append(sector)
    return have


def lightcurve_columns(ids):
    ids = np.asarray(sorted(set(int(t) for t in ids)), dtype=np.int64)
    qlp = _sectors(ids, 'qlp', LISTS / 'qlp_s{sector:04d}.npy', 1, CUTS['last_sector'])
    spoc = _sectors(ids, 'tess-spoc', LISTS / 'tess-spoc_s{sector:04d}.npy', 1, CUTS['last_sector'])
    twomin = _sectors(ids, 'twomin', TWOMIN / 's{sector:03d}.npy', 1, CUTS['last_sector'])
    rows = []
    for tic in ids:
        anylc = sorted(set(qlp.get(int(tic), [])) | set(spoc.get(int(tic), [])))
        s200 = [s for s in anylc if s >= CUTS['first_200s_sector']]
        two = sorted(set(twomin.get(int(tic), [])) & set(s200))
        rows.append(dict(tic_id=int(tic), n_sectors_qlp=len(qlp.get(int(tic), [])), n_sectors_tess_spoc=len(spoc.get(int(tic), [])),
                         sectors_200s=','.join(map(str, s200)), n_sectors_200s=len(s200),
                         sectors_2min_in_search=','.join(map(str, two)), n_sectors_2min_in_search=len(two)))
    return pd.DataFrame(rows)


def list_status():
    missing = {}
    for name, pattern in (('qlp', 'qlp_s{:04d}.status'), ('tess-spoc', 'tess-spoc_s{:04d}.status')):
        missing[name] = [s for s in range(CUTS['first_200s_sector'], CUTS['last_sector'] + 1)
                         if not (LISTS / pattern.format(s)).exists() or (LISTS / pattern.format(s)).read_text().strip() != 'ok']
    missing['twomin'] = [s for s in range(CUTS['first_200s_sector'], CUTS['last_sector'] + 1)
                         if not (TWOMIN / f's{s:03d}.status').exists() or (TWOMIN / f's{s:03d}.status').read_text().strip() != 'ok']
    return missing


def select_adjacent(meta, lc, excluded):
    frame = meta.merge(lc, on='tic_id', how='left')
    counts = dict(union_with_tic_metadata=int(len(frame)))
    s = frame[pd.to_numeric(frame.Teff, errors='coerce') < CUTS['teff_lt']]; counts['teff_lt_4500'] = int(len(s))
    tmag = pd.to_numeric(s.Tmag, errors='coerce')
    s = s[(tmag >= CUTS['tmag_min']) & (tmag <= CUTS['tmag_max'])]; counts['tmag_11.5_to_14.5'] = int(len(s))
    s = s[pd.to_numeric(s.gallat, errors='coerce').abs() >= CUTS['abs_b_min']]; counts['abs_b_ge_20'] = int(len(s))
    s = s[s.n_sectors_200s >= CUTS['min_sectors_200s']]; counts['ge_3_sectors_200s_with_lc'] = int(len(s))
    s = s[s.n_sectors_2min_in_search < s.n_sectors_200s / 2.0]; counts['ffi_majority'] = int(len(s))
    s = s[~s.tic_id.isin(excluded)].copy(); counts['core_and_E1_excluded'] = int(len(s))
    s['selection_sha256'] = s.tic_id.map(lambda tic: hashlib.sha256(f'20260908:ttt:{int(tic)}'.encode()).hexdigest())
    s = s.sort_values(['selection_sha256', 'tic_id'], kind='stable')
    return s.head(CUTS['first']).reset_index(drop=True), counts


def select():
    if (ROOT / 'manifests/ttt_adjacent_negatives.csv').exists():
        raise FileExistsError('LB1c selection is immutable')
    fetched = read(ROOT / 'manifests/ttt_adjacent_fetch.json')
    meta_path = REPO / fetched['path']
    if fetched.get('status') != 'COMPLETE' or sha(meta_path) != fetched['sha256']:
        raise RuntimeError('LB1c TIC metadata incomplete or changed')
    meta = pd.read_csv(meta_path, low_memory=False)
    lc = lightcurve_columns(meta.tic_id)
    core = pd.read_csv(ROOT / 'manifests/targets_p12_core.csv', usecols=['tic_id']).tic_id.astype(int)
    e1 = pd.read_csv(ROOT / 'manifests/targets_ext_E1.csv', usecols=['tic_id']).tic_id.astype(int)
    selected, counts = select_adjacent(meta, lc, set(core) | set(e1))
    union = pd.read_csv(UNION, low_memory=False)
    lb1a = pd.read_csv(ROOT / 'manifests/ttt_negatives.csv', usecols=['tic_id']).tic_id.astype(int)
    truth = union[union.tic_id.isin(selected.tic_id)]
    manifest = ROOT / 'manifests/ttt_adjacent_negatives.csv'
    with manifest.open('x', encoding='utf-8', newline='') as stream:
        selected.to_csv(stream, index=False, lineterminator='\n')
    truth_path = DATA / 'negatives/truth/ttt_adjacent_ephemerides.json'
    write(truth_path, dict(utc=utc(), source='TESS Ten Thousand journal MRT union (Tables 3 and 4), attempt 5',
        records=json.loads(truth.to_json(orient='records', double_precision=15))))
    receipt = dict(utc=utc(), status='COMPLETE', clause='LB1c adjacent domain (K and late-K dwarfs), not the M-dwarf domain',
        cuts=CUTS, counts=counts, selected=int(len(selected)), overlap_with_LB1a=sorted(set(selected.tic_id) & set(lb1a)),
        target_lists_missing_sectors_56_105=list_status(), manifest_sha256=sha(manifest),
        guarded_ephemerides_path=truth_path.relative_to(REPO).as_posix(), ephemerides_sha256=sha(truth_path),
        tic_metadata_sha256=sha(meta_path), union_sha256=sha(UNION),
        radius_and_pool_join='not applied: the enumerated LB1c cuts omit them and both encode the M-dwarf domain',
        teff_tmag_source='TIC v8 (fetch step), the columns the P8 domain cuts use')
    write(ROOT / 'manifests/ttt_adjacent_selection.json', receipt)
    for tic in sorted(union.tic_id.astype(int).unique()):
        append_jsonl(ROOT / 'manifests/exposure_ledger.jsonl', dict(utc=utc(), star=int(tic),
            stage='0f LB1c adjacent-domain selection', path=UNION.relative_to(REPO).as_posix(),
            reader='ttt_adjacent_p12.py select', prompt_of_origin='P12',
            content='catalogue evaluator only; no candidate prediction or ephemeris values displayed'))
    print(json.dumps(dict(selected=receipt['selected'], counts=counts, overlap_with_LB1a=len(receipt['overlap_with_LB1a']))), flush=True)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['fetch', 'select'])
    args = parser.parse_args(argv)
    fetch() if args.action == 'fetch' else select()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
