"""One top-level, unchanged p10.0 Stage C job in a fresh isolated case root."""
from common import REPO,ROOT,DATA,read,write,sha,utc,environment
environment()
import csv
import sys
import time
import traceback
import numpy as np
from blind_io import install,summary,SidecarAccessError
from science_json import safe
from funnel_worker import legacy
from full_funnel_plan import stage_decision
from part_f_guards_v1 import require_hash,assert_no_integrity_failure,IntegrityFailure,signal_integrity_failure


def validate_upstream(receipts):
    if (stage_decision(receipts['A'])!='PASS' or stage_decision(receipts['S']) not in ('PASS','HOLD') or
        stage_decision(receipts['B'])!='PASS'):
        raise IntegrityFailure('Stage C requires the unchanged A/S/B route to pass')


def setup_case(runtime,base):
    cid,tic=runtime['candidate_id'],int(runtime['tic_id'])
    if base['candidate_id']!=cid or int(base['tic_id'])!=tic:raise IntegrityFailure('C base candidate identity differs')
    root=REPO/runtime['output_root']
    if root.resolve()!=(DATA/f'funnel/C_cases_v1/{cid}').resolve():raise IntegrityFailure('Unexpected C output root')
    root.mkdir(parents=True,exist_ok=False)
    columns=sorted(set(base['candidate'])|set(base['star'])|{'period_days','tic_id'})
    candidate=dict(base['candidate'],**base['star'],tic_id=tic)
    for name,rows in [('survivors.csv',[candidate]),('candidates.csv',base['all_candidates'])]:
        with (root/name).open('x',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    F=legacy(root)
    import audit_p5 as A
    from tesshunter.survey import get_config
    A.set_input_config(get_config('survey_p10'));A.set_roots(root,REPO/'data/survey/audit_lc')
    def products(requested):
        if int(requested)!=tic:raise IntegrityFailure('Unexpected host in C raw input request')
        out=[]
        for product in base['raw_products']:
            path=REPO/product['raw_path'];require_hash(path,product['raw_sha256'],'Frozen C raw input')
            with np.load(path,allow_pickle=False) as z:record={k:np.asarray(z[k]) for k in z.files}
            record.update(product['metadata']);out.append(record)
        return out
    A.load_products=products
    star=base['star'];stellar={'radius':star['radius_rsun'],'mass':star['mass_msun'],'teff':star['teff_k'],
        'tmag':star['tmag'],'ra':star['ra_deg'],'dec':star['dec_deg']}
    A.stellar_from_cache=lambda requested:stellar if int(requested)==tic else {}
    if (F.V.RULE_SET.version!='p10.0' or F.V.RULE_SET.stagec_peak_rule!='strongest' or
        not F.V.RULE_SET.stagec_sde_robust_fallback or not F.V.RULE_SET.duration_floor_cadence):
        raise IntegrityFailure('C scientific route differs from frozen p10.0')
    jobs=F.V.jobs()
    if len(jobs)!=1 or jobs[0]['tic_id']!=tic or jobs[0]['planet_num']!=int(base['candidate']['planet_num']):
        raise IntegrityFailure('C table conversion changed candidate identity')
    return F,jobs[0],root


def main(runtime_name,expected_hash):
    assert_no_integrity_failure();require_hash(REPO/runtime_name,expected_hash,'C runtime')
    runtime=read(REPO/runtime_name);cid=runtime['candidate_id']
    result_path=ROOT/f'results/funnel/C/{cid}.json'
    if result_path.exists():raise RuntimeError('No scientific retry for C')
    guard=install(ROOT/f'results/funnel_io/C_{cid}.jsonl',REPO/'data/cache/catalogs/spoc_tce/spoc_tce.ephemerides.csv')
    started,timer,cpu=utc(),time.perf_counter(),time.process_time()
    try:
        if runtime['threads']!=8 or runtime['oversampling']!=3:raise IntegrityFailure('C execution arguments differ')
        for path,digest in runtime['source_hashes'].items():require_hash(REPO/path,digest,'C registered source')
        require_hash(ROOT/'manifests/stage_C_method_registration_v1.json',runtime['method_registration_sha256'],'C method registration')
        require_hash(REPO/runtime['selection_path'],runtime['selection_sha256'],'C frozen selection')
        require_hash(REPO/runtime['base_runtime_path'],runtime['base_runtime_sha256'],'C base runtime')
        base=read(REPO/runtime['base_runtime_path'])
        for path,digest in base['source_hashes'].items():require_hash(REPO/path,digest,'Original early-funnel source')
        upstream={}
        for path,digest in runtime['upstream_hashes'].items():
            require_hash(REPO/path,digest,'C upstream evidence');receipt=read(REPO/path);upstream[receipt['stage']]=receipt
        validate_upstream(upstream)
        # Verify raw identities outside the legacy exception handler as well.
        for product in base['raw_products']:require_hash(REPO/product['raw_path'],product['raw_sha256'],'C raw input')
        F,job,root=setup_case(runtime,base)
        measurement=F.V.stagec_one(job,threads=8,oversampling=3,force=False)
        # Legacy stagec_one catches ordinary exceptions. Recheck raw bytes and
        # the open guard here so an integrity exception cannot be downgraded.
        for product in base['raw_products']:require_hash(REPO/product['raw_path'],product['raw_sha256'],'C raw input after measurement')
        io=summary(guard)
        if io['sidecar_open_attempts']:raise IntegrityFailure('Ephemeris sidecar accessed by C worker')
        status='COMPLETE' if measurement.get('decision') in ('PASS','FAIL') else 'OPERATIONAL_UNKNOWN'
        receipt=dict(candidate_id=cid,tic_id=runtime['tic_id'],stage='C',status=status,measurement=measurement,
            io=io,case_root=runtime['output_root'],threads=8,oversampling=3,rules_version='p10.0')
    except (IntegrityFailure,SidecarAccessError) as error:
        signal_integrity_failure(error,dict(phase='funnel_C',candidate_id=cid));raise
    except Exception as error:
        receipt=dict(candidate_id=cid,tic_id=runtime['tic_id'],stage='C',status='OPERATIONAL_UNKNOWN',
            error=f'{type(error).__name__}: {error}',traceback=traceback.format_exc(),io=summary(guard))
    receipt.update(started_utc=started,completed_utc=utc(),wall_seconds=time.perf_counter()-timer,
        cpu_seconds=time.process_time()-cpu,runtime_sha256=expected_hash,scientific_attempt=1,
        method_registration_sha256=runtime['method_registration_sha256'])
    write(result_path,safe(receipt))
    write(ROOT/f'results/funnel_timing/C/{cid}.json',{k:v for k,v in safe(receipt).items() if k not in ('measurement','io')})
    print(cid,receipt['status'],(receipt.get('measurement') or {}).get('decision'),flush=True)
    if receipt['status']!='COMPLETE':raise SystemExit(2)


if __name__=='__main__':
    try:main(sys.argv[1],sys.argv[2])
    except (IntegrityFailure,SidecarAccessError) as error:
        signal_integrity_failure(error,dict(phase='funnel_C',runtime=sys.argv[1]));raise
