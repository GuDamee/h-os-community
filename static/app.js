const CAPTION = "Esri World Imagery · H-FARM College / Campus, Roncade (La Serra · Via Sile). Satellite di default; pin schematici sugli edifici del dataset. Non è un rilievo ufficiale.";
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
  boards: [],
  activeBoardId: null,
  activeBoard: null,
  calendar: null,
  deskPanel: "home",
  chatBusy: false,
  boardFilter: "Tutti",
  boardSearch: "",
  boardStatus: "programmati",
  interestDraft: new Set(),
  enrolledIds: new Set(),
  boardPosts: [],
  sourceFilter: "Tutti",
};

const SESSION_KEY = "hos.session.v4";
const SESSION_LEGACY_KEYS = ["hos.session.v3", "hos.session.v2", "hos.session"];
const DEMO_LIKES = ["cinema", "finanza", "gaming", "programmazione"];

const INTEREST_GROUPS = [
  { id: "ai", label: "AI e tecnologia", icon: "◆", tags: ["AI", "data-science", "programmazione", "robotica", "cybersecurity"] },
  { id: "startup", label: "Startup e business", icon: "↗", tags: ["startup", "imprenditoria", "marketing", "finanza", "networking"] },
  { id: "sport", label: "Sport e movimento", icon: "●", tags: ["sport", "fitness", "calcio", "basket", "running"] },
  { id: "musica", label: "Musica", icon: "♪", tags: ["musica"] },
  { id: "cinema", label: "Cinema e creatività", icon: "✦", tags: ["cinema", "arte", "fotografia", "teatro", "design", "UX-UI"] },
  { id: "gaming", label: "Gaming", icon: "+", tags: ["gaming"] },
  { id: "sosten", label: "Sostenibilità", icon: "❀", tags: ["sostenibilita", "ambiente"] },
  { id: "culture", label: "Culture e nuove amicizie", icon: "◎", tags: ["networking", "teatro"] },
];

const FEEDBACK_CHIPS = [
  "Ottimo evento",
  "Orario scomodo",
  "Location poco chiara",
  "Servirebbero piu posti",
  "Docente / host chiaro",
  "Vorrei un follow-up",
];
const SOURCE_TYPES = [
  { id: "club", label: "Club", css: "src-club" },
  { id: "life", label: "Eventi Student Life", css: "src-life" },
  { id: "office", label: "Messaggi Student Office", css: "src-office" },
  { id: "faculty", label: "Messaggi docenti", css: "src-faculty" },
];
const SOURCE_BY_ID = Object.fromEntries(SOURCE_TYPES.map((s) => [s.id, s]));
const CHATTA_RECIPIENTS = [
  { email: "life@campus.demo", name: "Student Life", keys: ["student life", "aperitivo", "evento", "club", "big hall", "serata", "iscriv"] },
  { email: "reception@campus.demo", name: "Student Office", keys: ["student office", "reception", "badge", "documento", "orari", "locker", "ufficio"] },
  { email: "age.fund@campus.demo", name: "Age Fund Desk", keys: ["age fund", "grant", "bando", "fond"] },
  { email: "bianchi@faculty.demo", name: "Prof. Bianchi (Business English)", keys: ["bianchi", "business english", "inglese"] },
  { email: "rossi@faculty.demo", name: "Prof. Rossi (AI Data Science)", keys: ["rossi", "data science", "ai ", "machine learning"] },
  { email: "verdi@faculty.demo", name: "Prof. Verdi (Calculus)", keys: ["verdi", "calculus", "calcolo", "serie"] },
];
const SURVEY_KEY = "hos.surveys.v2";
const SURVEY_INTERESTS = [
  "AI e tecnologia",
  "Startup e business",
  "Sport e movimento",
  "Musica",
  "Cinema e creatività",
  "Gaming",
  "Sostenibilità",
  "Culture e amicizie",
];
const SURVEY_WANTS = [
  "Eventi Student Life",
  "Workshop / skill",
  "Sport e benessere",
  "Supporto Student Office",
  "Incontri con docenti",
];
const SURVEY_TO = [
  { id: "life", label: "Student Life" },
  { id: "office", label: "Student Office" },
  { id: "both", label: "Entrambi" },
];
let bootReady = null;
let bootResolve = null;
bootReady = new Promise((resolve) => { bootResolve = resolve; });

let boardLoad = 0;
let campusMap = null;
let pinLayer = null;
let pinCloseTimer = null;
let mapFitted = false;

const CAMPUS_CENTER = [45.5665, 12.4305]; // H-FARM College / Campus · Nominatim 2026-10-24
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
document.getElementById("like-btn").addEventListener("click", () => decideCurrent(true));
document.getElementById("dislike-btn").addEventListener("click", () => decideCurrent(false));
document.getElementById("skip-btn")?.addEventListener("click", () => decideCurrent("skip"));
document.getElementById("enter-map").addEventListener("click", () => enterDesk());
document.getElementById("demo-likes").addEventListener("click", useDemoLikes);
document.getElementById("reset-onboarding")?.addEventListener("click", resetOnboarding);
wireSwipe();
wireAssistantForm();
wireFeedbackForm();
wirePersonalize();
wireChattaForm();
wireSurveyUI();

document.getElementById("formula")?.addEventListener("change", (event) => {
  if (state.busy) {
    event.target.value = state.formula;
    return;
  }
  state.formula = event.target.value;
  if (state.selectedId) refreshStudent();
});
document.getElementById("restart-cards")?.addEventListener("click", restartPreferenceCards);
const accessSubmitBtn = document.querySelector("#access-form button[type='submit']");
if (accessSubmitBtn) {
  accessSubmitBtn.disabled = true;
  accessSubmitBtn.dataset.wait = "1";
}

boot();

async function boot() {
  try {
    const [health, users, events, places, tags, boards, calendar] = await Promise.all([
      api("/health"),
      api("/users"),
      api("/events"),
      api("/places"),
      api("/tags"),
      api("/community/boards"),
      api("/calendar"),
    ]);
    state.health = health;
    state.users = users.users;
    state.events = events.events;
    state.places = places.places;
    state.tags = normalizeTagList(tags && tags.tags);
    state.boards = boards.boards || [];
    state.calendar = calendar;
    state.session = loadSession();
    if (state.session) sanitizeSessionTags(state.session, true);
    paintDate();
    const readyBtn = document.querySelector("#access-form button[type='submit']");
    if (readyBtn) {
      readyBtn.disabled = false;
      delete readyBtn.dataset.wait;
    }
    if (state.session) {
      state.deskUser = deskUserFromSession();
      const requested = location.hash.replace("#", "");
      state.selectedId = state.users.some((user) => user.id === requested) ? requested : "usr-desk";
      if (state.selectedId !== "usr-desk") document.getElementById("roster").hidden = false;
      showScreen("desk");
      paintExternalLinks();
      focusSection("bacheca");
      if ((state.session.likes || []).length) {
        try {
          await api("/desk/profile", { method: "POST", body: JSON.stringify(profileBody()) });
        } catch (_) { /* ignore stale profile */ }
        await refreshStudent();
      } else {
        state.matches = [];
        state.busy = null;
        render();
      }
      await ensureCommunitySeed();
      renderFilterPills();
      renderIgFeed();
      if (!(state.session.likes || []).length) {
        window.setTimeout(() => openPersonalizeModal(true), 400);
      }
    } else {
      showScreen("access");
    }
  } catch (error) {
    state.error = error.message || "H-ELP non risponde.";
    if (!state.tags.length) state.tags = normalizeTagList([]);
    showScreen("access");
    const err = document.getElementById("error");
    if (err) {
      err.hidden = false;
      err.textContent = state.error;
    }
  } finally {
    if (bootResolve) bootResolve();
  }
}

