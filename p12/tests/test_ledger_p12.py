import math
import pytest
import ledger_p12 as ledger
from p12_common import write,read


@pytest.fixture
def ledger_root(tmp_path,monkeypatch):
    root=tmp_path/'p12';(root/'manifests').mkdir(parents=True)
    monkeypatch.setattr(ledger,'REPO',tmp_path);monkeypatch.setattr(ledger,'ROOT',root)
    write(root/'protocol/config.json',dict(forecast_margin=1.25,photometry_bar={'wall_ratio_max':3},
        forecast_units=dict(search_queue_seconds=31.9,A_queue_seconds=15.5,S_queue_seconds=1.3,
            B_queue_seconds=.45,C_queue_hours=.36,D_queue_minutes=7.5,download_queue_seconds=12.9,verify_queue_seconds=1.54)))
    return tmp_path,root


def test_queue_units_divide_concurrency_once():
    assert ledger.queue_seconds_per_job([760,760],24)==pytest.approx(31.6666666667)
    assert ledger.queue_seconds_per_job([],24) is None
    with pytest.raises(ValueError):ledger.queue_seconds_per_job([math.nan],24)


def test_forecast_margin_and_ratio_ceiling(ledger_root):
    repo,root=ledger_root
    first=ledger.forecast()
    assert first['total']['with_margin_queue_hours'][0]==pytest.approx(first['total']['base_queue_hours'][0]*1.25)
    ratio1=first['scenarios']['ADOPT_SML_ratio_1']['base_queue_hours'][0]
    ratio3=first['scenarios']['ADOPT_SML_ratio_3_ceiling']['base_queue_hours'][0]
    assert ratio3-ratio1==pytest.approx(96.2)
    write(root/'results/part2/photometry_decision.json',{'decision':'ADOPT_SML','median_wall_ratio':3})
    updated=ledger.forecast(after_part2=True)
    assert updated['total']['base_queue_hours'][0]==pytest.approx(ratio3)
    assert updated['separate_C_retry_tail_queue_hours']==73
    assert (root/'manifests/forecast_before_part2.json').exists()


@pytest.mark.parametrize('ratio',[None,3.01])
def test_after_part2_missing_or_excessive_ratio_refused(ledger_root,ratio):
    repo,root=ledger_root
    write(root/'results/part2/photometry_decision.json',{'decision':'ADOPT_SML','median_wall_ratio':ratio})
    with pytest.raises(ValueError):ledger.forecast(after_part2=True)


def test_pilot_never_lowers_registered_unit(ledger_root):
    repo,root=ledger_root
    write(root/'results/pilot_timing.json',dict(production_workers=24,search_job_walls_seconds=[240],A_job_walls_seconds=[480]))
    result=ledger.forecast()
    assert result['unit_costs']['search_queue_seconds']==31.9
    assert result['unit_costs']['A_queue_seconds']==20


def test_measured_counts_and_stage_conversion(ledger_root):
    repo,root=ledger_root
    write(root/'manifests/eligibility_p12.json',dict(forecast_counts=dict(core_eligible=1000,tce_eligible=218,calibration_eligible=150,injections_eligible=1050,two_b_injections_eligible=300)))
    write(root/'manifests/final_search_jobs.json',[{},{}])
    write(root/'manifests/final_C_jobs.json',[{},{}])
    write(root/'manifests/final_D_jobs.json',[{},{}])
    result=ledger.forecast()
    assert result['count_status']=='MEASURED_ELIGIBILITY'
    assert result['phases']['final_search']['base_queue_hours']==pytest.approx(2*31.9/3600)
    assert result['phases']['final_C']['base_queue_hours']==.72
    assert result['phases']['final_D']['base_queue_hours']==.25


def test_reduced_calibration_retains_real_host_and_C_costs(ledger_root):
    repo,root=ledger_root
    write(root/'manifests/eligibility_p12.json',dict(forecast_counts=dict(core_eligible=1000,tce_eligible=436,calibration_eligible=150,injections_eligible=1050,two_b_injections_eligible=300)))
    write(root/'results/pilot_timing.json',dict(production_workers=24,search_job_walls_seconds=[31.9*48],A_job_walls_seconds=[15.5*48]))
    result=ledger.forecast()
    costs=result['part2_base_components_queue_hours']
    assert costs['archival_real436']==pytest.approx(7.6)
    assert costs['sml_real436']==pytest.approx(7.6)
    assert costs['archival_C']==10.8
    assert costs['archival_search']==pytest.approx(21.1)
    assert costs['archival_A']==pytest.approx(8.2)
    expected_A=25.4*(1000*2.363+436*2.532)/(2000*2.363+436*2.532)*2
    assert result['part5_components_queue_hours']['A']==pytest.approx(expected_A)


@pytest.mark.parametrize('phase,script,extra,kind',[
    ('plumbing_d','p12/protocol/stage_d_worker_p12.py',[],'D'),('final_D','p12/protocol/stage_d_worker_p12.py',[],'D'),
    ('bar_p9_eph','p12/heldout/runner.py',[],'other'),('cal_a_A','p12/protocol/funnel_stage_p12.py',['A'],'A'),
    ('cal_a_search','p12/protocol/blind_search_worker_p12.py',[],'search'),('cal_a_C','p12/protocol/stage_c_worker_p12.py',[],'C')])
def test_stage_detection_uses_the_worker_not_the_name_case(phase,script,extra,kind):
    jobs=[dict(job_id='x',attempt=1,arguments=[script,*extra])]
    assert ledger._job_kind(phase,jobs)==kind


def test_plumbing_d_priced_at_the_d_unit(ledger_root):
    repo,root=ledger_root
    write(root/'manifests/forecast_p12.json',dict(unit_costs=dict(search_queue_seconds=31.9,A_queue_seconds=15.5,S_queue_seconds=1.3,
        B_queue_seconds=.45,C_queue_hours=.36,D_queue_minutes=7.5,download_queue_seconds=12.9,verify_queue_seconds=1.54),
        forecast_margin=1.25,phases={}))
    write(root/'manifests/plumbing_d_jobs.json',[dict(job_id=str(i),attempt=1,arguments=['p12/protocol/stage_d_worker_p12.py']) for i in range(6)])
    row=ledger.price_phase('plumbing_d',root/'manifests/plumbing_d_jobs.json')
    assert row['kind']=='D' and row['base_queue_hours']==pytest.approx(0.75)
