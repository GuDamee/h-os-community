"""Local librarian graph. Cognee is not imported.

Cognee (https://github.com/topoteretes/cognee) is PLANNED and is not installed.
This module does not call Cognee or an LLM. `cognify` links each synthetic
record to its tags. `search` returns only nodes that were added. `memify`
stays planned.
"""

from __future__ import annotations

import re

TOKEN = re.compile(r"[a-z0-9àèéìòù]{4,}", re.IGNORECASE)
GENERIC = {
    "campus", "evento", "eventi", "event", "studente", "studenti", "demo",
    "questo", "quello", "sono", "cosa", "come", "quando", "dove", "offre",
    "there", "what", "your", "with", "nella", "della", "delle", "degli",
    "una", "uno", "per", "con", "che", "non",
}


class CampusMemory:
    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: list[tuple[str, str, str]] = []

    def add(self, source_id: str, kind: str, title: str, text: str, tags: list[str] | None = None) -> None:
        self.nodes[source_id] = {
            "source_id": source_id,
            "kind": kind,
            "title": title,
            "text": text,
            "tags": list(tags or []),
            "synthetic": True,
        }
        for tag in tags or []:
            tag_id = f"tag:{tag}"
            self.nodes.setdefault(
                tag_id,
                {"source_id": tag_id, "kind": "tag", "title": tag, "text": tag, "tags": [tag], "synthetic": True},
            )
            self.edges.append((source_id, "tagged", tag_id))

    def cognify(self, records: list[dict]) -> dict:
        """Deterministic graph build. Not Cognee's model extraction."""
        for record in records:
            self.add(
                record["source_id"],
                record.get("kind") or "record",
                record.get("title") or record["source_id"],
                record.get("text") or record.get("description") or record.get("body") or "",
                record.get("tags") or [],
            )
        return {"nodes": len(self.nodes), "edges": len(self.edges), "engine": "local-graph", "cognee_installed": False}

    def search(self, query: str, limit: int = 5) -> list[dict]:
        tokens = [token.lower() for token in TOKEN.findall(query or "") if token.lower() not in GENERIC]
        if not tokens:
            return []
        hits = []
        for node in self.nodes.values():
            if node["kind"] == "tag":
                continue
            hay = f"{node['title']} {node['text']} {' '.join(node['tags'])}".lower()
            shared = [token for token in tokens if token in hay]
            if not shared:
                continue
            hits.append({**node, "matched_tokens": shared, "score": len(shared)})
        hits.sort(key=lambda item: (-item["score"], item["source_id"]))
        return hits[:limit]


def records_from_campus(events: list[dict], posts: list[dict], lessons: list[dict]) -> list[dict]:
    rows = []
    for event in events:
        rows.append(
            {
                "source_id": event["source_id"],
                "kind": "event",
                "title": event["title"],
                "text": event.get("description") or "",
                "tags": list(event.get("tags") or []),
            }
        )
    for post in posts:
        rows.append(
            {
                "source_id": post["source_id"],
                "kind": "post",
                "title": post["title"],
                "text": post.get("body") or "",
                "tags": list(post.get("tags") or []),
            }
        )
    for lesson in lessons:
        rows.append(
            {
                "source_id": lesson["source_id"],
                "kind": "lesson",
                "title": lesson["title"],
                "text": lesson.get("description") or lesson["title"],
                "tags": list(lesson.get("tags") or []),
            }
        )
    return rows
