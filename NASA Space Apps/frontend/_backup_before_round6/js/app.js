// APP — router, layout, global event handling.
(() => {
  const { esc, link } = U;
  const ROUTES = {
    "": PAGES.home, ask: PAGES.ask, explore: PAGES.explore, investigation: PAGES.investigation, compare: PAGES.compare,
    graph: PAGES.graph, gaps: PAGES.gaps, lab: PAGES.lab, model: PAGES.model, scenario: PAGES.scenario,
    learn: PAGES.learn, about: PAGES.about, dev: PAGES.dev, hardware: PAGES.hardware
  };

  function parseHash() {
    const h = location.hash.replace(/^#\/?/, "");
    const [path, qs] = h.split("?");
    const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
    return { name: parts[0] || "", params: parts.slice(1), query: new URLSearchParams(qs || "") };
  }

  function renderHeader() {
    const st = S.get(), cfg = S.personaCfg(), cur = parseHash().name || "home";
    const nav = cfg.nav.map(r => {
      const href = r === "home" ? "#/" : "#/" + r;
      return r === cur ? `<b>${esc(ROUTE_LABELS[r])}</b>` : link(href, ROUTE_LABELS[r]);
    }).join("");
    const personaSel = `<select data-action-change="set-persona"><option value="">Choose persona…</option>${Object.entries(PERSONAS).map(([k, p]) =>
      `<option value="${k}" ${st.persona === k ? "selected" : ""}>${esc(p.label)}</option>`).join("")}</select>`;
    const scenSel = `<select data-action-change="set-scenario">${Object.entries(DATA.scenarios).map(([k, s]) =>
      `<option value="${k}" ${st.scenario === k ? "selected" : ""}>${esc(s.label)}</option>`).join("")}</select>`;
    document.getElementById("header").innerHTML = `
      <div>${link("#/", U.projectName())} — <span class="muted">NASA Space Apps 2026 · Flame in Freefall</span></div>
      <nav>${nav}${link("#/dev", "All pages")}</nav>
      <div>Persona ${personaSel} Scenario ${scenSel}
        <form data-form="ask" class="inline"><input name="q" placeholder="Ask anything…" size="30"><button>Ask</button></form></div>`;
  }

  function render() {
    const { name, params, query } = parseHash();
    const page = ROUTES[name] || PAGES.notFound;
    renderHeader();
    const root = document.getElementById("main");
    let out;
    try { out = page(params, query); }
    catch (e) { out = { html: `<h1>Page error</h1><pre>${esc(e.stack || e.message)}</pre>` }; console.error(e); }
    root.innerHTML = out.html;
    if (out.mount) out.mount(root);
  }

  // Global delegated events
  document.addEventListener("click", e => {
    const el = e.target.closest("[data-action]");
    if (!el) return;
    const a = el.dataset.action;
    if (a === "set-persona") S.set({ persona: el.dataset.value });
    if (a === "clear-conversation") { S.set({ conversation: [] }); location.hash = "#/ask"; }
    if (a === "reset-state") S.set({ persona: null, compare: [], conversation: [] });
    if (a === "toggle-compare") {
      const onExplore = parseHash().name === "explore";
      S.toggleCompare(el.dataset.id, onExplore);       // silent on Explore so filters aren't wiped
      const c = document.getElementById("compare-count"); if (c) c.textContent = S.get().compare.length;
    }
  });
  document.addEventListener("change", e => {
    const el = e.target.closest("[data-action-change]");
    if (!el) return;
    const a = el.dataset.actionChange;
    if (a === "set-persona") S.set({ persona: el.value || null });
    if (a === "set-scenario") S.set({ scenario: el.value });
    if (a === "add-compare" && el.value) {
      const { query } = parseHash();
      if (query.get("ids")) location.hash = "#/compare?ids=" + [...query.get("ids").split(","), el.value].slice(-4).join(",");
      else S.toggleCompare(el.value);
    }
  });
  document.addEventListener("submit", e => {
    const form = e.target.closest('[data-form="ask"]');
    if (!form) return;
    e.preventDefault();
    const q = (new FormData(form).get("q") || "").trim();
    if (!q) return;
    const target = "#/ask?q=" + encodeURIComponent(q);
    if (location.hash === target) PAGES.runAsk(q); else location.hash = target;
  });

  S.on(render);
  window.addEventListener("hashchange", render);
  render();
  API.health().then(() => { const el = document.getElementById("ai-status"); if (el) el.textContent = API.describe(); });
})();
