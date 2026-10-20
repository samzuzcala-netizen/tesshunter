"""Fixed identity batches for unchanged P8 catalogue queries, two workers total."""
from common import ROOT,REPO,read,write,utc
import csv


def main():
    ids=sorted(int(r['tic_id']) for r in csv.DictReader((ROOT/'manifests/targets_after_a.csv').open()))
    bulk=[dict(job_id=kind,arguments=['p10/part3/protocol/neighbours_worker.py',kind],result_path=f'p10/part3/results/neighbour_receipts/{kind}.json') for kind in ('simbad','vsx')]
    write(ROOT/'manifests/neighbours_bulk_jobs.json',bulk)
    jobs=[]
    for i in range(0,len(ids),25):
        name=f'neighbours_{i//25+1:02d}';path=ROOT/f'manifests/neighbour_batches/{name}.json'
        write(path,dict(batch_id=name,tics=ids[i:i+25]))
        jobs.append(dict(job_id=name,arguments=['p10/part3/protocol/neighbours_batch_worker.py',path.relative_to(REPO).as_posix()],result_path=f'p10/part3/results/neighbour_batches/{name}.json'))
    write(ROOT/'manifests/neighbours_stars_jobs.json',jobs)
    write(ROOT/'manifests/neighbours_preflight.json',dict(utc=utc(),stars=len(ids),workers=2,batch_size=25,
        bulk_deadline_seconds=900,batch_deadline_seconds=900,bulk_forecast_minutes=8,star_forecast_minutes=18,
        forecast_basis='Unchanged P8 measured 1.7-second Gaia cones; 25-host persistent top-level batches amortize imports. Allow 18 minutes at two workers including network and startup margin.',
        case_checkpoints='Each star retains its native neighbour record and status/timing receipt; batch failures never become scientific misses',
        science_source='Unchanged scripts/p8_neighbours.py bulk_simbad, bulk_vsx, and one, with every output root isolated'))
    print('Neighbour plan',len(ids),'stars in',len(jobs),'fixed batches; two workers')


if __name__=='__main__':main()
