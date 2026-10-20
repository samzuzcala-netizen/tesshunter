"""Read-only historical verification and isolated P11.5 final evidence seals."""
from common import *
import sys,subprocess,psutil

PROCESS_FIELDS = ('pid', 'create_time', 'cmdline')


def is_protocol_python(info):
    command = info.get('cmdline') or []
    return bool(command and Path(command[0]).name.lower().startswith('python') and
                any('p11_5/protocol' in arg.replace('\\', '/') for arg in command[1:]))


def remaining_protocol_processes(current, ancestors, processes):
    """Exclude only this verifier and identical-invocation Python ancestors.

    Windows virtual environments use a Python redirector parent. Its identical
    argument vector and actual ancestry distinguish it from scientific owners,
    sibling helpers and other protocol processes. PID plus creation time binds
    every exclusion to the observed process identity.
    """
    identity = lambda row: (row['pid'], row['create_time'])
    verifiers = [dict(current, reason='Current verifier process')]
    for row in ancestors:
        command = row.get('cmdline') or []
        if (command and Path(command[0]).name.lower().startswith('python') and
                command[1:] == (current.get('cmdline') or [])[1:]):
            verifiers.append(dict(row, reason='Python ancestor with the exact verifier invocation'))
    permitted = {identity(row) for row in verifiers}
    remaining = [row for row in processes if is_protocol_python(row) and
                 identity(row) not in permitted]
    return remaining, verifiers


def protocol_process_snapshot():
    me = psutil.Process()
    current = me.as_dict(attrs=PROCESS_FIELDS)
    ancestors = []
    for proc in me.parents():
        try:
            ancestors.append(proc.as_dict(attrs=PROCESS_FIELDS))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    observed = []
    for proc in psutil.process_iter(PROCESS_FIELDS):
        try:
            observed.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return remaining_protocol_processes(current, ancestors, observed)

def historical():
    frozen=read(REPO/'p11/manifests/final_freeze.json');checks={}
    for path,expected in frozen['source_and_evidence'].items():
        if isinstance(expected,dict):expected=expected.get('sha256')
        actual=sha(REPO/path);checks[path]=dict(expected=expected,actual=actual,match=actual==expected)
    entry=read(ROOT/'results/entry.json');source_checks={}
    original=read(REPO/'p11/manifests/entry_source_and_evidence_hashes.json')
    for path in entry['effective_source_checks']:
        expected=original[path]
        actual=sha(REPO/path);source_checks[path]=dict(expected=expected,actual=actual,match=actual==expected)
    result=dict(utc=utc(),old_freeze_sha256=sha(REPO/'p11/manifests/final_freeze.json'),
        frozen_evidence_checks=checks,effective_historical_source_checks=source_checks,
        all_pass=all(r['match'] for r in list(checks.values())+list(source_checks.values())),
        old_receipts_rewritten=False)
    if not result['all_pass']:raise ValueError('Historical evidence/source changed')
    write(ROOT/'results/historical_integrity_final.json',result)
    print('historical content checks passed',len(checks)+len(source_checks))

def final():
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Owning controller still active')
    owners,verifier_processes=protocol_process_snapshot()
    if owners:raise RuntimeError('P11.5 Python process remains: '+str(owners))
    required=['INPUT_POLICY_P11_5.md','SEARCH_ALTERNATIVES_P11_5.md','C_LOCAL_P11_5.md','DECISION_P11_5.md','HANDOFF_P11_5.md','RESUME_P11_5.md']
    for name in required:
        if not (ROOT/name).exists():raise FileNotFoundError(name)
    excluded={'work','__pycache__','.pytest_cache'};hashes={}
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file() or any(p in excluded for p in path.relative_to(ROOT).parts) or path.suffix in ('.pyc','.tmp'):continue
        if path.name in ('final_freeze.json','local_commit_receipt.json'):continue
        hashes[path.relative_to(REPO).as_posix()]=sha(path)
    for path in sorted((REPO/'src/tesshunter').glob('p11_5_*.py')):hashes[path.relative_to(REPO).as_posix()]=sha(path)
    attributes=REPO/'src/tesshunter/.gitattributes'
    hashes[attributes.relative_to(REPO).as_posix()]=sha(attributes)
    data={p.relative_to(REPO).as_posix():sha(p) for p in sorted(DATA.rglob('*')) if p.is_file() and p.suffix not in ('.tmp','.pyc')}
    write(ROOT/'manifests/scientific_data_final.json',dict(utc=utc(),hashes=data,files=len(data),
        total_bytes=sum((REPO/p).stat().st_size for p in data),historical_data_deleted=False))
    path=ROOT/'manifests/scientific_data_final.json';hashes[path.relative_to(REPO).as_posix()]=sha(path)
    write(ROOT/'manifests/final_freeze.json',dict(utc=utc(),head_before_local_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        source_and_evidence=hashes,all_p11_5_jobs_closed=True,python_owners=owners,
        verifier_processes=verifier_processes,
        scientific_data_manifest_sha256=sha(path),no_reserved_ephemerides_opened=True,no_push=True))
    print('final source/evidence seal',len(hashes),'files; scientific data',len(data),'files')

if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else ''
    if mode=='historical':historical()
    elif mode=='final':final()
    elif mode=='processes':
        owners,verifiers=protocol_process_snapshot()
        print(json.dumps(dict(utc=utc(),remaining_protocol_processes=owners,
            verifier_processes=verifiers,read_only=True)))
    else:raise ValueError('Use historical, final, or processes')
