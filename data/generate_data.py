"""Team corpus generator for the Hack Day snapshot.

The checked-in files in data/ are this script at seed 20261024 with 40
students and 80 events. Preferences are 3 to 6 tags drawn from a vocabulary
of 25. That is a design space of C(25,3)+C(25,4)+C(25,5)+C(25,6) = 245180
profiles. The script writes the students you ask for. It does not enumerate
that space.

Timestamps are naive campus-local datetimes. The loader attaches Europe/Rome.
Buildings have no coordinates. The desk maps them onto the schematic in
data/places.json.

Default --out is data/generated so a run does not overwrite the snapshot.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 20261024
TAGS = [
    "AI",
    "data-science",
    "programmazione",
    "robotica",
    "cybersecurity",
    "design",
    "UX-UI",
    "arte",
    "fotografia",
    "cinema",
    "musica",
    "teatro",
    "sport",
    "fitness",
    "calcio",
    "basket",
    "running",
    "startup",
    "imprenditoria",
    "marketing",
    "finanza",
    "sostenibilita",
    "ambiente",
    "gaming",
    "networking",
]
LOCATIONS = ["La Serra", "Building 1", "Building 2", "Building 3", "Building 4", "Building 5"]
FIRST = [
    "Alex", "Andrea", "Sam", "Nico", "Luca", "Mia", "Noa", "Eli", "Ari", "Leo",
    "Teo", "Sasha", "Vale", "Dani", "Rene", "Chris", "Toni", "Ema", "Gio", "Robin",
]
LAST = [
    "Rossi", "Bianchi", "Verdi", "Conti", "Moretti", "Fontana", "Marini", "Costa",
    "Ricci", "Galli", "Serra", "Ferri", "Greco", "Leoni", "Riva", "Villa", "Neri",
    "Colombo", "Moro", "Fiore",
]
TITLES = [
    "Laboratorio pratico",
    "Meetup studenti",
    "Workshop creativo",
    "Sfida a squadre",
    "Talk con ospiti",
    "Sessione introduttiva",
    "Community night",
    "Progetto collaborativo",
    "Mini hackathon",
    "Open lab",
]
DESCRIPTIONS = [
    "Un incontro aperto agli studenti per sperimentare, confrontarsi e conoscere nuove persone.",
    "Attività guidate e momenti di networking per condividere idee e interessi.",
    "Un evento interattivo con esercizi di gruppo e discussione finale.",
    "Esperienze pratiche per imparare insieme e costruire connessioni nel campus.",
]
PREFERENCE_SPACE = sum(math.comb(len(TAGS), k) for k in range(3, 7))
SCHEMA = {
    "users.json": {
        "required": ["id", "name", "role", "preferences", "year", "interests_text"],
        "types": {
            "id": "string",
            "name": "string",
            "role": "student",
            "preferences": "string[] (3-6)",
            "year": "integer",
            "interests_text": "string",
        },
    },
    "events.json": {
        "required": ["id", "title", "description", "tags", "location", "start", "end", "capacity", "source_id"],
        "types": {
            "id": "string",
            "title": "string",
            "description": "string",
            "tags": "string[] (2-5)",
            "location": {"building": "string", "lat": "number (optional)", "lng": "number (optional)"},
            "start": "ISO 8601 local datetime",
            "end": "ISO 8601 local datetime",
            "capacity": "integer",
            "source_id": "string",
        },
    },
    "emails.json": {
        "required": ["id", "from", "to", "subject", "body", "related_event_id"],
        "types": {
            "id": "string",
            "from": "string",
            "to": "string",
            "subject": "string",
            "body": "string",
            "related_event_id": "string",
        },
    },
}


def build(users_n: int = 40, events_n: int = 80, seed: int = SEED):
    if not 1 <= users_n <= 80:
        raise SystemExit("--users must be between 1 and 80")
    if not 1 <= events_n <= 120:
        raise SystemExit("--events must be between 1 and 120")
    rng = random.Random(seed)
    users = []
    for i in range(1, users_n + 1):
        prefs = sorted(rng.sample(TAGS, rng.randint(3, 6)))
        users.append(
            {
                "id": f"usr-{i:03d}",
                "name": f"{FIRST[(i - 1) % len(FIRST)]} {LAST[(i - 1) // len(FIRST)]}",
                "role": "student",
                "preferences": prefs,
                "year": rng.randint(1, 3),
                "interests_text": (
                    f"Mi interessano {', '.join(prefs[:3])} e vorrei conoscere "
                    "altri studenti con passioni simili."
                ),
            }
        )
    events = []
    base = datetime(2026, 10, 26, 16, 0)
    for i in range(1, events_n + 1):
        tags = sorted(rng.sample(TAGS, rng.randint(2, 5)))
        start = base + timedelta(days=(i - 1) // 3, hours=((i - 1) % 3) * 2)
        end = start + timedelta(minutes=rng.choice([60, 90, 120]))
        events.append(
            {
                "id": f"evt-{i:03d}",
                "title": f"{TITLES[(i - 1) % len(TITLES)]}: {tags[0]}",
                "description": f"{DESCRIPTIONS[(i - 1) % len(DESCRIPTIONS)]} Focus: {', '.join(tags)}.",
                "tags": tags,
                "location": {"building": LOCATIONS[(i - 1) % len(LOCATIONS)]},
                "start": start.isoformat(timespec="seconds"),
                "end": end.isoformat(timespec="seconds"),
                "capacity": rng.choice([15, 20, 25, 30, 40, 50, 60]),
                "source_id": f"evt-{i:03d}",
            }
        )
    emails = []
    for i in range(1, min(13, users_n + 1, events_n + 1)):
        ev = events[i - 1]
        emails.append(
            {
                "id": f"mail-{i:03d}",
                "from": "eventi@campus.example",
                "to": f"usr-{i:03d}@students.example",
                "subject": f"Invito: {ev['title']}",
                "body": (
                    f"Ciao! Ti segnaliamo {ev['title']} presso {ev['location']['building']}. "
                    "Vuoi partecipare?"
                ),
                "related_event_id": ev["id"],
            }
        )
    return users, events, emails


def _wrap(key: str, rows, seed: int) -> dict:
    return {
        "synthetic": True,
        "dataset": "team",
        "seed": seed,
        "preference_space": {
            "tags": len(TAGS),
            "profile_sizes": [3, 4, 5, 6],
            "theoretical_profiles": PREFERENCE_SPACE,
            "note": (
                "Theoretical profiles are the combinations of 3 to 6 distinct tags. "
                "This file materializes one cohort, not that space."
            ),
        },
        key: rows,
    }


def write_corpus(out: Path, users_n: int, events_n: int, seed: int) -> None:
    if out.resolve() == Path(__file__).resolve().parent and out.name == "data":
        # Allowed: the snapshot directory. We only replace the team files.
        pass
    out.mkdir(parents=True, exist_ok=True)
    users, events, emails = build(users_n, events_n, seed)
    _dump(out / "users.json", _wrap("users", users, seed))
    _dump(out / "events.json", _wrap("events", events, seed))
    _dump(out / "emails.json", _wrap("emails", emails, seed))
    _dump(out / "tags.json", _wrap("tags", list(TAGS), seed))
    _dump(
        out / "schema.json",
        {
            "synthetic": True,
            "dataset": "team",
            "note": "Field contract for the team JSON. Not loaded by the desk.",
            "files": SCHEMA,
        },
    )
    print(
        f"wrote {len(users)} users, {len(events)} events, {len(emails)} emails "
        f"to {out} (seed {seed}, theoretical profiles {PREFERENCE_SPACE})"
    )


def _dump(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the team synthetic campus cohort.")
    parser.add_argument("--out", default="data/generated", help="Directory for the JSON files.")
    parser.add_argument("--users", type=int, default=40)
    parser.add_argument("--events", type=int, default=80)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    write_corpus(out, args.users, args.events, args.seed)


if __name__ == "__main__":
    main()
