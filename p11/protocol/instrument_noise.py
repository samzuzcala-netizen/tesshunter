"""Source+sky+aperture+read noise from full mission FITS calibration headers.

The initial inventory's compact header list omitted READNOIA..D/INT_TIME/NREADOUT.
This supplemental diagnostic reads those actual fields without changing any preparation.
"""
import numpy as np
from astropy.io import fits
from common import REPO,P11,read,write,sha,utc,append_event
import time


def count_noise(source_e,sky_e,n_pixels,n_reads,read_e):
    values=np.array([source_e,sky_e,n_pixels,n_reads,read_e],dtype=float)
    if not np.all(np.isfinite(values)) or source_e<=0 or min(sky_e,n_pixels,n_reads,read_e)<0:
        raise ValueError('Invalid physical noise inputs')
    return float(np.sqrt(source_e+sky_e+n_pixels*n_reads*read_e**2)/source_e)


def main():
    timer=time.perf_counter();started=utc();out=[]
    for host in read(P11/'manifests/audit_hosts.json'):
        tic=int(host['tic_id']);inv=read(P11/f'results/input_inventory_v2/tic{tic}.json')
        best={}
        for rec in inv['records']:
            p=rec['metadata'];s=p.get('sector',-1)
            if s not in inv['audited_selected_sectors'] or not rec.get('source_matches'):continue
            rank={'SPOC':0,'TESS-SPOC':1,'QLP':2}
            if s not in best or rank[p['author']]<rank[best[s]['metadata']['author']]:best[s]=rec
        for s,rec in best.items():
            src=rec['source_matches'][0];path=REPO/src['path']
            base=dict(tic_id=tic,sector=s,author=rec['metadata']['author'],source_path=src['path'],source_sha256=sha(path),
                      formula='sqrt(N_source+N_sky+n_pixels*n_reads*read_noise_e**2)/N_source')
            with fits.open(path,memmap=False) as hd:
                h=hd[1].header;d=hd[1].data
                calibration={k:h.get(k,hd[0].header.get(k)) for k in ['INT_TIME','READTIME','FRAMETIM','NUM_FRM','NREADOUT','READNOIA','READNOIB','READNOIC','READNOID','GAINA','GAINB','GAINC','GAIND','CROWDSAP','FLFRCSAP']}
                aperture=next((x.data for x in hd[2:] if x.name=='APERTURE' and x.data is not None),None)
                errors=[]
                if aperture is None:errors.append('No supplied aperture mask')
                if calibration['INT_TIME'] is None or calibration['NREADOUT'] is None:errors.append('Missing live integration/readout counts')
                rn=[calibration[k] for k in ['READNOIA','READNOIB','READNOIC','READNOID'] if calibration[k] is not None]
                if not rn:errors.append('No electron read-noise calibration')
                unit=hd[1].columns['SAP_FLUX'].unit if 'SAP_FLUX' in d.names else None
                if unit!='e-/s':errors.append('SAP is not calibrated in electrons/second')
                if 'SAP_BKG' not in d.names:errors.append('No summed aperture sky flux')
                base['calibration']=calibration;base['flux_unit']=unit
                if errors:
                    out.append(dict(base,status='UNMEASURED',missing=errors));continue
                n_pixels=int(np.count_nonzero(aperture&2));n_reads=int(calibration['NREADOUT']);live=float(calibration['INT_TIME'])*n_reads
                good=np.isfinite(d['TIME'])&np.isfinite(d['SAP_FLUX'])&np.isfinite(d['SAP_BKG'])&(d['SAP_FLUX']>0)&(d['SAP_BKG']>=0)&((d['QUALITY']&rec['quality_mask'])==0)
                if good.sum()<50:out.append(dict(base,status='UNMEASURED',missing=['Fewer than 50 valid flux/sky rows']));continue
                source_rate=float(np.median(d['SAP_FLUX'][good]));sky_rate=float(np.median(d['SAP_BKG'][good]))
                source_e=source_rate*live;sky_e=sky_rate*live
                low=count_noise(source_e,sky_e,n_pixels,n_reads,min(rn));high=count_noise(source_e,sky_e,n_pixels,n_reads,max(rn))
                crowd=calibration['CROWDSAP']
                out.append(dict(base,status='MEASURED_MODEL_DIAGNOSTIC',n_aperture_pixels=n_pixels,live_integration_seconds=live,n_reads=n_reads,
                    source_plus_contaminant_electrons=source_e,sky_electrons=sky_e,read_noise_e_range=[min(rn),max(rn)],
                    source_photon_only_floor_ppt=1000/np.sqrt(source_e),total_SAP_point_noise_ppt_range=[1000*low,1000*high],
                    approximate_target_corrected_point_noise_ppt_range=[1000*low/crowd,1000*high/crowd] if crowd and 0<crowd<=1 else None,
                    target_source_electrons=source_e*crowd if crowd and 0<crowd<=1 else None,
                    contaminant_source_electrons=source_e*(1-crowd) if crowd and 0<crowd<=1 else None,
                    assumptions=['SAP_BKG is the supplied summed aperture background in e-/s.',
                        'NREADOUT times INT_TIME gives effective live integration; read noise spans all four calibrated CCD outputs rather than guessing the aperture amplifier.',
                        'The interval is an amplifier range, not a confidence interval. Cosmic-ray rejection/cotrending correlations and systematic variability are not modeled.',
                        'PDC comparison uses the approximate CROWDSAP scaling; the empirical transit-scale scatter remains the measured diagnostic.']))
    write(P11/'results/instrument_noise_model.json',dict(utc=utc(),rows=out,source_sha256=sha(__file__),wall_seconds=time.perf_counter()-timer,
        supersedes='Per-host noise_audit raw_diagnostics.total_noise_model placeholder: compact inventory headers omitted actual mission amplifier/live-time fields. QLP still lacks joint physical calibration.',
        references=['https://heasarc.gsfc.nasa.gov/docs/tess/data-products.html','https://heasarc.gsfc.nasa.gov/docs/tess/TESS-CosmicRayPrimer.html','https://ntrs.nasa.gov/api/citations/20180007935/downloads/20180007935.pdf']))
    append_event(P11/'manifests/queue_intervals.jsonl',dict(event='interval',phase='audit_instrument_noise',started_utc=started,ended_utc=utc(),wall_seconds=time.perf_counter()-timer))
    print('instrument noise models',sum(r['status']=='MEASURED_MODEL_DIAGNOSTIC' for r in out),'/',len(out),flush=True)


if __name__=='__main__':main()
