"""Registered search/funnel retention and paired whole-host uncertainty."""
from common import REPO,ROOT,read,write,sha,utc,environment
environment()
import csv,json,time,math,hashlib
from collections import Counter,defaultdict
import numpy as np
from cluster_bootstrap_v1 import host_weights,logistic_snr50
from part_f_math_v1 import STRATA,finite,model_snr_bin,expected_snr_bin,period_bin
from full_funnel_plan import stage_decision,charge
from part_f_guards_v1 import require_hash,assert_no_integrity_failure
from registration_execution_v3 import verify
from lock_predictions import both_locked

PRESETS=('survey_p10','survey_p8')
STAGES=('search','pre_gate','A','S','B','C')

def search_state(summary):
    status=summary['status']
    return 'PASS' if status.startswith('RECOVERED_') else 'FAIL' if status=='NOT_RECOVERED' else 'OUTSIDE_DOMAIN' if status=='OUTSIDE_DOMAIN' else 'UNKNOWN'

def sequence(summary,pregate,decisions,selected_C):
    state=search_state(summary)
    if state!='PASS':return dict(states={s:state for s in STAGES},passing_candidates={s:[] for s in STAGES},not_run_C=[])
    active=set(summary['recovered_candidate_ids']);unknown=False
    states={'search':'PASS'};carried={'search':sorted(active)};notrun=[]
    for stage in STAGES[1:]:
        passing=set();new_unknown=False
        for cid in active:
            if stage=='pre_gate':d='PASS' if cid in pregate else 'FAIL'
            elif stage=='C' and cid not in selected_C:d='NOT_RUN';notrun.append(cid)
            else:d=decisions.get(stage,{}).get(cid,'OPERATIONAL_UNKNOWN')
            if d=='PASS' or (stage=='S' and d=='HOLD'):passing.add(cid)
            elif d!='FAIL':new_unknown=True
        unknown=unknown or new_unknown
        if passing:states[stage]='PASS'
        elif unknown:
            only_unrun=(stage=='C' and notrun and not unknown_before_C(states) and all(cid not in selected_C for cid in active))
            states[stage]='NOT_RUN' if only_unrun else 'UNKNOWN'
        else:states[stage]='FAIL'
        active=passing;carried[stage]=sorted(active)
    return dict(states=states,passing_candidates=carried,not_run_C=sorted(set(notrun)))

def unknown_before_C(states):
    return any(v in ('UNKNOWN','NOT_RUN') for k,v in states.items() if k!='C')

class HostStatistics:
    def __init__(self,hosts,weights):
        self.hosts=list(hosts);self.index={h:i for i,h in enumerate(hosts)}
        self.weights=weights;self.cache={}
    def counts(self,hosts):
        a=np.zeros(len(self.hosts),dtype=float)
        for host in hosts:a[self.index[host]]+=1
        return a
    def ratio(self,numerator_hosts,denominator_hosts,allow_rate=False):
        n,d=self.counts(numerator_hosts),self.counts(denominator_hosts)
        if not allow_rate and np.any(n>d):raise ValueError('Numerator is not a denominator subset by host')
        key=(tuple(n),tuple(d));cached=self.cache.get(key)
        if cached is not None:return cached.copy()
        ns,ds=int(n.sum()),int(d.sum())
        result=dict(numerator=ns,denominator=ds,fraction=ns/ds if ds else None,ci95=None,bootstrap_valid_draws=0)
        if ds:
            indices=np.flatnonzero(d)
            draws=self.weights[:,indices].astype(float) @ np.column_stack((n[indices],d[indices]))
            good=draws[:,1]>0;values=draws[good,0]/draws[good,1]
            result.update(ci95=np.percentile(values,[2.5,97.5]).tolist(),bootstrap_valid_draws=int(good.sum()))
        self.cache[key]=result.copy();return result

    def difference(self,first_hosts,second_hosts,denominator_hosts):
        a,b,d=self.counts(first_hosts),self.counts(second_hosts),self.counts(denominator_hosts)
        if np.any(a>d) or np.any(b>d):raise ValueError('Paired outcomes must share the denominator')
        total=int(d.sum())
        result=dict(n_paired=total,difference=(a.sum()-b.sum())/total if total else None,ci95=None,bootstrap_valid_draws=0)
        if total:
            ix=np.flatnonzero(d);draws=self.weights[:,ix].astype(float)@np.column_stack((a[ix]-b[ix],d[ix]))
            good=draws[:,1]>0;values=draws[good,0]/draws[good,1]
            result.update(ci95=np.percentile(values,[2.5,97.5]).tolist(),bootstrap_valid_draws=int(good.sum()))
        return result

