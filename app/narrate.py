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


SOURCE_RE = re.compile(
    r"\b(?:usr|pref|evt|loc|mail|post|cal|contact|board)-[a-z0-9]+(?:-[a-z0-9]+)*\b|\bD\d{3}\b"
)


def retrieval_meta(count: int) -> dict:
    """LlamaIndex-style retrieve-then-synthesize. The package is not imported."""
    return {
        "engine": "local-nodes",
        "pattern": "retrieve-then-reason",
        "nodes": count,
        "status": "real",
        "llamaindex_installed": False,
        "cognee_installed": False,
    }


def deterministic_reason(
    question: str,
    passages: list[dict],
    student: dict | None,
    recommend: bool,
    set_aside: list[dict] | None = None,
    considered: int | None = None,
) -> dict:
    """Compare retrieved passages and answer from the ones that survive. No network."""
    held_back = list(set_aside or [])
    total = considered if considered is not None else len(passages) + len(held_back)
    prefs = ", ".join((student or {}).get("preferences") or []) or "nessuna"
    steps = [
        f"Recupero: {total} passaggi da eventi, post e documenti. "
        f"Dopo il confronto ne restano {len(passages)}. Domanda: {question.strip()}."
    ]
    if recommend:
        steps.append(f"Rango per copertura sulle preferenze ({prefs}), solo eventi ancora futuri.")
    for passage in passages:
        steps.append(_evidence_step(passage, question))
    if held_back:
        shown = held_back[:4]
        bits = [f"{item['source_id']} ({item.get('aside_reason') or 'meno pertinente'})" for item in shown]
        extra = len(held_back) - len(shown)
        more = f" e altri {extra}" if extra else ""
        steps.append("Messi da parte: " + "; ".join(bits) + more + ".")
    conclusion = _recommend_reply(passages) if recommend else _search_reply(passages, held_back)
    steps.append(conclusion)
    return {
        "text": conclusion,
        "reasoning": steps,
        "source_ids": [passage["source_id"] for passage in passages],
        "assistant": "dataset",
        "model": "deterministic",
    }


def _evidence_step(passage: dict, question: str) -> str:
    shared = [tag for tag in (passage.get("shared_tags") or []) if tag]
    tokens = [token for token in (passage.get("matched_tokens") or []) if token]
    title = str(passage.get("title") or passage["source_id"]).strip()
    if shared:
        because = f"Tag in comune con lo studente: {', '.join(shared)}."
        if passage.get("score") is not None:
            because += f" Copertura {passage['score']}."
    elif passage.get("title_hit") or title.lower() in question.lower():
        because = "Il titolo coincide con la domanda."
    elif tokens:
        because = f"Parole della domanda nel testo: {', '.join(tokens)}."
    else:
        because = "Passaggio recuperato dal dataset."
    step = f"{title} ({passage['source_id']}). {because}"
    if passage.get("when"):
        step += f" Inizio: {passage['when']}."
    if passage.get("where"):
        step += f" Luogo: {passage['where']}."
    return step


def _recommend_reply(passages: list[dict]) -> str:
    top = passages[0]
    bits = []
    for passage in passages:
        tags = ", ".join(passage.get("shared_tags") or []) or "nessun tag"
        score = passage.get("score")
        score_bit = f", copertura {score}" if score is not None else ""
        when = f", inizio {passage['when']}" if passage.get("when") else ""
        bits.append(f"{passage.get('title')} ({passage['source_id']}: {tags}{score_bit}{when})")
    scores = [passage.get("score") for passage in passages]
    if len(passages) > 1 and all(score == scores[0] for score in scores):
        choice = f"A parità di copertura scelgo {top['source_id']}, il primo tra gli eventi futuri."
    else:
        choice = f"Scelgo {top['source_id']} perché la copertura è la più alta."
    sources = ", ".join(passage["source_id"] for passage in passages)
    return (
        f"Confronto: {'; '.join(bits)}. {choice} "
        f"Fonti: {sources}. Nessuna iscrizione è stata eseguita."
    )


def _search_reply(passages: list[dict], held_back: list[dict]) -> str:
    bits = []
    for passage in passages:
        tokens = ", ".join(passage.get("matched_tokens") or [])
        if passage.get("title_hit"):
            because = "titolo nella domanda"
        elif tokens:
            because = tokens
        else:
            because = "dataset"
        bits.append(f"{passage.get('title')} ({passage['source_id']}: {because})")
    aside = ""
    if held_back:
        shown = held_back[:4]
        dropped = [f"{item['source_id']} ({item.get('aside_reason') or 'meno pertinente'})" for item in shown]
        extra = len(held_back) - len(shown)
        more = f" e altri {extra}" if extra else ""
        aside = " Messi da parte: " + "; ".join(dropped) + more + "."
    sources = ", ".join(passage["source_id"] for passage in passages)
    return (
        f"Risposta: {'; '.join(bits)}.{aside} "
        f"Fonti: {sources}. Nessuna iscrizione è stata eseguita."
    )


