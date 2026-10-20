"""Replay the recorded P8 mask-timing discrepancy without changing calibration inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(repo / 'src'), str(repo / 'scripts')]
os.environ['LIGHTKURVE_CACHE'] = str(repo / 'data/cache/lightkurve')
for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[name] = '1'
import audit_p5 as A
import p8_completeness as C
import p8_decisions as D
from tesshunter.survey import get_config

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--job', default='inj01014_tic234507624')
parser.add_argument('--out', default='data/survey/p8/decision_mask_replay_p8.json')
args = parser.parse_args()
key = args.job
job = next(j for j in C.recovered_jobs(C._load_results(C.INJ_RUN)) if j['job_id'] == key)
source = D.injection_job(job)
root = C.P8 / 'inj_funnel' / key
paths = [C.P8 / 'decisions/inj' / f'{key}.json', *root.glob('stageA/*.json'), *root.glob('secondary/*.json')]
hashes = {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
baseline = json.loads(next(root.glob('stageA/*.json')).read_text())
prep = json.loads(next(root.glob('prep/*.json')).read_text())
mask_eph = prep['transit_masked_detrend']['ephemeris']
A.set_input_config(get_config('survey_p8'))
C.install_injection(job)
products = A.choose_per_sector(A.load_products(job['tic_id']))
original = D._mask_fn
try:
    D._mask_fn = lambda eph: original(mask_eph)
    result = D.measure(products, source['eph'], source['survey_depth_ppt'], source['window'],
                       source['rstar'], source['mstar'], source['teff'], secondary_from=source['secondary_from'])
finally:
    D._mask_fn = original
variant = result['by_mask']['masked']['variants']['cap5']
chosen = baseline['per_ephemeris'][baseline['chosen_ephemeris']]
checks = {'n_kept_event_table': (variant['n_kept'], sum(bool(e.get('observed')) and not e.get('excluded')
                                                     for e in chosen['events'])),
          'n_observed': (variant['n_observed'], chosen['n_observed']),
          'kept_snr': (variant['kept_snr'], chosen['det_kept']['snr']),
          'p_const': (variant['p_const'], chosen['det_kept']['p_const']),
          'p_const_white': (variant['p_const_white'], chosen['det_kept']['p_const_white']),
          'kept_depth_ppt': (variant['kept_depth_ppt'], chosen['det_kept']['weighted_mean_depth_ppt']),
          'all_six': (variant['criteria']['0.001']['all'], baseline['decision'] == 'PASS')}
assert all(left == right for left, right in checks.values()), checks
assert hashes == {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
report = {'generated_utc': C.utc(), 'key': key, 'scope': 'Diagnostic replay only; calibration records unchanged',
          'instrument_mask_ephemeris': source['eph'], 'stageA_mask_ephemeris': mask_eph,
          'checks_replay_then_stageA': checks, 'all_equal': True, 'source_sha256': hashes,
          'stageA_finite_kept_depths': chosen['det_kept']['n'],
          'event_count_note': 'The event-table kept count includes events without a finite depth/error; the Stage A criterion count uses finite depth measurements.',
          'explanation': 'The fixed-ephemeris variant instrument masks the chosen TLS ephemeris. The stored full Stage A detrended around the survey ephemeris before TLS. Replaying with the stored survey mask reproduces its decision and reported statistics exactly.'}
target = Path(args.out)
if not target.is_absolute():
    target = repo / target
target.write_text(json.dumps(report, indent=1), encoding='utf-8')
print(json.dumps(report))

