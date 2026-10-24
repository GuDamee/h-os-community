"""One tick, one proposal. Nothing reaches the bacheca without a human decision.

Pattern from OpenInstinct (https://github.com/Merit-Systems/OpenInstinct):
a proactive agent may prepare an action, and a person still has to approve
before it sends or spends. OpenInstinct is not installed. Here the action is
a bacheca notice, and approve is the only way it posts.
"""

from __future__ import annotations

from datetime import datetime

from app.brain import rank_matches
from app.corpus import Corpus, demo_now
from app.narrate import narrate
from app.scoring import FORMULAS, SOON_HOURS, propose_floor
from app.store import Store, new_id


def tick(
    corpus: Corpus,
    store: Store,
    user_id: str | None = None,
    now: datetime | None = None,
    formula: str = "jaccard",
) -> dict:
    if formula not in FORMULAS:
        raise ValueError(f"formula must be one of {', '.join(FORMULAS)}")
    clock = now or demo_now()
    floor = propose_floor(formula)
    if user_id is not None and user_id not in corpus.users_by_id:
        raise KeyError(user_id)
    candidates = []
    users = [corpus.users_by_id[user_id]] if user_id else list(corpus.users)
    for user in users:
        ranked = rank_matches(corpus, user["id"], limit=8, now=clock, formula=formula)
        for match in ranked["matches"]:
            if match["score"] < floor:
                continue
            if store.get_pair(user["id"], match["event_id"]):
                continue
            candidates.append((user, match))
            break
    if not candidates:
        return {
            "status": "idle",
            "user_id": user_id,
            "reason": _idle_reason(corpus, store, user_id, clock, formula),
        }
    candidates.sort(key=lambda item: (-item[1]["score"], item[1]["starts_at"], item[0]["id"]))
    user, match = candidates[0]
    narrate([match], set(corpus.by_id))
    trace = _trace(corpus, user, match, clock)
    action = store.insert_action(
        user_id=user["id"],
        event_id=match["event_id"],
        signal=trace["event"]["signal"],
        score=match["score"],
        trace=trace,
    )
    return {
        "status": "proposed",
        "action": action,
        "roles": ["librarian", "campus_brain", "student_agent", "human"],
        "patterns": ["gbrain", "cognee", "pipeshub", "paperclip", "langgraph", "openinstinct"],
        "inspiration_installed": False,
        "requires_human": True,
    }


def approve(corpus: Corpus, store: Store, action_id: str, decision: str) -> dict:
    action = store.get(action_id)
    if action is None:
        raise KeyError(action_id)
    if decision not in {"approve", "dismiss"}:
        raise ValueError(decision)
    target = "approved" if decision == "approve" else "dismissed"
    if action["status"] == target:
        return {"action": action, "notice": action["notice"], "idempotent": True}
    if action["status"] != "pending":
        raise RuntimeError(f"action {action_id} is already {action['status']}")
    notice = None
    if target == "approved":
        notice = _notice(corpus, action)
    updated = store.decide(action_id, target, notice)
    return {"action": updated, "notice": updated["notice"], "idempotent": False}


def _idle_reason(
    corpus: Corpus,
    store: Store,
    user_id: str | None,
    now: datetime,
    formula: str = "jaccard",
) -> str:
    who = user_id or "gli studenti"
    floor = propose_floor(formula)
    ranked_users = [corpus.users_by_id[user_id]] if user_id else corpus.users
    above = 0
    blocked = 0
    for user in ranked_users:
        ranked = rank_matches(corpus, user["id"], limit=8, now=now, formula=formula)
        for match in ranked["matches"]:
            if match["score"] < floor:
                continue
            above += 1
            if store.get_pair(user["id"], match["event_id"]):
                blocked += 1
    if above == 0:
        return (
            f"Nessun evento supera {floor:.2f} ({formula}) per {who}. "
            "L'agente non inventa un invito sotto soglia."
        )
    return (
        f"Le coppie sopra {floor:.2f} ({formula}) per {who} hanno già un esito "
        f"({blocked} su {above}). Non propongo due volte la stessa coppia."
    )


