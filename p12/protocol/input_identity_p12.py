"""Exact source-FITS checks following P11 input_inventory, without its writers."""
from p12_common import REPO, sha, environment
environment()
from pathlib import Path
import re
import numpy as np
from astropy.io import fits

HEADERS=('ORIGIN','CREATOR','PROCVER','FILEVER','VERSION','DATE','DATE-OBS','DATE-END',
         'TICID','SECTOR','CAMERA','CCD','TIMESYS','TIMEREF','BJDREFI','BJDREFF',
         'TIMEUNIT','TIMEDEL','TIMEPIXR','TSTART','TSTOP')
PREFERENCE={'SPOC':0,'TESS-SPOC':1,'QLP':2}


def equal(a,b):
    return a.shape==b.shape and bool(np.array_equal(a,b,equal_nan=True))


def read_source(path):
    with fits.open(path,memmap=False) as hd:
        h0,h1=hd[0].header,hd[1].header
        headers={k:h1.get(k,h0.get(k)) for k in HEADERS}
        names=hd[1].data.names
        columns={k:np.asarray(hd[1].data[k]).copy() for k in names
                 if k in ('TIME','QUALITY','SAP_FLUX','SAP_FLUX_ERR','SAP_BKG',
                          'PDCSAP_FLUX','PDCSAP_FLUX_ERR','DET_FLUX','DET_FLUX_ERR',
                          'KSPSAP_FLUX','KSPSAP_FLUX_ERR','FLUX','FLUX_ERR')}
    t=np.asarray(columns['TIME'],dtype=float)
    reference=float(headers.get('BJDREFI') or 0)+float(headers.get('BJDREFF') or 0)
    btjd=t+(reference-2457000) if reference else t.copy()
    version=re.search(r'_v([^_]+)_',path.name)
    author='QLP' if 'hlsp_qlp' in path.name else 'TESS-SPOC' if 'hlsp_tess-spoc' in path.name else 'SPOC'
    record=dict(path=path.relative_to(REPO).as_posix(),sha256=sha(path),bytes=path.stat().st_size,
                headers=headers,author=author,sector=int(headers.get('SECTOR') or -1),
                version=version.group(1) if version else headers.get('PROCVER'))
    return record,btjd,columns


def compare(raw,metadata,source):
    record,t,columns=source
    keep=np.ones(len(t),dtype=bool) if equal(raw['time'],t) else np.isfinite(t)
    column=metadata['flux_column'].upper()
    checks={'TIME':equal(raw['time'],t[keep]),
            'flux':column in columns and equal(raw['flux'],np.asarray(columns.get(column,[])[keep],dtype=float)) if column in columns else False,
            'SAP': 'SAP_FLUX' in columns and equal(raw['sap_flux'],np.asarray(columns['SAP_FLUX'][keep],dtype=float)),
            'quality':'QUALITY' in columns and equal(raw['quality'],columns['QUALITY'][keep]),
            'BJD_TDB_SOLARSYSTEM':record['headers']['TIMESYS']=='TDB' and record['headers']['TIMEREF']=='SOLARSYSTEM' and record['headers']['BJDREFI']==2457000,
            'sector':record['sector']==metadata['sector'], 'author':record['author']==metadata['author']}
    error_columns=[c for c in (column+'_ERR','FLUX_ERR','SAP_FLUX_ERR','KSPSAP_FLUX_ERR')
                   if c in columns and equal(raw['flux_err'],np.asarray(columns[c][keep],dtype=float))]
    return dict(checks=checks,all_required_exact=all(checks.values()),
                nonfinite_time_rows_removed=int((~keep).sum()),flux_error_matching_columns=error_columns,
                flux_error_all_nan=bool(np.all(np.isnan(raw['flux_err']))))


def timing_status(metadata,source,comparison,configuration):
    if not source or not comparison['all_required_exact']:return 'SOURCE_UNVERIFIED'
    if metadata['author']=='QLP':
        if metadata['sector'] in configuration['qlp_excluded_sectors']:return 'FROZEN_QLP_EXCLUSION'
        if metadata['sector'] in configuration['qlp_correction_required_sectors']:
            return 'CORRECTED_V02_SOURCE_VERIFIED' if str(source['version']) in ('02','2','2.0') else 'CORRECTED_V02_REQUIRED'
    return 'SOURCE_VERIFIED'


def choose_verified(records,configuration):
    best={}
    for r in records:
        p=r['metadata'];sector=int(p['sector'])
        if not configuration['sector_min']<=sector<=configuration['sector_max']:continue
        if p['author'] not in PREFERENCE:continue
        if p['author']=='QLP' and sector in configuration['qlp_excluded_sectors']:continue
        if sector not in best or PREFERENCE[p['author']]<PREFERENCE[best[sector]['metadata']['author']]:best[sector]=r
    # Preserve P11's author choice; a failed preferred source is disclosed, never silently replaced.
    return [r for s,r in sorted(best.items()) if r['timing_status'] in ('SOURCE_VERIFIED','CORRECTED_V02_SOURCE_VERIFIED')
            and r['n_quality_good']>=50 and r['metadata']['cadence_s']<=300]
