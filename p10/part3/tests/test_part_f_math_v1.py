import sys
from pathlib import Path
import math
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'protocol'))
from part_f_math_v1 import candidate_match, epoch_rule, expected_snr, representative, expected_snr_bin, period_bin
from forced_box_v1 import fit_box, presence
from cluster_bootstrap_v1 import host_weights, fractions, logistic_snr50


def row(**changes):
    result = dict(tce_period=4.0, tce_period_err=0.0, tce_time0bt=100.0,
                  tce_duration=6.0, tce_depth=1000.0, tce_model_snr=15,
                  tce_num_transits=4, source_filename='a.csv', source_row=1)
    return dict(result, **changes)


def candidate(period=4., epoch=100.):
    return dict(candidate_id='example', period_days=period, epoch_btjd=epoch)


@pytest.mark.parametrize('ratio,label', [(1.,'1:1'),(2.,'2:1'),(3.,'3:1'),(.5,'1:2'),(1/3,'1:3')])
def test_only_registered_aliases_and_epoch_alignment(ratio, label):
    result = candidate_match(row(), candidate(4*ratio), 701.)
    assert result['alias'] == label and result['recovered'] and result['epoch_agrees']
    assert result['exact'] == (ratio == 1)


@pytest.mark.parametrize('ratio', [1.5,2/3,1.01,.99])
def test_unregistered_ratios_and_exact_boundary_rejected(ratio):
    assert candidate_match(row(), candidate(4*ratio), 700.) is None


def test_epoch_condition_is_strict_and_uncertainty_missing_is_period_only():
    # Four cycles, 0.03125 d period error, half duration 0.125 d.
    assert not epoch_rule(row(tce_period_err=.03125), 116.)['checkable']
    assert epoch_rule(row(tce_period_err=.03124), 116.)['checkable']
    missing = candidate_match(row(tce_period_err='nan'), candidate(epoch=101.), 700.)
    assert missing['recovered'] and missing['epoch']['mode'] == 'PERIOD_ONLY'


def test_checked_epoch_wrong_phase_and_wrap():
    assert not candidate_match(row(), candidate(epoch=101.), 700.)['recovered']
    assert candidate_match(row(), candidate(epoch=103.99), 700.)['recovered']
    assert candidate_match(row(), candidate(epoch=100.125), 700.)['recovered']
    assert not candidate_match(row(), candidate(epoch=100.126), 700.)['recovered']


def test_epoch_propagation_uses_native_midpoint_and_candidate_period():
    # An ephemeris aligned at epoch 100 drifts by 0.4 d after 100 cycles.
    match = candidate_match(row(), candidate(period=4.004), 500.)
    assert not match['recovered'] and match['phase_distance_days'] > .125
    assert candidate_match(row(tce_period_err=.01), candidate(period=4.004), 500.)['recovered']


def test_expected_snr_units_and_invalid_inputs():
    n = dict(sigma=.001, n_cad=1000)
    assert expected_snr(row(tce_period=2.,tce_duration=2.), n) == pytest.approx(math.sqrt(1000/24))
    assert expected_snr(row(tce_depth=0),n) == 0
    assert expected_snr(row(tce_depth=-1),n) is None
    assert expected_snr(row(),dict(sigma=0,n_cad=1000)) is None
    assert expected_snr_bin(7)=='[7,10)' and period_bin(30)=='[20,30]'
    assert period_bin(30.1)=='>30' and period_bin(.499)=='<0.5'


def test_representative_is_highest_snr_with_stable_source_row_ties():
    rows=[row(source_filename='b.csv',source_row=1),row(source_row=2),row(source_row=1)]
    assert representative(list(reversed(rows)))==rows[2]
    rows.append(row(tce_model_snr=20,source_filename='z.csv'))
    assert representative(rows)==rows[-1]


def test_presence_boundary_and_unknown_error():
    assert presence(.03,.01)=='PRESENT'
    assert presence(.0299,.01)=='ABSENT'
    assert presence(-.1,.01)=='ABSENT'
    assert presence(0.,0.)=='OPERATIONAL_UNKNOWN'
    assert presence(1.,float('nan'))=='OPERATIONAL_UNKNOWN'


def synthetic(seed=2026091402, epoch=0.73):
    rng=np.random.Generator(np.random.PCG64(seed))
    t=np.sort(rng.uniform(0,40,4000));p=2.7;duration=.11
    mask=((t-epoch+duration/2)%p)<duration
    f=1-.008*mask+rng.normal(0,.001,len(t))
    return t,f,p,duration,epoch,mask


