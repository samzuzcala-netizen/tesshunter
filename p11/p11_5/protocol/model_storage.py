"""Losslessly pack completed fitted-model NPZs; never change predictions.

An archive reference remains its original logical .npz path. If packed, the
corresponding .npz.xz contains that exact original file, verified by SHA256.
Use open_model(path) for either representation, or standard XZ decompression.
"""
from common import *
environment()
import io,lzma,shutil,time,sys,re
import numpy as np
import psutil

def decompressed_sha(path):
    value=hashlib.sha256()
    with lzma.open(path,'rb') as stream:
        while block:=stream.read(1024*1024):value.update(block)
    return value.hexdigest()

def open_model(logical_path):
    path=Path(logical_path)
    if path.exists():return np.load(path,allow_pickle=False)
    with lzma.open(str(path)+'.xz','rb') as stream:data=stream.read()
    return np.load(io.BytesIO(data),allow_pickle=False)

def pack_container(source,destination):
    source=Path(source);destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    start=time.perf_counter();cpu=time.process_time();original=sha(source)
    temporary=destination.with_suffix(destination.suffix+'.tmp')
    with source.open('rb') as inp,lzma.open(temporary,'wb',preset=6) as out:shutil.copyfileobj(inp,out,1024*1024)
    if decompressed_sha(temporary)!=original or sha(source)!=original:raise ValueError('Original archive bytes not preserved')
    os.replace(temporary,destination)
    return dict(original_sha256=original,packed_sha256=sha(destination),original_bytes=source.stat().st_size,
        packed_bytes=destination.stat().st_size,wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
        original_container_bytes_identical=True,codec='XZ / LZMA2 preset 6; exact original NPZ container retained')

def pack_one(cid,stage='C'):
    if not re.fullmatch(r'[A-Za-z0-9_]+',cid):raise ValueError('Invalid candidate identity')
    if stage not in ('C','C_v2'):raise ValueError('Invalid model stage')
    directory='c_models_v2' if stage=='C_v2' else 'c_models'
    case=ROOT/f'results/funnel/{stage}/{cid}.json';source=DATA/f'{directory}/{cid}.npz';packed=Path(str(source)+'.xz')
    if not case.exists():raise ValueError('Scientific model writer has not sealed its case')
    if source.resolve().parent!=(DATA/directory).resolve():raise ValueError('Model path outside isolated P11.5 directory')
    receipt=ROOT/f'results/model_storage/C_v2/{cid}.json' if stage=='C_v2' else ROOT/f'results/model_storage/{cid}.json'
    if receipt.exists():
        old=read(receipt)
        if sha(packed)!=old['packed_sha256']:raise ValueError('Packed archive changed')
        if source.exists():
            if sha(source)!=old['original_sha256']:raise ValueError('Original archive changed')
            source.unlink()
        return old
    record=pack_container(source,packed)
    record.update(utc=utc(),logical_archive=source.relative_to(REPO).as_posix(),physical_archive=packed.relative_to(REPO).as_posix(),
        candidate_id=cid,case_sha256=sha(case),scientific_prediction_changed=False)
    write(receipt,record)
    # Both paths are explicitly scoped above. Remove only the verified redundant
    # new-run container after its exact bytes and a durable receipt exist.
    if sha(source)!=record['original_sha256']:raise ValueError('Source changed before redundant copy removal')
    source.unlink()
    return record

def batch(name,limit=24,stage='C'):
    if stage not in ('C','C_v2'):raise ValueError('Invalid model stage')
    start=time.perf_counter();cpu=time.process_time();owner=ROOT/'manifests/controller_owner.json'
    if owner.exists():
        identity=read(owner);proc=psutil.Process(identity['pid'])
        if proc.create_time()!=identity['create_time']:raise ValueError('Owner identity changed')
        cpus=proc.cpu_affinity()
    else:cpus=[0,2,4,6,8,10,12,14]+list(range(16,32)) if psutil.cpu_count()==32 else psutil.Process().cpu_affinity()[:24]
    psutil.Process().cpu_affinity(cpus)
    directory='c_models_v2' if stage=='C_v2' else 'c_models'
    files=[p for p in (DATA/directory).glob('*.npz') if (ROOT/f'results/funnel/{stage}/{p.stem}.json').exists()]
    files.sort(key=lambda p:(-p.stat().st_size,p.name));done=[]
    for path in files[:limit]:done.append(pack_one(path.stem,stage))
    write(ROOT/f'results/storage_batches/{name}.json',dict(utc=utc(),logical_cpus=cpus,stage=stage,packed=len(done),
        saved_bytes=sum(r['original_bytes']-r['packed_bytes'] for r in done),
        wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
        purpose='Lossless evidence packaging, not a new scientific measurement or benchmark; original C timing and prediction bytes unchanged'))
    print('packed model containers',len(done),'saved bytes',sum(r['original_bytes']-r['packed_bytes'] for r in done))

if __name__=='__main__':batch(sys.argv[1],int(sys.argv[2]) if len(sys.argv)>2 else 24,sys.argv[3] if len(sys.argv)>3 else 'C')
