"""Post-lock audit of reported C duration and the registered event census.

Read saved measurements only. Duration substitutions are diagnostic identity
checks, not alternative primary scores, a new search, or a gate variant.
"""
from common import *
import csv
import numpy as np
from scoring import times_for, match_signal, verify_lock
from tables import table


def run():
    scores=read(P9/'results/scored_signals.json')
    truth={r['truth_id']:r for r in csv.DictReader((P9/'truth/final_truth.csv').open(encoding='utf-8'))}
    rows=[];identities=[];sources={}
    for tic in read(P9/'manifests/final_ids.json'):
        root=P9/'results/blind'/f'tic{tic}'
        for path in sorted((root/'stageC').glob('*.json')):
            lock=verify_lock(tic);c=read(path);b=c.get('blind') or {}
            if not b:continue
            key=path.stem;duration=float(b['duration_days']);fitpath=root/'fit'/path.name
            fit=read(fitpath) if fitpath.exists() else {}
            row=dict(tic_id=tic,key=key,native_C_decision=c['decision'],
                reported_C_duration_seconds=duration*86400,
                reported_C_duration_over_nominal_cadence=duration*86400/200,
                sub_cadence_duration=duration*86400<200,
                native_D_seed_duration_seconds=(fit.get('ephemeris_start') or {}).get('duration',0)*86400 or None,
                D_fitted_duration_hours=(fit.get('adopted') or {}).get('t14_hours'))
            rows.append(row);sources[str(path.relative_to(P9))]=sha(path)
            if fitpath.exists():sources[str(fitpath.relative_to(P9))]=sha(fitpath)
            for s in scores:
                if s.get('candidate_key')!=key or s.get('first_termination')!='C_signal_switch':continue
                t=truth[s['truth_id']];tt=times_for(tic)
                a=read(root/'stageA'/path.name)
                ae=a['per_ephemeris'][a['chosen_ephemeris']]['ephemeris']
                eph=dict(period=b['period'],t0=b['T0_btjd'],duration=duration)
                choices={'reported_C':duration,'accepted_A_duration':ae['duration'],
                    'native_D_seed_duration':fit['ephemeris_start']['duration'],
                    'locked_D_fit_duration':fit['adopted']['t14_hours']/24,
                    'published_truth_duration':float(t['duration_hours'])/24}
                checks={name:dict(duration_seconds=d*86400,
                    event_match=match_signal(tt,t,dict(eph,duration=d)),primary_credit=False)
                    for name,d in choices.items()}
                fit_eph=dict(period=fit['adopted']['period'],t0=fit['adopted']['t0_btjd'],
                    duration=fit['adopted']['t14_hours']/24)
                identities.append(dict(truth_id=s['truth_id'],key=key,tic_id=tic,
                    native_C_decision=c['decision'],primary_termination=s['first_termination'],
                    primary_C_match=s.get('C_match'),same_C_period_and_epoch_duration_checks=checks,
                    existing_locked_D_fit_match=match_signal(tt,t,fit_eph),outcome_locked_utc=lock['utc'],
                    no_scientific_stage_rerun=True,no_primary_score_change=True))
    out=dict(utc=utc(),records=rows,identity_checks=identities,source_sha256=sources,
        script_sha256=sha(Path(__file__)),
        interpretation='Reported-duration sensitivity of event identity after lock. Primary truth, gate decisions and nested scores remain unchanged. No replacement duration rule is calibrated.')
    write(P9/'results/duration_identity_audit.json',out)
    import pandas as pd
    pd.DataFrame(rows).to_csv(P9/'results/C_reported_durations.csv',index=False)
    body=['# P9 reported-duration and event-identity audit','',out['interpretation'],'',
        table(['Candidate','Native C','C duration (s)','C duration / 200 s','Native D seed (s)','D fit (h)'],
            [[r['key'],r['native_C_decision'],r['reported_C_duration_seconds'],r['reported_C_duration_over_nominal_cadence'],r['native_D_seed_duration_seconds'],r['D_fitted_duration_hours']] for r in rows]),'']
    for r in identities:
        body += ['## '+r['truth_id'],'',
            'The primary category `C_signal_switch` means the accepted ephemeris failed the registered identity rule. It does not by itself prove a different physical signal. The following checks keep C period and epoch identical, substitute one recorded duration at a time, and apply the original match function. None earns primary credit.','',
            table(['Duration source','Seconds','Matched events','Truth opportunities','Found opportunities','Identity rule'],
                [[k,v['duration_seconds'],v['event_match']['matched_events'],v['event_match'].get('n_truth_opportunities'),v['event_match'].get('n_found_opportunities'),v['event_match']['matched']] for k,v in r['same_C_period_and_epoch_duration_checks'].items()]),'',
            'The independently saved final fit matches the labelled signal: '+str(r['existing_locked_D_fit_match'])+'. This is an existing-fit association, not repaired nested completeness.','']
    body+=['The frozen native physical-fit adapter already uses the wider of survey and C durations for its fitting window; see `_p8_fit_input` in [audit_p5.py](baseline/source/scripts/audit_p5.py). This is existing production behavior, not a P9 rescue. The upstream cause of the very short C duration was not established. A future duration/identity protocol needs independent positive and negative evaluation; this selected example does not measure its specificity cost.','']
    (P9/'DURATION_AUDIT.md').write_text('\n'.join(body),encoding='utf-8')
    print('C durations audited',len(rows),'sub-cadence',sum(r['sub_cadence_duration'] for r in rows),'identity failures',len(identities),flush=True)
    for r in identities:print(r['truth_id'],r['same_C_period_and_epoch_duration_checks'],flush=True)


if __name__=='__main__':run()
