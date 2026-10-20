"""Inverse-variance combination of recur.py output (TESS-SPOC s2/29/42/69/70 + QLP s92, survey ephemeris)."""
import json, sys, numpy as np
R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else '../results/recur.json'))
use = [r for r in R if r['eph'] == 'survey_eph' and (r['prod'] == 'spoc' or r['sector'] == 92)]
for name, k, e in [('depth', 'depth', 'err'), ('odd', 'odd', 'odd_e'), ('even', 'even', 'even_e'), ('phase0.5', 'sec', 'sec_e')]:
    v = np.array([r[k] for r in use]); s = np.array([r[e] for r in use]); w = 1 / s**2
    m = (v * w).sum() / w.sum(); chi = (((v - m) / s) ** 2).sum()
    print(f"{name:9s} {m:.2f} +- {w.sum()**-0.5:.2f} ppt  chi2 {chi:.2f}/{len(v)-1}")
early = [r for r in use if r['sector'] in (2, 29, 42)]
v = np.array([r['depth'] for r in early]); s = np.array([r['err'] for r in early]); w = 1 / s**2
print('early-only (prospective) depth', round((v * w).sum() / w.sum(), 2), '+-', round(w.sum() ** -0.5, 2))
