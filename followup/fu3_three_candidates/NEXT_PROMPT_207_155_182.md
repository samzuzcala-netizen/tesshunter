Do an intensive, skeptical, reproducible archival follow-up of three more TESS S1 batch-1 candidates, using the same
method as the FU3 follow-up of TIC 270573718 / 262843927 / 193718989:

- TIC 207432717: P = 43.4446 d, ~3.8 ppt, ~3.7 Re. FPP 8%, NFPP 0. Only 4 of 6 events kept; the fit covariance is singular.
- TIC 155949537: P = 38.8918 d, ~2.0 ppt, ~2.6 Re. FPP 0.9%. Only 3 events (S51, S77, S78); S78 pixels are missing.
- TIC 18229070: P = 22.9488 d, ~1.4 ppt, ~2.2 Re. FPP 66%, dominated by an eclipsing binary on TIC 18229066 (a K star
  23.6" away; it would need a 21% eclipse). The transit is long (5.9 h). The survey's Gaia scene was built around the
  WRONG star: a float-rounded Gaia ID picked a G = 20 source 32" away. The true target is Gaia DR3 4602156143129990272
  (G = 13.14), so every packet localization for this star is invalid and must be redone.

Do not presume any of them is planetary, and report unfavourable or null results as prominently as favourable ones.

Template to follow (read these first):
- C:\Users\seanj\Documents\TESS_followup_262_193_270: PROTOCOL.md, code\ (s00-s22, events.py, pixels.py, prf.py,
  reductions.py), and report\FU3_three_candidates.html. Reuse the code, but work in a NEW folder
  (C:\Users\seanj\Documents\TESS_followup_207_155_182) with its own PROTOCOL.md, frozen before any new epoch is examined.
  Leave the FU3 folder unchanged.
- Batch-1 review of all 23 candidates: C:\Users\seanj\Documents\Codex\2026-10-18\look-at-the-results-of-batch
  (batch1_rankings.json, candidate_judgments.json).
- Packets: D:\tesshunter_s1\packets\s1_b1\tic207432717_P43.4471, tic155949537_P38.8999, tic18229070_P22.9484.
- Quick triage already done: FU3 results\other16_triage.json and results\gaia_id_audit_b1.json.

Cover the same ground as FU3:
1. Inventory with hashes; inputs read-only (never write under D:\tesshunter_s1 or the repo).
2. Archive census, keeping failure separate from absence: TOI/CTOI/TCE, sectors after 98, ZTF/ATLAS/ASAS-SN, Gaia
   flags, and spectra.
3. Per-event depths and timing in many reductions (PDCSAP, SAP, TGLC, own pixel apertures/PRF), calibrated by
   injection and null epochs; recover missing sectors' pixels where possible.
4. Host localization: injection-calibrated difference images on the target and on every flux-capable neighbour, plus
   a flux budget for 1.5-3 px apertures. For 18229070 this is the decisive test.
5. Shape (k-profiles with dilution free, ρ★ / eccentricity), odd/even and phase-0.5 checks, a 2P search beyond 50 d,
   Gaia RV limits, the colour-magnitude over-luminosity check (s22), and a TRICERATOPS scenario audit.
6. Selection: where each signal sits in its star's discovery funnel (s08b).

Deliverables: a report with one chapter per star and a synthesis (tier recommendation, the smallest decisive new
observation), plus tables, figures, tests and manifests. Publish the report as an artifact. Make no observing requests.

Environment notes:
- Python: C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe. Run child processes at normal priority (the live
  S1 survey starves below-normal ones). Do not touch D:\tess_fu3_cache\replay.
- Gaia TAP: async results are silently capped at 50,000 rows, so slice queries. Use INNER JOIN ... USING for 2MASS (a
  LEFT OUTER JOIN times out). Read Gaia IDs as strings, never floats.
- Fixed-template timing errors are heavy-tailed: calibrate with periodic injections. Free-shape fits need bounds and
  outlier clipping.
