"""Retain all 300/600 original identities in the final measured accounting."""
from common import *
from collections import Counter

def main():
    registered=read(ROOT/'manifests/population_accounting_registered.json')
    evaluation=read(ROOT/'results/development_evaluation.json')
    by_id={r['job_id']:r for r in evaluation['rows']}
    hosts=[];injections=[]
    for original in registered['hosts']:
        row=dict(original)
        if row['status']=='EVALUATION_REGISTERED':
            row['status']='EVALUATED_PAIRED'
            natural=ROOT/f"results/predictions/tic{row['tic_id']}.json"
            if not natural.exists():raise ValueError('Registered natural series lacks predictions')
            row['natural_prediction_sha256']=sha(natural)
            row['evaluated_injections']=sum(r['tic_id']==row['tic_id'] for r in by_id.values())
        hosts.append(row)
    for original in registered['injections']:
        row=dict(original)
        if row['status']=='EVALUATION_REGISTERED':
            measured=by_id[row['job_id']]
            row.update(status='EVALUATED_PAIRED',snr_expected=measured['snr_expected'],
                reference_unobservable=measured['snr_expected']==0,
                baseline_pre_A_bound_S=measured['R0_AS'],R1_pre_A_bound_S=measured['R1_AS'],
                overall_denominator_retained=True,evaluation_path='p11/p11_5/results/development_evaluation.json')
        injections.append(row)
    if len(hosts)!=300 or len(injections)!=600:raise ValueError('Original population identity loss')
    write(ROOT/'manifests/population_accounting_final.json',dict(utc=utc(),
        registration_sha256=sha(ROOT/'manifests/population_accounting_registered.json'),
        evaluation_sha256=sha(ROOT/'results/development_evaluation.json'),
        original=registered['original'],input_eligible=registered['input_eligible'],
        measured=dict(hosts=evaluation['n_hosts'],injections=evaluation['n_injections'],natural_series=evaluation['n_hosts']),
        host_status_counts=dict(Counter(r['status'] for r in hosts)),injection_status_counts=dict(Counter(r['status'] for r in injections)),
        hosts=hosts,injections=injections,input_exclusions_are_measured_misses=False,
        missing_rows_included_in_qualified_claim=False,individual_injection_selection=False))
    print('Final population accounting retains',len(hosts),'hosts and',len(injections),'injections')

if __name__=='__main__':main()
