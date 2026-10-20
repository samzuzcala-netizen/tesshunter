# FU3 public-archive census: TIC 270573718, TIC 262843927, TIC 193718989

Run 2026-10-18, 21:18-22:26 UTC. Availability and metadata only: no TESS light curve, TPF or TESScut cutout was
downloaded and nothing was fitted. Every HTTP request made by the census scripts has a receipt in `receipts/`
(659 receipts: 625 HTTP 200, 18 HTTP 400, 6 HTTP 403, 6 HTTP 500, 4 exceptions). Raw bodies are in
`D:\tess_fu3_cache\census_raw` (655 files, 264 MB, none larger than 9.5 MB; larger TCE files are kept as
header plus matching lines). Scripts: `code/census/` (c01-c15, cx_* helpers). Deliverables: `census_<tic>.json`,
`census_table.csv` (212 entries), `new_epochs.json`. Intermediate tables: `tables/`, `parts/`.
The web searches (task 12) ran through the assistant's search tool and have no local receipts; the queries are
logged in `parts/c14_web_search_log.json`.

Outcome codes follow the census rules. An empty catalogue result is coded NO_MATCH or NO_DATA, never as a
scientific negative, and the key_findings field says when a footprint or target list was not verified.

## 1. TESS data: what exists

State of MAST at census time (per-sector counts): SPOC FFIs through S109, TICA FFIs through S107, QLP light
curves through S104, TESS-SPOC light curves: 0 counted in S96-S100. TESScut now refuses `product='TICA'`
("Input product must be SPOC").

| | TIC 270573718 | TIC 262843927 | TIC 193718989 |
|---|---|---|---|
| TESScut (SPOC) sectors | the 23 discovery sectors only | discovery sectors plus **S31 (cam4/ccd2), S88 (cam4/ccd3)** | the 7 discovery sectors only |
| Any data in a sector > 98 | none | none | none |
| WTV / tess-point (to S121) | not on silicon S99-S121 | not on silicon S99-S121 | next on silicon **S117, S118, S119** (May-Jul 2027), no data yet |
| Sectors <= 98 not used by discovery | S97: TICA FFI footprint only (see below) | S31, S88: TESScut cutouts only, no pipeline light curve | none |

**TIC 262843927, S31 and S88.** TESScut lists both, and the SPOC FFI 4-corner footprints contain the position by
18.3 px (S31) and 22.8 px (S88). WTV/tess-point does not list either sector, and no QLP, TESS-SPOC, TARS or TGLC
product exists for them. A 4-corner polygon ignores the field distortion, so the on-silicon status is
**unresolved by metadata**. PROTOCOL.md section 6 records that the continuation's S31/S88 extractions were
gross failures. Coverage prediction (sector start/end only, gaps unknown, +/-0.25 d):
- S31 (BTJD 2144.514-2169.944): primary n=34 at 2152.491 (even n), phase-0.5 at 2164.546.
- S88 (BTJD 3690.145-3717.922): primary n=98 at 3695.463 (even n), phase-0.5 at 3707.517.

**TIC 270573718, S97.** The 15" cone returned only the TICA S97 cam4/ccd1 FFI, whose footprint contains the star by
6.2 px. The SPOC FFI tess-s0097-4-1 (same CCD, fetched by obs_id) excludes it by 26.9 px. TESScut and
WTV/tess-point do not list S97. If the star were on silicon, primary n=63 (3942.077, odd) and n=64 (3983.461,
even) and phase-0.5 at 3962.769 would fall inside the MAST S97 span (3933.653-3988.285).

MAST lists S97 and S98 with t_min/t_max spans of about 54.6 d and 57.4 d (for example, the QLP S98 product for
TIC 270573718 covers 3988.50-4045.90). These are recorded as given, not interpreted.

Other product families that exist for the discovery sectors but were not used by discovery are listed in
`new_epochs.json` (`unused_products_in_used_sectors`). They are the same photons (D-alt), not new epochs:
- 270573718: QLP S1-S68, TARS S1-S95, TGLC and GSFC-ELEANOR-LITE S1-S11, T16 S1-S7, TASOC S1-S6.
- 262843927: SPOC 2-min S1-S3 (spoc-5.0.10/5.0.11/5.0.20 reprocessing), TASOC 2-min (c0120) S1-S3 and FFI
  S1-S4, QLP S1-S69, TARS S1-S96, TGLC, GSFC-ELEANOR-LITE and T16 S1-S4.
- 193718989: QLP for all 7 sectors (S79 is the corrected v02 file), TARS for all 7, TASOC S26.

