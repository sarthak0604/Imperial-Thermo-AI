// MORE MODEL WIDGETS — charts for the models added from the haykm branch: THM-04, 05, 06, 15, 17, 18, 19, 20.
// Same chart kit and look as js/model_widgets.js; they register themselves with MW.extend(). Data: data/model_outputs.js.
// Written with SI assistance (Claude, Anthropic).
(() => {
  const { esc } = U;
  const { host, frame, line, dot, vref, href, chip, chipRows, hatchDef, caps, title, titleW, T, range, scale, r1, monoW, capsW, tkSize, CHIP_H } = CH;
  const M = () => DATA.modelOutputs;
  const badge = (tag, text) => `<span class="badge" data-tag="${tag}">[${text}]</span>`;
  MW.STATUS.reduction = badge("direct_psi", "Reduces measured data");
  MW.STATUS.screening = badge("semi_empirical", "Screening estimate");
  MW.STATUS.budget = badge("semi_empirical", "Thermal budget");
  MW.STATUS.illustrative = badge("synthetic", "ILLUSTRATIVE inputs");

  // legend: short line samples + uppercase labels, right-aligned on the title row
  function lineKey(items, xr, y) {
    let x = xr, s = "";
    items.slice().reverse().forEach(([label, style]) => {
      x -= capsW(label, 10);
      s += caps(x, y, label) + `<path class="s${style === "dash" ? " dash" : style === "thin" ? " thin" : ""}" d="M${r1(x - 22)},${r1(y - 3.5)}h16"/>`;
      x -= 32;
    });
    return s;
  }
  // draw a sub-chart in a panel of its own (x0, width pw) so two small charts can sit side by side
  const panel = (sz, x0, pw, fn) => `<g transform="translate(${r1(x0)},0)">${fn({ w: pw, h: sz.h, compact: sz.compact, id: sz.id })}</g>`;
  const thousands = v => String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");

  // ---------- THM-04: heat release from oxygen use ----------
  function hrrChart() {
    return host(sz => {
      const D = M().THM04, c = sz.compact;
      const F = frame(sz, { x: [995, 1005], y: [0, 400], xticks: [995, 1000, 1005], yticks: [0, 100, 200, 300, 400], xlabel: "Time into test", xunit: "s", ylabel: "Power", yunit: "kW", top: 14 });
      const { sx, sy, X0, X1, Y0 } = F;
      let s = F.axes + line(D.time_s.map((t, i) => [t, D.reference_kW[i]]), sx, sy, { dashed: true }) + line(D.time_s.map((t, i) => [t, D.hrr_kW[i]]), sx, sy);
      s += lineKey(c ? [["O₂", "solid"], ["Meter", "dash"]] : [["From O₂", "solid"], ["Burner meter", "dash"]], sz.w, c ? 24 : 26);
      s += dot(sx(D.peak_time_s), sy(D.peak_kW), { r: 4, tip: `peak ${D.peak_kW.toFixed(0)} kW` });
      const pct = (D.model_minus_reference_kJ / D.reference_total_kJ * 100).toFixed(1);
      const items = c ? [{ x: (X0 + X1) / 2, anchor: "middle", text: `peak ${D.peak_kW.toFixed(0)} kW`, dark: true }, { x: (X0 + X1) / 2, anchor: "middle", text: `+${pct}% vs meter` }]
        : [{ x: (X0 + X1) / 2, anchor: "middle", text: `peak ${D.peak_kW.toFixed(0)} kW at ${D.peak_time_s} s`, dark: true },
          { x: (X0 + X1) / 2, anchor: "middle", text: `${thousands(D.total_kJ)} kJ vs ${thousands(D.reference_total_kJ)} kJ metered · +${pct}%` }];
      const room = Y0 - sy(D.peak_kW) - 14, fit = Math.max(1, Math.min(items.length, Math.floor(room / (CHIP_H + 6))));
      s += chipRows(items.slice(0, fit), sy(D.peak_kW) + 14 + CHIP_H / 2, CHIP_H + 6, { compact: c, bounds: sz.w }).svg;
      return s;
    }, { label: "Heat release rate worked out from oxygen use, against the burner's own meter" });
  }

  // ---------- THM-05: opposed-flow spread vs thickness ----------
  function spreadChart() {
    return host(sz => {
      const D = M().THM05, c = sz.compact, sw = D.sweep;
      const F = frame(sz, { x: [0, 0.5], y: [0, 2.5], xticks: [0, 0.1, 0.2, 0.3, 0.4, 0.5], yticks: [0, 0.5, 1, 1.5, 2, 2.5], xlabel: "Sheet thickness", xunit: "mm", ylabel: "Spread rate", yunit: "mm/s", top: 14 });
      const { sx, sy } = F;
      let s = F.axes + line(sw.map(p => [p.thickness_mm, p.rate_mm_s]), sx, sy);
      s += D.checks.map(k => dot(sx(k.thickness_mm), sy(k.observed_mm_s), { hollow: true, r: 5, tip: `NASA ${k.run}: ${k.observed_mm_s} mm/s` })).join("");
      s += sw.map(p => dot(sx(p.thickness_mm), sy(p.rate_mm_s), { r: 3.2, tip: `model: ${p.rate_mm_s} mm/s` })).join("");
      const cur = sw.find(p => p.thickness_mm === D.thickness_mm) || sw[2];
      s += chip(sx(cur.thickness_mm) + 12, sy(cur.rate_mm_s) - 12, c ? `${cur.rate_mm_s.toFixed(2)} mm/s` : `${cur.thickness_mm} mm → ${cur.rate_mm_s.toFixed(2)} mm/s`, { dark: true, compact: c, bounds: sz.w });
      const ly = c ? 24 : 26, wN = capsW(c ? "NASA" : "NASA runs", 10);
      s += lineKey([["Model", "solid"]], sz.w - wN - 36, ly) + `<circle class="pt hollow" cx="${r1(sz.w - wN - 14)}" cy="${ly - 3.5}" r="4"/>` + caps(sz.w - wN, ly, c ? "NASA" : "NASA runs");
      return s;
    }, { label: "Flame spread rate against sheet thickness, model and NASA measurements" });
  }

  // ---------- THM-06: concurrent-flow spread ----------
  function growthRateChart() {
    return host(sz => {
      const D = M().THM06, c = sz.compact, tmax = Math.ceil(D.time_s[D.time_s.length - 1] / 10) * 10;
      const F = frame(sz, { x: [0, tmax], y: [1.5, 2.6], xticks: range(0, tmax, tmax / 10 > 9 ? 5 : tmax / 10).filter((_, i) => i % 2 === 0), yticks: [1.5, 2, 2.5], xlabel: "Time", xunit: "s", ylabel: "Spread rate", yunit: "mm/s" });
      const { sx, sy, X0, X1 } = F;
      let s = F.axes + href(sy(D.limiting_mm_s), X0, X1) + title(X1, sy(D.limiting_mm_s) + 15, "Limiting rate", D.limiting_mm_s.toFixed(2) + " mm/s", "end");
      s += line(D.time_s.map((t, i) => [t, D.rate_mm_s[i]]), sx, sy);
      const t0 = D.time_s[0], r0 = D.rate_mm_s[0];
      s += dot(sx(t0), sy(r0), { r: 4 }) + chip(sx(t0) + 10, sy(r0) - 16, c ? `${r0.toFixed(2)} mm/s` : `starts at ${r0.toFixed(2)} mm/s`, { compact: c, bounds: sz.w });
      return s;
    }, { label: "Spread rate against time as the flame grows" });
  }
  function frontChart() {
    return host(sz => {
      const D = M().THM06, c = sz.compact, tmax = Math.ceil(D.time_s[D.time_s.length - 1] / 10) * 10, L = D.sample_length_m * 100;
      const F = frame(sz, { x: [0, tmax], y: [0, 35], xticks: range(0, tmax, tmax / 10 > 9 ? 5 : tmax / 10).filter((_, i) => i % 2 === 0), yticks: [0, 10, 20, 30], xlabel: "Time", xunit: "s", ylabel: "Position", yunit: "cm", top: 14 });
      const { sx, sy, X0, X1 } = F;
      let s = F.axes + href(sy(L), X0, X1) + title(X0 + 6, sy(L) - 6, "End of sample", L.toFixed(0) + " cm");
      s += line(D.time_s.map((t, i) => [t, D.front_m[i] * 100]), sx, sy) + line(D.time_s.map((t, i) => [t, D.tip_m[i] * 100]), sx, sy, { dashed: true });
      s += lineKey(c ? [["Front", "solid"], ["Tip", "dash"]] : [["Burning front", "solid"], ["Flame tip", "dash"]], sz.w, c ? 24 : 26);
      return s;
    }, { label: "Position of the burning front and flame tip along the sample over time" });
  }

  // ---------- THM-15: soot inception screen ----------
  function sootGauge() {
    return host(sz => {
      const { w, h, compact: c, id } = sz, D = M().THM15, fs = tkSize(c), lo = 1050, hi = 1350;
      const first = v => (D.sweep.find(p => p[1] === v) || [null])[0], nearAt = first("near_threshold"), possAt = first("inception_possible");
      const sx = scale(lo, hi, 2, w - 2), bh = c ? 24 : Math.round(Math.min(46, Math.max(28, h * 0.1))), step = CHIP_H + 6;
      const need = 20 + bh + fs + 12 + step * 2 + (c ? 0 : 20), by0 = Math.max(20, Math.round((h - need) / 2) + 20), by1 = by0 + bh, hid = id + "-h";
      const seg = (a, b, attrs) => `<rect x="${r1(sx(a))}" y="${by0}" width="${r1(sx(b) - sx(a))}" height="${bh}" ${attrs}/>`;
      let s = hatchDef(hid) + seg(lo, nearAt, `fill="url(#${hid})"`) + seg(nearAt, possAt, `class="paper"`) + seg(possAt, hi, `class="band"`);
      s += `<rect class="frame" x="${r1(sx(lo))}" y="${by0}" width="${r1(sx(hi) - sx(lo))}" height="${bh}"/>` + [nearAt, possAt].map(v => `<line class="base" x1="${r1(sx(v))}" x2="${r1(sx(v))}" y1="${by0}" y2="${by1}"/>`).join("");
      const mid = (a, b) => sx((a + b) / 2), wide = (a, b, txt) => sx(b) - sx(a) > capsW(txt, 10.5) + 6;
      s += caps(mid(lo, nearAt), by0 - 7, wide(lo, nearAt, "Below") ? "Below" : "", "middle") + caps(mid(nearAt, possAt), by0 - 7, wide(nearAt, possAt, "Near") ? "Near" : "", "middle") +
        caps(mid(possAt, hi), by0 - 7, wide(possAt, hi, "Inception possible") ? "Inception possible" : "Soot", "middle");
      s += (c || w < 420 ? [1100, 1200, 1300] : [1100, 1150, 1200, 1250, 1300]).map(v => T(sx(v), by1 + fs + 4, String(v), "tk", "middle")).join("");
      s += `<line class="mk" x1="${r1(sx(D.threshold_K))}" x2="${r1(sx(D.threshold_K))}" y1="${by0 - 2}" y2="${by1 + 2}"/>`;
      s += `<line class="mk" x1="${r1(sx(D.local_K))}" x2="${r1(sx(D.local_K))}" y1="${by0 - 2}" y2="${by1 + 2}"/>`;
      const rows = chipRows([{ x: sx(D.threshold_K), anchor: "end", text: c ? `limit ${D.threshold_K}` : `threshold ${D.threshold_K} K`, leader: by1 + 2 },
        { x: sx(D.local_K), anchor: "start", text: c ? `${D.local_K} K` : `flame ${D.local_K} K · +${D.margin_K} K`, dark: true, leader: by1 + 2 }], by1 + fs + 16 + CHIP_H / 2, step, { compact: c, bounds: w });
      s += rows.svg;
      if (!c) s += title(w - 2, by1 + fs + 16 + rows.rows * step + 14, "Local flame temperature", `${D.fuel} · C/O ${D.co_ratio} · ${D.residence_s} s`, "end");
      return s;
    }, { label: "Flame temperature against the soot inception threshold" });
  }

  // ---------- THM-17: limiting oxygen vs airflow ----------
  function limitChart() {
    return host(sz => {
      const D = M().THM17, c = sz.compact, xs = D.speed_cm_s_sweep;
      const F = frame(sz, { x: [0.2, 25], y: [12, 17], xlog: true, xticks: [0.2, 0.5, 1, 2, 5, 10, 20], yticks: [12, 13, 14, 15, 16, 17], xlabel: "Airflow speed", xunit: "cm/s", ylabel: "Oxygen needed", yunit: "%", top: 14 });
      const { sx, sy } = F, pts = k => xs.map((v, i) => [v, D[k][i]]);
      let s = F.axes;
      s += line(pts("quench_pct"), sx, sy, { dashed: true }) + line(pts("blowoff_pct"), sx, sy, { thin: true }) + line(pts("limit_curve_pct"), sx, sy);
      const low = pts("limit_curve_pct").reduce((a, b) => b[1] < a[1] ? b : a), x = sx(low[0]), y = sy(low[1]);
      s += dot(x, y, { r: 5 }) + chip(x + 9, y + 20, c ? `${low[1].toFixed(1)}%` : `lowest ≈ ${low[1].toFixed(1)}% O₂ at ${low[0].toFixed(0)} cm/s`, { dark: true, compact: c, bounds: sz.w });
      s += lineKey([["Limit", "solid"], ["Quench", "dash"], ["Blow-off", "thin"]], sz.w, c ? 24 : 26);
      return s;
    }, { label: "Oxygen needed for a flame to keep spreading, against airflow speed" });
  }

  // ---------- THM-18: suppression ----------
  function dilutionChart() {
    return host(sz => {
      const D = M().THM18, c = sz.compact, gap = c ? 18 : 32, pw = Math.floor((sz.w - gap) / 2), a = D.added_pct, at = D.at_30;
      const one = (sub, name, unit, ys, yr, yt, mark, txt) => {
        const F = frame(sub, { x: [0, 100], y: yr, xticks: [0, 50, 100], yticks: yt, xlabel: c ? "CO₂ added" : "CO₂ added", xunit: "%", ylabel: name, yunit: unit });
        const { sx, sy } = F; let s = F.axes + line(a.map((v, i) => [v, ys[i]]), sx, sy);
        s += dot(sx(at.added_pct), sy(mark), { r: 4.5 }) + chip(sx(at.added_pct) + 8, sy(mark) + (name === "Oxygen" ? -16 : 18), txt, { dark: true, compact: c, bounds: sub.w });
        return s;
      };
      return panel(sz, 0, pw, sub => one(sub, "Oxygen", "% left", D.o2_pct, [0, 25], [0, 10, 20], at.o2_pct, `${at.o2_pct.toFixed(1)}% at 30%`)) +
        panel(sz, pw + gap, pw, sub => one(sub, c ? "Heat" : "Heat soaked", "kJ/m³", D.heat_kJ_m3, [100, 170], [100, 130, 160], 119.04 + at.extra_heat_kJ_m3, `+${at.extra_heat_kJ_m3.toFixed(0)} kJ/m³`));
    }, { label: "Oxygen left and heat absorbed as carbon dioxide is added to air" });
  }
  const mistFacts = () => { const m = M().THM18.mist;
    return `<div class="facts"><div><span>Heating the water</span><b>${m.sensible_heat_kJ.toFixed(0)} kJ</b></div><div><span>Evaporating half</span><b>${m.latent_heat_kJ.toFixed(0)} kJ</b></div><div><span>Total absorbed</span><b>${m.total_water_heat_sink_kJ.toFixed(0)} kJ</b></div></div>`; };

  // ---------- THM-19: sealed cabin ----------
  function cabinChart() {
    return host(sz => {
      const D = M().THM19, c = sz.compact, gap = c ? 18 : 32, pw = Math.floor((sz.w - gap) / 2), t = D.time_s;
      const one = (sub, name, unit, ys, yr, yt, peak, txt) => {
        const F = frame(sub, { x: [0, 300], y: yr, xticks: [0, 100, 200, 300], yticks: yt, xlabel: "Time", xunit: "s", ylabel: name, yunit: unit });
        const { sx, sy } = F; let s = F.axes + line(t.map((v, i) => [v, ys[i]]), sx, sy);
        const k = ys.indexOf(Math.max(...ys)); s += dot(sx(t[k]), sy(ys[k]), { r: 4.5 }) + chip(sx(t[k]) + 10, sy(ys[k]) - 2, txt, { dark: true, compact: c, bounds: sub.w });
        return s;
      };
      const dP = D.pressure_change_kPa, dT = D.temperature_K.map(v => v - D.T0_K);
      return panel(sz, 0, pw, sub => one(sub, "Pressure", "+kPa", dP, [0, 3], [0, 1, 2, 3], D.peak_dp_kPa, `+${D.peak_dp_kPa.toFixed(1)} kPa`)) +
        panel(sz, pw + gap, pw, sub => one(sub, "Temperature", "+K", dT, [0, 15], [0, 5, 10, 15], D.peak_T_K - D.T0_K, `+${(D.peak_T_K - D.T0_K).toFixed(0)} K`));
    }, { label: "Cabin pressure and temperature rise after a fire, in a sealed cabin" });
  }

  // ---------- THM-20: smoke in a duct ----------
  function smokeChart() {
    return host(sz => {
      const D = M().THM20, c = sz.compact, gap = c ? 18 : 32, pw = Math.floor((sz.w - gap) / 2), t = D.time_s;
      const one = (sub, name, unit, ys, yr, yt, fmtv) => {
        const F = frame(sub, { x: [0, 100], y: yr, xticks: [0, 50, 100], yticks: yt, xlabel: "Time", xunit: "s", ylabel: name, yunit: unit });
        const { sx, sy, Y0, Y1 } = F; let s = F.axes + vref(sx(D.travel_s), Y0, Y1) + line(t.map((v, i) => [v, ys[i]]), sx, sy);
        const k = t.reduce((b, v, i) => Math.abs(v - D.travel_s) < Math.abs(t[b] - D.travel_s) ? i : b, 0);
        s += dot(sx(t[k]), sy(ys[k]), { r: 4.5 }) + chip(sx(t[k]) + 8, sy(ys[k]) - 16, fmtv, { dark: true, compact: c, bounds: sub.w });
        return s;
      };
      return panel(sz, 0, pw, sub => one(sub, c ? "Count" : "Particle count", "10¹¹/m³", D.number_1e11_m3, [0, 14], [0, 5, 10], D.n_arrival_1e11_m3.toFixed(1))) +
        panel(sz, pw + gap, pw, sub => one(sub, "Size", "µm", D.diameter_um, [0.99, 1.02], [1, 1.01, 1.02], D.d_arrival_um.toFixed(3)));
    }, { label: "Smoke particle count and size as the smoke travels along a duct" });
  }

  // ---------- register ----------
  const S = "reduction", Z = "illustrative";
  MW.extend({
    thm04_hrr: { reg: { model: "THM-04", title: "Fire power from oxygen use", cat: "graph", status: S, size: "w",
      desc: "How strong a fire is can be worked out from how much oxygen it uses up (about 13 MJ per kg of O₂). This example reduces 10 s of a NIST natural-gas burner test, a ground test rather than microgravity; its total comes within about 2% of the burner's own meter. NASA's Saffire VI used the same method in orbit.",
      render: () => hrrChart() }, tile: () => hrrChart(), shape: [1.8, 1.4, 2.7] },
    thm05_spread: { reg: { model: "THM-05", title: "Flame creeping against airflow", cat: "graph", status: "estimate", size: "w",
      desc: "How fast a flame crawls along a PMMA sheet against a gentle 3 cm/s airflow. Thinner sheets burn faster; the model line passes through the BASS-II measurements NASA took in microgravity (hollow circles) at 0.2 and 0.3 mm.",
      render: () => spreadChart() }, tile: () => spreadChart(), shape: [1.8, 1.4, 2.6] },
    thm06_rate: { reg: { model: "THM-06", title: "Flame spread speeds up as it grows", cat: "graph", status: Z, size: "w",
      desc: "Flame spreading WITH the airflow over a thin fabric card (Saffire II). The burning zone lengthens and the spread rate climbs toward a limiting value of about 2.4 mm/s. The limiting rate is anchored to NASA runs; the growth curve starts from illustrative values.",
      render: () => growthRateChart() }, tile: () => growthRateChart(), shape: [1.9, 1.4, 2.8] },
    thm06_front: { reg: { model: "THM-06", title: "Where the flame front is", cat: "graph", status: Z, size: "w",
      desc: "Positions of the burning front and the flame tip along the 29 cm fabric card over about 90 s, with airflow in the same direction. The model stops when the heated zone reaches the end of the sample.",
      render: () => frontChart() }, tile: () => frontChart(), shape: [1.8, 1.4, 2.6] },
    thm15_soot: { reg: { model: "THM-15", title: "Soot inception screen", cat: "visual", status: "screening", size: "w",
      desc: "A quick screen for whether a flame region is hot enough for soot to begin forming, here for an ethylene flame in a drop-tower. The threshold (1190 K at C/O 0.6) is published; the 50 K 'near' band and the flame conditions are illustrative. It says nothing about how much soot is made or how the flame looks.",
      render: () => sootGauge() }, tile: () => sootGauge(), shape: [2.4, 1.6, 3.4] },
    thm17_limiting_oxygen: { reg: { model: "THM-17", title: "Oxygen a flame needs vs airflow", cat: "graph", status: "estimate", size: "w",
      desc: "The lowest oxygen level at which a flame keeps spreading over a PMMA rod in microgravity, against airflow speed. Very slow flow starves the flame (quench) and fast flow blows it off, so the easiest speed for a flame sits in between. This is the pooled BASS-II fit, with substantial scatter near the limit.",
      render: () => limitChart() }, tile: () => limitChart(), shape: [1.8, 1.4, 2.6] },
    thm18_dilution: { reg: { model: "THM-18", title: "Adding CO₂ to air", cat: "graph", status: "budget", size: "w",
      desc: "How adding carbon dioxide to air changes the oxygen left and the heat the gas can soak up when warmed from 300 to 400 K. This is a thermal budget only; it does not predict whether a flame goes out. Inputs are illustrative.",
      render: () => dilutionChart() }, tile: () => dilutionChart(), shape: [2.0, 1.6, 3.0] },
    thm18_mist: { reg: { model: "THM-18", title: "Water mist heat sink", cat: "data", status: "budget", size: "w",
      desc: "Heat taken up by 0.2 kg of water mist warmed from 20 to 100 °C with half of it evaporating. Most of the heat goes into evaporation. A thermal budget only; droplet delivery and evaporation rate are not modelled.",
      render: () => mistFacts() }, tile: () => mistFacts(), shape: [3.0, 2.2, 5.0] },
    thm19_cabin: { reg: { model: "THM-19", title: "Cabin pressure after a fire", cat: "graph", status: Z, size: "w",
      desc: "A sealed 16.7 m³ cabin at 54.6 kPa and 30% oxygen with a small fire (peaking at 2.4 kW) for 3 minutes: pressure and temperature rise, then ease as the walls absorb heat. The fire history is illustrative, inspired by Saffire VI.",
      render: () => cabinChart() }, tile: () => cabinChart(), shape: [2.0, 1.6, 3.0] },
    thm20_smoke: { reg: { model: "THM-20", title: "Smoke ageing in a duct", cat: "graph", status: Z, size: "w",
      desc: "Smoke particles drifting along a 3 m vent duct. Over the ≈40 s the smoke takes to reach the far end, particles clump together so the count falls by almost a third, while their size grows by less than 1%. Illustrative duct and smoke values, inspired by NASA's SAME experiments.",
      render: () => smokeChart() }, tile: () => smokeChart(), shape: [2.0, 1.6, 3.0] }
  });
})();
