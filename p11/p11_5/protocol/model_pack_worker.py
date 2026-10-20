"""Owned, identity-checked packing of one sealed corrected-C model archive."""
from common import *
environment()
import re,sys
import psutil
import model_storage


def validate_plan(plan, *, repo=REPO, root=ROOT, data=DATA):
    if set(plan) != {'candidate_id','stage','case_path','case_sha256',
                     'archive_path','archive_sha256','source_hashes'}:
        raise ValueError('Packing manifest schema differs')
    cid=plan['candidate_id']
    if not re.fullmatch(r'[A-Za-z0-9_]+',cid) or plan['stage']!='C_v2':
        raise ValueError('Packing candidate or stage differs')
    case=(repo/plan['case_path']).resolve()
    archive=(repo/plan['archive_path']).resolve()
    if case!=(root/f'results/funnel/C_v2/{cid}.json').resolve():
        raise ValueError('Packing case outside registered scope')
    if archive!=(data/f'c_models_v2/{cid}.npz').resolve():
        raise ValueError('Packing archive outside isolated corrected-C scope')
    if sha(case)!=plan['case_sha256'] or sha(archive)!=plan['archive_sha256']:
        raise ValueError('Packing evidence bytes changed')
    if read(case).get('candidate_id')!=cid:
        raise ValueError('Packing case identity differs')
    for path,expected in plan['source_hashes'].items():
        if sha(repo/path)!=expected:
            raise ValueError('Packing source changed')
    return cid


def main(path):
    identity=read(ROOT/'manifests/controller_owner.json')
    owner=psutil.Process(identity['pid'])
    if owner.create_time()!=identity['create_time'] or owner.cmdline()!=identity['command']:
        raise ValueError('Packing owner identity changed')
    if owner.pid not in {p.pid for p in psutil.Process().parents()}:
        raise ValueError('Packing worker is not descended from its owner')
    plan=read(path);cid=validate_plan(plan)
    result=model_storage.pack_one(cid,'C_v2')
    if result['original_sha256']!=plan['archive_sha256'] or result['case_sha256']!=plan['case_sha256']:
        raise ValueError('Packed evidence receipt identity differs')
    print(json.dumps(dict(candidate_id=cid,original_bytes=result['original_bytes'],
        packed_bytes=result['packed_bytes'],original_bytes_verified=True,
        prediction_bytes_unchanged=sha(REPO/plan['case_path'])==plan['case_sha256'])),flush=True)


if __name__=='__main__':
    main(sys.argv[1])
