"""Create the complete selected-host raw/reference handoff after size lock."""
from common import *
import sys

def main():
    selection=read(ROOT/'manifests/development_selection.json')
    if not selection['metadata_only_selection'] or selection['aggregate_efficacy_inspected']:
        raise ValueError('Development selection must precede efficacy inspection')
    sources=[p.relative_to(REPO).as_posix() for p in (REPO/'src/tesshunter').glob('*.py')]
    sources+=['p11/p11_5/protocol/common.py']
    jobs=[]
    for tic in selection['host_ids']:
        for kind,script,result in [('raw','raw_inputs.py',f'results/raw_inputs/tic{tic}.json'),
                                   ('reference','reference_snr.py',f'results/reference_snr/tic{tic}.json')]:
            if (ROOT/result).exists():continue
            jobs.append(dict(job_id=f'{kind}_tic{tic}',command=['p11/p11_5/protocol/'+script,str(tic)],source_paths=sources))
    write(ROOT/'manifests/development_input_jobs.json',jobs)
    write(ROOT/'manifests/development_series.json',selection['series_ids'])
    hosts=read(ROOT/'manifests/hosts.json');injections=read(ROOT/'manifests/injections_evaluator.json')
    selected=set(selection['host_ids']);selected_series=set(selection['series_ids'])
    def status(host):
        if host['tic_id'] in selected:return 'EVALUATION_REGISTERED'
        return 'INPUT_ELIGIBLE_NOT_SELECTED' if host['population']=='D_core' else 'INPUT_INELIGIBLE'
    by={h['tic_id']:h for h in hosts}
    write(ROOT/'manifests/population_accounting_registered.json',dict(utc=utc(),selection_sha256=sha(ROOT/'manifests/development_selection.json'),
        original=dict(hosts=300,injections=600),input_eligible=dict(hosts=235,injections=484),
        registered=dict(hosts=len(selected),injections=selection['n_injections'],series=len(selected_series)),
        hosts=[dict(tic_id=h['tic_id'],population=h['population'],status=status(h)) for h in hosts],
        injections=[dict(job_id=r['job_id'],tic_id=r['tic_id'],status=status(by[r['tic_id']])) for r in injections],
        exclusions_are_misses=False,individual_injection_selection=False,
        scope='Every original identity retained; only the locked selected D_core population is evaluated. Unobservable included injections remain in the overall denominator.'))
    print('registered input jobs',len(jobs),'science series',len(selected_series))

if __name__=='__main__':main()
