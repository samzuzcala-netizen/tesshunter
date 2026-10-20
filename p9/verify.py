"""Read-only evidence verification. A receipt is written outside all locked hosts."""
from common import *
import argparse,csv,collections,subprocess

def run(partial=False):
    checks={};failures=[]
    def check(name,value):
        checks[name]=bool(value)
        if not value:failures.append(name)
    def hashes(name,root,mapping):
        bad=[k for k,h in mapping.items() if not (root/k).is_file() or sha(root/k)!=h]
        check(name,not bad)
        if bad:checks[name+'_mismatches']=bad
    hashes('archived_scientific_source_unchanged',BASE,read(P9/'baseline/source_hashes.json'))
    hashes('historical_P8_and_existing_followups_unchanged',REPO,read(P9/'baseline/preserved_hashes.json'))
    hashes('P8_target_lists_unchanged',REPO,read(P9/'baseline/target_list_hashes.json'))
    hashes('two_minute_lists_unchanged',REPO,read(P9/'baseline/twomin_list_hashes.json'))
    check('corrected_coverage_inventory_unchanged',sha(P9/'manifests/coverage_corrected.json')==read(P9/'protocol/coverage_correction.json')['corrected_sha256'])
    hashes('truth_catalogue_snapshots_unchanged',P9/'truth/catalogues',
      {k:v['sha256'] for k,v in read(P9/'truth/catalogues/receipts.json').items()})
    hashes('production_catalogue_snapshot_unchanged',P9/'truth/production_catalogues',read(P9/'truth/production_catalogues_hashes.json'))
    if (P9/'calibration/p8_source_hashes.json').exists():
        hashes('rescored_P8_injection_evidence_unchanged',REPO,read(P9/'calibration/p8_source_hashes.json'))
    if (P9/'results/historical_B_caps.json').exists():
        hs=read(P9/'results/historical_B_caps.json')['source_sha256']
        hashes('historical_cap_source_records_unchanged',REPO,hs)
        hashes('historical_cap_evidence_copies_match',P9/'calibration/historical_caps_source',
          {str(Path(k).relative_to('data/survey/p8')):v for k,v in hs.items()})
    inp=read(P9/'protocol/final_inputs_lock.json')
    hashes('frozen_raw_stellar_sky_inputs_unchanged',P9,inp['input_hashes'])
    check('execution_manifest_unchanged',sha(P9/'manifests/final_execution.csv')==inp['execution_sha256'])
    check('truth_manifest_unchanged',sha(P9/'truth/final_truth.csv')==inp['truth_sha256'])
    check('eligibility_unchanged',sha(P9/'truth/final_eligibility.json')==inp['eligibility_sha256'])
    check('selected_product_receipts_unchanged',all(sha(P9/'manifests/products'/f'tic{t}.json')==h for t,h in inp['product_hashes'].items()))
    sampling=read(P9/'protocol/final_sampling_lock.json')
    check('host_selection_unchanged',sha(P9/'truth/final_selection.csv')==sampling['selection_sha256'])
    check('preregistration_unchanged',sha(P9/'protocol/PREREGISTRATION.md')==sampling['protocol_sha256'])
    check('pre_execution_amendments_unchanged',sha(P9/'protocol/AMENDMENTS.md')==sampling['amendments_sha256'])
    check('scientific_runner_unchanged_since_final_sampling',sha(P9/'runner.py')==sampling['code_sha256']['runner.py'])
    check('baseline_git_HEAD_unchanged',subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()==(P9/'baseline/commit.txt').read_text().strip())
    ids=read(P9/'manifests/final_ids.json');locked=[];pending=[];counts=collections.Counter();ops=collections.Counter();violations=[]
    for tic in ids:
        root=P9/'results/blind'/f'tic{tic}';lp=P9/'results/locks'/f'tic{tic}.json'
        if not lp.exists():pending.append(tic)
        else:
            lock=read(lp);actual={str(p.relative_to(P9)):sha(p) for p in root.rglob('*') if p.is_file()}
            check(f'locked_host_{tic}_exact_file_census',actual==lock['sha256']);locked.append(tic)
        for folder,prev,pfield,allowed in [('secondary','stageA','decision',{'PASS'}),('stageB','secondary','gate',{'PASS','HOLD'}),
          ('stageC','stageB','decision',{'PASS'}),('stageD','stageC','decision',{'PASS'})]:
            for path in (root/folder).glob('*.json'):
                pp=root/prev/path.name
                if not pp.exists() or read(pp).get(pfield) not in allowed:violations.append(str(path.relative_to(P9)))
        for folder,field in [('stageA','decision'),('secondary','gate'),('stageB','decision'),('stageC','decision'),('final','scientific_verdict')]:
            for p in (root/folder).glob('*.json'):counts[folder+':'+str(read(p).get(field))]+=1
        table=root/'survivors.csv'
        pregate={f'tic{tic}_P{float(r["period_days"]):.4f}' for r in csv.DictReader(table.open(encoding='utf-8'))} if table.exists() else set()
        for path in (root/'stageA').glob('*.json'):
            if path.stem not in pregate:violations.append('A without pre:'+str(path))
        for p in (root/'final').glob('*.json'):
            d=read(p);check('no_actual_submission:'+p.stem,d.get('actual_submission_eligible') is False)
            hashes('review_evidence:'+p.stem,P9,d['evidence_sha256'])
    check('no_primary_downstream_after_failed_gate',not violations)
    if violations:checks['downstream_violations']=violations
    if not partial:check('all_selected_hosts_locked',not pending)
    op_files=list((P9/'results/operations').glob('*.json'))
    for path in op_files:
        d=read(path);ops[d['status']]+=1
        for a in d['attempts']:
            check('operation_uses_frozen_runner:'+path.stem+':'+str(a['pid']),a.get('runner_sha256')==sha(P9/'runner.py') or 'reuse_validation' in d)
    scores=P9/'results/scored_signals.json'
    if scores.exists():
        rows=read(scores);check('all_selected_signals_scored',len(rows)==len(list(csv.DictReader((P9/'truth/final_truth.csv').open(encoding='utf-8')))))
        receipt=read(P9/'results/scoring_receipt.json')
        from datetime import datetime
        moment=lambda s:datetime.fromisoformat(s.replace('Z','+00:00'))
        check('scoring_receipt_current_code_and_truth',receipt['scorer_sha256']==sha(P9/'scoring.py') and receipt['truth_sha256']==sha(P9/'truth/final_truth.csv'))
        check('every_score_lock_precedes_scoring',all(moment(r['outcome_locked_utc'])<moment(receipt['utc']) and r['outcome_locked_utc']==read(P9/'results/locks'/f'tic{r["tic_id"]}.json')['utc'] for r in rows))
        check('all_signals_have_post_lock_diagnostic_covariates',{r['truth_id'] for r in rows}=={r['truth_id'] for r in read(P9/'results/diagnostic_features.json')})
        if (P9/'results/metrics.json').exists():
            metrics=read(P9/'results/metrics.json')
            check('positive_conditional_products_consistent',all(v['verified'] or v['conditional_product'] is None for v in metrics['cohorts']['positive_all']['conditional_product_checks'].values()))
        positive={r['truth_id'] for r in rows if r['label']=='positive'}
        if (P9/'results/failure_autopsies.json').exists():check('every_positive_has_autopsy',positive=={r['truth_id'] for r in read(P9/'results/failure_autopsies.json')})
        ep=read(P9/'results/positive_ephemeris_audit.json')
        check('all_positives_in_timing_context_audit',positive=={r['truth_id'] for r in ep['records']})
        hashes('post_lock_ephemeris_snapshots_unchanged',P9,ep['source_sha256'])
        for r in ep['records']:
            if r.get('post_lock_source'):
                sr=r['post_lock_source'];lock=read(P9/'results/locks'/f'tic{r["tic_id"]}.json')
                check('timing_query_after_lock:'+r['truth_id'],sr['outcome_locked_utc']==lock['utc'] and moment(sr['utc'])>moment(lock['utc']))
                check('alternative_timing_never_primary_credit:'+r['truth_id'],all(a['primary_credit'] is False and a['no_scientific_stage_rerun'] is True for a in r['alternative_solutions']))
        du=read(P9/'results/duration_identity_audit.json')
        hashes('duration_identity_source_records_unchanged',P9,du['source_sha256'])
        check('all_C_records_have_duration_audit',{r['key'] for r in du['records']}=={p.stem for p in (P9/'results/blind').glob('*/stageC/*.json')})
        check('duration_identity_checks_never_change_primary',all(r['no_primary_score_change'] and r['no_scientific_stage_rerun'] and all(c['primary_credit'] is False for c in r['same_C_period_and_epoch_duration_checks'].values()) for r in du['identity_checks']))
    if (P9/'results/pilot_cache_reuse.json').exists():
        reuse=read(P9/'results/pilot_cache_reuse.json')
        for rec in reuse:
            if rec['validated_identical_candidate_and_vetting_lists']:
                hashes('reused_pilot_measurements:'+str(rec['tic_id']),P9/'results/blind'/f'tic{rec["tic_id"]}',rec['copied'])
    result=dict(utc=utc(),status='PASS' if not failures else 'FAIL',partial=partial,checks=checks,failures=failures,
      n_locked_hosts=len(locked),pending_hosts=pending,n_operations=len(op_files),operation_status_counts=dict(ops),blind_candidate_decisions=dict(counts),
      verifier_sha256=sha(Path(__file__)))
    write(P9/'results'/('verification_partial.json' if partial else 'verification.json'),result)
    print(result['status'],'checks',len(checks),'locked',len(locked),'pending',len(pending),'failures',failures,flush=True)
    if failures:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');a=p.parse_args();run(a.partial)
