"""Local desk identity. Not Canvas, not Pronote, and not a password store.

The signed-up student lives in sqlite plus the browser. Likes become the
preference set the brain already scores. The cohort JSON is not rewritten.
"""

from __future__ import annotations

import re

from app.corpus import TAG_RE, Corpus, _pref_id

DESK_ID = "usr-desk"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")


def name_from_email(email: str) -> tuple[str, str]:
    """alex@ → Alex. alex.rossi@ → Alex, Rossi. The form does not ask for a name."""
    local = email.split("@", 1)[0]
    words: list[str] = []
    for part in re.split(r"[._\-]+", local):
        cleaned = re.sub(r"[^0-9A-Za-zÀ-ÿ]", "", part)
        if cleaned:
            words.append(cleaned[:1].upper() + cleaned[1:].lower())
    if not words:
        return "Studente", ""
    if len(words) == 1:
        return words[0], ""
    return words[0], " ".join(words[1:])


def display_name(profile: dict) -> str:
    parts = [str(profile.get("nome") or "").strip(), str(profile.get("cognome") or "").strip()]
    return " ".join(part for part in parts if part) or "Studente"


def normalize_profile(raw: dict, vocabulary: list[str] | None) -> dict:
    email = str(raw.get("email", "")).strip()
    if EMAIL_RE.fullmatch(email) is None:
        raise ValueError("L'email deve contenere @. Il dominio può essere finto.")
    nickname = " ".join(str(raw.get("nickname") or "").split())
    nome = " ".join(str(raw.get("nome", "")).split())
    cognome = " ".join(str(raw.get("cognome", "")).split())
    if nickname:
        if not 2 <= len(nickname) <= 40:
            raise ValueError("Il nickname deve avere tra 2 e 40 caratteri.")
        nome = nickname
        if not str(raw.get("cognome") or "").strip():
            cognome = ""
    elif not nome and not cognome:
        nome, cognome = name_from_email(email)
    elif not nome:
        nome = name_from_email(email)[0]
    likes = list(raw.get("likes") or [])
    dislikes = list(raw.get("dislikes") or [])
    if not likes:
        raise ValueError("Serve almeno un mi piace per abbinare gli eventi.")
    if len(set(likes)) != len(likes) or len(set(dislikes)) != len(dislikes):
        raise ValueError("Tag ripetuto.")
    if set(likes) & set(dislikes):
        raise ValueError("Uno stesso tag non può essere insieme un mi piace e uno scarto.")
    allowed = set(vocabulary) if vocabulary is not None else None
    for tag in [*likes, *dislikes]:
        if not isinstance(tag, str) or TAG_RE.fullmatch(tag) is None:
            raise ValueError(f"Tag non valido: {tag!r}")
        if allowed is not None and tag not in allowed:
            raise ValueError(f"{tag} non è nel vocabolario di tags.json.")
    return {
        "id": DESK_ID,
        "nome": nome,
        "cognome": cognome,
        "email": email,
        "canvas_id": str(raw.get("canvas_link") or raw.get("canvas_id") or "").strip(),
        "pronote_id": str(raw.get("pronote_link") or raw.get("pronote_id") or "").strip(),
        "likes": likes,
        "dislikes": dislikes,
    }


def public_desk(profile: dict) -> dict:
    return {
        "id": DESK_ID,
        "name": display_name(profile),
        "nickname": profile["nome"],
        "nome": profile["nome"],
        "cognome": profile["cognome"],
        "role": "student",
        "email": profile["email"],
        "canvas_id": profile.get("canvas_id") or "",
        "pronote_id": profile.get("pronote_id") or "",
        "canvas_link": profile.get("canvas_id") or "",
        "pronote_link": profile.get("pronote_id") or "",
        "likes": list(profile["likes"]),
        "dislikes": list(profile.get("dislikes") or []),
        "connectors": {"canvas": "mock", "pronote": "mock"},
        "password_stored": False,
        "synthetic": True,
    }


def with_desk_user(corpus: Corpus, profile: dict) -> Corpus:
    """Return a corpus view that can cite the local likes. Does not mutate `corpus`."""
    name = display_name(profile)
    shown = ", ".join(profile["likes"][:3])
    interests = f"Mi interessano {shown}."
    prefs = []
    for tag in profile["likes"]:
        pref_id = _pref_id(DESK_ID, tag)
        prefs.append(
            {
                "id": pref_id,
                "tag": tag,
                "weight": None,
                "note": (
                    f"{tag} è un mi piace di {name} ({DESK_ID}), registrato in locale. "
                    "Non viene da Canvas né da Pronote."
                ),
            }
        )
    user = {
        "id": DESK_ID,
        "name": name,
        "role": "student",
        "preferences": prefs,
        "interests_text": interests,
        "email": profile["email"],
    }
    users = [item for item in corpus.users if item["id"] != DESK_ID]
    users.append(user)
    by_id = {
        key: value
        for key, value in corpus.by_id.items()
        if key != DESK_ID and not str(key).startswith("pref-desk-")
    }
    by_id[DESK_ID] = {
        "source_id": DESK_ID,
        "kind": "user",
        "quote": f"{name}, accesso locale. {interests}",
        "field": "name",
        "record": user,
    }
    for pref in prefs:
        by_id[pref["id"]] = {
            "source_id": pref["id"],
            "kind": "preference",
            "quote": pref["note"],
            "field": "tag",
            "record": {**pref, "user_id": DESK_ID, "user_name": name},
        }
    return Corpus(
        campus_note=corpus.campus_note,
        view_box=corpus.view_box,
        places=corpus.places,
        users=users,
        events=corpus.events,
        emails=corpus.emails,
        by_id=by_id,
        dataset=corpus.dataset,
        vocabulary=corpus.vocabulary,
    )
