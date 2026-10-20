import json, sys
import astropy.units as u
from astropy.coordinates import SkyCoord
from astroquery.vizier import Vizier

Vizier.TIMEOUT = 90
c = SkyCoord(356.609026 * u.deg, -11.797127 * u.deg)
cats = ['J/A+A/649/A6/table1c', 'J/A+A/657/A7/tablea3', 'J/A+A/669/A104/catalog', 'J/A+A/677/A137/catalog',
        'J/A+A/684/A29/extend', 'J/A+A/692/A115/pristine_ca', 'J/AJ/155/180/table1', 'J/AJ/156/102/table9',
        'J/AJ/158/93/table2', 'J/AJ/159/84/table2', 'J/AJ/161/234/table2', 'J/AJ/161/234/table3',
        'J/AJ/161/234/table4', 'J/AJ/161/234/table5', 'J/AJ/165/267/table1', 'J/ApJ/984/58/table1',
        'J/MNRAS/486/251/tablea1', 'V/160/shboost', 'I/355/paramp', 'IV/34/epic', 'IV/39/tic82']
v = Vizier(columns=["**"], row_limit=3)
for cat in cats:
    base = cat.rsplit('/', 1)[0] if cat.count('/') > 2 else cat
    try:
        meta = Vizier(row_limit=1).get_catalog_metadata(catalog=base)
        title = str(meta['title'][0]) if 'title' in meta.colnames else ''
    except Exception as e:
        title = f'(meta err {e})'
    try:
        t = v.query_region(c, radius=3 * u.arcsec, catalog=cat)
        if len(t):
            row = t[0][0]
            vals = {k: str(row[k]) for k in t[0].colnames if str(row[k]) not in ('--', '', 'nan')}
        else:
            vals = 'no rows'
    except Exception as e:
        vals = f'ERR {e}'
    print(f'### {cat} :: {title}')
    print(json.dumps(vals)[:1500])
