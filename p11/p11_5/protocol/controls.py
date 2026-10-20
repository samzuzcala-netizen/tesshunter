"""Evaluator-only exact historical control registration and trusted raw handoff."""
from common import *
environment()
import ast,csv,sys,re,time
from collections import Counter,defaultdict
import numpy as np
from astropy.io import fits
sys.path[:0]=[str(REPO/'src'),str(ROOT/'protocol')]
from tesshunter import survey_p8
from candidates import sources,catalogues

def legacy_inventory_functions():
    # Import only pure readers, never the historical fixed-path main/writer.
    p=REPO/'p11/protocol/input_inventory.py';tree=ast.parse(p.read_text(encoding='utf-8'))
    keep={'scalar','candidate_files','source_info','equal','timing_pair','inventory_host'}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in keep or
           isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('AUTHORS','HEADERS') for t in n.targets)]
    namespace=dict(globals());exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),namespace)
    return namespace

def first_survivor(root):
    return next(csv.DictReader((Path(root)/'survivors.csv').open(encoding='utf-8-sig')))

def standard_candidate(row,tid):
    return dict(tic_id=tid,period=float(row.get('period_days',row.get('period'))),
        period_days=float(row.get('period_days',row.get('period'))),epoch_btjd=float(row['epoch_btjd']),
        duration_days=float(row['duration_days']),depth_ppt=float(row['depth_ppt']),
        stitch_snr=float(row.get('stitch_snr') or row.get('snr') or 0),
        stitch_n_transits=int(float(row.get('stitch_n_transits') or row.get('n_transits') or 3)),
        planet_num=int(float(row.get('planet_num') or 1)),rank=int(float(row.get('rank') or 1)),
        n_units=int(float(row.get('n_units') or 1)),tmag=float(row.get('tmag') or 0))

def star_row(row,tid):
    path=REPO/f'data/cache/tic/tic{tid}.json'
    # Runtime A independently uses the unchanged TIC-cache precedence. Tables
    # below preserve their measured input fields as the same fallback.
    return {k:float(row.get(k) or fallback) for k,fallback in [('radius_rsun',1),('mass_msun',1),('teff_k',5500),('tmag',0)]}

