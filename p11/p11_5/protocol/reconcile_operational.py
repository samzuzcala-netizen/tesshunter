"""Seal absent terminal stage outputs from immutable operational receipts.

This does not retry science, infer a result from a timeout, or overwrite a
completed measurement. Missing search results require explicit separate review.
"""
from common import *
import sys

def main():
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Reconcile after owner closes')
    restored=[];search_missing=[]
    for folder in sorted((ROOT/'results/controllers').iterdir()):
        if not folder.is_dir():continue
        for path in sorted(folder.glob('*.json')):
            r=read(path)
            if r.get('status') not in ('INPUT_ERROR','TIMEOUT','INTERRUPTED'):continue
            command=r.get('command',[])
            if not command:continue
            if command[0].endswith('search_worker.py'):
                runtime=read(REPO/command[-1]);out=ROOT/f"results/search/{runtime['job_id']}.json"
                if not out.exists():search_missing.append(dict(job_id=runtime['job_id'],receipt=path.relative_to(REPO).as_posix()))
                continue
            corrected=command[0].endswith('c_v2_worker.py')
            if not corrected and not command[0].endswith('funnel_worker.py'):continue
            handoff_path=REPO/command[-1]
            handoff=read(handoff_path) if corrected else None
            runtime_path=REPO/handoff['runtime_path'] if corrected else handoff_path
            runtime=read(runtime_path);stage='C_v2' if corrected else command[1];cid=runtime['candidate_id']
            out=ROOT/f'results/funnel/{stage}/{cid}.json'
            if out.exists():continue
            status='TIMEOUT' if r['status']=='TIMEOUT' else 'INPUT_ERROR'
            write(out,dict(candidate_id=cid,series_id=runtime['series_id'],tic_id=runtime['tic_id'],stage=stage,status=status,
                input_key=runtime['input_key'],raw_index_sha256=runtime['raw_index_sha256'],source_hashes=handoff['source_hashes'] if corrected else runtime['source_hashes'],
                runtime_manifest_sha256=sha(runtime_path),measurement=dict(decision='ERROR',gate='UNKNOWN',status=status),
                wall_seconds=r['wall_seconds'],cpu_seconds=r.get('measured_process_tree_cpu_seconds',0),
                error='Operational attempt ended without a scientific output; no pass or measured rejection is inferred.',
                operational_receipt=path.relative_to(REPO).as_posix(),operational_receipt_sha256=sha(path),
                measurement_available=False,truth_opened=False,engineering_label=runtime.get('engineering_label'),
                reconciliation_utc=utc(),no_scientific_retry=True,
                corrected_C_handoff_sha256=sha(handoff_path) if corrected else None))
            restored.append(dict(candidate_id=cid,stage=stage,status=status,path=out.relative_to(REPO).as_posix()))
    # Keep every reconciliation invocation, including no-op verification.
    index=len(list((ROOT/'results').glob('operational_reconciliation_*.json')))+1
    write(ROOT/f'results/operational_reconciliation_{index:02d}.json',dict(utc=utc(),restored_terminal_statuses=restored,
        missing_searches=search_missing,no_outcome_imputation=True))
    print('terminal operational records',len(restored),'missing searches requiring review',len(search_missing))
    if search_missing:raise SystemExit(2)

if __name__=='__main__':main()
