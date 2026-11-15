// ANSWER — turns the AI's reply into two things:
//   overview(M): the one widget on the answer page. It fills the screen: title, short answer, key facts, an outline of
//     the findings and small previews of the generated figures. Clicking it opens the full answer.
//   full(M): the full answer, shown in a focus window: the findings (each with the figures that show it), more from
//     the data, the thread, next questions, and closed References and Method drop-downs. Every box in it opens on top.
// The data display settings (UI.display) decide which sections and figures appear.
// Also builds the question tab above the prompt bar while the AI works: the question, the steps, and the rail the
// rocket climbs as the progress marker.
// Written with SI assistance (Claude, Anthropic).
window.ANS = (() => {
  const { esc, md } = U, ic = (...a) => UI.ic(...a);
  const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const plain = s => String(s ?? "").replace(/\*\*/g, "").replace(/\s+/g, " ").trim();
  const firstSentence = s => { const t = plain(s), m = t.match(/^.*?[.!?](\s|$)/); return m ? m[0].trim() : t; };
  const pad = n => String(n).padStart(2, "0");
  const year = d => { const m = String(d || "").match(/(\d{4})/); return m ? m[1] : ""; };

  // the NASA investigations each thermo model is built on (from the model tracker, as in standin/context.json)
  const LINKED = {"THM-01":["PSI-20","PSI-159","PSI-69"],"THM-02":["PSI-20","PSI-10","PSI-69"],"THM-03":["PSI-159","PSI-10"],"THM-04":["PSI-98","PSI-99","PSI-100","PSI-25"],"THM-05":["PSI-26","PSI-25","PSI-98","PSI-99","PSI-100"],"THM-06":["PSI-26","PSI-25","PSI-98","PSI-99","PSI-100"],"THM-07":["PSI-25","PSI-106"],"THM-08":["PSI-25","PSI-22"],"THM-09":["PSI-26","PSI-25","PSI-98","PSI-99","PSI-100"],"THM-10":["PSI-69","PSI-68","PSI-39"],"THM-11":["PSI-69","PSI-68","PSI-159"],"THM-12":["PSI-69","PSI-68"],"THM-13":["PSI-25","PSI-20"],"THM-14":["PSI-98","PSI-99","PSI-100","PSI-10"],"THM-15":["PSI-10","PSI-159","PSI-69"],"THM-16":["PSI-26","PSI-25","PSI-98","PSI-99","PSI-100"],"THM-17":["PSI-25","PSI-20"],"THM-18":["PSI-69","PSI-25"],"THM-19":["PSI-98","PSI-99","PSI-100"],"THM-20":["PSI-102","PSI-101","PSI-98","PSI-99","PSI-100"]};
  const ENV = {
    isChart: t => !!MW.lib[t], isPsi: id => !!U.inv(id), desc: t => (W.def(t) || {}).desc || "",
    linked: t => { const d = W.def(t); return (d && (d.psi && d.psi.length ? d.psi : LINKED[d.model])) || []; }
  };
  // a figure can be switched off in the data display settings by its analysis (generated) or its own type (library)
  const shown = t => { const d = W.def(t) || {}; return UI.display.chart(t) && (!d.gen || UI.display.chart(d.lib)); };
  const STATUS_LABEL = { physics: "Model calculation", reconstruction: "Reconstructs a NASA FLEX run", estimate: "Model estimate", synthetic: "Synthetic material",
    reduction: "Reduces measured data", screening: "Screening estimate", budget: "Thermal budget", illustrative: "Illustrative inputs", bound: "Theoretical bound", demo: "Demo data · synthetic" };
  const TAG_LABEL = t => (DATA.evidenceTags[t] || {}).label || "";

  // ---------- references: everything the answer used, numbered in reading order ----------
  function Refs() {
    const list = [], idx = new Map();
    const add = (key, make) => { if (!idx.has(key)) { const r = make(); if (!r) return 0; r.n = list.length + 1; r.key = key; list.push(r); idx.set(key, r.n); } return idx.get(key); };
    const psi = (id, ev) => add("psi:" + id, () => {
      const i = U.inv(id); if (!i) return null;
      const yrs = [year(i.start), year(i.end)].filter(Boolean), when = yrs.length ? (yrs[0] === yrs[1] || yrs.length === 1 ? yrs[0] : yrs.join("–")) : "";
      return { kind: "NASA PSI investigation", title: `${i.acronym ? i.acronym + ": " : ""}${i.title}`, url: i.url,
        desc: [i.id, i.projectType, i.platform, when, String(i.center || "").replace(/\s*\(.*\)/, "")].filter(Boolean).join(" · "), psi: i.id, notes: [] };
    });
    const model = t => { const d = W.def(t); if (!d || !d.model) return 0;
      return add("model:" + d.model, () => {
        const L = DATA.literature && DATA.literature[d.model];
        return { kind: "Thermo model and its literature", title: `${d.model}${L ? ": " + L.method.charAt(0).toUpperCase() + L.method.slice(1) : ""}`, url: null,
          desc: d.gen ? `Imperial thermo team model, re-run for this question by the demo pipeline on synthetic data. Charts used: ${d.title}.` : `Imperial thermo team model, run ahead of time by standin/precompute_models.py. Charts used: ${d.title}.`, model: d.model, charts: [t],
          sub: L ? L.sources.map(s => ({ text: s.citation, url: s.url, id: s.id })) : [], boundary: L ? L.boundary : "" };
      }); };
    const source = e => add("source:" + (e.evidence_id || e.url || e.note), () => ({ kind: e.review_status || "Source file",
      title: e.note || e.psi_id || "Source", url: /^https?:\/\//i.test(e.url || "") ? e.url : null,
      desc: e.psi_id || "", notes: [] }));
    return { list, psi, model, source, note(n, text, tag) { const r = list[n - 1]; if (r && text && !r.notes.some(x => x.text === text)) r.notes.push({ text, tag }); },
      chart(n, t) { const r = list[n - 1], d = W.def(t); if (r && r.charts && !r.charts.includes(t)) { r.charts.push(t); r.desc = r.desc.replace(/Charts used: .*$/, "Charts used: " + r.charts.map(c => W.def(c).title).join(", ") + "."); } } };
  }
  const cites = (ns, still) => { const u = [...new Set((ns || []).filter(Boolean))].sort((a, b) => a - b); return u.length ? `<span class="cite">${u.map(n => still ? `<span>${n}</span>` : `<a href="#ref-${n}" data-ref="${n}" aria-label="Reference ${n}">${n}</a>`).join("")}</span>` : ""; };

  // ---------- the answer, as the page will show it ----------
  function build(a, ctx) {
    a = a || {};
    if (a.figures && window.FIG) FIG.register(a.figures);
    const live = a.meta && a.meta.source === "live", demo = a.meta && a.meta.source === "demo", R = Refs(), D = UI.display;
    let hidden = 0;
    const raw = STORY.points(a, ENV), points = raw.map(p => { const keep = D.section("charts") ? p.charts.filter(shown) : []; hidden += p.charts.length - keep.length; return { ...p, charts: keep }; });
    const allFacts = (a.key_facts || []).filter(f => f && f.label && f.value).slice(0, 3);
    if (!D.section("facts")) hidden += allFacts.length;
    const facts = (D.section("facts") ? allFacts : []).map(f => ({ ...f, refs: f.psi_id && U.inv(f.psi_id) ? [R.psi(f.psi_id)] : [] }));
    const evNote = {}; (a.evidence || []).forEach(e => { if (e && e.psi_id) evNote[String(e.psi_id).toUpperCase()] = e; });
    const finds = points.map((p, k) => {
      const refs = [];
      p.psi_ids.forEach(id => { const n = R.psi(id); refs.push(n); const e = evNote[id]; if (e && e.note) R.note(n, e.note, e.tag); });
      p.charts.forEach(t => { const n = R.model(t); refs.push(n); R.chart(n, t); });
      return { n: k + 1, text: p.text, psi: p.psi_ids, charts: p.charts, refs };
    });
    if (a.meta?.provider === "thermo") (a.evidence || []).forEach(e => R.source(e));
    const extraAll = (a.widgets || []).map(w => w && w.type).filter(t => t && MW.lib[t] && !raw.some(p => p.charts.includes(t))).filter((t, i, s) => s.indexOf(t) === i).slice(0, 4);
    const extraOk = D.section("extra") ? extraAll.filter(shown) : []; hidden += extraAll.length - extraOk.length;
    const extra = extraOk.map(t => { const n = R.model(t); R.chart(n, t); return { type: t, refs: [n] }; });
    (a.evidence || []).forEach(e => { if (e && U.inv(String(e.psi_id || "").toUpperCase())) { const n = R.psi(String(e.psi_id).toUpperCase()); R.note(n, e.note, e.tag); } });
    // NASA experiments worth a card: cited ones, most-cited first, skipping those already inside a finding box
    const count = {}; finds.forEach(f => f.psi.forEach(id => count[id] = (count[id] || 0) + 2)); Object.keys(evNote).forEach(id => count[id] = (count[id] || 0) + 1);
    const inFinding = new Set(finds.filter(f => !f.charts.length && f.psi[0]).map(f => f.psi[0]));
    let exps = Object.keys(count).filter(id => U.inv(id) && !inFinding.has(id)).sort((x, y) => count[y] - count[x]).slice(0, 6).map(id => ({ psi: id, refs: [R.psi(id)] }));
    if (!D.section("exps")) { hidden += exps.length; exps = []; }
    const lim = plain(a.limitations); if (lim && !D.section("lim")) hidden++;
    let summary = a.summary || "", note = "";
    if (demo) note = a.meta.error ? `The AI did not answer this time (${String(a.meta.error).slice(0, 160)}), so the demo pipeline wrote this straight from the figures.`
      : "No AI connected: the demo pipeline wrote this straight from the figures it generated. Start the server (see the README) for an AI-written answer.";
    else if (!live) note = a.meta && a.meta.error ? `The AI did not answer this time (${String(a.meta.error).slice(0, 160)}). The findings below were picked from the words in your question; ask again in a moment.`
      : "Preview without the AI: the findings and charts below were picked from the words in your question. Start the server (see the README) for a written answer.";
    if (!live && !demo) summary = "";
    const figs = Object.keys(a.figures || {}).length;
    const fu = (a.follow_ups || []).filter(Boolean).slice(0, 3);
    const seed = TILER.hash(ctx.q || "");
    return {
      q: ctx.q, p: ctx.p || null, s: ctx.s || "iss", live, demo, figs, meta: a.meta || {}, at: ctx.at || Date.now(), cached: !!ctx.cached,
      title: plain(a.title) || ctx.q, summary, note, facts, finds, extra, exps,
      limitations: D.section("lim") ? lim : "", hidden, method: a.method || null, follow_ups: fu.length ? fu : TW.ASK_NEXT.map((x, i) => TW.ASK_NEXT[(i + seed) % TW.ASK_NEXT.length]).filter(x => x !== ctx.q).slice(0, 3),
      blocks: (a.blocks || []).filter(b => b.type !== "chart" || D.section("charts")), clarifications: a.clarifications || [], function_pipeline: a.function_pipeline || [],
      refs: R.list, dropped: a.dropped || [], raw: a
    };
  }

  // ---------- boxes ----------
  const forWho = M => `${M.p ? "For " + UI.personaLabel(M.p).toLowerCase() + "s" : "General answer"} · ${UI.envLabel(M.s)}`;
  const chartArea = (t, h) => { const [aspect] = MW.shape(t); return `<div class="bc" style="aspect-ratio:${Math.max(1.15, Math.min(2.6, aspect)).toFixed(2)}${h ? ";max-height:" + h + "px" : ""}">${MW.tile(t)}</div>`; };
  const chartCap = t => { const d = W.def(t); return `<div class="ccap"><b>${esc(d.title)}</b><span>${esc([d.model, STATUS_LABEL[d.status]].filter(Boolean).join(" · "))}</span></div>`; };
  const head = (label, meta) => `<div class="bh"><span class="bl">${label}</span>${meta ? `<span class="bm">${esc(meta)}</span>` : ""}<span class="bx" aria-hidden="true">${ic("expand")}</span></div>`;
  const boxAttrs = (i, cls, label, id) => `${id ? `id="${id}" ` : ""}class="box ${cls} rv" data-box="${i}" tabindex="0" role="button" aria-label="${esc(label)}: open full screen"`;
  function expMini(id) { const i = U.inv(id); if (!i) return ""; return `<div class="exp-mini"><span class="lab">NASA experiment</span><b>${esc(i.acronym || i.id)}</b><span>${esc(i.title.length > 110 ? i.title.slice(0, 108) + "…" : i.title)}</span></div>`; }

  function findingHTML(f, i, wide) {
    const meta = [...f.psi.map(id => (U.inv(id) || {}).acronym || id), ...f.charts.map(t => W.def(t).model)].filter((x, j, s) => x && s.indexOf(x) === j).join(" · ");
    const text = `<p class="bt">${esc(plain(f.text))}${cites(f.refs)}</p>`;
    if (!wide) return `<article ${boxAttrs(i, "s6 find", "Finding " + f.n, "find-" + f.n)}>${head(`Finding <b>${pad(f.n)}</b>`, meta)}${text}
      ${f.charts.length ? `<div style="margin-top:auto">${chartArea(f.charts[0])}</div>${chartCap(f.charts[0])}` : expMini(f.psi[0])}</article>`;
    const aside = f.charts.length > 1 ? `<div class="charts">${f.charts.map(t => `<div>${chartArea(t)}${chartCap(t)}</div>`).join("")}</div>`
      : f.charts.length ? `<div>${chartArea(f.charts[0], 420)}${chartCap(f.charts[0])}</div>` : `<div style="display:flex">${expMini(f.psi[0])}</div>`;
    return `<article ${boxAttrs(i, "s12 find", "Finding " + f.n, "find-" + f.n)}>${head(`Finding <b>${pad(f.n)}</b>`, meta)}<div class="duo"><div>${text}</div>${aside}</div></article>`;
  }
  // a row holds two half-width findings or one wide one; a finding with two charts is always wide
  function packFindings(finds) {
    const wide = finds.map(f => f.charts.length > 1);
    let open = -1;
    finds.forEach((f, k) => { if (wide[k]) { if (open >= 0) wide[open] = true; open = -1; } else if (open < 0) open = k; else open = -1; });
    if (open >= 0) wide[open] = true;
    return wide;
  }
  function factHTML(f, i) {           // a key fact: a cell in the overview's strip; opens like any box
    const v = String(f.value);
    return `<button type="button" class="fcell" data-box="${i}" aria-label="Key fact: ${esc(f.label)}: open full screen"><span class="lab">Key fact${f.psi_id ? " · " + esc(f.psi_id) : ""}</span><span class="fv${v.length > 18 ? " sm" : ""}">${esc(v)}</span><span class="fl">${esc(f.label)}${cites(f.refs, true)}</span>${f.source ? `<span class="fs">${esc(f.source)}</span>` : ""}</button>`;
  }
  function expHTML(e, i, cls = "s4") {
    const x = U.inv(e.psi); if (!x) return "";
    const yrs = [year(x.start), year(x.end)].filter(Boolean), when = yrs.length ? (yrs[0] === yrs[1] || yrs.length === 1 ? yrs[0] : yrs.join("–")) : "";
    return `<article ${boxAttrs(i, cls + " exp", "NASA experiment " + (x.acronym || x.id))}>${head("NASA experiment", x.id)}<p class="en">${esc(x.acronym || x.id)}${e.refs ? cites(e.refs) : ""}</p><p class="et">${esc(x.title)}</p>
      <p class="em">${esc([x.projectType, x.platform, when].filter(Boolean).join(" · "))}</p><p class="eo">${esc(plain(x.objectives))}</p></article>`;
  }
  function chartBoxHTML(c, i, cls = "s6") {
    const d = W.def(c.type);
    return `<article ${boxAttrs(i, cls + " chart", d.title)}>${head(esc(d.cat || "chart"), d.model)}<p class="bt" style="font-size:14px;color:var(--muted)">${esc(firstSentence(d.desc))}${c.refs ? cites(c.refs) : ""}</p><div style="margin-top:auto">${chartArea(c.type)}</div>${chartCap(c.type)}</article>`;
  }

  // ---------- the answer page: one overview widget that fills the screen; clicking it opens the full answer ----------
  const pillsHTML = M => [M.figs ? `<span class="pill">Demo data</span>` : "", !M.live ? `<span class="pill warn">${M.meta && M.meta.error ? "AI unavailable" : M.demo ? "No AI · pipeline text" : "Preview · no AI"}</span>` : "", M.cached ? `<span class="pill">Saved</span>` : ""].join("");
  const factCell = (f, attrs = "") => { const v = String(f.value); return `<div class="fcell" ${attrs}><span class="lab">Key fact</span><span class="fv${v.length > 18 ? " sm" : ""}">${esc(v)}</span><span class="fl">${esc(f.label)}</span>${f.source ? `<span class="fs">${esc(f.source)}</span>` : ""}</div>`; };
  function overview(M) {
    const figs = M.finds.flatMap(f => f.charts.map(t => ({ t, n: f.n }))).concat(M.extra.map(c => ({ t: c.type, n: 0 }))).slice(0, 4);
    const outline = M.finds.length ? `<nav class="ov-r" aria-label="In this answer"><p class="lab">In this answer</p><ol class="ov-outline">${M.finds.map(f => `<li><button type="button" data-open-find="${f.n}"><span>${pad(f.n)}</span><em>${esc(firstSentence(f.text))}</em>${f.charts.length ? ic("layers", "oc") : ""}</button></li>`).join("")}</ol></nav>` : "";
    const n = M.refs.length, th = M.th ? UI.thread(M.th) : [];
    return `<article class="box ov" data-ov tabindex="0" role="button" aria-label="Answer overview: open the full answer">
      <div class="bh"><span class="bl">${UI.mark()}AI overview</span>${pillsHTML(M)}<span class="ov-q" title="${esc(M.q)}">${esc(M.q)}</span><span class="sp"></span>
        <span class="cpm" role="status"></span><button type="button" class="ib sm" data-act="copy" aria-label="Copy answer" title="Copy answer">${ic("copy")}</button><button type="button" class="ib sm" data-act="again" aria-label="Ask again" title="Ask again">${ic("refresh")}</button><span class="bx" aria-hidden="true">${ic("expand")}</span></div>
      <div class="ov-main${outline ? "" : " solo"}"><div class="ov-l"><h1>${esc(M.title)}</h1>
        ${M.summary ? `<div class="sum" data-stream>${md(M.summary)}</div>` : ""}
        ${M.note ? `<p class="note">${esc(M.note)}</p>` : ""}</div>${outline}</div>
      ${M.facts.length ? `<div class="fstrip">${M.facts.map(f => factCell(f)).join("")}</div>` : ""}
      ${figs.length ? `<div class="ov-figs" style="--n:${figs.length}">${figs.map(({ t, n }) => `<button type="button" class="ov-fig" data-open-find="${n}" aria-label="${esc(W.def(t).title)}: open in the full answer"><span class="ov-fig-c">${MW.tile(t)}</span><span class="ov-fig-t">${n ? `<b>${pad(n)}</b>` : ""}${esc(W.def(t).title)}</span></button>`).join("")}</div>` : ""}
      <p class="ov-foot"><span class="ov-hint">${ic("expand")}Click anywhere for the full answer</span><span>${M.finds.length} finding${M.finds.length === 1 ? "" : "s"} · ${M.figs ? `${M.figs} generated figure${M.figs === 1 ? "" : "s"} · ` : ""}${n} source${n === 1 ? "" : "s"}</span>${th.length > 1 ? `<span>Question ${th.findIndex(h => String(h.q).trim().toLowerCase() === String(M.q).trim().toLowerCase()) + 1} of ${th.length} in this thread</span>` : ""}${M.hidden ? `<a href="#display" class="ov-hid">${ic("sliders")}${M.hidden} display${M.hidden > 1 ? "s" : ""} hidden by your settings</a>` : ""}</p>
    </article>`;
  }

  // ---------- the full answer (focus window); boxes[] keeps what each box is, for the view on top of it ----------
  function full(M) {
    const boxes = [{ kind: "overview" }]; let html = "";
    const add = b => (boxes.push(b), boxes.length - 1);
    const when = new Date(M.at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
    html += `<header class="doss-h rv"><p class="lab">${esc(forWho(M))} · ${esc(when)}</p><p class="doss-q">${esc(M.q)}</p>${pillsHTML(M) ? `<p class="doss-p">${pillsHTML(M)}</p>` : ""}</header>`;
    html += `<section class="doss-lead rv">${M.summary ? `<div class="ov-big">${md(M.summary)}</div>` : ""}${M.note ? `<p class="note">${esc(M.note)}</p>` : ""}
      ${M.facts.length ? `<div class="fstrip">${M.facts.map(f => `<button type="button" class="fcell" data-box="${add({ kind: "fact", f })}" aria-label="Key fact: ${esc(f.label)}: open"><span class="lab">Key fact${f.psi_id ? " · " + esc(f.psi_id) : ""}</span><span class="fv${String(f.value).length > 18 ? " sm" : ""}">${esc(f.value)}</span><span class="fl">${esc(f.label)}${cites(f.refs, true)}</span>${f.source ? `<span class="fs">${esc(f.source)}</span>` : ""}</button>`).join("")}</div>` : ""}</section>`;
    if (M.blocks.length || M.clarifications.length || M.function_pipeline.length) {
      html += `<div class="sec-h"><h2>Backend results</h2></div><div class="backend-results">${M.blocks.map(b => `<section class="box workflow-result">${WORKFLOW.render(b)}</section>`).join("")}</div>`;
      html += M.clarifications.map(c => `<section class="box workflow-result"><h3>More information needed</h3><p>${esc(c.question || c.message || "Supply the missing model inputs.")}</p>${(c.options || []).map(o => `<button class="chip" data-reply="${esc(typeof o === "string" ? o : o.label || o.value)}">${esc(typeof o === "string" ? o : o.label || o.value)}</button>`).join("")}</section>`).join("");
      if (M.function_pipeline.length) html += `<details class="workflow-result"><summary>Function execution details</summary><pre>${esc(JSON.stringify(M.function_pipeline, null, 2))}</pre></details>`;
    }
    if (M.finds.length) {
      const wide = packFindings(M.finds);
      html += `<div class="sec-h"><h2>Findings</h2><p>In reading order, each with the figure generated for it. Open any box to explore it and re-run its model.</p></div>
        <div class="grid">${M.finds.map((f, k) => findingHTML(f, add({ kind: "finding", f }), wide[k])).join("")}</div>`;
    }
    const more = [];
    if (M.limitations) more.push(`<article ${boxAttrs(add({ kind: "lim", text: M.limitations }), "s12 lim", "What the data can't say")}>${head("What the data can't say")}<p class="bt">${esc(M.limitations)}</p></article>`);
    M.exps.forEach(e => more.push(expHTML(e, add({ kind: "exp", e }), M.exps.length === 2 ? "s6" : "s4")));
    M.extra.forEach(c => more.push(chartBoxHTML(c, add({ kind: "chart", c }), "s6")));
    if (more.length) html += `<div class="sec-h"><h2>More from the data</h2><p>The experiments behind the findings, and what the data can't tell you.</p></div><div class="grid">${more.join("")}</div>`;
    const th = M.th ? UI.thread(M.th) : [];
    if (th.length > 1) html += `<div class="sec-h"><h2>This thread</h2><p>${th.length} questions asked one after another.</p></div><ol class="doss-th rv">${th.map((h, i) => { const on = String(h.q).trim().toLowerCase() === String(M.q).trim().toLowerCase();
      return `<li${on ? ' class="on"' : ""}><span class="qn">${pad(i + 1)}</span><a href="${esc(UI.href(h.q, h.p, h.s))}"${on ? ' aria-current="true"' : ""}>${esc(UI.label(h))}</a><small>${esc(new Date(h.t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }))}</small></li>`; }).join("")}</ol>`;
    if (M.follow_ups.length) html += `<div class="sec-h"><h2>Ask next</h2></div><div class="fups rv">${M.follow_ups.map(q => `<a class="chip" href="${esc(UI.href(q, M.p, M.s))}" data-followup>${ic("spark")}${esc(q)}</a>`).join("")}</div>`;
    const n = M.refs.length;
    html += `<div class="drops rv">
      <details class="drop" id="references"><summary><span class="dl">References</span><span class="dc">${n ? `${n} source${n > 1 ? "s" : ""} · the numbers in the text point here` : "none cited"}</span>${ic("chev", "cv")}</summary><div class="drop-b">${refsHTML(M)}</div></details>
      <details class="drop" id="method"><summary><span class="dl">Method</span><span class="dc">How this answer was made, and where the data comes from</span>${ic("chev", "cv")}</summary><div class="drop-b">${methodHTML(M)}</div></details></div>`;
    return { html: `<div class="doss">${html}</div>`, boxes };
  }
  function refsHTML(M) {
    if (!M.refs.length) return `<p class="made">No sources were cited.</p>`;
    return `<ol class="refs rv">${M.refs.map(r => `<li id="ref-${r.n}"><span class="rn">[${r.n}]</span><div><p class="rk">${esc(r.kind)}</p>
      <p class="rt">${r.url ? `<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>` : esc(r.title)}</p><p class="rd">${esc(r.desc)}</p>
      ${r.notes && r.notes.length ? `<p class="rd">${r.notes.map(x => `${x.tag ? `<span class="badge" data-tag="${esc(x.tag)}">${esc(TAG_LABEL(x.tag))}</span> ` : ""}${esc(x.text)}`).join("<br>")}</p>` : ""}
      ${r.sub && r.sub.length ? `<ul class="rsub">${r.sub.map(s => `<li>${esc(s.text)}${s.url ? ` <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.id || "link")} ↗</a>` : s.id ? ` <span class="t-id">${esc(s.id)}</span>` : ""}</li>`).join("")}</ul>` : ""}
      ${r.boundary ? `<p class="rd">Evidence boundary: ${esc(r.boundary)}</p>` : ""}</div></li>`).join("")}</ol>`;
  }
  function madeLine(M) {
    if (M.meta?.provider === "thermo") return `Thermo backend · ${M.meta.status || "result"}. Calculations, reference inputs and provenance are returned by the backend. Bundled illustrative inputs are labelled in the results. Status and method details appear with each calculation.`;
    const m = M.meta || {}, when = new Date(M.at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
    const who = M.live ? `Written by ${m.provider || "the AI"}${m.model ? " / " + m.model : ""}${m.stand_in ? " through the team's stand-in server" : ""}${m.seconds ? ` in ${m.seconds} s` : ""}` : M.demo ? "No AI connected: written by the demo pipeline from the figures it generated" : "No AI connected: preview built from the question's words";
    const checks = M.live ? ` The server removed anything it could not match to the data${M.dropped.length ? ` (${M.dropped.length} item${M.dropped.length > 1 ? "s" : ""}: ${M.dropped.slice(0, 4).join(", ")})` : " (nothing needed removing)"}.` : "";
    return `${who}, ${when}. ${forWho(M)}.${checks}${M.figs ? " Figures: the team's models re-run on this question's conditions with synthetic demo data." : ""} Sources: NASA Physical Sciences Informatics (PSI) combustion investigations and the Imperial thermo team's models. Research support only, not safety certification.`;
  }
  const madeHTML = M => `<p class="made">How this answer was made: ${esc(madeLine(M))}</p>`;
  // Method: the backend may send `method` with the answer (string, list of steps, or { summary, steps, notes });
  // until then it is described from what the page knows.
  const stepHTML = x => typeof x === "string" ? esc(x) : x && typeof x === "object" ? `${x.title ? `<b>${esc(x.title)}</b> ` : ""}${esc(x.text || x.detail || "")}` : "";
  function methodHTML(M) {
    if (M.meta?.provider === "thermo") return `<p>${esc(madeLine(M))}</p><p>Open Backend results for model methods, input assumptions, source provenance and downloadable JSON.</p>`;
    const m = M.method, models = [...new Set(M.refs.filter(r => r.model).map(r => r.model))], psi = M.refs.filter(r => r.psi).length, mm = M.meta || {};
    let given = "";
    if (typeof m === "string" && m.trim()) given = `<div class="mth-given">${md(m)}</div>`;
    else if (Array.isArray(m) && m.length) given = `<ol class="mth-steps">${m.map(x => `<li>${stepHTML(x)}</li>`).join("")}</ol>`;
    else if (m && typeof m === "object") given = `${m.summary ? `<div class="mth-given">${md(m.summary)}</div>` : ""}${Array.isArray(m.steps) && m.steps.length ? `<ol class="mth-steps">${m.steps.map(x => `<li>${stepHTML(x)}</li>`).join("")}</ol>` : ""}${Array.isArray(m.notes) ? m.notes.map(x => `<p class="rd">${esc(x)}</p>`).join("") : ""}`;
    const steps = [
      `Read the question for ${M.p ? UI.personaLabel(M.p).toLowerCase() + "s" : "a general reader"}, in the ${esc(UI.envLabel(M.s))} environment.`,
      `Searched ${DATA.investigations.length} NASA PSI combustion investigations${psi ? `; ${psi} are cited here` : ""}.`,
      models.length ? `Used the Imperial thermo team's models ${esc(models.join(", "))} for the charts (run ahead of time; literature in References).` : "No thermo-model chart was needed.",
      M.live ? `Wrote the answer with ${esc(mm.provider || "the AI")}${mm.model ? " / " + esc(mm.model) : ""}${mm.seconds ? ` in ${mm.seconds} s` : ""}.` : "No AI connected: the preview was picked from the words of the question.",
      M.live ? `Checked every citation against the data${M.dropped.length ? `, and removed ${M.dropped.length} that didn't match (${esc(M.dropped.slice(0, 4).join(", "))})` : "; nothing needed removing"}.` : ""
    ].filter(Boolean);
    return `${given || `<ol class="mth-steps">${steps.map(x => `<li>${x}</li>`).join("")}</ol>`}
      <p class="mth-src"><b>Where the data comes from.</b> NASA's Physical Sciences Informatics (PSI) microgravity combustion investigations, and the Imperial thermo team's models built on them. Every source is listed under References.</p>
      <p class="mth-src"><b>Research support only</b>, not safety certification. Check the references before relying on a number.</p>
      ${madeHTML(M)}`;
  }

  // ---------- after it is on the page: stream the overview, reveal boxes in order ----------
  function stream(el) {
    if (!el || RM) return 0;
    const nodes = []; const walk = n => n.childNodes.forEach(c => c.nodeType === 3 ? nodes.push(c) : walk(c)); walk(el);
    const words = nodes.reduce((s, n) => s + (n.textContent.match(/\S+/g) || []).length, 0), step = Math.min(30, 1300 / Math.max(1, words));
    let i = 0;
    nodes.forEach(n => { const f = document.createDocumentFragment();
      n.textContent.split(/(\s+)/).forEach(p => { if (!p) return; if (/^\s+$/.test(p)) f.appendChild(document.createTextNode(p)); else { const s = document.createElement("span"); s.className = "tok"; s.style.animationDelay = Math.round(i++ * step) + "ms"; s.textContent = p; f.appendChild(s); } });
      n.replaceWith(f); });
    return i * step;
  }
  function reveal(root, delay = 0) {
    const els = [...root.querySelectorAll(".rv")];
    if (RM) { els.forEach(e => e.classList.add("in")); return () => {}; }
    const q = []; let timer = null, ready = false;
    const pump = () => { const e = q.shift(); if (!e) { timer = null; return; } e.classList.add("in"); timer = setTimeout(pump, 95); };
    const kick = () => { if (ready && !timer && q.length) { q.sort((a, b) => els.indexOf(a) - els.indexOf(b)); pump(); } };
    const io = new IntersectionObserver(es => { es.forEach(en => { if (en.isIntersecting) { io.unobserve(en.target); q.push(en.target); } }); kick(); }, { rootMargin: "0px 0px -6% 0px", threshold: .06 });
    els.forEach(e => io.observe(e));
    const t0 = setTimeout(() => { ready = true; kick(); }, delay);
    return () => { io.disconnect(); clearTimeout(t0); clearTimeout(timer); els.forEach(e => e.classList.add("in")); };
  }

  // ---------- plain-text version (copy, share) ----------
  function text(M) {
    const L = [`${M.title}`, `Question: ${M.q}`, `${forWho(M)}`, ""];
    if (M.summary) L.push(plain(M.summary), "");
    if (M.note) L.push(M.note, "");
    if (M.facts.length) { L.push("Key facts"); M.facts.forEach(f => L.push(`- ${f.value}: ${f.label}${f.refs.length ? " [" + f.refs.join(",") + "]" : ""}`)); L.push(""); }
    if (M.blocks.length || M.clarifications.length || M.function_pipeline.length) {
      html += `<div class="sec-h"><h2>Backend results</h2></div><div class="backend-results">${M.blocks.map(b => `<section class="box workflow-result">${WORKFLOW.render(b)}</section>`).join("")}</div>`;
      html += M.clarifications.map(c => `<section class="box workflow-result"><h3>More information needed</h3><p>${esc(c.question || c.message || "Supply the missing model inputs.")}</p>${(c.options || []).map(o => `<button class="chip" data-reply="${esc(typeof o === "string" ? o : o.label || o.value)}">${esc(typeof o === "string" ? o : o.label || o.value)}</button>`).join("")}</section>`).join("");
      if (M.function_pipeline.length) html += `<details class="workflow-result"><summary>Function execution details</summary><pre>${esc(JSON.stringify(M.function_pipeline, null, 2))}</pre></details>`;
    }
    if (M.finds.length) { L.push("Findings"); M.finds.forEach(f => L.push(`${f.n}. ${plain(f.text)}${f.refs.filter(Boolean).length ? " [" + [...new Set(f.refs.filter(Boolean))].join(",") + "]" : ""}`)); L.push(""); }
    if (M.limitations) L.push("What the data can't say", M.limitations, "");
    if (M.refs.length) { L.push("References"); M.refs.forEach(r => { L.push(`[${r.n}] ${r.title}${r.url ? " " + r.url : ""}`); (r.sub || []).forEach(s => L.push(`     ${s.text}${s.url ? " " + s.url : ""}`)); }); L.push(""); }
    L.push(madeLine(M));
    return L.join("\n");
  }

  // ---------- the question tab (above the prompt bar): the question, the steps, the rocket's rail, the thread ----------
  function steps(ctx) {
    return ["Processing your question with the Thermo backend", "Displaying returned results"];
  }
  // o: { q, p, s, state: thinking|stopped, line, open, thread, thinking: [step labels] }
  // The steps read bottom to top: the rocket climbs past each one as it is done.
  function qtab(o) {
    const thinking = o.state === "thinking", th = (o.thread || []).filter(h => h && h.q), st = steps(o);
    const status = thinking ? `<span class="shim">Thinking</span>` : `<span class="qt-line">${esc(o.line || "")}</span>`;
    const again = !thinking ? `<button type="button" class="tg" data-again>${ic("refresh")}Ask again</button>` : "";
    const list = th.length > 1 ? `<div class="qt-thread"><p class="lab">This thread · ${th.length} questions</p><ol>${th.map((h, i) => {
      const cur = String(h.q).trim().toLowerCase() === String(o.q).trim().toLowerCase();
      return `<li${cur ? ' class="on"' : ""}><span class="qn">${pad(i + 1)}</span><a href="${esc(UI.href(h.q, h.p, h.s))}"${cur ? ' aria-current="true"' : ""}>${esc(UI.label(h))}</a><small>${esc(new Date(h.t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }))}</small></li>`; }).join("")}</ol></div>` : "";
    return `<div class="qtab${o.open ? " open" : ""}" data-state="${o.state}" role="region" aria-label="Your question">
      <div class="qt-h">
        <button type="button" class="ib sm qt-tg" data-qtab aria-expanded="${!!o.open}" aria-label="${o.open ? "Hide" : "Show"} the steps${th.length > 1 ? " and this thread" : ""}">${ic("up")}</button>
        <span class="qt-ic">${thinking ? `<canvas class="tflame" aria-hidden="true"></canvas>` : ic(o.state === "stopped" ? "stop" : "check")}</span>
        <div class="qt-q"><b title="${esc(o.q)}">${esc(o.q)}</b><small>${esc(forWho(o))}${th.length > 1 ? ` · question ${th.findIndex(h => String(h.q).trim().toLowerCase() === String(o.q).trim().toLowerCase()) + 1} of ${th.length} in this thread` : ""}</small></div>
        <span class="qt-st" role="status" aria-live="polite">${status}</span>${again}
      </div>
      <div class="qt-b"><div class="qt-bi"><div class="qt-prog"><ol class="rk-steps">${st.map((x, i) => `<li class="${thinking ? (i === 0 ? "on" : "") : "done"}"><span>${esc(x)}</span></li>`).join("")}</ol>
        <div class="rail" aria-hidden="true"><i class="trail"></i><span class="rk-r">${UI.rocket()}</span></div></div>${list}</div></div>
    </div>`;
  }

  return { build, overview, full, reveal, stream, text, madeLine, methodHTML, qtab, steps, cites, chartArea, chartCap, expHTML, chartBoxHTML, forWho, STATUS_LABEL, LINKED, ENV, plain, firstSentence };
})();
