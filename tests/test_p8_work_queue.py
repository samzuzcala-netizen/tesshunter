from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from p8_work_queue import claims, create_queue


def test_concurrent_workers_claim_every_job_once(tmp_path):
    path = tmp_path / "shared queue.sqlite"
    expected = [f"job_{i:03d}" for i in range(100)]
    create_queue(path, expected)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: list(claims(path)), range(8)))
    actual = [key for batch in results for key in batch]
    assert sorted(actual) == expected
    assert list(claims(path)) == []


def test_a_live_queue_cannot_be_replaced(tmp_path):
    path = tmp_path / "queue.sqlite"
    create_queue(path, ["one", "two"])
    with pytest.raises(FileExistsError):
        create_queue(path, ["replacement"])
    assert list(claims(path)) == ["one", "two"]


def test_a_worker_does_not_create_a_missing_queue(tmp_path):
    path = tmp_path / "missing.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        list(claims(path))
    assert not path.exists()


@pytest.mark.parametrize("limit", [0, 1, 3])
def test_bounded_worker_leaves_every_unclaimed_job_available(tmp_path, limit):
    path = tmp_path / "bounded.sqlite"
    expected = ["one", "two", "three", "four"]
    create_queue(path, expected)
    assert list(claims(path, limit=limit)) == expected[:limit]
    assert list(claims(path)) == expected[limit:]


def test_bounded_workers_share_queue_with_unbounded_workers(tmp_path):
    path = tmp_path / "mixed.sqlite"
    expected = [f"job_{i:03d}" for i in range(100)]
    create_queue(path, expected)
    with ThreadPoolExecutor(max_workers=6) as pool:
        batches = list(pool.map(lambda limit: list(claims(path, limit=limit)), [7, 7, 7, 7, None, None]))
    assert all(len(batch) <= 7 for batch in batches[:4])
    assert sorted(key for batch in batches for key in batch) == expected