def _trace(corpus: Corpus, user: dict, match: dict, now: datetime) -> dict:
    event = corpus.events_by_id[match["event_id"]]
    place = corpus.places_by_id[match["location_id"]]
    signal, event_summary, event_ids = _event_step(corpus, user, match, event)
    event_cites = [corpus.cite(source_id) for source_id in event_ids]
    _assert(event_summary, event_cites)

    pref_bits = ", ".join(
        (
            f"{pref['tag']} ({pref['id']})"
            if pref.get("weight") is None
            else f"{pref['tag']} {pref['weight']:.2f} ({pref['id']})"
        )
        for pref in user["preferences"]
        if pref["id"] in match["pref_ids"]
    )
    anno = f", anno {user['year']}" if user.get("year") not in (None, "") else ""
    if user.get("program"):
        who = f"{user['name']} ({user['id']}), {user['program']}{anno}"
    else:
        who = f"{user['name']} ({user['id']}){anno}"
    where = place["name"]
    if event.get("building"):
        where = f"{event['building']}, pin {place['name']}"
    host_line = ""
    if event.get("host"):
        host_line = f" Organizza {event['host']} (ruolo {event['host_role']})."
    if event.get("going") is not None:
        seats = f" Nel dato sintetico i posti segnati sono {event['going']} su {event['capacity']}."
    else:
        seats = f" Capienza nel dataset: {event['capacity']}. Il file non dice quanti posti sono già presi."
    context_summary = (
        f"Contesto di {who}. "
        f"Preferenze usate: {pref_bits}. "
        f"{event['title']} ({event['id']}) è a {where} ({place['id']})."
        f"{host_line}{seats}"
    )
    context_cites = [corpus.cite(user["id"], "preferences")]
    context_cites.extend(corpus.cite(pref_id, "tag") for pref_id in match["pref_ids"])
    context_cites.append(corpus.cite(event["id"], "blurb"))
    context_cites.append(corpus.cite(place["id"], "name"))
    _assert(context_summary, context_cites)

    formula = match.get("formula") or "jaccard"
    floor = propose_floor(formula)
    if match["email_ids"] and formula == "weighted":
        mail_line = f"La mail {match['email_ids'][0]} entra nel punteggio."
    elif match["email_ids"]:
        mail_line = (
            f"La mail {match['email_ids'][0]} collega la coppia ed è citata. "
            f"Non modifica lo score {formula}."
        )
    else:
        mail_line = "Nessuna mail collega questa coppia."
    company_line = ""
    company_cites = []
    if match["company"]:
        other = match["company"][0]
        company_line = (
            f" {other['name']} ({other['user_id']}) è a {other['score']:.2f} sullo stesso evento. "
            "Questo tic non avvisa anche quella persona."
        )
        company_cites.append(corpus.cite(other["user_id"], "preferences"))
    if formula == "weighted":
        score_line = (
            f"La somma dei pesi allineati è {match['matched_weight']:.2f} "
            f"({', '.join(match['pref_ids'])})."
        )
    else:
        score_line = (
            f"Tag in comune {match['intersection']} "
            f"({', '.join(match['pref_ids'])})."
        )
    reasoning_summary = (
        f"Formula {formula}. Punteggio {match['score']:.2f} su {event['id']}. "
        f"{score_line} "
        f"Soglia per proporre: {floor:.2f}. Finestra tempo del segnale: {SOON_HOURS} ore dall'orologio demo. "
        f"{mail_line}{company_line} Non pubblico: manca l'approvazione di una persona."
    )
    reasoning_cites = [corpus.cite(pref_id, "tag") for pref_id in match["pref_ids"]]
    reasoning_cites.extend(company_cites)
    if match["email_ids"]:
        reasoning_cites.append(corpus.cite(match["email_ids"][0], "subject"))
    reasoning_cites.append(corpus.cite(event["id"], "starts_at"))
    _assert(reasoning_summary, reasoning_cites)

    draft = match["display_text"]
    action_summary = (
        f"Bozza per {user['name']} ({user['id']}) su {event['id']}: {draft} "
        "Stato: pending. Canale: bacheca. Nessun messaggio esce da H-OS finché una persona non approva."
    )
    action_cites = [corpus.cite(user["id"], "name"), corpus.cite(event["id"], "title")]
    _assert(action_summary, action_cites)

    return {
        "event": {"step": "EVENT", "signal": signal, "summary": event_summary, "citations": event_cites},
        "context": {"step": "CONTEXT", "summary": context_summary, "citations": context_cites},
        "reasoning": {
            "step": "REASONING",
            "summary": reasoning_summary,
            "draft": draft,
            "citations": reasoning_cites,
        },
        "action": {
            "step": "ACTION",
            "summary": action_summary,
            "kind": "bacheca_notice",
            "status": "pending",
            "requires_human": True,
            "delivered_externally": False,
            "citations": action_cites,
        },
    }