def _selection_note(passages: list[dict], set_aside: list[dict] | None) -> str:
    kept = ", ".join(passage["source_id"] for passage in passages)
    held_back = list(set_aside or [])
    if not held_back:
        return f"Selezione: tengo {kept}."
    shown = ", ".join(item["source_id"] for item in held_back[:4])
    extra = len(held_back) - min(len(held_back), 4)
    more = f" e altri {extra}" if extra else ""
    return f"Selezione: tengo {kept}. Messi da parte: {shown}{more}."


def answer_from_passages(
    question: str,
    passages: list[dict],
    student: dict | None = None,
    recommend: bool = False,
    set_aside: list[dict] | None = None,
    considered: int | None = None,
) -> dict:
    """Reply from passages that already survived the local reason step.

    Gemini may rewrite that reply only when GEMINI_API_KEY is set and every id
    in the JSON was retrieved. A missing key, a failed call, or an invented id
    keeps the deterministic reply.
    """
    grounded = deterministic_reason(question, passages, student, recommend, set_aside=set_aside, considered=considered)
    allowed = [passage["source_id"] for passage in passages]
    allowed_set = set(allowed)
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return grounded
    try:
        raw = gemma_complete(
            _ask_prompt(question, passages, student, recommend),
            key,
            os.getenv("GEMMA_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        )
        reasoning, text = _parse_reason(raw)
    except Exception as exc:
        log.warning("Gemini reasoning skipped: %s", exc.__class__.__name__)
        return {**grounded, "assistant": "fallback_after_gemma", "model": "fallback_after_gemini"}
    blob = "\n".join([*reasoning, text])
    found = set(SOURCE_RE.findall(blob))
    if not found or not found <= allowed_set or len(text) > 1400:
        return {**grounded, "assistant": "fallback_after_gemma", "model": "fallback_after_gemini"}
    cited = [source_id for source_id in allowed if source_id in text]
    if not cited:
        return {**grounded, "assistant": "fallback_after_gemma", "model": "fallback_after_gemini"}
    return {
        "text": text,
        "reasoning": [_selection_note(passages, set_aside), *reasoning],
        "source_ids": cited,
        "assistant": "gemma",
        "model": "gemini",
    }


def _strip_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    return text


def _parse_reason(raw: str) -> tuple[list[str], str]:
    text = _strip_fence(raw)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Gemini did not return JSON")
    data = json.loads(text[start : end + 1])
    reasoning = data.get("reasoning") if isinstance(data, dict) else None
    answer = data.get("answer") if isinstance(data, dict) else None
    if not isinstance(reasoning, list) or not reasoning or not all(isinstance(step, str) and step.strip() for step in reasoning):
        raise ValueError("Gemini reasoning missing")
    if not isinstance(answer, str) or len(answer.strip()) < 40:
        raise ValueError("Gemini answer missing")
    return [step.strip() for step in reasoning], answer.strip()


def _ask_prompt(question: str, passages: list[dict], student: dict | None = None, recommend: bool = False) -> str:
    prefs = ", ".join((student or {}).get("preferences") or []) or "nessuna"
    lines = []
    for passage in passages:
        lines.append(
            "\n".join(
                [
                    f"source_id: {passage['source_id']}",
                    f"titolo: {passage.get('title') or ''}",
                    f"testo: {passage.get('text') or ''}",
                    f"quando: {passage.get('when') or ''}",
                    f"dove: {passage.get('where') or ''}",
                    f"tag in comune: {', '.join(passage.get('shared_tags') or [])}",
                    f"parole trovate: {', '.join(passage.get('matched_tokens') or [])}",
                ]
            )
        )
    task = (
        "Questi passaggi sono già il rango per copertura sulle preferenze. Spiega perché il primo è il consiglio."
        if recommend
        else "Spiega quale passaggio risponde alla domanda e perché."
    )
    return (
        "Non sei una chat libera. Ragiona solo sui passaggi recuperati dal dataset del campus.\n"
        f"Preferenze dello studente: {prefs}.\n"
        f"{task}\n"
        "Ogni passo e la conclusione devono copiare i source_id che usi, uguali a quelli dei passaggi.\n"
        "Non inventare eventi, orari, luoghi o id. Non dire che un'iscrizione è già fatta.\n"
        'Rispondi solo con JSON: {"reasoning":["..."],"answer":"..."}\n\n'
        f"DOMANDA: {question}\n\nPASSAGGI:\n" + "\n\n".join(lines)
    )


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
