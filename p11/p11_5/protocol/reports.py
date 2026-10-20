"""Build self-contained final Markdown reports from locked measured evidence."""
from common import *
import sys,collections

def num(value,places=2):
    return 'n/a' if value is None else f'{value:.{places}f}'

def stat(row):
    if not row.get('n'):return '0 injections; gain unidentified'
    lo,hi=row['ci95_pp']
    return (f"{row['proposed']}/{row['n']} versus {row['baseline']}/{row['n']}; "
        f"{row['gain_pp']:+.2f} percentage points (95% host interval {lo:+.2f} to {hi:+.2f}); "
        f"{row['wins']} paired wins / {row['losses']} losses")

def save(name,lines):
    (ROOT/name).write_text('\n'.join(lines)+'\n',encoding='utf-8')

def main(state):
    assert state in ('NO_QUALIFIED_GAIN','DEVELOPMENT_GAIN_ONLY','UPSTREAM_QUALIFIED')
    r=read(ROOT/'results/development_evaluation.json');sens=read(ROOT/'results/sensitivity_tables.json')
    figure=read(ROOT/'results/development_overview.json')
    if figure['evaluation_sha256']!=sha(ROOT/'results/development_evaluation.json'):
        raise ValueError('Development figure does not match locked evaluation')
    for path,expected in figure['figures'].items():
        if sha(REPO/path)!=expected:raise ValueError('Development figure changed')
    cost=read(ROOT/'results/resource_accounting_final.json');selection=read(ROOT/'manifests/development_selection.json')
    forecast=read(ROOT/'results/affordability_forecast.json');trace=read(ROOT/'results/trace_diagnostic.json')
    joins=read(ROOT/'manifests/control_joins.json');policies=r['policies']
    deadline_repairs=[row for path in (ROOT/'results').glob('deadline_precedence_[0-9][0-9].json')
                      for row in read(path).get('repaired',[])]
    deadline_note=(f"{len(deadline_repairs)} completed payload artifacts had owning-controller TIMEOUT receipts. "
        'The registered controller deadline takes precedence: exact original payload bytes and timings remain in `results/late_payloads_v1/`, '
        'while subsequent handoffs and recovery/workload accounting use terminal operational unknowns. '
        'The uniform rule, discovered before aggregate efficacy scoring, is registered in `manifests/operational_deadline_precedence_v1.json`; '
        'per-application receipts are `results/deadline_precedence_*.json`. Already computed descendants and all attempt costs remain preserved.')
    storage=read(ROOT/'manifests/c_v2_storage_plan_v1.json')
    packing_hours=sum(p['charged_seconds'] for p in cost['phases']
        if (p.get('phase') or '').startswith(('c_v2_pack_batch_','c_v2_storage_pilot')))/3600
    storage_note=(f"The original-NPZ storage forecast exceeded available headroom, so all {storage['remaining_candidates']} remaining corrected-C candidates "
        f"were retained in {len(storage['batches'])} finite batches. Completed model containers were packed losslessly as XZ; "
        'original NPZ hashes and exact-container verification receipts remain in `results/model_storage/C_v2/`. '
        f"Packing owners occupied {packing_hours:.4f} queue-hours, included in total expenditure. "
        'These storage phases are separate from the scientific C measurements. '
        'The frozen plan and each disk/memory/budget preflight are in `manifests/c_v2_storage_plan_v1.json` and `results/c_v2_batch_checks/`. '
        'Every C case retained its 600-second deadline, and each packing job had a separate 300-second deadline.')
    if state=='UPSTREAM_QUALIFIED':raise RuntimeError('Full fresh-validation report adapter is required for a qualified endpoint')
    if r['finalist'] is not None:raise RuntimeError('An eligible finalist requires the conditional validation decision before final reporting')
    header=f"Completed development: {r['n_hosts']} D_core hosts, {r['n_injections']} fixed injections, and {r['n_hosts']} uninjected series."
    completion=('All registered cases reached a terminal accounting state, with '
        f"{len(r['operationally_failed_required_stages'])} required stage records retaining operational unknowns. "
        'Recovery and workload use the predeclared conservative treatment. This is a complete attempted-cohort result with incomplete individual scientific measurements; it does not establish what the censored stages would have returned.'
        if r['operationally_failed_required_stages'] else
        'All required scientific route measurements are complete for the registered cohort.')
    scope='Original population: 300 hosts / 600 injections. Verified input-eligible D_core: 235 hosts / 484 injections. Input exclusions are not measured misses. No extrapolation to excluded hosts or sectors is made.'
    claims='This is upstream development evidence. It establishes neither planet discovery, astrophysical false-positive probability, endpoint reliability nor authority for a survey or submission.'
    endpoint='The unretuned P10 endpoint risks remain: confirmed TOI-762 A b and TOI-122 b are rejected by tier thresholds; TIC 144277542 changes from artifact KILL to SUBMIT under rescoring. P11.5 does not repair or validate these endpoints.'
    search=[ '# P11.5 alternative search: completed development', '',header,'',scope,'',
        f"Selected search: **{r['selected_search']}**. Low-SNR comparison is after unchanged pre-gate, A and bound S: {stat(r['search_low'])}.",
        f"Overall paired comparison: {stat(r['search_overall'])}.",'',
        '| Search admission requirement | Met |','|---|---|']
    search += [f'| {k} | {v} |' for k,v in r['search_requirements'].items()]
    search += ['', '| Method | Natural pre-gate candidates | Search/confirmation wall h | Search/confirmation/A/S wall h | Scientific CPU h |',
        '|---|---:|---:|---:|---:|']
    for method in ('R0','R1'):
        c=r['search_costs'][method]
        search.append(f"| {method} | {r['natural_pregate_counts'][method]} | {c['search_wall']/3600:.3f} | {c['wall']/3600:.3f} | {c['cpu']/3600:.3f} |")
    search += ['', 'R0 and R1 share one newly measured ordinary trajectory on identical frozen arrays. The observer retains complete gate-passing resolved pools and reconstructable masks. Each method includes the full shared work in its deployable cost; actual experiment expenditure counts it once. Original timings are retained on cache reuse.',
        '', 'R1 preserves ordinary winners and all original accepted candidates within the original 24 limit, top-16 internal pool and 2,700-second detector budget. Up to two distinct extras per pass enter a separate 12-candidate reservoir. Only ordinary winners change subsequent masks. Extras undergo actual whole-stitch confirmation. Deduplication requires relative period difference at most 0.001 and epoch offset plus accumulated drift at most half the shorter duration; rational aliases remain distinct.',
        '', f"All {trace['n_cases']} historical ranking-loss cases and {trace['n_witnesses']} witnesses were inspected. Only {trace['relevant_exhausted_reclaimable_cases']} meet the applicability/exhaustion/reclaimable-time conditions, below ten; R2 was not admitted. Historical witnesses are not new recoveries, and incomplete historical masks were not treated as valid replay evidence.",
        '', 'The complete nested population was selected before aggregate efficacy from measured six-host timing distributions, clustered runtime resampling and a 25% allocation margin. See `results/affordability_forecast.json` and `manifests/development_selection.json`.',
        '', 'The first main controller stopped during a Windows progress-record access error. Its completed predictions were reused and all 24 interrupted attempts and partial snapshots were preserved. A source-versioned controller resumed the same registered search/A/S/B workload with bounded progress-write retries; remaining C work used the already registered corrected version. No scientific outcome chose a retry, and no per-case deadline or cumulative cap was increased. See `manifests/controller_interruption_recovery_v1.json` and `manifests/development_resume_freeze_v2.json`.',
        '', deadline_note,
        '', storage_note,
        '', 'The read-only source review in `results/shared_downstream_contract_review.json` verifies that R1 extra-candidate context does not change the shared A/S/B scientific gates. Deep-candidate flags remain recorded diagnostic metadata under P10. This equivalence does not extend to later endpoint tiers.',
        '', 'The prepared-provenance audit checked all 719 generated array files and sidecars. Runtime arrays contain time, flux, errors and sector identity, with no physical injection parameters or recovery truth in provenance. A series-membership boolean remains in the sidecar; the fixed predictor does not consume it or copy it into the LightCurve metadata. This distinction is explicit in `results/prepared_provenance_review.json`. The prediction freeze additionally verifies prepared array, provenance, resolved-pool and mask-snapshot hashes.',
        '', 'Per-injection exact and alias outcomes, physical period/radius tables, expected-SNR bins and 10,000 paired whole-host bootstrap intervals are in `results/development_evaluation.json` and `results/sensitivity_tables.json`. Unobservable included injections remain in the overall denominator.',
        '',claims]
    save('SEARCH_ALTERNATIVES_P11_5.md',search)
    c=[ '# P11.5 C_local: measured joint development', '',header,'',
        'No joint policy satisfied every registered development admission requirement; no fresh holdout was used to search for a winner.', '',
        '![All 36 registered development policies](results/development_overview.png)', '',
        'Final decisions use only C_local v2. Static review before aggregate recovery scoring corrected the broad BLS minimum duration from an unintended 0.02 days to one native cadence, and required residual support to retain the candidate period/epoch. The registered finite thresholds, model family and 600-second deadline stayed fixed. Every first-version result and attempt cost is retained; corrected measurements use separate source, input, result and model identities. See `manifests/C_v2_correctness_registration.json` and `manifests/c_v2_execution_freeze.json`.', '',
        'C_local fits an exposure-integrated trapezoid family to native prepared flux/error arrays. The physical chi-squared uses measured sector noise inflation and identical per-sector constant and linear baselines for flat, planet and two-eclipse fits. This is a finite template discriminator, not an astrophysical radius fit or FPP. Fitted models, flat/transit chi-squared, baseline coefficients, noise inflation and finite-grid diagnostics are archived.',
        '', 'The frozen local ratios are 1/3, 1/2, 2/3, 1, 3/2, 2 and 3, each within 1.5%. Local BLS uses 257 periods and eight durations, geometric and BLS phase seeds, three ingress fractions and bounded refinement. Seven exposure subsamples and a one-cadence duration floor are retained. Physical impossibility and software/grid limits are distinct. Broader native BLS uses 40,000 periods over 0.5–110 days, at most four unrelated competitors and at most three P10 residual masks with three covered events.',
        '', 'Two-eclipse fits at P and 2P optimize secondary phase, depth, duration and ingress with 32 phase seeds. Parameter counts are 2S for flat, 2S+5 for planet and 2S+9 for two-eclipse, where S is the number of sectors. E compares the candidate planet BIC with the fitted binary BIC; rejection additionally requires registered recurrence in at least two sectors. A distinct single-transit alias better by more than six BIC points rejects the primary; two alternatives clearing D and within six BIC points remain unresolved.',
        '', 'Unchanged B is measured before C. The actual ordered route and isolated S/C are both reported. Operational errors and timeouts are never clean passes or measured rejections. Natural unresolved candidates are forwarded; corresponding injections are not recovered. Historical protection requires measured rejection in both isolated S/C and the ordered route. Catalogue-conditioned historical controls are labelled engineering evidence outside survey-domain inference.',
        '', '| Policy | Low-SNR gain pp | Y / n | Protected / 26 | Natural forwarded candidates | C median / p90 s | C unknown / arrivals | CPU / R0 | Eligible |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for p in policies:
        c.append(f"| {p['policy']} | {num(p['low']['gain_pp'])} | {p['low'].get('proposed',0)} / {p['low']['n']} | {p['protected']} | {p['natural_forwarded_candidates']} | {num(p['C_median_wall'])} / {num(p['C_p90_wall'])} | {p['C_unknown']} / {p['C_arrivals']} | {num(p['cpu_ratio'])} | {p['eligible']} |")
    c += ['', 'Historical negative records forwarded by the actual ordered route are shown below. Each count includes PASS and UNRESOLVED. These are candidate-conditioned engineering records, with overlap retained across collections; the union column counts distinct exact measurement identities.',
        '', '| Policy | S EB forwarded / 18 | S blend forwarded / 22 | C EB forwarded / 41 | Distinct negative identities forwarded |',
        '|---|---:|---:|---:|---:|']
    for p in policies:
        outcomes=p['control_outcomes']
        counts=[sum(x['ordered']!='REJECT' for x in outcomes if x['collection']==collection and x['original_id'].startswith(prefix))
                for collection,prefix in [('S_original_40','eb_'),('S_original_40','blend_'),('C_original_41','')]]
        c.append(f"| {p['policy']} | {counts[0]} | {counts[1]} | {counts[2]} | {p['forwarded_distinct_negative_controls']} |")
    c += ['', f"Historical registration contains {joins['registered']} rows and {joins['unique_measurements']} unique exact measurement identities; {joins['unavailable']} input handoffs were unavailable. The five collections retain 40 original S controls (18 EB, 22 blend), the distinct 41-record EB C collection, 37 native C records, 30 injection-C controls and 60 fixed-hash S-killed injections. The seven known half/double records remain tagged. Exact joins and overlap are in `manifests/control_joins.json`.",
        '', 'The three persistent P10 C(a) passes are reported individually below. Entries give ordered / isolated status for every registered policy.',
        '', '| Policy | eb_tic178858648_candidate1 | eb_tic237116051_candidate1 | eb_tic272598447_candidate1 |','|---|---|---|---|']
    persistent=['eb_tic178858648_candidate1','eb_tic237116051_candidate1','eb_tic272598447_candidate1']
    for p in policies:
        by={x['original_id']:x for x in p['control_outcomes'] if x['collection']=='C_original_41'}
        c.append('| '+p['policy']+' | '+' | '.join(by[x]['ordered']+' / '+by[x]['isolated'] for x in persistent)+' |')
    c += ['', 'All original control rows and all 36 policy outcomes are preserved, including missing/unknown reasons in per-stage records. No perfect rejection criterion was added after seeing outcomes, and no survivor is excused by a possible later D rejection.',
        '', f"There are {len(r['operationally_failed_required_stages'])} operationally failed required stage records across the paired R0/R1 and historical-engineering domains. Their exact identities, stages and errors are in `results/development_evaluation.json`; full controller and measurement statuses and all costs are in `results/resource_accounting_final.json`. Scientific UNRESOLVED decisions are reported separately from INPUT_ERROR and TIMEOUT.",
        '', deadline_note,
        '', storage_note,
        '', 'Natural candidate PASS and UNRESOLVED counts, host intervals and the complete multiplicity histogram for every policy are in `results/development_evaluation.json`. The same fields for the R0 pre-C post-S comparator remain separate. Forwarded natural candidates are not labelled confirmed contaminants.',
        '', 'Optional broad-TLS reference runs were allocated zero. No paired threefold CPU speed-up claim is made. Native C and end-to-end measured cost, including failed-attempt expenditure, are reported independently.',
        '', 'SNR50/SNR90 in `results/sensitivity_tables.json` are fitted point diagnostics with extrapolated or unidentified crossings labelled. P10\'s historical after-A/S SNR50 of 18.26124 and pre-gated 952/2,100 recovery remain unchanged.', '',endpoint]
    save('C_LOCAL_P11_5.md',c)
    failed=collections.Counter(k for p in policies for k,v in p['criteria'].items() if not v)
    low_max=max((p['low']['gain_pp'] for p in policies if p['low']['gain_pp'] is not None),default=None)
    decision=['# P11.5 final decision','',f'**{state}**','',header,'',scope,'',completion,'',
        f"R1 versus R0 after pre/A/bound-S in expected SNR [7,15): {stat(r['search_low'])}. Selected search is {r['selected_search']}.",
        '',f"The maximum actual-route C-policy low-SNR point gain over U10 was {num(low_max)} percentage points. None of the 36 joint policies met every admission requirement. U10 is the unchanged same-input true-period pre/A/bound-S route, before B/C; Y additionally requires the actual selected pre/A/S/B/C route and unambiguous fitted-C true-period PASS. This is a conservative upper-bound comparator, not a direct measurement of P10 post-C recovery.",
        '', '| Unmet requirement | Policies failing, of 36 |','|---|---:|']
    decision += [f'| {k} | {v} |' for k,v in sorted(failed.items())]
    decision += ['', f"The full registered population has paired records, including {len(r['operationally_failed_required_stages'])} explicitly operationally failed required stage records across the comparison and engineering controls. Completed accounting does not turn unknown measurements into scientific rejections. No development finalist was admitted; no fresh validation cohort or new validation signal draw was made. Therefore all fresh-domain sensitivity, high-SNR protection and binary-challenge qualification claims remain unmeasured.",
        '',f"Cumulative charged scientific time was {cost['cumulative_charged_hours']:.4f} / 48 hours, including the P11 carry and all controller failures/stalls. P11.5 job wall expenditure was {cost['actual_experiment_job_wall_seconds']/3600:.3f} hours across parallel jobs. Sampled process-tree CPU was {cost['actual_experiment_sampled_process_tree_cpu_seconds']/3600:.3f} CPU-hours; its sampling-tail limitation is recorded. Acquisition was {cost['cumulative_acquisition_bytes']:,} / 15,000,000,000 bytes cumulatively. Final free disk was {cost['free_disk_bytes']/1e9:.2f} GB.",
        '', 'The finite policy table, paired wins/losses, host intervals, natural multiplicity, exact controls, physical completeness and attempt receipts remain available in the accompanying reports and JSON evidence. Natural survivors are not all proven false positives.', '',endpoint,'',claims]
    save('DECISION_P11_5.md',decision)
    handoff=['# P11.5 closed handoff','',f'Final state: **{state}**. '+header,'',completion,'',
        'All owned P11.5 scientific queues are closed. Original P10/P11 controllers and sealed evidence remain unchanged. No scheduled continuation, full discovery survey, reserved TCE-ephemeris exercise, submission or push occurred.',
        '', 'The versioned implementation is in `src/tesshunter/p11_5_detector.py`, `p11_5_search.py` and final `p11_5_clocal_v2.py`; the first C implementation remains as `p11_5_clocal.py`. Isolated orchestration/evaluation is in `p11/p11_5/protocol/`. Per-case source/input identities, failed attempts and timing receipts remain durable. New scientific arrays and models are in `data/survey/p11/p11_5/` and indexed by the final data seal.',
        '', 'Reproduction uses the recorded Python environment. Completed outputs are immutable; do not rerun fixed-path writers over this evidence. Reproduce in a separate isolated P11.5 revision with matching input/source hashes, or use the tests and read-only hash checks. The executed phase manifests and owning-controller receipts record exact commands.',
        '', 'Scoped Git attributes preserve the exact bytes of the new P11.5 source and evidence despite the checkout\'s automatic line-ending conversion setting. The source-directory attribute pattern applies only to `p11_5_*.py` and its own attribute file; existing named scientific configurations retain their prior bytes and behavior.',
        '', 'Core commands, in their original execution order:', '', '```powershell',
        'python p11/p11_5/protocol/cost_selection.py',
        'python p11/p11_5/protocol/development_handoff.py',
        'python p11/p11_5/protocol/controller.py p11/p11_5/manifests/development_input_jobs.json --workers 24 --timeout 300',
        'python p11/p11_5/protocol/flow_controller.py development_complete --series p11/p11_5/manifests/development_series.json --candidates p11/p11_5/manifests/control_A.json --workers 24 --stages ASBC',
        'python p11/p11_5/protocol/recover_controller_interruption.py',
        'python p11/p11_5/protocol/bounded_launch_v2.py development_complete_v2 p11/p11_5/protocol/flow_controller_v2.py development_complete_v2 --series p11/p11_5/manifests/development_series.json --candidates p11/p11_5/manifests/control_A.json --workers 24 --stages ASB',
        'python p11/p11_5/protocol/reconcile_operational.py',
        'python p11/p11_5/protocol/prerequisite_completion.py prerequisite_completion_after_development_v2',
        'python p11/p11_5/protocol/reconcile_operational_v2.py',
        'python p11/p11_5/protocol/prerequisite_completion.py prerequisite_completion_after_deadline_precedence_v1',
        'python p11/p11_5/protocol/c_v2_handoff.py',
        'python p11/p11_5/protocol/c_v2_plan.py pilot',
        'python p11/p11_5/protocol/bounded_launch_v2.py c_v2_memory_pilot p11/p11_5/protocol/controller_v2.py p11/p11_5/manifests/c_v2_memory_pilot_jobs.json --workers 1 --timeout 600',
        'python p11/p11_5/protocol/reconcile_operational_v2.py',
        'python p11/p11_5/protocol/c_v2_plan.py remaining',
        '# The full-plain-archive preflight above refused storage; its receipt is preserved.',
        'python p11/p11_5/protocol/bounded_launch_v2.py c_v2_storage_pilot p11/p11_5/protocol/controller_v2.py p11/p11_5/manifests/c_v2_storage_pilot_jobs.json --workers 1 --timeout 300',
        'python p11/p11_5/protocol/c_v2_storage_plan.py register',
        'python p11/p11_5/protocol/c_v2_storage_plan.py C 1',
        'python p11/p11_5/protocol/bounded_launch_v2.py c_v2_batch_01 p11/p11_5/protocol/controller_v2.py p11/p11_5/manifests/c_v2_batch_01_jobs.json --workers 24 --timeout 600',
        'python p11/p11_5/protocol/reconcile_operational_v2.py',
        'python p11/p11_5/protocol/c_v2_storage_plan.py PACK 1',
        'python p11/p11_5/protocol/bounded_launch_v2.py c_v2_pack_batch_01 p11/p11_5/protocol/controller_v2.py p11/p11_5/manifests/c_v2_pack_batch_01_jobs.json --workers 24 --timeout 300',
        f"# Repeat the frozen C/reconcile/PACK sequence for indices 2 through {len(storage['batches'])}; use the packing worker count returned by each preflight.",
        'python p11/p11_5/protocol/reconcile_operational_v2.py',
        'python -m pytest tests p11/tests p11/p11_5/tests -q',
        'python p11/p11_5/protocol/evaluate.py freeze regression_before_prediction_freeze_v3',
        'python p11/p11_5/protocol/evaluate.py evaluate',
        'python p11/p11_5/protocol/sensitivity_tables.py',
        'python p11/p11_5/protocol/plot_development.py',
        'python p11/p11_5/protocol/population_final.py',
        '```','', 'No eligible development finalist exists. A future fresh validation run must follow a new eligible frozen development result and the original full-domain criteria; reusing these exposed hosts does not create a holdout. See the measured admission failures and costed next-step evidence.', '',endpoint]
    save('HANDOFF_P11_5.md',handoff)
    save('RESUME_P11_5.md',['# P11.5 closed','',f'**{state}**. '+header,'',
        f"Completed selected search {r['selected_search']} and all 36 joint policies. No eligible finalist; no fresh holdout drawn or scored. Cumulative science charge {cost['cumulative_charged_hours']:.4f}/48 hours. All P11.5 jobs closed; no continuation schedule. Read DECISION_P11_5.md and HANDOFF_P11_5.md before any newly authorized work."])
    policy=ROOT/'INPUT_POLICY_P11_5.md';text=policy.read_text(encoding='utf-8').split('\n## Final evaluated population')[0]
    policy.write_text(text+'\n## Final evaluated population\n\n'+header+'\n\n'+scope+'\n\nThe complete fixed population accounting is in `manifests/population_accounting_final.json`; computational nonselection and input ineligibility are distinct. No fresh validation cohort was admitted.\n',encoding='utf-8')
    print('six final reports written',state)

if __name__=='__main__':main(sys.argv[1])
