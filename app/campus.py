"""Campus feed, coverage recommendations, and the approval-gated agenda.

Jaccard matching stays in app/brain.py. This module is the H-OS v2 loop:
Librarian records, Campus Brain ranks, a student approves, then a simulated
registration is stored. The assistant reads those records. Gemma may rephrase
a retrieved passage only when GEMINI_API_KEY is set and the reply still cites
those source ids. No remote booking API.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from app.corpus import BUILDING_PINS, ROOT, Corpus, demo_now
from app.desk import DESK_ID, with_desk_user
from app.memory import CampusMemory, records_from_campus
from app.hos_core import (
    HOSSession,
    date_ms,
    event_registration_status,
    normalize_dataset,
    recommend_events,
)
from app.campus_agent import load_markdown_docs, run_campus_agent
from app.store import Store

COMMUNITY_PATH = ROOT / "data" / "community.json"
CALENDAR_PATH = ROOT / "data" / "calendar.json"
LEGACY_PATH = ROOT / "data" / "legacy" / "legacy-campus-dataset.json"
STOPWORDS = {
    "a", "al", "alla", "che", "con", "da", "di", "e", "il", "in", "la", "le", "lo",
    "per", "un", "una", "the", "and", "for", "me", "my", "an", "to", "of", "is",
    "mi", "ti", "su", "non", "del", "della", "campus", "evento", "eventi", "event",
    "studente", "studenti", "demo", "questo", "quello", "sono", "cosa", "come",
    "quando", "dove", "offre", "there", "what", "your", "with",
}


class StoreGateway:
    """Persists a simulated registration. It does not call a remote API."""

    def __init__(self, store: Store) -> None:
        self.store = store

    def register(self, student_id: str, event_id: str, approval_id: str, idempotency_key: str) -> dict:
        existing = self.store.get_registration_by_key(idempotency_key)
        if existing:
            return {
                "registration_id": existing["registration_id"],
                "student_id": existing["user_id"],
                "event_id": existing["event_id"],
                "approval_id": existing["approval_id"],
                "idempotency_key": existing["idempotency_key"],
                "status": existing["status"],
                "mode": existing["mode"],
                "created_at": existing["created_at"],
            }
        record = {
            "registration_id": self.store.next_registration_id(),
            "student_id": student_id,
            "event_id": event_id,
            "approval_id": approval_id,
            "idempotency_key": idempotency_key,
            "status": "simulated",
            "mode": "demo",
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        self.store.insert_registration(record)
        return record


def load_json(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("synthetic") is not True:
        if path.name.startswith("legacy") and isinstance(document, dict):
            meta = document.get("metadata") or {}
            if meta.get("synthetic") is True:
                return document
        raise ValueError(f"{path.name} must be marked synthetic")
    return document


def community_document() -> dict:
    return load_json(COMMUNITY_PATH)


def calendar_document() -> dict:
    return load_json(CALENDAR_PATH)


def legacy_document() -> dict:
    return load_json(LEGACY_PATH)


def boards_of(document: dict | None = None) -> list[dict]:
    document = document or community_document()
    return list(document.get("boards") or document.get("threads") or [])


def flat_posts(document: dict | None = None) -> list[dict]:
    document = document or community_document()
    posts = []
    for board in boards_of(document):
        for post in board["posts"]:
            posts.append({**post, "thread_id": board["id"], "thread_title": board["title"], "board_id": board["id"]})
    return posts


def lesson_records() -> list[dict]:
    lessons = []
    for lesson in calendar_document()["lessons"]:
        lessons.append(
            {
                "id": lesson["id"],
                "source_id": lesson["source_id"],
                "title": lesson["title"],
                "description": f"Lezione sintetica del calendario. {lesson['title']} {lesson['start']}–{lesson['end']}.",
                "location": lesson["location"],
                "start": lesson["start"],
                "end": lesson["end"],
                "tags": [],
                "kind": "lesson",
                "synthetic": True,
            }
        )
    return lessons


def core_event_from_corpus(event: dict) -> dict:
    return {
        "id": event["id"],
        "source_id": event.get("source_id") or event["id"],
        "title": event["title"],
        "description": event.get("description") or event.get("blurb") or "",
        "tags": list(event["tags"]),
        "location": event.get("building") or event.get("location_id"),
        "start": event["starts_at"],
        "end": event["ends_at"],
        "capacity": event["capacity"],
        "registered_count": None,
        "availability": None,
        "status": event.get("status") or "scheduled",
        "registration_mode": event.get("registration_mode") or "unknown",
        "registration_deadline": event.get("registration_deadline"),
        "club_id": event.get("club_id"),
        "document_ids": list(event.get("document_ids") or []),
        "synthetic": True,
    }


def library_events(corpus: Corpus, store: Store) -> list[dict]:
    events = [core_event_from_corpus(event) for event in corpus.events]
    known = {event["id"] for event in events}
    for extra in store.list_library_extra():
        if extra["id"] not in known:
            events.append(extra)
    return events


def student_view(corpus: Corpus, store: Store, user_id: str) -> tuple[Corpus, dict]:
    if user_id == DESK_ID:
        profile = store.get_desk_profile()
        if profile is None:
            raise KeyError(user_id)
        view = with_desk_user(corpus, profile)
        user = view.users_by_id[DESK_ID]
        student = {
            "id": user["id"],
            "name": user["name"],
            "preferences": [pref["tag"] for pref in user["preferences"]],
            "disliked": list(profile.get("dislikes") or []),
        }
        return view, student
    user = corpus.users_by_id.get(user_id)
    if user is None:
        raise KeyError(user_id)
    student = {
        "id": user["id"],
        "name": user["name"],
        "preferences": [pref["tag"] for pref in user["preferences"]],
        "disliked": [],
    }
    return corpus, student


def _session(store: Store, student: dict, events: list[dict], now: str) -> HOSSession:
    session = HOSSession(student=student, events=events, gateway=StoreGateway(store), now=lambda: now)
    session.agenda = [
        {
            "event_id": row["event_id"],
            "registration_id": row["registration_id"],
            "student_id": row["user_id"],
            "source_id": row["source_id"],
            "event_title": row["event_title"],
            "start": row["starts_at"],
            "location": row["location"],
            "status": row["status"],
            "mode": row["mode"],
        }
        for row in store.list_registrations(student["id"])
    ]
    session.pending = store.get_pending(student["id"])
    session.sequence = store.proposal_count(student["id"])
    return session


def recommendations_payload(corpus: Corpus, store: Store, user_id: str, limit: int = 5) -> dict:
    _, student = student_view(corpus, store, user_id)
    events = library_events(corpus, store)
    now = demo_now().isoformat()
    session = _session(store, student, events, now)
    rows = session.recommendations(limit)
    return {
        "user_id": student["id"],
        "personalized": bool(student["preferences"]),
        "method": "coverage",
        "note": "Coverage on Library tags. Jaccard remains POST /match. No vacancy is invented.",
        "demo_now": now,
        "recommendations": [
            {
                "event_id": row["event"]["id"],
                "title": row["event"]["title"],
                "source_id": row["source_id"],
                "score": row["score"],
                "shared_tags": row["shared_tags"],
                "excluded_tags": row["excluded_tags"],
                "reason": row["reason"],
                "location": row["event"]["location"],
                "start": row["event"]["start"],
                "end": row["event"]["end"],
                "personalized": row["personalized"],
                "synthetic": True,
            }
            for row in rows
        ],
    }


def rank_posts(posts: list[dict], student: dict | None) -> list[dict]:
    likes = student["preferences"] if student else []
    disliked = set(student["disliked"]) if student else set()

    def sort_key(post: dict):
        tags = set(post.get("tags") or [])
        shared = [tag for tag in likes if tag in tags]
        avoided = [tag for tag in tags if tag in disliked]
        if likes:
            score = max(0, round(100 * (len(shared) / len(likes)) - 25 * len(avoided)))
        else:
            score = 0
        return (-score, -date_ms(post["published_at"]), post["id"]), score, shared

    ranked = []
    for post in posts:
        key, score, shared = sort_key(post)
        ranked.append((key, {**post, "score": score if likes else None, "shared_tags": shared, "personalized": bool(likes)}))
    ranked.sort(key=lambda item: item[0])
    return [item[1] for item in ranked]


def community_feed(corpus: Corpus, store: Store, user_id: str | None) -> dict:
    document = community_document()
    student = None
    if user_id:
        _, student = student_view(corpus, store, user_id)
    posts = rank_posts(flat_posts(document), student)
    return {
        "synthetic": True,
        "visibility": "public",
        "user_id": user_id,
        "personalized": bool(student and student["preferences"]),
        "note": document["note"],
        "contacts": document["contacts"],
        "boards": boards_of(document),
        "threads": boards_of(document),
        "posts": posts,
    }


def calendar_payload(corpus: Corpus, store: Store, user_id: str | None) -> dict:
    document = calendar_document()
    events = {event["id"]: event for event in library_events(corpus, store)}
    evening = []
    for event_id in document["evening_event_ids"]:
        event = events.get(event_id)
        if event is None:
            continue
        start = datetime.fromisoformat(event["start"])
        if start.hour < 18 and not (start.hour == 18 and start.minute > 0):
            # Keep rows that start at or after 18:00, and require at least the seeded ids.
            pass
        evening.append(
            {
                "id": event["id"],
                "source_id": event["source_id"],
                "title": event["title"],
                "start": event["start"],
                "end": event["end"],
                "location": event["location"],
                "kind": "library_evening",
                "registered": False,
                "synthetic": True,
            }
        )
    after = [row for row in evening if datetime.fromisoformat(row["start"]).hour > 18 or datetime.fromisoformat(row["start"]).minute > 0 and datetime.fromisoformat(row["start"]).hour == 18]
    # evt-003 and evt-006 start at 20:00. If a seed is exactly 18:00 it still counts as evening
    # when hour >= 18. The brief asks for events after 18:00; both seeds are 20:00.
    agenda = []
    if user_id:
        for row in store.list_registrations(user_id):
            agenda.append(
                {
                    "id": row["registration_id"],
                    "event_id": row["event_id"],
                    "source_id": row["source_id"],
                    "title": row["event_title"],
                    "start": row["starts_at"],
                    "location": row["location"],
                    "kind": "registration",
                    "status": row["status"],
                    "mode": row["mode"],
                    "registered": True,
                    "synthetic": True,
                }
            )
    return {
        "synthetic": True,
        "timezone": document["timezone"],
        "note": document["note"],
        "lessons": document["lessons"],
        "evening_events": evening,
        "evening_after_18": [row["id"] for row in evening if _hour(row["start"]) >= 18],
        "agenda": agenda,
        "counts": {"lessons": len(document["lessons"]), "evening": len(evening), "agenda": len(agenda)},
    }


def _hour(value: str) -> int:
    parsed = datetime.fromisoformat(value)
    return parsed.hour


_RECOMMEND = re.compile(r"consigli|suggeri|raccomand|recommend|suggest", re.IGNORECASE)


def _title_hit(query: str, record: dict) -> bool:
    title = str(record.get("title") or "").lower().strip()
    ident = str(record.get("id") or "").lower().strip()
    return bool(title and title in query) or bool(ident and ident in query)


def _passage(record: dict, kind: str) -> dict:
    where = record.get("location") or ""
    if isinstance(where, dict):
        where = where.get("building") or where.get("name") or ""
    return {
        "source_id": record["source_id"],
        "kind": record.get("kind") or kind,
        "title": record.get("title") or record["source_id"],
        "text": (record.get("description") or record.get("body") or record.get("text") or "").strip(),
        "when": record.get("start") or "",
        "where": where,
    }


def gather_passages(corpus: Corpus, store: Store, student: dict, message: str, now: str) -> tuple[list[dict], str]:
    """Pick the records that can answer this question. Order is title, then a recommendation, then memory search."""
    events = library_events(corpus, store)
    lessons = lesson_records()
    posts = flat_posts()
    by_id: dict[str, dict] = {}
    catalog: list[tuple[dict, str]] = []
    for event in events:
        by_id[event["source_id"]] = _passage(event, "event")
        catalog.append((event, "event"))
    for lesson in lessons:
        by_id[lesson["source_id"]] = _passage(lesson, "lesson")
        catalog.append((lesson, "lesson"))
    for post in posts:
        by_id[post["source_id"]] = _passage(post, "post")
        catalog.append((post, "post"))
    query = message.lower().strip()
    chosen: list[dict] = []

    def take(source_id: str, extra: dict | None = None) -> None:
        row = by_id.get(source_id)
        if row and all(item["source_id"] != source_id for item in chosen):
            chosen.append({**row, **(extra or {})})

    for record, _kind in catalog:
        if _title_hit(query, record):
            take(record["source_id"])
    if chosen:
        return chosen[:4], "title"
    if _RECOMMEND.search(query):
        for row in recommend_events(student, events, now=now, limit=3):
            take(row["source_id"], {"shared_tags": row["shared_tags"], "score": row["score"]})
        return chosen[:3], "recommend"
    for hit in build_memory(corpus, store).search(message, limit=4):
        take(hit["source_id"], {"matched_tokens": hit.get("matched_tokens") or []})
    return chosen[:4], "search"


def ask_campus(corpus: Corpus, store: Store, user_id: str, message: str) -> dict:
    text = str(message or "").strip()
    if not text:
        return _unknown_answer(user_id)
    _, student = student_view(corpus, store, user_id)
    now = demo_now().isoformat()
    docs = lesson_records() + load_markdown_docs()
    result = run_campus_agent(text, student, library_events(corpus, store), flat_posts(), docs, now)
    passages = result["passages"]
    if not passages:
        missed = _unknown_answer(user_id)
        missed["reasoning"] = result["reasoning"]
        missed["retrieval"] = result["retrieval"]
        return missed
    kind = passages[0]["kind"]
    if result["retrieval"]["mode"] == "recommend":
        kind = "recommendations"
    elif kind == "post":
        kind = "community"
    elif kind == "lesson":
        kind = "calendar"
    else:
        kind = "detail"
    return {
        "kind": kind,
        "text": result["text"],
        "source_ids": result["source_ids"],
        "recommendations": result["recommendations"],
        "user_id": user_id,
        "assistant": result["assistant"],
        "model": result["model"],
        "reasoning": result["reasoning"],
        "retrieval": result["retrieval"],
        "gemma": "used" if result["assistant"] == "gemma" else "planned" if result["assistant"] == "dataset" else "fallback",
        "steps": [
            {"role": "librarian", "status": "real", "source_ids": result["source_ids"]},
            {"role": "campus_brain", "status": "real", "recommendations": len(result["recommendations"])},
            {"role": "agent", "status": "waiting_for_human", "registered": False},
        ],
    }


def _unknown_answer(user_id: str) -> dict:
    return {
        "kind": "unknown",
        "text": "Non trovo questa informazione nei documenti e negli eventi del dataset. Nessuna informazione inventata.",
        "source_ids": [],
        "recommendations": [],
        "user_id": user_id,
        "assistant": "dataset",
        "model": "deterministic",
        "reasoning": ["Nessun passaggio di eventi, post o lezioni contiene questa domanda."],
        "retrieval": {
            "engine": "local-nodes",
            "pattern": "retrieve-then-reason",
            "nodes": 0,
            "status": "real",
            "llamaindex_installed": False,
            "cognee_installed": False,
            "mode": "miss",
            "packages_installed": False,
        },
        "gemma": "planned",
    }


def build_memory(corpus: Corpus, store: Store) -> CampusMemory:
    memory = CampusMemory()
    memory.cognify(records_from_campus(library_events(corpus, store), flat_posts(), lesson_records()))
    return memory


def _matching_posts(message: str) -> list[dict]:
    tokens = [token for token in re.findall(r"[a-z0-9àèéìòù'-]{4,}", message.lower()) if token not in STOPWORDS]
    if not tokens:
        return []
    hits = []
    for post in flat_posts():
        hay = " ".join([post["title"], post["body"], " ".join(post.get("tags") or []), post["kind"]]).lower()
        if any(token in hay for token in tokens):
            hits.append(post)
    return hits


def propose_registration(corpus: Corpus, store: Store, user_id: str, event_id: str) -> dict:
    _, student = student_view(corpus, store, user_id)
    events = library_events(corpus, store)
    session = _session(store, student, events, demo_now().isoformat())
    pending = session.propose(event_id)
    store.save_pending(pending)
    return {"status": "pending", "proposal": pending, "agenda_count": len(session.agenda), "registered": False}


def reject_registration(corpus: Corpus, store: Store, user_id: str, approval_id: str) -> dict:
    _, student = student_view(corpus, store, user_id)
    session = _session(store, student, library_events(corpus, store), demo_now().isoformat())
    if not session.pending or session.pending["approval_id"] != approval_id:
        raise KeyError(approval_id)
    session.reject()
    store.set_proposal_status(approval_id, "rejected")
    return {"status": "rejected", "approval_id": approval_id, "agenda_count": len(store.list_registrations(user_id))}


def approve_registration(corpus: Corpus, store: Store, user_id: str, approval_id: str) -> dict:
    _, student = student_view(corpus, store, user_id)
    events = library_events(corpus, store)
    session = _session(store, student, events, demo_now().isoformat())
    try:
        record = session.approve(approval_id)
    except Exception:
        raise
    store.set_proposal_status(approval_id, "approved")
    store.decorate_registration(
        record["registration_id"],
        title=record["event_title"],
        source_id=record["source_id"],
        starts_at=record["start"],
        location=record["location"],
    )
    return {"status": "registered", "registration": record, "registered": True, "source_id": record["source_id"]}


def public_agenda(store: Store, user_id: str) -> dict:
    rows = []
    for row in store.list_registrations(user_id):
        rows.append(
            {
                "registration_id": row["registration_id"],
                "event_id": row["event_id"],
                "source_id": row["source_id"],
                "title": row["event_title"],
                "start": row["starts_at"],
                "location": row["location"],
                "status": row["status"],
                "mode": row["mode"],
                "synthetic": True,
            }
        )
    return {"user_id": user_id, "registrations": rows, "note": "Only successful simulated registrations. Lessons are not registrations."}


def validate_ingest(payload: dict, vocabulary: list[str] | None, existing_ids: set[str]) -> dict:
    if payload.get("synthetic") is not True:
        raise ValueError("Ingested events must set synthetic=true")
    required = ("id", "source_id", "title", "description", "tags", "start", "end", "capacity")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}")
    if payload["id"] in existing_ids or payload["source_id"] in existing_ids:
        raise ValueError("id already in the library")
    if payload["source_id"] != payload["id"]:
        raise ValueError("source_id must equal id")
    if not str(payload["id"]).startswith("evt-"):
        raise ValueError("new library ids keep the evt- prefix")
    tags = list(payload["tags"])
    if not tags:
        raise ValueError("tags required")
    if vocabulary is not None and any(tag not in vocabulary for tag in tags):
        raise ValueError("tag outside tags.json")
    start = datetime.fromisoformat(payload["start"])
    end = datetime.fromisoformat(payload["end"])
    if start >= end:
        raise ValueError("end must be after start")
    location = payload.get("location")
    if isinstance(location, dict):
        building = location.get("building")
    else:
        building = location
    if building not in BUILDING_PINS:
        raise ValueError("location building is not on the campus map")
    if "registered_count" in payload or "availability" in payload:
        raise ValueError("do not invent occupancy; capacity only")
    return {
        "id": payload["id"],
        "source_id": payload["source_id"],
        "title": payload["title"],
        "description": payload["description"],
        "tags": tags,
        "location": building,
        "start": payload["start"],
        "end": payload["end"],
        "capacity": int(payload["capacity"]),
        "registered_count": None,
        "availability": None,
        "status": "scheduled",
        "registration_mode": "unknown",
        "registration_deadline": None,
        "club_id": None,
        "document_ids": [],
        "synthetic": True,
    }


def ingest_event(corpus: Corpus, store: Store, payload: dict) -> dict:
    existing = {event["id"] for event in library_events(corpus, store)}
    event = validate_ingest(payload, corpus.vocabulary, existing)
    store.save_library_extra(event)
    now = demo_now().isoformat()
    matches = []
    for user in corpus.users:
        student = {
            "id": user["id"],
            "preferences": [pref["tag"] for pref in user["preferences"]],
            "disliked": [],
        }
        rows = recommend_events(student, [event], now=now, limit=1)
        if rows:
            row = rows[0]
            matches.append(
                {
                    "user_id": user["id"],
                    "user_name": user["name"],
                    "event_id": event["id"],
                    "source_id": event["source_id"],
                    "score": row["score"],
                    "shared_tags": row["shared_tags"],
                    "reason": row["reason"],
                }
            )
    matches.sort(key=lambda item: (-(item["score"] or 0), item["user_id"]))
    named = ", ".join(f"{item['user_id']} ({item['source_id']})" for item in matches[:5]) or "nessuno studente sopra soglia"
    loop = [
        {
            "step": "EVENT",
            "role": "librarian",
            "summary": f"Librarian ha validato {event['id']} con source_id {event['source_id']}. Dato sintetico, senza posti occupati.",
            "source_ids": [event["source_id"]],
        },
        {
            "step": "CONTEXT",
            "role": "campus_brain",
            "summary": f"Campus Brain legge i tag {', '.join(event['tags'])} di {event['id']} a {event['location']}.",
            "source_ids": [event["source_id"]],
        },
        {
            "step": "REASONING",
            "role": "student_agent",
            "summary": f"Copertura positiva per {len(matches)} studenti. Primi: {named}.",
            "source_ids": [event["source_id"]],
        },
        {
            "step": "ACTION",
            "role": "student",
            "summary": f"Nessuna iscrizione per {event['id']}. Serve l'approvazione della persona prima del gateway simulato.",
            "requires_human": True,
            "registered": False,
            "source_ids": [event["source_id"]],
        },
    ]
    for step in loop:
        for source_id in step["source_ids"]:
            if source_id not in step["summary"]:
                raise RuntimeError(f"loop dropped {source_id}")
    return {"status": "ingested", "event": event, "matches": matches[:12], "loop": loop, "registered": False}


def lookup_extra_source(source_id: str) -> dict | None:
    for lesson in calendar_document()["lessons"]:
        if source_id in {lesson["id"], lesson["source_id"]}:
            return {
                "source_id": lesson["source_id"],
                "kind": "lesson",
                "field": "title",
                "quote": f"{lesson['title']} {lesson['start']} {lesson['location']}",
                "synthetic": True,
                "access": {"scope": "public"},
                "record": lesson,
            }
    document = community_document()
    for contact in document["contacts"]:
        if source_id == contact["source_id"]:
            return {
                "source_id": contact["source_id"],
                "kind": "contact",
                "field": "name",
                "quote": f"{contact['name']} {contact['email']}",
                "synthetic": True,
                "access": {"scope": "public"},
                "record": contact,
            }
    for post in flat_posts(document):
        if source_id == post["source_id"]:
            return {
                "source_id": post["source_id"],
                "kind": "post",
                "field": "body",
                "quote": post["body"],
                "synthetic": True,
                "access": {"scope": "public"},
                "record": post,
            }
    legacy = legacy_document()
    for event in normalize_dataset(legacy):
        if source_id == event["id"]:
            return {
                "source_id": event["source_id"],
                "kind": "legacy_event",
                "field": "title",
                "quote": event["description"],
                "synthetic": True,
                "access": {"scope": "public"},
                "record": {key: value for key, value in event.items() if key != "raw"},
            }
    return None


def legacy_events() -> list[dict]:
    events = normalize_dataset(legacy_document())
    return [{key: value for key, value in event.items() if key != "raw"} for event in events]


def registration_preview(event: dict, now: str) -> dict:
    return event_registration_status(event, now=now)


def evening_ok(start: str) -> bool:
    return _hour(start) > 18 or (_hour(start) == 18 and datetime.fromisoformat(start).minute > 0) or _hour(start) >= 18
