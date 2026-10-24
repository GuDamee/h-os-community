"""Python mirror of reference/hos-core.

The FastAPI desk is the source of truth. The Node module under
reference/hos-core is the original harness, not the site. Scores here are
coverage percentages, not probabilities and not the Jaccard ranker in
app/brain.py. Gemma is not called from this module.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
HOS_NAME = "H-OS"

INTENT = re.compile(
    r"consigli|suggeri|raccomand|interess|evento|attivit|partecip|iscriv|registr|"
    r"recommend|suggest|event|activit|join|sign[\s-]*up|interest|upcoming|"
    r"what(?:'s| is) on|study group|gruppo studio|passagg|car share|aiut",
    re.IGNORECASE,
)


def unique(values) -> list[str]:
    seen: list[str] = []
    for value in values or []:
        if isinstance(value, str) and value not in seen:
            seen.append(value)
    return seen


def date_ms(value: str) -> float:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ROME)
    return parsed.timestamp() * 1000


def js_round(value: float) -> int:
    return int(math.floor(value + 0.5))


def normalize_dataset(raw) -> list[dict]:
    if isinstance(raw, list):
        events = []
        for event in raw:
            if not event.get("id") or not event.get("source_id") or not isinstance(event.get("tags"), list) or not event.get("start") or not event.get("end"):
                raise ValueError(f"Invalid new event record: {event.get('id', 'unknown')}")
            location = event["location"]["building"] if isinstance(event.get("location"), dict) else event.get("location")
            events.append(
                {
                    "id": event["id"],
                    "source_id": event["source_id"],
                    "title": event.get("title"),
                    "description": event.get("description") or "",
                    "tags": unique(event.get("tags")),
                    "location": location,
                    "start": event["start"],
                    "end": event["end"],
                    "capacity": event.get("capacity"),
                    "registered_count": None,
                    "availability": None,
                    "status": "scheduled",
                    "registration_mode": "unknown",
                    "registration_deadline": None,
                    "club_id": None,
                    "document_ids": [],
                    "synthetic": True,
                    "raw": event,
                }
            )
        return events
    if isinstance(raw, dict) and isinstance(raw.get("events"), list) and isinstance(raw.get("interests"), list):
        names = {item["id"]: item["label"] for item in raw["interests"]}
        events = []
        for event in raw["events"]:
            remaining = None
            if isinstance(event.get("registered_count"), int):
                remaining = max(0, event["capacity"] - event["registered_count"])
            events.append(
                {
                    "id": event["id"],
                    "source_id": event["id"],
                    "title": event.get("title"),
                    "description": event.get("description") or "",
                    "tags": [names.get(item, item) for item in event.get("interest_ids") or []],
                    "tagIds": unique(event.get("interest_ids")),
                    "location": event.get("location"),
                    "start": event.get("start"),
                    "end": event.get("end"),
                    "capacity": event.get("capacity"),
                    "registered_count": event.get("registered_count"),
                    "availability": remaining,
                    "status": event.get("status"),
                    "registration_mode": event.get("registration_mode"),
                    "registration_deadline": event.get("registration_deadline"),
                    "club_id": event.get("club_id"),
                    "document_ids": list(event.get("document_ids") or []),
                    "synthetic": True,
                    "raw": event,
                }
            )
        return events
    raise ValueError("Unsupported H-OS dataset format")


def normalize_student(raw: dict, legacy_data: dict | None = None) -> dict:
    if isinstance(raw.get("preferences"), list):
        return {
            "id": raw["id"],
            "name": raw.get("name"),
            "preferences": unique(raw["preferences"]),
            "disliked": [],
            "email": None,
        }
    if isinstance(raw.get("liked_interest_ids"), list) and legacy_data:
        labels = {item["id"]: item["label"] for item in legacy_data["interests"]}
        return {
            "id": raw["id"],
            "name": raw.get("name"),
            "preferences": unique(labels.get(item, item) for item in raw["liked_interest_ids"]),
            "disliked": unique(labels.get(item, item) for item in (raw.get("disliked_interest_ids") or [])),
            "email": None,
        }
    raise ValueError("Unsupported H-OS student schema")


def recommend_events(student: dict, events: list[dict], now: str | None = None, limit: int = 5, exclude_registered: list[str] | None = None) -> list[dict]:
    liked = unique(student.get("preferences"))
    disliked = set(student.get("disliked") or [])
    excluded = set(exclude_registered or [])
    clock = date_ms(now or datetime.now(ROME).isoformat())
    rows = []
    for event in events:
        if event.get("status") in {"cancelled", "completed"}:
            continue
        if date_ms(event["start"]) <= clock or event["id"] in excluded:
            continue
        shared = [tag for tag in liked if tag in event.get("tags", [])]
        avoided = [tag for tag in event.get("tags", []) if tag in disliked]
        if liked:
            score = max(0, js_round(100 * (len(shared) / len(liked)) - 25 * len(avoided)))
        else:
            score = None
        rows.append(
            {
                "event": event,
                "score": score,
                "shared_tags": shared,
                "excluded_tags": avoided,
                "source_id": event["source_id"],
                "reason": (
                    (f"Interessi condivisi: {', '.join(shared)}." if shared else "Nessun interesse condiviso.")
                    if liked
                    else "Prossimo evento in calendario: preferenze non impostate."
                ),
                "personalized": bool(liked),
            }
        )
    kept = [row for row in rows if not liked or (row["score"] > 0 and row["shared_tags"])]
    kept.sort(key=lambda row: (-(row["score"] or 0), date_ms(row["event"]["start"]), row["event"]["id"]))
    return kept[:limit]


def event_registration_status(event: dict, now: str | None = None) -> dict:
    clock = date_ms(now or datetime.now(ROME).isoformat())
    if event.get("status") == "cancelled":
        return {"allowed": False, "reason": "Evento annullato"}
    if event.get("status") == "completed" or date_ms(event["start"]) <= clock:
        return {"allowed": False, "reason": "Evento concluso o iniziato"}
    deadline = event.get("registration_deadline")
    if deadline and date_ms(deadline) < clock:
        return {"allowed": False, "reason": "Iscrizioni chiuse"}
    if event.get("registration_mode") == "closed":
        return {"allowed": False, "reason": "Iscrizioni chiuse"}
    if event.get("registration_mode") == "waitlist" or event.get("availability") == 0:
        return {"allowed": False, "reason": "Solo lista d’attesa: non supportata da questo modulo"}
    if event.get("availability") is None:
        reason = "Posti disponibili non verificabili: capienza totale soltanto"
    else:
        reason = f"{event['availability']} posti dichiarati nel dataset sintetico"
    return {"allowed": True, "reason": reason}


def _title_match(query: str, record: dict) -> bool:
    title = str(record.get("title") or "").lower()
    ident = str(record.get("id") or "").lower()
    return (title and title in query) or (ident and ident in query)


def answer_event_question(query: str, student: dict, events: list[dict], now: str | None = None, references: list[dict] | None = None) -> dict:
    text = str(query or "").lower().strip()
    clock = now or datetime.now(ROME).isoformat()
    if not text:
        return {"kind": "unknown", "text": "Scrivi una domanda sugli eventi del dataset.", "source_ids": [], "recommendations": []}
    candidates = recommend_events(student, events, now=clock, limit=5)
    pool = list(events) + list(references or [])
    match = next((item for item in pool if _title_match(text, item)), None)
    if match:
        return {
            "kind": "detail",
            "text": f"{match['title']}: {match.get('description') or ''} Luogo: {match.get('location')}. Inizio: {match.get('start')}. Fonte: {match['source_id']}.",
            "source_ids": [match["source_id"]],
            "recommendations": [],
            "event_id": match["id"],
        }
    if INTENT.search(text):
        if not candidates:
            return {
                "kind": "recommendations",
                "text": "Non trovo eventi futuri compatibili nel dataset. Prova a modificare le preferenze.",
                "source_ids": [],
                "recommendations": [],
            }
        top = candidates[0]
        return {
            "kind": "recommendations",
            "text": (
                f"Ti consiglio «{top['event']['title']}». {top['reason']} "
                f"Luogo: {top['event']['location']}; inizio: {top['event']['start']}. "
                f"Fonte: {top['source_id']}. Per iscriverti devi approvare una proposta: nessuna azione è stata eseguita."
            ),
            "source_ids": [top["source_id"]],
            "recommendations": [
                {
                    "event_id": row["event"]["id"],
                    "source_id": row["source_id"],
                    "score": row["score"],
                    "shared_tags": row["shared_tags"],
                    "reason": row["reason"],
                }
                for row in candidates
            ],
            "event_id": top["event"]["id"],
        }
    return {
        "kind": "unknown",
        "text": "Non posso verificarlo con i dati sugli eventi disponibili. Nessuna informazione inventata.",
        "source_ids": [],
        "recommendations": [],
    }


class InMemoryDemoRegistrationGateway:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def register(self, student_id: str, event_id: str, approval_id: str, idempotency_key: str) -> dict:
        existing = next((row for row in self.records if row["idempotency_key"] == idempotency_key), None)
        if existing:
            return existing
        record = {
            "registration_id": f"demo-{len(self.records) + 1}",
            "student_id": student_id,
            "event_id": event_id,
            "approval_id": approval_id,
            "idempotency_key": idempotency_key,
            "status": "simulated",
            "mode": "demo",
            "created_at": datetime.now(ROME).isoformat(),
        }
        self.records.append(record)
        return record


class HttpRegistrationGateway:
    """Proposal adapter. The desk does not point this at a live remote API."""

    def __init__(self, base_url: str, fetcher) -> None:
        if not base_url or not callable(fetcher):
            raise ValueError("Backend URL and fetch required")
        self.base_url = base_url.rstrip("/")
        self.fetcher = fetcher

    def register(self, student_id: str, event_id: str, approval_id: str, idempotency_key: str) -> dict:
        payload = {
            "student_id": student_id,
            "event_id": event_id,
            "approval_id": approval_id,
            "idempotency_key": idempotency_key,
        }
        response = self.fetcher(
            f"{self.base_url}/registrations",
            {
                "method": "POST",
                "headers": {"Content-Type": "application/json", "Idempotency-Key": idempotency_key},
                "body": payload,
            },
        )
        if not response.get("ok"):
            raise RuntimeError(f"Registration API rejected request: {response.get('status')}")
        data = response["json"]
        if (
            not data.get("registration_id")
            or data.get("status") not in {"confirmed", "waitlisted"}
            or data.get("event_id") != event_id
            or data.get("student_id") != student_id
        ):
            raise RuntimeError("Invalid registration API response")
        return {**data, "mode": "backend"}


class HOSSession:
    def __init__(self, student: dict, events: list[dict], gateway, now=None) -> None:
        if not student or not student.get("id") or not getattr(gateway, "register", None):
            raise ValueError("Student and registration gateway required")
        self.student = {**student, "preferences": unique(student.get("preferences"))}
        self.events = events
        self.gateway = gateway
        self.now = now or (lambda: datetime.now(ROME).isoformat())
        self.pending = None
        self.agenda: list[dict] = []
        self.sequence = 0

    def set_preferences(self, preferences, disliked=None) -> None:
        self.student["preferences"] = unique(preferences)
        if disliked is None:
            disliked = self.student.get("disliked") or []
        self.student["disliked"] = [tag for tag in unique(disliked) if tag not in self.student["preferences"]]
        self.pending = None

    def recommendations(self, limit: int = 5) -> list[dict]:
        return recommend_events(
            self.student,
            self.events,
            now=self.now(),
            limit=limit,
            exclude_registered=[item["event_id"] for item in self.agenda],
        )

    def ask(self, text: str, references: list[dict] | None = None) -> dict:
        return answer_event_question(text, self.student, self.events, now=self.now(), references=references)

    def propose(self, event_id: str) -> dict:
        event = next((item for item in self.events if item["id"] == event_id), None)
        if event is None:
            raise ValueError("Unknown event ID")
        if any(item["event_id"] == event_id for item in self.agenda):
            raise ValueError("Already registered in agenda")
        state = event_registration_status(event, now=self.now())
        if not state["allowed"]:
            raise ValueError(state["reason"])
        self.sequence += 1
        self.pending = {
            "approval_id": f"client-proposal-{self.sequence}",
            "student_id": self.student["id"],
            "event_id": event["id"],
            "event_title": event["title"],
            "source_id": event["source_id"],
            "warning": state["reason"],
        }
        return self.pending

    def reject(self) -> None:
        self.pending = None

    def approve(self, approval_id: str) -> dict:
        pending = self.pending
        if not pending or pending["approval_id"] != approval_id:
            raise ValueError("No matching pending approval")
        if any(item["event_id"] == pending["event_id"] for item in self.agenda):
            raise ValueError("Already in agenda")
        event = next((item for item in self.events if item["id"] == pending["event_id"]), None)
        if event is None or not event_registration_status(event, now=self.now())["allowed"]:
            raise ValueError("Event no longer eligible")
        self.pending = None
        key = f"{self.student['id']}:{pending['event_id']}:{pending['approval_id']}"
        try:
            record = self.gateway.register(
                student_id=self.student["id"],
                event_id=pending["event_id"],
                approval_id=pending["approval_id"],
                idempotency_key=key,
            )
            if (
                not record
                or not record.get("registration_id")
                or record.get("event_id") != pending["event_id"]
                or record.get("student_id") != self.student["id"]
                or record.get("status") not in {"confirmed", "waitlisted", "simulated"}
            ):
                raise ValueError("Gateway returned an invalid registration")
            stored = {
                **record,
                "event_title": event["title"],
                "source_id": event["source_id"],
                "start": event["start"],
                "location": event["location"],
            }
            self.agenda.append(stored)
            return stored
        except Exception:
            self.pending = pending
            raise
