#!/usr/bin/env python3
"""Combinatorial cohort in the same schema the demo loads.

The twelve students in data/users.json are written by hand so the Hack Day
story has a voice. This script shows the same records can be grown from
name parts, programs, and preference bundles. It never overwrites the
curated files. Point the app at the result with HOS_DATA_DIR.

    python data/generate.py --users 24 --events 12 --seed 20261024
    HOS_DATA_DIR=data/generated uvicorn app.main:app --port 47231
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.brain import rank_matches  # noqa: E402
from app.corpus import load_corpus  # noqa: E402

FIRST = [
    "Marta", "Andrea", "Sara", "Lucio", "Noor", "Paolo", "Irene", "Hassan",
    "Giada", "Tommaso", "Leila", "Riccardo", "Bianca", "Omar", "Chiara", "Ivan",
]
LAST = [
    "Trevisan", "Basile", "Conti", "Greco", "Neri", "Fontana", "De Luca",
    "Romano", "Gallo", "Barbieri", "Vitali", "Esposito",
]
PROGRAMS = [
    "Digital Management", "Computer Science", "Communication", "Entrepreneurship",
    "Data Analytics", "Communication Design", "Robotics", "Management",
]
BUNDLES = [
    ("sustainability", "climate", "volunteering"),
    ("ai", "coding", "robotics"),
    ("film", "journalism", "photography"),
    ("startups", "entrepreneurship", "debate"),
    ("sport", "wellness", "community"),
    ("design", "art", "photography"),
    ("data", "ai", "coding"),
    ("music", "film", "community"),
    ("fashion", "sustainability", "art"),
    ("languages", "debate", "community"),
    ("food", "community", "sustainability"),
    ("robotics", "coding", "sport"),
]
# First tag of a bundle picks a place that exists in data/places.json.
PLACE_FOR = {
    "sustainability": "loc-orto",
    "ai": "loc-lab",
    "film": "loc-corte",
    "startups": "loc-startup",
    "sport": "loc-campo",
    "design": "loc-library",
    "data": "loc-college",
    "music": "loc-serra",
    "fashion": "loc-residenze",
    "languages": "loc-college",
    "food": "loc-mensa",
    "robotics": "loc-lab",
}
TITLES = {
    "sustainability": "Turno verde: {n}",
    "ai": "Banco modelli: {n}",
    "film": "Proiezione di cohort: {n}",
    "startups": "Pitch lampo: {n}",
    "sport": "Uscita all'argine: {n}",
    "design": "Parete libera: {n}",
    "data": "Grafico singolo: {n}",
    "music": "Set corto: {n}",
    "fashion": "Rammendo aperto: {n}",
    "languages": "Tavolo misto: {n}",
    "food": "Cena di cohort: {n}",
    "robotics": "Motori accesi: {n}",
}
# Tuesday-style stamps after the Hack Day clock, cycling through the week.
STAMPS = [
    "2026-10-25T10:00:00+01:00",
    "2026-10-26T18:00:00+01:00",
    "2026-10-27T17:30:00+01:00",
    "2026-10-28T19:00:00+01:00",
    "2026-10-29T18:30:00+01:00",
    "2026-10-30T09:00:00+01:00",
]


def build(users_n: int, events_n: int, seed: int) -> tuple[dict, dict, dict]:
    if not 1 <= users_n <= 80:
        raise SystemExit("--users must be between 1 and 80")
    if not 1 <= events_n <= 40:
        raise SystemExit("--events must be between 1 and 40")
    rng = random.Random(seed)
    names = [(first, last) for first in FIRST for last in LAST]
    rng.shuffle(names)
    if users_n > len(names):
        raise SystemExit(f"only {len(names)} name combinations")

    hangouts = list(PLACE_FOR.values())
    users = []
    for index, (first, last) in enumerate(names[:users_n], start=1):
        bundle = BUNDLES[(index - 1) % len(BUNDLES)]
        prefs = []
        for slot, tag in enumerate(bundle):
            base = (0.92, 0.7, 0.46)[slot]
            weight = round(min(0.99, max(0.2, base + rng.uniform(-0.04, 0.04))), 2)
            prefs.append(
                {
                    "id": f"pref-gen-{index:02d}-{tag}",
                    "tag": tag,
                    "weight": weight,
                    "note": f"Peso generato per il tag {tag}. Cohort sintetica, non è una preferenza raccolta.",
                }
            )
        users.append(
            {
                "id": f"usr-gen-{index:02d}",
                "name": f"{first} {last}",
                "role": "student",
                "program": PROGRAMS[(index - 1) % len(PROGRAMS)],
                "year": (index % 3) + 1,
                "hometown": "Cohort",
                "languages": ["it", "en"],
                "hangout_id": hangouts[(index - 1) % len(hangouts)],
                "bio": "Profilo sintetico generato per provare lo schema. Non è una persona reale.",
                "preferences": prefs,
            }
        )

    events = []
    for index in range(1, events_n + 1):
        bundle = BUNDLES[(index - 1) % len(BUNDLES)]
        lead = bundle[0]
        start = STAMPS[(index - 1) % len(STAMPS)]
        # End ninety minutes later by rewriting the hour. Stamps are on the hour or half.
        end = _plus_minutes(start, 90)
        events.append(
            {
                "id": f"evt-gen-{index:02d}",
                "title": TITLES[lead].format(n=index),
                "tags": list(bundle),
                "location_id": PLACE_FOR[lead],
                "starts_at": start,
                "ends_at": end,
                "posted_at": "2026-10-22T12:00:00+02:00",
                "host": "Cohort sintetica",
                "host_role": "studenti",
                "capacity": 20,
                "going": (index * 3) % 12,
                "blurb": "Evento generato per combinazione di tag e luogo. Non è in programma al campus.",
            }
        )

    emails = []
    events_by_tag: dict[str, list[dict]] = {}
    for event in events:
        for tag in event["tags"]:
            events_by_tag.setdefault(tag, []).append(event)
    for user in users:
        strongest = max(user["preferences"], key=lambda pref: pref["weight"])
        pool = events_by_tag.get(strongest["tag"], [])
        if not pool:
            continue
        event = pool[(int(user["id"][-2:]) - 1) % len(pool)]
        number = user["id"][-2:]
        emails.append(
            {
                "id": f"mail-gen-{number}",
                "from": "cohort@bacheca.example",
                "to": f"{user['id']}@studenti.example",
                "subject": f"Segnale generato per {user['name'].split()[0]}",
                "body": (
                    f"Mail mock della cohort. Collega {user['name']} all'evento "
                    f"«{event['title']}». Non è stata spedita a nessuno."
                ),
                "received_at": "2026-10-23T10:00:00+02:00",
                "related_user_ids": [user["id"]],
                "related_event_ids": [event["id"]],
            }
        )

    users_doc = {
        "synthetic": True,
        "note": "Cohort generata da data/generate.py. Persone inventate.",
        "users": users,
    }
    events_doc = {
        "synthetic": True,
        "note": "Eventi generati da data/generate.py. Non sono nel calendario reale.",
        "events": events,
    }
    emails_doc = {
        "synthetic": True,
        "note": "Mail mock generate. Indirizzi su .example. Nessun invio.",
        "emails": emails,
    }
    return users_doc, events_doc, emails_doc


def _plus_minutes(stamp: str, minutes: int) -> str:
    hour = int(stamp[11:13])
    minute = int(stamp[14:16])
    minute += minutes
    hour += minute // 60
    minute = minute % 60
    return f"{stamp[:11]}{hour:02d}:{minute:02d}{stamp[16:]}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic H-OS cohort.")
    parser.add_argument("--users", type=int, default=24)
    parser.add_argument("--events", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20261024)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "generated")
    args = parser.parse_args()
    out = args.out.resolve()
    curated = (ROOT / "data").resolve()
    if out == curated:
        raise SystemExit("refusing to overwrite the curated data/ files. Choose another --out.")

    users_doc, events_doc, emails_doc = build(args.users, args.events, args.seed)
    out.mkdir(parents=True, exist_ok=True)
    for name, doc in ("users.json", users_doc), ("events.json", events_doc), ("emails.json", emails_doc):
        (out / name).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    corpus = load_corpus(out)
    sample = rank_matches(corpus, corpus.users[0]["id"], limit=1)
    top = sample["matches"][0]
    print(
        f"wrote {len(corpus.users)} users, {len(corpus.events)} events, "
        f"{len(corpus.emails)} emails → {out}"
    )
    print(
        f"sample {sample['user_id']} → {top['event_id']} "
        f"score {top['score']} sources {', '.join(item['source_id'] for item in top['citations'][:6])}"
    )


if __name__ == "__main__":
    main()