def register():
    entries=[]
    def add(collection,identity,tid,candidate,star,raw,source,model=None,native=False,protected=False,restrict=None):
        entries.append(dict(collection=collection,original_id=identity,tic_id=tid,candidate=candidate,star=star,
            original_raw_root=str(raw),source_path=Path(source).relative_to(REPO).as_posix(),source_sha256=sha(source),
            fixed_absolute_model=model,native_control=native,original_protected_rejection=protected,
            restrict_sectors=restrict,exposure='HISTORICAL_DEVELOPMENT_ENGINEERING'))
    for p in sorted((REPO/'data/survey/p10/secondary_modes/adv').glob('*.json')):
        r=read(p);tid=int(r['tic_id']);e=r['eph']
        candidate=standard_candidate(dict(period=e['period'],epoch_btjd=e['t0'],duration_days=e['duration'],depth_ppt=r['survey_depth_ppt']),tid)
        add('S_original_40',r['key'],tid,candidate,dict(radius_rsun=r['rstar'],mass_msun=r['mstar'],teff_k=r['teff'],tmag=0),
            r['lc_root'],p,native=True,protected=r['gates']['bound']=='FAIL')
    assert len(entries)==40 and sum(r['original_protected_rejection'] for r in entries)==26
    p=REPO/'p10/results/original_adversarial_c_manifest.json';manifest=read(p)
    half=set(read(REPO/'p10/results/stage_c_corrected_control_measurements.json')['half_double_case_ids'])
    for item in manifest['items']:
        r=item['record'];tid=int(r['tic_id']);sv=first_survivor(r['source_root'])
        idx=read(Path(r['lc_root'])/f'tic{tid}/index.json')
        add('C_original_41',item['id'],tid,standard_candidate(sv,tid),star_row(sv,tid),r['lc_root'],p,
            native=True,restrict=[int(q['sector']) for q in idx['products']])
        entries[-1]['known_half_double']=item['id'] in half
    p=REPO/'p10/results/stage_c_corrected_control_manifest.json';manifest=read(p)
    for item in manifest['items']:
        if item['set']!='inj':continue
        tid=int(item['record']['tic_id']);sv=item['injection']
        add('C_injection_30',item['id'],tid,standard_candidate(sv,tid),star_row(sv,tid),item['record']['lc_root'],p,model=item['injection_model'])
    p=REPO/'p10/results/stage_c_native_corrected_20260910.json'
    for row in read(p)['rows']:
        sv=first_survivor(REPO/row['workspace']);tid=int(sv['tic_id'])
        add('C_native_37',row['set']+'_'+row['key'],tid,standard_candidate(sv,tid),star_row(sv,tid),REPO/'data/survey/audit_lc',p)
    # Exactly the final P10 calibration's 200 bound-S kills, not the earlier 189.
    base=REPO/'data/survey/p10/part2d/calibration';killed=[]
    expected=read(base/'expected_snr_p10.json')
    calibration=read(REPO/'p10/results/part2d_calibration_20260912/calibration_manifest.json')
    for job in calibration['recovered_jobs']:
        jid=job['job_id'];tid=int(job['tic_id']);key=f'tic{tid}_P{float(job["period_days"]):.4f}'
        ap=base/f'inj_funnel/{jid}/stageA/{key}.json';sp=base/f'inj_funnel/{jid}/secondary/{key}.json'
        if ap.exists() and sp.exists() and read(ap).get('decision')=='PASS' and read(sp).get('gate')=='FAIL':
            killed.append(dict(job=job,snr=float(expected[jid]['snr_expected']),source=sp))
    assert len(killed)==200,len(killed)
    bins=[[r for r in killed if lo<=r['snr']<hi] for lo,hi in ((7,15),(15,50))]
    for group in bins:group.sort(key=lambda r:(order(r['job']['tic_id'],'negative_controls'),r['job']['job_id']))
    selected=bins[0][:30]+bins[1][:30]
    if len(selected)<60:
        remainder=[r for group in bins for r in group if r not in selected];selected+=remainder[:60-len(selected)]
    assert len(selected)==60
    for row in selected:
        j=row['job'];tid=int(j['tic_id']);model={k:j['inj_'+k] for k in ('period','t0','rp_rs','b','a_rs','u1','u2')}
        add('S_killed_60',j['job_id'],tid,standard_candidate(j,tid),star_row(j,tid),REPO/'data/survey/audit_lc',row['source'],model=model)
        entries[-1]['historical_snr_expected']=row['snr']
    for i,row in enumerate(entries):row['registration_id']=f'control{i:03d}'
    write(ROOT/'manifests/controls_evaluator.json',dict(utc=utc(),entries=entries,counts=dict(Counter(r['collection'] for r in entries)),
        protected_original_ids=[r['original_id'] for r in entries if r['original_protected_rejection']],
        S_killed_original_n=200,S_killed_strata_denominators=[len(g) for g in bins],
        S_killed_selected=[r['job']['job_id'] for r in selected],half_double_ids=sorted(half),
        truth_runtime_excluded=True,overlap_rule='Join final exact candidate ephemeris plus frozen product/input and configuration identity; TIC alone never joins.'))
    tics=sorted({r['tic_id'] for r in entries});reader=legacy_inventory_functions();lookup=reader['candidate_files']()
    write(ROOT/'manifests/control_source_files.json',{str(t):[p.relative_to(REPO).as_posix() for p in lookup[t]] for t in tics})
    jobs=[dict(job_id=f'control_audit_tic{t}',command=['p11/p11_5/protocol/controls.py','audit',str(t)],
               source_paths=['p11/p11_5/protocol/common.py','p11/protocol/input_inventory.py']) for t in tics]
    write(ROOT/'manifests/control_input_audits.json',jobs)
    print('control entries',len(entries),'distinct hosts',len(tics),'S killed bin denominators',[len(g) for g in bins])

def audit(tic):
    started=time.perf_counter()
    previous=REPO/f'p11/results/input_inventory_v2/tic{tic}.json'
    if previous.exists():
        r=read(previous)
        for p in r['records']:
            if p.get('raw_path') and sha(REPO/p['raw_path'])!=p['raw_sha256']:raise ValueError('Historical raw changed')
            for s in p.get('source_matches',[]):
                if sha(REPO/s['path'])!=s['sha256']:raise ValueError('Historical FITS changed')
        r=dict(r,p11_5_reuse=dict(path=previous.relative_to(REPO).as_posix(),sha256=sha(previous)))
    else:
        reader=legacy_inventory_functions();paths=[REPO/p for p in read(ROOT/'manifests/control_source_files.json')[str(tic)]]
        r=reader['inventory_host'](dict(tic_id=tic),paths)
    r['p11_5_wall_seconds']=time.perf_counter()-started
    write(ROOT/f'results/control_inputs/tic{tic}.json',r)
    print('control inputs audited',tic,flush=True)

if __name__=='__main__':
    if sys.argv[1]=='register':register()
    elif sys.argv[1]=='audit':audit(int(sys.argv[2]))
