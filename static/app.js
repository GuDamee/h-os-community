const CAPTION = "Esri World Imagery sul campus H-FARM, La Serra, Roncade (45.5665, 12.4305). I pin restano lo schema del dataset, non un rilievo. Nessuna chiave Google.";
const CAMPUS_CENTER = [45.5665, 12.4305];
const CAMPUS_ZOOM = 18;
const KIND = { user: "persona", preference: "pref", event: "evento", place: "luogo", email: "mail" };

const state = {
  health: null,
  users: [],
  events: [],
  places: [],
  selectedId: null,
  matches: [],
  method: null,
  displayBy: "deterministic",
  actions: [],
  notices: [],
  idleReason: null,
  busy: null,
  error: null,
  resetArmed: false,
  formula: "jaccard",
  tags: [],
  session: null,
  deskUser: null,
  screen: "access",
  flashNotice: false,
  view: "community",
  recommendations: [],
  posts: [],
  boards: [],
  contacts: [],
  calendar: null,
  agenda: [],
  feedback: [],
  proposal: null,
  chat: [],
  calendarMode: "month",
  calendarAnchor: null,
  boardFilter: "",
  eventModalId: null,
};

const SESSION_KEY = "hos.session.v1";
const DEMO_LIKES = ["cinema", "finanza", "gaming", "programmazione"];

let boardLoad = 0;
let campusMap = null;
let pinLayer = null;
let pinCloseTimer = null;

const SPORT_TAGS = new Set(["sport", "fitness", "calcio", "basket", "running", "ambiente", "sostenibilita"]);
const PIN_KIND = {
  mandatory: "Mandatory",
  student: "Student events",
  sport: "Sport / community",
  campus: "Campus event",
};
const PIN_ICONS = {
  mandatory: '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2.2" y="3.2" width="11.6" height="10.4" rx="1.4" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M2.2 6.4 H13.8 M5.2 2.2 V4.4 M10.8 2.2 V4.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
  student: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="6" cy="5" r="1.8" fill="currentColor"/><circle cx="11" cy="5.6" r="1.4" fill="currentColor"/><path d="M2.6 13.2c.4-2.1 1.8-3.2 3.4-3.2s3 1.1 3.4 3.2M9.4 10c1.1-.3 2.2 0 3 .9.6.7.9 1.4 1 2.2" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>',
  sport: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="11" cy="3" r="1.3" fill="currentColor"/><path d="M2.8 13.4 L6.8 8.6 L9 10.2 L12.4 6.2 M5.8 8.4 L3.8 6.4 M8.8 10.4 L11.2 13.4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  campus: '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2.2" y="3.2" width="11.6" height="10.4" rx="1.4" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M2.2 6.4 H13.8 M5.2 2.2 V4.4 M10.8 2.2 V4.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
};

document.addEventListener("click", onClick);
window.addEventListener("hashchange", () => {
  const id = location.hash.replace("#", "");
  if (!state.busy && knownPerson(id) && id !== state.selectedId) {
    state.selectedId = id;
    if (id !== "usr-desk") document.getElementById("roster").hidden = false;
    refreshStudent();
  }
});

document.getElementById("access-form").addEventListener("submit", submitAccess);
document.getElementById("like-btn").addEventListener("click", () => decideCurrent("like"));
document.getElementById("dislike-btn").addEventListener("click", () => decideCurrent("dislike"));
document.getElementById("skip-btn").addEventListener("click", () => decideCurrent("skip"));
document.getElementById("pref-grid").addEventListener("click", (event) => {
  const button = event.target.closest("[data-tag][data-value]");
  if (!button || !state.session) return;
  setTagChoice(button.dataset.tag, button.dataset.value);
  renderSwipe();
});
document.getElementById("assistant-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.getElementById("assistant-question");
  askAssistant(input.value);
  input.value = "";
});
document.getElementById("feedback-form").addEventListener("submit", (event) => {
  event.preventDefault();
  sendFeedback();
});
document.getElementById("feedback-event").addEventListener("change", () => {
  const select = document.getElementById("feedback-event");
  const event = state.events.find((item) => item.id === select.value);
  if (event?.starts_at) document.getElementById("feedback-date").value = event.starts_at.slice(0, 10);
  feedbackSubject();
});
document.getElementById("feedback-date").addEventListener("change", feedbackSubject);
document.getElementById("enter-map").addEventListener("click", () => enterDesk());
document.getElementById("demo-likes").addEventListener("click", useDemoLikes);
wireSwipe();

document.getElementById("formula").addEventListener("change", (event) => {
  if (state.busy) {
    event.target.value = state.formula;
    return;
  }
  state.formula = event.target.value;
  if (state.selectedId) refreshStudent();
});

wirePersonalize();
boot();

function wirePersonalize() {
  const dialog = document.getElementById("personalize-modal");
  if (dialog && dialog.dataset.wired !== "1") {
    dialog.dataset.wired = "1";
    dialog.addEventListener("click", (event) => {
      const chip = event.target.closest("[data-chip]");
      if (chip) {
        event.preventDefault();
        togglePersonalChip(chip.dataset.chip);
        return;
      }
      if (event.target.closest("[data-personalize='save']")) {
        event.preventDefault();
        savePersonalize();
      }
    });
  }
  for (const button of document.querySelectorAll("[data-open='personalize']")) {
    if (button.dataset.wired === "1") continue;
    button.dataset.wired = "1";
    button.addEventListener("click", (event) => {
      event.preventDefault();
      openPersonalize();
    });
  }
}

function openPersonalize() {
  renderPersonalizeChips();
  const dialog = document.getElementById("personalize-modal");
  const status = document.getElementById("personalize-status");
  if (status) status.textContent = state.session ? "Tocca un chip per tenerlo o lasciarlo." : "Entra prima, poi i chip restano attivi.";
  if (dialog && !dialog.open) dialog.showModal();
}

function renderPersonalizeChips() {
  const box = document.getElementById("personalize-chips");
  if (!box) return;
  const likes = new Set(state.session?.likes || []);
  box.replaceChildren();
  const tags = state.tags.length ? state.tags : Object.keys(TAG_NOTES);
  for (const tag of tags) {
    box.append(el("button", {
      type: "button",
      class: "pref-chip",
      "data-chip": tag,
      "aria-pressed": likes.has(tag) ? "true" : "false",
      text: tag,
    }));
  }
}

function togglePersonalChip(tag) {
  const status = document.getElementById("personalize-status");
  if (!state.session) {
    if (status) status.textContent = "Entra con email e password, poi Personalizza risponde al tap.";
    return;
  }
  const likes = new Set(state.session.likes || []);
  if (likes.has(tag)) likes.delete(tag);
  else likes.add(tag);
  state.session.likes = [...likes];
  state.session.dislikes = (state.session.dislikes || []).filter((item) => !likes.has(item));
  state.session.skipped = (state.session.skipped || []).filter((item) => !likes.has(item));
  saveSession(state.session);
  renderPersonalizeChips();
  if (status) status.textContent = likes.has(tag) ? `${tag} scelto.` : `${tag} tolto.`;
}

async function savePersonalize() {
  const dialog = document.getElementById("personalize-modal");
  if (!state.session) return;
  if (!state.session.likes.length) {
    const status = document.getElementById("personalize-status");
    if (status) status.textContent = "Tieni almeno un interesse.";
    return;
  }
  state.session.prefsConfirmed = true;
  saveSession(state.session);
  if (dialog?.open) dialog.close();
  state.deskUser = deskUserFromSession();
  state.selectedId = state.selectedId || "usr-desk";
  if (state.screen !== "desk") {
    showScreen("desk");
    showView("community");
  }
  try {
    await api("/desk/profile", { method: "POST", body: JSON.stringify(profileBody()) });
    await refreshStudent();
  } catch (error) {
    state.error = error.message || "Preferenze non salvate.";
    render();
  }
}

async function boot() {
  wirePersonalize();
  try {
    const [health, users, events, places, tags] = await Promise.all([
      api("/health"),
      api("/users"),
      api("/events"),
      api("/places"),
      api("/tags"),
    ]);
    state.health = health;
    state.users = users.users;
    state.events = events.events;
    state.places = places.places;
    state.tags = tags.tags;
    state.session = loadSession();
    renderPersonalizeChips();
    paintDate();
    const gate = document.getElementById("gate-status");
    if (gate) gate.textContent = "";
    if (state.session && state.session.prefsConfirmed && state.session.likes.length) {
      state.deskUser = deskUserFromSession();
      const requested = location.hash.replace("#", "");
      state.selectedId = state.users.some((user) => user.id === requested) ? requested : "usr-desk";
      if (state.selectedId !== "usr-desk") document.getElementById("roster").hidden = false;
      showScreen("desk");
      showView("community");
      await api("/desk/profile", { method: "POST", body: JSON.stringify(profileBody()) });
      await refreshStudent();
    } else if (state.session) {
      showScreen("prefs");
    } else {
      showScreen("access");
    }
  } catch (error) {
    state.error = error.message || "H-OS non risponde.";
    const gate = document.getElementById("gate-status");
    if (gate) gate.textContent = state.error;
    showScreen(state.session ? "prefs" : "access");
  }
}

