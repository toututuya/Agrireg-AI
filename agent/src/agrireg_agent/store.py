from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TERMINAL_STATUSES = {"completed", "failed", "rejected"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._setup()
        self._recover_active_runs()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _setup(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_threads (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    status TEXT NOT NULL,
                    require_approval INTEGER NOT NULL DEFAULT 0,
                    interrupt_json TEXT,
                    report TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(thread_id) REFERENCES agent_threads(id)
                );
                CREATE TABLE IF NOT EXISTS agent_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES agent_runs(id)
                );
                CREATE INDEX IF NOT EXISTS idx_agent_runs_thread ON agent_runs(thread_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_agent_events_run ON agent_events(run_id, seq);
                """
            )

    def _recover_active_runs(self) -> None:
        now = utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE agent_runs SET status = 'paused', updated_at = ? WHERE status = 'running'",
                (now,),
            )

    def create_thread(self, title: str) -> dict[str, Any]:
        thread_id, now = str(uuid.uuid4()), utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO agent_threads(id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (thread_id, title.strip(), now, now),
            )
        return self.get_thread(thread_id)

    def get_thread(self, thread_id: str) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_threads WHERE id = ?", (thread_id,)
            ).fetchone()
            if row is None:
                raise KeyError("thread_not_found")
            result = dict(row)
            result["runs"] = [
                self._run_from_row(item)
                for item in connection.execute(
                    "SELECT * FROM agent_runs WHERE thread_id = ? ORDER BY created_at DESC LIMIT 30",
                    (thread_id,),
                ).fetchall()
            ]
            return result

    def list_threads(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT t.*, r.id AS latest_run_id, r.status AS latest_status, r.question AS latest_question
                FROM agent_threads t
                LEFT JOIN agent_runs r ON r.id = (
                    SELECT id FROM agent_runs WHERE thread_id = t.id ORDER BY created_at DESC LIMIT 1
                )
                ORDER BY t.updated_at DESC LIMIT 50
                """
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["createdAt"] = item.pop("created_at")
                item["updatedAt"] = item.pop("updated_at")
                item["latestRunId"] = item.pop("latest_run_id")
                item["latestStatus"] = item.pop("latest_status")
                item["latestQuestion"] = item.pop("latest_question")
                result.append(item)
            return result

    def create_run(self, thread_id: str, question: str, require_approval: bool) -> dict[str, Any]:
        self.get_thread(thread_id)
        run_id, now = str(uuid.uuid4()), utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_runs(
                    id, thread_id, question, status, require_approval, created_at, updated_at
                ) VALUES (?, ?, ?, 'running', ?, ?, ?)
                """,
                (run_id, thread_id, question.strip(), int(require_approval), now, now),
            )
            connection.execute(
                "UPDATE agent_threads SET title = CASE WHEN title = '新分析任务' THEN ? ELSE title END, updated_at = ? WHERE id = ?",
                (question.strip()[:36], now, thread_id),
            )
        self.append_event(run_id, "run_started", "开始分析任务", question.strip(), {})
        return self.get_run(run_id)

    def get_run(self, run_id: str, thread_id: str | None = None) -> dict[str, Any]:
        query = "SELECT * FROM agent_runs WHERE id = ?"
        params: tuple[Any, ...] = (run_id,)
        if thread_id:
            query += " AND thread_id = ?"
            params = (run_id, thread_id)
        with self._lock, self._connect() as connection:
            row = connection.execute(query, params).fetchone()
            if row is None:
                raise KeyError("run_not_found")
            result = self._run_from_row(row)
            result["events"] = [
                self._event_from_row(item)
                for item in connection.execute(
                    "SELECT * FROM agent_events WHERE run_id = ? ORDER BY seq", (run_id,)
                ).fetchall()
            ]
            return result

    def update_run(self, run_id: str, status: str, **fields: Any) -> None:
        allowed = {"interrupt_json", "report", "error"}
        updates = {key: value for key, value in fields.items() if key in allowed}
        updates["status"] = status
        updates["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values()) + [run_id]
        with self._lock, self._connect() as connection:
            connection.execute(f"UPDATE agent_runs SET {assignments} WHERE id = ?", values)

    def append_event(
        self,
        run_id: str,
        kind: str,
        title: str,
        detail: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        now = utc_now()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO agent_events(run_id, kind, title, detail, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, kind, title, detail, json.dumps(payload or {}, ensure_ascii=False), now),
            )
            seq = int(cursor.lastrowid)
        return {"seq": seq, "runId": run_id, "kind": kind, "title": title, "detail": detail, "payload": payload or {}, "createdAt": now}

    def events_after(self, run_id: str, after: int) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_events WHERE run_id = ? AND seq > ? ORDER BY seq LIMIT 100",
                (run_id, after),
            ).fetchall()
            return [self._event_from_row(row) for row in rows]

    @staticmethod
    def _run_from_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["requireApproval"] = bool(result.pop("require_approval"))
        result["threadId"] = result.pop("thread_id")
        result["createdAt"] = result.pop("created_at")
        result["updatedAt"] = result.pop("updated_at")
        raw_interrupt = result.pop("interrupt_json")
        result["interrupt"] = json.loads(raw_interrupt) if raw_interrupt else None
        return result

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["runId"] = result.pop("run_id")
        result["createdAt"] = result.pop("created_at")
        result["payload"] = json.loads(result.pop("payload_json"))
        return result