async function refreshStudent() {
  const requestedId = state.selectedId;
  const generation = ++boardLoad;
  const person = selected();
  if (person) document.title = `H-ELP · ${person.name}`;
  state.busy = "match";
  state.error = null;
  state.idleReason = null;
  state.matches = [];
  state.actions = [];
  state.notices = [];
  state.method = null;
  render();
  try {
    const [match, actions, board] = await Promise.all([
      api("/match", {
        method: "POST",
        body: JSON.stringify({ user_id: requestedId, limit: 4, formula: state.formula }),
      }),
      api(`/agent/actions?user_id=${encodeURIComponent(requestedId)}`),
      api(`/bacheca?user_id=${encodeURIComponent(requestedId)}`),
    ]);
    if (generation !== boardLoad || state.selectedId !== requestedId) return;
    state.matches = match.matches;
    state.method = match.method;
    state.displayBy = match.display_by;
    state.actions = actions.actions;
    state.notices = board.notices;
    history.replaceState(null, "", `#${requestedId}`);
    document.title = `H-ELP · ${selected().name}`;
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
  if (state.busy && action !== "source") return;
  if (action === "match") refreshStudent();
  else if (action === "section") {
    focusSection(id);
    document.body.classList.remove("hy-rail-open");
  } else if (action === "chatta-suggest") {
    suggestChattaRecipient();
  } else if (action === "survey-save") {
    saveSurvey(id);
  } else if (action === "open-survey") {
    openSurveyDialog(true);
  } else if (action === "close-survey") {
    openSurveyDialog(false);
  } else if (action === "survey-submit") {
    submitInterestSurvey();
  }
  else if (action === "prefs" || action === "personalize") openPersonalizeModal(true);
  else if (action === "filter-pill") {
    state.sourceFilter = id || "Tutti";
    state.boardFilter = id || "Tutti";
    renderFilterPills();
    renderIgFeed();
  } else if (action === "toggle-interest") {
    toggleInterestDraft(id);
  } else if (action === "scopri") {
    if (id) openEventDetail(id);
  } else if (action === "event-enroll") {
    if (id) enrollEvent(id);
  } else if (action === "event-unroll") {
    if (id) unrollEvent(id);
  } else if (action === "event-ask") {
    if (id) askAboutEvent(id);
  }
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
  else if (action === "stub" || action === "close-stub") toggleStub(action === "stub");
  else if (action === "open-ai") openAiOverlay(true);
  else if (action === "open-map") openMapAt(id);
  else if (action === "close-ai") openAiOverlay(false);
  else if (action === "ext-canvas" || action === "ext-pronote") {
    const href = target.getAttribute("href") || "";
    if (!href || href === "#") {
      event.preventDefault();
      state.error = action === "ext-canvas"
        ? "Aggiungi il link Canvas in accesso (facoltativo)."
        : "Aggiungi il link Pronote in accesso (facoltativo).";
      const err = document.getElementById("error");
      if (err) { err.hidden = false; err.textContent = state.error; }
    }
  }
  else if (action === "open-board" || action === "ig-tab") {
    focusSection("bacheca");
    showIgTab("feed");
  }
}

function showIgTab(which) {
  const feed = document.getElementById("ig-feed-pane");
  if (feed) feed.hidden = false;
  const dms = document.getElementById("ig-dm-pane");
  if (dms) dms.hidden = true;
  for (const tab of document.querySelectorAll(".ig-tab")) {
    tab.setAttribute("aria-selected", String(tab.dataset.id === "feed"));
  }
  renderIgFeed();
}

function render() {
  const error = document.getElementById("error");
  if (error) {
    error.hidden = !state.error;
    error.textContent = state.error || "";
  }
  const modeEl = document.getElementById("mode");
  if (modeEl) modeEl.textContent = modeLabel();
  const matchBtn = document.getElementById("match-btn");
  const tickBtn = document.getElementById("tick-btn");
  if (matchBtn) {
    matchBtn.disabled = Boolean(state.busy);
    matchBtn.textContent = state.busy === "match" ? "Abbino…" : "Abbina";
  }
  if (tickBtn) {
    tickBtn.disabled = Boolean(state.busy);
    tickBtn.textContent = state.busy === "tick" ? "Leggo…" : "Tic dell'agente";
  }
  const person = selected();
  const mapTitle = document.getElementById("map-title");
  if (mapTitle) mapTitle.textContent = person ? person.name : "Campus";
  const homeTitle = document.getElementById("home-title");
  if (homeTitle) homeTitle.textContent = person ? `Ciao, ${person.name.split(" ")[0]}` : "La tua scrivania";
  const boardTitle = document.getElementById("board-title");
  if (boardTitle && state.deskPanel === "bacheca") boardTitle.textContent = "La bacheca del campus";
  paintDate();
  paintYou();
  renderRoster();
  renderPlan();
  renderTray();
  renderCork();
  renderDock();
  renderHome();
  paintPrefsSummary();
  paintExternalLinks();
  renderCalendar();
  renderFilterPills();
  renderIgFeed();
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
    el("div", { text: "Persone, eventi e mail sono inventati. L'accesso è locale: la password non viene salvata. Canvas e Pronote non sono collegati. MIT, su GitHub. Pattern aperti: GBrain, PipesHub, OpenInstinct. Nessuno dei tre è installato." }),
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
  // Schematic x/y from places.json, anchored on H-FARM College satellite footprint.
  return [
    CAMPUS_CENTER[0] + (300 - y) * 0.0000058,
    CAMPUS_CENTER[1] + (x - 500) * 0.0000072,
  ];
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
  campusMap = L.map(node, {
    center: CAMPUS_CENTER,
    zoom: 18,
    minZoom: 16,
    maxZoom: 19,
    scrollWheelZoom: true,
    zoomControl: true,
    attributionControl: true,
  });
  campusMap.setView(CAMPUS_CENTER, 18, { animate: false });
  const satellite = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    {
      maxZoom: 19,
      attribution: 'Tiles &copy; Esri — Esri, Maxar, Earthstar Geographics',
    },
  );
  const streets = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  });
  satellite.addTo(campusMap);
  L.control.layers(
    { Satellite: satellite, Strade: streets },
    null,
    { position: "topright", collapsed: false },
  ).addTo(campusMap);
  pinLayer = L.layerGroup().addTo(campusMap);
  node.dataset.map = "esri-world-imagery";
  node.setAttribute("aria-label", "Mappa satellite Esri del campus H-FARM College a Roncade.");
  const caption = document.getElementById("map-caption");
  if (caption) caption.textContent = CAPTION;
  const zones = document.getElementById("map-zones");
  if (zones) zones.textContent = "H-FARM College · La Serra · Via Sile · Campi · Big Hall";
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
  // Keep H-FARM campus framed — never fitBounds to world/low zoom.
  campusMap.setView(CAMPUS_CENTER, 18, { animate: false });
  mapFitted = true;
  window.requestAnimationFrame(() => {
    campusMap.invalidateSize({ animate: false });
    campusMap.setView(CAMPUS_CENTER, 18, { animate: false });
  });
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
    return "H-ELP non risponde. Controlla che il server sia acceso, poi premi Abbina.";
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
  // prefs screen kept as fallback; primary UX is modal on desk
  document.getElementById("screen-prefs").hidden = name !== "prefs";
  document.getElementById("screen-desk").hidden = name !== "desk";
  if (name === "prefs") {
    // Prefer modal when desk can show; else legacy sheet
    renderSwipe();
  }
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
  if (session.nickname && String(session.nickname).trim()) return String(session.nickname).trim();
  return [session.nome, session.cognome].filter(Boolean).join(" ");
}

function loadSession() {
  try {
    let raw = JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
    if (!raw) {
      for (const key of SESSION_LEGACY_KEYS) {
        const legacy = JSON.parse(localStorage.getItem(key) || "null");
        if (legacy && typeof legacy.email === "string") {
          raw = legacy;
          localStorage.removeItem(key);
          break;
        }
      }
    }
    if (!raw || typeof raw.email !== "string") return null;
    if ("password" in raw) delete raw.password;
    if (typeof raw.nome !== "string" || !raw.nome.trim()) {
      const derived = nameFromEmail(raw.email);
      raw.nome = derived.nome;
      raw.cognome = typeof raw.cognome === "string" && raw.cognome.trim() ? raw.cognome : derived.cognome;
    } else if (typeof raw.cognome !== "string") {
      raw.cognome = "";
    }
    raw.nickname = typeof raw.nickname === "string" ? raw.nickname.trim() : "";
    raw.likes = Array.isArray(raw.likes) ? raw.likes : [];
    raw.dislikes = Array.isArray(raw.dislikes) ? raw.dislikes : [];
    raw.skipped = Array.isArray(raw.skipped) ? raw.skipped : [];
    raw.canvas_id = raw.canvas_link || raw.canvas_id || "";
    raw.pronote_id = raw.pronote_link || raw.pronote_id || "";
    return raw;
  } catch {
    return null;
  }
}

function normalizeTagList(tags) {
  const fromApi = Array.isArray(tags) ? tags.filter((t) => typeof t === "string" && t.trim()) : [];
  if (fromApi.length) return fromApi;
  return Object.keys(TAG_NOTES);
}

function sanitizeSessionTags(session, persist) {
  if (!session) return session;
  const known = new Set(state.tags.length ? state.tags : Object.keys(TAG_NOTES));
  const clean = (list) => (Array.isArray(list) ? list.filter((tag) => known.has(tag)) : []);
  session.likes = clean(session.likes);
  session.dislikes = clean(session.dislikes);
  session.skipped = clean(session.skipped);
  if (!session.likes.length) {
    const pool = state.tags.length ? state.tags : Object.keys(TAG_NOTES);
    const pending = pool.filter((tag) => (
      !session.likes.includes(tag)
      && !session.dislikes.includes(tag)
      && !(session.skipped || []).includes(tag)
    ));
    if (!pending.length) {
      session.dislikes = [];
      session.skipped = [];
    }
  }
  if (persist) saveSession(session);
  return session;
}

function ensurePreferenceDeck() {
  if (!state.session) return;
  if (!state.tags.length) state.tags = normalizeTagList([]);
  sanitizeSessionTags(state.session, true);
}

function restartPreferenceCards() {
  if (!state.session) return;
  state.session.likes = [];
  state.session.dislikes = [];
  state.session.skipped = [];
  swipeBusy = false;
  saveSession(state.session);
  ensurePreferenceDeck();
  showScreen("prefs");
  renderSwipe();
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

async function submitAccess(event) {
  event.preventDefault();
  const nickname = document.getElementById("nickname").value.trim();
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;
  const errors = {};
  if (nickname.length < 2) errors.nickname = "Scegli un nickname di almeno 2 caratteri.";
  if (!/^[^@\s]+@[^@\s]+$/.test(email)) errors.email = "L'email scolastica deve contenere @. Il dominio può essere finto.";
  if (!passwordOk(password)) errors.password = "Servono 8 caratteri, maiuscola, minuscola, numero e simbolo.";
  if (!document.getElementById("terms").checked) errors.terms = "Accetta i termini per entrare.";
  for (const node of document.querySelectorAll(".field-error")) node.textContent = errors[node.dataset.for] || "";
  if (Object.keys(errors).length) return;
  const submitBtn = document.querySelector("#access-form button[type='submit']");
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = "Carico i tag…";
  }
  try {
    if (bootReady) await Promise.race([bootReady, new Promise((r) => setTimeout(r, 8000))]);
    if (!state.tags.length) state.tags = normalizeTagList([]);
    document.getElementById("password").value = "";
    const named = nameFromEmail(email);
    saveSession({
      nickname,
      nome: named.nome,
      cognome: named.cognome,
      email,
      canvas_id: document.getElementById("canvas-link").value.trim(),
      pronote_id: document.getElementById("pronote-link").value.trim(),
      likes: [],
      dislikes: [],
      skipped: [],
    });
    for (const key of SESSION_LEGACY_KEYS) localStorage.removeItem(key);
    swipeBusy = false;
    ensurePreferenceDeck();
    try { paintExternalLinks(); } catch (_) {}
    await enterDesk();
    try { openPersonalizeModal(true); } catch (modalErr) {
      console.warn("personalize modal", modalErr);
      showScreen("desk");
      focusSection("bacheca");
    }
  } catch (error) {
    console.error("submitAccess", error);
    state.error = (error && error.message) || "Accesso non completato.";
    const err = document.getElementById("error");
    if (err) { err.hidden = false; err.textContent = state.error; }
    // Still try to land on desk if session was saved
    if (state.session) {
      try { await enterDesk(); } catch (_) { showScreen("desk"); }
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = "Entra";
    }
  }
}

function pendingTags() {
  const session = state.session || { likes: [], dislikes: [], skipped: [] };
  return state.tags.filter((tag) => (
    !session.likes.includes(tag)
    && !session.dislikes.includes(tag)
    && !(session.skipped || []).includes(tag)
  ));
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
  cinema: ["cultura", "Proiezioni, corte e la fila per una sedia."],
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
  if (!state.tags.length) state.tags = normalizeTagList([]);
  if (state.session) sanitizeSessionTags(state.session, false);
  let pending = pendingTags();
  if (!pending.length && state.session && !(state.session.likes || []).length) {
    state.session.dislikes = [];
    state.session.skipped = [];
    saveSession(state.session);
    pending = pendingTags();
  }
  const tag = pending[0] || "";
  const card = document.getElementById("swipe-card");
  if (!card) return;
  card.dataset.tag = tag;
  card.classList.remove("toward-like", "toward-dislike", "is-dragging");
  card.style.transform = "";
  const note = TAG_NOTES[tag];
  const kind = note ? note[0] : "preferenza";
  document.getElementById("swipe-tag").textContent = tag || "Carte finite";
  document.getElementById("swipe-kind").textContent = tag ? kind : "fine";
  document.getElementById("swipe-blurb").textContent = tag
    ? (note ? note[1] : "Tag del dataset sintetico.")
    : ((state.session?.likes.length || 0)
      ? "Hai almeno un interesse. Premi «Entra in Bacheca» per aprire la Bacheca."
      : "Nessuna carta utile: premi «Ricomincia carte» oppure scegli il profilo demo.");
  document.getElementById("swipe-mark").innerHTML = TAG_MARKS[kind] || TAG_MARKS.codice;
  const likes = state.session?.likes.length || 0;
  const dislikes = state.session?.dislikes.length || 0;
  const skipped = state.session?.skipped?.length || 0;
  const total = state.tags.length;
  const at = tag ? Math.min(likes + dislikes + skipped + 1, total) : total;
  document.getElementById("swipe-progress").textContent = total ? `${at} di ${total}` : "Tag non caricati";
  const meter = document.getElementById("swipe-meter");
  if (meter) meter.style.width = total ? `${Math.round((at / total) * 100)}%` : "0";
  document.getElementById("swipe-counts").textContent = `${likes} interessa · ${dislikes} no · ${skipped} salta`;
  const enter = document.getElementById("enter-map");
  if (enter) enter.disabled = likes === 0;
  document.getElementById("like-btn").disabled = !tag;
  document.getElementById("dislike-btn").disabled = !tag;
  const skipBtn = document.getElementById("skip-btn");
  if (skipBtn) skipBtn.disabled = !tag;
}

