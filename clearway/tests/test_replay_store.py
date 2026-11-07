import json
import sqlite3
from uuid import uuid4

import pytest

from api.store import StateError, Store


def test_legacy_jobs_migrate_without_guessing_their_analysis(tmp_path):
    run_id = str(uuid4())
    global_analysis = {"mode": "cached", "status": "complete", "message": "Another source's old result"}
    with sqlite3.connect(tmp_path / "clearway.sqlite3") as db:
        db.executescript("""
            CREATE TABLE jobs(run_id TEXT, source_id TEXT, mode TEXT, token TEXT, status TEXT,
                              PRIMARY KEY(run_id, source_id));
            CREATE TABLE runs(id TEXT PRIMARY KEY, created_at TEXT, status TEXT, analysis TEXT);
            CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT);
        """)
        db.execute("INSERT INTO runs VALUES(?,?,?,?)", (run_id, "test-time", "ready", json.dumps(global_analysis)))
        db.execute("INSERT INTO settings VALUES('current_run',?)", (run_id,))
        db.execute("INSERT INTO jobs VALUES(?,?,?,?,?)", (run_id, "road-obstruction", "cached", "old-token", "done"))
    for _ in range(2):
        store = Store(tmp_path)
        assert store.reserve_replay(run_id, "road-obstruction", "cached") is None
        snapshot = store.snapshot(expected_run_id=run_id, analysis_source_id="road-obstruction")
        assert snapshot["run"]["id"] == run_id
        assert snapshot["analysis"]["status"] == "unavailable"
        assert "older replay" in snapshot["analysis"]["message"]
        assert snapshot["source_analyses"]["road-obstruction"] == snapshot["analysis"]
        assert store.snapshot()["analysis"] == global_analysis


def test_scoped_replay_snapshot_rejects_reset_before_response(tmp_path):
    store = Store(tmp_path)
    run_id = store.snapshot()["run"]["id"]
    store.reserve_replay(run_id, "road-obstruction", "fixture")
    store.reset()
    with pytest.raises(StateError) as error:
        store.snapshot(expected_run_id=run_id, analysis_source_id="road-obstruction")
    assert error.value.status == 409
    assert store.snapshot()["source_analyses"] == {}
