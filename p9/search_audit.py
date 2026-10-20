"""Post-lock census of local search competition for missed positive signals.

Uses recorded decisions only. Near periods are diagnostic, not newly credited
recoveries or proof of correct global ephemerides. No counterfactual search runs.
"""
from common import *
import argparse,re
import pandas as pd
from scoring import verify_lock
from tables import table


def run(partial=False):
    suffix='_partial' if partial else ''
    scores=read(P9/f'results/scored_signals{suffix}.json')
    truth=pd.read_csv(P9/'truth/final_truth.csv').set_index('truth_id');rows=[]
    for s in scores:
        if s['label']!='positive' or s['first_termination']!='search':continue
        tic=int(s['tic_id']);verify_lock(tic);period=float(truth.loc[s['truth_id'],'period'])
        op=read(P9/'results/operations'/f'search_tic{tic}.json');lp=P9/op['attempts'][-1]['log']
        passes={};chunk='unassigned';iteration=0
        for num,line in enumerate(lp.read_text(encoding='utf-8',errors='replace').splitlines(),1):
            m=re.search(r'search_light_curve: TIC \d+ (chunk\d+|stitch)',line)
            if m:chunk=m.group(1);iteration=0
            m=re.search(r'Detection pass (\d+) \(planet (\d+)\)',line)
            if m:
                iteration=int(m.group(1));passes[(chunk,iteration)]=dict(search=chunk,iteration=iteration,
                  requested_planet_number=int(m.group(2)),near_trials=[],chosen=None)
            rec=passes.get((chunk,iteration))
            if rec is None:continue
            m=re.search(r'\[([\d.]+) d -> ([\d.]+) d\]\s+(.*)',line)
            if m:
                raw,resolved=float(m.group(1)),float(m.group(2));nearraw=abs(raw/period-1)<=.01;nearresolved=abs(resolved/period-1)<=.01
                if nearraw or nearresolved:
                    tail=m.group(3);comp=re.search(r'composite ([\d.]+)',tail);snr=re.search(r'SNR ([\d.]+)',tail)
                    rec['near_trials'].append(dict(log_line=num,raw_period=raw,resolved_period=resolved,
                      resolved_near_truth=nearresolved,internal_gates_passed=tail.rstrip().endswith('PASS'),
                      composite=float(comp.group(1)) if comp else None,snr=float(snr.group(1)) if snr else None,recorded_message=tail))
            m=re.search(r'Accepted planet (\d+): \[([^]]*)\]\s+P = ([\d.]+) d.*composite ([\d.]+)',line)
            if m:rec['chosen']=dict(log_line=num,planet_num=int(m.group(1)),harmonic=m.group(2),period=float(m.group(3)),composite=float(m.group(4)))
        informative=[];witnesses=[]
        for rec in passes.values():
            if not rec['near_trials']:continue
            informative.append(rec)
            passing=[t for t in rec['near_trials'] if t['resolved_near_truth'] and t['internal_gates_passed']]
            chosen=rec['chosen']
            if passing and chosen and abs(chosen['period']/period-1)>.01:
                witnesses.append(dict(search=rec['search'],iteration=rec['iteration'],
                  near_period_passes=passing,chosen=chosen,
                  interpretation='Recorded local near-period survivors lost the composite selection. Period proximity alone does not establish global truth recovery.'))
        rows.append(dict(truth_id=s['truth_id'],tic_id=tic,published_period=period,
          native_budget_stop=s.get('search_budget_stop',False),n_detection_passes=len(passes),
          n_near_period_trial_messages=sum(len(p['near_trials']) for p in informative),
          n_competition_witnesses=len(witnesses),competition_witnesses=witnesses,informative_passes=informative,
          source_log=str(lp.relative_to(P9)),source_log_sha256=sha(lp)))
    out=dict(utc=utc(),partial=partial,records=rows,script_sha256=sha(Path(__file__)),
      frozen_selection_source_sha256=sha(BASE/'src/tesshunter/pipeline.py'),
      scope='Post-lock recorded local selection, not alternative recovery scoring, a rescued signal or a measured variant benefit')
    write(P9/f'results/search_trial_audit{suffix}.json',out)
    text=['# P9 search-selection autopsy supplement','',out['scope']+'.','',
      'The frozen pipeline selects the highest composite score from internal gate survivors and stops each partition at its configured accepted-candidate limit. A local near-period BLS solution need not have a globally correct ephemeris. Logged wall-budget stops, candidate-limit stops, alias decisions and ranking are different mechanisms.','',
      table(['Missed positive','Near-period log messages','Local selection losses','Recorded wall stop'],
        [[r['truth_id'],r['n_near_period_trial_messages'],r['n_competition_witnesses'],r['native_budget_stop']] for r in rows]),'']
    for r in rows:
        if not r['competition_witnesses']:continue
        text += ['## '+r['truth_id'],'',f'[Frozen search log]({r["source_log"].replace(chr(92),"/")}); SHA256 `{r["source_log_sha256"]}`.','']
        for w in r['competition_witnesses']:
            t=max(w['near_period_passes'],key=lambda v:v['composite'] or 0);c=w['chosen']
            text += [f'- {w["search"]}, pass {w["iteration"]}: a near-period {t["resolved_period"]:.4f} d solution passed at SNR {t["snr"]}, composite {t["composite"]} (log line {t["log_line"]}); the chosen {c["period"]:.6f} d candidate had composite {c["composite"]} (line {c["log_line"]}).']
        text += ['','These choices are measured. The benefit and negative-control cost of changing them are unmeasured; no extra accepted slot or alternative ranking was run.','']
    (P9/('SEARCH_AUDIT_PARTIAL.md' if partial else 'SEARCH_AUDIT.md')).write_text('\n'.join(text),encoding='utf-8')
    print('Search audit',len(rows),'misses;',sum(bool(r['competition_witnesses']) for r in rows),'with local ranking witnesses',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');a=p.parse_args();run(a.partial)