def observations(matching,forced,pregate,decisions,selected_C):
    output={unit:{s:[] for s in STRATA} for unit in ('families','raw_rows')}
    for family in matching['ephemeris_families']:
        presence=forced['families'][family['family_id']]['presence']
        for stratum,record in family['strata'].items():
            row=dict(observation_id=family['family_id'],family_id=family['family_id'],tic_id=family['tic_id'],
                representative_row_id=record['representative_row_id'],n_raw_rows=len(record['member_row_ids']),
                in_band=record['in_band'],mixed_domain_membership=record['mixed_domain_membership'],
                likely_periodic=record['likely_periodic_in_band'],expected_snr=record['expected_snr'],
                model_snr=finite(record['representative']['tce_model_snr']),period=finite(record['representative']['tce_period']),
                presence=presence,presets=record['presets'])
            row['sequence']=sequence(row['presets']['survey_p10'],pregate,decisions,selected_C)
            output['families'][stratum].append(row)
    for record in matching['rows']:
        row=dict(observation_id=record['row_id'],family_id=record['family_id'],tic_id=record['tic_id'],
            representative_row_id=record['row_id'],n_raw_rows=1,in_band=record['in_band'],mixed_domain_membership=False,
            likely_periodic=record['likely_periodic'],expected_snr=record['expected_snr'],
            model_snr=finite(record['raw']['tce_model_snr']),period=finite(record['raw']['tce_period']),
            presence=forced['families'][record['family_id']]['presence'],presets=record['presets'])
        row['sequence']=sequence(row['presets']['survey_p10'],pregate,decisions,selected_C)
        for stratum in (record['independence'],'UNION'):output['raw_rows'][stratum].append(row.copy())
    return output

def groups(rows,only_expected=False):
    yield 'all','ALL',rows
    functions=[('expected_snr',lambda r:expected_snr_bin(r['expected_snr']))]
    if not only_expected:functions.extend([('model_snr',lambda r:model_snr_bin(r['model_snr'])),('period',lambda r:period_bin(r['period']))])
    for dimension,function in functions:
        grouped=defaultdict(list)
        for row in rows:grouped[function(row)].append(row)
        for label,subset in grouped.items():yield dimension,label,subset

def search_table(rows,preset,stats):
    inside=[r for r in rows if r['in_band']]
    known=[r for r in inside if search_state(r['presets'][preset]) in ('PASS','FAIL')]
    recovered=[r for r in known if search_state(r['presets'][preset])=='PASS']
    exact=[r for r in known if r['presets'][preset]['exact_candidate_ids']]
    both=[r for r in known if r['presence'] in ('PRESENT','ABSENT')]
    hosts=lambda rs:[r['tic_id'] for r in rs]
    result=dict(n_total=len(rows),n_hosts=len(set(hosts(rows))),n_in_band=len(inside),n_outside=len(rows)-len(inside),
        n_mixed_domain=sum(r['mixed_domain_membership'] for r in rows),search_unknown=len(inside)-len(known),
        forced_unknown=sum(r['presence']=='OPERATIONAL_UNKNOWN' for r in inside),
        n_exact=len(exact),n_alias_only=len(recovered)-len(exact),n_not_recovered=len(known)-len(recovered),
        recovery=stats.ratio(hosts(recovered),hosts(known)),exact_recovery=stats.ratio(hosts(exact),hosts(known)),matrix={})
    for presence in ('PRESENT','ABSENT'):
        subset=[r for r in both if r['presence']==presence]
        yes=[r for r in subset if search_state(r['presets'][preset])=='PASS']
        result['recovery_'+presence.lower()]=stats.ratio(hosts(yes),hosts(subset))
        for recovered_state in ('PASS','FAIL'):
            cell=[r for r in subset if search_state(r['presets'][preset])==recovered_state]
            result['matrix'][presence+'_'+('RECOVERED' if recovered_state=='PASS' else 'NOT_RECOVERED')]=stats.ratio(hosts(cell),hosts(both))
    return result

