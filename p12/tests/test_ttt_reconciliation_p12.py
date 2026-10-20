"""Synthetic acquisition and selection-boundary regressions; no truth reads."""
import io
import tarfile
import pandas as pd
import pytest
import fetch_ttt_p12 as T
from p12_common import write, sha


def test_manuscript_sample_is_not_a_machine_readable_catalogue():
    stream = io.BytesIO()
    body = b'\\begin{table}\\caption{Table available in full as a machine-readable supplement.}\\begin{tabular}{rr} TIC & Period \\\\ 1 & 2 \\end{tabular}\\end{table}'
    with tarfile.open(fileobj=stream, mode='w') as archive:
        member = tarfile.TarInfo('main.tex'); member.size = len(body)
        archive.addfile(member, io.BytesIO(body))
    candidates, inventory = T._eprint_candidates(stream.getvalue())
    assert len(candidates) == 1
    assert candidates[0][1].attrs['incomplete_catalogue']
    with pytest.raises(ValueError, match='abbreviated'):
        T._choose_table(candidates)
    assert inventory == [dict(suffix='.tex', bytes=len(body))]


def test_unselected_missing_period_does_not_remove_a_catalogue_tic():
    frame = pd.DataFrame({'TIC': [1, 2, 3], 'Period': [2., None, -1.]})
    _, table = T._choose_table([('fixture', frame)], require_all=False)
    assert table.tic_id.tolist() == [1, 2, 3]
    assert table.attrs['ephemeris_validation']['missing_or_invalid_periods'] == 2
    selected = T._ephemeris_table(table[table.tic_id == 1])
    assert len(selected) == 1
    with pytest.raises(ValueError, match='missing or invalid'):
        T._ephemeris_table(table[table.tic_id == 2])


def test_original_strict_table_validation_is_preserved():
    with pytest.raises(ValueError, match='missing or invalid'):
        T._ephemeris_table(pd.DataFrame({'TIC': [1, 2], 'Period': [1., None]}))


def test_resume_requires_immutable_failed_attempts_and_download(tmp_path, monkeypatch):
    root=tmp_path/'p12'; data=tmp_path/'data/survey/p12'
    monkeypatch.setattr(T,'REPO',tmp_path); monkeypatch.setattr(T,'ROOT',root); monkeypatch.setattr(T,'DATA',data)
    downloaded=data/'negatives/ttt_downloads/source.tar'
    downloaded.parent.mkdir(parents=True); downloaded.write_bytes(b'fixture')
    attempts=[dict(kind='vizier',status='TIMEOUT',all_owned_workers_closed=True),
        dict(kind='eprint',status='OPERATIONAL_UNKNOWN',all_owned_workers_closed=True,
             download_path=downloaded.relative_to(tmp_path).as_posix(),sha256=sha(downloaded))]
    receipt=root/'manifests/attempt1.json'; write(receipt,dict(status='FETCHING',attempts=attempts))
    digest=sha(receipt)
    assert T._resume_attempts(receipt.relative_to(tmp_path),digest)==attempts
    downloaded.write_bytes(b'changed')
    with pytest.raises(RuntimeError,match='download identity'):
        T._resume_attempts(receipt.relative_to(tmp_path),digest)
