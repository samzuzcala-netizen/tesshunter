"""Conditional future-run cost from completed development; no signal draws."""
from common import *
environment()
import numpy as np
from cost_selection import makespan
from final_c import stage_path

def main():
    evaluation=read(ROOT/'results/development_evaluation.json');selection=read(ROOT/'manifests/development_selection.json')
    resource=read(ROOT/'results/resource_accounting_final.json');observations=[]
    method=evaluation['selected_search']
    for sid in selection['series_ids']:
        search=read(ROOT/f'results/search/{sid}.json');pred=read(ROOT/f'results/predictions/{sid}.json')
        time=float(search['timings'][method+'_deployable_wall'])
        for p in pred['predictions']:
            if method not in p['methods'] or not p['passes_pregate']:continue
            for stage in ('A','S','B','C'):
                path=stage_path(p['candidate_id'],stage)
                if path.exists():time+=read(path).get('wall_seconds',0)
        observations.append(dict(tic_id=pred['tic_id'],kind='natural' if sid==f'tic{pred["tic_id"]}' else 'injection',wall_seconds=time))
    by_host={tic:[r for r in observations if r['tic_id']==tic] for tic in selection['host_ids']}
    rng=np.random.Generator(np.random.PCG64(2026091304));levels=[]
    for hosts,planets in [(100,350),(200,700),(300,1050)]:
        draws=[]
        for _ in range(500):
            sampled=rng.choice(selection['host_ids'],size=len(selection['host_ids']),replace=True)
            donors=[row for tic in sampled for row in by_host[int(tic)]]
            natural=[r['wall_seconds'] for r in donors if r['kind']=='natural']
            injected=[r['wall_seconds'] for r in donors if r['kind']=='injection']
            if not injected:raise ValueError('No measured injected-series throughput')
            durations=list(rng.choice(natural,size=hosts,replace=True))+list(rng.choice(injected,size=planets,replace=True))
            # Forty binary backgrounds remain mandatory. Use the observed upper
            # injected-series runtime tail for planning, not a claimed EB rate.
            durations += [float(np.quantile(injected,.95))]*40
            durations.sort(reverse=True);draws.append(makespan(durations,24)/3600)
        q=np.quantile(draws,[.5,.9,.95,.99]).tolist();reserved_input=2.;reserved_analysis=2.
        conservative=q[2]*1.25+reserved_input+reserved_analysis
        levels.append(dict(hosts=hosts,planet_injections=planets,binary_backgrounds=40,total_series=hosts+planets+40,
            queue_hours_p50_p90_p95_p99=q,conservative_total_queue_hours=conservative,
            fits_remaining_queue_cap=conservative<=resource['remaining_queue_hours'],
            input_acquisition_audit_reserve_hours=reserved_input,analysis_reserve_hours=reserved_analysis,
            conditional_on_verified_fresh_domain_and_storage=True))
    failures={p['policy']:[k for k,v in p['criteria'].items() if not v] for p in evaluation['policies']}
    frame=read(ROOT/'manifests/validation_metadata_frame.json')
    write(ROOT/'results/costed_next_step.json',dict(utc=utc(),development_finalist=evaluation['finalist'],
        scientific_admission=evaluation['finalist'] is not None,
        measured_development_admission_failures=failures,conditional_runtime_levels=levels,
        remaining_queue_hours=resource['remaining_queue_hours'],remaining_acquisition_bytes=15000000000-resource['cumulative_acquisition_bytes'],
        available_disk_above_required_floor=resource['free_disk_bytes']-30000000000,
        inference='A resource forecast is not authorization or scientific admission. No eligible development policy means no fresh run. Runtime donor resampling preserves development-host clustering, uses the selected search and conservatively includes every measured downstream stage. New signal populations, audited input sizes and arrival rates may differ; acquisition and disk feasibility require an actual frozen fresh-domain audit.',
        future_requirement='Before spending fresh holdout data, the frozen development method must satisfy every unchanged admission criterion and the actual input/resource audit. This execution prompt already authorizes that conditional validation. No further threshold tuning or second holdout draw is implied.',
        fresh_domain_metadata_manifest_sha256=sha(ROOT/'manifests/validation_metadata_frame.json'),
        fresh_cohort_selected=False,new_planet_or_binary_signals_drawn=False,reserved_TCE_ephemerides_opened=False,
        engineering_rng_seed=2026091304,simulations=500,allocation_cores=24))
    print('conditional next-step costs written; scientific admission',evaluation['finalist'] is not None)

if __name__=='__main__':main()
