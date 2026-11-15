// ANSWER — turns the AI's reply into the answer page: an AI overview, key facts, the findings (each with the charts
// that show it), more from the data, follow-ups and a numbered reference list of everything used.
// The most relevant material comes first; boxes arrive in order as the answer lands and as you scroll to them.
// Every box opens full screen (js/expand.js). Written with SI assistance (Claude, Anthropic).
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
    linked: t => { const d = W.def(t); return (d && LINKED[d.model]) || []; }
  };
  const STATUS_LABEL = { physics: "Model calculation", reconstruction: "Reconstructs a NASA FLEX run", estimate: "Model estimate", synthetic: "Synthetic material",
    reduction: "Reduces measured data", screening: "Screening estimate", budget: "Thermal budget", illustrative: "Illustrative inputs", bound: "Theoretical bound" };
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
          desc: `Imperial thermo team model, run ahead of time by standin/precompute_models.py. Charts used: ${d.title}.`, model: d.model, charts: [t],
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
    const live = a.meta && a.meta.source === "live", R = Refs();
    const points = STORY.points(a, ENV);
    const facts = (a.key_facts || []).filter(f => f && f.label && f.value).slice(0, 3).map(f => ({ ...f, refs: f.psi_id && U.inv(f.psi_id) ? [R.psi(f.psi_id)] : [] }));
    const evNote = {}; (a.evidence || []).forEach(e => { if (e && e.psi_id) evNote[String(e.psi_id).toUpperCase()] = e; });
    const finds = points.map((p, k) => {
      const refs = [];
      p.psi_ids.forEach(id => { const n = R.psi(id); refs.push(n); const e = evNote[id]; if (e && e.note) R.note(n, e.note, e.tag); });
      p.charts.forEach(t => { const n = R.model(t); refs.push(n); R.chart(n, t); });
      return { n: k + 1, text: p.text, psi: p.psi_ids, charts: p.charts, refs };
    });
    if (a.meta?.provider === "thermo") (a.evidence || []).forEach(e => R.source(e));
    const shownCharts = new Set(points.flatMap(p => p.charts));
    const extra = (a.widgets || []).map(w => w && w.type).filter(t => t && MW.lib[t] && !shownCharts.has(t)).filter((t, i, s) => s.indexOf(t) === i).slice(0, 4)
      .map(t => { const n = R.model(t); R.chart(n, t); return { type: t, refs: [n] }; });
    (a.evidence || []).forEach(e => { if (e && U.inv(String(e.psi_id || "").toUpperCase())) { const n = R.psi(String(e.psi_id).toUpperCase()); R.note(n, e.note, e.tag); } });
    // NASA experiments worth a card: cited ones, most-cited first, skipping those already inside a finding box
    const count = {}; finds.forEach(f => f.psi.forEach(id => count[id] = (count[id] || 0) + 2)); Object.keys(evNote).forEach(id => count[id] = (count[id] || 0) + 1);
    const inFinding = new Set(finds.filter(f => !f.charts.length && f.psi[0]).map(f => f.psi[0]));
    const exps = Object.keys(count).filter(id => U.inv(id) && !inFinding.has(id)).sort((x, y) => count[y] - count[x]).slice(0, 6).map(id => ({ psi: id, refs: [R.psi(id)] }));
    let summary = a.summary || "", note = "";
    if (!live) note = a.meta && a.meta.error ? `The AI did not answer this time (${String(a.meta.error).slice(0, 160)}). The findings below were picked from the words in your question; ask again in a moment.`
      : "Preview without the AI: the findings and charts below were picked from the words in your question. Start the server (see the README) for a written answer.";
    if (!live) summary = "";
    const fu = (a.follow_ups || []).filter(Boolean).slice(0, 3);
    const seed = TILER.hash(ctx.q || "");
    return {
      q: ctx.q, p: ctx.p || null, s: ctx.s || "iss", live, meta: a.meta || {}, at: ctx.at || Date.now(), cached: !!ctx.cached,
      title: plain(a.title) || ctx.q, summary, note, facts, finds, extra, exps, blocks: a.blocks || [],
      limitations: plain(a.limitations), follow_ups: fu.length ? fu : TW.ASK_NEXT.map((x, i) => TW.ASK_NEXT[(i + seed) % TW.ASK_NEXT.length]).filter(x => x !== ctx.q).slice(0, 3),
      refs: R.list, dropped: a.dropped || [], raw: a
    };
  }

  // ---------- boxes ----------
  const forWho = M => `${M.p ? "For " + UI.personaLabel(M.p).toLowerCase() + "s" : "General answer"} · ${UI.envLabel(M.s)}`;
  const chartArea = (t, h) => { const [aspect] = MW.shape(t); return `<div class="bc" style="aspect-ratio:${Math.max(1.15, Math.min(2.6, aspect)).toFixed(2)}${h ? ";max-height:" + h + "px" : ""}">${MW.tile(t)}</div>`; };
  const chartCap = t => { const d = W.def(t); return `<div class="ccap"><b>${esc(d.title)}</b><span>${esc([d.model, STATUS_LABEL[d.status]].filter(Boolean).join(" · "))}</span></div>`; };
  const head = (label, meta) => `<div class="bh"><span class="bl">${label}</span>${meta ? `<span class="bm">${esc(meta)}</span>` : ""}<span class="bx" aria-hidden="true">${ic("expand")}</span></div>`;
  const boxAttrs = (i, cls, label) => `class="box ${cls} rv" data-box="${i}" tabindex="0" role="button" aria-label="${esc(label)}: open full screen"`;
  function expMini(id) { const i = U.inv(id); if (!i) return ""; return `<div class="exp-mini"><span class="lab">NASA experiment</span><b>${esc(i.acronym || i.id)}</b><span>${esc(i.title.length > 110 ? i.title.slice(0, 108) + "…" : i.title)}</span></div>`; }

  function findingHTML(f, i, wide) {
    const meta = [...f.psi.map(id => (U.inv(id) || {}).acronym || id), ...f.charts.map(t => W.def(t).model)].filter((x, j, s) => x && s.indexOf(x) === j).join(" · ");
    const text = `<p class="bt">${esc(plain(f.text))}${cites(f.refs)}</p>`;
    if (!wide) return `<article ${boxAttrs(i, "s6 find", "Finding " + f.n)}>${head(`Finding <b>${pad(f.n)}</b>`, meta)}${text}
      ${f.charts.length ? `<div style="margin-top:auto">${chartArea(f.charts[0])}</div>${chartCap(f.charts[0])}` : expMini(f.psi[0])}</article>`;
    const aside = f.charts.length > 1 ? `<div class="charts">${f.charts.map(t => `<div>${chartArea(t)}${chartCap(t)}</div>`).join("")}</div>`
      : f.charts.length ? `<div>${chartArea(f.charts[0], 420)}${chartCap(f.charts[0])}</div>` : `<div style="display:flex">${expMini(f.psi[0])}</div>`;
    return `<article ${boxAttrs(i, "s12 find", "Finding " + f.n)}>${head(`Finding <b>${pad(f.n)}</b>`, meta)}<div class="duo"><div>${text}</div>${aside}</div></article>`;
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

  function overviewHTML(M, factsHTML) {
    const pill = M.meta?.provider === "thermo" ? `<span class="pill">${esc((M.meta.status || "").replaceAll("_", " "))}</span>` : !M.live ? `<span class="pill warn">${M.meta && M.meta.error ? "AI unavailable" : "Preview · no AI"}</span>` : M.cached ? `<span class="pill">Saved answer</span>` : "";
    return `<article class="box ov s12 rv" data-box="0" aria-label="AI overview">
      <div class="bh"><span class="bl">${UI.mark()}AI overview</span>${pill}<button type="button" class="ib sm" data-open="0" aria-label="Open the overview full screen" title="Open full screen" style="margin-left:auto">${ic("expand")}</button></div>
      <h1>${esc(M.title)}</h1>
      ${M.summary ? `<div class="sum" data-stream>${md(M.summary)}</div>` : ""}
      ${M.note ? `<p class="note">${esc(M.note)}</p>` : ""}
      ${factsHTML ? `<div class="fstrip">${factsHTML}</div>` : ""}
      <div class="ov-acts"><button type="button" class="ib sm" data-act="copy" aria-label="Copy answer" title="Copy answer">${ic("copy")}</button><button type="button" class="ib sm" data-act="again" aria-label="Ask again" title="Ask again">${ic("refresh")}</button><span class="cpm" role="status"></span></div>
    </article>`;
  }

  // the page body; boxes[] keeps what each box is, for the full-screen view
  function render(M) {
    const boxes = [{ kind: "overview" }]; let html = "";
    const add = b => (boxes.push(b), boxes.length - 1);
    const facts = M.facts.map(f => factHTML(f, add({ kind: "fact", f }))).join("");
    html += `<div class="grid top-grid">${overviewHTML(M, facts)}</div>`;
    if (M.raw.clarifications?.length) {
      html += `<section class="box s12"><h2>More information needed</h2>${M.raw.clarifications.map(c => `<p>${esc(c.question)}${c.unit ? ` (${esc(c.unit)})` : ""}</p>${(c.choices || []).map(choice => `<button type="button" class="chip" data-reply="${esc(choice)}">${esc(choice)}</button>`).join("")}`).join("")}<p>Reply in the question box to continue this task.</p></section>`;
    }
    if (M.finds.length) {
      const wide = packFindings(M.finds);
      html += `<div class="sec-h"><h2>Findings</h2><p>In reading order, each with the NASA data it rests on. Open any box to explore it.</p></div>
        <div class="grid">${M.finds.map((f, k) => findingHTML(f, add({ kind: "finding", f }), wide[k])).join("")}</div>`;
    }
    if (M.blocks.length) html += `<div class="sec-h"><h2>Results</h2></div><div class="grid">${M.blocks.map(b => `<article class="box s12 rv workflow-result">${WORKFLOW.render(b)}</article>`).join("")}</div>`;
    const more = [];
    if (M.limitations) more.push(`<article ${boxAttrs(add({ kind: "lim", text: M.limitations }), "s12 lim", "What the data can't say")}>${head("What the data can't say")}<p class="bt">${esc(M.limitations)}</p></article>`);
    M.exps.forEach(e => more.push(expHTML(e, add({ kind: "exp", e }), M.exps.length === 2 ? "s6" : "s4")));
    M.extra.forEach(c => more.push(chartBoxHTML(c, add({ kind: "chart", c }), "s6")));
    if (more.length) html += `<div class="sec-h"><h2>More from the data</h2><p>The experiments behind the findings, and what the data can't tell you.</p></div><div class="grid">${more.join("")}</div>`;
    html += `<div class="sec-h"><h2>Ask next</h2></div><div class="fups rv">${M.follow_ups.map(q => `<a class="chip" href="${esc(UI.href(q, UI.persona(), UI.env()))}" data-followup>${ic("spark")}${esc(q)}</a>`).join("")}</div>`;
    html += `<div class="sec-h" id="references"><h2>References</h2><p>Everything this answer used, so you can check it. Numbers in the text point here.</p></div>${refsHTML(M)}${madeHTML(M)}`;
    return { html, boxes };
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
    const m = M.meta || {}, when = new Date(M.at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
    const who = M.live ? `Written by ${m.provider || "the AI"}${m.model ? " / " + m.model : ""}${m.stand_in ? " through the team's stand-in server" : ""}${m.seconds ? ` in ${m.seconds} s` : ""}` : "No AI connected: preview built from the question's words";
    const graph = M.meta?.graph_id ? ` Graph: ${M.meta.graph_id}.` : "";
    const checks = M.meta?.provider === "thermo" ? ` Source excerpts and calculation outputs retain their original provenance.${graph}` : M.live ? ` The server removed anything it could not match to the data${M.dropped.length ? ` (${M.dropped.length} item${M.dropped.length > 1 ? "s" : ""}: ${M.dropped.slice(0, 4).join(", ")})` : " (nothing needed removing)"}.` : "";
    return `${who}, ${when}. ${forWho(M)}.${checks} Sources: NASA Physical Sciences Informatics (PSI) combustion investigations and the Imperial thermo team's models. Research support only, not safety certification.`;
  }
  const madeHTML = M => `<p class="made">How this answer was made: ${esc(madeLine(M))}</p>`;

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
    if (M.finds.length) { L.push("Findings"); M.finds.forEach(f => L.push(`${f.n}. ${plain(f.text)}${f.refs.filter(Boolean).length ? " [" + [...new Set(f.refs.filter(Boolean))].join(",") + "]" : ""}`)); L.push(""); }
    if (M.limitations) L.push("What the data can't say", M.limitations, "");
    if (M.refs.length) { L.push("References"); M.refs.forEach(r => { L.push(`[${r.n}] ${r.title}${r.url ? " " + r.url : ""}`); (r.sub || []).forEach(s => L.push(`     ${s.text}${s.url ? " " + s.url : ""}`)); }); L.push(""); }
    L.push(madeLine(M));
    return L.join("\n");
  }

  // ---------- thinking ----------
  function thinkingHTML(ctx) {
    const s = API.status, who = ctx.p ? UI.personaLabel(ctx.p).toLowerCase() : "a general reader";
    const steps = [`Reading your question for ${ctx.p ? "a " + who : who}`, `Searching ${DATA.investigations.length} NASA PSI investigations`, "Choosing the thermo-model charts that show the answer",
      s.mode === "live" && s.provider ? `Writing the answer with ${s.provider}${s.model ? " / " + s.model : ""}` : "Building a preview (no AI connected)", "Checking every citation against the data"];
    return `<div class="think" role="status" aria-live="polite"><div class="th-h"><canvas class="tflame" aria-hidden="true"></canvas><span class="shim">Thinking</span>
      <button type="button" class="tg" aria-expanded="true" data-steps>Hide steps${ic("chev")}</button></div><ol class="steps">${steps.map(x => `<li>${esc(x)}</li>`).join("")}</ol></div>`;
  }

  return { build, render, reveal, stream, text, madeLine, thinkingHTML, cites, chartArea, chartCap, expHTML, chartBoxHTML, forWho, STATUS_LABEL, LINKED, ENV, plain, firstSentence };
})();
