# P9 amendments, before primary scoring

## 1. Recording adapter repair

The timing pilot initially retained accepted search signals and stage records but
did not retain every rejected BLS/alias trial because default logging was WARNING.
No pilot truth scoring has been run. Add INFO logging and append-only trial
records around the unchanged BLS and alias functions. Preserve the original pilot
directory as timing-only evidence, and repeat its controls with the final sample
under the same repaired recording adapter before primary scoring. The production
code, gates, grids and scientific decisions are unchanged; the additional I/O can
affect a wall-budget-limited search, which is why the repeat is primary.

The operational wrapper now treats returned ERROR records as execution errors,
not successful processes, and records adapter hashes per attempt. The original
adapter versions are archived. Scientific FAIL is never retried.

## 2. Independently labelled blends

Before any of these supplementary controls execute, add four hosts from the
existing frozen ExoFOP FP frame whose TFOP comments explicitly say a nearby EB
was confirmed or the object was retired as NEB. Selection uses the same seed/hash
order, excludes already selected hosts, and requires the same period, duration,
magnitude and delivered-sector coverage. Record the exact comment and ExoFOP page;
this is a TFOP follow-up catalogue label, not a label inferred from TessHunter.
Exclude comments that merely speculate about a possible NEB without a final
retirement/confirmation. These four are fixed regardless of pilot runtime and
are reported separately from the MAST EB catalogue controls.

Generic variability in an FP-host comment does not establish that the labelled
signal itself is a variable-star false positive; no such relabelling is permitted.
Likewise no P8 rejected signal is an independently labelled instrumental control.
If no independently attributable instrumental/variable-signal labels are secured,
those cells remain explicitly uncalibrated.

## 3. Preparation ahead of runtime sizing

Raw products and ordinary sky data can be downloaded for the maximum registered
44-host pool while the two expensive pilot C jobs run. Nonpilot search/vetting
waits for final runtime sizing and manifest freeze. Unused preparation-pool hosts
are explicitly listed and have no primary outcomes.

## 4. Replay cache validation and preparation clarification

Before nonpilot execution or primary scoring, allow reuse of pilot downstream
measurements after the instrumented primary search reproduces the entire accepted
candidate and vetting lists exactly, with identical stellar, raw, and sanitized
sky inputs. Hash the old and new results and all reused measurements. A difference
in any accepted signal invalidates that host's downstream reuse. The search replay
itself always remains primary, including any wall-budget effect of trace I/O.

Opportunity eligibility counts finite flux as well as finite timestamps, consistently
with post-lock matching. This is a data-availability clarification before the final
inputs freeze, not a recovery-based exclusion. Final truth rows retain their original
signal strata and separately record host sampling strata for cluster resampling.
The supplementary blend truth replaces the corresponding uncertain catalogue row;
other signals on a blend host retain their independent labels.

The timeout-cleanup dependency psutil 7.2.2 was installed after the pilot began;
it does not enter scientific calculations. Record it as an execution environment
supplement to the initial dependency snapshot. No timeout had occurred before this
repair.

## 5. Two-minute coverage parser repair, before final freeze and scoring

The original preparation parser expected `_sNNN` filenames for both target-list
directories. MIT two-minute caches are named `sNNN.npy`, so all two-minute counts
in the original frame were incorrectly zero. A pilot's actual SPOC products exposed
this discrepancy. The original frame, selection priority and pilot remain preserved.
The corrected inventory uses all 50 sector-56–105 MIT lists and intersects two-minute
sectors with delivered FFI sectors, as production does.

Keep every originally selected control and the original host sampling strata; do
not replace any control based on outcomes. The original `p8_proxy` sampling stratum
must be described as the cool/faint stellar oversample, with its minority-cadence
condition unverified at selection. It still contains every potentially overlapping
host in that stellar frame because the error only broadened the proxy group.
Strict P8 overlap uses the corrected inventory, ordinary TIC/Gaia cuts and actual
products. Report the change in overlap explicitly and do not use the original
proxy name to imply FFI representativeness. This reduces the scope of valid inference,
without changing a scientific gate or silently removing a difficult target.
