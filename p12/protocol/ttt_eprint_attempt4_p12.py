"""One authorized 600-second e-print parser attempt; no truth values emitted."""
import json
import time
from pathlib import Path
import pandas as pd
from p12_common import ROOT, REPO, DATA, read, write, sha, utc, append_jsonl
from fetch_ttt_p12 import _eprint_candidates, _choose_table, _normalized_columns, _ephemeris_table, select_negatives


def main():
    started=utc(); clock=time.perf_counter()
    plan=read(ROOT/'manifests/ttt_attempt4_plan.json')
    archive=REPO/plan['archive_path']
    if sha(archive)!=plan['archive_sha256']:
        raise RuntimeError('E-print archive identity mismatch')
    candidates,inventory=_eprint_candidates(archive.read_bytes())
    tables=[]
    for name,frame in candidates:
        metadata=dict(member=name,rows=len(frame),**frame.attrs)
        tables.append(metadata)
        try: identifiers=_normalized_columns(frame).tic_id
        except ValueError: continue
        for tic in sorted(set(identifiers.astype(int))):
            append_jsonl(ROOT/'manifests/exposure_ledger.jsonl',dict(utc=utc(),star=int(tic),
                stage='0f authorized attempt 4 parser engineering',path=plan['archive_path']+'::'+name,
                reader='script-only manuscript structure inspection and ttt_eprint_attempt4_p12.py',
                prompt_of_origin='P12',content='catalogue parsing only; no candidate predictions or ephemeris values displayed'))
    result=dict(attempt=4,kind='eprint parser repair',started_utc=started,url=plan['url'],
        download_path=plan['archive_path'],sha256=plan['archive_sha256'],bytes=archive.stat().st_size,
        reused_download=True,new_http_requests=0,deadline_s=600,
        source_sha256=sha(ROOT/'protocol/fetch_ttt_p12.py'),candidate_tables=tables,archive_inventory=inventory,
        selection_rules_unchanged=True,selection_implementation_sha256=plan['selection_implementation_sha256'])
    try:
        name,table=_choose_table(candidates)
    except ValueError:
        result.update(status='UNAVAILABLE',reason=('ONLY_EXPLICITLY_ABBREVIATED_TABLES' if tables and all(t.get('incomplete_catalogue') for t in tables)
            else 'NO_COMPLETE_VALID_TIC_PERIOD_TABLE'),fallback_retained=True)
    else:
        pool=pd.read_csv(REPO/'data/survey/cache/p8/pool_after_xmatch.csv',low_memory=False)
        core=pd.read_csv(ROOT/'manifests/targets_p12_core.csv',usecols=['tic_id'])
        selected,selection=select_negatives(table,pool,core.tic_id)
        truth=_ephemeris_table(table[table.tic_id.isin(selected.tic_id)]) if len(selected) else table.iloc[:0].copy()
        table_path=DATA/'negatives/truth/ttt_table_attempt4.csv'
        with table_path.open('x',encoding='utf-8',newline='') as stream:table.to_csv(stream,index=False,lineterminator='\n')
        selected_path=ROOT/'manifests/ttt_negatives_attempt4.csv'
        with selected_path.open('x',encoding='utf-8',newline='') as stream:selected.to_csv(stream,index=False,lineterminator='\n')
        truth_path=DATA/'negatives/truth/ttt_ephemerides_attempt4.json'
        write(truth_path,dict(utc=utc(),source='eprint attempt 4',records=json.loads(truth.to_json(orient='records',double_precision=15))))
        result.update(status='COMPLETE',table_name=name,rows=len(table),selection=selection,
            table_path=table_path.relative_to(REPO).as_posix(),table_sha256=sha(table_path),
            selected_path=selected_path.relative_to(REPO).as_posix(),selected_sha256=sha(selected_path),
            guarded_ephemerides_path=truth_path.relative_to(REPO).as_posix(),ephemerides_sha256=sha(truth_path),fallback_retained=False)
    result.update(utc=utc(),wall_seconds=time.perf_counter()-clock)
    write(ROOT/'results/ttt_fetch/attempt4.json',result)
    print(json.dumps(dict(attempt=4,status=result['status'],candidate_tables=len(tables),
        parsed_rows=sum(t['rows'] for t in tables),selected=result.get('selection',{}).get('selected'),
        fallback_retained=result['fallback_retained'])))


if __name__=='__main__':main()