async function refreshStudent() {
  const requestedId = state.selectedId;
  const generation = ++boardLoad;
  const person = selected();
  if (person) document.title = `H-OS · ${person.name}`;
  state.busy = "match";
  state.error = null;
  state.idleReason = null;
  state.matches = [];
  state.actions = [];
  state.notices = [];
  state.method = null;
  render();
  try {
    const [match, actions, board, recs, feed, calendar, agenda, feedback] = await Promise.all([
      api("/match", {
        method: "POST",
        body: JSON.stringify({ user_id: requestedId, limit: 4, formula: state.formula }),
      }),
      api(`/agent/actions?user_id=${encodeURIComponent(requestedId)}`),
      api(`/bacheca?user_id=${encodeURIComponent(requestedId)}`),
      api(`/recommendations?user_id=${encodeURIComponent(requestedId)}&limit=5`),
      api(`/community?user_id=${encodeURIComponent(requestedId)}`),
      api(`/calendar?user_id=${encodeURIComponent(requestedId)}`),
      api(`/agenda?user_id=${encodeURIComponent(requestedId)}`),
      api("/feedback"),
    ]);
    if (generation !== boardLoad || state.selectedId !== requestedId) return;
    state.matches = match.matches;
    state.method = match.method;
    state.displayBy = match.display_by;
    state.actions = actions.actions;
    state.notices = board.notices;
    state.recommendations = recs.recommendations || [];
    state.posts = feed.posts || [];
    state.boards = feed.boards || [];
    state.contacts = feed.contacts || [];
    state.calendar = calendar;
    state.agenda = agenda.registrations || [];
    state.feedback = feedback.feedback || [];
    history.replaceState(null, "", `#${requestedId}`);
    document.title = `H-OS · ${selected().name}`;
  } catch (error) {
    if (generation !== boardLoad || state.selectedId !== requestedId) return;
    state.error = friendlyError(error);
  } finally {
    if (generation === boardLoad) {
      state.busy = null;
      render();
    }
  }
}

async function tickAgent() {
  state.busy = "tick";
  state.error = null;
  state.idleReason = null;
  render();
  try {
    const result = await api("/agent/tick", {
      method: "POST",
      body: JSON.stringify({ user_id: state.selectedId, formula: state.formula }),
    });
    if (result.status === "idle") state.idleReason = result.reason;
    await reloadBoard();
  } catch (error) {
    state.error = error.message || "Il tic non è riuscito.";
    state.busy = null;
    render();
  }
}

async function decide(actionId, decision) {
  state.busy = decision;
  state.error = null;
  render();
  try {
    await api("/agent/approve", {
      method: "POST",
      body: JSON.stringify({ action_id: actionId, decision }),
    });
    state.flashNotice = decision === "approve";
    await reloadBoard();
    window.setTimeout(() => {
      state.flashNotice = false;
    }, 1400);
  } catch (error) {
    state.error = error.message || "Decisione non registrata.";
    state.busy = null;
    render();
  }
}

