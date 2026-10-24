"""H-OS demo invariants: cited sources, set scores, and no notice before approval."""

from __future__ import annotations

import json
from math import comb
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.corpus import load_corpus
from app.main import create_app
from app.narrate import text_is_grounded, why_template
from app.scoring import jaccard_score, overlap_score, score_overlap

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = create_app(db_path=tmp_path / "hos.sqlite", data_dir=ROOT / "data")
    with TestClient(app) as test_client:
        yield test_client


def test_score_formula_is_stable():
    assert score_overlap(1.67, 15.8, True) == 0.86
    assert score_overlap(0, 1, True) == 0.0
    assert score_overlap(1.67, -3, False) < score_overlap(1.67, 10, False)


def test_jaccard_and_overlap_scores():
    prefs = {"cinema", "gaming", "programmazione"}
    tags = {"gaming", "programmazione", "robotica", "teatro"}
    assert jaccard_score(prefs, tags) == round(2 / 5, 2)
    assert overlap_score(prefs, tags) == round(2 / 3, 2)
    assert jaccard_score(prefs, {"ambiente"}) == 0.0
    assert overlap_score(set(), tags) == 0.0
    assert overlap_score(prefs, tags) >= jaccard_score(prefs, tags)


def test_preference_space_is_not_materialized():
    tags = json.loads((ROOT / "data" / "tags.json").read_text(encoding="utf-8"))
    users = json.loads((ROOT / "data" / "users.json").read_text(encoding="utf-8"))
    assert tags["synthetic"] is True
    space = sum(comb(len(tags["tags"]), k) for k in range(3, 7))
    assert space == 245180
    assert tags["preference_space"]["theoretical_profiles"] == space
    assert len(users["users"]) == 55
    assert len(users["users"]) < space


def test_team_files_keep_the_source_fields():
    users = json.loads((ROOT / "data" / "users.json").read_text(encoding="utf-8"))["users"]
    events = json.loads((ROOT / "data" / "events.json").read_text(encoding="utf-8"))["events"]
    emails = json.loads((ROOT / "data" / "emails.json").read_text(encoding="utf-8"))["emails"]
    assert set(users[0]) == {"id", "name", "role", "preferences", "year", "interests_text"}
    assert all(isinstance(tag, str) for tag in users[0]["preferences"])
    assert "weight" not in users[0]
    assert set(events[0]) == {
        "id",
        "title",
        "description",
        "tags",
        "location",
        "start",
        "end",
        "capacity",
        "source_id",
    }
    assert set(events[0]["location"]) == {"building"}
    assert "going" not in events[0] and "host" not in events[0]
    assert set(emails[0]) == {"id", "from", "to", "subject", "body", "related_event_id"}
    assert "received_at" not in emails[0]


