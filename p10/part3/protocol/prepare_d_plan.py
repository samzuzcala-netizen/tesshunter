"""Freeze identity-only Part D inputs and source paths, before flux inspection."""
from common import REPO,ROOT,read,write,sha,utc
from registration_chain import verify
import csv,os,re


def main():
    verify()
    targets=list(csv.DictReader((ROOT/'manifests/targets_after_a.csv').open()))
    ids={int(r['tic_id']) for r in targets};lookup={tic:[] for tic in ids}
    for base,dirs,files in os.walk(REPO/'data/cache/audit_lightkurve'):
        for name in files:
            if not name.endswith(('_lc.fits','_llc.fits')):continue
            m=re.search(r'(?<!\d)(\d{16})(?!\d)',name)
            if m and int(m[1]) in ids:lookup[int(m[1])].append((__import__('pathlib').Path(base)/name).relative_to(REPO).as_posix())
    policy=read(ROOT/'manifests/sector_policy.json');notice=policy['notice_snapshot']
    if sha(REPO/notice['path'])!=notice['sha256']:raise RuntimeError('Frozen timing notice changed')
    write(ROOT/'manifests/sector_policy_effective.json',dict(policy,utc=utc(),
        acquisition_27_55='Retained only for unreindexed v1 pilot stars; D1 floor 56 for all v2 acquisition',
        amendment_chain_sha256=sha(ROOT/'manifests/registration_amendments_D1_D4.json')))
    jobs=[]
    for tic in sorted(ids):
        write(ROOT/f'manifests/input_jobs/tic{tic}.json',dict(tic_id=tic,source_paths=sorted(lookup[tic]),
            index_sha256=sha(REPO/f'data/survey/audit_lc/tic{tic}/index.json'),notice_snapshot_sha256=notice['sha256']))
        jobs.append(dict(job_id=f'tic{tic}',arguments=['p10/part3/protocol/verify_prepare_star.py',str(tic)],result_path=f'p10/part3/results/native_noise/tic{tic}.json'))
    write(ROOT/'manifests/verify_prepare_jobs.json',jobs)
    write(ROOT/'manifests/verify_prepare_preflight.json',dict(utc=utc(),jobs=len(jobs),workers=8,deadline_seconds=600,
        forecast_minutes=25,forecast_basis='Read-only local FITS/NPZ identity plus native preprocessing, 8 top-level single-thread workers; 600-second hard job bound. No search or ephemeris used.',
        source_paths=sum(map(len,lookup.values())),missing_source_hosts=sorted(t for t in ids if not lookup[t]),
        preparation='Unchanged survey_p8 harmonise_cadence and build_prepared under frozen survey_p10; paired P8 ingestion-key assertion',
        usable_sector_rule='At least 50 retained native prepared points per sector, the existing P11 input rule',
        deadline_behavior='Failed preparation remains INPUT_OPERATIONAL_UNKNOWN, never a scientific miss'))
    print('Part D plan:',len(jobs),'hosts;',sum(map(len,lookup.values())),'FITS paths')


if __name__=='__main__':main()
