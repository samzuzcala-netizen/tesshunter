import common as C
from astropy.io import fits
from astropy.wcs import WCS
import numpy as np
rows=[]
for r in C.json.loads((C.WS/'inputs/pixel_inventory.json').read_text()):
    with fits.open(r['path']) as h:
        p=h[1].header;xy=WCS(h[2].header).all_world2pix([[257.222579,50.487785]],0)[0]
        row=dict(sector=r['sector'],origin=[p['1CRV4P'],p['2CRV4P']],target_ccd=[p['1CRV4P']+xy[0],p['2CRV4P']+xy[1]],header={k:p.get(k) for k in ['1CRPX4','2CRPX4','1CRVL4','2CRVL4','1CRV4P','2CRV4P','TIMEDEL','INT_TIME','NUM_FRM','TIMEREF','TIMESYS','BJDREFI']})
        rows.append(row)
C.write(C.WS/'inputs/ccd_geometry.json',rows);print(C.json.dumps(C.clean(rows),indent=1))
