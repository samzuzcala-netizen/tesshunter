"""Download a metadata-selected QLP product per affected sector and compare TIME."""
from urllib.parse import quote
import numpy as np
from astropy.io import fits
from common import REPO,P11,DATA,read,write,sha,utc,host_order
from public_metadata import fetch


def main():
    dev={int(r['tic_id']) for r in read(P11/'manifests/development_hosts.json')}
    observations=[]
    for path in sorted((DATA/'acquisition').glob('mast_survey_*.json')):observations+=read(path)['data']
    selections=[]
    for sector in range(99,105):
        available=[r for r in observations if r['provenance_name']=='QLP' and r['sequence_number']==sector and int(r['target_name']) in dev]
        available.sort(key=lambda r:host_order(r['target_name'],'audit'))
        if not available:continue
        selections.append(available[0])
    selection=P11/'manifests/timing_refresh_selection.json'
    if not selection.exists():write(selection,dict(utc=utc(),rule='first audit SHA256 development TIC per sector 99-104, metadata only',rows=selections,source_sha256=sha(__file__)))
    output=[]
    for row in selections:
        tic=int(row['target_name']);sector=int(row['sequence_number']);uri=row['dataURL']
        path=DATA/f'acquisition/timing_refresh/{row["obs_id"]}.fits'
        if not path.exists():fetch('https://mast.stsci.edu/api/v0.1/Download/file?uri='+quote(uri,safe=''),path)
        with fits.open(path,memmap=False) as hd:
            time=np.asarray(hd[1].data['TIME'],dtype=float);h=hd[1].header
            timesys=h.get('TIMESYS',hd[0].header.get('TIMESYS'));timeref=h.get('TIMEREF',hd[0].header.get('TIMEREF'))
            version=hd[0].header.get('VERSION')
            current_flux=np.asarray(hd[1].data['DET_FLUX'],dtype=float)
            cadence_days=h.get('TIMEDEL',hd[0].header.get('TIMEDEL'))
        old=REPO/f'data/survey/audit_lc/tic{tic}/s{sector:03d}_QLP.npz'
        with np.load(old) as z:
            old_time=z['time'];old_flux=z['flux']
        same=time.shape==old_time.shape and np.array_equal(time,old_time,equal_nan=True)
        diff=(time-old_time)*86400 if time.shape==old_time.shape else np.array([])
        output.append(dict(tic_id=tic,sector=sector,current_path=path.relative_to(REPO).as_posix(),current_sha256=sha(path),
            historical_path=old.relative_to(REPO).as_posix(),historical_sha256=sha(old),TIME_exact_equal=same,
            max_absolute_difference_seconds=float(np.nanmax(abs(diff))) if len(diff) else None,
            DET_FLUX_exact_equal=current_flux.shape==old_flux.shape and bool(np.array_equal(current_flux,old_flux,equal_nan=True)),
            TIMESYS=timesys,TIMEREF=timeref,header_version=version,header_cadence_days=cadence_days,
            metadata_exposure_seconds=row['t_exptime'],verdict='No changed/corrected timestamp array delivered for this fixture' if same else 'CHANGED_NEEDS_AUTHORITATIVE_CORRECTION_VERIFICATION'))
        print(sector,tic,'same time',same,flush=True)
    write(P11/'results/timestamp_redelivery_checks.json',dict(utc=utc(),rows=output,source_sha256=sha(__file__),
        limitation='One metadata-selected product per sector is a release check, not proof of the state of every file. No flux alignment, injection truth or catalogue ephemeris was used.'))


if __name__=='__main__':main()