Version tags per sector, including TESS-SPOC data-release numbers 36-112, are in `tables/product_versions.csv`.

## 2. TCEs, DV, TOIs, CTOIs

- **SPOC TCEs:** none for any target in 57 tcestats files. These are every single-sector file for a sector with
  data plus every overlapping multi-sector run, up to s0001-s0096 (created 2026-06-01). The index page was last
  modified 2026-10-16. Only TIC 262843927 was ever a SPOC TPS target: it is in the 2-min rms-CDPP tables of S1,
  S2 and S3, but not in the s1-s92 or s1-s96 multi-sector CDPP tables. The other two stars are absent from all
  39 CDPP tables, so for them a missing TCE carries no information. Positive control: TOI-101 was found by the
  same code. No SPOC DV products exist on MAST for any target. No public QLP TCE list exists.
- **ExoFOP:** every PHP endpoint returned HTTP 200 with a literal `Array` body (download_toi/ctoi.php,
  target.php and its &json variant, gototicid, download_imaging/spect/tseries/stellar/planet/uploads/filelist/
  nearbytarget). The index and view_toi.php render `Array` as their page body. news.php works and carries no
  retirement notice (latest item 2026-09-15; CTOI uploads were paused on 2026-03-31 and reopened on 2026-08-19
  for published candidates). The documented pre-built tables do download:
  - json/tois.csv: 8151 rows, Last-Modified 2026-10-18 12:43 GMT.
  - json/ctois.csv: 5138 rows, 2026-10-18 11:04 GMT.
  - json/imaging.csv: 36,971 rows.
  - json/spect.csv: 34,775 rows.

  None lists a target, a TIC v8 neighbour within 2', or any entry within 2'. The nearest TOI is 43' away for
  270573718, 22' for 262843927 and 1.7 deg for 193718989. The nearest CTOI is 38', 77' and 79' away.
- **Other TOI sources:** the MAST TOI CSV (7913 rows, Last-Modified 2026-03-14) has none. The NASA Exoplanet
  Archive `toi` table (8151 rows, last rowupdate 2026-10-09) has no exact TIC match. Its cone queries were
  blocked by Cloudflare (HTTP 403) and were not retried.

## 3. Variability and eclipsing-binary catalogues (60" cones plus TIC queries)

- **TESS EB catalogues:** no entry within 60" and no TIC match in any of them: Prsa+2022, Justesen & Albrecht
  2021, Shi+2022, Tang+2025, Kostov+2025, Battley+2022 (CDIPS) and IJspeert+2021. The Guerrero+2021 TOI
  catalogue has none either.
- **Periodic-variable catalogues:** nothing within 60" in ASAS-SN II/366 (catv2021), ATLAS (Heinze+2018), ZTF
  periodic (Chen+2020; not applicable to the southern pair), WISE (Chen+2018) or CSS/SSS (Drake+2014/2017).
  Footprint and depth coverage were not verified. II/365 is CatWISE2020, not a variable catalogue, so
  J/ApJS/237/28 was queried instead.
- **VSX:** TIC 270573718 and TIC 193718989 have Gaia-derived entries (names are their Gaia DR3 IDs), type ROT,
  G 13.69-13.72 and 13.21-13.24, with no period. Agreement with P, 2P or P/2 cannot be assessed.
