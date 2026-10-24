"""Community bacheca chats and campus calendar (lessons + evening events)."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.corpus import DATA_DIR, ROME, demo_now

_LOCK = threading.Lock()


def _read(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_community(data_dir: Path | None = None) -> dict:
    base = data_dir or DATA_DIR
    return _read(base / "community.json")


def load_calendar(data_dir: Path | None = None) -> dict:
    base = data_dir or DATA_DIR
    return _read(base / "calendar.json")


def boards_summary(doc: dict) -> list[dict]:
    out = []
    for board in doc.get("boards", []):
        msgs = board.get("messages") or []
        last = msgs[-1] if msgs else None
        out.append(
            {
                "id": board["id"],
                "name": board["name"],
                "tag": board.get("tag", ""),
                "description": board.get("description", ""),
                "message_count": len(msgs),
                "last_message": last,
            }
        )
    return out


def board_detail(doc: dict, board_id: str) -> dict | None:
    for board in doc.get("boards", []):
        if board["id"] == board_id:
            return {
                "id": board["id"],
                "name": board["name"],
                "tag": board.get("tag", ""),
                "description": board.get("description", ""),
                "messages": list(board.get("messages") or []),
            }
    return None


def append_message(
    data_dir: Path,
    board_id: str,
    *,
    author: str,
    text: str,
    role: str = "student",
) -> dict:
    """Persist a new chat message into community.json (demo-local)."""
    path = data_dir / "community.json"
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        raise ValueError("Il messaggio è vuoto.")
    if len(cleaned) > 800:
        raise ValueError("Messaggio troppo lungo (max 800).")
    author = (author or "Studente").strip()[:80] or "Studente"
    with _LOCK:
        doc = _read(path)
        target = None
        for board in doc.get("boards", []):
            if board["id"] == board_id:
                target = board
                break
        if target is None:
            raise KeyError(board_id)
        message = {
            "id": f"msg-{uuid.uuid4().hex[:10]}",
            "author": author,
            "role": role,
            "at": demo_now().astimezone(ROME).isoformat(),
            "text": cleaned,
        }
        target.setdefault("messages", []).append(message)
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return message


def calendar_payload(doc: dict) -> dict:
    """Expand lessons onto concrete dates for the desk UI."""
    now = demo_now().astimezone(ROME)
    lessons = []
    for lesson in doc.get("lessons", []):
        for day in lesson.get("dates") or []:
            start = _combine(day, lesson["start"])
            end = _combine(day, lesson["end"])
            lessons.append(
                {
                    "id": f"{lesson['id']}-{day}",
                    "series_id": lesson["id"],
                    "title": lesson["title"],
                    "kind": "lezione",
                    "weekday": lesson.get("weekday"),
                    "date": day,
                    "start": lesson["start"],
                    "end": lesson["end"],
                    "starts_at": start.isoformat(),
                    "ends_at": end.isoformat(),
                    "location": lesson.get("location", ""),
                    "past": end < now,
                }
            )
    events = []
    for event in doc.get("events", []):
        start = _combine(event["date"], event["start"])
        end = _combine(event["date"], event["end"])
        events.append(
            {
                "id": event["id"],
                "title": event["title"],
                "kind": "evento",
                "date": event["date"],
                "start": event["start"],
                "end": event["end"],
                "starts_at": start.isoformat(),
                "ends_at": end.isoformat(),
                "location": event.get("location", ""),
                "blurb": event.get("blurb", ""),
                "past": end < now,
            }
        )
    items = sorted(lessons + events, key=lambda row: row["starts_at"])
    return {
        "timezone": doc.get("timezone", "Europe/Rome"),
        "demo_now": now.isoformat(),
        "lessons": lessons,
        "events": events,
        "items": items,
    }


def _combine(day: str, hhmm: str) -> datetime:
    hour, minute = (int(part) for part in hhmm.split(":", 1))
    year, month, day_n = (int(part) for part in day.split("-"))
    return datetime(year, month, day_n, hour, minute, tzinfo=ROME)
