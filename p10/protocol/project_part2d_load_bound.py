"""Conservative C-load bound without observing new real-candidate outcomes.

The frozen projection allows at most 531 additional stars from the bare-SPOC
TCE pool. Without their prepared noise curves, use the 531 largest geometric
yield weights in the ENTIRE eligible-source pool as a superset bound. This
does not select a Part 3 population. Recovery probability cannot exceed one,
so this bounds the original P8/DC15 yield machinery for every logistic curve.
The actual p10.0 recovery/yield point estimates remain separate and pending.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(REPO/'src'),str(REPO/'scripts'),str(REPO/'p10/protocol')]
from tesshunter import survey, survey_yield as sy
from p8_expected_yield import R_EARTH_RSUN, B_GRID
import run_part2d_injection_search as Q

OUT=REPO/'p10/results/part2d_calibration_20260912'
CLAIMED_FRACTION=.03
MAX_ADDITIONAL=531


def stellar_weights(radius, mass, cells):
    """Identical geometric/radius/mass convention to original p8_expected_yield."""
    radius=float(radius)
    mass=float(mass) if mass not in ('',None,'nan') else radius
    if not math.isfinite(mass):mass=radius
    if not math.isfinite(radius) or radius<=0 or mass<=0:
        raise ValueError('Undefined original stellar geometry; no finite bound asserted')
    weights=[]
    for c in cells:
        if c['rate']<=0:continue
        pmid=math.sqrt(c['p_lo']*c['p_hi'])
        rp_rs=c['r_rep']*R_EARTH_RSUN/max(radius,.05)
        a_rs=survey.a_over_rs(pmid,mass,radius)
        pgeo=min(1.,max(0.,(1.+rp_rs)/a_rs))
        weights.append(dict(cell=c['label'],rate=c['rate'],pgeo=pgeo,
                            weight=(1.-CLAIMED_FRACTION)*c['rate']*pgeo))
    return weights


def maximum_subset_sum(values, size):
    if size<0 or size>len(values) or any(not math.isfinite(v) or v<0 for v in values):
        raise ValueError('Invalid bounded population')
    return sum(sorted(values,reverse=True)[:size])


def calculate():
    result_path=OUT/'geometric_C_load_bound.json'
    assert not result_path.exists(), 'Bound generation is exclusive'
    cfg=survey.get_config('survey_p10')
    assert cfg.period_min==.5 and cfg.period_max==30.
    assert Q.frozen_section_sha()==Q.FROZEN_SHA
    cells=sy.occurrence_cells('m',sy.CENTRAL_MODEL['m'],cfg.period_max,p_min=cfg.period_min)
    targets=REPO/'data/survey/targets_p8.csv'
    pool_path=REPO/'data/survey/cache/p8/pool_after_xmatch.csv'
    base=list(csv.DictReader(targets.open(newline='',encoding='utf-8')))
    pool=list(csv.DictReader(pool_path.open(newline='',encoding='utf-8')))
    bare=[r for r in pool if r['xmatch_status']=='REJECT' and r['xmatch_tic_sources']=='spoc_tce']
    assert len(base)==len({r['tic_id'] for r in base})==2000
    assert len(bare)==len({r['tic_id'] for r in bare}) and len(bare)>=MAX_ADDITIONAL
    assert not ({r['tic_id'] for r in base}&{r['tic_id'] for r in bare})
    def bound_rows(rows,radius,mass):
        return [dict(tic_id=int(r['tic_id']),radius_rsun=float(r[radius]),mass_input=r[mass],
                     geometric_expected_signal_upper_bound=sum(w['weight'] for w in stellar_weights(r[radius],r[mass],cells))) for r in rows]
    b=bound_rows(base,'radius_rsun','mass_msun')
    extra=bound_rows(bare,'rad','mass')
    selected=sorted(extra,key=lambda r:(-r['geometric_expected_signal_upper_bound'],r['tic_id']))[:MAX_ADDITIONAL]
    base_bound=sum(r['geometric_expected_signal_upper_bound'] for r in b)
    extra_bound=maximum_subset_sum([r['geometric_expected_signal_upper_bound'] for r in extra],MAX_ADDITIONAL)
    fa_seal=OUT/'false_alarm_closed_seal_20260912.json'
    fa=Q.read(fa_seal)
    assert fa['status']=='FA_complete_verified' and fa['metrics']['n_stars']==300
    fa_count=fa['metrics']['stageA_pass_and_secondary']
    fa_term=fa_count/300*2531
    source_paths=[Path(__file__).resolve(),REPO/'scripts/p8_expected_yield.py',REPO/'src/tesshunter/survey_yield.py',
                  REPO/'src/tesshunter/survey.py',REPO/'src/tesshunter/occurrence_grids.py']
    report=dict(utc=Q.utc(),status='conservative_model_bound_not_a_recovery_measurement',
        rules='p10.0',config='survey_p10',central_occurrence_model=sy.CENTRAL_MODEL['m'],claimed_fraction=CLAIMED_FRACTION,
        period_band_days=[cfg.period_min,cfg.period_max],original_impact_parameter_grid=B_GRID,
        proof=['The original per-cell signal yield is (1-claimed_fraction)*rate*P_transit*P_recovery, averaged over four impact parameters.',
               'Each logistic recovery probability and the impact-parameter average are in [0,1]; setting them to one upper-bounds every cell.',
               'All possible Part 3 additions belong to the original bare-SPOC-only pool. Summing its 531 largest nonnegative stellar bounds upper-bounds any subset of at most 531 stars, irrespective of later Gaia/cadence cuts.',
               'No real-candidate search/funnel output, TCE ephemeris or held-out outcome enters this calculation. No Part 3 target selection or population policy is adopted.'],
        population=dict(original_stars=2000,bare_source_pool=len(extra),maximum_additional_stars=MAX_ADDITIONAL,
                        prospective_maximum_stars=2531,bound_source='Entire source pool; it is deliberately larger than the P8 domain and any eventual Part 3 set.'),
        original_2000_perfect_recovery_signal_bound=base_bound,any_531_additional_perfect_recovery_signal_bound=extra_bound,
        all_2531_perfect_recovery_signal_bound=base_bound+extra_bound,FA_S_count=fa_count,FA_S_denominator=300,
        FA_S_times_2531=fa_term,C_load_upper_bound=fa_term+base_bound+extra_bound,
        limit=150,load_limit_satisfied_by_sufficient_bound=fa_term+base_bound+extra_bound<=150,
        stop_rule_1_evaluated=False,SNR50_S_pending=True,actual_new_curve_yield_pending=True,
        limitations=['This is an expectation bound under the fixed central DC15 model and claimed fraction, not a confidence interval or a hard bound on the realized number of candidates.',
                     'The empirical false-alarm rate is extrapolated as the frozen rule specifies; its sampling uncertainty remains.',
                     'HU19 occurrence sensitivity and the actual new-curve expected yield must still be reported with the final calibration; they are not substituted for the fixed central-model stop criterion.',
                     'The 150-run realized Stage C cap and all later stop rules remain binding.'],
        inputs_sha256={str(p.relative_to(REPO)):Q.sha(p) for p in (targets,pool_path,fa_seal)},
        sources_sha256={str(p.relative_to(REPO)):Q.sha(p) for p in source_paths},
        original_stellar_bounds=b,bare_source_stellar_bounds=extra,
        upper_bound_maximizing_531_tics=[r['tic_id'] for r in selected])
    Q.save(result_path,report,exclusive=True)
    print(__import__('json').dumps({k:report[k] for k in ('population','original_2000_perfect_recovery_signal_bound',
        'any_531_additional_perfect_recovery_signal_bound','FA_S_times_2531','C_load_upper_bound',
        'load_limit_satisfied_by_sufficient_bound','stop_rule_1_evaluated')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['calculate']);parser.parse_args()
    calculate()
