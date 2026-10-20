"""Machine-only sidecar-access audit before advancing a closed search phase."""
from common import REPO,ROOT,read,write,sha,utc
from pathlib import Path
import json,os


def inspect(log):
    denied=[];malformed=0;events=0
    for line in log.read_text(encoding='utf-8').splitlines():
        try:r=json.loads(line)
        except json.JSONDecodeError:malformed+=1;continue
        events+=1
        if r.get('denied') or Path(r.get('path','').replace('\\','/')).name.casefold()=='spoc_tce.ephemerides.csv':denied.append(r)
    return dict(path=log.relative_to(REPO).as_posix() if log.is_relative_to(REPO) else str(log),sha256=sha(log),events=events,malformed_rows=malformed,forbidden=denied)


def pilot():
    jobs=read(ROOT/'manifests/timing_pilot_search_jobs.json');records=[];missing=[]
    for j in jobs:
        p=ROOT/f'results/search_io/{j["job_id"]}.jsonl'
        if p.exists():records.append(inspect(p))
        else:missing.append(j['job_id'])
    forbidden=[r for r in records if r['forbidden']]
    result=dict(utc=utc(),status='STOP-4' if forbidden else 'NO_SIDECAR_ACCESS_RECORDED',logs=records,
        missing_logs_operational_unknown=missing,malformed_log_count=sum(r['malformed_rows']>0 for r in records),
        complete_io_coverage=not missing and not any(r['malformed_rows'] for r in records),source_sha256=sha(__file__))
    write(ROOT/'results/timing_pilot_io_verification.json',result)
    if forbidden:raise RuntimeError('STOP-4: a sidecar path was recorded by a blind worker')
    return result
