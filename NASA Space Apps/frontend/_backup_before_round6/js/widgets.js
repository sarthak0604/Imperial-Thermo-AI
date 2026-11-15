// WIDGET LIBRARY — everything a dashboard can show. The AI picks widgets by `type` + `params`.
// size: s = 1×1, w = 2×1 (wide), t = 1×2 (tall), b = 2×2 (big).
// data: "real" (PSI / challenge brief / calculation) or "synthetic" (illustrative mock until the thermo models deliver).
window.W = (() => {
  const { esc, badge, inv, invLabel, short, link } = U;
  const { xy, line, dots, bars, range, scale, r2, fmt } = CH;

  // ---------- synthetic mock physics (ILLUSTRATIVE SHAPES ONLY — replace with thermo model outputs) ----------
  const MOCK = {
    loi: (u, scen) => 15.5 + 10 * Math.exp(-u / 2) + 0.006 * u * u + (scen === "lunar_habitat" ? 1.5 : scen === "spacesuit" ? 3 : 0),
    spread: (u, o2, scen) => Math.max(0, o2 - MOCK.loi(u, scen)) * 0.12 * (1 + u / 30),
    tad: (o2, p) => 300 + 3000 * (1 - Math.exp(-o2 / 22)) - 80 * (1 - p / 14.7)
  };
  const SCEN = k => (DATA.scenarios[k] ? k : "iss");
  const SCEN_O2 = { iss: 21, lunar_habitat: 30, spacesuit: 100, earth: 21 };
  const SCEN_P = { iss: 14.7, lunar_habitat: 10.2, spacesuit: 4.3, earth: 14.7 };

  function frame(type, def, inner, opts = {}) {
    const dataLabel = def.data === "synthetic" ? `<span class="badge" data-tag="synthetic">[SYNTHETIC mock]</span>` : (def.tag ? badge(def.tag) : "");
    return `<section class="widget size-${def.size}" data-widget="${esc(type)}" data-params="${esc(JSON.stringify(opts.params || {}))}" style="--i:${opts.i || 0}">
      <header><b>${esc(opts.title || def.title)}</b><span class="kind">${esc(def.kind)}</span>${dataLabel}</header>
      ${opts.why ? `<p class="why">${esc(opts.why)}</p>` : ""}
      <div class="widget-body">${inner}</div>
      <footer>${esc(def.source)}${def.models ? " · " + def.models.map(m => link(U.modelHref(m), m)).join(", ") : ""}</footer>
    </section>`;
  }
  const slider = (name, label, min, max, step, val, unit) =>
    `<label class="slider">${esc(label)} <input type="range" name="${name}" min="${min}" max="${max}" step="${step}" value="${val}"> <output>${val}</output> ${esc(unit)}</label>`;

  // ---------- chart builders ----------
  function flammabilityMap(p) {
    const scen = SCEN(p.scenario), o2 = +(p.o2 ?? Math.min(SCEN_O2[scen], 40)), u = +(p.airflow ?? 10);
    const svg = xy({ w: 520, h: 300, x: [0, 40], y: [14, 40], xticks: [0, 10, 20, 30, 40], yticks: [15, 20, 25, 30, 35, 40],
      xlabel: "Airflow speed (cm/s)", ylabel: "Oxygen (%)", aria: "Flammability map",
      draw: ({ sx, sy }) => {
        const edge = range(0, 40, 80).map(x => [x, Math.min(40, MOCK.loi(x, scen))]);
        let s = `<path class="cell" d="${CH.path(edge, sx, sy)}L${sx(40)},${sy(40)}L${sx(0)},${sy(40)}Z"/>`;
        s += line(range(0, 40, 80).map(x => [x, Math.min(40, MOCK.loi(x, scen))]), sx, sy, 0, 'stroke-width="2"');
        s += `<text class="note" x="${sx(1)}" y="${sy(38.5)}">FLAMMABLE (shaded)</text><text class="note" x="${sx(0.6)}" y="${sy(16)}">quench</text><text class="note" x="${sx(33)}" y="${sy(16)}">blow-off</text>`;
        const inside = o2 > MOCK.loi(u, scen);
        s += `<g class="marker"><line x1="${sx(u) - 7}" x2="${sx(u) + 7}" y1="${sy(Math.min(o2, 40))}" y2="${sy(Math.min(o2, 40))}"/><line x1="${sx(u)}" x2="${sx(u)}" y1="${sy(Math.min(o2, 40)) - 7}" y2="${sy(Math.min(o2, 40)) + 7}"/>
          <text x="${sx(u) + 9}" y="${sy(Math.min(o2, 40)) - 6}">${inside ? "burns (mock)" : "does not burn (mock)"}</text></g>`;
        return s;
      } });
    return { svg, o2, u, scen };
  }
  function atmosphereChart(P, O2) {
    const pts = [[14.7, 21, "ISS / Earth"], [10.2, 30, "Lunar habitat"], [4.3, 100, "Spacesuit"]];
    return xy({ w: 520, h: 300, x: [0, 16], y: [0, 100], xticks: [0, 4, 8, 12, 16], yticks: [0, 25, 50, 75, 100],
      xlabel: "Total pressure (psi)", ylabel: "Oxygen (%)", aria: "Atmosphere explorer",
      legend: [{ label: "Earth's O₂ partial pressure", dash: "6 4" }],
      draw: ({ sx, sy }) => {
        const earthPP = 14.7 * 0.21;
        let s = line(range(3.2, 16, 60).map(p => [p, Math.min(100, earthPP / p * 100)]), sx, sy, 1);
        s += pts.map(([x, y, l]) => `<circle class="dot" cx="${sx(x)}" cy="${sy(y)}" r="4"><title>${esc(l)}</title></circle><text class="note" x="${sx(x) - 6}" y="${sy(y) + 16}" text-anchor="${x > 12 ? "end" : "middle"}">${esc(l)}</text>`).join("");
        s += `<g class="marker"><circle cx="${sx(P)}" cy="${sy(O2)}" r="7" fill="none"/><line x1="${sx(P) - 11}" x2="${sx(P) + 11}" y1="${sy(O2)}" y2="${sy(O2)}"/><line x1="${sx(P)}" x2="${sx(P)}" y1="${sy(O2) - 11}" y2="${sy(O2) + 11}"/></g>`;
        return s;
      } });
  }
  function networkSvg(id) {
    const c = inv(id); if (!c) return `<p>Unknown investigation ${esc(id)}</p>`;
    const hw = U.hardwareFor(id);
    const related = new Set([...c.related, ...DATA.investigations.filter(i => i.related.includes(id)).map(i => i.id)]);
    const siblings = new Set(hw.flatMap(h => h.investigations).filter(x => x !== id && !related.has(x)));
    const ring = [...related].map(x => [x, "related"]).concat([...siblings].map(x => [x, "same hardware"])).slice(0, 10);
    const W0 = 520, H0 = 300, cx = W0 / 2, cy = H0 / 2;
    let s = "";
    hw.forEach((h, k) => { const x = cx + (k - (hw.length - 1) / 2) * 150, y = cy + 112;
      s += `<line class="edge dashed" x1="${cx}" y1="${cy}" x2="${x}" y2="${y}"/><rect class="hw" x="${x - 70}" y="${y - 11}" width="140" height="22"/><text class="note" x="${x}" y="${y + 4}" text-anchor="middle">${esc(h.short || h.name.slice(0, 24))}</text>`; });
    ring.forEach(([x, rel], k) => { const a = -Math.PI / 2 + (k - (ring.length - 1) / 2) * (Math.PI / Math.max(ring.length, 4)) * 1.15;
      const nx = cx + 200 * Math.cos(a) * 1.05, ny = cy + 120 * Math.sin(a) + 8, i = inv(x);
      s += `<line class="edge ${rel === "related" ? "" : "dashed"}" x1="${cx}" y1="${cy}" x2="${r2(nx)}" y2="${r2(ny)}"/>
        <a href="${esc(U.invHref(x))}"><circle class="node" cx="${r2(nx)}" cy="${r2(ny)}" r="6"><title>${esc(i ? i.title : x)} — ${rel}</title></circle>
        <text class="note" x="${r2(nx)}" y="${r2(ny) - 10}" text-anchor="middle">${esc(invLabel(i))}</text></a>`; });
    s += `<circle class="node center" cx="${cx}" cy="${cy}" r="11"/><text class="lab" x="${cx}" y="${cy + 26}" text-anchor="middle">${esc(invLabel(c))}</text>`;
    return `<svg class="chart" viewBox="0 0 ${W0} ${H0}" role="img" aria-label="Investigation network">${s}
      <g class="legend"><line x1="10" x2="28" y1="14" y2="14" class="edge"/><text x="32" y="17">related (PSI)</text><line x1="10" x2="28" y1="30" y2="30" class="edge dashed"/><text x="32" y="33">shares hardware</text></g></svg>`;
  }
  const parseDate = s => { const m = /^(\d{2})-(\d{2})-(\d{4})$/.exec(s || ""); return m ? +m[3] + (+m[1] - 1) / 12 : null; };

  // ---------- the library ----------
  const R = {
    // ===== charts from the thermo models (synthetic until outputs arrive) =====
    flammability_map: { title: "Flammability map", kind: "interactive chart", size: "b", data: "synthetic", source: "Mock shape of the THM flammability models", models: ["THM-05", "THM-07", "THM-13", "THM-17"],
      sample: { scenario: "lunar_habitat", o2: 30, airflow: 8 },
      render: p => { const m = flammabilityMap(p);
        return `<div class="chart-slot">${m.svg}</div><div class="controls">${slider("o2", "O₂", 14, 40, 0.5, Math.min(m.o2, 40), "%")}${slider("airflow", "Airflow", 0, 40, 0.5, m.u, "cm/s")}</div>`; },
      mount: (el, p) => { const draw = () => { const f = Object.fromEntries([...el.querySelectorAll("input")].map(i => [i.name, +i.value]));
          el.querySelectorAll("output").forEach((o, k) => o.textContent = el.querySelectorAll("input")[k].value);
          el.querySelector(".chart-slot").innerHTML = flammabilityMap({ ...p, ...f }).svg; };
        el.querySelectorAll("input").forEach(i => i.addEventListener("input", draw)); } },

    flame_spread_curve: { title: "Flame spread vs airflow", kind: "chart", size: "w", data: "synthetic", source: "Mock shape of THM-05 / THM-06", models: ["THM-05", "THM-06"],
      sample: { scenario: "iss" },
      render: p => { const scen = SCEN(p.scenario), levels = [21, 30, 40];
        return xy({ x: [0, 40], y: [0, 4], xticks: [0, 10, 20, 30, 40], yticks: [0, 1, 2, 3, 4], xlabel: "Airflow speed (cm/s)", ylabel: "Spread rate (mm/s)",
          legend: levels.map(o => ({ label: o + "% O₂" })),
          draw: ({ sx, sy }) => levels.map((o, i) => line(range(0, 40, 80).map(u => [u, Math.min(4, MOCK.spread(u, o, scen))]), sx, sy, i)).join("") }); } },

    flame_temperature: { title: "Adiabatic flame temperature", kind: "chart", size: "w", data: "synthetic", source: "Mock shape of THM-01", models: ["THM-01"],
      sample: {},
      render: () => { const ps = [[14.7, "14.7 psi (Earth / ISS)"], [10.2, "10.2 psi (lunar)"], [4.3, "4.3 psi (suit)"]];
        return xy({ x: [15, 100], y: [1500, 3500], xticks: [21, 30, 50, 75, 100], yticks: [1500, 2000, 2500, 3000, 3500], xlabel: "Oxygen (%)", ylabel: "Temperature (K)",
          legend: ps.map(([, l]) => ({ label: l })),
          draw: ({ sx, sy }) => ps.map(([P], i) => line(range(15, 100, 85).map(o => [o, MOCK.tad(o, P)]), sx, sy, i)).join("") }); } },

    cabin_fire_timeline: { title: "Closed-cabin fire over time", kind: "chart (small multiples)", size: "w", data: "synthetic", source: "Mock shape of THM-19", models: ["THM-19"],
      sample: { scenario: "lunar_habitat" },
      render: p => { const scen = SCEN(p.scenario), P0 = SCEN_P[scen] * 6.895, O0 = SCEN_O2[scen], t = range(0, 600, 60);
        const T = t.map(x => [x, 295 + 30 * (1 - Math.exp(-x / 180))]);
        const panels = [["Gas temperature (K)", T, [290, 330]], ["Pressure (kPa)", T.map(([x, k]) => [x, P0 * k / 295]), [P0 * 0.98, P0 * 1.12]],
          ["O₂ (%)", t.map(x => [x, O0 - 2.5 * (1 - Math.exp(-x / 250))]), [O0 - 3, O0 + 0.5]], ["CO₂ (%)", t.map(x => [x, 0.4 + 2.2 * (1 - Math.exp(-x / 250))]), [0, 3]]];
        return `<div class="multiples">${panels.map(([lab, pts, yr]) => xy({ w: 260, h: 150, m: { l: 40, b: 30, t: 18 }, x: [0, 600], y: yr, xticks: [0, 300, 600], yticks: [yr[0], yr[1]].map(v => r2(v)),
          xlabel: "time (s)", ylabel: "", draw: ({ sx, sy, m }) => `<text class="lab" x="${m.l + 4}" y="12">${esc(lab)}</text>` + line(pts, sx, sy) })).join("")}</div>`; } },

    droplet_burning: { title: "Droplet burning (d² law)", kind: "chart", size: "w", data: "synthetic", source: "Mock shape of THM-10 / THM-11; FLEX-type behaviour", models: ["THM-10", "THM-11"],
      sample: { fuel: "n-heptane" },
      render: () => { const hot = range(0, 12, 24).map(t => [t, 9 - 0.55 * t]), cool = range(12, 25, 26).map(t => [t, 2.4 - 0.08 * (t - 12)]), meth = range(0, 16, 32).map(t => [t, 9 - 0.5 * t]);
        return xy({ x: [0, 26], y: [0, 10], xticks: [0, 5, 10, 15, 20, 25], yticks: [0, 2.5, 5, 7.5, 10], xlabel: "Time (s)", ylabel: "d² (mm²)",
          legend: [{ label: "alkane: hot → cool flame" }, { label: "no cool flame" }],
          draw: ({ sx, sy }) => line(hot.concat(cool), sx, sy, 0) + line(meth, sx, sy, 1) +
            `<text class="note" x="${sx(12.4)}" y="${sy(3.4)}">hot flame out → cool flame</text>` }); } },

    suppressant_compare: { title: "Suppressant effectiveness", kind: "chart", size: "t", data: "synthetic", source: "Mock shape of THM-18 (FLEX dilution)", models: ["THM-18"],
      sample: {},
      render: () => bars([{ label: "N₂", value: 1.0 }, { label: "He", value: 1.25 }, { label: "CO₂", value: 1.5 }], { w: 280, h: 200, ylabel: "relative (N₂ = 1)", max: 2, yticks: [0, 1, 2] }) },

    gravity_scaling: { title: "Buoyancy vs ventilation across gravity", kind: "chart", size: "w", data: "synthetic", source: "Illustrative Richardson-number calculation (assumed ΔT = 1000 K, L = 1 cm); THM-08", models: ["THM-08"],
      sample: {},
      render: () => { const ri = (g, U) => g * 9.81 * (1 / 300) * 1000 * 0.01 / (U * U), gs = [1e-6, 1e-4, 1e-2, 0.16, 0.38, 1];
        const lv = [[1e-6, "ISS ~1e-6 g"], [0.16, "Moon"], [0.38, "Mars"], [1, "Earth"]];
        return xy({ x: [1e-6, 1], y: [1e-6, 1e3], xlog: true, ylog: true, xticks: [1e-6, 1e-4, 1e-2, 1], yticks: [1e-6, 1e-3, 1, 1e3],
          xlabel: "Gravity (g, log)", ylabel: "Richardson number (log)", legendAt: "left", legend: [{ label: "airflow 5 cm/s" }, { label: "airflow 20 cm/s" }],
          draw: ({ sx, sy }) => `<rect class="band" x="${sx(0.16)}" y="${sy(1e3)}" width="${sx(0.38) - sx(0.16)}" height="${sy(1e-6) - sy(1e3)}"><title>Partial gravity: no PSI data — theoretical only</title></rect>
            <text class="note" x="${sx(0.16) - 4}" y="${sy(3e-6)}" text-anchor="end">no PSI data →</text>
            <line class="ref" x1="${sx(1e-6)}" x2="${sx(1)}" y1="${sy(1)}" y2="${sy(1)}"/><text class="note" x="${sx(2e-6)}" y="${sy(1) - 4}">Ri = 1: buoyancy ≈ ventilation</text>` +
            [0.05, 0.2].map((U, i) => line(gs.map(g => [g, ri(g, U)]), sx, sy, i)).join("") + lv.map(([g, l]) => `<text class="note" x="${sx(g)}" y="${sy(1e-6) - 4}" text-anchor="middle">${l}</text>`).join("") }); } },

    smoke_particle_sizes: { title: "Smoke particle sizes, 0 g vs 1 g", kind: "chart", size: "t", data: "synthetic", source: "Mock shape of THM-20; SAME / SAME-R topic", models: ["THM-20"],
      sample: {},
      render: () => { const ln = (d, med) => Math.exp(-Math.pow(Math.log(d / med), 2) / (2 * 0.35)), ds = range(-1, 0.5, 30).map(e => 10 ** e);
        return xy({ w: 300, h: 200, m: { l: 36, b: 34 }, x: [0.1, 3], y: [0, 1.1], xlog: true, xticks: [0.1, 0.3, 1, 3], yticks: [0, 0.5, 1], xlabel: "Particle diameter (µm)", ylabel: "rel. count",
          legend: [{ label: "1 g" }, { label: "0 g" }], draw: ({ sx, sy }) => line(ds.map(d => [d, ln(d, 0.4)]), sx, sy, 0) + line(ds.map(d => [d, ln(d, 0.8)]), sx, sy, 1) }); } },

    // ===== visuals on real data =====
    atmosphere_explorer: { title: "Atmosphere explorer", kind: "interactive", size: "b", data: "real", tag: null, source: "Presets: challenge brief. O₂ partial pressure = pressure × O₂ fraction (calculation).",
      sample: { pressure: 10.2, o2: 30 },
      render: p => { const P = +(p.pressure ?? 10.2), O = +(p.o2 ?? 30);
        return `<div class="chart-slot">${atmosphereChart(P, O)}</div><div class="controls">${slider("pressure", "Pressure", 2, 16, 0.1, P, "psi")}${slider("o2", "O₂", 15, 100, 1, O, "%")}</div><p class="readout"></p>`; },
      mount: (el) => { const ins = el.querySelectorAll("input"), outs = el.querySelectorAll("output");
        const draw = () => { const P = +ins[0].value, O = +ins[1].value; outs[0].textContent = P; outs[1].textContent = O;
          el.querySelector(".chart-slot").innerHTML = atmosphereChart(P, O);
          const pp = P * O / 100; el.querySelector(".readout").textContent = `O₂ partial pressure ${pp.toFixed(2)} psi (${(pp / 3.087 * 100).toFixed(0)}% of Earth's) · O₂ fraction ${(O / 21).toFixed(2)}× Earth's`; };
        ins.forEach(i => i.addEventListener("input", draw)); draw(); } },

    investigation_timeline: { title: "When the experiments ran", kind: "visual", size: "w", data: "real", tag: "direct_psi", source: "PSI investigation start/end dates",
      sample: {},
      render: p => { let items = (p.ids && p.ids.length ? p.ids.map(inv) : DATA.investigations.filter(i => i.projectType === "Microgravity Investigation" && i.draft.relevance !== "low")).filter(Boolean)
          .map(i => [i, parseDate(i.start), parseDate(i.end)]).filter(([, a, b]) => a && b).sort((x, y) => x[1] - y[1]).slice(0, 14);
        const h = 26 + items.length * 17, w = 520, sx = scale(2000, 2026, 110, w - 14);
        let s = [2000, 2005, 2010, 2015, 2020, 2025].map(y => `<line class="gridv" x1="${sx(y)}" x2="${sx(y)}" y1="6" y2="${h - 18}"/><text class="note" x="${sx(y)}" y="${h - 4}" text-anchor="middle">${y}</text>`).join("");
        s += items.map(([i, a, b], k) => `<a href="${esc(U.invHref(i.id))}"><text class="note" x="104" y="${18 + k * 17}" text-anchor="end">${esc(invLabel(i).slice(0, 18))}</text>
          <rect class="bar" x="${r2(sx(a))}" y="${8 + k * 17}" width="${r2(Math.max(3, sx(b) - sx(a)))}" height="11"><title>${esc(i.title)}: ${esc(i.start)} → ${esc(i.end)}</title></rect></a>`).join("");
        return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Investigation timeline">${s}</svg>`; } },

    investigation_network: { title: "Connections", kind: "visual", size: "b", data: "real", tag: "direct_psi", source: "PSI related investigations + shared hardware (challenge brief)",
      sample: { node: "PSI-69" }, render: p => networkSvg(p.node || p.id || "PSI-69") },

    coverage_matrix: { title: "What the data covers", kind: "visual", size: "s", data: "real", tag: null, source: "Counts of PSI investigations by DRAFT tags (frontend heuristic)",
      sample: {},
      render: () => { const roles = ["prevention", "detection", "suppression"], ph = ["solid", "liquid", "gas", "aerosol"];
        const n = (r, f) => DATA.investigations.filter(i => i.draft.roles.includes(r) && i.draft.fuelPhase === f).length, max = 8;
        return `<table class="matrix"><tr><th></th>${ph.map(f => `<th>${f}</th>`).join("")}</tr>${roles.map(r => `<tr><th>${r}</th>${ph.map(f => { const v = n(r, f);
          return `<td style="--a:${(v / max).toFixed(2)}" title="${v} investigations">${v || "0"}</td>`; }).join("")}</tr>`).join("")}</table>
          <p class="muted small">0 = possible gap. Partial gravity: 0 datasets.</p>`; } },

    investigation_card: { title: "Investigation", kind: "card", size: "t", data: "real", tag: "direct_psi", source: "PSI",
      sample: { id: "PSI-25" },
      render: p => { const i = inv(p.id); if (!i) return `<p>Unknown id ${esc(p.id)}</p>`;
        return `<h3 class="card-title">${esc(U.invTitle(i))}</h3><p>${esc(i.title)}</p><p class="muted small">${esc(i.projectType)} · ${esc(i.platform || "—")}<br>${esc(i.start)} → ${esc(i.end)}</p>
          <p class="small">${esc(short(i.objectives, 260))}</p><p class="small">${link(U.invHref(i.id), "Dashboard")} · <a href="${esc(i.url)}" target="_blank" rel="noopener">PSI page ↗</a></p>`; } },

    investigation_compare: { title: "Compare investigations", kind: "table", size: "w", data: "real", tag: "direct_psi", source: "PSI",
      sample: { ids: ["PSI-26", "PSI-25", "PSI-98"] },
      render: p => { const items = (p.ids || []).map(inv).filter(Boolean);
        const rows = [["Type", i => i.projectType], ["Platform", i => i.platform], ["Facility", i => U.hardwareFor(i.id).map(h => h.name.split(" (")[0]).join(", ")],
          ["Fuel (draft)", i => i.draft.fuelPhase], ["Role (draft)", i => i.draft.roles.join(", ")], ["Dates", i => `${i.start} → ${i.end}`]];
        return `<table class="compare"><tr><th></th>${items.map(i => `<th>${link(U.invHref(i.id), invLabel(i))}</th>`).join("")}</tr>${rows.map(([k, f]) =>
          `<tr><th>${esc(k)}</th>${items.map(i => `<td>${esc(f(i) || "—")}</td>`).join("")}</tr>`).join("")}</table>`; } },

    ranked_list: { title: "Most relevant investigations", kind: "list", size: "t", data: "real", tag: "direct_psi", source: "AI ranking over PSI",
      sample: { items: [{ id: "PSI-25", reason: "sample reason" }, { id: "PSI-26", reason: "sample reason" }, { id: "PSI-98", reason: "sample reason" }] },
      render: p => `<ol class="ranked">${(p.items || []).map(it => { const i = inv(it.id);
          return `<li>${link(U.invHref(it.id), invLabel(i) + " · " + it.id)}<br><span class="small muted">${esc(it.reason || "")}</span></li>`; }).join("")}</ol>` },

    atmosphere_compare: { title: "Atmospheres compared", kind: "table", size: "w", data: "real", tag: null, source: "Challenge brief",
      sample: { scenarios: ["iss", "lunar_habitat", "spacesuit"] },
      render: p => `<table><tr><th>Environment</th><th>Pressure</th><th>O₂</th><th>Gravity</th></tr>${(p.scenarios || Object.keys(DATA.scenarios)).map(k => { const s = DATA.scenarios[k];
          return s ? `<tr><td>${esc(s.label)}</td><td>${esc(s.pressure)}</td><td>${esc(s.o2)}</td><td>${esc(s.gravity)}</td></tr>` : ""; }).join("")}</table>` }
  };
  // ===== text, link and image widgets =====
  const txt = t => `<p>${esc(t || "")}</p>`;
  Object.assign(R, {
    explanation: { title: "Explanation", kind: "text", size: "w", data: "real", source: "AI summary of the data", sample: { text: "" }, render: p => txt(p.text) },
    key_fact: { title: "Key fact", kind: "stat", size: "s", data: "real", source: "PSI / challenge brief", sample: { label: "", value: "" },
      render: p => `<div class="tile-label">${esc(p.label || "")}</div><div class="tile-value">${esc(p.value || "")}</div>` },
    glossary: { title: "Glossary", kind: "text", size: "s", data: "real", source: "Team glossary", sample: { terms: [] },
      render: p => `<dl>${(p.terms || []).map(t => { const g = [...DATA.glossaryExtra, ...DATA.glossary].find(x => x.term.toLowerCase() === String(t).toLowerCase()); return g ? `<dt>${esc(g.term)}</dt><dd>${esc(g.def)}</dd>` : ""; }).join("")}</dl>` },
    limitations: { title: "Limitations", kind: "text", size: "s", data: "real", source: "AI + challenge brief", sample: { text: "" }, render: p => txt(p.text) },
    links: { title: "Sources & links", kind: "links", size: "t", data: "real", source: "NASA PSI", sample: { psi_ids: [] },
      render: p => `<ul>${(p.psi_ids || []).map(inv).filter(Boolean).map(i => `<li><a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(U.invTitle(i))} ↗</a></li>`).join("")}</ul>` },
    evidence: { title: "Evidence", kind: "links", size: "w", data: "real", source: "PSI", sample: { items: [] },
      render: p => `<ul>${(p.items || []).map(e => `<li>${badge(e.tag)} ${link(U.invHref(e.psi_id), e.psi_id)} — ${esc(e.note || "")}</li>`).join("")}</ul>` },
    follow_ups: { title: "Ask next", kind: "links", size: "s", data: "real", source: "AI", sample: { items: [] },
      render: p => `<ul>${(p.items || []).map(f => `<li><a href="#q=${encodeURIComponent(f)}">${esc(f)}</a></li>`).join("")}</ul>` },
    experiment_image: { title: "Experiment photo", kind: "image", size: "s", data: "real", source: "PSI representative images", sample: { id: "PSI-25" }, render: () => `<p>Image from the PSI archive.</p>` }
  });

  // category + one-line explanation for every widget (shown in the focus window)
  const META = {
    flammability_map: ["interactive", "Where a material can keep burning, plotted against airflow speed and oxygen level. Slide the controls to place a scenario inside or outside the flammable zone. Will come from the thermo team's flammability models (THM-05, 07, 13, 17)."],
    flame_spread_curve: ["graph", "How fast a flame creeps across a solid material as cabin airflow changes, at three oxygen levels. From model THM-05/06, checked against the BASS and Saffire burns."],
    flame_temperature: ["graph", "How hot a flame can get as oxygen rises, at Earth/ISS, lunar-habitat and spacesuit pressures. From the equilibrium model THM-01."],
    cabin_fire_timeline: ["graph", "What a fire does to a sealed module over time: temperature, pressure, oxygen and CO₂. From the closed-cabin model THM-19, informed by Saffire."],
    droplet_burning: ["graph", "How a burning fuel droplet shrinks over time, including the switch to an almost invisible 'cool flame'. From THM-10/11 and the FLEX experiments."],
    suppressant_compare: ["graph", "How well helium, CO₂ and nitrogen put fires out when added to the air. From THM-18 and the FLEX suppression tests."],
    gravity_scaling: ["graph", "How the balance between buoyancy and ventilation changes from the ISS to the Moon, Mars and Earth. The shaded partial-gravity band has no measured data yet."],
    smoke_particle_sizes: ["graph", "How big smoke particles get in microgravity compared with Earth, which matters for smoke detectors. From THM-20 and the SAME experiments."],
    atmosphere_explorer: ["interactive", "Compare the air in the ISS, a lunar habitat and a spacesuit. Move pressure and oxygen to see how a new atmosphere compares with Earth's."],
    investigation_timeline: ["visual", "When each relevant NASA experiment ran, from PSI records."],
    investigation_network: ["visual", "How investigations connect: related studies, and experiments that shared the same hardware."],
    coverage_matrix: ["visual", "Which kinds of fire-safety research have data and where the gaps are, split by prevention, detection and suppression."],
    experiment_image: ["visual", "A photo of the experiment hardware from the PSI archive."],
    investigation_card: ["data", "A summary of one NASA investigation: what it set out to do, where it flew and when."],
    investigation_compare: ["data", "Several investigations side by side: platform, hardware, fuel and dates."],
    ranked_list: ["data", "The investigations most relevant to the question, ranked, with the reason for each."],
    atmosphere_compare: ["data", "The pressure, oxygen and gravity of each crewed environment in one table."],
    key_fact: ["data", "One headline number or condition, with its source."],
    explanation: ["explanation", "A short plain-language answer to the question, written from the data."],
    glossary: ["explanation", "Definitions of the technical terms used on this page."],
    limitations: ["explanation", "What the data can't tell you, for example that there's no partial-gravity fire data yet."],
    links: ["link", "Direct links to the NASA PSI pages and sources behind this dashboard."],
    evidence: ["link", "Every investigation this dashboard relies on, and how strong the evidence is."],
    follow_ups: ["link", "Good next questions. Each one opens a new dashboard."]
  };
  for (const [k, [cat, desc]] of Object.entries(META)) if (R[k]) Object.assign(R[k], { cat, desc });
  R.graph_neighbourhood = R.investigation_network;   // old name

  // ---------- SKETCHES: pure visual placeholders (no data, no text) — what the site shows for now ----------
  // Each sketch has its own natural shape [w, h]; the tiler uses w/h to choose a box that fits it.
  // Drawn in unit coordinates (0–1) and mapped into the sketch's own viewBox.
  function canvas(w, h, m = 0.08) {
    const X = x => (m * w + x * w * (1 - 2 * m)).toFixed(1), Y = y => (m * h + y * h * (1 - 2 * m)).toFixed(1);
    const P = (x, y) => `${X(x)} ${Y(y)}`;
    return { w, h, X, Y, P, ax: `<path class="sk-ax" d="M${P(0, 0)}V${Y(1)}H${X(1)}"/>` };
  }
  const SK = {
    line3:     { vb: [200, 118], draw: c => c.ax + [[.05, .25], [.4, .5], [.75, .8]].map(([e, f], i) =>
                   `<path class="sk${i ? " d" + i : ""}" d="M${c.P(0, .95 - i * .03)}C${c.P(.25, e)} ${c.P(.5, e)} ${c.P(1, f - .05)}"/>`).join("") },
    umap:      { vb: [180, 130], draw: c => c.ax + `<path class="sk-fill" d="M${c.P(0, .25)}C${c.P(.15, .95)} ${c.P(.35, .95)} ${c.P(1, .4)}L${c.P(1, 0)}L${c.P(0, 0)}Z"/>
                   <path class="sk" d="M${c.P(0, .25)}C${c.P(.15, .95)} ${c.P(.35, .95)} ${c.P(1, .4)}"/><path class="sk-x" d="M${(+c.X(.25) - 6).toFixed(1)} ${c.Y(.45)}h12M${c.X(.25)} ${(+c.Y(.45) - 6).toFixed(1)}v12"/>` },
    multiples: { vb: [200, 130], draw: () => [[8, 8], [106, 8], [8, 70], [106, 70]].map(([x, y], k) =>
                   `<path class="sk-ax" d="M${x + 6} ${y + 4}V${y + 50}H${x + 90}"/><path class="sk" d="M${x + 6} ${y + (k % 2 ? 14 : 46)}C${x + 30} ${y + 30} ${x + 50} ${y + (k % 2 ? 38 : 18)} ${x + 90} ${y + (k % 2 ? 42 : 14)}"/>`).join("") },
    droplet:   { vb: [200, 118], draw: c => c.ax + `<path class="sk" d="M${c.P(0, .05)}L${c.P(.55, .7)}L${c.P(1, .85)}"/><path class="sk d1" d="M${c.P(0, .05)}L${c.P(.75, 1)}"/>` },
    bars:      { vb: [130, 130], draw: c => c.ax + [[.15, .55], [.45, .38], [.75, .15]].map(([x, y]) => `<rect class="sk-bar" x="${c.X(x)}" y="${c.Y(y)}" width="${(c.w * .17).toFixed(1)}" height="${(+c.Y(1) - +c.Y(y)).toFixed(1)}"/>`).join("") },
    loglines:  { vb: [190, 120], draw: c => c.ax + `<rect class="sk-band" x="${c.X(.72)}" y="${c.Y(0)}" width="${(c.w * .11).toFixed(1)}" height="${(+c.Y(1) - +c.Y(0)).toFixed(1)}"/><path class="sk" d="M${c.P(0, .92)}L${c.P(1, .1)}"/><path class="sk d1" d="M${c.P(0, 1)}L${c.P(1, .35)}"/>` },
    bells:     { vb: [170, 120], draw: c => c.ax + `<path class="sk" d="M${c.P(0, 1)}C${c.P(.2, 1)} ${c.P(.25, .05)} ${c.P(.35, .05)}S${c.P(.55, 1)} ${c.P(.75, 1)}"/><path class="sk d1" d="M${c.P(.2, 1)}C${c.P(.42, 1)} ${c.P(.48, .2)} ${c.P(.58, .2)}S${c.P(.78, 1)} ${c.P(1, 1)}"/>` },
    hyper:     { vb: [150, 130], draw: c => c.ax + `<path class="sk d1" d="M${c.P(.12, .02)}C${c.P(.3, .65)} ${c.P(.55, .85)} ${c.P(1, .9)}"/><circle class="sk-dot" cx="${c.X(.2)}" cy="${c.Y(.03)}" r="4"/><circle class="sk-dot" cx="${c.X(.6)}" cy="${c.Y(.78)}" r="4"/><circle class="sk-dot" cx="${c.X(.9)}" cy="${c.Y(.88)}" r="4"/><circle class="sk-ring" cx="${c.X(.6)}" cy="${c.Y(.78)}" r="9"/>` },
    gantt:     { vb: [240, 110], draw: () => [[30, 70], [50, 60], [20, 40], [80, 100], [100, 50], [130, 70], [70, 30]].map(([x, w], k) => `<rect class="sk-bar" x="${x}" y="${8 + k * 14}" width="${w}" height="8"/>`).join("") },
    network:   { vb: [150, 140], draw: () => { const n = [[30, 30], [75, 14], [120, 30], [22, 104], [128, 104], [75, 126]];
                   return n.map(([x, y], k) => `<path class="sk${k % 2 ? " d1" : ""}" d="M75 70L${x} ${y}"/>`).join("") + n.map(([x, y]) => `<circle class="sk-node" cx="${x}" cy="${y}" r="6"/>`).join("") + `<circle class="sk-dot" cx="75" cy="70" r="10"/>`; } },
    matrix:    { vb: [170, 120], draw: () => { let t = ""; [[.6, .3, .7, .1], [.2, 0, .4, .8], [.3, .9, 0, 0]].forEach((r, i) => r.forEach((a, j) =>
                   t += `<rect class="sk-cell" x="${8 + j * 40}" y="${8 + i * 36}" width="36" height="32" style="fill-opacity:${(a * 0.6 + 0.04).toFixed(2)}"/>`)); return t; } },
    card:      { vb: [120, 160], draw: () => `<rect class="sk-bar" x="12" y="14" width="70" height="12"/>` + [40, 54, 68, 82, 96, 110, 124].map((y, k) => `<rect class="sk-txt${k > 3 ? " light" : ""}" x="12" y="${y}" width="${[96, 86, 92, 60, 96, 80, 70][k]}" height="6"/>`).join("") },
    table:     { vb: [210, 120], draw: () => { let t = `<rect class="sk-fill" x="8" y="8" width="194" height="20"/><rect class="sk-frame" x="8" y="8" width="194" height="104"/>`;
                   [28, 49, 70, 91].forEach(y => t += `<path class="sk-ax" d="M8 ${y}H202"/>`); [58, 106, 154].forEach(x => t += `<path class="sk-ax" d="M${x} 8V112"/>`); return t; } },
    para:      { vb: [220, 120], draw: () => [14, 30, 46, 62, 78, 94].map((y, k) => `<rect class="sk-txt${k > 3 ? " light" : ""}" x="10" y="${y}" width="${[200, 186, 196, 150, 190, 120][k]}" height="7"/>`).join("") },
    stat:      { vb: [140, 110], draw: () => `<rect class="sk-txt light" x="14" y="16" width="70" height="7"/><rect class="sk-bar" x="14" y="36" width="88" height="34"/><rect class="sk-txt light" x="14" y="84" width="54" height="6"/>` },
    terms:     { vb: [170, 120], draw: () => [12, 64].map(y => `<rect class="sk-bar" x="10" y="${y}" width="64" height="9"/><rect class="sk-txt" x="10" y="${y + 18}" width="150" height="6"/><rect class="sk-txt light" x="10" y="${y + 30}" width="120" height="6"/>`).join("") },
    warn:      { vb: [170, 110], draw: () => `<path class="sk" d="M30 18L52 58H8Z"/><path class="sk" d="M30 32V44"/><circle class="sk-dot" cx="30" cy="51" r="2"/>` + [22, 38, 54, 70].map((y, k) => `<rect class="sk-txt${k > 1 ? " light" : ""}" x="66" y="${y}" width="${[94, 80, 90, 60][k]}" height="6"/>`).join("") },
    linkrows:  { vb: [150, 140], draw: () => [14, 44, 74, 104].map((y, k) => `<path class="sk" d="M12 ${y + 12}L22 ${y + 2}M15 ${y + 2}H22V${y + 9}"/><rect class="sk-txt" x="34" y="${y + 3}" width="${[100, 84, 92, 70][k]}" height="7"/>`).join("") },
    evrows:    { vb: [210, 120], draw: () => [12, 42, 72].map((y, k) => `<rect class="sk-frame" x="10" y="${y}" width="44" height="16"/><rect class="sk-txt" x="64" y="${y + 5}" width="${[130, 110, 120][k]}" height="6"/>`).join("") + `<rect class="sk-frame" x="10" y="102" width="44" height="12" style="stroke-dasharray:3 3"/>` },
    chips:     { vb: [190, 110], draw: () => [[10, 14, 110], [10, 46, 150], [10, 78, 90]].map(([x, y, w]) => `<rect class="sk-chip" x="${x}" y="${y}" width="${w}" height="22" rx="11"/><rect class="sk-txt light" x="${x + 12}" y="${y + 8}" width="${w - 24}" height="6"/>`).join("") },
    photo:     { vb: [160, 120], draw: () => `<rect class="sk-frame" x="8" y="8" width="144" height="104"/><circle class="sk-node" cx="112" cy="36" r="10"/><path class="sk-fill" d="M8 112L56 52L88 86L108 68L152 112Z"/><path class="sk" d="M8 112L56 52L88 86L108 68L152 112"/>` },
    list:      { vb: [120, 150], draw: () => [14, 50, 86, 122].map((y, k) => `<circle class="sk-node" cx="18" cy="${y + 6}" r="7"/><rect class="sk-txt" x="34" y="${y}" width="${[76, 64, 70, 58][k]}" height="6"/><rect class="sk-txt light" x="34" y="${y + 12}" width="50" height="5"/>`).join("") }
  };
  const SKETCH_OF = { flammability_map: "umap", flame_spread_curve: "line3", flame_temperature: "line3", cabin_fire_timeline: "multiples", droplet_burning: "droplet",
    suppressant_compare: "bars", gravity_scaling: "loglines", smoke_particle_sizes: "bells", atmosphere_explorer: "hyper", investigation_timeline: "gantt",
    investigation_network: "network", graph_neighbourhood: "network", coverage_matrix: "matrix", investigation_card: "card", investigation_compare: "table",
    ranked_list: "list", atmosphere_compare: "table", explanation: "para", key_fact: "stat", glossary: "terms", limitations: "warn",
    links: "linkrows", evidence: "evrows", follow_ups: "chips", experiment_image: "photo" };
  const SLIDER = new Set(["flammability_map", "atmosphere_explorer"]);   // interactive → draw a slider hint
  const skOf = type => SK[SKETCH_OF[type]] || SK.card;
  // natural shape (w/h) and visual weight (how much room it deserves) for the tiler
  const WEIGHT = { b: 4, w: 2.6, t: 2.2, s: 1.4 };
  const shape = type => { const k = skOf(type), h = k.vb[1] + (SLIDER.has(type) ? 26 : 0); return { aspect: k.vb[0] / h, weight: WEIGHT[(R[type] || {}).size] || 1.5 }; };

  function sketchSvg(type) {
    const k = skOf(type), [w, h] = k.vb, sl = SLIDER.has(type), H = sl ? h + 26 : h;
    const slider = sl ? `<path class="sk-ax" d="M${w * .15} ${h + 14}H${w * .85}"/><circle class="sk-knob" cx="${w * .55}" cy="${h + 14}" r="6"/>` : "";
    return `<svg class="sk-svg" viewBox="0 0 ${w} ${H}" preserveAspectRatio="xMidYMid meet" aria-hidden="true">${k.draw(canvas(w, h))}${slider}</svg>`;
  }
  function sketch(type, opts = {}) {
    const def = R[type] || { title: type };
    return `<section class="widget sketch" data-type="${esc(type)}" data-i="${opts.i || 0}" tabindex="0" role="button" aria-label="${esc(def.title)} — open"
      style="--i:${opts.i || 0};${opts.place || ""}"><span class="w-label">${esc(opts.label || def.title)}</span>${sketchSvg(type)}</section>`;
  }

  return {
    lib: R,
    MODE: "sketch",                                   // "sketch" = visual placeholders; "full" = detailed charts below
    sketch, sketchSvg, shape, def: t => R[t],
    cats: () => [...new Set(Object.values(R).map(d => d.cat))],
    types: () => Object.keys(R).filter(k => k !== "graph_neighbourhood"),
    byCat: c => Object.keys(R).filter(k => k !== "graph_neighbourhood" && R[k].cat === c),
    samples: Object.fromEntries(Object.entries(R).map(([k, d]) => [k, d.sample || {}])),
    size: t => (R[t] ? R[t].size : "s"),
    render(w, opts = {}) {
      const def = R[w && w.type];
      if (!def) return frame("unknown", { title: "Unknown widget", kind: "?", size: "s", source: "" }, `<p>No widget called <code>${esc(w && w.type)}</code>.</p>`, opts);
      try { return frame(w.type, def, def.render(w.params || {}), { ...opts, params: w.params, why: opts.why ?? w.why }); }
      catch (e) { return frame(w.type, def, `<p>Widget error: ${esc(e.message)}</p>`, opts); }
    },
    mountAll(root) {
      root.querySelectorAll("[data-widget]").forEach(el => { const def = R[el.dataset.widget];
        if (def && def.mount && !el.dataset.mounted) { el.dataset.mounted = "1"; def.mount(el, JSON.parse(el.dataset.params || "{}")); } });
    }
  };
})();
