"""Match a student's preferences to campus events, and cite every claim.

Pattern from GBrain (https://github.com/garrytan/gbrain): the brain answers
with the source ids that support the claim. GBrain is not installed.

Baseline score is Jaccard on the tag sets. The alternate is the overlap
coefficient. A weighted formula remains for preference rows that carry a weight.
"""

from __future__ import annotations

from datetime import datetime

from app.corpus import Corpus, demo_now
from app.narrate import narrate
from app.scoring import (
    FORMULAS,
    SOON_HOURS,
    company_floor,
    jaccard_score,
    overlap_score,
    propose_floor,
    score_overlap,
)


def match_user(
    corpus: Corpus,
    user_id: str,
    limit: int = 4,
    now: datetime | None = None,
    formula: str = "jaccard",
) -> dict:
    result = rank_matches(corpus, user_id, limit=limit, now=now, formula=formula)
    mode = narrate(result["matches"], set(corpus.by_id))
    result["display_by"] = mode
    return result


def rank_matches(
    corpus: Corpus,
    user_id: str,
    limit: int = 4,
    now: datetime | None = None,
    formula: str = "jaccard",
) -> dict:
    if formula not in FORMULAS:
        raise ValueError(f"formula must be one of {', '.join(FORMULAS)}")
    user = corpus.users_by_id.get(user_id)
    if user is None:
        raise KeyError(user_id)
    if formula == "weighted" and any(pref.get("weight") is None for pref in user["preferences"]):
        raise ValueError(
            "formula weighted needs a weight on every preference. "
            "This dataset stores tags only. Use jaccard or overlap."
        )
    clock = now or demo_now()
    ranked = [
        row
        for row in (_score_pair(corpus, user, event, clock, formula) for event in corpus.events)
        if row
    ]
    ranked.sort(key=lambda row: (-row["score"], row["starts_at"], row["event_id"]))
    matches = ranked[:limit]
    for match in matches:
        _attach_company(corpus, user, match, clock, formula)
    source_ids: list[str] = []
    seen: set[str] = set()
    for match in matches:
        for citation in match["citations"]:
            if citation["source_id"] not in seen:
                seen.add(citation["source_id"])
                source_ids.append(citation["source_id"])
    return {
        "user_id": user["id"],
        "user_name": user["name"],
        "demo_now": clock.isoformat(),
        "display_by": "deterministic",
        "limit": limit,
        "method": {
            "name": formula,
            "formula": FORMULAS[formula],
            "soon_hours": SOON_HOURS,
            "propose_floor": propose_floor(formula),
            "company_min": company_floor(formula),
            "demo_now": clock.isoformat(),
        },
        "source_ids": source_ids,
        "matches": matches,
    }


def _score_pair(corpus: Corpus, user: dict, event: dict, now: datetime, formula: str) -> dict | None:
    event_tags = set(event["tags"])
    matched_prefs = [pref for pref in user["preferences"] if pref["tag"] in event_tags]
    if not matched_prefs:
        return None
    matched_prefs = sorted(matched_prefs, key=lambda pref: (-(pref["weight"] or 0), pref["id"]))
    prefs = {pref["tag"] for pref in user["preferences"]}
    inter = prefs & event_tags
    union = prefs | event_tags
    start = datetime.fromisoformat(event["starts_at"])
    hours = (start - now).total_seconds() / 3600
    mails = corpus.mails_for.get((user["id"], event["id"]), [])
    weights = [pref["weight"] for pref in matched_prefs]
    matched_weight = None
    if formula == "jaccard":
        score = jaccard_score(prefs, event_tags)
    elif formula == "overlap":
        score = overlap_score(prefs, event_tags)
    else:
        matched_weight = round(sum(weights), 4)
        score = score_overlap(matched_weight, hours, bool(mails))
    if score <= 0:
        return None
    place = corpus.places_by_id[event["location_id"]]
    explanation, citations = _explain(corpus, user, event, place, matched_prefs, mails, start)
    return {
        "event_id": event["id"],
        "user_id": user["id"],
        "user_name": user["name"],
        "title": event["title"],
        "formula": formula,
        "score": score,
        "intersection": len(inter),
        "union": len(union),
        "pref_count": len(prefs),
        "tag_count": len(event_tags),
        "matched_weight": matched_weight,
        "hours_until": round(hours, 2),
        "soon": 0 <= hours <= SOON_HOURS,
        "mailed": bool(mails),
        "email_ids": [mail["id"] for mail in mails],
        "pref_ids": [pref["id"] for pref in matched_prefs],
        "overlapping_tags": [pref["tag"] for pref in matched_prefs],
        "explanation": explanation,
        "display_text": explanation,
        "display_by": "deterministic",
        "citations": citations,
        "company": [],
        "starts_at": event["starts_at"],
        "ends_at": event["ends_at"],
        "location_id": place["id"],
        "location_name": place["name"],
        "location_zone": place["zone"],
        "building": event.get("building"),
        "x": place["x"],
        "y": place["y"],
        "host": event.get("host"),
        "host_role": event.get("host_role"),
        "tags": list(event["tags"]),
        "blurb": event["blurb"],
        "capacity": event["capacity"],
        "going": event.get("going"),
    }


