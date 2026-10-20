"""Render the fixed P10.3 measurements, without fitting or rerunning searches."""
from common import REPO,ROOT,DATA,read,write,sha,utc,environment
environment()
import csv,json,math,time
from collections import Counter,defaultdict
from full_funnel_plan import charge
from retention_analysis_v1 import HostStatistics,search_state
from cluster_bootstrap_v1 import host_weights

PRESETS=('survey_p10','survey_p8')
STRATA=('INDEPENDENT','OVERLAPPING','UNION')
UNITS=('families','raw_rows')
STAGES=('search','pre_gate','A','S','B','C')
ANALYSIS=read(ROOT/'results/retention_analysis.json')
OBS=read(ROOT/'results/retention_observations.json')['observations']
LOSSES=read(ROOT/'results/funnel_loss_attributions.json')['losses']

def num(x,digits=4):
    return 'unmeasured' if x is None else f'{x:.{digits}g}' if isinstance(x,(float,int)) else str(x)

def fraction(r,rate=False):
    if r['fraction'] is None:return f"{r['numerator']}/{r['denominator']}; unmeasured"
    scale=1 if rate else 100
    unit='' if rate else '%'
    ci=r['ci95'];valid=r['bootstrap_valid_draws']
    tail=f'; valid {valid}' if valid!=10000 else ''
    return f"{r['numerator']}/{r['denominator']}; {r['fraction']*scale:.3f}{unit} [{ci[0]*scale:.3f}, {ci[1]*scale:.3f}]{tail}"

def delta(r):
    if r['difference'] is None:return 'unmeasured'
    return f"{r['difference']*100:+.3f} pp [{r['ci95'][0]*100:+.3f}, {r['ci95'][1]*100:+.3f}]; valid {r['bootstrap_valid_draws']}"

def table(headers,rows):
    def cell(value):return str(value).replace('|','\\|').replace('\n','; ')
    return '\n'+'| '+' | '.join(headers)+' |\n|'+'|'.join('---' for _ in headers)+'|\n'+''.join('| '+' | '.join(cell(c) for c in row)+' |\n' for row in rows)+'\n'

def md(name,parts):
    path=ROOT/name
    assert not (ROOT/'manifests/final_delivery_seal.json').exists(), 'Final delivery already sealed'
    path.write_text('\n\n'.join(parts).rstrip()+'\n',encoding='utf-8')

def overall_search(unit='families',stratum='UNION',preset='survey_p10'):
    return next(r for r in ANALYSIS['search_tables'] if r['unit']==unit and r['stratum']==stratum and r['preset']==preset and r['dimension']=='all')

def overall_funnel(unit='families',stratum='UNION'):
    return next(r['stages'] for r in ANALYSIS['funnel_tables'] if r['unit']==unit and r['stratum']==stratum and r['dimension']=='all')

ASSUMPTIONS='''## Assumptions and evidence limits

[A] The effective preregistration, its D1–D4 amendment chain, the all_eligible allocation, and the user's prospective supervision amendment govern. Part F's computational conventions were committed before ephemeris exposure. The analysis and autopsy source registrations identify later deterministic reporting code; they do not redefine those rules.

[A] Families use the registered one-percent within-host deduplication, with a deterministic canonical forced fit and a highest-model-SNR representative within each stratum for binning. A family can occur in both strata; union families are deduplicated again. Raw rows preserve run duplicates and share their family's presence classification. Stratum totals therefore cannot simply be added for families.

[A] A recovery may use an exact period or the registered 2, 3, 1/2 or 1/3 aliases, with the conditional epoch check. Exact recovery is kept separate from alias-only recovery. The forced box depth threshold is three conditional standard errors; best-phase fitting when epoch is uncheckable includes a phase search. These errors are not a global false-alarm calibration and do not account for all correlated variability.

[A] Every displayed measured fraction has a 95% percentile interval from 10,000 paired whole-host PCG64 resamples, seed 2026091401. The same 436-host resamples are used across real-data presets and stages. Zero-denominator bootstrap draws are omitted and their valid count is disclosed. Counts alone are censuses, not binomial confidence claims. A degenerate [100,100] empirical bootstrap interval is not a guarantee of perfect population retention.

[I] These are periodic-signal retention measurements, including binaries and systematics. Expected SNR uses catalogue depth/duration and measured later-data scatter, so a large value need not describe a transit in the later data. No endpoint precision, planet yield, or discovery claim follows. Outside-domain and input-ineligible cases are never misses. Operational unknowns and C cases not run are never recoded as scientific failures. [M] All original 531 stars are development-exposed from Part F and cannot be a holdout.'''

def supplementary():
    path=ROOT/'results/final_supplementary_censuses.json'
    if path.exists():return read(path)
    assert not (ROOT/'manifests/controller_owner.json').exists()
    started,timer=utc(),time.perf_counter()
    try:
        hosts=read(ROOT/'manifests/allocation.json')['selected_tic_ids']
        stats=HostStatistics(hosts,host_weights(len(hosts)))
        census={}
        for preset in PRESETS:
            prediction=read(ROOT/f'manifests/predictions_{preset}.json')
            records=[];partition_hosts=[];exhausted_partition_hosts=[];exhausted_hosts=[]
            for h in prediction['hosts']:
                source=REPO/h['result_path'];assert sha(source)==h['result_sha256']
                searches=read(source)['searches']
                flags=[dict(partition=s.get('partition'),path=f'/searches/{i}/budget_exhausted',budget_exhausted=s.get('budget_exhausted')) for i,s in enumerate(searches)]
                assert all(isinstance(f['budget_exhausted'],bool) for f in flags)
                partition_hosts.extend([h['tic_id']]*len(flags))
                exhausted_partition_hosts.extend([h['tic_id']]*sum(f['budget_exhausted'] for f in flags))
                if any(f['budget_exhausted'] for f in flags):exhausted_hosts.append(h['tic_id'])
                records.append(dict(tic_id=h['tic_id'],flags=flags,source=h['result_path'],sha256=h['result_sha256']))
            census[preset]=dict(hosts=stats.ratio(exhausted_hosts,hosts),partitions=stats.ratio(exhausted_partition_hosts,partition_hosts),records=records)
        qualifying=[r for r in OBS['families']['INDEPENDENT'] if r['likely_periodic'] and r['in_band'] and r['presence']=='PRESENT']
        h_summary={p:stats.ratio([r['tic_id'] for r in qualifying if search_state(r['presets'][p])=='PASS'],[r['tic_id'] for r in qualifying]) for p in PRESETS}
        forced_unknown=[dict(family_id=r['family_id'],tic_id=r['tic_id'],in_band=r['in_band'],period_days=r['period']) for r in OBS['families']['UNION'] if r['presence']=='OPERATIONAL_UNKNOWN']
        result=dict(utc=utc(),purpose='Descriptive final-report censuses; primary measurements unchanged',budget_flags=census,
            H_qualifying_recovery=h_summary,H_expected_snr_range=[min(r['expected_snr'] for r in qualifying),max(r['expected_snr'] for r in qualifying)],
            forced_unknown=forced_unknown,bootstrap=ANALYSIS['bootstrap'],analysis_sha256=sha(ROOT/'results/retention_analysis.json'))
        write(path,result)
    finally:charge(started,timer,'F_H_final_descriptive_censuses')
    return result

