"""SQLite memory for proposals and approvals. The JSON files stay read-only."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def now_iso() -> str:
    return datetime.now(ROME).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS actions (
              id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              event_id TEXT NOT NULL,
              status TEXT NOT NULL,
              signal TEXT NOT NULL,
              score REAL NOT NULL,
              trace_json TEXT NOT NULL,
              notice_json TEXT,
              created_at TEXT NOT NULL,
              decided_at TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS actions_pair
              ON actions(user_id, event_id);
            CREATE TABLE IF NOT EXISTS desk_profile (
              id TEXT PRIMARY KEY,
              nome TEXT NOT NULL,
              cognome TEXT NOT NULL,
              email TEXT NOT NULL,
              canvas_id TEXT NOT NULL DEFAULT '',
              pronote_id TEXT NOT NULL DEFAULT '',
              likes_json TEXT NOT NULL,
              dislikes_json TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS proposals (
              approval_id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              event_id TEXT NOT NULL,
              event_title TEXT NOT NULL,
              source_id TEXT NOT NULL,
              warning TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS registrations (
              registration_id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              event_id TEXT NOT NULL,
              approval_id TEXT NOT NULL,
              idempotency_key TEXT NOT NULL UNIQUE,
              status TEXT NOT NULL,
              mode TEXT NOT NULL,
              event_title TEXT NOT NULL,
              source_id TEXT NOT NULL,
              starts_at TEXT,
              location TEXT,
              created_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS registrations_pair
              ON registrations(user_id, event_id);
            CREATE TABLE IF NOT EXISTS library_extra (
              id TEXT PRIMARY KEY,
              source_id TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS feedback (
              id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              author_name TEXT NOT NULL,
              rating INTEGER NOT NULL,
              body TEXT NOT NULL,
              subject TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def get_pair(self, user_id: str, event_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM actions WHERE user_id = ? AND event_id = ?",
                (user_id, event_id),
            ).fetchone()
        return _action(row) if row else None

    def get(self, action_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
        return _action(row) if row else None

    def list_actions(self, user_id: str | None = None, status: str | None = None) -> list[dict]:
        clauses: list[str] = []
        params: list[str] = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM actions {where} ORDER BY created_at DESC, id DESC",
                params,
            ).fetchall()
        return [_action(row) for row in rows]

    def insert_action(
        self,
        user_id: str,
        event_id: str,
        signal: str,
        score: float,
        trace: dict,
    ) -> dict:
        action_id = new_id("act")
        created = now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO actions (
                  id, user_id, event_id, status, signal, score, trace_json, notice_json, created_at, decided_at
                ) VALUES (?, ?, ?, 'pending', ?, ?, ?, NULL, ?, NULL)
                """,
                (action_id, user_id, event_id, signal, score, json.dumps(trace, ensure_ascii=False), created),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
        return _action(row)

    def decide(self, action_id: str, status: str, notice: dict | None) -> dict:
        decided = now_iso()
        notice_json = json.dumps(notice, ensure_ascii=False) if notice else None
        with self._lock:
            current = self._conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
            if current is None:
                raise KeyError(action_id)
            trace = json.loads(current["trace_json"])
            trace.setdefault("action", {})["status"] = status
            self._conn.execute(
                """
                UPDATE actions
                   SET status = ?, trace_json = ?, notice_json = ?, decided_at = ?
                 WHERE id = ?
                """,
                (status, json.dumps(trace, ensure_ascii=False), notice_json, decided, action_id),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
        return _action(row)

    def counts(self) -> dict:
        with self._lock:
            pending = self._conn.execute(
                "SELECT COUNT(*) AS n FROM actions WHERE status = 'pending'"
            ).fetchone()["n"]
            notices = self._conn.execute(
                "SELECT COUNT(*) AS n FROM actions WHERE status = 'approved'"
            ).fetchone()["n"]
        return {"pending_actions": pending, "notices": notices}

    def save_desk_profile(self, profile: dict) -> dict:
        """Local desk identity. The password is not a column and is not written."""
        updated = now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO desk_profile (
                  id, nome, cognome, email, canvas_id, pronote_id, likes_json, dislikes_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  nome = excluded.nome,
                  cognome = excluded.cognome,
                  email = excluded.email,
                  canvas_id = excluded.canvas_id,
                  pronote_id = excluded.pronote_id,
                  likes_json = excluded.likes_json,
                  dislikes_json = excluded.dislikes_json,
                  updated_at = excluded.updated_at
                """,
                (
                    profile["id"],
                    profile["nome"],
                    profile["cognome"],
                    profile["email"],
                    profile.get("canvas_id") or "",
                    profile.get("pronote_id") or "",
                    json.dumps(profile["likes"], ensure_ascii=False),
                    json.dumps(profile.get("dislikes") or [], ensure_ascii=False),
                    updated,
                ),
            )
            self._conn.commit()
        return self.get_desk_profile()

    def get_desk_profile(self) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM desk_profile WHERE id = 'usr-desk'").fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "nome": row["nome"],
            "cognome": row["cognome"],
            "email": row["email"],
            "canvas_id": row["canvas_id"],
            "pronote_id": row["pronote_id"],
            "likes": json.loads(row["likes_json"]),
            "dislikes": json.loads(row["dislikes_json"]),
            "updated_at": row["updated_at"],
        }

    def reset(self) -> int:
        with self._lock:
            count = self._conn.execute("SELECT COUNT(*) AS n FROM actions").fetchone()["n"]
            self._conn.execute("DELETE FROM actions")
            self._conn.execute("DELETE FROM proposals")
            self._conn.execute("DELETE FROM registrations")
            self._conn.commit()
        return int(count)

    def proposal_count(self, user_id: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM proposals WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return int(row["n"])

    def get_pending(self, user_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM proposals
                 WHERE user_id = ? AND status = 'pending'
                 ORDER BY created_at DESC LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def save_pending(self, pending: dict) -> dict:
        created = now_iso()
        with self._lock:
            self._conn.execute(
                "UPDATE proposals SET status = 'superseded' WHERE user_id = ? AND status = 'pending'",
                (pending["student_id"],),
            )
            self._conn.execute(
                """
                INSERT INTO proposals (
                  approval_id, user_id, event_id, event_title, source_id, warning, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    pending["approval_id"],
                    pending["student_id"],
                    pending["event_id"],
                    pending["event_title"],
                    pending["source_id"],
                    pending["warning"],
                    created,
                ),
            )
            self._conn.commit()
        return self.get_pending(pending["student_id"])

    def set_proposal_status(self, approval_id: str, status: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE proposals SET status = ? WHERE approval_id = ?",
                (status, approval_id),
            )
            self._conn.commit()

    def list_registrations(self, user_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM registrations WHERE user_id = ? ORDER BY created_at, registration_id",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_registration_by_key(self, idempotency_key: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM registrations WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        return dict(row) if row else None

    def insert_registration(self, record: dict) -> dict:
        created = record.get("created_at") or now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO registrations (
                  registration_id, user_id, event_id, approval_id, idempotency_key,
                  status, mode, event_title, source_id, starts_at, location, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["registration_id"],
                    record["student_id"],
                    record["event_id"],
                    record["approval_id"],
                    record["idempotency_key"],
                    record["status"],
                    record["mode"],
                    record.get("event_title") or "",
                    record.get("source_id") or record["event_id"],
                    record.get("start") or record.get("starts_at"),
                    record.get("location"),
                    created,
                ),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM registrations WHERE registration_id = ?",
                (record["registration_id"],),
            ).fetchone()
        return dict(row)

    def decorate_registration(self, registration_id: str, title: str, source_id: str, starts_at: str, location: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                UPDATE registrations
                   SET event_title = ?, source_id = ?, starts_at = ?, location = ?
                 WHERE registration_id = ?
                """,
                (title, source_id, starts_at, location, registration_id),
            )
            self._conn.commit()

    def next_registration_id(self) -> str:
        with self._lock:
            count = self._conn.execute("SELECT COUNT(*) AS n FROM registrations").fetchone()["n"]
        return f"demo-{int(count) + 1}"

    def list_library_extra(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload_json FROM library_extra ORDER BY created_at, id"
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def save_library_extra(self, event: dict) -> dict:
        created = now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO library_extra (id, source_id, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (event["id"], event["source_id"], json.dumps(event, ensure_ascii=False), created),
            )
            self._conn.commit()
        return event

    def add_feedback(self, user_id: str, author_name: str, rating: int, body: str, subject: str) -> dict:
        feedback_id = new_id("fb")
        created = now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO feedback (id, user_id, author_name, rating, body, subject, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (feedback_id, user_id, author_name, rating, body, subject, created),
            )
            self._conn.commit()
        return {
            "id": feedback_id,
            "user_id": user_id,
            "author_name": author_name,
            "rating": rating,
            "body": body,
            "subject": subject,
            "created_at": created,
            "synthetic": True,
            "visibility": "public",
        }

    def list_feedback(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM feedback ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [{**dict(row), "synthetic": True, "visibility": "public"} for row in rows]


def _action(row: sqlite3.Row) -> dict:
    trace = json.loads(row["trace_json"])
    trace.setdefault("action", {})["status"] = row["status"]
    notice = json.loads(row["notice_json"]) if row["notice_json"] else None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "event_id": row["event_id"],
        "status": row["status"],
        "signal": row["signal"],
        "score": row["score"],
        "trace": trace,
        "notice": notice,
        "created_at": row["created_at"],
        "decided_at": row["decided_at"],
    }
