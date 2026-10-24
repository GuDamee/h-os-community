"""Load the synthetic campus and refuse anything that is not marked invented.

The team files store preferences as tag names and events as a building plus a
naive local datetime. This module keeps those fields and adds only the indexes
the desk needs in memory: a preference id per existing tag, a Europe/Rome
offset, and a schematic pin for the building name. Those indexes are not
written back to the JSON.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.access import describe_access

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ROME = ZoneInfo("Europe/Rome")

PREFIX = {
    "user": "usr-",
    "preference": "pref-",
    "event": "evt-",
    "place": "loc-",
    "email": "mail-",
}
HOST_ROLES = {"studenti", "prof", "gestori"}
TAG_RE = re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$")
SOURCE_ID_RE = re.compile(r"^(?:usr|pref|evt|loc|mail)-[a-z0-9]+(?:-[a-z0-9]+)*$")

# The team events name a building and do not carry coordinates.
# These pins are the campus schematic in places.json, not a surveyed point.
BUILDING_PINS = {
    "La Serra": "loc-serra",
    "Building 1": "loc-college",
    "Building 2": "loc-lab",
    "Building 3": "loc-library",
    "Building 4": "loc-auditorium",
    "Building 5": "loc-startup",
}


def demo_now() -> datetime:
    raw = os.getenv("DEMO_NOW", "2026-10-24T18:40:00+02:00")
    return _datetime(raw, "DEMO_NOW")


def load_corpus(data_dir: Path | None = None) -> "Corpus":
    base = DATA_DIR
    overlay = Path(data_dir or os.getenv("HOS_DATA_DIR", base))
    places_path = overlay / "places.json"
    if not places_path.exists():
        places_path = base / "places.json"
    places_doc = _read_marked(places_path)
    users_doc = _read_marked(overlay / "users.json")
    events_doc = _read_marked(overlay / "events.json")
    emails_doc = _read_marked(overlay / "emails.json")
    vocabulary = _vocabulary(overlay)

    places = places_doc["places"]
    users = [_normalize_user(user) for user in users_doc["users"]]
    events = [_normalize_event(event) for event in events_doc["events"]]
    emails = [_normalize_email(mail) for mail in emails_doc["emails"]]
    if not isinstance(places, list) or not places:
        raise ValueError(f"{places_path} has no places")

    by_id: dict[str, dict] = {}

    def remember(source_id: str, kind: str, quote: str, field: str, record: dict) -> None:
        prefix = PREFIX[kind]
        if not source_id.startswith(prefix):
            raise ValueError(f"{source_id} must start with {prefix}")
        if SOURCE_ID_RE.fullmatch(source_id) is None:
            raise ValueError(f"{source_id} is not a citable id")
        if source_id in by_id:
            raise ValueError(f"duplicate source id {source_id}")
        by_id[source_id] = {
            "source_id": source_id,
            "kind": kind,
            "quote": quote,
            "field": field,
            "record": record,
        }

    for place in places:
        _need(place, ("id", "name", "zone", "x", "y"), "place")
        if not isinstance(place["x"], (int, float)) or not isinstance(place["y"], (int, float)):
            raise ValueError(f"{place['id']} has non-numeric coordinates")
        quote = f"{place['name']} · {place['zone']}"
        remember(place["id"], "place", quote, "name", place)

    place_ids = {place["id"] for place in places}

    for user in users:
        if user["role"] != "student":
            raise ValueError(
                f"{user['id']} has role {user['role']!r}. This demo loads students only."
            )
        if user.get("hangout_id") and user["hangout_id"] not in place_ids:
            raise ValueError(f"{user['id']} hangout {user['hangout_id']} is not a place")
        if not user["preferences"]:
            raise ValueError(f"{user['id']} needs at least one preference")
        quote = _user_quote(user)
        remember(user["id"], "user", quote, "name", user)
        seen_tags: set[str] = set()
        for pref in user["preferences"]:
            tag = pref["tag"]
            if TAG_RE.fullmatch(tag) is None:
                raise ValueError(f"{pref['id']} tag {tag!r} is not a tag token")
            if vocabulary is not None and tag not in vocabulary:
                raise ValueError(f"{pref['id']} tag {tag!r} is not in tags.json")
            if tag in seen_tags:
                raise ValueError(f"{user['id']} repeats tag {tag}")
            seen_tags.add(tag)
            weight = pref.get("weight")
            if weight is not None:
                if not isinstance(weight, (int, float)) or not 0 < float(weight) <= 1:
                    raise ValueError(f"{pref['id']} weight must be in (0, 1]")
                pref["weight"] = float(weight)
            remember(
                pref["id"],
                "preference",
                pref["note"],
                "tag",
                {**pref, "user_id": user["id"], "user_name": user["name"]},
            )

    for event in events:
        if event["location_id"] not in place_ids:
            raise ValueError(f"{event['id']} location {event['location_id']} is not a place")
        if event.get("host_role") and event["host_role"] not in HOST_ROLES:
            raise ValueError(f"{event['id']} host_role must be one of {sorted(HOST_ROLES)}")
        if not event["tags"]:
            raise ValueError(f"{event['id']} needs tags")
        for tag in event["tags"]:
            if TAG_RE.fullmatch(tag) is None:
                raise ValueError(f"{event['id']} has a bad tag {tag!r}")
            if vocabulary is not None and tag not in vocabulary:
                raise ValueError(f"{event['id']} tag {tag!r} is not in tags.json")
        _datetime(event["starts_at"], f"{event['id']}.starts_at")
        _datetime(event["ends_at"], f"{event['id']}.ends_at")
        if event.get("posted_at"):
            _datetime(event["posted_at"], f"{event['id']}.posted_at")
        if event.get("going") is not None and not 0 <= int(event["going"]) <= int(event["capacity"]):
            raise ValueError(f"{event['id']} going exceeds capacity")
        quote = f"{event['title']}. Tag: {', '.join(event['tags'])}. {event['blurb']}"
        remember(event["id"], "event", quote, "tags", event)

    user_ids = {user["id"] for user in users}
    event_ids = {event["id"] for event in events}
    for mail in emails:
        if mail.get("received_at"):
            _datetime(mail["received_at"], f"{mail['id']}.received_at")
        if not str(mail["from"]).endswith(".example") or not str(mail["to"]).endswith(".example"):
            raise ValueError(f"{mail['id']} must use example addresses")
        for user_id in mail["related_user_ids"]:
            if user_id not in user_ids:
                raise ValueError(f"{mail['id']} names unknown user {user_id}")
        for event_id in mail["related_event_ids"]:
            if event_id not in event_ids:
                raise ValueError(f"{mail['id']} names unknown event {event_id}")
        if not mail["related_event_ids"] or not mail["related_user_ids"]:
            raise ValueError(f"{mail['id']} must link at least one student and one event")
        remember(mail["id"], "email", mail["subject"], "subject", mail)

    return Corpus(
        campus_note=places_doc.get("note", ""),
        view_box=places_doc.get("viewBox", [0, 0, 1000, 640]),
        places=places,
        users=users,
        events=events,
        emails=emails,
        by_id=by_id,
        dataset=users_doc.get("dataset", "curated"),
        vocabulary=vocabulary,
    )


class Corpus:
    def __init__(
        self,
        campus_note: str,
        view_box: list,
        places: list[dict],
        users: list[dict],
        events: list[dict],
        emails: list[dict],
        by_id: dict[str, dict],
        dataset: str,
        vocabulary: list[str] | None,
    ) -> None:
        self.campus_note = campus_note
        self.view_box = view_box
        self.places = places
        self.users = users
        self.events = events
        self.emails = emails
        self.by_id = by_id
        self.dataset = dataset
        self.vocabulary = vocabulary
        self.places_by_id = {place["id"]: place for place in places}
        self.users_by_id = {user["id"]: user for user in users}
        self.events_by_id = {event["id"]: event for event in events}
        self.mails_for: dict[tuple[str, str], list[dict]] = {}
        for mail in emails:
            for user_id in mail["related_user_ids"]:
                for event_id in mail["related_event_ids"]:
                    self.mails_for.setdefault((user_id, event_id), []).append(mail)

    def cite(self, source_id: str, field: str | None = None) -> dict:
        row = self.by_id.get(source_id)
        if row is None:
            raise KeyError(source_id)
        return {
            "source_id": source_id,
            "kind": row["kind"],
            "field": field or row["field"],
            "quote": row["quote"],
            "access": describe_access(row["kind"], row["record"])["scope"],
        }

    def public_source(self, source_id: str) -> dict:
        row = self.by_id.get(source_id)
        if row is None:
            raise KeyError(source_id)
        return {
            "source_id": source_id,
            "kind": row["kind"],
            "field": row["field"],
            "quote": row["quote"],
            "synthetic": True,
            "access": describe_access(row["kind"], row["record"]),
            "record": row["record"],
        }


def _vocabulary(overlay: Path) -> list[str] | None:
    path = overlay / "tags.json"
    if not path.exists():
        return None
    doc = _read_marked(path)
    tags = doc.get("tags")
    if not isinstance(tags, list) or not tags:
        raise ValueError(f"{path.name} has no tags")
    return list(tags)


def _normalize_user(user: dict) -> dict:
    _need(user, ("id", "name", "role", "year", "preferences"), "user")
    if not isinstance(user["preferences"], list) or not user["preferences"]:
        raise ValueError(f"{user['id']} needs at least one preference")
    prefs = []
    for raw in user["preferences"]:
        if isinstance(raw, str):
            pref_id = _pref_id(user["id"], raw)
            note = user.get("interests_text") or f"{raw} è una preferenza di {user['name']}."
            prefs.append({"id": pref_id, "tag": raw, "weight": None, "note": note})
        elif isinstance(raw, dict):
            _need(raw, ("id", "tag", "weight", "note"), f"{user['id']} preference")
            prefs.append(dict(raw))
        else:
            raise ValueError(f"{user['id']} has a preference that is not a tag or a row")
    normalized = {
        "id": user["id"],
        "name": user["name"],
        "role": user["role"],
        "year": user["year"],
        "preferences": prefs,
    }
    for key in ("program", "hometown", "languages", "bio", "interests_text", "hangout_id"):
        if key in user:
            normalized[key] = user[key]
    return normalized


def _normalize_event(event: dict) -> dict:
    if "location_id" in event and "starts_at" in event:
        _need(
            event,
            (
                "id",
                "title",
                "tags",
                "location_id",
                "starts_at",
                "ends_at",
                "capacity",
                "blurb",
            ),
            "event",
        )
        normalized = dict(event)
        normalized["starts_at"] = _datetime(event["starts_at"], f"{event['id']}.starts_at").isoformat()
        normalized["ends_at"] = _datetime(event["ends_at"], f"{event['id']}.ends_at").isoformat()
        return normalized

    _need(
        event,
        ("id", "title", "description", "tags", "location", "start", "end", "capacity", "source_id"),
        "event",
    )
    location = event["location"]
    if not isinstance(location, dict) or "building" not in location:
        raise ValueError(f"{event['id']} location needs a building")
    building = location["building"]
    if building not in BUILDING_PINS:
        raise ValueError(f"{event['id']} building {building!r} has no schematic pin")
    if event["source_id"] != event["id"]:
        raise ValueError(f"{event['id']} source_id must equal the event id")
    return {
        "id": event["id"],
        "title": event["title"],
        "tags": list(event["tags"]),
        "blurb": event["description"],
        "description": event["description"],
        "building": building,
        "location_id": BUILDING_PINS[building],
        "starts_at": _datetime(event["start"], f"{event['id']}.start").isoformat(),
        "ends_at": _datetime(event["end"], f"{event['id']}.end").isoformat(),
        "capacity": event["capacity"],
        "source_id": event["source_id"],
    }


def _normalize_email(mail: dict) -> dict:
    _need(mail, ("id", "from", "to", "subject", "body"), "email")
    normalized = dict(mail)
    if "related_user_ids" not in normalized:
        local = str(mail["to"]).split("@", 1)[0]
        normalized["related_user_ids"] = [local]
    if "related_event_ids" not in normalized:
        if "related_event_id" not in mail:
            raise ValueError(f"{mail['id']} needs related_event_id or related_event_ids")
        normalized["related_event_ids"] = [mail["related_event_id"]]
    return normalized


def _pref_id(user_id: str, tag: str) -> str:
    if not user_id.startswith("usr-"):
        raise ValueError(f"{user_id} must start with usr-")
    slug = tag.lower()
    return f"pref-{user_id.removeprefix('usr-')}-{slug}"


def _user_quote(user: dict) -> str:
    if user.get("program") and user.get("bio"):
        return f"{user['name']}, {user['program']}, anno {user['year']}. {user['bio']}"
    interest = user.get("interests_text") or ""
    return f"{user['name']}, anno {user['year']}. {interest}".strip()


def _read_marked(path: Path) -> dict:
    if not path.exists():
        raise ValueError(f"missing data file {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("synthetic") is not True:
        raise ValueError(
            f"{path.name} must be a JSON object with synthetic=true. "
            "H-OS refuses files that are not marked as invented."
        )
    return data


def _need(record: dict, keys: tuple[str, ...], where: str) -> None:
    missing = [key for key in keys if key not in record]
    if missing:
        raise ValueError(f"{where} missing {', '.join(missing)}")


def _datetime(value: str, where: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{where} is not an ISO datetime: {value}") from exc
    if parsed.tzinfo is None:
        # Team timestamps are campus-local and carry no offset. Europe/Rome
        # is the campus zone. After 25 Oct 2026 that is CET (+01).
        parsed = parsed.replace(tzinfo=ROME)
    return parsed
