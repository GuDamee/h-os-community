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
            self._conn.commit()
        return int(count)


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
