# Diagnostic history

- Before measurements: froze `config.json` after recovering original input
  conventions. The saved survey, forced TLS, blind TLS and physical-fit widths
  are not interchangeable.
- Initial sector 63 run: first-order reference registration converged within
  its bounds. The initial injection position estimator maximized the amplitude
  divided by a noisy per-position control standard deviation. Even strong
  exact-model injections had offsets of 0.1-0.3 pixel. Replaced the position
  estimator by the spatial likelihood maximum; empirical controls still set
  significance. This is a validation-driven correction, before examination of
  the other sectors. The target sector-63 flux measurement is unchanged.
- Initial full run stopped at sector 61: the CCD2 archive also contains
  `tess-prf-phot-*` 33x33 images. The generic filename filter selected an
  incompatible file. Restricted retrieval to the documented 117x117 mission
  commissioning PRFs `tess2019*`. The rejected file is preserved in `archive/`.
- TESScut CADENCENO is zero in the inspected files. Exposure matching uses a
  unique nearest QLP time within 90 seconds (less than half the 200-second
  cadence), and records the measured offsets and match count. QLP target
  barycentric times replace CCD-centre TESScut times only for matched exposures.
- Quality convention reconciliation: plain SPOC 17087 ignored QLP's 2^30
  low-precision flag. A conservative all-nonzero QLP experiment then removed
  valid 2^29-only cadences. Both complete attempts are preserved separately.
  Verified the inherited `audit_prep.quality_mask` implementation and official
  QLP documentation; the final primary union uses 17087 plus 2^30 for these
  sectors. This was a correction of input semantics; no depth cut was used.
  The raw FITS and saved audit NPZ quality arrays and times agree exactly.
- Catalogue retrieval initially requested an incorrect OGLE photometry subpath
  and received HTTP 404. The successful canonical path is `phot/I/`; the failed
  receipt remains in `measurements_initial_qlp_bitmask/` and the current receipt
  records the successful request. Cached source content is reused by default.
- Final figure review found that a four-colour plotting loop omitted the fifth
  source selected across the three injection sectors. The plot now includes all
  sources and explicitly labels trials that exceed an estimated stellar flux as
  spatial stress tests. Empty time bins now break lines at observing gaps. These
  display corrections do not change event measurements or injection recovery.
