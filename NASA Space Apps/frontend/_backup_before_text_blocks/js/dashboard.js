// DASHBOARD — the question sits in the centre; widget boxes tile around it and fill the whole screen.
// Click (or Enter on) any box → it opens enlarged in a focus window with an explanation.
// #q=<question> → dashboard (shareable, Back works). #library → every widget.
(() => {
  const { esc, inv, invLabel, md } = U;
  const form = document.getElementById("ask-form");
  const home = document.getElementById("home");
  const out = document.getElementById("dashboard");
  const focusEl = document.getElementById("focus");
  // persona: from the URL, else remembered choice, else none ("general")
  const PKEY = "fif-persona";
  let persona = null;
  try { persona = localStorage.getItem(PKEY); } catch (e) {}
  const hashParams = () => new URLSearchParams(location.hash.replace(/^#/, ""));
  const qHref = (q, p = persona) => "#" + new URLSearchParams(p ? { q, p } : { q }).toString();
  function setPersonaUI() {
    form.querySelectorAll("[data-persona]").forEach(b => b.setAttribute("aria-checked", String(b.dataset.persona === persona)));
  }
  form.querySelector(".persona-pick").addEventListener("click", e => {
    const b = e.target.closest("[data-persona]"); if (!b) return;
    persona = persona === b.dataset.persona ? null : b.dataset.persona;     // click again to deselect
    try { persona ? localStorage.setItem(PKEY, persona) : localStorage.removeItem(PKEY); } catch (err) {}
    setPersonaUI();
    const q = hashParams().get("q");
    if (q) location.hash = qHref(q);                                        // on a dashboard → rebuild for the new persona
  });
  U.invHref = id => qHref(`Everything about ${invLabel(inv(id))} (${id})`);
  U.modelHref = id => qHref(`Thermo model ${id}`);
  const CAT_LABEL = { graph: "Graph", interactive: "Interactive", visual: "Visual", data: "Data", explanation: "Explanation", link: "Links" };
  let current = null;   // { widgets, centreHTML, seed }

  const place = r => `grid-row:${r.r + 1} / span ${r.rs};grid-column:${r.c + 1} / span ${r.cs};`;

  // Live answers carry text fields (summary, key facts, evidence…) — show them as widgets too
  function withTextWidgets(a) {
    const ws = (a.widgets || []).slice(0, 10), has = t => ws.some(w => w.type === t), extra = [];
    if (a.summary && !has("explanation")) extra.push({ type: "explanation", params: { text: a.summary } });
    (a.key_facts || []).slice(0, 3).forEach(f => extra.push({ type: "key_fact", params: f }));
    if ((a.evidence || []).length && !has("evidence")) extra.push({ type: "evidence", params: { items: a.evidence } });
    if (a.limitations && !has("limitations")) extra.push({ type: "limitations", params: { text: a.limitations } });
    if ((a.follow_ups || []).length && !has("follow_ups")) extra.push({ type: "follow_ups", params: { items: a.follow_ups } });
    return extra.concat(ws).slice(0, 16);
  }

  function draw(widgets, centreHTML, seed) {
    current = { widgets, centreHTML, seed };
    const L = TILER.layout(widgets.map(w => W.shape(w.type)), seed, { w: window.innerWidth, h: window.innerHeight });
    out.innerHTML = `<div class="bento" style="grid-template-columns:repeat(${L.C},minmax(0,1fr));grid-template-rows:repeat(${L.R},minmax(0,1fr))">
      <section class="centre" style="${place(L.centre)}"><div id="form-slot"></div>${centreHTML}</section>
      ${L.rects.map((r, i) => W.sketch(widgets[i].type, { i, place: place(r), label: widgets[i].params && widgets[i].params.label })).join("")}</div>`;
    document.getElementById("form-slot").appendChild(form);
  }

  // ---------- focus window ----------
  function contentFor(w) {
    const p = w.params || {};
    if (w.type === "explanation" || w.type === "limitations") return p.text ? md(p.text) : "";
    if (w.type === "key_fact" && p.value) return `<p class="focus-stat">${esc(p.value)}</p><p class="muted">${esc(p.label || "")}${p.source ? " · " + esc(p.source) : ""}</p>`;
    if (w.type === "follow_ups" && (p.items || []).length) return `<ul>${p.items.map(f => `<li><a href="${qHref(f)}">${esc(f)}</a></li>`).join("")}</ul>`;
    if (w.type === "evidence" && (p.items || []).length) return `<ul>${p.items.map(e => { const i = inv(e.psi_id);
      return `<li><a href="${esc(U.invHref(e.psi_id))}">${esc(i ? invLabel(i) : e.psi_id)} · ${esc(e.psi_id)}</a>${e.note ? " — " + esc(e.note) : ""}</li>`; }).join("")}</ul>`;
    const ids = [p.id, p.node, ...(p.ids || []), ...(p.psi_ids || []), ...((p.items || []).map(x => x && x.id))].filter(Boolean);
    const uniq = [...new Set(ids)].map(inv).filter(Boolean);
    return uniq.length ? `<p class="focus-sub">Investigations</p><ul>${uniq.map(i => `<li><a href="${esc(U.invHref(i.id))}">${esc(U.invTitle(i))}</a> · <a href="${esc(i.url)}" target="_blank" rel="noopener">PSI ↗</a></li>`).join("")}</ul>` : "";
  }
  let lastFocus = null;
  function openFocus(i) {
    const w = current && current.widgets[i]; if (!w) return;
    const d = W.def(w.type) || { title: w.type };
    lastFocus = document.activeElement;
    focusEl.innerHTML = `<div class="focus-backdrop" data-close></div>
      <div class="focus-panel" role="dialog" aria-modal="true" aria-labelledby="focus-title">
        <button class="focus-close" data-close aria-label="Close">×</button>
        <div class="focus-visual">${W.full(w.type)}</div>
        <div class="focus-text">
          <p class="focus-cat">${esc(CAT_LABEL[d.cat] || "")} · ${esc(d.model || "")}</p>
          <h2 id="focus-title">${esc(d.title)}</h2>
          ${MW.STATUS[d.status] || ""}
          <p>${esc(d.desc || "")}</p>
          ${w.why ? `<p class="focus-sub">Why it's here</p><p>${esc(w.why)}</p>` : ""}
          <p class="focus-source">From the thermo team's ${esc(d.model || "")} model · outputs pre-computed by standin/precompute_models.py</p>
        </div>
      </div>`;
    focusEl.hidden = false; document.body.classList.add("focus-open");
    W.mountFull(focusEl.querySelector(".mw-full"), w.type);
    focusEl.querySelector(".focus-close").focus();
  }
  function closeFocus() {
    if (focusEl.hidden) return;
    focusEl.hidden = true; focusEl.innerHTML = ""; document.body.classList.remove("focus-open");
    if (lastFocus) lastFocus.focus();
  }
  out.addEventListener("click", e => { const el = e.target.closest(".widget.sketch"); if (el) openFocus(+el.dataset.i); });
  out.addEventListener("keydown", e => { const el = e.target.closest(".widget.sketch"); if (el && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openFocus(+el.dataset.i); } });
  focusEl.addEventListener("click", e => { if (e.target.closest("[data-close]")) closeFocus(); else if (e.target.closest("a")) closeFocus(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeFocus(); });

  // ---------- pages ----------
  async function generate(q) {
    closeFocus();
    const who = persona;
    document.body.classList.add("has-dashboard");
    form.elements.q.value = q;
    draw([], `<p class="centre-status">…</p>`, 1);
    const a = await API.ask({ question: q, persona: who || "general", scenario: "iss", history: [] });
    if (hashParams().get("q") !== q || persona !== who) return;                           // user moved on
    const live = a.meta && a.meta.source === "live";
    draw((a.widgets || []).filter(w => W.def(w.type)), `<h1>${esc(a.title || q)}</h1>${live ? "" : `<span class="tag-mock">mock</span>`}`, TILER.hash(q + "|" + (who || "")));
  }
  function library() {
    closeFocus();
    document.body.classList.add("has-dashboard", "is-library");
    form.elements.q.value = "";
    draw(W.types().map(t => ({ type: t, params: W.samples[t] })), `<h1>Widget library</h1>`, 11);
  }
  function route() {
    document.body.classList.remove("is-library");
    const hp = hashParams(), q = hp.get("q");
    if (hp.has("p")) { persona = ["student", "professor", "engineer"].includes(hp.get("p")) ? hp.get("p") : null; try { persona && localStorage.setItem(PKEY, persona); } catch (e) {} }
    setPersonaUI();
    if (location.hash === "#library") library();
    else if (q) generate(q);
    else { closeFocus(); current = null; document.body.classList.remove("has-dashboard"); out.innerHTML = ""; home.prepend(form); form.elements.q.value = ""; }
  }

  form.addEventListener("submit", e => {
    e.preventDefault();
    const q = form.elements.q.value.trim();
    if (!q) return;
    if (location.hash === qHref(q)) generate(q); else location.hash = qHref(q);
  });
  let t; window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => {
    if (current && current.widgets.length) { const v = form.elements.q.value; draw(current.widgets, current.centreHTML, current.seed); form.elements.q.value = v;
      out.querySelectorAll(".widget.sketch").forEach(el => { el.style.animation = "none"; el.style.opacity = 1; }); } }, 200); });
  window.addEventListener("hashchange", route);
  API.health().then(route);
})();
