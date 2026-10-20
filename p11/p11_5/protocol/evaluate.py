"""One locked, complete development evaluation; no runtime truth access."""
from common import *
environment()
import sys
from collections import Counter
import numpy as np
from score_common import *
from final_c import C_STAGE,stage_path,storage_receipt

def stage(cid,name):
    p=stage_path(cid,name)
    return read(p) if p.exists() else dict(status='INPUT_ERROR',reason='Required stage unavailable; earlier measured rejection may make it inapplicable')

def load_candidate(row):
    cid=row['candidate_id']
    return dict(row,**{s:stage(cid,s) for s in ('A','S','B','C')})

def downstream_cost(candidate,method):
    if method not in candidate['methods'] or not candidate['passes_pregate']:return dict(wall=0.,cpu=0.)
    return {key:sum(candidate[s].get(key+'_seconds',0.) for s in ('A','S')) for key in ('wall','cpu')}

def measured_arrival(p,S):
    return p['passes_pregate'] and p['A'].get('status')=='COMPLETE' and p['A']['measurement'].get('decision')=='PASS' and s_gate(p['S'],S)=='PASS' and p['B'].get('status')=='COMPLETE' and p['B']['measurement'].get('decision')=='PASS'

def c_cost(p,S):
    if not p['passes_pregate'] or p['A'].get('status')!='COMPLETE' or p['A']['measurement'].get('decision')!='PASS':return 0.
    if s_gate(p['S'],S)!='PASS':return 0.
    return p['B'].get('cpu_seconds',0.)+(p['C'].get('cpu_seconds',0.) if p['B'].get('status')=='COMPLETE' and p['B']['measurement'].get('decision')=='PASS' else 0.)

