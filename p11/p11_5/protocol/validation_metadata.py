"""Outcome-free fresh-domain candidate frame. Does not acquire or draw truth."""
from common import *
import csv,sys
from collections import Counter

def frame():
    excluded=set();exposure_sources={}
    for name in ('targets_p8.csv','targets_v1.csv','targets_v1_fallback.csv'):
        path=REPO/'data/survey'/name
        ids={int(r['tic_id']) for r in csv.DictReader(path.open(encoding='utf-8-sig'))}
        excluded|=ids;exposure_sources[path.relative_to(REPO).as_posix()]=dict(sha256=sha(path),ids=len(ids))
    for directory in (REPO/'p9/inputs/raw',REPO/'data/survey/audit_lc'):
        ids={int(p.name[3:]) for p in directory.glob('tic*') if p.is_dir() and p.name[3:].isdigit()}
        excluded|=ids;exposure_sources[directory.relative_to(REPO).as_posix()]=dict(ids=len(ids),meaning='Conservative exclusion of every previously acquired historical host')
    controls=read(ROOT/'manifests/controls_evaluator.json')['entries'];excluded|={r['tic_id'] for r in controls}
    rows=[];reasons=Counter();path=REPO/'data/survey/cache/p8/pool_after_xmatch.csv'
    for r in csv.DictReader(path.open(encoding='utf-8-sig')):
        tid=int(r['tic_id'])
        try:
            if not (float(r['Teff'])<3600 and float(r['rad'])<.45 and 12.5<=float(r['Tmag'])<=14 and abs(float(r['gallat']))>=20):continue
            if r['gaia_dwarf_check']!='pass' or r['lumclass'] not in ('DWARF',''):continue
            # This excludes the whole bare-SPOC/TCE association source pool,
            # including any reserved 531 subset, without reading an ephemeris.
            if r['xmatch_status']!='CLEAN':reasons['original_catalogue_domain_or_TCE_exclusion']+=1;continue
            if tid in excluded:reasons['previously_exposed_or_conservatively_acquired']+=1;continue
            parse=lambda value:{int(s) for s in value.split(',') if s}
            qlp=parse(r['sectors_qlp'])-{80,83,85,99,100,101,102,103,104}
            spoc=parse(r['sectors_tess_spoc'])
            ffi={s for s in qlp|spoc if 56<=s<=105}
            targeted=parse(r['sectors_2min_list'])
            if len(ffi)<3 or len(ffi&targeted)>=len(ffi)/2:reasons['metadata_coverage_upper_bound_fails']+=1;continue
            mag=float(r['Tmag']);stratum=f'{min(2,int((mag-12.5)/.5))}:{0 if len(ffi)<=5 else 1 if len(ffi)<=10 else 2}'
            rows.append(dict(tic_id=tid,hash=order(tid,'validation'),stratum=stratum,
                radius_rsun=float(r['rad']),mass_msun=float(r['mass'] or r['rad']),teff_k=float(r['Teff']),tmag=mag,
                ra_deg=float(r['ra']),dec_deg=float(r['dec']),galactic_lat_deg=float(r['gallat']),
                ffi_sector_upper_bound=sorted(ffi),targeted_sectors=sorted(targeted),
                input_eligibility='UNVERIFIED_METADATA_CANDIDATE',outcome_exposed=False))
        except (ValueError,TypeError):reasons['missing_required_metadata']+=1
    groups={s:sorted([r for r in rows if r['stratum']==s],key=lambda r:r['hash']) for s in sorted({r['stratum'] for r in rows})}
    ordered=[];used={s:0 for s in groups}
    for i in range(len(rows)):
        key=max((s for s in groups if used[s]<len(groups[s])),key=lambda s:((i+1)*len(groups[s])/len(rows)-used[s],s))
        ordered.append(groups[key][used[key]]);used[key]+=1
    write(ROOT/'manifests/validation_metadata_frame.json',dict(utc=utc(),source_sha256=sha(path),
        previously_exposed_excluded_ids=sorted(excluded),exposure_sources=exposure_sources,
        n_metadata_candidates=len(rows),stratum_counts={s:len(v) for s,v in groups.items()},exclusion_counts=dict(reasons),
        reserved_ephemerides_opened=False,reserved_ID_handling='Exclude the complete non-CLEAN catalogue-association source pool, a conservative superset of any reserved bare-SPOC/TCE subset; no 531 cohort was selected by closed P10.',
        actual_validation_cohort_selected=False,truth_drawn=False,rows=ordered,
        next_admission='Only after an eligible development finalist: freeze an affordable metadata-only acquisition frame, audit all frame members under exact common-input policy, then stratified sample one largest supported 300/200/100 level. For audited eligible stratum N_s and selected n_s publish inclusion n_s/N_s and conditional weights N_s/n_s. Do not claim metadata upper bounds are verified coverage.'))
    print('metadata-only fresh candidates',len(rows),'strata',{s:len(v) for s,v in groups.items()})

if __name__=='__main__':frame()
