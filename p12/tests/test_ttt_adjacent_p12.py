import hashlib
import numpy as np
import pandas as pd
import ttt_adjacent_p12 as adjacent


def meta(rows):
    base = dict(Teff=4200.0, Tmag=13.0, gallat=35.0, rad=0.7, mass=0.7)
    return pd.DataFrame([dict(base, tic_id=t, **extra) for t, extra in rows])


def lc(rows):
    base = dict(n_sectors_200s=6, n_sectors_2min_in_search=0)
    return pd.DataFrame([dict(base, tic_id=t, **extra) for t, extra in rows])


def test_enumerated_cuts_each_fire_and_just_not_fire():
    ids = list(range(1, 15))
    m = meta([(1, {}), (2, dict(Teff=4500.0)), (3, dict(Teff=4499.0)), (4, dict(Tmag=11.49)), (5, dict(Tmag=11.5)),
              (6, dict(Tmag=14.5)), (7, dict(Tmag=14.51)), (8, dict(gallat=-19.99)), (9, dict(gallat=-20.0)),
              (10, {}), (11, {}), (12, {}), (13, {}), (14, dict(rad=2.0))])
    l = lc([(t, {}) for t in ids[:9]] + [(10, dict(n_sectors_200s=2)), (11, dict(n_sectors_200s=3)),
                                         (12, dict(n_sectors_200s=4, n_sectors_2min_in_search=2)),
                                         (13, dict(n_sectors_200s=5, n_sectors_2min_in_search=2)), (14, {})])
    selected, counts = adjacent.select_adjacent(m, l, excluded={1})
    assert set(selected.tic_id) == {3, 5, 6, 9, 11, 13, 14}
    assert counts['teff_lt_4500'] == 13 and counts['core_and_E1_excluded'] == 7
    # radius and pool membership are not cuts of LB1c (rad 2.0 kept)
    assert 14 in set(selected.tic_id)


def test_hash_order_and_first_thirty():
    ids = list(range(1000, 1100))
    selected, _ = adjacent.select_adjacent(meta([(t, {}) for t in ids]), lc([(t, {}) for t in ids]), excluded=set())
    expected = sorted(ids, key=lambda t: (hashlib.sha256(f'20260908:ttt:{t}'.encode()).hexdigest(), t))[:30]
    assert list(selected.tic_id) == expected


def test_lightcurve_columns_from_list_fixtures(tmp_path, monkeypatch):
    lists, twomin = tmp_path / 'lists', tmp_path / 'twomin'
    lists.mkdir(); twomin.mkdir()
    def put(folder, name, ids):
        np.save(folder / f'{name}.npy', np.asarray(ids, dtype=np.int64)); (folder / f'{name}.status').write_text('ok')
    put(lists, 'qlp_s0055', [7]); put(lists, 'qlp_s0056', [7, 8]); put(lists, 'tess-spoc_s0057', [7])
    put(lists, 'qlp_s0060', [7]); put(twomin, 's060', [7]); put(lists, 'qlp_s0061', [9])
    (lists / 'qlp_s0062.npy').write_bytes(b''); (lists / 'qlp_s0062.status').write_text('missing')
    monkeypatch.setattr(adjacent, 'LISTS', lists); monkeypatch.setattr(adjacent, 'TWOMIN', twomin)
    frame = adjacent.lightcurve_columns([7, 8, 9, 10]).set_index('tic_id')
    assert frame.loc[7, 'sectors_200s'] == '56,57,60' and frame.loc[7, 'n_sectors_200s'] == 3
    assert frame.loc[7, 'n_sectors_2min_in_search'] == 1 and frame.loc[10, 'n_sectors_200s'] == 0
