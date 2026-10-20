"""Evidence census for every external planet, without changing locked outcomes."""
from common import *
import collections,math
import pandas as pd
from diagnose import slug,scores_available

def number(x,places=3):
    try:return f'{float(x):.{places}g}' if math.isfinite(float(x)) else 'missing'
    except (TypeError,ValueError):return 'missing'

def run():
    scores=scores_available();features={r['truth_id']:r for r in read(P9/'results/diagnostic_features.json')}
    audit_path=next((P9/f'results/{n}' for n in ['search_trial_audit.json','search_trial_audit_partial.json'] if (P9/f'results/{n}').exists()),None)
    search_audits={r['truth_id']:r for r in read(audit_path)['records']} if audit_path else {}
    spectrum_path=next((P9/f'results/{n}' for n in ['spectrum_normalization_audit.json','spectrum_normalization_audit_partial.json'] if (P9/f'results/{n}').exists()),None)
    spectra={r['key']:r for r in read(spectrum_path)['records']} if spectrum_path else {}
    timing_path=next((P9/f'results/{n}' for n in ['positive_ephemeris_audit.json','positive_ephemeris_audit_partial.json'] if (P9/f'results/{n}').exists()),None)
    timings={r['truth_id']:r for r in read(timing_path)['records']} if timing_path else {}
    duration_path=P9/'results/duration_identity_audit.json'
    durations={r['truth_id']:r for r in read(duration_path)['identity_checks']} if duration_path.exists() else {}
    truth=pd.read_csv(P9/'truth/final_truth.csv').set_index('truth_id');cards=[];rows=[]
    for s in scores:
        if s['label']!='positive':continue
        from scoring import verify_lock
        verify_lock(s['tic_id']);f=features.get(s['truth_id'],{});t=truth.loc[s['truth_id']]
        root=P9/'results/blind'/f'tic{s["tic_id"]}';key=s.get('candidate_key') or s.get('alias_candidate_key');tags=[];evidence=[]
        term=s['first_termination'];snr=f.get('snr_expected')
        if term=='search':
            if snr is not None and snr<7.1:tags.append('expected_SNR_below_pregate_scale')
            elif snr is not None and snr<12:tags.append('near_search_threshold')
            elif snr is not None:tags.append('higher_SNR_search_miss_requires_attention')
            else:tags.append('expected_SNR_diagnostic_missing')
            if s.get('aliases'):tags.append('registered_alias_instead_of_exact')
            if s.get('search_budget_stop'):tags.append('wall_budget_stop_recorded_not_proven_causal')
            near=[a for a in s.get('all_search_matches',[]) if (a['match'].get('period_fraction') or 0)<=.01]
            if near:
                tags.append('near_period_but_failed_multi_event_alignment')
                evidence.append('Accepted near-period signals failed alignment: '+str(near))
            evidence.append(f'Blind search accepted {s.get("n_accepted_signals",0)} signals on the host; none satisfies this planet’s exact period-and-event rule.')
        if term=='pre':evidence.append('Pre-gate fields: '+str(s.get('pregate_fields')))
        if s.get('termination_reason'):evidence.append('First-termination record: '+s['termination_reason'])
        if s.get('final_reason'):evidence.append('Final review: '+s['final_reason'])
        if s.get('operational'):tags.append('operational_incomplete')
        if (f.get('ephemeris_sigma_over_duration') or 0)>=.5:tags.append('published_ephemeris_uncertainty_material')
        if t.get('ttv_flag')==1:tags.append('catalogue_TTV_flag_causal_role_unresolved')
        rp=f.get('rotation_proxy') or {}
        if (rp.get('semi_amplitude_ppt') or 0)>=3:tags.append('large_periodic_variability_proxy_may_include_transit_or_artifact')
        records={};source_files=[]
        timing=timings.get(s['truth_id'],{})
        for alternative in timing.get('alternative_solutions',[]):
            if alternative['diagnostic_existing_path']['search']:
                tags.append('alternative_published_ephemeris_matches_locked_signal_no_primary_credit')
                evidence.append('Post-lock alternative published timing matches existing blind outputs: '+str(alternative)+'. This is a truth-timing sensitivity, not a search rerun, a changed verdict or primary recovery credit.')
                source_files.append(P9/'diagnostics/ephemeris_sources'/f'tic{s["tic_id"]}_nasa_ps.csv')
        if key:
            for folder in ['stageA','secondary','stageB','stageC','final']:
                path=root/folder/f'{key}.json'
                if path.exists():records[folder]=read(path);source_files.append(path)
            for stage in ['A','S','B','C','D']:
                path=P9/'results/operations'/f'{stage}_{key}.json'
                if path.exists():
                    source_files.append(path)
                    op=read(path)
                    if op.get('status') in ('error','timeout'):
                        evidence.append(f'Operational {stage}: {op["status"]}; {len(op.get("attempts",[]))} recorded attempts. This is an unavailable scientific outcome, not measured rejection.')
        if 'stageA' in records:
            a=records['stageA'];chosen=(a.get('per_ephemeris') or {}).get(a.get('chosen_ephemeris')) or {}
            failures=[k for k,v in (a.get('criteria') or {}).items() if not v]
            if term.startswith('A'):tags.extend('A_'+x for x in failures)
            evidence.append(f'Blind A chose {a.get("chosen_ephemeris", "unavailable")}: {a.get("reason")}. Failed criteria: {failures}.')
            if term.startswith('A'):
                counts=collections.Counter(c for e in chosen.get('events',[]) if e.get('observed') and e.get('excluded') for c in e.get('artefact_classes',[]))
                evidence.append('Removed-event classes at the blind accepted ephemeris: '+str(dict(counts)))
        if 'secondary' in records:
            a=records['secondary'];evidence.append('Blind secondary scan: '+str(a.get('reason')))
            if term=='S':tags.append('secondary_gate_rejected_independently_labelled_planet')
        if 'stageB' in records:evidence.append('Blind B: '+str(records['stageB'].get('reason')))
        if 'stageC' in records:
            c=records['stageC'];b=c.get('blind') or {}
            evidence.append(f'Blind C strongest P={number(b.get("period"))} d, SDE={number(b.get("SDE"))}; maximum near the survey seed SDE={number(b.get("SDE_at_survey_period_max_1pct"))}; survey-region rank={b.get("SDE_rank_of_survey_period")}. {c.get("reason")}')
            if term.startswith('C'):
                if (b.get('SDE') or 0)<c['thresholds']['sde']:tags.append('C_SDE_below_threshold')
                if not (b.get('match') or {}).get('same_period_1pct'):tags.append('C_strongest_peak_period_disagreement')
                if 'switch' in term:tags.append('C_accepted_ephemeris_fails_registered_identity_not_proof_of_physical_switch')
                if s['truth_id'] in durations:
                    tags.append('C_reported_duration_changes_event_census_no_primary_credit')
                    evidence.append('Post-lock duration/identity audit: '+str(durations[s['truth_id']])+'. Identical C period/epoch with alternate recorded durations is diagnostic only. Native D already uses the wider survey/C duration; no scientific stage or primary score is changed.')
                    source_files.append(duration_path)
                sa=spectra.get(key)
                if sa:
                    evidence.append(f'Saved native spectrum minimum is {number(sa["minimum_power"],8)} at {number(sa["minimum_period"],10)} d; that single bin contributes {100*sa["minimum_bin_variance_fraction"]:.6f}% of total centered power variance across {sa["n_trials"]} trials. TLS uses the global standard deviation in SDE normalization. No bin is removed, no alternative SDE is scored, and raw chi-square trial residuals were not saved to establish the upstream origin.')
                    source_files.append(root/'tls'/f'{key}_spectrum.npz')
        if term.startswith('D'):tags.append('final_review_or_fit_ephemeris')
        srpath=root/'search/results'/f'tic{s["tic_id"]}.json'
        if term=='search' and srpath.exists():
            search_notes=read(srpath).get('result',{}).get('notes') or []
            if search_notes:
                evidence.append('Recorded native search notes, contributing context rather than a causal rescue: '+str(search_notes))
            if any('masking' in n and 'would remove' in n for n in search_notes):
                tags.append('mask_width_stop_recorded_not_proven_causal')
            if any('finite cadences remain' in n for n in search_notes):
                tags.append('remaining_cadence_stop_recorded_not_proven_causal')
        # Trial census is diagnostic and contains no new search execution.
        trialpath=root/'search_trials.jsonl';near_trials=[]
        if trialpath.exists():
            source_files.append(trialpath)
            for line_number,line in enumerate(trialpath.open(encoding='utf-8'),1):
                rec=__import__('json').loads(line)
                if rec.get('event')=='broad_bls':
                    for q in rec.get('candidates',[]):
                        try:
                            if abs(float(q['period_days'])/float(t.period)-1)<=.01:
                                near_trials.append(dict(jsonl_line=line_number,**{k:q.get(k) for k in ['period_days','epoch_btjd','duration_days','snr','depth_ppt','peak_rank']}))
                        except (KeyError,TypeError,ValueError):pass
            if near_trials:evidence.append(f'{len(near_trials)} BLS/refinement trial rows were within 1% of the published period; this does not establish that a trial passed the search gates.')
        sa=search_audits.get(s['truth_id']) or {}
        if sa.get('competition_witnesses'):
            tags.append('local_near_period_candidate_lost_composite_selection')
            source_files.append(P9/sa['source_log'])
            for witness in sa['competition_witnesses']:
                q=max(witness['near_period_passes'],key=lambda v:v['composite'] or 0);chosen=witness['chosen']
                evidence.append(f'Recorded local competition in {witness["search"]}, pass {witness["iteration"]}: near-period {q["resolved_period"]} d candidate passed internal gates at composite {q["composite"]} (log line {q["log_line"]}), but {chosen["period"]} d won at composite {chosen["composite"]} (line {chosen["log_line"]}). Period proximity is diagnostic only; no alternative global recovery is credited.')
        cf=f.get('truth_counterfactual_A');ev=f.get('truth_event_summary') or {}
        evidence.append('Truth-ephemeris counterfactual A criteria (excluded from primary counts): '+str(cf))
        if term=='search' and ev.get('det_kept'):
            evidence.append('Counterfactual kept-event depth SNR='+number(ev['det_kept'].get('snr'))+'; this is selected/processed at published timing and is not blind search significance.')
        evidence.append('Truth-ephemeris event-removal classes, contributing diagnostics only: '+str(f.get('event_removal_counts',{})))
        record=dict(truth_id=s['truth_id'],tic_id=s['tic_id'],first_termination=term,retained_useful=s.get('D_useful',False),
          contributors=tags,diagnostic_status=f.get('status'),snr_expected=snr,period=float(t.period),
          ephemeris_sigma_over_duration=f.get('ephemeris_sigma_over_duration'),evidence=evidence,
          n_near_period_trial_rows=len(near_trials),near_period_trial_examples=near_trials[:12],
          search_competition_witnesses=sa.get('competition_witnesses',[]),
          evidence_sha256={str(p.relative_to(P9)):sha(p) for p in source_files+([srpath] if srpath.exists() else [])})
        rows.append(record)
        title=f'## {s["truth_id"]} — {term}'
        body=[title,'',f'TIC {s["tic_id"]}; published period {number(t.period,8)} d; radius {number(t.radius_re)} Earth radii; duration {number(t.duration_hours)} h.',
          f'Observed opportunities: {s.get("opportunities")}; expected model SNR: {number(snr)}; box-model expected SNR: {number(f.get("snr_box_expected"))}; cadence MAD: {number(f.get("sigma_cadence_ppt"))} ppt.',
          f'Published timing-error scale at the end of observations / duration: {number(f.get("ephemeris_sigma_over_duration"))}. TTV flag: {number(t.ttv_flag)}.',
          '', 'Evidence and interpretation:', '']
        body += ['- '+e for e in evidence]
        body += ['', 'Contributing tags: '+', '.join(tags or ['no additional cause assigned'])+'.',
          '', 'TTVs, spot crossings, dilution errors and truth-ephemeris covariance are not independently fitted here. A tag or correlation does not establish a unique causal mechanism.',
          '',f'![Truth-informed diagnostic](diagnostics/{slug(s["truth_id"])}/autopsy.png)',
          '',f'[Machine-readable diagnostic](diagnostics/{slug(s["truth_id"])}/diagnostic.json) · [Locked host outcome](results/locks/tic{s["tic_id"]}.json)','']
        cards.append('\n'.join(body))
    write(P9/'results/failure_autopsies.json',rows)
    flat=[{k:v for k,v in r.items() if not isinstance(v,(dict,list))} | {'contributors':';'.join(r['contributors'])} for r in rows]
    pd.DataFrame(flat).to_csv(P9/'results/failure_autopsies.csv',index=False)
    introduction='# P9 planet-by-planet autopsies\n\nEvery card uses an individually locked blind outcome. Published ephemerides are used only for the labelled diagnostics. First termination is distinct from contributing evidence. Retained planets are included for comparison.\n\n'
    (P9/'AUTOPSIES.md').write_text(introduction+'\n'.join(cards),encoding='utf-8')
    print('autopsy cards',len(cards),flush=True)

if __name__=='__main__':run()
