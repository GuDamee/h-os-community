"""One desk path: sourced ask, recommendation, proposal, human approval, agenda."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = create_app(db_path=tmp_path / "hos.sqlite", data_dir=ROOT / "data")
    with TestClient(app) as test_client:
        yield test_client


def test_ask_recommend_approve_lands_on_the_agenda(client):
    asked = client.post(
        "/assistant/ask",
        json={"user_id": "usr-001", "message": "Recommend an event"},
    )
    assert asked.status_code == 200
    answer = asked.json()
    assert answer["kind"] == "recommendations"
    assert answer["assistant"] == "dataset"
    assert answer["source_ids"]
    assert answer["recommendations"]
    for source_id in answer["source_ids"]:
        assert source_id in answer["text"]
        assert client.get(f"/sources/{source_id}").status_code == 200
    roles = [step["role"] for step in answer["steps"]]
    assert roles == ["librarian", "campus_brain", "agent"]
    assert answer["steps"][2]["registered"] is False
    assert answer["model"] == "deterministic"
    assert answer["retrieval"]["status"] == "real"
    assert answer["retrieval"]["llamaindex_installed"] is False
    assert answer["retrieval"]["cognee_installed"] is False
    assert answer["reasoning"]
    assert any(top_id in step for step in answer["reasoning"] for top_id in answer["source_ids"])
    assert "confronto" in answer["text"].lower()
    assert "copertura" in answer["text"].lower()
    assert answer["retrieval"]["pipeline"] == ["retrieve", "reason", "deterministic_reply", "cite"]
    assert answer["retrieval"]["set_aside"] == []
    top = answer["recommendations"][0]
    assert top["event_id"] == top["source_id"]
    assert top["source_id"] in answer["source_ids"]

    proposed = client.post(
        "/registrations/propose",
        json={"user_id": "usr-001", "event_id": top["event_id"]},
    )
    assert proposed.status_code == 200
    proposal = proposed.json()
    assert proposal["registered"] is False
    assert proposal["proposal"]["source_id"] == top["source_id"]
    assert client.get("/agenda", params={"user_id": "usr-001"}).json()["registrations"] == []

    approved = client.post(
        "/registrations/approve",
        json={"user_id": "usr-001", "approval_id": proposal["proposal"]["approval_id"]},
    )
    assert approved.status_code == 200
    assert approved.json()["registered"] is True
    assert approved.json()["source_id"] == top["source_id"]
    agenda = client.get("/agenda", params={"user_id": "usr-001"}).json()["registrations"]
    assert len(agenda) == 1
    assert agenda[0]["event_id"] == top["event_id"]
    assert agenda[0]["source_id"] == top["source_id"]
    assert agenda[0]["status"] == "simulated"
    assert agenda[0]["title"]


def test_reject_leaves_the_agenda_empty(client):
    asked = client.post(
        "/assistant/ask",
        json={"user_id": "usr-002", "message": "Consigliami un evento"},
    ).json()
    event_id = asked["recommendations"][0]["event_id"]
    proposal = client.post(
        "/registrations/propose",
        json={"user_id": "usr-002", "event_id": event_id},
    ).json()["proposal"]
    rejected = client.post(
        "/registrations/reject",
        json={"user_id": "usr-002", "approval_id": proposal["approval_id"]},
    )
    assert rejected.status_code == 200
    assert client.get("/agenda", params={"user_id": "usr-002"}).json()["registrations"] == []


def test_doc_question_cites_the_markdown_source(client):
    answer = client.post(
        "/assistant/ask",
        json={"user_id": "usr-001", "message": "ridurre gli sprechi"},
    ).json()
    assert "D001" in answer["source_ids"]
    assert "D001" in answer["text"]
    assert answer["retrieval"]["packages_installed"] is False
    assert [item["name"] for item in answer["retrieval"]["inspired_by"]] == [
        "smolagents",
        "llamaindex",
        "haystack",
        "pydantic-ai",
    ]
    assert answer["retrieval"]["pipeline"] == ["retrieve", "reason", "deterministic_reply", "cite"]
    assert answer["retrieval"]["set_aside"] == []


def test_feedback_subject_keeps_event_and_date(client):
    created = client.post(
        "/feedback",
        json={
            "user_id": "usr-001",
            "rating": 4,
            "subject": "Progetto collaborativo: finanza · 2026-11-14",
            "body": "Utile. Orario chiaro per il gruppo.",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["subject"] == "Progetto collaborativo: finanza · 2026-11-14"
    assert "Utile" in body["body"]


def test_unknown_question_cites_nothing(client):
    answer = client.post(
        "/assistant/ask",
        json={"user_id": "usr-001", "message": "where is the campus shuttle tonight"},
    ).json()
    assert answer["kind"] == "unknown"
    assert answer["source_ids"] == []
    assert answer["recommendations"] == []
    assert answer["retrieval"]["nodes"] == 0
    assert answer["model"] == "deterministic"


def test_two_questions_retrieve_different_sources(client):
    lesson = client.post(
        "/assistant/ask",
        json={"user_id": "usr-001", "message": "Business English"},
    ).json()
    ride = client.post(
        "/assistant/ask",
        json={"user_id": "usr-001", "message": "Cerco un passaggio per Treviso"},
    ).json()
    assert "cal-tue-business-english" in lesson["source_ids"]
    assert lesson["source_ids"] != ride["source_ids"]
    assert ride["source_ids"] == ["post-cs-001"]
    assert "post-ph-003" in ride["retrieval"]["set_aside"]
    assert "treviso" in " ".join(ride["reasoning"]).lower()
    assert "messi da parte" in " ".join(ride["reasoning"]).lower()


def test_gemini_reasoning_keeps_only_retrieved_ids(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake(prompt, key, model):
        ids = re.findall(r"source_id: (\S+)", prompt)
        return json.dumps(
            {
                "reasoning": [f"Il passaggio {ids[0]} è quello che risponde, gli altri no."],
                "answer": f"La conclusione usa solo il passaggio recuperato. Fonte: {ids[0]}. Nessuna iscrizione è stata eseguita.",
            }
        )

    monkeypatch.setattr("app.narrate.gemma_complete", fake)
    answer = client.post(
        "/assistant/ask",
        json={"user_id": "usr-001", "message": "Recommend an event"},
    ).json()
    assert answer["assistant"] == "gemma"
    assert answer["model"] == "gemini"
    assert answer["retrieval"]["pipeline"][2] == "gemini"
    assert answer["reasoning"][0].startswith("Selezione:")
    assert answer["source_ids"]
    for source_id in answer["source_ids"]:
        assert source_id in answer["text"]


def test_gemini_invented_id_falls_back_to_the_trace(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake(prompt, key, model):
        return json.dumps(
            {
                "reasoning": ["Ho inventato evt-999 che non è nel recupero."],
                "answer": "C'è uno shuttle notturno. Fonte: evt-999. Nessuna iscrizione è stata eseguita.",
            }
        )

    monkeypatch.setattr("app.narrate.gemma_complete", fake)
    answer = client.post(
        "/assistant/ask",
        json={"user_id": "usr-001", "message": "Recommend an event"},
    ).json()
    assert answer["assistant"] == "fallback_after_gemma"
    assert answer["model"] == "fallback_after_gemini"
    assert answer["retrieval"]["pipeline"][2] == "fallback_after_gemini"
    assert "evt-999" not in answer["source_ids"]
    assert "evt-999" not in answer["text"]
    assert answer["source_ids"]
    assert answer["source_ids"][0] in answer["text"]


def test_reason_keeps_the_rare_token_and_sets_the_weak_hit_aside():
    from app.campus_agent import run_campus_agent

    student = {"id": "usr-001", "preferences": ["cinema"], "disliked": []}
    events = [
        {
            "id": "evt-001",
            "source_id": "evt-001",
            "title": "Cerco idee",
            "description": "Cerco persone per un laboratorio.",
            "tags": ["cinema"],
            "kind": "event",
            "start": "2026-12-01T18:00:00+01:00",
            "location": "Aula 1",
        }
    ]
    posts = [
        {
            "id": "post-ride",
            "source_id": "post-ride",
            "title": "Sera a Treviso",
            "body": "Un passaggio verso Treviso dopo lezione.",
            "tags": [],
            "kind": "post",
        },
        {
            "id": "post-room",
            "source_id": "post-room",
            "title": "Sala prove",
            "body": "Cerco una sala quieta.",
            "tags": [],
            "kind": "post",
        },
    ]
    docs = [
        {
            "id": "D009",
            "source_id": "D009",
            "title": "Nota",
            "description": "Nessun dato sul trasporto.",
            "tags": [],
            "kind": "doc",
        }
    ]
    result = run_campus_agent(
        "Cerco un passaggio per Treviso",
        student,
        events,
        posts,
        docs,
        "2026-10-24T18:40:00+02:00",
    )
    assert result["source_ids"] == ["post-ride"]
    assert set(result["retrieval"]["set_aside"]) == {"evt-001", "post-room"}
    assert "post-ride" in result["text"]
    assert result["retrieval"]["pipeline"] == ["retrieve", "reason", "deterministic_reply", "cite"]
    assert result["retrieval"]["packages_installed"] is False


def test_reason_cites_the_doc_when_events_only_share_a_common_word():
    from app.campus_agent import run_campus_agent

    student = {"id": "usr-001", "preferences": [], "disliked": []}
    events = []
    for index in range(1, 6):
        events.append(
            {
                "id": f"evt-{index:03d}",
                "source_id": f"evt-{index:03d}",
                "title": f"Note {index}",
                "description": "Laboratorio aperto agli studenti del corso.",
                "tags": [],
                "kind": "event",
                "start": "2026-12-01T18:00:00+01:00",
                "location": "Aula 1",
            }
        )
    docs = [
        {
            "id": "D001",
            "source_id": "D001",
            "title": "Mensa",
            "description": "Laboratorio per ridurre gli sprechi.",
            "tags": [],
            "kind": "doc",
        }
    ]
    result = run_campus_agent(
        "laboratorio sprechi",
        student,
        events,
        [],
        docs,
        "2026-10-24T18:40:00+02:00",
    )
    assert result["source_ids"] == ["D001"]
    assert "D001" in result["text"]
    assert len(result["retrieval"]["set_aside"]) == 4
    assert all(source_id.startswith("evt-") for source_id in result["retrieval"]["set_aside"])
