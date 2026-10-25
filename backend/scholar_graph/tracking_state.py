"""Durable operational journals, separate from the frozen business contracts."""

import json
import os
import sqlite3
import time
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .errors import PipelineError


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def operation_lock(root, name, *, timeout=0):
    """Kernel-owned locks work across HTTP workers/CLI and release after a crash."""
    parent = Path(root) / "tracking"
    parent.mkdir(parents=True, exist_ok=True)
    with (parent / (name + ".lock")).open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise PipelineError("VALIDATION_ERROR", "同一数据目录的操作正在执行，请稍后重试。") from None
                time.sleep(.05)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


class TrackingState:
    def __init__(self, root):
        self.path = Path(root) / "tracking" / "state.sqlite3"

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=30)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, started TEXT NOT NULL, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS duplicates (identity TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS votes (profile TEXT, paper TEXT, vote INTEGER NOT NULL, updated TEXT NOT NULL, PRIMARY KEY(profile,paper))")
            db.execute("CREATE TABLE IF NOT EXISTS feedback_events (id INTEGER PRIMARY KEY, profile TEXT NOT NULL, payload TEXT NOT NULL)")
            yield db

    def run(self, value):
        with self.connect() as db:
            db.execute("INSERT INTO runs VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                       (value["run_id"], value["started_at"], json.dumps(value, ensure_ascii=False, allow_nan=False)))

    def latest(self):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM runs ORDER BY started DESC,id DESC LIMIT 1").fetchone()
        return json.loads(row[0]) if row else None

    def duplicate(self, identity, paper_id, reason, *, score=None):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM duplicates WHERE identity=?", (identity,)).fetchone()
            record = json.loads(row[0]) if row else {"identity": identity, "paper_id": paper_id,
                "reason": reason, "similarity": score, "first_seen": utc_now(), "occurrences": 0}
            record.update(occurrences=record["occurrences"] + 1, last_seen=utc_now())
            db.execute("INSERT INTO duplicates VALUES (?,?) ON CONFLICT(identity) DO UPDATE SET payload=excluded.payload",
                       (identity, json.dumps(record, ensure_ascii=False, allow_nan=False)))
        return {**record, "record_created": row is None}

    def duplicates(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT payload FROM duplicates ORDER BY identity")]

    def votes(self, profile):
        with self.connect() as db:
            return [{"paper_id": row[0], "vote": row[1], "updated_at": row[2]}
                    for row in db.execute("SELECT paper,vote,updated FROM votes WHERE profile=? ORDER BY paper", (profile,))]

    def feedback(self, profile, paper_id, vote, event):
        with self.connect() as db:
            db.execute("INSERT INTO votes VALUES (?,?,?,?) ON CONFLICT(profile,paper) DO UPDATE SET vote=excluded.vote,updated=excluded.updated",
                       (profile, paper_id, vote, utc_now()))
            cursor = db.execute("INSERT INTO feedback_events(profile,payload) VALUES (?,?)",
                                (profile, json.dumps(event, ensure_ascii=False, allow_nan=False)))
            return cursor.lastrowid

    def events(self, profile):
        with self.connect() as db:
            return [{"event_id": row[0], **json.loads(row[1])} for row in db.execute(
                "SELECT id,payload FROM feedback_events WHERE profile=? ORDER BY id", (profile,))]
