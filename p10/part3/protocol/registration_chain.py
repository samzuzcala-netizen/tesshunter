"""Verify the original registration and the explicitly adopted D1-D4 chain."""
from common import REPO, ROOT, read, sha


def verify(repo=REPO, root=ROOT):
    seal_path = root / 'manifests/registration_seal.json'
    seal = read(seal_path)
    chain = read(root / 'manifests/registration_amendments_D1_D4.json')
    if sha(seal_path) != chain['original_seal_sha256']:
        raise RuntimeError('Original registration seal changed')
    original_name = 'p10/part3/PREREGISTRATION_P10_3.md'
    snapshot = repo / chain['original_preregistration_snapshot']
    if sha(snapshot) != seal['hashes'][original_name] or sha(snapshot) != chain['original_preregistration_sha256']:
        raise RuntimeError('Original preregistration snapshot changed')
    for name, digest in seal['hashes'].items():
        expected = chain['effective_preregistration_sha256'] if name == original_name else digest
        if sha(repo / name) != expected:
            raise RuntimeError('Registration changed: ' + name)
    if sha(repo / chain['amendment_document']) != chain['amendment_document_sha256']:
        raise RuntimeError('Acquisition amendment document changed')
    for name, digest in chain['prelaunch_amendment_hashes'].items():
        if sha(repo / name) != digest:
            raise RuntimeError('Registered acquisition source or plan changed: ' + name)
    return dict(original_seal_verified=True, original_snapshot_verified=True,
                effective_preregistration_verified=True,
                amendment_chain_sha256=sha(root / 'manifests/registration_amendments_D1_D4.json'))
