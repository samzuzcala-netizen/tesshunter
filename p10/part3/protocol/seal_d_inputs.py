"""Freeze the completed input evidence, verified products and native inputs."""
from common import REPO,ROOT,DATA,read,write,sha,utc
from registration_chain import verify
import json


def main():
    verify()
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Owner still present')
    hashes={};headers_checked=0;missing_headers=0
    def put(path,digest):
        if path in hashes and hashes[path]!=digest:raise RuntimeError('Conflicting input hashes: '+path)
        hashes[path]=digest
    for p in sorted((ROOT/'results/input_identity').glob('tic*.json')):
        r=read(p);put(p.relative_to(REPO).as_posix(),sha(p))
        put(f'data/survey/audit_lc/tic{r["tic_id"]}/index.json',r['index_sha256'])
        for product in r['records']:
            if product.get('raw_path'):put(product['raw_path'],product['raw_sha256'])
            source=product.get('source')
            if source:
                put(source['path'],source['sha256'])
                tid=source['headers'].get('TICID')
                if tid is not None:
                    if int(tid)!=r['tic_id']:raise RuntimeError('Source FITS target identity mismatch')
                    headers_checked+=1
                else:missing_headers+=1
    for p in sorted((ROOT/'results/native_noise').glob('tic*.json')):
        r=read(p);put(p.relative_to(REPO).as_posix(),sha(p))
        if r.get('prepared_path'):
            put(r['prepared_path'],r['prepared_sha256'])
            put(str(__import__('pathlib').Path(r['prepared_path']).with_suffix('.json')).replace('\\','/'),r['provenance_sha256'])
    for p in sorted((DATA/'neighbours').glob('tic*.json')):put(p.relative_to(REPO).as_posix(),sha(p))
    for p in sorted((DATA/'neighbours_bulk').glob('*.json')):put(p.relative_to(REPO).as_posix(),sha(p))
    for name in ['manifests/input_eligibility.json','manifests/targets_eligible.csv','results/part_d.json']:
        p=ROOT/name;put(p.relative_to(REPO).as_posix(),sha(p))
    sizes={name:(REPO/name).stat().st_size for name in hashes}
    receipt=dict(utc=utc(),hashes=hashes,files=len(hashes),bytes=sum(sizes.values()),
        method='Use exact per-product hashes measured in the closed Part D workers, plus fresh hashes of aggregate and neighbour records. Native inputs are rechecked again by each search worker.',
        source_TICID_headers_checked=headers_checked,missing_TICID_headers=missing_headers,
        source_filename_identity='Every source path was selected by its exact 16-digit TIC filename; populated TICID headers also checked',
        mutable_historical_paths_written=False,source_sha256=sha(__file__))
    write(ROOT/'manifests/input_data_seal.json',receipt)
    write(ROOT/'manifests/source_pre_pilot.json',dict(utc=utc(),hashes={p.relative_to(REPO).as_posix():sha(p) for p in (ROOT/'protocol').glob('*.py')}))
    print(json.dumps({k:v for k,v in receipt.items() if k!='hashes'}))


if __name__=='__main__':main()
