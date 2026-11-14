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
      // shrink the type a little before resorting to a fade
      for (let px = parseFloat(getComputedStyle(b).fontSize) - 0.5; b.scrollHeight > b.clientHeight + 2 && px >= 11; px -= 0.5) b.style.fontSize = px + "px";
      b.classList.toggle("clipped", b.scrollHeight > b.clientHeight + 2);
    });
  }

  // ---------- focus window ----------
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
          ${text ? (TW.srcOf(w.type, p) ? `<p class="focus-source">${esc(TW.srcOf(w.type, p))}</p>` : "")
            : `<p class="focus-source">From the thermo team's ${esc(d.model || "")} model · outputs pre-computed by standin/precompute_models.py</p>`}
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
  out.addEventListener("click", e => { if (e.target.closest("a")) return;                       // links inside a box (ask next) just navigate
    const el = e.target.closest(".widget.sketch"); if (el) openFocus(+el.dataset.i); });
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
    const charts = (a.widgets || []).filter(w => W.def(w.type) && !W.isText(w.type));
    draw(TW.assemble(a, charts, { live, question: q, error: a.meta && a.meta.error }), `<h1>${esc(a.title || q)}</h1>${live ? "" : `<span class="tag-mock">mock</span>`}`, TILER.hash(q + "|" + (who || "")));
  }
  function library() {
    closeFocus();
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
