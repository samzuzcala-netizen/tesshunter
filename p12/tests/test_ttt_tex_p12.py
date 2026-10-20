"""Synthetic TeX source fixtures; test output stays verdicts and counts only."""
import pytest
import fetch_ttt_p12 as T


def test_regular_tabular_identifiers_period_and_duplicate_headings():
    body=br'''\begin{sidewaystable}
\caption{Complete catalogue fixture}
\begin{tabular}{rrrr}
\hline TIC ID & Period & Depth & Depth \\
1 & $2.5$ & 0.1 & 0.2 \\
2 & 3.5 & 0.2 & 0.3 \\
\end{tabular}\end{sidewaystable}'''
    frames=list(T._tex_table_candidates(body))
    name,table=T._choose_table([('fixture.tex',frames[0])])
    assert table.tic_id.tolist()==[1,2]
    assert table.period_days.tolist()==[2.5,3.5]
    assert list(table.columns)==['tic_id','period','depth','depth_2','period_days']


def test_deluxetable_balanced_headers_units_and_notes():
    body=br'''\begin{deluxetable*}{rr}
\tablehead{\colhead{TIC ID} & \colhead{Period}}
\startdata
TIC 10 & $4.5$\tablenotemark{a} \\
20 & 5.5 \nl
\enddata
\end{deluxetable*}'''
    frame=list(T._tex_table_candidates(body))[0]
    assert T._ephemeris_table(frame).tic_id.tolist()==[10,20]
    assert not frame.attrs['incomplete_catalogue']


def test_abbreviated_table_rejected_before_selection():
    body=br'''\begin{table}\caption{Table available in full as machine-readable online supplement.}
\begin{tabular}{rr} TIC & Period \\ 1 & 2 \\ \end{tabular}\end{table}'''
    frames=list(T._tex_table_candidates(body))
    assert len(frames)==1 and len(frames[0])==1
    with pytest.raises(ValueError,match='abbreviated'):
        T._choose_table([('fixture.tex',frames[0])])


def test_complete_candidate_can_follow_abbreviated_candidate():
    sample=br'''\begin{table}\caption{First 2 rows shown.}\begin{tabular}{rr} TIC & Period \\ 1 & 2 \\ \end{tabular}\end{table}'''
    complete=br'''\begin{deluxetable}{rr}\tablehead{TIC & Period}\startdata 3 & 4 \\ \enddata\end{deluxetable}'''
    candidates=[('sample',f) for f in T._tex_table_candidates(sample)]+[('complete',f) for f in T._tex_table_candidates(complete)]
    name,table=T._choose_table(candidates)
    assert name=='complete' and table.tic_id.tolist()==[3]


def test_invalid_embedded_period_remains_a_parse_failure():
    body=br'''\begin{tabular}{rr} TIC & Period \\ 1 & \nodata \\ \end{tabular}'''
    frames=list(T._tex_table_candidates(body))
    with pytest.raises(ValueError,match='invalid orbital periods'):
        T._choose_table([('fixture',frames[0])])
