import socket; socket.setdefaulttimeout(90)
from astroquery.mast import Observations
import astropy.units as u
from astropy.coordinates import SkyCoord
c = SkyCoord(356.609026*u.deg, -11.797127*u.deg)
t = Observations.query_region(c, radius=3*u.arcsec)
cols = ['obs_collection','provenance_name','project','target_name','sequence_number','t_exptime','t_min','t_max','dataproduct_type','obsid']
t = t[[x for x in cols if x in t.colnames]]
t.sort(['obs_collection','sequence_number'])
t.pprint(max_lines=200, max_width=250)
