"""Stage D pixel records for K7 and K9: difference images and fixed apertures.

Copied from ``scripts/p8_eb_difference_image.py`` and ``scripts/p8_target_aperture.py``
(whose ``main`` functions refuse any non-P8 record and write under ``data/survey/p8``).
The pure pixel methods are imported read-only: ``event_differences``
(p8_eb_difference_image), ``extract`` (p8_eb_aperture) and
``tesshunter.secondary.box_depth``. Output formats are the ``eb_screen`` records
that ``verdict_tiers.load_inputs`` reads:
``eb_screen/<key>_fit_difference.{json,npz}`` and ``eb_screen/<key>_target_aperture.{json,npz}``.
A sector whose aperture has fewer than 16 clean sky pixels is recorded unmeasurable,
never "no contamination" (gotcha 16). Cutouts come from the D-drive TESScut cache the
centroid step filled; no cutout is downloaded here.

Superseded 2026-09-23 (AMENDMENTS_P12.md, the Part 1d plumbing fix): the Gaia DR3 cone of ``gaia_positions``
runs with a hard wall limit. The same query is tried synchronously (``Gaia.launch_job``, bounded at
``GAIA_SYNC_S``; a result at the synchronous row cap is not accepted) and then asynchronously
(``launch_job_async``, bounded at ``GAIA_ASYNC_S``); each attempt runs in a daemon thread the caller abandons at its
limit (as ``survivor_packets.py`` abandons a stalled TESScut transfer), so an abandoned query never holds the exit. The plumbing run of 2026-09-23 held a
worker 40+ minutes on one unbounded asynchronous Gaia job. When both attempts fail the error is raised and the
pixel step records it (H3 holds); the query text and the accepted table are unchanged.
"""
from p12_common import REPO, sha, utc, write
import json
import math
import warnings
from pathlib import Path

import numpy as np

GAIA_RADIUS_DEG = 0.075
GAIA_SYNC_S = 300.0
GAIA_ASYNC_S = 900.0
GAIA_SYNC_ROW_CAP = 2000


def _bounded(function, limit):
    """Run ``function`` in a daemon thread; abandon it at ``limit`` (a daemon thread never holds the exit)."""
    import threading
    box = {}

    def target():
        try:
            box['value'] = function()
        except BaseException as exc:  # carried to the caller
            box['error'] = exc
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(limit)
    if thread.is_alive():
        raise TimeoutError(f'Gaia query exceeded {limit:.0f} s')
    if 'error' in box:
        raise box['error']
    return box['value']


def gaia_positions(ra, dec, out_path):
    """Gaia DR3 astrometry and magnitudes in a 4.5-arcmin cone (the P9 query), cached."""
    out_path = Path(out_path)
    if out_path.is_file():
        record = json.loads(out_path.read_text(encoding='utf-8'))
        if record.get('status') == 'complete':
            return record
    from astroquery.gaia import Gaia
    query = ("SELECT source_id,ra,dec,pmra,pmdec,phot_g_mean_mag,phot_rp_mean_mag FROM gaiadr3.gaia_source "
             f"WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{float(ra)},{float(dec)},{GAIA_RADIUS_DEG}))")
    attempts, table = [], None
    for mode, limit in (('sync', GAIA_SYNC_S), ('async', GAIA_ASYNC_S)):
        try:
            if mode == 'sync':
                result = _bounded(lambda: Gaia.launch_job(query, dump_to_file=False).get_results(), limit)
                if len(result) >= GAIA_SYNC_ROW_CAP:
                    attempts.append(dict(mode=mode, status='ROW_CAP', rows=len(result)))
                    continue
            else:
                result = _bounded(lambda: Gaia.launch_job_async(query, dump_to_file=False).get_results(), limit)
            attempts.append(dict(mode=mode, status='COMPLETE', rows=len(result)))
            table = result
            break
        except Exception as exc:
            attempts.append(dict(mode=mode, status='FAILED', error=f'{type(exc).__name__}: {exc}'[:300]))
    if table is None:
        raise RuntimeError(f'Gaia positions unavailable after bounded attempts: {attempts}')
    rows = []
    for r in table:
        row = {}
        for name in table.colnames:
            key = name.lower()
            if np.ma.is_masked(r[name]):
                row[key] = None
            elif key == 'source_id':
                row[key] = int(r[name])
            else:
                v = float(r[name])
                row[key] = v if math.isfinite(v) else None
        rows.append(row)
    record = dict(utc=utc(), status='complete', query=query, source='Gaia DR3 TAP; astrometry and magnitudes only', objects=rows,
                  attempts=attempts)
    write(out_path, record, replace=out_path.exists())
    return record


