"""Campus agent: retrieval over the synthetic JSON + docs, then Gemini reasons over it.

Pattern borrowed from smolagents / LlamaIndex "retrieve -> reason -> cite":
1. Librarian: index every record (events, calendar, community, emails, places, docs/*.md)
   with a stable source id.
2. Retrieve top-k by BM25-style scoring for the question (plus personal matches).
3. Gemini answers ONLY from those records and must return the ids it used.
   Ids not in the retrieved set are dropped. No key / failure -> mode "retrieval"
   returns the retrieved records themselves (never a canned sentence).
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from collections import Counter
from pathlib import Path

import httpx

log = logging.getLogger("hos.agent")
ROOT = Path(__file__).resolve().parents[1]
WORD = re.compile(r"[a-z0-9àèéìòù]+")
STOP = set("il lo la i gli le un una di da in con su per tra fra e o che chi cosa come quando dove quale quali c'è ce sono è the a an of to and or is are what when where which who for on at me mi ti".split())


def _tok(text: str) -> list[str]:
    return [w for w in WORD.findall(text.lower()) if w not in STOP and len(w) > 1]


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def build_index(data_dir: Path) -> list[dict]:
    docs: list[dict] = []

    def add(sid, kind, text):
        if text and sid:
            docs.append({"id": str(sid), "kind": kind, "text": " ".join(str(text).split())[:700]})

    ev = _read(data_dir / "events.json") or {}
    for e in ev.get("events", ev if isinstance(ev, list) else []):
        loc = e.get("location")
        where = loc.get("building") or loc.get("name") if isinstance(loc, dict) else loc
        add(e.get("id"), "evento", f"Evento: {e.get('title')}. Quando: {e.get('start') or e.get('date')} {e.get('time','')}. "
            f"Dove: {where or e.get('location_name','')}. Organizza: {e.get('host') or e.get('organizer','')}. "
            f"Tag: {', '.join(e.get('tags') or [])}. {e.get('description') or e.get('blurb') or ''}")
    cal = _read(data_dir / "calendar.json") or {}
    for i, r in enumerate([x for v in (cal.values() if isinstance(cal, dict) else [cal]) if isinstance(v, list) for x in v if isinstance(x, dict)]):
        add(r.get("id") or f"cal-{i}", r.get("kind") or "calendario",
            f"{r.get('kind','')}: {r.get('title')}. {r.get('weekday') or r.get('date','')} {', '.join(r.get('dates') or [])} {r.get('start','')}-{r.get('end','')}. "
            f"Dove: {r.get('location','')}. {r.get('blurb','')}")
    com = _read(data_dir / "community.json") or {}
    for b in com.get("boards") or []:
        for j, m in enumerate(b.get("messages") or []):
            add(m.get("id") or f"{b.get('id')}-{j}", "community",
                f"Canale {b.get('name')}. {m.get('org') or m.get('role') or ''} {m.get('author','')} ({m.get('at') or m.get('time','')}): {m.get('text')}")
    for name in ("emails.json", "places.json"):
        d = _read(data_dir / name) or {}
        for key, rows in (d.items() if isinstance(d, dict) else [("x", d)]):
            if isinstance(rows, list):
                for r in rows:
                    if isinstance(r, dict) and r.get("id"):
                        add(r["id"], name[:-5], json.dumps({k: v for k, v in r.items() if k != "id"}, ensure_ascii=False))
    for md in list((ROOT / "docs").glob("*.md")) + [ROOT / "README.md"]:
        if md.exists():
            for k, chunk in enumerate(re.split(r"\n(?=#)", md.read_text(encoding="utf-8", errors="ignore"))):
                add(f"doc-{md.stem.lower()}-{k}", "doc", chunk)
    for d in docs:
        d["tf"] = Counter(_tok(d["text"]))
        d["len"] = sum(d["tf"].values()) or 1
    return docs


def retrieve(index: list[dict], question: str, k: int = 8) -> list[dict]:
    q = _tok(question)
    if not q or not index:
        return []
    q_low = question.lower()
    qset = set(q)
    n = len(index)
    avg = sum(d["len"] for d in index) / n
    df = Counter(t for d in index for t in set(d["tf"]))
    scored = []
    for d in index:
        s = 0.0
        for t in q:
            # prefix match so "lezioni" hits "lezione", "eventi" hits "evento"
            f = d["tf"].get(t, 0) or sum(c for w, c in d["tf"].items() if len(t) > 4 and w[:5] == t[:5])
            if f:
                idf = math.log(1 + (n - df.get(t, 1) + 0.5) / (df.get(t, 1) + 0.5))
                s += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * d["len"] / avg))
        # Prefer canonical lesson/event titles (e.g. "Business English" -> les-be)
        title_m = re.search(r"(?i)(?:evento|lezione|calendario)\s*:?\s*([^.\n]+)", d["text"])
        if title_m:
            title = title_m.group(1).strip()
            title_toks = _tok(title)
            if title and title.lower() in q_low:
                s += 12.0
            elif title_toks and all(any(t == x or (len(t) > 3 and (t.startswith(x) or x.startswith(t))) for x in qset) for t in title_toks):
                s += 7.0
            if d.get("kind") in {"lezione", "calendario", "evento"} and title_toks and len(set(title_toks) & qset) >= max(1, len(title_toks) - 0):
                s += 3.0
        # Stable series ids like les-be should win over chat noise for course names
        if str(d.get("id", "")).startswith("les-") and any(t in d["text"].lower() for t in q):
            s += 2.5
        if any(k in q_low for k in ("dopo le 18", "seral", "evening", "aperitivo")) and d.get("kind") in {"evento", "calendario"}:
            if any(tok in d["text"] for tok in ("18:", "19:", "20:", "21:")):
                s += 4.0
        if s > 0:
            scored.append((s, d))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:k]]


def gemini(prompt: str) -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("HOS_AGENT_MODEL") or os.getenv("GEMMA_MODEL") or "gemini-3.5-flash"
    last_err = None
    for attempt in range(3):
        r = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": key, "content-type": "application/json"},
            json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0.4, "maxOutputTokens": 900}},
            timeout=45.0,
        )
        if r.status_code in (429, 503):
            last_err = RuntimeError(f"transient {r.status_code}")
            time.sleep(1.2 * (attempt + 1))
            continue
        r.raise_for_status()
        data = r.json()
        cand = (data.get("candidates") or [{}])[0]
        content = cand.get("content") or {}
        parts = content.get("parts") or []
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        if not text and isinstance(cand.get("text"), str):
            text = cand["text"]
        if not text:
            raise RuntimeError(f"empty model response status={r.status_code}")
        return text
    raise last_err or RuntimeError("gemini unavailable")


def ask(index: list[dict], question: str, extra: list[dict] | None = None, history: list[dict] | None = None) -> dict:
    hits = (extra or []) + retrieve(index, question)
    seen, ctx = set(), []
    for h in hits:
        if h["id"] not in seen:
            seen.add(h["id"]); ctx.append(h)
    ctx = ctx[:10]
    if os.getenv("GEMINI_API_KEY", "").strip():
        records = "\n".join(f"[{h['id']}] ({h['kind']}) {h['text']}" for h in ctx) or "(nessun record trovato)"
        hist = "\n".join(f"{m.get('role')}: {m.get('text')}" for m in (history or [])[-6:])
        prompt = (
            "Sei H-OS, l'agente del campus H-FARM College. Ragiona sui RECORD qui sotto (sono l'unica fonte di verità; "
            "dati sintetici). Rispondi nella lingua della domanda, in modo specifico alla domanda: confronta, filtra per giorno/orario, "
            "suggerisci cosa fare, proponi un'azione se utile (es. iscriversi: serve sempre approvazione dello studente). "
            "Se i record non bastano dillo e suggerisci cosa chiedere. Non inventare eventi, orari o persone. "
            "Cita gli id tra parentesi quadre nel testo.\n"
            'Rispondi SOLO JSON: {"answer":"...","sources":["id",...],"suggested_action":null|{"type":"register","event_id":"..."}}\n\n'
            f"CONVERSAZIONE:\n{hist}\n\nRECORD:\n{records}\n\nDOMANDA: {question}"
        )
        try:
            raw = gemini(prompt).strip()
            if not raw:
                raise ValueError("empty model text")
            if raw.startswith("`"):
                raw = raw[3:]
                if raw.lower().startswith("json"):
                    raw = raw[4:]
                if "`" in raw:
                    raw = raw[:raw.rfind("`")]
                raw = raw.strip()
            allowed = {h["id"] for h in ctx}
            data = None
            start, end = raw.find("{"), raw.rfind("}")
            if start >= 0 and end > start:
                try:
                    data = json.loads(raw[start:end + 1])
                except json.JSONDecodeError:
                    data = None
            if isinstance(data, dict):
                srcs = [s for s in (data.get("sources") or []) if s in allowed] or [h["id"] for h in ctx[:3]]
                act = data.get("suggested_action")
                if not (isinstance(act, dict) and act.get("event_id") in allowed):
                    act = None
                answer = (data.get("answer") or data.get("reply") or "").strip() or raw
            else:
                # Prose answer still counts as gemini-rag; cite retrieved ids.
                answer = raw
                cited = [sid for sid in allowed if f"[{sid}]" in raw or sid in raw]
                srcs = cited or [h["id"] for h in ctx[:3]]
                act = None
            if answer.lstrip().startswith("{"):
                try:
                    blob = json.loads(answer[answer.find("{"): answer.rfind("}") + 1])
                    if isinstance(blob, dict) and (blob.get("answer") or blob.get("reply")):
                        answer = (blob.get("answer") or blob.get("reply") or "").strip()
                        extra_srcs = [s for s in (blob.get("sources") or []) if s in allowed]
                        if extra_srcs:
                            srcs = extra_srcs
                        act2 = blob.get("suggested_action")
                        if isinstance(act2, dict) and act2.get("event_id") in allowed:
                            act = act2
                except Exception:
                    pass
            return {"reply": answer, "sources": srcs, "suggested_action": act,
                    "mode": "gemini-rag", "retrieved": [h["id"] for h in ctx]}
        except Exception as exc:  # noqa: BLE001
            log.warning("gemini agent failed: %s", exc)
    if not ctx:
        return {"reply": "Non trovo record su questo nei dati del campus. Prova con un titolo, un giorno o un club.",
                "sources": [], "mode": "retrieval", "retrieved": []}
    lines_out = [f"{h['text'][:220]} [{h['id']}]" for h in ctx[:4]]
    reply = "Dai dati campus (retrieval, senza modello):\n" + "\n".join(f"• {ln}" for ln in lines_out)
    return {"reply": reply, "sources": [h["id"] for h in ctx[:4]], "mode": "retrieval", "retrieved": [h["id"] for h in ctx]}
