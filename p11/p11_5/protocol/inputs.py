"""Bounded metadata reconciliation and frozen product eligibility, without scores."""
from common import *
environment()
import csv
import sys
import time
import shutil
from collections import Counter, defaultdict
from urllib.parse import quote
import requests
import numpy as np

EXCLUDED = {80,83,85,99,100,101,102,103,104}
AUTHOR = {'SPOC':0,'TESS-SPOC':1,'QLP':2}

def fetch(url, name, request=None):
    path=DATA/'acquisition'/name
    if path.exists(): return path
    used=81827574+sum(read(p)['bytes'] for p in (ROOT/'results/acquisition').glob('*.json'))
    assert used<15000000000 and shutil.disk_usage(REPO).free>31000000000
    start=time.perf_counter()
    response=requests.post(url,data={'request':json.dumps(request)},timeout=(15,45)) if request else requests.get(url,timeout=(15,45))
    body=response.content
    assert used+len(body)<=15000000000 and shutil.disk_usage(REPO).free-len(body)>=30000000000
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
    write(ROOT/'results/acquisition'/(name.replace('/','_')+'.json'),dict(utc=utc(),url=url,
        request=request,status_code=response.status_code,bytes=len(body),path=path.relative_to(REPO).as_posix(),
        sha256=sha(path),wall_seconds=time.perf_counter()-start))
    return path

def metadata():
    hosts=read(REPO/'p11/manifests/development_hosts.json')
    original={int(r['tic_id']):r for r in csv.DictReader((REPO/'data/survey/cache/p8/pool_products.csv').open())}
    listed=[int(r['tic_id']) for r in hosts if '105' in original[int(r['tic_id'])]['sectors_any_lc'].split(',')]
    ids=sorted(set(listed+[288430636]))
    request=dict(service='Mast.Caom.Filtered',params=dict(columns='*',filters=[
        dict(paramName='target_name',values=[str(t) for t in ids]),
        dict(paramName='provenance_name',values=list(AUTHOR)),
        dict(paramName='dataproduct_type',values=['timeseries'])]),format='json',pagesize=50000,page=1)
    p=fetch('https://mast.stsci.edu/api/v0/invoke','bounded_metadata.json',request)
    response=read(p)
    assert response['status']=='COMPLETE' and response.get('paging',{}).get('pagesFiltered',1)==1
    obs=response['data']
    s105=[r for r in obs if int(r.get('sequence_number') or -1)==105]
    omission=[r for r in obs if int(r['target_name'])==288430636 and int(r.get('sequence_number') or -1)==69]
    for label,url in [('mast_qlp','https://archive.stsci.edu/hlsp/qlp'),('mit_qlp','https://tess.mit.edu/qlp/'),
                      ('tls_faq','https://transitleastsquares.readthedocs.io/en/latest/FAQ.html'),
                      ('tess_products','https://heasarc.gsfc.nasa.gov/docs/tess/data-products.html')]:
        fetch(url,label+'.html')
    write(ROOT/'results/sector_reconciliation.json',dict(utc=utc(),sector_set=list(range(56,106)),
        listed_s105_original_hosts=listed,original_product_manifest_sha256=sha(REPO/'data/survey/cache/p8/pool_products.csv'),
        original_s105_list_sha256=sha(REPO/'data/survey/cache/target_lists/qlp_s0105.npy'),
        current_s105_observations=s105,sector69_omission_observations=omission,
        metadata_sha256=sha(p),interpretation='Target-list membership is not proof of delivered, usable light curves. No latest-sector expansion.'))
    print('sector105 listed',len(listed),'observations',len(s105),'omission69',len(omission),flush=True)