function toggleStub(open) {
  const panel = document.getElementById("agent-stub");
  const button = document.getElementById("agent-bubble");
  if (!panel || !button) return;
  const show = open === true ? true : open === false ? false : panel.hidden;
  panel.hidden = !show;
  button.setAttribute("aria-expanded", show ? "true" : "false");
  if (show) {
    const thread = document.getElementById("assistant-thread");
    if (thread && !thread.dataset.seeded) {
      thread.dataset.seeded = "1";
      appendAssistantBubble(
        "assistant",
        "Ciao! Sono l'assistente a regole di H-ELP (dataset locale, Gemma 4 non collegato). Chiedimi un evento, la mappa o l'agenda.",
      );
    }
  }
}

function wireAssistantForm() {
  const form = document.getElementById("assistant-form");
  if (!form || form.dataset.wired) return;
  form.dataset.wired = "1";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = document.getElementById("assistant-input");
    const question = (input && input.value || "").trim();
    if (!question) return;
    input.value = "";
    answerAssistant(question);
  });
  document.querySelectorAll("[data-assist-q]").forEach((button) => {
    button.addEventListener("click", () => answerAssistant(button.dataset.assistQ));
  });
}

function appendAssistantBubble(role, text, sourceId) {
  const thread = document.getElementById("assistant-thread");
  if (!thread) return;
  const bubble = el("div", { class: "assist-bubble from-" + role }, [
    el("p", { text }),
    sourceId ? el("small", { class: "source-ref", text: "Fonte · " + sourceId }) : null,
  ]);
  thread.append(bubble);
  thread.scrollTop = thread.scrollHeight;
}

async function answerAssistant(question) {
  appendAssistantBubble("student", question);
  // Prefer local Chatta routing so H-ELP can open the compose flow
  if (/email|scrivi a|contatta|chatta|messaggio a|destinatario|ufficio|prof\.?\s|docente/.test(String(question || "").toLowerCase())) {
    const local = localCampusAnswer(question);
    appendAssistantBubble("assistant", local.reply, local.sourceId);
    if (local.openChatta) {
      openAiOverlay(false);
      focusSection("chatta");
      const intent = document.getElementById("chatta-intent");
      if (intent && !intent.value.trim()) intent.value = question;
      suggestChattaRecipient();
    }
    return;
  }
  try {
    const res = await fetch("/assistant/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        likes: (state.session && state.session.likes) || [],
        user_id: state.selectedId || null,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      appendAssistantBubble("assistant", data.reply || data.answer || "Nessuna risposta.", data.source_id || (data.sources && data.sources[0]) || null);
      if (Array.isArray(data.sources) && data.sources.length > 1) {
        appendAssistantBubble("assistant", "Altre fonti: " + data.sources.slice(1, 4).join(", "), null);
      }
      return;
    }
  } catch (_) { /* fall through to local brain */ }
  const local = localCampusAnswer(question);
  appendAssistantBubble("assistant", local.reply, local.sourceId);
  if (local.openChatta) {
    openAiOverlay(false);
    focusSection("chatta");
    const intent = document.getElementById("chatta-intent");
    if (intent && !intent.value.trim()) intent.value = question;
    suggestChattaRecipient();
  }
}

