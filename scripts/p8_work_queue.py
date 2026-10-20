"""Atomic work claims for P8's top-level subprocesses; scientific files remain the checkpoints."""
from pathlib import Path
import sqlite3


def create_queue(path, keys):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to replace a live work queue: {path}")
    with sqlite3.connect(path, timeout=30) as connection:
        connection.execute("CREATE TABLE work (sequence INTEGER PRIMARY KEY, job_key TEXT UNIQUE NOT NULL, claimed INTEGER NOT NULL DEFAULT 0)")
        connection.executemany("INSERT INTO work (job_key) VALUES (?)", [(str(key),) for key in keys])


def claims(path, limit: int | None = None):
    """Yield each pending key to exactly one worker. A resume starts a fresh queue and reads caches."""
    if limit is not None and limit < 0:
        raise ValueError("The claim limit cannot be negative")
    connection = sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=rw", uri=True, timeout=30)
    try:
        claimed = 0
        while limit is None or claimed < limit:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute("SELECT sequence, job_key FROM work WHERE claimed=0 ORDER BY sequence LIMIT 1").fetchone()
                if row is None:
                    return
                connection.execute("UPDATE work SET claimed=1 WHERE sequence=?", (row[0],))
            claimed += 1
            yield row[1]
    finally:
        connection.close()
