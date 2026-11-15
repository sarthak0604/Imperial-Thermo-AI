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
  let current = null;   // bento (library): { widgets, centreHTML, seed } · answer page: { story: true, a, rows, widgets, lead }

  const place = r => `grid-row:${r.r + 1} / span ${r.rs};grid-column:${r.c + 1} / span ${r.cs};`;

  // ---------- widget library: the bento grid ----------
  const PAGE = 16;   // most boxes the tiler places on one screen; longer lists (the widget library) become stacked screens
  function draw(widgets, centreHTML, seed) {
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
  }

  // text boxes that hold more than they can show get a fade + "open" hint
  function markClipped() {
    out.querySelectorAll(".ttile .t-body").forEach(b => {
      b.style.fontSize = "";
      if (b.closest(".srow[hidden]")) return;
      if (b.closest(".t-point") && !b.closest(".stack")) b.style.fontSize = "22px";             // a point's words fill their box, then shrink to fit
      // shrink the type a little before resorting to a fade
      for (let px = parseFloat(getComputedStyle(b).fontSize) - 0.5; b.scrollHeight > b.clientHeight + 2 && px >= 11.5; px -= 0.5) b.style.fontSize = px + "px";
      b.classList.toggle("clipped", b.scrollHeight > b.clientHeight + 2);
    });
  }

  // ---------- answer page: the story ----------
  // Header row (question, short answer, key facts) → one row per point (its words + the charts that show it, or the
  // NASA experiment behind it) → caveats / evidence / ask next. Each row is justified to fill the width (js/story.js).
  // the NASA investigations each thermo model is built on (from the model tracker, as in standin/context.json)
  const LINKED = {"THM-01":["PSI-20","PSI-159","PSI-69"],"THM-02":["PSI-20","PSI-10","PSI-69"],"THM-03":["PSI-159","PSI-10"],"THM-04":["PSI-98","PSI-99","PSI-100","PSI-25"],"THM-05":["PSI-26","PSI-25","PSI-98","PSI-99","PSI-100"],"THM-06":["PSI-26","PSI-25","PSI-98","PSI-99","PSI-100"],"THM-07":["PSI-25","PSI-106"],"THM-08":["PSI-25","PSI-22"],"THM-09":["PSI-26","PSI-25","PSI-98","PSI-99","PSI-100"],"THM-10":["PSI-69","PSI-68","PSI-39"],"THM-11":["PSI-69","PSI-68","PSI-159"],"THM-12":["PSI-69","PSI-68"],"THM-13":["PSI-25","PSI-20"],"THM-14":["PSI-98","PSI-99","PSI-100","PSI-10"],"THM-15":["PSI-10","PSI-159","PSI-69"],"THM-16":["PSI-26","PSI-25","PSI-98","PSI-99","PSI-100"],"THM-17":["PSI-25","PSI-20"],"THM-18":["PSI-69","PSI-25"],"THM-19":["PSI-98","PSI-99","PSI-100"],"THM-20":["PSI-102","PSI-101","PSI-98","PSI-99","PSI-100"]};
  const ENV = {
    isChart: t => !!MW.lib[t], isPsi: id => !!U.inv(id), desc: t => (W.def(t) || {}).desc || "",
    linked: t => { const d = W.def(t); return (d && LINKED[d.model]) || []; }
  };
  const ROW = { gap: 10, minText: 0.3, hmin: 240 };
  function storyHTML() {
    const c = current, vw = document.documentElement.clientWidth || window.innerWidth, vh = window.innerHeight;
    const phone = vw < 760, Wd = vw - 2 * ROW.gap;
    let i = 0;
    c.widgets = [];
    const box = (it, style) => {
      if (it.type === "lead") return `<section class="centre lead" style="${style}"><div id="form-slot"></div>${c.lead}</section>`;
      c.widgets.push(it);
      return W.sketch(it.type, { i: i++, place: style, params: it.params });
    };
    return c.rows.map((row, k) => {
      if (phone) {
        const items = [...row.items].sort((x, y) => (y.type === "point") - (x.type === "point"));   // on a phone the words come first
        return `<div class="srow stack ${row.kind}" data-row="${k}">${items.map(it => {
          if (W.isText(it.type) || it.type === "lead") return box(it, "");
          const [aspect, amin] = MW.shape(it.type);
          return box(it, `height:${Math.round(Wd / Math.max(amin, Math.min(aspect, 1.3)))}px`);
        }).join("")}</div>`;
      }
      const specs = row.items.map(it => it.type === "lead" ? { flex: true, need: 70000 + String(it.params.summary || "").length * 260 + (it.params.note ? 30000 : 0) }
        : W.isText(it.type) ? { flex: true, need: TW.need(it.type, it.params) }
        : (([aspect, amin, amax]) => ({ aspect, amin, amax }))(MW.shape(it.type)));
      const textOnly = row.items.every(it => it.type === "lead" || W.isText(it.type));
      const o = { ...ROW, hmin: row.kind === "header" ? 270 : row.kind === "close" ? 150 : textOnly && row.items.length === 1 ? 110 : textOnly ? 200 : ROW.hmin, hmax: Math.max(300, Math.round(vh * (row.kind === "close" ? 0.42 : 0.52))), hpref: Math.round(vh * 0.42) };
      let { h, widths } = STORY.solve(specs, Wd, o);
      if (row.kind === "header") {                                  // the question box must fit: ask box, title, short answer, replay button
        const lw = widths[0] - 44, chars = String(row.items[0].params.summary || "").length + 40;
        h = Math.max(h, 190 + Math.ceil(chars * 8.6 / Math.max(200, lw)) * 25);
      }
      if (textOnly && row.kind === "point" && row.items.length === 1) h = Math.max(110, Math.min(h, 60 + Math.ceil(String(row.items[0].params.text).length * 11 / widths[0]) * 34));
      return `<div class="srow ${row.kind}" data-row="${k}" style="height:${Math.round(h)}px">${row.items.map((it, j) =>
        box(it, `width:${(widths[j]).toFixed(1)}px`)).join("")}</div>`;
    }).join("");
  }
  function drawStory() {
    out.innerHTML = `<div class="story">${storyHTML()}</div>`;
    document.getElementById("form-slot").appendChild(form);
    applyReveal(false);
    markClipped();
  }

  // ---------- walkthrough: the rows appear one at a time ----------
  let tour = null;
  const barEl = document.createElement("div");
  barEl.id = "tour-bar"; barEl.hidden = true; document.body.appendChild(barEl);
  const calm = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function stepLabel(k) {
    const r = current.rows[k], pts = current.rows.filter(x => x.kind === "point").length;
    return r.kind === "header" ? "The short answer" : r.kind === "close" ? "Caveats, evidence and what to ask next"
      : `Point ${r.items.find(x => x.type === "point").params.n} of ${pts}`;
  }
  function applyReveal(scroll) {
    const n = tour ? tour.shown() : Infinity;
    out.querySelectorAll(".srow").forEach(r => { r.hidden = +r.dataset.row >= n; });
    if (!tour) { barEl.hidden = true; barEl.innerHTML = ""; return; }
    barEl.hidden = false;
    barEl.innerHTML = `<span class="tour-step">Step ${tour.shown()} of ${tour.total} · ${esc(stepLabel(tour.pos))}</span>
      <button type="button" data-tour="back"${tour.pos === 0 ? " disabled" : ""}>← Back</button>
      <button type="button" data-tour="next" class="primary">${tour.atEnd() ? "Finish" : "Next →"}</button>
      <button type="button" data-tour="skip">Show the whole answer</button>
      <label class="tour-off"><input type="checkbox" data-tour="off"${TOUR.pref.off() ? " checked" : ""}> Don't walk me through next time</label>`;
    if (scroll) {
      const row = out.querySelector(`.srow[data-row="${tour.pos}"]`);
      if (row) {
        if (!calm()) { row.classList.remove("just"); void row.offsetWidth; row.classList.add("just"); }
        markClipped();
        const top = row.getBoundingClientRect().top + window.scrollY - ROW.gap;
        const fits = row.offsetHeight + barEl.offsetHeight + 2 * ROW.gap <= window.innerHeight;
        window.scrollTo({ top: fits ? Math.max(0, top - (window.innerHeight - barEl.offsetHeight - row.offsetHeight - 2 * ROW.gap)) : top, behavior: calm() ? "auto" : "smooth" });
      }
    }
  }
  function startTour() {
    if (!current || !current.story || current.rows.length < TOUR.MIN_BOXES) return;
    closeFocus(); tour = TOUR.steps(current.rows.length);
    applyReveal(false); window.scrollTo(0, 0);
    const nx = barEl.querySelector('[data-tour="next"]'); if (nx) nx.focus({ preventScroll: true });
  }
  function endTour() { tour = null; if (current && current.story) { applyReveal(false); markClipped(); } else { barEl.hidden = true; barEl.innerHTML = ""; } }
  function tourNext() { if (!tour) return; if (tour.atEnd()) return endTour(); tour.next(); applyReveal(true); barEl.querySelector('[data-tour="next"]').focus({ preventScroll: true }); }
  function tourBack() { if (!tour || !tour.back()) return; applyReveal(true); barEl.querySelector('[data-tour="back"]:not([disabled])') ? barEl.querySelector('[data-tour="back"]').focus({ preventScroll: true }) : barEl.querySelector('[data-tour="next"]').focus({ preventScroll: true }); }
  barEl.addEventListener("click", e => {
    const t = e.target.closest("[data-tour]"); if (!t) return;
    const k = t.dataset.tour;
    if (k === "next") tourNext(); else if (k === "back") tourBack(); else if (k === "skip") endTour(); else if (k === "off") TOUR.pref.set(t.checked);
  });

  // ---------- focus window: any box, opened large ----------
  let lastFocus = null;
  function openFocus(i) {
    const w = current && current.widgets[i]; if (!w) return;
    const d = W.def(w.type) || { title: w.type }, text = W.isText(w.type), p = w.params || {};
    lastFocus = document.activeElement;
    focusEl.innerHTML = `<div class="focus-backdrop" data-close></div>
      <div class="focus-panel" role="dialog" aria-modal="true" aria-labelledby="focus-title">
        <button class="focus-close" data-close aria-label="Close">×</button>
        <div class="focus-visual">${text ? `<div class="mw-full text-full t-${esc(w.type)}">${TW.full(w.type, p)}</div>` : W.full(w.type)}</div>
        <div class="focus-text">
          <p class="focus-cat">${text ? "Text" : esc(CAT_LABEL[d.cat] || "") + " · " + esc(d.model || "")}</p>
          <h2 id="focus-title">${esc(text ? TW.titleOf(w.type, p) : d.title)}</h2>
          ${MW.STATUS[d.status] || ""}
          <p>${esc(d.desc || "")}</p>
          ${w.why ? `<p class="focus-sub">Why it's here</p><p>${esc(w.why)}</p>` : ""}
          ${text ? "" : TW.litHTML(w.type)}
          ${text ? (TW.srcOf(w.type, p) ? `<p class="focus-source">${esc(TW.srcOf(w.type, p))}</p>` : "")
            : `<p class="focus-source">From the thermo team's ${esc(d.model || "")} model · outputs pre-computed by standin/precompute_models.py</p>`}
        </div>
      </div>`;
    focusEl.hidden = false; document.body.classList.add("focus-open");
    W.mountFull(focusEl.querySelector(".mw-full"), w.type);
    focusEl.querySelector(".focus-close").focus();
  }
  function closeFocus() {
    if (focusEl.hidden && !focusEl.innerHTML && !document.body.classList.contains("focus-open")) return;
    focusEl.hidden = true; focusEl.innerHTML = ""; document.body.classList.remove("focus-open");
    if (lastFocus && lastFocus.isConnected) lastFocus.focus({ preventScroll: true });
  }
  out.addEventListener("click", e => {
    if (e.target.closest("[data-replay]")) return startTour();
    if (e.target.closest("a")) return;                                                   // links inside a box (ask next) just navigate
    const el = e.target.closest(".widget.sketch"); if (el) openFocus(+el.dataset.i);
  });
  out.addEventListener("keydown", e => { const el = e.target.closest(".widget.sketch"); if (el && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openFocus(+el.dataset.i); } });
  focusEl.addEventListener("click", e => { if (e.target.closest("[data-close]") || e.target.closest("a")) closeFocus(); });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") { if (!focusEl.hidden) closeFocus(); else if (tour) endTour(); return; }
    if (e.key === "Tab" && !focusEl.hidden) {                                            // keep Tab inside the open window
      const f = [...focusEl.querySelectorAll("button:not([disabled]),input,select,textarea,a[href],[tabindex]:not([tabindex='-1'])")].filter(x => x.offsetParent !== null);
      if (!f.length) return;
      const k = f.indexOf(document.activeElement);
      if (k < 0 || (e.shiftKey && k === 0) || (!e.shiftKey && k === f.length - 1)) { e.preventDefault(); f[e.shiftKey ? f.length - 1 : 0].focus(); }
      return;
    }
    if (!tour || !focusEl.hidden || (e.key !== "ArrowRight" && e.key !== "ArrowLeft")) return;
    if (e.target.closest && e.target.closest("input:not([type=checkbox]),select,textarea")) return;       // the ask box and sliders keep their arrow keys
    e.preventDefault(); e.key === "ArrowRight" ? tourNext() : tourBack();
  });

  // ---------- pages ----------
  function stopAll() { tour = null; barEl.hidden = true; barEl.innerHTML = ""; closeFocus(); document.body.classList.remove("is-story"); }
  async function generate(q) {
    stopAll();
    const who = persona;
    document.body.classList.add("has-dashboard");
    form.elements.q.value = q;
    current = null;
    out.innerHTML = `<div class="story"><div class="srow header" style="min-height:260px"><section class="centre lead" style="width:100%"><div id="form-slot"></div><p class="centre-status">Working out the answer from the NASA data…</p></section></div></div>`;
    document.getElementById("form-slot").appendChild(form);
    const a = await API.ask({ question: q, persona: who || "general", scenario: "iss", history: [] });
    if (hashParams().get("q") !== q || persona !== who) return;                           // user moved on
    const live = a.meta && a.meta.source === "live";
    const points = STORY.points(a, ENV);
    const ans = { ...a };
    if (!live) { ans.note = true; ans.summary = a.meta && a.meta.error
      ? `The AI did not answer this time (${String(a.meta.error).slice(0, 140)}). Below, the charts were picked from the words in your question; try asking again in a moment.`
      : TW.PREVIEW_NOTE.replace("the charts were picked", "the points and charts below were picked"); }
    if (!(ans.evidence || []).length) ans.evidence = [...new Set(points.flatMap(p => p.psi_ids))].map(psi_id => ({ psi_id }));
    if (!(ans.follow_ups || []).length) { const seed = TILER.hash(q); ans.follow_ups = TW.ASK_NEXT.map((x, i) => TW.ASK_NEXT[(i + seed) % TW.ASK_NEXT.length]).filter(x => x !== q).slice(0, 3); }
    const rows = STORY.rows(ans, points);
    const walk = rows.length >= TOUR.MIN_BOXES;
    current = { story: true, a: ans, rows, widgets: [],
      lead: `<h1>${esc(ans.title || q)}</h1>${live ? "" : `<span class="tag-mock">mock</span>`}
        <div class="lead-answer${ans.note ? " t-note" : ""}">${U.md(ans.summary || "")}</div>
        ${walk ? `<button type="button" class="replay" data-replay>▶ Walk me through it</button>` : ""}` };
    document.body.classList.add("is-story");
    if (walk && !TOUR.pref.off()) tour = TOUR.steps(rows.length);
    drawStory();
    window.scrollTo(0, 0);
  }
  function library() {
    stopAll();
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
    else { stopAll(); current = null; document.body.classList.remove("has-dashboard"); out.innerHTML = ""; home.prepend(form); form.elements.q.value = ""; }
  }

  form.addEventListener("submit", e => {
    e.preventDefault();
    const q = form.elements.q.value.trim();
    if (!q) return;
    if (location.hash === qHref(q)) generate(q); else location.hash = qHref(q);
  });
  let t; window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => {
    if (!current) return;
    const v = form.elements.q.value;
    if (current.story) drawStory();
    else if (current.widgets.length) { draw(current.widgets, current.centreHTML, current.seed); out.querySelectorAll(".widget.sketch").forEach(el => { el.style.animation = "none"; el.style.opacity = 1; }); }
    form.elements.q.value = v; }, 200); });
  window.addEventListener("hashchange", route);
  API.health().then(route);
})();
