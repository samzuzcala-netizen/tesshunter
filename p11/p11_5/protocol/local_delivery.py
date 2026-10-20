"""Commit only sealed P11.5 files locally, then package verified deliverables.

The scientific data stay in their registered repository location and are linked
by the final content manifest. No network operation is performed.
"""
from common import *
import shutil
import subprocess
import sys
import zipfile


def git(*args, input=None):
    return subprocess.check_output(['git','-c','gc.auto=0','-c','maintenance.auto=false',
        *args],cwd=REPO,input=input)


def sealed_paths():
    if (ROOT/'manifests/controller_owner.json').exists():
        raise RuntimeError('Delivery requires a closed scientific owner')
    freeze=read(ROOT/'manifests/final_freeze.json')
    if not freeze['all_p11_5_jobs_closed']:
        raise ValueError('Final process closure not verified')
    if not read(ROOT/'results/historical_integrity_final.json')['all_pass']:
        raise ValueError('Historical integrity did not pass')
    for path,expected in freeze['source_and_evidence'].items():
        if sha(REPO/path)!=expected:
            raise ValueError('Sealed source/evidence changed: '+path)
    paths=sorted(set(freeze['source_and_evidence'])|{'p11/p11_5/manifests/final_freeze.json'})
    for path in paths:
        if not (path.startswith('p11/p11_5/') or path.startswith('src/tesshunter/p11_5_')
                and path.endswith('.py') or path=='src/tesshunter/.gitattributes'):
            raise ValueError('Outside explicit P11.5 commit scope: '+path)
        if not (REPO/path).resolve().is_relative_to(REPO.resolve()):
            raise ValueError('Path escapes repository')
    return paths


def verify_committed_bytes(commit,paths):
    stdin=('\n'.join(paths)+'\n').encode('utf-8')
    actual=git('hash-object','--no-filters','--stdin-paths',input=stdin).decode().splitlines()
    objects=git('cat-file','--batch-check',
        input=('\n'.join(commit+':'+p for p in paths)+'\n').encode('utf-8')).decode().splitlines()
    if len(actual)!=len(paths) or len(objects)!=len(paths):
        raise ValueError('Incomplete Git object verification')
    for path,want,line in zip(paths,actual,objects):
        fields=line.split()
        if len(fields)!=3 or fields[1]!='blob' or fields[0]!=want:
            raise ValueError('Committed bytes differ from sealed working bytes: '+path)


def delivery_headroom(destination,paths):
    """Reserve two full copies plus overhead before any staging or output write."""
    location=Path(destination).resolve()
    while not location.exists():
        location=location.parent
    source_bytes=sum((REPO/path).stat().st_size for path in paths)
    # This covers loose Git objects/index or the copied folder plus ZIP, with
    # 10% payload overhead and 64 MiB for generated metadata and file headers.
    required=int(2.1*source_bytes)+64*1024**2
    free=shutil.disk_usage(location).free
    record=dict(checked_path=str(location),source_bytes=source_bytes,
        planned_additional_bytes=required,free_disk_bytes=free,
        required_free_disk_floor_bytes=30000000000)
    if free-required<record['required_free_disk_floor_bytes']:
        raise RuntimeError('Delivery would breach the 30 GB free-disk floor')
    return record


def commit():
    receipt=ROOT/'manifests/local_commit_receipt.json'
    if receipt.exists():
        raise FileExistsError('A local commit was already recorded')
    paths=sealed_paths()
    if git('diff','--cached','--name-only').strip():
        raise RuntimeError('Existing staged work must remain untouched')
    storage=delivery_headroom(REPO,paths)
    before=git('rev-parse','HEAD').decode().strip()
    # NUL-separated exact paths never expand a directory, glob or user file.
    git('--literal-pathspecs','add','-f','--pathspec-from-file=-','--pathspec-file-nul',
        input=('\0'.join(paths)+'\0').encode('utf-8'))
    staged=git('diff','--cached','--name-only','-z').decode().split('\0')
    staged={p for p in staged if p}
    if staged!=set(paths):
        raise ValueError('Staged paths differ from the explicit final seal')
    git('commit','-m','Complete bounded P11.5 paired development experiment')
    head=git('rev-parse','HEAD').decode().strip()
    verify_committed_bytes(head,paths)
    write(receipt,dict(utc=utc(),head_before=before,commit=head,
        branch=git('branch','--show-current').decode().strip(),
        explicit_committed_paths=paths,committed_bytes_match_final_seal=True,
        final_freeze_sha256=sha(ROOT/'manifests/final_freeze.json'),
        delivery_storage_preflight=storage,
        automatic_gc_disabled=True,automatic_maintenance_disabled=True,no_push=True,
        receipt_excluded_from_its_own_commit=True))
    print('Explicit local commit',head,'verified files',len(paths))


def package(output_dir):
    paths=sealed_paths()
    receipt_path=ROOT/'manifests/local_commit_receipt.json'
    receipt=read(receipt_path)
    verify_committed_bytes(receipt['commit'],paths)
    paths=paths+[receipt_path.relative_to(REPO).as_posix()]
    destination=Path(output_dir).resolve()
    folder=destination/'P11_5'
    archive=destination/'P11_5_evidence.zip'
    if folder.exists() or archive.exists():
        raise FileExistsError('Existing output package will not be overwritten')
    storage=delivery_headroom(destination,paths)
    destination.mkdir(parents=True,exist_ok=True)
    folder.mkdir()
    copied={}
    for path in paths:
        relative=path.removeprefix('p11/p11_5/') if path.startswith('p11/p11_5/') else 'source/'+path.removeprefix('src/')
        target=folder/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(REPO/path,target)
        if sha(target)!=sha(REPO/path):
            raise ValueError('Output copy differs: '+relative)
        copied[relative]=dict(repository_path=path,sha256=sha(target),bytes=target.stat().st_size)
    note=folder/'PACKAGE_ORIGIN.md'
    note.write_text('# P11.5 evidence package\n\n'
        'Local commit: `'+receipt['commit']+'`. No push was performed.\n\n'
        'Repository: `'+str(REPO)+'`.\n\n'
        'Reports, isolated protocols, tests, predictions, control joins, logs and content seals are copied byte-for-byte from the completed experiment. '
        'New versioned scientific modules are under `source/tesshunter/`.\n\n'
        'Large scientific arrays and fitted model archives remain in `data/survey/p11/p11_5/` in the repository. '
        'Their exact content identities are in `manifests/scientific_data_final.json`; they are not duplicated in this package. '
        'Historical dependencies remain at their sealed original paths. The commit receipt is a post-commit receipt and is explicitly excluded from its own commit.\n',encoding='utf-8')
    write(folder/'PACKAGE_MANIFEST.json',dict(utc=utc(),commit=receipt['commit'],
        files=copied,origin_note_sha256=sha(note),scientific_data_included=False))
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(folder.rglob('*')):
            if path.is_file():z.write(path,path.relative_to(destination).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise ValueError('Output ZIP integrity check failed')
    write(destination/'P11_5_package_receipt.json',dict(utc=utc(),commit=receipt['commit'],
        folder=str(folder),zip_path=str(archive),zip_sha256=sha(archive),zip_bytes=archive.stat().st_size,
        copied_sealed_files=len(copied),all_copied_bytes_verified=True,
        delivery_storage_preflight=storage))
    print('Verified output package',archive,'bytes',archive.stat().st_size)


if __name__=='__main__':
    if sys.argv[1]=='commit':commit()
    elif sys.argv[1]=='package':package(sys.argv[2])
    else:raise ValueError('Use commit or package OUTPUT_DIR')