def _event_step(corpus: Corpus, user: dict, match: dict, event: dict) -> tuple[str, str, list[str]]:
    when = match["starts_at"]
    hours = match["hours_until"]
    if match["mailed"]:
        mail = corpus.by_id[match["email_ids"][0]]["record"]
        received = f", ricevuta {mail['received_at']}," if mail.get("received_at") else ""
        summary = (
            f"Segnale inbox_hint. La mail {mail['id']} («{mail['subject']}»){received} "
            f"collega {user['id']} a {event['id']}. "
            f"L'evento inizia {when}, tra {hours:.0f} ore rispetto all'orologio demo."
        )
        return "inbox_hint", summary, [mail["id"], event["id"], user["id"]]
    if match["soon"]:
        summary = (
            f"Segnale event_soon. {event['id']} inizia {when}, tra {hours:.0f} ore "
            f"dall'orologio demo, dentro la finestra di {SOON_HOURS} ore. "
            f"Nessuna mail mock collega {user['id']} a questo evento: il segnale è il tempo."
        )
        return "event_soon", summary, [event["id"], user["id"]]
    summary = (
        f"Segnale preference_overlap. {event['id']} non è nelle prossime {SOON_HOURS} ore "
        f"e nessuna mail mock lo collega a {user['id']}, ma i tag coincidono e il punteggio "
        f"resta sopra soglia. Inizio: {when}."
    )
    return "preference_overlap", summary, [event["id"], user["id"]]


def _notice(corpus: Corpus, action: dict) -> dict:
    user = corpus.users_by_id[action["user_id"]]
    event = corpus.events_by_id[action["event_id"]]
    place = corpus.places_by_id[event["location_id"]]
    draft = action["trace"]["reasoning"].get("draft") or action["trace"]["action"]["summary"]
    notice_id = new_id("note")
    text = (
        f"{user['name']}, {event['title']} — {event['starts_at']} a {place['name']} ({place['id']}). "
        f"{draft} Avviso {notice_id} approvato da una persona. Nessuna email è stata inviata."
    )
    citations = []
    seen = set()
    for step in ("event", "context", "reasoning", "action"):
        for citation in action["trace"][step]["citations"]:
            if citation["source_id"] in seen:
                continue
            seen.add(citation["source_id"])
            citations.append(citation)
    citations.append(corpus.cite(place["id"], "name"))
    if place["id"] not in text:
        raise RuntimeError("notice dropped the place id")
    return {
        "id": notice_id,
        "action_id": action["id"],
        "user_id": user["id"],
        "user_name": user["name"],
        "event_id": event["id"],
        "event_title": event["title"],
        "location_id": place["id"],
        "location_name": place["name"],
        "starts_at": event["starts_at"],
        "text": text,
        "channel": "bacheca",
        "delivered_externally": False,
        "citations": citations,
        "synthetic": True,
    }


def _assert(text: str, citations: list[dict]) -> None:
    missing = [item["source_id"] for item in citations if item["source_id"] not in text]
    if missing:
        raise RuntimeError(f"trace dropped sources: {missing} in {text}")