function localCampusAnswer(question) {
  const q = question.toLocaleLowerCase("it-IT");
  const likes = (state.session && state.session.likes) || [];
  const words = q.split(/[^a-z0-9àèéìòù]+/i).filter((w) => w.length > 2);
  const scoreText = (text) => {
    const t = String(text || "").toLocaleLowerCase("it-IT");
    return words.reduce((n, w) => n + (t.includes(w) ? 1 : 0), 0);
  };

  // Lessons / calendar — prefer canonical series id (les-be)
  if (/lezione|calendario|agenda|orario|business english|programming|calculus|business|english/.test(q)) {
    const items = (state.calendar && (state.calendar.items || state.calendar.lessons)) || [];
    const ranked = items
      .map((row) => {
        const title = String(row.title || "").toLocaleLowerCase("it-IT");
        let s = scoreText(row.title + " " + (row.blurb || "") + " " + (row.location || ""));
        if (title && q.includes(title)) s += 8;
        if (/lezione|orario/.test(q) && row.kind === "lezione") s += 2;
        if (/business english/.test(q) && /business english/.test(title)) s += 10;
        return { row, s };
      })
      .sort((a, b) => b.s - a.s);
    const hit = (ranked[0] && ranked[0].s > 0 ? ranked[0].row : null) || items.find((r) => !r.past);
    if (hit) {
      const sourceId = hit.series_id || (String(hit.id || "").startsWith("les-") ? String(hit.id).split("-").slice(0, 2).join("-") : hit.id) || "calendar";
      return {
        reply: `${hit.kind === "evento" ? "Evento" : "Lezione"} «${hit.title}»: ${hit.weekday || hit.date || ""} ${hit.start || ""}–${hit.end || ""} · ${hit.location || "Campus"}.${hit.blurb ? " " + hit.blurb : ""}`,
        sourceId,
      };
    }
  }

  // Recommendations from matches / likes
  if (/consigli|recommend|interess|per me|cosa fare|stasera|dopo le/.test(q)) {
    const top = state.matches[0];
    if (top) {
      return {
        reply: `Ti consiglio «${top.title}» (score ${(top.score || 0).toFixed(2)} su tag ${likes.slice(0, 4).join(", ") || "preferenze"}). ${top.why || top.display_text || ""}`,
        sourceId: top.event_id,
      };
    }
    const evening = ((state.calendar && state.calendar.events) || []).filter((r) => !r.past);
    if (evening[0]) {
      return {
        reply: `Nessun match personale ancora. Evento serale in agenda: «${evening[0].title}» ${evening[0].date} ${evening[0].start}–${evening[0].end} · ${evening[0].location || "Campus"}.`,
        sourceId: evening[0].id || "calendar-event",
      };
    }
  }

  // Map / place
  if (/mappa|campus|h-farm|satellite|dove|edificio|serra|biblioteca|digital lab|big hall/.test(q)) {
    const place = (state.places || []).map((p) => ({ p, s: scoreText(p.name + " " + (p.blurb || "")) })).sort((a, b) => b.s - a.s)[0];
    if (place && place.s > 0) {
      return {
        reply: `Luogo nel dataset: «${place.p.name}» (${place.p.id || "place"}). ${place.p.blurb || "Pin schematico sulla mappa satellite H-FARM College."}`,
        sourceId: place.p.id || "place",
      };
    }
    return {
      reply: "La mappa satellite (Esri) è centrata su H-FARM College, Roncade / La Serra (~45.5665, 12.4305), zoom campus. I pin sono schematici sugli edifici del dataset.",
      sourceId: "map-hfarm",
    };
  }

  // Chatta / email to staff
  if (/email|scrivi a|contatta|chatta|messaggio a|ufficio|prof\.?|docente|destinatario/.test(q)) {
    const rec = routeChattaRecipient(q);
    return {
      reply: "Per questa richiesta il destinatario giusto è " + rec.name + " <" + rec.email + ">. Apri Chatta dal menu (tendina) oppure dimmi pure il testo e preparo oggetto e corpo.",
      sourceId: "chatta",
      openChatta: true,
    };
  }

  // Community boards
  if (/bacheca|community|student office|student life|age fund|club/.test(q)) {
    const boards = state.boards || [];
    const msgs = boards.flatMap((b) => (b.messages || []).map((m) => ({ ...m, board: b.name, boardId: b.id })));
    const hit = msgs.map((m) => ({ m, s: scoreText(m.text + " " + m.author + " " + (m.org || "")) })).sort((a, b) => b.s - a.s)[0];
    if (hit && hit.s > 0) {
      return {
        reply: `In «${hit.m.board}», ${hit.m.org || hit.m.role || "utente"} ${hit.m.author}: «${hit.m.text}»`,
        sourceId: hit.m.id || hit.m.boardId,
      };
    }
  }

  // Event title search
  const events = state.events || [];
  const rankedEv = events
    .map((ev) => ({
      ev,
      s: scoreText((ev.title || "") + " " + (ev.blurb || ev.description || "") + " " + ((ev.tags || []).join(" "))),
    }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s);
  if (rankedEv[0]) {
    const ev = rankedEv[0].ev;
    const where = ev.location_name || (ev.location && ev.location.building) || ev.building || "campus";
    return {
      reply: `Trovato nel dataset: «${ev.title}» (${ev.id}). Dove: ${where}. ${(ev.blurb || ev.description || "").slice(0, 180)}`,
      sourceId: ev.id,
    };
  }

  if (/come funzion|pipeline|brain|librarian|gemma/.test(q)) {
    return {
      reply: "Flusso: Library (JSON eventi/community) → Librarian (validazione fonti) → Campus Brain (match tag) → Agent (bozza) → Human Approval → Action. Gemma 4 narra solo se GEMINI_API_KEY è configurata; altrimenti risposte dataset-grounded locali con citazione id.",
      sourceId: "architecture",
    };
  }

  return {
    reply: `Non ho trovato un record preciso per «${question.slice(0, 80)}». Nel corpus: ${events.length} eventi, ${(state.boards || []).length} canali, ${((state.calendar && state.calendar.items) || []).length} voci calendario. Prova con un titolo evento, una lezione (Business English / Programming / Calculus) o «consigliami».`,
    sourceId: "corpus-stats",
  };
}

let swipeBusy = false;

function decideCurrent(like) {
  const card = document.getElementById("swipe-card");
  const tag = card.dataset.tag;
  if (!tag || !state.session || swipeBusy) return;
  const mode = like === "skip" ? "skip" : (like ? "like" : "dislike");
  const commit = () => {
    state.session.likes = state.session.likes.filter((item) => item !== tag);
    state.session.dislikes = state.session.dislikes.filter((item) => item !== tag);
    state.session.skipped = (state.session.skipped || []).filter((item) => item !== tag);
    if (mode === "like") state.session.likes.push(tag);
    else if (mode === "dislike") state.session.dislikes.push(tag);
    else state.session.skipped.push(tag);
    saveSession(state.session);
    swipeBusy = false;
    renderSwipe();
    if (!pendingTags().length && state.session.likes.length) {
      window.setTimeout(() => enterDesk(), 220);
    }
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

function resetOnboarding() {
  localStorage.removeItem(SESSION_KEY);
  for (const key of SESSION_LEGACY_KEYS) localStorage.removeItem(key);
  state.session = null;
  state.deskUser = null;
  state.selectedId = null;
  state.matches = [];
  state.actions = [];
  state.notices = [];
  history.replaceState(null, "", location.pathname);
  showScreen("access");
}

function useDemoLikes() {
  if (!state.session) return;
  state.session.likes = DEMO_LIKES.filter((tag) => state.tags.includes(tag));
  state.session.dislikes = (state.session.dislikes || []).filter((tag) => !state.session.likes.includes(tag));
  state.session.skipped = (state.session.skipped || []).filter((tag) => !state.session.likes.includes(tag));
  saveSession(state.session);
  enterDesk();
}

async function enterDesk() {
  if (!state.session) return;
  state.deskUser = deskUserFromSession();
  state.selectedId = "usr-desk";
  showScreen("desk");
  paintExternalLinks();
  focusSection("bacheca");
  try {
    if ((state.session.likes || []).length) {
      await api("/desk/profile", { method: "POST", body: JSON.stringify(profileBody()) });
      await refreshStudent();
    } else {
      state.matches = [];
      state.actions = [];
      state.notices = [];
      state.busy = null;
      render();
    }
    await ensureCommunitySeed();
    focusSection("bacheca");
    showIgTab("feed");
    renderFilterPills();
    renderIgFeed();
    renderSceltoPerTe();
    updateAgendaBadge();
  } catch (error) {
    state.error = error.message || "Profilo non registrato.";
    state.busy = null;
    try { render(); } catch (_) {}
    focusSection("bacheca");
    renderFilterPills();
    renderIgFeed();
    renderSceltoPerTe();
  }
}

function signOut() {
  localStorage.removeItem(SESSION_KEY);
  for (const key of SESSION_LEGACY_KEYS) localStorage.removeItem(key);
  state.session = null;
  state.deskUser = null;
  state.selectedId = null;
  document.getElementById("you-panel").hidden = true;
  document.getElementById("roster").hidden = true;
  history.replaceState(null, "", location.pathname);
  showScreen("access");
}


function scrollBachecaTop() {
  const pane = document.getElementById("ig-feed-pane");
  const board = document.getElementById("bacheca");
  const stage = document.querySelector(".main-stage");
  if (pane) pane.scrollTop = 0;
  if (board) board.scrollTop = 0;
  if (stage) stage.scrollTop = 0;
  window.scrollTo(0, 0);
}

function focusSection(id) {
  const known = ["bacheca", "mappa", "calendario", "prenotazioni", "feedback", "chatta", "contatti", "shelf", "personalizzazioni", "home"];
  if (!known.includes(id)) id = "bacheca";
  state.deskPanel = id;
  for (const button of document.querySelectorAll(".rail button[data-action='section']")) {
    button.removeAttribute("aria-current");
  }
  const current = document.querySelector(`.rail button[data-id='${id}']`);
  if (current) current.setAttribute("aria-current", "true");
  const side = document.querySelector(".side");
  if (side) side.hidden = false;
  for (const panelId of known) {
    const node = document.getElementById(panelId);
    if (node) node.hidden = panelId !== id;
  }
  if (id === "bacheca") {
    showIgTab("feed");
    scrollBachecaTop();
  } else if (id === "mappa") {
    window.setTimeout(() => {
      ensureMap();
      renderPlan();
      if (campusMap) {
        campusMap.invalidateSize({ animate: false });
        campusMap.setView(CAMPUS_CENTER, 18, { animate: false });
      }
    }, 40);
  } else if (id === "personalizzazioni") {
    paintPrefsSummary();
  }
}

function paintExternalLinks() {
  const session = state.session || {};
  const canvas = document.getElementById("rail-canvas");
  const pronote = document.getElementById("rail-pronote");
  if (canvas) {
    const href = session.canvas_id || session.canvas_link || "";
    canvas.href = href || "#";
    canvas.title = href ? "Apri il tuo Canvas" : "Aggiungi il link Canvas in accesso";
    canvas.classList.toggle("is-empty", !href);
  }
  if (pronote) {
    const href = session.pronote_id || session.pronote_link || "";
    pronote.href = href || "#";
    pronote.title = href ? "Apri il tuo Pronote" : "Aggiungi il link Pronote in accesso";
    pronote.classList.toggle("is-empty", !href);
  }
}

function paintPrefsSummary() {
  const node = document.getElementById("prefs-summary");
  if (!node || !state.session) return;
  const likes = state.session.likes || [];
  const dislikes = state.session.dislikes || [];
  const skipped = state.session.skipped || [];
  node.textContent = likes.length
    ? `Interessa: ${likes.join(", ")}. No: ${dislikes.slice(0, 8).join(", ") || "—"}. Salta: ${skipped.length}.`
    : "Nessun interesse ancora: usa «Personalizza la tua bacheca».";
}

function openAiOverlay(show) {
  const overlay = document.getElementById("ai-overlay");
  if (!overlay) return;
  overlay.hidden = !show;
  if (show) {
    const thread = document.getElementById("assistant-thread");
    if (thread && !thread.dataset.seeded) {
      thread.dataset.seeded = "1";
      appendAssistantBubble(
        "assistant",
        "Ciao! Sono l'agente H-ELP (dataset locale). Posso consigliarti eventi dai tuoi tag, spiegare mappa/calendario e citare le fonti. Gemma 4 resta opzionale.",
      );
    }
    document.getElementById("assistant-input")?.focus();
  }
}

function paintDate() {
  const clock = document.getElementById("clock");
  if (!clock) return;
  const stamp = state.health?.demo_now ? new Date(state.health.demo_now) : new Date();
  clock.textContent = new Intl.DateTimeFormat("it-IT", {
    timeZone: "Europe/Rome",
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(stamp);
}

function paintYou() {
  const button = document.getElementById("you-btn") || document.getElementById("settings-btn");
  if (!button) return;
  const session = state.session;
  const name = displayName(session);
  button.setAttribute("aria-label", name || "Il tuo accesso");
  const youName = document.getElementById("you-name");
  const youEmail = document.getElementById("you-email");
  if (youName) youName.textContent = name;
  if (youEmail) youEmail.textContent = session ? session.email : "";
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


async function ensureCommunitySeed() {
  try {
    if (!state.boards.length) {
      const boards = await api("/community/boards");
      state.boards = boards.boards || [];
    }
    if (!state.calendar) {
      state.calendar = await api("/calendar");
    }
    await loadBoardPosts();
    renderHome();
    renderCalendar();
  } catch (error) {
    console.warn(error);
  }
}

async function loadBoardPosts() {
  const ids = ["board-generale", "board-eventi", "board-annunci"];
  const posts = [];
  for (const bid of ids) {
    try {
      const detail = await api(`/community/boards/${bid}`);
      const board = detail.board || detail;
      for (const msg of board.messages || []) {
        const src = classifyMessageSource(msg);
        if (!src) continue; // skip peer student chatter
        posts.push({
          kind: "message",
          id: msg.id,
          title: msg.author || src.label,
          text: msg.text || "",
          author: msg.author || "",
          org: msg.org || "",
          at: msg.at || "",
          source: src.id,
          sourceLabel: src.label,
        });
      }
    } catch (err) {
      console.warn("board", bid, err);
    }
  }
  // Deduplicate by id
  const seen = new Set();
  state.boardPosts = posts.filter((p) => {
    if (seen.has(p.id)) return false;
    seen.add(p.id);
    return true;
  });
}

function classifyMessageSource(msg) {
  const org = String(msg.org || "").toLowerCase();
  const author = String(msg.author || "").toLowerCase();
  const role = String(msg.role || "").toLowerCase();
  if (org.includes("student office") || author.includes("student office")) return SOURCE_BY_ID.office;
  if (org.includes("student life") || author.includes("student life")) return SOURCE_BY_ID.life;
  if (org.includes("faculty") || org.includes("docent") || /^prof\.?\s/.test(author) || author.startsWith("prof ")) return SOURCE_BY_ID.faculty;
  if (org.includes("club") || author.includes("club") || org === "age fund" || author.includes("age fund")) return SOURCE_BY_ID.club;
  if (role === "student") return null;
  if (role === "admin") return SOURCE_BY_ID.office;
  return null;
}

function classifyEventSource(ev) {
  const host = String(ev.host || ev.organizer || "").toLowerCase();
  const title = String(ev.title || "").toLowerCase();
  const tags = (ev.tags || []).map((t) => String(t).toLowerCase());
  const blurb = String(ev.blurb || ev.description || "").toLowerCase();
  const hay = `${host} ${title} ${tags.join(" ")} ${blurb}`;
  if (/student office|reception|badge|welcome week/.test(hay)) return SOURCE_BY_ID.office;
  if (/\bprof\b|docente|faculty|office hours|lezione|business english|calculus/.test(hay)) return SOURCE_BY_ID.faculty;
  if (/club|meetup studenti|jam|coding club|gaming|sfida a squadre|peer/.test(hay)) return SOURCE_BY_ID.club;
  if (/student life|community night|aperitivo|cinema|serata|workshop creativo|talk con ospiti/.test(hay)) return SOURCE_BY_ID.life;
  // Heuristic by title family from seed generator
  if (title.startsWith("meetup") || title.startsWith("sfida") || title.includes("collaborativo")) return SOURCE_BY_ID.club;
  if (title.startsWith("talk") || title.startsWith("sessione")) return SOURCE_BY_ID.faculty;
  if (title.startsWith("laboratorio") || title.startsWith("workshop") || title.startsWith("community")) return SOURCE_BY_ID.life;
  // Stable fallback by id hash → mostly Student Life + some Club
  let h = 0;
  const s = String(ev.id || title || "x");
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h % 5 === 0 ? SOURCE_BY_ID.club : SOURCE_BY_ID.life;
}

function wireChatForm() {
  /* student-to-student chat removed — bacheca only */
}

async function openBoard(boardId) {
  /* no-op: messaging boards hidden; keep id for seed data only */
  state.activeBoardId = boardId || state.activeBoardId;
}


const POSTER_PALETTES = [
  ["#1f5c45", "#163f30"],
  ["#2a6b52", "#1a4030"],
  ["#3d6b4f", "#1f3d30"],
  ["#4a7a5c", "#243f32"],
  ["#5f8a6a", "#2a4a38"],
  ["#6b9a78", "#315240"],
];

function posterStyle(key, title) {
  let h = 0;
  const s = String(key || title || "x");
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  const [a, b] = POSTER_PALETTES[h % POSTER_PALETTES.length];
  return `background-image:linear-gradient(160deg, ${a}, ${b})`;
}

function groupForTag(tag) {
  for (const g of INTEREST_GROUPS) {
    if (g.tags.includes(tag)) return g.label;
  }
  return null;
}

function eventGroups(event) {
  const labels = new Set();
  for (const tag of event.tags || []) {
    const g = groupForTag(tag);
    if (g) labels.add(g);
  }
  return [...labels];
}

function dateBadge(iso) {
  if (!iso) return { day: "—", mon: "" };
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { day: "—", mon: "" };
  const day = String(d.getDate());
  const mon = new Intl.DateTimeFormat("it-IT", { month: "short", timeZone: "Europe/Rome" }).format(d).replace(".", "").toUpperCase();
  return { day, mon };
}

function timeRange(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const start = new Intl.DateTimeFormat("it-IT", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" }).format(d);
  const endD = new Date(d.getTime() + 60 * 60 * 1000);
  const end = new Intl.DateTimeFormat("it-IT", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" }).format(endD);
  return `${start} – ${end}`;
}


function isEventCancelled(ev) {
  if (!ev) return false;
  if (ev.status === "cancelled" || ev.cancelled === true) return true;
  const t = String(ev.title || "").toLowerCase();
  return /\bannullat/.test(t) || t.includes("green challenge");
}

function isEventPast(ev) {
  const iso = ev && (ev.ends_at || ev.starts_at);
  if (!iso) return false;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return false;
  const now = state.health?.demo_now ? new Date(state.health.demo_now) : new Date();
  return d.getTime() < now.getTime();
}

function matchReasonFor(ev) {
  const likes = new Set(state.session?.likes || []);
  if (!likes.size) return "";
  const hit = [];
  for (const g of INTEREST_GROUPS) {
    if (g.tags.some((t) => likes.has(t)) && eventGroups(ev).includes(g.label)) hit.push(g.label);
  }
  if (!hit.length) return "";
  if (hit.length === 1) return `Perché ti interessa ${hit[0]}.`;
  return `Perché ti interessa ${hit.slice(0, -1).join(", ")} e ${hit[hit.length - 1]}.`;
}

function renderSceltoPerTe() {
  const root = document.getElementById("scelto-per-te");
  const banner = document.getElementById("interest-banner");
  if (!root) return;
  const likes = state.session?.likes || [];
  if (!likes.length) {
    root.hidden = true;
    root.replaceChildren();
    if (banner) banner.hidden = false;
    return;
  }
  if (banner) banner.hidden = true;
  const ranked = (state.matches || []).map((m) => state.events.find((e) => e.id === m.event_id)).filter(Boolean);
  let pick = ranked.find((ev) => matchReasonFor(ev)) || null;
  if (!pick) {
    pick = (state.events || []).find((ev) => matchReasonFor(ev) && !isEventCancelled(ev) && !isEventPast(ev)) || null;
  }
  if (!pick) {
    root.hidden = true;
    root.replaceChildren();
    return;
  }
  root.hidden = false;
  root.replaceChildren(
    el("div", { class: "scelto-mark", text: "✦" }),
    el("div", {}, [
      el("p", { class: "eyebrow", text: "Scelto per te" }),
      el("strong", { text: pick.title }),
      el("p", { class: "reason", text: matchReasonFor(pick) }),
    ]),
    el("button", {
      type: "button",
      class: "text-link",
      text: "Dai un'occhiata ↗",
      "data-action": "scopri",
      "data-id": pick.id,
    }),
  );
}

function formatWhen(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return new Intl.DateTimeFormat("it-IT", {
    timeZone: "Europe/Rome",
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

function openEventDetail(eventId) {
  const ev = (state.events || []).find((e) => e.id === eventId);
  const dlg = document.getElementById("event-modal");
  const body = document.getElementById("event-modal-body");
  if (!ev || !dlg || !body) {
    if (eventId) openSource(eventId);
    return;
  }
  const cancelled = isEventCancelled(ev);
  const enrolled = state.enrolledIds?.has(ev.id);
  const place = ev.location_name || ev.building || (ev.location && (ev.location.name || ev.location.building)) || "Campus";
  const seatsLeft = (ev.capacity != null && ev.going != null)
    ? Math.max(0, ev.capacity - ev.going)
    : (ev.capacity != null ? ev.capacity : null);
  const groups = eventGroups(ev);
  const sourceIds = [ev.id, ev.source_id].filter(Boolean);
  const kids = [
    el("p", { class: "eyebrow", text: `${ev.host || "Student Life"} · EVENTO` }),
    el("h2", { id: "event-modal-title", text: ev.title }),
    el("p", { class: "lede", text: ev.description || ev.blurb || "Evento del campus." }),
  ];
  if (groups.length) {
    const tags = el("div", { class: "event-tags" });
    for (const g of groups.slice(0, 4)) tags.append(el("span", { text: g }));
    kids.push(tags);
  }
  kids.push(el("div", { class: "event-modal-meta" }, [
    el("div", {}, [el("span", { class: "k", text: "Quando" }), el("span", { text: `${formatWhen(ev.starts_at)}${ev.ends_at ? " – " + timeRange(ev.starts_at).split("–")[1] : ""}` })]),
    el("div", {}, [el("span", { class: "k", text: "Dove" }), el("span", { text: place })]),
    el("div", {}, [el("span", { class: "k", text: "Organizzatore" }), el("span", { text: ev.host || "Student Life" })]),
    el("div", {}, [el("span", { class: "k", text: "Disponibilità" }), el("span", { text: cancelled ? "Annullato" : (seatsLeft != null ? `${seatsLeft} posti disponibili` : "Aperto") })]),
  ]));
  const actions = el("div", { class: "event-modal-actions" });
  if (cancelled) {
    actions.append(el("button", { type: "button", class: "solid forest", disabled: "disabled", text: "Evento annullato" }));
  } else if (enrolled) {
    actions.append(el("button", {
      type: "button", class: "solid forest", text: "Annulla iscrizione",
      "data-action": "event-unroll", "data-id": ev.id,
    }));
  } else {
    actions.append(el("button", {
      type: "button", class: "solid forest", text: "Iscriviti all'evento",
      "data-action": "event-enroll", "data-id": ev.id,
    }));
  }
  actions.append(el("button", {
    type: "button", class: "ghost assist", text: "Chiedi all'assistente ✦",
    "data-action": "event-ask", "data-id": ev.id,
  }));
  kids.push(actions);
  const sources = el("div", { class: "event-sources" }, [
    el("p", { class: "eyebrow", text: "Documenti e fonti" }),
    el("div", { class: "src-row" }, sourceIds.map((sid) => el("button", {
      type: "button",
      text: sid,
      "data-action": "source",
      "data-id": sid,
      title: sid,
    }))),
  ]);
  kids.push(sources);
  kids.push(el("p", { class: "micro", text: "Iscrizione simulata. Compare in agenda solo dopo Approva (happy path)." }));
  body.replaceChildren(...kids);
  body.className = "event-modal-body";
  try {
    if (typeof dlg.showModal === "function") { if (!dlg.open) dlg.showModal(); }
    else dlg.setAttribute("open", "");
  } catch (_) { dlg.setAttribute("open", ""); }
}

function closeEventModal() {
  const dlg = document.getElementById("event-modal");
  if (!dlg) return;
  try { if (dlg.open) dlg.close(); else dlg.removeAttribute("open"); } catch (_) { dlg.removeAttribute("open"); }
}

function showHosToast(text) {
  let t = document.getElementById("hos-toast");
  if (!t) {
    t = document.createElement("div");
    t.id = "hos-toast";
    t.className = "toast-hos";
    document.body.appendChild(t);
  }
  t.hidden = false;
  t.textContent = text;
  clearTimeout(showHosToast._timer);
  showHosToast._timer = setTimeout(() => { t.hidden = true; }, 2800);
}

async function enrollEvent(eventId) {
  if (!state.enrolledIds) state.enrolledIds = new Set();
  state.enrolledIds.add(eventId);
  closeEventModal();
  showHosToast("Iscrizione simulata — conferma con Approva nella bacheca");
  updateAgendaBadge();
  try { await tickAgent(); } catch (_) {}
}

function unrollEvent(eventId) {
  state.enrolledIds?.delete(eventId);
  closeEventModal();
  showHosToast("Iscrizione simulata annullata");
  updateAgendaBadge();
  renderIgFeed();
}

function askAboutEvent(eventId) {
  const ev = (state.events || []).find((e) => e.id === eventId);
  closeEventModal();
  openAiOverlay(true);
  const input = document.getElementById("assistant-input");
  if (input && ev) {
    input.value = `Dimmi di più su «${ev.title}» (${ev.id})`;
    document.getElementById("assistant-form")?.requestSubmit();
  }
}

function updateAgendaBadge() {
  const badge = document.getElementById("agenda-badge");
  if (!badge) return;
  const n = (state.enrolledIds && state.enrolledIds.size) || 0;
  const pending = (state.actions || []).filter((a) => a.status === "pending").length;
  badge.textContent = String(n + pending);
}


function renderFilterPills() {
  const root = document.getElementById("filter-pills");
  if (!root) return;
  root.replaceChildren();
  const labels = ["Tutti", ...SOURCE_TYPES.map((s) => s.label)];
  const active = state.sourceFilter || state.boardFilter || "Tutti";
  for (const label of labels) {
    root.append(el("button", {
      type: "button",
      class: `filter-pill${label === active ? " active" : ""}`,
      "data-action": "filter-pill",
      "data-id": label,
      text: label,
    }));
  }
}

function filteredEvents() {
  const q = (state.boardSearch || "").trim().toLowerCase();
  let list = (state.events || []).slice();
  const matchIds = new Set((state.matches || []).map((m) => m.event_id));
  list.sort((a, b) => {
    const am = matchIds.has(a.id) ? 0 : 1;
    const bm = matchIds.has(b.id) ? 0 : 1;
    if (am !== bm) return am - bm;
    return String(a.starts_at || "").localeCompare(String(b.starts_at || ""));
  });
  const status = state.boardStatus || "programmati";
  if (status === "conclusi") list = list.filter((ev) => isEventPast(ev) || isEventCancelled(ev));
  else list = list.filter((ev) => !isEventPast(ev));
  const srcFilter = state.sourceFilter || state.boardFilter || "Tutti";
  if (srcFilter && srcFilter !== "Tutti") {
    list = list.filter((ev) => classifyEventSource(ev).label === srcFilter);
  }
  if (q) {
    list = list.filter((ev) => {
      const hay = `${ev.title || ""} ${(ev.tags || []).join(" ")} ${ev.location_name || ""} ${ev.host || ""} ${ev.building || ""}`.toLowerCase();
      return hay.includes(q);
    });
  }
  return list;
}

function filteredBoardPosts() {
  const q = (state.boardSearch || "").trim().toLowerCase();
  const srcFilter = state.sourceFilter || state.boardFilter || "Tutti";
  const status = state.boardStatus || "programmati";
  let list = (state.boardPosts || []).slice();
  if (status === "conclusi") {
    // messages stay in archive view too
  }
  if (srcFilter && srcFilter !== "Tutti") {
    list = list.filter((p) => p.sourceLabel === srcFilter);
  }
  if (q) {
    list = list.filter((p) => {
      const hay = `${p.title || ""} ${p.text || ""} ${p.author || ""} ${p.org || ""} ${p.sourceLabel || ""}`.toLowerCase();
      return hay.includes(q);
    });
  }
  list.sort((a, b) => String(b.at || "").localeCompare(String(a.at || "")));
  return list;
}

function initialsFrom(name) {
  const parts = String(name || "?").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function buildIgCard({ id, src, author, caption, meta, visualStyle, visualChild, actions, extraClass }) {
  const attrs = { class: `ig-card ${src.css}${extraClass ? ` ${extraClass}` : ""}` };
  if (id) attrs.id = id;
  const card = el("article", attrs);
  const head = el("div", { class: "ig-card-head" }, [
    el("div", { class: `ig-avatar ${src.css}`, text: initialsFrom(author || src.label) }),
    el("div", { class: "ig-who" }, [
      el("span", { class: `ig-role ${src.css}`, text: src.label }),
      el("span", { class: "ig-nick", text: author || src.label }),
    ]),
  ]);
  const poster = el("div", { class: "ig-poster" });
  if (visualStyle) poster.setAttribute("style", visualStyle);
  if (visualChild) poster.append(visualChild);
  else poster.append(el("p", { class: "ig-poster-title", text: (caption || "").slice(0, 72) }));
  const cap = el("p", { class: "ig-caption" });
  cap.append(el("strong", { text: author || src.label }), document.createTextNode(" " + (caption || "")));
  const body = el("div", { class: "ig-body" }, [
    cap,
    el("p", { class: "ig-meta", text: meta || "" }),
  ]);
  const acts = el("div", { class: "ig-actions" });
  for (const a of actions || []) acts.append(a);
  card.append(head, poster, body, acts);
  return card;
}

function renderIgFeed() {
  const root = document.getElementById("ig-feed");
  if (!root) return;
  root.replaceChildren();
  root.className = "ig-feed";
  const posts = filteredBoardPosts();
  const events = filteredEvents();
  const count = document.getElementById("event-count");
  if (count) count.textContent = `${posts.length + events.length} avvisi`;

  for (const notice of (state.notices || []).slice(0, 2)) {
    const src = SOURCE_BY_ID.office;
    root.append(buildIgCard({
      id: `notice-${notice.id || notice.event_title || "n"}`,
      src,
      author: "Bacheca campus",
      caption: notice.event_title || "Avviso",
      meta: notice.text || "",
      visualStyle: "background:linear-gradient(135deg,#0b3d91,#6b8fd6)",
      actions: [
        el("button", { type: "button", text: "Chatta ↗", "data-action": "section", "data-id": "chatta" }),
      ],
      extraClass: "is-message",
    }));
  }

  for (const post of posts.slice(0, 20)) {
    const src = SOURCE_BY_ID[post.source] || SOURCE_BY_ID.office;
    const author = post.author || post.org || src.label;
    const whenTxt = post.at
      ? new Intl.DateTimeFormat("it-IT", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" }).format(new Date(post.at))
      : "";
    root.append(buildIgCard({
      id: `post-${post.id}`,
      src,
      author,
      caption: post.text || "",
      meta: [whenTxt, post.org].filter(Boolean).join(" · "),
      visualStyle: posterStyle(post.id || author, post.text || src.label),
      actions: [
        el("button", { type: "button", text: "Rispondi ↗", "data-action": "section", "data-id": "chatta" }),
      ],
      extraClass: "is-message",
    }));
  }

  if (!posts.length && !events.length && !(state.notices || []).length) {
    root.append(el("p", { class: "meta", text: "Nessun avviso per questo filtro. Apri Filtri sotto il feed o personalizza la bacheca." }));
    renderSceltoPerTe();
    updateAgendaBadge();
    return;
  }

  for (const ev of events.slice(0, 18)) {
    const src = classifyEventSource(ev);
    const badge = dateBadge(ev.starts_at);
    const place = ev.location_name || ev.building || (ev.location && (ev.location.name || ev.location.building)) || "Campus";
    const mapPlace = findPlaceByName(place);
    const metaBits = [timeRange(ev.starts_at), place].filter(Boolean).join(" · ");
    const author = ev.host || src.label;
    const cancelled = isEventCancelled(ev);
    const seatsLeft = (ev.capacity != null && ev.going != null)
      ? Math.max(0, ev.capacity - ev.going)
      : (ev.capacity != null ? ev.capacity : null);
    const dateNode = el("div", { class: "ig-date-badge" }, [
      el("strong", { text: badge.day }),
      el("span", { text: badge.mon }),
    ]);
    const titleOverlay = el("p", { class: "ig-poster-title", text: ev.title });
    const posterInner = el("div", { class: "ig-poster-inner" });
    posterInner.append(dateNode, titleOverlay);
    const actions = [
      el("button", {
        type: "button",
        text: "Scopri ↗",
        "data-action": "scopri",
        "data-id": ev.id,
      }),
    ];
    if (mapPlace) {
      actions.unshift(el("button", {
        type: "button",
        text: "Mappa",
        title: place,
        "data-action": "open-map",
        "data-id": mapPlace.id,
      }));
    }
    actions.push(el("span", {
      class: "ig-seats",
      text: cancelled ? "Annullato" : (seatsLeft != null ? `${seatsLeft} posti` : "Aperto"),
    }));
    root.append(buildIgCard({
      id: `feed-${ev.id}`,
      src,
      author,
      caption: ev.title,
      meta: metaBits,
      visualStyle: posterStyle(ev.id, ev.title),
      visualChild: posterInner,
      actions,
      extraClass: cancelled ? "cancelled" : "",
    }));
  }
  renderSceltoPerTe();
  updateAgendaBadge();
}


function openPersonalizeModal(show) {
  const dlg = document.getElementById("personalize-modal");
  if (!dlg) {
    if (show) showScreen("prefs");
    return;
  }
  if (show) {
    state.interestDraft = new Set();
    const likes = new Set(state.session?.likes || []);
    for (const g of INTEREST_GROUPS) {
      if (g.tags.some((t) => likes.has(t))) state.interestDraft.add(g.id);
    }
    try { renderInterestGrid(); } catch (e) { console.warn(e); }
    try {
      if (typeof dlg.showModal === "function") {
        if (!dlg.open) dlg.showModal();
      } else {
        dlg.setAttribute("open", "");
      }
    } catch (e) {
      console.warn("showModal failed", e);
      dlg.setAttribute("open", "");
      showScreen("prefs");
    }
  } else {
    try {
      if (typeof dlg.close === "function" && dlg.open) dlg.close();
      else dlg.removeAttribute("open");
    } catch (_) {
      dlg.removeAttribute("open");
    }
  }
}

function renderInterestGrid() {
  const grid = document.getElementById("interest-grid");
  if (!grid) return;
  grid.replaceChildren();
  for (const g of INTEREST_GROUPS) {
    const on = state.interestDraft.has(g.id);
    grid.append(el("button", {
      type: "button",
      class: `interest-tile${on ? " on" : ""}`,
      "data-action": "toggle-interest",
      "data-id": g.id,
    }, [
      el("span", { class: "ico", text: g.icon }),
      el("strong", { text: g.label }),
      el("span", { text: on ? "Selezionato" : "Tocca per scegliere" }),
    ]));
  }
}

function toggleInterestDraft(id) {
  if (state.interestDraft.has(id)) state.interestDraft.delete(id);
  else state.interestDraft.add(id);
  renderInterestGrid();
}

async function applyInterestDraft(requireSome) {
  if (!state.session) return;
  if (requireSome && !state.interestDraft.size) {
    state.error = "Scegli almeno un interesse, oppure esplora senza preferenze.";
    const err = document.getElementById("error");
    if (err) { err.hidden = false; err.textContent = state.error; }
    return;
  }
  const likes = [];
  for (const g of INTEREST_GROUPS) {
    if (state.interestDraft.has(g.id)) {
      for (const t of g.tags) {
        if (state.tags.includes(t) && !likes.includes(t)) likes.push(t);
      }
    }
  }
  state.session.likes = likes;
  state.session.dislikes = (state.session.dislikes || []).filter((t) => !likes.includes(t));
  saveSession(state.session);
  openPersonalizeModal(false);
  await enterDesk();
}

function wirePersonalize() {
  if (wirePersonalize._done) return;
  wirePersonalize._done = true;
  document.getElementById("find-community-btn")?.addEventListener("click", (event) => {
    event.preventDefault();
    applyInterestDraft(true);
  });
  document.getElementById("explore-no-prefs-btn")?.addEventListener("click", async (event) => {
    event.preventDefault();
    if (state.session) {
      state.session.likes = state.session.likes || [];
      saveSession(state.session);
    }
    openPersonalizeModal(false);
    if (state.session) {
      try { await enterDesk(); } catch (_) { showScreen("desk"); focusSection("bacheca"); }
    }
  });
  document.getElementById("bacheca-search")?.addEventListener("input", (event) => {
    state.boardSearch = event.target.value || "";
    renderIgFeed();
  });
  document.getElementById("board-status")?.addEventListener("change", (event) => {
    state.boardStatus = event.target.value || "programmati";
    renderIgFeed();
  });
  const dlg = document.getElementById("personalize-modal");
  dlg?.addEventListener("click", (event) => {
    if (event.target === dlg) openPersonalizeModal(false);
  });
}

function renderBoardList() {
  /* student chat channel list removed */
}

function renderChatThread() {
  /* student chat thread removed */
}

const calUi = {
  mode: "month",
  cursor: null,
  selected: null,
};

function calItemsByDate() {
  const map = new Map();
  for (const item of state.calendar?.items || []) {
    if (!item.date) continue;
    if (!map.has(item.date)) map.set(item.date, []);
    map.get(item.date).push(item);
  }
  return map;
}

function ymd(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function startOfWeekMonday(d) {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const day = (x.getDay() + 6) % 7;
  x.setDate(x.getDate() - day);
  return x;
}

function renderCalendar() {
  const grid = document.getElementById("cal-grid");
  const list = document.getElementById("calendar-list");
  const label = document.getElementById("cal-month-label");
  const heading = document.getElementById("cal-day-heading");
  if (!grid || !list) return;

  if (!calUi.cursor) {
    const demo = state.calendar?.demo_now ? new Date(state.calendar.demo_now) : new Date();
    calUi.cursor = new Date(demo.getFullYear(), demo.getMonth(), 1);
    calUi.selected = ymd(demo);
  }

  const byDay = calItemsByDate();
  const monthFmt = new Intl.DateTimeFormat("it-IT", { month: "long", year: "numeric" });
  if (label) {
    label.textContent = calUi.mode === "week"
      ? ("Settimana · " + monthFmt.format(calUi.cursor))
      : monthFmt.format(calUi.cursor).replace(/^./, (c) => c.toUpperCase());
  }

  document.querySelectorAll(".cal-mode").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.calMode === calUi.mode);
  });

  grid.replaceChildren();
  let cells = [];
  if (calUi.mode === "week") {
    const start = startOfWeekMonday(new Date(calUi.selected + "T12:00:00"));
    for (let i = 0; i < 7; i++) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      cells.push({ date: d, muted: false });
    }
  } else {
    const year = calUi.cursor.getFullYear();
    const month = calUi.cursor.getMonth();
    const first = new Date(year, month, 1);
    const startPad = (first.getDay() + 6) % 7;
    const start = new Date(year, month, 1 - startPad);
    for (let i = 0; i < 42; i++) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      cells.push({ date: d, muted: d.getMonth() !== month });
    }
  }

  const today = ymd(state.calendar?.demo_now ? new Date(state.calendar.demo_now) : new Date());
  for (const cell of cells) {
    const key = ymd(cell.date);
    const rows = byDay.get(key) || [];
    const dots = el("span", { class: "cal-dots" }, rows.slice(0, 3).map((r) => el("span", { class: "dot" + (r.kind === "evento" ? " evento" : "") })));
    const btn = el("button", {
      type: "button",
      class: "cal-cell" + (cell.muted ? " muted" : "") + (key === today ? " today" : "") + (key === calUi.selected ? " selected" : ""),
      "data-cal-day": key,
      "aria-label": key,
    }, [
      el("span", { text: String(cell.date.getDate()) }),
      dots,
    ]);
    btn.addEventListener("click", () => {
      calUi.selected = key;
      if (calUi.mode === "month") calUi.cursor = new Date(cell.date.getFullYear(), cell.date.getMonth(), 1);
      renderCalendar();
    });
    grid.append(btn);
  }

  list.replaceChildren();
  const dayRows = (byDay.get(calUi.selected) || []).slice().sort((a, b) => String(a.start).localeCompare(String(b.start)));
  const dayFmt = new Intl.DateTimeFormat("it-IT", { weekday: "long", day: "numeric", month: "long", timeZone: "Europe/Rome" });
  if (heading) {
    heading.textContent = dayFmt.format(new Date(calUi.selected + "T12:00:00+02:00"));
  }
  if (!dayRows.length) {
    list.append(el("p", { class: "meta", text: "Nessuna lezione o evento in questo giorno." }));
  } else {
    for (const row of dayRows) {
      list.append(el("article", { class: "cal-item kind-" + row.kind + (row.past ? " past" : "") }, [
        el("p", { class: "cal-when", text: row.start + "\u2013" + row.end }),
        el("h4", { text: row.title }),
        el("p", { class: "meta", text: (row.kind === "lezione" ? "Lezione" : "Evento") + " · " + (row.location || "Campus") + " · " + (row.series_id || row.id || "") }),
        row.blurb ? el("p", { text: row.blurb }) : null,
      ]));
    }
  }

  const shell = document.getElementById("iphone-cal");
  if (shell && !shell.dataset.wired) {
    shell.dataset.wired = "1";
    document.getElementById("cal-prev")?.addEventListener("click", () => {
      if (calUi.mode === "week") {
        const d = new Date(calUi.selected + "T12:00:00");
        d.setDate(d.getDate() - 7);
        calUi.selected = ymd(d);
        calUi.cursor = new Date(d.getFullYear(), d.getMonth(), 1);
      } else {
        calUi.cursor = new Date(calUi.cursor.getFullYear(), calUi.cursor.getMonth() - 1, 1);
      }
      renderCalendar();
    });
    document.getElementById("cal-next")?.addEventListener("click", () => {
      if (calUi.mode === "week") {
        const d = new Date(calUi.selected + "T12:00:00");
        d.setDate(d.getDate() + 7);
        calUi.selected = ymd(d);
        calUi.cursor = new Date(d.getFullYear(), d.getMonth(), 1);
      } else {
        calUi.cursor = new Date(calUi.cursor.getFullYear(), calUi.cursor.getMonth() + 1, 1);
      }
      renderCalendar();
    });
    document.querySelectorAll(".cal-mode").forEach((btn) => {
      btn.addEventListener("click", () => {
        calUi.mode = btn.dataset.calMode || "month";
        renderCalendar();
      });
    });
  }
}


function renderHome() {
  const lessonsRoot = document.getElementById("home-lessons");
  const eventsRoot = document.getElementById("home-events");
  const boardsRoot = document.getElementById("home-boards");
  const recRoot = document.getElementById("home-recs");
  if (!lessonsRoot || !eventsRoot || !boardsRoot) return;
  const upcomingLessons = (state.calendar?.lessons || []).filter((row) => !row.past).slice(0, 4);
  const upcomingEvents = (state.calendar?.events || []).filter((row) => !row.past).slice(0, 3);
  lessonsRoot.replaceChildren();
  if (!upcomingLessons.length) {
    lessonsRoot.append(el("p", { class: "meta", text: "Nessuna lezione in agenda." }));
  } else {
    for (const row of upcomingLessons) {
      lessonsRoot.append(el("div", { class: "home-row" }, [
        el("strong", { text: row.title }),
        el("span", { class: "meta", text: `${row.weekday || row.date} · ${row.start}–${row.end}` }),
        el("span", { class: "meta", text: row.location || "" }),
      ]));
    }
  }
  eventsRoot.replaceChildren();
  if (!upcomingEvents.length) {
    eventsRoot.append(el("p", { class: "meta", text: "Nessun evento serale." }));
  } else {
    for (const row of upcomingEvents) {
      eventsRoot.append(el("div", { class: "home-row" }, [
        el("strong", { text: row.title }),
        el("span", { class: "meta", text: `${row.date} · ${row.start}` }),
        el("span", { class: "meta", text: row.location || "" }),
      ]));
    }
  }
  boardsRoot.replaceChildren();
  const highlight = (state.events || []).filter((ev) => !ev.past).slice(0, 4);
  if (!highlight.length) {
    boardsRoot.append(el("p", { class: "meta", text: "Nessun evento in evidenza. Apri la bacheca per esplorare." }));
  } else {
    for (const ev of highlight) {
      boardsRoot.append(el("button", {
        class: "home-row linkish",
        type: "button",
        "data-action": "section",
        "data-id": "bacheca",
      }, [
        el("strong", { text: ev.title || "Evento" }),
        el("span", { class: "meta", text: [ev.when || ev.date, ev.place || ev.location].filter(Boolean).join(" · ") }),
      ]));
    }
  }
  if (recRoot) {
    recRoot.replaceChildren();
    const likes = state.session?.likes || [];
    if (!state.matches.length) {
      recRoot.append(el("p", { class: "meta", text: likes.length
        ? "Sto calcolando i match dalle tue preferenze…"
        : "Scegli almeno un interesse nelle preferenze per vedere i consigli." }));
    } else {
      for (const match of state.matches.slice(0, 4)) {
        const pct = Math.round((Number(match.score) || 0) * 100);
        recRoot.append(el("article", { class: "home-row rec-row" }, [
          el("strong", { text: match.title }),
          el("span", { class: "score-pill", text: `${pct}% match` }),
          el("span", { class: "meta", text: match.why || match.display_text || "" }),
          el("span", { class: "meta", text: `Fonte · ${match.event_id}` }),
        ]));
      }
    }
  }
}

function feedbackCatalog() {
  const items = state.calendar?.items || [];
  const seen = new Set();
  const out = [];
  for (const row of items) {
    const key = row.title + "|" + row.date;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ id: row.series_id || row.id, title: row.title, date: row.date, kind: row.kind });
  }
  return out.sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

function selectedFeedbackChips() {
  return [...document.querySelectorAll("#feedback-chips .fb-chip.selected")].map((n) => n.dataset.chip);
}

function buildFeedbackSubject() {
  const sel = document.getElementById("feedback-event");
  const opt = sel && sel.selectedOptions[0];
  const title = (opt && opt.dataset.title) || "Evento";
  const date = (opt && opt.dataset.date) || "";
  return "Feedback: " + title + " \u2014 " + date;
}

function buildFeedbackBody() {
  const chips = selectedFeedbackChips();
  const extra = ((document.getElementById("feedback-text") || {}).value || "").trim();
  const parts = [];
  if (chips.length) parts.push(chips.join(" · "));
  if (extra) parts.push(extra);
  return parts.join("\n\n") || "(nessun commento)";
}

function refreshFeedbackSubject() {
  const node = document.getElementById("feedback-subject");
  if (node) node.textContent = "Oggetto: " + buildFeedbackSubject();
}

function populateFeedbackEvents() {
  const sel = document.getElementById("feedback-event");
  if (!sel) return;
  const catalog = feedbackCatalog();
  const prev = sel.value;
  sel.replaceChildren();
  if (!catalog.length) {
    sel.append(el("option", { value: "", text: "Nessun evento in agenda" }));
    refreshFeedbackSubject();
    return;
  }
  for (const row of catalog) {
    const opt = el("option", { value: row.id + "::" + row.date, text: row.date + " · " + row.title });
    opt.dataset.title = row.title;
    opt.dataset.date = row.date;
    sel.append(opt);
  }
  if ([...sel.options].some((o) => o.value === prev)) sel.value = prev;
  refreshFeedbackSubject();
}

function wireFeedbackForm() {
  const form = document.getElementById("feedback-form");
  if (!form || form.dataset.wired) return;
  form.dataset.wired = "1";

  const chipsRoot = document.getElementById("feedback-chips");
  if (chipsRoot) {
    chipsRoot.replaceChildren();
    for (const label of FEEDBACK_CHIPS) {
      const chip = el("button", { type: "button", class: "fb-chip", "data-chip": label, text: label });
      chip.addEventListener("click", () => {
        chip.classList.toggle("selected");
        refreshFeedbackSubject();
      });
      chipsRoot.append(chip);
    }
  }

  populateFeedbackEvents();
  document.getElementById("feedback-event")?.addEventListener("change", refreshFeedbackSubject);
  document.getElementById("feedback-text")?.addEventListener("input", refreshFeedbackSubject);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const status = document.getElementById("feedback-status");
    const subject = buildFeedbackSubject();
    const body = buildFeedbackBody();
    if (body.length < 3) {
      if (status) status.textContent = "Seleziona almeno un commento o scrivi un dettaglio.";
      return;
    }
    window.location.href = "mailto:life@campus.demo?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(body);
    if (status) status.textContent = "Pronto: oggetto «" + subject + "».";
  });

  document.getElementById("feedback-mock")?.addEventListener("click", async () => {
    const status = document.getElementById("feedback-status");
    const subject = buildFeedbackSubject();
    const body = buildFeedbackBody();
    try {
      await fetch("/feedback", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ subject, body, synthetic: true }),
      });
    } catch (_) {}
    if (status) status.textContent = "Demo salvata · " + subject;
  });

  const overlay = document.getElementById("ai-overlay");
  if (overlay && !overlay.dataset.wired) {
    overlay.dataset.wired = "1";
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) openAiOverlay(false);
    });
  }
}

