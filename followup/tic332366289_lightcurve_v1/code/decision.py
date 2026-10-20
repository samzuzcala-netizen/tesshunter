import common as C
import numpy as np,pandas as pd
from recipe import aggregate
d=C.json.loads((C.WS/'results/depths.json').read_text());j=C.json.loads((C.WS/'results/retained_joint.json').read_text());bp=C.json.loads((C.WS/'results/backprojection.json').read_text());m=C.json.loads((C.WS/'results/map_summary.json').read_text());a=C.json.loads((C.WS/'results/alias_summary.json').read_text());p=C.json.loads((C.WS/'results/pdc_diagnostics.json').read_text());sup=C.json.loads((C.WS/'results/independent_support.json').read_text())
flags=[];depend=[]
for r in p:
    if r['ephemeris']!='EA' or r['sector'] not in [57,79,80] or not r['valid']:continue
    s=r['sector'];sap=next(x for x in d if x['sector']==s and x['photometry']=='SAP' and x['ephemeris']=='EA');pdc=next(x for x in d if x['sector']==s and x['photometry']=='PDCSAP' and x['ephemeris']=='EA')
    if r['snr']>=3:flags.append(f'PDC_DEEPENING_S{s}')
    if r['snr']>=3 and sap['snr']<2 and pdc['snr']>=3:depend.append(s)
refuted=all(bp[k]['backprojected']['shortfall_sigma']>=3 for k in ['EA','EF']) and m['all_map_excludes_reference']
if refuted:status='PERIOD_REFUTED'
elif j['EA']['SAP']['snr']<3 or j['EA']['PIX_OPT']['snr']<3:status='NOT_SUPPORTED'
elif depend:status='PDC_DEPENDENT'
elif len(a['supported_sectors'])<2 or a['n_surviving']>1:status='PERIOD_AMBIGUOUS'
else:status='RAW_SIGNAL_CONSISTENT'
flags+=['S79_RAW_EVENT_UNCONFIRMED','S80_SUGGESTIVE_BELOW_INDEPENDENT_RULE','FOUR_INVENTORY_SECTORS_OFF_SCIENCE_ARRAY','CONDITIONAL_ALIASES_ONLY','EMPIRICAL_TAILS_UNRESOLVED','E39_DIAGNOSTIC_ONLY']
loo={}
for drop in [57,79,80]:
    rr=[{**r,'depth':r['target_depth'],'error':r['target_error']} for r in d if r['sector'] in [57,79,80] and r['sector']!=drop and r['photometry']=='SAP' and r['ephemeris']=='EA' and r['valid']]
    loo[str(drop)]=aggregate(rr)
allraw=aggregate([{**r,'depth':r['target_depth'],'error':r['target_error']} for r in d if r['photometry']=='SAP' and r['ephemeris']=='EA' and r['sector']!=84 and r['valid']])
inj=pd.read_csv(C.WS/'results/injections.csv');summ=[]
for (s,name,amp),g in inj.groupby(['sector','photometry','injected_ppt']):
    e=g.incremental_ppt-amp
    summ.append(dict(sector=s,photometry=name,injected_ppt=amp,n=len(g),mean_incremental_bias=e.mean(),median_incremental_bias=e.median(),incremental_sd=e.std(),absolute_recovery_bias=(g.recovered_ppt-amp).mean(),absolute_recovery_sd=g.recovered_ppt.std(),max_abs_incremental_bias=abs(e).max()))
pd.DataFrame(summ).to_csv(C.WS/'results/injection_summary.csv',index=False)
decision=dict(primary_status=status,flags=flags,independent_raw_events=a['supported_sectors'],n_independent_raw_events=len(a['supported_sectors']),retained_joint=j,all_non_diagnostic_fixed_EA_SAP=allraw,leave_one_out_SAP=loo,pdc_dependency_rule_fired=depend,period_refuted=refuted,conditional_aliases=a['n_surviving'],not_a_planet_probability=True)
C.write(C.WS/'results/decision.json',decision);print(C.json.dumps(C.clean(decision),indent=1))
