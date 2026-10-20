"""Exact historical-control evidence tables after the prediction freeze."""
from common import *
import collections
from final_c import C_STAGE,stage_path

def main():
    evaluation=read(ROOT/'results/development_evaluation.json');joins=read(ROOT/'manifests/control_joins.json')['rows']
    rows=[]
    for row in joins:
        cid=row.get('candidate_id');stages={}
        for stage in ('A','S','B','C'):
            path=stage_path(cid,stage)
            stages[stage]=read(path) if cid and path.exists() else dict(status='INPUT_ERROR',reason=row.get('reason') or 'Required measurement unavailable or downstream of a terminal stage')
        c=stages['C'];m=c.get('measurement',{});primary=m.get('primary') or {}
        outcomes={p['policy']:next(x for x in p['control_outcomes'] if x['original_id']==row['original_id'] and x['collection']==row['collection']) for p in evaluation['policies']}
        rows.append(dict(registration_id=row['registration_id'],collection=row['collection'],original_id=row['original_id'],
            tic_id=row['tic_id'],candidate_id=cid,prediction_key=row.get('prediction_key'),raw_input_key=row.get('raw_input_key'),
            known_half_double=row.get('known_half_double',False),historically_protected=row['original_protected_rejection'],
            stage_statuses={k:v['status'] for k,v in stages.items()},
            operational_reasons={k:v.get('error') or v.get('reason') or v.get('measurement',{}).get('reason') for k,v in stages.items() if v['status']!='COMPLETE'},
            A_decision=stages['A'].get('measurement',{}).get('decision'),S_bound=stages['S'].get('measurement',{}).get('gate'),
            S_modes=stages['S'].get('measurement',{}).get('secondary',{}).get('gate_by_mode_p10'),
            B_decision=stages['B'].get('measurement',{}).get('decision'),
            C_primary={k:primary.get(k) for k in ('period_days','epoch_btjd','duration_days','chi2_flat','chi2','D','BIC','k','n')},
            C_operational_status=c['status'],C_wall_seconds=c.get('wall_seconds'),C_cpu_seconds=c.get('cpu_seconds'),
            outcomes=outcomes,full_C_record=None if not cid else stage_path(cid,'C').relative_to(REPO).as_posix(),
            interpretation='Historical candidate-conditioned engineering control; not a fresh survey-domain binary challenge'))
    summaries=[]
    for policy in evaluation['policies']:
        for collection in sorted({r['collection'] for r in rows}):
            selected=[r for r in rows if r['collection']==collection]
            summaries.append(dict(policy=policy['policy'],collection=collection,n_registered=len(selected),
                unique_measurement_identities=len({r['candidate_id'] for r in selected if r['candidate_id']}),
                ordered_counts=dict(collections.Counter(r['outcomes'][policy['policy']]['ordered'] for r in selected)),
                isolated_counts=dict(collections.Counter(r['outcomes'][policy['policy']]['isolated'] for r in selected)),
                operational_C_counts=dict(collections.Counter(r['C_operational_status'] for r in selected))))
    persistent={'eb_tic178858648_candidate1','eb_tic237116051_candidate1','eb_tic272598447_candidate1'}
    write(ROOT/'results/historical_control_tables.json',dict(utc=utc(),evaluation_sha256=sha(ROOT/'results/development_evaluation.json'),
        registered_rows=len(rows),rows=rows,summaries=summaries,final_C_stage=C_STAGE,
        persistent_EB_aliases=[r for r in rows if r['collection']=='C_original_41' and r['original_id'] in persistent],
        exact_join='Collection + original record identity -> registered ephemeris + raw array content + stellar/config/source identity. TIC equality alone is never a join.',
        unknowns_count_as_protected=False,negative_forwarding_semantics='Ordered/isolated UNRESOLVED is forwarded. Natural and historical survivor counts are not all proven astrophysical false positives.'))
    print('historical control tables complete',len(rows),'original rows')

if __name__=='__main__':main()
