# P9 leakage and blindness audit

Automated search and vetting are ephemeris-blind. Manual adjudication is **unblinded**:
the investigating session prepared the sample, inspected catalogue labels and read
primary discovery sources. A process/input boundary reduces leakage; it is not an
OS sandbox or an independent blinded experiment.

## Data boundary

| Potential route | Handling and evidence |
|---|---|
| Published periods, epochs, durations, radii and dispositions | Kept in `truth/`. The execution CSV contains only TIC ID, stellar radius/mass/temperature/magnitude and position. Raw product preparation may use timing solely to establish pre-execution data eligibility. |
| Known-object hard stop | The original six-catalogue outcome is retained in `truth/exclusions/`. Execution receives a hash and explicit exclusion-bypassed flag, never a fabricated CLEAN outcome. The wrapper removes the status field from a copy only for the provisional scientific verdict. Actual submission eligibility is false. |
| Catalogue contamination checks | The ordinary Gaia position, photometry, astrometry, source counts and generic variability/VSX flags remain. Candidate-depth contamination limits are recomputed using all blind pre-gate survivors. Names, object classes and orbital parameters are redacted, with field-level logs in `truth/sky_redactions/`. The scientific effect of classification redaction is a disclosed departure from production, unavoidable if known EB/planet labels are to remain hidden. |
| Cached packets and period seeds | Execution packet roots start empty. Original repository `data/`, `docs/`, `followups/` and P9 `truth/` are denied by a Python file audit hook. Filenames use TIC IDs and blind fitted periods, not planet names. A starts only from the blind survey seed; C searches 0.5–110 d independently; D starts at the accepted C ephemeris. |
| Timing-pilot reuse | Instrumented primary searches are always new. Downstream reuse requires identical complete accepted-candidate and vetting lists, identical raw/stellar/sanitized-sky inputs, and recorded source/output hashes. Five of six hosts qualified; TIC 177079323 did not and its downstream stages were rerun. Its primary replay returned eight accepted signals versus six in the pilot. This is material evidence that a wall-budget-limited search is not bit-for-bit hardware/timing invariant. |
| TLS subprocesses | Numeric light-curve arrays and ordinary stellar parameters are passed to subprocesses. The Python audit hook is not an inherited security policy in every spawned interpreter; the payload and worker implementation were inspected. No truth manifest or published period is passed. |
| FPP and pixel services | Native TRICERATOPS and TESScut queries use TIC IDs, source positions/stellar photometry and the blind accepted ephemeris. Scenario calculations, stellar tables, settings and pixel source hashes are saved. FPP code does not import the truth catalogue or a published planet solution. A circular aperture and first-three-sector FPP approximation remain; pixels are reviewed across the available sectors. |
| Manual review | `reviews/` records evidence and rationale; `adjudicate.py` checks prior-gate eligibility, B/fit caps and evidence hashes. A useful HOLD requires a coherent transit, no demonstrated nonplanetary cause and a specific resolvable limitation. Known truth cannot override a cap. No claim of blinded manual reproducibility is made. |
| Truth-informed diagnostics | Scoring verifies a host's hash lock first. Diagnostics use separate `diagnostics/` directories and explicitly label known-ephemeris event analysis as counterfactual. No diagnostic rescue changes the blind verdict. Partial scoring includes only already locked hosts; final scoring requires all selected hosts locked. |

## Departures and scope limits

The frozen scientific source and thresholds remain unchanged. Adapter changes,
pilot replay and the four separately labelled blend controls are documented in
[AMENDMENTS.md](protocol/AMENDMENTS.md). The six-source production snapshot was
pinned rather than refreshed separately for each host. The original catalogue
check uses source coordinates but omits additional per-TIC cone resolution;
independent scientific Gaia neighbour queries remain active. All 48 prepared Gaia
inputs were available; the adapter's explicit missing-Gaia operational guard did
not affect any control.

The original two-minute inventory parser missed filenames of the form `sNNN.npy`.
The selected controls and original erroneous frame are preserved. Corrected
coverage is used for overlap analysis; the `p8_proxy` identifier means the original
cool/faint sampling stratum, not verified P8 FFI overlap. This error changes the
scope of valid transport to P8, even though it changes no signal's scientific gate.

The baseline dependency snapshot preceded addition of psutil 7.2.2 for timeout
cleanup. No timeout had occurred and no scientific dependency changed. Numerical
library threads, TLS worker limits, seeds, commands and wall times are recorded.
Native FPP retains its own seed 20260902; sampling/other P9 random operations use
20260907. Historical pilot code versions and operation receipts remain available.

Pixel presentation repairs are recorded in
[SCORING_IMPLEMENTATION.md](protocol/SCORING_IMPLEMENTATION.md). Every available
sector is reviewed, including a zero-error centroid sector excluded from the
native weighted average. Fixed-aperture failures due to insufficient clean sky
are explicit unavailable auxiliary measurements. Neither repair changes the
centroid calculation, difference images, sky mask or scientific verdict rubric.
The affected sector coverage was repaired before its host was adjudicated or
scored, and previously locked reviews were audited for the same omission.

`catalogue_audit.py` opens the unredacted catalogue classifications only after
each corresponding host is locked. It decomposes the recorded B caps and
candidate-depth limits without issuing an alternative verdict. Operational
timeouts are separately bounded unknown outcomes, with completed-only cohorts;
they are never treated as demonstrated rejection of a labelled false positive.

The post-lock negative timing audit retrieves period/epoch uncertainties that the
initial EB truth builder omitted from its frozen manifest. It uses the original
catalogue bytes and keeps nominal primary matching unchanged. Period proximity,
larger harmonics and host-wide candidate unions are labelled diagnostic bounds;
none supplies a truth-informed execution seed or an alternative blind verdict.

`verify.py` checks the archived source, original P8/follow-up files, input locks,
selection/protocol hashes, exact locked-output file censuses, downstream gate
eligibility and manual evidence. This audit can show that the implemented boundary
was followed; it cannot remove the selection bias of previously discovered planets
or the expectation bias of an unblinded final reviewer.