def search_report(supp):
    parts=['# P10.3 search retention',
    '[M] Both presets evaluated all 436 eligible stars, reusing the same six timing-pilot hosts. The original list has 531 stars; 58 fail the Gaia input cut and a further 37 fail verified usable coverage. All 473 Gaia-passing stars pass the corrected FFI-majority cut. The 95 exclusions remain INPUT_INELIGIBLE.',
    '[M] There are 2,363 evaluated raw TCE rows and 1,449 ephemeris families. Of these, 503 families are in the search period domain; 432 have a present forced-fit signal and 71 are absent. The 946 outside-domain families are separately accounted for. There are 24 forced-fit operational unknowns, all outside the search period domain; neither preset has a search operational unknown.',
    '## Main measured comparison',
    table(['Stratum','Preset','Present-signal recovery; 95% CI','All in-band recovery; 95% CI','Exact / alias-only counts'],
          [[s,p,fraction(overall_search(stratum=s,preset=p)['recovery_present']),fraction(overall_search(stratum=s,preset=p)['recovery']),f"{overall_search(stratum=s,preset=p)['n_exact']} / {overall_search(stratum=s,preset=p)['n_alias_only']}"] for s in STRATA for p in PRESETS]),
    '[I] The independent stratum is the prior-epoch comparison. OVERLAPPING is same-epoch, different-pipeline/cadence evidence. P10 performs better than P8 in this paired sample; the result does not establish planet completeness.',
    table(['Unit','Stratum','Paired present cases','P10 minus P8; 95% CI'],[[r['unit'],r['stratum'],r['n_paired'],delta(r)] for r in ANALYSIS['paired_present_recovery_differences'] if r['dimension']=='all']),
    '## Method, locks and missing measurements',
    '[A] Accepted periods match within 1% of 1, 2, 3, 1/2 or 1/3 times the TCE period. The propagated epoch is tested only if sigma_P × N_cycles < T14/2 at the prepared-data midpoint. Otherwise the receipt explicitly says period-only. Expected SNR = (catalogue depth / measured native sigma) × sqrt(n_cad × T14/P), using consistent units. Forced fits cover every family, including outside-domain families; fixed epoch is used when checkable and best phase otherwise, with a one-cadence duration floor.',
    '[M] `results/matching.json` and `results/forced_fits.json` hold the complete row/family evidence. The unmeasured forced cases have no measured in- or out-of-transit level. Their errors remain unknown, rather than absent. CPython opened-file guards and final worker logs show no sidecar access during either blind search; this is application-level instrumentation, not an operating-system-wide I/O audit.',
    table(['Preset','Hosts','Accepted candidates','Prediction manifest SHA256'],[[p,436,read(ROOT/f'manifests/predictions_{p}.json')['n_accepted'],sha(ROOT/f'manifests/predictions_{p}.json')] for p in PRESETS]),
    '## Detector-budget census',
    '[M] A detector-budget flag can accompany a successful worker result. It records truncation of that partition, not an operational timeout. This census reads all partitions, including partitions with no accepted candidate.',
    table(['Preset','Hosts with any exhausted partition; 95% CI','Exhausted partitions; 95% CI'],[[p,fraction(supp['budget_flags'][p]['hosts']),fraction(supp['budget_flags'][p]['partitions'])] for p in PRESETS]),
    'The per-host/partition flags and source hashes are in `results/final_supplementary_censuses.json`.',
    '## Full registered tables',
    '[M] The following tables cover both counting units, all strata, both presets and every populated registered bin. Recovery denominators exclude outside-domain cases. The 2×2 cells divide by all in-band cases with known search and presence status; the separate present/absent columns instead divide by their own presence class. “Not recovered” includes absence until the 2×2 separates it and must not be called a retention loss. The `<0.5` and `>30` period rows show outside-domain accounting. No data fell in a missing-value bin.']
    orders={'all':['ALL'],'expected_snr':['[0,7)','[7,10)','[10,15)','[15,20)','[20,30)','>=30'],
            'model_snr':['<9','[9,12)','[12,20)','>=20'],'period':['<0.5','[0.5,1)','[1,2)','[2,5)','[5,10)','[10,20)','[20,30]','>30']}
    for unit in UNITS:
        for stratum in STRATA:
            for dimension,order in orders.items():
                rows=[r for r in ANALYSIS['search_tables'] if r['unit']==unit and r['stratum']==stratum and r['dimension']==dimension]
                rows.sort(key=lambda r:(order.index(r['bin']),PRESETS.index(r['preset'])))
                parts.append(f'### {unit} · {stratum} · {dimension}')
                parts.append(table(['Bin','Preset','Total','Hosts','In band','Outside','Exact','Alias only','Not recovered','Search unknown','Forced unknown (in band)'],
                    [[r['bin'],r['preset'],*[r[k] for k in ('n_total','n_hosts','n_in_band','n_outside','n_exact','n_alias_only','n_not_recovered','search_unknown','forced_unknown')]] for r in rows]))
                parts.append(table(['Bin','Preset','Recovery; 95% CI','Exact recovery; 95% CI','Present recovery; 95% CI','Absent recovery; 95% CI'],
                    [[r['bin'],r['preset'],*[fraction(r[k]) for k in ('recovery','exact_recovery','recovery_present','recovery_absent')]] for r in rows]))
                parts.append(table(['Bin','Preset','Present + recovered','Present + not recovered','Absent + recovered','Absent + not recovered'],
                    [[r['bin'],r['preset'],*[fraction(r['matrix'][k]) for k in ('PRESENT_RECOVERED','PRESENT_NOT_RECOVERED','ABSENT_RECOVERED','ABSENT_NOT_RECOVERED')]] for r in rows]))
    parts.extend(['## Full paired differences',table(['Unit','Stratum','Dimension','Bin','Paired present cases','P10 minus P8; 95% CI'],
        [[r['unit'],r['stratum'],r['dimension'],r['bin'],r['n_paired'],delta(r)] for r in ANALYSIS['paired_present_recovery_differences']]),ASSUMPTIONS])
    md('SEARCH_RETENTION_P10_3.md',parts)

