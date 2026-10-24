"""HTTP surface for the H-OS student demo."""

from __future__ import annotations

import logging
import re
import os
from contextlib import asynccontextmanager
from math import comb
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app import __version__
from app.access import emails_for
from app.agent import approve as approve_action
from app.agent import tick as tick_agent
from app.brain import match_user
from app.corpus import ROOT, Corpus, demo_now, load_corpus
from app.desk import DESK_ID, normalize_profile, public_desk, with_desk_user
from app.narrate import narration_configured
from app.scoring import FORMULAS
from app.store import Store
from app.community import (
    append_message,
    board_detail,
    boards_summary,
    calendar_payload,
    load_calendar,
    load_community,
)

log = logging.getLogger("hos")
STATIC = ROOT / "static"


class MatchIn(BaseModel):
    user_id: str
    limit: int = Field(default=4, ge=1, le=8)
    formula: str = "jaccard"


class TickIn(BaseModel):
    user_id: str | None = None
    formula: str = "jaccard"


class ApproveIn(BaseModel):
    action_id: str
    decision: str = "approve"


class DeskIn(BaseModel):
    """Local profile. Extra keys, including a password, are ignored and not stored."""

    model_config = ConfigDict(extra="ignore")
    nome: str = Field(default="", max_length=80)
    cognome: str = Field(default="", max_length=80)
    email: str = Field(min_length=3, max_length=120)
    canvas_id: str = Field(default="", max_length=300)
    pronote_id: str = Field(default="", max_length=300)
    canvas_link: str = Field(default="", max_length=300)
    pronote_link: str = Field(default="", max_length=300)
    likes: list[str] = Field(min_length=1, max_length=25)
    dislikes: list[str] = Field(default_factory=list, max_length=25)


class CommunityPostIn(BaseModel):
    author: str = Field(default="", max_length=80)
    text: str = Field(min_length=1, max_length=800)


class FeedbackIn(BaseModel):
    subject: str = Field(default="", max_length=200)
    body: str = Field(default="", max_length=2000)
    synthetic: bool = True


class AssistantIn(BaseModel):
    question: str = Field(min_length=1, max_length=400)
    likes: list[str] = Field(default_factory=list)
    user_id: str | None = None
    history: list[dict] = Field(default_factory=list)


class NoCacheStatic(StaticFiles):

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


