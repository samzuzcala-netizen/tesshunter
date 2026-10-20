import common as C
from astropy.io import fits
for p in (C.BIG/'downloads').glob('*lc.fits'):
    with fits.open(p) as h:print(p.name,h[1].columns.names)
