"""Record unblinded human-style D review without importing control truth."""
from common import *
import argparse,csv

def queue():
    records=[]
    for tic in read(P9/'manifests/final_ids.json'):
        root=P9/'results/blind'/f'tic{tic}'
        for path in (root/'stageC').glob('*.json'):
            c=read(path)
            if c.get('decision')!='PASS':continue
            key=c['key'];dp=root/'stageD'/f'{key}.json';ep=root/'expensive'/f'{key}.json'
            d=read(dp) if dp.exists() else {};e=read(ep) if ep.exists() else {}
            f=(d.get('fit') or {});a=f.get('adopted') or {}
            records.append(dict(tic_id=tic,key=key,reviewed=(root/'final'/f'{key}.json').exists(),
              provisional_verdict=d.get('provisional_verdict'),provisional_reason=d.get('provisional_reason'),
              adopted_fit=a,fit_uncertainty_issues=f.get('uncertainty_issues'),expensive_status=e.get('status'),
              fpp={k:(e.get('fpp') or {}).get(k) for k in ['available','fpp','nfpp','error','aperture_source','n_points_used']},
              centroid={k:(e.get('centroid') or {}).get(k) for k in ['available','sigma','shift_arcsec','sectors_used']},
              pixel_assets=[str(p.relative_to(P9)) for p in (root/'eb_screen').glob('*.png')]))
    write(P9/'reviews/queue.json',dict(utc=utc(),status='unblinded review queue; no published ephemerides or labels loaded',records=records))
    print([(r['key'],r['provisional_verdict'],r['expensive_status'],len(r['pixel_assets']),r['reviewed']) for r in records],flush=True)

def apply(path):
    from runner import restrict_inputs
    restrict_inputs();review=read(path);tic=int(review['tic_id']);key=review['key'];root=P9/'results/blind'/f'tic{tic}'
    if (P9/'results/locks'/f'tic{tic}.json').exists():raise RuntimeError('Host already locked; do not change primary verdict')
    for folder,field,allowed in [('stageA','decision',{'PASS'}),('secondary','gate',{'PASS','HOLD'}),('stageB','decision',{'PASS'}),('stageC','decision',{'PASS'})]:
        if read(root/folder/f'{key}.json').get(field) not in allowed:raise RuntimeError('D not permitted by frozen funnel')
    verdict=review['scientific_verdict']
    if verdict not in ['SUBMIT_EQUIVALENT','HOLD','KILL','OPERATIONAL_INCOMPLETE']:raise ValueError('Unknown review verdict')
    d=read(root/'stageD'/f'{key}.json')
    b=read(root/'stageB'/f'{key}.json')
    if verdict=='SUBMIT_EQUIVALENT' and (b.get('max_verdict')=='HOLD' or d.get('provisional_verdict') in ('HOLD','KILL')):
        raise RuntimeError('Review cannot override a frozen B/fit verdict cap')
    if review.get('legitimate_useful_hold') and (verdict!='HOLD' or not review.get('hold_reason') or not review.get('coherent_transit_evidence') or not review.get('resolvable_limitation')):
        raise ValueError('Useful HOLD requires explicit coherent transit and resolvable limitation')
    evidence={}
    for relative in review['evidence_files']:
        p=P9/relative
        if not p.resolve().is_relative_to(root.resolve()):raise RuntimeError('Review evidence must come from this blind result')
        evidence[relative]=sha(p)
    out=dict(review,utc=utc(),manual_review_blinded=False,actual_submission_eligible=False,
      adjudication_basis='Unblinded inspection of saved blind evidence; published label does not supply a scientific pass',
      evidence_sha256=evidence,review_source_sha256=sha(path),writer_sha256=sha(Path(__file__)))
    write(root/'final'/f'{key}.json',out);print('recorded',key,verdict,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('cmd',choices=['queue','apply']);p.add_argument('--review',type=Path);a=p.parse_args()
    if a.cmd=='queue':queue()
    else:apply(a.review)
