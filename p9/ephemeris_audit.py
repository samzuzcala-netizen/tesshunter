"""Post-lock published-timing audit; no scientific rerun or primary score change.

Every locked positive is listed. All NASA PS solutions are snapshotted for each
positive with an accepted near-period signal that fails the frozen event rule.
Each solution is evaluated separately; none replaces the frozen truth manifest.
"""
from common import *
import argparse, math
import pandas as pd
import numpy as np
from scoring import GATES, times_for, observed_centers, match_signal, score_one, verify_lock
from tables import table


def solutions(name,tic,lock):
    folder=P9/'diagnostics/ephemeris_sources';folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'tic{tic}_nasa_ps.csv';receipt=folder/f'tic{tic}_receipt.json'
    if path.exists():
        rec=read(receipt)
        if sha(path)!=rec['sha256']:raise RuntimeError('Changed post-lock source snapshot')
        return pd.read_csv(path),rec
    import requests
    fields='pl_name,default_flag,pl_orbper,pl_orbpererr1,pl_orbpererr2,pl_tranmid,pl_tranmiderr1,pl_tranmiderr2,pl_trandur,pl_refname'
    query=f"select {fields} from ps where pl_name='{name.replace(chr(39),chr(39)*2)}'"
    response=requests.get('https://exoplanetarchive.ipac.caltech.edu/TAP/sync',
        params={'query':query,'format':'csv'},timeout=60)
    response.raise_for_status();data=response.content
    import io
    frame=pd.read_csv(io.BytesIO(data))
    if len(frame)==0 or not {'pl_orbper','pl_tranmid','pl_refname'}<=set(frame):
        raise RuntimeError('No valid published ephemerides returned')
    path.write_bytes(data)
    rec=dict(utc=utc(),source_url=response.url,query=query,sha256=sha(path),
        outcome_locked_utc=lock['utc'],selection='All available PS timing rows, queried only after a near-period/no-event-match positive was locked',
        primary_manifest_unchanged=True)
    write(receipt,rec)
    return frame,rec


def timing_differences(times,truth,candidate):
    true=observed_centers(times,truth['period'],truth['epoch_btjd'],truth['duration_hours']/24)
    p=candidate['period'];t0=candidate['t0']
    residual=t0+np.rint((true-t0)/p)*p-true
    return dict(median_absolute_hours=float(np.median(abs(residual))*24) if len(residual) else None,
        minimum_absolute_hours=float(np.min(abs(residual))*24) if len(residual) else None,
        maximum_absolute_hours=float(np.max(abs(residual))*24) if len(residual) else None)


