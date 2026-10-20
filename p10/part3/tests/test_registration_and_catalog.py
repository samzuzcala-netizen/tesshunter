import io
import json
import numpy as np
import pandas as pd
import pytest
from common import REPO, ROOT, read, sha
from build_list import domain_mask, original_list, corrected_inventory, apply_input_cuts
from catalog_adapter import cx, LEGACY_PARSE, EPHEMERIS_COLUMNS, _parse_spoc_tce, hard_stop_p10, sector_stratum
from tce_families import families, counts


def raw_row(tic=101,period=2,sector="s0001-s0036"):
    return dict(zip(EPHEMERIS_COLUMNS,[f"{tic}-01",tic,1,sector,period,0.00001,1500,
        0.001,2,0.2,1000,100,12,3,0]))


def raw_bytes(rows):
    return pd.DataFrame(rows).to_csv(index=False,lineterminator="\n").encode()


@pytest.mark.parametrize("column,value",[("Teff",3600),("rad",0.45),("Tmag",12.49),("Tmag",14.01),("gallat",19.99),("n_sectors_200s",2),("n_sectors_2min_in_search",2)])
def test_each_domain_boundary(column,value):
    row=dict(Teff=3599,rad=0.449,Tmag=12.5,gallat=-20,n_sectors_200s=4,n_sectors_2min_in_search=1,
        xmatch_status="REJECT",xmatch_tic_sources="spoc_tce")
    assert domain_mask(pd.DataFrame([row])).iloc[0]
    row[column]=value
    assert not domain_mask(pd.DataFrame([row])).iloc[0]


def test_sidecar_pool_wide_duplicates_and_no_normalized_change(tmp_path):
    files=[("tess-s0001-s0036_dvr-tcestats.csv",raw_bytes([raw_row(101),raw_row(202),raw_row(999)])),
           ("tess-s0001-s0055_dvr-tcestats.csv",raw_bytes([raw_row(101,2.01,"s0001-s0055")]))]
    expected=LEGACY_PARSE(files).to_csv(index=False).encode()
    destination=tmp_path/"ephemerides.csv"
    actual=_parse_spoc_tce(files,ephemerides_path=destination,pool_tics=[101,202])
    assert actual.to_csv(index=False).encode()==expected
    rows=pd.read_csv(destination)
    assert list(rows.ticid)==[101,202,101]
    assert len(rows)==3
    assert not rows["source_filename"].isna().any()
    assert len(families(rows.to_dict("records")))==2
    with pytest.raises(FileExistsError):
        _parse_spoc_tce(files,ephemerides_path=destination,pool_tics=[101,202])


def test_sidecar_requires_real_headers_and_complete_pool(tmp_path):
    with pytest.raises(ValueError,match="Explicit complete pool"):
        _parse_spoc_tce([("run",raw_bytes([raw_row()]))],ephemerides_path=tmp_path/"a")
    row=raw_row();row.pop("tce_period_err")
    with pytest.raises(ValueError,match="Missing ephemeris headers"):
        _parse_spoc_tce([("run",raw_bytes([row]))],ephemerides_path=tmp_path/"b",pool_tics=[101])


@pytest.mark.parametrize("run,expected",[("s0055","INDEPENDENT"),("s0001-s0055","INDEPENDENT"),("s0056","OVERLAPPING"),("s0014-s0060","OVERLAPPING")])
def test_stratum_boundary(run,expected):
    assert sector_stratum(run)[2]==expected


def synthetic_catalog(sources):
    tables={source:pd.DataFrame(dict(tic_id=[101],ra=[10.],dec=[20.],label=["example"],detail=[""])) for source in sources}
    return cx.KnownObjectCatalog(tables,{})


@pytest.mark.parametrize("other",["toi","ctoi","nasa_ps","nasa_pscomppars","tess_eb"])
def test_other_sources_stay_reject(other):
    cat=synthetic_catalog(["spoc_tce",other])
    assert hard_stop_p10(101,catalog=cat,resolve_neighbours=False).status=="REJECT"


def test_bare_tce_flag_interface_and_neighbour_unchanged():
    cat=synthetic_catalog(["spoc_tce"])
    assert cx.hard_stop(101,catalog=cat,resolve_neighbours=False).status=="REJECT"
    row=raw_row()
    flag=hard_stop_p10(101,catalog=cat,resolve_neighbours=False,ephemerides=[row])
    assert flag.status=="FLAG"
    assert flag.to_dict()["tic_matches"][0]["ephemerides"][0]["tce_period"]==2
    assert "bare SPOC" in flag.summary()
    before=cat.check(202,10.,20.)
    after=hard_stop_p10(202,10.,20.,catalog=cat,resolve_neighbours=False)
    assert before.to_dict()==after.to_dict() and after.status=="FLAG"
    with pytest.raises(ValueError,match="requires ephemerides"):
        hard_stop_p10(101,catalog=cat,resolve_neighbours=False)


def test_corrected_inventory_intersects_ffi_and_requires_every_list(tmp_path):
    np.save(tmp_path/"s056.npy",np.array([101,202]))
    np.save(tmp_path/"s057.npy",np.array([202]))
    inventory,files=corrected_inventory([101,202],tmp_path,56,57)
    assert inventory=={101:[56],202:[56,57]}
    with pytest.raises(ValueError,match="Missing MIT"):
        corrected_inventory([101],tmp_path,56,58)
    base=dict(tic_id=101,Tmag=13,Teff=3400,rad=.3,gaia_dwarf_check="pass",
        sectors_200s="57,58,59",n_sectors_2min_in_search=0)
    row=apply_input_cuts(pd.DataFrame([base]),inventory)[0]
    assert row["n_corrected_twomin_in_search"]==0 and row["after_a_eligible"]


def test_real_registered_531_and_p8_evidence_unchanged():
    if not (ROOT/"results/hard_stop_p10.json").exists():
        pytest.skip("Part B/C has not executed")
    result=read(ROOT/"results/hard_stop_p10.json")
    assert len(result["original"])==531
    assert all(r["old"]=="REJECT" and r["new"]=="FLAG" for r in result["original"])
    assert len(result["p8"])==2000 and all(r["unchanged"] for r in result["p8"])
    assert all(sha(REPO/p)==h for p,h in read(ROOT/"manifests/crossmatch_before.json").items())
    assert read(ROOT/"results/part_a.json")["after_corrected_ffi_majority"]==473


def test_registration_seal():
    from registration_chain import verify
    assert verify()["original_snapshot_verified"]
