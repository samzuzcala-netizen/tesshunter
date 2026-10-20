# TIC 167304394: values for a VSX "new variable star" submission

Prepared 2026-09-03 from the prompt-5 audit data (`data/survey/p5/tls/tic167304394_P22.7802_lc.npz`,
`scripts/eb_report.py`). Figure: `tic167304394_fold.png`. Measurements JSON:
`tic167304394_measurements.json`. Nothing has been submitted; the human submits.

Catalog status checked 2026-09-03 [M]: no VSX entry within 1 arcmin; SIMBAD lists
UCAC4 114-012846 as a plain star (type `*`); not in the TESS EB catalog (Prsa et al.,
2-minute targets, sectors 1-26); not in any SPOC TCE list; not a TOI or CTOI.
(The second binary from prompt 6, TIC 188830181, is ALREADY catalogued: VSX
ZTF J173401.31+515730.5, type EW, P = 0.9866422 d; SIMBAD ATO J263.5054+51.9584,
EB*. Nothing to submit for it.)

## Form fields

| VSX field | value | source |
|---|---|---|
| Name (primary) | TIC 167304394 | TESS Input Catalog v8 |
| Other names | UCAC4 114-012846; Gaia DR3 5283324796495406336 | SIMBAD, Gaia DR3 |
| RA (J2000) | 06 32 00.29 (98.001223 deg) | TIC |
| Dec (J2000) | -67 18 17.2 (-67.304764 deg) | TIC |
| Constellation | auto-filled by VSX from the coordinates | |
| Variability type | EA (detached eclipsing binary, eccentric orbit) | this analysis |
| Period | 22.7797 +/- 0.0011 d | TLS on 34 sectors, 2018-2025 |
| Epoch of primary minimum | BJD_TDB 2458326.3718 (enter as JD; the HJD-BJD_TDB difference of about 70 s is far below the 4.4-h eclipse width) | forced TLS T0 |
| Max magnitude | 11.47, band TESS (T) | TIC Tmag |
| Min magnitude | 11.53, band TESS (T) | max + 0.062 mag (55.5 ppt observed depth) |
| Eclipse duration | 4.4 h = 0.8% of the period (VSX "D" field for EA) | fold, full width at 3 sigma |
| Secondary minimum | 1.1 ppt (0.001 mag), 2.2 h, at phase 0.7385 | fold and per-cycle check, 29 of 29 cycles |
| Spectral type | leave blank (TIC Teff 5284 K; composite, see remarks) | |
| Discoverer | your name | |
| Data source / reference | TESS full-frame images, MIT QLP light curves (HLSP), 34 sectors 2018-2025; analysis by the submitter | |
| Light curve | upload `tic167304394_fold.png` (VSX requires a phase plot or a link to one) | |

## Remarks text (paste into the VSX remarks box; edit freely)

Detached eclipsing binary identified in TESS full-frame-image photometry
(MIT QLP light curves, 34 sectors, 2018-2025). Primary eclipse depth 0.062
mag in the TESS band, duration 4.4 h, V-shaped, 34 eclipses observed at a
constant period of 22.7797 +/- 0.0011 d. A shallow secondary eclipse
(0.0011 mag, 2.2 h) is present at phase 0.7385 rather than 0.5, so the orbit
is eccentric (e cos omega about 0.37). Gaia DR3 resolves two sources of equal
brightness (G 12.79 and 12.64) 0.4 arcsec apart at this position, both inside
the TESS aperture; the observed depths are therefore diluted by about a
factor of two and the eclipsing pair is one of the two. Not in the TESS
Eclipsing Binary Catalog or the SPOC TCE lists as of 2026-09-03.

## Caveats to keep in mind

* The depth and the duration are from 30-minute-binned QLP flux with a
  wotan biweight detrend (window 0.75 d); a 4.4-h eclipse loses little to
  that window, but quote depths as "observed in the TESS band, diluted".
* The epoch uncertainty is of order 0.005 d (the forced-TLS grid); VSX does
  not require one.
* Which of the two Gaia sources eclipses is unknown; the position given is
  the TIC position (epoch 2000), 0.06 arcsec from the Gaia DR3 source named.
* No radial velocities exist; the classification rests on photometry alone.
  Gaia's RV amplitude for the source (51.8 km/s over 26 transits) is within
  its own noise expectation and is not evidence either way.