def loss_text(r):
    values=[]
    for e in r['evidence']:
        fields=[e['candidate_id']]
        if e.get('failed_criteria'):fields.append(', '.join(e['failed_criteria']))
        if e.get('reason'):fields.append(str(e['reason']))
        if e.get('gate_mode'):fields.append('mode='+e['gate_mode'])
        if e.get('chosen_ephemeris'):fields.append('ephemeris='+str(e['chosen_ephemeris']))
        values.append(': '.join(fields))
    return '; '.join(values)

def funnel_rows(stages):
    return [[stage,r['n_at_risk'],r['n_pass'],r['n_fail'],r['n_unknown'],r['n_not_run'],r['conditional_unknown'],fraction(r['conditional']),fraction(r['cumulative'])] for stage,r in stages.items()]

FUNNEL_HEADERS=['Stage','At risk','Pass','New known fail','Cumulative unknown','C not run','Unknown/not run at risk','Conditional retention; 95% CI','Cumulative retention; 95% CI']

def funnel_report():
    selection=read(ROOT/'manifests/stage_C_selection_v1.json')
    cs=read(ROOT/'results/stage_C_summary.json')['candidates']
    matching=read(ROOT/'results/matching.json');raw={r['row_id']:r['raw'] for r in matching['rows']}
    parts=['# P10.3 funnel retention',
    '[M] All 4,328 accepted survey_p10 candidates entered collection. The pre-gate carried 1,104; Stage A passed 293 with two operational timeouts; the bound secondary gate carried 29; all 29 passed B. Six candidates qualified for C and all six were run: five passed and one failed. This is the frozen p10.0 route through `p10/protocol/p10_funnel_calibration.py`, using the isolated Part 3 worker adapter and output roots. `early_funnel_closed_evidence_seal.json` and `stage_C_method_registration_v1.json` pin the route and source hashes.',
    '[M] Counting distinct in-band forced-present families, the union sequence is 174 recovered → 131 pre-gate → 37 A → 13 S → 13 B. Two families remain unknown from A. At C, eight families have a passing route, one a failing route, four were not run, and the two A unknowns remain unknown. One accepted candidate can be associated with several different TCE families through the allowed aliases, so candidate and family counts differ.',
    '## Main sequential measurement: union families',table(FUNNEL_HEADERS,funnel_rows(overall_funnel())),
    '[A] Conditional denominators are previous-stage passers with a known current outcome. Cumulative denominators include known earlier failures but exclude unresolved unknowns and C not-run cases. “New known fail” counts failures among current at-risk cases; it is not the total accumulated failure count. A family passes if at least one matching candidate passes the full route; unknown alternate routes cannot turn a known pass into a failure. S HOLD is carried. These are periodic-signal rejections, not established planet losses.',
    '## Natural candidate load on all 436 hosts',
    table(['Stage','Passing candidates','Attempted/considered','Operational unknowns','Candidates per host; 95% CI','P10 control reference per host [P10]'],
          [[r['stage'],r['passing_count'],r['attempted'],r['operational_unknowns'],fraction(r['per_star'],rate=True),{'accepted':'11.65','pre_gate':'2.36','A':'0.150','S':'0.0067'}.get(r['stage'],'unmeasured')] for r in ANALYSIS['natural_load']]),
    '[P10] The four reference values are the registered rounded historic natural-control rates, not new measurements. [I] This brighter, longer-baseline, bare-TCE population has a larger surviving A/S load than that control population. The present experiment did not measure the specificity of those survivors.',
    '## Stage C allocation and complete disposition',
    '[M] At B closure the ledger had 18.105466884 new queue-hours remaining. The prospectively authorized formula gave N_C = floor((18.105466884 − 3.0) × 3 / 3.4) = 13. This computation was recorded before the first C launch, with a three-hour reserve and at most three concurrent runs. Six candidates met the TCE-match/likely-periodic/B-pass selection; no qualifying candidate was excluded by the cap. Eighteen B survivors were unmatched; five matched survivors had no qualifying in-band likely-periodic row. Forced presence was not a selection cut.',
    '[M] The fixed cap receipt is `manifests/C_cap_at_B_closure.json`. The original B-closure ledger bytes were reconstructed from preserved accounting and verified against the cap receipt hash; `manifests/B_ledger_snapshot_provenance.json` discloses that reconstruction. The cap was not recomputed using a later ledger.',
    table(['Rank','Candidate','Selection expected SNR','C decision','Strongest period (d)','SDE','Stage record'],
          [[r['rank'],r['candidate_id'],num(r['ranking_expected_snr']),cs[r['candidate_id']]['decision'],num(cs[r['candidate_id']]['measurement']['blind']['period']),num(cs[r['candidate_id']]['measurement']['blind']['SDE']),cs[r['candidate_id']]['receipt_path']] for r in selection['selected']]),
    '[M] The C failure is tic282923395_p02: the strongest period is approximately 1.758599 d versus the survey period 0.880514 d, a 2:1 alias; SDE 6.16597 is below the fixed threshold 9. The conditional robust fallback did not trigger. There were no C timeouts or rule changes.',
    table(['B-passing candidate not run in C','Reason','B stage record'],[[r['candidate_id'],r['reason'],f"p10/part3/results/funnel/B/{r['candidate_id']}.json"] for r in selection['excluded']]),
    '### Carried associations, without endpoint promotion']
    for r in selection['selected']:
        cid=r['candidate_id']
        if cs[cid]['decision']!='PASS':continue
        byfamily={}
        for q in sorted(r['qualifying_rows'],key=lambda q:-(q['expected_snr'] or 0)):
            byfamily.setdefault(q['family_id'],q)
        assoc=[]
        for q in byfamily.values():
            t=raw[q['row_id']]
            assoc.append(f"F7 association: SPOC TCE {t['sectors']} pn {t['tce_plnt_num']} at P = {t['tce_period']} d ({q['family_id']}; {q['alias']}; not promoted)")
        parts.append(f"[M] **{cid}**: carried, unverdicted. "+'; '.join(assoc)+'. All row associations are retained in the selection manifest.')
    parts.extend(['## Full sequential tables by unit, stratum and expected SNR'])
    order=['ALL','[0,7)','[7,10)','[10,15)','[15,20)','[20,30)','>=30']
    for unit in UNITS:
        for stratum in STRATA:
            rows=[r for r in ANALYSIS['funnel_tables'] if r['unit']==unit and r['stratum']==stratum]
            rows.sort(key=lambda r:order.index(r['bin']))
            for r in rows:
                parts.extend([f"### {unit} · {stratum} · expected SNR {r['bin']}",table(FUNNEL_HEADERS,funnel_rows(r['stages']))])
    parts.extend(['## Historic injection comparison at the same expected-SNR bins',
        '[M, P10] The sealed P10 2,100-injection outcome table on 300 hosts was rebinned, without rerunning injections, into the registered P10.3 expected-SNR bins. The table below places its cumulative retention alongside the measured present-signal family retention for each stratum. Each fraction has its own whole-host bootstrap interval; the historical hosts form a separate bootstrap. This is a descriptive comparison, not a paired treatment estimate across the two populations.',
        '[I] Injections are planets by construction and the historic recovered flag credits exact-period recovery. Real TCEs include binaries/systematics and the registered alias recoveries. The box-based presence diagnostic and catalogue-based expected SNR also differ from injection truth. These differences prevent a direct planet-completeness interpretation. B/C and endpoint specificity have no corresponding calibration here.'])
    inj=ANALYSIS['injection_comparison']
    for label in order:
        rows=[]
        for stage in STAGES[:4]:
            h=next((r for r in inj['tables'] if r['bin']==label and r['stage']==stage),None)
            if h is None:continue
            vals=[]
            for stratum in STRATA:
                group=next((r for r in ANALYSIS['funnel_tables'] if r['unit']=='families' and r['stratum']==stratum and r['bin']==label),None)
                vals.append(fraction(group['stages'][stage]['cumulative']) if group else 'no observations')
            rows.append([stage,fraction(h['retention']),*vals])
        parts.extend([f'### Expected SNR {label}',table(['Stage','Historic injection cumulative; 95% CI','INDEPENDENT present-family cumulative','OVERLAPPING present-family cumulative','UNION present-family cumulative'],rows)])
    parts.extend(['## Measured loss attribution',
        '[M] In the union, the new family rejections are 43 at pre-gate, 92 at A, 24 at S and one at C. B removes none. Two A timeouts are excluded from these counts. A criteria below are those on the recorded chosen ephemeris; several criteria can fail for one family and one family can have several candidate routes. S uses the bound mode. The lists are diagnostic attributions, not mutually exclusive causal effects.'])
    aggregated=Counter()
    for r in LOSSES:
        if r['unit']!='families':continue
        tags=set()
        for e in r['evidence']:
            tags.update(e.get('failed_criteria',[]))
            if e.get('reason') and r['removed_at'] not in ('A','pre_gate'):
                tags.add(str(e['reason']).split(':',1)[0] if r['removed_at']=='S' else str(e['reason']))
        for tag in tags:aggregated[(r['stratum'],r['removed_at'],tag)]+=1
    parts.append(table(['Stratum','Removed at','Recorded criterion/reason','Affected families (nonexclusive)'],[[*key,n] for key,n in sorted(aggregated.items())]))
    parts.append('### Complete per-loss record index')
    parts.append(table(['Unit','Stratum','Expected SNR bin','Observation','Removed at','Candidate criteria / S mode / reason'],
        [[r['unit'],r['stratum'],r['expected_snr_bin'],r['observation_id'],r['removed_at'],loss_text(r)] for r in LOSSES]))
    parts.extend(['[M] Exact structured evidence is in `results/funnel_loss_attributions.json`, with stage receipts under `results/funnel/{A,S,B,C}/`. The two timeout receipts are tic177352028_p01 and tic33866201_p01. No retries were used to obtain a scientific result.',ASSUMPTIONS])
    md('FUNNEL_RETENTION_P10_3.md',parts)

