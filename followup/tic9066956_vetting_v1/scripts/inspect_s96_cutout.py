import glob, sys, numpy as np
from astropy.io import fits
from astropy.wcs import WCS
p = glob.glob(sys.argv[1] if len(sys.argv) > 1 else "s96/*s0096*.fits")[0]
h = fits.open(p); d = h[1].data; q = d['QUALITY']; g = q == 0
med = np.nanmedian(np.asarray(d['FLUX'][g], float), axis=0)
np.set_printoptions(linewidth=300)
for r in range(24, -1, -1):
    print('%2d ' % r + ' '.join('%4d' % v for v in med[r]))
print('    ' + ' '.join('%4d' % c for c in range(25)))
w = WCS(h[2].header)
print(h[2].header.get('CRVAL1'), h[2].header.get('CRVAL2'), h[2].header.get('CRPIX1'), h[2].header.get('CRPIX2'))
# time series of the brightest pixel and of the total
tot = np.nansum(np.asarray(d['FLUX'], float), axis=(1, 2))
print('total flux percentiles over time', np.nanpercentile(tot[g], [1, 25, 50, 75, 99]))
nz = np.mean(np.abs(np.asarray(d['FLUX'], float)).sum(axis=(1, 2)) > 1000)
print('fraction cadences with |flux| sum >1000', nz)
