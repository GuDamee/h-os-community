# Architecture

The engine that runs is this repo: FastAPI (`app/main.py`) and the registration session in `app/hos_core.py` (the same rules as `reference/hos-core`). Upstream agent projects are inspiration. None of them is imported.

## Happy path

One path, visible on the desk after signup. The button is **Chiedi un evento**. It sends `Recommend an event`.

1. **Librarian** reads the synthetic library and returns passages with `source_ids`. `POST /assistant/ask`.
2. **Campus Brain** ranks future events by coverage against the student's tags. The same response carries `recommendations`.
3. **Agent** creates a proposal only. `POST /registrations/propose`. The agenda stays empty.
4. **Human** presses **Approva** or **Rifiuta**. Nothing is registered on propose.
5. **Action** writes one simulated registration. `POST /registrations/approve`, then `GET /agenda`.

Jaccard matching (`POST /match`) and the bacheca tick (`POST /agent/tick`) stay a separate gate. They do not register an event.

## Librarian, Brain, Agent

| Role | Inspiration (not installed) | What actually runs | Status |
| --- | --- | --- | --- |
| Librarian | [Cognee](https://github.com/topoteretes/cognee), [LlamaIndex](https://github.com/run-llama/llama_index), [Haystack](https://github.com/deepset-ai/haystack), [smolagents](https://github.com/huggingface/smolagents), [PydanticAI](https://github.com/pydantic/pydantic-ai), [PipesHub](https://github.com/pipeshub-ai/pipeshub-ai) | `app/campus_agent.py` retrieves events, community posts, and docs separately, drops the weaker hits, then replies with those `source_id`s. Gemini may rewrite the reply. The answer is a pydantic model. None of those five packages is imported | **REAL** retrieval, local reason step, deterministic reply, and citation check. **PLANNED** for Cognee and LlamaIndex packages. **Inspiration** for smolagents, Haystack, PydanticAI, and PipesHub |
| Campus Brain | [GBrain](https://github.com/garrytan/gbrain) | `app/brain.py` ranks Jaccard matches and cites ids. `app/campus.py` ranks the ask recommendation with the coverage score from `app/hos_core.py` | **REAL** ranking in our code. **Inspiration** for GBrain: the repo is not vendored |
| Agent | [Paperclip](https://github.com/paperclipai/paperclip) for multi-role orchestration, [LangGraph](https://github.com/langchain-ai/langgraph) for a human interrupt, [OpenInstinct](https://github.com/Merit-Systems/OpenInstinct) for propose-then-approve | `app/hos_core.py` holds the proposal until `approve`. `app/agent.py` does the same for a bacheca notice. The tick names the roles `librarian`, `campus_brain`, `student_agent`, `human` inside this one process | **REAL** interrupt: propose does not register; approve is the only write to the agenda. **PLANNED** for Paperclip and LangGraph: neither package is installed |

`/health` reports `inspiration_installed: false`. Cognee, Paperclip, and LangGraph are `status: planned`.

## REAL, MOCKED, PLANNED

| Piece | Status |
| --- | --- |
| FastAPI desk, `app/hos_core.py`, sourced ask, coverage recommendation, propose / approve / agenda | **REAL** |
| Jaccard match, bacheca approval, SQLite for proposals and registrations | **REAL** |
| Local librarian graph in `app/memory.py` | **REAL** as our graph. Cognee itself is **PLANNED** |
| LlamaIndex-style retrieve-then-reason | **REAL** as our node retrieval plus reasoning. The LlamaIndex package is **PLANNED** |
| `app/campus_agent.py` pipeline retrieve → reason → reply → cite | **REAL** over events, community, and `data/docs`. Each corpus is searched on its own, then weaker token hits are set aside before the reply. smolagents, Haystack, and PydanticAI are **inspiration** and are not installed |
| Feedback subject | **REAL** form: event title, date, comment chips, and an optional typed line. The note is synthetic |
| Ask reasoning | **REAL** deterministic reply: the trace compares coverage or token weight, names the hits set aside, and the reply cites only the passages that survived. It is not a free chat reply |
| Gemini on the retrieved passages | **REAL** call only when `GEMINI_API_KEY` is set and every id in the JSON trace was retrieved. The call sees the passages that survived the local reason step. A missing key, a failed call, or an invented id keeps the deterministic reply. No key: **PLANNED** |
| Students, events, posts, lessons, emails | **MOCKED** synthetic data |
| Canvas, Pronote, remote registration API | **MOCKED**. Links are stored and never opened. The gateway writes `status: simulated` |
| Map tiles | **REAL** Esri World Imagery in the browser, centered on 45.5665, 12.4305. Pins are a schematic of the dataset, not a survey |
| GBrain, PipesHub, OpenInstinct, Cognee, Paperclip, LangGraph | Not mocked products. They are real upstream repos. This tree does not contain their code |

## Process

One Python process. `./run.sh` serves the API and `static/` on port 47231. Approvals live in `var/hos.sqlite`, which is created on first run and is not committed.
