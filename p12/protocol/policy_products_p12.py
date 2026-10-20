"""Frozen policy-selected products; no implicit acquisition or alternative source."""
from p12_common import REPO, ROOT, DATA, read, sha, environment, redirect_audit_cache
environment()
import sys
import numpy as np
from input_identity_p12 import choose_verified


def _check(path, digest, label):
    if not isinstance(digest, str) or len(digest) != 64 or sha(path) != digest:
        raise RuntimeError(label + ' hash changed or missing')


def _selected(tic):
    identity = read(ROOT / f'manifests/input_identity/tic{int(tic)}.json')
    if int(identity['tic_id']) != int(tic):
        raise RuntimeError('Input identity TIC mismatch')
    cfg = read(ROOT / 'protocol/config.json')
    index = REPO / identity.get('index_path', f'data/survey/audit_lc/tic{int(tic)}/index.json')
    _check(index, identity['index_sha256'], 'Acquisition index')
    selected = choose_verified(identity['records'], cfg)
    if [r['metadata']['sector'] for r in selected] != identity['selected_sectors']:
        raise RuntimeError('Selected sectors disagree with frozen policy')
    return identity, selected


def load_policy_products(tic, arm='archival'):
    if arm not in ('archival', 'sml'):
        raise ValueError('Unknown photometry arm')
    _, selected = _selected(tic)
    products = []
    swaps = {}
    if arm == 'sml':
        index = read(ROOT / 'manifests/sml_store_index.json')
        swaps = {int(r['sector']): r for r in index['products'] if int(r['tic_id']) == int(tic)}
    for record in selected:
        source = record.get('source')
        if not source or not record.get('comparison', {}).get('all_required_exact'):
            raise RuntimeError('Selected preferred product lacks verified source')
        _check(REPO / source['path'], source['sha256'], 'Source FITS')
        path = REPO / record['raw_path']
        _check(path, record['raw_sha256'], 'Raw product')
        with np.load(path, allow_pickle=False) as z:
            product = {k: np.asarray(z[k]).copy() for k in z.files}
        product.update(record['metadata'])
        if arm == 'sml':
            sector = int(product['sector'])
            if sector not in swaps:
                raise RuntimeError('SML store lacks selected sector')
            swapped = swaps[sector]
            if swapped['original_raw_sha256'] != record['raw_sha256']:
                raise RuntimeError('SML store uses a different raw input')
            _check(REPO / swapped['raw_path'], swapped['raw_sha256'], 'SML product')
            with np.load(REPO / swapped['raw_path'], allow_pickle=False) as z:
                if set(z.files) != {k for k, v in product.items() if isinstance(v, np.ndarray)}:
                    raise RuntimeError('SML array keys changed')
                for key in z.files:
                    allowed = key == 'flux' and swapped['uses_sml'] and product['author'] == 'QLP'
                    if not allowed and not np.array_equal(z[key], product[key], equal_nan=True):
                        raise RuntimeError('SML modified an unpermitted array')
                product['flux'] = np.asarray(z['flux']).copy()
            if swapped['uses_sml']:
                if product['author'] != 'QLP' or not swapped.get('column_exists') or swapped['finite_fraction_ratio'] < .9:
                    raise RuntimeError('SML swap violates registered finite-fraction rule')
        products.append(product)
    return products


def install(tic, arm='archival'):
    """Patch both historical loaders for exactly one TIC; return a restorer."""
    sys.path.insert(0, str(REPO / 'src'))
    sys.path.insert(0, str(REPO / 'scripts'))
    from tesshunter import survey_p8
    import audit_p5
    redirect_audit_cache(audit_p5)
    previous_survey, previous_audit = survey_p8.load_audit_products, audit_p5.load_products

    def products(requested_tic, *args, **kwargs):
        if int(requested_tic) != int(tic):
            raise RuntimeError('Policy patch requested a different star')
        return load_policy_products(tic, arm)

    survey_p8.load_audit_products = products
    audit_p5.load_products = products

    def restore():
        survey_p8.load_audit_products = previous_survey
        audit_p5.load_products = previous_audit

    return restore
