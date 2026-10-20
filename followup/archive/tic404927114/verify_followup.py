"""Check scientific products against original inputs and write a full hash inventory.

This verifier does not import the analysis module or alter original inputs.
Assertions check numerical consistency, input/time/flag provenance, and coverage;
passing them does not establish that the adopted physical model is correct.
"""
from pathlib import Path
from datetime import datetime, timezone
from importlib.metadata import version
import hashlib
import json
import platform
import re
import subprocess
import sys
import traceback
import numpy as np
import pandas as pd
from astropy.io import fits
from astropy.coordinates import SkyCoord
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / 'measurements'
P8 = REPO / 'data/survey/p8'
REPORT = REPO / 'docs/TIC404927114_FOLLOWUP.md'
TID = '4659930359605646592'
BASELINE = 'fbc68571'
CHECKS = []
INPUTS = set()


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check(name, fn):
    try:
        detail = fn()
        CHECKS.append({'name': name, 'passed': True, 'detail': detail})
        print('PASS:', name, flush=True)
    except Exception:
        CHECKS.append({'name': name, 'passed': False, 'error': traceback.format_exc()})
        print('FAIL:', name, flush=True)


def preservation():
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    changed = subprocess.check_output(['git', 'diff', '--name-only', BASELINE], cwd=REPO, text=True).splitlines()
    forbidden = [p for p in changed if not (p.startswith('followups/tic404927114/') or p == 'docs/TIC404927114_FOLLOWUP.md')]
    assert not forbidden, forbidden
    previous = read(OUT / 'run_manifest.json')['source_sha256']
    original = {p: h for p, h in previous.items() if not p.startswith('followups/')}
    for name, digest in original.items():
        path = REPO / name
        assert sha(path) == digest, name
        INPUTS.add(path)
    return {'baseline': BASELINE, 'head': head, 'changed_original_tracked_files': forbidden,
            'original_run_hashes_rechecked': len(original)}


def source_association():
    path = P8 / 'neighbours/tic404927114.json'
    nb = read(path)
    assert str(nb['gaia']['target']['source_id']) == TID
    INPUTS.add(path)
    cone = read(P8 / 'eb_screen/tic404927114_gaia_cone_300arcsec.json')['objects']
    assert len(cone) == 3429
    gaia = next(s for s in cone if str(s['source_id']) == '4659943588105397760')
    ogle = read(OUT / 'catalogue_queries.json')['ogle_neighbours'][0]
    distance = SkyCoord(gaia['ra'], gaia['dec'], unit='deg').separation(
        SkyCoord(ogle['ra'], ogle['dec'], unit='deg')).arcsec
    assert distance < 1, distance
    for path in OUT.glob('s???_sources.json'):
        target = next(s for s in read(path) if s['source_id'] == TID)
        assert target['proper_motion_available']
        assert target['jyear'] > 2022
        assert target['dec_epoch'] > target['dec']
    return {'target_exact_gaia_id': TID, 'cone_n': len(cone), 'ogle_gaia_separation_arcsec': float(distance)}


def times_and_flags():
    metas = [read(p) for p in sorted(OUT.glob('s???.json'))]
    assert len(metas) == 12
    total = 0
    details = []
    for m in metas:
        pixel = REPO / m['path']
        qlp = REPO / m['qlp_path']
        INPUTS.update([pixel, qlp])
        with fits.open(pixel) as h:
            t = np.asarray(h[1].data['TIME'], dtype=float)
            quality = np.asarray(h[1].data['QUALITY'], dtype=np.int64)
        with fits.open(qlp) as h:
            qt = np.asarray(h[1].data['TIME'], dtype=float)
            qq = np.asarray(h[1].data['QUALITY'], dtype=np.int64)
        with np.load(OUT / f's{m["sector"]:03d}_series.npz') as a:
            # Independently identify the exposure by its exact saved target time.
            ix = np.searchsorted(qt, a['time'])
            assert np.all(ix < len(qt))
            np.testing.assert_array_equal(qt[ix], a['time'])
            assert len(np.unique(ix)) == len(t)
            delta = (qt[ix] - t) * 86400
            assert np.all(np.abs(delta) < 90)
            np.testing.assert_allclose(np.percentile(delta, [0, 50, 100]), m['time_match_delta_seconds'], atol=1e-7)
            expected_good = ((quality & 17087) == 0) & ((qq[ix] & (17087 | 2**30)) == 0)
            np.testing.assert_array_equal(a['good'], expected_good)
            np.testing.assert_array_equal(a['quality'], quality)
            np.testing.assert_array_equal(a['qlp_quality'], qq[ix])
        assert len(t) == m['n_cadences'] == m['matched_exposures']
        total += len(t)
        details.append({'sector': m['sector'], 'n_unique_matched': len(t)})
    assert total == 148549
    qmetas = read(OUT / 'qlp_metadata.json')
    assert len(qmetas) == 22
    for m in qmetas:
        sec = m['sector']
        files = list((REPO / 'data/cache/audit_lightkurve/mastDownload/HLSP').glob(f'*s{sec:04d}-0000000404927114*/*.fits'))
        assert len(files) == 1
        cached = REPO / f'data/survey/audit_lc/tic404927114/s{sec:03d}_QLP.npz'
        INPUTS.update([files[0], cached])
        with fits.open(files[0]) as h, np.load(cached) as a:
            np.testing.assert_array_equal(h[1].data['TIME'], a['time'])
            np.testing.assert_array_equal(h[1].data['QUALITY'], a['quality'])
    return {'total_pixel_exposures': total, 'qlp_fits_npz_agreement_sectors': 22, 'pixel_sectors': details}


