"""SQLite state shared by the separate local and responder processes.

Every state transition rechecks the current run under an IMMEDIATE transaction.
Analysis runs outside that transaction so reset never waits for a provider.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail


class Store:
    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.path = data_dir / "clearway.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                    status TEXT NOT NULL, analysis TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, source_id TEXT NOT NULL,
                    payload TEXT NOT NULL, UNIQUE(run_id, source_id)
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    run_id TEXT NOT NULL, source_id TEXT NOT NULL, mode TEXT NOT NULL,
                    token TEXT NOT NULL, status TEXT NOT NULL,
                    PRIMARY KEY(run_id, source_id)
                );
                CREATE TABLE IF NOT EXISTS labels (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL
                );
            """)
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM settings WHERE key='current_run'").fetchone() is None:
                self._new_run(db)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def _current_id(self, db) -> str:
        return db.execute("SELECT value FROM settings WHERE key='current_run'").fetchone()[0]

    def _require_current(self, db, run_id: str, *, public=False):
        if self._current_id(db) != run_id:
            known = db.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone()
            if public and not known:
                raise StateError(404, "Run not found.")
            raise StateError(410 if public else 409, "This run expired after reset. Start a new replay.")

    def _new_run(self, db):
        run_id = str(uuid4())
        analysis = {"mode": "fixture", "status": "idle", "message": "Ready for an explicitly labeled fixture replay."}
        db.execute("INSERT INTO runs VALUES(?,?,?,?)", (run_id, now(), "idle", json.dumps(analysis)))
        db.execute("INSERT OR REPLACE INTO settings VALUES('current_run',?)", (run_id,))
        return run_id

    def reset(self):
        with self.transaction() as db:
            old = self._current_id(db)
            db.execute("UPDATE runs SET status='expired' WHERE id=?", (old,))
            db.execute("UPDATE jobs SET status='cancelled' WHERE run_id=? AND status='running'", (old,))
            self._new_run(db)

    def snapshot(self) -> dict:
        with self.connect() as db:
            # A read transaction guarantees the run and incident list share a snapshot.
            db.execute("BEGIN")
            run_id = self._current_id(db)
            run = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            incidents = [json.loads(r[0]) for r in db.execute("SELECT payload FROM incidents WHERE run_id=? ORDER BY rowid", (run_id,))]
            return {
                "run": {"id": run["id"], "created_at": run["created_at"], "status": run["status"]},
                "incidents": incidents,
                "analysis": json.loads(run["analysis"]),
            }

    def reserve_replay(self, run_id: str, source_id: str, mode: str) -> str | None:
        with self.transaction() as db:
            self._require_current(db, run_id)
            job = db.execute("SELECT * FROM jobs WHERE run_id=? AND source_id=?", (run_id, source_id)).fetchone()
            if job:
                if job["mode"] != mode:
                    raise StateError(409, "Reset the run before changing its analysis mode.")
                return None
            token = str(uuid4())
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?)", (run_id, source_id, mode, token, "running"))
            analysis = {"mode": mode, "status": "running", "message": "Preparing the selected replay analysis."}
            db.execute("UPDATE runs SET status='replaying', analysis=? WHERE id=?", (json.dumps(analysis), run_id))
            return token

    def finish_replay(self, run_id: str, source_id: str, token: str, result: dict, source: dict):
        with self.transaction() as db:
            self._require_current(db, run_id)
            job = db.execute("SELECT * FROM jobs WHERE run_id=? AND source_id=?", (run_id, source_id)).fetchone()
            if not job or job["token"] != token or job["status"] != "running":
                raise StateError(409, "The analysis request is no longer active.")
            if result["candidate"]:
                incident_id = str(uuid4())
                payload = {
                    "id": incident_id, "run_id": run_id, "source_id": source_id,
                    "title": result["title"], "category": result["category"],
                    "source_mode": source["source_mode"], "analysis_mode": result["mode"],
                    "review_status": "candidate", "created_at": now(), "confirmed_at": None,
                    "evidence": result["observations"], "unknowns": result["unknowns"],
                    "context_status": "not_applicable", "location": source["location"],
                    "provenance": result["provenance"],
                    "responder_path": f"/respond/{run_id}/{incident_id}",
                }
                db.execute("INSERT INTO incidents VALUES(?,?,?,?)", (incident_id, run_id, source_id, json.dumps(payload)))
            analysis = {k: result[k] for k in ("mode", "status", "message")}
            db.execute("UPDATE jobs SET status='done' WHERE run_id=? AND source_id=?", (run_id, source_id))
            db.execute("UPDATE runs SET status=?, analysis=? WHERE id=?", ("ready" if result["status"] == "complete" else "unavailable", json.dumps(analysis), run_id))

    def review(self, run_id: str, incident_id: str, action: str) -> dict:
        with self.transaction() as db:
            self._require_current(db, run_id)
            row = db.execute("SELECT payload FROM incidents WHERE id=? AND run_id=?", (incident_id, run_id)).fetchone()
            if not row:
                raise StateError(404, "Incident not found in this run.")
            incident = json.loads(row[0])
            target = "confirmed" if action == "confirm" else "dismissed"
            if incident["review_status"] == target:
                return incident
            if incident["review_status"] != "candidate":
                raise StateError(409, "This incident has already been reviewed. Reset to begin again.")
            incident["review_status"] = target
            if target == "confirmed":
                incident["confirmed_at"] = now()
            db.execute("UPDATE incidents SET payload=? WHERE id=?", (json.dumps(incident), incident_id))
            return incident

    def responder(self, run_id: str, incident_id: str) -> dict:
        with self.connect() as db:
            db.execute("BEGIN")
            self._require_current(db, run_id, public=True)
            row = db.execute("SELECT payload FROM incidents WHERE id=? AND run_id=?", (incident_id, run_id)).fetchone()
            if not row:
                raise StateError(404, "Incident not found in this run.")
            return json.loads(row[0])

    def add_label(self, payload: dict) -> dict:
        label = {**payload, "id": str(uuid4()), "created_at": now()}
        with self.transaction() as db:
            db.execute("INSERT INTO labels VALUES(?,?)", (label["id"], json.dumps(label)))
        return label

    def labels(self) -> list[dict]:
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT payload FROM labels ORDER BY rowid")]
