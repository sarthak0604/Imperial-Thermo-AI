// UI KIT — icons, theme, menus, the prompt bar's environment and persona pickers, data display settings,
// question history (Recent, pins, folders, threads), sidebar, share menu, toast.
// Written with SI assistance (Claude, Anthropic).
window.UI = (() => {
  const { esc } = U;
  const IC = {
    flame: '<path d="M12 3C9 7 6.5 9.6 6.5 14a5.5 5.5 0 0 0 11 0C17.5 9.6 15 7 12 3Z"/><path d="M12 11.5c-1.2 1.5-2 2.5-2 3.7a2 2 0 0 0 4 0c0-1.2-.8-2.2-2-3.7Z"/>',
    student: '<path d="M3 9.5l9-4.5 9 4.5-9 4.5-9-4.5Z"/><path d="M7 12v3.5c0 1.4 2.4 2.8 5 2.8s5-1.4 5-2.8V12"/><path d="M21 9.5v4.5"/>',
    professor: '<path d="M4 5.5c2.5-1 5.5-1 8 .5 2.5-1.5 5.5-1.5 8-.5V19c-2.5-1-5.5-1-8 .5-2.5-1.5-5.5-1.5-8-.5Z"/><path d="M12 6v13.5"/>',
    engineer: '<path d="M4.5 19.5l15-15v15Z"/><path d="M14.5 19.5v-2.5M17 19.5v-5"/><path d="M12.5 15.5h3v-3"/>',
    general: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c.6-3.6 3.4-6 7-6s6.4 2.4 7 6"/>',
    iss: '<rect x="9.5" y="9.5" width="5" height="5" rx="1"/><path d="M3 7.5h5v9H3zM16 7.5h5v9h-5zM8 12h1.5M14.5 12H16M12 6v3.5M12 14.5V18"/>',
    moon: '<path d="M19.5 14.5A7.8 7.8 0 1 1 9.5 4.5a6.2 6.2 0 0 0 10 10Z"/>',
    sun: '<circle cx="12" cy="12" r="3.8"/><path d="M12 2.8v2M12 19.2v2M2.8 12h2M19.2 12h2M5.5 5.5l1.4 1.4M17.1 17.1l1.4 1.4M5.5 18.5l1.4-1.4M17.1 6.9l1.4-1.4"/>',
    suit: '<circle cx="12" cy="9" r="5"/><path d="M9.5 8.5h5M6 21v-3a6 6 0 0 1 12 0v3"/>',
    earth: '<circle cx="12" cy="12" r="8.5"/><path d="M7 6.5c1.5 1 1.2 2.6 2.8 3.2 1.6.6 1.4 2.3.4 3.3-.9.9-.3 2.6.8 3.5M16.5 6.5c-.8 1.4.2 2.8 1.8 3"/>',
    env: '<circle cx="12" cy="12" r="8.5" stroke-dasharray="2.2 2.4"/><path d="M12 8.5v7M8.5 12h7"/>',
    beaker: '<path d="M9 3.5h6M10 3.5V9l-5 8.8A2 2 0 0 0 6.8 21h10.4a2 2 0 0 0 1.8-3.2L14 9V3.5"/><path d="M7.6 15h8.8"/>',
    search: '<circle cx="11" cy="11" r="6"/><path d="M19.5 19.5l-4-4"/>',
    copy: '<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M15.5 8.5V6.5a2 2 0 0 0-2-2h-7a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h2"/>',
    refresh: '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.5 4.5v4h-4"/>',
    plus: '<path d="M12 5v14M5 12h14"/>', arrow: '<path d="M12 19V5.5M6 11l6-6 6 6"/>',
    stop: '<rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" stroke="none"/>',
    chev: '<path d="M7 9.5l5 5 5-5"/>', check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>', x: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    side: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><path d="M9 4.5v15"/>',
    edit: '<path d="M12 20h7.5"/><path d="M16.3 4.7a2 2 0 0 1 3 3L8 19l-3.8 1 1-3.8Z"/>',
    share: '<path d="M12 4v11M8 8l4-4 4 4"/><path d="M5 13.5V18a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4.5"/>',
    link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    layers: '<path d="M12 4l8.5 4.5L12 13 3.5 8.5Z"/><path d="M3.5 12.5L12 17l8.5-4.5M3.5 16.5L12 21l8.5-4.5"/>',
    download: '<path d="M12 4v11M8 11l4 4 4-4"/><path d="M5 19.5h14"/>',
    expand: '<path d="M14 4.5h5.5V10M10 19.5H4.5V14M19.5 4.5l-6 6M4.5 19.5l6-6"/>',
    doc: '<path d="M7 3.5h7l4.5 4.5v12.5H7Z"/><path d="M14 3.5V8h4.5M9.5 12.5h6M9.5 16h6"/>',
    trash: '<path d="M5 7h14M10 7V4.5h4V7M7 7l1 12.5h8L17 7"/>',
    spark: '<path d="M12 3c.6 4.6 3.4 7.4 8 8-4.6.6-7.4 3.4-8 8-.6-4.6-3.4-7.4-8-8 4.6-.6 7.4-3.4 8-8Z"/>',
    folder: '<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.2h7a2 2 0 0 1 2 2v7.8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2Z"/>',
    folderPlus: '<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.2h7a2 2 0 0 1 2 2v7.8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2Z"/><path d="M12 11v5M9.5 13.5h5"/>',
    sliders: '<path d="M5 6.5h8M17 6.5h2M5 12h2M11 12h8M5 17.5h10"/><circle cx="15" cy="6.5" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="17.5" r="2"/>',
    pin: '<path d="M9 4.5h6l-1 5 3.5 3.5h-11L10 9.5Z"/><path d="M12 13v6.5"/>',
    more: '<circle cx="6" cy="12" r="1.2" fill="currentColor"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/><circle cx="18" cy="12" r="1.2" fill="currentColor"/>',
    grid: '<rect x="4" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5"/>',
    list: '<path d="M9 6.5h11M9 12h11M9 17.5h11"/><circle cx="5" cy="6.5" r="1.2"/><circle cx="5" cy="12" r="1.2"/><circle cx="5" cy="17.5" r="1.2"/>',
    table: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M3.5 14.5h17M9.5 9.5v10"/>',
    sort: '<path d="M8 5v14M4.5 15.5L8 19l3.5-3.5M16 19V5M12.5 8.5L16 5l3.5 3.5"/>',
    up: '<path d="M7 14.5l5-5 5 5"/>', down: '<path d="M7 9.5l5 5 5-5"/>',
    open: '<path d="M14 4.5h5.5V10M19.5 4.5l-8 8"/><path d="M18 14v4.5a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6H10"/>',
    move: '<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.2h7a2 2 0 0 1 2 2v7.8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2Z"/><path d="M10 13.5h5M13 11.5l2 2-2 2"/>',
    group: '<rect x="4" y="4" width="16" height="5" rx="1.5"/><path d="M4 13h16M4 17h11"/>'
  };
  const ic = (n, c) => `<svg class="ic${c ? " " + c : ""}" viewBox="0 0 24 24" aria-hidden="true">${IC[n] || ""}</svg>`;
  // the flame mark: a ring of light with a belt of dust (design 2), as a static icon
  const mark = () => `<svg viewBox="0 0 24 24" aria-hidden="true"><defs><radialGradient id="mk-g"><stop offset=".34" stop-color="var(--fblu)" stop-opacity="0"/><stop offset=".44" stop-color="var(--forg)" stop-opacity=".9"/><stop offset=".55" stop-color="#D6E2FF"/><stop offset=".72" stop-color="var(--fblu)" stop-opacity=".45"/><stop offset="1" stop-color="var(--fblu)" stop-opacity="0"/></radialGradient></defs>
    <circle cx="12" cy="12" r="9" fill="url(#mk-g)"/><ellipse cx="12" cy="12" rx="10.5" ry="3" fill="none" stroke="currentColor" stroke-opacity=".55" stroke-width="1" stroke-dasharray=".6 2.2" stroke-linecap="round" transform="rotate(-14 12 12)"/></svg>`;

  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; } },
    set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) {} },
    json(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch (e) { return d; } },
    setJson(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  };
  const emitter = () => { const fs = []; return { on: f => fs.push(f), emit: (...a) => fs.forEach(f => f(...a)) }; };

  // ---------- theme ----------
  const theme = () => document.documentElement.dataset.theme === "light" ? "light" : "dark";
  const themeE = emitter();
  function setTheme(m) {
    document.documentElement.dataset.theme = m; store.set("fif-theme", m);
    const b = document.getElementById("mode"); b.setAttribute("aria-checked", String(m === "dark"));
    themeE.emit(m);
  }
  function initTheme() {
    const b = document.getElementById("mode");
    b.innerHTML = `<span class="mk">${ic("sun")}${ic("moon")}</span>`;
    b.setAttribute("aria-checked", String(theme() === "dark"));
    b.addEventListener("click", () => setTheme(theme() === "dark" ? "light" : "dark"));
  }

  // ---------- toast ----------
  let tt;
  function toast(msg) { const t = document.getElementById("toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(tt); tt = setTimeout(() => t.classList.remove("show"), 2200); }
  async function copy(text) {
    try { await navigator.clipboard.writeText(text); return true; }
    catch (e) {
      const ta = document.createElement("textarea"); ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0"; document.body.appendChild(ta); ta.select();
      let ok = false; try { ok = document.execCommand("copy"); } catch (_) {} ta.remove(); return ok;
    }
  }

  // ---------- menus: any .dd / .pop with a [aria-expanded] button and a .menu ----------
  // Menus inside the prompt bar are placed against the whole bar (above or below it), so they never cover the typing area.
  function closeMenus(except) {
    document.querySelectorAll(".dd.open, .pop.open").forEach(d => { if (d === except) return; d.classList.remove("open"); const b = d.querySelector("[aria-expanded]"); if (b) b.setAttribute("aria-expanded", "false"); });
  }
  function openMenu(d) {
    closeMenus(d);
    d.classList.remove("up"); d.classList.add("open"); d.querySelector("[aria-expanded]").setAttribute("aria-expanded", "true");
    const a = d.closest(".pb") || d, r = a.getBoundingClientRect(), m = d.querySelector(".menu"), need = (m ? m.offsetHeight : 260) + 16;
    d.classList.toggle("up", r.bottom + need > innerHeight && r.top > need * .8);
    const sel = d.querySelector('.mi[role="menuitemradio"][aria-checked="true"]') || d.querySelector('.mi:not([disabled])'); if (sel) sel.focus({ preventScroll: true });
  }
  document.addEventListener("click", e => {
    const b = e.target.closest(".dd > [aria-expanded], .pop > [aria-expanded]");
    if (b) { const d = b.parentElement; d.classList.contains("open") ? closeMenus() : openMenu(d); return; }
    if (!e.target.closest(".menu")) closeMenus();
  });
  document.addEventListener("keydown", e => {
    const d = e.target.closest && e.target.closest(".dd.open, .pop.open"); if (!d) return;
    const items = [...d.querySelectorAll(".menu .mi:not([disabled])")], i = items.indexOf(document.activeElement);
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeMenus(); d.querySelector("[aria-expanded]").focus(); }
    else if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); const n = items[(i + (e.key === "ArrowDown" ? 1 : items.length - 1)) % items.length]; n && n.focus(); }
  }, true);

  // ---------- persona picker (in the prompt bar, just left of send) ----------
  const PERSONAS = [
    { v: null, label: "General", d: "Clear answers for anyone", ic: "general" },
    { v: "student", label: "Student", d: "Plain language, with the ideas built up", ic: "student" },
    { v: "professor", label: "Professor", d: "Mechanisms, equations and the literature", ic: "professor" },
    { v: "engineer", label: "Engineer", d: "Design numbers, limits and safety margins", ic: "engineer" }
  ];
  const pOf = v => PERSONAS.find(p => p.v === (v || null)) || PERSONAS[0];
  let persona = ["student", "professor", "engineer"].includes(store.get("fif-persona")) ? store.get("fif-persona") : null;
  const personaE = emitter();
  function renderPersona() {
    const p = pOf(persona), dd = document.getElementById("persona-dd");
    dd.innerHTML = `<button type="button" class="pbtn" aria-haspopup="menu" aria-expanded="false" aria-label="Answer for: ${esc(p.label)}" title="Who the answer is for">${ic(p.ic)}<span>${esc(p.label)}</span>${ic("chev", "cv")}</button>
      <div class="menu right" role="menu"><p class="menu-h">Answer for</p>${PERSONAS.map(o => `<button type="button" class="mi" role="menuitemradio" data-persona="${o.v || ""}" aria-checked="${o.v === (persona || null)}">${ic(o.ic)}<span><b>${o.label}</b><small>${o.d}</small></span>${ic("check", "tk")}</button>`).join("")}
      <p class="menu-note">Applies to your next question. "Ask again" re-answers the open one.</p></div>`;
  }
  function setPersona(v) { persona = v || null; store.set("fif-persona", persona); renderPersona(); personaE.emit(persona); }
  document.addEventListener("click", e => { const b = e.target.closest("[data-persona]"); if (!b) return; setPersona(b.dataset.persona || null); closeMenus(); });

  // ---------- environment (dropdown at the left of the prompt bar) ----------
  // Starts empty, so the reader picks one before asking; "Make … my default" pre-selects it on later visits.
  const ENVS = [
    { v: "iss", label: "ISS cabin", d: "14.7 psi · 21% O₂ · microgravity", ic: "iss" },
    { v: "lunar_habitat", label: "Lunar habitat", d: "≤ 10.2 psi · ≥ 30% O₂ · 0.16 g", ic: "moon" },
    { v: "spacesuit", label: "Spacesuit", d: "4.3 psi · 100% O₂", ic: "suit" },
    { v: "earth", label: "Earth, 1 g", d: "Sea level baseline", ic: "earth" }
  ];
  const isEnv = v => ENVS.some(x => x.v === v);
  let envDef = isEnv(store.get("fif-env-default")) ? store.get("fif-env-default") : "";
  let env = envDef, envAsk = false;
  const eOf = v => ENVS.find(x => x.v === v) || ENVS[0];
  const envE = emitter();
  function renderEnv() {
    const e = env ? eOf(env) : null, pop = document.getElementById("env-pop");
    pop.classList.toggle("empty", !e); pop.classList.toggle("ask", envAsk);
    pop.innerHTML = `<button type="button" class="pbtn" aria-haspopup="menu" aria-expanded="false" aria-label="Environment: ${e ? esc(e.label) : "none chosen"}" title="Environment for the answer">${ic(e ? e.ic : "env")}<span>${e ? esc(e.label) : "Environment"}</span>${ic("chev", "cv")}</button>
      <div class="menu" role="menu"><p class="menu-h">${envAsk ? "Choose an environment to ask" : "Environment for the answer"}</p>${ENVS.map(o => `<button type="button" class="mi" role="menuitemradio" data-env="${o.v}" aria-checked="${o.v === env}">${ic(o.ic)}<span><b>${o.label}</b><small>${o.d}</small></span>${o.v === envDef ? `<span class="mdef-tag">Default</span>` : ""}${ic("check", "tk")}</button>`).join("")}
      <button type="button" class="mi mdef" role="menuitemcheckbox" data-env-default aria-checked="${!!env && env === envDef}" ${env ? "" : "disabled"}><span class="cbx">${ic("check")}</span><span><b>${env ? `Make ${esc(e.label)} my default` : "Make it my default"}</b><small>${envDef ? `Default now: ${esc(eOf(envDef).label)}. New visits start with it.` : "No default: every visit starts empty."}</small></span></button></div>`;
  }
  function setEnv(v, o = {}) { env = isEnv(v) ? v : ""; if (env) envAsk = false; renderEnv(); envE.emit(env, o); }
  function askEnv() { envAsk = true; renderEnv(); const d = document.getElementById("env-pop"); d.classList.remove("shake"); void d.offsetWidth; d.classList.add("shake"); openMenu(d); }
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-env]");
    if (b) { const wasAsking = envAsk; setEnv(b.dataset.env, { picked: true, wasAsking }); closeMenus(); document.getElementById("q").focus(); return; }
    const df = e.target.closest("[data-env-default]");
    if (df && env) { envDef = envDef === env ? "" : env; store.set("fif-env-default", envDef || null); renderEnv(); openMenu(document.getElementById("env-pop")); toast(envDef ? `${eOf(envDef).label} is your default environment` : "No default environment"); }
  });

  // ---------- data display settings: which answer sections and charts appear ----------
  const SECTIONS = [
    { k: "facts", label: "Key facts", d: "The strip of headline numbers inside the AI overview." },
    { k: "charts", label: "Charts in findings", d: "The thermo-model chart(s) beside each finding. Off: findings are text only." },
    { k: "exps", label: "NASA experiment cards", d: "Cards for the PSI investigations behind the findings." },
    { k: "lim", label: "What the data can't say", d: "The limits of the answer, as their own box." },
    { k: "extra", label: "More charts", d: "Other charts the AI chose that don't belong to a finding." }
  ];
  const DKEY = "fif-display";
  let disp = (() => { const d = store.json(DKEY, {}); return { sections: { ...Object.fromEntries(SECTIONS.map(s => [s.k, true])), ...(d.sections || {}) }, off: Array.isArray(d.off) ? d.off : [] }; })();
  const dispE = emitter();
  const saveDisp = () => { store.setJson(DKEY, disp); dispE.emit(disp); };
  const display = {
    SECTIONS, get: () => disp,
    section: k => disp.sections[k] !== false,
    chart: t => !disp.off.includes(t),
    setSection(k, on) { disp.sections[k] = !!on; saveDisp(); },
    setChart(t, on) { disp.off = disp.off.filter(x => x !== t); if (!on) disp.off.push(t); saveDisp(); },
    setCharts(ts, on) { disp.off = disp.off.filter(x => !ts.includes(x)); if (!on) disp.off.push(...ts); saveDisp(); },
    reset() { disp = { sections: Object.fromEntries(SECTIONS.map(s => [s.k, true])), off: [] }; saveDisp(); },
    hiddenCount: () => disp.off.length + SECTIONS.filter(s => disp.sections[s.k] === false).length,
    on: f => dispE.on(f)
  };

  // ---------- question history: each question with the answer it got (reopening is instant) ----------
  // entry: { id, q, p, s, t, a, th (thread id), name?, pin?, folder? }
  const HKEY = "fif-history", FKEY = "fif-folders", HMAX = 60;
  const histE = emitter();
  const hist = () => store.json(HKEY, []).filter(h => h && h.q);
  const keyOf = (q, p, s) => [String(q).trim().toLowerCase(), p || "", s || "iss"].join("|");
  const dropOldest = H => { const i = H.map(h => !h.pin).lastIndexOf(true); H.splice(i < 0 ? H.length - 1 : i, 1); };
  function write(H) {
    H.sort((a, b) => b.t - a.t);
    while (H.length > HMAX) dropOldest(H);
    while (H.length && !store.setJson(HKEY, H)) dropOldest(H);       // storage full: drop the oldest unpinned
    renderHist(); histE.emit();
  }
  function save(entry) {
    const k = keyOf(entry.q, entry.p, entry.s), old = hist().find(h => keyOf(h.q, h.p, h.s) === k);
    const keep = old ? { name: old.name, pin: old.pin, folder: old.folder } : {};
    write([{ th: (old && old.th) || entry.id, ...entry, ...keep }, ...hist().filter(h => keyOf(h.q, h.p, h.s) !== k)]);
  }
  const find = (q, p, s) => hist().find(h => keyOf(h.q, h.p, h.s) === keyOf(q, p, s));
  const get = id => hist().find(h => h.id === id);
  function update(id, patch) { write(hist().map(h => h.id === id ? { ...h, ...patch } : h)); }
  function remove(id) { write(hist().filter(h => h.id !== id)); }
  const thread = th => th ? hist().filter(h => (h.th || h.id) === th).sort((a, b) => a.t - b.t) : [];
  const folders = () => store.json(FKEY, []).filter(f => f && f.id && f.name);
  function addFolder(name) { const f = { id: "f" + Date.now().toString(36), name: String(name).trim().slice(0, 60) || "New folder" }; store.setJson(FKEY, [...folders(), f]); renderHist(); histE.emit(); return f; }
  function renameFolder(id, name) { store.setJson(FKEY, folders().map(f => f.id === id ? { ...f, name: String(name).trim().slice(0, 60) || f.name } : f)); renderHist(); histE.emit(); }
  function removeFolder(id) { store.setJson(FKEY, folders().filter(f => f.id !== id)); write(hist().map(h => h.folder === id ? { ...h, folder: null } : h)); }
  const label = h => h.name || h.q;

  // ---------- sidebar: Pinned + Recent, each section collapsible ----------
  let filter = "", activeKey = "";
  const collapsed = new Set(store.json("fif-side-collapsed", []));
  function renderHist() {
    const el = document.getElementById("hist"); if (!el) return;
    const f = filter.toLowerCase(), H = hist().filter(h => !f || (label(h) + " " + h.q).toLowerCase().includes(f));
    const item = h => `<div class="hi${keyOf(h.q, h.p, h.s) === activeKey ? " on" : ""}"><a href="${esc(href(h.q, h.p, h.s))}" title="${esc(h.q)}">${h.pin ? ic("pin", "pn") : ""}<span>${esc(label(h))}</span></a><button type="button" class="ib" data-forget="${esc(h.id)}" aria-label="Remove from history" title="Remove">${ic("x")}</button></div>`;
    const sec = (k, title, items, more) => items.length || k === "recent" ? `<div class="hsec${collapsed.has(k) ? " shut" : ""}"><button type="button" class="side-lab" data-hsec="${k}" aria-expanded="${!collapsed.has(k)}">${esc(title)}${ic("chev", "cv")}</button>
      <div class="hsec-b">${items.length ? items.map(item).join("") : `<p class="hist-empty">${f ? "No questions match." : "Your questions will appear here."}</p>`}${more || ""}</div></div>` : "";
    const pins = H.filter(h => h.pin), rest = H.filter(h => !h.pin);
    el.innerHTML = sec("pinned", "Pinned", pins) + sec("recent", "Recent", rest.slice(0, 12), rest.length > 12 ? `<a class="hist-more" href="#questions">All ${hist().length} questions</a>` : "");
  }
  function setActive(q, p, s) { activeKey = q ? keyOf(q, p, s) : ""; renderHist(); }
  const href = (q, p, s) => "#" + new URLSearchParams({ q, ...(p ? { p } : {}), ...(s && s !== "iss" ? { s } : {}) }).toString();

  function initSide() {
    const app = document.getElementById("app"), mobile = () => innerWidth <= 900;
    document.querySelectorAll("[data-side]").forEach(b => b.innerHTML = ic("side"));
    document.querySelectorAll(".si[data-ic]").forEach(b => b.insertAdjacentHTML("afterbegin", ic(b.dataset.ic)));
    document.querySelectorAll(".brand-mark").forEach(b => b.innerHTML = mark());
    if (store.get("fif-side") === "closed") app.classList.add("noside");
    document.addEventListener("click", e => {
      if (e.target.closest("[data-side]")) {
        if (mobile()) app.classList.toggle("sideopen");
        else { app.classList.toggle("noside"); store.set("fif-side", app.classList.contains("noside") ? "closed" : null); }
        return;
      }
      if (e.target.closest("[data-side-close]") || (mobile() && e.target.closest(".side a"))) app.classList.remove("sideopen");
      const fg = e.target.closest("[data-forget]"); if (fg) { e.preventDefault(); remove(fg.dataset.forget); }
      const hs = e.target.closest("[data-hsec]"); if (hs) { const k = hs.dataset.hsec; collapsed.has(k) ? collapsed.delete(k) : collapsed.add(k); store.setJson("fif-side-collapsed", [...collapsed]); renderHist(); }
      if (e.target.closest("[data-search]")) { const l = document.querySelector(".side-search"); l.hidden = !l.hidden; if (!l.hidden) l.querySelector("input").focus(); else { filter = ""; l.querySelector("input").value = ""; renderHist(); } }
    });
    document.getElementById("hsearch").addEventListener("input", e => { filter = e.target.value; if (filter) collapsed.delete("recent"); renderHist(); });
    renderHist();
  }
  function setRoute(r) { document.querySelectorAll(".si[data-route]").forEach(a => a.classList.toggle("on", a.dataset.route === r)); }
  function setStatus(s) {
    const el = document.getElementById("ai-status"), live = s.mode === "live" && s.provider;
    el.classList.toggle("live", !!live);
    el.querySelector("span").textContent = live ? `Live AI · ${s.provider} / ${s.model}` : s.mode === "live" ? "Server found, no AI key — mock answers" : "Mock answers (open through the server for live AI)";
  }

  // ---------- share menu (top bar) ----------
  function renderShare() {
    document.getElementById("share-pop").innerHTML = `<button type="button" class="btn s sm" aria-haspopup="menu" aria-expanded="false">${ic("share")}<span>Share</span></button>
      <div class="menu right" role="menu"><p class="menu-h">Share this answer</p>
        <button type="button" class="mi" data-share="link">${ic("link")}<span><b>Copy link</b><small>Opens this question for anyone</small></span></button>
        ${navigator.share ? `<button type="button" class="mi" data-share="native">${ic("share")}<span><b>Share…</b><small>Messages, mail, AirDrop</small></span></button>` : ""}
        <button type="button" class="mi" data-share="text">${ic("copy")}<span><b>Copy answer as text</b><small>Overview, findings and references</small></span></button>
        <button type="button" class="mi" data-pdf>${ic("download")}<span><b>Download PDF summary</b><small>Everything the AI wrote, with charts and sources</small></span></button>
        <p class="menu-note">A shared link asks the AI again, so wording can differ. Send the PDF to share this exact answer.</p></div>`;
    document.querySelectorAll("[data-pdf].btn").forEach(b => { if (!b.querySelector(".ic")) b.innerHTML = `${ic("download")}<span>PDF</span>`; });
  }

  // an on/off switch (data display settings)
  const sw = (on, attrs = "", lab = "") => `<button type="button" class="sw" role="switch" aria-checked="${!!on}" ${attrs}${lab ? ` aria-label="${esc(lab)}"` : ""}><i></i></button>`;

  function init() {
    initTheme(); renderPersona(); renderEnv(); initSide(); renderShare();
    const send = document.querySelector(".send"); send.innerHTML = ic("arrow", "ar") + ic("stop", "st");
  }
  return { IC, ic, mark, esc, store, theme, setTheme, onTheme: themeE.on, toast, copy, closeMenus, openMenu, sw,
    persona: () => persona, personaLabel: v => pOf(v).label, personaIcon: v => pOf(v).ic, onPersona: personaE.on, setPersona,
    env: () => env, envDefault: () => envDef, envLabel: v => v ? eOf(v).label : "No environment", envIcon: v => v ? eOf(v).ic : "env", ENVS, setEnv, askEnv, onEnv: envE.on,
    display, hist, save, find, get, update, remove, thread, folders, addFolder, renameFolder, removeFolder, label, onHist: histE.on,
    setActive, href, setRoute, setStatus, init };
})();