- **Gaia DR3 variability:**
  - 270573718 and 193718989: phot_variable_flag VARIABLE, vari_classifier SOLAR_LIKE (scores 0.497 and 0.833).
    Neither is in the eclipsing-binary, planetary-transit or rotation-modulation tables.
  - 262843927: no variability processing (NOT_AVAILABLE).
  - Its neighbour Gaia DR3 4673750907194777600 (54.8", G=20.04) is classified AGN (0.962).
  - No NSS solution (two-body, acceleration, non-linear spectro, VIM) for any target or any source within 90".

## 4. Gaia DR3 (ESA TAP; the targets' TIC epoch-2000 positions propagate to the DR3 positions within 0.7 mas)

| | 270573718 | 262843927 | 193718989 |
|---|---|---|---|
| G, BP-RP, parallax (mas) | 13.706, 2.17, 11.745 | 13.000, 2.05, 11.957 | 13.227, 2.03, 11.698 |
| RUWE; excess noise (sig) | 1.117; 0.038 mas (0.8) | **1.307; 0.124 mas (15.2)** | 1.037; 0 (0) |
| ipd_frac_multi_peak / odd_win | 0 / 0 | 0 / 0 | 0 / 0 |
| RV (km/s), method, N transits | 19.27+/-1.46, 2, 19 | 8.25+/-0.51, 1, 23 (has_rvs) | -5.44+/-1.07, 1, 21 |
| rv_amplitude_robust, rv_chisq_pvalue | n/a | 7.32, 0.977 | 15.28, 0.183 |
| AP | GSP-Phot 3752 K, logg 4.74, R 0.509 | GSP-Spec 3865 K, logg 5.0, [M/H] -0.32 (no GSP-Phot) | GSP-Phot 3896 K, R 0.570; GSP-Spec 3953 K |
| DSC combmod P(star) / P(binary star) | 0.998 / 0.0017 | 0.996 / 0.0035 | **1.0e-6 / 0.999999** |

The DSC value for TIC 193718989 is reported as returned. Check the DSC class definitions before using it.
- **Sources within 5":** none for any target.
- **Neighbours:**
  - 270573718: **G=14.71 at 34.4"** (BP-RP 0.93, parallax 1.14 mas); next G=16.62 at 52.1" and G=15.79 at 56.0".
  - 262843927: nearest 42.0" (G=19.48).
  - 193718989: **9.79" (G=19.59, ipd_frac_multi_peak=2)**, then 16.3" (19.72), 16.4" (19.86) and 26.4" (19.24).
- **Epoch photometry** (DataLink, DATAMODEL_STANDARD; saved in `gaia_epoch_photometry/`, not interpreted;
  time = TCB-based BJD - 2455197.5):
  - 270573718: 36 transits.
  - 193718989: 46 transits.
  - The 54.8" AGN-class neighbour of 262843927.
  - 262843927 itself has none.

## 5. Ground and other time series

- **ZTF** (TIC 193718989 only; the southern targets are NOT_APPLICABLE). The default collection is ztf_dr24: its
  sha256 is identical to an explicit COLLECTION=ztf_dr24 query. The API page still names dr18, which now returns
  "UsageFault". For the target:
  - zg: 1379 rows (1279 with catflags=0)
  - zr: 1495 rows (1409)
  - zi: 258 rows (230)
  - MJD 58198.4-60960.2, two fields (725 and 1763).

  All 8 Gaia neighbours within 60" with G<21 returned light curves, including the 9.8" star: zr 1368 rows,
  median r=19.64. CSVs are in `ztf/`. Transit-phase coverage was not assessed.
- **ZTF forced photometry and ATLAS forced photometry:** ACCESS_RESTRICTED (account required; not attempted).
- **ASAS-SN Sky Patrol v2:** the documented client (skypatrol 0.6.21) was installed only in
  `D:\tess_fu3_cache\venv_census`. All three stars are in its catalogue (asas_sn_id 609885790728, 652835198109,
  42950227346), but `get_block_servers` returned [] and the server message dated 13 Oct 2026 announces that the
  light-curve service is down for maintenance. Coded ACCESS_FAILED, not a negative result.

## 6. Spectroscopy and RV; high-resolution imaging

- **RAVE DR6, TIC 262843927:** two spectra, 2004-01-03 (HRV 7.48+/-2.01 km/s, S/N 31) and 2011-08-22
  (HRV 3.08+/-3.47, S/N 18). The RAVE Gaia DR2 cross-match row gives the DR2 RV as 8.93+/-0.51 (14 transits).
- **LAMOST DR11 (V/162), TIC 193718989:** one LRS spectrum on 2021-04-10 (ObsID 901105152, dM0,
  z = -2.46e-5 +/- 0.66e-5, i.e. cz about -7.4 +/- 2.0 km/s, Teff 3746, logg 4.64, [M/H] -0.23). The input
  catalogue also lists a 2013-05-22 plan, which has no catalogue spectrum. Nothing in the DR5 (V/164) table.
- **No entries:** APOGEE DR17, GALAH DR3 and DR4 (not applicable to 193718989), HARPS RV database, ESO archive
  (no spectra and no pointed raw frames; only VISTA VHS/VEXAS survey products and ELT guide-star catalogue
  entries cover the southern pair), and KOA (no rows; not applicable to 262843927).
- **High-resolution imaging:** no entries in SOAR TESS I/II, Howell+2021, Tokovinin 2023, WDS or the ExoFOP
  imaging summaries. The TOI-keyed speckle tables cannot contain non-TOIs.

## 7. Prior public analyses (these use the same TESS photons and are not independent confirmation)

- **TIC 193718989**, github.com/eumemic/exoplanets (repository created 2026-10-07): candidate
  `TIC193718989_P24.533`, added 2026-10-08 in a "faint M dwarfs" stack-slide search of TESS-SPOC/QLP FFI light
  curves (S1-104). Its TRICERATOPS files were re-committed up to 2026-10-16.
  - Fit: P = 24.5329228 +/- 0.0002 d, T0 = BJD_TDB 2459785.12684 (+/- 7.3 min), T14 = 3.38 h,
    depth 1947 ppm, Rp 2.58 Re, b 0.34.
  - Vetting: depth 2365 +/- 213 ppm, SNR 11.1, MES 13.5, 8 transits, using TESS-SPOC S25, S26, S40, S52, S53,
    S79 and S80.
  - TRICERATOPS on S40, S52 and S53: FPP 0.029 +/- 0.004 and NFPP 2.8e-7; FPP 0.011 with MOLUSC/Gaia
    constraints.
  - Centroid offsets 1.4" (S25) and 8.8" (S53); tier B.
  - Its tess-point sector list is 117, 118, 119, 124, 125, 132.
  - Copies are in `prior_public_analysis/eumemic_exoplanets/`.
- **TIC 262843927:** in the 1599-star low-mass sample of Cloutier (2019, AJ 158, 81), which searched S1-S2
  2-min data. The TIC ID does not appear anywhere in the paper text or tables, so it was not reported as a
  candidate or a false positive. Its other SIMBAD references are RAVE DR2-DR6, APASS and GCNS.
- **TIC 270573718:** the only SIMBAD reference is GCNS. Web searches for all three TIC and Gaia IDs found
  nothing. TIC 193718989 has no SIMBAD entry.

## 8. Product caveat documentation (MAST HLSP pages fetched 2026-10-18)

- **QLP, Sectors 99-104:** barycentric timing error from orbit 210 (second half of S99) through orbit 220 (end
  of S104). Velocity instead of position was used from orbit 215 (first half of S102). Redelivery is in
  progress; S99-S104 are still asterisked as not redelivered. **Does not apply to any of these stars**: none
  has data in S99-S104.
- **QLP, Sectors 74-79:** wrong-reference-plane ephemeris, timestamp error up to about +/-3 min, corrected and
  re-uploaded as v02. **Applies only to the TIC 193718989 QLP S79 file**, and the MAST copy found is v02.
  Discovery used TESS-SPOC for S79.
- **TESS-SPOC, Sectors 40-68:** no CDPP values in the light curves (pipeline bug; the CDPP header values only).
  Applies to the TESS-SPOC light curves of 270573718 S61, S64, S65, S67, S68; 262843927 S61, S64, S68; and
  193718989 S40, S52, S53.
- **TGLC, Sectors 1-26:** possible negative fluxes and detrending failure for very dim stars (about 15 T mag
  or fainter) near variables. Its stated condition is not met (T = 12.0-12.7). TGLC exists only for S1-S11 and
  S1-S4 here.
- **TARS:** v01, Sectors 1-96. No timing caveat stated.
- **Not official documentation:** the eumemic README masks QLP orbit edges in S94-S104.

## 9. Failures, deviations and workarounds (all recorded in receipts)

- Open-ended MAST FFI sector-range queries (`sequence_number=[95,300]`) timed out at 120 s. They were replaced
  by per-sector count queries. A total count for QLP sectors >= 99 returned the same number as S99 alone and
  was not used.
- The old WTV CGI returned HTTP 403. The WTV v2 RA/Dec lookup was used instead.
- Gaia: the ESA TAP sync endpoint (the service behind `Gaia.launch_job`) was called directly with `requests`,
  so that the response bodies could be receipted. One RemoteDisconnected error was retried once and succeeded.
  DataLink with DATA_STRUCTURE=INDIVIDUAL returned HTTP 500 ("deprecated"), so DATAMODEL_STANDARD was used.
- VizieR: one find_catalogs keyword call failed (ConnectionError); its catalogue was found by ID instead.
  TAPVizieR rejected LOWER(), so case variants were spelled out. SIMBAD TAP needed `"year"` quoted.
- NASA Exoplanet Archive: the first attempt failed with "Failed to connect to cx_Oracle" (HTTP 400). Later cone
  queries were blocked by Cloudflare (403) and not retried.
- KOA `koa_reduced_data` is not position-searchable (HTTP 400). ZTF `ztf_dr18` is no longer valid.
- ExoFOP PHP endpoints return `Array`, and the ASAS-SN light-curve service is down; both are coded
  ACCESS_FAILED.
- No account was created or used anywhere.
