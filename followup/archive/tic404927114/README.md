# TIC 404927114 scientific follow-up

This directory is separate from P8. Inputs in `data/survey/p8`, its rules, verdicts
and packets are read-only. `config.json` records diagnostic choices before new
pixel measurements. Failures and sensitivity runs remain part of the evidence.

From the repository root, use the existing astronomy environment. Run the steps
in this order; the pixel extraction and spatial injections are the slowest step.

```powershell
$followupPython = 'C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe'
& $followupPython -X utf8 followups/tic404927114/run_followup.py
& $followupPython -X utf8 followups/tic404927114/catalogue_followup.py
& $followupPython -X utf8 followups/tic404927114/lightcurve_followup.py
& $followupPython -X utf8 followups/tic404927114/summarize_followup.py
& $followupPython -X utf8 followups/tic404927114/validate_and_sensitivity.py
& $followupPython -X utf8 followups/tic404927114/independent_checks.py
& $followupPython -X utf8 followups/tic404927114/final_figures.py
& $followupPython -X utf8 followups/tic404927114/verify_followup.py
```

Scripts resolve the repository from their own location. They require the original
P8 records, the 12 cached target TESScut files, and all 22 cached QLP FITS products
in their existing repository paths. The deliverable does not duplicate those
large original observations. Their paths and SHA-256 hashes are recorded in
`audit_manifest.json`; the exported copy of this directory should be placed back
under `followups/tic404927114` in that repository for a full rerun.

The validated environment uses Python 3.13.3, NumPy 2.5.1, SciPy 1.18.0,
Astropy 8.0.1, pandas, matplotlib, requests and batman-package. Exact installed
versions are recorded by verification. Public PRFs, Gaia responses, OGLE data
and mission timing tables are cached in `archive/`. The default uses these
frozen responses. `catalogue_followup.py --refresh` deliberately requests new
catalogue content and should be treated as a new comparison. A first run without
the cache requires network access. No survey or verdict-writing code is invoked.

The first script supports `--sectors 63 90 98` for a subset and `--resume` for
already completed sectors. These are convenience modes, not a substitute for a
complete run. `run_manifest.json` describes the inputs touched during that
invocation; the final `audit_manifest.json` is the comprehensive inventory.

Key products:

- `measurements/pixel_events.csv`, `pixel_summary.json` and the sector JSON/NPZ
  files retain all predicted events, their masks, individual contrasts and controls.
- `measurements/stacked_localization.npz` contains sky-coordinate maps and the
  empirical distribution of control maxima. There is no significant localized
  source and therefore no claimed source-position confidence ellipse.
- `measurements/injections_with_physical_limits.csv` distinguishes physically
  possible flux losses from spatial stress tests. The large faint-source trials
  must not be interpreted as possible eclipses. `physical_event_injections.csv`
  tests the saved transit shape and real 50% neighbour eclipses.
- `measurements/qlp_events.csv`, `older_ephemeris_grid.csv` and
  `gaia_epoch_photometry.csv` retain the additional-epoch checks.
- `figures/` contains the individual events, background images, source maps,
  controls, validation and independent photometry.
- `measurements/verification.json` records numerical, provenance and preservation
  checks. It is generated before the final hashed manifest.

`measurements_initial_qlp_bitmask/` and `measurements_all_nonzero_qlp/` preserve
superseded quality experiments. `diagnostic_history.md` explains the amendments;
the primary mask is documented in `config_amendment_quality.json`. These folders
must not be mixed with the final `measurements/` results.

All depths, source fluxes and error bars depend on the stated PRF/background
model. Exact-model injection increments are a linear-estimator identity; the
altered-PRF and blind position tests provide the meaningful robustness evidence.
Control tails describe this diagnostic, not a blind transit-search false-alarm
probability. The scientific disposition is **UNRESOLVED**, with background and
correction effects favored. See `../../docs/TIC404927114_FOLLOWUP.md` for the full
evidence and the observation needed to resolve the remaining ambiguity.
