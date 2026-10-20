"""Final read-only comparison of Part 3 evidence and new source/data seals."""
from common import REPO,ROOT,DATA,read,write,sha,utc,environment
environment()
import os,json,time,math,psutil
from pathlib import Path
from part_f_guards_v1 import assert_no_integrity_failure,require_hash
from registration_execution_v3 import verify

def dead(d):
    try:
        p=psutil.Process(d['pid'])
        assert abs(p.create_time()-d['create_time'])>=.01, 'A recorded closed process is alive'
    except psutil.NoSuchProcess:pass

def main():
    started=utc();timer=time.perf_counter()
    assert_no_integrity_failure();verify(require_launch_seal=True)
    assert not (ROOT/'manifests/controller_owner.json').exists()
    assert not (ROOT/'results/final_evidence_audit.json').exists()
    historical=read(ROOT/'results/integrity_final/summary.json')
    assert historical['status']=='PASS' and not historical['mismatches'] and not historical['verifier_errors']
    regression=read(ROOT/'results/final_regression_isolated.json');assert regression['status']=='PASS'
    for suite in regression['suites']:require_hash(REPO/suite['log_path'],suite['log_sha256'],'Final regression log')
    parent_names=('input_data_seal.json','execution_launch_seal.json','full_search_plan_seal.json',
      'timing_pilot_closed_evidence_seal.json','predictions_survey_p10_seal.json','predictions_survey_p8_seal.json',
      'early_funnel_closed_evidence_seal.json','forced_fits_closed_evidence_seal.json','stage_C_closed_evidence_seal.json',
      'autopsies_closed_evidence_seal.json')
    expected={};parents={}
    for name in parent_names:
        path=ROOT/'manifests'/name;seal=read(path)
        mapping=seal.get('files') if isinstance(seal.get('files'),dict) else seal.get('hashes')
        if mapping is None and isinstance(seal.get('path'),str) and isinstance(seal.get('sha256'),str):
            mapping={seal['path']:seal['sha256']}
        assert isinstance(mapping,dict), (name,list(seal))
        for relative,digest in mapping.items():
            digest=digest['sha256'] if isinstance(digest,dict) else digest
            assert isinstance(digest,str) and len(digest)==64
            assert relative not in expected or expected[relative]==digest, ('Conflicting parent hashes',relative)
            expected[relative]=digest
        parents[path.relative_to(REPO).as_posix()]=sha(path)
    verified={};total=0
    for i,(relative,digest) in enumerate(sorted(expected.items()),1):
        path=REPO/relative
        got=sha(path)
        assert got==digest, ('Final parent mismatch',relative,digest,got)
        verified[relative]=got;total+=path.stat().st_size
        if i%10000==0:print(json.dumps(dict(parent_files_verified=i,bytes_verified=total)),flush=True)
    source_hashes={}
    for name in ('part_f_method_registration_v1.json','stage_C_method_registration_v1.json','retention_analysis_registration_v1.json','autopsy_method_registration_v1.json'):
        path=ROOT/'manifests'/name;reg=read(path)
        for relative,digest in reg['source_hashes'].items():
            require_hash(REPO/relative,digest,'Final registered source')
            assert relative not in source_hashes or source_hashes[relative]==digest
            source_hashes[relative]=digest
        parents[path.relative_to(REPO).as_posix()]=sha(path)
    for folder in ('protocol','tests'):
        for path in sorted((ROOT/folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix in ('.py','.json'):
                relative=path.relative_to(REPO).as_posix();digest=sha(path)
                assert relative not in source_hashes or source_hashes[relative]==digest
                source_hashes[relative]=digest
    data_hashes={};data_bytes=0
    for i,path in enumerate(sorted(p for p in DATA.rglob('*') if p.is_file()),1):
        assert path.name!='ctoi_fields.json' and 'stageD' not in path.parts
        relative=path.relative_to(REPO).as_posix()
        data_hashes[relative]=verified.get(relative) or sha(path)
        data_bytes+=path.stat().st_size
        if i%10000==0:print(json.dumps(dict(new_data_files_sealed=i,new_data_bytes=data_bytes)),flush=True)
    closed=0;attempts=0
    for path in sorted((ROOT/'results/controllers').glob('*/closure.json')):
        d=read(path);assert d['status']=='CLOSED' and d['pending']==0 and d['all_owned_workers_closed'] and d['source_hashes_unchanged'],path
        dead(d['owner']);closed+=1
        for ap in (path.parent/'attempts').glob('*.json'):
            a=read(ap);dead(a);attempts+=1
    ledger=read(ROOT/'manifests/resource_ledger.json')
    assert math.isclose(sum(i['hours'] for i in ledger['intervals']),ledger['new_queue_hours'],abs_tol=1e-9)
    assert ledger['new_queue_hours']<=31.98 and ledger['prior_queue_hours']+ledger['new_queue_hours']<=48
    assert ledger['cumulative_acquisition_budget_charge_upper_bytes']<=15_000_000_000
    assert psutil.disk_usage('C:\\').free>25_000_000_000
    checks=[json.loads(line) for line in (ROOT/'logs/checkins.jsonl').read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    schedule=read(ROOT/'manifests/checkin_schedule.json');assert len(checks)==schedule['count']==34
    for p in ('survey_p10','survey_p8'):
        assert read(ROOT/f'manifests/predictions_{p}.json')['n_hosts']==436
    assert read(ROOT/'results/autopsy_closure_summary.json')['n_complete']==5
    analysis=read(ROOT/'results/retention_analysis.json')
    assert len(analysis['search_tables'])==228 and len(analysis['funnel_tables'])==42
    assert all(analysis['calibration'][p]['fires'] for p in ('survey_p10','survey_p8'))
    for r in analysis['search_tables']:
        assert r['n_in_band']+r['n_outside']==r['n_total']
        assert r['n_exact']+r['n_alias_only']+r['n_not_recovered']+r['search_unknown']==r['n_in_band']
        assert sum(c['numerator'] for c in r['matrix'].values())==r['n_in_band']-r['search_unknown']-r['forced_unknown']
    write(ROOT/'manifests/final_source_seal.json',dict(utc=utc(),files=source_hashes,n_files=len(source_hashes),parent_registration_seals=parents))
    write(ROOT/'manifests/final_data_seal.json',dict(utc=utc(),files=data_hashes,n_files=len(data_hashes),n_bytes=data_bytes,
          outside_input_data_seal='p10/part3/manifests/input_data_seal.json',outside_input_data_seal_sha256=sha(ROOT/'manifests/input_data_seal.json')))
    result=dict(started_utc=started,completed_utc=utc(),wall_seconds=time.perf_counter()-timer,status='PASS',
          engineering_time=True,historical_verifier_receipt_sha256=sha(ROOT/'results/integrity_final/summary.json'),
          parent_seals=parents,unique_parent_files_verified=len(verified),parent_bytes_verified=total,
          new_scientific_data_files=len(data_hashes),new_scientific_data_bytes=data_bytes,source_files=len(source_hashes),
          closed_controller_phases=closed,closed_recorded_workers=attempts,owner_present=False,
          ledger_intervals_reconciled=True,new_queue_hours=ledger['new_queue_hours'],checkins_reconciled=len(checks),
          final_source_seal_sha256=sha(ROOT/'manifests/final_source_seal.json'),final_data_seal_sha256=sha(ROOT/'manifests/final_data_seal.json'),
          report_table_counts_verified=True,forbidden_endpoint_outputs_found=False)
    write(ROOT/'results/final_evidence_audit.json',result)
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