def costed_next_step():
    ledger=read(ROOT/'manifests/resource_ledger.json');phases={r['phase']:r['hours'] for r in ledger['intervals']}
    paired_pilot=phases['timing_pilot_search']
    result=dict(utc=utc(),iteration_executed=False,authorization='User explicitly limited Part H to costing; no p10.1 execution',
        proposed_scope='One prospectively registered selection/ranking variant, motivated by four local ranking witnesses; exact policy requires design before any new measurement',
        historical_subset_hours=13.75,margin=1.25,remaining_hours=ledger['new_queue_hours_cap']-ledger['new_queue_hours'],
        full_2100_remeasurement_cost='Not newly measured; 13.75 h is the registered 600-injection plus 300-control planning benchmark, not a guarantee for an expanded full revalidation',
        presets={})
    for p in PRESETS:
        rerun=phases['search_'+p]+paired_pilot
        cost=(13.75+rerun)*1.25
        result['presets'][p]=dict(measured_430_host_phase_hours=phases['search_'+p],six_host_conservative_proxy_hours=paired_pilot,
             full_436_host_planning_rerun_hours=rerun,total_with_margin_hours=cost,fits_remaining=cost<=result['remaining_hours'])
    result['proxy_note']='The six-host timing ledger combines both presets. Charging its entire union interval to each individual changed preset is a conservative planning proxy, not a measured per-preset pilot duration or a tail guarantee.'
    write(ROOT/'results/p10_1_costed_next_step.json',result,replace=True)
    return result

