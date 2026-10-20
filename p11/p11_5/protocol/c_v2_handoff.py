"""Freeze corrected-C jobs for every required paired candidate and control.

No truth, SNR bin, recovery count, or old C decision participates in selection.
This entry point is allowed only after the first scientific owner has closed.
"""
from common import *
environment()
from candidates import sources
from funnel_worker import A

def main():
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Wait for the active owner to close')
    correction=read(ROOT/'manifests/C_v2_correctness_registration.json')
    implementation=REPO/'src/tesshunter/p11_5_clocal_v2.py'
    if sha(implementation)!=correction['draft_source_sha256']:raise ValueError('Corrected source differs from registered engineering draft')
    selected=read(ROOT/'manifests/development_selection.json');ids={};omitted=[]
    for jid in selected['series_ids']:
        for row in read(ROOT/f'results/predictions/{jid}.json')['predictions']:
            if row['passes_pregate']:ids.setdefault(row['candidate_id'],set()).add('paired_development')
    for row in read(ROOT/'manifests/control_joins.json')['rows']:
        if row.get('candidate_id'):ids.setdefault(row['candidate_id'],set()).add(row['collection'])
    hashes=sources()
    for name in ('c_v2_worker.py','c_v2_handoff.py'):
        hashes['p11/p11_5/protocol/'+name]=sha(ROOT/'protocol'/name)
    jobs=[]
    for cid,roles in sorted(ids.items()):
        runtime_path=ROOT/f'manifests/runtime_funnel/{cid}.json';runtime=read(runtime_path)
        ap=ROOT/f'results/funnel/A/{cid}.json';ar=read(ap);measured=ar.get('measurement',{})
        eligible=ar['status']=='COMPLETE' and (measured.get('decision')=='PASS' or
            runtime.get('engineering_label') and measured.get('chosen_ephemeris'))
        if not eligible:
            omitted.append(dict(candidate_id=cid,roles=sorted(roles),A_status=ar['status'],
                A_decision=measured.get('decision'),reason='No completed eligible A ephemeris; keep actual ordered status'))
            continue
        stage_hashes={s:sha(ROOT/f'results/funnel/{s}/{cid}.json') for s in ('A','S','B')}
        root=DATA/f'funnel/{cid}';key=A.key(runtime['tic_id'],runtime['candidate']['period'])
        prepared=root/f'tls/{key}_lc.npz';meta=root/f'prep/{key}.json'
        handoff=dict(candidate_id=cid,runtime_path=runtime_path.relative_to(REPO).as_posix(),runtime_sha256=sha(runtime_path),
            stage_hashes=stage_hashes,prepared_path=prepared.relative_to(REPO).as_posix(),prepared_sha256=sha(prepared),
            prep_metadata_path=meta.relative_to(REPO).as_posix(),prep_metadata_sha256=sha(meta),
            source_hashes=hashes,correction_registration_sha256=sha(ROOT/'manifests/C_v2_correctness_registration.json'))
        hp=ROOT/f'manifests/runtime_c_v2/{cid}.json';write(hp,handoff)
        jobs.append(dict(job_id='C_v2_'+cid,roles=sorted(roles),
            command=['p11/p11_5/protocol/c_v2_worker.py',hp.relative_to(REPO).as_posix()],source_paths=sorted(hashes)))
    write(ROOT/'manifests/c_v2_jobs.json',jobs)
    write(ROOT/'manifests/c_v2_execution_freeze.json',dict(utc=utc(),jobs=len(jobs),omitted=omitted,
        job_manifest_sha256=sha(ROOT/'manifests/c_v2_jobs.json'),source_hashes=hashes,
        selection_sha256=sha(ROOT/'manifests/development_selection.json'),
        predecessor_reuse='Exact candidate runtime, A/S/B result hashes, native A arrays, prep metadata and original source hashes verified in every job.',
        truth_matching_performed=False,selection_uses_old_C_outcome=False,per_case_deadline_seconds=600,
        old_C_attempt_costs_preserved=True,required_C_stage='C_v2'))
    print('Corrected C jobs frozen',len(jobs),'earlier-stage inapplicable candidates',len(omitted))

if __name__=='__main__':main()