async function reloadBoard() {
  const [actions, board] = await Promise.all([
    api(`/agent/actions?user_id=${encodeURIComponent(state.selectedId)}`),
    api(`/bacheca?user_id=${encodeURIComponent(state.selectedId)}`),
  ]);
  state.actions = actions.actions;
    state.notices = board.notices;
  state.busy = null;
  render();
  if (state.flashNotice) {
    document.querySelector("#cork .card.just-posted, #bacheca")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

async function resetDemo() {
  if (!state.resetArmed) {
    state.resetArmed = true;
    render();
    return;
  }
  state.busy = "reset";
  state.resetArmed = false;
  render();
  try {
    await api("/demo/reset", { method: "POST", body: "{}" });
    state.idleReason = null;
    await reloadBoard();
  } catch (error) {
    state.error = error.message || "Reset non riuscito.";
    state.busy = null;
    render();
  }
}

async function openSource(sourceId) {
  const dialog = document.getElementById("source-dialog");
  const body = document.getElementById("source-body");
  body.replaceChildren(el("p", { text: "Apro la fonte…" }));
  if (!dialog.open) dialog.showModal();
  try {
    renderSource(await api(`/sources/${encodeURIComponent(sourceId)}`));
  } catch (error) {
    body.replaceChildren(el("p", { text: error.message || "Fonte non trovata." }));
  }
}

function onClick(event) {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  const id = target.dataset.id;
  if (state.busy && !["source", "prefs", "section", "ai", "ai-close", "ask-suggest", "cal-mode", "cal-shift", "cal-today", "cal-day", "board-filter", "event-open", "event-ask"].includes(action)) return;
  if (action === "match") refreshStudent();
  else if (action === "section") showView(id);
  else if (action === "prefs") showScreen("prefs");
  else if (action === "cohort") document.getElementById("roster").hidden = !document.getElementById("roster").hidden;
  else if (action === "you") {
    const panel = document.getElementById("you-panel");
    panel.hidden = !panel.hidden;
    paintYou();
  } else if (action === "signout") signOut();
  else if (action === "tick") tickAgent();
  else if (action === "approve") decide(id, "approve");
  else if (action === "dismiss") decide(id, "dismiss");
  else if (action === "select") {
    state.selectedId = id;
    state.resetArmed = false;
    refreshStudent();
  } else if (action === "focus") {
    document.getElementById(`card-${id}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } else if (action === "source") openSource(id);
  else if (action === "reset") resetDemo();
  else if (action === "ai" || action === "ai-close") toggleAssistant(action === "ai");
  else if (action === "ask-suggest") {
    setAssistant(true);
    askAssistant(id);
  }
  else if (action === "propose") proposeRegistration(id);
  else if (action === "approve-reg") approveRegistration();
  else if (action === "reject-reg") rejectRegistration();
  else if (action === "feedback-chip") {
    const pressed = target.getAttribute("aria-pressed") === "true";
    target.setAttribute("aria-pressed", pressed ? "false" : "true");
  }
  else if (action === "cal-mode") {
    state.calendarMode = target.dataset.mode === "week" ? "week" : "month";
    renderCalendarView();
  }
  else if (action === "cal-shift") shiftCalendar(Number(id));
  else if (action === "cal-today") {
    state.calendarAnchor = demoDay();
    renderCalendarView();
  }
  else if (action === "cal-day") {
    state.calendarAnchor = id;
    renderCalendarView();
  }
  else if (action === "board-filter") {
    state.boardFilter = id || "";
    renderCommunity();
  }
  else if (action === "event-open") openEventModal(id);
  else if (action === "event-enroll") enrollFromModal();
  else if (action === "event-ask") askFromModal();
}

function render() {
  const error = document.getElementById("error");
  error.hidden = !state.error;
  error.textContent = state.error || "";
  document.getElementById("clock").textContent = state.health
    ? `Demo ${when(state.health.demo_now)}`
    : "Orologio demo";
  document.getElementById("mode").textContent = modeLabel();
  const matchBtn = document.getElementById("match-btn");
  const tickBtn = document.getElementById("tick-btn");
  matchBtn.disabled = Boolean(state.busy);
  tickBtn.disabled = Boolean(state.busy);
  matchBtn.textContent = state.busy === "match" ? "Abbino…" : "Abbina";
  tickBtn.textContent = state.busy === "tick" ? "Leggo…" : "Tic dell'agente";
  const person = selected();
  document.getElementById("map-title").textContent = person ? person.name : "Mappa";
  document.getElementById("board-title").textContent = person ? `Bacheca di ${person.name.split(" ")[0]}` : "Bacheca";
  paintDate();
  paintYou();
  renderRoster();
  renderPlan();
  renderTray();
  renderCork();
  renderDock();
  renderCommunity();
  renderScelto();
  renderClub();
  renderCalendarView();
  if (document.getElementById("event-modal")?.open) paintEventModal();
  renderBookings();
  renderShelf();
  renderContacts();
  renderLinks();
  renderFeedback();
  renderSettings();
  renderChat();
}

function renderRoster() {
  const roster = document.getElementById("roster");
  roster.replaceChildren();
  if (!state.users.length) {
    roster.append(el("p", { class: "loading", text: state.error ? "Nessuno studente caricato." : "Sto leggendo le fonti…" }));
    return;
  }
  const people = state.deskUser ? [state.deskUser, ...state.users] : state.users;
  for (const user of people) {
    const button = el("button", {
      class: `student${user.id === state.selectedId ? " selected" : ""}`,
      type: "button",
      "data-action": "select",
      "data-id": user.id,
    });
    const year = user.year != null ? `${user.year}° anno` : "";
    const meta = [user.program, year].filter(Boolean).join(" · ") || "studente";
    button.append(
      el("strong", { text: user.name }),
      el("div", { class: "meta", text: meta }),
    );
    for (const pref of user.preferences.slice(0, 4)) {
      const row = el("div", { class: "pref-row" });
      row.append(el("span", { text: pref.tag }));
      if (pref.weight != null) {
        const track = el("div", { class: "track" });
        const bar = document.createElement("i");
        bar.style.width = `${Math.round(pref.weight * 100)}%`;
        track.append(bar);
        row.append(track);
      }
      button.append(row);
    }
    roster.append(button);
  }
  const note = el("div", { class: "fine-print" });
  note.append(
    el("div", { text: "Persone, eventi e mail sono inventati. L'accesso è locale: la password non viene salvata. Canvas e Pronote non sono collegati. MIT, su GitHub. Ispirazione, non installata: GBrain, Cognee, PipesHub, Paperclip, LangGraph, OpenInstinct." }),
    el("button", {
      class: "ghost",
      type: "button",
      "data-action": "reset",
      text: state.resetArmed ? "Conferma azzeramento" : "Azzera approvazioni",
    }),
  );
  roster.append(note);
}

function placeLatLng(place) {
  const x = Number(place.x);
  const y = Number(place.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return CAMPUS_CENTER.slice();
  return [CAMPUS_CENTER[0] + (320 - y) * 0.0000042, CAMPUS_CENTER[1] + (x - 500) * 0.0000055];
}

function eventCategory(event) {
  const title = event.title || "";
  if (title.startsWith("Sessione introduttiva") || title.startsWith("Laboratorio pratico")) return "mandatory";
  if (title.startsWith("Meetup studenti") || title.startsWith("Community night") || title.startsWith("Sfida a squadre")) return "student";
  const tags = (event.tags || []).map((tag) => String(tag).toLowerCase());
  if (tags.some((tag) => SPORT_TAGS.has(tag))) return "sport";
  return "campus";
}

function ensureMap() {
  const node = document.getElementById("campus-map");
  if (!node) return false;
  if (typeof L === "undefined") {
    node.textContent = "La mappa Leaflet non è disponibile.";
    return false;
  }
  if (campusMap) return true;
  campusMap = L.map(node, { scrollWheelZoom: true }).setView(CAMPUS_CENTER, CAMPUS_ZOOM);
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 19,
    attribution: 'Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community',
  }).addTo(campusMap);
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 19,
    opacity: 0.8,
  }).addTo(campusMap);
  const caption = document.getElementById("map-caption");
  if (caption) caption.textContent = CAPTION;
  pinLayer = L.layerGroup().addTo(campusMap);
  return true;
}

function openPin(marker) {
  window.clearTimeout(pinCloseTimer);
  marker.openPopup();
}

function schedulePinClose(marker) {
  window.clearTimeout(pinCloseTimer);
  pinCloseTimer = window.setTimeout(() => marker.closePopup(), 450);
}

function placePopupNode(model, event, category, match, posted) {
  const wrap = document.createElement("div");
  wrap.className = "map-card";
  const kind = document.createElement("p");
  kind.className = "eyebrow";
  kind.textContent = `${PIN_KIND[category]} · ${model.place.name}`;
  const title = document.createElement("h3");
  title.textContent = event.title;
  const info = document.createElement("p");
  info.className = "blurb";
  info.textContent = event.blurb || "";
  const meta = document.createElement("p");
  meta.className = "meta";
  const bits = [];
  if (event.starts_at) bits.push(when(event.starts_at));
  if (event.building) bits.push(event.building);
  if (match) bits.push(`score ${match.score.toFixed(2)}`);
  if (posted) bits.push("APPESO");
  meta.textContent = bits.join(" · ");
  wrap.append(kind, title);
  if (event.blurb) wrap.append(info);
  wrap.append(meta);
  if (match) {
    const link = document.createElement("button");
    link.type = "button";
    link.className = "ghost map-jump";
    link.textContent = "Apri in bacheca";
    link.addEventListener("click", () => {
      document.getElementById(`card-${match.event_id}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
    wrap.append(link);
  }
  return wrap;
}

const PIN_OFFSET = {
  mandatory: [-0.00062, -0.0008],
  student: [-0.00062, 0.0008],
  sport: [0.00062, -0.0008],
  campus: [0.00062, 0.0008],
};

function renderPlan() {
  if (!ensureMap()) return;
  pinLayer.clearLayers();
  const posted = new Set(state.notices.map((notice) => notice.event_id));
  const markers = [];
  for (const model of pinModels()) {
    if (!model.events.length) continue;
    const groups = new Map();
    for (const event of model.events) {
      const category = eventCategory(event);
      const list = groups.get(category) || [];
      list.push(event);
      groups.set(category, list);
    }
    const spread = groups.size > 1;
    for (const [category, events] of groups) {
      const match = events
        .map((event) => state.matches.find((item) => item.event_id === event.id))
        .filter(Boolean)
        .sort((a, b) => state.matches.indexOf(a) - state.matches.indexOf(b))[0] || null;
      const event = (match && state.events.find((item) => item.id === match.event_id)) || events[0];
      const rank = match ? state.matches.findIndex((item) => item.event_id === match.event_id) + 1 : 0;
      const [lat, lng] = placeLatLng(model.place);
      const [dLat, dLng] = spread ? PIN_OFFSET[category] : [0, 0];
      const icon = L.divIcon({
        className: "pin-icon",
        html: `<button type="button" class="map-pin pin-${category}${rank === 1 ? " hero" : ""}${posted.has(event.id) ? " posted" : ""}">${PIN_ICONS[category]}</button>`,
        iconSize: [36, 42],
        iconAnchor: [18, 40],
        popupAnchor: [0, -36],
      });
      const marker = L.marker([lat + dLat, lng + dLng], { icon, keyboard: false, title: event.title });
      marker.bindPopup(placePopupNode(model, event, category, match, posted.has(event.id)), {
        closeButton: false,
        autoPan: true,
        className: "place-card",
      });
      marker.on("mouseover", () => openPin(marker));
      marker.on("mouseout", () => schedulePinClose(marker));
      marker.on("click", () => openPin(marker));
      marker.on("popupopen", () => {
        const popup = marker.getPopup().getElement();
        if (!popup || popup.dataset.bound) return;
        popup.dataset.bound = "1";
        popup.addEventListener("mouseenter", () => window.clearTimeout(pinCloseTimer));
        popup.addEventListener("mouseleave", () => schedulePinClose(marker));
      });
      marker.on("add", () => {
        const button = marker.getElement()?.querySelector("button");
        if (!button) return;
        const where = model.place.name || "Luogo";
        button.setAttribute("aria-label", `${PIN_KIND[category]}. ${where}. ${event.title}`);
        button.addEventListener("focus", () => openPin(marker));
        button.addEventListener("blur", () => schedulePinClose(marker));
      });
      marker.addTo(pinLayer);
      markers.push(marker);
    }
  }
  if (state.view === "map") window.requestAnimationFrame(frameCampus);
}

function frameCampus() {
  if (!campusMap) return;
  campusMap.invalidateSize();
  campusMap.setView(CAMPUS_CENTER, CAMPUS_ZOOM, { animate: false });
}

function renderTray() {
  const tray = document.getElementById("tray");
  tray.replaceChildren();
  const pending = state.actions.filter((action) => action.status === "pending");
  const dismissed = state.actions.filter((action) => action.status === "dismissed");
  if (!state.users.length) {
    tray.append(el("div", { class: "empty-tray", text: "La bacheca si apre quando le fonti sono caricate." }));
    return;
  }
  if (!pending.length) {
    tray.append(el("div", { class: "empty-tray", text: "Nessun avviso in attesa. L'agente può prepararne uno, ma non lo appende." }));
  }
  for (const action of pending) {
    const event = state.events.find((item) => item.id === action.event_id);
    const card = el("article", { class: "tray-card" });
    card.append(
      el("p", { class: "kicker", text: `In attesa · ${action.trace.event.signal}` }),
      el("h3", { text: event ? event.title : action.event_id }),
      el("p", { class: "blurb", text: action.trace.reasoning.draft || action.trace.action.summary }),
    );
    const row = el("div", { class: "row-actions" });
    row.append(
      el("button", { class: "leaf", type: "button", "data-action": "approve", "data-id": action.id, text: state.busy === "approve" ? "Appendo…" : "Approva" }),
      el("button", { class: "ghost", type: "button", "data-action": "dismiss", "data-id": action.id, text: "Scarta" }),
    );
    card.append(row);
    tray.append(card);
  }
  if (dismissed.length) {
    const row = el("div", { class: "dismissed" });
    row.append(el("span", { text: "Scartati" }));
    for (const action of dismissed) {
      const event = state.events.find((item) => item.id === action.event_id);
      row.append(el("span", { class: "chip", text: event ? event.title : action.event_id }));
    }
    tray.append(row);
  }
}

function renderCork() {
  const cork = document.getElementById("cork");
  cork.replaceChildren();
  if (!state.users.length) return;
  const posted = new Set(state.notices.map((notice) => notice.event_id));
  if (state.notices.length) {
    for (const notice of state.notices) {
      cork.append(noticeCard(notice));
    }
  }
  if (!state.matches.length) {
    const empty = el("article", { class: "card" });
    if (state.busy === "match") {
      empty.append(el("h3", { text: "Abbino…" }), el("p", { text: "Sto leggendo le fonti di questa persona." }));
    } else if (state.error) {
      empty.append(el("h3", { text: "Bacheca non aggiornata" }), el("p", { text: "Le carte di prima sono state tolte, così non restano sotto il nome sbagliato. Premi Abbina." }));
    } else {
      empty.append(el("h3", { text: "Nessuna carta" }), el("p", { text: "Nessun evento condivide un tag con questa persona." }));
    }
    cork.append(empty);
    return;
  }
  state.matches.forEach((match, index) => {
    cork.append(matchCard(match, index + 1, posted.has(match.event_id)));
  });
  if (state.method) {
    const details = el("details", { class: "formula" });
    details.append(el("summary", { text: "Come è calcolato" }));
    details.append(el("code", { text: state.method.formula }));
    cork.append(details);
  }
}

function renderDock() {
  const dock = document.getElementById("dock");
  dock.replaceChildren();
  if (state.idleReason) dock.append(el("p", { class: "dock-note", text: state.idleReason }));
  const latest = state.actions[0];
  const steps = latest
    ? [
        ["01 EVENT", latest.trace.event.summary],
        ["02 CONTEXT", latest.trace.context.summary],
        ["03 REASONING", latest.trace.reasoning.summary],
        ["04 ACTION", latest.trace.action.summary],
      ]
    : [
        ["01 EVENT", "Nessun segnale letto."],
        ["02 CONTEXT", "Il contesto si apre dopo il tic."],
        ["03 REASONING", "Il ragionamento resta vuoto finché non c'è un segnale."],
        ["04 ACTION", "Nessuna azione. L'agente non pubblica da solo."],
      ];
  const grid = el("div", { class: "steps" });
  steps.forEach(([title, summary], index) => {
    const cell = el("section", { class: "step" });
    cell.append(el("h3", { text: title }), el("p", { text: summary }));
    if (index === 3 && latest && latest.status === "pending") {
      const row = el("div", { class: "row-actions" });
      row.append(
        el("button", { class: "leaf", type: "button", "data-action": "approve", "data-id": latest.id, text: "Approva" }),
        el("button", { class: "ghost", type: "button", "data-action": "dismiss", "data-id": latest.id, text: "Scarta" }),
      );
      cell.append(row);
    }
    grid.append(cell);
  });
  dock.append(grid);
}

function matchCard(match, rank, posted) {
  const card = el("article", {
    class: `card${posted ? " notice" : ""}${posted && state.flashNotice ? " just-posted" : ""}`,
    id: `card-${match.event_id}`,
  });
  card.style.setProperty("--tilt", `${tilt(match.event_id)}deg`);
  if (posted) card.append(el("span", { class: "stamp posted", text: "APPESO" }));
  card.append(
    el("h3", { text: match.title }),
    el("p", { class: "meta", text: cardMeta(match) }),
    el("p", { class: "why-kicker", text: "Perché ti consiglio questo" }),
    el("p", { class: "blurb", text: match.why || match.display_text }),
  );
  const score = el("div", { class: "scoreline" });
  score.append(
    el("span", { class: "score", text: match.score.toFixed(2) }),
    el("span", { class: "meta", text: voiceLabel(match.display_by) }),
  );
  card.append(score);
  if (match.company.length) {
    const row = el("div", { class: "company-row" });
    for (const person of match.company) {
      row.append(el("button", {
        class: "company",
        type: "button",
        "data-action": "select",
        "data-id": person.user_id,
        text: `${person.name} · ${person.score.toFixed(2)}`,
        title: person.sentence,
      }));
    }
    card.append(row);
  }
  card.append(chipRow(match.citations));
  card.dataset.rank = String(rank);
  return card;
}

function cardMeta(match) {
  const bits = [when(match.starts_at), match.location_name];
  if (match.building) bits.push(match.building);
  if (match.host_role) bits.push(match.host_role);
  if (match.going != null && match.capacity != null) bits.push(`${match.going} su ${match.capacity}`);
  else if (match.capacity != null) bits.push(`capienza ${match.capacity}`);
  return bits.filter(Boolean).join(" · ");
}

function noticeCard(notice) {
  const card = el("article", { class: `card notice${state.flashNotice ? " just-posted" : ""}`, id: `notice-${notice.id}` });
  card.style.setProperty("--tilt", `${tilt(notice.id)}deg`);
  card.append(
    el("span", { class: "stamp posted", text: "APPESO" }),
    el("h3", { text: notice.event_title }),
    el("p", { class: "meta", text: `${when(notice.starts_at)} · ${notice.location_name} · bacheca · nessuna email` }),
    el("p", { class: "blurb", text: notice.text }),
    chipRow(notice.citations || []),
  );
  return card;
}

function chipRow(citations) {
  const row = el("div", { class: "chips" });
  const seen = new Set();
  for (const citation of citations) {
    if (seen.has(citation.source_id)) continue;
    seen.add(citation.source_id);
    const button = el("button", {
      class: `chip${citation.kind === "email" ? " email" : ""}`,
      type: "button",
      "data-action": "source",
      "data-id": citation.source_id,
      title: citation.quote || citation.source_id,
    });
    button.append(el("span", { class: "kind", text: KIND[citation.kind] || citation.kind }));
    button.append(document.createTextNode(citation.source_id));
    row.append(button);
  }
  return row;
}

function renderSource(source) {
  const body = document.getElementById("source-body");
  body.replaceChildren(
    el("p", { class: "eyebrow", text: "Fonte sintetica · non è un dato reale del campus" }),
    el("h3", { id: "source-title", text: source.source_id }),
    el("p", { class: "meta", text: `${KIND[source.kind] || source.kind} · ${accessLabel(source.access)}` }),
    el("blockquote", { text: source.quote }),
  );
  const record = source.record || {};
  if (source.kind === "email") {
    body.append(
      el("p", { text: `Da ${record.from}` }),
      el("p", { text: `A ${record.to}` }),
      el("p", { text: record.body }),
      el("p", { class: "meta", text: "Mock. Questo testo non è stato inviato." }),
    );
  } else if (source.kind === "preference") {
    const weight = record.weight == null ? "senza peso nel dataset" : `peso ${Number(record.weight).toFixed(2)}`;
    body.append(el("p", { text: `${record.user_name} · ${record.tag} · ${weight}` }));
    if (record.note) body.append(el("p", { text: record.note }));
  } else if (source.kind === "event") {
    body.append(el("p", { text: record.blurb || "" }), el("p", { text: `Tag: ${(record.tags || []).join(", ")}` }));
    if (record.building) {
      body.append(el("p", { text: `Edificio nel dataset: ${record.building}. Il pin è lo schema del campus, non una coordinata del file.` }));
    }
    if (record.host) body.append(el("p", { text: `Pubblica ${record.host} · ruolo ${record.host_role}` }));
  } else if (source.kind === "user") {
    const bits = [];
    if (record.program) bits.push(record.program);
    if (record.year != null) bits.push(`anno ${record.year}`);
    if (bits.length) body.append(el("p", { text: bits.join(", ") }));
    body.append(el("p", { text: record.interests_text || record.bio || "" }));
  } else if (source.kind === "place") {
    body.append(el("p", { text: `${record.name}, zona ${record.zone}. Punto nello schema, non una coordinata catastale.` }));
  }
}

function pinModels() {
  const ranked = new Map(state.matches.map((match, index) => [match.event_id, { ...match, rank: index + 1 }]));
  const posted = new Set(state.notices.map((notice) => notice.event_id));
  const pending = new Set(state.actions.filter((action) => action.status === "pending").map((action) => action.event_id));
  const byPlace = new Map();
  for (const event of state.events) {
    const list = byPlace.get(event.location.id) || [];
    list.push(event);
    byPlace.set(event.location.id, list);
  }
  const models = [];
  for (const [placeId, events] of byPlace) {
    const place = state.places.find((item) => item.id === placeId) || {
      id: placeId,
      name: events[0].location.name,
      x: events[0].location.x,
      y: events[0].location.y,
    };
    const best = events.map((event) => ranked.get(event.id)).filter(Boolean).sort((a, b) => a.rank - b.rank)[0] || null;
    models.push({
      place,
      events,
      best,
      posted: events.some((event) => posted.has(event.id)),
      pending: events.some((event) => pending.has(event.id)),
    });
  }
  return models;
}

function accessLabel(access) {
  const scope = typeof access === "string" ? access : access && access.scope;
  if (scope === "personal") return "accesso personale";
  if (scope === "public") return "accesso pubblico";
  return "fonte sintetica";
}

function modeLabel() {
  if (state.displayBy === "gemma") return "Gemma";
  if (state.displayBy === "fallback_after_gemma" || state.displayBy === "mixed") return "Fonti al posto di Gemma";
  if (state.health?.narration_mode === "gemma") return "Gemma pronta";
  return "Deterministico";
}

function voiceLabel(mode) {
  if (mode === "gemma") return "Gemma ha scritto il perché. Gli id sono stati ricontrollati.";
  if (mode === "fallback_after_gemma") return "Senza Gemma: frase dai tag e dal punteggio.";
  return "Senza chiave: frase dai tag e dal punteggio.";
}

function knownPerson(id) {
  if (state.deskUser && id === state.deskUser.id) return true;
  return state.users.some((user) => user.id === id);
}

function selected() {
  if (state.deskUser && state.selectedId === state.deskUser.id) return state.deskUser;
  return state.users.find((user) => user.id === state.selectedId) || null;
}

function when(iso) {
  if (!iso) return "";
  return new Intl.DateTimeFormat("it-IT", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Rome",
  }).format(new Date(iso));
}

function tilt(id) {
  let hash = 0;
  for (const char of id) hash = (hash + char.charCodeAt(0) * 13) % 5;
  return (hash - 2) * 0.4;
}

function friendlyError(error) {
  const message = error && error.message ? error.message : "";
  if (!message || message === "Failed to fetch" || message === "NetworkError when attempting to fetch resource.") {
    return "H-OS non risponde. Controlla che il server sia acceso, poi premi Abbina.";
  }
  return message;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    headers: { accept: "application/json", "content-type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch (_error) {
      /* keep the status text */
    }
    throw new Error(detail);
  }
  return response.json();
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) if (child) node.append(child);
  return node;
}