def run(partial=False):
    suffix='_partial' if partial else ''
    scores=read(P9/f'results/scored_signals{suffix}.json')
    truth=pd.read_csv(P9/'truth/final_truth.csv').set_index('truth_id')
    eligibility=read(P9/'truth/final_eligibility.json')
    features={r['truth_id']:r for r in read(P9/'results/diagnostic_features.json')}
    rows=[];evidence=[]
    for s in scores:
        if s['label']!='positive':continue
        tic=int(s['tic_id']);lock=verify_lock(tic);t=truth.loc[s['truth_id']].to_dict()
        t.update(truth_id=s['truth_id'],tic_id=tic)
        near=[r for r in s.get('all_search_matches',[]) if
            r['match'].get('period_fraction') is not None and r['match']['period_fraction']<=.01 and not r['match']['matched']]
        f=features.get(s['truth_id'],{})
        row=dict(truth_id=s['truth_id'],tic_id=tic,first_termination=s['first_termination'],primary_search=s['search'],
            ephemeris_sigma_over_duration=f.get('ephemeris_sigma_over_duration'),
            near_period_event_mismatches=near,alternative_solutions=[])
        if not s['search'] and near:
            tt=times_for(tic);root=P9/'results/blind'/f'tic{tic}'
            sr=read(root/'search/results'/f'tic{tic}.json')
            selected=[q for q in sr['result']['planets'] if q['planet_num'] in {n['planet_num'] for n in near}]
            frame,receipt=solutions(s['truth_id'],tic,lock)
            row['post_lock_source']=receipt
            row['nominal_candidate_timing']=[dict(key=f'tic{tic}_P{q["period_days"]:.4f}',
                **timing_differences(tt,t,dict(period=q['period_days'],t0=q['epoch_btjd']))) for q in selected]
            for _,r in frame.iterrows():
                if not pd.notna(r.pl_orbper) or not pd.notna(r.pl_tranmid):continue
                alt=dict(t,period=float(r.pl_orbper),epoch_btjd=float(r.pl_tranmid)-2457000,
                    duration_hours=float(r.pl_trandur) if pd.notna(r.pl_trandur) and r.pl_trandur>0 else float(t['duration_hours']))
                # score_one reads existing locked gates only; it launches no stage.
                eg=next(e for e in eligibility if e['truth_id']==s['truth_id']) if isinstance(eligibility,list) else eligibility[s['truth_id']]
                result=score_one(alt,eg)
                candidates=[]
                for q in selected:
                    ep=dict(period=q['period_days'],t0=q['epoch_btjd'],duration=q['duration_days'])
                    candidates.append(dict(key=f'tic{tic}_P{q["period_days"]:.4f}',event_match=match_signal(tt,alt,ep),
                        timing=timing_differences(tt,alt,ep)))
                errors=[abs(float(r[k])) for k in ['pl_orbpererr1','pl_orbpererr2'] if pd.notna(r[k])]
                ee=[abs(float(r[k])) for k in ['pl_tranmiderr1','pl_tranmiderr2'] if pd.notna(r[k])]
                sig=math.hypot(max(ee),max(abs((tt-alt['epoch_btjd'])/alt['period']))*max(errors))/(alt['duration_hours']/24) if errors and ee else None
                row['alternative_solutions'].append(dict(reference=r.pl_refname,default_flag=int(r.default_flag),
                    period=alt['period'],epoch_btjd=alt['epoch_btjd'],duration_hours=alt['duration_hours'],
                    duration_source='same published PS solution' if pd.notna(r.pl_trandur) else 'frozen manifest fallback',
                    ephemeris_sigma_over_duration=float(sig) if sig is not None else None,
                    candidate_matches=candidates,diagnostic_existing_path={g:result[g] for g in GATES},
                    diagnostic_first_termination=result.get('first_termination'),
                    primary_credit=False,no_scientific_stage_rerun=True))
            evidence.append(P9/'diagnostics/ephemeris_sources'/f'tic{tic}_nasa_ps.csv')
        rows.append(row)
    out=dict(utc=utc(),partial=partial,records=rows,script_sha256=sha(Path(__file__)),
        source_sha256={str(p.relative_to(P9)):sha(p) for p in evidence},
        interpretation='Post-lock sensitivity to published timing solutions. All primary scores and frozen ephemerides are unchanged. No stage, fit or manual review is rerun, and an alternative association earns no primary credit.',
        uncertainty='Independent period/epoch errors only; covariance and timing variations are unmodeled. No variant effectiveness or specificity is inferred.')
    write(P9/f'results/positive_ephemeris_audit{suffix}.json',out)
    text=['# P9 positive-control published-ephemeris audit','',out['interpretation'],'',out['uncertainty'],'',
        table(['Planet','Primary search','First termination','Timing sigma / duration','Near-period rejected matches'],
            [[r['truth_id'],r['primary_search'],r['first_termination'],r['ephemeris_sigma_over_duration'],len(r['near_period_event_mismatches'])] for r in rows]),'']
    for r in rows:
        if not r['alternative_solutions']:continue
        text+=['## '+r['truth_id'],'',
            'All available NASA PS timing solutions, including publication and ExoFOP entries, were retrieved after the host lock; the selection was a nominal near-period/event mismatch. They are not ranked by downstream performance. Each row applies the same fixed event rule to existing blind outputs.','',
            'Frozen-ephemeris timing residuals: '+str(r['nominal_candidate_timing']), '',
            table(['Published reference','Period (d)','Epoch (BTJD)','Duration (h)','Timing sigma / duration','Diagnostic existing-path end','Primary credit'],
                [[a['reference'],a['period'],a['epoch_btjd'],a['duration_hours'],a['ephemeris_sigma_over_duration'],a['diagnostic_first_termination'],'none'] for a in r['alternative_solutions']]),'']
    (P9/('EPHEMERIS_AUDIT_PARTIAL.md' if partial else 'EPHEMERIS_AUDIT.md')).write_text('\n'.join(text),encoding='utf-8')
    print('Positive ephemeris audit',len(rows),'controls;',sum(bool(r['alternative_solutions']) for r in rows),'with alternative published-solution diagnostics',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');args=parser.parse_args();run(args.partial)
