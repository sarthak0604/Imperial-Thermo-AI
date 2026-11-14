// MODEL WIDGETS FROM LIEM'S MODELS — charts for THM-01, 03, 07, 08, 09. Same chart kit and look as js/model_widgets.js;
// they register themselves with MW.extend(). Data: data/model_outputs.js (made by standin/precompute_models.py).
// Written with SI assistance (Claude, Anthropic).
(() => {
  const { host, frame, line, dot, vref, href, chip, chipRows, hatchDef, caps, title, T, scale, r1, capsW, tkSize, CHIP_H } = CH;
  const M = () => DATA.modelOutputs;
  const badge = (tag, text) => `<span class="badge" data-tag="${tag}">[${text}]</span>`;
  MW.STATUS.bound = badge("theoretical_bound", "Theoretical bound");

  function lineKey(items, xr, y) {
    let x = xr, s = "";
    items.slice().reverse().forEach(([label, style]) => {
      x -= capsW(label, 10);
      s += caps(x, y, label) + `<path class="s${style === "dash" ? " dash" : style === "thin" ? " thin" : ""}" d="M${r1(x - 22)},${r1(y - 3.5)}h16"/>`;
      x -= 32;
    });
    return s;
  }
  const panel = (sz, x0, pw, fn) => `<g transform="translate(${r1(x0)},0)">${fn({ w: pw, h: sz.h, compact: sz.compact, id: sz.id })}</g>`;
  const num = (v, d = 2) => v >= 100 ? String(Math.round(v)) : v.toFixed(d);

  // ---------- THM-01: flame temperature in three atmospheres ----------
  function flameTempChart() {
    return host(sz => {
      const D = M().THM01, c = sz.compact, at = D.atmospheres, st = ["solid", "dash", "thin"], keys = ["methane", "hydrogen", "propane"], names = c ? ["ISS", "Lunar", "Suit"] : ["ISS air", "Lunar hab.", "Spacesuit"];
      const F = frame(sz, { x: [-0.35, 2.35], y: [1800, 3000], xticks: [0, 1, 2], xfmt: v => names[v], yticks: [2000, 2400, 2800], ylabel: "Flame temperature", yunit: "K", top: 14 });
      const { sx, sy } = F;
      let s = F.axes;
      keys.forEach((k, i) => { s += line(at.map((_, j) => [j, D.fuels[k].T_ad_K[j]]), sx, sy, { dashed: st[i] === "dash", thin: st[i] === "thin" }); });
      const m = D.fuels.methane.T_ad_K;
      s += at.map((a, j) => dot(sx(j), sy(m[j]), { r: 4, tip: `${a.name}: ${m[j].toFixed(0)} K (methane)` })).join("");
      s += lineKey(c ? keys.map((k, i) => [D.fuels[k].label.slice(0, 4) + ".", st[i]]) : keys.map((k, i) => [D.fuels[k].label, st[i]]), sz.w, c ? 24 : 26);
      s += at.map((a, j) => chip(sx(j), sy(m[j]) + 22, `${m[j].toFixed(0)}${c ? "" : " K"}`, { dark: true, compact: c, bounds: sz.w, anchor: "middle" })).join("");
      return s;
    }, { label: "Flame temperature of methane, hydrogen and propane in ISS air, lunar habitat air and a spacesuit" });
  }

  // ---------- THM-03: flame position (Burke-Schumann) ----------
  function zstChart() {
    return host(sz => {
      const D = M().THM03, c = sz.compact, gap = c ? 18 : 32, pw = Math.floor((sz.w - gap) / 2), x = D.y_ox_pct;
      const one = (sub, name, unit, ys, yr, yt, mark, txt, fmt) => {
        const F = frame(sub, { x: [10, 100], y: yr, xticks: [20, 60, 100], yticks: yt, xlabel: "Oxygen", xunit: "%", ylabel: name, yunit: unit, yfmt: fmt });
        const { sx, sy } = F; let s = F.axes + line(x.map((v, i) => [v, ys[i]]), sx, sy);
        s += dot(sx(23.2), sy(mark), { r: 4.5 }) + chip(sx(23.2) + 8, sy(mark) + (name === "Flame size" ? -16 : 11), txt, { dark: true, compact: c, bounds: sub.w });
        return s;
      };
      return panel(sz, 0, pw, sub => one(sub, c ? "Position" : "Flame position", "Z_st", D.zst, [0, 0.25], [0, 0.1, 0.2], D.air_zst, `${D.air_zst.toFixed(3)} in air`)) +
        panel(sz, pw + gap, pw, sub => one(sub, "Flame size", "× burner", D.radius_ratio, [0, 60], [0, 20, 40, 60], D.air_radius_ratio, `${D.air_radius_ratio.toFixed(0)}× in air`));
    }, { label: "Flame position and size against oxygen supplied, for a methane flame in microgravity" });
  }

  // ---------- THM-07: Damkohler number vs airflow ----------
  function blowoffChart() {
    return host(sz => {
      const D = M().THM07, c = sz.compact, u = D.speed_cm_s, A = D.cases.iss, B = D.cases.lunar, lg = v => Math.log10(v);
      const F = frame(sz, { x: [4, 150], y: [-1.6, 2.3], xlog: true, xticks: [5, 10, 20, 50, 100], yticks: [-1, 0, 1, 2], yfmt: v => String(Math.round(10 ** v * 10) / 10), xlabel: "Airflow speed", xunit: "cm/s", ylabel: "Damköhler number", yunit: "", top: 14 });
      const { sx, sy, X0, X1 } = F, pts = d => u.map((v, i) => [v, lg(d[i])]);
      let s = F.axes + href(sy(0), X0, X1) + title(X0 + 6, sy(0) + 15, "Da = 1", "blow-off");
      s += line(pts(A.da), sx, sy) + line(pts(B.da), sx, sy, { dashed: true });
      s += dot(sx(A.blowoff_cm_s), sy(0), { r: 4.5 }) + dot(sx(B.blowoff_cm_s), sy(0), { r: 4.5 });
      s += chip(sx(A.blowoff_cm_s) - 9, sy(0) - 18, c ? `${A.blowoff_cm_s.toFixed(0)}` : `ISS ${A.blowoff_cm_s.toFixed(0)} cm/s`, { dark: true, compact: c, bounds: sz.w, anchor: "end" });
      s += chip(sx(B.blowoff_cm_s) + 9, sy(0) - 18, c ? `${B.blowoff_cm_s.toFixed(0)}` : `Lunar ${B.blowoff_cm_s.toFixed(0)} cm/s`, { dark: true, compact: c, bounds: sz.w });
      s += lineKey(c ? [["ISS", "solid"], ["Lunar", "dash"]] : [["ISS air", "solid"], ["Lunar habitat", "dash"]], sz.w, c ? 24 : 26);
      return s;
    }, { label: "Damköhler number against airflow speed, for ISS air and lunar habitat air; flames blow off where it drops below one" });
  }

  // ---------- THM-08: buoyancy vs forced flow gauge ----------
  function richardsonGauge() {
    return host(sz => {
      const { w, h, compact: c, id } = sz, D = M().THM08, fs = tkSize(c), lo = -3, hi = 2.2, lg = v => Math.log10(v);
      const sx = scale(lo, hi, 2, w - 2), bh = c ? 24 : Math.round(Math.min(46, Math.max(28, h * 0.1))), step = CHIP_H + 6;
      const need = 20 + bh + fs + 12 + step * 2 + (c ? 0 : 20), by0 = Math.max(20, Math.round((h - need) / 2) + 20), by1 = by0 + bh, hid = id + "-h";
      const seg = (a, b, attrs) => `<rect x="${r1(sx(a))}" y="${by0}" width="${r1(sx(b) - sx(a))}" height="${bh}" ${attrs}/>`;
      let s = hatchDef(hid) + seg(lo, -1, `fill="url(#${hid})"`) + seg(-1, 1, `class="paper"`) + seg(1, hi, `class="band"`);
      s += `<rect class="frame" x="${r1(sx(lo))}" y="${by0}" width="${r1(sx(hi) - sx(lo))}" height="${bh}"/>` + [-1, 1].map(v => `<line class="base" x1="${r1(sx(v))}" x2="${r1(sx(v))}" y1="${by0}" y2="${by1}"/>`).join("");
      const mid = (a, b) => sx((a + b) / 2), wide = (a, b, txt) => sx(b) - sx(a) > capsW(txt, 10.5) + 6;
      s += caps(mid(lo, -1), by0 - 7, wide(lo, -1, c ? "Forced" : "Airflow wins") ? (c ? "Forced" : "Airflow wins") : "", "middle") + caps(mid(-1, 1), by0 - 7, wide(-1, 1, "Mixed") ? "Mixed" : "", "middle") +
        caps(mid(1, hi), by0 - 7, wide(1, hi, c ? "Buoyancy" : "Buoyancy wins") ? (c ? "Buoyancy" : "Buoyancy wins") : "", "middle");
      const ticks = c || w < 420 ? [-2, 0, 2] : [-2, -1, 0, 1, 2], lab = v => v < 0 ? String(10 ** v) : String(10 ** v);
      s += ticks.map(v => T(sx(v), by1 + fs + 4, lab(v), "tk", "middle")).join("");
      const names = ["ISS", "Moon", "Mars", "Earth"], xr = e => sx(Math.max(lg(e.Ri), lo + 0.05)), anc = ["start", "end", "start", "start"];
      const items = D.envs.map((e, i) => ({ x: xr(e), anchor: anc[i], dark: i > 0, leader: by1 + 2,
        text: c ? `${names[i]} ${e.Ri < 0.01 ? "≈0" : e.Ri.toFixed(0)}` : `${e.name.replace(/ \(.*/, "")} ${e.Ri < 0.01 ? "≈ 0" : e.Ri.toFixed(0)}` }));
      s += D.envs.map(e => `<line class="mk" x1="${r1(xr(e))}" x2="${r1(xr(e))}" y1="${by0 - 2}" y2="${by1 + 2}"/>`).join("");
      const rows = chipRows(items, by1 + fs + 16 + CHIP_H / 2, step, { compact: c, bounds: w });
      s += rows.svg;
      if (!c) s += title(w - 2, by1 + fs + 16 + rows.rows * step + 14, "Richardson number", `${D.forced_cm_s} cm/s airflow · Moon, Mars: bounds`, "end");
      return s;
    }, { label: "Richardson number in ISS, Moon, Mars and Earth gravity: whether buoyancy or forced airflow dominates" });
  }

  // ---------- THM-09: Spalding B-number ----------
  function bnumberChart() {
    return host(sz => {
      const D = M().THM09, c = sz.compact, gap = c ? 18 : 32, pw = Math.floor((sz.w - gap) / 2), x = D.o2_pct, i0 = x.indexOf(21);
      const pnl = (sub, name, unit, series, yr, yt, mark, txt) => {
        const F = frame(sub, { x: [15, 50], y: yr, xticks: [20, 30, 40, 50], yticks: yt, xlabel: "Oxygen", xunit: "%", ylabel: name, yunit: unit, top: series.length > 1 ? 12 : 0 });
        const { sx, sy, X1 } = F; let s = F.axes;
        series.forEach(([ys, dashed, lab]) => { s += line(x.map((v, i) => [v, ys[i]]), sx, sy, { dashed }); if (lab) s += caps(X1, sy(ys[ys.length - 1]) + 15, lab, "end"); });
        const k = series[series.length - 1][0];
        s += dot(sx(21), sy(k[i0]), { r: 4.5 }) + chipRows([{ x: sx(21), anchor: "start", text: txt, dark: true, leader: sy(k[i0]) - 5 }], sy(yr[1] * 0.86), CHIP_H + 6, { compact: c, bounds: sub.w }).svg;
        return s;
      };
      return panel(sz, 0, pw, sub => pnl(sub, "B-number", "", [[D.b_ideal, true, c ? "Ideal" : "Ideal"], [D.b_eff, false, ""]], [0, 4.5], [0, 2, 4], D.air.b_eff, `${D.air.b_eff.toFixed(2)} in air`)) +
        panel(sz, pw + gap, pw, sub => pnl(sub, "Burn rate", "g/m²/s", [[D.flux_g_m2_s, false, ""]], [0, 7], [0, 2, 4, 6], D.air.flux, `${D.air.flux.toFixed(1)} in air`));
    }, { label: "Spalding B-number and surface burn rate of PMMA against oxygen level" });
  }

  // ---------- register ----------
  const P = "physics";
  MW.extend({
    thm01_flame_temp: { reg: { model: "THM-01", title: "Flame temperature by atmosphere", cat: "graph", status: P, size: "w",
      desc: "The hottest a flame can get (adiabatic flame temperature) for methane, hydrogen and propane burning with just enough oxygen in three atmospheres: ISS cabin air (21% O₂, 14.7 psi), the lunar habitat (30%, 10.2 psi) and a spacesuit (100% O₂, 4.3 psi). More oxygen means a hotter flame, and the calculation includes molecules splitting apart at high temperature, which takes about 100 K off methane's answer in air. It is a thermodynamic ceiling: real flames lose heat, so they run cooler.",
      render: () => flameTempChart() }, tile: () => flameTempChart(), shape: [2.0, 1.5, 3.0] },
    thm03_zst: { reg: { model: "THM-03", title: "Where a space flame sits", cat: "graph", status: P, size: "w",
      desc: "In microgravity a methane flame forms a sphere around a small burner (3.2 mm radius). The mixture fraction Z_st says how much of the gas at the flame came from the fuel; the flame sits where fuel and oxygen are in exactly the right proportion. Supplying more oxygen raises Z_st and pulls the flame much closer to the burner. The model classes Z_st below 0.12 as soot-prone (yellow, glowing) and above that as dim blue and soot-free, which for methane happens above roughly 55% oxygen. Idealised infinitely fast chemistry.",
      render: () => zstChart() }, tile: () => zstChart(), shape: [2.0, 1.6, 3.0] },
    thm07_blowoff: { reg: { model: "THM-07", title: "Airflow that blows a flame off", cat: "graph", status: P, size: "w",
      desc: "The Damköhler number compares how long gas takes to flow past the flame's edge with how long the chemistry needs. Above 1 the flame holds on; below 1 the airflow wins and the flame blows off. The curves show the number falling as ventilation speeds up, for ISS air and for the 30% oxygen lunar habitat, where the flame survives faster airflow. Uses a single-step reaction with generic constants, so read it as a trend, not a precise limit.",
      render: () => blowoffChart() }, tile: () => blowoffChart(), shape: [1.8, 1.4, 2.6] },
    thm08_richardson: { reg: { model: "THM-08", title: "Buoyancy vs forced airflow", cat: "visual", status: "bound", size: "w",
      desc: "The Richardson number compares buoyancy (hot gas rising) with forced ventilation. On the ISS buoyancy is almost zero, so airflow decides where heat and smoke go. On the Moon, Mars and Earth, buoyancy overtakes a 10 cm/s airflow around a 5 cm object and a rising plume forms. Moon and Mars values are theoretical scaling bounds: NASA's PSI archive has no partial-gravity combustion experiments.",
      render: () => richardsonGauge() }, tile: () => richardsonGauge(), shape: [2.4, 1.6, 3.4] },
    thm09_bnumber: { reg: { model: "THM-09", title: "How oxygen drives burning (B-number)", cat: "graph", status: P, size: "w",
      desc: "The Spalding B-number measures how strongly a flame pulls fuel off a solid surface. The ideal line ignores heat the hot surface radiates away; the solid line includes it, which matters in microgravity where airflow carries little heat. For PMMA at 15 cm/s, more oxygen raises both the B-number and the rate the plastic turns to gas. Right panel is that burn rate.",
      render: () => bnumberChart() }, tile: () => bnumberChart(), shape: [2.0, 1.6, 3.0] }
  });
})();