def test_fixed_box_depth_and_error_equal_explicit_linear_least_squares():
    t,f,p,d,e,mask=synthetic()
    result=fit_box(t,f,p,d,.002,e)
    design=np.column_stack((np.ones(len(t)),-mask.astype(float)))
    beta=np.linalg.lstsq(design,f,rcond=None)[0]
    residual=f-design@beta
    error=np.sqrt((residual@residual/(len(t)-2))*np.linalg.inv(design.T@design)[1,1])
    assert result['depth_fraction']==pytest.approx(beta[1],rel=1e-11)
    assert result['depth_standard_error_fraction']==pytest.approx(error,rel=1e-11)
    assert result['presence']=='PRESENT' and result['epoch_mode']=='FIXED_CHECKABLE_EPOCH'


def test_best_phase_recovers_a_shifted_box_and_circular_wrap():
    for epoch in (.73,2.69):
        t,f,p,d,e,mask=synthetic(epoch=epoch)
        r=fit_box(t,f,p,d,.002)
        delta=abs((r['epoch_btjd']-e+p/2)%p-p/2)
        assert delta<.02 and r['presence']=='PRESENT'
        assert r['depth_fraction']==pytest.approx(.008,abs=.001)


def test_optimized_box_matches_exhaustive_phase_partitions():
    rng=np.random.Generator(np.random.PCG64(123))
    t=np.sort(rng.uniform(0,3,30));f=rng.normal(1,.002,len(t));p=1.7;d=.23
    result=fit_box(t,f,p,d,.01)
    phases=(t-t.min())%p
    boundaries=np.unique(np.r_[phases,(phases-d)%p]);nxt=np.r_[boundaries[1:],boundaries[0]+p]
    best=-math.inf
    for start in (boundaries+nxt)/2:
        mask=((phases-start)%p)<d
        if not mask.any() or mask.all():continue
        depth=f[~mask].mean()-f[mask].mean()
        score=max(depth,0)**2/(1/mask.sum()+1/(~mask).sum())
        best=max(best,score)
    actual=max(result['depth_fraction'],0)**2/(1/result['n_in']+1/result['n_out'])
    assert actual==pytest.approx(best,rel=1e-9,abs=1e-15)


def test_duration_floor_and_absent_signal():
    t=np.arange(1000)*.01;rng=np.random.Generator(np.random.PCG64(42))
    f=1+rng.normal(0,.001,len(t))
    r=fit_box(t,f,1.,.0001,.01,.003)
    assert r['duration_days']==.01 and r['duration_floored']
    # An upward fixed box is an explicitly absent positive-depth transit.
    mask=((t-.3+.05)%1.)<.1;f=1+.01*mask+rng.normal(0,.001,len(t))
    assert fit_box(t,f,1.,.1,.01,.3)['presence']=='ABSENT'


def test_fit_failure_is_not_absence():
    with pytest.raises(ValueError,match='in- or out-of-transit'):
        fit_box([0.,.01,.02],[1.,1.1,.9],1.,.1,.01,.5)
    with pytest.raises(ValueError,match='full-period'):
        fit_box([0.,.5,1.],[1.,.9,1.],1.,1.1,.01)


def test_bootstrap_whole_hosts_and_identical_paired_draws():
    w=host_weights(3,draws=200,seed=2026091401)
    assert np.all(w.sum(axis=1)==3)
    assert np.array_equal(w,host_weights(3,draws=200,seed=2026091401))
    a=fractions([1,0,2],[1,1,2],w)
    assert a==fractions([1,0,2],[1,1,2],w)
    assert a['fraction']==.75 and a['bootstrap_valid_draws']==200
    assert fractions([0,0,0],[0,0,0],w)['fraction'] is None
    assert fractions([0,0,0],[0,0,0],w)['ci95'] is None
    with pytest.raises(ValueError):fractions([2,0,0],[1,0,0],w)


def test_logistic_known_binomial_mle_and_weighted_host_multiplicities():
    snr=np.repeat(np.exp([-1.,0.,1.]),10)
    y=np.r_[np.ones(2),np.zeros(8),np.ones(5),np.zeros(5),np.ones(8),np.zeros(2)]
    fit=logistic_snr50(snr,y)
    assert fit['status']=='IDENTIFIED'
    assert fit['a']==pytest.approx(0.,abs=1e-8)
    assert fit['b']==pytest.approx(np.log(4),rel=1e-7)
    assert fit['snr50']==pytest.approx(1.,rel=1e-8)
    weights=np.tile([1,2,3],10)
    expanded=logistic_snr50(np.repeat(snr,weights),np.repeat(y,weights))
    weighted=logistic_snr50(snr,y,weights)
    assert expanded['snr50']==pytest.approx(weighted['snr50'],rel=1e-8)


def test_logistic_separation_and_no_variation_are_unidentified():
    assert logistic_snr50([1,2,3,4],[0,0,1,1])['status']=='UNIDENTIFIED'
    assert logistic_snr50([1,2,3,4],[1,1,1,1])['status']=='UNIDENTIFIED'
    assert logistic_snr50([2,2,2,2],[0,1,0,1])['status']=='UNIDENTIFIED'
