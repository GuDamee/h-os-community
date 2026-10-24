"""Desk path on the H-ELP snapshot: cited ask, feedback, boards, approval gate."""

from __future__ import annotations

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


def test_ask_cites_a_retrieved_campus_record(client):
    asked = client.post(
        "/assistant/ask",
        json={"user_id": "usr-001", "question": "Progetto collaborativo finanza"},
    )
    assert asked.status_code == 200
    answer = asked.json()
    assert answer["mode"] == "retrieval"
    assert answer["synthetic"] is True
    assert answer["reply"] == answer["answer"]
    assert answer["sources"]
    assert answer["source_id"] == answer["sources"][0]
    assert "evt-058" in answer["sources"]
    assert "evt-058" in answer["reply"]
    for source_id in answer["sources"]:
        if source_id.startswith(("evt-", "mail-", "loc-", "usr-")):
            assert client.get(f"/sources/{source_id}").status_code == 200


def test_unknown_question_does_not_invent_a_registration(client):
    answer = client.post(
        "/assistant/ask",
        json={"user_id": "usr-001", "question": "where is the campus shuttle tonight"},
    ).json()
    assert answer["mode"] == "retrieval"
    assert isinstance(answer["sources"], list)
    assert answer["reply"]
    assert client.get("/bacheca", params={"user_id": "usr-001"}).json()["notices"] == []


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
    assert body["stored"] is True


def test_bacheca_boards_are_the_colored_sources(client):
    boards = client.get("/community/boards")
    assert boards.status_code == 200
    ids = {board["id"] for board in boards.json()["boards"]}
    assert {"board-generale", "board-eventi", "board-annunci"} <= ids
    detail = client.get("/community/boards/board-generale").json()["board"]
    assert detail["messages"]
    assert any(message.get("org") or message.get("author") for message in detail["messages"])


def test_calendar_expands_lessons(client):
    calendar = client.get("/calendar")
    assert calendar.status_code == 200
    body = calendar.json()
    assert body["synthetic"] is True
    assert body["lessons"]
    assert body["lessons"][0]["kind"] == "lezione"


def test_tick_still_waits_for_a_person(client):
    proposed = client.post("/agent/tick", json={"user_id": "usr-001"}).json()
    assert proposed["status"] == "proposed"
    assert proposed["action"]["status"] == "pending"
    assert client.get("/bacheca", params={"user_id": "usr-001"}).json()["notices"] == []
    approved = client.post(
        "/agent/approve",
        json={"action_id": proposed["action"]["id"], "decision": "approve"},
    )
    assert approved.status_code == 200
    assert approved.json()["notice"]["delivered_externally"] is False
