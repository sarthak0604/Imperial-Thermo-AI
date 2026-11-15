// APP — routing and the ask flow.
// #            home: the flame, one question, the ask box
// #q=…&p=…&s=… an answer (p = persona, s = environment); reopened from the sidebar's Recent instantly, without asking again
// #library     every thermo-model widget · #experiments  the 26 NASA PSI investigations
// Written with SI assistance (Claude, Anthropic).
(() => {
  const { esc } = U, ic = (...a) => UI.ic(...a), $ = s => document.querySelector(s);
  UI.init();
  const form = $("#ask-form"), ta = form.elements.q, home = $("#home"), ansEl = $("#answer"), page = $("#page"), dock = $("#dock"), acts = $("#acts-top");
  const PERS = ["student", "professor", "engineer"], vp = p => PERS.includes(p) ? p : null, ve = s => UI.ENVS.some(e => e.v === s) ? s : "iss";
  let view = null, M = null, boxes = [], pageBoxes = [], stopReveal = null, ctrl = null, seq = 0, flame = null, tflame = null, routeKey = null, timers = [];

  // links that widgets and text boxes make (an experiment, a model, a question) become new questions
  U.askHref = q => UI.href(q, UI.persona(), UI.env());
  U.invHref = id => U.askHref(`Everything about ${U.invLabel(U.inv(id))} (${id})`);
  U.modelHref = id => U.askHref(`Thermo model ${id}`);

  const SUGG = ["Can fabric catch fire in a lunar habitat?", "Why is a flame in microgravity a sphere?", "How does helium change how a fire behaves?", "How well does the droplet model match NASA's data?"];
  $("#sugg").innerHTML = SUGG.map(q => `<button type="button" class="chip" data-q="${esc(q)}">${esc(q)}</button>`).join("");

  // ---------- views ----------
  function show(v) {
    view = v; home.hidden = v !== "home"; ansEl.hidden = v !== "answer"; page.hidden = v !== "library" && v !== "experiments"; dock.hidden = v === "home";
    (v === "home" ? $("#home-slot") : $("#dock-slot")).appendChild(form);
    acts.hidden = !(v === "answer" && M);
    UI.setRoute(v === "library" || v === "experiments" ? v : null);
    if (v === "home" && !flame) flame = FLAME.mount($("#flame"), { R: 30, n: 90 });
    if (stopReveal && v !== "answer") { stopReveal(); stopReveal = null; }
    document.body.classList.toggle("on-home", v === "home");
  }
  function clearTimers() { timers.forEach(clearTimeout); timers = []; }
  function stopThinking() { document.body.classList.remove("thinking"); BG.thinking(false); if (flame) flame.think(false); if (tflame) { tflame.stop(); tflame = null; } clearTimers(); }

  function goHome() {
    abort(); stopThinking(); M = null; show("home"); ta.value = ""; autosize(); UI.setActive(null);
    document.title = "Flame in Freefall"; ansEl.innerHTML = "";
  }

  // ---------- asking ----------
  function abort() { if (ctrl) { ctrl.abort(); ctrl = null; } }
  function go(q, o = {}) {
    const p = o.p !== undefined ? o.p : UI.persona(), s = o.s || UI.env(), href = UI.href(q, p, s);
    if (location.hash !== href) history.pushState(null, "", href);
    routeKey = href;
    open(q, p, s, { fresh: true, history: o.history || [] });
  }
  function open(q, p, s, o = {}) {
    EXPAND.close();
    const saved = !o.fresh && UI.find(q, p, s);
    if (saved) return render(saved.a, { q, p, s, at: saved.t, cached: true });
    return ask(q, p, s, o.history || []);
  }
  async function ask(q, p, s, hist) {
    abort(); stopThinking(); const my = ++seq; M = null; show("answer");
    window.scrollTo(0, 0); ta.value = ""; autosize(); UI.setActive(q, p, s);
    document.title = `${q} · Flame in Freefall`;
    ansEl.innerHTML = `<div class="qrow"><div class="bub">${esc(q)}<small>${esc(ANS.forWho({ p, s }))}</small></div></div>${ANS.thinkingHTML({ p })}<div class="res"></div>`;
    document.body.classList.add("thinking"); BG.thinking(true);
    tflame = FLAME.mount(ansEl.querySelector(".tflame"), { R: 7, n: 48, lean: false, dotScale: .75, seed: 3 }); tflame.think(true);
    const lis = [...ansEl.querySelectorAll(".steps li")], mark = i => lis.forEach((d, j) => d.className = j < i ? "done" : j === i ? "on" : "");
    mark(0); for (let i = 1; i <= lis.length - 2; i++) timers.push(setTimeout(() => mark(i), i * 950));
    ctrl = new AbortController(); const t0 = performance.now();
    const a = await API.ask({ question: q, persona: p || "general", scenario: s, history: hist, signal: ctrl.signal });
    if (my !== seq) return;
    ctrl = null;
    if (a.meta && a.meta.aborted) return stopped(q, p, s);
    clearTimers(); mark(lis.length - 1);
    timers.push(setTimeout(() => {
      if (my !== seq) return;
      mark(lis.length);
      const secs = a.meta && a.meta.seconds ? a.meta.seconds : Math.round((performance.now() - t0) / 100) / 10;
      render(a, { q, p, s, at: Date.now(), secs });
    }, 420));
  }
  function stopped(q, p, s) {
    stopThinking();
    const th = ansEl.querySelector(".think"); if (th) th.outerHTML = `<div class="think done"><div class="th-h"><span class="done-line">Stopped before the answer arrived.</span></div></div>`;
    ansEl.querySelector(".res").innerHTML = `<div class="fups"><button type="button" class="chip" data-again>${ic("refresh")}Ask again</button></div>`;
    ta.value = q; autosize(); ta.focus();
  }

  // ---------- the answer page ----------
  function render(a, ctx) {
    stopThinking(); if (stopReveal) stopReveal();
    M = ANS.build(a, ctx);
    const r = ANS.render(M); boxes = r.boxes;
    show("answer");
    if (ctx.cached) {
      ansEl.innerHTML = `<div class="qrow"><div class="bub">${esc(M.q)}<small>${esc(ANS.forWho(M))}</small></div></div>
        <div class="think done"><div class="th-h"><span class="done-line">Saved answer from ${esc(new Date(M.at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }))}</span><button type="button" class="tg" data-again>${ic("refresh")}Ask again</button></div></div><div class="res"></div>`;
      window.scrollTo(0, 0);
    } else {
      const th = ansEl.querySelector(".think");
      if (th) {
        const m = M.meta || {}, n = M.refs.length;
        const line = `${M.live ? "Answered" : "Preview ready"} in ${ctx.secs || "?"} s${M.live && m.provider ? ` · ${m.provider}${m.model ? " / " + m.model : ""}` : ""} · ${n} source${n === 1 ? "" : "s"} checked`;
        th.classList.add("done", "collapsed");
        th.querySelector(".th-h").innerHTML = `<span class="done-line">${esc(line)}</span><button type="button" class="tg" aria-expanded="false" data-steps>Show steps${ic("chev")}</button>`;
        th.querySelectorAll(".steps li").forEach(li => li.className = "done");
      }
    }
    const res = ansEl.querySelector(".res");
    res.innerHTML = r.html;
    const dur = ANS.stream(res.querySelector("[data-stream]"));
    stopReveal = ANS.reveal(res, ctx.cached ? 0 : Math.min(520, dur * .3));
    acts.hidden = false; UI.setActive(M.q, M.p, M.s);
    document.title = `${M.title} · Flame in Freefall`;
    if (!ctx.cached && !(a.meta && a.meta.aborted)) UI.save({ id: String(Date.now()), q: M.q, p: M.p, s: M.s, t: M.at, a });
  }

  // ---------- library and experiments ----------
  function library() {
    abort(); stopThinking(); M = null; show("library"); window.scrollTo(0, 0); document.title = "Widget library · Flame in Freefall";
    const types = MW.types(), cats = [...new Set(types.map(t => W.def(t).cat))];
    pageBoxes = types.map(t => ({ kind: "chart", c: { type: t } }));
    page.innerHTML = `<div class="page-h"><div><h1>Widget library</h1><p>All ${types.length} charts built from the thermo team's models. Open one to use it: its sliders, dropdowns and readouts are live.</p></div><span class="sp"></span>
      <div class="seg" role="group" aria-label="Show">${["all", ...cats].map(c => `<button type="button" data-cat="${c}" aria-pressed="${c === "all"}">${c === "all" ? "All" : c.charAt(0).toUpperCase() + c.slice(1)}</button>`).join("")}</div></div>
      <div class="grid">${types.map((t, i) => ANS.chartBoxHTML({ type: t }, i, "s4").replace('class="box', `data-cat="${W.def(t).cat}" class="box`)).join("")}</div>`;
    stopReveal = ANS.reveal(page);
  }
  function experiments() {
    abort(); stopThinking(); M = null; show("experiments"); window.scrollTo(0, 0); document.title = "NASA experiments · Flame in Freefall";
    const inv = [...DATA.investigations].sort((a, b) => (!!b.acronym - !!a.acronym) || String(a.acronym || a.id).localeCompare(String(b.acronym || b.id)));
    pageBoxes = inv.map(i => ({ kind: "exp", e: { psi: i.id } }));
    page.innerHTML = `<div class="page-h"><div><h1>NASA experiments</h1><p>The ${inv.length} microgravity combustion investigations from NASA's Physical Sciences Informatics database that the answers draw on.</p></div><span class="sp"></span>
      <label class="side-search" style="width:min(280px,100%);padding:0"><span class="visually-hidden">Filter experiments</span><input type="search" id="exp-filter" placeholder="Filter experiments" autocomplete="off"></label></div>
      <div class="grid">${inv.map((i, k) => ANS.expHTML({ psi: i.id }, k, "s4")).join("")}</div>`;
    page.querySelector("#exp-filter").addEventListener("input", e => { const f = e.target.value.toLowerCase(); page.querySelectorAll(".box").forEach((b, k) => { const i = inv[k]; b.hidden = !!f && ![i.id, i.acronym, i.title, i.keywords, i.platform].join(" ").toLowerCase().includes(f); }); });
    stopReveal = ANS.reveal(page);
  }

  // ---------- routing ----------
  function route() {
    const key = location.hash; if (key === routeKey && view) return; routeKey = key;
    EXPAND.close();
    if (key === "#library") return library();
    if (key === "#experiments") return experiments();
    const hp = new URLSearchParams(key.replace(/^#/, "")), q = (hp.get("q") || "").trim();
    if (!q) return goHome();
    const p = vp(hp.get("p")), s = ve(hp.get("s"));
    if (p !== UI.persona()) UI.setPersona(p);
    open(q, p, s);
  }
  addEventListener("hashchange", route);
  addEventListener("popstate", route);

  // ---------- the ask box ----------
  function autosize() { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 168) + "px"; }
  ta.addEventListener("input", autosize);
  ta.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { cancelable: true })); } });
  form.addEventListener("submit", e => {
    e.preventDefault();
    if (document.body.classList.contains("thinking")) { const q = (M && M.q) || ansEl.querySelector(".bub")?.firstChild?.textContent || ""; abort(); ++seq; stopped(q); return; }
    const q = ta.value.trim(); if (!q) { ta.focus(); return; }
    go(q, { history: view === "answer" && M && M.summary ? [{ q: M.q, a: M.summary }] : [] });
  });

  // ---------- clicks ----------
  function openBox(el) {
    const i = +el.dataset.box, list = view === "answer" ? boxes : pageBoxes, b = list[i]; if (!b) return;
    const sp = EXPAND.spec(b, view === "answer" ? M : null); if (sp) EXPAND.open(el, sp);
  }
  function toRef(n) {
    const go2 = () => { const li = document.getElementById("ref-" + n); if (!li) return;
      li.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
      li.classList.add("flash"); setTimeout(() => li.classList.remove("flash"), 1400); };
    EXPAND.isOpen() ? EXPAND.close(go2) : go2();
  }
  document.addEventListener("click", e => {
    const t = e.target;
    const ref = t.closest("[data-ref]"); if (ref) { e.preventDefault(); return toRef(ref.dataset.ref); }
    const q = t.closest("[data-q]"); if (q) { ta.value = q.dataset.q; return go(q.dataset.q); }
    const fu = t.closest("[data-followup]"); if (fu) { e.preventDefault(); return go(fu.textContent.trim(), { history: M && M.summary ? [{ q: M.q, a: M.summary }] : [] }); }
    const ak = t.closest("[data-ask]"); if (ak) { const qq = ak.dataset.ask; return EXPAND.close(() => go(qq)); }
    if (t.closest("[data-home]")) { e.preventDefault(); if (location.hash) history.pushState(null, "", location.pathname + location.search); routeKey = ""; goHome(); ta.focus(); return; }
    if (t.closest("[data-again]")) { const qq = (M && M.q) || ta.value.trim(); if (qq) go(qq); return; }
    const act = t.closest("[data-act]");
    if (act && M) {
      if (act.dataset.act === "copy") UI.copy(ANS.text(M)).then(ok => { const c = act.parentElement.querySelector(".cpm"); if (c) { c.textContent = ok ? "Copied" : "Copy failed"; setTimeout(() => c.textContent = "", 1600); } });
      if (act.dataset.act === "again") go(M.q);
      return;
    }
    const op = t.closest("[data-open]"); if (op) { const el = op.closest(".box"); if (el) { const sp = EXPAND.spec(boxes[+op.dataset.open], M); EXPAND.open(el, sp); } return; }
    const st = t.closest("[data-steps]"); if (st) { const th = st.closest(".think"), o = st.getAttribute("aria-expanded") !== "true"; st.setAttribute("aria-expanded", String(o)); st.firstChild.textContent = o ? "Hide steps" : "Show steps"; th.classList.toggle("collapsed", !o); return; }
    const sh = t.closest("[data-share]"); if (sh && M) { UI.closeMenus(); return share(sh.dataset.share); }
    if (t.closest("[data-pdf]") && M) { UI.closeMenus(); REPORT.download(M).catch(err => { console.error(err); UI.toast("Couldn't make the PDF: " + err.message); }); return; }
    const cat = t.closest("[data-cat]:not(.box)"); if (cat) { page.querySelectorAll("[data-cat]:not(.box)").forEach(b => b.setAttribute("aria-pressed", String(b === cat))); page.querySelectorAll(".box").forEach(b => b.hidden = cat.dataset.cat !== "all" && b.dataset.cat !== cat.dataset.cat); return; }
    const fc = t.closest(".fcell[data-box]"); if (fc) return openBox(fc);
    const box = t.closest(".box[data-box]");
    if (box && !t.closest("a, button, input, select, textarea, label") && box.closest("#answer, #page")) { if (box.classList.contains("ov") && !t.closest("h1, .sum")) return; openBox(box); }
  });
  document.addEventListener("keydown", e => {
    const box = e.target.closest && e.target.closest(".box[data-box][role=button]");
    if (box && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openBox(box); }
    if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(e.target.tagName) && !EXPAND.isOpen()) { e.preventDefault(); ta.focus(); }
  });
  async function share(kind) {
    const url = location.href.split("#")[0] + UI.href(M.q, M.p, M.s);
    if (kind === "link") { UI.toast(await UI.copy(url) ? "Link copied" : "Couldn't copy the link"); }
    if (kind === "native") { try { await navigator.share({ title: `${M.title} · Flame in Freefall`, text: ANS.plain(M.summary || M.q).slice(0, 240), url }); } catch (e) {} }
    if (kind === "text") { UI.toast(await UI.copy(ANS.text(M) + "\n\n" + url) ? "Answer copied as text" : "Couldn't copy"); }
  }
  addEventListener("scroll", () => document.body.classList.toggle("scrolled", scrollY > 6), { passive: true });
  UI.onTheme(() => { BG.redraw(); if (flame) flame.redraw(); });

  show("home");
  API.health().then(s => { UI.setStatus(s); route(); });
})();