def funnel_table(rows,stats):
    eligible=[r for r in rows if r['in_band'] and r['presence']=='PRESENT']
    output={};hosts=lambda rs:[r['tic_id'] for r in rs]
    for index,stage in enumerate(STAGES):
        prior=STAGES[index-1] if index else None
        at_risk=[r for r in eligible if prior is None or r['sequence']['states'][prior]=='PASS']
        known=[r for r in eligible if r['sequence']['states'][stage] in ('PASS','FAIL')]
        conditional=[r for r in at_risk if r['sequence']['states'][stage] in ('PASS','FAIL')]
        passes=[r for r in known if r['sequence']['states'][stage]=='PASS']
        # A previously unknown route can establish a later pass via another candidate;
        # pass still implies at least one actual passing path through every prior gate.
        cp=[r for r in conditional if r['sequence']['states'][stage]=='PASS']
        output[stage]=dict(n_present_in_band=len(eligible),n_at_risk=len(at_risk),n_pass=len(passes),
            n_fail=sum(r['sequence']['states'][stage]=='FAIL' for r in at_risk),
            n_unknown=sum(r['sequence']['states'][stage]=='UNKNOWN' for r in eligible),
            n_not_run=sum(r['sequence']['states'][stage]=='NOT_RUN' for r in eligible),
            conditional_unknown=sum(r['sequence']['states'][stage] in ('UNKNOWN','NOT_RUN') for r in at_risk),
            conditional=stats.ratio(hosts(cp),hosts(conditional)),cumulative=stats.ratio(hosts(passes),hosts(known)))
    return output

def interpretation_rule(n,point,baseline):
    if n<40:return 'NOT_POWERED',False
    if point['status']!='IDENTIFIED':return 'UNIDENTIFIED',False
    fires=point['snr50']>1.3*baseline
    return ('OPTIMISTIC' if fires else 'DID_NOT_FIRE'),fires

def calibration(rows,stats):
    qualifying=[r for r in rows if r['in_band'] and r['likely_periodic'] and r['presence']=='PRESENT']
    result={}
    for preset,baseline in (('survey_p10',11.58),('survey_p8',13.15)):
        sample=[r for r in qualifying if finite(r['expected_snr']) is not None and r['expected_snr']>0 and search_state(r['presets'][preset]) in ('PASS','FAIL')]
        snr=np.array([r['expected_snr'] for r in sample]);y=np.array([search_state(r['presets'][preset])=='PASS' for r in sample],dtype=int)
        point=logistic_snr50(snr,y);values=[];failed=Counter();slopes=Counter()
        columns=[stats.index[r['tic_id']] for r in sample]
        for weights in stats.weights[:,columns]:
            fit=logistic_snr50(snr,y,weights)
            if fit['status']=='IDENTIFIED':values.append(fit['snr50']);slopes[str(fit['increasing_with_snr'])]+=1
            else:failed[fit['reason']]+=1
        rule,fires=interpretation_rule(len(sample),point,baseline)
        result[preset]=dict(n_qualifying=len(qualifying),n_fitted=len(sample),n_hosts=len({r['tic_id'] for r in sample}),
            excluded_unmeasured=len(qualifying)-len(sample),fit=point,bootstrap_ci95=np.percentile(values,[2.5,97.5]).tolist() if values else None,
            bootstrap_valid=len(values),bootstrap_failures=dict(failed),bootstrap_slope_signs=dict(slopes),
            injection_snr50=baseline,threshold=1.3*baseline,rule=rule,fires=fires,
            fitted_family_ids=[r['family_id'] for r in sample])
        print('H',preset,rule,'n',len(sample),'valid bootstrap',len(values),flush=True)
    return result

