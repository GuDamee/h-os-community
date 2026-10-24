"""HTTP surface for the H-OS student demo."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from math import comb
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app import __version__
from app.access import emails_for
from app.agent import approve as approve_action
from app.agent import tick as tick_agent
from app.brain import match_user
from app.campus import (
    approve_registration,
    ask_campus,
    calendar_payload,
    build_memory,
    community_feed,
    ingest_event,
    legacy_events,
    library_events,
    lookup_extra_source,
    propose_registration,
    public_agenda,
    recommendations_payload,
    reject_registration,
)
from app.corpus import ROOT, Corpus, demo_now, load_corpus
from app.desk import DESK_ID, normalize_profile, public_desk, with_desk_user
from app.narrate import narration_configured
from app.scoring import FORMULAS
from app.store import Store

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


class AskIn(BaseModel):
    user_id: str
    message: str = Field(min_length=1, max_length=500)


class ProposeIn(BaseModel):
    user_id: str
    event_id: str


class RegistrationDecisionIn(BaseModel):
    user_id: str
    approval_id: str


class FeedbackIn(BaseModel):
    user_id: str
    body: str = Field(min_length=8, max_length=350)
    rating: int = Field(ge=1, le=5)
    subject: str = Field(default="campus", max_length=160)


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
    nickname: str = Field(default="", max_length=40)
    likes: list[str] = Field(min_length=1, max_length=25)
    dislikes: list[str] = Field(default_factory=list, max_length=25)


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
                        "uses": "Campus Brain",
                        "status": "inspiration",
                        "installed": False,
                    },
                    {
                        "name": "cognee",
                        "repo": "https://github.com/topoteretes/cognee",
                        "uses": "Librarian memory, with PipesHub",
                        "status": "planned",
                        "installed": False,
                    },
                    {
                        "name": "llamaindex",
                        "repo": "https://github.com/run-llama/llama_index",
                        "uses": "retrieve then reason",
                        "status": "planned",
                        "installed": False,
                    },
                    {
                        "name": "smolagents",
                        "repo": "https://github.com/huggingface/smolagents",
                        "uses": "one tool per corpus",
                        "status": "inspiration",
                        "installed": False,
                    },
                    {
                        "name": "haystack",
                        "repo": "https://github.com/deepset-ai/haystack",
                        "uses": "retriever then generator",
                        "status": "inspiration",
                        "installed": False,
                    },
                    {
                        "name": "pydantic-ai",
                        "repo": "https://github.com/pydantic/pydantic-ai",
                        "uses": "typed citations",
                        "status": "inspiration",
                        "installed": False,
                    },
                    {
                        "name": "PipesHub",
                        "repo": "https://github.com/pipeshub-ai/pipeshub-ai",
                        "uses": "Librarian access and citations",
                        "status": "inspiration",
                        "installed": False,
                    },
                    {
                        "name": "paperclip",
                        "repo": "https://github.com/paperclipai/paperclip",
                        "uses": "multi-role orchestration",
                        "status": "planned",
                        "installed": False,
                    },
                    {
                        "name": "langgraph",
                        "repo": "https://github.com/langchain-ai/langgraph",
                        "uses": "HITL interrupt before registration",
                        "status": "planned",
                        "installed": False,
                    },
                    {
                        "name": "OpenInstinct",
                        "repo": "https://github.com/Merit-Systems/OpenInstinct",
                        "uses": "proactive agent + human control",
                        "status": "inspiration",
                        "installed": False,
                    },
                ],
            },
            "role_demo": "studenti",
            "dataset": corpus.dataset,
            "formulas": list(FORMULAS),
            "default_formula": "jaccard",
            "preference_space": _preference_space(corpus),
            "narration_mode": "gemma" if narration_configured() else "deterministic",
            "assistant": "dataset_grounded",
            "retrieval": "real",
            "reasoning": "gemini" if narration_configured() else "deterministic",
            "llamaindex": "planned",
            "cognee": "planned",
            "gemma": "optional" if narration_configured() else "planned",
            "registration_gateway": "simulated_local",
            "remote_registration_api": "not_configured",
            "map": "esri_world_imagery",
            "map_center": {"lat": 45.5665, "lng": 12.4305, "zoom": 18},
            "canonical_library": "evt-120",
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
            extra = lookup_extra_source(source_id)
            if extra is not None:
                return extra
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

    @app.get("/bacheca")
    def bacheca(user_id: str | None = Query(default=None)):
        if user_id and not known_user(user_id):
            raise HTTPException(status_code=404, detail=f"Unknown user {user_id}")
        notices = []
        for action in store.list_actions(user_id=user_id, status="approved"):
            if action["notice"]:
                notices.append(action["notice"])
        return {"notices": notices, "delivered_externally": False}

    @app.get("/recommendations")
    def recommendations(user_id: str, limit: int = Query(default=5, ge=1, le=8)):
        try:
            return recommendations_payload(corpus, store, user_id, limit=limit)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Unknown user {user_id}") from None

    @app.post("/assistant/ask")
    def assistant_ask(body: AskIn):
        try:
            return ask_campus(corpus, store, body.user_id, body.message)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Unknown user {body.user_id}") from None
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/community")
    def community(user_id: str | None = None):
        if user_id and not known_user(user_id):
            raise HTTPException(status_code=404, detail=f"Unknown user {user_id}")
        try:
            return community_feed(corpus, store, user_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Unknown user {user_id}") from None

    @app.get("/calendar")
    def calendar(user_id: str | None = None):
        if user_id and not known_user(user_id):
            raise HTTPException(status_code=404, detail=f"Unknown user {user_id}")
        return calendar_payload(corpus, store, user_id)

    @app.get("/agenda")
    def agenda(user_id: str):
        if not known_user(user_id):
            raise HTTPException(status_code=404, detail=f"Unknown user {user_id}")
        return public_agenda(store, user_id)

    @app.post("/registrations/propose")
    def registrations_propose(body: ProposeIn):
        try:
            return propose_registration(corpus, store, body.user_id, body.event_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Unknown user {body.user_id}") from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/registrations/reject")
    def registrations_reject(body: RegistrationDecisionIn):
        try:
            return reject_registration(corpus, store, body.user_id, body.approval_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Nessuna proposta in attesa con questo id") from None

    @app.post("/registrations/approve")
    def registrations_approve(body: RegistrationDecisionIn):
        try:
            return approve_registration(corpus, store, body.user_id, body.approval_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Unknown user {body.user_id}") from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/library")
    def library(source: str = "library"):
        if source == "legacy":
            events = legacy_events()
            return {
                "source": "legacy",
                "canonical": False,
                "note": "Archived 17-event set. IDs E00x are not evt-* and are not the live Library.",
                "events": events,
                "count": len(events),
            }
        if source != "library":
            raise HTTPException(status_code=422, detail="source must be library or legacy")
        events = library_events(corpus, store)
        return {
            "source": "library",
            "canonical": True,
            "note": "120-event Library with stable evt-* ids. Ingested extras, if any, are appended in this process only.",
            "events": events,
            "count": len(events),
        }

    @app.post("/library/events")
    def library_ingest(payload: dict = Body()):
        try:
            return ingest_event(corpus, store, payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/memory/search")
    def memory_search(q: str = Query(min_length=1, max_length=200)):
        memory = build_memory(corpus, store)
        hits = memory.search(q, limit=5)
        return {
            "engine": "local-graph",
            "cognee": "planned",
            "cognee_installed": False,
            "memify": "planned",
            "nodes": len(memory.nodes),
            "edges": len(memory.edges),
            "query": q,
            "hits": hits,
        }

    @app.get("/feedback")
    def read_feedback():
        return {"synthetic": True, "visibility": "public", "feedback": store.list_feedback()}

    @app.post("/feedback")
    def write_feedback(body: FeedbackIn):
        if not known_user(body.user_id):
            raise HTTPException(status_code=404, detail=f"Unknown user {body.user_id}")
        if body.user_id == DESK_ID:
            profile = store.get_desk_profile()
            author = public_desk(profile)["name"] if profile else "Studente"
        else:
            author = corpus.users_by_id[body.user_id]["name"]
        return store.add_feedback(body.user_id, author, body.rating, body.body.strip(), body.subject.strip())

    @app.post("/demo/reset")
    def reset_demo():
        cleared = store.reset()
        return {"cleared": cleared, "note": "Approvals removed. Synthetic JSON was not touched."}

    @app.get("/")
    def index():
        response = FileResponse(STATIC / "index.html")
        response.headers["Cache-Control"] = "no-store"
        return response

    app.mount("/static", NoCacheStatic(directory=STATIC), name="static")
    return app


def _preference_space(corpus) -> dict | None:
    if corpus.dataset != "team" or not corpus.vocabulary:
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