def freeze(selection_path,regression_name):
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Prediction freeze requires closed scientific owner')
    selection=read(selection_path);ids=selection['series_ids'];hashes={};missing=[]
    regression=ROOT/'results'/regression_name
    receipt=read(regression/'receipt.json')
    if receipt['exit_code']!=0 or not receipt['source_hashes_verified_at_end']:
        raise ValueError('Full compatibility regression did not pass')
    for path,expected in read(regression/'source_freeze.json')['hashes'].items():
        if sha(REPO/path)!=expected:raise ValueError('Tested source changed before prediction freeze: '+path)
        hashes[path]=expected
    for p in (regression/'receipt.json',regression/'source_freeze.json',regression/'pytest.log',
              ROOT/'manifests/injections_evaluator.json',ROOT/'manifests/development_order.json'):
        hashes[p.relative_to(REPO).as_posix()]=sha(p)
    for host in selection['host_ids']:
        p=ROOT/f'results/reference_snr/tic{host}.json';hashes[p.relative_to(REPO).as_posix()]=sha(p)
    provenance_path=ROOT/'results/prepared_provenance_review.json'
    provenance=read(provenance_path)
    if not provenance['all_physical_truth_checks_pass']:raise ValueError('Prepared provenance truth audit did not pass')
    hashes[provenance_path.relative_to(REPO).as_posix()]=sha(provenance_path)
    for item in provenance['rows']:
        path=item['sidecar_path'];expected=item['sidecar_sha256']
        if sha(REPO/path)!=expected:raise ValueError('Prepared provenance changed: '+path)
        hashes[path]=expected
    correction=ROOT/'manifests/c_v2_execution_freeze.json'
    if not correction.exists():raise RuntimeError('Corrected C execution freeze is required')
    for p in (correction,ROOT/'protocol/evaluate.py',ROOT/'protocol/score_common.py',ROOT/'protocol/final_c.py'):
        hashes[p.relative_to(REPO).as_posix()]=sha(p)
    for path,expected in read(correction)['source_hashes'].items():
        if sha(REPO/path)!=expected:raise ValueError('Corrected C source changed before evaluation: '+path)
        hashes[path]=expected
    def model_archives(record_path):
        refs=set()
        def walk(value):
            if isinstance(value,dict):
                if isinstance(value.get('archive'),str):refs.add(value['archive'])
                for item in value.values():walk(item)
            elif isinstance(value,list):
                for item in value:walk(item)
        walk(read(record_path))
        for ref in refs:
            logical=REPO/ref;physical=logical if logical.exists() else Path(str(logical)+'.xz')
            if not physical.exists():missing.append(ref);continue
            hashes[physical.relative_to(REPO).as_posix()]=sha(physical)
            if physical!=logical:
                receipt=storage_receipt(logical)
                if not receipt.exists():raise ValueError('Packed model receipt missing')
                packed=read(receipt)
                if packed['packed_sha256']!=sha(physical) or packed['case_sha256']!=sha(record_path):raise ValueError('Packed model/case identity changed')
                hashes[receipt.relative_to(REPO).as_posix()]=sha(receipt)
    for jid in ids:
        search=ROOT/f'results/search/{jid}.json';pred=ROOT/f'results/predictions/{jid}.json'
        for p in (search,pred):
            if not p.exists():missing.append(p.relative_to(REPO).as_posix())
            else:hashes[p.relative_to(REPO).as_posix()]=sha(p)
        if not pred.exists() or not search.exists():continue
        sr=read(search);pr=read(pred)
        runtime_path=ROOT/f'manifests/runtime_search/{jid}.json';runtime=read(runtime_path)
        if pr['search_result_sha256']!=sha(search) or pr['input_key']!=sr['input_key']:
            raise ValueError('Prediction/search identity differs: '+jid)
        if sr['input_sha256']!=runtime['prepared_sha256'] or sr['input_key']!=runtime['array_key']:
            raise ValueError('Search/preparation identity differs: '+jid)
        bound={runtime['prepared_path']:runtime['prepared_sha256'],sr['pools_path']:sr['pools_sha256'],**sr['snapshots']}
        for path,expected in bound.items():
            if sha(REPO/path)!=expected:raise ValueError('Prepared array or resolved-pool snapshot changed: '+path)
            hashes[path]=expected
        hashes[runtime_path.relative_to(REPO).as_posix()]=sha(runtime_path)
        for p in read(pred)['predictions']:
            if not p['passes_pregate']:continue
            cid=p['candidate_id'];a=stage(cid,'A')
            for s in ('A','S','B','C'):
                f=stage_path(cid,s)
                if f.exists():
                    hashes[f.relative_to(REPO).as_posix()]=sha(f)
                    if s=='C':model_archives(f)
                elif s=='A' or a.get('status')=='COMPLETE' and a['measurement'].get('decision')=='PASS':missing.append(f.relative_to(REPO).as_posix())
    joins=ROOT/'manifests/control_joins.json'
    if joins.exists():
        hashes[joins.relative_to(REPO).as_posix()]=sha(joins)
        for row in read(joins)['rows']:
            cid=row.get('candidate_id')
            if not cid:continue
            for s in ('A','S','B','C'):
                p=stage_path(cid,s)
                if p.exists():
                    hashes[p.relative_to(REPO).as_posix()]=sha(p)
                    if s=='C':model_archives(p)
                elif s=='A' or stage(cid,'A').get('status')=='COMPLETE' and stage(cid,'A').get('measurement',{}).get('chosen_ephemeris'):missing.append(p.relative_to(REPO).as_posix())
    else:missing.append(joins.relative_to(REPO).as_posix())
    if missing:raise RuntimeError(f'{len(missing)} required predictions absent; reconcile explicit operational statuses before evaluation: {missing[:8]}')
    write(ROOT/'manifests/development_prediction_freeze.json',dict(utc=utc(),selection_sha256=sha(selection_path),hashes=hashes,
        truth_matching_performed=False,operational_rows_complete=True,final_C_stage=C_STAGE,
        previous_C_attempts_used_for_final_decisions=False,full_regression_receipt=regression_name))

