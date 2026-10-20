"""VSX separations must not depend on the units chosen for VizieR's _r column."""
import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import p8_neighbours as N


@pytest.mark.parametrize("target,source,expected", [
    ({"ra_deg": 0, "dec_deg": 0}, {"RAJ2000": 0.5 / 60, "DEJ2000": 0}, 30.0),
    ({"ra_deg": 359.999, "dec_deg": 0}, {"RAJ2000": 0.001, "DEJ2000": 0}, 7.2),
    ({"ra_deg": 10, "dec_deg": 60}, {"RAJ2000": 10.01, "DEJ2000": 60}, 18.0),
])
def test_coordinate_separations_cover_units_wrap_and_declination(target, source, expected):
    source.update(Name="test", _r=0.5, sep_arcsec=1800.0, Type="E")
    original = copy.deepcopy(source)
    result = N.vsx_with_separations(target, [source])[0]
    assert result["sep_arcsec"] == expected
    assert {k: v for k, v in result.items() if k != "sep_arcsec"} == {k: v for k, v in source.items() if k != "sep_arcsec"}
    assert source == original


def test_cached_bulk_distances_are_repaired_without_querying(tmp_path, monkeypatch):
    from astroquery.vizier import Vizier
    monkeypatch.setattr(N, "BULK", tmp_path)
    def no_query(*args, **kwargs):
        raise AssertionError("A cached result must not query the service")
    monkeypatch.setattr(type(Vizier), "query_region", no_query)
    cache = tmp_path / "vsx_00000.json"
    cache.write_text(json.dumps({"1": [{"RAJ2000": 0.5 / 60, "DEJ2000": 0, "_r": 0.5,
                                       "sep_arcsec": 1800.0, "Name": "test", "Type": "E"}]}))
    result = N.bulk_vsx([{"tic_id": 1, "ra_deg": 0, "dec_deg": 0}])
    assert result[1][0]["sep_arcsec"] == 30.0
    assert json.loads(cache.read_text())["1"][0] == result[1][0]


def test_new_bulk_query_uses_sky_coordinates(tmp_path, monkeypatch):
    from astropy.table import Table
    from astroquery.vizier import Vizier
    monkeypatch.setattr(N, "BULK", tmp_path)
    table = Table({"_q": [1], "_r": [0.5], "RAJ2000": [0.5 / 60], "DEJ2000": [0.0], "Name": ["test"]})
    table["_r"].unit = "arcmin"
    monkeypatch.setattr(type(Vizier), "query_region", lambda *args, **kwargs: [table])
    result = N.bulk_vsx([{"tic_id": 1, "ra_deg": 0, "dec_deg": 0}])
    assert result[1][0]["sep_arcsec"] == 30.0


def test_completed_repair_preserves_later_candidate_context(tmp_path, monkeypatch):
    import p8_repair_vsx_separations as R
    record = tmp_path / "neighbour.json"
    record.write_text(json.dumps({"candidate_depths_ppt": [4.0], "vsx": {"objects": [{"Name": "test", "sep_arcsec": 30.0}]}}))
    evidence = tmp_path / "repair.json"
    evidence.write_text(json.dumps({"status": "complete", "files": [{"path": "neighbour.json", "kind": "neighbour",
        "replacements": [{"index": 0, "name": "test", "old": 1800.0, "new": 30.0}]}]}))
    monkeypatch.setattr(R, "REPO", tmp_path)
    monkeypatch.setattr(R, "EVIDENCE", evidence)
    before = record.read_bytes(), evidence.read_bytes()
    R.main()
    assert (record.read_bytes(), evidence.read_bytes()) == before