function findPlaceByName(name) {
  const n = String(name || "").toLowerCase().trim();
  if (!n) return null;
  return (state.places || []).find((p) => {
    const pn = String(p.name || "").toLowerCase();
    return pn && (pn === n || pn.includes(n) || n.includes(pn)) && p.id;
  }) || null;
}

function openMapAt(placeId) {
  focusSection("mappa");
  if (!placeId) return;
  window.setTimeout(() => {
    const place = (state.places || []).find((p) => p.id === placeId);
    if (!place || !campusMap) return;
    try { campusMap.setView(placeLatLng(place), 19, { animate: true }); } catch (e) {}
  }, 140);
}
// Close settings/account panel on outside click or Esc
(function () {
  const close = () => { const p = document.getElementById("you-panel"); if (p && !p.hidden) p.hidden = true; };
  document.addEventListener("pointerdown", (e) => {
    const p = document.getElementById("you-panel");
    if (!p || p.hidden) return;
    if (p.contains(e.target) || e.target.closest?.('[data-action="you"]')) return;
    close();
  }, true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
})();


function routeChattaRecipient(text) {
  const q = String(text || "").toLowerCase();
  let best = CHATTA_RECIPIENTS[1]; // Student Office default
  let score = 0;
  for (const rec of CHATTA_RECIPIENTS) {
    let s = 0;
    for (const k of rec.keys) {
      if (q.includes(k)) s += k.length;
    }
    if (s > score) { score = s; best = rec; }
  }
  return best;
}

function suggestChattaRecipient() {
  const intent = document.getElementById("chatta-intent");
  const text = (intent && intent.value) || "";
  const rec = routeChattaRecipient(text);
  const sel = document.getElementById("chatta-to");
  if (sel) {
    const val = `${rec.email}|${rec.name}`;
    let found = false;
    for (const opt of sel.options) {
      if (opt.value === val) { sel.value = val; found = true; break; }
    }
    if (!found) sel.value = val;
  }
  const hint = document.getElementById("chatta-dest-hint");
  if (hint) hint.textContent = `Destinatario suggerito: ${rec.name} · ${rec.email}`;
  const sub = document.getElementById("chatta-subject");
  if (sub && !sub.value.trim()) {
    const snippet = text.trim().slice(0, 60) || "Richiesta studente H-ELP";
    sub.value = `[H-ELP] ${snippet}`;
  }
  const body = document.getElementById("chatta-body");
  if (body && !body.value.trim() && text.trim()) {
    const nick = displayName(state.session) || "Studente";
    body.value = `Ciao ${rec.name},\n\n${text.trim()}\n\nGrazie,\n${nick}`;
  }
  showHosToast(`Destinatario: ${rec.name}`);
}

function wireChattaForm() {
  if (wireChattaForm._done) return;
  wireChattaForm._done = true;
  const form = document.getElementById("chatta-form");
  if (!form) return;
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const to = document.getElementById("chatta-to")?.value || "";
    const subject = (document.getElementById("chatta-subject")?.value || "").trim();
    const body = (document.getElementById("chatta-body")?.value || "").trim();
    const intent = (document.getElementById("chatta-intent")?.value || "").trim();
    if (!to) {
      suggestChattaRecipient();
    }
    const finalTo = document.getElementById("chatta-to")?.value || to;
    if (!finalTo || !subject || !body) {
      const st = document.getElementById("chatta-status");
      if (st) st.textContent = "Compila destinatario, oggetto e messaggio.";
      return;
    }
    const [email, name] = finalTo.split("|");
    const payload = {
      at: new Date().toISOString(),
      to: email,
      toName: name,
      subject,
      body,
      intent,
      from: state.session?.email || "studente@demo",
    };
    try {
      const key = "hos.chatta.outbox.v1";
      const box = JSON.parse(localStorage.getItem(key) || "[]");
      box.unshift(payload);
      localStorage.setItem(key, JSON.stringify(box.slice(0, 40)));
    } catch (_) { /* ignore */ }
    const st = document.getElementById("chatta-status");
    if (st) st.textContent = `Email demo inviata a ${name} <${email}>. Nessun invio reale.`;
    showHosToast(`Inviato (demo) a ${name}`);
  });
  document.getElementById("chatta-intent")?.addEventListener("blur", () => {
    const to = document.getElementById("chatta-to");
    if (to && !to.value) suggestChattaRecipient();
  });
}