def calibration_report(supp,cost):
    H=ANALYSIS['calibration']
    parts=['# P10.3 calibration check',
    '**Registered outcome: RETENTION_MEASURED_CALIBRATION_OPTIMISTIC.** [M] Both Part H point-value rules fire on 89 qualifying independent, likely-periodic, in-band, forced-present families on 74 hosts. All 89 have measured outcomes in both presets; the minimum of 40 is met.',
    '**[I] Neither fitted SNR50 is a usable sensitivity threshold.** Both fitted slopes are negative, and the crossings are extreme extrapolations with unstable bootstrap intervals. The literal registered trigger is retained, but these fits do not support a stable increasing recovery-versus-SNR calibration or a quantitative factor by which injection sensitivity is optimistic.',
    '## Registered calculation',
    '[A] The unpenalized model is logit(p_recovered) = a + b × ln(expected SNR), with SNR50 = exp(−a/b). The rule compares that point crossing against 1.3 times the preset-specific search-only injection SNR50. Likely-periodic means model SNR ≥12 and at least three DV-run transits. The subset is INDEPENDENT, in 0.5–30 d, and forced-present. Slope constraints or a changed model were not introduced after viewing outcomes.',
    table(['Preset','N / hosts','Recovered qualifying families; 95% CI','a','b','SNR50 point','95% finite-bootstrap interval','Injection SNR50 [P10]','Threshold','Rule'],
      [[p,f"{H[p]['n_fitted']} / {H[p]['n_hosts']}",fraction(supp['H_qualifying_recovery'][p]),num(H[p]['fit']['a'],8),num(H[p]['fit']['b'],8),num(H[p]['fit']['snr50'],8),f"[{num(H[p]['bootstrap_ci95'][0],8)}, {num(H[p]['bootstrap_ci95'][1],8)}]",H[p]['injection_snr50'],num(H[p]['threshold']),H[p]['rule']] for p in PRESETS]),
    table(['Preset','Attempted draws','Finite crossing draws','Nonfinite crossing draws','Negative-slope finite draws','Positive-slope finite draws'],
      [[p,10000,H[p]['bootstrap_valid'],H[p]['bootstrap_failures'].get('NONFINITE_SNR50_CROSSING',0),H[p]['bootstrap_slope_signs'].get('False',0),H[p]['bootstrap_slope_signs'].get('True',0)] for p in PRESETS]),
    f"[M] Expected SNR in the fitted subset ranges from {num(supp['H_expected_snr_range'][0],8)} to {num(supp['H_expected_snr_range'][1],8)}. Both point crossings lie beyond the measured range. The numerical fit status `IDENTIFIED` records convergence and a finite algebraic crossing; it does not establish a physically identifiable sensitivity threshold. The reported percentile intervals condition on finite crossings. Near-zero bootstrap slopes can produce extreme tails, and the P8 point lies outside its percentile interval; this is another sign of instability.",
    '## Five required autopsies',
    '[M] The five highest expected-SNR independent likely-periodic forced-present misses were selected from the union of the two triggered presets; all five miss in both. Their original searches and primary Part F fits remain unchanged. `AUTOPSIES_P10_3.md` gives the event-removal census, conditional epoch/alias checks, trace and log ranking witnesses, detector-budget flags, and diagnostic plots for each.',
    '[M] Four have a recorded P10 local period-compatible internal-gate survivor that lost selection to a different period. Three nominal TCE durations exceed the frozen 4.8-hour search maximum. Four nominal epochs are uncheckable. All five have counterfactual nominal-ephemeris depth ratios below 0.5 or unmeasured; only one has a recorded detector-budget exhaustion, in P8.',
    '[I] Local selection competition is a shared contributor in at least three cases, satisfying the evidence-count basis for costing one bounded ranking experiment. It is not proof that an alternative would produce an accepted globally matching ephemeris. The counterfactual event diagnostics are not actual Stage A losses: all five first terminate at search matching. Variability, broad nominal durations and epoch uncertainty limit causal attribution.',
    '## Costed next step; no iteration executed',
    '[A] The user explicitly directed that p10.1 be costed only. A future experiment would prospectively fix one ranking/selection variant, remeasure the required injection and control evidence, assess specificity and resource load, freeze the chosen preset, and rerun its paired Part E measurement. No policy was chosen from a measured variant and no variant was tested here.',
    table(['Changed preset','Measured 430-host phase (h)','Six-host conservative proxy (h)','Full 436-host rerun planning value (h)','(13.75 + rerun) × 1.25 (h)','Fits current remainder'],
      [[p,*[num(cost['presets'][p][k],8) for k in ('measured_430_host_phase_hours','six_host_conservative_proxy_hours','full_436_host_planning_rerun_hours','total_with_margin_hours')],cost['presets'][p]['fits_remaining']] for p in PRESETS]),
    f"[M, A] Remaining scientific allocation at costing: {cost['remaining_hours']:.6f} h. {cost['proxy_note']} The 13.75 h [P10] is the stipulated 600-injection plus 300-control benchmark. Full 2,100-injection remeasurement remains part of the registered iteration scope; its additional cost is not newly measured here. Even the stipulated subset-based planning test exceeds the remaining budget for either preset.",
    '[I] A future Part 5 also needs independent B/C and endpoint specificity evidence, Stage D and endpoint review, resource forecasting using the observed natural load, and explicit authorization. This development-exposed TCE set cannot serve as its holdout.',ASSUMPTIONS]
    md('CALIBRATION_CHECK_P10_3.md',parts)

AUTOPSY_INTERPRETATIONS={
353898013:'[M] The nominal TCE duration exceeds the search duration ceiling. Period-compatible BLS trials exist, but no saved log witness establishes a period-compatible internal-gate survivor losing final selection. The prepared light curve has a strong short-period rotation proxy. [I] Broad nominal duration, variability and uncertain phase are plausible contributors; no single causal mechanism is established for this case.',
29002055:'[M] P10 recorded a local 2.8856-day (1:3) internal-gate passer at composite 19.46, while that pass selected 1.926697 d at composite 42.97. There are seven kept nominal event opportunities, but none has a finite detrended depth measurement. The nominal duration is 24.2536 hours. [I] Ranking competition and the mismatch between the broad nominal box and the search duration range both matter diagnostically; a globally matching alternative recovery has not been measured.',
314825931:'[M] A P10 local 16.7679-day (3:1) internal-gate passer at composite 12.87 lost to 28.567457 d at composite 24.8. The P8 chunk1 search exhausted its detector budget. The nominal-event kept depth is negative and inconsistent. [I] This supports a local ranking-loss witness, while phase uncertainty and structured variability prevent interpreting the nominal-event audit as proof of a missed stable transit.',
150066550:'[M] P10 local allowed-alias candidates lost to a 1.194001-day (1:5, outside the allowed alias set) winner. An accepted P10 candidate is period-compatible at 2:1 but fails the registered epoch test: phase distance 0.748600251 d exceeds T14/2 = 0.332508333 d, with accumulated period error 0.299879780 d making the epoch check applicable. P8 also has local selection witnesses. [I] A period-only alternative would change the registered rule; it is not credited. Nominal-event depth dilution and a duration wider than the search maximum are additional diagnostics.',
149216532:'[M] A local exact-period 15.7365-day internal-gate passer at composite 38.26 lost to 11.540574 d at composite 44.36 in P10, and to 10.49113 d at composite 45.3 in P8. Nominal-event kept depth is negative. [I] The saved logs establish selection competition in both presets, but the uncheckable epoch and variable nominal-event depths limit claims about the underlying signal.'}

