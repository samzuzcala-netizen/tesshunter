"""Synthetic MRT parsing and union checks; no real catalogue values emitted."""
import pandas as pd
import pytest
import fetch_ttt_p12 as T


def fixture(rows,period_label='Per',period_start=45):
    header='''Title: Synthetic fixture
Authors: Test
Table: Catalogue fixture
================================================================================
Byte-by-byte Description of file: fixture.dat
--------------------------------------------------------------------------------
   Bytes Format Units Label Explanations
--------------------------------------------------------------------------------
   1- 10 I10    ---   TIC   Identifier
  45- 53 F9.6   d     Per   Orbital period
--------------------------------------------------------------------------------
'''
    header=header.replace('45- 53',f'{period_start}- {period_start+8}').replace('Per   Orbital',period_label+'   Orbital')
    return (header+'\n'.join(f'{tic:10d}'+(' '*(period_start-11))+f'{period:9.6f}'+(' '*10) for tic,period in rows)+'\n').encode()


def test_mrt_reader_matches_fixed_width_and_days():
    parsed=T._journal_mrt(fixture([(101,1.25),(202,2.5)]),2)
    assert parsed.tic_id.tolist()==[101,202]
    assert parsed.period_days.tolist()==[1.25,2.5]


def test_known_binary_table_maps_only_tess_period():
    body=fixture([(303,3.75)],'Per-TESS',38)
    parsed=T._journal_mrt(body,1)
    assert parsed.tic_id.tolist()==[303] and parsed.period_days.tolist()==[3.75]
    with pytest.raises(ValueError,match='required TIC/Per'):
        T._journal_mrt(body.replace(b'Per-TESS',b'Per-Gaia'),1)


def test_mrt_rejects_wrong_count_and_duplicate_identifiers():
    with pytest.raises(ValueError,match='row count'):
        T._journal_mrt(fixture([(101,1.25)]),2)
    with pytest.raises(ValueError,match='uniqueness'):
        T._journal_mrt(fixture([(101,1.25),(101,2.5)]),2)


def test_union_requires_both_tables_and_disjoint_identifiers():
    first=pd.DataFrame({'tic_id':[1,2],'period_days':[1.,2.]})
    second=pd.DataFrame({'tic_id':[3],'period_days':[3.]})
    assert T._journal_union({3:first,4:second},3).tic_id.tolist()==[1,2,3]
    with pytest.raises(ValueError,match='Both'):
        T._journal_union({3:first},2)
    with pytest.raises(ValueError,match='disjointness'):
        T._journal_union({3:first,4:first.iloc[:1]},3)


def test_journal_sources_are_exact_and_expected_counts_sum_to_10001():
    assert sum(row['rows'] for row in T.JOURNAL_TABLES.values())==10001
    assert all(row['url'].startswith('https://content.cld.iop.org/journals/0067-0049/279/2/50/revision1/') for row in T.JOURNAL_TABLES.values())