function loadSurveyStore() {
  try { return JSON.parse(localStorage.getItem(SURVEY_KEY) || '{"responses":[],"totals":{}}'); }
  catch (_) { return { responses: [], totals: {} }; }
}

function saveSurveyStore(store) {
  try { localStorage.setItem(SURVEY_KEY, JSON.stringify(store)); } catch (_) {}
}

function formatSurveyWhen(iso) {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("it-IT", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Rome" }).format(new Date(iso));
  } catch (_) { return iso; }
}

function wireSurveyUI() {
  const interestRoot = document.getElementById("survey-interest-chips");
  const wantRoot = document.getElementById("survey-want-chips");
  const toRoot = document.getElementById("survey-to-chips");
  if (interestRoot && !interestRoot.dataset.ready) {
    interestRoot.dataset.ready = "1";
    for (const label of SURVEY_INTERESTS) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "survey-chip";
      btn.dataset.chip = label;
      btn.textContent = label;
      btn.addEventListener("click", () => btn.classList.toggle("selected"));
      interestRoot.appendChild(btn);
    }
  }
  if (wantRoot && !wantRoot.dataset.ready) {
    wantRoot.dataset.ready = "1";
    for (const label of SURVEY_WANTS) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "survey-chip";
      btn.dataset.chip = label;
      btn.textContent = label;
      btn.addEventListener("click", () => {
        wantRoot.querySelectorAll(".survey-chip").forEach((n) => n.classList.remove("selected"));
        btn.classList.add("selected");
      });
      wantRoot.appendChild(btn);
    }
  }
  if (toRoot && !toRoot.dataset.ready) {
    toRoot.dataset.ready = "1";
    for (const item of SURVEY_TO) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "survey-chip";
      btn.dataset.chip = item.id;
      btn.textContent = item.label;
      if (item.id === "both") btn.classList.add("selected");
      btn.addEventListener("click", () => {
        toRoot.querySelectorAll(".survey-chip").forEach((n) => n.classList.remove("selected"));
        btn.classList.add("selected");
      });
      toRoot.appendChild(btn);
    }
  }
  const dialog = document.getElementById("survey-dialog");
  dialog?.addEventListener("close", () => {
    const st = document.getElementById("survey-status");
    if (st) { st.hidden = true; st.textContent = ""; }
  });
  paintSurveyTopHint();
}

