"""Prospective complete-manifest schedule forecast; never opens injection truth."""
from common import *
environment()
import sys,heapq
import numpy as np

def makespan(durations,workers):
    slots=[0.]*workers;heapq.heapify(slots)
    for duration in durations:
        finish=heapq.heappop(slots)+float(duration);heapq.heappush(slots,finish)
    return max(slots,default=0.)

def main():
    order=read(ROOT/'manifests/development_order.json');pilot=order['pilot_hosts'];timing_ids=read(ROOT/'manifests/all_timing_series.json')
    events=[json.loads(s) for s in (ROOT/'manifests/events.jsonl').read_text().splitlines()]
    spent=.920809591111111+sum(e.get('wall_seconds',0) for e in events if e['event']=='science_end')/3600
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Select size after timing-owner closure')
    observations=[];evidence={}
    for tid in pilot:
        prep=read(ROOT/f'results/preparation/tic{tid}.json')
        for case in prep['cases']:
            jid=case['job_id'];p=ROOT/f'results/search/{jid}.json';r=read(p);evidence[p.relative_to(REPO).as_posix()]=sha(p)
            downstream=[];by_stage={s:[] for s in ('A','S','B','C')}
            predictions=read(ROOT/f'results/predictions/{jid}.json')['predictions']
            for candidate in predictions:
                if not candidate['passes_pregate']:continue
                cid=candidate['candidate_id']
                for s in by_stage:
                    path=ROOT/f'results/funnel/{s}/{cid}.json'
                    if path.exists():
                        record=read(path);by_stage[s].append(float(record['wall_seconds']));evidence[path.relative_to(REPO).as_posix()]=sha(path)
                    elif s=='A':raise RuntimeError('Timing A attempt missing')
                a=read(ROOT/f'results/funnel/A/{cid}.json')
                if a.get('status')=='COMPLETE' and a['measurement'].get('decision')=='PASS':
                    for s in ('S','B','C'):
                        if not (ROOT/f'results/funnel/{s}/{cid}.json').exists():raise RuntimeError('Required timing downstream attempt missing')
            observations.append(dict(job_id=jid,tic_id=tid,kind=case['kind'],n_points=case['n_points'],baseline=case['baseline_days'],
                search=float(r['timings']['R1_deployable_wall']),stages=by_stage,
                total_wall=float(r['timings']['R1_deployable_wall'])+sum(sum(x) for x in by_stage.values())))
    if not any(o['stages']['C'] for o in observations):raise RuntimeError('No real native C timing measurement yet')
    cases=[]
    for item in order['order']:
        tid=item['tic_id'];prep=read(ROOT/f'results/preparation/tic{tid}.json')
        for case in prep['cases']:cases.append(dict(case,tic_id=tid))
    # Independent engineering stream; outcomes/SNR/truth never enter forecasts.
    rng=np.random.Generator(np.random.PCG64(2026091304));forecasts=[];workers=24
    reserve=dict(conditional_validation=15.,final_analysis=2.,controls=6.,remaining_input_preparation=.5)
    for n in order['nested_sizes']:
        ids={h['tic_id'] for h in order['order'][:n]};selected=[c for c in cases if c['tic_id'] in ids]
        # Schedule longest metadata workloads first; no scored outcomes determine
        # task order. All injections of selected hosts stay in the manifest.
        selected.sort(key=lambda c:(-c['n_points'],-c['baseline_days'],c['job_id']))
        draws=[]
        for _ in range(500):
            durations=[]
            # Resample whole timing hosts to retain host-level runtime clustering.
            host_multiplicity=rng.multinomial(len(pilot),np.full(len(pilot),1/len(pilot)))
            for case in selected:
                peers=[o for o in observations if o['kind']==case['kind']]
                distances=np.array([abs(np.log(case['n_points']/o['n_points']))+.5*abs(np.log(max(case['baseline_days'],1)/max(o['baseline'],1))) for o in peers])
                probability=np.exp(-distances)*np.array([host_multiplicity[pilot.index(o['tic_id'])] for o in peers])
                if not probability.sum():probability=np.exp(-distances)
                donor=peers[int(rng.choice(len(peers),p=probability/probability.sum()))]
                scale=float(np.clip((case['n_points']/donor['n_points'])**.75*(max(case['baseline_days'],1)/max(donor['baseline'],1))**.25,.5,2.))
                # Treat a full per-series dependency chain as occupying one slot;
                # this is more conservative than the candidate-level queue.
                duration=min(3600,donor['search']*scale)
                for stage,limit in [('A',1200),('S',300),('B',300),('C',600)]:
                    duration+=sum(min(limit,value*scale) for value in donor['stages'][stage])
                durations.append(duration)
            draws.append(makespan(durations,workers)/3600)
        q=np.quantile(draws,[.5,.9,.95,.99]).tolist()
        # An additional 25% runtime margin addresses the small six-host pilot and
        # the larger allocation. This is a forecast, not an observed benchmark.
        conservative=q[2]*1.25
        total=spent+conservative+sum(reserve.values())
        forecasts.append(dict(hosts=n,series=len(selected),queue_hours_quantiles_p50_p90_p95_p99=q,
            conservative_development_hours=conservative,total_with_prior_and_reserves_hours=total,affordable=total<=48,
            workers=workers,simulations=500,remaining_reserves_hours=reserve))
    affordable=[f for f in forecasts if f['affordable']]
    if not affordable:raise RuntimeError('No registered nested development level fits conservative forecast; costed resource amendment required before launch')
    selected=max(affordable,key=lambda f:f['hosts']);chosen=order['order'][:selected['hosts']];ids={r['tic_id'] for r in chosen}
    selected_cases=[c for c in cases if c['tic_id'] in ids];selected_cases.sort(key=lambda c:(-c['n_points'],-c['baseline_days'],c['job_id']))
    write(ROOT/'results/affordability_forecast.json',dict(utc=utc(),prior_charged_hours=spent,observations=observations,evidence_sha256=evidence,
        forecasts=forecasts,selected=selected,aggregate_efficacy_inspected=False,bootstrap_seed=2026091304,
        limitations='Six metadata-stratified hosts; runtime-cluster resampling, point-count/baseline scaling, per-stage deadlines, conservative serial chains, 25% allocation margin. Forecast distributions are not measured end-to-end benchmarks.'))
    write(ROOT/'manifests/development_selection.json',dict(utc=utc(),host_ids=[r['tic_id'] for r in chosen],series_ids=[c['job_id'] for c in selected_cases],
        n_hosts=len(chosen),n_injections=sum(c['kind']=='injection' for c in selected_cases),metadata_only_selection=True,
        aggregate_efficacy_inspected=False,forecast_sha256=sha(ROOT/'results/affordability_forecast.json'),workers=workers,
        original_population=dict(hosts=300,injections=600),input_eligible_population=dict(hosts=235,injections=484),
        estimand='Declared evaluated D_core population; equal empirical weights, no extrapolation to input-excluded hosts.'))
    print('selected development hosts',len(chosen),'series',len(selected_cases),'forecast total hours',selected['total_with_prior_and_reserves_hours'])

if __name__=='__main__':main()
