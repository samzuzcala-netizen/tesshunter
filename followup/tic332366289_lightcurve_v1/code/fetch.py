import common as C
import requests, sys, zipfile
from urllib.parse import quote
S=requests.Session()
LEDGER=C.WS/'inputs/network_ledger.json'
def request(method,url,**kw):
    C.check(); log=C.json.loads(LEDGER.read_text()) if LEDGER.exists() else []
    for attempt in range(2):
        row=dict(utc=C.datetime.datetime.now(C.datetime.timezone.utc).isoformat(),method=method,url=url,attempt=attempt)
        try:
            r=S.request(method,url,timeout=(20,120),**kw); row['status']=r.status_code
            r.raise_for_status(); log.append(row); C.write(LEDGER,log); return r
        except (requests.ConnectionError,requests.Timeout) as e:
            row['error']=str(e); log.append(row); C.write(LEDGER,log)
            if attempt: raise
        except Exception as e:
            row['error']=str(e); log.append(row); C.write(LEDGER,log); raise
def mast(service,params,name):
    out=C.WS/'inputs'/name
    if out.exists(): return C.json.loads(out.read_text())
    payload=dict(service=service,params=params,format='json',pagesize=10000,page=1)
    C.write(out.with_suffix('.request.json'),payload)
    data=request('POST','https://mast.stsci.edu/api/v0/invoke',data={'request':C.json.dumps(payload)}).json()
    C.write(out,data)
    if data.get('status')!='COMPLETE': raise RuntimeError(data)
    return data
def download(url,path):
    path=C.Path(path)
    if path.exists(): return path
    budget=C.WS/'inputs/download_bytes.json'
    state=C.json.loads(budget.read_text()) if budget.exists() else {'received_bytes':0}
    r=request('GET',url,stream=True)
    size=int(r.headers.get('content-length',0))
    if state['received_bytes']+size>C.LIMIT: raise RuntimeError('5 GB download cap')
    tmp=path.with_suffix(path.suffix+'.part'); begin=C.time.monotonic()
    try:
        with open(tmp,'wb') as f:
            for b in r.iter_content(1024*1024):
                C.check()
                if C.time.monotonic()-begin>600: raise RuntimeError('600 s per-product wall cap')
                state['received_bytes']+=len(b)
                if state['received_bytes']>C.LIMIT: raise RuntimeError('5 GB download cap')
                f.write(b)
        tmp.replace(path)
    finally: C.write(budget,state); r.close()
    print('Downloaded',path.name,path.stat().st_size,flush=True)
    return path
if __name__=='__main__':
    if sys.argv[1]=='search':
        data=mast('Mast.Caom.Filtered.Position',dict(columns='*',position='257.222579, 50.487785, 0.001',filters=[{'paramName':'provenance_name','values':['TESS-SPOC','QLP']}]),'mast_search.json')
        rows=data.get('data',[])
        print('Rows',len(rows))
        for r in rows: print({k:r.get(k) for k in ['obsid','obs_id','target_name','provenance_name','sequence_number','dataURL','t_min','t_max']})
    elif sys.argv[1]=='products':
        rows=C.json.loads((C.WS/'inputs/mast_search.json').read_text())['data']
        rows=[r for r in rows if str(r.get('target_name','')).replace('TIC ','')=='332366289' or '0000000332366289' in r['obs_id']]
        rows=[r for r in rows if int(r.get('sequence_number') or -1) in C.SECTORS[:8]]
        ids=','.join(str(r['obsid']) for r in rows)
        data=mast('Mast.Caom.Products',{'obsid':ids},'mast_products.json')
        products=[r for r in data['data'] if r.get('productFilename','').endswith(('_lc.fits','_llc.fits'))]
        C.write(C.WS/'inputs/selected_products.json',products)
        for p in products:
            download('https://mast.stsci.edu/api/v0.1/Download/file?uri='+quote(p['dataURI']),C.BIG/'downloads'/p['productFilename'])
        print('Selected products',len(products))
    elif sys.argv[1]=='cutouts':
        rows=C.json.loads((C.WS/'inputs/needed_cutouts.json').read_text())
        for row in rows:
            s=row['sector']; url=f'https://mast.stsci.edu/tesscut/api/v0.1/astrocut?ra=257.222579&dec=50.487785&x=21&y=21&units=px&sector={s}'
            z=download(url,C.BIG/'downloads'/f'tesscut_s{s:04d}.zip')
            with zipfile.ZipFile(z) as zz:
                for n in zz.namelist():
                    if n.endswith('.fits'):
                        dest=C.BIG/'downloads'/C.Path(n).name
                        if not dest.exists():
                            with zz.open(n) as src,open(dest,'wb') as dst:
                                import shutil
                                shutil.copyfileobj(src,dst)
