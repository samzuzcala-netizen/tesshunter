"""Record the original P10 stop decision from sealed calibration and yield outputs."""
from __future__ import annotations

import csv
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'p10/protocol'))
import run_part2d_yield_projection as Y

OUT = Y.OUT
LABELS = {
    'search_only': 'Search only',
    'search_and_pregate': 'Search + pre-gate',
    'search_and_stageA': 'Search + A',
    'search_and_stageA_and_secondary': 'Search + A + S',
    'full_funnel_with_pregate': 'Search + pre-gate + A + S',
}


def interval(level, metric):
    fit = level['logistic']
    low, high = fit[metric + '_16_84']
    return f'{fit[metric]:.2f} [{low:.2f}, {high:.2f}]'


def write_exclusive(path, text):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)


def main():
    assert Y.section_zero_sha() == Y.FROZEN
    p8_path = REPO / 'data/survey/p8/completeness_p8.json'
    p10_path = Y.CAL / 'completeness_p10.json'
    csv_path = Y.CAL / 'injection_outcomes_p10.csv'
    projection_path = OUT / 'expected_yield_projection_p10.json'
    seal_path = OUT / 'full_calibration_closed_seal_20260912.json'
    p8, p10 = Y.read(p8_path), Y.read(p10_path)
    projection, seal = Y.read(projection_path), Y.read(seal_path)
    assert seal['status'] == 'full_calibration_closed_verified'
    assert projection['status'] == 'closed_projection_verified'
    sealed = {r['path']: r['sha256'] for r in seal['files']}
    for path in (p10_path, csv_path):
        assert Y.sha(path) == sealed[path.relative_to(REPO).as_posix()]
    for level in LABELS:
        assert p8['levels'][level]['n'] == p10['levels'][level]['n'] == 2100
        assert p10['levels'][level]['logistic']['n_boot'] == 1000
    rows = list(csv.DictReader(csv_path.open(newline='', encoding='utf-8')))
    truth = lambda row, key: row[key] == 'True'
    assert len(rows) == len({r['job_id'] for r in rows}) == 2100
    sequential = [2100, sum(truth(r, 'recovered') for r in rows),
                  sum(truth(r, 'through_pregate') for r in rows),
                  sum(truth(r, 'through_pregate') and truth(r, 'through_stageA') for r in rows),
                  sum(truth(r, 'through_funnel_pregated') for r in rows)]
    assert sequential == [2100, 1240, 1184, 1141, 952]
    through_s = p10['levels']['search_and_stageA_and_secondary']['logistic']
    full = p10['levels']['full_funnel_with_pregate']['logistic']
    stop = through_s['snr50'] > 14.0 or projection['C_load_expectation_range'][1] > 150
    assert stop and full['snr50'] > 14.0
    table = ['| Level | P8 through / 2,100 | P10 through / 2,100 | P8 SNR50 [16–84%] | P10 SNR50 [16–84%] | P8 SNR90 [16–84%] | P10 SNR90 [16–84%] |',
             '|---|---:|---:|---|---|---|---|']
    for key, label in LABELS.items():
        before, after = p8['levels'][key], p10['levels'][key]
        table.append(f"| {label} | {before['n_through']:,} | {after['n_through']:,} | {interval(before, 'snr50')} | {interval(after, 'snr50')} | {interval(before, 'snr90')} | {interval(after, 'snr90')} |")
    table_text = '\n'.join(table)
    decision = {'utc': Y.utc(), 'status': 'STOP_RULE_1_FAILED', 'proceed_to_parts_3_to_5': False,
        'frozen_section_0_sha256': Y.FROZEN,
        'SNR50_S': {'level': 'search_and_stageA_and_secondary',
            'baseline': p8['levels']['search_and_stageA_and_secondary']['logistic']['snr50'],
            'measured': through_s['snr50'], 'bootstrap_16_84': through_s['snr50_16_84'],
            'limit': 14., 'passes': False},
        'full_funnel_including_pregate': {'baseline': p8['levels']['full_funnel_with_pregate']['logistic']['snr50'],
            'measured': full['snr50'], 'bootstrap_16_84': full['snr50_16_84'], 'also_above_limit': True},
        'nomenclature': 'Frozen section 0.5 names the original 20.19 after-A/S level; earlier operational prose used the pre-gated level. Both are reported and both fail; the frozen rule is unchanged.',
        'C_load': {'range': projection['C_load_expectation_range'], 'limit': 150.,
                   'passes_by_sufficient_upper_bound': projection['C_load_expectation_range'][1] <= 150.,
                   'range_is_not_a_confidence_interval': True},
        'FA_S': {'count': 2, 'stars': 300, 'rate': 2 / 300, 'times_2531': 2 / 300 * 2531},
        'sequential_injection_counts': dict(zip(('injected', 'recovered', 'pre_gate', 'A_after_pre_gate', 'S_after_pre_gate_and_A'), sequential)),
        'stage_A_all_recovered': {'pass': 1164, 'fail': 76, 'error': 0},
        'stage_S_all_A_passers': {'pass': 964, 'fail': 200, 'false_kill_fraction': 200 / 1164},
        'five_levels': {key: {'p8': p8['levels'][key], 'p10': p10['levels'][key]} for key in LABELS},
        'yield_projection': projection,
        'inputs_sha256': {p.relative_to(REPO).as_posix(): Y.sha(p) for p in
                          (p8_path, p10_path, csv_path, projection_path, seal_path, Y.MODEL / 'closed_seal.json')},
        'report_generator_sha256': Y.sha(__file__),
        'execution_boundary': 'Parts 3–5 were not run; no new real/held-out outcomes or TCE ephemerides were opened. Stop and pause the existing heartbeat.'}
    Y.save(OUT / 'stop_rule_1_decision.json', decision)
    es_low, es_high = projection['signal_expectation_range']
    load_low, load_high = projection['C_load_expectation_range']
    report = f'''# P10 stopped at the original recovery threshold

Decision recorded {decision['utc']}. **Stop Rule 1 fails: after-A/S SNR50 is {through_s['snr50']:.2f} [{through_s['snr50_16_84'][0]:.2f}, {through_s['snr50_16_84'][1]:.2f}], above the required 14.0.** The projected workload passes, at {load_low:.2f}–{load_high:.2f} expected C runs under the frozen central model and population bound, below 150. Both requirements must pass. The repairs improve recovery, but the original rule does not justify proceeding to Parts 3–5.

The final action is to preserve and commit this evidence and pause the existing two-hour heartbeat. Parts 3–5 remain unexecuted. Nothing here is a detection or a confirmation.

## Complete calibration

All 2,100 original injections on the same seeded 300 stars completed successfully: 1,240 recovered, 765 missed and 95 aliases. Aliases are not credited. The selected search is e, frozen as `survey_p10`; 600 selected-e searches were reused byte-for-byte and 1,500 ran with identical effective configuration. Fresh A/S records name `p10.0` and `survey_p10`. The full seal covers 15,583 files / 7,915,270,129 bytes. The checked controller closed at {seal['controller_completed_utc']}; no calibration owner or lock remains.

Every level uses 2,100 injections. Brackets are the original algorithm's 16th–84th percentiles from 1,000 individual-injection bootstrap resamples.

{table_text}

**SNR50 naming is explicit.** Frozen HANDOFF section 0.5 says “from 20.19,” identifying search + A + S without the pre-gate: 20.19 → 18.26. Earlier operational prose called the whole pre-gated funnel SNR50_S; that separate curve changes 20.44 → 18.63 [18.05, 19.32]. Both fail 14.0. The frozen section and its original threshold are unchanged. The yield calculation uses the original P8 machinery's pre-gated whole-funnel curve.

![P8 and P10 recovery thresholds](snr50_comparison.png)

## Residual losses

The exact sequential path is **2,100 injected → 1,240 recovered → 1,184 pre-gate → 1,141 A → 952 S**. Search loses 860 (including the 95 aliases); the following steps remove 56, 43 and 189 respectively. These sequential counts differ from the diagnostic A/S levels that omit the pre-gate.

Across every recovered injection, A passes 1,164 and rejects 76, with no errors. Bound S rejects another **200/1,164 = {200 / 1164:.2%}** of the A passers, retaining 964. The pre-gate removes 12 of those 964. Relative to P8, search gains 77 recoveries and the pre-gated full funnel gains 56 (896 → 952, or 42.67% → 45.33%). The after-A SNR50 reaches 13.05, while adding S raises it to 18.26. The retained secondary gate is the main remaining downstream sensitivity loss. Its false-kill fraction is nearly the P8 value, 189/1,093 = 17.29%.

The selected secondary mode remains `bound`: it was the only Part 2a mode that passed the frozen negative-control requirement. A failures can overlap: kept events <3 (12), top-event share >50% (19), inconsistent depths (32), kept SNR <7 (31), SNR without the top event <5 (22), and depth outside 0.5–2 times survey depth (9). No threshold was relaxed after observing these losses.

The full-search median/p90/maximum wall times are 444.35/1,284.28/1,681.88 s; 463 jobs hit a detection budget. Median/p90 A times are 100.15/517.11 s and S times 4.40/13.50 s. Search timing includes the preserved 600 selected-e executions and later full-search executions; it is not a fresh paired hardware benchmark.

## False alarms and projected workload

The original 300-star selected-e control search has 3,494 accepted candidates, 709 through the pre-gate, 45 A passers and **2 A+S survivors**. All 709 A and 111 S records validate. The 111 S records include 66 seeded A-failure controls; those are excluded from FA_S. Their 41 S passes are not counted as false-alarm survivors. FA_S = 2/300 = 0.006667 per star, giving **16.873333** for 2,531 stars. Every A/S key and decision matches the earlier selected-e p8.0 comparison.

| Quantity under the recorded model | Expected signals/runs |
|---|---:|
| Original 2,000 stars, central DC15 model through the pre-gated A/S funnel | {projection['original_2000_new_signals']:.6f} |
| Original 2,000 stars, search-only diagnostic | {projection['original_2000_search_only_new_signals']:.6f} |
| Original 2,000 stars, HU19 occurrence sensitivity through the funnel | {projection['original_2000_HU19_sensitivity_new_signals']:.6f} |
| Up to 531 additional stars, central-model signal upper bound | {projection['additional_signal_upper_bound']:.6f} |
| Prospective population, central-model E_S bounding range | {es_low:.6f}–{es_high:.6f} |
| FA_S × 2,531 | 16.873333 |
| Projected C load, central-model bounding range | {load_low:.6f}–{load_high:.6f} |
| Original C-load limit | 150 |

The original P8/DC15 numerical machinery was used with the new recovery curve and a fixed claimed fraction of 0.03 for every detectability class. All 2,000 original per-star prepared-noise files were copied byte-for-byte into an isolated P10 model root, rechecked after execution, and left unchanged. The original geometry, occurrence cells, contamination fill, limb darkening and four-point impact grid remain in use. The legacy low/mid/high fields are identical because their claimed fractions are identical; they are not uncertainty bounds. The engine's explicitly renamed P8 legacy “yield ≥3” diagnostic does not determine P10 continuation.

The additional stars lack measured noise in this calibration. The upper endpoint therefore adds the 531 largest nonnegative geometric signal weights from the entire 1,837-star bare-SPOC-only source pool, assuming perfect recovery. This bounds any eventual subset of at most 531 without selecting that subset or opening its TCE ephemerides or candidate outcomes. It is a sufficient bound for the central-model load criterion, **not a point estimate, confidence interval or bound on the realized candidate count**. The previously recorded all-population perfect-recovery bound, 148.931096 C runs, also lies below 150.

## Repairs, compatibility and limits

Part 2a retains bound S; Part 2b selects e / `survey_p10_both` and freezes its effective fields as `survey_p10`. Part 2c retains strongest-peak rule (a), with conditional robust fallback and the one-cadence duration floor. All comparative (b) conditions passed, but three of seven half/double controls pass both rules, so the original absolute alias-failure requirement prevents adopting (b). This pre-existing limitation remains disclosed. Selected injection-C retention is 24/30: 8/10 at SNR [7,12), 6/10 at [12,20), 10/10 at [20,50). Each corrected EB comparison has 16 PASS and 25 FAIL, with no new FAIL-to-PASS flip; only HIP 97166 b changes under fallback among the native development cases.

The EB controls retain their original catalogue-windowed development exposure; they are not a blind holdout. The two TIC 92743594 controls lie outside the inherited blind grid and do not establish successful alias rejection. The excluded sector-filtered EB attempts, exact-unit correction and thirteenth injection's suspension-inflated raw timers remain preserved.

P7 reproduces 823 records across all 16 slices with 0 field differences, 0 decision differences and worst relative difference 0.0; 2,513 P6 input hashes are unchanged. The seeded P8 cached replay is 20/20 byte-identical. A separate fresh replay is scientifically identical but 0/20 byte-identical because timestamps and measured runtimes differ. The latest full regression passed 774 tests, with 1 skipped and 9 warnings; ten subsequent schema-guard/routing checks and three load-bound checks passed. Thirteen final yield, bound and legacy-yield checks passed (one known optional lightkurve dependency warning). No full unchanged-source baseline was repeated at periodic checks.

The original calibration controller's validation guard compared the Stage A writer schema against rule-summary metadata. The checked successor corrected only that guard after exact owner closure, validated and reused every completed A record, then finished S and injection analysis. The numerical thresholds and original worker outputs did not change. Its original failed-guard diagnostics remain part of the provenance.

Bootstrap intervals resample individual injections and do not model within-star dependence, population uncertainty or model misspecification. The logistic crossing is an SNR-marginal fit. The fixed FA extrapolation has sampling uncertainty. HU19 is an inherited occurrence-box rescaling sensitivity, including its radius-distribution and spectral-type assumptions, and does not replace the frozen central DC15 criterion. Later B/C/D losses and final candidate counts remain unknown. P8/P9 records, frozen section 0, candidate identities and exposure boundaries are preserved.

## Evidence

Repository: `C:\\Users\\seanj\\Downloads\\tess-exoplanet-candidate-hunter\\tess-exoplanet-candidate-hunter`, branch `improve/recovery`.

- `p10/results/part2d_calibration_20260912/stop_rule_1_decision.json`: exact decision, level tables, input hashes and loss counts.
- `full_calibration_closed_seal_20260912.json` in the same directory: every scientific artifact and verified controller closure.
- `expected_yield_projection_p10.json` and `yield_model/`: measured yield, noise provenance, execution log and closed model seal.
- `COMPLETENESS_P10.md`: all SNR/period/radius/magnitude/rotation bins and failure diagnostics.
- `docs/RULES.md` section 9: accumulated rule choices and full calibration.
- `HANDOFF_P10.md` / `RESUME_P10.md`: final stop and operational entry point; older execution entries are historical.

Frozen section 0 SHA-256: `{Y.FROZEN}`.
'''
    write_exclusive(OUT / 'STOP_RULE_1.md', report)
    write_exclusive(OUT / 'level_comparison_p8_p10.md', table_text + '\n')
    # A standard scientific figure, rather than a generated illustration.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})
    fig, ax = plt.subplots(figsize=(11.5, 5.7), constrained_layout=True)
    y = np.arange(len(LABELS))
    for data, offset, color, label in ((p8, -.13, '#67778b', 'P8'), (p10, .13, '#007f86', 'P10')):
        fits = [data['levels'][key]['logistic'] for key in LABELS]
        centers = np.array([f['snr50'] for f in fits])
        errors = np.array([[f['snr50'] - f['snr50_16_84'][0], f['snr50_16_84'][1] - f['snr50']] for f in fits]).T
        ax.errorbar(centers, y + offset, xerr=errors, fmt='o', markersize=7, capsize=4,
                    color=color, label=label, linewidth=2)
        for center, yi in zip(centers, y + offset):
            ax.text(center + 1.0, yi, f'{center:.2f}', va='center', fontsize=10, color=color)
    ax.axvline(14, color='#bb4141', linestyle='--', linewidth=1.5)
    ax.text(14.1, -.55, 'Required after-S SNR50 ≤ 14', color='#9c3333', fontsize=10)
    ax.set_yticks(y, list(LABELS.values()))
    ax.invert_yaxis()
    ax.set_xlim(10, 24)
    ax.set_xlabel('Expected SNR at 50% fitted recovery — lower is better')
    ax.set_title('P10 improves recovery; the after-S threshold still fails', loc='left', pad=23, weight='bold')
    ax.grid(axis='x', alpha=.15)
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.legend(loc='lower right', frameon=False)
    fig.savefig(OUT / 'snr50_comparison.png', dpi=180)
    fig.savefig(OUT / 'snr50_comparison.svg')
    plt.close(fig)
    print(f'STOP: after-S SNR50={through_s["snr50"]:.8f}; central C-load range={load_low:.8f}–{load_high:.8f}')


if __name__ == '__main__':
    main()
