import math
import pytest
from common import write,read
import full_funnel_plan as F


@pytest.mark.parametrize('remaining',[28.2,11.2,3.,2.5])
def test_C_cap_uses_B_closure_ledger_and_is_immutable(tmp_path,monkeypatch,remaining):
    root=tmp_path/'p10/part3';monkeypatch.setattr(F,'ROOT',root);monkeypatch.setattr(F,'verify',lambda:None)
    write(root/'results/controllers/funnel_B/closure.json',dict(status='CLOSED',all_owned_workers_closed=True,source_hashes_unchanged=True,utc='closed'))
    write(root/'manifests/resource_ledger.json',dict(new_queue_hours=31.98-remaining))
    write(root/'manifests/supervision_policy_v3.json',dict(user_authorized=True))
    r=F.freeze_C_cap();assert r['N_C']==math.floor((r['remaining_hours_at_B_closure']-3.)*3/3.4)
    assert r['max_runnable']==max(0,r['N_C']) and r['max_concurrent']==3
    write(root/'manifests/resource_ledger.json',dict(new_queue_hours=31.),replace=True)
    assert F.freeze_C_cap()==r
