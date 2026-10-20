"""Build the scientific audit from final locked measurements and reviewed evidence.

Narrative limitations are explicit; numerical tables are generated from metrics.
This script never edits a blind output, truth manifest or scientific gate.
"""
from common import *
import collections, math
import pandas as pd
from scoring import GATES
from tables import table, percent, interval


def count_table(cohort):
    rows=[]
    for gate,s in cohort['gates'].items():
        rows.append([gate,f'{s["k"]}/{s["n"]}',percent(s['rate']),interval(s['scientific_Wilson95_envelope']),
          interval(s['scientific_host_bootstrap95_envelope']),f'{s["k"]}/{s["conditional_n"]}',
          percent(s['conditional_rate']),interval(s['scientific_conditional_Wilson95_envelope'])])
    return table(['Gate','Unconditional','Observed rate','Wilson 95% / unknown envelope','Host bootstrap 95% / envelope',
      'Conditional','Observed rate','Conditional Wilson 95% / envelope'],rows)


def figures(df):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    pos=df[(df.label=='positive')&(df.eligibility=='eligible')]
    fig,ax=plt.subplots(1,2,figsize=(13,max(6.5,0.25*len(pos))),layout='constrained')
    colors={'search':'#9D493B','pre':'#CE8153','A':'#B2903B','S':'#8E6B91','B':'#73546E','C':'#50628A',
      'C_signal_switch':'#50628A','D':'#376D83','retained':'#327551'}
    display={'search':'Search match','C':'Native C gate','C_signal_switch':'C identity (duration)','D':'Final review','retained':'Useful retained'}
    for term,g in pos.groupby('first_termination'):
        good=g.snr_expected.notna() & (g.snr_expected>0)
        g=g[good]
        ax[0].scatter(g.period,g.snr_expected,s=48,c=colors.get(term,'#666666'),label=f'{display.get(term,term)} (n={len(g)})',edgecolor='white',linewidth=.6)
    for threshold in [7.1,12,20,50]:
        ax[0].axhline(threshold,color='#777777',lw=.65,ls='--',alpha=.5)
    ax[0].set(xscale='log',yscale='log',xlabel='Published orbital period (days)',ylabel='Expected model SNR',
      title='Post-lock covariates exist for misses and recoveries')
    ax[0].legend(fontsize=8,loc='best');ax[0].grid(alpha=.15)
    x=np.arange(len(pos));order=pos.sort_values(['snr_expected','truth_id'])
    kept=np.array([bool(v) for v in order.D_useful]);found=np.array([bool(v) for v in order.search])
    ax[1].barh(x,order.snr_expected.clip(upper=200),color=np.where(kept,'#327551',np.where(found,'#376D83','#9D493B')))
    ax[1].set_yticks(x,order.truth_id,fontsize=8.3);ax[1].set(xscale='log',xlabel='Expected model SNR (display capped at 200)',
      title='All selected confirmed planets')
    ax[1].grid(axis='x',alpha=.15)
    fig.suptitle('P9 sensitivity context — selected known planets; no transported P8 efficiency',fontsize=12)
    fig.savefig(P9/'figures/signal_domain.png',dpi=180);plt.close(fig)


