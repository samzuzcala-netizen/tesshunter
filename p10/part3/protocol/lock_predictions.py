"""Lock every selected host's terminal predictions after its blind search closes."""
from common import REPO,ROOT,read,write,sha,utc
from registration_execution_v3 import verify
from verify_search_io import inspect
from science_json import safe
import math


def normalize(tic,result):
    partitions={r['label']:bool(r.get('budget_exhausted')) for r in result.get('searches',[])}
    rows=[]
    for candidate in (result.get('result') or {}).get('planets') or []:
        required=['planet_num','period_days','epoch_btjd','duration_days','depth_ppt']
        if any(k not in candidate or candidate[k] is None for k in required):raise RuntimeError('Accepted prediction lacks ephemeris fields')
        if not all(math.isfinite(float(candidate[k])) for k in required):raise RuntimeError('Accepted prediction is nonfinite')
        partition=candidate.get('search')
        rows.append(dict(tic_id=tic,candidate_id=f'tic{tic}_p{int(candidate["planet_num"]):02d}',planet_num=int(candidate['planet_num']),
            period_days=float(candidate['period_days']),epoch_btjd=float(candidate['epoch_btjd']),duration_days=float(candidate['duration_days']),
            depth_ppt=float(candidate['depth_ppt']),stitch_snr=candidate.get('stitch_snr'),partition=partition,
            partition_budget_exhausted=partitions.get(partition),all_partition_budget_flags=partitions,raw_candidate=candidate))
    if len({r['candidate_id'] for r in rows})!=len(rows):raise RuntimeError('Duplicate accepted candidate identity')
    return rows


def lock(preset):
    verify()
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Search owner has not closed')
    path=ROOT/f'manifests/predictions_{preset}.json'
    if path.exists():
        seal=read(path.with_name(path.stem+'_seal.json'))
        if sha(path)!=seal['sha256']:raise RuntimeError('Locked predictions changed')
        return seal
    allocation=read(ROOT/'manifests/allocation.json');pilot=set(allocation['reused_pilot_tic_ids']);phase=f'search_{preset}'
    closure=read(ROOT/f'results/controllers/{phase}/closure.json')
    if closure['status']!='CLOSED' or not closure['all_owned_workers_closed'] or not closure['source_hashes_unchanged'] or closure['pending']:raise RuntimeError('Search phase did not close cleanly')
    records=[];audits=[];missing=[];unknown=[]
    for tic in allocation['selected_tic_ids']:
        job=f'{preset}_tic{tic}';prior='timing_pilot_search' if tic in pilot else phase
        attempt_path=ROOT/f'results/controllers/{prior}/attempts/{job}.json';attempt=read(attempt_path)
        io=ROOT/f'results/search_io/{job}.jsonl';audit=inspect(io) if io.exists() else None
        if audit:audits.append(audit)
        else:missing.append(job)
        if audit and audit['forbidden']:
            stop=ROOT/f'results/STOP4_{preset}.json'
            if not stop.exists():write(stop,dict(utc=utc(),status='STOP-4',job_id=job,audit=audit))
            raise RuntimeError('STOP-4: sidecar access in blind search')
        receipt_path=ROOT/f'results/search_receipts/{preset}/tic{tic}.json';receipt=read(receipt_path) if receipt_path.exists() else None
        row=dict(tic_id=tic,preset=preset,reused_pilot=tic in pilot,attempt_status=attempt['status'],attempt_sha256=sha(attempt_path),accepted=[],status='OPERATIONAL_UNKNOWN')
        if receipt:
            row.update(receipt_sha256=sha(receipt_path),result_path=receipt['result_path'],result_sha256=receipt['result_sha256'],trace_path=receipt['trace_path'],trace_sha256=receipt['trace_sha256'],prepared_sha256=receipt['prepared_sha256'],ingest_key=receipt['ingest_key'])
            if sha(REPO/receipt['result_path'])!=receipt['result_sha256']:raise RuntimeError('Saved search result changed')
            if receipt['trace_sha256'] and sha(REPO/receipt['trace_path'])!=receipt['trace_sha256']:raise RuntimeError('Saved trace changed')
            result=read(REPO/receipt['result_path'])
            if attempt['status']=='COMPLETE' and receipt['status']=='COMPLETE' and result['status']=='ok' and audit and not audit['malformed_rows']:
                row.update(status='COMPLETE',accepted=normalize(tic,result))
        if row['status']!='COMPLETE':unknown.append(tic)
        records.append(row)
    if len(records)!=436:raise RuntimeError('Incomplete evaluated membership')
    payload=dict(utc=utc(),status='LOCKED',preset=preset,allocation_sha256=sha(ROOT/'manifests/allocation.json'),hosts=records,
        n_hosts=len(records),n_accepted=sum(len(r['accepted']) for r in records),operational_unknown_tic_ids=unknown,
        meaning='Every evaluated host has terminal accounting; accepted predictions are immutable. Unknowns remain unknown, not misses.',
        input_ingest_keys=sorted({r['ingest_key'] for r in records if 'ingest_key' in r}))
    write(path,safe(payload))
    audit_path=ROOT/f'results/io_verification_{preset}.json'
    write(audit_path,dict(utc=utc(),status='NO_SIDECAR_ACCESS_RECORDED',logs=audits,missing_logs_operational_unknown=missing,
        malformed_logs_operational_unknown=[r['path'] for r in audits if r['malformed_rows']],complete_io_coverage=not missing and not any(r['malformed_rows'] for r in audits)))
    seal=dict(utc=utc(),path=path.relative_to(REPO).as_posix(),sha256=sha(path),hosts=436,accepted=payload['n_accepted'],unknowns=len(unknown),io_audit_sha256=sha(audit_path),allocation_sha256=payload['allocation_sha256'])
    write(path.with_name(path.stem+'_seal.json'),seal)
    return seal


def both_locked():
    allocation=read(ROOT/'manifests/allocation.json');out=[]
    for preset in allocation['preset_sequence']:
        p=ROOT/f'manifests/predictions_{preset}.json';s=read(p.with_name(p.stem+'_seal.json'))
        if sha(p)!=s['sha256'] or s['allocation_sha256']!=sha(ROOT/'manifests/allocation.json'):raise RuntimeError('Prediction lock changed')
        out.append(s)
    return out