function showScreen(name) {
  state.screen = name;
  document.getElementById("screen-access").hidden = name !== "access";
  document.getElementById("screen-prefs").hidden = name !== "prefs";
  document.getElementById("screen-desk").hidden = name !== "desk";
  if (name === "prefs") renderSwipe();
}

function nameFromEmail(email) {
  const local = String(email || "").split("@")[0] || "";
  const words = local.split(/[._-]+/).map((part) => {
    const cleaned = part.replace(/[^0-9A-Za-zÀ-ÿ]/g, "");
    if (!cleaned) return "";
    return cleaned.charAt(0).toUpperCase() + cleaned.slice(1).toLowerCase();
  }).filter(Boolean);
  if (!words.length) return { nome: "Studente", cognome: "" };
  return { nome: words[0], cognome: words.slice(1).join(" ") };
}

function displayName(session) {
  if (!session) return "";
  return [session.nome, session.cognome].filter(Boolean).join(" ");
}

function loadSession() {
  try {
    const raw = JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
    if (!raw || typeof raw.email !== "string") return null;
    if ("password" in raw) delete raw.password;
    if (typeof raw.nome !== "string" || !raw.nome.trim()) {
      const derived = nameFromEmail(raw.email);
      raw.nome = derived.nome;
      raw.cognome = typeof raw.cognome === "string" && raw.cognome.trim() ? raw.cognome : derived.cognome;
    } else if (typeof raw.cognome !== "string") {
      raw.cognome = "";
    }
    raw.likes = Array.isArray(raw.likes) ? raw.likes : [];
    raw.dislikes = Array.isArray(raw.dislikes) ? raw.dislikes : [];
    raw.skipped = Array.isArray(raw.skipped) ? raw.skipped : [];
    raw.prefsConfirmed = Boolean(raw.prefsConfirmed);
    raw.canvas_id = raw.canvas_link || raw.canvas_id || "";
    raw.pronote_id = raw.pronote_link || raw.pronote_id || "";
    return raw;
  } catch {
    return null;
  }
}

function saveSession(session) {
  const stored = { ...session };
  delete stored.password;
  localStorage.setItem(SESSION_KEY, JSON.stringify(stored));
  state.session = stored;
}

function profileBody() {
  const session = state.session;
  return {
    nome: session.nome,
    cognome: session.cognome,
    email: session.email,
    canvas_id: session.canvas_id || "",
    pronote_id: session.pronote_id || "",
    nickname: session.nome,
    likes: session.likes,
    dislikes: session.dislikes || [],
  };
}

function deskUserFromSession() {
  const session = state.session;
  return {
    id: "usr-desk",
    name: displayName(session),
    role: "student",
    program: "tu, accesso locale",
    preferences: session.likes.map((tag) => ({ tag, weight: null, id: `pref-desk-${tag.toLowerCase()}` })),
  };
}

function passwordOk(value) {
  return value.length >= 8
    && /[a-z]/.test(value)
    && /[A-Z]/.test(value)
    && /\d/.test(value)
    && /[^A-Za-z0-9]/.test(value);
}

