"""Short Italian “perché” for a match. Gemma may write it; the template always can.

The model may rephrase grounded facts. It may not invent sources. A missing
key, a failed call, or a note that cites an unknown id falls back to the
template so the desk still has a sentence before Approva.
"""

from __future__ import annotations

import json
import logging
import os
import re

import httpx

log = logging.getLogger("hos.narrate")

ID_RE = re.compile(r"\b(?:usr|pref|evt|loc|mail)-[a-z0-9]+(?:-[a-z0-9]+)*\b")
DEFAULT_MODEL = "gemma-4-26b-a4b-it"


def narration_configured() -> bool:
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


def why_template(match: dict) -> str:
    """Two to four Italian sentences from tags, score, and source ids. No network."""
    name = match.get("user_name") or "ti"
    user_id = match.get("user_id") or ""
    who = f"{name} ({user_id})" if user_id else name
    tags = ", ".join(match.get("overlapping_tags") or []) or "i tag in comune"
    pref = (match.get("pref_ids") or [""])[0]
    place = match.get("location_name") or "campus"
    place_id = match.get("location_id") or ""
    building = match.get("building")
    if building and place_id:
        where = f"{building} ({place}, {place_id})"
    elif place_id:
        where = f"{place} ({place_id})"
    else:
        where = place
    score = float(match.get("score") or 0)
    formula = match.get("formula") or "jaccard"
    title = match.get("title") or "questo evento"
    event_id = match.get("event_id") or ""
    return (
        f"Ti consiglio {title} ({event_id}) perché i tuoi mi piace toccano {tags}, in particolare {pref}. "
        f"Per {who} il punteggio {formula} è {score:.2f}. "
        f"Il posto nel dataset è {where}. "
        f"Resta un suggerimento: in bacheca ci finisce solo dopo Approva."
    )


def apply_deterministic(matches: list[dict], mode: str = "deterministic") -> str:
    for match in matches:
        why = why_template(match)
        match["why"] = why
        match["display_text"] = why
        match["display_by"] = mode
    return mode


def text_is_grounded(text: str, allowed_ids: set[str], required_ids: set[str]) -> bool:
    if not text or len(text) < 40 or len(text) > 700:
        return False
    found = set(ID_RE.findall(text))
    if not found or not found <= allowed_ids:
        return False
    if not required_ids <= found:
        return False
    return True


def narrate(matches: list[dict], allowed_ids: set[str]) -> str:
    """Set display_text on each match. Returns deterministic, gemma, or fallback_after_gemma."""
    if not matches:
        return "deterministic"
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return apply_deterministic(matches)
    try:
        raw = gemma_complete(_prompt(matches), key, os.getenv("GEMMA_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL)
        notes = _parse_notes(raw, len(matches))
    except Exception as exc:
        log.warning("Gemma rewrite skipped: %s", exc.__class__.__name__)
        return apply_deterministic(matches, "fallback_after_gemma")

    any_gemma = False
    any_fallback = False
    for match, note in zip(matches, notes, strict=True):
        required = {match["event_id"], *match["pref_ids"][:1]}
        cleaned = note.strip()
        if text_is_grounded(cleaned, allowed_ids, required):
            match["why"] = cleaned
            match["display_text"] = cleaned
            match["display_by"] = "gemma"
            any_gemma = True
        else:
            why = why_template(match)
            match["why"] = why
            match["display_text"] = why
            match["display_by"] = "fallback_after_gemma"
            any_fallback = True
    if any_gemma and any_fallback:
        return "mixed"
    if any_gemma:
        return "gemma"
    return "fallback_after_gemma"


def gemma_complete(prompt: str, key: str, model: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    response = httpx.post(
        url,
        headers={"x-goog-api-key": key, "content-type": "application/json"},
        json={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700},
        },
        timeout=8.0,
    )
    response.raise_for_status()
    payload = response.json()
    parts = payload["candidates"][0]["content"]["parts"]
    text = "\n".join(part.get("text", "") for part in parts if part.get("text"))
    if not text.strip():
        raise ValueError("empty Gemma response")
    return text


def _prompt(matches: list[dict]) -> str:
    lines = []
    for index, match in enumerate(matches, start=1):
        lines.append(f"{index}. {why_template(match)}")
    joined = "\n".join(lines)
    return (
        "Per ogni scheda scrivi perché ti consiglio questo evento.\n"
        "Italiano, da due a quattro frasi brevi, tono da compagno di corso.\n"
        "Usa solo i fatti già nella scheda: mi piace e tag, titolo, posto, punteggio, formula, identificativi.\n"
        "Ogni testo deve contenere, copiati uguali, gli identificativi che già compaiono "
        "(iniziano con usr-, pref-, evt-, loc- o mail-). Non inventarne di nuovi.\n"
        "Non dire che la persona ha già approvato. In bacheca ci finisce solo dopo Approva.\n"
        'Rispondi solo con JSON: {"notes":["..."]}\n'
        "Stesso numero di note, stesso ordine.\n\n"
        f"SCHEDE:\n{joined}"
    )


def _parse_notes(raw: str, count: int) -> list[str]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Gemma did not return a JSON object")
    data = json.loads(text[start : end + 1])
    notes = data.get("notes") if isinstance(data, dict) else None
    if not isinstance(notes, list) or len(notes) != count:
        raise ValueError("Gemma notes length does not match")
    if not all(isinstance(note, str) for note in notes):
        raise ValueError("Gemma notes must be strings")
    return notes
