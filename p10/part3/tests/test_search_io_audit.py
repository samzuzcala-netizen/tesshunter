import json
from verify_search_io import inspect


def test_sidecar_denial_or_path_is_a_stop_signal_and_truncation_is_unknown(tmp_path):
    p=tmp_path/'io.jsonl'
    p.write_text(json.dumps({'path':r'C:\cache\spoc_tce.ephemerides.csv','denied':True})+'\n'+ '{"path":')
    r=inspect(p)
    assert len(r['forbidden'])==1 and r['malformed_rows']==1
    p.write_text(json.dumps({'path':r'C:\data\native200.npz','denied':False})+'\n')
    r=inspect(p)
    assert not r['forbidden'] and r['malformed_rows']==0
