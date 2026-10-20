"""P11 cached-FITS aperture read pattern, limited to P12 inventory/store."""
from p12_common import REPO,ROOT,DATA,read,write,sha,utc,environment
environment()
import argparse
import csv
import shutil
import numpy as np
from astropy.io import fits
import policy_products_p12 as policy


def _small(record, product):
    """Return aligned SML array only under the exact registered mixed-aperture rule."""
    item=dict(sector=int(product['sector']),author=product['author'],column_exists=False,
        finite_fraction_ratio=0.,uses_sml=False,
        generation='QLP_TGLC_s94_onward' if product['author']=='QLP' and product['sector']>=94
            else 'QLP_pre94' if product['author']=='QLP' else product['author'])
    if product['author']!='QLP':return item,None
    source=record['source'];path=REPO/source['path']
    policy._check(path,source['sha256'],'SML source FITS')
    with fits.open(path,memmap=False) as hd:
        data=hd[1].data
        if 'DET_FLUX_SML' not in data.names or 'DET_FLUX' not in data.names:return item,None
        default=np.asarray(data['DET_FLUX'],dtype=float)
        small=np.asarray(data['DET_FLUX_SML'],dtype=float)
        item['column_exists']=True
        finite_default=int(np.isfinite(default).sum());finite_small=int(np.isfinite(small).sum())
        item.update(finite_default=finite_default,finite_small=finite_small,
            finite_fraction_ratio=float(finite_small/finite_default) if finite_default else 0.)
        valid=np.ones(len(data),dtype=bool) if len(data)==len(product['time']) else np.isfinite(data['TIME'])
        small=np.asarray(small[valid],dtype=float).copy()
    if len(small)!=len(product['time']):raise RuntimeError('SML source time mapping mismatch')
    item['uses_sml']=bool(finite_default and item['finite_fraction_ratio']>=.9)
    return item,small if item['uses_sml'] else None


def inventory(tics):
    rows=[]
    for tic in sorted({int(t) for t in tics}):
        identity,records=policy._selected(tic)
        products=policy.load_policy_products(tic,'archival')
        for record,product in zip(records,products):
            item,_=_small(record,product)
            rows.append(dict(item,tic_id=tic,raw_path=record['raw_path'],raw_sha256=record['raw_sha256'],
                source_path=record['source']['path'],source_sha256=record['source']['sha256']))
    result=dict(utc=utc(),products=rows,n_products=len(rows),n_sml=sum(r['uses_sml'] for r in rows),
        rule='QLP selected product, DET_FLUX_SML exists, finite fraction >= 0.9 of DET_FLUX',
        efficacy_measured=False)
    write(ROOT/'manifests/sml_inventory.json',result)
    return result


def store(tics):
    index_path=ROOT/'manifests/sml_store_index.json'
    previous=read(index_path) if index_path.exists() else None
    previous_hash=sha(index_path) if previous else None
    by_key={(int(r['tic_id']),int(r['sector'])):r for r in previous['products']} if previous else {}
    added=[]
    for tic in sorted({int(t) for t in tics}):
        _,records=policy._selected(tic)
        products=policy.load_policy_products(tic,'archival')
        for record,product in zip(records,products):
            item,small=_small(record,product)
            original=REPO/record['raw_path'];destination=DATA/f'sml/raw/tic{tic}'/original.name
            destination.parent.mkdir(parents=True,exist_ok=True)
            key=(tic,int(product['sector']))
            if destination.exists():
                old=by_key.get(key)
                if not old or old['original_raw_sha256']!=record['raw_sha256'] or old['source_sha256']!=record['source']['sha256'] or old['uses_sml']!=item['uses_sml']:
                    raise RuntimeError('Existing SML product has a different input or policy')
                policy._check(destination,old['raw_sha256'],'Existing SML product')
                continue
            if key in by_key:raise RuntimeError('Indexed SML product is missing')
            if small is None:
                shutil.copyfile(original,destination)
            else:
                with np.load(original,allow_pickle=False) as z:arrays={k:np.asarray(z[k]).copy() for k in z.files}
                arrays['flux']=small
                np.savez_compressed(destination,**arrays)
            by_key[key]=dict(item,tic_id=tic,original_raw_path=record['raw_path'],
                original_raw_sha256=record['raw_sha256'],raw_path=destination.relative_to(REPO).as_posix(),
                raw_sha256=sha(destination),source_sha256=record['source']['sha256'])
            added.append(dict(tic_id=tic,sector=key[1]))
    if previous and not added:return previous
    rows=[by_key[key] for key in sorted(by_key)]
    result=dict(utc=utc(),products=rows,n_products=len(rows),n_sml=sum(r['uses_sml'] for r in rows),
        efficacy_measured=False,previous_index_sha256=previous_hash,added_product_keys=added,
        previous_index=previous)
    write(index_path,result,replace=previous is not None)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('inventory','store'))
    parser.add_argument('--targets',required=True);args=parser.parse_args(argv)
    with open(args.targets,newline='',encoding='utf-8-sig') as stream:tics=[r['tic_id'] for r in csv.DictReader(stream)]
    result={'inventory':inventory,'store':store}[args.action](tics)
    print('SML products',result['n_products'],'qualifying',result['n_sml'],flush=True)
    return 0


if __name__=='__main__':main()