def autopsy_report():
    jobs=read(ROOT/'manifests/autopsy_jobs.json')
    parts=['# P10.3 five required autopsies',
    '[M] Both H rules fired. The locked selection contains the five highest expected-SNR INDEPENDENT likely-periodic in-band forced-present misses across the fired presets. Every selected family misses in both presets. Five one-attempt diagnostics completed with no unknowns. The original primary fits, searches and prediction locks were preserved.',
    '[A] The new diagnostic uses the independent representative TCE period, nominal epoch and duration, with the one-cadence duration floor, in a fresh per-family root. It runs the unchanged preparation/event-census functions only. There is no new blind search, TLS fit, or primary Part F fit. The P9-style nominal-ephemeris A criteria are counterfactual; they cannot be recorded as actual Stage A losses. Best-phase primary presence is explicitly distinguished from nominal-epoch diagnostics.',
    '[M] Four P10 autopsies have local internal-gate/selection witnesses; three have nominal durations wider than the 4.8-hour search maximum; four have uncheckable nominal epochs. The saved witnesses identify a shared selection contributor, not a demonstrated alternative recovery or a unique common cause. The proposed iteration is costed in `CALIBRATION_CHECK_P10_3.md` and is not executed.']
    for rank,job in enumerate(jobs,1):
        r=read(REPO/job['result_path']);runtime=read(REPO/job['arguments'][1]);t=r['representative'];fid=r['family_id'];tic=r['tic_id']
        primary=r['primary_forced_fit'];fit=primary['fit']
        if 'fit' in fit:fit=fit['fit']
        parts.extend([f'## {rank}. TIC {tic} · {fid}',
          '[M] '+AUTOPSY_INTERPRETATIONS[tic].removeprefix('[M] '),
          table(['Quantity','Recorded value'],[
            ['Representative source',f"{t['source_filename']} row {t['source_row']}; {t['sectors']}; pn {t['tce_plnt_num']}"],
            ['TCE period / epoch',f"{t['tce_period']} d / BTJD {t['tce_time0bt']}"],
            ['Nominal duration / depth',f"{t['tce_duration']} h / {t['tce_depth']} ppm"],
            ['DV model SNR / transit count',f"{t['tce_model_snr']} / {t['tce_num_transits']}"],
            ['Expected SNR',num(r['expected_snr'],10)],
            ['Primary presence',primary.get('presence','PRESENT')],
            ['Primary fit phase mode',fit.get('epoch_mode','see primary receipt')],
            ['Primary fitted depth significance',num(fit.get('depth_sigma'),9)],
            ['Epoch condition',json.dumps(r['primary_epoch_rule'])],
            ['First actual termination',r['first_termination']],
            ['Diagnostic root',r['diagnostic_root']],
            ['Autopsy result SHA256',sha(REPO/job['result_path'])]]),
          '### Nominal event census and counterfactual A criteria',
          table(['Metric','Count'],[[k,v] for k,v in r['event_summary'].items() if k.startswith('n_')]),
          'The predicted-in-span count includes gaps without observed coverage. Kept event opportunities need not have a finite detrended depth measurement. Removal classes can overlap within one event.',
          table(['Removal class','Observed events carrying class'],list(r['event_removal_counts'].items())),
          table(['Frozen native preparation counter','Value'],list(r['frozen_native_preparation_counters'].items())),
          table(['Counterfactual criterion','Satisfied'],list(r['counterfactual_A_criteria']['criteria'].items())),
          table(['Counterfactual metric','Value'],[[k,num(v,8)] for k,v in r['counterfactual_A_criteria'].items() if k not in ('criteria',)]),
          '[M] Rotation/variability proxy from the pre-exposure native-noise record: '+json.dumps(r['rotation_proxy'])+'. This proxy was not used to select the five misses.'])
        for p in PRESETS:
            d=r['search'][p];paths=runtime['search_paths'][p]
            parts.extend([f'### {p}: traces, selection, accepted aliases and budget',
                table(['Evidence','Value'],[
                  ['BLS near-period/allowed-alias trial count',d['trace']['near_trial_count']],
                  ['Broad-rank competitions',len(d['trace']['broad_rank_competition'])],
                  ['Local internal-gate/selection witnesses',len(d['log']['selection_witnesses'])],
                  ['Trace path',paths['trace_path']],['Trace SHA256',runtime['input_hashes'][paths['trace_path']]],
                  ['Search log path',paths['log_path']],['Search log SHA256',runtime['input_hashes'][paths['log_path']]]]),
                '[A] BLS rank competition alone does not establish internal-gate passage. The following log witnesses require both a locally period-compatible gate passer and selection of a different period. They do not establish the epoch or a globally accepted alternative result.'])
            witnesses=[]
            for w in d['log']['selection_witnesses']:
                for q in w['near_trials']:
                    if not q['internal_gates_passed'] or not q['resolved_alias']:continue
                    witnesses.append([w['partition'],w['pass_number'],q['line'],q['resolved_period'],q['resolved_alias'],q['composite'],w['chosen']['line'],w['chosen']['period'],w['chosen']['composite']])
            parts.append(table(['Partition','Pass','Trial log line','Local period d','Alias','Local composite','Chosen log line','Chosen period d','Chosen composite'],witnesses) if witnesses else '[M] No qualifying saved final-selection witness.')
            near=d['trace']['near_trials']
            parts.append(table(['Trace line','Partition','Pass','Trial period d','Alias','BLS SNR','Peak rank'],
                [[q['line'],q['partition'],q['pass_number'],q['period_days'],q['alias'],num(q['snr']),q['peak_rank']] for q in near]))
            associations=[]
            for q in d['accepted_associations']:
                for e in q['associations']:
                    associations.append([q['row_id'],e['candidate_id'],e['alias'],num(e['relative_period_error'],8),e['epoch']['mode'],e.get('epoch_agrees'),e['recovered'],num(e.get('phase_distance_days'),9)])
            parts.append(table(['TCE row','Accepted candidate','Alias','Relative period error','Epoch mode','Epoch agrees','Recovered','Phase distance d'],associations) if associations else '[M] No accepted candidate has a registered period/alias association with this representative independent ephemeris.')
            parts.append(table(['Detector-budget field','Exhausted'],[[q['path'],q['value']] for q in d['budget_flags']]))
            if d['log']['stop_messages']:
                parts.append(table(['Log line','Stop/budget message'],[[q['line'],q['message']] for q in d['log']['stop_messages']]))
        plot=f'results/autopsies/{fid}'+('_display_v2.png' if tic==29002055 else '.png')
        parts.extend([f'![TIC {tic}: native input, nominal TCE fold, and event census]({plot})',
                      '[M] Display plots use saved arrays and measurements only. The fold is TCE-informed and diagnostic. The TIC 29002055 display copy explicitly annotates its empty detrended-depth panel; the sealed original plot remains unchanged.'])
    parts.append(ASSUMPTIONS)
    md('AUTOPSIES_P10_3.md',parts)

