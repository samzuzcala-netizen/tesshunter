import common as C
notes=dict(utc=C.datetime.datetime.now(C.datetime.timezone.utc).isoformat(),changes=[
 'Input loader correction: early QLP uses KSPSAP_FLUX, not DET_FLUX; mapped to common internal name. No recipe change.',
 'Finite-pixel correction: a NaN elsewhere in a cutout must not discard a finite aperture. Background selector now requires finite median-image pixels. Sector 52 still has no finite 3x3 aperture.',
 'Input identity correction after first diagnostic measurements: aperture figure showed no target in sectors 25/40/50/52. CCD-coordinate verification places their target centres outside the active imaging area, robust to a one-pixel origin convention. These cutouts are collateral/off-detector coverage, not stellar light curves. Their initial normalised residuals are not used as science depths or period evidence. Final outputs label target outside active CCD science pixels. No baseline, window, error or significance rule was adjusted.',
 'Science pixel bounds cross-checked against official tessgi/tess-point README (45–2092 columns, 1–2048 rows). Code package tess_stars2px was not used.'
],source='https://github.com/tessgi/tess-point')
C.write(C.WS/'inputs/implementation_corrections.json',notes)
print('Input corrections documented')
