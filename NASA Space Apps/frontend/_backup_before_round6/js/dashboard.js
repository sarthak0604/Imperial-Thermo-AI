// APP — routing and the ask flow.
// #              home: the environment (or the flame, before one is chosen) and the prompt bar
// #q=…&p=…&s=…   an answer (p = persona, s = environment); reopened from Recent / All questions instantly
// #questions     All questions (folders, pins, rename) · #experiments  the 26 NASA PSI investigations
// #display       data display settings (#library still works and lands there)
//
// Asking: the question and its thinking steps sit in a tab just above the prompt bar; the centre shows the
// environment, thinking. When the answer lands, that tab shrinks to one line and the AI overview grows out of it
// to fill the screen; the findings follow below, with References and Method as closed drop-downs at the end.
// Written with SI assistance (Claude, Anthropic).
(() => {
  const { esc } = U, ic = (...a) => UI.ic(...a), $ = s => document.querySelector(s);
  const RM = matchMedia("(prefers-reduced-motion: reduce)").matches, NAME = "IMPER-ai-L";
  UI.init();
  const form = $("#ask-form"), ta = form.elements.q, home = $("#home"), ansEl = $("#answer"), page = $("#page"), dock = $("#dock"), acts = $("#acts-top"), qslot = $("#qtab-slot");
  const PERS = ["student", "professor", "engineer"], vp = p => PERS.includes(p) ? p : null, ve = s => UI.ENVS.some(e => e.v === s) ? s : "iss";
  const PAGES = { experiments: "NASA experiments", questions: "All questions", display: "Data display settings" };
  let view = null, M = null, cur = null, boxes = [], stopReveal = null, ctrl = null, seq = 0, flame = null, aflame = null, tflame = null, routeKey = null, timers = [], pending = null;

  // links that widgets and text boxes make (an experiment, a model, a question) become new questions
  U.askHref = q => UI.href(q, UI.persona(), (M && M.s) || UI.env() || "iss");
  U.invHref = id => U.askHref(`Everything about ${U.invLabel(U.inv(id))} (${id})`);
  U.modelHref = id => U.askHref(`Thermo model ${id}`);

  // ---------- the centre: the flame until an environment is chosen, then that environment ----------
  const envCap = $("#env-cap");
  function syncEnv() {
    const e = UI.env(), d = UI.ENVS.find(x => x.v === e);
    if (flame) flame.setGlyph(e || null);
    envCap.innerHTML = d ? `<b>${esc(d.label)}</b><span>${esc(d.d)}</span>` : `<span>Choose an environment to begin</span>`;
    envCap.classList.toggle("none", !d);
  }
  UI.onEnv((e, o) => {
    syncEnv();
    if (o && o.picked && pending) { const p = pending; pending = null; go(p.q, p.o); }
  });

  // ---------- views ----------
  function show(v) {
    view = v; home.hidden = v !== "home"; ansEl.hidden = v !== "answer"; page.hidden = !PAGES[v]; dock.hidden = v !== "answer";
    if (v === "home") $("#home-slot").appendChild(form); else if (v === "answer") $("#dock-slot").appendChild(form);
    form.classList.toggle("flat", v === "answer"); ta.placeholder = v === "answer" ? "Ask a follow-up, or anything new" : "Ask about any flame in microgravity"; autosize();
    acts.hidden = !(v === "answer" && M);
    UI.setRoute(PAGES[v] ? v : null);
    if (v === "home" && !flame) { flame = FLAME.mount($("#flame"), { R: 40, n: 100, glyph: UI.env() || null }); syncEnv(); }
    if (stopReveal && v !== "answer") { stopReveal(); stopReveal = null; }
    if (v !== "answer") qslot.innerHTML = "";
    document.body.classList.toggle("on-home", v === "home");
    document.body.dataset.view = v;
  }
  function clearTimers() { timers.forEach(clearTimeout); timers = []; }
  function stopThinking() {
    document.body.classList.remove("thinking"); BG.thinking(false);
    if (tflame) { tflame.stop(); tflame = null; } if (aflame) { aflame.stop(); aflame = null; } clearTimers();
  }
  function goHome() {
    abort(); stopThinking(); M = null; cur = null; pending = null; show("home"); ta.value = ""; autosize(); UI.setActive(null);
    document.title = NAME; ansEl.innerHTML = "";
  }

  // ---------- the question tab above the prompt bar ----------
  function setQtab(o) {
    if (tflame) { tflame.stop(); tflame = null; }
    qslot.innerHTML = ANS.qtab(o);
    const cv = qslot.querySelector(".tflame");
    if (cv) { tflame = FLAME.mount(cv, { R: 7, n: 48, lean: false, dotScale: .75, seed: 3 }); tflame.think(true); }
  }
  function threadFor(th, q, p, s) {
    const T = UI.thread(th);
    return T.some(h => h.q.trim().toLowerCase() === q.trim().toLowerCase()) ? T : [...T, { q, p, s, t: Date.now() }];
  }

  // ---------- asking ----------
  function abort() { if (ctrl) { ctrl.abort(); ctrl = null; } }
  function go(q, o = {}) {
    const s = o.s || UI.env();
    if (!s) {                                                     // an environment is needed first: ask for it, then go on
      pending = { q, o };
      if (view !== "answer" && view !== "home") { EXPAND.close(); history.pushState(null, "", location.pathname + location.search); routeKey = ""; abort(); stopThinking(); M = null; show("home"); }
      ta.value = q; autosize(); requestAnimationFrame(() => UI.askEnv()); return;
    }
    const p = o.p !== undefined ? o.p : UI.persona(), href = UI.href(q, p, s);
    if (location.hash !== href) history.pushState(null, "", href);
    routeKey = href;
    open(q, p, s, { fresh: true, history: o.history || [], th: o.th || null });
  }
  function open(q, p, s, o = {}) {
    EXPAND.close();
    const saved = !o.fresh && UI.find(q, p, s);
    if (saved) return render(saved.a, { q, p, s, at: saved.t, cached: true, th: saved.th || saved.id });
    return ask(q, p, s, o);
  }
  async function ask(q, p, s, o) {
    abort(); stopThinking(); const my = ++seq; M = null; cur = { q, p, s, th: o.th || null };
    show("answer"); window.scrollTo(0, 0); ta.value = ""; autosize(); UI.setActive(q, p, s);
    if (UI.env() !== s) UI.setEnv(s);
    document.title = `${q} · ${NAME}`;
    ansEl.innerHTML = `<div class="astage" aria-hidden="true"><canvas class="aflame"></canvas><p class="astage-cap"></p></div><div class="res"></div>`;
    setQtab({ q, p, s, state: "thinking", open: true, thread: o.th ? threadFor(o.th, q, p, s) : [] });
    document.body.classList.add("thinking"); BG.thinking(true);
    aflame = FLAME.mount(ansEl.querySelector(".aflame"), { R: 44, n: 120, glyph: s, seed: 11 }); aflame.think(true);
    const lis = [...qslot.querySelectorAll(".steps li")], cap = ansEl.querySelector(".astage-cap");
    const mark = i => { lis.forEach((d, j) => d.className = j < i ? "done" : j === i ? "on" : ""); if (lis[i]) cap.textContent = lis[i].textContent; };
    mark(0); for (let i = 1; i <= lis.length - 2; i++) timers.push(setTimeout(() => mark(i), i * 950));
    ctrl = new AbortController(); const t0 = performance.now();
    const a = await API.ask({ question: q, persona: p || "general", scenario: s, history: o.history || [], signal: ctrl.signal });
    if (my !== seq) return;
    ctrl = null;
    if (a.meta && a.meta.aborted) return stopped();
    clearTimers(); mark(lis.length - 1);
    timers.push(setTimeout(() => {
      if (my !== seq) return;
      mark(lis.length);
      const secs = a.meta && a.meta.seconds ? a.meta.seconds : Math.round((performance.now() - t0) / 100) / 10;
      render(a, { q, p, s, at: Date.now(), secs, th: o.th, grow: true });
    }, 420));
  }
  function stopped() {
    stopThinking();
    const c = cur || {};
    setQtab({ q: c.q || "", p: c.p, s: c.s, state: "stopped", line: "Stopped before the answer arrived", open: false, thread: c.th ? threadFor(c.th, c.q, c.p, c.s) : [] });
    const st = ansEl.querySelector(".astage"); if (st) st.classList.add("idle");
    const cp = ansEl.querySelector(".astage-cap"); if (cp) cp.textContent = "Stopped. Edit the question below, or ask again.";
    ta.value = c.q || ""; autosize(); ta.focus();
  }

  // ---------- the answer ----------
  function render(a, ctx) {
    stopThinking(); if (stopReveal) stopReveal();
    const from = ctx.grow && !RM ? qslot.querySelector(".qtab")?.getBoundingClientRect() : null;
    const id = String(Date.now());
    let th = ctx.th;
    if (!ctx.cached && !(a.meta && a.meta.aborted)) { th = th || id; UI.save({ id, q: ctx.q, p: ctx.p, s: ctx.s, t: ctx.at, a, th }); }
    M = ANS.build(a, ctx); M.th = th || null;
    cur = { q: M.q, p: M.p, s: M.s, th: M.th };
    const r = ANS.render(M); boxes = r.boxes;
    show("answer");
    if (UI.env() !== M.s) UI.setEnv(M.s);
    ansEl.innerHTML = `<div class="res">${r.html}</div>`;
    const m = M.meta || {}, n = M.refs.length;
    const line = ctx.cached ? `Saved answer · ${new Date(M.at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}`
      : `${M.live ? "Answered" : "Preview ready"} in ${ctx.secs || "?"} s${M.live && m.provider ? ` · ${m.provider}${m.model ? " / " + m.model : ""}` : ""} · ${n} source${n === 1 ? "" : "s"}`;
    setQtab({ q: M.q, p: M.p, s: M.s, state: ctx.cached ? "cached" : "done", line, open: false, thread: M.th ? UI.thread(M.th) : [] });
    if (ctx.cached) window.scrollTo(0, 0);
    const res = ansEl.querySelector(".res"), ov = res.querySelector(".box.ov");
    const start = () => { const dur = ANS.stream(res.querySelector("[data-stream]")); stopReveal = ANS.reveal(res, ctx.cached ? 0 : Math.min(520, dur * .3)); };
    if (from && ov) grow(from, ov, start); else start();
    acts.hidden = false; UI.setActive(M.q, M.p, M.s);
    document.title = `${M.title} · ${NAME}`;
  }
  // the thinking tab grows into the AI overview: a plain panel moves from the tab to the overview's place, then the overview fades in
  function grow(from, ov, then) {
    ov.classList.remove("rv"); ov.classList.add("growing");
    const to = ov.getBoundingClientRect(), g = document.createElement("div"); g.className = "grow-ghost"; document.body.appendChild(g);
    const geo = r => ({ left: r.left + "px", top: r.top + "px", width: r.width + "px", height: Math.min(r.height, innerHeight * 1.2) + "px" });
    const done = () => { ov.classList.remove("growing"); g.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 240, easing: "ease-out", fill: "forwards" }).onfinish = () => g.remove(); then(); };
    g.animate([{ ...geo(from), opacity: .85, borderRadius: "16px" }, { ...geo(to), opacity: 1, borderRadius: "16px" }], { duration: 560, easing: "cubic-bezier(.2,.8,.2,1)", fill: "forwards" }).onfinish = done;
  }

  // ---------- management pages ----------
  function managePage(k) {
    abort(); stopThinking(); M = null; cur = null; show(k); window.scrollTo(0, 0); document.title = `${PAGES[k]} · ${NAME}`;
    page.innerHTML = ""; page.onclick = null;
    MANAGE[k](page);
  }

  // ---------- routing ----------
  function route() {
    let key = location.hash; if (key === routeKey && view) return; routeKey = key;
    EXPAND.close();
    if (key === "#library") { history.replaceState(null, "", "#display"); key = routeKey = "#display"; }
    const pg = key.replace(/^#/, ""); if (PAGES[pg]) return managePage(pg);
    const hp = new URLSearchParams(key.replace(/^#/, "")), q = (hp.get("q") || "").trim();
    if (!q) return goHome();
    const p = vp(hp.get("p")), s = ve(hp.get("s"));
    if (p !== UI.persona()) UI.setPersona(p);
    open(q, p, s);
  }
  addEventListener("hashchange", route);
  addEventListener("popstate", route);

  // ---------- the prompt bar ----------
  function autosize() { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, form.classList.contains("flat") ? 120 : 168) + "px"; }
  ta.addEventListener("input", autosize);
  ta.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { cancelable: true })); } });
  form.addEventListener("submit", e => {
    e.preventDefault();
    if (document.body.classList.contains("thinking")) { abort(); ++seq; stopped(); return; }
    const q = ta.value.trim(); if (!q) { ta.focus(); return; }
    go(q, view === "answer" && M ? { history: M.summary ? [{ q: M.q, a: M.summary }] : [], th: M.th } : {});
  });
  new ResizeObserver(() => document.documentElement.style.setProperty("--dockh", dock.offsetHeight + "px")).observe(dock);

  // ---------- clicks ----------
  function openBox(el) {
    const b = boxes[+el.dataset.box]; if (!b || view !== "answer") return;
    const sp = EXPAND.spec(b, M); if (sp) EXPAND.open(el, sp);
  }
  const smooth = () => matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
  function toRef(n) {
    const go2 = () => { const d = document.getElementById("references"); if (d) d.open = true;
      const li = document.getElementById("ref-" + n); if (!li) return;
      li.scrollIntoView({ behavior: smooth(), block: "center" });
      li.classList.add("flash"); setTimeout(() => li.classList.remove("flash"), 1400); };
    EXPAND.isOpen() ? EXPAND.close(go2) : go2();
  }
  function goTo(id) {
    const el = document.getElementById(id); if (!el) return;
    el.classList.add("in"); el.scrollIntoView({ behavior: smooth(), block: "start" });
    el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1300);
  }
  const followCtx = () => M ? { history: M.summary ? [{ q: M.q, a: M.summary }] : [], th: M.th, p: M.p, s: M.s } : {};
  document.addEventListener("click", e => {
    const t = e.target;
    const ref = t.closest("[data-ref]"); if (ref) { e.preventDefault(); return toRef(ref.dataset.ref); }
    const gt = t.closest("[data-goto]"); if (gt) { e.preventDefault(); return goTo(gt.dataset.goto); }
    const q = t.closest("[data-q]"); if (q) { ta.value = q.dataset.q; return go(q.dataset.q); }
    const fu = t.closest("[data-followup]"); if (fu) { e.preventDefault(); const qq = fu.textContent.trim(), c = followCtx(); return EXPAND.close(() => go(qq, c)); }
    const ak = t.closest("[data-ask]"); if (ak) { const qq = ak.dataset.ask; return EXPAND.close(() => go(qq, M ? { p: M.p, s: M.s } : {})); }
    if (t.closest("[data-home]")) { e.preventDefault(); if (location.hash) history.pushState(null, "", location.pathname + location.search); routeKey = ""; goHome(); ta.focus(); return; }
    if (t.closest("[data-again]")) { const c = M || cur; if (c && c.q) go(c.q, { p: c.p, s: c.s, th: c.th }); return; }
    const qt = t.closest("[data-qtab]"); if (qt) { const tab = qt.closest(".qtab"), o = !tab.classList.contains("open"); tab.classList.toggle("open", o); qt.setAttribute("aria-expanded", String(o)); return; }
    const act = t.closest("[data-act]");
    if (act && M) {
      if (act.dataset.act === "copy") UI.copy(ANS.text(M)).then(ok => { const c = act.parentElement.querySelector(".cpm"); if (c) { c.textContent = ok ? "Copied" : "Copy failed"; setTimeout(() => c.textContent = "", 1600); } });
      if (act.dataset.act === "again") go(M.q, { p: M.p, s: M.s, th: M.th });
      return;
    }
    const sh = t.closest("[data-share]"); if (sh && M) { UI.closeMenus(); return share(sh.dataset.share); }
    if (t.closest("[data-pdf]") && M) { UI.closeMenus(); REPORT.download(M).catch(err => { console.error(err); UI.toast("Couldn't make the PDF: " + err.message); }); return; }
    const fc = t.closest(".fcell[data-box]"); if (fc) return openBox(fc);
    const box = t.closest(".box[data-box]");
    if (box && box.closest("#answer") && !t.closest("a, button, input, select, textarea, label, summary")) openBox(box);
  });
  document.addEventListener("keydown", e => {
    const box = e.target.closest && e.target.closest(".box[data-box][role=button]");
    if (box && e.target === box && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openBox(box); }
    if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(e.target.tagName) && !EXPAND.isOpen()) { e.preventDefault(); ta.focus(); }
  });
  async function share(kind) {
    const url = location.href.split("#")[0] + UI.href(M.q, M.p, M.s);
    if (kind === "link") { UI.toast(await UI.copy(url) ? "Link copied" : "Couldn't copy the link"); }
    if (kind === "native") { try { await navigator.share({ title: `${M.title} · ${NAME}`, text: ANS.plain(M.summary || M.q).slice(0, 240), url }); } catch (e) {} }
    if (kind === "text") { UI.toast(await UI.copy(ANS.text(M) + "\n\n" + url) ? "Answer copied as text" : "Couldn't copy"); }
  }
  addEventListener("scroll", () => document.body.classList.toggle("scrolled", scrollY > 6), { passive: true });
  UI.onTheme(() => { BG.redraw(); if (flame) flame.redraw(); if (aflame) aflame.redraw(); });

  show("home");
  API.health().then(s => { UI.setStatus(s); route(); });
})();