def test_health_is_mit_and_students_only(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["license"] == "MIT"
    assert body["open_source"]["inspiration_installed"] is False
    repos = [item["repo"] for item in body["open_source"]["patterns"]]
    assert repos == [
        "https://github.com/garrytan/gbrain",
        "https://github.com/topoteretes/cognee",
        "https://github.com/run-llama/llama_index",
        "https://github.com/huggingface/smolagents",
        "https://github.com/deepset-ai/haystack",
        "https://github.com/pydantic/pydantic-ai",
        "https://github.com/pipeshub-ai/pipeshub-ai",
        "https://github.com/paperclipai/paperclip",
        "https://github.com/langchain-ai/langgraph",
        "https://github.com/Merit-Systems/OpenInstinct",
    ]
    assert all(item["installed"] is False for item in body["open_source"]["patterns"])
    planned = {item["name"] for item in body["open_source"]["patterns"] if item["status"] == "planned"}
    assert planned == {"cognee", "llamaindex", "paperclip", "langgraph"}
    assert body["retrieval"] == "real"
    assert body["reasoning"] == "deterministic"
    assert body["llamaindex"] == "planned"
    assert body["cognee"] == "planned"
    assert body["role_demo"] == "studenti"
    assert body["dataset"] == "team"
    assert body["default_formula"] == "jaccard"
    assert body["formulas"][:2] == ["jaccard", "overlap"]
    assert body["preference_space"]["theoretical_profiles"] == 245180
    assert body["preference_space"]["materialized_users"] == 55
    assert body["synthetic_data"] is True
    assert body["narration_mode"] == "deterministic"
    assert body["counts"]["users"] == 55
    assert body["counts"]["events"] == 120
    assert body["counts"]["emails"] == 12
    assert body["counts"]["pending_actions"] == 0


def test_email_access_follows_the_student(client):
    assert client.get("/emails").status_code == 400
    alex = client.get("/emails", params={"user_id": "usr-001"})
    assert alex.status_code == 200
    assert alex.json()["access"] == "personal"
    assert {mail["id"] for mail in alex.json()["emails"]} == {"mail-001"}
    andrea = client.get("/emails", params={"user_id": "usr-002"}).json()
    assert "mail-001" not in {mail["id"] for mail in andrea["emails"]}
    personal = client.get("/sources/mail-001").json()["access"]
    assert personal["scope"] == "personal"
    assert personal["owner_id"] == "usr-001"
    assert client.get("/sources/evt-001").json()["access"]["scope"] == "public"


def test_get_user_keeps_tags_as_tags(client):
    alex = client.get("/users/usr-001")
    assert alex.status_code == 200
    body = alex.json()
    assert body["role"] == "student"
    assert body["name"] == "Alex Rossi"
    assert "program" not in body
    assert body["preferences"][0]["tag"] == "cinema"
    assert body["preferences"][0]["id"] == "pref-001-cinema"
    assert body["preferences"][0]["weight"] is None
    assert client.get("/users/usr-missing").status_code == 404


def test_match_cites_sources_and_ranks_jaccard(client):
    users = client.get("/users").json()["users"]
    assert len(users) == 55
    for user in users:
        response = client.post("/match", json={"user_id": user["id"], "limit": 4})
        assert response.status_code == 200
        body = response.json()
        assert body["display_by"] == "deterministic"
        assert body["method"]["name"] == "jaccard"
        assert body["matches"]
        scores = [match["score"] for match in body["matches"]]
        assert scores == sorted(scores, reverse=True)
        for match in body["matches"]:
            assert match["citations"]
            assert match["display_by"] == "deterministic"
            assert match["why"] == match["display_text"]
            assert match["event_id"] in match["why"]
            assert match["pref_ids"][0] in match["why"]
            assert match["user_id"] in match["why"]
            assert "Approva" in match["why"]
            ids = [item["source_id"] for item in match["citations"]]
            assert ids == list(dict.fromkeys(ids))
            for source_id in ids:
                assert source_id in match["explanation"]
                source = client.get(f"/sources/{source_id}")
                assert source.status_code == 200
                assert source.json()["synthetic"] is True
            assert set(match["pref_ids"]) <= set(ids)
            assert match["event_id"] in ids
    alex = client.post("/match", json={"user_id": "usr-001", "limit": 1}).json()["matches"][0]
    assert alex["event_id"] == "evt-058"
    assert alex["score"] == 0.5
    assert alex["building"] == "Building 3"
    assert alex["location_id"] == "loc-library"
    assert "pref-001-finanza" in alex["explanation"]
    assert "pref-001-finanza" in alex["why"]
    assert "finanza" in alex["why"]
    assert "0.50" in alex["why"]
    assert "loc-library" in alex["why"]
    assert alex["company"] == []
    overlap = client.post("/match", json={"user_id": "usr-001", "limit": 1, "formula": "overlap"}).json()
    assert overlap["method"]["name"] == "overlap"
    assert overlap["matches"][0]["event_id"] == "evt-058"
    assert overlap["matches"][0]["score"] == 1.0
    andrea = client.post("/match", json={"user_id": "usr-002", "limit": 1}).json()["matches"][0]
    assert andrea["event_id"] == "evt-011"
    assert {person["user_id"] for person in andrea["company"]} == {"usr-022", "usr-023"}
    refused = client.post("/match", json={"user_id": "usr-001", "formula": "weighted"})
    assert refused.status_code == 422
    assert client.post("/match", json={"user_id": "usr-001", "formula": "cosine"}).status_code == 422


def test_tick_does_not_notify_until_approve(client):
    proposed = client.post("/agent/tick", json={"user_id": "usr-001"})
    assert proposed.status_code == 200
    body = proposed.json()
    assert body["status"] == "proposed"
    action = body["action"]
    assert action["status"] == "pending"
    assert action["event_id"] == "evt-058"
    assert action["score"] == 0.5
    assert action["trace"]["event"]["signal"] == "preference_overlap"
    for step in ("event", "context", "reasoning", "action"):
        summary = action["trace"][step]["summary"]
        for citation in action["trace"][step]["citations"]:
            assert citation["source_id"] in summary
    assert action["trace"]["action"]["requires_human"] is True
    assert action["trace"]["action"]["delivered_externally"] is False

    board = client.get("/bacheca", params={"user_id": "usr-001"}).json()
    assert board["notices"] == []
    assert board["delivered_externally"] is False

    approved = client.post(
        "/agent/approve",
        json={"action_id": action["id"], "decision": "approve"},
    )
    assert approved.status_code == 200
    notice = approved.json()["notice"]
    assert notice["delivered_externally"] is False
    assert notice["channel"] == "bacheca"
    assert notice["event_id"] == "evt-058"
    assert "Nessuna email è stata inviata" in notice["text"]
    assert client.get("/bacheca", params={"user_id": "usr-001"}).json()["notices"][0]["id"] == notice["id"]

    again = client.post("/agent/approve", json={"action_id": action["id"], "decision": "approve"})
    assert again.json()["idempotent"] is True
    assert len(client.get("/bacheca", params={"user_id": "usr-001"}).json()["notices"]) == 1

    assert client.get("/bacheca", params={"user_id": "usr-002"}).json()["notices"] == []

    nxt = client.post("/agent/tick", json={"user_id": "usr-001"}).json()
    assert nxt["status"] == "proposed"
    assert nxt["action"]["event_id"] != "evt-058"
    assert nxt["action"]["status"] == "pending"


def test_dismiss_blocks_the_pair_and_sends_nothing(client):
    action = client.post("/agent/tick", json={"user_id": "usr-002"}).json()["action"]
    assert action["event_id"] == "evt-011"
    dismissed = client.post(
        "/agent/approve",
        json={"action_id": action["id"], "decision": "dismiss"},
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["notice"] is None
    assert client.get("/bacheca", params={"user_id": "usr-002"}).json()["notices"] == []
    conflict = client.post("/agent/approve", json={"action_id": action["id"], "decision": "approve"})
    assert conflict.status_code == 409
    nxt = client.post("/agent/tick", json={"user_id": "usr-002"}).json()
    assert nxt["action"]["event_id"] != "evt-011"


def test_unknown_action_and_bad_decision(client):
    assert client.post("/agent/approve", json={"action_id": "act-missing", "decision": "approve"}).status_code == 404
    assert client.post("/match", json={"user_id": "usr-none"}).status_code == 404
    assert client.post("/match", json={"user_id": "usr-001", "limit": 0}).status_code == 422
    assert client.post("/agent/tick", json={"user_id": "usr-ghost"}).status_code == 404


def test_reset_clears_notices_only(client):
    action = client.post("/agent/tick", json={"user_id": "usr-003"}).json()["action"]
    client.post("/agent/approve", json={"action_id": action["id"], "decision": "approve"})
    cleared = client.post("/demo/reset").json()
    assert cleared["cleared"] == 1
    assert client.get("/bacheca").json()["notices"] == []
    assert client.get("/users/usr-003").status_code == 200


def test_homepage_is_the_desk(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "H-OS" in page.text
    assert "bacheca" in page.text.lower()
    assert 'id="formula"' in page.text
    assert "Accetta i termini" in page.text
    assert "DISLIKE" in page.text and "LIKE" in page.text
    assert "Prenotazioni" in page.text
    assert "non collegato" in page.text
    assert "Bacheca community" in page.text
    assert 'data-map="satellite"' in page.text
    assert "Esri" in page.text
    assert "Mese" in page.text and "Settimana" in page.text


DESK = {
    "nome": "Alex",
    "cognome": "Rossi",
    "email": "alex@campus.example",
    "likes": ["cinema", "finanza", "gaming", "programmazione"],
    "dislikes": ["calcio"],
    "password": "HackDay!1",
}


def test_desk_profile_keeps_no_password(client):
    assert client.get("/desk/profile").status_code == 404
    assert client.post("/match", json={"user_id": "usr-desk"}).status_code == 404
    tags = client.get("/tags").json()
    assert tags["synthetic"] is True
    assert tags["count"] == 25
    assert "programmazione" in tags["tags"]
    created = client.post("/desk/profile", json=DESK)
    assert created.status_code == 200
    body = created.json()
    assert body["id"] == "usr-desk"
    assert body["password_stored"] is False
    assert "password" not in body
    assert body["connectors"] == {"canvas": "mock", "pronote": "mock"}
    assert body["likes"] == DESK["likes"]
    listed = client.get("/users").json()["users"]
    assert len(listed) == 55
    assert all(user["id"] != "usr-desk" for user in listed)
    assert client.post("/desk/profile", json={**DESK, "email": "senza-chiocciola"}).status_code == 422
    assert client.post("/desk/profile", json={**DESK, "likes": ["unicorno"]}).status_code == 422


def test_email_local_part_names_the_desk_and_still_matches(client):
    created = client.post(
        "/desk/profile",
        json={
            "email": "alex@campus.example",
            "likes": ["cinema", "finanza", "gaming", "programmazione"],
            "canvas_link": "https://canvas.example/alex",
            "pronote_link": "https://pronote.example/alex",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["name"] == "Alex"
    assert body["nome"] == "Alex"
    assert body["cognome"] == ""
    assert body["canvas_link"] == "https://canvas.example/alex"
    assert body["pronote_link"] == "https://pronote.example/alex"
    assert "password" not in body
    top = client.post("/match", json={"user_id": "usr-desk", "limit": 1}).json()["matches"][0]
    assert top["event_id"] == "evt-058"
    assert top["score"] == 0.5
    dotted = client.post(
        "/desk/profile",
        json={"email": "alex.rossi@campus.example", "likes": ["cinema"]},
    ).json()
    assert dotted["name"] == "Alex Rossi"


def test_local_likes_match_through_the_same_gate(client):
    assert client.post("/desk/profile", json=DESK).status_code == 200
    match = client.post("/match", json={"user_id": "usr-desk", "limit": 1}).json()
    top = match["matches"][0]
    assert match["method"]["name"] == "jaccard"
    assert top["event_id"] == "evt-058"
    assert top["score"] == 0.5
    assert "pref-desk-finanza" in top["explanation"]
    source = client.get("/sources/pref-desk-finanza")
    assert source.status_code == 200
    assert source.json()["synthetic"] is True
    assert source.json()["access"]["scope"] == "personal"
    cohort = client.post("/match", json={"user_id": "usr-001", "limit": 1}).json()["matches"][0]
    assert cohort["event_id"] == "evt-058"
    assert cohort["company"] == []
    proposed = client.post("/agent/tick", json={"user_id": "usr-desk"}).json()
    assert proposed["status"] == "proposed"
    action = proposed["action"]
    assert action["event_id"] == "evt-058"
    assert action["status"] == "pending"
    assert action["trace"]["event"]["signal"] == "preference_overlap"
    for step in ("event", "context", "reasoning", "action"):
        summary = action["trace"][step]["summary"]
        for citation in action["trace"][step]["citations"]:
            assert citation["source_id"] in summary
    assert client.get("/bacheca", params={"user_id": "usr-desk"}).json()["notices"] == []
    approved = client.post("/agent/approve", json={"action_id": action["id"], "decision": "approve"})
    assert approved.status_code == 200
    assert approved.json()["notice"]["delivered_externally"] is False
    assert client.get("/bacheca", params={"user_id": "usr-001"}).json()["notices"] == []
    cleared = client.post("/demo/reset").json()
    assert cleared["cleared"] == 1
    assert client.get("/desk/profile").status_code == 200
    assert client.get("/bacheca", params={"user_id": "usr-desk"}).json()["notices"] == []


def test_loader_rejects_unmarked_people(tmp_path):
    for name in ("places.json", "events.json", "emails.json", "tags.json"):
        (tmp_path / name).write_text((ROOT / "data" / name).read_text(encoding="utf-8"), encoding="utf-8")
    users = json.loads((ROOT / "data" / "users.json").read_text(encoding="utf-8"))
    users["synthetic"] = False
    (tmp_path / "users.json").write_text(json.dumps(users), encoding="utf-8")
    with pytest.raises(ValueError, match="synthetic"):
        load_corpus(tmp_path)
    (tmp_path / "users.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="synthetic"):
        load_corpus(tmp_path)


def test_gemma_cannot_invent_sources(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake(prompt, key, model):
        assert key == "test-key"
        return json.dumps({"notes": ["Ci vediamo a evt-inventato, promesso, con tante parole di contorno inutili."]})

    monkeypatch.setattr("app.narrate.gemma_complete", fake)
    body = client.post("/match", json={"user_id": "usr-001", "limit": 1}).json()
    match = body["matches"][0]
    assert match["display_by"] == "fallback_after_gemma"
    assert match["why"] == match["display_text"]
    assert match["display_text"] != match["explanation"]
    assert "evt-058" in match["why"]
    assert "evt-inventato" not in match["display_text"]
    assert "evt-inventato" not in [item["source_id"] for item in match["citations"]]


def test_gemma_rewrite_keeps_required_ids(client, monkeypatch):
    first = client.post("/match", json={"user_id": "usr-001", "limit": 1}).json()["matches"][0]
    note = (
        f"Alex usr-001 tiene {first['pref_ids'][0]} e dovrebbe vedere {first['event_id']} "
        f"vicino a {first['location_id']}."
    )
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake(prompt, key, model):
        assert "perché ti consiglio questo" in prompt
        assert first["event_id"] in prompt
        assert first["pref_ids"][0] in prompt
        return json.dumps({"notes": [note]})

    monkeypatch.setattr("app.narrate.gemma_complete", fake)
    body = client.post("/match", json={"user_id": "usr-001", "limit": 1}).json()
    match = body["matches"][0]
    assert body["display_by"] == "gemma"
    assert match["display_by"] == "gemma"
    assert match["why"] == note
    assert match["display_text"] == note
    assert first["pref_ids"][0] in [item["source_id"] for item in match["citations"]]


def test_gemma_http_failure_uses_the_template(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def boom(prompt, key, model):
        raise RuntimeError("down")

    monkeypatch.setattr("app.narrate.gemma_complete", boom)
    match = client.post("/match", json={"user_id": "usr-001", "limit": 1}).json()["matches"][0]
    assert match["display_by"] == "fallback_after_gemma"
    assert match["why"] == match["display_text"]
    assert "evt-058" in match["why"]
    assert "Approva" in match["why"]


def test_why_template_is_grounded_italian():
    match = {
        "user_name": "Alex Rossi",
        "user_id": "usr-001",
        "overlapping_tags": ["finanza", "programmazione"],
        "pref_ids": ["pref-001-finanza", "pref-001-programmazione"],
        "location_name": "Biblioteca",
        "location_id": "loc-library",
        "building": "Building 3",
        "score": 0.5,
        "formula": "jaccard",
        "title": "Progetto collaborativo: finanza",
        "event_id": "evt-058",
    }
    text = why_template(match)
    assert 2 <= len(text.split(". ")) <= 4
    allowed = {"usr-001", "pref-001-finanza", "pref-001-programmazione", "evt-058", "loc-library"}
    assert text_is_grounded(text, allowed, {"evt-058", "pref-001-finanza"})


def test_grounding_rules():
    allowed = {"usr-001", "pref-001-finanza", "evt-058", "loc-library"}
    good = "Alex usr-001 tiene pref-001-finanza e dovrebbe vedere evt-058 vicino a loc-library."
    assert text_is_grounded(good, allowed, {"evt-058", "pref-001-finanza"})
    assert not text_is_grounded("Vieni e basta, senza fonti, ma con tante parole di contorno inutili.", allowed, {"evt-058"})
    assert not text_is_grounded(
        "Alex usr-001 vede evt-falso e pref-001-finanza da qualche parte nel campus.",
        allowed,
        {"evt-058"},
    )


def test_generator_cohort_matches(tmp_path):
    from data.generate import build

    users_doc, events_doc, emails_doc = build(8, 6, 20261024)
    tmp_path.joinpath("users.json").write_text(json.dumps(users_doc), encoding="utf-8")
    tmp_path.joinpath("events.json").write_text(json.dumps(events_doc), encoding="utf-8")
    tmp_path.joinpath("emails.json").write_text(json.dumps(emails_doc), encoding="utf-8")
    corpus = load_corpus(tmp_path)
    assert len(corpus.users) == 8
    ranked = __import__("app.brain", fromlist=["rank_matches"]).rank_matches(corpus, "usr-gen-01", limit=2)
    assert ranked["matches"]
    assert ranked["method"]["name"] == "jaccard"
    for match in ranked["matches"]:
        for citation in match["citations"]:
            assert citation["source_id"] in corpus.by_id
            assert citation["source_id"] in match["explanation"]