def _cutout(cache, sector, ra, dec):
    pattern = f"tess-s{int(sector):04d}-*_{float(ra):.6f}_{float(dec):.6f}_21x21_astrocut.fits"
    paths = sorted(Path(cache).glob(pattern))
    return paths[0] if len(paths) == 1 else None


def _positions(objects, tpf, time, shape):
    from astropy.coordinates import SkyCoord
    from astropy.time import Time
    import astropy.units as u
    out = []
    for obj in objects:
        if obj.get('pmra') is not None and obj.get('pmdec') is not None:
            coord = SkyCoord(obj['ra'] * u.deg, obj['dec'] * u.deg, pm_ra_cosdec=obj['pmra'] * u.mas / u.yr,
                             pm_dec=obj['pmdec'] * u.mas / u.yr, obstime=Time(2016, format='jyear'))
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                coord = coord.apply_space_motion(new_obstime=Time(np.median(time) + 2457000, format='jd'))
        else:
            coord = SkyCoord(obj['ra'], obj['dec'], unit='deg')
        x, y = tpf.wcs.world_to_pixel(coord)
        if -0.5 <= x < shape[1] - 0.5 and -0.5 <= y < shape[0] - 0.5:
            out.append(dict(source_id=int(obj['source_id']), x=float(x), y=float(y), G=obj.get('phot_g_mean_mag')))
    return out


def difference(root, key, ephemeris, sectors, gaia, neighbours, cutout_cache, sources):
    """Local out-minus-in difference images at the fit ephemeris, per sector with a cutout."""
    import lightkurve as lk
    import astropy.units as u
    import p8_eb_difference_image as I
    root = Path(root)
    target_id = int(((neighbours.get('gaia') or {}).get('target') or {}).get('source_id') or -1)
    records, arrays, inputs = [], {}, list(sources)
    for sector in sectors:
        path = _cutout(cutout_cache, sector, neighbours['ra'], neighbours['dec'])
        if path is None:
            records.append(dict(sector=sector, status='unavailable', error='no cached 21x21 cutout for this sector'))
            continue
        try:
            tpf = lk.TessTargetPixelFile(str(path))
            time, flux = np.asarray(tpf.time.value), np.asarray(tpf.flux.to_value(u.electron / u.s))
            finite = np.isfinite(time)
            time, flux = time[finite], flux[finite]
            p = I.event_differences(time, flux, ephemeris['period'], ephemeris['t0'], ephemeris['duration'])
            s = I.event_differences(time, flux, ephemeris['period'], ephemeris['t0'] + ephemeris['period'] / 2, ephemeris['duration'])
            positions = _positions(gaia['objects'], tpf, time, flux.shape[1:])
            for pos in positions:
                pos['label'] = 'T' if pos['source_id'] == target_id else None
            maxima = {}
            for name, result in (('primary', p), ('secondary', s)):
                y, x = np.unravel_index(np.nanargmax(result['difference']), result['difference'].shape)
                maxima[name] = dict(row=int(y), column=int(x), difference_e_per_s=float(result['difference'][y, x]))
                for field in ('difference', 'event_scatter', 'reference'):
                    arrays[f's{sector}_{name}_{field}'] = result[field]
            records.append(dict(sector=sector, status='complete', n_cadences=len(time),
                                time_range_btjd=[float(time.min()), float(time.max())],
                                median_cadence_s=float(np.median(np.diff(time)) * 86400), primary_counts=p['counts'],
                                secondary_counts=s['counts'], gaia_positions=positions, maximum_pixels=maxima,
                                cutout=path.name))
            inputs.append(path)
        except Exception as exc:
            records.append(dict(sector=sector, status='error', error=f'{type(exc).__name__}: {exc}'[:300]))
    stem = root / 'eb_screen' / f'{key}_fit_difference'
    stem.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(stem.with_name(stem.name + '.npz'), **arrays)
    record = dict(key=key, ephemeris=ephemeris, scope='Pixel diagnostic for K7a; no source identity or verdict is assigned here.',
                  method=I.event_differences.__doc__, sectors=[r for r in records if r.get('status') == 'complete'],
                  sector_attempts=records, source_sha256={_rel(p): sha(p) for p in inputs}, generated_utc=utc())
    stem.with_name(stem.name + '.json').write_text(json.dumps(record, indent=1, allow_nan=False) + '\n', encoding='utf-8')
    return record