function submitAccess(event) {
  event.preventDefault();
  const nickname = document.getElementById("nickname").value.trim();
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;
  const errors = {};
  if (nickname.length < 2) errors.nickname = "Scrivi un nickname di almeno 2 caratteri.";
  if (!/^[^@\s]+@[^@\s]+$/.test(email)) errors.email = "L'email deve contenere @. Il dominio può essere finto.";
  if (!passwordOk(password)) errors.password = "Servono 8 caratteri, maiuscola, minuscola, numero e simbolo.";
  if (!document.getElementById("terms").checked) errors.terms = "Accetta i termini per entrare.";
  for (const node of document.querySelectorAll(".field-error")) node.textContent = errors[node.dataset.for] || "";
  if (Object.keys(errors).length) return;
  document.getElementById("password").value = "";
  const previous = state.session;
  saveSession({
    nome: nickname,
    cognome: "",
    email,
    canvas_id: document.getElementById("canvas-link").value.trim(),
    pronote_id: document.getElementById("pronote-link").value.trim(),
    likes: previous?.likes || [],
    dislikes: previous?.dislikes || [],
    skipped: previous?.skipped || [],
    prefsConfirmed: false,
  });
  showScreen("prefs");
}

function pendingTags() {
  const session = state.session || { likes: [], dislikes: [], skipped: [] };
  const skipped = session.skipped || [];
  return state.tags.filter((tag) => !session.likes.includes(tag) && !session.dislikes.includes(tag) && !skipped.includes(tag));
}

function setTagChoice(tag, value) {
  const session = state.session;
  session.likes = session.likes.filter((item) => item !== tag);
  session.dislikes = (session.dislikes || []).filter((item) => item !== tag);
  session.skipped = (session.skipped || []).filter((item) => item !== tag);
  if (value === "yes" || value === "like") session.likes.push(tag);
  else if (value === "no" || value === "dislike") session.dislikes.push(tag);
  else session.skipped.push(tag);
  saveSession(session);
}

const TAG_NOTES = {
  AI: ["codice", "Laboratori e serate in cui si costruisce con i modelli."],
  "data-science": ["codice", "Dati, grafici e il lavoro che sta dietro un numero."],
  programmazione: ["codice", "Ore in cui si scrive, si rompe e si rimette insieme."],
  robotica: ["codice", "Bracci, sensori e prove in laboratorio."],
  cybersecurity: ["codice", "Come si difende un sistema, senza spettacolo."],
  design: ["codice", "Forma, poster e oggetti che qualcuno userà."],
  "UX-UI": ["codice", "Schermate, percorsi e il punto in cui ci si perde."],
  gaming: ["codice", "Partite, jam e il tavolo che non si libera."],
  arte: ["cultura", "Mostre, aule e il lavoro appeso al muro."],
  fotografia: ["cultura", "Uscite, rullini e il ritaglio di un pomeriggio."],
  cinema: ["cultura", "Proiezioni, H-Farmers e la fila per una sedia."],
  musica: ["cultura", "Prove, palchi piccoli e il volume giusto."],
  teatro: ["cultura", "Letture, scene e chi entra in ritardo."],
  sport: ["corpo", "Campi, orari e la voglia di muoversi."],
  fitness: ["corpo", "Sale e allenamenti aperti a chi passa."],
  calcio: ["corpo", "Partite e il campo quando è libero."],
  basket: ["corpo", "Canestri, tornei e un'ora in palestra."],
  running: ["corpo", "Uscite lungo il campus, a passo di gruppo."],
  startup: ["impresa", "Pitch, prototipi e chi cerca un socio."],
  imprenditoria: ["impresa", "Idee da provare prima che restino idee."],
  marketing: ["impresa", "Come si racconta un progetto a chi non c'era."],
  finanza: ["impresa", "Numeri di un progetto, non di un conto vero."],
  networking: ["impresa", "Tavoli in cui ci si presenta e si resta."],
  sostenibilita: ["terra", "Scelte di campus che consumano meno."],
  ambiente: ["terra", "Pulizie del fiume, orti e uscite all'aperto."],
};

const TAG_MARKS = {
  codice: '<svg viewBox="0 0 32 32"><path d="M12 8 L6 16 L12 24 M20 8 L26 16 L20 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  cultura: '<svg viewBox="0 0 32 32"><circle cx="16" cy="16" r="7" fill="none" stroke="currentColor" stroke-width="2"/><path d="M16 5 V9 M16 23 V27 M5 16 H9 M23 16 H27" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  corpo: '<svg viewBox="0 0 32 32"><circle cx="16" cy="8" r="3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10 28 L16 16 L22 28 M8 18 H24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  impresa: '<svg viewBox="0 0 32 32"><rect x="7" y="14" width="18" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 14 V10 H20 V14 M16 18 V22" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
  terra: '<svg viewBox="0 0 32 32"><path d="M16 26 C16 18 10 16 10 10 C14 12 16 8 16 6 C16 8 18 12 22 10 C22 16 16 18 16 26 Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
};

function renderSwipe() {
  const pending = pendingTags();
  const tag = pending[0] || "";
  const card = document.getElementById("swipe-card");
  card.dataset.tag = tag;
  card.classList.remove("toward-like", "toward-dislike", "is-dragging");
  card.style.transform = "";
  const note = TAG_NOTES[tag];
  const kind = note ? note[0] : "preferenza";
  document.getElementById("swipe-tag").textContent = tag || "Carte finite";
  document.getElementById("swipe-kind").textContent = tag ? kind : "fine";
  document.getElementById("swipe-blurb").textContent = tag
    ? (note ? note[1] : "Tag del dataset sintetico.")
    : "Carte finite. Apri la community se hai almeno un Interessa.";
  document.getElementById("swipe-mark").innerHTML = TAG_MARKS[kind] || TAG_MARKS.codice;
  const likes = state.session?.likes.length || 0;
  const dislikes = state.session?.dislikes.length || 0;
  const total = state.tags.length;
  const at = tag ? Math.min(likes + dislikes + 1, total) : total;
  document.getElementById("swipe-progress").textContent = total ? `${at} di ${total}` : "";
  const meter = document.getElementById("swipe-meter");
  if (meter) meter.style.width = total ? `${Math.round((at / total) * 100)}%` : "0";
  const skipped = state.session?.skipped?.length || 0;
  document.getElementById("swipe-counts").textContent = `${likes} mi piace · ${dislikes} scartati · ${skipped} saltati`;
  document.getElementById("enter-map").disabled = likes === 0;
  document.getElementById("like-btn").disabled = !tag;
  document.getElementById("dislike-btn").disabled = !tag;
  document.getElementById("skip-btn").disabled = !tag;
  renderPrefGrid();
  renderPrefPreview();
}

function toggleStub(open) {
  const panel = document.getElementById("agent-stub");
  const button = document.getElementById("agent-bubble");
  if (!panel || !button) return;
  const show = open ? panel.hidden : false;
  panel.hidden = !show;
  button.setAttribute("aria-expanded", show ? "true" : "false");
}

let swipeBusy = false;

function decideCurrent(choice) {
  const card = document.getElementById("swipe-card");
  const tag = card.dataset.tag;
  const mode = choice === true || choice === "like" ? "like" : choice === "skip" ? "skip" : "dislike";
  if (!tag || !state.session || swipeBusy) return;
  const commit = () => {
    setTagChoice(tag, mode);
    swipeBusy = false;
    const finished = pendingTags().length === 0 && state.session.likes.length > 0;
    renderSwipe();
    if (finished) enterDesk();
  };
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce || mode === "skip") {
    commit();
    return;
  }
  swipeBusy = true;
  card.classList.remove("is-dragging");
  card.style.transform = mode === "like" ? "translateY(88px)" : "translateY(-88px)";
  window.setTimeout(commit, 170);
}

function useDemoLikes() {
  if (!state.session) return;
  state.session.likes = DEMO_LIKES.filter((tag) => state.tags.includes(tag));
  state.session.dislikes = (state.session.dislikes || []).filter((tag) => !state.session.likes.includes(tag));
  state.session.skipped = (state.session.skipped || []).filter((tag) => !state.session.likes.includes(tag));
  state.session.prefsConfirmed = true;
  saveSession(state.session);
  enterDesk();
}

async function enterDesk() {
  if (!state.session || !state.session.likes.length) return;
  state.session.prefsConfirmed = true;
  saveSession(state.session);
  state.deskUser = deskUserFromSession();
  state.selectedId = "usr-desk";
  showScreen("desk");
  showView("community");
  try {
    await api("/desk/profile", { method: "POST", body: JSON.stringify(profileBody()) });
    await refreshStudent();
  } catch (error) {
    state.error = error.message || "Profilo non registrato.";
    render();
  }
}

function signOut() {
  localStorage.removeItem(SESSION_KEY);
  state.session = null;
  state.deskUser = null;
  state.selectedId = null;
  document.getElementById("you-panel").hidden = true;
  document.getElementById("roster").hidden = true;
  history.replaceState(null, "", location.pathname);
  showScreen("access");
}

function showView(id) {
  const alias = { bacheca: "community", community: "community", mappa: "map", map: "map", calendario: "calendar", calendar: "calendar", agenda: "calendar", prenotazioni: "bookings", bookings: "bookings", feedback: "feedback", voci: "feedback", contatti: "contacts", contacts: "contacts", canvas: "canvas", pronote: "pronote", shelf: "shelf", personalizzazioni: "settings", settings: "settings", club: "club" };
  const view = alias[id] || "community";
  state.view = view;
  for (const section of document.querySelectorAll(".stage .view")) {
    section.hidden = section.dataset.view !== view;
  }
  for (const button of document.querySelectorAll(".help-nav button, .rail button[data-action='section']")) {
    const target = alias[button.dataset.id] || button.dataset.id;
    if (target === view) button.setAttribute("aria-current", "true");
    else button.removeAttribute("aria-current");
  }
  const dateBtn = document.getElementById("demo-date");
  if (dateBtn) dateBtn.setAttribute("aria-pressed", view === "calendar" ? "true" : "false");
  const gear = document.querySelector(".head-gear");
  if (gear) gear.setAttribute("aria-pressed", view === "settings" ? "true" : "false");
  if (view === "map") window.setTimeout(frameCampus, 80);
}

