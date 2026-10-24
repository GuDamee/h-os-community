# H-OS frontend ↔ Campus Brain contract (proposal, not a verified existing API)

**Status:** Proposed interface requiring backend teammate approval. Do not deploy this as though these endpoints already exist. Code uses `HttpRegistrationGateway` ONLY after `baseUrl` is configured. All IDs retain the existing formats from the two datasets. A mapping to stable canonical IDs may be negotiated, not silently invented.

## Event/read models

The frontend adapter accepts two **existing**, non-interchangeable sources:

- New: `users.json`, `events.json`, `tags.json` with 40 students, 80 events, 25 tags, e.g. `usr-001`, `evt-017`, `source_id: evt-017`; `capacity` exists but `registered_count` does **not**.
- Original: `dataset.json` with 4 profiles, 17 events, 8 labelled interests, e.g. `U01`, `E009` and `D001`; has `registered_count`, `registration_deadline`, status, clubs, document IDs.

Read APIs **to agree with backend teammate**:

- `GET /api/me` → `{ "id": "usr-001", "name": "...", "preferences": ["AI"] }` with real identity server-side.
- `PATCH /api/me/preferences` body `{ "preferences": ["AI", "design"] }` → updated student. Preference labels must be validated against the shared tags vocabulary.
- `GET /api/events` → **existing** `events.json` records or agreed wrapper, preserving `id`/`source_id`. Add `available_places` only if authoritative.
- `GET /api/registrations?student_id=...` → authoritative registrations for My Agenda (server derives authenticated student ID, does not trust arbitrary client-selected ID).
- `POST /api/agent/questions` → `{ "message":"...", "student_id":"..." }` and response with answer, `source_ids`, suggested event IDs; do not claim Gemma 4 until confirmed and tested.

## Action/human approval

The UI creates a **client-side pending proposal** (nothing is sent to the API). On explicit approval only:

`POST /api/registrations`

Header `Idempotency-Key: usr-001:evt-017:client-proposal-1` (demonstration format only; production token scheme agreed with backend).

```json
{
  "student_id":"usr-001",
  "event_id":"evt-017",
  "approval_id":"client-proposal-1",
  "idempotency_key":"usr-001:evt-017:client-proposal-1"
}
```

Expected response **only after successful booking**, e.g.:

```json
{
  "registration_id":"reg-server-generated",
  "student_id":"usr-001",
  "event_id":"evt-017",
  "status":"confirmed"
}
```

`status` may also be `waitlisted` where the backend explicitly allows it. Do not use `simulated` on the real API. After success, backend persistence is authoritative; refreshing My Agenda must query the server. Reject/error must not write agenda.

**Backend responsibilities:** authenticate student; validate authorization and approval, validate event existence/ID and available capacity using an atomic transaction; enforce deadline and dedup/idempotency; reject stale or cancelled events; provide safe CORS/session configuration; issue server-side reference/source metadata; return structured errors. The frontend's demo checks are UX only, not security.

**Open questions for teammate:** API base URL, stack/framework, canonical schema (17-event or 80-event), source-id stability, date/time offsets and timezone, event capacity availability, auth/session strategy, registration state semantics and waitlisting, LLM endpoint and provenance, persistence, error codes, GitHub branch/deployment.

## AI provenance

The current deterministic demo assistant only supports dataset-backed event information and returns `source_id`; it is **not** Gemma 4 and does not claim to be. A future backend response needs a structured `source_ids` array, validated against the event store, and an optional `suggested_action` (type `register_event`, `event_id`, `requires_approval=true`); no mutation occurs from model text.