def register():
    hosts=read(REPO/'p11/manifests/development_hosts.json')
    targets={int(r['tic_id']):r for r in csv.DictReader((REPO/'data/survey/targets_p8.csv').open())}
    host_rows=[];products=[];excluded=[]
    for host in hosts:
        tic=int(host['tic_id']);meta=targets[tic]
        inv=read(REPO/f'p11/results/input_inventory_v2/tic{tic}.json')
        valid=[]
        for p in inv['records']:
            m=p['metadata'];sec=int(m['sector']);why=[]
            if not 56<=sec<=105:why.append('OUTSIDE_FROZEN_SECTOR_SET')
            if m['author']=='QLP' and sec in EXCLUDED:why.append('UNRESOLVED_QLP_TIMING')
            if not p.get('checks') or not all(p['checks'].values()):why.append('SOURCE_IDENTITY_OR_TIME_REFERENCE_UNVERIFIED')
            if p.get('n_quality_good',0)<50:why.append('INSUFFICIENT_QUALITY_POINTS')
            if m.get('cadence_s',1e9)>300:why.append('COARSER_THAN_NATIVE_POLICY')
            if m['author']=='SPOC' and abs(m.get('cadence_s',0)-120)>5:why.append('NONSTANDARD_TARGETED_CADENCE')
            if m['author']=='QLP' and 74<=sec<=79 and p.get('timing_status')!='QLP_74_79_CORRECTED_SOURCE_VERIFIED':why.append('CORRECTED_SOURCE_REQUIRED')
            if why:
                excluded.append(dict(tic_id=tic,metadata=m,raw_path=p.get('raw_path'),reasons=why));continue
            assert sha(REPO/p['raw_path'])==p['raw_sha256']
            for src in p['source_matches']:
                assert sha(REPO/src['path'])==src['sha256']
            valid.append(p)
        # Acquisition additions use the identical audit record schema.
        ap=ROOT/f'results/additional_products/tic{tic}.json'
        if ap.exists():valid+=read(ap)
        ffi={p['metadata']['sector'] for p in valid if p['metadata']['author'] in ('QLP','TESS-SPOC') and abs(p['metadata']['cadence_s']-200)<=5}
        twomin={int(s) for s in meta['sectors_2min'].split(',') if s}
        best={}
        for p in valid:
            s=p['metadata']['sector']
            if s not in best or AUTHOR[p['metadata']['author']]<AUTHOR[best[s]['metadata']['author']]:best[s]=p
        selected=[best[s] for s in sorted(best)]
        cuts=(float(meta['teff_k'])<3600 and float(meta['radius_rsun'])<.45 and
              12.5<=float(meta['tmag'])<=14 and abs(float(meta['galactic_lat_deg']))>=20 and meta['gaia_dwarf_check']=='pass')
        reasons=[]
        if not cuts:reasons.append('ORIGINAL_P8_CUTS_FAIL')
        if len(ffi)<3:reasons.append('FEWER_THAN_THREE_VERIFIED_NATIVE_FFI_SECTORS')
        if len(twomin&ffi)>=len(ffi)/2:reasons.append('TARGETED_SECTORS_NOT_STRICT_MINORITY')
        population='D_core' if not reasons else 'D_aux' if selected else 'INPUT_INELIGIBLE'
        entries=[]
        for p in selected:
            record=dict(tic_id=tic,metadata=p['metadata'],raw_path=p['raw_path'],raw_sha256=p['raw_sha256'],
                        source_matches=p['source_matches'],checks=p['checks'],n_quality_good=p['n_quality_good'])
            products.append(record);entries.append(dict(p['metadata'],file=str((REPO/p['raw_path']).resolve())))
        rawroot=DATA/f'raw/tic{tic}'
        write(rawroot/'index.json',dict(tic_id=tic,products=entries,source='P11.5 frozen audited common inputs'))
        pts=sum(p['n_quality_good'] for p in selected)
        baseline=max((p['metadata']['t_end'] for p in selected),default=0)-min((p['metadata']['t_start'] for p in selected),default=0)
        hr=dict(tic_id=tic,original=meta,population=population,exclusion_reasons=reasons,
            verified_native_ffi_sectors=sorted(ffi),targeted_ffi_sectors=sorted(twomin&ffi),selected_sectors=sorted(best),
            n_ffi=len(ffi),n_selected=len(selected),n_quality_points=pts,baseline_days=baseline,
            product_authors=dict(Counter(p['metadata']['author'] for p in selected)),
            selected_raw_hashes=[p['raw_sha256'] for p in selected],
            crowding=[s['headers'].get('CROWDSAP') for p in selected for s in p['source_matches']],
            input_key=digest([p['raw_sha256'] for p in selected]))
        host_rows.append(hr)
    injections=[]
    bytic={r['tic_id']:r for r in host_rows}
    for row in csv.DictReader((REPO/'data/survey/p10/injections_2b.csv').open()):
        oldpath=REPO/f'data/survey/runs/p10_2b/e_inj/results/{row["job_id"]}.json'
        old=read(oldpath)
        injections.append(dict(original=row,job_id=row['job_id'],tic_id=int(row['tic_id']),
            original_result_sha256=sha(oldpath),fixed_absolute_model=old['injection_model'],
            input_status='ELIGIBLE' if bytic[int(row['tic_id'])]['population']=='D_core' else 'INPUT_INELIGIBLE'))
    assert len(host_rows)==300 and len(injections)==600
    write(ROOT/'manifests/hosts.json',host_rows);write(ROOT/'manifests/products.json',products)
    write(ROOT/'manifests/injections_evaluator.json',injections);write(ROOT/'manifests/product_exclusions.json',excluded)
    write(ROOT/'manifests/exposure.json',dict(utc=utc(),original_hosts=[r['tic_id'] for r in host_rows],
        permanent_exposure='All historical P8/P9/P10 candidates, old controls and P11 audit hosts remain development-exposed, including input-excluded hosts.',
        validation_outcomes_opened=False,reserved_ephemerides_opened=False))
    counts=Counter(r['population'] for r in host_rows)
    write(ROOT/'results/input_counts.json',dict(original_hosts=300,original_injections=600,populations=dict(counts),
        eligible_injections=sum(r['input_status']=='ELIGIBLE' for r in injections),evaluated_hosts=0,evaluated_injections=0,
        selected_products=len(products),excluded_products=len(excluded)))
    paths=[ROOT/'PREREGISTRATION_P11_5.md',ROOT/'protocol/config.json',ROOT/'protocol/PROMPT_P11_5.txt',
           ROOT/'manifests/hosts.json',ROOT/'manifests/products.json',ROOT/'manifests/injections_evaluator.json',ROOT/'manifests/product_exclusions.json']
    write(ROOT/'manifests/input_freeze.json',dict(utc=utc(),hashes={p.relative_to(REPO).as_posix():sha(p) for p in paths}))
    resume(f'Input registration complete: {dict(counts)}. No new development efficacy inspected. Next: native preparation eligibility check, R1/C implementation and timing pilot. Historical queues stay closed.')
    print(dict(counts),'eligible injections',sum(r['input_status']=='ELIGIBLE' for r in injections),flush=True)

if __name__=='__main__':
    {'metadata':metadata,'register':register}[sys.argv[1]]()