def export_tables():
    folder=ROOT/'results/tables';folder.mkdir(exist_ok=True)
    for name,rows in [('search',ANALYSIS['search_tables']),('funnel',ANALYSIS['funnel_tables']),('paired_differences',ANALYSIS['paired_present_recovery_differences']),('natural_load',ANALYSIS['natural_load'])]:
        flat=[]
        def flatten(d,prefix='',out=None):
            out={} if out is None else out
            for key,value in d.items():
                key=prefix+key
                if isinstance(value,dict):flatten(value,key+'.',out)
                elif isinstance(value,list):out[key]=json.dumps(value)
                else:out[key]=value
            return out
        flat=[flatten(r) for r in rows]
        headers=list(dict.fromkeys(k for row in flat for k in row))
        with (folder/f'{name}.csv').open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=headers);writer.writeheader();writer.writerows(flat)

def decision_report():
    shutdown=read(ROOT/'manifests/final_supervision_disabled.json')
    assert shutdown['status']=='DISABLED_VERIFIED' and shutdown['old_p10_status']=='PAUSED'
    assert not (ROOT/'manifests/controller_owner.json').exists()
    audit=read(ROOT/'results/final_evidence_audit.json')
    assert audit['status']=='PASS'
    ledger=read(ROOT/'manifests/resource_ledger.json');cost=read(ROOT/'results/p10_1_costed_next_step.json');supp=read(ROOT/'results/final_supplementary_censuses.json')
    H=ANALYSIS['calibration'];fs=overall_funnel()
    parts=['# RETENTION_MEASURED_CALIBRATION_OPTIMISTIC',
    '[M] P10.3 is complete through the registered measured sequence, including the five required autopsies. The hourly routine is disabled and verified, all owned scientific processes are closed, and the old P10 routine remains paused. No Part I stop fired. The user-authorized automatic continuation ends at this final delivery.',
    '## Populations actually evaluated',
    '[M] Original list: **531** bare-SPOC-TCE domain stars. Input-eligible: **436** after 58 Gaia exclusions and 37 verified-coverage exclusions. Evaluated: **436 under each preset**, with six timing-pilot hosts reused and 430 new hosts per preset. All 473 Gaia-passing stars pass the corrected FFI-majority cut. There are 2,363 evaluated TCE rows, 1,449 distinct period families and 503 in-band families. All original 531 stars are development-exposed from Part F and cannot be reused as a holdout.',
    '## Search retention',
    table(['Stratum','Preset','Present in-band family recovery; 95% CI','All in-band family recovery; 95% CI'],
          [[s,p,fraction(overall_search(stratum=s,preset=p)['recovery_present']),fraction(overall_search(stratum=s,preset=p)['recovery'])] for s in STRATA for p in PRESETS]),
    '[M] The union present-signal paired advantage is **+5.556 percentage points [2.494, 8.772]** for P10 over P8. Exact versus alias recovery and every model-SNR, expected-SNR, period and raw-row table are in `SEARCH_RETENTION_P10_3.md`. All fractions use the registered 10,000 whole-host bootstrap. Absence is separated from a present-signal miss; outside-domain families are not search failures.',
    '## Early-funnel retention and attributed rejections',table(FUNNEL_HEADERS,funnel_rows(fs)),
    '[M] Of 174 recovered union present families, pre-gate removes 43. Stage A removes a further 92 and leaves two unknown; bound S removes 24; B removes none. Thirteen families reach B. C has eight passing families, one failing family, four not run and the two propagated A unknowns. Candidate-level C used six runs (five PASS, one FAIL), because multiple alias-associated families can share one candidate. N_C was fixed at 13 from the B-closure ledger; all six qualifying candidates were tested. Eighteen unmatched and five nonqualifying B survivors were excluded by the registered selection, not by capacity.',
    '[M] `FUNNEL_RETENTION_P10_3.md` gives every recorded A criterion, S bound-mode reason, per-loss candidate path and expected-SNR comparison with historic injections. These are rejections of periodic-signal associations, not demonstrated losses of planets.',
    '## Natural load',table(['Stage','Candidates passed','Candidates per evaluated host; 95% CI'],[[r['stage'],r['passing_count'],fraction(r['per_star'],rate=True)] for r in ANALYSIS['natural_load']]),
    '[P10, I] Historic control references are 11.65 accepted, 2.36 pre-gate, 0.150 A and 0.0067 S per host. The observed A/S load is higher in this selected TCE population. Specificity cannot be inferred from those count differences.',
    '## Part H rule and autopsies',
    '**[M] Both literal SNR50 rules fire on 89 qualifying independent families on 74 hosts. [I] Both fitted slopes are negative; the crossings are unstable extrapolations and are not usable sensitivity thresholds.** The formal state preserves the registered trigger without claiming a reliable physical estimate of the injection-calibration shortfall.',
    table(['Preset','Slope b','SNR50','95% finite-bootstrap interval','Rule'],[[p,num(H[p]['fit']['b'],8),num(H[p]['fit']['snr50'],8),f"[{num(H[p]['bootstrap_ci95'][0],8)}, {num(H[p]['bootstrap_ci95'][1],8)}]",H[p]['rule']] for p in PRESETS]),
    '[M] Each fit has 9,965 finite bootstrap crossings and 35 nonfinite crossings. Four of the five highest-SNR misses have local P10 internal-gate passers that lose recorded selection. Three nominal TCE durations exceed the fixed search maximum; four nominal epochs are uncheckable. The complete five autopsies preserve the original searches and primary forced fits. Ranking is a shared contributor, not a proven single cause or a measured alternative recovery.',
    f"[A, M] **p10.1 was costed only, as the user directed.** The stipulated subset benchmark plus a conservative full 436-host rerun and 25% margin costs {cost['presets']['survey_p10']['total_with_margin_hours']:.3f} h for P10 or {cost['presets']['survey_p8']['total_with_margin_hours']:.3f} h for P8, against {cost['remaining_hours']:.3f} h remaining. Even these planning costs exceed the available allocation; the full 2,100-injection revalidation cost is not newly measured. The six-host proxy conservatively charges the entire paired-pilot interval to each proposed changed preset. No iteration was launched.",
    '## Operational unknowns by stage',
    table(['Stage','Operational unknowns','Disposition'],[
      ['Final acquisition',0,'473 indices; 11,532 products; final recorded product failures zero'],
      ['survey_p10 / survey_p8', '0 / 0','All 436 hosts complete in each locked manifest'],
      ['Stage A',2,'tic177352028_p01 and tic33866201_p01; one attempt, no scientific retry'],
      ['S / B / C','0 / 0 / 0','Two A family unknowns remain propagated downstream'],
      ['Part F forced fits',24,'All outside 0.5–30 d; no measured in- or out-of-transit level; never absent or missed'],
      ['Autopsies',0,'Five complete; one nominal-event detrended-depth series is unmeasured and explicitly annotated']]),
    '## Resource accounting',
    table(['Resource','Final measured/charged value'],[
      ['New union scientific queue-hours, failures and stalls included',f"{ledger['new_queue_hours']:.9f} / 31.98 h"],
      ['Prior cumulative hours',f"{ledger['prior_queue_hours']:.4f} h"],
      ['Cumulative charged scientific hours',f"{ledger['prior_queue_hours']+ledger['new_queue_hours']:.9f} / 48 h"],
      ['Remaining new allocation',f"{31.98-ledger['new_queue_hours']:.9f} h"],
      ['Cumulative measured acquisition bytes',ledger['cumulative_measured_acquisition_bytes']],
      ['Cumulative conservative acquisition charge',f"{ledger['cumulative_acquisition_budget_charge_upper_bytes']} / 15000000000 bytes"],
      ['Unreconciled acquisition reservation included in upper charge',ledger['acquisition_outstanding_reserved_upper_bytes']],
      ['C free at final shutdown',f"{shutdown['disk_free_bytes']['C']/1e9:.3f} GB"],
      ['D free at final shutdown',f"{shutdown['disk_free_bytes']['D']/1e9:.3f} GB"],
      ['Routine check-ins',f"{shutdown['checkin_count']}; normal interval 60 minutes; early/final exceptions preserved"],
      ['First / last recorded firing',f"{shutdown['first_firing']} / {shutdown['last_firing']}"],
      ['Current supervision',shutdown['status']]]),
    '[M] The per-interval ledger includes downloads, preparation, searches, failed/timed-out jobs, forced fits, C and descriptive analysis. Reports, integrity verification, regression checks and check-ins are engineering time. Before acquisition closeout, C reached 27.7 GB free; user-authorized relocation of the regenerable stitched cache (3,763,602,311 bytes) and TESScut cache (21,004,824,598 bytes) to D restored headroom. Original paths remain directory junctions. Both byte-count receipts are retained; no sealed evidence was moved. Entry disk measurements are retained in the entry/handoff receipts.',
    '## Criteria not met, validation and remaining measurements',
    '[M] STOP-1 passed with 95 independent likely-periodic in-band eligible families (minimum 60). Input eligibility fails for the 95 enumerated original stars. The H minimum of 40 is met, but the optimistic-calibration rule fires for both presets and a useful monotonic SNR50 estimate is not obtained. Early-funnel retention is low, and one C case fails SDE. The two A and 24 forced-fit unknowns remain unresolved under the one-attempt rule. The stipulated p10.1 budget test does not fit; the user also prohibited executing it. No Part I storage, budget or integrity stop fired.',
    '[M] Final compatibility validation: **891 passed, 1 skipped**. The separate Part 3 suite had **116 passed**, and the subsequently added two autopsy checks passed in a focused invocation. An initial combined-suite collection failed because historical and Part 3 tests import different unqualified `common` modules; that log is retained. Fresh separate processes passed without changing scientific code or outcomes.',
    '[M] Historical read-only integrity checks passed with no mismatches or verifier errors: the P11.5 check covered 63,168 files and 26,609,076,372 bytes, alongside the P10/P11 seal and historical-entry checks. Final Part 3 parent seals and all new scientific arrays were checked separately; `results/final_evidence_audit.json` and the source/data seals describe coverage. No blind worker opened the sidecar. All five autopsy diagnostics verify unchanged original inputs.',
    '[I] Unmeasured: B/C specificity in this population, Stage D, every endpoint precision/recall or submission claim, and retention for excluded original stars. No new planet classification is inferred. The five C passers are carried, unverdicted, with recorded F7 SPOC-TCE associations and no promotion.',
    '[P10] The unretuned endpoint risks remain: TOI-762 A b and TOI-122 b are known confirmed planets rejected by the p10.0 tiers, and TIC 144277542 changes from artefact KILL to SUBMIT under rescoring. This run does not resolve those risks.',
    '## What a Part 5 rerun would need',
    '[I] Before a survey of the original 2,000 plus additional eligible stars, Part 5 needs a prospectively fixed policy, direct specificity and endpoint validation on independent data, a budget/storage forecast using this measured natural load, a coverage policy for the excluded stars, and explicit survey authorization. A proposed ranking change first needs the costed injection/control experiment and full required revalidation; its gain is currently unmeasured. Apply the named isolated hard_stop_p10 catalogue adapter and its FLAG-with-ephemeris interface without changing the old hard stop or historical sealed sources. This run provides tables and preserved associations, not survey approval.',
    '## Delivery record',
    '[M] The allocation and supervision amendments, prediction locks, exposure ledger, closure receipts, full tables, five autopsies, resource ledger and disabled-verified routine receipt are delivered under `p10/part3/`. The local final commit is recorded in the exported delivery receipt, avoiding a self-referential commit hash inside committed reports. Nothing is pushed. The original registration and historical evidence remain sealed.',ASSUMPTIONS]
    md('DECISION_P10_3.md',parts)

def main():
    import sys
    if '--decision' in sys.argv:
        decision_report();print('Final decision written after verified supervision shutdown');return
    supp=supplementary()
    assert len(supp['forced_unknown'])==24 and not any(r['in_band'] for r in supp['forced_unknown'])
    search_report(supp);funnel_report();autopsy_report()
    cost=costed_next_step();calibration_report(supp,cost);export_tables()
    write(ROOT/'results/final_reports_ready.json',dict(utc=utc(),status='REPORTS_READY_FOR_FINAL_SHUTDOWN',
        files={name:sha(ROOT/name) for name in ('SEARCH_RETENTION_P10_3.md','FUNNEL_RETENTION_P10_3.md','CALIBRATION_CHECK_P10_3.md','AUTOPSIES_P10_3.md')},
        primary_analysis_sha256=sha(ROOT/'results/retention_analysis.json'),final_decision_written=False),replace=True)
    print(json.dumps(dict(status='REPORTS_READY',budget_counts={p:supp['budget_flags'][p]['hosts'] for p in PRESETS},H_snr_range=supp['H_expected_snr_range'],H_recovery=supp['H_qualifying_recovery'],cost=cost)))

if __name__=='__main__':main()
