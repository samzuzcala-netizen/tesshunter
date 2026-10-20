"""Read all 52 historical loss cases; never treat witnesses as new recoveries."""
from common import *
environment()
import sys,re
from collections import Counter
sys.path[:0]=[str(REPO/'src'),str(REPO/'p10/protocol')]
from tesshunter.p11_5_search import ephemeris_equal
from search_trace_audit import reconstructed

def main():
    original=read(REPO/'p10/results/search_injections_e.json')
    cases=[r for r in original['rows'] if r.get('ranking',{}).get('lost_to_ranking')]
    assert len(cases)==52 and sum(len(r['ranking']['witnesses']) for r in cases)==124
    hosts={r['tic_id']:r for r in read(ROOT/'manifests/hosts.json')}
    run=REPO/'data/survey/runs/p10_2b/e_inj';rows=[]
    for case in cases:
        jid=case['job_id'];path=run/f'results/{jid}.json';rec=read(path)
        trace=run/f'traces/{jid}.jsonl';log=run/f'logs/{jid}.log'
        groups,winners,diagnostic=reconstructed(trace,log,16)
        h=hosts[case['tic_id']];index=read(DATA/f'raw/tic{h["tic_id"]}/index.json')
        old=rec['result']['provenance']['products'];current=index['products']
        old_ids={(int(p['unit']),p['author'],Path(p['file']).name) for p in old}
        new_ids={(int(p['sector']),p['author'],Path(p.get('original_file',p['file'])).name) for p in current}
        # Identical product membership is necessary but insufficient for replay;
        # the inherited traces have no immutable mask/flux arrays.
        input_membership_unchanged=old_ids==new_ids
        partitions=[];unused_before=0.
        for part in rec['searches']:
            used=float(part['timings'].get('detect',0));allowance=.85*float(part['budget_s'])
            notes=part.get('notes',[])
            exhausted=any('detection budget' in note.lower() for note in notes)
            partitions.append(dict(partition=part['label'],nominal_budget_seconds=part['budget_s'],
                effective_detection_allowance_seconds=allowance,measured_detection_seconds=used,
                exhausted=exhausted,potential_unused_seconds=max(0.,allowance-used),
                previously_available_seconds=unused_before,notes=notes))
            unused_before+=max(0.,allowance-used)
        bypart={r['partition']:r for r in partitions};witnesses=[]
        for witness in case['ranking']['witnesses']:
            key=(witness['partition'],witness['detection_pass'])
            passing=[e['resolved'] for e in groups[key] if e['all_gates_pass_log']]
            ranked=sorted(passing,key=lambda p:-float(p['snr']))
            matches=[i for i,p in enumerate(ranked) if abs(float(p['period_days'])-witness['injection_trial_period'])<1e-12 and abs(float(p['epoch_btjd'])-witness['injection_trial_epoch'])<1e-12]
            assert matches
            duplicate_pairs=[dict(first=i+1,second=j+1) for i,p in enumerate(ranked) for j,q in enumerate(ranked[i+1:],i+1)
                if ephemeris_equal(p,q,rec['baseline_days'])]
            prior=[]
            for (part,number),events in groups.items():
                if part==key[0] and number<key[1] and (part,number) in winners:
                    winner=max((e['resolved'] for e in events if e['all_gates_pass_log']),key=lambda q:float(q['snr']))
                    prior.append(dict(detection_pass=number,**{k:winner[k] for k in ('period_days','epoch_btjd','duration_days')}))
            diagnostic_applicable=h['population']=='D_core' and input_membership_unchanged
            part=bypart[key[0]]
            witnesses.append(dict(witness,all_matching_ranks=[i+1 for i in matches],rank=matches[0]+1,
                ranked_gate_passing_pool=ranked,period_epoch_duplicates=duplicate_pairs,ordinary_masking_history=prior,
                relevant_partition=part,diagnostic_applicable_to_frozen_products=diagnostic_applicable,
                potentially_reclaimable=bool(part['exhausted'] and part['previously_available_seconds']>0),
                mask_snapshot_available=False,replay_valid=False))
        text=log.read_text(encoding='utf-8')
        rows.append(dict(job_id=jid,tic_id=case['tic_id'],population=h['population'],
            input_membership_unchanged=input_membership_unchanged,partitions=partitions,witnesses=witnesses,
            masking_log=[l for l in text.splitlines() if 'mask' in l.lower() and ('veto' in l.lower() or 'mask check' in l.lower())],
            source_sha256={p.relative_to(REPO).as_posix():sha(p) for p in (path,trace,log)}))
    admission=sum(any(w['diagnostic_applicable_to_frozen_products'] and w['potentially_reclaimable'] for w in r['witnesses']) for r in rows)
    result=dict(utc=utc(),n_cases=len(rows),n_witnesses=sum(len(r['witnesses']) for r in rows),
        relevant_exhausted_reclaimable_cases=admission,R2_admitted=False,
        R2_reason='Fewer than 10 applicable cases satisfy exhaustion plus prior reclaimable time' if admission<10 else 'Affordability must be checked before admission',
        meaning='Historical development diagnostics only. No new recovery or complete replay claim.',rows=rows)
    write(ROOT/'results/trace_diagnostic.json',result)
    print('trace cases',len(rows),'witnesses',result['n_witnesses'],'R2 relevant',admission)

if __name__=='__main__':main()
