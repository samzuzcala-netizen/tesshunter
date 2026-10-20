"""D review assets from frozen P8 pixel methods; never reads planet truth."""
from common import *
import argparse, csv, warnings
import numpy as np

def positions(tic):
    path=P9/'inputs/gaia_positions'/f'tic{tic}.json'
    if path.exists() and read(path).get('status')=='complete':return path
    from astroquery.gaia import Gaia
    st=read(P9/'inputs/stellar'/f'tic{tic}.json')
    query=f"SELECT source_id,ra,dec,pmra,pmdec,phot_g_mean_mag,phot_rp_mean_mag FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{float(st['ra'])},{float(st['dec'])},0.075))"
    tab=Gaia.launch_job_async(query,dump_to_file=False).get_results()
    rows=[]
    for r in tab:
        row={}
        for k in tab.colnames:
            if np.ma.is_masked(r[k]):row[k]=None
            elif k=='source_id':row[k]=int(r[k])
            else:
                v=float(r[k]);row[k]=v if np.isfinite(v) else None
        rows.append(row)
    write(path,dict(utc=utc(),status='complete',query=query,source='Gaia DR3 TAP; astrometry and magnitudes only',objects=rows))
    return path

def run(tic,key):
    if (P9/'results/locks'/f'tic{tic}.json').exists():raise RuntimeError('Host is locked')
    from runner import setup
    root,F,A,V=setup(tic)
    import p8_eb_difference_image as I
    import p8_eb_aperture as AP
    import lightkurve as lk
    import astropy.units as u
    from tesshunter.secondary import box_depth,planet_secondary_bound
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    extra=read(root/'expensive'/f'{key}.json')
    sectors=sorted(s['sector'] for s in extra.get('centroid',{}).get('per_sector',[]) if s.get('available'))
    if not sectors:raise RuntimeError('No native D TESScut sectors available')
    gaia=P9/'inputs/gaia_positions'/f'tic{tic}.json'
    I.ROOT=root;I.REPO=P9
    (root/'eb_screen').mkdir(exist_ok=True)
    # Frozen implementation and its fit-cache validation are used unchanged.
    sys.argv=['p8_eb_difference_image.py','--key',key,'--sectors',*[str(s) for s in sectors],
      '--gaia',str(gaia),'--ephemeris','fit','--pixel-cache',str(P9/'work/execution_lightkurve/tesscut')]
    I.main()
    from aperture_review import run as render_apertures
    render_apertures(tic,key)
    if len(sectors)>4:
        from pixel_pages import run as render_pages
        render_pages(tic,key)
        from aperture_pages import run as render_aperture_pages
        render_aperture_pages(tic,key)
    print('pixel review assets complete',key,flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('cmd',choices=['prepare','run']);a.add_argument('--tic',type=int,required=True);a.add_argument('--key');args=a.parse_args()
    if args.cmd=='prepare':print(positions(args.tic),flush=True)
    else:run(args.tic,args.key)
