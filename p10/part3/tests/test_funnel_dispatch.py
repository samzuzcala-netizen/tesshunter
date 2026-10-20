import csv,json
from funnel_worker import legacy


def test_legacy_collection_routes_all_candidates_and_uses_fixed_pregate(tmp_path):
    root=tmp_path/'funnel';run=tmp_path/'run';(run/'results').mkdir(parents=True)
    target=dict(tic_id=101,radius_rsun=.3,mass_msun=.3,teff_k=3300,tmag=13,ra_deg=10,dec_deg=20)
    targets=tmp_path/'targets.csv'
    with targets.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=target);w.writeheader();w.writerow(target)
    base=dict(search='stitch',epoch_btjd=100,duration_days=.1,depth_ppt=2,snr=10,stitch_snr=10,
              stitch_n_transits=4,stitch_epoch_consistent=True,n_transits_observed=4)
    planets=[dict(base,planet_num=1,period_days=2),dict(base,planet_num=2,period_days=3,stitch_snr=7.0)]
    record=dict(status='ok',tic_id=101,n_units=5,baseline_days=100,n_cadences_raw=10000,result=dict(planets=planets,vetting=[],notes=[]))
    (run/'results/tic101.json').write_text(json.dumps(record))
    F=legacy(root);result=F.collect(run,targets)
    assert result['n_accepted_candidates']==2 and result['n_pass_pregate']==1
    jobs=F.V.jobs()
    assert len(jobs)==1 and jobs[0]['period']==2 and jobs[0]['planet_num']==1
    assert F.OUT==root and F.V.OUT_ROOT==root
    assert F.V.RULES=='p10.0'
