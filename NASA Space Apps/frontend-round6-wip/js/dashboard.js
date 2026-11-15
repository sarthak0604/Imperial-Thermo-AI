// APP — routing and the ask flow.
// #              home: the environment (or the flame, before one is chosen) and the prompt bar
// #q=…&p=…&s=…   an answer (p = persona, s = environment); reopened from Recent / All questions instantly
// #questions     All questions (folders, pins, rename) · #experiments  the 26 NASA PSI investigations
// #display       data display settings (#library still works and lands there)
//
// Asking: the prompt bar glides down into the dock and the rocket on the send button lifts off into the question tab
// above it, then climbs the tab's rail as each step is done (the pipeline really runs: it reads the question, picks the
// NASA data and models, and draws the figures). When the answer is ready the rocket leaves the top and the tab grows
// to fill the screen as the overview: the only thing on the page. Clicking it opens the full answer in a focus window.
// Written with SI assistance (Claude, Anthropic).
(() => {
  const { esc } = U, ic = (...a) => UI.ic(...a), $ = s => document.querySelector(s);
  const RM = matchMedia("(prefers-reduced-motion: reduce)").matches, NAME = "IMPER-ai-L";
  const EASE = "cubic-bezier(.2,.8,.2,1)";
  UI.init();
  const form = $("#ask-form"), ta = form.elements.q, home = $("#home"), ansEl = $("#answer"), page = $("#page"), dock = $("#dock"), acts = $("#acts-top"), qslot = $("#qtab-slot"), send = form.querySelector(".send");
  const PERS = ["student", "professor", "engineer"], vp = p => PERS.includes(p) ? p : null, ve = s => UI.ENVS.some(e => e.v === s) ? s : "iss";
  const PAGES = { experiments: "NASA experiments", questions: "All questions", display: "Data display settings" };
  let view = null, M = null, cur = null, boxes = [], stopReveal = null, ctrl = null, seq = 0, flame = null, aflame = null, tflame = null, routeKey = null, timers = [], pending = null;

  // links that widgets and text boxes make (an experiment, a model, a question) become new questions
  U.askHref = q => UI.href(q, UI.persona(), (M && M.s) || UI.env() || "iss");
  U.invHref = id => U.askHref(`Everything about ${U.invLabel(U.inv(id))} (${id})`);
  U.modelHref = id => U.askHref(`Thermo model ${id}`);

  // ---------- the centre: the flame until an environment is chosen, then that environment ----------
  const envCap = $("#env-cap");
  let capSet = false;
  function syncEnv() {
    const e = UI.env(), d = UI.ENVS.find(x => x.v === e);
    if (flame) flame.setGlyph(e || null);
    const html = d ? `<b>${esc(d.label)}</b><span>${esc(d.d)}</span>` : `<span>Choose an environment to begin</span>`;
    const put = () => { envCap.innerHTML = html; envCap.classList.toggle("none", !d); };
    if (!capSet || RM || view !== "home") { put(); capSet = true; return; }
    // the caption sinks with the drawing and rises with the new one
    envCap.getAnimations().forEach(a => a.cancel());
    envCap.animate([{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateY(8px)" }], { duration: 300, easing: "cubic-bezier(.5,0,.75,0)", fill: "forwards" }).onfinish = () => {
      put(); envCap.animate([{ opacity: 0, transform: "translateY(10px)" }, { opacity: 1, transform: "none" }], { duration: 520, delay: 120, easing: "cubic-bezier(.2,1.25,.4,1)", fill: "forwards" });
    };
  }
  UI.onEnv((e, o) => {
    syncEnv();
    if (o && o.picked && pending) { const p = pending; pending = null; go(p.q, p.o); }
  });

  // ---------- views ----------
  function show(v) {
    const prev = view, r0 = !RM && prev && prev !== v && (v === "home" || v === "answer") ? form.getBoundingClientRect() : null;
    view = v; home.hidden = v !== "home"; ansEl.hidden = v !== "answer"; page.hidden = !PAGES[v]; dock.hidden = v !== "answer";
    if (v === "home") $("#home-slot").appendChild(form); else if (v === "answer") $("#dock-slot").appendChild(form);
    form.classList.toggle("flat", v === "answer"); ta.placeholder = v === "answer" ? "Ask a follow-up, or anything new" : "Ask about any flame in microgravity"; autosize();
    acts.hidden = !(v === "answer" && M);
    UI.setRoute(PAGES[v] ? v : null);
    if (v === "home" && !flame) { flame = FLAME.mount($("#flame"), { R: 40, n: 100, glyph: UI.env() || null, cy: () => $(".flame-stage").clientHeight / 2, sink: form }); syncEnv(); }
    if (v === "home") fitStage();
    if (stopReveal && v !== "answer") { stopReveal(); stopReveal = null; }
    if (v !== "answer") qslot.innerHTML = "";
    document.body.classList.toggle("on-home", v === "home");
    document.body.dataset.view = v;
    // the prompt bar glides between the middle of the home screen and the dock
    if (r0 && r0.width && (prev === "home" || prev === "answer")) {
      const r1 = form.getBoundingClientRect(), dx = r0.left - r1.left, dy = r0.top - r1.top;
      if (Math.abs(dx) + Math.abs(dy) > 2) form.animate([{ transform: `translate(${dx}px,${dy}px)` }, { transform: "none" }], { duration: 620, easing: EASE });
    }
    if (PAGES[v] && prev !== v) page.animate([{ opacity: 0, transform: "translateY(8px)" }, { opacity: 1, transform: "none" }], { duration: 420, easing: EASE });
  }
  // the home drawing's canvas reaches down behind the prompt bar, so it can sink into it
  function fitStage() {
    const st = $(".flame-stage"); if (!st || home.hidden) return;
    const ext = form.getBoundingClientRect().bottom - st.getBoundingClientRect().bottom;
    st.style.setProperty("--ext", Math.max(0, Math.round(ext + 6)) + "px");
  }
  addEventListener("resize", fitStage);
  function clearTimers() { timers.forEach(clearTimeout); timers = []; }
  function stopThinking() {
    document.body.classList.remove("thinking"); BG.thinking(false);
    if (tflame) { tflame.stop(); tflame = null; } if (aflame) { aflame.stop(); aflame = null; } clearTimers();
    document.querySelectorAll(".rk-fly").forEach(f => f.remove());
  }
  function goHome() {
    abort(); stopThinking(); M = null; cur = null; pending = null;
    EXPAND.closeAll(); show("home"); ta.value = ""; autosize(); UI.setActive(null);
    document.title = NAME; ansEl.innerHTML = ""; landRocket();
  }

  // ---------- the question tab above the prompt bar, and the rocket ----------
  function setQtab(o) {
    if (tflame) { tflame.stop(); tflame = null; }
    qslot.innerHTML = ANS.qtab(o);
    const cv = qslot.querySelector(".tflame");
    if (cv) { tflame = FLAME.mount(cv, { R: 7, n: 48, lean: false, dotScale: .75, seed: 3 }); tflame.think(true); }
    placeRail();
  }
  // the rail sits exactly above the send button, so the rocket flies straight up into it
  function placeRail() {
    const tab = qslot.querySelector(".qtab"), rail = tab && tab.querySelector(".rail"); if (!rail) return;
    const t = tab.getBoundingClientRect(), b = send.getBoundingClientRect();
    if (b.width) rail.style.right = Math.max(8, Math.round(t.right - (b.left + b.width / 2) - 1 - rail.offsetWidth / 2)) + "px";
  }
  const railEl = () => qslot.querySelector(".rail");
  function rocketTo(i, n) {                             // step i of n (0 = bottom row)
    const rail = railEl(); if (!rail) return;
    const lis = rail.parentElement.querySelectorAll(".rk-steps li"), li = lis[Math.min(i, lis.length - 1)];
    const y = li ? rail.getBoundingClientRect().bottom - (li.getBoundingClientRect().top + li.offsetHeight / 2) : 0;
    rail.style.setProperty("--y", Math.max(0, Math.round(y)) + "px");
  }
  function launchRocket(delay) {
    send.classList.remove("land"); send.classList.add("gone");
    const b = send.getBoundingClientRect();
    if (RM || !b.width) { const r = railEl(); if (r) r.classList.add("on"); return; }
    const fly = document.createElement("span"); fly.className = "rk-fly"; fly.innerHTML = UI.rocket(); document.body.appendChild(fly);
    Object.assign(fly.style, { left: b.left + b.width / 2 + "px", top: b.top + b.height / 2 + "px", opacity: 0 });
    timers.push(setTimeout(() => {
      const rail = railEl(); if (!rail) { fly.remove(); return; }
      const s0 = send.getBoundingClientRect(), rr = rail.querySelector(".rk-r").getBoundingClientRect();
      const x0 = s0.left + s0.width / 2, y0 = s0.top + s0.height / 2, x1 = rr.left + rr.width / 2, y1 = rr.top + rr.height / 2;
      Object.assign(fly.style, { left: x0 + "px", top: y0 + "px", opacity: 1 });
      fly.animate([{ transform: "translate(-50%,-50%) scale(1)", offset: 0 }, { transform: `translate(calc(-50% + ${(x1 - x0) * .2}px), calc(-50% + ${(y1 - y0) * .35 + 6}px)) scale(1.06)`, offset: .3 },
        { transform: `translate(calc(-50% + ${x1 - x0}px), calc(-50% + ${y1 - y0}px)) scale(1)`, offset: 1 }], { duration: 640, easing: "cubic-bezier(.45,.05,.25,1)", fill: "forwards" })
        .onfinish = () => { rail.classList.add("on"); fly.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 120, fill: "forwards" }).onfinish = () => fly.remove(); };
    }, delay));
  }
  function exitRocket(then) {
    const rail = railEl();
    if (!rail || RM) { then(); return; }
    rail.classList.add("on", "out"); rail.style.setProperty("--y", rail.offsetHeight + 52 + "px");
    timers.push(setTimeout(then, 440));
  }
  function landRocket() { send.classList.remove("gone"); if (!RM) { send.classList.remove("land"); void send.offsetWidth; send.classList.add("land"); } }
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
      if (view !== "answer" && view !== "home") { EXPAND.closeAll(); history.pushState(null, "", location.pathname + location.search); routeKey = ""; abort(); stopThinking(); M = null; show("home"); }
      ta.value = q; autosize(); requestAnimationFrame(() => UI.askEnv()); return;
    }
    const p = o.p !== undefined ? o.p : UI.persona(), href = UI.href(q, p, s);
    if (location.hash !== href) history.pushState(null, "", href);
    routeKey = href;
    open(q, p, s, { fresh: true, history: o.history || [], th: o.th || null });
  }
  function open(q, p, s, o = {}) {
    EXPAND.closeAll();
    const saved = !o.fresh && UI.find(q, p, s);
    if (saved) return render(saved.a, { q, p, s, at: saved.t, cached: true, th: saved.th || saved.id });
    return ask(q, p, s, o);
  }
  async function ask(q, p, s, o) {
    abort(); stopThinking(); const my = ++seq; M = null; cur = { q, p, s, th: o.th || null };
    const fromHome = view === "home";
    const run = PIPE.run(q, p, s);                                       // the real first steps: parse, plan, run the models
    show("answer"); window.scrollTo(0, 0); ta.value = ""; autosize(); UI.setActive(q, p, s);
    if (UI.env() !== s) UI.setEnv(s);
    document.title = `${q} · ${NAME}`;
    ansEl.innerHTML = `<div class="astage" aria-hidden="true"><canvas class="aflame"></canvas><p class="astage-cap"></p></div>`;
    setQtab({ q, p, s, state: "thinking", open: true, thread: o.th ? threadFor(o.th, q, p, s) : [], thinking: run.thinking });
    if (fromHome && !RM) qslot.querySelector(".qtab").style.animationDelay = ".26s";
    document.body.classList.add("thinking"); BG.thinking(true);
    aflame = FLAME.mount(ansEl.querySelector(".aflame"), { R: 44, n: 120, glyph: s, seed: 11 }); aflame.think(true);
    const lis = [...qslot.querySelectorAll(".rk-steps li")], cap = ansEl.querySelector(".astage-cap"), N = lis.length;
    const mark = i => { lis.forEach((d, j) => d.className = j < i ? "done" : j === i ? "on" : ""); if (lis[i]) cap.textContent = lis[i].textContent; rocketTo(Math.min(i, N - 1), N); };
    mark(0); launchRocket(fromHome ? 560 : 120);
    for (let i = 1; i <= N - 2; i++) timers.push(setTimeout(() => mark(i), 300 + i * 520));
    ctrl = new AbortController(); const t0 = performance.now();
    const a = await API.ask({ question: q, persona: p || "general", scenario: s, history: o.history || [], signal: ctrl.signal, run });
    if (my !== seq) return;
    ctrl = null;
    if (a.meta && a.meta.aborted) return stopped();
    clearTimers(); mark(N - 1);
    timers.push(setTimeout(() => {
      if (my !== seq) return;
      mark(N);
      const secs = a.meta && a.meta.seconds ? a.meta.seconds : Math.round((performance.now() - t0) / 100) / 10;
      exitRocket(() => { if (my === seq) render(a, { q, p, s, at: Date.now(), secs, th: o.th, grow: true }); });
    }, 480));
  }
  function stopped() {
    stopThinking(); landRocket();
    const c = cur || {};
    setQtab({ q: c.q || "", p: c.p, s: c.s, state: "stopped", line: "Stopped before the answer arrived", open: false, thread: c.th ? threadFor(c.th, c.q, c.p, c.s) : [] });
    const st = ansEl.querySelector(".astage"); if (st) st.classList.add("idle");
    const cp = ansEl.querySelector(".astage-cap"); if (cp) cp.textContent = "Stopped. Edit the question below, or ask again.";
    ta.value = c.q || ""; autosize(); ta.focus();
  }

  // ---------- the answer: one overview widget ----------
  function render(a, ctx) {
    const from = ctx.grow && !RM ? qslot.querySelector(".qtab")?.getBoundingClientRect() : null;
    stopThinking(); if (stopReveal) { stopReveal(); stopReveal = null; }
    const id = String(Date.now());
    let th = ctx.th;
    if (!ctx.cached && !(a.meta && a.meta.aborted)) { th = th || id; UI.save({ id, q: ctx.q, p: ctx.p, s: ctx.s, t: ctx.at, a, th }); }
    M = ANS.build(a, ctx); M.th = th || null;
    cur = { q: M.q, p: M.p, s: M.s, th: M.th };
    show("answer");
    if (UI.env() !== M.s) UI.setEnv(M.s);
    qslot.innerHTML = "";                                                   // the tab becomes the overview
    ansEl.innerHTML = ANS.overview(M);
    const ov = ansEl.querySelector(".box.ov");
    if (ctx.cached) window.scrollTo(0, 0);
    const start = () => { ov.classList.add("in"); ANS.stream(ov.querySelector("[data-stream]")); };
    if (from) grow(from, ov, start); else { ov.classList.add("enter"); requestAnimationFrame(start); }
    landRocket();
    acts.hidden = false; UI.setActive(M.q, M.p, M.s);
    document.title = `${M.title} · ${NAME}`;
  }
  // the question tab grows into the overview: a glass panel moves from the tab to the overview's place, then the
  // overview's contents arrive in order
  function grow(from, ov, then) {
    ov.classList.add("growing");
    requestAnimationFrame(() => {
      const to = ov.getBoundingClientRect(), g = document.createElement("div"); g.className = "grow-ghost"; document.body.appendChild(g);
      const geo = r => ({ left: r.left + "px", top: r.top + "px", width: r.width + "px", height: r.height + "px" });
      g.animate([{ ...geo(from), borderRadius: "16px" }, { ...geo(to), borderRadius: "20px" }], { duration: 640, easing: "cubic-bezier(.65,0,.15,1)", fill: "forwards" }).onfinish = () => {
        ov.classList.remove("growing"); then();
        g.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 300, easing: "ease-out", fill: "forwards" }).onfinish = () => g.remove();
      };
    });
  }
  // the full answer, in a focus window that lifts out of the overview
  function openFull(find) {
    const ov = ansEl.querySelector(".box.ov"); if (!ov || !M || view !== "answer") return;
    const F = ANS.full(M); boxes = F.boxes;
    let stop = null;
    EXPAND.open(ov, { label: `${UI.mark()} Full answer`, title: M.title, one: true, cls: "doss-fx", html: F.html,
      actions: `<button type="button" class="btn sm" data-share="link">${ic("link")}<span>Copy link</span></button><button type="button" class="btn sm" data-pdf>${ic("download")}<span>PDF</span></button>`,
      mount: inn => {
        const body = inn.querySelector(".fx-body");
        stop = ANS.reveal(body, 260);
        if (find) setTimeout(() => { const el = body.querySelector("#find-" + find); if (el) { el.classList.add("in"); body.scrollTo({ top: el.offsetTop - 70, behavior: smooth() }); el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1300); } }, 480);
      },
      onClose: () => { if (stop) stop(); } });
  }

  // ---------- management pages ----------
  function managePage(k) {
    abort(); stopThinking(); M = null; cur = null; show(k); window.scrollTo(0, 0); document.title = `${PAGES[k]} · ${NAME}`;
    page.innerHTML = ""; page.onclick = null; landRocket();
    MANAGE[k](page);
  }

  // ---------- routing ----------
  function route() {
    let key = location.hash; if (key === routeKey && view) return; routeKey = key;
    EXPAND.closeAll();
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
  new ResizeObserver(() => { document.documentElement.style.setProperty("--dockh", dock.offsetHeight + "px"); placeRail(); }).observe(dock);

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
    if (EXPAND.depth() > 1) EXPAND.close(go2); else if (EXPAND.depth() === 1) go2(); else { openFull(); setTimeout(go2, 700); }
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
    const fu = t.closest("[data-followup]"); if (fu) { e.preventDefault(); const qq = fu.textContent.trim(), c = followCtx(); return EXPAND.closeAll(() => go(qq, c)); }
    const ak = t.closest("[data-ask]"); if (ak) { const qq = ak.dataset.ask; return EXPAND.closeAll(() => go(qq, M ? { p: M.p, s: M.s } : {})); }
    if (t.closest("[data-home]")) { e.preventDefault(); if (location.hash) history.pushState(null, "", location.pathname + location.search); routeKey = ""; goHome(); ta.focus(); return; }
    if (t.closest("[data-again]")) { const c = M || cur; if (c && c.q) EXPAND.closeAll(() => go(c.q, { p: c.p, s: c.s, th: c.th })); return; }
    const qt = t.closest("[data-qtab]"); if (qt) { const tab = qt.closest(".qtab"), o = !tab.classList.contains("open"); tab.classList.toggle("open", o); qt.setAttribute("aria-expanded", String(o)); return; }
    const act = t.closest("[data-act]");
    if (act && M) {
      if (act.dataset.act === "copy") UI.copy(ANS.text(M)).then(ok => { const c = act.parentElement.querySelector(".cpm"); if (c) { c.textContent = ok ? "Copied" : "Copy failed"; setTimeout(() => c.textContent = "", 1600); } });
      if (act.dataset.act === "again") go(M.q, { p: M.p, s: M.s, th: M.th });
      return;
    }
    const sh = t.closest("[data-share]"); if (sh && M) { UI.closeMenus(); return share(sh.dataset.share); }
    if (t.closest("[data-pdf]") && M) { UI.closeMenus(); REPORT.download(M).catch(err => { console.error(err); UI.toast("Couldn't make the PDF: " + err.message); }); return; }
    const of = t.closest("[data-open-find]"); if (of && of.closest("#answer")) { e.preventDefault(); return openFull(+of.dataset.openFind || 0); }
    if (t.closest("#answer [data-ov]") && !t.closest("a, button, input, select, textarea, label, summary")) return openFull();
    const fc = t.closest(".fcell[data-box]"); if (fc && fc.closest(".fx-layer")) return openBox(fc);
    const box = t.closest(".box[data-box]");
    if (box && box.closest(".fx-layer") && !t.closest("a, button, input, select, textarea, label, summary")) openBox(box);
  });
  document.addEventListener("keydown", e => {
    const el = e.target;
    if (el && el.matches && (e.key === "Enter" || e.key === " ")) {
      if (el.matches("#answer [data-ov]")) { e.preventDefault(); return openFull(); }
      if (el.matches(".fx-layer .box[data-box][role=button]")) { e.preventDefault(); return openBox(el); }
    }
    if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(el.tagName) && !EXPAND.isOpen()) { e.preventDefault(); ta.focus(); }
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