def loss_attributions(observed,receipts,collection):
    out=[]
    for unit,by_stratum in observed.items():
        for stratum,rows in by_stratum.items():
            for row in rows:
                if not row['in_band'] or row['presence']!='PRESENT':continue
                states=row['sequence']['states']
                for i,stage in enumerate(STAGES[1:],1):
                    prior=STAGES[i-1]
                    if states[prior]!='PASS' or states[stage]!='FAIL':continue
                    evidence=[]
                    for cid in row['sequence']['passing_candidates'][prior]:
                        if stage=='pre_gate':
                            candidate=collection[cid]
                            evidence.append(dict(candidate_id=cid,failed_criteria=[k for k in ('pregate_snr','pregate_transits','pregate_epoch') if candidate.get(k,'').lower()!='true']))
                        else:
                            rec=receipts.get(stage,{}).get(cid,{})
                            m=rec.get('measurement',{})
                            evidence.append(dict(candidate_id=cid,decision=stage_decision(rec),reason=m.get('reason'),
                                failed_criteria=[k for k,v in m.get('criteria',{}).items() if v is False],
                                gate_mode=m.get('thresholds',{}).get('gate_mode'),chosen_ephemeris=m.get('chosen_ephemeris')))
                    out.append(dict(unit=unit,stratum=stratum,observation_id=row['observation_id'],tic_id=row['tic_id'],
                        expected_snr_bin=expected_snr_bin(row['expected_snr']),removed_at=stage,evidence=evidence))
    return out

def injection_comparison(path):
    rows=list(csv.DictReader(path.open(encoding='utf-8-sig')))
    hosts=sorted({int(r['tic_id']) for r in rows});stats=HostStatistics(hosts,host_weights(len(hosts)))
    mapping={'search':'recovered','pre_gate':'through_pregate','A':None,'S':'through_funnel_pregated'}
    output=[]
    for label in ['ALL']+list(dict.fromkeys(expected_snr_bin(r['snr_expected']) for r in rows)):
        subset=rows if label=='ALL' else [r for r in rows if expected_snr_bin(r['snr_expected'])==label]
        for stage,field in mapping.items():
            if field is None:passers=[r for r in subset if r['recovered']=='True' and r['pregate']=='True' and r['stageA']=='PASS']
            else:passers=[r for r in subset if r[field]=='True']
            output.append(dict(bin=label,stage=stage,retention=stats.ratio([int(r['tic_id']) for r in passers],[int(r['tic_id']) for r in subset])))
    return dict(source=path.relative_to(REPO).as_posix(),sha256=sha(path),n_injections=len(rows),n_hosts=len(hosts),tables=output,
        comparison_limits='Historic injections are planets by construction and exact-only recovery; real TCE families count registered integer aliases and include binaries/systematics. B/C and endpoint specificity were not injection-calibrated here. Injection host bootstrap is independent of the paired real-host bootstrap.')

