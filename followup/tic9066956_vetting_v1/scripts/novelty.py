import requests, re, csv, io, datetime, socket
socket.setdefaulttimeout(90)
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
print('checked', now)
t = requests.get("https://exofop.ipac.caltech.edu/tess/target.php?id=9066956", timeout=90).text
for lab in ['TOIs', 'CTOIs', 'Imaging', 'Spectroscopy', 'Time Series', 'Files', 'Planet Parameters']:
    m = re.search(re.escape(lab) + r'\s*\((\d+)\)', t)
    print(lab, m.group(1) if m else 'n/a')
for name, url in [('TOI', "https://exofop.ipac.caltech.edu/tess/json/tois.csv"), ('CTOI', "https://exofop.ipac.caltech.edu/tess/json/ctois.csv")]:
    r = requests.get(url, timeout=120)
    rows = list(csv.DictReader(io.StringIO(r.text)))
    hits = [x for x in rows if x.get('TIC ID', '').strip() == '9066956']
    # any candidate with P within 0.2% of 0.71345 d (or 2x / 0.5x) within 1 deg
    near = []
    for x in rows:
        try:
            ra = float(x['RA']) if ':' not in x['RA'] else None
            de = float(x['Dec']) if ':' not in x['Dec'] else None
            p = float(x.get('Period (days)') or 'nan')
        except Exception:
            continue
        if ra is None: continue
        if abs(de + 11.797) < 1.0 and abs((ra - 356.609) * 0.979) < 1.0:
            near.append((x.get('TOI') or x.get('CTOI'), x['TIC ID'], p))
    print(name, 'rows', len(rows), 'last-modified', r.headers.get('Last-Modified'), 'exact TIC hits', len(hits), 'within 1 deg', near)