function paintSurveyTopHint() {
  const btn = document.getElementById("survey-top-btn");
  if (!btn) return;
  const store = loadSurveyStore();
  const last = (store.responses || []).slice(-1)[0];
  if (last?.at) {
    btn.title = "Ultimo sondaggio: " + formatSurveyWhen(last.at);
    btn.classList.add("has-done");
  } else {
    btn.title = "Sondaggio veloce · interessi per Life & Office";
    btn.classList.remove("has-done");
  }
}

function openSurveyDialog(show) {
  const dialog = document.getElementById("survey-dialog");
  if (!dialog) return;
  wireSurveyUI();
  if (show) {
    const st = document.getElementById("survey-status");
    const report = document.getElementById("survey-report");
    if (st) { st.hidden = true; st.textContent = ""; }
    if (report) report.hidden = true;
    if (!dialog.open) dialog.showModal();
  } else if (dialog.open) {
    dialog.close();
  }
}

function selectedSurveyChips(rootId) {
  return [...document.querySelectorAll("#" + rootId + " .survey-chip.selected")].map((n) => n.dataset.chip);
}

function submitInterestSurvey() {
  const interests = selectedSurveyChips("survey-interest-chips");
  const wants = selectedSurveyChips("survey-want-chips");
  const to = selectedSurveyChips("survey-to-chips")[0] || "both";
  const note = (document.getElementById("survey-note")?.value || "").trim();
  const st = document.getElementById("survey-status");
  if (!interests.length) {
    if (st) {
      st.hidden = false;
      st.textContent = "Scegli almeno un interesse — ci vuole un attimo.";
    }
    return;
  }
  if (!wants.length) {
    if (st) {
      st.hidden = false;
      st.textContent = "Dimmi cosa vorresti di più questa settimana.";
    }
    return;
  }
  const store = loadSurveyStore();
  if (!Array.isArray(store.responses)) store.responses = [];
  if (!store.totals || typeof store.totals !== "object") store.totals = {};
  const entry = {
    at: new Date().toISOString(),
    interests,
    want: wants[0],
    to,
    note,
  };
  store.responses.push(entry);
  if (store.responses.length > 40) store.responses = store.responses.slice(-40);
  for (const label of interests) {
    store.totals[label] = (store.totals[label] || 0) + 1;
  }
  store.totals["__want__:" + wants[0]] = (store.totals["__want__:" + wants[0]] || 0) + 1;
  store.totals["__to__:" + to] = (store.totals["__to__:" + to] || 0) + 1;
  store.last = entry;
  saveSurveyStore(store);
  paintSurveyTopHint();
  paintSurveyReport(store);
  if (st) {
    st.hidden = false;
    const dest = to === "office" ? "Student Office" : to === "life" ? "Student Life" : "Student Life e Student Office";
    st.textContent = "Grazie! I tuoi interessi aiutano " + dest + " a decidere cosa attivare. Salvato in locale (demo).";
  }
  showHosToast("Sondaggio inviato · report Life/Office aggiornato");
}

