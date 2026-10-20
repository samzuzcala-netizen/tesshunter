"""Post-lock interpretation of preserved B flags and catalogue-history effects.

No flag is removed and no alternate pipeline verdict is produced.
"""
from common import *
import argparse
import pandas as pd

def run(partial=False):
    from scoring import verify_lock
    ids=read(P9/'manifests/final_ids.json');truth=pd.read_csv(P9/'truth/final_truth.csv');rows=[];hosts=[]
    for tic in ids:
        if not (P9/'results/locks'/f'tic{tic}.json').exists():
            if partial:continue
            raise RuntimeError('Unsettled host '+str(tic))
        verify_lock(tic);root=P9/'results/blind'/f'tic{tic}';rawpath=P9/'truth/sky_raw/neighbours'/f'tic{tic}.json'
        raw=read(rawpath);vsx=(raw.get('vsx') or {}).get('objects') or []
        vsx_summary=[{k:o.get(k) for k in ['Name','Type','sep_arcsec']} for o in vsx]
        host=dict(tic_id=tic,labels=sorted(set(truth.loc[truth.tic_id==tic,'label'])),VSX=vsx_summary,
          raw_source_sha256=sha(rawpath),execution_sky_sha256=sha(P9/'inputs/neighbours'/f'tic{tic}.json'))
        hosts.append(host)
        for path in (root/'stageB').glob('*.json'):
            b=read(path);nbpath=root/'neighbours'/f'tic{tic}.json';nb=read(nbpath) if nbpath.exists() else {}
            neighbours=(nb.get('gaia') or {}).get('neighbours') or [];depth=b.get('survey_depth_ppt')
            capable=sum((n.get('sep_arcsec') or 0)<=63 and (n.get('max_observed_depth_ppt_total_eclipse') or 0)>=depth for n in neighbours) if depth is not None else None
            examples=(b.get('deep_event_host') or {}).get('examples') or []
            rows.append(dict(tic_id=tic,key=path.stem,labels=';'.join(host['labels']),decision=b.get('decision'),max_verdict=b.get('max_verdict'),
              survey_depth_ppt=depth,n_possible_neighbours_native_host_summary=(b.get('gaia') or {}).get('n_neighbours_could_produce_depth_within_3px'),
              n_possible_neighbours_at_this_depth_diagnostic=capable,n_VSX=len(vsx),VSX_postlock_types=';'.join(str(o.get('Type')) for o in vsx),
              VSX_separations_arcsec=';'.join(str(o.get('sep_arcsec')) for o in vsx),
              flags=b.get('flags'),deep_signal_period_ratios=[q['period_days']/b['survey_period'] for q in examples if q.get('period_days') and b.get('survey_period')],
              interpretation='Diagnostic decomposition only. The native B cap remains unchanged; period ratios alone do not prove duplicate signals.',
              stageB_sha256=sha(path)))
    suffix='_partial' if partial else ''
    write(P9/f'results/catalogue_flag_audit{suffix}.json',dict(utc=utc(),hosts=hosts,signals=rows,script_sha256=sha(Path(__file__)),
      boundary='Raw classification fields opened only for locked hosts; execution received redacted fields and unchanged generic counts/flags.',
      limitation='Catalogue membership and generic variability can depend on discovery history. This is a benchmark-selection issue to audit, not permission to use known labels in vetting.'))
    flat=[{k:(';'.join(v) if k=='flags' and isinstance(v,list) else v) for k,v in r.items() if k!='deep_signal_period_ratios'} for r in rows]
    pd.DataFrame(flat).to_csv(P9/f'results/catalogue_flag_audit{suffix}.csv',index=False)
    print('catalogue flag audit',len(hosts),'locked hosts',len(rows),'B records',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');a=p.parse_args();run(a.partial)