def event_selection_and_depths():
    events = pd.read_csv(OUT / 'pixel_events.csv')
    assert len(events) == 14
    use = events[events.usable]
    assert len(use) == 6
    ephem = read(OUT / 'ephemerides.json')['ephemerides']['physical_fit']
    np.testing.assert_allclose(events.tc_btjd, ephem['epoch'] + events.cycle * ephem['period'], atol=1e-9)
    for p in OUT.glob('s???.json'):
        m = read(p)
        with np.load(OUT / f's{m["sector"]:03d}_images.npz') as a:
            assert a['control_maps'].shape == (80, 2025)
            assert np.all(np.isfinite(a['control_maps']))
            assert np.all(a['grid_den'] > 0)
            assert np.all(a['sigma'] > 0)
        for event in m['events']:
            if event['usable']:
                assert event['empirical_error_e_s'] >= event['white_error_e_s']
                assert event['empirical_error_e_s'] >= m['control_sigma_e_s'] - 1e-12
    depth = 1000 * use.depth_e_s / use.target_reference_flux
    err = 1000 * use.empirical_error_e_s / use.target_reference_flux
    w = 1 / err**2
    mean = float(np.sum(w * depth) / np.sum(w))
    error = float(1 / np.sqrt(np.sum(w)))
    summary = read(OUT / 'pixel_summary.json')
    np.testing.assert_allclose([mean, error], [summary['target_depth_ppt'], summary['target_error_ppt']], rtol=1e-12)
    return {'predicted': len(events), 'usable': len(use), 'target_depth_ppt': mean, 'error_ppt': error}


def localization_controls():
    s = read(OUT / 'pixel_summary.json')
    with np.load(OUT / 'stacked_localization.npz') as a:
        mask = np.linalg.norm(a['offsets_arcsec'], axis=1) <= 90
        peak = np.max(a['snr'][mask])
        tail = (1 + np.count_nonzero(a['null_max_snr'] >= peak)) / (1 + len(a['null_max_snr']))
        assert len(a['null_max_snr']) == 2000
        np.testing.assert_allclose([peak, tail], [s['peak_snr'], s['peak_control_global_tail_fraction']], rtol=1e-12)
    return {'peak_snr': float(peak), 'control_tail': float(tail)}


def injections():
    a = pd.read_csv(OUT / 'injections_with_physical_limits.csv', dtype={'source_id': str})
    assert len(a) == 864
    # All physical flags must reflect the saved source flux estimate.
    np.testing.assert_allclose(a.estimated_eclipse_fraction, a.injected_e_s / a.source_flux_estimate)
    np.testing.assert_array_equal(a.physically_possible_under_flux_estimate, a.estimated_eclipse_fraction <= 1)
    target = a[(a.source_id == TID) & (a.target_equiv_ppt == 4.5)]
    assert len(target) == 72
    np.testing.assert_array_equal(a.success, (a.peak_control_snr > 3) & (a.position_error_px < .5))
    p = pd.read_csv(OUT / 'physical_event_injections.csv', dtype={'source_id': str})
    np.testing.assert_allclose(p.increment_ratio, p.recovered_increment_e_s / p.expected_contrast_e_s, rtol=1e-12)
    np.testing.assert_allclose(p.after_injection_contrast_e_s - p.before_injection_e_s, p.recovered_increment_e_s, atol=1e-10)
    physical = p[(p.kind == 'target_physical_fit') & p.mismatch]
    assert len(physical) == 6
    assert np.all(physical.expected_contrast_e_s > 0)
    assert set(p[p.kind == 'neighbour_50percent_box'].intrinsic_eclipse_fraction) == {.5}
    return {'n_spatial': len(a), 'unique_sources': a.source_id.nunique(),
            'over_estimated_total_flux': int((~a.physically_possible_under_flux_estimate).sum()),
            'target_4p5ppt_success': target.groupby('mismatch').success.agg(['sum', 'count']).to_dict('index'),
            'altered_physical_transit_recovery_range': [float(physical.increment_ratio.min()), float(physical.increment_ratio.max())]}


