# H-OS — frontend integration patch + verification harness

**Not a patch applied to a previously published live site.** Source files for that website were unavailable. This package contains working, framework-agnostic JavaScript modules + a small separate local test page that exercises the end-to-end workflow. Do NOT deploy this page in place of the existing site without reviewing and integrating its modules with the existing codebase.

## What is actually implemented (tested)

- `src/hos-core.mjs`: adapters for both EXISTING synthetic event schemas (17-event legacy and 80-event new), preference-aware ranking, source-linked assistant answers, approval-gated action, agenda update on gateway success, and a production-shaped HTTP adapter (endpoint not configured).
- `demo/index.html` + `demo/main.mjs`: standalone **local verification harness** with H-OS branding, student selection, preferences, event search, recommendations, dataset-guided assistant, approval dialog and in-memory agenda. The UI is not a change to the original site's design.
- `tests/hos-core.test.mjs`: automated tests including 17/80 data, changes in recommendations, source grounding, no available seat invention, cancelled/full events, approval-before-registration and backend failure.
- `docs/BACKEND_CONTRACT.md`: proposed API contracts for teammate review (not implemented server endpoints).
- `data/`: unmodified datasets from the previous project conversation.

## Verify locally

Requires Node 20+ to run tests (no dependency install). Python 3 only for serving local static files.

```sh
npm test
python3 -m http.server 8080
```

Open `http://localhost:8080/demo/`. File `demo/index.html` cannot reliably load JSON through `file://` due to browser restrictions.

90-second journey: select `usr-001`, toggle `AI` + `design`, click **Save preferences** → see sorted “Recommended for you” → enter “Consigliami un evento” → **Ask H-OS** → **Propose registration** → verify **My Agenda** remains empty until **Approve simulated registration** → approve → see event appear in My Agenda with `SIMULATED REGISTRATION`.

Change preferences to `musica` and verify top events/titles change. Change dataset to **Original demo** to verify full/waitlist/closed handling. Ask about transport or other unknowns: assistant refuses unsupported claims. Without original source code, no browser test has been run on the published site.

## Integrating into existing app

1. **Do not overwrite** existing UI. Import `normalizeDataset`, `recommendEvents`, `answerEventQuestion`, `HOSSession` from `src/hos-core.mjs` into the existing event store/state layer.
2. Feed current `users.json` + `events.json` or the original `dataset.json` to the adapter. Keep IDs and source IDs unchanged.
3. Connect existing onboarding preferences to `session.setPreferences([...])` and refresh recommendations with `session.recommendations()`.
4. Connect existing assistant panel to `session.ask(question)`; display source IDs as provenance. Label as guided/deterministic until Gemma 4 is tested.
5. Connect registration CTA to `session.propose(eventId)`; show existing confirmation component with event ID, source, and approval ID. **Never** automatically call `approve()`.
6. After user clicks Approve, call `await session.approve(pending.approval_id)` and update existing My Agenda from `session.agenda`. In demo mode this is in-memory and expires on page reload; in backend mode query persisted authoritative registrations.
7. Only after backend teammate approves API contract, configure `HttpRegistrationGateway({baseUrl: ...})`. Do not implement extra fake services.
8. User-visible titles, navigation, the assistant, and the footer in this package say H-OS.

## Deployment & factual status

- Existing website: `https://help-campus-ferry-demo.gardennova4096.chatgpt.site` (not updated here).
- This package: local-only reference implementation, not a published site, not a replacement for original design.
- Gemma 4: **not connected**.
- Real student identity/email verification: **not connected**.
- Backend/database persistence: **not connected**.
- Event registrations: only **explicitly simulated** in local demo mode; server adapter code is inert until configured.
- “Available places” cannot be inferred for 80-event data: only total capacity is known.
- Feedback, real campus map, clubs and rich announcements: belong to the original app, NOT reimplemented or verified here.
