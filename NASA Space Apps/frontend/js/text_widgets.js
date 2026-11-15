// TEXT WIDGETS — the words around the charts. They are flexible boxes: the tiler gives the charts the shapes they
// look best in, then these fill the space that is left (answer to the question, key facts, what each chart shows,
// evidence, limits, what to ask next). Same box style as the chart widgets; click one to read it in full.
// Written with SI assistance (Claude, Anthropic).
window.TW = (() => {
  const { esc, md } = U;
  const plain = s => String(s ?? "").replace(/\*\*/g, "").replace(/\s+/g, " ").trim();
  const clip = (s, n) => { const t = plain(s); return t.length > n ? t.slice(0, n - 1).trimEnd() + "…" : t; };
  const sentence = s => { const t = plain(s), m = t.match(/^.*?[.!?](\s|$)/); return m ? m[0].trim() : t; };

  const PREVIEW_NOTE = "This is a preview without the AI: the charts were picked from the words in your question. Start the stand-in server (see the README) to get a written answer here.";
  const BADGES = [
    ["physics", "A calculation from the model's equations, no fitted data."],
    ["reconstruction", "Reproduces a real NASA test (FLEX) from its own data."],
    ["estimate", "A model prediction, checked against a NASA observation."],
    ["synthetic", "Illustrative material the thermo team made up — shapes, not real numbers."]
  ];
  const MODELS = [
    ["THM-02", "Gas transport and the Lewis number: how heat and gases spread in different fuels and cabin atmospheres."],
    ["THM-11", "Droplet burning: an n-decane droplet going from hot flame to cool flame, checked against NASA FLEX runs."],
    ["THM-16", "Time to ignition of a solid: a slab heated until it ignites (synthetic demo material)."],
    ["THM-01", "Flame temperature: the hottest a flame can get in ISS, lunar habitat and spacesuit air."],
    ["THM-03", "Flame position: where a microgravity flame sits around a burner as oxygen changes."],
    ["THM-07", "Blow-off: how fast ventilation has to be to blow a flame out."],
    ["THM-08", "Buoyancy against airflow on the ISS, Moon, Mars and Earth (theoretical bounds for Moon and Mars)."],
    ["THM-09", "Burn rate: how oxygen level changes how fast a plastic surface gasifies."],
    ["THM-04", "Fire power: heat release rate and total energy from a measured oxygen-calorimetry burn."],
    ["THM-05", "Flame spread against airflow: spread speed versus sheet thickness, checked against measured points."],
    ["THM-06", "Concurrent flame spread: how fast a flame front grows along a sample (illustrative inputs)."],
    ["THM-15", "Soot inception: whether the flame is hot enough to start making soot (screening estimate)."],
    ["THM-17", "Limiting oxygen: the lowest oxygen that still burns at each airflow speed."],
    ["THM-18", "Suppression budget: heat absorbed by CO₂ dilution and water mist (illustrative inputs)."],
    ["THM-19", "Cabin pressure: pressure and temperature rise in a sealed cabin after a fire (illustrative inputs)."],
    ["THM-20", "Smoke ageing: how smoke particles change on the way along a duct to a detector (illustrative inputs)."]
  ];
  const ASK_NEXT = [
    "Why does helium behave differently as a fire suppressant?",
    "How long does it take a solid to ignite under a radiant heater?",
    "How well does the droplet model match NASA's flame data?",
    "How do the ISS, lunar habitat and spacesuit atmospheres differ?",
    "Which fuels are most likely to form unstable flame balls?",
    "What does the oxygen level do to flame stability?"
  ];

  const DEF = {
    workflow_result: { title: "Thermo result", desc: "Output from the Thermo research workflow.", src: "Thermo workflow" },
    answer: { title: "Answer", desc: "A direct answer to your question, written by the stand-in AI from the NASA PSI investigations in the data. The Evidence box lists what it relied on.",
      src: "Written by the stand-in AI from the NASA PSI data. Check it against the evidence." },
    key_fact: { title: "Key fact", desc: "One number or fact copied from the data, with where it came from.", src: "Copied from the NASA PSI data or the challenge brief." },
    explain: { title: "What the charts show", desc: "One line on why each chart is on this dashboard, for your question. Open any chart to see it in full.", src: "The AI chooses the charts; the descriptions come from the thermo team's models." },
    evidence: { title: "Evidence", desc: "The NASA PSI investigations the answer relied on. Open one to see a dashboard about it.", src: "Investigation list from the NASA PSI database." },
    limitations: { title: "What the data can't say", desc: "The limits of what this data can tell you about your question.", src: "Written by the stand-in AI." },
    follow_ups: { title: "Ask next", desc: "Questions that would make a useful next dashboard. Click one to ask it.", src: "" },
    point: { title: "Point", desc: "One step of the answer, and the NASA experiments it rests on. The chart or experiment card beside it shows this step.",
      src: "Written by the stand-in AI from the NASA PSI data. Check it against the experiments named." },
    experiment: { title: "NASA experiment", desc: "The NASA PSI investigation this step of the answer rests on.", src: "From the NASA Physical Sciences Informatics (PSI) database." },
    about: { title: "About these widgets", desc: "How to read the widget badges and which model each chart comes from.", src: "" }
  };
  const has = t => t in DEF, def = t => DEF[t];
  const titleOf = (t, p = {}) => t === "workflow_result" ? (p.title || p.model_id || (p.type === "inspection" ? "File inspection" : "Thermo result")) : t === "point" ? `Point ${p.n || ""}`.trim() : t === "key_fact" ? (p.label || DEF.key_fact.title) : t === "about" ? (p.kind === "models" ? "The thermo models" : "Badges") : DEF[t].title;

  const askHref = q => (U.askHref ? U.askHref(q) : "#q=" + encodeURIComponent(q));
  const invOf = id => U.inv(id) || null;
  const invName = (id, full) => { const i = invOf(id); return i ? (full ? U.invTitle(i) : U.invLabel(i)) : id; };

  // ---------- content ----------
  function stat(p, full) {
    const i = p.psi_id ? invOf(p.psi_id) : null, src = [p.source, p.psi_id].filter(Boolean).join(" · ");
    const lw = Math.max(0, ...String(p.value).split(/\s+/).map(x => x.length)), n = String(p.value).length, sz = full ? "" : (lw <= 6 && n <= 8) ? "" : (lw <= 9 && n <= 16) ? " md" : " sm";
    return `<b class="t-stat${sz}">${esc(p.value)}</b>` +
      (full ? `<p class="t-big-label">${esc(p.label || "")}</p>` : "") +
      `<span class="t-src">${esc(src)}</span>` +
      (full && i ? `<p><a href="${esc(U.invHref(i.id))}">Dashboard about ${esc(U.invTitle(i))}</a> · <a href="${esc(i.url)}" target="_blank" rel="noopener">PSI ↗</a></p>` : "");
  }
  const year = d => { const m = String(d || "").match(/(\d{4})/); return m ? m[1] : ""; };
  function expBody(p, full) {
    const i = invOf(p.psi_id);
    if (!i) return `<p>${esc(p.psi_id || "")}</p>`;
    const yrs = [year(i.start), year(i.end)].filter(Boolean), when = yrs.length ? (yrs[0] === yrs[1] || yrs.length === 1 ? yrs[0] : yrs.join("–")) : "";
    const meta = [i.projectType, i.platform, when, String(i.center || "").replace(/\s*\(.*\)/, "")].filter(Boolean).map(esc).join(" · ");
    return `<p class="t-exp-name"><b>${esc(i.acronym || i.id)}</b>${i.acronym ? ` <span class="t-id">${esc(i.id)}</span>` : ""}</p>
      <p class="t-exp-title">${esc(full ? i.title : clip(i.title, 110))}</p><p class="t-src">${meta}</p>
      <p>${esc(full ? plain(i.objectives) : clip(i.objectives, 260))}</p>` +
      (full ? `<p><a href="${esc(U.invHref(i.id))}">Dashboard about ${esc(U.invTitle(i))}</a> · <a href="${esc(i.url)}" target="_blank" rel="noopener">PSI ↗</a></p>` : "");
  }
  // ---------- the theory behind a chart (data/literature.js, from the thermo team's thm_literature_map.py) ----------
  const litOf = t => { const d = W.def(t), L = window.DATA && DATA.literature; return d && L && L[d.model] ? { model: d.model, ...L[d.model] } : null; };
  const srcLink = s => s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.short)}</a>` : esc(s.short);
  function methodLine(charts, full) {               // "Method: Richardson-number buoyancy scaling (Sacksteder 1990, Olson et al. 1988)"
    const seen = new Set(), ls = (charts || []).map(litOf).filter(l => l && !seen.has(l.model) && seen.add(l.model));
    if (!ls.length) return "";
    return `<p class="t-method">Method: ${ls.map(l => `${esc(l.method)} (${l.sources.slice(0, full ? 3 : 2).map(full ? srcLink : s => esc(s.short)).join(", ")})`).join("; ")}</p>`;
  }
  function litHTML(t) {                             // the "Where this comes from" block in the enlarged chart view
    const l = litOf(t); if (!l) return "";
    return `<p class="focus-sub">Where this comes from</p><p><b>${esc(l.method.charAt(0).toUpperCase() + l.method.slice(1))}.</b> ${esc(l.summary)}</p>` +
      (l.equations.length ? `<pre class="lit-eq">${l.equations.map(esc).join("\n")}</pre>` : "") +
      `<ol class="lit-src">${l.sources.map(s => `<li>${esc(s.citation)}${s.url ? ` <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.id || "link")} ↗</a>` : s.id ? ` <span class="t-id">${esc(s.id)}</span>` : ""}${s.relevance ? `<br><span class="lit-why">${esc(s.relevance)}</span>` : ""}</li>`).join("")}</ol>` +
      `<p class="focus-source">Evidence boundary: ${esc(l.boundary)}${l.psi.length ? " · aligned with " + esc(l.psi.join("; ")) : ""} · literature map by the thermo team (thm_literature_map.py)</p>`;
  }

  function body(type, p = {}, full = false) {
    switch (type) {
      case "point": return md(p.text) + ((p.psi_ids || []).length ? `<p class="t-rests">NASA data: ${(p.psi_ids || []).map(id => full
        ? `<a href="${esc(U.invHref(id))}">${esc(invName(id, true))}</a>` : `<b>${esc(invName(id))}</b>`).join(", ")}</p>` : "") + methodLine(p.charts, full);
      case "experiment": return expBody(p, full);
      case "workflow_result": return workflowResult(p, full);
      case "answer": return (p.note ? `<div class="t-note">` : "") + md(p.text) + (p.note ? `</div>` : "");
      case "limitations": return md(p.text);
      case "key_fact": return stat(p, full);
      case "explain": return `<ul class="t-list">${(p.items || []).map(it => `<li><b>${esc(it.title)}</b> ${esc(full ? it.text : clip(it.text, 90))}</li>`).join("")}</ul>`;
      case "evidence": return `<ul class="t-list">${(p.items || []).map(e => evidenceItem(e, full)).join("")}</ul>`;
      case "follow_ups": return `<ul class="t-list t-links">${(p.items || []).map(q => `<li><a href="${esc(askHref(q))}">${esc(q)}</a></li>`).join("")}</ul>`;
      case "about": return p.kind === "models"
        ? `<ul class="t-list">${MODELS.map(([id, t]) => `<li><span class="t-id">${id}</span> ${esc(t)}</li>`).join("")}</ul>`
        : `<ul class="t-list">${BADGES.map(([k, t]) => `<li>${MW.STATUS[k]} ${esc(t)}</li>`).join("")}</ul>`;
    }
    return "";
  }
  const safeUrl = url => typeof url === "string" && /^https?:\/\//i.test(url) ? url : null;
  function evidenceItem(e, full) {
    const note = e.note ? " — " + esc(full ? e.note : clip(e.note, 80)) : "";
    if (e.label && !e.psi_id) {
      const url = safeUrl(e.url);
      const title = url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(e.label)} ↗</a>` : esc(e.label);
      return `<li>${title}${note}</li>`;
    }
    const id = `<span class="t-id">${esc(e.psi_id)}</span>`;
    if (!full) return `<li>${id} ${esc(invName(e.psi_id))}${note}</li>`;
    const url = safeUrl(e.url || invOf(e.psi_id)?.url);
    const source = url ? ` · <a href="${esc(url)}" target="_blank" rel="noopener">View source ↗</a>` : "";
    return `<li><a href="${esc(U.invHref(e.psi_id))}">${esc(invName(e.psi_id, true))}</a> ${id}${note}${source}</li>`;
  }

  function axisFormatter(ticks) {
    if (new Set(ticks.map(CH.fmt)).size === ticks.length) return CH.fmt;
    const step = Math.abs(ticks[1] - ticks[0]);
    const decimals = Math.max(0, Math.ceil(-Math.log10(step)));
    const magnitude = Math.max(...ticks.map(Math.abs));
    if (decimals <= 10 && magnitude < 1e9) return value => value.toFixed(decimals);
    const digits = Math.max(1, Math.min(16, Math.ceil(Math.log10(magnitude / step)) + 1));
    return value => value.toPrecision(digits);
  }

  function workflowResult(p, full) {
    const label = [p.illustrative ? "Illustrative" : "", (p.evidence_type || "").replaceAll("_", " ")].filter(Boolean).join(" · ");
    const citation = p.source_file_ids?.length ? `<p>Source files: ${esc(p.source_file_ids.join(", "))}</p>` : "";
    const header = label ? `<p class="muted">${esc(label)}</p>` : "";
    if (p.type === "chart" && p.x?.values?.length && p.series?.length) {
      const plots = p.series.map(series => {
        const points = p.x.values.map((x, i) => [x, series.values[i]]).filter(pair => pair.every(Number.isFinite));
        if (!points.length) return "";
        const bounds = values => {
          let lo = Infinity, hi = -Infinity;
          for (const v of values) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
          return lo === hi ? [lo - 1, hi + 1] : [lo, hi];
        };
        const x = bounds(points.map(pair => pair[0])), y = bounds(points.map(pair => pair[1]));
        const xticks = CH.range(...x, 4), yticks = CH.range(...y, 4);
        return `<div style="height:${full ? 280 : 188}px">${CH.host(size => {
          const f = CH.frame(size, { x, y, xticks, yticks, xfmt: axisFormatter(xticks), yfmt: axisFormatter(yticks),
            xlabel: p.x.label, xunit: p.x.unit, ylabel: series.label, yunit: series.unit });
          const marks = p.chart_type === "scatter"
            ? points.map(([xv, yv]) => CH.dot(f.sx(xv), f.sy(yv), { r: 2 })).join("")
            : CH.line(points, f.sx, f.sy);
          return f.axes + marks;
        }, { label: series.label })}</div>`;
      }).join("");
      return header + plots + citation;
    }
    const url = safeUrl(p.url);
    if (url) return `<p><a href="${esc(url)}" target="_blank" rel="noopener">Open ${esc(p.type)} ↗</a></p>`;
    if (p.type === "inspection") {
      const preview = p.row_count != null ? `${p.row_count} rows` : p.file_id;
      return `<p>${esc(p.message || preview || "")}</p>` +
        (full ? `<pre>${esc(JSON.stringify(p, null, 2))}</pre>` : "");
    }
    const data = p.data || {};
    const assumptions = Array.isArray(data.assumptions) ? data.assumptions.filter(s => typeof s === "string" && s.trim()) : [];
    const note = assumptions.length
      ? `<h3>Model assumptions and defaults</h3><ul class="t-list">${assumptions.map(s => `<li>${esc(s)}</li>`).join("")}</ul>`
      : "";
    const summary = p.result_summary ? `<p>${esc(p.result_summary)}</p>` : "";
    const details = full ? `<pre>${esc(JSON.stringify(p.data || p, null, 2))}</pre>` : "";
    return header + citation + summary + note + (details || (summary ? "" : "<p>Open to read the calculation output.</p>"));
  }

  const srcOf = (t, p = {}) => t === "answer" && p.note ? "Preview mode: no AI connected." : DEF[t].src;
  const full = (t, p) => body(t, p, true);

  // ---------- shape: how much room the words need, and which proportions read well ----------
  const SHAPES = {   // [natural, narrowest, widest] width:height
    workflow_result: [1.4, 0.65, 3.5], answer: [1.35, 0.85, 2.3], key_fact: [1.25, 0.85, 1.9], explain: [1.2, 0.6, 2.4], evidence: [1.2, 0.55, 2.4],
    limitations: [1.7, 0.9, 3.2], point: [1.4, 0.6, 3.5], experiment: [1.3, 0.7, 2.6], follow_ups: [1.5, 0.7, 3.2], about: [1.3, 0.7, 2.4]
  };
  function chars(t, p = {}) {
    if (t === "answer" || t === "limitations") return plain(p.text).length;
    if (t === "explain") return (p.items || []).reduce((s, it) => s + it.title.length + Math.min(90, plain(it.text).length) + 6, 0);
    if (t === "evidence") return (p.items || []).reduce((s, e) => s + 14 + Math.min(80, plain(e.note).length) + 8, 0);
    if (t === "follow_ups") return (p.items || []).reduce((s, q) => s + String(q).length + 10, 0);
    if (t === "about") return p.kind === "models" ? 280 : 250;
    if (t === "point") return plain(p.text).length + (p.psi_ids || []).length * 14 + ((p.charts || []).length ? 70 : 0);
    if (t === "workflow_result") return p.type === "chart" ? 2200 : 450;
    if (t === "experiment") return 300;
    return 0;
  }
  function shape(t, p = {}) {
    const [a, lo, hi] = SHAPES[t];
    const need = t === "key_fact" ? 24000 : 15000 + chars(t, p) * (t === "answer" ? 150 : 135) * (t === "answer" && p.note ? 0.9 : 1);
    return { flex: true, aspect: a, amin: lo, amax: hi, need };
  }

  // ---------- tile (the box on the dashboard) ----------
  // room the words need at story-page type size (px²), for STORY.solve
  const need = (t, p = {}) => t === "key_fact" ? 26000 : 14000 + chars(t, p) * (t === "point" ? 230 : 175);
  function tile(type, o = {}) {
    const p = o.params || {}, i = o.i || 0;
    return `<section class="widget sketch ttile t-${esc(type)}" data-type="${esc(type)}" data-i="${i}" tabindex="0" role="button" aria-label="${esc(titleOf(type, p))} — open"
      style="--i:${i};${o.place || ""}"><span class="w-label">${esc(titleOf(type, p))}</span><div class="t-body">${body(type, p, false)}</div></section>`;
  }

  // ---------- which text boxes go on a dashboard ----------
  // a = the AI's answer (or null), charts = [{type, params, why}], o = { live, question, library }
  function assemble(a, charts, o = {}) {
    if (o.library) return charts.concat([{ type: "about", params: { kind: "badges" } }, { type: "about", params: { kind: "models" } }]);
    a = a || {};
    const ch = charts.slice(0, 8), cand = {};
    if (o.live === false) cand.answer = { type: "answer", params: { text: o.error ? `The AI did not answer this time (${String(o.error).slice(0, 140)}). The charts were picked from the words in your question; try asking again in a moment.` : PREVIEW_NOTE, note: true } };
    else if (plain(a.summary)) cand.answer = { type: "answer", params: { text: a.summary } };
    if (ch.length >= 2) cand.explain = { type: "explain", params: { items: ch.map(w => { const d = W.def(w.type); return { title: d.title, text: plain(w.why) || sentence(d.desc) }; }) } };
    const fu = (a.follow_ups || []).filter(Boolean).slice(0, 3);
    const seed = TILER.hash(o.question || "");
    cand.follow_ups = { type: "follow_ups", params: { items: fu.length ? fu : ASK_NEXT.map((q, i) => ASK_NEXT[(i + seed) % ASK_NEXT.length]).filter(q => q !== o.question).slice(0, 3) } };
    const facts = (a.key_facts || []).filter(f => f && f.label && f.value).slice(0, 3).map(f => ({ type: "key_fact", params: f }));
    if ((a.evidence || []).length) cand.evidence = { type: "evidence", params: { items: a.evidence.slice(0, 6) } };
    if (plain(a.limitations)) cand.limitations = { type: "limitations", params: { text: a.limitations } };
    // when there are lots of charts there is less room: keep the most useful text first
    const slots = Math.max(3, 14 - ch.length), pick = [];
    [cand.answer, cand.explain, cand.follow_ups, facts[0], cand.evidence, facts[1], cand.limitations, facts[2]].forEach(t => { if (t && pick.length < slots) pick.push(t); });
    const of = ty => pick.filter(t => t.type === ty);
    return [...of("answer"), ...of("key_fact"), ...ch, ...of("explain"), ...of("evidence"), ...of("limitations"), ...of("follow_ups")];
  }

  return { has, def, titleOf, body, full, srcOf, shape, need, tile, assemble, ASK_NEXT, PREVIEW_NOTE, litHTML, litOf };
})();
