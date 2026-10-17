"""SQLite job/event ledger. One writer transaction per state transition."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class QueueFull(Exception):
    pass


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, run_id TEXT NOT NULL,
                status TEXT NOT NULL, period TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                payload TEXT NOT NULL, result TEXT, error TEXT,
                cancel_requested INTEGER NOT NULL DEFAULT 0
              );
              CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                event TEXT NOT NULL, job_id TEXT
              );
              CREATE INDEX IF NOT EXISTS job_queue ON jobs(status, created_at);
              CREATE INDEX IF NOT EXISTS run_events ON events(run_id, seq);
            """)
            # Additive migration: historical event rows remain intact. New jobs
            # bind every imported child event to the actual durable queue job.
            if "job_id" not in {row["name"] for row in db.execute("PRAGMA table_info(events)")}:
                db.execute("ALTER TABLE events ADD COLUMN job_id TEXT")
            db.execute("CREATE INDEX IF NOT EXISTS job_events ON events(job_id,seq)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _decode(row):
        if row is None:
            return None
        item = dict(row)
        for key in ("payload", "result", "error"):
            item[key] = json.loads(item[key]) if item[key] is not None else None
        return item

    @staticmethod
    def _event(db, run_id, task_id, type_, status, summary, actor="api", evidence_refs=None, parent_task_id=None, job_id=None):
        event = dict(id=str(uuid4()), run_id=run_id, task_id=task_id,
                     timestamp=utc_now(), actor=actor, type=type_, status=status,
                     summary=summary, evidence_refs=evidence_refs or [])
        if parent_task_id:
            event["parent_task_id"] = parent_task_id
        db.execute("INSERT INTO events(run_id,event,job_id) VALUES (?,?,?)", (run_id, json.dumps(event), job_id or task_id))

    def enqueue(self, kind, period, payload, run_id=None, max_pending=20):
        job_id = run_id if kind == "close" and run_id else str(uuid4())
        run_id = run_id or job_id
        stamp = utc_now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
            if count >= max_pending:
                raise QueueFull()
            db.execute("INSERT INTO jobs(id,kind,run_id,status,period,created_at,updated_at,payload) VALUES (?,?,?,'queued',?,?,?,?)",
                       (job_id, kind, run_id, period, stamp, stamp, json.dumps(payload)))
            label = {"close": "Fechamento enfileirado", "investigation": "Investigação enfileirada", "comparison": "Comparação enfileirada", "case_review": "Revisão de caso enfileirada"}[kind]
            self._event(db, run_id, job_id, "task.created", "queued", label)
        return self.get(job_id)

    def get(self, job_id):
        with self.connect() as db:
            return self._decode(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def list_runs(self, limit=100):
        with self.connect() as db:
            return [self._decode(r) for r in db.execute("SELECT * FROM jobs WHERE kind='close' ORDER BY created_at DESC LIMIT ?", (limit,))]

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at,id LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET status='running',updated_at=? WHERE id=?", (utc_now(), row["id"]))
            self._event(db, row["run_id"], row["id"], "task.started", "running", "Execução iniciada", "worker")
            result = self._decode(row)
            result["status"] = "running"
            return result

    def finish(self, job_id, status, result=None, error=None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None or row["status"] != "running":
                return
            db.execute("UPDATE jobs SET status=?,updated_at=?,result=?,error=? WHERE id=?",
                       (status, utc_now(), json.dumps(result) if result is not None else None,
                        json.dumps(error) if error else None, job_id))
            event_type = "task.failed" if status in ("failed", "cancelled", "timed_out", "interrupted") else "review.required" if status in ("blocked", "unavailable") else "task.completed"
            event_status = "failed" if event_type == "task.failed" else "blocked" if event_type == "review.required" else "completed"
            self._event(db, row["run_id"], job_id, event_type, event_status,
                        "Execução encerrada: " + status, "worker")
            if status == "pending_review":
                self._event(db, row["run_id"], job_id, "review.required", "blocked", "Preparação concluída; revisão financeira pendente", "worker")

    def cancel(self, job_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                return None
            if row["status"] == "queued":
                db.execute("UPDATE jobs SET status='cancelled',cancel_requested=1,updated_at=? WHERE id=?", (utc_now(), job_id))
                self._event(db, row["run_id"], job_id, "task.failed", "failed", "Cancelado antes da execução")
            elif row["status"] == "running":
                db.execute("UPDATE jobs SET cancel_requested=1,updated_at=? WHERE id=?", (utc_now(), job_id))
        return self.get(job_id)

    def recover_interrupted(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT id,run_id FROM jobs WHERE status='running'").fetchall()
            for row in rows:
                error = {"code": "WORKER_INTERRUPTED", "message": "Servidor reiniciado durante a execução; inicie nova tentativa."}
                db.execute("UPDATE jobs SET status='interrupted',updated_at=?,error=? WHERE id=?", (utc_now(), json.dumps(error), row["id"]))
                self._event(db, row["run_id"], row["id"], "task.failed", "failed", "Execução interrompida por reinício", "worker")
        return len(rows)

    def append_events(self, job, events):
        allowed = {"task.created", "task.started", "tool.called", "evidence.found", "handoff.requested", "task.completed", "task.failed", "decision.proposed", "review.required"}
        observed_tasks = {str(event.get("task_id"))[:160] for event in events if isinstance(event, dict) and event.get("task_id")}
        with self.connect() as db:
            for event in events:
                if not isinstance(event, dict) or event.get("type") not in allowed:
                    continue
                status = event.get("status", "completed")
                if status not in {"queued", "running", "completed", "failed", "blocked"}:
                    status = "completed"
                task_id = str(event.get("task_id") or job["id"])[:160]
                parent = str(event.get("parent_task_id") or "")[:160]
                if parent == task_id or parent not in observed_tasks | {job["id"]}:
                    parent = job["id"] if task_id != job["id"] else None
                self._event(db, job["run_id"], task_id, event["type"], status,
                            str(event.get("summary", ""))[:2000], str(event.get("actor", "investigator"))[:100], event.get("evidence_refs", []),
                            parent_task_id=parent, job_id=job["id"])

    def events(self, run_id, after=0, limit=100):
        with self.connect() as db:
            rows = db.execute("SELECT seq,event FROM events WHERE run_id=? AND seq>? ORDER BY seq LIMIT ?", (run_id, after, limit)).fetchall()
        items = [{**json.loads(r["event"]), "cursor": r["seq"]} for r in rows]
        return {"items": items, "next_cursor": rows[-1]["seq"] if rows else None}

    def job_events(self, job_id, after=0, limit=100):
        with self.connect() as db:
            rows = db.execute("SELECT seq,event FROM events WHERE job_id=? AND seq>? ORDER BY seq LIMIT ?", (job_id, after, limit)).fetchall()
        return {"events": [{**json.loads(row["event"]), "cursor": row["seq"]} for row in rows],
                "next_cursor": rows[-1]["seq"] if rows else None}
