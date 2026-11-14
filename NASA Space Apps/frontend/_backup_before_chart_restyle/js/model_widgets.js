// MODEL WIDGETS — real charts drawn from the thermo team's model outputs (data/model_outputs.js).
// Preview first (model-widgets.html); each is added to the main library once approved.
// Monochrome: series told apart by dash pattern / fill weight, never colour.
// Written with SI assistance (Claude, Anthropic).
window.MW = (() => {
  const { esc } = U;
  const { xy, line, bars, range, scale, r2, fmt } = CH;
  const M = () => DATA.modelOutputs;
  const sel = (name, opts, cur) => `<select name="${name}">${Object.entries(opts).map(([v, l]) => `<option value="${esc(v)}" ${v === cur ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`;
  const slider = (name, label, min, max, step, val, unit) =>
    `<label class="slider">${esc(label)} <input type="range" name="${name}" min="${min}" max="${max}" step="${step}" value="${val}"> <output>${val}</output> ${esc(unit)}</label>`;
  const STATUS = {
    physics: `<span class="badge" data-tag="semi_empirical">[Model calculation]</span>`,
    reconstruction: `<span class="badge" data-tag="direct_psi">[Reconstructs NASA FLEX run]</span>`,
    estimate: `<span class="badge" data-tag="semi_empirical">[Model estimate]</span>`,
    synthetic: `<span class="badge" data-tag="synthetic">[SYNTHETIC material]</span>`
  };

  // ---------- THM-02 ----------
  const regimeShort = le => le < 0.9 ? "unstable — cellular / flame-ball risk" : le <= 1.1 ? "neutral — smooth flame" : "damped — quench-prone";

  function lewisGauge() {
    const g = M().THM02.gauge_in_air, F = M().THM02.fuels;
    return xy({ w: 520, h: 170, m: { l: 20, r: 20, t: 34, b: 40 }, x: [0.2, 6], y: [0, 1], xlog: true, xticks: [0.2, 0.5, 0.9, 1.1, 2, 5], yticks: [],
      xlabel: "Lewis number of the fuel (log scale)", ylabel: "", aria: "Lewis number gauge",
      draw: ({ sx, sy }) => {
        const band = (a, b, op, label) => `<rect x="${sx(a)}" y="${sy(1)}" width="${sx(b) - sx(a)}" height="${sy(0) - sy(1)}" style="fill:#111;fill-opacity:${op}"/>
          <text class="note" x="${(sx(a) + sx(b)) / 2}" y="${sy(1) - 6}" text-anchor="middle">${label}</text>`;
        let s = band(0.2, 0.9, 0.16, "unstable") + band(0.9, 1.1, 0.04, "neutral") + band(1.1, 6, 0.09, "quench-prone");
        Object.entries(g).forEach(([f, v], i) => {
          const x = sx(v.Le), y = sy(0.25 + i * 0.25);
          s += `<line class="ref" x1="${x}" x2="${x}" y1="${sy(0)}" y2="${sy(1)}"/><circle class="dot" cx="${x}" cy="${y}" r="5"><title>${esc(F[f])}: Le = ${v.Le}</title></circle>
                <text class="lab" x="${x + 8}" y="${y + 4}">${esc(F[f])} ${v.Le}</text>`;
        });
        return s;
      } });
  }

  function mixerChart(f, d, p, o2) {
    const T = M().THM02, pts = T.o2_values.map(o => [o, T.grid[`${f}|${d}|${p}|${o}`]]).filter(([, v]) => v).map(([o, v]) => [o, v.Le]);
    const ys = pts.map(q => q[1]), lo = Math.min(...ys, 0.9), hi = Math.max(...ys, 1.1);
    const step = hi - lo > 3 ? 1 : hi - lo > 1.2 ? 0.5 : 0.25;
    const y0 = Math.max(0, Math.floor(lo * 0.9 / step) * step), y1 = Math.ceil(hi * 1.08 / step) * step, cur = T.grid[`${f}|${d}|${p}|${o2}`];
    const yt = []; for (let v = y0; v <= y1 + 1e-9; v += step) yt.push(r2(v));
    return xy({ w: 520, h: 230, x: [15, 100], y: [y0, y1], xticks: [15, 21, 30, 50, 75, 100], yticks: yt,
      xlabel: "Oxygen (%)", ylabel: "Lewis number",
      draw: ({ sx, sy }) => `<rect class="band" x="${sx(15)}" y="${sy(Math.min(1.1, y1))}" width="${sx(100) - sx(15)}" height="${sy(Math.max(0.9, y0)) - sy(Math.min(1.1, y1))}"><title>neutral band 0.9–1.1</title></rect>` +
        line(pts, sx, sy) + (cur ? `<g class="marker"><circle cx="${sx(o2)}" cy="${sy(cur.Le)}" r="6" fill="none"/></g>` : "") });
  }
  function mixerReadout(f, d, p, o2) {
    const v = M().THM02.grid[`${f}|${d}|${p}|${o2}`];
    if (!v) return `<p class="readout">No mixture: 2% fuel + ${o2}% O₂ exceeds 100%.</p>`;
    return `<div class="readout-grid">
      <div><b>${v.Le}</b><span>Lewis</span></div><div><b>${v.Pr}</b><span>Prandtl</span></div><div><b>${v.Sc}</b><span>Schmidt</span></div>
      <div><b>${(v.k * 1000).toFixed(1)}</b><span>k (mW/m·K)</span></div><div><b>${v.alpha.toExponential(2)}</b><span>α (m²/s)</span></div><div><b>${v.D.toExponential(2)}</b><span>D (m²/s)</span></div></div>
      <p class="readout">${esc(regimeShort(v.Le))}</p>`;
  }

  function atmospheresChart() {
    const A = M().THM02.atmospheres, keys = ["iss", "lunar_habitat", "spacesuit"], base = A.iss;
    const w = 520, h = 230, m = { l: 44, r: 10, t: 24, b: 40 }, max = 4;
    const sy = scale(0, max, h - m.b, m.t), gw = (w - m.l - m.r) / keys.length, bw = gw * 0.28;
    let s = `<g class="grid">${[0, 1, 2, 3, 4].map(v => `<line x1="${m.l}" x2="${w - m.r}" y1="${sy(v)}" y2="${sy(v)}"/>`).join("")}</g>
      <g class="ax"><line x1="${m.l}" x2="${w - m.r}" y1="${h - m.b}" y2="${h - m.b}"/>${[0, 1, 2, 3, 4].map(v => `<text x="${m.l - 6}" y="${sy(v) + 3}" text-anchor="end">×${v}</text>`).join("")}
      <text class="lab" transform="translate(11 ${(m.t + h - m.b) / 2}) rotate(-90)" text-anchor="middle">relative to ISS</text></g>`;
    keys.forEach((k, i) => {
      const a = A[k], x0 = m.l + i * gw + gw * 0.18;
      [["alpha", a.alpha / base.alpha, 0.85], ["D", a.D / base.D, 0.35]].forEach(([n, v, op], j) => {
        const x = x0 + j * (bw + 4);
        s += `<rect x="${r2(x)}" y="${r2(sy(v))}" width="${r2(bw)}" height="${r2(sy(0) - sy(v))}" style="fill:#111;fill-opacity:${op};stroke:#111"><title>${n === "alpha" ? "Heat" : "Oxygen"} diffusion ×${v.toFixed(2)}</title></rect>
          <text class="val" x="${r2(x + bw / 2)}" y="${r2(sy(v)) - 4}" text-anchor="middle">${v.toFixed(2)}</text>`;
      });
      s += `<text class="ax-t" x="${r2(x0 + bw + 2)}" y="${h - m.b + 14}" text-anchor="middle">${esc(a.label)}</text><text class="note" x="${r2(x0 + bw + 2)}" y="${h - m.b + 27}" text-anchor="middle">${a.o2_pct}% O₂ · ${a.pressure_kPa} kPa</text>`;
    });
    s += `<g class="legend"><rect x="${m.l + 8}" y="6" width="10" height="10" style="fill:#111;fill-opacity:.85"/><text x="${m.l + 22}" y="15">heat diffusion α</text>
      <rect x="${m.l + 120}" y="6" width="10" height="10" style="fill:#111;fill-opacity:.35;stroke:#111"/><text x="${m.l + 134}" y="15">O₂ diffusion D</text></g>`;
    return `<svg class="chart" viewBox="0 0 ${w} ${h}">${s}</svg>`;
  }

  function diluentCharts() {
    const D = M().THM02.diluents_for_heptane, N = { N2: "N₂", CO2: "CO₂", HE: "He" };
    const order = ["N2", "CO2", "HE"];
    return `<div class="multiples">${bars(order.map(k => ({ label: N[k], value: D[k].k * 1000 })), { w: 380, h: 270, ylabel: "conductivity k (mW/m·K)", max: 110, yticks: [0, 50, 100] })}
      ${bars(order.map(k => ({ label: N[k], value: D[k].Le })), { w: 380, h: 270, ylabel: "Lewis number of n-heptane", max: 6.5, yticks: [0, 2, 4, 6] })}</div>`;
  }

  // ---------- THM-11 ----------
  function dropletChart(id) {
    const R = M().THM11.runs[id], pts = R.time_s.map((t, i) => [t, R.d2_mm2[i]]);
    const tEnd = R.cool_extinction_time_s, obs = R.held_out_check && R.held_out_check.observed_cool_extinction_time_s;
    const xmax = Math.max(28, Math.ceil(tEnd + 2));
    return xy({ w: 520, h: 250, x: [0, xmax], y: [0, 18], xticks: Array.from({ length: Math.floor(xmax / 5) + 1 }, (_, i) => i * 5), yticks: [0, 5, 10, 15],
      xlabel: "Time since established burning (s)", ylabel: "Droplet diameter² (mm²)", aria: "Droplet burning",
      draw: ({ sx, sy }) => {
        let s = `<rect class="band" x="${sx(0)}" y="${sy(18)}" width="${sx(R.hot_extinction_time_s) - sx(0)}" height="${sy(0) - sy(18)}" style="fill-opacity:.12;stroke:none"/>
          <rect class="band" x="${sx(R.hot_extinction_time_s)}" y="${sy(18)}" width="${sx(tEnd) - sx(R.hot_extinction_time_s)}" height="${sy(0) - sy(18)}" style="fill-opacity:.04;stroke:none"/>
          <text class="note" x="${sx(R.hot_extinction_time_s / 2)}" y="${sy(17)}" text-anchor="middle">HOT FLAME</text>
          <text class="note" x="${sx((R.hot_extinction_time_s + tEnd) / 2)}" y="${sy(17)}" text-anchor="middle">COOL FLAME</text>`;
        s += line(pts.filter((_, i) => R.phase[i] === "hot_flame").concat([pts[R.phase.indexOf("cool_flame")]]), sx, sy, 0, 'stroke-width="2"');
        s += line(pts.filter((_, i) => R.phase[i] === "cool_flame"), sx, sy, 1, 'stroke-width="2"');
        [[R.hot_extinction_time_s, "hot flame out"], [tEnd, "cool flame out (model)"]].forEach(([t, l], i) =>
          s += `<line class="ref" x1="${sx(t)}" x2="${sx(t)}" y1="${sy(0)}" y2="${sy(15.5)}"/><text class="note" x="${sx(t) + (i ? -4 : 4)}" y="${sy(14.5 - i * 1.6)}" text-anchor="${i ? "end" : "start"}">${l} · ${t.toFixed(1)} s</text>`);
        if (obs) s += `<g class="marker"><line x1="${sx(obs)}" x2="${sx(obs)}" y1="${sy(0)}" y2="${sy(9)}" style="stroke-dasharray:2 2"/><text x="${sx(obs) - 4}" y="${sy(9.6)}" text-anchor="end">observed ≈ ${obs} s</text></g>`;
        return s;
      } });
  }

  function heldOutChart() {
    const R = M().THM11.runs.R379, h = R.held_out_check, w = 520, H = 150, sx = scale(0, 30, 120, w - 20);
    const row = (y, label, t, dashed) => `<text class="lab" x="112" y="${y + 9}" text-anchor="end">${label}</text>
      <rect x="${sx(0)}" y="${y}" width="${sx(t) - sx(0)}" height="14" style="fill:#111;fill-opacity:${dashed ? .25 : .82};${dashed ? "stroke:#111;stroke-dasharray:3 2" : ""}"/>
      <text class="val" x="${sx(t) + 6}" y="${y + 11}">${t.toFixed(1)} s</text>`;
    return `<svg class="chart" viewBox="0 0 ${w} ${H}">
      ${[0, 10, 20, 30].map(v => `<line class="gridv" x1="${sx(v)}" x2="${sx(v)}" y1="14" y2="${H - 30}"/><text class="note" x="${sx(v)}" y="${H - 16}" text-anchor="middle">${v} s</text>`).join("")}
      ${row(24, "Model predicts", R.cool_extinction_time_s, false)}${row(60, "NASA observed", h.observed_cool_extinction_time_s, true)}
      <text class="note" x="${sx(h.observed_cool_extinction_time_s)}" y="${100}">model is ${h.model_minus_observed_s.toFixed(1)} s late</text>
      <text class="note" x="${sx(15)}" y="${H - 2}" text-anchor="middle">Cool-flame end · FLEX R379 · 17% O₂ · 3.86 mm n-decane</text></svg>`;
  }

  // ---------- THM-16 ----------
  function heatingChart(flux) {
    const T = M().THM16, R = T.by_flux[String(flux)], crit = T.ignition_criterion_K;
    const s1 = R.time_s.map((t, i) => [t, R.surface_K[i]]), s2 = R.time_s.map((t, i) => [t, R.back_K[i]]);
    return xy({ w: 520, h: 240, x: [0, 90], y: [280, 700], xticks: [0, 30, 60, 90], yticks: [300, 400, 500, 600, 700],
      xlabel: "Heating time (s)", ylabel: "Temperature (K)", legendAt: "left", legend: [{ label: "heated surface" }, { label: "back face" }],
      draw: ({ sx, sy }) => `<line class="ref" x1="${sx(0)}" x2="${sx(90)}" y1="${sy(crit)}" y2="${sy(crit)}"/><text class="note" x="${sx(89)}" y="${sy(crit) - 5}" text-anchor="end">ignition criterion ${crit} K</text>` +
        line(s1, sx, sy, 0, 'stroke-width="2"') + line(s2, sx, sy, 1) +
        (R.time_to_ignition_s ? `<g class="marker"><circle cx="${sx(R.time_to_ignition_s)}" cy="${sy(crit)}" r="6" fill="none"/><text x="${sx(R.time_to_ignition_s) - 8}" y="${sy(crit) - 10}" text-anchor="end">ignites · ${R.time_to_ignition_s.toFixed(1)} s</text></g>` : "") });
  }

  function heatmap() {
    const H = M().THM16.heatmap_35kW, t = H.time_s, z = H.depth_mm, rows = H.T_K;
    const lo = 295, hi = Math.max(...rows.flat()), w = 520, h = 240, m = { l: 48, r: 84, t: 12, b: 38 };
    const sx = scale(0, t[t.length - 1], m.l, w - m.r), sy = scale(0, z[z.length - 1], m.t, h - m.b);
    const cw = (sx(t[1]) - sx(t[0])) + 0.6, ch = (sy(z[1]) - sy(z[0])) + 0.6;
    let s = "";
    rows.forEach((row, i) => row.forEach((v, j) => { s += `<rect x="${r2(sx(t[j]))}" y="${r2(sy(z[i]))}" width="${r2(cw)}" height="${r2(ch)}" style="fill:#111;fill-opacity:${((v - lo) / (hi - lo) * 0.9).toFixed(3)}"/>`; }));
    s += `<g class="ax"><line x1="${m.l}" x2="${w - m.r}" y1="${h - m.b + 2}" y2="${h - m.b + 2}"/>${[0, 10, 20, 30, 40].filter(v => v <= t[t.length - 1]).map(v => `<text x="${sx(v)}" y="${h - m.b + 15}" text-anchor="middle">${v}</text>`).join("")}
      ${[0, 1, 2, 3, 4].map(v => `<text x="${m.l - 6}" y="${sy(v) + 3}" text-anchor="end">${v}</text>`).join("")}
      <text class="lab" x="${(m.l + w - m.r) / 2}" y="${h - 4}" text-anchor="middle">Time (s) — until ignition at 35 kW/m²</text>
      <text class="lab" transform="translate(12 ${(m.t + h - m.b) / 2}) rotate(-90)" text-anchor="middle">Depth into slab (mm)</text></g>`;
    const lg = scale(lo, hi, h - m.b, m.t);
    s += range(0, 1, 20).map(f => `<rect x="${w - m.r + 18}" y="${r2(lg(lo + f * (hi - lo))) - 5}" width="14" height="6" style="fill:#111;fill-opacity:${(f * 0.9).toFixed(2)}"/>`).join("") +
      `<text class="note" x="${w - m.r + 36}" y="${m.t + 8}">${Math.round(hi)} K</text><text class="note" x="${w - m.r + 36}" y="${h - m.b}">${lo} K</text>`;
    return `<svg class="chart" viewBox="0 0 ${w} ${h}" aria-label="Temperature through the slab">${s}</svg>`;
  }

  function ignitionVsFlux() {
    const B = M().THM16.by_flux, pts = Object.entries(B).map(([f, v]) => [+f, v.time_to_ignition_s]);
    return xy({ w: 520, h: 230, x: [5, 45], y: [0, 100], xticks: [10, 20, 30, 40], yticks: [0, 30, 60, 90],
      xlabel: "Incident heat flux (kW/m²)", ylabel: "Time to ignition (s)",
      draw: ({ sx, sy }) => `<line class="ref" x1="${sx(5)}" x2="${sx(45)}" y1="${sy(90)}" y2="${sy(90)}"/><text class="note" x="${sx(44.5)}" y="${sy(90) + 12}" text-anchor="end">end of 90 s exposure</text>` +
        line(pts.filter(p => p[1]), sx, sy, 0) +
        pts.map(([f, t]) => t ? `<circle class="dot" cx="${sx(f)}" cy="${sy(t)}" r="4"><title>${f} kW/m²: ${t.toFixed(1)} s</title></circle><text class="note" x="${sx(f) + 6}" y="${sy(t) - 6}">${t.toFixed(0)} s</text>`
          : `<circle cx="${sx(f)}" cy="${sy(95)}" r="4" style="fill:#faf8f3;stroke:#111"><title>${f} kW/m²: no ignition within 90 s</title></circle>`).join("") +
        `<text class="note" x="${sx(17.5)}" y="${sy(95) - 9}" text-anchor="middle">no ignition within 90 s</text>` });
  }

  // ---------- registry ----------
  const R = {
    thm02_lewis_gauge: { model: "THM-02", title: "Lewis number gauge", cat: "visual", status: "physics", size: "w",
      desc: "Where each fuel's flame sits between unstable (Le < 0.9), neutral and quench-prone (Le > 1.1). Fuel at 2% in air, 300 K, 1 atm.",
      render: () => lewisGauge() },
    thm02_gas_mixer: { model: "THM-02", title: "Gas mixer", cat: "interactive", status: "physics", size: "b",
      desc: "Pick a fuel, diluent and cabin pressure, then slide the oxygen level. Every number is from THM-02's kinetic-theory calculation (pre-computed grid, 300 K, 2% fuel).",
      render: () => `<div class="controls">${sel("fuel", M().THM02.fuels, "C7H16")}${sel("dil", M().THM02.diluents, "N2")}${sel("p", M().THM02.pressures, "70.3")}
          ${slider("o2", "O₂", 15, 95, 5, 30, "%")}</div><div class="chart-slot">${mixerChart("C7H16", "N2", "70.3", 30)}</div><div class="read-slot">${mixerReadout("C7H16", "N2", "70.3", 30)}</div>`,
      mount: el => { const f = el.querySelector("[name=fuel]"), d = el.querySelector("[name=dil]"), p = el.querySelector("[name=p]"), o = el.querySelector("[name=o2]");
        const draw = () => { el.querySelector("output").textContent = o.value; el.querySelector(".chart-slot").innerHTML = mixerChart(f.value, d.value, p.value, +o.value);
          el.querySelector(".read-slot").innerHTML = mixerReadout(f.value, d.value, p.value, +o.value); };
        [f, d, p, o].forEach(x => x.addEventListener("input", draw)); } },
    thm02_atmospheres: { model: "THM-02", title: "How gases move in each atmosphere", cat: "graph", status: "physics", size: "w",
      desc: "Heat and oxygen diffuse faster at low pressure: about 1.4× faster in a lunar habitat and 3.5× in a spacesuit than on the ISS. Their ratio (Lewis number ≈ 1.02) barely changes.",
      render: () => atmospheresChart() },
    thm02_diluents: { model: "THM-02", title: "Nitrogen vs CO₂ vs helium", cat: "graph", status: "physics", size: "w",
      desc: "Swapping nitrogen for helium makes the gas ~4× better at conducting heat and roughly doubles n-heptane's Lewis number — one reason helium behaves differently as a suppressant (FLEX).",
      render: () => diluentCharts() },
    thm11_droplet: { model: "THM-11", title: "Droplet burning: hot → cool flame", cat: "interactive", status: "reconstruction", size: "w",
      desc: "An n-decane droplet shrinks steadily while the visible flame burns, then keeps burning as an almost invisible cool flame. R377 reconstructs a real FLEX test; R379 is a model estimate checked against NASA's observation.",
      render: () => `<div class="controls">${sel("run", { R377: "FLEX run R377 · 21% O₂ · 4.03 mm", R379: "FLEX run R379 · 17% O₂ · 3.86 mm" }, "R377")}</div><div class="chart-slot">${dropletChart("R377")}</div>`,
      mount: el => { const s = el.querySelector("[name=run]"); s.addEventListener("input", () => { el.querySelector(".chart-slot").innerHTML = dropletChart(s.value);
        const b = el.querySelector("header .badge"); if (b) b.outerHTML = STATUS[s.value === "R377" ? "reconstruction" : "estimate"]; }); } },
    thm11_held_out: { model: "THM-11", title: "Model vs NASA observation", cat: "explanation", status: "estimate", size: "w",
      desc: "Honest check: for run R379 the model's cool-flame end comes about 11 s after the ≈13 s NASA observed. Shows where the model needs more evidence.",
      render: () => heldOutChart() },
    thm11_facts: { model: "THM-11", title: "Droplet key facts (R377)", cat: "data", status: "reconstruction", size: "w",
      desc: "Headline numbers for FLEX run R377 from THM-11.",
      render: () => { const R = M().THM11.runs.R377;
        return `<div class="facts"><div><span>Visible flame goes out</span><b>${R.hot_extinction_time_s.toFixed(1)} s</b></div><div><span>Cool flame lasts</span><b>${R.cool_stage_duration_s.toFixed(1)} s</b></div><div><span>Burning ends</span><b>${R.cool_extinction_time_s.toFixed(1)} s</b></div></div>`; } },
    thm16_heating: { model: "THM-16", title: "Heating to ignition", cat: "interactive", status: "synthetic", size: "w",
      desc: "How fast a solid's surface heats under a radiant heater, and when it reaches the ignition temperature. Slide the heat flux. Material is the thermo team's synthetic 4 mm demo slab.",
      render: () => `<div class="controls">${slider("flux", "Heat flux", 10, 40, 5, 35, "kW/m²")}</div><div class="chart-slot">${heatingChart(35)}</div>`,
      mount: el => { const s = el.querySelector("input"); s.addEventListener("input", () => { el.querySelector("output").textContent = s.value; el.querySelector(".chart-slot").innerHTML = heatingChart(+s.value); }); } },
    thm16_heatmap: { model: "THM-16", title: "Heat soaking into the material", cat: "visual", status: "synthetic", size: "w",
      desc: "Temperature through the slab's thickness over time (darker = hotter) until the surface ignites, at 35 kW/m².",
      render: () => heatmap() },
    thm16_ignition_vs_flux: { model: "THM-16", title: "Ignition time vs heat flux", cat: "graph", status: "synthetic", size: "w",
      desc: "Stronger heating ignites the material sooner; at 25 kW/m² and below it doesn't ignite within 90 s.",
      render: () => ignitionVsFlux() },
    thm16_fact: { model: "THM-16", title: "Time to ignition", cat: "data", status: "synthetic", size: "s",
      desc: "Headline number from THM-16 for the synthetic slab at 35 kW/m².",
      render: () => `<div class="facts one"><div><span>Ignites after</span><b>${M().THM16.by_flux["35"].time_to_ignition_s.toFixed(0)} s</b><span>at 35 kW/m² · synthetic slab</span></div></div>` }
  };

  // compact previews for dashboard tiles (default state, no controls)
  const TILE = {
    thm02_lewis_gauge: () => lewisGauge(), thm02_gas_mixer: () => mixerChart("C7H16", "N2", "70.3", 30),
    thm02_atmospheres: () => atmospheresChart(), thm02_diluents: () => diluentCharts(),
    thm11_droplet: () => dropletChart("R377"), thm11_held_out: () => heldOutChart(), thm11_facts: () => R.thm11_facts.render(),
    thm16_heating: () => heatingChart(35), thm16_heatmap: () => heatmap(), thm16_ignition_vs_flux: () => ignitionVsFlux(), thm16_fact: () => R.thm16_fact.render()
  };
  const ASPECT = { thm02_lewis_gauge: 520 / 170, thm02_gas_mixer: 520 / 230, thm02_atmospheres: 520 / 230, thm02_diluents: 2.7, thm11_droplet: 520 / 250,
    thm11_held_out: 520 / 150, thm11_facts: 3.0, thm16_heating: 520 / 240, thm16_heatmap: 520 / 240, thm16_ignition_vs_flux: 520 / 230, thm16_fact: 1.25 };

  function render(type) {
    const d = R[type];
    return `<section class="widget mw size-${d.size}" data-mw="${type}">
      <header><b>${esc(d.title)}</b><span class="kind">${esc(d.model)} · ${esc(d.cat)}</span>${STATUS[d.status]}</header>
      <p class="why">${esc(d.desc)}</p><div class="widget-body">${d.render()}</div></section>`;
  }
  function mountAll(root) { root.querySelectorAll("[data-mw]").forEach(el => { const d = R[el.dataset.mw]; if (d.mount) d.mount(el); }); }
  return { lib: R, types: () => Object.keys(R), render, mountAll, STATUS,
    tile: t => TILE[t](), aspect: t => ASPECT[t] || 2, body: t => R[t].render(), mount: (el, t) => R[t].mount && R[t].mount(el) };
})();