def main():
    assert_no_integrity_failure();verify(require_launch_seal=True);both_locked()
    assert not (ROOT/'manifests/controller_owner.json').exists()
    assert not (ROOT/'results/retention_analysis.json').exists()
    for name in ('early_funnel_closed_evidence_seal.json','forced_fits_closed_evidence_seal.json','stage_C_closed_evidence_seal.json'):
        for path,digest in read(ROOT/'manifests'/name)['files'].items():require_hash(REPO/path,digest,'Closed analysis input')
    registration=read(ROOT/'manifests/retention_analysis_registration_v1.json')
    for path,digest in registration['source_hashes'].items():require_hash(REPO/path,digest,'Analysis source')
    started,timer=utc(),time.perf_counter()
    try:
        hosts=read(ROOT/'manifests/allocation.json')['selected_tic_ids'];weights=host_weights(len(hosts));stats=HostStatistics(hosts,weights)
        matching=read(ROOT/'results/matching.json');forced=read(ROOT/'results/forced_fits.json')
        receipts={stage:{p.stem:read(p) for p in (ROOT/f'results/funnel/{stage}').glob('*.json')} for stage in ('A','S','B','C')}
        decisions={s:{cid:stage_decision(r) for cid,r in rec.items()} for s,rec in receipts.items()}
        full=read(ROOT/'manifests/full_funnel_candidates.json');pregate={r['candidate_id'] for r in full['entries']}
        collection={f"tic{int(r['tic_id'])}_p{int(r['planet_num']):02d}":r for r in csv.DictReader((REPO/full['collection_root']/'candidates.csv').open(encoding='utf-8-sig'))}
        selected={r['candidate_id'] for r in read(ROOT/'manifests/stage_C_selection_v1.json')['selected']}
        observed=observations(matching,forced,pregate,decisions,selected)
        write(ROOT/'results/retention_observations.json',dict(utc=utc(),observations=observed))
        searches=[];funnels=[];paired=[]
        for unit,by_stratum in observed.items():
            for stratum,rows in by_stratum.items():
                for dimension,label,subset in groups(rows):
                    for preset in PRESETS:searches.append(dict(unit=unit,stratum=stratum,preset=preset,dimension=dimension,bin=label,**search_table(subset,preset,stats)))
                    pair=[r for r in subset if r['in_band'] and r['presence']=='PRESENT' and all(search_state(r['presets'][p]) in ('PASS','FAIL') for p in PRESETS)]
                    paired.append(dict(unit=unit,stratum=stratum,dimension=dimension,bin=label,
                        **stats.difference([r['tic_id'] for r in pair if search_state(r['presets'][PRESETS[0]])=='PASS'],
                        [r['tic_id'] for r in pair if search_state(r['presets'][PRESETS[1]])=='PASS'],[r['tic_id'] for r in pair])))
                for dimension,label,subset in groups(rows,only_expected=True):
                    funnels.append(dict(unit=unit,stratum=stratum,dimension=dimension,bin=label,stages=funnel_table(subset,stats)))
        print('Retention tables complete',len(searches),len(funnels),flush=True)
        H=calibration(observed['families']['INDEPENDENT'],stats)
        natural=[]
        for stage in ('accepted','pre_gate','A','S','B','C'):
            if stage=='accepted':passed=[int(r['tic_id']) for r in collection.values()];unknown=0;attempted=len(passed)
            elif stage=='pre_gate':passed=[int(collection[c]['tic_id']) for c in pregate];unknown=0;attempted=len(collection)
            else:
                passed=[int(r['tic_id']) for r in receipts[stage].values() if stage_decision(r)=='PASS' or (stage=='S' and stage_decision(r)=='HOLD')]
                attempted=len(pregate) if stage=='A' else len(receipts[stage])
                unknown=attempted-len(receipts[stage])+sum(stage_decision(r)=='OPERATIONAL_UNKNOWN' for r in receipts[stage].values())
            natural.append(dict(stage=stage,passing_count=len(passed),attempted=attempted,operational_unknowns=unknown,
                per_star=stats.ratio(passed,hosts,allow_rate=True)))
        losses=loss_attributions(observed,receipts,collection);write(ROOT/'results/funnel_loss_attributions.json',dict(utc=utc(),losses=losses))
        historic=REPO/'data/survey/p10/part2d/calibration/injection_outcomes_p10.csv'
        result=dict(utc=utc(),status='RETENTION_ANALYZED',original_population=531,input_eligible=436,evaluated=436,
            original_development_exposed=531,search_tables=searches,paired_present_recovery_differences=paired,
            funnel_tables=funnels,natural_load=natural,calibration=H,
            injection_comparison=injection_comparison(historic),
            bootstrap=dict(draws=10000,seed=2026091401,bit_generator='PCG64',host_order_sha256=hashlib.sha256(json.dumps(hosts).encode()).hexdigest(),
                paired_host_weights_sha256=hashlib.sha256(weights.tobytes()).hexdigest(),ci_percentiles=[2.5,97.5]),
            assumptions=read(ROOT/'manifests/part_f_method_registration_v1.json')['assumptions'])
        write(ROOT/'results/retention_analysis.json',result)
        print(json.dumps(dict(status=result['status'],H={p:{k:v for k,v in r.items() if k not in ('fitted_family_ids','bootstrap_slope_signs')} for p,r in H.items()})),flush=True)
    finally:charge(started,timer,'F_G_H_retention_bootstrap_analysis')

if __name__=='__main__':main()
