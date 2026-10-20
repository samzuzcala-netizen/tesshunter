"""Retrieve public catalogues, preserving exact IDs and download receipts."""
from pathlib import Path
import io
import json
import argparse
from datetime import datetime,timezone
import requests
import pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u
from run_followup import ARCH,OUT,save,sha,NB,TID

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--refresh',action='store_true',help='Re-download catalogues; default reuses the frozen cache.')
args=parser.parse_args()
receipts=[]
def get(url,name,params=None):
    p=ARCH/name
    try:
        full_url=requests.Request('GET',url,params=params).prepare().url
        if p.exists() and not args.refresh:
            receipts.append({'url':full_url,'status':'cached','path':p.name,'sha256':sha(p),
                             'checked_utc':datetime.now(timezone.utc).isoformat()})
            return p.read_text(encoding='utf8')
        r=requests.get(url,params=params,timeout=50);r.raise_for_status();p.write_bytes(r.content)
        receipts.append({'url':r.url,'status':r.status_code,'path':str(p.name),'sha256':sha(p),'utc':datetime.now(timezone.utc).isoformat()})
        return r.text
    except Exception as e:
        receipts.append({'url':url,'params':params,'error':str(e)})
        return None

base='https://gea.esac.esa.int/tap-server/tap/sync'
queries={
 'gaia_rotation':f'SELECT * FROM gaiadr3.vari_rotation_modulation WHERE source_id={TID}',
 'gaia_variable_cone':"SELECT g.source_id,g.ra,g.dec,g.phot_g_mean_mag,g.phot_rp_mean_mag,g.phot_variable_flag,v.best_class_name,v.best_class_score FROM gaiadr3.gaia_source AS g LEFT OUTER JOIN gaiadr3.vari_classifier_result AS v ON g.source_id=v.source_id WHERE 1=CONTAINS(POINT('ICRS',g.ra,g.dec),CIRCLE('ICRS',85.137263,-66.173515,0.025))",
 'gaia_eb_cone':"SELECT e.* FROM gaiadr3.vari_eclipsing_binary AS e JOIN gaiadr3.gaia_source AS g ON e.source_id=g.source_id WHERE 1=CONTAINS(POINT('ICRS',g.ra,g.dec),CIRCLE('ICRS',85.137263,-66.173515,0.025))"
}
for name,q in queries.items():get(base,name+'.csv',{'REQUEST':'doQuery','LANG':'ADQL','FORMAT':'csv','QUERY':q})
og='https://www.astrouw.edu.pl/ogle/ogle4/OCVS/lmc/ecl/'
get(og,'ogle_index.html')
ident=get(og+'ident.dat','ogle_ident.dat')
params=get(og+'ecl.dat','ogle_ecl.dat')
found=[]
if ident:
    c=SkyCoord(NB['ra'],NB['dec'],unit='deg')
    for line in ident.splitlines():
        items=line.split()
        if len(items)<4 or not items[0].startswith('OGLE'):continue
        # Archive ident.dat: name, type, RA(hms), Dec(dms), cross-identifications.
        try: s=SkyCoord(items[2],items[3],unit=(u.hourangle,u.deg));sep=c.separation(s).arcsec
        except Exception:continue
        if sep<90:
            row={'name':items[0],'sep_arcsec':sep,'ra':s.ra.deg,'dec':s.dec.deg,'ident_line':line}
            if params:
                row['parameter_line']=next((l for l in params.splitlines() if l.startswith(items[0])),None)
            found.append(row)
    for row in found:
        get(og+'phot/I/'+row['name']+'.dat',row['name']+'_I.dat')
save(OUT/'catalogue_queries.json',{'receipts':receipts,'ogle_neighbours':found})
print(json.dumps(found,indent=2));print([(r.get('path'),r.get('status'),r.get('error')) for r in receipts])
