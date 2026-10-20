"""Render verified numerical estimates without manual transcription."""
from common import *
from scoring import GATES

def percent(v):return 'undefined' if v is None else f'{100*v:.1f}%'
def interval(a):return 'undefined' if a[0] is None else f'{100*a[0]:.1f}–{100*a[1]:.1f}%'
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(str(v) for v in row)+' |' for row in rows])

def gate_table(e):
    rows=[]
    for gate,s in e['gates'].items():
        rows.append([gate,f'{s["k"]}/{s["n"]}',percent(s['rate']),interval(s['wilson95']),interval(s['host_bootstrap95']),
          f'{s["k"]}/{s["conditional_n"]}',percent(s['conditional_rate']),interval(s['conditional_wilson95']),interval(s['conditional_host_bootstrap95'])])
    result=table(['Gate','Unconditional n/N','Observed rate','Wilson 95%','Host bootstrap 95%','Conditional n/N','Observed rate','Wilson 95%','Host bootstrap 95%'],rows)
    if any(s['n_operational_unknown'] for s in e['gates'].values()):
        rows=[[g,s['n_operational_unknown'],interval(s['scientific_rate_bounds']),interval(s['scientific_Wilson95_envelope']),
          interval(s['scientific_host_bootstrap95_envelope']),interval(s['scientific_conditional_rate_bounds'])] for g,s in e['gates'].items()]
        result+='\n\nOperationally unresolved paths are **not scientific rejections**. Logical survival ranges and interval envelopes allow these unknown paths to survive; completed-only results exclude them and describe a potentially selected subset.\n\n'
        result+=table(['Gate','Unknown outcomes','Unconditional logical bounds','Wilson 95% envelope','Host bootstrap 95% envelope','Conditional logical bounds'],rows)
    return result

def run():
    m=read(P9/'results/metrics.json');chunks=['# P9 numerical results','',
      'Signal-level estimates use independently labelled eligible signals. Host resampling keeps all planets on a shared host together and resamples within frozen sampling strata. Intervals describe the selected population; they do not correct its discovery or product-selection bias.',
      '', 'Both final D outcomes use the same Stage C denominator. Useful means SUBMIT-equivalent or a specifically justified useful HOLD. A 0/0 conditional rate is undefined. The degenerate bootstrap interval at zero or one is supplemented by marginal Wilson and exact independent-host bounds; it is not certainty.','']
    names={
      'positive_all':'Confirmed/validated planets: all eligible controls',
      'positive_operational_complete':'Planets: operationally completed signal paths',
      'positive_cool_faint_oversample':'Planets: original cool/faint stellar oversample',
      'positive_strict_P8_targeting':'Planets: strict corrected P8 targeting overlap',
      'positive_strict_P8_actual_products':'Planets: strict P8 targeting and actual product overlap',
      'negative_exact':'Labelled negatives: exact signal match',
      'negative_exact_or_registered_alias':'Labelled negatives: exact or registered alias family',
      'uncertain_descriptive':'Uncertain TOIs: descriptive recovery only'}
    for name,e in m['cohorts'].items():
        chunks += ['## '+names.get(name,name.replace('_',' ')),'',f'{e["n_signals"]} eligible signals on {e["n_hosts"]} independent hosts.','',gate_table(e),'']
        d=e['gates']['D_submit'];u=e['gates']['D_useful']
        chunks += [f'Host-any-survival binomial exact 95% bounds/envelopes: SUBMIT-equivalent {interval(d["host_any_possible_survival_exact95_envelope"])}; useful {interval(u["host_any_possible_survival_exact95_envelope"])}. This uses an independent exchangeable-host model and includes unresolved operational paths. Host-any-survival is a different estimand from per-planet completeness; the host bootstrap separately preserves the sampling strata.','']
        for final,c in e['conditional_product_checks'].items():
            chunks += [f'{final}: product of conditional rates = {c["conditional_product"]}; direct rate = {c["direct_rate"]}. {c["note"]}.','']
    chunks += ['# Positive-control stratification','',
      'Cells are descriptive and often sparse. Table entries are unconditional retained counts. Full per-cell conditional rates and both interval types are in [metrics.json](results/metrics.json). Every row retains measured or missing covariates for failures as well as successes. Depth display cutpoints are exploratory; radius, period and SNR cutpoints were preregistered. Rotation/amplitude estimates are periodic-variability proxies that can include transits and artifacts, not independently established stellar rotation.','']
    for dimension,cells in m['stratification'].items():
        rows=[]
        for label,e in cells.items():rows.append([label,e['n_signals'],e['n_hosts']]+[e['gates'][g]['k'] for g in GATES])
        chunks += ['## '+dimension,'',table(['Cell','Signals','Hosts',*GATES],rows),'']
    chunks += ['# P8 overlap and weighting','',
      'Strict P8 weighting status: '+m['weighting']['status']+'. Required support is at least five independent positive hosts per cell, maximum weight five and effective sample size at least ten. No weights are assigned to unsupported regions; ESS is unavailable, not a fabricated zero-variance estimate.','',
      'The original sampling identifier `p8_proxy` is retained for auditability. Its two-minute-coverage parser was faulty; the corrected inventory shows that it is a cool/faint stellar oversample, not a representative P8 FFI sample.','']
    (P9/'TABLES.md').write_text('\n'.join(chunks),encoding='utf-8')
    print('tables written',len(m['cohorts']),'cohorts',flush=True)

if __name__=='__main__':run()