def create_app(db_path: Path | None = None, data_dir: Path | None = None) -> FastAPI:
    load_dotenv(ROOT / ".env")
    corpus = load_corpus(data_dir)
    database = Path(db_path or os.getenv("HOS_DB", ROOT / "var" / "hos.sqlite"))
    store = Store(database)
    community_dir = Path(data_dir or ROOT / "data")
    if not (community_dir / "community.json").exists():
        community_dir = ROOT / "data"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        mode = "gemma" if narration_configured() else "deterministic"
        log.info("H-OS %s · students only · narration %s · db %s", __version__, mode, database)
        yield

    app = FastAPI(
        title="H-OS",
        version=__version__,
        description=(
            "Student desk of an AI operating system for the H-FARM campus. "
            "Synthetic data, cited matches, human approval before any bacheca notice. "
            "MIT licensed."
        ),
        lifespan=lifespan,
    )
    app.state.corpus = corpus
    app.state.store = store

    @app.get("/health")
    def health():
        counts = store.counts()
        return {
            "status": "ok",
            "service": "h-os",
            "version": __version__,
            "license": "MIT",
            "open_source": {
                "license": "MIT",
                "inspiration_installed": False,
                "patterns": [
                    {
                        "name": "gbrain",
                        "repo": "https://github.com/garrytan/gbrain",
                        "uses": "brain + citations",
                    },
                    {
                        "name": "PipesHub",
                        "repo": "https://github.com/pipeshub-ai/pipeshub-ai",
                        "uses": "knowledge / access",
                    },
                    {
                        "name": "OpenInstinct",
                        "repo": "https://github.com/Merit-Systems/OpenInstinct",
                        "uses": "proactive agent + human control",
                    },
                ],
            },
            "role_demo": "studenti",
            "dataset": corpus.dataset,
            "formulas": list(FORMULAS),
            "default_formula": "jaccard",
            "preference_space": _preference_space(corpus),
            "narration_mode": "gemma" if narration_configured() else "deterministic",
            "demo_now": demo_now().isoformat(),
            "synthetic_data": True,
            "counts": {
                "users": len(corpus.users),
                "events": len(corpus.events),
                "places": len(corpus.places),
                "emails": len(corpus.emails),
                **counts,
            },
        }

    def resolve_corpus(user_id: str) -> Corpus:
        if user_id == DESK_ID:
            profile = store.get_desk_profile()
            if profile is None:
                raise KeyError(user_id)
            return with_desk_user(corpus, profile)
        if user_id not in corpus.users_by_id:
            raise KeyError(user_id)
        return corpus

    def known_user(user_id: str) -> bool:
        if user_id in corpus.users_by_id:
            return True
        return user_id == DESK_ID and store.get_desk_profile() is not None

    @app.get("/tags")
    def list_tags():
        tags = list(corpus.vocabulary or [])
        return {"synthetic": True, "tags": tags, "count": len(tags)}

    @app.get("/desk/profile")
    def read_desk():
        profile = store.get_desk_profile()
        if profile is None:
            raise HTTPException(status_code=404, detail="Nessun accesso locale. La password non è conservata.")
        return public_desk(profile)

    @app.post("/desk/profile")
    def write_desk(body: DeskIn):
        try:
            profile = normalize_profile(body.model_dump(), corpus.vocabulary)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        stored = store.save_desk_profile(profile)
        return public_desk(stored)

    @app.get("/users")
    def list_users():
        return {"users": [_public_user(corpus, user) for user in corpus.users]}

    @app.get("/users/{user_id}")
    def get_user(user_id: str):
        if user_id == DESK_ID:
            profile = store.get_desk_profile()
            if profile is None:
                raise HTTPException(status_code=404, detail=f"Unknown user {user_id}")
            return public_desk(profile)
        user = corpus.users_by_id.get(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail=f"Unknown user {user_id}")
        return _public_user(corpus, user)

    @app.get("/events")
    def list_events():
        return {"events": [_public_event(corpus, event) for event in corpus.events]}

    @app.get("/places")
    def list_places():
        return {
            "synthetic": True,
            "note": corpus.campus_note,
            "viewBox": corpus.view_box,
            "places": corpus.places,
        }

    @app.get("/emails")
    def list_emails(user_id: str | None = None):
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="Pass user_id. Mock email is personal to the student it names. There is no campus-wide inbox.",
            )
        if not known_user(user_id):
            raise HTTPException(status_code=404, detail=f"Unknown user {user_id}")
        return {
            "synthetic": True,
            "user_id": user_id,
            "access": "personal",
            "emails": emails_for(corpus.emails, user_id),
        }

    @app.get("/sources/{source_id}")
    def get_source(source_id: str):
        try:
            return corpus.public_source(source_id)
        except KeyError:
            profile = store.get_desk_profile()
            if profile is not None and (source_id == DESK_ID or source_id.startswith("pref-desk-")):
                try:
                    return with_desk_user(corpus, profile).public_source(source_id)
                except KeyError:
                    pass
            raise HTTPException(status_code=404, detail=f"Unknown source {source_id}") from None

    @app.post("/match")
    def match(body: MatchIn):
        try:
            view = resolve_corpus(body.user_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Unknown user {body.user_id}") from None
        try:
            return match_user(view, body.user_id, limit=body.limit, formula=body.formula)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/agent/tick")
    def tick(body: TickIn | None = None):
        user_id = body.user_id if body else None
        formula = body.formula if body else "jaccard"
        try:
            view = resolve_corpus(user_id) if user_id else corpus
            return tick_agent(view, store, user_id=user_id, formula=formula)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Unknown user {user_id}") from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/agent/approve")
    def approve(body: ApproveIn):
        if body.decision not in {"approve", "dismiss"}:
            raise HTTPException(status_code=422, detail="decision must be approve or dismiss")
        existing = store.get(body.action_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Unknown action {body.action_id}")
        try:
            view = resolve_corpus(existing["user_id"])
            return approve_action(view, store, body.action_id, body.decision)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Unknown action {body.action_id}") from None
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/agent/actions")
    def list_actions(user_id: str | None = None, status: str | None = None):
        if user_id and not known_user(user_id):
            raise HTTPException(status_code=404, detail=f"Unknown user {user_id}")
        if status and status not in {"pending", "approved", "dismissed"}:
            raise HTTPException(status_code=422, detail="status must be pending, approved, or dismissed")
        return {"actions": store.list_actions(user_id=user_id, status=status)}


    @app.get("/community/boards")
    def community_boards():
        doc = load_community(community_dir)
        return {"synthetic": True, "boards": boards_summary(doc)}

    @app.get("/community/boards/{board_id}")
    def community_board(board_id: str):
        doc = load_community(community_dir)
        board = board_detail(doc, board_id)
        if board is None:
            raise HTTPException(status_code=404, detail=f"Bacheca {board_id} non trovata")
        return {"synthetic": True, "board": board}

    @app.post("/community/boards/{board_id}/messages")
    def community_post(board_id: str, body: CommunityPostIn):
        try:
            message = append_message(
                community_dir,
                board_id,
                author=body.author,
                text=body.text,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Bacheca {board_id} non trovata") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"ok": True, "message": message}

    @app.get("/calendar")
    def campus_calendar():
        doc = load_calendar(community_dir)
        return {"synthetic": True, **calendar_payload(doc)}

    @app.get("/bacheca")
    def bacheca(user_id: str | None = Query(default=None)):
        if user_id and not known_user(user_id):
            raise HTTPException(status_code=404, detail=f"Unknown user {user_id}")
        notices = []
        for action in store.list_actions(user_id=user_id, status="approved"):
            if action["notice"]:
                notices.append(action["notice"])
        return {"notices": notices, "delivered_externally": False}

    @app.post("/demo/reset")
    def reset_demo():
        cleared = store.reset()
        return {"cleared": cleared, "note": "Approvals removed. Synthetic JSON was not touched."}


    @app.post("/feedback")
    def feedback_mock(payload: FeedbackIn):
        """Demo-only feedback capture. Subject is Feedback: {event} — {date}."""
        subject = (payload.subject or "").strip() or "Feedback: (senza evento)"
        body = (payload.body or "").strip()
        path = ROOT / "var" / "feedback_demo.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        from datetime import datetime, timezone
        row = {
            "at": datetime.now(timezone.utc).isoformat(),
            "subject": subject[:200],
            "body": body[:2000],
            "synthetic": True,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(_json.dumps(row, ensure_ascii=False) + "\n")
        return {"ok": True, "subject": subject, "body": body, "stored": True, "synthetic": True}


    @app.post("/assistant/ask")
    def assistant_ask(payload: AssistantIn):
        """Dataset-grounded campus Q&A with source ids. Uses Gemma only if configured."""
        from app.narrate import narration_configured, gemma_complete

        q = payload.question.strip()
        q_low = q.lower()
        from app import campus_agent
        if not getattr(app.state, "agent_index", None):
            app.state.agent_index = campus_agent.build_index(community_dir)
        extra = []
        uid = payload.user_id if payload.user_id and known_user(payload.user_id) else None
        if uid and any(k in q_low for k in ("consigl", "recommend", "per me", "interess", "suggest")):
            for m in (match_user(corpus, uid, limit=3, formula="jaccard").get("matches") or []):
                extra.append({"id": str(m.get("event_id")), "kind": "match-personale",
                              "text": f"Match per {uid}: {m.get('title')} score {m.get('score', 0):.2f}. {m.get('why') or ''}"})
        res = campus_agent.ask(app.state.agent_index, q, extra, getattr(payload, "history", None))
        res.update(answer=res["reply"], source_id=(res["sources"] or [None])[0], synthetic=True)
        return res
        sources: list[str] = []
        bits: list[str] = []

        # Calendar / lessons
        cal = calendar_payload(load_calendar(community_dir))
        items = cal.get("items") or []
        for row in items:
            blob = f"{row.get('title','')} {row.get('blurb','')} {row.get('location','')}".lower()
            if any(w in blob for w in q_low.split() if len(w) > 3) or (
                any(k in q_low for k in ("lezione", "calendario", "agenda", "orario")) and row.get("kind") == "lezione"
            ):
                bits.append(
                    f"{'Evento' if row.get('kind')=='evento' else 'Lezione'} «{row.get('title')}»: "
                    f"{row.get('weekday') or row.get('date')} {row.get('start')}–{row.get('end')} · {row.get('location') or 'Campus'}."
                )
                sources.append(str(row.get("id") or "calendar"))
                break

        # Events corpus
        for event in corpus.events:
            title = str(event.get("title") or "")
            desc = str(event.get("description") or event.get("blurb") or "")
            tags = " ".join(event.get("tags") or [])
            blob = f"{title} {desc} {tags}".lower()
            words = [w for w in re.split(r"[^a-z0-9àèéìòù]+", q_low) if len(w) > 2]
            if words and sum(1 for w in words if w in blob) >= max(1, min(2, len(words)//2)):
                loc = event.get("location") or {}
                if isinstance(loc, dict):
                    where = loc.get("building") or loc.get("name") or event.get("location_name") or "campus"
                else:
                    where = loc or event.get("location_name") or "campus"
                bits.append(f"Evento «{title}» ({event.get('id')}). Dove: {where}. {desc[:160]}")
                sources.append(str(event.get("id")))
                if len(bits) >= 2:
                    break

        # Community messages
        doc = load_community(community_dir)
        for board in doc.get("boards") or []:
            for msg in board.get("messages") or []:
                text = str(msg.get("text") or "")
                if any(w in text.lower() for w in q_low.split() if len(w) > 3):
                    bits.append(
                        f"In «{board.get('name')}», {msg.get('org') or msg.get('role')} {msg.get('author')}: «{text}»"
                    )
                    sources.append(str(msg.get("id") or board.get("id")))
                    break
            if len(bits) >= 3:
                break

        # Preference-based tip
        if payload.likes and ("consigli" in q_low or "recommend" in q_low or "interess" in q_low or "per me" in q_low):
            uid = payload.user_id if payload.user_id and known_user(payload.user_id) else None
            if uid:
                matched = match_user(corpus, uid, limit=1, formula="jaccard")
                if matched.get("matches"):
                    m = matched["matches"][0]
                    bits.insert(0, f"Match personale: «{m.get('title')}» score {m.get('score', 0):.2f}. {m.get('why') or m.get('display_text') or ''}")
                    sources.insert(0, str(m.get("event_id")))

        if not bits:
            bits.append(
                f"Nessun record preciso. Corpus: {len(corpus.events)} eventi, "
                f"{len((doc.get('boards') or []))} canali community, {len(items)} voci calendario. "
                "Prova un titolo evento, una lezione o «consigliami un evento»."
            )
            sources.append("corpus-stats")

        reply = " ".join(bits[:3]).strip()
        mode = "rules"
        if narration_configured():
            try:
                polished = gemma_complete(
                    "Rispondi in italiano, max 4 frasi, solo fatti seguenti, cita gli id fonte. "
                    f"Domanda: {q}\nFatti:\n" + "\n".join(bits[:4]),
                    os.getenv("GEMINI_API_KEY", "").strip(),
                    os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it"),
                )
                if polished and len(polished.strip()) > 20:
                    reply = polished.strip()
                    mode = "gemma"
            except Exception as exc:  # noqa: BLE001
                log.warning("assistant gemma skipped: %s", exc.__class__.__name__)

        return {
            "reply": reply,
            "answer": reply,
            "source_id": sources[0] if sources else None,
            "sources": sources[:6],
            "mode": mode,
            "synthetic": True,
        }


    @app.get("/")
    def index():
        response = FileResponse(STATIC / "index.html")
        response.headers["Cache-Control"] = "no-store"
        return response

    app.mount("/static", NoCacheStatic(directory=STATIC), name="static")
    return app


def _preference_space(corpus) -> dict | None:
    if not corpus.vocabulary or not str(corpus.dataset).startswith("team"):
        return None
    return {
        "tags": len(corpus.vocabulary),
        "profile_sizes": [3, 4, 5, 6],
        "theoretical_profiles": sum(comb(len(corpus.vocabulary), k) for k in range(3, 7)),
        "materialized_users": len(corpus.users),
    }


def _public_user(corpus, user: dict) -> dict:
    payload = {
        "id": user["id"],
        "name": user["name"],
        "role": user["role"],
        "year": user["year"],
        "preferences": user["preferences"],
        "synthetic": True,
    }
    for key in ("program", "hometown", "languages", "bio", "interests_text"):
        if user.get(key) not in (None, ""):
            payload[key] = user[key]
    if user.get("hangout_id"):
        hangout = corpus.places_by_id[user["hangout_id"]]
        payload["hangout"] = {"id": hangout["id"], "name": hangout["name"], "zone": hangout["zone"]}
    return payload


def _public_event(corpus, event: dict) -> dict:
    place = corpus.places_by_id[event["location_id"]]
    payload = {
        "id": event["id"],
        "title": event["title"],
        "tags": list(event["tags"]),
        "blurb": event["blurb"],
        "starts_at": event["starts_at"],
        "ends_at": event["ends_at"],
        "capacity": event["capacity"],
        "location_id": place["id"],
        "synthetic": True,
        "location": {
            "id": place["id"],
            "name": place["name"],
            "zone": place["zone"],
            "x": place["x"],
            "y": place["y"],
        },
    }
    for key in ("building", "host", "host_role", "going", "source_id"):
        if event.get(key) is not None:
            payload[key] = event[key]
    return payload


app = create_app()
