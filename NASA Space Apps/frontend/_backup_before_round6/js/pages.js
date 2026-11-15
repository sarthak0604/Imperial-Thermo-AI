// PAGES — one render function per route. Each returns { html, mount(root)? }.
window.PAGES = (() => {
  const { esc, md, badge, inv, invLabel, short, link } = U;
  const ROLES = ["prevention", "detection", "suppression"];
  const unique = arr => [...new Set(arr)].filter(Boolean).sort();

  function scenarioLine() {
    const s = DATA.scenarios[S.get().scenario];
    return `<p class="muted">Scenario: <b>${esc(s.label)}</b> — ${esc(s.pressure)}, ${esc(s.o2)} O₂, ${esc(s.gravity)}</p>`;
  }
  function askForm(q = "") {
    return `<form data-form="ask"><label>Ask a question<br>
      <textarea name="q" rows="3" cols="70" placeholder="e.g. Can this fabric burn in a lunar habitat?">${esc(q)}</textarea></label><br>
      <button type="submit">Ask</button></form>`;
  }
  function invCard(i) {
    const inCompare = S.get().compare.includes(i.id);
    return `<article class="card">
      <h3>${link("#/investigation/" + i.id, U.invTitle(i))}</h3>
      <p>${esc(i.title)}</p>
      <p class="muted">${esc(i.projectType)} · ${esc(i.platform || "—")} · draft tags: ${esc(i.draft.fuelPhase)}, ${esc(i.draft.hardwareGroup)}, ${esc(i.draft.roles.join("/") || "none")}, relevance ${esc(i.draft.relevance)}</p>
      <p>${esc(short(i.objectives))}</p>
      <label><input type="checkbox" data-action="toggle-compare" data-id="${esc(i.id)}" ${inCompare ? "checked" : ""}> Compare</label>
    </article>`;
  }

  function compareTable(ids) {
    const items = ids.map(inv).filter(Boolean);
    if (!items.length) return "<p>No investigations selected.</p>";
    const rows = [
      ["Title", i => i.title], ["Type", i => i.projectType], ["Platform", i => i.platform], ["Hardware", i => i.hardware],
      ["Fuel phase (draft)", i => i.draft.fuelPhase], ["Hardware group (draft)", i => i.draft.hardwareGroup],
      ["Fire-safety role (draft)", i => i.draft.roles.join(", ")], ["Sub-area", i => i.subArea],
      ["Dates", i => `${i.start} → ${i.end}`], ["Keywords", i => i.keywords],
      ["Objectives", i => short(i.objectives, 400)], ["Related", i => i.related.join(", ")],
      ["Fuel / sample size", () => "TODO (from experimental tables / graph)"], ["O₂ / pressure / airflow", () => "TODO"], ["Sensors", () => "TODO"]
    ];
    return `<table class="compare"><tr><th></th>${items.map(i => `<th>${link("#/investigation/" + i.id, invLabel(i))}</th>`).join("")}</tr>
      ${rows.map(([k, f]) => `<tr><th>${esc(k)}</th>${items.map(i => `<td>${esc(f(i) || "—")}</td>`).join("")}</tr>`).join("")}</table>`;
  }

  // ---------- HOME ----------
  function home() {
    const st = S.get();
    const personaButtons = Object.entries(PERSONAS).map(([k, p]) =>
      `<button data-action="set-persona" data-value="${k}" ${st.persona === k ? "disabled" : ""}>I'm a ${esc(p.label)}</button>`).join(" ");
    const intro = `<h1>${U.pv(PROJECT.name, "project name")}</h1>
      <p>${PROJECT.tagline ? esc(PROJECT.tagline) : U.unknown("tagline")}</p>
      <p class="muted">${esc(PROJECT.concept)}</p>`;
    if (!st.persona) return { html: `${intro}
      <h2>Who are you?</h2><p>${personaButtons}</p>${askForm()}` };
    const cfg = S.personaCfg();
    const ex = DATA.mockAnswers[st.persona];
    return { html: `
      ${intro}
      <p>Viewing as <b>${esc(cfg.label)}</b>. Switch: ${personaButtons}</p>
      ${scenarioLine()}
      ${askForm()}
      <p>Example: ${link("#/ask?q=" + encodeURIComponent(ex.question), ex.question)}</p>
      <h2>Your tools</h2>
      <ul>${cfg.homeTools.map(([r, d]) => `<li>${link("#/" + r, ROUTE_LABELS[r])} — ${esc(d)}</li>`).join("")}</ul>
      <h2>At a glance</h2>
      <p>${DATA.investigations.length} PSI combustion investigations · ${DATA.hardware.length} hardware facilities · ${DATA.models.length} thermo models tracked (0 with outputs) · 0 partial-gravity datasets in PSI</p>
      <h2>The challenge</h2>
      <p><b>${esc(PROJECT.challenge.name)}</b> — ${esc(PROJECT.challenge.event)}, theme "${esc(PROJECT.challenge.theme)}".</p>
      <p>${esc(PROJECT.challenge.objective)}</p>
      <ul>${PROJECT.challenge.userGoals.map(g => `<li>${esc(g)}</li>`).join("")}</ul>` };
  }

  // ---------- ASK ----------
  function ask(params, query) {
    const q = query.get("q");
    const st = S.get();
    const turns = st.conversation.map(t => `<div class="turn"><p class="q">Q: ${esc(t.question)}</p>${t.answer ? renderAnswer(t.answer) : "<p>Loading…</p>"}</div>`).join("");
    return {
      html: `<h1>Ask</h1>${scenarioLine()}
        <p class="muted">AI: <b id="ai-status">${esc(API.describe())}</b> · persona sent: ${esc(st.persona || "student")}</p>
        <div id="conversation">${turns || "<p>No questions yet.</p>"}</div>
        ${askForm()}
        ${st.conversation.length ? `<button data-action="clear-conversation">Clear conversation</button>` : ""}`,
      mount() {
        // Ask once per new ?q= (re-renders after the answer arrives keep the same q, so they don't re-ask)
        const last = st.conversation[st.conversation.length - 1];
        if (q && (!last || last.question !== q)) runAsk(q);
      }
    };
  }
  async function runAsk(question) {
    const st = S.get();
    const turn = { question, answer: null };
    S.set({ conversation: [...st.conversation, turn] });
    try {
      turn.answer = await API.ask({ question, persona: st.persona || "student", scenario: st.scenario,
        history: st.conversation.filter(t => t.answer).map(t => ({ q: t.question, a: t.answer.answer })) });
    } catch (e) {
      turn.answer = { answer: "Error: " + e.message + ". (Fallback to cached answers goes here.)", evidence: [], widgets: [], follow_ups: [], meta: { source: "error" } };
    }
    S.set({});  // re-render
  }
  function renderAnswer(a) {
    const src = a.meta && a.meta.source;
    return `<div class="answer">
      ${src !== "live"
        ? `<p class="warn">[${esc((src || "unknown").toUpperCase())} ANSWER — SI-generated placeholder]${a.meta && a.meta.error ? " Live AI failed: " + esc(a.meta.error) : ""}</p>`
        : `<p class="muted">SI-generated answer · ${esc(a.meta.provider || "")} / ${esc(a.meta.model || "")}${a.meta.stand_in ? " (stand-in model)" : ""} · ${esc(a.meta.seconds ?? "")} s${(a.dropped || []).length ? ` · ${a.dropped.length} unverifiable item(s) removed` : ""}</p>`}
      <div class="answer-text">${md(a.answer)}</div>
      <div class="answer-widgets">${(a.widgets || []).map(W.render).join("")}</div>
      <aside class="evidence"><h3>Evidence</h3><ul>${(a.evidence || []).map(e => {
        const i = inv(e.psi_id);
        return `<li>${badge(e.tag)} ${link("#/investigation/" + e.psi_id, invLabel(i) + " (" + e.psi_id + ")")} — ${esc(e.note || "")} <span class="muted">${esc(e.graph_node || "")}</span></li>`;
      }).join("") || "<li>None</li>"}</ul></aside>
      ${a.limitations ? `<p><b>Limitations:</b> ${esc(a.limitations)}</p>` : ""}
      ${(a.follow_ups || []).length ? `<p><b>Follow-ups:</b> ${a.follow_ups.map(f => link("#/ask?q=" + encodeURIComponent(f), f)).join(" · ")}</p>` : ""}
    </div>`;
  }

  // ---------- EXPLORE ----------
  function explore() {
    const all = DATA.investigations;
    const opt = (name, vals) => `<label>${esc(name)} <select name="${esc(name)}"><option value="">All</option>${vals.map(v => `<option>${esc(v)}</option>`).join("")}</select></label>`;
    return {
      html: `<h1>Explore investigations</h1>
        <p class="muted">Real PSI data. Filter tags marked "draft" are frontend heuristics until the knowledge graph replaces them.</p>
        <form data-form="filters">
          <label>Search <input name="text" placeholder="keyword, acronym, ID"></label>
          ${opt("role", ROLES)} ${opt("phase", unique(all.map(i => i.draft.fuelPhase)))}
          ${opt("hardware", unique(all.map(i => i.draft.hardwareGroup)))} ${opt("type", unique(all.map(i => i.projectType)))}
          <label><input type="checkbox" name="hideLow" checked> Hide low-relevance</label>
        </form>
        <p>${link("#/compare", "Compare selected")} (<span id="compare-count">${S.get().compare.length}</span>) · ${link("#/hardware", "Browse by hardware")}</p>
        <div id="results"></div>`,
      mount(root) {
        const form = root.querySelector('[data-form="filters"]');
        const draw = () => {
          const f = Object.fromEntries(new FormData(form));
          const t = (f.text || "").toLowerCase();
          const res = all.filter(i =>
            (!t || [i.id, i.acronym, i.title, i.keywords, i.objectives].join(" ").toLowerCase().includes(t)) &&
            (!f.role || i.draft.roles.includes(f.role)) && (!f.phase || i.draft.fuelPhase === f.phase) &&
            (!f.hardware || i.draft.hardwareGroup === f.hardware) && (!f.type || i.projectType === f.type) &&
            (!f.hideLow || i.draft.relevance !== "low"));
          root.querySelector("#results").innerHTML = `<p>${res.length} of ${all.length}</p>` + res.map(invCard).join("");
        };
        form.addEventListener("input", draw); form.addEventListener("change", draw); draw();
      }
    };
  }

  // ---------- INVESTIGATION ----------
  function investigation(params) {
    const i = inv(params[0]);
    if (!i) return notFound();
    const field = (k, v) => v ? `<h2>${esc(k)}</h2><p>${esc(v)}</p>` : "";
    return { html: `
      <p>${link("#/explore", "← Explore")}</p>
      <h1>${esc(U.invTitle(i))}</h1> ${badge("direct_psi")}
      <p>${esc(i.title)}</p>
      <table>
        <tr><th>Type</th><td>${esc(i.projectType)}</td></tr><tr><th>Platform</th><td>${esc(i.platform || "—")}</td></tr>
        <tr><th>Hardware</th><td>${esc(i.hardware || "—")}</td></tr><tr><th>Sub-area</th><td>${esc(i.subArea || "—")}</td></tr>
        <tr><th>Dates</th><td>${esc(i.start)} → ${esc(i.end)}</td></tr><tr><th>PI</th><td>${esc(i.pi || "—")}</td></tr>
        <tr><th>Keywords</th><td>${esc(i.keywords || "—")}</td></tr>
        <tr><th>Draft tags</th><td>${esc(i.draft.fuelPhase)} · ${esc(i.draft.hardwareGroup)} · ${esc(i.draft.roles.join(", ") || "none")} · relevance ${esc(i.draft.relevance)}</td></tr>
        <tr><th>Related</th><td>${i.related.map(r => link("#/investigation/" + r, invLabel(inv(r)) + " (" + r + ")")).join(", ") || "—"}</td></tr>
        <tr><th>Hardware facility</th><td>${U.hardwareFor(i.id).map(h => link("#/hardware/" + h.id, h.name)).join(", ") || "—"}</td></tr>
        <tr><th>Thermo models using it</th><td>${U.modelsFor(i.id).map(m => link("#/model/" + m, m)).join(", ") || "—"}</td></tr>
        <tr><th>Source</th><td><a href="${esc(i.url)}" target="_blank" rel="noopener">PSI landing page</a> · DOI ${(i.doi || DATA.dois[i.id]) ? esc(i.doi || DATA.dois[i.id]) : U.unknown("DOI — read from PSI landing page")}</td></tr>
      </table>
      ${DATA.briefNotes[i.id] ? `<h2>What the challenge brief says</h2><ul>${DATA.briefNotes[i.id].map(n => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}
      <p><button data-action="toggle-compare" data-id="${esc(i.id)}">${S.get().compare.includes(i.id) ? "Remove from" : "Add to"} compare</button>
         ${link("#/ask?q=" + encodeURIComponent("Summarise " + invLabel(i) + " for fire safety"), "Ask the AI about this")}</p>
      ${field("Objectives", i.objectives)}${field("Approach", i.approach)}${field("Hypothesis", i.hypothesis)}
      ${field("Research impacts / Earth benefits", i.impacts)}${field("Publications", i.publications)}
      <h2>Runs / experimental table</h2><div class="placeholder">TODO: per-run conditions (fuel, size, O₂, pressure, airflow, sensors) from PSI experimental tables via the knowledge graph.</div>
      ${W.render({ type: "graph_neighbourhood", params: { node: i.id } })}` };
  }

  // ---------- COMPARE ----------
  function compare(params, query) {
    const ids = query.get("ids") ? query.get("ids").split(",") : S.get().compare;
    const choices = DATA.investigations.filter(i => !ids.includes(i.id)).map(i => `<option value="${esc(i.id)}">${esc(invLabel(i))} (${esc(i.id)})</option>`).join("");
    return { html: `<h1>Compare investigations</h1>
      <p>Selected: ${ids.map(id => `${esc(invLabel(inv(id)))} <button data-action="toggle-compare" data-id="${esc(id)}">×</button>`).join(" ") || "none"} (max 4)</p>
      <p><select data-action-change="add-compare"><option value="">Add investigation…</option>${choices}</select></p>
      ${compareTable(ids)}` };
  }

  // ---------- GRAPH ----------
  function graph() {
    const edges = [];
    DATA.investigations.forEach(i => i.related.forEach(r => edges.push([i.id, "related_to", r])));
    DATA.investigations.forEach(i => edges.push([i.id, "uses_hardware", i.draft.hardwareGroup]));
    return { html: `<h1>Knowledge graph</h1>
      <div class="placeholder">GRAPH VIEW PLACEHOLDER — Cytoscape.js canvas fed by the backend's graph export (node + edge types TBC).<br>
      Planned interactions: click node → side panel; filter by node type; "ask about this node".</div>
      <h2>Edges we can already derive (${edges.length})</h2>
      <table><tr><th>From</th><th>Edge</th><th>To</th></tr>${edges.map(([a, e, b]) =>
        `<tr><td>${link("#/investigation/" + a, invLabel(inv(a)) + " " + a)}</td><td>${esc(e)}</td><td>${b.startsWith("PSI-") ? link("#/investigation/" + b, invLabel(inv(b)) + " " + b) : esc(b)}</td></tr>`).join("")}</table>` };
  }

  // ---------- GAPS ----------
  function gaps() {
    const phases = unique(DATA.investigations.map(i => i.draft.fuelPhase)).filter(p => p !== "none");
    const count = (role, ph) => DATA.investigations.filter(i => i.draft.roles.includes(role) && i.draft.fuelPhase === ph).length;
    return { html: `<h1>Research-gap finder</h1>
      <p class="muted">Professor tool. Counts use DRAFT heuristic tags — replace with graph queries.</p>
      <table><tr><th>Role \\ fuel phase</th>${phases.map(p => `<th>${esc(p)}</th>`).join("")}</tr>
      ${ROLES.map(r => `<tr><th>${esc(r)}</th>${phases.map(p => `<td>${count(r, p) || "<b>0 — gap?</b>"}</td>`).join("")}</tr>`).join("")}</table>
      <h2>Known gaps (from challenge brief)</h2>
      <ul><li>Partial gravity (Moon 0.16 g, Mars 0.38 g): <b>0 datasets in PSI</b>. Future: LUCI, FM2.</li>
      <li>Lunar habitat atmosphere (≤10.2 psi, ≥30% O₂): coverage TODO — needs per-run O₂/pressure from the graph.</li></ul>
      <h2>Data expected in future</h2><ul>${DATA.futureExperiments.map(x => `<li><b>${esc(x.name)}</b> — ${esc(x.desc)}</li>`).join("")}</ul>
      <div class="placeholder">TODO: condition-space plot (O₂ × pressure × airflow) with runs plotted and empty regions highlighted.</div>` };
  }

  // ---------- LAB ----------
  function lab() {
    const domains = unique(DATA.models.map(m => m.domain));
    return { html: `<h1>Physics lab</h1>${scenarioLine()}
      <p class="muted">Model catalogue is real (thermo tracker). No outputs exist yet — charts are placeholders.</p>
      <h2>Main visuals</h2>
      ${["flammability_map", "flame_temperature", "gravity_scaling", "cabin_fire_timeline", "droplet_burning", "suppressant_compare"]
        .map(t => W.render({ type: t, params: { scenario: S.get().scenario } })).join("")}
      <h2>Key dimensionless groups</h2>
      <table><tr><th>Group</th><th>Formula</th><th>Meaning</th><th>Regime</th><th>Models</th></tr>
      ${DATA.dimensionless.map(d => `<tr><td>${esc(d.name)}</td><td><code>${esc(d.formula)}</code></td><td>${esc(d.meaning)}</td><td>${esc(d.threshold)}</td><td>${d.models.map(x => link("#/model/" + x, x)).join(", ")}</td></tr>`).join("")}</table>
      <p class="muted">Source: thermo team reference sheet.</p>
      <h2>All models</h2>
      ${domains.map(d => `<h3>${esc(d)}</h3><ul>${DATA.models.filter(m => m.domain === d).map(m =>
        `<li>${link("#/model/" + m.id, m.id)} ${badge(DATA.evidenceFromSheet[m.evidence])} ${esc(short(m.description, 120))} <span class="muted">[${esc(m.priority)} · ${esc(m.status)} · ${esc(m.runtime)}]</span></li>`).join("")}</ul>`).join("")}` };
  }

  // ---------- MODEL ----------
  function model(params) {
    const m = U.model(params[0]);
    if (!m) return notFound();
    const row = (k, v) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`;
    return { html: `<p>${link("#/lab", "← Physics lab")}</p><h1>${esc(m.id)}</h1> ${badge(DATA.evidenceFromSheet[m.evidence])}
      <p>${esc(m.description)}</p>
      <table>${row("Domain", m.domain)}${row("Function", m.signature)}${row("File", m.file)}${row("Principle", m.principle)}
      ${row("Literature", m.literature)}${row("Evidence boundary", m.evidence)}${row("PSI investigations & hardware", m.psi)}
      ${row("Priority", m.priority)}${row("Status", m.status + " (" + Math.round((m.pct || 0) * 100) + "%)")}${row("Owner", m.owner)}${row("Runtime", m.runtime)}</table>
      <h2>Linked PSI investigations</h2><ul>${(DATA.modelInvestigations[m.id] || []).map(id => `<li>${link("#/investigation/" + id, U.invTitle(inv(id)))}</li>`).join("")}</ul>
      <h2>Interactive</h2><div class="placeholder">TODO: sliders for this model's inputs + chart, from its pre-computed output grid.</div>
      <h2>Plain-English meaning</h2><div class="placeholder">TODO: one-paragraph explanation per persona (from thermo team).</div>` };
  }

  // ---------- SCENARIO (engineer) ----------
  function scenario() {
    const st = S.get();
    const opts = (arr, cur) => arr.map(([v, l]) => `<option value="${esc(v)}" ${v === cur ? "selected" : ""}>${esc(l)}</option>`).join("");
    return {
      html: `<h1>Scenario tool</h1>
        <p class="warn">Research support only — not safety certification.</p>
        <form data-form="scenario">
          <label>Atmosphere <select name="scenario">${opts(Object.entries(DATA.scenarios).map(([k, s]) => [k, s.label]), st.scenario)}</select></label>
          <label>Material <select name="material">${opts(DATA.materials.map(m => [m.id, m.label]), "")}</select></label>
          <label>Airflow (cm/s) <input name="airflow" type="number" value="10" min="0" max="50"></label>
        </form>
        <div id="scenario-out"></div>`,
      mount(root) {
        const form = root.querySelector('[data-form="scenario"]');
        const draw = () => {
          const f = Object.fromEntries(new FormData(form));
          if (f.scenario !== S.get().scenario) { S.set({ scenario: f.scenario }); return; }
          const byRole = r => DATA.investigations.filter(i => i.draft.roles.includes(r) && i.draft.relevance === "high");
          root.querySelector("#scenario-out").innerHTML =
            `<p><b>${esc(DATA.scenarios[f.scenario].label)}:</b> ${esc(DATA.scenarioSignificance[f.scenario] || "")}</p>` +
            W.render({ type: "flammability_map", params: f }) +
            W.render({ type: "atmosphere_compare", params: { scenarios: [f.scenario, "iss"] } }) +
            `<h2>Checklist (draft)</h2>` + ROLES.map(r => `<h3>${esc(r)}</h3><ul>${byRole(r).map(i =>
              `<li>${link("#/investigation/" + i.id, invLabel(i) + " (" + i.id + ")")}</li>`).join("")}</ul>`).join("") +
            `<p><button disabled>Export report (TODO)</button></p>`;
        };
        form.addEventListener("change", draw); form.addEventListener("input", draw); draw();
      }
    };
  }

  // ---------- LEARN ----------
  function learn() {
    return { html: `<h1>Learn</h1>
      <h2>Start here</h2><ol>
        <li>${link("#/learn", "Why fire behaves differently in space")} <span class="muted">(TODO explainer + 0g vs 1g slider)</span></li>
        <li>${link("#/lab", "Oxygen, pressure and airflow")} <span class="muted">(TODO)</span></li>
        <li>${link("#/explore", "How NASA tests fire on the ISS")}</li>
        <li>${link("#/ask?q=" + encodeURIComponent("Why are flames round in space?"), "Ask your own question")}</li></ol>
      <h2>Fire incidents in spaceflight</h2><ul>${DATA.incidents.map(x => `<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a> — ${esc(x.summary)}</li>`).join("")}</ul>
      <h2>Where does the data come from?</h2>
      <ul>${DATA.hardware.map(h => `<li>${link("#/hardware/" + h.id, h.name)}</li>`).join("")}</ul>
      <h2>Fire safety on Earth</h2><ul>${DATA.earthApplications.map(x => `<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a> — ${esc(x.desc)}</li>`).join("")}</ul>
      <h2>What's next: experiments coming</h2><ul>${DATA.futureExperiments.map(x => `<li><b>${esc(x.name)}</b> — ${esc(x.desc)}</li>`).join("")}</ul>
      <h2>Glossary</h2><dl>${[...DATA.glossaryExtra, ...DATA.glossary].map(g => `<dt id="g-${esc(g.term)}"><b>${esc(g.term)}</b></dt><dd>${esc(g.def)}</dd>`).join("")}</dl>` };
  }

  // ---------- ABOUT ----------
  function about() {
    const tagDefs = {
      direct_psi: "Measured in a NASA experiment and published in PSI.",
      semi_empirical: "Calculated by our models from established correlations, checked against PSI data where possible.",
      theoretical_bound: "A theoretical estimate or bound — e.g. any lunar or Martian (partial-gravity) value, since PSI has no partial-g combustion data.",
      synthetic: "Placeholder data used while building. Never shown in the final site."
    };
    const members = PROJECT.members.length ? `<ul>${PROJECT.members.map(m => `<li>${esc(m.name)}${m.role ? " — " + esc(m.role) : ""}</li>`).join("")}</ul>` : `<p>${U.unknown("team members and roles")}</p>`;
    return { html: `<h1>About & methods</h1>
      <h2>What this is</h2>
      <p><b>${U.pv(PROJECT.name, "project name")}</b> — ${PROJECT.tagline ? esc(PROJECT.tagline) : U.unknown("tagline")}</p>
      <p>${esc(PROJECT.concept)}</p>
      <p>Built for the NASA Space Apps Challenge 2026: <a href="${esc(PROJECT.challenge.url)}" target="_blank" rel="noopener">${esc(PROJECT.challenge.name)}</a>.</p>
      <h2>Who it is for</h2>
      <ul>${Object.values(PERSONAS).map(p => `<li><b>${esc(p.label)}</b> — ${p.homeTools.map(t => esc(t[1])).join("; ")}</li>`).join("")}</ul>
      <h2>Evidence badges</h2>
      <ul>${Object.keys(DATA.evidenceTags).map(k => `<li>${badge(k)} — ${esc(tagDefs[k] || "")}</li>`).join("")}</ul>
      <h2>Data</h2>
      <ul>
        <li><b>${DATA.investigations.length} NASA PSI combustion-science investigations</b> (flight and ground) — objectives, approach, hardware, publications. ${link("#/explore", "Browse them")}.</li>
        <li><b>${DATA.hardware.length} experiment facilities</b> (CIR, MDCA, ACME, MSG flow duct, Cygnus, smoke diagnostics). ${link("#/hardware", "Browse them")}.</li>
        <li><b>${DATA.models.length} thermodynamic models</b> written by our thermo team, each linked to the PSI investigations it draws on. ${link("#/lab", "Browse them")}.</li>
        <li>PSI asks users to cite each investigation by its DOI. ${U.unknown("DOIs for 25 of 26 investigations")}</li>
      </ul>
      <h2>How the AI works</h2>
      <ol>
        <li>The backend builds a knowledge graph linking investigations, hardware, fuels, conditions, measurements and models.</li>
        <li>An AI model searches the graph for each question and writes an answer for the chosen persona.</li>
        <li>The answer names the visuals to show; the website draws them from its own tested components — the AI never draws charts.</li>
        <li>Every answer lists the investigations it relied on, with evidence badges and limitations.</li>
      </ol>
      <p>Model: ${U.pv(PROJECT.aiModel, "AI model / provider")} · Graph: ${U.pv(PROJECT.graphTech, "knowledge-graph technology")} · Hosting: ${U.pv(PROJECT.hosting, "hosting")}</p>
      <h2>Use of Super Intelligence (SI)</h2>
      <p>All AI answers on this site are SI-generated and labelled. SI tools used in building it:</p>
      <table><tr><th>What</th><th>Tool</th><th>Where</th></tr>${DATA.siUse.map(x => `<tr><td>${esc(x.what)}</td><td>${x.tool ? esc(x.tool) : U.unknown("tool")}</td><td>${esc(x.where)}</td></tr>`).join("")}</table>
      <p>${U.unknown("SI use by the backend and thermo teams")}</p>
      <h2>Limitations</h2>
      <ul>
        <li>PSI holds no partial-gravity combustion data. Lunar and Martian values are theoretical bounds between microgravity and 1 g results, never measurements.</li>
        <li>Electric-field (E-FIELD) tests mimic some partial-gravity effects; they are an analogue, not lunar gravity.</li>
        <li>CFI-G's 85% O₂ was a burner stream inside a nitrogen + fuel chamber, not a cabin atmosphere.</li>
        <li>Rocket and propellant fires are out of scope.</li>
        <li>This is research support, not certification of any spacecraft's fire safety.</li>
      </ul>
      <h2>Team</h2>
      <p>Team: ${U.pv(PROJECT.teamName, "team name")} · Event: ${U.pv(PROJECT.localEvent, "Local Event")}</p>
      ${members}
      <h2>References</h2>
      ${DATA.references.map(g => `<h3>${esc(g.group)}</h3><ul>${g.items.map(([n, u]) => `<li>${u ? `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(n)}</a>` : esc(n)}</li>`).join("")}</ul>`).join("")}
      <h3>Scientific literature (from our thermo models)</h3>
      <ul>${DATA.models.map(m => `<li>${link("#/model/" + m.id, m.id)}: ${esc(m.literature)}</li>`).join("")}</ul>` };
  }

  // ---------- HARDWARE ----------
  function hardware(params) {
    if (params[0]) {
      const h = DATA.hardware.find(x => x.id === params[0]);
      if (!h) return notFound();
      const inside = (h.hosts || []).map(id => DATA.hardware.find(x => x.id === id)).filter(Boolean);
      return { html: `<p>${link("#/hardware", "← Hardware")}</p><h1>${esc(h.name)}</h1>
        <p>${esc(h.desc)}</p><p class="muted">Source: ${esc(h.source)}</p>
        ${inside.length ? `<h2>Hosts</h2><ul>${inside.map(x => `<li>${link("#/hardware/" + x.id, x.name)}</li>`).join("")}</ul>` : ""}
        ${h.investigations.length ? `<h2>Investigations</h2><div id="results">${h.investigations.map(inv).filter(Boolean).map(invCard).join("")}</div>` : ""}` };
    }
    return { html: `<h1>Hardware</h1><p class="muted">Facilities the PSI combustion experiments ran in. Investigations in the same facility share apparatus — but not necessarily objectives or conditions.</p>
      ${DATA.hardware.map(h => `<article class="card"><h3>${link("#/hardware/" + h.id, h.name)}</h3><p>${esc(h.desc)}</p>
        <p class="muted">${h.investigations.map(id => link("#/investigation/" + id, U.invLabel(inv(id)))).join(", ") || "Hosts: " + (h.hosts || []).join(", ")}</p></article>`).join("")}` };
  }

  // ---------- DEV ----------
  function dev() {
    const routes = ["#/", "#/ask", "#/ask?q=test", "#/explore", "#/investigation/PSI-25", "#/compare?ids=PSI-26,PSI-25,PSI-98",
      "#/graph", "#/gaps", "#/lab", "#/model/THM-05", "#/scenario", "#/learn", "#/about", "#/hardware", "#/hardware/msg-duct", "#/nope"];
    return { html: `<h1>All pages (dev)</h1>
      <ul>${routes.map(r => `<li>${link(r, r)}</li>`).join("")}</ul>
      <h2>State</h2><pre>${esc(JSON.stringify({ ...S.get(), conversation: S.get().conversation.length + " turns" }, null, 1))}</pre>
      <p><button data-action="reset-state">Reset persona / compare</button></p>
      <h2>Widget gallery (${W.types().length})</h2>${W.types().map(t => W.render({ type: t, params: W.samples[t] })).join("")}
      ${W.render({ type: "not_a_widget", params: { x: 1 } })}` };
  }

  function notFound() { return { html: `<h1>Not found</h1><p>${link("#/", "Home")}</p>` }; }

  return { hardware, home, ask, explore, investigation, compare, graph, gaps, lab, model, scenario, learn, about, dev, notFound, compareTable, runAsk };
})();
