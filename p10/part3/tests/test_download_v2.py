from download_star_v2 import allowed_download_rows
from build_batches_v2 import transport_class


def test_d1_sector_floor_comes_from_config_and_qlp_exclusions_hold():
    class Result:
        mission = [f"TESS Sector {s}" for s in (26, 27, 55, 56, 80, 80, 105, 106, 1751)]
        author = ["QLP", "QLP", "SPOC", "TESS-SPOC", "QLP", "TESS-SPOC", "QLP", "SPOC", "SPOC"]
        def __len__(self): return len(self.author)
    config = dict(sector_min=56, sector_max=105, qlp_excluded_sectors=[80, 83, 85, 99, 100, 101, 102, 103, 104])
    # 27 and 55 are the P8 superset and must now be dropped; QLP at 80 is excluded, TESS-SPOC at 80 is kept.
    assert allowed_download_rows(Result(), config) == [3, 5, 6]
    # The version-1 behaviour is recovered only by asking for it explicitly.
    assert allowed_download_rows(Result(), dict(config, sector_min=27)) == [1, 2, 3, 5, 6]


def test_d3_transport_classification():
    assert transport_class("TIMEOUT", None)
    assert transport_class("OPERATIONAL_UNKNOWN", None)
    assert transport_class("OPERATIONAL_UNKNOWN", "HTTPError: 502 Server Error: Bad Gateway for url: x")
    assert transport_class("OPERATIONAL_UNKNOWN", "HTTPError: 404 Client Error: Not Found for url: y")
    assert transport_class("OPERATIONAL_UNKNOWN", "ConnectionError: ('Connection aborted.', RemoteDisconnected(...))")
    assert not transport_class("OPERATIONAL_UNKNOWN", "ValueError: could not convert string to float")
    assert not transport_class("OPERATIONAL_UNKNOWN", "KeyError: 'tce_period'")
