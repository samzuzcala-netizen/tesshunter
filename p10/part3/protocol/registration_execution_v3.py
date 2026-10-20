"""Verify original registration plus the prospectively authorized execution amendment."""
from common import REPO,ROOT,read,sha
from registration_chain import verify as verify_original


def verify(repo=REPO,root=ROOT,require_launch_seal=False):
    original=verify_original(repo,root)
    path=root/'manifests/registration_execution_v3.json';chain=read(path)
    if sha(repo/chain['prior_chain'])!=chain['prior_chain_sha256']:raise RuntimeError('Prior amendment chain changed')
    for name,digest in chain['hashes'].items():
        if sha(repo/name)!=digest:raise RuntimeError('Execution registration changed: '+name)
    allocation=read(root/'manifests/allocation.json')
    if not allocation['selection_frozen']:raise RuntimeError('Evaluation membership is not frozen')
    result=dict(**original,execution_chain_sha256=sha(path),allocation_sha256=sha(root/'manifests/allocation.json'))
    if require_launch_seal:result['execution_launch_seal_sha256']=verify_launch_inputs(repo,root)
    return result


def verify_launch_inputs(repo=REPO,root=ROOT):
    path=root/'manifests/execution_launch_seal.json';seal=read(path)
    if sha(root/'manifests/registration_execution_v3.json')!=seal['registration_sha256']:raise RuntimeError('Execution registration changed after launch sealing')
    for name,digest in seal['hashes'].items():
        if sha(repo/name)!=digest:raise RuntimeError('Sealed execution source or input changed: '+name)
    return sha(path)
