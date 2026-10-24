# Architecture

The engine that runs is this repo: FastAPI (`app/main.py`) serving the **H-ELP** student desk in `static/`. Upstream agent projects are inspiration. None of them is imported.

The student desk is the vertical bacheca. **Chiedi ad H-ELP** calls `POST /assistant/ask`. **Sondaggio** stays in the browser. The left drawer opens Mappa eventi, Prenotazioni, Feedback, and Chatta. Chatta composes an email to Student Office, Student Life, or a docente and does not message another student. There is no bottom floating button.

A bacheca notice is a separate gate. `POST /agent/tick` prepares one proposal. `POST /agent/approve` is the only way it is posted. Until then `GET /bacheca` has no new notice, and `delivered_externally` stays false.

## What runs

| Piece | Where | Status |
| --- | --- | --- |
| Desk UI | `static/` | **REAL** in this process |
| Jaccard and overlap match | `app/brain.py`, `app/scoring.py` | **REAL** |
| Cited “perché” | `app/narrate.py` | **REAL** template. Gemma only with `GEMINI_API_KEY`, and only when the note still cites real ids |
| Approval before a notice | `app/agent.py`, `app/store.py` | **REAL** |
| Campus ask over the JSON | `app/campus_agent.py` | **REAL** local retrieval. No agent package is installed |
| Community boards and calendar | `app/community.py`, `data/community.json`, `data/calendar.json` | **REAL** synthetic feed |
| Students, events, emails | `data/` | **MOCKED** synthetic data |
| Canvas, Pronote, email send, Prenota | The form and Chatta | **MOCKED**. Nothing is dialed and no email leaves the browser |
| Map | Leaflet in `static/app.js` | **REAL** Esri World Imagery by default, OpenStreetMap on **Strade**. Pins are schematic |
| GBrain, PipesHub, OpenInstinct | Inspiration only | Not installed. This tree does not contain their code |

`/health` reports `inspiration_installed: false` and `license: MIT`.

## Process

One Python process. `./run.sh` serves the API and `static/` on port **47231**. After a clone, hard-refresh the desk with **Ctrl+F5**. Approvals live in `var/hos.sqlite`, which is created on first run and is not committed. Do not put `GEMINI_API_KEY` in git.
