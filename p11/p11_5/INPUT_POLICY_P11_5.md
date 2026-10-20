# P11.5 input policy

Input registration is complete. The original 300 hosts and all 600 fixed comparison injections remain in the accounting manifests. D_core contains **235 hosts and 484 fixed injections**. Another 64 hosts are D_aux; one has no usable selected product. All 235 D_core preparations succeeded, producing 719 common series (235 uninjected and 484 injected). The computational evaluation size is pending the prospective timing decision; these are input-eligible counts, not recovery results.

## Frozen timing and cadence policy

Use selected products from sectors 56–105 with the original SPOC, TESS-SPOC, QLP preference. QLP 80, 83, 85 and 99–104 remain excluded. The official notices were refreshed once and archived with response hashes; no later-sector expansion or transit-based clock adjustment was made. Corrected QLP 74–79 requires the saved corrected-source verification. Default trusted flux, quality mask, native 200-second preparation, original P8 cuts and strict-minority targeted-sector rule remain unchanged.

The inventory establishes raw TIME, flux, SAP and quality identity against their FITS sources, records time-reference/exposure/header/column evidence, and distinguishes that ingestion proof from physical timestamp correctness. The known unresolved QLP timing regimes remain excluded regardless of filename. FFI coverage is counted from verified usable native-200-second FFI products, including a valid FFI counterpart when the preferred selected flux is targeted SPOC.

## Sector 105 reconciliation

The original target-list metadata names 46 of the 300 hosts in sector 105. The bounded current product query returned no delivered sector-105 observations for those 46. Target-list membership therefore added no usable product. The recorded sector-69 omission for TIC 288430636 was a multi-sector DVT product (s0056–s0069), not a missing raw light curve; its ephemerides were not opened. Exact selected products and hashes were frozen once.

## Population distributions

All baseline and coverage summaries below refer to the newly trusted products; the original group retains every original identity. Unavailable crowding values remain missing. No absent-domain extrapolation is made.

| Population | Hosts | Tmag median [min,max] | Verified FFI median [min,max] | Trusted baseline median [min,max], d |
|---|---:|---|---|---|
| Original registered | 300 | 13.24 [12.51, 14.00] | 6.50 [0.00, 19.00] | 780.92 [0.00, 1083.10] |
| D_core | 235 | 13.29 [12.51, 14.00] | 11.00 [3.00, 19.00] | 837.57 [72.07, 1083.10] |
| D_aux | 64 | 13.02 [12.51, 13.96] | 2.00 [1.00, 4.00] | 754.04 [25.79, 780.92] |

Full quantiles, selected-author counts, crowding availability and exclusion reasons are in `results/input_distributions.json`. Host, product, original-injection and per-product exclusion rows are in `manifests/`. Input-excluded injections are INPUT_INELIGIBLE, never measured misses. Every evaluated host must carry all its fixed injections, including unobservable ones, plus its uninjected series.

## Preparation and controls

Inject the original absolute exposure-integrated models into both corrected and SAP flux before harmonisation, detrending or clipping. Recompute the common uninjected expected-SNR coordinate with unchanged P10 arithmetic. Search arrays include sector identity; the first preparation adapter lost that field on legacy-cache reload, failed before scoring, and was replaced by the preserved V2 native-array format. Original failed files and costs remain archived.

Historical controls retain their exact original identities and clearly labelled engineering input profiles. Seventeen P9 control-reader path failures were repaired by routing to their recorded P9 raw/FITS caches; all seventeen repair audits completed. These controls are outside survey-domain inference when they fail D_core cuts. Their candidate/A/S evidence is regenerated on trusted inputs, and unavailable alternatives remain unknown.

Official source snapshots: [MAST QLP release notices](https://archive.stsci.edu/hlsp/qlp), [QLP product-era notes](https://tess.mit.edu/qlp/), [TESS product conventions](https://heasarc.gsfc.nasa.gov/docs/tess/data-products.html). Acquisition timestamps and exact HTML hashes are stored locally under P11.5.

## Final evaluated population

Completed development: 120 D_core hosts, 242 fixed injections, and 120 uninjected series.

Original population: 300 hosts / 600 injections. Verified input-eligible D_core: 235 hosts / 484 injections. Input exclusions are not measured misses. No extrapolation to excluded hosts or sectors is made.

The complete fixed population accounting is in `manifests/population_accounting_final.json`; computational nonselection and input ineligibility are distinct. No fresh validation cohort was admitted.
