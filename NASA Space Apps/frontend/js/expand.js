// EXPAND — any box opens to fill the screen: it grows from where it sits on the page in one quick move, the
// full interactive version fades in, and it shrinks back to its place when closed (Esc, ×, or the backdrop).
// The full content is laid out at its final size from the start, so charts draw once and nothing reflows mid-move.
window.EXPAND = (() => {
  const RM = matchMedia("(prefers-reduced-motion: reduce)").matches, { esc } = U, ic = (...a) => UI.ic(...a);
  const host = document.getElementById("focus");
  const EASE_OPEN = "cubic-bezier(.2,.8,.2,1)", EASE_CLOSE = "cubic-bezier(.4,0,.2,1)";
  // layers stack: the full answer opens over the page, and any box inside it opens over the full answer
  const stack = [];
  const target = d => { const m = (innerWidth <= 640 ? 0 : 14) + (innerWidth <= 640 ? 0 : d * 22); return { x: m, y: m, w: innerWidth - 2 * m, h: innerHeight - 2 * m }; };
  const geo = g => ({ left: g.x + "px", top: g.y + "px", width: g.w + "px", height: g.h + "px" });
  const rectOf = el => { const r = el.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; };

  function open(box, spec) {
    const d = stack.length, from = rectOf(box), T = target(d), lastFocus = document.activeElement;
    host.hidden = false; document.body.classList.add("focus-open");
    const layer = document.createElement("div"); layer.className = "fx-layer"; layer.style.zIndex = String(80 + d * 3);
    layer.innerHTML = `<div class="fx-scrim" data-fx-close></div><div class="fx${spec.cls ? " " + spec.cls : ""}" role="dialog" aria-modal="true" aria-labelledby="fx-title-${d}"><div class="fx-snap"></div><div class="fx-in">
      <div class="fx-head"><span class="bl">${spec.label}</span><h2 id="fx-title-${d}">${esc(spec.title)}</h2>${spec.actions || ""}<span class="esc" aria-hidden="true">Esc</span><button type="button" class="ib" data-fx-close aria-label="Close" title="Close">${ic("x")}</button></div>
      <div class="fx-body${spec.one ? " one" : ""}">${spec.html}</div></div></div>`;
    host.appendChild(layer);
    const fx = layer.querySelector(".fx"), snap = fx.querySelector(".fx-snap"), inn = fx.querySelector(".fx-in"), scrim = layer.querySelector(".fx-scrim");
    const clone = box.cloneNode(true); clone.classList.add("in"); clone.removeAttribute("tabindex"); clone.removeAttribute("role"); clone.removeAttribute("id"); clone.style.cssText = `width:${from.w}px;height:${from.h}px;visibility:visible`;
    clone.querySelectorAll("[id]").forEach(e => e.removeAttribute("id"));
    snap.appendChild(clone); Object.assign(snap.style, { width: from.w + "px", height: from.h + "px" });
    Object.assign(inn.style, { width: T.w + "px", height: T.h + "px" }); Object.assign(fx.style, geo(T));
    const c = { box, fx, snap, inn, scrim, layer, lastFocus, spec, d };
    stack.push(c);
    if (spec.mount) try { spec.mount(inn, c); } catch (e) { console.error(e); }
    if (RM) { inn.style.opacity = 1; snap.style.opacity = 0; }
    else {
      const big = from.w * from.h > T.w * T.h * .45;                          // a big box (the overview) lifts; a small one grows
      fx.classList.add("moving");
      fx.animate([{ ...geo(from), borderRadius: "18px" }, { ...geo(T), borderRadius: "18px" }], { duration: big ? 520 : 460, easing: EASE_OPEN }).onfinish = () => fx.classList.remove("moving");
      snap.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 260, easing: "ease-out", fill: "forwards" });
      inn.animate([{ opacity: 0, transform: "translateY(8px)" }, { opacity: 1, transform: "none" }], { duration: 340, delay: 140, easing: EASE_OPEN, fill: "forwards" });
      scrim.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 380, easing: "ease-out" });
    }
    box.style.visibility = "hidden";                         // the box lifts off the page while it is open
    fx.querySelector(".fx-head [data-fx-close]").focus({ preventScroll: true });
    return c;
  }
  function finish(c) {
    c.layer.remove();
    const i = stack.indexOf(c); if (i >= 0) stack.splice(i, 1);
    if (!stack.length) { host.hidden = true; document.body.classList.remove("focus-open"); }
    c.box.style.visibility = "";
    if (c.lastFocus && c.lastFocus.isConnected) c.lastFocus.focus({ preventScroll: true });
    if (c.spec.onClose) c.spec.onClose();
  }
  // close the top layer (Esc, ×, the backdrop): it shrinks back into the box it came from
  function close(then) {
    const c = [...stack].reverse().find(x => !x.closing);              // Esc again while one is closing closes the next
    if (!c) { if (then) then(); return; }
    c.closing = true;
    const done = () => { finish(c); if (then) then(); };
    const to = c.box.isConnected ? rectOf(c.box) : null, seen = to && to.y + to.h > 0 && to.y < innerHeight && to.w > 0;
    if (RM || !seen) { done(); return; }
    const from = rectOf(c.fx);
    c.inn.getAnimations().forEach(a => a.cancel()); c.snap.getAnimations().forEach(a => a.cancel());
    c.box.style.visibility = "hidden"; c.fx.classList.add("moving");
    c.inn.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 140, fill: "forwards" });
    c.snap.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 200, delay: 60, fill: "forwards" });
    c.scrim.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 360, fill: "forwards" });
    c.fx.animate([{ ...geo(from), borderRadius: "18px" }, { ...geo(to), borderRadius: "18px" }], { duration: 380, easing: EASE_CLOSE, fill: "forwards" }).onfinish = done;
  }
  // close everything (moving to another question or page): the layers above go at once, the bottom one shrinks home
  function closeAll(then) {
    while (stack.length > 1) finish(stack[stack.length - 1]);
    close(then);
  }
  host.addEventListener("click", e => { const x = e.target.closest("[data-fx-close]"); if (x && x.closest(".fx-layer") === (stack[stack.length - 1] || {}).layer) close(); });
  document.addEventListener("keydown", e => {
    const c = stack[stack.length - 1]; if (!c) return;
    if (e.key === "Escape") { if (document.querySelector(".dd.open,.pop.open")) return; e.preventDefault(); close(); return; }
    if (e.key === "Tab") {                                                   // keep Tab inside the top layer
      const f = [...c.layer.querySelectorAll("button:not([disabled]),input,select,textarea,a[href],summary,[tabindex]:not([tabindex='-1'])")].filter(x => x.offsetParent !== null);
      if (!f.length) return; const k = f.indexOf(document.activeElement);
      if (k < 0 || (e.shiftKey && k === 0) || (!e.shiftKey && k === f.length - 1)) { e.preventDefault(); f[e.shiftKey ? f.length - 1 : 0].focus(); }
    }
  });
  addEventListener("resize", () => stack.forEach(c => { const T = target(c.d); Object.assign(c.fx.style, geo(T)); Object.assign(c.inn.style, { width: T.w + "px", height: T.h + "px" }); }));

  // ---------- what each kind of box shows when open ----------
  const pad = n => String(n).padStart(2, "0");
  function chartsPanel(types) {
    return `${types.length > 1 ? `<div class="tabs" role="tablist">${types.map((t, i) => `<button type="button" role="tab" aria-selected="${!i}" data-tab="${i}">${esc(W.def(t).title)}</button>`).join("")}</div>` : ""}<div class="fx-chart">${W.full(types[0])}</div>`;
  }
  function mountCharts(types, side) {
    return inn => {
      const slot = inn.querySelector(".fx-chart"), show = i => { slot.innerHTML = W.full(types[i]); W.mountFull(slot.querySelector(".mw-full"), types[i]); if (side) inn.querySelector(".fx-txt").innerHTML = side(types[i]); };
      W.mountFull(slot.querySelector(".mw-full"), types[0]);
      inn.querySelectorAll("[data-tab]").forEach(b => b.addEventListener("click", () => { inn.querySelectorAll("[data-tab]").forEach(x => x.setAttribute("aria-selected", String(x === b))); show(+b.dataset.tab); }));
    };
  }
  const refList = (M, ns) => { const rs = [...new Set(ns.filter(Boolean))].map(n => M.refs[n - 1]).filter(Boolean); return rs.length ? `<ol class="lit-src" style="list-style:none;padding:0">${rs.map(r => `<li><span class="t-id">[${r.n}]</span> ${r.url ? `<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>` : esc(r.title)}<br><span class="lit-why">${esc(r.kind)}</span></li>`).join("")}</ol>` : ""; };
  const aboutChart = t => { const d = W.def(t); return `<h3>About this chart</h3>${MW.STATUS[d.status] || ""}<p>${esc(d.desc || "")}</p>${TW.litHTML(t)}`; };

  function spec(b, M) {
    switch (b.kind) {
      case "finding": {
        const f = b.f, side = t => `<h3>Finding ${pad(f.n)}</h3><p class="lead">${esc(ANS.plain(f.text))}${ANS.cites(f.refs)}</p>${t ? aboutChart(t) : ""}${refList(M, f.refs) ? `<h3>Sources for this finding</h3>${refList(M, f.refs)}` : ""}`;
        if (!f.charts.length) return { label: `Finding <b>${pad(f.n)}</b>`, title: ANS.firstSentence(f.text), one: true,
          html: `<div class="fx-one"><p class="ov-big">${esc(ANS.plain(f.text))}${ANS.cites(f.refs)}</p>${f.psi[0] ? `<h3>The NASA experiment behind it</h3>${TW.full("experiment", { psi_id: f.psi[0] })}` : ""}${refList(M, f.refs) ? `<h3>Sources</h3>${refList(M, f.refs)}` : ""}</div>` };
        return { label: `Finding <b>${pad(f.n)}</b>`, title: ANS.firstSentence(f.text), html: `<div class="fx-vis">${chartsPanel(f.charts)}</div><div class="fx-txt">${side(f.charts[0])}</div>`, mount: mountCharts(f.charts, side) };
      }
      case "chart": {
        const t = b.c.type, d = W.def(t), side = x => `${aboutChart(x)}${M && b.c.refs ? `<h3>Sources</h3>${refList(M, b.c.refs)}` : ""}`;
        return { label: `${esc(d.cat || "Chart")} · ${esc(d.model)}`, title: d.title, html: `<div class="fx-vis">${chartsPanel([t])}</div><div class="fx-txt">${side(t)}</div>`, mount: mountCharts([t], side) };
      }
      case "fact": {
        const f = b.f;
        return { label: "Key fact", title: f.label, one: true, html: `<div class="fx-one"><div class="fv" style="font-size:clamp(36px,5vw,60px)">${esc(f.value)}</div><p class="ov-big">${esc(f.label)}${ANS.cites(f.refs)}</p>
          ${f.source ? `<p class="fs">Source: ${esc(f.source)}</p>` : ""}${f.psi_id && U.inv(f.psi_id) ? `<h3>The NASA experiment it comes from</h3>${TW.full("experiment", { psi_id: f.psi_id })}` : ""}</div>` };
      }
      case "exp": {
        const i = U.inv(b.e.psi), models = Object.entries(ANS.LINKED).filter(([, ids]) => ids.includes(i.id)).map(([m]) => m);
        const charts = MW.types().filter(t => models.includes(W.def(t).model));
        return { label: "NASA experiment", title: i.acronym ? `${i.acronym}: ${i.title}` : i.title, one: true,
          html: `<div class="fx-one">${TW.full("experiment", { psi_id: i.id })}
            <p style="margin-top:18px;display:flex;gap:8px;flex-wrap:wrap"><button type="button" class="btn p" data-ask="${esc(`Everything about ${U.invLabel(i)} (${i.id})`)}">${ic("spark")}Ask about this experiment</button>${i.url ? `<a class="btn" href="${esc(i.url)}" target="_blank" rel="noopener">${ic("link")}Open in NASA PSI</a>` : ""}</p>
            ${charts.length ? `<h3>Thermo-model charts built on it</h3><ul class="t-list">${charts.map(t => `<li><b>${esc(W.def(t).title)}</b> <span class="t-id">${esc(W.def(t).model)}</span></li>`).join("")}</ul>` : ""}</div>` };
      }
      case "lim":
        return { label: "What the data can't say", title: "Limits of this answer", one: true, html: `<div class="fx-one"><p class="ov-big">${esc(b.text)}</p><p class="fs">Moon and Mars: NASA's PSI database has no partial-gravity combustion data, so statements about them are theoretical bounds.</p></div>` };
      case "overview":
        return { label: `${UI.mark()} AI overview`, title: M.title, one: true, html: `<div class="fx-one">
          ${M.summary ? `<div class="ov-big">${U.md(M.summary)}</div>` : ""}${M.note ? `<p class="note">${esc(M.note)}</p>` : ""}
          ${M.facts.length ? `<h3>Key facts</h3><ul class="t-list">${M.facts.map(f => `<li><b>${esc(f.value)}</b> ${esc(f.label)}${ANS.cites(f.refs)}</li>`).join("")}</ul>` : ""}
          ${M.finds.length ? `<h3>The answer, step by step</h3><ol class="ov-outline" style="gap:10px">${M.finds.map(f => `<li><span>${pad(f.n)}</span><div style="color:var(--text)">${esc(ANS.plain(f.text))}${ANS.cites(f.refs)}</div></li>`).join("")}</ol>` : ""}
          ${M.limitations ? `<h3>What the data can't say</h3><p>${esc(M.limitations)}</p>` : ""}
          ${M.follow_ups.length ? `<h3>Ask next</h3><div class="fups">${M.follow_ups.map(q => `<a class="chip" href="${esc(UI.href(q, M.p, M.s))}" data-followup>${ic("spark")}${esc(q)}</a>`).join("")}</div>` : ""}
          <h3>How this answer was made</h3><p class="fs" style="font-size:12px">${esc(ANS.madeLine(M))}</p></div>` };
    }
    return null;
  }
  return { open, close, closeAll, spec, isOpen: () => stack.length > 0, depth: () => stack.length, top: () => stack[stack.length - 1] || null };
})();