def independent_and_older():
    s = read(OUT / 'independent_checks.json')
    a = pd.read_csv(OUT / 'gaia_epoch_photometry.csv')
    assert len(a) == s['gaia']['n_total']
    assert int(a.good.sum()) == s['gaia']['n_good']
    inside = a.good & (abs(a.hours_from_candidate) < 2.899 / 2)
    assert int(inside.sum()) == s['gaia']['n_in_candidate_window']
    grid = pd.read_csv(OUT / 'older_ephemeris_grid.csv')
    assert len(grid) == 49
    np.testing.assert_allclose(grid.snr.max(), s['old_grid_max_snr']['snr'])
    for name in ['catalogue_queries.json', 'independent_checks.json']:
        for r in read(OUT / name)['receipts']:
            assert 'error' not in r, r
            assert sha(HERE / 'archive' / r['path']) == r['sha256']
    return {'gaia_good': int(a.good.sum()), 'gaia_in_window': int(inside.sum()), 'older_grid_max_snr': float(grid.snr.max())}


def deliverables():
    for path in HERE.glob('*.py'):
        compile(path.read_text(encoding='utf8'), str(path), 'exec')
    links = re.findall(r'\]\(([^)]+)\)', REPORT.read_text(encoding='utf8'))
    local = [x for x in links if not x.startswith(('http:', 'https:', '#'))]
    for link in local:
        assert (REPORT.parent / link).resolve().exists(), link
    figures = list((HERE / 'figures').glob('*.png'))
    for path in figures:
        with Image.open(path) as im:
            assert min(im.size) >= 500
            im.verify()
    assert (HERE / 'measurements_initial_qlp_bitmask/s098.json').exists()
    assert (HERE / 'measurements_all_nonzero_qlp/s098.json').exists()
    return {'local_report_links': len(local), 'valid_pngs': len(figures), 'python_sources': len(list(HERE.glob('*.py')))}


def write_manifest():
    # Include target evidence even when it was inspected outside the main script.
    for path in P8.rglob('*'):
        if path.is_file() and ('404927114' in str(path.relative_to(P8)) or path.parent == P8):
            INPUTS.add(path)
    packet = REPO / 'docs/packets/audit_p8/tic404927114_P27.5436'
    INPUTS.update(p for p in packet.rglob('*') if p.is_file())
    INPUTS.update(p for p in (REPO / 'configs').rglob('*') if p.is_file())
    for name in ['HANDOFF_P8.md', 'docs/AUDIT_P8.md', 'src/tesshunter/audit_prep.py',
                 'scripts/survivor_packets.py', 'data/survey/audit_lc/tic404927114/index.json']:
        path = REPO / name
        assert path.exists(), name
        INPUTS.add(path)
    records = []
    for path in sorted(INPUTS):
        records.append({'role': 'original_input', 'path': path.relative_to(REPO).as_posix(),
                        'bytes': path.stat().st_size, 'sha256': sha(path)})
    for path in sorted([REPORT] + [p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                                   and p.name != 'audit_manifest.json']):
        rel = path.relative_to(REPO).as_posix()
        role = 'public_archive' if path.is_relative_to(HERE / 'archive') else 'followup_product_or_code'
        records.append({'role': role, 'path': rel, 'bytes': path.stat().st_size, 'sha256': sha(path)})
    result = {'created_utc': datetime.now(timezone.utc).isoformat(), 'repository_root_at_run': str(REPO),
              'baseline_commit': BASELINE, 'records': records,
              'note': 'Paths are repository-relative. SHA-256 fingerprints do not authenticate the source. Manifest excludes itself and Python bytecode.'}
    (HERE / 'audit_manifest.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    return len(records)


def main():
    for name, fn in [('P8 and input preservation', preservation), ('Exact source associations', source_association),
                     ('Exposure clocks and inherited masks', times_and_flags), ('Event products and weighted mean', event_selection_and_depths),
                     ('Empirical localization controls', localization_controls), ('Spatial and physical injections', injections),
                     ('Independent data and older ephemeris grid', independent_and_older), ('Code, links and figure integrity', deliverables)]:
        check(name, fn)
    result = {'utc': datetime.now(timezone.utc).isoformat(), 'python': sys.version, 'platform': platform.platform(),
              'versions': {p: version(p) for p in ['numpy', 'scipy', 'astropy', 'pandas', 'matplotlib', 'requests', 'batman-package']},
              'all_passed': all(c['passed'] for c in CHECKS), 'checks': CHECKS,
              'limits': 'Numerical consistency and input provenance checks; not a proof of the PRF/background model or astrophysical interpretation.'}
    (OUT / 'verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    if result['all_passed']:
        print('Manifest records:', write_manifest())
    else:
        print(json.dumps([c for c in CHECKS if not c['passed']], indent=2))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
