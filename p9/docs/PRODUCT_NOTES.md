# Selected-product provenance note

Checked 2026-09-08 after TIC 172421004's outcome lock. Its selected inputs include
four SPOC sectors (60, 71, 72, 73), harmonized from 120 to 200 seconds, plus one
200-second TESS-SPOC product tagged sector 1751. The latter spans approximately
BTJD 4055.759–4063.004 and is included by the unchanged preset's `sector_min=56`
without a maximum. The exact product receipt is
[tic172421004.json](../manifests/products/tic172421004.json).

Sector 1751 is an authentic special pointing for 3I/ATLAS on January 15–22, 2026,
with 4.25 days of collected science data and substantial interruptions. The
mission reports scattered light in Camera 3 late in the observation. These are
documented observing conditions, not a newly inferred cause of this control's
outcome. [NASA sector summary](https://heasarc.gsfc.nasa.gov/docs/tess/sector1751_summary.html)

MAST explicitly released TESS-SPOC light curves derived from the 200-second FFIs
for this pointing. The unusual integer is therefore not a concatenation of
ordinary sector numbers. P9 preserves its inherited inclusion and does not
retroactively remove its observations. [MAST June 2026 release](https://archive.stsci.edu/contents/newsletters/june-2026/june-hlsp-update)

All selected-product author/cadence counts and sectors outside the ordinary
56–105 target-list inventory are included in the final census. The control's
published EB classification is used only after its locked automated outcome;
this provenance note does not modify that outcome.
