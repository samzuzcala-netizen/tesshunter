# P11 FINAL STOP — NO_QUALIFIED_GAIN; evaluation incomplete

Closed 2026-09-12T20:48:47.915532+00:00 at the declared data/input limit. No P11 science controller remains active. **Do not resume these completed audit queues or launch Parts B–D.** The required common 300-host/600-injection comparison is unavailable under the audited timing/coverage policy. Read DECISION_P11.md first, then INPUT_AUDIT.md and results/decision.json.

The 60-host audit is complete, including the preserved failed import attempt and corrected reader comparison. Final tests: 793 passed, one skipped. Historical P9/P10/raw content checks pass; P9's expected HEAD mismatch is preserved. No P10 controller or automation was started. There is no finalist, validation cohort, validation truth draw or performance claim.

All future efficacy work requires a separate reviewed protocol once authoritative/common inputs are available. Preserve all records, source snapshots, seeds, manifests and exposure ledgers. No automatic continuation is authorized.

## Durable evidence and reproduction

Repository is the original tess-exoplanet-candidate-hunter checkout. Use the verified existing `C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe`; no environment replacement was installed. The `protocol/` directory contains the runnable audit, metadata acquisition, provenance verification and analysis code. `protocol/registration_seal.json` preserves the prospective design; `protocol/MAIN_INPUT_POLICY.json` is the final input policy, not a validation freeze.

`results/input_inventory/` preserves the initial source-reader diagnostic; `input_inventory_v2/` reproduces Lightkurve's finite-TIME selection exactly. `results/noise/` and `noise_attempt1_stop.json` preserve the module-shadowing failure. The operationally corrected, source-sealed run is `results/noise_v2/`; its 60 completed timings are immutable. `instrument_noise_model.json` supplements the abbreviated header inventory. `peer_timing_quality_filtered.json` holds independent timing witnesses. The original maps and downloads are in `data/survey/p11/` and are sealed by `manifests/data_files.json`.

To verify on this existing checkout, run `python p11/protocol/integrity_check.py`. For a new compatibility receipt, use `python p11/protocol/entry_check.py --label <new-unique-label> --include-p11`; it preserves/restores the P9 verification file in a finally block. Completed source/measurement files should not be regenerated in place. The archive requires the original repository inputs identified by the recorded hashes; it is not a portable copy of every historical TESS FITS file.

The initial audit-magnitude subset includes 60 deliberate metadata selections, so its bootstrap describes that allocation. Small-aperture gain is descriptive and fails the depth/pixel qualification requirements. Later search, C, validation and endpoint results are unmeasured. The local execution commits only explicit P11 artifacts; no push is authorized.
