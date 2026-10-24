"""Retrieve, reason, reply, then cite. Packages below are not imported.

The shape follows four open-source agents and none of their runtimes:

- smolagents: one plain function per corpus (events, community, docs)
- LlamaIndex: retrieve nodes, then synthesize
- Haystack: those steps are a fixed pipeline
- PydanticAI: the answer is a pydantic model, so a citation cannot be dropped quietly

Each corpus keeps its own hits, then a local reason step drops the weaker ones.
A rare token outranks a word that shows up everywhere. Gemini rewrites the
reply only when GEMINI_API_KEY is set and every cited id was retrieved.
No key is read from a file in this module.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from app.corpus import ROOT
from app.hos_core import recommend_events
from app.memory import GENERIC, TOKEN, CampusMemory
from app.narrate import answer_from_passages, retrieval_meta

DOCS_DIR = ROOT / "data" / "docs"
_RECOMMEND = re.compile(r"consigli|suggeri|raccomand|recommend|suggest", re.IGNORECASE)

INSPIRED_BY = [
    {
        "name": "smolagents",
        "repo": "https://github.com/huggingface/smolagents",
        "uses": "one tool per corpus",
        "status": "inspiration",
        "installed": False,
    },
    {
        "name": "llamaindex",
        "repo": "https://github.com/run-llama/llama_index",
        "uses": "retrieve then synthesize",
        "status": "planned",
        "installed": False,
    },
    {
        "name": "haystack",
        "repo": "https://github.com/deepset-ai/haystack",
        "uses": "retriever then generator pipeline",
        "status": "inspiration",
        "installed": False,
    },
    {
        "name": "pydantic-ai",
        "repo": "https://github.com/pydantic/pydantic-ai",
        "uses": "typed answer with required citations",
        "status": "inspiration",
        "installed": False,
    },
]


class CitedAnswer(BaseModel):
    text: str = Field(min_length=1)
    reasoning: list[str]
    source_ids: list[str]
    assistant: str
    model: str


def load_markdown_docs(folder: Path | None = None) -> list[dict]:
    root = folder or DOCS_DIR
    if not root.is_dir():
        return []
    rows = []
    for path in sorted(root.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
        rows.append(
            {
                "id": path.stem,
                "source_id": path.stem,
                "title": title,
                "description": text[:1500],
                "tags": [],
                "kind": "doc",
                "location": "",
                "start": "",
                "synthetic": True,
            }
        )
    return rows


def search_events(question: str, student: dict, events: list[dict], now: str) -> tuple[list[dict], str]:
    """Coverage rank when the question asks for a recommendation, otherwise title or token hits."""
    query = question.lower()
    if _RECOMMEND.search(query) and not _title_hits(query, events):
        rows = []
        for row in recommend_events(student, events, now=now, limit=3):
            rows.append(_passage(row["event"], "event", {"shared_tags": row["shared_tags"], "score": row["score"]}))
        return rows, "recommend"
    return _search_records(question, events, "event"), "events"


def search_community(question: str, posts: list[dict]) -> list[dict]:
    return _search_records(question, posts, "post")


def search_docs(question: str, docs: list[dict]) -> list[dict]:
    return _search_records(question, docs, "doc")


def run_campus_agent(question: str, student: dict, events: list[dict], posts: list[dict], docs: list[dict], now: str) -> dict:
    """Pipeline: retrieve each corpus, reason over the hits, reply, cite."""
    retrieved, mode = _retrieve(question, student, events, posts, docs, now)
    df = _document_frequency([*events, *posts, *docs])
    selected, set_aside = _reason(retrieved, mode, df)
    if selected:
        grounded = answer_from_passages(
            question,
            selected,
            student=student,
            recommend=mode == "recommend",
            set_aside=set_aside,
            considered=len(retrieved),
        )
        reply_stage = {
            "gemini": "gemini",
            "fallback_after_gemini": "fallback_after_gemini",
        }.get(grounded["model"], "deterministic_reply")
    else:
        grounded = None
        reply_stage = "deterministic_reply"
    meta = {
        **retrieval_meta(len(retrieved)),
        "mode": mode,
        "corpora": ["events", "community", "docs"],
        "pipeline": ["retrieve", "reason", reply_stage, "cite"],
        "inspired_by": INSPIRED_BY,
        "packages_installed": False,
        "considered": [passage["source_id"] for passage in retrieved],
        "set_aside": [passage["source_id"] for passage in set_aside],
        "cited": [] if grounded is None else list(grounded["source_ids"]),
    }
    if grounded is None:
        return {
            "text": "Non trovo questa informazione nei documenti e negli eventi del dataset. Nessuna informazione inventata.",
            "reasoning": ["Nessun passaggio di eventi, community o docs contiene questa domanda."],
            "source_ids": [],
            "assistant": "dataset",
            "model": "deterministic",
            "recommendations": [],
            "retrieval": meta,
            "passages": [],
        }
    answer = CitedAnswer(
        text=grounded["text"],
        reasoning=list(grounded["reasoning"]),
        source_ids=list(grounded["source_ids"]),
        assistant=grounded["assistant"],
        model=grounded["model"],
    )
    for source_id in answer.source_ids:
        if source_id not in answer.text:
            raise RuntimeError(f"assistant dropped {source_id}")
    payload = answer.model_dump()
    payload["retrieval"] = meta
    payload["passages"] = selected
    payload["recommendations"] = [
        {"event_id": passage["source_id"], "source_id": passage["source_id"], "title": passage["title"]}
        for passage in selected
        if passage["kind"] == "event"
    ]
    return payload


def _retrieve(question: str, student: dict, events: list[dict], posts: list[dict], docs: list[dict], now: str) -> tuple[list[dict], str]:
    """Title hits, else a recommendation, else the best hits from each corpus."""
    query = question.lower().strip()
    titled = _title_hits(query, events) + _title_hits(query, posts) + _title_hits(query, docs)
    if titled:
        related = search_events(question, student, events, now)[0]
        related += search_community(question, posts)
        related += search_docs(question, docs)
        return _unique(titled + related), "title"
    if _RECOMMEND.search(query):
        return search_events(question, student, events, now)
    found = search_events(question, student, events, now)[0]
    found += search_community(question, posts)
    found += search_docs(question, docs)
    return _unique(found), "search"


def _reason(passages: list[dict], mode: str, df: dict[str, int]) -> tuple[list[dict], list[dict]]:
    """Keep the passages that actually answer. Weaker token hits are set aside."""
    if mode == "recommend" or not passages:
        return passages, []
    ranked = sorted(passages, key=lambda passage: (-_token_score(passage, df), passage["source_id"]))
    best = _token_score(ranked[0], df)
    if best <= 0:
        selected = ranked[:4]
    else:
        selected = [passage for passage in ranked if _token_score(passage, df) >= best * 0.75][:4]
    selected_ids = {passage["source_id"] for passage in selected}
    aside = []
    for passage in ranked:
        if passage["source_id"] in selected_ids:
            continue
        score = _token_score(passage, df)
        tokens = ", ".join(passage.get("matched_tokens") or [])
        if best > 0 and score < best * 0.75:
            if tokens:
                reason = f"token meno distintivi ({tokens})"
            else:
                reason = "nessuna parola distintiva"
        else:
            reason = "oltre i quattro passaggi più pertinenti"
        aside.append({**passage, "aside_reason": reason})
    return selected, aside


def _token_score(passage: dict, df: dict[str, int]) -> float:
    score = 0.0
    for token in passage.get("matched_tokens") or []:
        score += 1.0 / max(df.get(str(token).lower(), 1), 1)
    if passage.get("title_hit"):
        score += 5
    return score


def _document_frequency(records: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        for token in _tokens(_record_text(record)):
            counts[token] = counts.get(token, 0) + 1
    return counts


def _record_text(record: dict) -> str:
    tags = " ".join(str(tag) for tag in (record.get("tags") or []))
    body = record.get("description") or record.get("body") or record.get("text") or ""
    return f"{record.get('title') or ''} {body} {tags}"


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN.findall(text or "") if token.lower() not in GENERIC}


def _title_hits(query: str, records: list[dict]) -> list[dict]:
    hits = []
    for record in records:
        title = str(record.get("title") or "").lower().strip()
        ident = str(record.get("id") or "").lower().strip()
        if (title and title in query) or (ident and ident in query):
            kind = record.get("kind") or "record"
            hits.append(_passage(record, kind, {"title_hit": True}))
    return hits


def _search_records(question: str, records: list[dict], kind: str) -> list[dict]:
    if not records:
        return []
    memory = CampusMemory()
    memory.cognify(
        [
            {
                "source_id": record.get("source_id") or record["id"],
                "kind": record.get("kind") or kind,
                "title": record.get("title") or record.get("id"),
                "text": record.get("description") or record.get("body") or record.get("text") or "",
                "tags": list(record.get("tags") or []),
            }
            for record in records
        ]
    )
    by_id = {(record.get("source_id") or record["id"]): record for record in records}
    rows = []
    for hit in memory.search(question, limit=4):
        record = by_id.get(hit["source_id"])
        if record is None:
            continue
        rows.append(_passage(record, record.get("kind") or kind, {"matched_tokens": hit.get("matched_tokens") or []}))
    return rows


def _passage(record: dict, kind: str, extra: dict | None = None) -> dict:
    where = record.get("location") or ""
    if isinstance(where, dict):
        where = where.get("building") or where.get("name") or ""
    row = {
        "source_id": record.get("source_id") or record["id"],
        "kind": record.get("kind") or kind,
        "title": record.get("title") or record.get("source_id") or record["id"],
        "text": (record.get("description") or record.get("body") or record.get("text") or "").strip(),
        "when": record.get("start") or "",
        "where": where,
        "shared_tags": list((extra or {}).get("shared_tags") or []),
        "matched_tokens": list((extra or {}).get("matched_tokens") or []),
    }
    if extra and "score" in extra:
        row["score"] = extra["score"]
    if (extra or {}).get("title_hit"):
        row["title_hit"] = True
    return row


def _unique(rows: list[dict]) -> list[dict]:
    chosen = []
    index: dict[str, int] = {}
    for row in rows:
        source_id = row["source_id"]
        if source_id in index:
            kept = chosen[index[source_id]]
            if not kept.get("matched_tokens") and row.get("matched_tokens"):
                kept["matched_tokens"] = list(row["matched_tokens"])
            if row.get("title_hit"):
                kept["title_hit"] = True
            if kept.get("score") is None and row.get("score") is not None:
                kept["score"] = row["score"]
            continue
        index[source_id] = len(chosen)
        chosen.append(row)
    return chosen