function focusSection(id) {
  showView(id);
}

function paintDate() {
  const stack = document.getElementById("demo-date");
  if (!stack || !state.health?.demo_now) return;
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Rome",
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
  }).formatToParts(new Date(state.health.demo_now));
  const pick = (type) => parts.find((part) => part.type === type)?.value || "—";
  document.getElementById("date-d").textContent = pick("day");
  document.getElementById("date-m").textContent = pick("month");
  document.getElementById("date-y").textContent = pick("year");
}

function paintYou() {
  const button = document.getElementById("you-btn");
  if (!button) return;
  const session = state.session;
  const name = displayName(session);
  button.setAttribute("aria-label", name || "Il tuo accesso");
  document.getElementById("you-name").textContent = name;
  document.getElementById("you-email").textContent = session ? session.email : "";
  const links = document.getElementById("you-links");
  if (links) {
    const bits = [];
    if (session?.canvas_id) bits.push(`Canvas ${session.canvas_id}`);
    if (session?.pronote_id) bits.push(`Pronote ${session.pronote_id}`);
    links.textContent = bits.join(" · ");
  }
}

function wireSwipe() {
  const card = document.getElementById("swipe-card");
  const stage = document.getElementById("swipe-stage");
  let drag = null;
  let wheelAt = 0;
  card.addEventListener("pointerdown", (event) => {
    if (swipeBusy) return;
    drag = { id: event.pointerId, y: event.clientY, dy: 0 };
    card.classList.add("is-dragging");
    card.setPointerCapture(event.pointerId);
  });
  card.addEventListener("pointermove", (event) => {
    if (!drag || drag.id !== event.pointerId) return;
    drag.dy = event.clientY - drag.y;
    card.style.transform = `translateY(${drag.dy}px)`;
    card.classList.toggle("toward-like", drag.dy > 24);
    card.classList.toggle("toward-dislike", drag.dy < -24);
  });
  const release = (event) => {
    if (!drag || (event && drag.id !== event.pointerId)) return;
    const dy = drag.dy;
    drag = null;
    if (dy >= 72) decideCurrent(true);
    else if (dy <= -72) decideCurrent(false);
    else {
      card.classList.remove("is-dragging", "toward-like", "toward-dislike");
      card.style.transform = "";
    }
  };
  card.addEventListener("pointerup", release);
  card.addEventListener("pointercancel", release);
  card.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      decideCurrent(true);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      decideCurrent(false);
    }
  });
  stage.addEventListener("wheel", (event) => {
    if (state.screen !== "prefs") return;
    event.preventDefault();
    const now = Date.now();
    if (now - wheelAt < 450) return;
    if (event.deltaY > 30) {
      wheelAt = now;
      decideCurrent(true);
    } else if (event.deltaY < -30) {
      wheelAt = now;
      decideCurrent(false);
    }
  }, { passive: false });
}

function renderPrefGrid() {
  const grid = document.getElementById("pref-grid");
  if (!grid || !state.session) return;
  grid.replaceChildren();
  for (const tag of state.tags) {
    const choice = state.session.likes.includes(tag) ? "yes" : state.session.dislikes.includes(tag) ? "no" : state.session.skipped?.includes(tag) ? "skip" : "";
    const row = el("div", { class: "pref-row-edit" });
    row.append(el("strong", { text: tag }));
    const actions = el("div", {});
    for (const [value, label, extra] of [["yes", "Interessa", ""], ["no", "Non interessa", "no"], ["skip", "Salta", ""]]) {
      actions.append(el("button", {
        type: "button",
        class: extra,
        "data-tag": tag,
        "data-value": value,
        "aria-pressed": choice === value ? "true" : "false",
        text: label,
      }));
    }
    row.append(actions);
    grid.append(row);
  }
}

function renderPrefPreview() {
  const node = document.getElementById("pref-preview");
  if (!node || !state.session) return;
  const likes = new Set(state.session.likes);
  const ranked = state.events
    .map((event) => ({ event, shared: (event.tags || []).filter((tag) => likes.has(tag)).length }))
    .filter((row) => row.shared > 0)
    .sort((a, b) => b.shared - a.shared || a.event.id.localeCompare(b.event.id))
    .slice(0, 3);
  node.replaceChildren(el("p", { class: "meta", text: ranked.length ? "Anteprima dal dataset, prima di entrare." : "Segna almeno un Interessa per vedere i consigli." }));
  for (const row of ranked) {
    node.append(el("p", { text: `${row.event.title} · ${row.event.id} · tag in comune ${row.shared}` }));
  }
}

function renderScelto() {
  const node = document.getElementById("scelto-list");
  if (!node) return;
  node.replaceChildren();
  if (!state.recommendations.length) {
    node.append(el("p", { class: "meta", text: "I consigli compaiono dopo l'accesso, dalle tue preferenze." }));
    return;
  }
  for (const row of state.recommendations) {
    const card = el("button", {
      type: "button",
      class: "scelto-card",
      "data-action": "event-open",
      "data-id": row.event_id,
    });
    card.append(
      el("strong", { text: row.title }),
      el("span", { text: row.reason || row.source_id || "" }),
    );
    node.append(card);
  }
}

function renderClub() {
  const node = document.getElementById("club-feed");
  if (!node) return;
  node.replaceChildren();
  const posts = state.posts.filter((post) => post.board_id === "board-club" || /club/i.test(post.thread_title || ""));
  if (!posts.length) {
    node.append(el("p", { class: "meta", text: "Nessun post Club caricato. La mappa satellite resta sul pulsante qui sotto." }));
    return;
  }
  for (const post of posts.slice(0, 8)) {
    node.append(el("article", { class: "mini-card" }, [
      el("p", { class: "board-pill", text: post.thread_title || "Club" }),
      el("h3", { text: post.title || "Club" }),
      el("p", { text: post.body || "" }),
    ]));
  }
}

function findListedEvent(eventId) {
  return state.events.find((item) => item.id === eventId)
    || state.recommendations.find((item) => item.event_id === eventId)
    || null;
}

function openEventModal(eventId) {
  state.eventModalId = eventId;
  paintEventModal();
  const dialog = document.getElementById("event-modal");
  if (dialog && !dialog.open) dialog.showModal();
}

function paintEventModal() {
  const title = document.getElementById("event-modal-title");
  if (!title) return;
  const record = findListedEvent(state.eventModalId);
  title.textContent = record?.title || state.eventModalId || "Evento";
  const body = document.getElementById("event-modal-body");
  if (body) body.textContent = record?.description || record?.blurb || record?.reason || "";
  const sources = document.getElementById("event-sources");
  if (sources) {
    sources.replaceChildren();
    const ids = [...new Set([record?.source_id, record?.id, state.eventModalId].filter(Boolean))];
    for (const sourceId of ids) {
      sources.append(el("button", {
        type: "button",
        class: "ghost",
        "data-action": "source",
        "data-id": sourceId,
        text: sourceId,
      }));
    }
  }
  const pending = Boolean(state.proposal && state.proposal.event_id === state.eventModalId);
  const enroll = document.getElementById("event-enroll");
  const approve = document.getElementById("event-approve");
  const reject = document.getElementById("event-reject");
  if (enroll) enroll.hidden = pending;
  if (approve) approve.hidden = !pending;
  if (reject) reject.hidden = !pending;
}

async function enrollFromModal() {
  if (!state.eventModalId) return;
  await proposeRegistration(state.eventModalId);
  paintEventModal();
}

function askFromModal() {
  const record = findListedEvent(state.eventModalId);
  setAssistant(true);
  askAssistant(record?.title || "Recommend an event");
}

function renderCommunity() {
  const feed = document.getElementById("feed");
  const perTe = document.getElementById("per-te");
  if (perTe) {
    perTe.replaceChildren();
    if (state.proposal) {
      const box = el("div", { class: "ig-proposal" });
      box.append(
        el("p", { text: `Proposta ${state.proposal.approval_id} per ${state.proposal.event_title}. L'agenda è ancora vuota.` }),
        el("button", { class: "solid", type: "button", "data-action": "approve-reg", text: "Approva iscrizione simulata" }),
        el("button", { class: "ghost", type: "button", "data-action": "reject-reg", text: "Rifiuta" }),
      );
      perTe.append(box);
    }
  }
  if (!feed) return;
  feed.replaceChildren();
  const column = el("div", { class: "ig-column" });
  const stories = el("div", { class: "ig-stories", "aria-label": "Per te" });
  if (!state.recommendations.length) {
    stories.append(el("p", { class: "meta", text: "Nessun consiglio ancora." }));
  }
  for (const row of state.recommendations.slice(0, 8)) {
    const story = el("button", {
      type: "button",
      class: "ig-story",
      "data-action": "ask-suggest",
      "data-id": row.title,
      "aria-label": `Chiedi di ${row.title}`,
    });
    story.append(
      el("span", { class: "ig-avatar", text: (row.title || "?").slice(0, 1).toUpperCase() }),
      el("span", { class: "ig-story-name", text: row.title }),
    );
    stories.append(story);
  }
  const labels = el("div", { class: "board-labels", "aria-label": "Etichette della bacheca community" });
  labels.append(el("button", {
    type: "button",
    class: "board-label",
    "data-action": "board-filter",
    "data-id": "",
    "aria-pressed": state.boardFilter ? "false" : "true",
    text: "Tutte",
  }));
  for (const board of state.boards) {
    labels.append(el("button", {
      type: "button",
      class: "board-label",
      "data-action": "board-filter",
      "data-id": board.id,
      "aria-pressed": state.boardFilter === board.id ? "true" : "false",
      text: board.title,
    }));
  }
  column.append(el("p", { class: "ig-kicker", text: `Community · ${state.boards.length} bacheche` }), labels, stories);
  const visiblePosts = state.posts.filter((post) => !state.boardFilter || post.board_id === state.boardFilter || post.thread_id === state.boardFilter);
  for (const post of visiblePosts.slice(0, 18)) {
    const name = post.author_name || "Campus";
    const card = el("article", { class: "ig-post" });
    const who = el("div", { class: "ig-who" });
    who.append(
      el("strong", { text: name }),
      el("p", { class: "ig-meta", text: post.thread_title || "Community" }),
    );
    const head = el("header", { class: "ig-post-head" });
    head.append(
      el("span", { class: "ig-avatar", text: name.trim().slice(0, 1).toUpperCase() }),
      who,
    );
    if (post.score) head.append(el("span", { class: "ig-score", text: `${post.score}%` }));
    head.append(el("span", { class: "board-pill", text: post.thread_title || "Community" }));
    const tone = ["a", "b", "c", "d"][(post.source_id || "").length % 4];
    const visual = el("div", { class: `ig-visual tone-${tone}` });
    visual.append(el("p", { text: post.title || "" }));
    const caption = el("p", {});
    caption.append(el("strong", { text: name.split("—")[0].trim() }));
    caption.append(document.createTextNode(` ${post.body || ""}`));
    card.append(
      head,
      visual,
      el("div", { class: "ig-caption" }, [
        caption,
        el("p", { class: "ig-meta", text: `Fonte ${post.source_id}${post.shared_tags?.length ? ` · ${post.shared_tags.join(", ")}` : ""}` }),
      ]),
    );
    column.append(card);
  }
  feed.append(column);
}