def _attach_company(corpus: Corpus, user: dict, match: dict, now: datetime, formula: str) -> None:
    event = corpus.events_by_id[match["event_id"]]
    floor = company_floor(formula)
    company = []
    for other in corpus.users:
        if other["id"] == user["id"]:
            continue
        if formula == "weighted" and any(pref.get("weight") is None for pref in other["preferences"]):
            continue
        other_row = _score_pair(corpus, other, event, now, formula)
        if other_row is None or other_row["score"] < floor:
            continue
        named_prefs = other_row["pref_ids"][:3]
        pref_text = ", ".join(named_prefs)
        sentence = (
            f"Anche {other['name']} ({other['id']}) arriva a {other_row['score']:.2f} "
            f"per {pref_text}."
        )
        citations = [corpus.cite(other["id"], "preferences")]
        citations.extend(corpus.cite(pref_id, "tag") for pref_id in named_prefs)
        missing = [item["source_id"] for item in citations if item["source_id"] not in sentence]
        if missing:
            raise RuntimeError(f"company sentence dropped {missing}")
        company.append(
            {
                "user_id": other["id"],
                "name": other["name"],
                "score": other_row["score"],
                "pref_ids": named_prefs,
                "sentence": sentence,
                "citations": citations,
            }
        )
    company.sort(key=lambda item: (-item["score"], item["user_id"]))
    company = company[:2]
    if not company:
        return
    extra = " ".join(item["sentence"] for item in company)
    match["explanation"] = f"{match['explanation']} {extra}"
    match["display_text"] = match["explanation"]
    for item in company:
        match["citations"].extend(item["citations"])
    match["company"] = company
    _assert_cited(match["explanation"], match["citations"])


def _explain(corpus, user, event, place, matched_prefs, mails, start: datetime) -> tuple[str, list[dict]]:
    citations = [corpus.cite(user["id"], "preferences")]
    pref_bits = []
    for pref in matched_prefs:
        citations.append(corpus.cite(pref["id"], "tag"))
        if pref.get("weight") is None:
            pref_bits.append(f"{pref['tag']} ({pref['id']})")
        else:
            pref_bits.append(f"{pref['tag']} (peso {pref['weight']:.2f}, {pref['id']})")
    citations.append(corpus.cite(event["id"], "tags"))
    citations.append(corpus.cite(place["id"], "name"))
    when = _format_when(start)
    if event.get("building"):
        where = f"{event['building']}, pin dello schema {place['name']} ({place['id']})"
    else:
        where = f"{place['name']} ({place['id']})"
    parts = [
        f"{user['name']} ({user['id']}) ha tra le preferenze {', '.join(pref_bits)}.",
        (
            f"{event['title']} ({event['id']}) porta i tag {', '.join(event['tags'])} "
            f"e si tiene a {where} il {when}."
        ),
    ]
    if mails:
        mail = mails[0]
        citations.append(corpus.cite(mail["id"], "subject"))
        parts.append(
            f"La mail {mail['id']} («{mail['subject']}») nomina {event['id']} per {user['id']}."
        )
    text = " ".join(parts)
    _assert_cited(text, citations)
    return text, citations


def _assert_cited(text: str, citations: list[dict]) -> None:
    missing = [item["source_id"] for item in citations if item["source_id"] not in text]
    if missing:
        raise RuntimeError(f"explanation dropped sources: {missing}")


def _format_when(moment: datetime) -> str:
    from zoneinfo import ZoneInfo

    giorni = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
    mesi = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
    local = moment.astimezone(ZoneInfo("Europe/Rome"))
    return f"{giorni[local.weekday()]} {local.day} {mesi[local.month - 1]}, {local:%H:%M}"
