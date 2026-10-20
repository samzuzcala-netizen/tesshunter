"""Pull planet vs best-triple parameters and per-band depths from the Codex class906v2 continuous fits."""
import json
B = r"C:/Users/seanj/Documents/Codex/2026-10-05/can-you-look-at-all-the/class906v2/results/"
m = json.load(open(B + "continuous_models.json"))
for fam in ("planet", "triple"):
    x = sorted([y for y in m if y['name'] == fam], key=lambda y: y['chi_total'])[0]
    print('==', fam, 'chi_total', round(x['chi_total'], 2), 'near_bounds', x.get('near_bounds'), 'impact', round(x['impact'], 3))
    for comp in ('primary', 'secondary', 'tertiary'):
        o = x.get(comp)
        if o: print('  ', comp, {k: round(o[k], 4) for k in ('m', 'r', 'r0', 'inflate', 't', 't0', 'suppress') if k in o})
    print('   depths ppt', {b: round(v['primary'] * 1e3, 2) for b, v in x['depths'].items()})
nc = json.load(open(B + "triple_no_cooling.json")); nc = nc if isinstance(nc, list) else [nc]
p = nc[0]['primary']
print('== no-cooling triple chi', round(nc[0]['chi_total'], 2), {k: round(p[k], 4) for k in ('m', 'r', 'r0', 'inflate', 't', 'suppress')})