function paintSurveyReport(store) {
  const box = document.getElementById("survey-report");
  const bars = document.getElementById("survey-report-bars");
  if (!box || !bars) return;
  const totals = store.totals || {};
  const rows = SURVEY_INTERESTS
    .map((label) => ({ label, n: totals[label] || 0 }))
    .filter((r) => r.n > 0)
    .sort((a, b) => b.n - a.n);
  bars.replaceChildren();
  if (!rows.length) {
    box.hidden = true;
    return;
  }
  const max = Math.max(...rows.map((r) => r.n), 1);
  for (const row of rows.slice(0, 6)) {
    const line = document.createElement("div");
    line.className = "survey-bar-row";
    const name = document.createElement("span");
    name.className = "survey-bar-label";
    name.textContent = row.label;
    const track = document.createElement("div");
    track.className = "survey-bar-track";
    const fill = document.createElement("div");
    fill.className = "survey-bar-fill";
    fill.style.width = Math.round((row.n / max) * 100) + "%";
    track.appendChild(fill);
    const count = document.createElement("span");
    count.className = "survey-bar-count";
    count.textContent = String(row.n);
    line.append(name, track, count);
    bars.appendChild(line);
  }
  box.hidden = false;
}

/** Legacy no-op kept for any old survey-save hooks */
function saveSurvey(kind) {
  openSurveyDialog(true);
}

function wireSurveyStatus() {
  wireSurveyUI();
}