const CAL_MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"];
const CAL_WEEKDAYS = ["L", "M", "M", "G", "V", "S", "D"];

function campusDay(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
  return match ? `${match[1]}-${match[2]}-${match[3]}` : "";
}

function campusClock(value) {
  const match = String(value || "").match(/T(\d{2}:\d{2})/);
  return match ? match[1] : "";
}

function parseDay(key) {
  const [y, m, d] = key.split("-").map(Number);
  return { y, m, d };
}

function dayKey(y, m, d) {
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

function addDays(key, count) {
  const { y, m, d } = parseDay(key);
  const utc = new Date(Date.UTC(y, m - 1, d + count));
  return dayKey(utc.getUTCFullYear(), utc.getUTCMonth() + 1, utc.getUTCDate());
}

function addMonths(key, count) {
  const { y, m, d } = parseDay(key);
  const utc = new Date(Date.UTC(y, m - 1 + count, 1));
  const last = new Date(Date.UTC(utc.getUTCFullYear(), utc.getUTCMonth() + 1, 0)).getUTCDate();
  return dayKey(utc.getUTCFullYear(), utc.getUTCMonth() + 1, Math.min(d, last));
}

function weekdayMon0(key) {
  const { y, m, d } = parseDay(key);
  return (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
}

function demoDay() {
  return campusDay(state.health?.demo_now) || "2026-10-24";
}

function shiftCalendar(direction) {
  const anchor = state.calendarAnchor || demoDay();
  state.calendarAnchor = state.calendarMode === "week" ? addDays(anchor, direction * 7) : addMonths(anchor, direction);
  renderCalendarView();
}

function calendarEntries() {
  const rows = [];
  for (const lesson of state.calendar?.lessons || []) {
    rows.push({
      day: campusDay(lesson.start),
      title: lesson.title,
      time: `${campusClock(lesson.start)}–${campusClock(lesson.end)}`.replace(/–$/, ""),
      where: lesson.location || "",
      kind: "Lezione",
      tone: "lesson",
      source_id: lesson.source_id,
    });
  }
  for (const event of state.calendar?.evening_events || []) {
    rows.push({
      day: campusDay(event.start),
      title: event.title,
      time: campusClock(event.start),
      where: event.location || "",
      kind: "Serata",
      tone: "evening",
      source_id: event.source_id,
    });
  }
  for (const item of state.calendar?.agenda || []) {
    rows.push({
      day: campusDay(item.start),
      title: item.title || item.event_id,
      time: campusClock(item.start),
      where: item.location || "",
      kind: "Agenda",
      tone: "agenda",
      source_id: item.source_id,
    });
  }
  return rows.filter((row) => row.day);
}

function longDay(key) {
  const { y, m, d } = parseDay(key);
  return new Intl.DateTimeFormat("it-IT", {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(y, m - 1, d, 12)));
}

function renderCalendarView() {
  const node = document.getElementById("calendar-body");
  const detail = document.getElementById("calendar-day");
  const heading = document.getElementById("cal-heading");
  if (!node || !state.calendar) return;
  if (!state.calendarAnchor) state.calendarAnchor = demoDay();
  const anchor = state.calendarAnchor;
  const mode = state.calendarMode === "week" ? "week" : "month";
  const monthBtn = document.getElementById("cal-mode-month");
  const weekBtn = document.getElementById("cal-mode-week");
  if (monthBtn) monthBtn.setAttribute("aria-pressed", mode === "month" ? "true" : "false");
  if (weekBtn) weekBtn.setAttribute("aria-pressed", mode === "week" ? "true" : "false");
  const { y, m } = parseDay(anchor);
  if (heading) {
    if (mode === "week") {
      const start = addDays(anchor, -weekdayMon0(anchor));
      const end = addDays(start, 6);
      const startParts = parseDay(start);
      const endParts = parseDay(end);
      heading.textContent = start.slice(0, 7) === end.slice(0, 7)
        ? `${startParts.d}–${endParts.d} ${CAL_MONTHS[endParts.m - 1]} ${endParts.y}`
        : `${startParts.d} ${CAL_MONTHS[startParts.m - 1]} – ${endParts.d} ${CAL_MONTHS[endParts.m - 1]} ${endParts.y}`;
    } else {
      heading.textContent = `${CAL_MONTHS[m - 1].charAt(0).toUpperCase()}${CAL_MONTHS[m - 1].slice(1)} ${y}`;
    }
  }
  const entries = calendarEntries();
  const byDay = new Map();
  for (const row of entries) {
    const list = byDay.get(row.day) || [];
    list.push(row);
    byDay.set(row.day, list);
  }
  const today = demoDay();
  node.replaceChildren();
  const grid = el("div", { class: `iphone-cal ${mode}`, role: "grid", "aria-label": mode === "week" ? "Settimana" : "Mese" });
  for (const label of CAL_WEEKDAYS) {
    grid.append(el("div", { class: "cal-dow", text: label }));
  }
  const { y: ay, m: am } = parseDay(anchor);
  const first = dayKey(ay, am, 1);
  const origin = mode === "week" ? addDays(anchor, -weekdayMon0(anchor)) : addDays(first, -weekdayMon0(first));
  const count = mode === "week" ? 7 : 42;
  for (let index = 0; index < count; index += 1) {
    const key = addDays(origin, index);
    const inMonth = parseDay(key).m === am;
    const selected = key === anchor;
    const dayEntries = byDay.get(key) || [];
    const button = el("button", {
      type: "button",
      class: `cal-day${inMonth || mode === "week" ? "" : " outside"}${selected ? " selected" : ""}${key === today ? " today" : ""}`,
      "data-action": "cal-day",
      "data-id": key,
      "aria-pressed": selected ? "true" : "false",
      "aria-label": `${longDay(key)}${dayEntries.length ? `, ${dayEntries.length} voci` : ""}`,
    });
    button.append(el("span", { class: "cal-num", text: String(Number(key.slice(8))) }));
    if (mode === "week") {
      const stack = el("div", { class: "cal-pills" });
      for (const row of dayEntries.slice(0, 3)) {
        stack.append(el("span", { class: `cal-pill tone-${row.tone}`, text: row.title }));
      }
      if (dayEntries.length > 3) stack.append(el("span", { class: "cal-more", text: `+${dayEntries.length - 3}` }));
      button.append(stack);
    } else {
      const dots = el("span", { class: "cal-dots" });
      for (const tone of [...new Set(dayEntries.map((row) => row.tone))].slice(0, 3)) {
        dots.append(el("i", { class: `dot tone-${tone}` }));
      }
      button.append(dots);
    }
    grid.append(button);
  }
  node.append(grid);
  if (!detail) return;
  const chosen = byDay.get(anchor) || [];
  detail.replaceChildren(el("h3", { text: longDay(anchor) }));
  if (!chosen.length) {
    detail.append(el("p", { class: "meta", text: "Niente in questo giorno. Tocca un giorno con il puntino per le lezioni, la serata o l'agenda." }));
    return;
  }
  for (const row of chosen) {
    detail.append(el("article", { class: "mini-card cal-item" }, [
      el("p", { class: `board-pill tone-${row.tone}`, text: row.kind }),
      el("h3", { text: row.title }),
      el("p", { text: [row.time, row.where].filter(Boolean).join(" · ") }),
      el("p", { class: "meta", text: row.source_id || "" }),
    ]));
  }
}

function renderBookings() {
  const list = document.getElementById("booking-list");
  const agenda = document.getElementById("agenda-list");
  if (list) {
    list.replaceChildren();
    for (const row of state.recommendations) {
      list.append(el("article", { class: "mini-card" }, [
        el("h3", { text: row.title }),
        el("p", { text: row.reason }),
        el("button", { class: "leaf", type: "button", "data-action": "propose", "data-id": row.event_id, text: "Proponi iscrizione" }),
      ]));
    }
  }
  if (agenda) {
    agenda.replaceChildren(el("h3", { text: "My Agenda" }));
    if (!state.agenda.length) agenda.append(el("p", { text: "Vuota finché un'approvazione non registra l'iscrizione simulata." }));
    for (const row of state.agenda) {
      agenda.append(el("article", { class: "mini-card" }, [
        el("h3", { text: row.title || row.event_id }),
        el("p", { class: "meta", text: `${row.status} · ${row.mode} · ${row.source_id}` }),
      ]));
    }
  }
  const strip = document.getElementById("agenda-strip");
  if (strip) {
    strip.replaceChildren(el("h3", { text: "In agenda" }));
    if (!state.agenda.length) strip.append(el("p", { class: "meta", text: "Vuota finché Approva non registra l'iscrizione simulata." }));
    for (const row of state.agenda) {
      strip.append(el("button", {
        type: "button",
        class: "scelto-card",
        "data-action": "event-open",
        "data-id": row.event_id,
      }, [
        el("strong", { text: row.title || row.event_id }),
        el("span", { text: `${row.status} · ${row.source_id}` }),
      ]));
    }
  }
}

function renderShelf() {
  const node = document.getElementById("shelf-list");
  if (!node) return;
  node.replaceChildren();
  for (const post of state.posts.filter((item) => item.kind === "share")) {
    node.append(el("article", { class: "mini-card" }, [
      el("h3", { text: post.title }),
      el("p", { text: post.body }),
      el("p", { class: "meta", text: post.source_id }),
    ]));
  }
}

function renderContacts() {
  const node = document.getElementById("contact-list");
  if (!node) return;
  node.replaceChildren();
  for (const contact of state.contacts) {
    node.append(el("article", { class: "mini-card" }, [
      el("h3", { text: contact.name }),
      el("p", { text: `${contact.role} · ${contact.where || ""}` }),
      el("p", { class: "meta", text: `${contact.email} · ${contact.note}` }),
    ]));
  }
}

function renderLinks() {
  const canvas = document.getElementById("canvas-pane");
  const pronote = document.getElementById("pronote-pane");
  const session = state.session;
  if (canvas) {
    canvas.textContent = session?.canvas_id ? `Link salvato, non aperto: ${session.canvas_id}` : "Canvas non collegato.";
  }
  if (pronote) {
    pronote.textContent = session?.pronote_id ? `Link salvato, non aperto: ${session.pronote_id}` : "Pronote non collegato.";
  }
}

function renderFeedback() {
  const select = document.getElementById("feedback-event");
  if (select && state.events.length && select.options.length !== state.events.length + 1) {
    const current = select.value;
    select.replaceChildren(el("option", { value: "", text: "Scegli un evento" }));
    for (const event of state.events) {
      select.append(el("option", { value: event.id, text: event.title }));
    }
    if (current) select.value = current;
  }
  const node = document.getElementById("feedback-list");
  if (!node) return;
  node.replaceChildren();
  for (const item of state.feedback) {
    node.append(el("article", { class: "mini-card" }, [
      el("h3", { text: `${item.author_name} · ${item.rating}/5` }),
      el("p", { text: item.body }),
    ]));
  }
}

function renderSettings() {
  const node = document.getElementById("settings-summary");
  if (!node || !state.session) return;
  node.textContent = `Mi piace: ${(state.session.likes || []).join(", ") || "nessuno"}. Scarti: ${(state.session.dislikes || []).join(", ") || "nessuno"}.`;
}

function setAssistant(show) {
  const panel = document.getElementById("ai-overlay");
  const chip = document.getElementById("ai-chip");
  const head = document.querySelector(".head-ai");
  if (!panel) return;
  panel.hidden = !show;
  if (chip) chip.setAttribute("aria-expanded", show ? "true" : "false");
  if (head) head.setAttribute("aria-expanded", show ? "true" : "false");
}

function toggleAssistant(open) {
  const panel = document.getElementById("ai-overlay");
  if (!panel) return;
  setAssistant(open ? panel.hidden : false);
}

function renderChat() {
  const log = document.getElementById("ai-log");
  const mode = document.getElementById("assistant-mode");
  if (mode && state.health) {
    const last = [...state.chat].reverse().find((item) => item.role === "assistant" && item.assistant);
    if (last?.model === "gemini" || last?.assistant === "gemma") mode.textContent = "Gemini ha ragionato solo sui passaggi recuperati.";
    else if (last?.model === "fallback_after_gemini" || last?.assistant === "fallback_after_gemma") mode.textContent = "Gemini scartato: il ragionamento resta sui documenti citati.";
    else if (state.health.gemma === "planned") mode.textContent = "Retrieval reale. Gemini è PLANNED, non collegato.";
    else mode.textContent = "Gemini può ragionare solo sui passaggi recuperati.";
  }
  if (!log) return;
  log.replaceChildren();
  for (const message of state.chat) {
    const bubble = el("div", { class: `bubble ${message.role === "student" ? "user" : "assistant"}` });
    if (message.reasoning?.length) {
      const trace = el("ol", { class: "trace" });
      for (const step of message.reasoning) trace.append(el("li", { text: step }));
      bubble.append(el("p", { class: "meta", text: "Retrieval → ragionamento → risposta" }), trace);
    }
    bubble.append(el("p", { text: message.text }));
    if (message.source_ids) {
      for (const sourceId of message.source_ids) {
        bubble.append(el("button", { class: "ghost", type: "button", "data-action": "source", "data-id": sourceId, text: sourceId }));
      }
    }
    const top = (message.recommendations || [])[0];
    const pendingSame = state.proposal && top && state.proposal.event_id === top.event_id;
    const already = top && state.agenda.some((row) => row.event_id === top.event_id);
    if (top && message.latestRecommend && !pendingSame && !already) {
      bubble.append(el("p", { class: "meta", text: `Brain · ${top.title} · ${top.source_id}` }));
      bubble.append(el("button", {
        class: "solid",
        type: "button",
        "data-action": "propose",
        "data-id": top.event_id,
        text: "Proponi iscrizione",
      }));
    }
    log.append(bubble);
  }
  if (state.proposal) {
    log.append(el("div", { class: "bubble assistant" }, [
      el("p", { text: `Agent · proposta ${state.proposal.approval_id} per ${state.proposal.event_title}. Fonte ${state.proposal.source_id}. L'agenda è ancora vuota.` }),
      el("button", { class: "solid", type: "button", "data-action": "approve-reg", text: "Approva" }),
      el("button", { class: "ghost", type: "button", "data-action": "reject-reg", text: "Rifiuta" }),
    ]));
  }
  if (state.agenda.length) {
    const agenda = el("div", { class: "bubble assistant" });
    agenda.append(el("p", { text: "Agenda" }));
    for (const row of state.agenda) {
      agenda.append(el("p", { text: `${row.title || row.event_id} · ${row.source_id} · ${row.status}` }));
    }
    log.append(agenda);
  }
  log.scrollTop = log.scrollHeight;
}

async function askAssistant(text) {
  const message = String(text || "").trim();
  if (!message || !state.selectedId) return;
  state.chat.push({ role: "student", text: message });
  renderChat();
  try {
    const answer = await api("/assistant/ask", {
      method: "POST",
      body: JSON.stringify({ user_id: state.selectedId, message }),
    });
    const recommendations = answer.recommendations || [];
    for (const item of state.chat) delete item.latestRecommend;
    state.chat.push({
      role: "assistant",
      text: answer.text,
      source_ids: answer.source_ids || [],
      assistant: answer.assistant || "dataset",
      model: answer.model || "deterministic",
      reasoning: answer.reasoning || [],
      recommendations,
      latestRecommend: recommendations.length > 0,
    });
  } catch (error) {
    state.chat.push({ role: "assistant", text: error.message || "Nessuna risposta.", source_ids: [] });
  }
  renderChat();
}

async function proposeRegistration(eventId) {
  try {
    const result = await api("/registrations/propose", {
      method: "POST",
      body: JSON.stringify({ user_id: state.selectedId, event_id: eventId }),
    });
    state.proposal = result.proposal;
    state.agenda = [];
    state.chat.push({
      role: "assistant",
      text: "Proposta registrata in attesa. Nessuna iscrizione in agenda finché non premi Approva.",
      source_ids: result.proposal?.source_id ? [result.proposal.source_id] : [],
    });
    render();
  } catch (error) {
    state.error = error.message || "Proposta non creata.";
    render();
  }
}

async function approveRegistration() {
  if (!state.proposal) return;
  try {
    const approved = await api("/registrations/approve", {
      method: "POST",
      body: JSON.stringify({ user_id: state.selectedId, approval_id: state.proposal.approval_id }),
    });
    const sourceId = approved.source_id || state.proposal.source_id;
    state.proposal = null;
    state.chat.push({
      role: "assistant",
      text: `Agenda aggiornata: ${approved.registration?.event_title || sourceId}. Fonte: ${sourceId}. Iscrizione simulata.`,
      source_ids: sourceId ? [sourceId] : [],
    });
    await refreshStudent();
    showView("calendario");
    setAssistant(true);
  } catch (error) {
    state.error = error.message || "Iscrizione non registrata.";
    render();
  }
}

async function rejectRegistration() {
  if (!state.proposal) return;
  try {
    await api("/registrations/reject", {
      method: "POST",
      body: JSON.stringify({ user_id: state.selectedId, approval_id: state.proposal.approval_id }),
    });
    state.proposal = null;
    render();
  } catch (error) {
    state.error = error.message || "Rifiuto non registrato.";
    render();
  }
}

function feedbackSubject() {
  const select = document.getElementById("feedback-event");
  const date = document.getElementById("feedback-date").value;
  const event = state.events.find((item) => item.id === select.value);
  const subject = event && date ? `${event.title} · ${date}` : "";
  const preview = document.getElementById("feedback-subject");
  if (preview) preview.textContent = subject ? `Oggetto: ${subject}` : "Oggetto: evento · data";
  return subject.slice(0, 160);
}

async function sendFeedback() {
  const chips = [...document.querySelectorAll("#feedback-chips button[aria-pressed='true']")].map((button) => button.dataset.id);
  const typed = document.getElementById("feedback-body").value.trim();
  const body = [...chips, typed].filter(Boolean).join(". ");
  const subject = feedbackSubject();
  const rating = Number(document.getElementById("feedback-rating").value);
  if (!subject || body.length < 8) {
    state.error = "Servono un evento, una data e un commento di almeno 8 caratteri.";
    render();
    return;
  }
  try {
    await api("/feedback", {
      method: "POST",
      body: JSON.stringify({ user_id: state.selectedId, body, subject, rating }),
    });
    document.getElementById("feedback-body").value = "";
    state.feedback = (await api("/feedback")).feedback;
    renderFeedback();
  } catch (error) {
    state.error = error.message || "Feedback non pubblicato.";
    render();
  }
}