def evaluate():
    selection=read(ROOT/'manifests/development_selection.json');seal=read(ROOT/'manifests/development_prediction_freeze.json')
    if sha(ROOT/'manifests/development_selection.json')!=seal['selection_sha256']:raise ValueError('Selection changed')
    for p,h in seal['hashes'].items():
        if sha(REPO/p)!=h:raise ValueError('Prediction changed: '+p)
    if (ROOT/'results/development_evaluation.json').exists():raise FileExistsError('Development evaluation already locked')
    hosts=selection['host_ids'];metadata={r['tic_id']:r for r in read(ROOT/'manifests/development_order.json')['order']}
    weights=bootstrap_weights(hosts,[metadata[h]['stratum'] for h in hosts]);truth={r['job_id']:r for r in read(ROOT/'manifests/injections_evaluator.json')}
    snr={r['job_id']:r for h in hosts for r in read(ROOT/f'results/reference_snr/tic{h}.json')['rows']}
    cohort=[];natural=[];costs={m:dict(wall=0.,cpu=0.,search_wall=0.,search_cpu=0.) for m in ('R0','R1')}
    policies=[(s,d,e) for s in ('S0','S1','S2') for d in (25,36,49,64,81,100) for e in (6,10)]
    for jid in selection['series_ids']:
        pred=read(ROOT/f'results/predictions/{jid}.json');search=read(ROOT/f'results/search/{jid}.json')
        candidates=[load_candidate(r) for r in pred['predictions']]
        row=dict(job_id=jid,tic_id=pred['tic_id'],candidate_ids=[p['candidate_id'] for p in candidates],candidates=candidates)
        for method in ('R0','R1'):
            for key in ('wall','cpu'):
                base=search['timings'][method+'_deployable_'+key]
                costs[method]['search_'+key]+=base
                costs[method][key]+=base+sum(downstream_cost(p,method)[key] for p in candidates)
        if jid in truth:
            model=truth[jid]['fixed_absolute_model'];row.update(snr_expected=snr[jid]['snr_expected'],period=model['period'],rp_earth=float(truth[jid]['original']['rp_earth']))
            for method in ('R0','R1'):
                pool=[p for p in candidates if method in p['methods']]
                matched=[p for p in pool if match(model,p['ephemeris'])==1]
                row[method+'_search']=bool(matched);row[method+'_pre']=any(p['passes_pregate'] for p in matched)
                row[method+'_AS']=any(u10(p['A'],p['S'],p['passes_pregate']) for p in matched)
                row[method+'_alias']=any(match(model,p['ephemeris'],(2.,3.,.5,1/3)) is not None for p in pool)
                for s,d,e in policies:
                    key=f'{method}_{s}_D{d}_E{e}'
                    row[key]=any(ordered(p['A'],p['S'],p['B'],p['C'],s,d,e,p['passes_pregate'])=='PASS'
                        and match(model,p['C'].get('measurement',{}).get('primary'))==1 for p in matched)
            cohort.append(row)
        else:row['is_natural']=True;natural.append(row)
    low=[7<=r['snr_expected']<15 for r in cohort];all_rows=[True]*len(cohort)
    search_low=paired(cohort,'R0_AS','R1_AS',low,hosts,weights);search_all=paired(cohort,'R0_AS','R1_AS',all_rows,hosts,weights)
    pre_counts={m:sum(p['passes_pregate'] and m in p['methods'] for r in natural for p in r['candidates']) for m in ('R0','R1')}
    search_requirements=dict(low_gain=search_low['gain_pp'] is not None and search_low['gain_pp']>=3,overall_gain=search_all['gain_pp']>=0,
        natural_pregate=pre_counts['R1']<=1.5*pre_counts['R0'],wall=costs['R1']['wall']<=1.5*costs['R0']['wall'])
    chosen='R1' if all(search_requirements.values()) else 'R0'
    control_rows=read(ROOT/'manifests/control_joins.json')['rows'];controls={r['candidate_id']:load_candidate(dict(candidate_id=r['candidate_id'])) for r in control_rows if r.get('candidate_id')}
    baseline_natural_by_host={r['tic_id']:sum(u10(p['A'],p['S'],p['passes_pregate']) for p in r['candidates'] if 'R0' in p['methods']) for r in natural}
    baseline_natural=sum(baseline_natural_by_host.values())
    table=[]
    for s,d,e in policies:
        name=f'{chosen}_{s}_D{d}_E{e}';stat=paired(cohort,'R0_AS',name,low,hosts,weights)
        overall=paired(cohort,'R0_AS',name,all_rows,hosts,weights)
        forwarded=0;forwarded_hosts=set();arrival=[];extra_cpu=0.;natural_counts={h:0 for h in hosts};natural_statuses=Counter()
        for r in cohort+natural:
            for p in r['candidates']:
                if chosen not in p['methods']:continue
                extra_cpu+=c_cost(p,s)
                if measured_arrival(p,s):arrival.append(p)
                if r.get('is_natural'):
                    status=ordered(p['A'],p['S'],p['B'],p['C'],s,d,e,p['passes_pregate'])
                    if status!='REJECT':
                        forwarded+=1;forwarded_hosts.add(r['tic_id']);natural_counts[r['tic_id']]+=1;natural_statuses[status]+=1
        control_outcomes=[];protected=0
        for r in control_rows:
            c=controls.get(r.get('candidate_id'),{})
            iso=isolated(c.get('S',{}),c.get('C',{}),s,d,e)
            actual=ordered(c.get('A',{}),c.get('S',{}),c.get('B',{}),c.get('C',{}),s,d,e)
            if r['original_protected_rejection'] and iso=='REJECT' and actual=='REJECT':protected+=1
            control_outcomes.append(dict(original_id=r['original_id'],collection=r['collection'],candidate_id=r.get('candidate_id'),isolated=iso,ordered=actual,
                protected_original=r['original_protected_rejection'],
                retained_protected_rejection=bool(r['original_protected_rejection'] and iso=='REJECT' and actual=='REJECT')))
        times=[p['C'].get('wall_seconds',600.) for p in arrival]
        unknown=sum(p['C'].get('status')!='COMPLETE' or p['C'].get('policy_decisions',{}).get(f'D{d}_E{e}',{}).get('status') not in ('PASS','REJECT') for p in arrival)
        median=float(np.median(times)) if times else None;p90=float(np.quantile(times,.9)) if times else None
        cpu=costs[chosen]['cpu']+extra_cpu
        criteria=dict(historical_protection=protected>=24,low_gain=stat['gain_pp'] is not None and stat['gain_pp']>=5,
            natural_workload=forwarded/len(hosts)<=1.25*baseline_natural/len(hosts)+.005,
            C_median=median is not None and median<=120,C_p90=p90 is not None and p90<=600,
            unresolved_fraction=bool(times) and unknown/len(times)<=.1,whole_cpu=cpu<=2*costs['R0']['cpu'])
        table.append(dict(policy=name,S=s,D=d,E=e,low=stat,overall=overall,protected=protected,protection_denominator=26,
            natural_forwarded_candidates=forwarded,natural_forwarded_hosts=len(forwarded_hosts),natural_host_interval=binomial(len(forwarded_hosts),len(hosts)),
            natural_forwarded_status_counts=dict(natural_statuses),natural_multiplicity_histogram=dict(Counter(natural_counts.values())),
            natural_forwarded_counts_by_host=natural_counts,
            C_arrivals=len(arrival),C_median_wall=median,C_p90_wall=p90,C_unknown=unknown,C_unknown_fraction=unknown/len(times) if times else None,
            cpu_seconds=cpu,cpu_ratio=cpu/costs['R0']['cpu'],criteria=criteria,eligible=all(criteria.values()),control_outcomes=control_outcomes,
            forwarded_original_S_controls=sum(r['isolated']!='REJECT' for r in control_outcomes if r['collection']=='S_original_40'),
            forwarded_distinct_negative_controls=len({r['candidate_id'] or (r['collection'],r['original_id'])
                for r in control_outcomes if r['collection'] in ('S_original_40','C_original_41') and r['ordered']!='REJECT'})))
    eligible=[p for p in table if p['eligible']]
    finalist=None
    if eligible:
        best=max(p['low']['gain_pp'] for p in eligible);tie=[p for p in eligible if p['low']['gain_pp']>=best-1]
        finalist=min(tie,key=lambda p:(p['forwarded_distinct_negative_controls'],p['cpu_seconds'],p['S'],-p['D'],-p['E']))['policy']
    operational=Counter();failed=[];seen=set()
    def record_operations(candidate,domain):
        cid=candidate['candidate_id'];a=candidate['A']
        required=['A']
        if a.get('status')=='COMPLETE' and (a.get('measurement',{}).get('decision')=='PASS' or
                domain=='historical_engineering' and a.get('measurement',{}).get('chosen_ephemeris')):
            required+=['S','B','C']
        for st in required:
            key=(domain,cid,st)
            if key in seen:continue
            seen.add(key);record=candidate[st];status=record.get('status','INPUT_ERROR')
            operational[domain+'_'+st+'_'+status]+=1
            if status!='COMPLETE':failed.append(dict(domain=domain,candidate_id=cid,stage=st,status=status,
                error=record.get('error') or record.get('reason') or record.get('measurement',{}).get('reason'),
                result_path=stage_path(cid,st).relative_to(REPO).as_posix()))
    for row in cohort+natural:
        for candidate in row['candidates']:
            if candidate['passes_pregate']:record_operations(candidate,'paired_R0_R1')
    for candidate in controls.values():record_operations(candidate,'historical_engineering')
    compact=[{k:v for k,v in r.items() if k!='candidates'} for r in cohort]
    result=dict(utc=utc(),scope='Complete registered paired D_core development only; no fresh validation inference',
        completion_kind='COMPLETE_ATTEMPTED_COHORT_WITH_OPERATIONAL_UNKNOWNS' if failed else 'COMPLETE_MEASURED_COHORT',
        completion_interpretation='All registered terminal records are frozen. Operational failures/timeouts remain unknown scientific outcomes and use the predeclared recovery/workload treatment; a complete attempted-cohort endpoint does not establish what censored stages would have returned.',
        final_C_stage=C_STAGE,
        n_hosts=len(hosts),n_injections=len(cohort),search_low=search_low,search_overall=search_all,search_requirements=search_requirements,
        selected_search=chosen,search_costs=costs,natural_pregate_counts=pre_counts,baseline_natural_postS_candidates=baseline_natural,
        baseline_natural_postS_hosts=sum(n>0 for n in baseline_natural_by_host.values()),
        baseline_natural_postS_host_interval=binomial(sum(n>0 for n in baseline_natural_by_host.values()),len(hosts)),
        baseline_natural_postS_multiplicity=dict(Counter(baseline_natural_by_host.values())),
        baseline_natural_postS_counts_by_host=baseline_natural_by_host,
        policies=table,finalist=finalist,rows=compact,
        operational_status_counts=dict(operational),operationally_failed_required_stages=failed,
        matching='P10 1% exact-period and modulo-epoch window; aliases separate. U10 uses true-matched survey candidate + unchanged pre/A/bound S. Y additionally requires unambiguous actual C PASS and the fitted C primary to match truth.',
        historical_protection='Require both isolated S/C and ordered A/S/B/C rejection on the exact original 26. An operationally unknown ordered route is not protected; A/B alone cannot conceal an isolated S/C failure. Historical controls are conditioned on their registered candidate ephemeris, not a new blind survey selection.',
        tie_forwarding='Unique exact measurement identities in the union of S_original_40 and C_original_41; preserve unavailable row identities. Count actual ordered UNRESOLVED as forwarded. Other collections contain planet injections and are not contamination negatives.',
        no_new_validation_outcomes=True)
    write(ROOT/'results/development_evaluation.json',result)
    print('development evaluation complete',len(hosts),len(cohort),'selected search',chosen,'finalist',finalist)

if __name__=='__main__':
    freeze(ROOT/'manifests/development_selection.json',sys.argv[2]) if sys.argv[1]=='freeze' else evaluate()