def run():
    ver=read(P9/'results/verification.json')
    if ver['status']!='PASS' or ver['pending_hosts']:raise RuntimeError('Final evidence must verify first')
    m=read(P9/'results/metrics.json');c=read(P9/'results/census.json');comp=read(P9/'results/analytic_comparison.json')
    scores=read(P9/'results/scored_signals.json');df=pd.read_csv(P9/'results/analysis_table.csv')
    pos=m['cohorts']['positive_all'];neg=m['cohorts']['negative_exact_or_registered_alias'];unc=m['cohorts']['uncertain_descriptive']
    ps=[s for s in scores if s['label']=='positive'];loss=collections.Counter(s['first_termination'] for s in ps)
    features={f['truth_id']:f for f in read(P9/'results/diagnostic_features.json')}
    misses=[s for s in ps if s['first_termination']=='search']
    weakmiss=sum(features[s['truth_id']].get('snr_expected') is not None and features[s['truth_id']]['snr_expected']<7.1 for s in misses)
    primary_ops=[s for s in scores if s.get('operational')]
    reuse=read(P9/'results/pilot_cache_reuse.json');runtime=read(P9/'protocol/final_sampling_lock.json')
    audit_flags=read(P9/'results/catalogue_flag_audit.json');B=audit_flags['signals']
    negative_timing=read(P9/'results/negative_timing_audit.json')
    historical_caps=read(P9/'results/historical_B_caps.json')
    bcap=sum(r.get('max_verdict')=='HOLD' for r in B)
    b_depth_neighbours=sum((r.get('n_possible_neighbours_at_this_depth_diagnostic') or 0)>0 for r in B)
    cand=read(P9/'results/candidate_ledger.json');final=[r for r in cand if r.get('D')]
    npfinal=sum(bool(r.get('final_fit_truth_associations')) for r in final)
    aux=c['auxiliary_fixed_aperture_availability'];auxbad=[a for a in aux if a.get('available_sectors',0)<a.get('n_sectors',1)]
    nraw=len(read(P9/'protocol/final_inputs_lock.json')['input_hashes'])
    commit=(P9/'baseline/commit.txt').read_text().strip()
    products=df.groupby('label').product_group.value_counts().to_dict()
    final_counts=pos['gates'];useful=final_counts['D_useful'];submit=final_counts['D_submit']
    nonuseful=sum(s.get('verdict')=='HOLD' and not s['D_useful'] for s in ps)
    allheld=[s for s in ps if s.get('verdict')=='HOLD']
    operation_table=table(['Stage','Outcome','Operations'],[[r['stage'],r['status'],r['n']] for r in c['operation_counts']])
    loss_table=table(['First termination / useful retention','Signals','Distinct hosts'],[[k,n,len({s['tic_id'] for s in ps if s['first_termination']==k})] for k,n in loss.items()])
    negative_table=[]
    for name,e in m['cohorts'].items():
        if name.startswith('negative_family_') and name!='negative_family_operational_complete':
            negative_table.append([name.removeprefix('negative_family_'),e['n_signals'],e['n_hosts'],*[e['gates'][g]['k'] for g in GATES],
              max(s['n_operational_unknown'] for s in e['gates'].values())])
    verdict_rows=[]
    for r in final:
        root=P9/'results/blind'/f'tic{r["tic_id"]}';f=read(root/'final'/f'{r["key"]}.json')
        verdict_rows.append([f'[{r["key"]}](../p9/results/blind/tic{r["tic_id"]}/final/{r["key"]}.json)',
          r.get('final_fit_truth_associations') or 'No labelled signal association',r['D'],
          'yes' if f.get('legitimate_useful_hold') else 'no',f.get('hold_reason') or f.get('reason')])
    yield_rows=pd.read_csv(P9/'results/yield_scenarios.csv')
    ym=yield_rows[(yield_rows.occurrence_assumption=='DC15_adopted_giants')&(yield_rows.incumbent_assumption=='mid')]
    ym_table=table(['Assumed late B/C/D retention','Expected final new submissions','P(0), conditional Poisson'],
      [[f'{r.late_retention:.2f}',f'{r.expected_new_submit_equivalent:.3f}',f'{r.probability_zero_conditional_Poisson:.6g}'] for r in ym.itertuples()])
    sample_table=table(['Cohort','Eligible signals','Independent hosts'],[['Confirmed/validated planets',pos['n_signals'],pos['n_hosts']],
      ['MAST EB: lower-morphology subgroup',6,6],['MAST EB: higher-morphology subgroup',6,6],['TFOP-confirmed nearby EB blends',4,4],
      ['Uncertain TOI PCs',unc['n_signals'],unc['n_hosts']],['Total',len(scores),c['n_hosts']]])
    strata_table=table(['Positive sampling stratum','Signals','Hosts'],[[k,v['n_signals'],v['n_hosts']] for k,v in m['stratification']['stratum'].items()])
    snr_table=table(['Expected model SNR','Signals / hosts','Exact search','Correct C','Useful final','SUBMIT-equivalent'],
      [[k,f'{v["n_signals"]} / {v["n_hosts"]}',*[f'{v["gates"][g]["k"]}/{v["n_signals"]}' for g in ['search','C','D_useful','D_submit']]]
        for k,v in m['stratification']['snr_bin'].items()])
    protocol_hash=sha(P9/'protocol/PREREGISTRATION.md');runner_hash=sha(P9/'runner.py')
    prose=f'''# P9: external validity and full-funnel completeness

Final evidence as of {utc()}. Baseline commit `{commit}`.

The frozen pipeline met the registered period-and-event match for **{final_counts['search']['k']}/{pos['n_signals']} confirmed planets** in the selected observations, retained **{final_counts['C']['k']}** on their correct nested signal paths through blind TLS, and produced **{submit['k']} scientific SUBMIT-equivalents** and **{useful['k']} useful retained outcomes**. Actual new-discovery eligibility is zero for every control. There are {len(misses)} failures of the registered search match; {weakmiss} have expected model SNR below 7.1. The TOI-849 b ephemeris exception below separates a matching limitation from a physical search miss. These are measurements of this selected external sample, not estimates for all planets in TessHunter's intended detection domain.

**The P8 null remains insufficient to distinguish an unfavorable undiscovered population from low full-funnel efficiency.** The selected sample has {m['cohorts']['positive_strict_P8_actual_products']['n_hosts']} confirmed-planet hosts meeting strict corrected P8 targeting and product overlap, and the registered analytic comparison has {comp['n_supported_real_hosts']} supported external hosts. The principal measured early loss is search sensitivity at weak signal levels. Among detected planets, the gate and final-review losses below identify specific limitations; they do not establish one universal cause of P8's zero submissions. No gate was tuned, no new survey was launched, and no object was submitted.

## What was frozen and what P8 actually measures

The checkout was at P8 commit `fbc68571`; [initial Git status](../p9/baseline/initial_status.txt) records existing untracked follow-up work. All {len(read(P9/'baseline/preserved_hashes.json'))} preserved P8/follow-up evidence files remain byte-identical. Scientific imports use {len(read(P9/'baseline/source_hashes.json'))} archived files, with [source hashes](../p9/baseline/source_hashes.json), [configuration](../p9/baseline/configuration.json), dependencies and command receipts. No live scientific source or P8 verdict was edited.

P8's historical flow is 2,000 stars → 13,252 accepted search signals → 3,688 pre-gate → 189 A → 19 secondary → 19 B → 6 C → 0 SUBMIT, 2 HOLD, 4 KILL. Its 2,100 flux injections on 300 hosts calibrated the early funnel through secondary. The approximately 11.7 expected new signals is an early-funnel model expectation, not an expected final submission count. Historical documents remain [AUDIT_P8.md](AUDIT_P8.md), [COMPLETENESS_P8.md](COMPLETENESS_P8.md) and [POPULATION_P8.md](POPULATION_P8.md).

There is a direct procedural explanation for the **recorded** submission ceiling: {historical_caps['n_B_capped_HOLD']}/{historical_caps['n_B']} historical B candidates, including all {historical_caps['n_C_pass']} C survivors, already carried a maximum verdict of HOLD. The [read-only historical cap audit](../p9/results/historical_B_caps.json) includes copies of the original B/C/D records. Under the frozen rule, none of these six paths could become a submission while its B flags stood. D then documented separate source/background problems and retained the historical two HOLDs and four KILLs. This establishes what constrained the recorded decision, not that the caps were astrophysically mistaken or that uncapped candidates would have been planets. It does not estimate the frequency of justified caps in an undiscovered population.

The verified [implementation map](../p9/protocol/PIPELINE_MAP.md) records source locations, thresholds, aliases, missing-data branches and manual decisions. The main scientific sequence is:

| Gate | Frozen decision and relevant limitation |
|---|---|
| Search | 0.5–30 d, 0.02–0.20 d duration, 200 s harmonization, BLS/alias resolution, raw and resolved SNR ≥5, event completeness ≥0.5, composite score ≥3. The preset has a 900 s partitioned wall budget and at most 12 merged signals. |
| Pre | Whole-stitch epoch consistency, SNR ≥7.1 and at least three observed transits. It is explicitly separate from A. |
| A | Transit-aware preparation and narrow TLS around the blind search seed; ≥3 kept events, kept SNR ≥7, strongest-event share ≤0.5, SNR without strongest ≥5, depth 0.5–2 times survey, constant-depth p ≥0.001. Event artifact removals and red-noise inflation are unchanged. |
| Secondary | Reject a measured off-phase SAP dip exceeding the planetary secondary bound by >3 sigma. This can operate on busy variable light curves. |
| B | Phase-independent sector non-detection can reject; Gaia/VSX, possible contaminating sources and another deep accepted signal can cap final verdict at HOLD. A cap permits C. |
| C | Independent TLS from 0.5–110 d, strongest SDE ≥9 and period agreement; special 2:1 aliases require depth consistency. Another stronger signal can terminate the registered planet's path. |
| D | Accepted-C physical fit, density-prior comparison, FPP, all available pixel-sector evidence and explicit unblinded review. Provisional SUBMIT is insufficient. A useful HOLD requires coherent transit evidence and a specific resolvable limitation; missing execution or generic unresolved status does not qualify. |

The product preference remains SPOC → TESS-SPOC → QLP; finer products are harmonized to 200 s and products too coarse are dropped under native rules. There are {c['selected_product_count']} selected products: {c['selected_product_authors']}. The target-list frame covers sectors 56–105, while the scientific preset has only a sector minimum. TIC 172421004 includes the authentic special sector 1751; its mission provenance and interruptions are documented in [PRODUCT_NOTES.md](../p9/docs/PRODUCT_NOTES.md). It is retained under the frozen input rule. No truth period is used to restrict a search.

## Samples, provenance and coverage

{sample_table}

All 48 selected hosts had prepared light curves, ordinary stellar data and sanitized scientific sky inputs. All 51 selected signals had at least three pre-execution observed transit opportunities; there were no silent outcome-based removals or replacement controls. The broader catalogue frame, exclusions and unavailable truth fields are recorded in [census.json](../p9/results/census.json), [sampling_frame.csv](../p9/truth/sampling_frame.csv) and the selection logs. Frame exclusions are nonexclusive; catalogue entries outside the eligibility cuts are not failed pipeline controls.

Positive truth comes from the NASA Exoplanet Archive default transiting-planet solutions with controversy flag zero, with primary discovery/validation references retained in [PRIMARY_SOURCES.md](../p9/truth/PRIMARY_SOURCES.md). It includes recent TOI publications and older validated Kepler planets; recency never substitutes for independent labels. Binary truth is from the independently curated [MAST TESS EB catalogue](https://archive.stsci.edu/hlsp/tess-ebs), described by [Prša et al.](https://arxiv.org/abs/2110.13382). Its morphology subgroups are approximate binary shapes, not certain source-localization classes. Four supplementary blends have explicit TFOP/ExoFOP nearby-EB confirmation or retirement comments. Uncertain TOI PCs remain separate; CTOI-only objects were not selected. Independent instrumental false positives and variable-star signals outside the EB/ellipsoidal catalogue remain uncalibrated. Pipeline rejection was never used as their truth label.

Sampling uses SHA256 host ordering with seed 20260907; every frame-eligible planet on a selected host is a separate target. A deterministic 25% development / 75% holdout assignment is retained and no tuning used either group. The prespecified six-host runtime pilot supported the default sample size. Its median search+A host cost was 162.8 s and longest C measurement was 2,040.2 s, below the 1,800 s and 7,200 s reduction triggers. Four blend hosts were separately frozen before their execution. Precision was expected to be coarse (roughly ±17–21 percentage points before clustering), not a definitive population calibration.

{strata_table}

**A preparation error materially limits transport.** The original two-minute target-list parser missed `sNNN.npy` files, assigning zero counts. The error was diagnosed before final freeze/scoring; the original frame and all selected controls were preserved. The corrected 50-sector inventory shows that all 13 hosts in the original cool/faint stellar oversample have majority two-minute targeting. The retained internal identifier `p8_proxy` therefore does not mean a verified P8-like FFI sample. Strict overlap additionally checks ordinary TIC/Gaia stellar criteria, Galactic latitude and actual products. There are {m['cohorts']['positive_strict_P8_targeting']['n_hosts']} strict P8 targeting hosts and {m['cohorts']['positive_strict_P8_actual_products']['n_hosts']} strict targeting-plus-product hosts in the selected positive sample. This is not a claim that no known P8-like planet exists anywhere.

The EB and blend frame is broader in stellar properties than P8; several negative hosts are hot or large stars. Their rejection and runtime measurements are useful stress tests but do not establish specificity for cool P8 dwarfs. Known planets are also a discovery-selected population. Matching observables alone would not remove that selection bias.

## Leakage, replay and operational completion

All 48 ordinary six-catalogue exclusions were REJECT and are preserved on the truth side. The external-validation wrapper bypasses known-status exclusion only for scientific eligibility. It preserves stellar information, Gaia astrometry/photometry, crowding, generic variability and source counts, while removing answer-bearing names, classes and orbital solutions. Classification redaction, omission of the extra per-TIC catalogue cone-resolution path and a pinned six-source snapshot are disclosed departures from production. The independent scientific neighbour queries remain active.

Automated execution is ephemeris-blind; **manual adjudication is unblinded** because this investigating session constructed truth. Empty packet roots, a Python audit hook against truth/historical files, allowed-field manifests and recorded payloads support the process boundary; it is not an OS sandbox or independent blinded replication. FPP and TESScut queries use blind accepted ephemerides and permitted stellar inputs. Detailed routes and limitations are in [LEAKAGE_AUDIT.md](../p9/LEAKAGE_AUDIT.md).

The original pilot omitted rejected BLS/alias traces. It was preserved, and all primary searches were instrumented replays. Five pilot hosts reused downstream measurements only after their entire accepted-signal and vetting lists and every scientific input were identical. TIC 177079323 changed from six to eight accepted signals in the wall-budget replay and its downstream results were rerun. This establishes timing sensitivity of the actual search; reproducible inputs do not guarantee bit-identical wall-budget outcomes across hardware.

The registered limits were four search/A workers, two C workers with eight TLS workers each, and two D workers. Outer limits are 1,800 s search, 3,600 s A, 900 s secondary/B, 36,000 s C and 14,400 s D, with one same-input retry for execution exceptions/timeouts. Scientific FAIL is never retried. Background dispatch only advances permitted successors. Sum of new primary operation wall times is {c['measured_seconds_new_primary']/3600:.2f} process-hours; reused pilot measurement wall time is {c['reused_measurement_seconds']/3600:.2f} hours. These sums are neither elapsed clock time nor CPU-hours.

{operation_table}

The [runtime breakdown](../p9/results/runtime_by_stage_and_label.csv) separates stages, control classes and completed versus exhausted operations, including retries and reused pilot measurements. Timeout durations are censored costs, not completed scientific runtimes. The initial pilot did not capture the full C runtime tail: at least one completed primary C check took over three hours, compared with the pilot maximum of about thirty-four minutes. Future planning should budget from these observed tails and preserve the distinction between computation cost and scientific efficiency.

There are {len(primary_ops)} operationally unresolved **exact primary labelled-signal paths**. The negative alias-family table independently includes failures on any matching alias. A missing operation is an unknown scientific outcome, not a rejected planet or false positive. [TABLES.md](../p9/TABLES.md) gives intention-to-run logical bounds, Wilson and host-bootstrap envelopes, and completed-only estimates. Completed-only subsets can be selected by computational difficulty.

Native D measurements and the auxiliary fixed-aperture review have separate availability. {len(auxbad)}/{len(aux)} final candidates have at least one unavailable fixed-aperture sector under the unchanged clean-sky requirement; details are in the census. Presentation repairs report these failures without relaxing the sky mask. Zero-error centroid entries for TIC 389900760 sector 85 and TIC 178709444 sector 99 are excluded from the native weighted centroids; their available pixels were reviewed before verdict lock. All earlier locked reviews were checked for this omission, and subsequent reviews use every available pixel sector. Missing auxiliary flux does not become a no-contamination measurement.

## Signal-level full-funnel results

Primary recovery requires a period within 1% and at least three one-to-one matched observed centers, covering at least 50% of both truth and found opportunities within half the sum of their durations. Candidate choice uses matched events, normalized timing residual, then blind candidate number before considering downstream survival. Each accepted A/C/D ephemeris is rechecked. Half/double/triple-period aliases are separately reported and cannot rescue exact planet completeness. Another signal on a planet host never inherits its truth label.

{count_table(pos)}

Both D branches use C as their conditional denominator. For each final branch, the computed product of defined conditional rates equals the direct nested count; undefined 0/0 is kept undefined. Full conditional host-bootstrap intervals, subtype tables and operational envelopes are in [TABLES.md](../p9/TABLES.md) and [metrics.json](../p9/results/metrics.json).

Uncertainty uses marginal Wilson 95% intervals and 5,000 whole-host resamples within frozen sampling strata, keeping planets sharing a host together. A degenerate zero/one bootstrap is not certainty. The independent exchangeable-host exact 95% interval/envelope for **any SUBMIT-equivalent per host** is {interval(submit['host_any_possible_survival_exact95_envelope'])}; this is a different estimand from per-planet completeness. Intervals describe this selected sample and do not correct discovery selection or unsupported covariate coverage.

![Full-funnel measurements and first losses](../p9/figures/funnel_and_losses.png)

Negative controls are reported both at the exact labelled period and as the union of exact plus registered aliases. The latter avoids calling an EB safely rejected merely because its half-period was recovered. These counts exclude unrelated signals on the same host; a failure to recover the labelled signal is not evidence that every artifact on its host was rejected. The deliberately selected positive/negative ratio does not estimate the purity of a future survey's candidate list.

{table(['Negative subtype (exact/alias family)','Signals','Hosts',*GATES,'Max unresolved'],negative_table)}

Overall negative exact/alias SUBMIT-equivalent survival is {neg['gates']['D_submit']['k']}/{neg['n_signals']}, with a Wilson/operational 95% envelope of {interval(neg['gates']['D_submit']['scientific_Wilson95_envelope'])}. Small-sample zero survival is not perfect specificity. Where no negative reaches a gate, that gate's conditional discriminating power is unmeasured; early rejection does not calibrate the later gate. Uncertain TOIs have {unc['gates']['search']['k']}/{unc['n_signals']} exact search recoveries, {unc['gates']['C']['k']} nested C survivals and {unc['gates']['D_useful']['k']} useful outcomes; those are descriptive signal results and do not establish planet truth.

Nominal binary ephemerides and finite event counts also limit matching. A close half-period can narrowly miss the fixed 50% event fraction, and some catalogue timing uncertainties are large over the later TESS baseline. The original EB truth CSV omitted available error columns; the post-lock audit retrieves them from the frozen catalogue without rewriting the manifest or primary results. [NEGATIVE_AUDIT.md](../p9/NEGATIVE_AUDIT.md) and the [truth notes](../p9/docs/NEGATIVE_TRUTH_NOTES.md) document the effect. As a conservative check, allowing **any** candidate on each negative-control host plus unresolved execution gives possible escape upper counts of {negative_timing['bounds']['C']['possible_host_candidate_upper']} at C, {negative_timing['bounds']['D_submit']['possible_host_candidate_upper']} at SUBMIT-equivalent and {negative_timing['bounds']['D_useful']['possible_host_candidate_upper']} at useful retention, each out of {neg['n_signals']}. These are identification bounds, not relabelled false positives or a new efficiency estimate. The audit distinguishes whether a possible escape is measured or operationally unknown. Sampling intervals conditional on nominal matching do not eliminate truth-timing ambiguity.

Every blind accepted candidate was processed when its predecessors permitted: {c['n_accepted_signals']} accepted → {c['n_pre']} pre → {c['candidate_survival']['A']} A → {c['candidate_survival']['S']} secondary → {c['candidate_survival']['B']} B → {c['candidate_survival']['C']} C. Candidate verdict counts are {dict(c['final_candidate_verdicts'])}. Search-level and final-fit truth associations are separate in [candidate_ledger.csv](../p9/results/candidate_ledger.csv); the count of final candidates without an independently labelled signal association under the registered rule is {len(final)-npfinal}. Late association cannot repair a broken nested recovery path.

## Final reviews and positive loss census

{table(['Blind candidate / evidence','Post-lock final-fit truth association','Scientific verdict','Useful HOLD','Reason category'],verdict_rows)}

Final source judgments use the saved fit, FPP scenarios, centroids, sector differences and available raw-aperture evidence. The [final evidence summary](../p9/results/final_evidence_summary.csv) collects fitted radii/impact parameters, fit improvement, FPP/NFPP, source counts and centroid significance for direct comparison. FPP is conditional on astrophysical scenario assumptions, an approximate circular aperture and the first three sectors. It is neither an instrumental-artifact probability nor a substitute for resolving crowded source positions. Numerically zero FPP is not certainty. A target-vicinity dimming patch can justify a specific source-follow-up HOLD without identifying an individual Gaia star; no actual submission is permitted. Useful-HOLD counts depend on this recorded unblinded adjudication. No independent second-reviewer agreement or reviewer-error calibration was measured, and the sampling intervals do not include that uncertainty.

Stage B imposes HOLD caps on {bcap}/{len(B)} candidates reaching B. [The post-lock catalogue audit](../p9/results/catalogue_flag_audit.json) retains each native host-summary neighbour count and a diagnostic count at the individual candidate depth, plus raw VSX classes/separations. Native B asks whether a neighbour can mimic any surviving host signal, so its host summary can be more restrictive than a single candidate's depth. At the individual candidate depth, {b_depth_neighbours}/{len(B)} still have at least one capable neighbour; a smaller count alone does not remove a cap. Deep signals can also be aliases of each other. These observations motivate an independent validation experiment, not a cap override in P9. Generic catalogue flags may partly reflect discovery history; their retained influence is a benchmark limitation. A standing B cap already precludes SUBMIT-equivalent, so final source-review limitations and B-cap effects cannot be uniquely apportioned from the observed zero.

{loss_table}

Each of the {pos['n_signals']} positive signals has a [complete autopsy card](../p9/AUTOPSIES.md) and diagnostic figure, including retained controls for comparison. Cards separate the first termination from event removal, wrong period/alias, strongest-peak competition, secondary evidence, physical-fit mismatch, FPP/source issues, TTV flags, ephemeris uncertainty and execution failure. They quote native evidence and never substitute a truth-ephemeris rescue. The machine-readable [loss census](../p9/results/loss_census.csv) and [failure autopsies](../p9/results/failure_autopsies.json) support this table.

For the {len(misses)} failures of the registered search match, {weakmiss} have expected SNR below the pre-gate's 7.1 scale. This supports weak-input sensitivity as a major loss in this sample; it does not show that every low-SNR miss is causally explained by noise alone. The expectation uses the same batman model norm divided by cadence MAD as P8, literature geometry, 200 s exposure integration and circular orbits. Missing impact parameters use 0.5. The box-depth expectation is retained separately. Real dilution, eccentricity, correlated noise, spot crossings and ephemeris covariance are not fully modeled. Published-timing A event checks are explicitly counterfactual and contain selection effects.

Eligibility required observed transit opportunities, not a minimum expected SNR. Thus the total-sample rate includes planets whose signals are too weak for a confident detection in these TESS data; it must not be called completeness above a guaranteed detection threshold. The preregistered SNR strata make that distinction visible. These post-lock model SNRs are diagnostic covariates, not the pipeline's measured search statistic. Per-cell uncertainty and host-cluster intervals are in the full tables.

{snr_table}

TOI-849 b is a **published-timing/matching limitation**, not established search insensitivity. The blind search finds 0.76553504 d, versus the frozen default 0.765548 d, but the default catalogue's propagated centers are 2.26–2.38 hours away from the detected events. The fixed event rule therefore matches zero of 110 opportunities. The default independent-error timing uncertainty reaches 2.71 transit durations; expected model SNR is 38.59. [The post-lock ephemeris audit](../p9/EPHEMERIS_AUDIT.md) lists every positive's timing context and retrieves all available archive solutions for this near-period mismatch.

The archive solution from the [Armstrong et al. discovery paper](https://arxiv.org/abs/2003.10314), at 0.76552414 d and BTJD 1394.73768, matches 110 of 111 truth opportunities and all 110 found opportunities. Using that solution solely to identify existing locked measurements gives a path through C to the already-recorded useful HOLD. Other archive solutions and their failures are also retained. No search, fit or review was rerun; the frozen truth and primary counts stay unchanged. This one-control sensitivity cannot calibrate a replacement matching protocol, and timing/label uncertainty is not included in the sampling intervals. Future truth preparation should choose and verify the precision of a consistent published period/epoch solution before outcomes are seen, rather than assuming that the archive default is always the best transit predictor.

![Published-timing sensitivity in the identical saved blind flux](../p9/figures/ephemeris_tic33595516_P0.7655_1.png)

LP 791-18 b is a material stronger-signal exception: expected model SNR is 13.74, and the published-timing event diagnostic gives kept SNR 10.22 with all six A criteria passing. In the locked blind search, four local near-period solutions pass internal gates but lose selection to higher composite scores. For example, chunk 0 pass 2 retains 10.232323 d at composite 5.33 over a near-0.9485 d solution at 5.20. The partitions then fill their three accepted slots; no wall-budget stop is recorded. The recorded choices identify search ranking/candidate limits as contributors, rather than an observed A rejection. Local period proximity and truth-timed diagnostics do not establish that an alternative blind full-stitch run would recover the planet. [SEARCH_AUDIT.md](../p9/SEARCH_AUDIT.md) also records a near-period ranking witness for low-expected-SNR Kepler-995 b; its proximity alone does not identify the signal. No ranking or capacity variant was tested, so its planet-retention benefit and negative-control cost remain unmeasured.

TOI-1470 c is a direct **C strongest-peak loss**. Its blind 18.08896-day search solution matches all three observed truth events and passes pre/A/secondary/B. Independent C finds a local peak at 18.08753 days with SDE 16.85, above the threshold of 9, but the strongest peak is the other planet's 2.52711-day signal at SDE 32.07. The longer-period signal ranks third, so native C rejects it and D is not permitted. Expected model SNR is 12.98; the published-timing event diagnostic retains all three events. The short-period planet's useful HOLD is a separate outcome and does not rescue c. This establishes a multi-planet competition failure in this control, without measuring the safety or benefit of a residual-search variant.

![A real planet rejected by C's strongest-peak requirement](../p9/figures/C_tic284441182_P18.0890.png)

HIP 97166 b exposes a different C limitation. Its strongest blind peak is the correct 10.28867-day signal, with TLS transit SNR 37.52 and 38 distinct transits, but global SDE is 3.56 and C requires 9. Expected model SNR is 69.62 and the published-timing event diagnostic has kept SNR 42.36. The [saved-spectrum audit](../p9/results/spectrum_normalization_audit.json) finds one extreme negative ordinate, -336.05 at 0.59462804 days, contributing **99.864% of the spectrum's centered variance** across 113,081 trial periods. The installed [TLS statistic implementation](../p9/calibration/tls_implementation/stats.py) normalizes detrended power by its global standard deviation. Thus this low global SDE has a specific normalization concern despite a strong recovered transit. The already-recorded narrow TLS diagnostic around the blind search seed has SDE 11.46; it is not independent C recovery and earns no primary credit.

The process completed and the native C FAIL remains in the primary ledger. The variance decomposition does not remove any ordinate, calculate a replacement SDE or advance the planet to D. Raw trial chi-square residuals were not saved, so the upstream origin of the extreme value remains unresolved. It could involve the trial fit or numerical/statistical handling; the evidence does not justify naming a specific solver bug or lowering the threshold. The audit covers every saved C spectrum after its host lock, allowing the concentration to be compared across controls.

![C's global statistic is dominated by one negative trial ordinate](../p9/figures/C_tic237222864_P10.2888.png)

TOI-1450 A b is the third primary C-stage loss, but **native C passed**. Its strongest period is correct, SDE is 28.57, and the frozen published timing is precise. TLS reports a duration of only **89.71 seconds**, shorter than the 200-second cadence. Using that duration in the registered event-coverage census admits 77 of 172 truth opportunities (44.77%), below the required 50%. The primary `C_signal_switch` category therefore records an identity-rule failure; it does not establish selection of a different physical signal.

[The post-lock duration audit](../p9/DURATION_AUDIT.md) inventories all 18 C records; this is the only sub-cadence duration. Holding C period and epoch fixed, the already-recorded A/native-D-window duration matches 171/172 opportunities, and the locked D fitted duration matches 172/172. The frozen native fit already uses the wider survey/C duration and independently returns a 0.989-hour transit with a useful HOLD. That existing final-fit association earns no nested primary credit. No stage was rerun, no duration floor or matching rule was changed, and the upstream origin of the short TLS duration is unresolved. This is a reported-duration/scoring limitation alongside the separate TOI-849 b truth-timing limitation; raw primary completeness should not be equated with physical signal sensitivity without these qualifications.

![Signal strength and observing-domain context](../p9/figures/signal_domain.png)

Prespecified marginal strata cover 1–2 / 2–4 Earth radii, 10–30-day periods, SNR, duration/opportunities, Tmag, temperature/radius, periodic-variability proxies, red-noise beta, crowding, sectors/products and TTV flags. All strata and missing values are in [TABLES.md](../p9/TABLES.md). Depth display bins were added after some partial scoring and are labelled exploratory. Rotation amplitude may include transit or instrumental structure; a catalogue TTV flag or uncertain ephemeris does not establish causality. Sparse cells are not fitted with an elaborate multivariate model. No population weights are assigned; ESS is unavailable and unsupported regions remain explicit.

## Analytic injections: comparison limits

The historical analytic experiment has {comp['n_injections']} signals on {comp['n_injection_hosts']} hosts. Original legacy counts are {comp['legacy_counts']}. Under the P9 event-matching and candidate-choice rule, observed counts are {comp['rescored_counts']}; missing downstream counts are {comp['rescored_missing_counts']}. Missing historical A/S records are bounded unknown outcomes, not manufactured failures. In particular, 79 newly credited pre-gate signals lack their corresponding historical A/S measurements. The old and new match rules are not nested, so changes in totals are scoring differences, not a new scientific pipeline result.

Registered matching requires period and radius ratios ≤1.5, SNR ratio ≤2, Tmag within 0.5, Teff within 300 K, stellar radius within 0.1 solar radii, sector counts within a factor of two, the same product-majority group and SPOC fraction within 0.25. At least five independent injection hosts per real signal, five real hosts per supported coarse cell and ten real hosts overall are required. The intersection yields {comp['n_real_with_five_injection_hosts']} real signals with five injection hosts and {comp['n_supported_real_hosts']} supported real hosts. See every caliper and intersection in [analytic_comparison.json](../p9/results/analytic_comparison.json).

Consequently, this experiment **cannot confirm or refute analytic-injection optimism under matched P8 conditions**. Unmatched SNR tables are descriptive and are not efficiency ratios. No validated real-signal transplantation was performed: donor noise separation, exposure integration, dilution transfer and spatial consistency were not established. Historical flux/SAP injections leave pixels unchanged and cannot calibrate localization, FPP or final D completeness. The independently observed real-control late-gate outcomes remain valid within their stated sample scope.

## Expected yield and the P8 zero

No supported external late-stage efficiency can be transported to P8. The reproducible [yield-stage bounds](../p9/results/yield_stage_bounds.csv) retain historical search and early-secondary expectations; pre and A lie between those nested endpoints, while B/C/final dispositions lie between zero and the early yield. HOLD and submission are separate final outcomes. These are logical/model-conditional bounds, not confidence intervals.

Occurrence, geometric transit probability, novelty/incumbent completeness, early detection efficiency and conditional late retention remain separate. The adopted DC15-plus-giant occurrence model has historical early-S expectations 8.087 / 11.675 / 14.924 under high / mid / low incumbent completeness. A HU19 normalization sensitivity gives 10.852 / 15.485 / 19.635. These are model alternatives, not posterior samples. P8's fitted early completeness and its uncertainty are retained in the saved historical yield payload; unsupported late calibration prevents a justified full predictive posterior.

For the middle incumbent assumption in the adopted occurrence model:

{ym_table}

The calculation is `lambda_final = lambda_early_S × q_late`, with `P(0 | scenario) = exp(-lambda_final)`. External end-to-end completeness is **not multiplied again** onto the calibrated early funnel. At late retention 0.1, zero submissions has conditional probability about 31%; at retention 1, it is about 0.00085%. Neither scenario has an empirically estimated probability weight here. Zero is therefore plausible under substantial late attrition, but P9 does not establish the predictive probability that applies to P8. Occurrence, novelty, calibration and population-selection uncertainties are not collapsed into a misleading precise final yield.

![Conditional yield scenarios](../p9/figures/yield_scenarios.png)

## Decisions before another large survey

1. Establish an independent control set in the actual corrected P8 FFI targeting/product domain, including weak 1–4 Earth-radius, 10–30-day signals. Validate the coverage parser and consistent published period/epoch precision before freezing a new sample; audit reported duration against cadence and event identity without assuming a replacement rule is already calibrated. Current selected known planets do not support P8 transport.
2. Calibrate B/C/D on that sample and on independently labelled EB, blend, variable and instrumental signals. Quantify the cost in negative-signal survival alongside any proposed gain in planet retention. The independently vetted FFI [TESS Ten Thousand catalogue](https://arxiv.org/abs/2506.05631) is a concrete source for a future negative frame, subject to verified stellar/product overlap. Broader hot/large-star negatives need separate runtime and domain reporting.
3. Audit per-trial TLS chi-square residuals and global SDE normalization, starting with the extreme 0.594628-day ordinate in HIP 97166 b's saved spectrum. Establish its upstream origin and evaluate any repair on both development positives and negatives before independent held-out testing. P9 performs no clipping, replacement statistic or rescue.
4. Validate a quantitative crowded-field source/background method and any treatment of centroid zero-error entries using real labelled sources and consistent spatial injections. Flux-only injections cannot support this decision. Preserve the current useful-HOLD distinction while that evidence is acquired.
5. Test search composite ranking/candidate capacity and C's strongest-peak requirement on development controls, including the observed LP 791-18 b and TOI-1470 c failure modes, followed by independent held-out evaluation. Any proposed event-consistency, B-cap or alias change likewise needs both planet-retention and negative-survival measurements. P9 changes no threshold and measures no variant's benefit or specificity cost.
6. Keep early yield separate from final eligibility and test novelty/incumbent assumptions for the proposed target population. Do not justify another 2,000-star run with the old 11.7 early-funnel expectation as if it were a submission forecast.

These are evidence-gathering recommendations, not validated gate changes. The measured sample identifies weak-signal search losses and specific downstream/source limitations; inadequate P8 overlap and small negative cells prevent attributing the historical null to population scarcity, overaggressive vetting or localization alone.

## Reproduction and integrity

[p9/README.md](../p9/README.md) contains the exact rerun sequence and evidence layout. [HANDOFF_P9.md](../HANDOFF_P9.md) records final status and continuation limits. Frozen protocol SHA256: `{protocol_hash}`. Scientific adapter SHA256: `{runner_hash}`. The final input lock covers {nraw} hashed input files plus execution/truth/eligibility and selected-product receipts. Per-host exact file locks precede their truth scores and final review evidence hashes are checked.

Baseline tests: 622 passed, 1 skipped; see [baseline_pytest.log](../p9/logs/baseline_pytest.log). P9 boundary/matching/operational tests and final integrity results are saved in [protocol_tests_final.log](../p9/logs/protocol_tests_final.log) and [verification.json](../p9/results/verification.json). Final integrity verification has {len(ver['checks'])} passing checks and no pending hosts. Scientific outputs, old verdicts and existing follow-ups remain preserved. The portable bundle has its own file manifest; verification of omitted historical repository files requires the full original workspace.
'''
    (REPO/'docs/AUDIT_P9.md').write_text(prose,encoding='utf-8')
    handoff=f'''# P9 handoff

Completed external-validation baseline at `{commit}`. Read [docs/AUDIT_P9.md](docs/AUDIT_P9.md) for interpretation and [p9/TABLES.md](p9/TABLES.md) for full numerical results.

- {c['n_hosts']} hosts, {len(scores)} eligible independently categorized signals; {pos['n_signals']} confirmed/validated planet signals on {pos['n_hosts']} hosts.
- Positive nested counts: {' → '.join(g+' '+str(pos['gates'][g]['k']) for g in GATES[:6])}; final SUBMIT-equivalent {submit['k']}, useful retained {useful['k']}. Every actual submission flag is false.
- Negative exact-or-alias family: {neg['n_signals']} labelled signals; final SUBMIT-equivalent {neg['gates']['D_submit']['k']}, useful {neg['gates']['D_useful']['k']}. Use unknown-outcome envelopes and completed-only tables when execution fails.
- {len(primary_ops)} unresolved exact labelled paths; operations, retries and auxiliary pixel availability are recorded separately.
- {len(misses)} positive search-match failures, including {weakmiss} with expected model SNR below 7.1. TOI-849 b is a documented published-timing exception, with no primary credit changed. Every positive has an autopsy.
- Strict corrected P8 product/targeting overlap: {m['cohorts']['positive_strict_P8_actual_products']['n_hosts']} hosts. Analytic matched comparison: {comp['inference_status']}. ESS and a transported P8 final-yield posterior are unavailable.
- All {len(ver['checks'])} final integrity checks pass; all 48 hosts locked. Original scientific source, P8 outcomes and pre-existing follow-ups remain unchanged.

The final inference is limited by sample/product coverage. Weak-signal search sensitivity is a major observed loss, with documented ranking and C strongest-peak exceptions. TOI-849 b fails the frozen timing match despite a locked useful signal; a post-lock published-solution audit identifies it without changing primary scores. HIP 97166 b also fails C despite the correct strongest period: one extreme negative trial ordinate dominates the global power variance. Its native FAIL remains; raw trial residuals are unavailable, and no replacement statistic was calculated. TOI-1450 A b also fails primary C identity because its reported duration is shorter than one cadence, despite native C PASS and a matching locked final fit; its primary score is unchanged. All six historical P8 C survivors already had B HOLD ceilings; subsequent D source/background judgments remain unchanged. This identifies the recorded submission constraint, but does not establish whether changing a cap would retain real planets safely or explain the astrophysical population. The old 11.7 is an early-secondary expectation; [yield scenarios](p9/results/yield_scenarios.csv) apply conditional late retention exactly once.

## Evidence and commands

Use the original Python environment recorded in [p9/baseline/environment.json](p9/baseline/environment.json), with the psutil supplement. Scientific execution imports [p9/baseline/source](p9/baseline/source). [p9/README.md](p9/README.md) gives full commands. Recompute from locked evidence with scoring → diagnostics → search audit → spectrum audit → ephemeris audit → ephemeris figures → duration audit → autopsies → failure figures → metrics → comparison → catalogue audit → historical caps → census → negative audit → tables → verify → report. Do not reopen or overwrite locked host trees.

The raw input/sky/truth manifests are separately hashed. The scientific runner has not changed since final sample freeze. Additional recording, scheduling, scoring and pixel-presentation repairs are disclosed in [AMENDMENTS.md](p9/protocol/AMENDMENTS.md), [SCORING_IMPLEMENTATION.md](p9/protocol/SCORING_IMPLEMENTATION.md) and [LEAKAGE_AUDIT.md](p9/LEAKAGE_AUDIT.md). Manual review is unblinded.

## What remains uncalibrated

No gate variant was evaluated; do not claim an improvement or specificity cost. No validated transplantation or spatial injection was performed. Independent instrumental/variable negatives outside the EB catalogue, representative P8 late-gate sensitivity, weighting and a full yield posterior remain unsupported. These are inference limitations, not unfinished permitted candidate stages.

Any future gate experiment or new sample belongs in a separate workspace with a fresh freeze and independent evaluation. No additional discovery survey or external submission is authorized by this handoff.
'''
    (REPO/'HANDOFF_P9.md').write_text(handoff,encoding='utf-8')
    figures(df)
    write(P9/'results/report_receipt.json',dict(utc=utc(),script_sha256=sha(Path(__file__)),
      sources={str(p.relative_to(P9)):sha(p) for p in [P9/'results/metrics.json',P9/'results/census.json',P9/'results/analytic_comparison.json',P9/'results/verification.json']},
      outputs={str(p.relative_to(REPO)):sha(p) for p in [REPO/'docs/AUDIT_P9.md',REPO/'HANDOFF_P9.md']}))
    print('Audit, handoff and sensitivity figure written',flush=True)


if __name__=='__main__':run()
