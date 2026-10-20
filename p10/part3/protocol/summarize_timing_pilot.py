"""Timing/count-only inputs for the main-session allocation decision."""
from common import ROOT,read,write,utc,sha
import math
import numpy as np


def distribution(values):
    if not values:return None
    a=np.asarray(values,dtype=float)
    return dict(n=len(a),min=float(a.min()),median=float(np.median(a)),mean=float(a.mean()),p90=float(np.quantile(a,.9)),max=float(a.max()),sum=float(a.sum()))


def main():
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('A phase is still running')
    for phase in ('timing_pilot_search','timing_pilot_A'):
        c=read(ROOT/f'results/controllers/{phase}/closure.json')
        if not c['all_owned_workers_closed'] or not c['source_hashes_unchanged']:raise RuntimeError('Pilot phase closure failed')
    entries=read(ROOT/'manifests/evaluation_order.json')
    search={};counts={};operational={}
    for preset in ('survey_p10','survey_p8'):
        values=[];cpu=[];accepted=[];pregate=[];unknown=[]
        for host in entries['pilot']:
            tic=host['tic_id'];path=ROOT/f'results/search_receipts/{preset}/tic{tic}.json'
            attempt=read(ROOT/f'results/controllers/timing_pilot_search/attempts/{preset}_tic{tic}.json')
            values.append(attempt['wall_seconds'])
            if path.exists():
                r=read(path);cpu.append(r['cpu_seconds']);accepted.append(r['n_accepted']);pregate.append(r['n_pre_gate'])
            if attempt['status']!='COMPLETE':unknown.append(tic)
        search[preset]=dict(wall=distribution(values),cpu=distribution(cpu),wall_seconds=values)
        counts[preset]=dict(n_accepted=accepted,n_pre_gate=pregate)
        operational[preset]=unknown
    atimes=[];acpu=[];aunknown=[]
    for p in (ROOT/'results/controllers/timing_pilot_A/attempts').glob('*.json'):
        attempt=read(p);atimes.append(attempt['wall_seconds'])
        receipt=ROOT/f'results/funnel_timing/A/{attempt["job_id"]}.json'
        if receipt.exists():acpu.append(read(receipt)['cpu_seconds'])
        if attempt['status']!='COMPLETE':aunknown.append(attempt['job_id'])
    pilot=dict(utc=utc(),search=search,candidate_counts=counts,stageA_wall=distribution(atimes),stageA_cpu=distribution(acpu),
        stageA_wall_seconds=atimes,operational_unknowns=dict(operational,stageA=aunknown),
        remaining_new_hours=31.98-read(ROOT/'manifests/resource_ledger.json')['new_queue_hours'],registered_levels=entries['levels'],
        allowed_content='Only durations, CPU, candidate counts and operational status; no periods, TCE rows, matches, A criteria or A decisions read',
        allocation_selected=False,requires_main_session=True,source_sha256=sha(__file__))
    write(ROOT/'results/timing_pilot_summary.json',pilot)
    print('Pilot timing summary ready; main-session level and paired P8 allocation review required',flush=True)


if __name__=='__main__':main()
