import pytest
import acquisition_meter as meter
from common import read
from download_star import allowed_download_rows


def test_byte_reservations_and_failed_reads_are_bounded(tmp_path,monkeypatch):
    monkeypatch.setattr(meter,"STATE",tmp_path/"meter.json")
    monkeypatch.setattr(meter,"LOCK",tmp_path/"lock")
    with meter.transaction() as state:
        state["prior_bytes"]=0;state["cap_bytes"]=7
    assert meter.reserved_read(None,10,lambda r,n:b"a"*min(4,n))==b"aaaa"
    assert read(meter.STATE)["measured_body_bytes"]==4
    assert meter.reserved_read(None,10,lambda r,n:b"b"*n)==b"bbb"
    with pytest.raises(RuntimeError,match="ACQUISITION_CAP"):
        meter.reserved_read(None,1,lambda r,n:b"x")
    with meter.transaction() as state:state["cap_bytes"]=10
    def failed(*args):raise OSError("interrupted transfer")
    with pytest.raises(OSError):meter.reserved_read(None,3,failed)
    state=read(meter.STATE)
    assert state["failed_read_upper_bytes"]==3
    assert sum(state["reservations"].values())==0


def test_acquisition_sector_filter_keeps_author_alternatives():
    class Result:
        mission=[f"TESS Sector {s}" for s in (26,27,55,80,80,105,106,1751)]
        author=["QLP","QLP","SPOC","QLP","TESS-SPOC","QLP","SPOC","SPOC"]
        def __len__(self):return len(self.author)
    assert allowed_download_rows(Result(),dict(sector_max=105,qlp_excluded_sectors=[80]))==[1,2,4,5]
