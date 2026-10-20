"""Lead's deterministic-clock replay of one sealed P10.3 Stage A record."""
from pathlib import Path
from types import SimpleNamespace
import contextlib,copy,hashlib,json,os,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'protocol'))
from p12_common import REPO,ROOT,DATA,read,write,sha,utc,append_jsonl,environment
environment()
from blind_io_p12 import install,summary
import funnel_worker_p12 as W
import policy_products_p12 as P
from input_identity_p12 import choose_verified

def run(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    guard=install(destination/'io.jsonl')
    seal_path=REPO/'p10/part3/manifests/final_data_seal.json';seal=read(seal_path)
    sealed=seal['files']
    if isinstance(sealed,list):sealed={row['path']:row for row in sealed}
    if not isinstance(sealed,dict):raise TypeError('Unsupported historical seal format')
    selected_tic=None
    def observed(path,stage):
        relative=Path(path).relative_to(REPO).as_posix()
        append_jsonl(ROOT/'manifests/exposure_ledger.jsonl',dict(utc=utc(),path=relative,stage=stage,
            reader='script Stage A engineering replay',prompt_of_origin='P10.3',star=selected_tic,
            p9_truth=False,sidecar=False,ttt_table=False,calibration_truth=False))
        return read(path)
    entries=observed(REPO/'p10/part3/manifests/full_funnel_candidates.json','fixed fixture selection')['entries']
    entries.sort(key=lambda row:hashlib.sha256(('2026092002:p12:stageA-fixture:'+row['candidate_id']).encode()).hexdigest())
    selected=entries[0];cid=selected['candidate_id'];tic=int(selected['tic_id'])
    selected_tic=tic
    runtime_path=REPO/selected['runtime_path']
    assert sha(runtime_path)==selected['runtime_sha256']
    original=observed(runtime_path,'sealed Stage A runtime')
    wrapper_path=REPO/f'p10/part3/results/funnel/A/{cid}.json'
    wrapper=observed(wrapper_path,'sealed Stage A expected record')
    key=wrapper['measurement']['key']
    expected_path=REPO/f'data/survey/p10/part3/funnel/cases/{cid}/stageA/{key}.json'
    expected=observed(expected_path,'sealed Stage A byte expectation')
    relative=expected_path.relative_to(REPO).as_posix()
    digest=sealed.get(relative)
    if isinstance(digest,dict):digest=digest.get('sha256')
    assert digest==sha(expected_path),'Expected Stage A record is not sealed'
    identity=observed(REPO/f'p10/part3/results/input_identity/tic{tic}.json','historical verified product identity')
    configuration=read(ROOT/'protocol/config.json')
    products=choose_verified(identity['records'],configuration)
    assert [(p['raw_path'],p['raw_sha256']) for p in products]==[(p['raw_path'],p['raw_sha256']) for p in original['raw_products']]
    fixture_root=destination/'p12';write(fixture_root/'protocol/config.json',configuration)
    identity['selected_sectors']=[p['metadata']['sector'] for p in products]
    write(fixture_root/f'manifests/input_identity/tic{tic}.json',identity)
    P.ROOT=fixture_root
    runtime={key:copy.deepcopy(original[key]) for key in ('candidate_id','tic_id','candidate','all_candidates','star','source_hashes','neighbours_reference')}
    runtime.update(phase='pilot',arm='archival')
    output=DATA/'engineering/stageA_replay'/hashlib.sha256(str(destination.resolve()).encode()).hexdigest()[:20]
    if output.exists():raise FileExistsError(output)
    F,restore=W.setup(runtime,output)
    # Only the two operational clock fields are deterministic fixture inputs.
    # Every scientific value is recomputed from the original verified arrays.
    original_clock=F.V.time;original_utc=F.V.utc
    ticks=iter((0.,float(expected['seconds'])))
    F.V.time=SimpleNamespace(perf_counter=lambda:next(ticks))
    F.V.utc=lambda:expected['generated_utc']
    started=time.perf_counter()
    try:
        # Scientific library chatter is discarded, never copied into a test log.
        with open(os.devnull,'w',encoding='utf-8') as stream:
            with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
                actual=F.V.stagea_one(F.V.jobs()[0],threads=1,force=True)
    finally:F.V.time=original_clock;F.V.utc=original_utc;restore()
    actual_path=output/'stageA'/f'{key}.json'
    same=actual_path.read_bytes()==expected_path.read_bytes()
    actual_record=read(actual_path)
    fields=sorted(key for key in set(actual_record)|set(expected) if actual_record.get(key)!=expected.get(key))
    result=dict(utc=utc(),status='PASS' if same else 'FAIL',byte_identical=same,mismatch_fields=fields,
        expected_sha256=sha(expected_path),actual_sha256=sha(actual_path),wall_seconds=time.perf_counter()-started,
        fixture_selection='lowest SHA256 of 2026092002:p12:stageA-fixture:<candidate_id>',
        deterministic_fixture_fields=['generated_utc','seconds'],scientific_fields_mocked=False,
        expected_record=relative,output_record=actual_path.relative_to(REPO).as_posix(),io=summary(guard),
        p12_sources={p.relative_to(REPO).as_posix():sha(p) for p in (ROOT/'protocol/funnel_worker_p12.py',ROOT/'protocol/rules_p12.py',ROOT/'protocol/policy_products_p12.py')})
    write(destination/'replay.json',result)
    write(ROOT/'tests/pilot_stageA_replay.json',result,replace=(ROOT/'tests/pilot_stageA_replay.json').exists())
    print(json.dumps(dict(status=result['status'],passed=int(same),failed=int(not same),mismatch_count=len(fields))),flush=True)
    assert same,'Stage A replay bytes differ'

if __name__=='__main__':
    # Imports/setup can also emit library chatter. Preserve only a numeric verdict.
    try:
        with open(os.devnull,'w',encoding='utf-8') as sink,contextlib.redirect_stdout(sink),contextlib.redirect_stderr(sink):
            run(sys.argv[1])
    except BaseException:
        print(json.dumps(dict(status='FAIL',passed=0,failed=1)),flush=True)
        raise SystemExit(1)
    print(json.dumps(dict(status='PASS',passed=1,failed=0)),flush=True)