def aperture(root, key, ephemeris, diff_record, neighbours, cutout_cache):
    """The one-pixel target aperture and 5-9-pixel sky annulus at the fit ephemeris (K7b, K9)."""
    import lightkurve as lk
    import astropy.units as u
    from p8_eb_aperture import extract
    from tesshunter.secondary import box_depth
    root = Path(root)
    target_id = int(((neighbours.get('gaia') or {}).get('target') or {}).get('source_id') or -1)
    period, epoch, width = ephemeris['period'], ephemeris['t0'], ephemeris['duration']
    records, arrays = [], {}
    for sector in diff_record['sectors']:
        sec = sector['sector']
        source = next((o for o in sector['gaia_positions'] if o['source_id'] == target_id), None)
        path = _cutout(cutout_cache, sec, neighbours['ra'], neighbours['dec'])
        if source is None or path is None:
            records.append(dict(sector=sec, status='unmeasurable', n_background_pixels=0,
                                error='target position or cutout unavailable'))
            continue
        try:
            tpf = lk.TessTargetPixelFile(str(path))
            cube = np.asarray(tpf.flux.to_value(u.electron / u.s))
            yy, xx = np.indices(cube.shape[1:])
            r2 = (xx - source['x']) ** 2 + (yy - source['y']) ** 2
            background = (r2 >= 25) & (r2 <= 81)
            for star in sector['gaia_positions']:
                if star.get('G') is not None and star['G'] < 18:
                    background &= (xx - star['x']) ** 2 + (yy - star['y']) ** 2 > 4
            n_sky = int(background.sum())
            try:
                net, ap, bkg = extract(cube, source, sector['gaia_positions'])
            except ValueError as exc:
                records.append(dict(sector=sec, status='unmeasurable', n_background_pixels=n_sky, error=str(exc)))
                continue
            raw = np.sum(cube[:, ap], axis=1)
            sky = raw - net
            time = np.asarray(tpf.time.value)
            keep = np.isfinite(time) & np.isfinite(net) & np.isfinite(raw)
            time, net, raw, sky = (v[keep] for v in (time, net, raw, sky))
            normalization = float(np.median(net))
            if normalization <= 0:
                records.append(dict(sector=sec, status='unmeasurable', n_background_pixels=n_sky,
                                    error='nonpositive net aperture normalization'))
                continue
            series = {'net': net / normalization, 'raw': 1 + (raw - np.median(raw)) / normalization,
                      'sky': 1 + (sky - np.median(sky)) / normalization}
            measurements = {name: box_depth(time, values, 0, period, epoch, width) for name, values in series.items()}
            for name, array in {'time': time, **series, 'aperture': ap, 'background': bkg}.items():
                arrays[f's{sec}_{name}'] = array
            records.append(dict(sector=sec, status='complete', position=source, n_cadences=len(time),
                                n_aperture_pixels=int(ap.sum()), n_background_pixels=int(bkg.sum()),
                                net_normalization_e_per_s=normalization, measurements=measurements))
        except Exception as exc:
            records.append(dict(sector=sec, status='error', n_background_pixels=0, error=f'{type(exc).__name__}: {exc}'[:300]))
    stem = root / 'eb_screen' / f'{key}_target_aperture'
    np.savez_compressed(stem.with_name(stem.name + '.npz'), **arrays)
    record = dict(key=key, source_gaia_id=target_id, ephemeris=ephemeris, method=extract.__doc__,
                  limitations='Fixed apertures remain diluted; no detrending, ephemeris refit or gate change. Box errors use local '
                              'point scatter and omit some correlated noise. A sector below 16 clean sky pixels is unmeasurable.',
                  sectors=records, source_sha256={_rel(root / 'eb_screen' / f'{key}_fit_difference.json'):
                                                  sha(root / 'eb_screen' / f'{key}_fit_difference.json')}, generated_utc=utc())
    stem.with_name(stem.name + '.json').write_text(json.dumps(_finite(record), indent=1, allow_nan=False) + '\n', encoding='utf-8')
    return record


def _rel(path):
    path = Path(path)
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def _finite(value):
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(v) for v in value]
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value
