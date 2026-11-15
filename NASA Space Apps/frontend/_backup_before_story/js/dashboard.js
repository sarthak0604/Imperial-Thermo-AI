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
  U.askHref = q => qHref(q);
  const CAT_LABEL = { graph: "Graph", interactive: "Interactive", visual: "Visual", data: "Data", explanation: "Explanation", link: "Links" };
  let current = null;   // { widgets, centreHTML, seed }

  const place = r => `grid-row:${r.r + 1} / span ${r.rs};grid-column:${r.c + 1} / span ${r.cs};`;

  const PAGE = 16;   // most boxes the tiler places on one screen; longer lists (the widget library) become stacked screens
  function draw(widgets, centreHTML, seed) {
    if (tour && tourFor !== widgets) tour = null;                                         // a different dashboard: the tour is over
    current = { widgets, centreHTML, seed };
    const vp = { w: window.innerWidth, h: window.innerHeight }, pages = [];
    for (let a = 0; a < widgets.length || !pages.length; a += PAGE) pages.push(widgets.slice(a, a + PAGE));
    let off = 0;
    out.innerHTML = pages.map((pg, n) => {
      const L = TILER.layout(pg.map(w => W.shape(w.type, w.params)), seed + n, vp);
      if (!n) current.layout = L;
      const html = `<div class="bento" style="grid-template-columns:repeat(${L.C},minmax(0,1fr));grid-template-rows:repeat(${L.R},minmax(0,1fr))">
      <section class="centre" style="${place(L.centre)}">${n ? `` : `<div id="form-slot"></div>`}${n ? `<h1>Widget library · part ${n + 1}</h1>` : centreHTML}</section>
      ${L.rects.map((r, i) => W.sketch(pg[i].type, { i: off + i, place: place(r), params: pg[i].params })).join("")}</div>`;
      off += pg.length; return html;
    }).join("");
    document.getElementById("form-slot").appendChild(form);
    markClipped();
    applyReveal();
  }

  // text boxes that hold more than they can show get a fade + "open" hint
  function markClipped() {
    out.querySelectorAll(".ttile .t-body").forEach(b => {
      b.style.fontSize = "";
      // shrink the type a little before resorting to a fade
      for (let px = parseFloat(getComputedStyle(b).fontSize) - 0.5; b.scrollHeight > b.clientHeight + 2 && px >= 11; px -= 0.5) b.style.fontSize = px + "px";
      b.classList.toggle("clipped", b.scrollHeight > b.clientHeight + 2);
    });
  }

  // ---------- guided walkthrough ----------
  // The final layout is drawn once; boxes not yet shown are faint outlines (.ghost). Each step opens a box large, then Next fills its outline.
  let tour = null, tourFor = null, flying = false, flyTimer = 0;
  function resetTour() {                                                                  // forget any tour, including a pending "landing" timer
    clearTimeout(flyTimer); tour = null; tourFor = null; flying = false;
    document.body.classList.remove("tour-flying");
  }
  function applyReveal() {
    const shown = tour ? new Set(tour.revealed()) : null;
    out.querySelectorAll(".widget.sketch").forEach(el => {
      const ghost = !!tour && !shown.has(+el.dataset.i);
      if (tour) el.classList.add("settled");                                             // no pop-in replay when the outline fills
      el.classList.toggle("ghost", ghost);
      el.tabIndex = ghost ? -1 : 0;                                                      // outlines are not reachable by keyboard or screen reader
      ghost ? el.setAttribute("aria-hidden", "true") : el.removeAttribute("aria-hidden");
    });
  }
  function startTour() {
    if (!current || !current.widgets || current.widgets.length < TOUR.MIN_BOXES) return;
    resetTour(); closeFocus();
    tour = TOUR.create(current.widgets); tourFor = current.widgets;
    applyReveal(); openFocus(tour.index(), true);
  }
  function endTour() {
    resetTour(); applyReveal(); closeFocus();
  }
  function tourNext() {
    if (!tour || flying) return;
    const t = tour, i = t.index(), last = t.atEnd();
    if (!last) tour.next();
    else tour.pos = tour.total;                                                          // Finish: everything revealed
    applyReveal();
    const el = out.querySelector(`.widget.sketch[data-i="${i}"]`);
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    focusEl.hidden = true; flying = true;                                                // let the box visibly land in its outline
    document.body.classList.add("tour-flying");                                          // no clicks on the dashboard while it lands
    if (el && !calm) { el.classList.remove("just"); void el.offsetWidth; el.classList.add("just"); }
    clearTimeout(flyTimer);
    flyTimer = setTimeout(() => {
      if (tour !== t || !flying) return;                                                 // this tour was skipped or replaced meanwhile
      flying = false; document.body.classList.remove("tour-flying");
      if (last) endTour(); else openFocus(t.index(), true);
    }, calm ? 0 : 520);
  }
  function tourBack() {
    if (!tour || flying || !tour.back()) return;
    applyReveal(); openFocus(tour.index(), true);
  }

  // ---------- focus window ----------
  let lastFocus = null;
  function openFocus(i, inTour) {
    const w = current && current.widgets[i]; if (!w) return;
    const d = W.def(w.type) || { title: w.type }, text = W.isText(w.type), p = w.params || {};
    lastFocus = document.activeElement;
    const cap = inTour && tour ? TOUR.caption(w) : null;
    focusEl.innerHTML = `<div class="focus-backdrop" data-close></div>
      <div class="focus-panel${cap ? " tour" : ""}" role="dialog" aria-modal="true" aria-labelledby="focus-title">
        <button class="focus-close" data-close aria-label="Close">×</button>
        <div class="focus-visual">${text ? `<div class="mw-full text-full t-${esc(w.type)}">${TW.full(w.type, p)}</div>` : W.full(w.type)}</div>
        <div class="focus-text">
          <p class="focus-cat">${cap ? `Step ${tour.pos + 1} of ${tour.total} · ${esc(cap.kicker)}` : text ? "Text" : esc(CAT_LABEL[d.cat] || "") + " · " + esc(d.model || "")}</p>
          <h2 id="focus-title">${esc(text ? TW.titleOf(w.type, p) : d.title)}</h2>
          ${MW.STATUS[d.status] || ""}
          <p>${esc(d.desc || "")}</p>
          ${cap ? `<p class="focus-sub">Why it matters for your question</p><p>${esc(cap.why)}</p>` : w.why ? `<p class="focus-sub">Why it's here</p><p>${esc(w.why)}</p>` : ""}
          ${text ? (TW.srcOf(w.type, p) ? `<p class="focus-source">${esc(TW.srcOf(w.type, p))}</p>` : "")
            : `<p class="focus-source">From the thermo team's ${esc(d.model || "")} model · outputs pre-computed by standin/precompute_models.py</p>`}
        </div>
        ${cap ? `<div class="tour-bar">
          <button type="button" data-tour="back"${tour.pos === 0 ? " disabled" : ""}>← Back</button>
          <button type="button" data-tour="next" class="primary">${tour.atEnd() ? "Finish" : "Next →"}</button>
          <button type="button" data-tour="skip">Skip to full dashboard</button>
          <label class="tour-off"><input type="checkbox" data-tour="off"${TOUR.pref.off() ? " checked" : ""}> Don't walk me through next time</label>
        </div>` : ""}
      </div>`;
    focusEl.hidden = false; document.body.classList.add("focus-open");
    W.mountFull(focusEl.querySelector(".mw-full"), w.type);
    (cap ? focusEl.querySelector('[data-tour="next"]') : focusEl.querySelector(".focus-close")).focus();
  }
  function closeFocus() {
    if (focusEl.hidden && !focusEl.innerHTML && !document.body.classList.contains("focus-open")) return;
    focusEl.hidden = true; focusEl.innerHTML = ""; document.body.classList.remove("focus-open");
    if (lastFocus && lastFocus.isConnected) lastFocus.focus();
  }
  out.addEventListener("click", e => { if (flying || e.target.closest("a")) return;                       // links inside a box (ask next) just navigate
    const el = e.target.closest(".widget.sketch"); if (el) openFocus(+el.dataset.i); });
  out.addEventListener("keydown", e => { if (flying) return; const el = e.target.closest(".widget.sketch"); if (el && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openFocus(+el.dataset.i); } });
  focusEl.addEventListener("click", e => {
    const t = e.target.closest("[data-tour]");
    if (t) {
      const k = t.dataset.tour;
      if (k === "next") tourNext(); else if (k === "back") tourBack(); else if (k === "skip") endTour();
      else if (k === "off") TOUR.pref.set(t.checked);
      return;
    }
    if (e.target.closest("[data-close]")) { tour ? endTour() : closeFocus(); } else if (e.target.closest("a")) { tour ? endTour() : closeFocus(); }
  });
  out.addEventListener("click", e => { if (e.target.closest("[data-replay]")) startTour(); });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") { tour ? endTour() : closeFocus(); return; }
    if (e.key === "Tab" && !focusEl.hidden) {                                            // keep Tab inside the open window
      const f = [...focusEl.querySelectorAll("button:not([disabled]),input,select,textarea,a[href],[tabindex]:not([tabindex='-1'])")].filter(x => x.offsetParent !== null);
      if (!f.length) return;
      const k = f.indexOf(document.activeElement);
      if (k < 0 || (e.shiftKey && k === 0) || (!e.shiftKey && k === f.length - 1)) { e.preventDefault(); f[e.shiftKey ? f.length - 1 : 0].focus(); }
      return;
    }
    if (!tour || (e.key !== "ArrowRight" && e.key !== "ArrowLeft")) return;
    if (e.target.closest && e.target.closest("input:not([type=checkbox]),select,textarea")) return;       // sliders in interactive boxes keep their arrow keys
    e.preventDefault(); e.key === "ArrowRight" ? tourNext() : tourBack();
  });

  // ---------- pages ----------
  async function generate(q) {
    resetTour(); closeFocus();
    const who = persona;
    document.body.classList.add("has-dashboard");
    form.elements.q.value = q;
    draw([], `<p class="centre-status">…</p>`, 1);
    const a = await API.ask({ question: q, persona: who || "general", scenario: "iss", history: [] });
    if (hashParams().get("q") !== q || persona !== who) return;                           // user moved on
    const live = a.meta && a.meta.source === "live";
    const charts = (a.widgets || []).filter(w => W.def(w.type) && !W.isText(w.type));
    const boxes = TW.assemble(a, charts, { live, question: q, error: a.meta && a.meta.error });
    const walk = boxes.length >= TOUR.MIN_BOXES;
    draw(boxes, `<h1>${esc(a.title || q)}</h1>${live ? "" : `<span class="tag-mock">mock</span>`}${walk ? `<button type="button" class="replay" data-replay>▶ Walk me through it</button>` : ""}`, TILER.hash(q + "|" + (who || "")));
    if (walk && !TOUR.pref.off()) startTour();
  }
  function library() {
    resetTour(); closeFocus();
    document.body.classList.add("has-dashboard", "is-library");
    form.elements.q.value = "";
    draw(TW.assemble(null, W.types().map(t => ({ type: t, params: W.samples[t] })), { library: true }), `<h1>Widget library</h1>`, 11);
  }
  function route() {
    document.body.classList.remove("is-library");
    const hp = hashParams(), q = hp.get("q");
    if (hp.has("p")) { persona = ["student", "professor", "engineer"].includes(hp.get("p")) ? hp.get("p") : null; try { persona && localStorage.setItem(PKEY, persona); } catch (e) {} }
    setPersonaUI();
    if (location.hash === "#library") library();
    else if (q) generate(q);
    else { resetTour(); closeFocus(); current = null; document.body.classList.remove("has-dashboard"); out.innerHTML = ""; home.prepend(form); form.elements.q.value = ""; }
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
